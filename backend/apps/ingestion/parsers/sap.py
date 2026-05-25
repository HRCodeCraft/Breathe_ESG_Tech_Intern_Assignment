"""
SAP CSV flat-file parser.

Format: SAP SE16N / ME2M / MIGO report exports.

Real SAP exports we handle:
  - Fuel / combustion: based on MIGO (goods movement) data, typically pulled via
    SE16N on table MSEG or a custom ABAP report. Columns reflect MSEG field names:
    WERKS (plant), MATNR (material number), MENGE (quantity), MEINS (base unit),
    BLDAT (document date), BWART (movement type), MAKTX (material description).
  - Procurement: ME2M output (purchase orders by material), adds LIFNR (vendor),
    EKGRP (purchasing group), NETWR (net value).

Header aliases: SAP exports sometimes come with German headers depending on system
locale. We map both English and German variants to canonical field names.

Subset we handle (documented in DECISIONS.md):
  - Movement types 261 (goods issue to production), 201 (goods issue to cost centre),
    101/102 (goods receipt/return) for procurement
  - Fuel materials: diesel, petrol/gasoline, natural gas, LPG, heating oil
  - We do NOT handle: STO transfers (301/311), consignment (411), scrapping (551)
"""

import io
from decimal import Decimal
from typing import Iterator
import chardet
import pandas as pd

from .base import ParsedRow, parse_date_flexible, parse_decimal, sanitize_for_json
from apps.emissions.models import EmissionRecord

# Canonical column name → list of aliases (SAP English + German variants)
SAP_FUEL_COLUMN_MAP = {
    'plant':          ['WERKS', 'Plant', 'Werk'],
    'material_num':   ['MATNR', 'Material', 'Material Number', 'Materialnummer'],
    'material_desc':  ['MAKTX', 'Material Description', 'Materialbezeichnung'],
    'quantity':       ['MENGE', 'Quantity', 'Menge'],
    'unit':           ['MEINS', 'Base Unit', 'Basismengeneinheit', 'UoM'],
    'doc_date':       ['BLDAT', 'Document Date', 'Belegdatum'],
    'movement_type':  ['BWART', 'Mvt', 'Movement Type', 'Bewegungsart'],
    'cost_center':    ['KOSTL', 'Cost Center', 'Kostenstelle'],
    'batch':          ['CHARG', 'Batch', 'Charge'],
}

SAP_PROCUREMENT_COLUMN_MAP = {
    'plant':          ['WERKS', 'Plant', 'Werk'],
    'vendor':         ['LIFNR', 'Vendor', 'Lieferant'],
    'material_num':   ['MATNR', 'Material', 'Material Number'],
    'material_desc':  ['TXZ01', 'Short Text', 'Kurztext', 'Material Description'],
    'quantity':       ['MENGE', 'PO Quantity', 'Quantity'],
    'unit':           ['MEINS', 'UoM', 'Base Unit'],
    'doc_date':       ['BEDAT', 'Document Date', 'PO Date', 'Belegdatum'],
    'net_value':      ['NETWR', 'Net Value', 'Nettowert'],
    'currency':       ['WAERS', 'Currency', 'Währung'],
    'purch_group':    ['EKGRP', 'Purch. Group', 'Einkäufergruppe'],
    'cost_center':    ['KOSTL', 'Cost Center', 'Kostenstelle'],
}

# SAP unit codes → canonical unit
SAP_UNIT_MAP = {
    'L': 'litre', 'LT': 'litre', 'LTR': 'litre',
    'GL': 'gallon_us', 'GAL': 'gallon_us',
    'M3': 'm3', 'KM3': 'm3',
    'KG': 'kg', 'G': 'g', 'T': 'tonne',
    'KWH': 'kwh', 'MWH': 'mwh',
    'GJ': 'gj', 'MJ': 'mj',
    'NM3': 'nm3',  # normal cubic metres (gas)
    'ST': 'unit',  # piece/unit
}

# Fuel material prefixes/keywords → fuel type
FUEL_KEYWORDS = {
    'diesel': 'diesel',
    'petrol': 'petrol', 'gasoline': 'petrol', 'benzin': 'petrol',
    'natural gas': 'natural_gas', 'erdgas': 'natural_gas', 'cng': 'natural_gas',
    'lpg': 'lpg', 'autogas': 'lpg',
    'heating oil': 'heating_oil', 'heizoil': 'heating_oil',
    'fuel oil': 'fuel_oil',
    'kerosene': 'kerosene', 'jet': 'kerosene',
}

FUEL_MOVEMENT_TYPES = {'261', '201', '601', '543'}  # goods issue types
PROCUREMENT_RECEIPT_TYPES = {'101', '103', '105'}   # goods receipt types


def _detect_encoding(raw_bytes: bytes) -> str:
    result = chardet.detect(raw_bytes[:10000])
    return result.get('encoding') or 'utf-8'


def _resolve_columns(df: pd.DataFrame, col_map: dict) -> dict[str, str | None]:
    """Return {canonical_name: actual_df_column} for whatever columns exist."""
    df_cols_lower = {c.lower(): c for c in df.columns}
    resolved = {}
    for canonical, aliases in col_map.items():
        found = None
        for alias in aliases:
            if alias.lower() in df_cols_lower:
                found = df_cols_lower[alias.lower()]
                break
        resolved[canonical] = found
    return resolved


def _identify_fuel_type(material_num: str, material_desc: str) -> str:
    text = f"{material_num} {material_desc}".lower()
    for keyword, fuel_type in FUEL_KEYWORDS.items():
        if keyword in text:
            return fuel_type
    return 'unknown'


def _map_unit(sap_unit: str) -> str:
    return SAP_UNIT_MAP.get(sap_unit.upper().strip(), sap_unit.lower())


def parse_sap_fuel(file_bytes: bytes, file_name: str) -> Iterator[tuple[ParsedRow | None, dict, str | None]]:
    """
    Yield (parsed_row_or_none, raw_dict, error_message) for each data row.
    Caller is responsible for DB writes.
    """
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
        raise ValueError(f"Could not parse file as CSV: {last_err}")

    df.columns = [str(c).strip() for c in df.columns]
    cols = _resolve_columns(df, SAP_FUEL_COLUMN_MAP)

    required = ['quantity', 'unit', 'doc_date']
    missing = [r for r in required if cols.get(r) is None]
    if missing:
        raise ValueError(f"Required columns not found: {missing}. Got: {list(df.columns)}")

    for _, row in df.iterrows():
        raw = sanitize_for_json(row.to_dict())
        try:
            qty_raw = raw.get(cols['quantity'], '')
            qty = parse_decimal(qty_raw)
            if qty is None:
                yield None, raw, f"Could not parse quantity: {qty_raw!r}"
                continue
            if qty <= 0:
                flags = [EmissionRecord.Flag.ZERO_VALUE]
            else:
                flags = []

            unit_raw = str(raw.get(cols['unit'], '')).strip()
            unit_canonical = _map_unit(unit_raw)

            date_raw = str(raw.get(cols['doc_date'], '')).strip()
            activity_date = parse_date_flexible(date_raw)
            if activity_date is None:
                yield None, raw, f"Could not parse date: {date_raw!r}"
                continue

            mvt = str(raw.get(cols.get('movement_type') or '', '')).strip()
            mat_num = str(raw.get(cols.get('material_num') or '', '')).strip()
            mat_desc = str(raw.get(cols.get('material_desc') or '', '')).strip()
            plant = str(raw.get(cols.get('plant') or '', '')).strip()
            cost_ctr = str(raw.get(cols.get('cost_center') or '', '')).strip()

            fuel_type = _identify_fuel_type(mat_num, mat_desc)

            # Determine scope/category from movement type
            # 261/201/601 = goods issue (consumption) → Scope 1 stationary or mobile
            # We default to stationary_combustion; analyst can correct
            if mvt in FUEL_MOVEMENT_TYPES or mvt == '':
                scope = 1
                category = EmissionRecord.Category.STATIONARY_COMBUSTION
            else:
                flags.append(EmissionRecord.Flag.INCOMPLETE)
                scope = 1
                category = EmissionRecord.Category.STATIONARY_COMBUSTION

            if fuel_type == 'unknown':
                flags.append(EmissionRecord.Flag.MISSING_FACTOR)

            parsed = ParsedRow(
                scope=scope,
                category=category,
                subcategory=fuel_type,
                activity_date=activity_date,
                period_start=None,
                period_end=None,
                facility=plant,
                cost_center=cost_ctr,
                supplier='',
                description=f"{mat_desc} ({mat_num})" if mat_num else mat_desc,
                quantity=qty,
                unit=unit_raw,
                quantity_normalized=qty,  # will be converted by normalizer
                unit_normalized=unit_canonical,
                raw_data=raw,
                flags=flags,
            )
            yield parsed, raw, None

        except Exception as e:
            yield None, raw, str(e)


def parse_sap_procurement(file_bytes: bytes, file_name: str) -> Iterator[tuple[ParsedRow | None, dict, str | None]]:
    """
    Parse SAP ME2M procurement export.
    Procurement items = Scope 3, Cat 1 (Purchased Goods & Services).
    """
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
        raise ValueError(f"Could not parse procurement file: {last_err}")

    df.columns = [str(c).strip() for c in df.columns]
    cols = _resolve_columns(df, SAP_PROCUREMENT_COLUMN_MAP)

    for _, row in df.iterrows():
        raw = sanitize_for_json(row.to_dict())
        try:
            qty_raw = raw.get(cols.get('quantity') or '', '')
            qty = parse_decimal(qty_raw)
            if qty is None:
                yield None, raw, f"Could not parse quantity: {qty_raw!r}"
                continue

            unit_raw = str(raw.get(cols.get('unit') or '', 'unit')).strip()
            unit_canonical = _map_unit(unit_raw)

            date_raw = str(raw.get(cols.get('doc_date') or '', '')).strip()
            activity_date = parse_date_flexible(date_raw)
            if activity_date is None:
                yield None, raw, f"Could not parse date: {date_raw!r}"
                continue

            vendor = str(raw.get(cols.get('vendor') or '', '')).strip()
            plant = str(raw.get(cols.get('plant') or '', '')).strip()
            mat_desc = str(raw.get(cols.get('material_desc') or '', '')).strip()
            mat_num = str(raw.get(cols.get('material_num') or '', '')).strip()
            net_val = parse_decimal(raw.get(cols.get('net_value') or '', ''))

            flags = []
            if qty <= 0:
                flags.append(EmissionRecord.Flag.ZERO_VALUE)

            parsed = ParsedRow(
                scope=3,
                category=EmissionRecord.Category.PROCUREMENT,
                subcategory='purchased_goods',
                activity_date=activity_date,
                period_start=None,
                period_end=None,
                facility=plant,
                cost_center=str(raw.get(cols.get('cost_center') or '', '')).strip(),
                supplier=vendor,
                description=f"{mat_desc} ({mat_num})" if mat_num else mat_desc,
                quantity=qty,
                unit=unit_raw,
                quantity_normalized=qty,
                unit_normalized=unit_canonical,
                raw_data=raw,
                flags=flags,
            )
            yield parsed, raw, None

        except Exception as e:
            yield None, raw, str(e)
