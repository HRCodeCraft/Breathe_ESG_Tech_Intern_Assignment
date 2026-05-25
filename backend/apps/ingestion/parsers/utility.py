"""
Utility electricity parser — Green Button CSV format.

Green Button is the US ESPI (Energy Service Provider Interface) standard.
Adopted by: PG&E, ConEd, Duke Energy, National Grid, and most major US utilities.
Many UK/EU utilities export compatible CSVs from their portals (SSEN, Octopus, etc.)
with slight column variation — we handle both variants.

Green Button CSV columns:
  TYPE, DATE, START TIME, END TIME, USAGE, UNITS, COST, NOTES
  where:
    TYPE: 'Electric usage' or 'Gas usage'
    DATE: MM/DD/YYYY
    START TIME: HH:MM  (15-minute or hourly intervals, or monthly billing)
    END TIME: HH:MM
    USAGE: float
    UNITS: kWh, therms, CCF, etc.
    COST: float
    NOTES: freetext

Portal CSV variant (UK utilities, manual exports) uses:
  Meter Point, Billing Period Start, Billing Period End, Consumption (kWh),
  Tariff, Cost (GBP), Meter Serial

We handle both by trying Green Button first, then portal variant.

What we IGNORE:
  - Sub-15-minute interval data (demand charges, power factor)
  - Time-of-use tariff breakdown
  - Generation / export rows (negative usage)
"""

import io
from decimal import Decimal
from datetime import date, datetime
from typing import Iterator
import pandas as pd
import chardet

from .base import ParsedRow, parse_date_flexible, parse_decimal, sanitize_for_json
from apps.emissions.models import EmissionRecord

GREEN_BUTTON_DATE_FORMATS = [
    '%m/%d/%Y', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d',
]


def _detect_encoding(raw_bytes: bytes) -> str:
    result = chardet.detect(raw_bytes[:10000])
    return result.get('encoding') or 'utf-8'


def _parse_green_button(df: pd.DataFrame) -> Iterator[tuple[ParsedRow | None, dict, str | None]]:
    """Green Button CSV: TYPE | DATE | START TIME | END TIME | USAGE | UNITS | COST | NOTES"""
    df.columns = [str(c).strip().upper() for c in df.columns]

    # find usage and date columns
    col_usage = next((c for c in df.columns if 'USAGE' in c or 'CONSUMPTION' in c), None)
    col_date = next((c for c in df.columns if c in ('DATE', 'START DATE', 'BILL DATE')), None)
    col_start = next((c for c in df.columns if 'START' in c and 'DATE' not in c), None)
    col_end = next((c for c in df.columns if 'END' in c and 'DATE' not in c), None)
    col_units = next((c for c in df.columns if 'UNIT' in c), None)
    col_type = next((c for c in df.columns if 'TYPE' in c), None)

    if col_usage is None or col_date is None:
        return  # signal caller to try portal variant

    for _, row in df.iterrows():
        raw = sanitize_for_json(row.to_dict())
        try:
            row_type = str(raw.get(col_type or 'TYPE', 'Electric usage')).lower()
            if 'gas' in row_type:
                continue  # gas is Scope 1, different parser needed

            usage_raw = raw.get(col_usage, '')
            usage = parse_decimal(usage_raw)
            if usage is None:
                yield None, raw, f"Could not parse usage: {usage_raw!r}"
                continue
            if usage < 0:
                continue  # generation/export — skip

            date_str = str(raw.get(col_date, '')).strip()
            activity_date = parse_date_flexible(date_str, GREEN_BUTTON_DATE_FORMATS)
            if activity_date is None:
                yield None, raw, f"Could not parse date: {date_str!r}"
                continue

            unit_raw = str(raw.get(col_units or '', 'kwh')).strip().lower()
            unit_normalized = 'kwh'

            # Green Button can be 15-min intervals; sum daily in the pipeline
            # For now emit one row per data row — aggregation is a display concern
            flags = []
            if usage == 0:
                flags.append(EmissionRecord.Flag.ZERO_VALUE)

            parsed = ParsedRow(
                scope=2,
                category=EmissionRecord.Category.PURCHASED_ELECTRICITY,
                subcategory='grid_electricity',
                activity_date=activity_date,
                period_start=None,
                period_end=None,
                facility='',
                cost_center='',
                supplier='',
                description='Purchased electricity',
                quantity=usage,
                unit=unit_raw,
                quantity_normalized=usage,  # normalizer will convert if needed
                unit_normalized=unit_normalized,
                raw_data=raw,
                flags=flags,
            )
            yield parsed, raw, None

        except Exception as e:
            yield None, raw, str(e)


def _parse_portal_variant(df: pd.DataFrame) -> Iterator[tuple[ParsedRow | None, dict, str | None]]:
    """
    Portal CSV (UK/EU format): Meter Point | Billing Period Start | Billing Period End |
    Consumption (kWh) | Tariff | Cost | Meter Serial
    """
    df.columns = [str(c).strip() for c in df.columns]
    col_map_lower = {c.lower(): c for c in df.columns}

    def find(keys):
        for k in keys:
            if k.lower() in col_map_lower:
                return col_map_lower[k.lower()]
        return None

    col_start = find(['billing period start', 'start date', 'period start', 'date from'])
    col_end = find(['billing period end', 'end date', 'period end', 'date to'])
    col_usage = find(['consumption (kwh)', 'consumption', 'usage (kwh)', 'units consumed', 'kwh'])
    col_meter = find(['meter point', 'mpan', 'meter id', 'site', 'meter serial'])

    if col_usage is None or col_start is None:
        raise ValueError("Could not identify required columns in portal CSV variant")

    for _, row in df.iterrows():
        raw = sanitize_for_json(row.to_dict())
        try:
            usage_raw = raw.get(col_usage, '')
            usage = parse_decimal(usage_raw)
            if usage is None:
                yield None, raw, f"Could not parse consumption: {usage_raw!r}"
                continue
            if usage < 0:
                continue

            start_str = str(raw.get(col_start, '')).strip()
            period_start = parse_date_flexible(start_str)
            if period_start is None:
                yield None, raw, f"Could not parse billing period start: {start_str!r}"
                continue

            period_end = None
            if col_end:
                period_end = parse_date_flexible(str(raw.get(col_end, '')).strip())

            # Use mid-point of billing period as activity_date
            if period_end:
                mid = period_start + (period_end - period_start) / 2
                activity_date = mid if isinstance(mid, date) else period_start
            else:
                activity_date = period_start

            facility = str(raw.get(col_meter or '', '')).strip()

            flags = []
            if usage == 0:
                flags.append(EmissionRecord.Flag.ZERO_VALUE)

            parsed = ParsedRow(
                scope=2,
                category=EmissionRecord.Category.PURCHASED_ELECTRICITY,
                subcategory='grid_electricity',
                activity_date=activity_date,
                period_start=period_start,
                period_end=period_end,
                facility=facility,
                cost_center='',
                supplier='',
                description='Purchased electricity (billing period)',
                quantity=usage,
                unit='kwh',
                quantity_normalized=usage,
                unit_normalized='kwh',
                raw_data=raw,
                flags=flags,
            )
            yield parsed, raw, None

        except Exception as e:
            yield None, raw, str(e)


def parse_utility_electricity(file_bytes: bytes, file_name: str) -> Iterator[tuple[ParsedRow | None, dict, str | None]]:
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
        raise ValueError(f"Could not parse utility file: {last_err}")

    df.columns = [str(c).strip() for c in df.columns]

    # Detect which variant: Green Button has TYPE / DATE / USAGE / UNITS columns
    upper_cols = {c.upper() for c in df.columns}
    if 'TYPE' in upper_cols and 'USAGE' in upper_cols:
        yield from _parse_green_button(df)
    else:
        yield from _parse_portal_variant(df)
