"""
Corporate travel parser — SAP Concur Trip Detail Export format.

Why Concur: Market leader in enterprise T&E (~70% enterprise market share).
SAP Concur's standard export is a CSV called "Trip Detail Report" accessible from
Reporting > Standard Reports > Travel > Trip Detail.

Concur Trip Detail columns (relevant subset):
  Employee ID, Employee Name, Department, Trip Start Date, Trip End Date,
  Booking Type (AIR/HTL/CAR/TRN/LIM), Origin, Destination, Class of Service,
  Vendor Name, Nights (for hotels), Distance (for car/ground, sometimes absent),
  Distance Unit, Amount, Currency, Trip Purpose

Navan (formerly TripActions) exports a similar schema with slight column name
differences — we handle both via the alias map below.

Flight distance calculation:
  When 'Distance' is absent (common), we calculate great-circle distance
  between IATA airport codes using the Haversine formula.
  We add a +9% uplift factor per DEFRA methodology to account for holding patterns
  and non-direct routing.

What we ignore:
  - Per-segment fare breakdown (just total trip)
  - Carbon offsets purchased via the travel platform
  - Rail journeys in non-UK countries (emission factors differ significantly)
"""

import io
import math
from decimal import Decimal
from typing import Iterator
import pandas as pd
import chardet

from .base import ParsedRow, parse_date_flexible, parse_decimal, sanitize_for_json
from apps.emissions.models import EmissionRecord

TRAVEL_COLUMN_MAP = {
    'employee_id':    ['Employee ID', 'EmployeeID', 'Employee Id', 'Staff ID'],
    'employee_name':  ['Employee Name', 'EmployeeName', 'Traveler Name', 'Traveller'],
    'department':     ['Department', 'Cost Center', 'Cost Centre', 'Division'],
    'trip_start':     ['Trip Start Date', 'Start Date', 'Departure Date', 'Travel Date'],
    'trip_end':       ['Trip End Date', 'End Date', 'Return Date'],
    'booking_type':   ['Booking Type', 'BookingType', 'Segment Type', 'Type'],
    'origin':         ['Origin', 'From', 'Departure', 'Origin Airport', 'Pick-up Location'],
    'destination':    ['Destination', 'To', 'Arrival', 'Destination Airport', 'Drop-off Location'],
    'class_service':  ['Class of Service', 'Class', 'Service Class', 'Cabin Class'],
    'vendor':         ['Vendor Name', 'Vendor', 'Airline', 'Hotel Name', 'Car Company'],
    'nights':         ['Nights', 'Hotel Nights', 'Number of Nights'],
    'distance':       ['Distance', 'Miles', 'Kilometers', 'KM', 'Trip Distance'],
    'distance_unit':  ['Distance Unit', 'Unit', 'Distance Units'],
    'amount':         ['Amount', 'Total Amount', 'Cost', 'Fare'],
    'currency':       ['Currency', 'CCY'],
    'trip_purpose':   ['Trip Purpose', 'Purpose', 'Business Purpose'],
}

BOOKING_TYPES = {
    'air': EmissionRecord.Category.BUSINESS_TRAVEL_AIR,
    'flight': EmissionRecord.Category.BUSINESS_TRAVEL_AIR,
    'htl': EmissionRecord.Category.BUSINESS_TRAVEL_HOTEL,
    'hotel': EmissionRecord.Category.BUSINESS_TRAVEL_HOTEL,
    'car': EmissionRecord.Category.BUSINESS_TRAVEL_GROUND,
    'trn': EmissionRecord.Category.BUSINESS_TRAVEL_GROUND,
    'train': EmissionRecord.Category.BUSINESS_TRAVEL_GROUND,
    'rail': EmissionRecord.Category.BUSINESS_TRAVEL_GROUND,
    'lim': EmissionRecord.Category.BUSINESS_TRAVEL_GROUND,
    'taxi': EmissionRecord.Category.BUSINESS_TRAVEL_GROUND,
    'ground': EmissionRecord.Category.BUSINESS_TRAVEL_GROUND,
    'bus': EmissionRecord.Category.BUSINESS_TRAVEL_GROUND,
}

# Cabin class → radiative forcing multiplier (DEFRA 2024)
# Economy = baseline, business/first have higher per-km factors due to seat area
CABIN_CLASS_MULTIPLIER = {
    'economy': Decimal('1.0'),
    'economy class': Decimal('1.0'),
    'premium economy': Decimal('1.26'),
    'business': Decimal('2.40'),
    'business class': Decimal('2.40'),
    'first': Decimal('2.40'),
    'first class': Decimal('2.40'),
}

DEFRA_FLIGHT_UPLIFT = Decimal('1.09')  # 9% indirect routing/holding uplift


def _detect_encoding(raw_bytes: bytes) -> str:
    result = chardet.detect(raw_bytes[:10000])
    return result.get('encoding') or 'utf-8'


def _resolve_cols(df: pd.DataFrame) -> dict[str, str | None]:
    df_cols_lower = {c.lower(): c for c in df.columns}
    resolved = {}
    for canonical, aliases in TRAVEL_COLUMN_MAP.items():
        found = None
        for alias in aliases:
            if alias.lower() in df_cols_lower:
                found = df_cols_lower[alias.lower()]
                break
        resolved[canonical] = found
    return resolved


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _lookup_airport_coords(iata: str) -> tuple[float, float] | None:
    """Look up lat/lon from DB. Returns None if not found."""
    try:
        from apps.emissions.models import AirportCode
        ap = AirportCode.objects.get(iata=iata.upper().strip())
        return float(ap.latitude), float(ap.longitude)
    except Exception:
        return None


def _calculate_flight_distance_km(origin: str, destination: str) -> Decimal | None:
    o_coords = _lookup_airport_coords(origin)
    d_coords = _lookup_airport_coords(destination)
    if o_coords and d_coords:
        km = _haversine_km(*o_coords, *d_coords)
        return Decimal(str(round(km, 1))) * DEFRA_FLIGHT_UPLIFT
    return None


def parse_travel(file_bytes: bytes, file_name: str) -> Iterator[tuple[ParsedRow | None, dict, str | None]]:
    encoding = _detect_encoding(file_bytes)
    df = None
    last_err = None
    for sep in [',', ';', '\t']:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding, dtype=str, sep=sep)
            if len(df.columns) > 1:
                break
        except Exception as e:
            last_err = e
    if df is None or len(df.columns) <= 1:
        raise ValueError(f"Could not parse travel file: {last_err}")

    df.columns = [str(c).strip() for c in df.columns]
    cols = _resolve_cols(df)

    required = ['booking_type', 'trip_start']
    missing = [r for r in required if cols.get(r) is None]
    if missing:
        raise ValueError(f"Required travel columns not found: {missing}. Got: {list(df.columns)}")

    for _, row in df.iterrows():
        raw = sanitize_for_json(row.to_dict())
        try:
            booking_type_raw = str(raw.get(cols['booking_type'], '')).strip().lower()
            category = BOOKING_TYPES.get(booking_type_raw)
            if category is None:
                yield None, raw, f"Unknown booking type: {booking_type_raw!r}"
                continue

            date_str = str(raw.get(cols['trip_start'], '')).strip()
            activity_date = parse_date_flexible(date_str)
            if activity_date is None:
                yield None, raw, f"Could not parse trip start date: {date_str!r}"
                continue

            trip_end = None
            if cols.get('trip_end'):
                trip_end = parse_date_flexible(str(raw.get(cols['trip_end'], '')).strip())

            origin = str(raw.get(cols.get('origin') or '', '')).strip()
            destination = str(raw.get(cols.get('destination') or '', '')).strip()
            vendor = str(raw.get(cols.get('vendor') or '', '')).strip()
            department = str(raw.get(cols.get('department') or '', '')).strip()

            flags = []

            if category == EmissionRecord.Category.BUSINESS_TRAVEL_AIR:
                # Flights — quantity = distance in km
                dist = None
                if cols.get('distance'):
                    dist_raw = raw.get(cols['distance'], '')
                    dist = parse_decimal(dist_raw)
                    if dist and cols.get('distance_unit'):
                        unit_raw = str(raw.get(cols['distance_unit'], 'km')).lower()
                        if 'mile' in unit_raw or unit_raw == 'mi':
                            dist = dist * Decimal('1.60934')

                if dist is None or dist == 0:
                    dist = _calculate_flight_distance_km(origin, destination)
                    if dist is None:
                        flags.append(EmissionRecord.Flag.MISSING_FACTOR)
                        dist = Decimal('0')

                # Cabin class multiplier applied at emission calc time
                cabin_raw = str(raw.get(cols.get('class_service') or '', 'economy')).lower()
                multiplier = next(
                    (v for k, v in CABIN_CLASS_MULTIPLIER.items() if k in cabin_raw),
                    Decimal('1.0')
                )

                parsed = ParsedRow(
                    scope=3,
                    category=category,
                    subcategory=cabin_raw or 'economy',
                    activity_date=activity_date,
                    period_start=activity_date,
                    period_end=trip_end,
                    facility='',
                    cost_center=department,
                    supplier=vendor,
                    description=f"{origin} → {destination}",
                    quantity=dist,
                    unit='km',
                    quantity_normalized=dist * multiplier,
                    unit_normalized='km',
                    raw_data=raw,
                    flags=flags,
                )

            elif category == EmissionRecord.Category.BUSINESS_TRAVEL_HOTEL:
                # Hotels — quantity = room nights
                nights = parse_decimal(raw.get(cols.get('nights') or '', ''))
                if nights is None or nights == 0:
                    if trip_end and activity_date:
                        nights = Decimal(str((trip_end - activity_date).days)) or Decimal('1')
                    else:
                        nights = Decimal('1')
                        flags.append(EmissionRecord.Flag.INCOMPLETE)

                parsed = ParsedRow(
                    scope=3,
                    category=category,
                    subcategory='hotel_stay',
                    activity_date=activity_date,
                    period_start=activity_date,
                    period_end=trip_end,
                    facility=destination,
                    cost_center=department,
                    supplier=vendor,
                    description=f"Hotel: {vendor or destination}",
                    quantity=nights,
                    unit='nights',
                    quantity_normalized=nights,
                    unit_normalized='nights',
                    raw_data=raw,
                    flags=flags,
                )

            else:
                # Ground transport — quantity = distance in km
                dist = None
                if cols.get('distance'):
                    dist_raw = raw.get(cols['distance'], '')
                    dist = parse_decimal(dist_raw)
                    if dist and cols.get('distance_unit'):
                        unit_raw = str(raw.get(cols['distance_unit'], 'km')).lower()
                        if 'mile' in unit_raw or unit_raw == 'mi':
                            dist = dist * Decimal('1.60934')

                if dist is None:
                    dist = Decimal('0')
                    flags.append(EmissionRecord.Flag.INCOMPLETE)

                parsed = ParsedRow(
                    scope=3,
                    category=category,
                    subcategory=booking_type_raw,
                    activity_date=activity_date,
                    period_start=activity_date,
                    period_end=trip_end,
                    facility='',
                    cost_center=department,
                    supplier=vendor,
                    description=f"Ground transport: {origin} → {destination}",
                    quantity=dist,
                    unit='km',
                    quantity_normalized=dist,
                    unit_normalized='km',
                    raw_data=raw,
                    flags=flags,
                )

            yield parsed, raw, None

        except Exception as e:
            yield None, raw, str(e)
