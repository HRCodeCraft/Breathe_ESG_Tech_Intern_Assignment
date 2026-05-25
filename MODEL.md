# Data Model

## Overview

The model is built around three invariants:
1. Every row has a traceable origin — which file, which run, which row number.
2. Every change is logged — the audit table is append-only and never updated.
3. Emission figures are reproducible — factor, unit, and source are stored alongside the CO₂e value so you can re-derive the number without trusting a black box.

---

## Entity Map

```
Organization ──< User
             └──< IngestionRun ──< RawRecord ──── EmissionRecord
                                                        │
                                             EmissionFactor (lookup)
                                             UnitConversion (lookup)
                                             AirportCode (lookup)
                                             AuditEvent (append-only)
```

---

## Multi-tenancy

Every data table has a non-nullable `organization` FK. All API views filter by `request.user.organization` before any other logic. There is no cross-org query path in the codebase.

Row-level isolation is enforced in the queryset layer (DRF views), not the database layer. In production I'd add PostgreSQL row-level security policies as a second enforcement layer, but that's marked as a tradeoff.

---

## `Organization`

```
id            UUID PK
name          CharField
slug          SlugField (unique) — used in URLs, never changes
industry      CharField
reporting_year PositiveSmallIntegerField — which GHG inventory year this org is filing
```

The `reporting_year` field matters because emission factors change year to year (DEFRA publishes annually) and the year defines which boundary period an analyst is working against.

---

## `User`

Extends Django's `AbstractUser`. Added:
```
organization  FK → Organization
role          enum: admin | analyst | auditor
```

Three roles:
- **Admin**: full access, can manage users
- **Analyst**: can upload, approve, flag, edit records
- **Auditor**: read-only — can view approved records and audit log, cannot modify

Role enforcement is in view-level permissions, not model-level. Kept simple for the prototype.

---

## `IngestionRun`

One record per file upload. Acts as the "batch" concept.

```
id              UUID PK
organization    FK
source_type     enum: sap_fuel | sap_procurement | utility_electricity | travel
status          enum: pending | processing | completed | completed_with_errors | failed
uploaded_by     FK → User (nullable — system runs don't have a user)
uploaded_at     DateTimeField (auto)
completed_at    DateTimeField (nullable)
file_name       CharField — original filename preserved for traceability
raw_file        FileField — raw bytes stored for re-processing if needed
row_count       int — total rows in file
success_count   int — rows that produced EmissionRecords
error_count     int — rows that failed parsing
skipped_count   int — rows skipped as duplicates
error_log       JSONField — [{row, error_type, message}]
```

Why store `raw_file`: If emission factor tables are updated or we add a new parser feature, we can re-run ingestion against the original bytes without asking the client to re-upload. This matters in an audit context.

---

## `RawRecord`

Verbatim copy of every parsed row, regardless of outcome.

```
id            UUID PK
run           FK → IngestionRun
row_number    int
raw_data      JSONField — exact key/value dict from the CSV row
parse_status  enum: ok | error | skipped
parse_error   TextField — human-readable reason if status != ok
```

Why this exists: When an analyst asks "why does this number look wrong?", you can show them the exact original values. Without this, you'd have to go back to the file.

The `source_hash` on `EmissionRecord` (SHA-256 of key fields) makes `RawRecord.parse_status = 'skipped'` the deduplication signal — if a file is re-uploaded, we skip rows whose hash already exists rather than erroring.

---

## `EmissionRecord`

The core normalised record. One row = one measurable activity event.

```
id                      UUID PK
organization            FK
ingestion_run           FK → IngestionRun (nullable — allows manual entry)
raw_record              OneToOne → RawRecord (nullable)
source_hash             SHA-256 string (indexed) — deduplication key

--- GHG classification ---
scope                   int: 1 | 2 | 3
category                enum (see below)
subcategory             str — fuel type, cabin class, etc.

--- Activity timing ---
activity_date           Date — when the activity occurred
period_start            Date (nullable) — for billing periods that span months
period_end              Date (nullable)

--- Activity context ---
facility                str — plant code, meter MPAN, or site name
cost_center             str — SAP KOSTL
supplier                str — vendor name for procurement/travel
description             str — material description, route, hotel name

--- Raw quantity (as ingested) ---
quantity                Decimal(18,6)
unit                    str — exactly as it appeared in the source file

--- Normalised quantity (canonical unit for category) ---
quantity_normalized     Decimal(18,6)
unit_normalized         str — litre | kwh | kg | km | nights

--- Emission calculation ---
emission_factor         Decimal(18,8) — kgCO₂e per unit_normalized
emission_factor_source  str — e.g. "DEFRA_2024"
emission_factor_unit    str — what the factor is per
co2e_kg                 Decimal(18,4) — quantity_normalized × emission_factor
co2_kg                  Decimal(18,4)
ch4_kg                  Decimal(18,4)
n2o_kg                  Decimal(18,4)

--- Review workflow ---
status                  enum: pending | approved | flagged | rejected
flags                   JSONField list of flag codes
reviewed_by             FK → User (nullable)
reviewed_at             DateTimeField (nullable)
review_notes            TextField

--- Edit tracking ---
is_edited               bool — true if analyst changed any field after creation
edited_by               FK → User (nullable)
edited_at               DateTimeField (nullable)
original_values         JSONField — snapshot of edited fields before change
```

### Canonical units

| Category | Canonical unit | Why |
|---|---|---|
| Liquid fuels | litre | DEFRA factors are per litre; easier to cross-check than energy basis |
| Natural gas | kWh | Avoids density ambiguity of nm³ (varies with calorific value and pressure) |
| Electricity | kWh | Universal; utility data already in kWh |
| Flights | km (× cabin class uplift × 1.09 routing) | DEFRA per-km methodology |
| Hotels | nights | DEFRA factor is per hotel night |
| Ground transport | km | DEFRA per-km |
| Procurement | kg or unit | Spend-based factors also supported, quantity tracked for material-based |

### GHG categories

```
Scope 1: stationary_combustion, mobile_combustion
Scope 2: purchased_electricity
Scope 3: business_travel_air, business_travel_hotel, business_travel_ground, procurement, waste
```

Follows GHG Protocol Corporate Standard categorisation.

---

## `EmissionFactor`

Reference table. Seeded from DEFRA 2024 and EPA eGRID 2023 at startup.

```
category        str
subcategory     str — fuel type or travel mode
unit            str — canonical unit this factor applies per
co2e_per_unit   Decimal(18,8)
co2_per_unit    Decimal(18,8)
ch4_per_unit    Decimal(18,8)
n2o_per_unit    Decimal(18,8)
factor_source   enum: DEFRA_2024 | EPA_2023 | IPCC_AR6 | GHG_PROTOCOL
valid_from      Date
valid_to        Date (nullable — null means currently valid)
```

Versioned so when DEFRA 2025 factors are published, you can add new rows without deleting old ones. The lookup always picks the most recent `valid_from` row for a given category/subcategory pair.

---

## `UnitConversion`

```
from_unit   str (unique)
to_unit     str — canonical unit
multiplier  Decimal(20,10)
notes       str
```

Handles the long tail of unit spellings: SAP `GL` → `litre`, `NM3` → `kwh` (with average calorific value), etc.

---

## `AirportCode`

```
iata        char(3) PK
name        str
city        str
country     str
latitude    Decimal(9,6)
longitude   Decimal(9,6)
```

Used by the travel parser to calculate great-circle distance when Concur/Navan don't provide it. Seeded with 30 airports covering the client's likely travel footprint; can be extended.

---

## `AuditEvent`

Append-only. No `UPDATE` or `DELETE` on this table in production (enforced by removing those permissions from the DB role).

```
id                  UUID PK
organization        FK
user                FK → User (nullable — system events)
action              enum: record_created | record_edited | record_approved |
                          record_flagged | record_rejected | bulk_approved |
                          bulk_flagged | run_started | run_completed | run_failed
timestamp           DateTimeField (auto_now_add — immutable)
emission_record_id  UUID (nullable, not a FK to avoid cascade delete)
ingestion_run_id    UUID (nullable)
before_state        JSONField — serialized record state before action
after_state         JSONField — serialized record state after action
metadata            JSONField — {count, ids, notes, file_name, etc.}
ip_address          GenericIPAddressField
```

Why store IDs rather than FKs: If a record is eventually deleted (e.g. rejected and cleaned up), the audit event should still be readable. Foreign key constraints would cascade.

---

## Source-of-truth tracking

The `source_hash` field answers "have I seen this activity before?". It is a SHA-256 of:
```json
{
  "org": "<uuid>",
  "source_type": "<type>",
  "category": "<category>",
  "activity_date": "<iso-date>",
  "facility": "<plant/meter>",
  "quantity": "<decimal string>",
  "unit": "<raw unit>",
  "supplier": "<vendor>"
}
```

Keys are sorted before hashing so field ordering doesn't affect the result.

When a file is re-uploaded, rows whose hash already exists are `skipped` in `RawRecord` rather than creating duplicate `EmissionRecord`s. The analyst sees the skip count in the ingestion run summary.

---

## What's not in the model (deliberate)

- **Organisational hierarchy** (divisions, business units, sub-entities): not needed for MVP. Multi-tenancy by org is sufficient.
- **Custom emission factor overrides per org**: relevant for orgs with market-based Scope 2 (supplier-specific EFs), but adds complexity. Tradeoff documented.
- **Reporting period close/lock**: in production you'd lock a period so approved records can't be modified after the auditor signs off. Not implemented — see TRADEOFFS.md.
