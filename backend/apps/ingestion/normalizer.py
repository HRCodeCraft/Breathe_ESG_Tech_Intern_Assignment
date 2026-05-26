"""
Unit normalization and emission factor lookup engine.

Converts raw parsed quantities to canonical units, then applies
DEFRA/EPA emission factors to compute kgCO2e.

Canonical units by category:
  - Liquid fuels (diesel, petrol, heating oil): litres
  - Gaseous fuels (natural gas): kwh (energy basis, avoids nm3 density ambiguity)
  - Solid fuels (coal): kg
  - Electricity: kwh
  - Flights: km (already multiplied by cabin class factor in parser)
  - Hotels: nights
  - Ground transport: km
  - Procurement: kg or unit (depends on material)
"""

from decimal import Decimal
from typing import Optional

from apps.ingestion.parsers.base import ParsedRow
from apps.emissions.models import EmissionRecord, EmissionFactor, UnitConversion

# Hardcoded fallback factors (kgCO2e per canonical unit) for when DB is not seeded.
# Sources: DEFRA GHG Conversion Factors 2024, UK Gov.
# Values are intentionally not buried in a magic constant — see data/emission_factors.json
# for the full table loaded at migration time.
FALLBACK_FACTORS: dict[tuple, dict] = {
    ('stationary_combustion', 'diesel'):       {'factor': Decimal('2.5390'), 'unit': 'litre', 'source': 'DEFRA_2024'},
    ('stationary_combustion', 'petrol'):       {'factor': Decimal('2.1978'), 'unit': 'litre', 'source': 'DEFRA_2024'},
    ('stationary_combustion', 'natural_gas'):  {'factor': Decimal('0.2020'), 'unit': 'kwh',   'source': 'DEFRA_2024'},
    ('stationary_combustion', 'lpg'):          {'factor': Decimal('1.5550'), 'unit': 'litre', 'source': 'DEFRA_2024'},
    ('stationary_combustion', 'heating_oil'):  {'factor': Decimal('2.5157'), 'unit': 'litre', 'source': 'DEFRA_2024'},
    ('stationary_combustion', 'fuel_oil'):     {'factor': Decimal('3.1493'), 'unit': 'litre', 'source': 'DEFRA_2024'},
    ('stationary_combustion', 'kerosene'):     {'factor': Decimal('2.5416'), 'unit': 'litre', 'source': 'DEFRA_2024'},
    ('mobile_combustion', 'diesel'):           {'factor': Decimal('2.5390'), 'unit': 'litre', 'source': 'DEFRA_2024'},
    ('mobile_combustion', 'petrol'):           {'factor': Decimal('2.1978'), 'unit': 'litre', 'source': 'DEFRA_2024'},
    ('purchased_electricity', 'grid_electricity'): {'factor': Decimal('0.20705'), 'unit': 'kwh', 'source': 'DEFRA_2024'},
    ('business_travel_air', 'economy'):        {'factor': Decimal('0.18861'), 'unit': 'km',   'source': 'DEFRA_2024'},
    ('business_travel_air', 'premium economy'):{'factor': Decimal('0.23752'), 'unit': 'km',   'source': 'DEFRA_2024'},
    ('business_travel_air', 'business'):       {'factor': Decimal('0.45268'), 'unit': 'km',   'source': 'DEFRA_2024'},
    ('business_travel_air', 'first'):          {'factor': Decimal('0.45268'), 'unit': 'km',   'source': 'DEFRA_2024'},
    ('business_travel_hotel', 'hotel_stay'):   {'factor': Decimal('16.10'),   'unit': 'nights','source': 'DEFRA_2024'},
    ('business_travel_ground', 'car'):         {'factor': Decimal('0.14549'), 'unit': 'km',   'source': 'DEFRA_2024'},
    ('business_travel_ground', 'taxi'):        {'factor': Decimal('0.14931'), 'unit': 'km',   'source': 'DEFRA_2024'},
    ('business_travel_ground', 'trn'):         {'factor': Decimal('0.03549'), 'unit': 'km',   'source': 'DEFRA_2024'},
    ('business_travel_ground', 'train'):       {'factor': Decimal('0.03549'), 'unit': 'km',   'source': 'DEFRA_2024'},
    ('procurement', 'purchased_goods'):        {'factor': Decimal('0.0'),     'unit': 'kg',   'source': 'SPEND_BASED'},
}

# Unit conversion to canonical units
UNIT_CONVERSIONS: dict[str, tuple[str, Decimal]] = {
    # Volume (→ litres)
    'gallon_us':  ('litre', Decimal('3.78541')),
    'gallon_uk':  ('litre', Decimal('4.54609')),
    'gal':        ('litre', Decimal('3.78541')),
    'm3':         ('litre', Decimal('1000')),
    'nm3':        ('litre', Decimal('1000')),    # approx; gas density varies
    'ml':         ('litre', Decimal('0.001')),
    # Mass (→ kg)
    'g':          ('kg', Decimal('0.001')),
    'tonne':      ('kg', Decimal('1000')),
    't':          ('kg', Decimal('1000')),
    'lb':         ('kg', Decimal('0.453592')),
    'lbs':        ('kg', Decimal('0.453592')),
    # Energy (→ kWh)
    'mj':         ('kwh', Decimal('0.277778')),
    'gj':         ('kwh', Decimal('277.778')),
    'mwh':        ('kwh', Decimal('1000')),
    'therm':      ('kwh', Decimal('29.3001')),
    'therms':     ('kwh', Decimal('29.3001')),
    'mmbtu':      ('kwh', Decimal('293.071')),
    'btu':        ('kwh', Decimal('0.000293071')),
    # Distance (→ km)
    'mile':       ('km', Decimal('1.60934')),
    'miles':      ('km', Decimal('1.60934')),
    'mi':         ('km', Decimal('1.60934')),
}

# Canonical units — no conversion needed
CANONICAL_UNITS = {'litre', 'kwh', 'kg', 'km', 'nights', 'unit', 'nm3', 'm3'}


def normalize_unit(quantity: Decimal, unit: str) -> tuple[Decimal, str]:
    """Return (normalized_quantity, canonical_unit)."""
    unit_lower = unit.lower().strip()
    if unit_lower in CANONICAL_UNITS:
        return quantity, unit_lower

    # Try DB first
    try:
        conv = UnitConversion.objects.get(from_unit=unit_lower)
        return quantity * conv.multiplier, conv.to_unit
    except UnitConversion.DoesNotExist:
        pass

    # Fallback hardcoded
    if unit_lower in UNIT_CONVERSIONS:
        to_unit, multiplier = UNIT_CONVERSIONS[unit_lower]
        return quantity * multiplier, to_unit

    # Unknown unit — return as-is, flag it
    return quantity, unit_lower


def lookup_emission_factor(category: str, subcategory: str) -> Optional[dict]:
    """
    Look up kgCO2e factor. DB takes precedence over hardcoded fallbacks.
    Returns dict with keys: factor, unit, source (or None if not found).
    """
    try:
        ef = EmissionFactor.objects.filter(
            category=category,
            subcategory__iexact=subcategory
        ).order_by('-valid_from').first()
        if ef:
            return {
                'factor': ef.co2e_per_unit,
                'co2': ef.co2_per_unit,
                'ch4': ef.ch4_per_unit,
                'n2o': ef.n2o_per_unit,
                'unit': ef.unit,
                'source': ef.factor_source,
            }
    except Exception:
        pass

    key = (category, subcategory)
    fb = FALLBACK_FACTORS.get(key)
    if fb:
        return {**fb, 'co2': fb['factor'], 'ch4': Decimal('0'), 'n2o': Decimal('0')}

    # Try with 'unknown' subcategory for generic category factor
    for (cat, sub), fb in FALLBACK_FACTORS.items():
        if cat == category:
            return {**fb, 'co2': fb['factor'], 'ch4': Decimal('0'), 'n2o': Decimal('0')}

    return None


def compute_emissions(row: ParsedRow) -> dict:
    """
    Normalize units and compute CO2e for a ParsedRow.
    Returns dict of fields to set on EmissionRecord.
    """
    qty_norm, unit_norm = normalize_unit(row.quantity, row.unit)
    ef = lookup_emission_factor(row.category, row.subcategory)

    flags = list(row.flags)

    if ef is None:
        flags.append(EmissionRecord.Flag.MISSING_FACTOR)
        co2e = None
        factor_val = None
        factor_unit = None
        factor_source = ''
        co2_kg = ch4_kg = n2o_kg = None
    else:
        factor_val = ef['factor']
        factor_unit = ef['unit']
        factor_source = ef['source']

        if unit_norm != factor_unit:
            # Try one more conversion pass toward the factor's expected unit
            qty_for_factor, converted_unit = normalize_unit(qty_norm, unit_norm)
            if converted_unit != factor_unit:
                flags.append(EmissionRecord.Flag.UNIT_MISMATCH)
        else:
            qty_for_factor = qty_norm

        co2e = qty_for_factor * factor_val
        co2_kg = qty_for_factor * ef.get('co2', factor_val)
        ch4_kg = qty_for_factor * ef.get('ch4', Decimal('0'))
        n2o_kg = qty_for_factor * ef.get('n2o', Decimal('0'))

    # Deduplicate flags
    flags = list(dict.fromkeys(flags))

    return {
        'quantity_normalized': qty_norm,
        'unit_normalized': unit_norm,
        'emission_factor': factor_val,
        'emission_factor_source': factor_source,
        'emission_factor_unit': factor_unit or '',
        'co2e_kg': co2e,
        'co2_kg': co2_kg,
        'ch4_kg': ch4_kg,
        'n2o_kg': n2o_kg,
        'flags': flags,
    }
