"""
Base parser class and shared utilities.
"""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass
class ParsedRow:
    """Intermediate representation after parsing, before DB write."""
    scope: int
    category: str
    subcategory: str
    activity_date: date
    period_start: date | None
    period_end: date | None
    facility: str
    cost_center: str
    supplier: str
    description: str
    quantity: Decimal
    unit: str
    quantity_normalized: Decimal
    unit_normalized: str
    raw_data: dict
    flags: list = field(default_factory=list)


def make_source_hash(org_id: str, source_type: str, row: ParsedRow) -> str:
    """
    Deterministic hash used to detect duplicate uploads.
    Intentionally excludes fields that vary between runs (timestamps, file names).
    """
    key = json.dumps({
        'org': str(org_id),
        'source_type': source_type,
        'category': row.category,
        'activity_date': row.activity_date.isoformat() if row.activity_date else None,
        'facility': row.facility,
        'quantity': str(row.quantity),
        'unit': row.unit,
        'supplier': row.supplier,
    }, sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()


# SAP German-locale date formats we need to handle
SAP_DATE_FORMATS = [
    '%d.%m.%Y',   # 31.12.2024 — standard SAP display format
    '%Y%m%d',     # 20241231 — SAP internal YYYYMMDD
    '%d/%m/%Y',   # 31/12/2024 — some regional configs
    '%m/%d/%Y',   # 12/31/2024 — US SAP configs
    '%Y-%m-%d',   # ISO, rare in SAP but possible in BW extracts
]


def parse_date_flexible(value: str, formats=SAP_DATE_FORMATS) -> date | None:
    from datetime import datetime
    value = str(value).strip()
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def sanitize_for_json(d: dict) -> dict:
    """Convert pandas NaN/float NaN to None so the dict is JSON-serializable."""
    import math
    result = {}
    for k, v in d.items():
        if isinstance(v, float) and math.isnan(v):
            result[str(k)] = None
        else:
            result[str(k)] = str(v) if v is not None else None
    return result


def parse_decimal(value: Any) -> Decimal | None:
    """Handle SAP's German decimal separators (1.234,56) and normal floats."""
    if value is None or str(value).strip() in ('', '-', 'N/A', 'NULL'):
        return None
    s = str(value).strip()
    # German format: periods as thousands separator, comma as decimal
    if ',' in s and '.' in s:
        if s.index('.') < s.index(','):
            s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return Decimal(s)
    except Exception:
        return None
