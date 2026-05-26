# Breathe ESG — Complete Technical & Business Guide

Everything a reviewer, interviewer, or new team member needs to understand this codebase. Covers the business problem, every technical decision, the data model, and what comes next.

---

## Table of Contents

1. [The Business Problem](#1-the-business-problem)
2. [What Are Scope 1, 2, and 3 Emissions?](#2-what-are-scope-1-2-and-3-emissions)
3. [Why Companies Need This Platform](#3-why-companies-need-this-platform)
4. [What This Platform Does (Feature by Feature)](#4-what-this-platform-does-feature-by-feature)
5. [Data Sources — Why These Three?](#5-data-sources--why-these-three)
6. [The Data Model](#6-the-data-model)
7. [How Ingestion Works (End-to-End)](#7-how-ingestion-works-end-to-end)
8. [Emission Factors — DEFRA 2024](#8-emission-factors--defra-2024)
9. [Anomaly Detection](#9-anomaly-detection)
10. [The Audit Trail](#10-the-audit-trail)
11. [Technology Choices](#11-technology-choices)
12. [Architecture Decisions](#12-architecture-decisions)
13. [Security](#13-security)
14. [What's Not Built (and Why)](#14-whats-not-built-and-why)
15. [Business Metrics This Platform Enables](#15-business-metrics-this-platform-enables)
16. [Recruiter Q&A](#16-recruiter-qa)

---

## 1. The Business Problem

Companies must report their greenhouse gas (GHG) emissions to regulators, investors, and customers. In the UK, large companies must comply with SECR (Streamlined Energy and Carbon Reporting). Listed companies increasingly face TCFD (Task Force on Climate-related Financial Disclosures) requirements. Globally, the EU's CSRD (Corporate Sustainability Reporting Directive) from 2024 mandates detailed emissions reporting for ~50,000 companies.

**The current reality at most companies:**  
Emissions data lives in 4–6 different systems — the ERP (SAP), utility portals, travel booking tools, procurement systems. Finance exports CSVs. Someone pastes them into a shared Excel file. Formulas break. Factors go stale. Version history disappears. Auditors can't verify anything. The CFO signs a number nobody is confident in.

**What this platform replaces:**  
A structured ingestion pipeline that reads the raw exports those systems already produce, normalizes them to a single unit system, applies vetted emission factors, flags anomalies automatically, and creates an immutable audit trail from raw data to final signed-off figure.

---

## 2. What Are Scope 1, 2, and 3 Emissions?

Defined by the **GHG Protocol Corporate Standard** (the global standard used by 92% of Fortune 500 companies):

| Scope | Definition | Examples in this platform |
|---|---|---|
| **Scope 1** | Direct emissions from sources owned or controlled by the company | Natural gas boilers, diesel generators, company fleet fuel (from SAP fuel data) |
| **Scope 2** | Indirect emissions from purchased electricity, heat, steam | Grid electricity consumption (from utility meter data) |
| **Scope 3** | All other indirect emissions in the value chain | Business flights, hotel stays, ground transport, purchased goods/services (from travel data + procurement) |

Scope 3 is typically 70–90% of a company's total footprint but is hardest to measure because the data is fragmented across suppliers and booking platforms.

**What is CO₂e?**  
Different greenhouse gases have different warming potentials. CO₂e (carbon dioxide equivalent) converts everything to a single number using GWP (Global Warming Potential) values from the IPCC AR5 report:
- CO₂: 1× (the baseline)
- CH₄ (methane): 25×
- N₂O (nitrous oxide): 298×

So if a boiler emits 1 kg CH₄, that's recorded as 25 kg CO₂e.

---

## 3. Why Companies Need This Platform

**The Excel problem at scale:**
- A mid-size company (500 employees, 3 offices) typically generates 2,000–5,000 emissions-relevant transactions per year across all three scopes.
- Manual Excel-based processes take 3–6 person-weeks per reporting cycle.
- Error rates in manually compiled emissions reports are estimated at 10–30% (Carbon Disclosure Project, 2022).
- External auditors charge £10,000–£50,000 to verify a report — and can't verify what has no audit trail.

**The regulatory risk:**
- SECR fines for non-compliance: up to £500/day.
- CSRD (EU) requires third-party assurance from 2025, meaning auditors must be able to trace every number back to a source document.
- Greenwashing risk: if a company publishes an emissions figure that is later found to be wrong, reputational and legal consequences are severe.

**What the platform solves specifically:**
1. Data fragmentation — pulls from 4 source types in one place
2. Manual effort — parse → normalize → calculate → review in minutes, not weeks
3. Auditability — every record has a traceable chain from raw CSV row to final CO₂e figure
4. Factor freshness — emission factors are versioned; updated factors can be applied to historical data without losing the original calculation

---

## 4. What This Platform Does (Feature by Feature)

### Ingestion
Upload a CSV. The system:
1. Detects which parser to use (SAP Fuel, SAP Procurement, Green Button electricity, or Concur travel)
2. Parses every row, handling format quirks (German decimal separators, SAP date formats, IATA codes)
3. Creates a `RawRecord` (verbatim copy of the parsed row) for full traceability
4. Normalizes units and calculates CO₂e
5. Checks for duplicates using a SHA-256 hash of identifying fields
6. Creates an `EmissionRecord` in `pending` status
7. Runs statistical outlier detection across the batch
8. Logs an `AuditEvent` for the ingestion run

### Review Queue
Analysts see all `pending` records. They can:
- Filter by scope, category, status, flags, date range, facility, supplier
- Sort by any column
- Expand a row to see gas breakdown (CO₂, CH₄, N₂O separately), the raw values, the emission factor used and its source
- Approve, flag, or reject individually or in bulk
- Add a note to every action (recorded in the audit log)

### Dashboard
Real-time KPIs visible immediately after login:
- Total CO₂e (approved records only — pending doesn't inflate the number)
- Scope 1 / 2 / 3 breakdown with tonnes CO₂e
- Top emission categories (bar chart)
- Monthly trend (area chart, by scope)
- Pending / flagged counts requiring attention

### Audit Log
Every state change is recorded as an immutable `AuditEvent`:
- Who did it (user FK)
- When (UTC timestamp)
- What changed (before/after JSON snapshot)
- Why (notes field)
- Which record or ingestion run it relates to

Audit events cannot be updated or deleted — the Django admin has change/delete permissions removed for `AuditEvent`.

---

## 5. Data Sources — Why These Three?

### SAP Fuel (SE16N / ME2M format)
SAP is the ERP used by ~80% of large enterprises. Fuel and energy consumption is tracked in the MM (Materials Management) and CO (Controlling) modules. The most accessible export is SE16N (table viewer) or ME2M (purchase orders by material) — both produce CSV. These contain goods receipt records from table MSEG with material descriptions that identify fuel type.

**Format challenges handled:**
- German decimal separators: `1.234,56` (dot = thousands, comma = decimal)
- DD.MM.YYYY date format
- German column headers (WERKS, MENGE, MEINS, BLDAT) alongside English aliases
- SAP unit codes: L (litres), GL (gallons), KWH, NM3 (normal cubic meters), KG

### Utility Electricity (Green Button CSV)
Green Button is the US DOE/NIST standard (ESPI — Energy Service Provider Interface) for electricity usage data. Utilities that participate in Green Button can export consumption data in a standard CSV format. The UK equivalent (Portal CSV) has slightly different column names but the same structure. Both are handled with automatic format detection.

**Why not API?** Green Button Connect (the API version) exists but requires utility-specific OAuth setup for each energy provider. CSV export is universal and works with any utility.

### Corporate Travel (SAP Concur)
SAP Concur is the dominant T&E (Travel & Expense) platform, used by 95 of the Fortune 100. Its Trip Detail Export produces a CSV with booking type codes (AIR, HTL, CAR, TRN, LIM) and trip details. This covers Scope 3 categories 6 (business travel) directly.

**What's non-trivial:**
- **Haversine distance calculation**: Concur records often don't include flight distance. The platform looks up IATA codes from a seeded airport table (30 major airports) and calculates great-circle distance using the Haversine formula.
- **Routing uplift**: DEFRA recommends adding 9% to great-circle distance to account for non-direct routing.
- **Cabin class multipliers**: Business class has a higher per-km emission factor than economy due to seat pitch (more space per passenger = proportionally higher allocation). Multipliers: Economy 1.0×, Premium Economy 1.6×, Business 2.0×, First 2.9×.
- **Hotel nights**: Derived from trip_start / trip_end dates when a "Nights" column is absent.

---

## 6. The Data Model

### Core entities

**Organization** — the tenant. Every data record has an `organization` FK. All API querysets filter by `request.user.organization`. A user from Company A can never see Company B's data.

**User** — extends Django's AbstractUser. Adds `organization` FK and `role` enum (admin / analyst / auditor). Role determines what actions are permitted (currently enforced at view level; can be moved to permission classes).

**IngestionRun** — one record per file upload. Tracks status (pending → processing → completed / failed), file name, row counts (success / error / skipped), and error log (JSON array of `{row, error_type, message}`).

**RawRecord** — verbatim parsed version of every CSV row. Stored as JSON in `raw_data`. Never modified. Exists for traceability: if the emission calculation is ever questioned, the original raw value is always available.

**EmissionRecord** — the normalized, calculated record. Key fields:
- `scope` (1/2/3), `category` (stationary_combustion, purchased_electricity, business_travel_air…)
- `activity_date` — the date the activity occurred (not upload date)
- `quantity` + `unit` — raw values from source
- `quantity_normalized` + `unit_normalized` — after unit conversion
- `emission_factor` — the factor applied (kg CO₂e per unit)
- `co2e_kg`, `co2_kg`, `ch4_kg`, `n2o_kg` — calculated values
- `status` — pending / approved / flagged / rejected
- `flags` — JSON array: outlier, duplicate, missing_factor, zero_value, etc.
- `source_hash` — SHA-256 of (org, source_type, category, activity_date, facility, quantity, unit, supplier). Duplicate uploads of the same data produce the same hash → skipped.

**EmissionFactor** — versioned reference table. Fields: category, subcategory, unit, factor (kg CO₂e/unit), co2_factor, ch4_factor, n2o_factor, source (DEFRA 2024), valid_from, valid_to. Allows historical recalculation when factors are updated.

**AuditEvent** — append-only. Stores action enum, user FK, before_state/after_state JSON, metadata JSON (notes, count, file_name). Admin permissions: no change, no delete.

### Source hash — why SHA-256?

Re-uploading the same file is inevitable: an analyst downloads the SAP report for Q1, uploads it, then realizes they forgot to filter by plant and uploads again. Without deduplication, every row doubles.

The hash is computed over the set of fields that uniquely identify a real-world activity: organization + source_type + category + activity_date + facility + quantity + unit + supplier. If those 8 fields match an existing record, the new row is skipped (recorded as `skipped` in `RawRecord`, increments `skipped_count` on the `IngestionRun`).

---

## 7. How Ingestion Works (End-to-End)

```
Upload CSV
    │
    ▼
View (views.py)
  · Read file bytes BEFORE model save (avoids stream exhaustion)
  · Create IngestionRun (status=pending)
  · Pass bytes to run_ingestion()
    │
    ▼
Parser (parsers/sap.py | utility.py | travel.py)
  · Try comma / semicolon / tab as delimiter
  · Map column headers (English + German aliases)
  · Parse dates (DD.MM.YYYY, YYYY-MM-DD, MM/DD/YYYY…)
  · Parse decimals (German: "1.234,56" → 1234.56)
  · Return list[ParsedRow]
    │
    ▼
Normalizer (normalizer.py)
  · Convert unit → canonical unit (DB lookup → fallback dict)
  · Look up emission factor (DB lookup → fallback dict)
  · Calculate co2e_kg = quantity_normalized × factor
  · Decompose into co2_kg, ch4_kg, n2o_kg
  · Return flags (missing_factor, zero_value, unit_mismatch)
    │
    ▼
Pipeline (pipeline.py)
  · Pre-fetch existing hashes (avoid N+1 queries)
  · For each row: hash → skip if duplicate, else create EmissionRecord
  · Bulk create RawRecords + EmissionRecords
  · Run 3σ outlier detection on co2e_kg within this batch
  · Update IngestionRun counts
  · Create AuditEvent (run_complete)
```

**Why read file bytes before model save?**  
Django's `InMemoryUploadedFile` is a stream. `model.raw_file = file` triggers Django to read and save the stream. After that, calling `file.read()` returns empty bytes. The fix: `bytes = file.read(); file.seek(0); model.raw_file = file` — read first, seek back, then let Django save.

**Why try multiple delimiters?**  
`pd.read_csv(sep=None, engine='python')` fails on `io.BytesIO` in some environments (it tries to sniff the delimiter from the file object but can't seek properly). Explicit try-loop over `[',', ';', '\t']` is deterministic and fast.

---

## 8. Emission Factors — DEFRA 2024

DEFRA (UK Department for Environment, Food & Rural Affairs) publishes the most widely used emission factor dataset for UK companies. The 2024 dataset is used here. Key factors seeded:

| Category | Example factor |
|---|---|
| Natural gas | 0.18316 kg CO₂e / kWh |
| Diesel | 2.6808 kg CO₂e / litre |
| Grid electricity (UK) | 0.20493 kg CO₂e / kWh |
| Short-haul flight (economy) | 0.15525 kg CO₂e / passenger-km |
| Long-haul flight (economy) | 0.19085 kg CO₂e / passenger-km |
| Hotel stay (UK) | 36.0 kg CO₂e / room-night |

Factors are stored in the `EmissionFactor` table with `valid_from` / `valid_to` dates. When DEFRA publishes updated factors (annually), new rows can be inserted without deleting old ones — historical records retain a reference to the factor version that was applied.

---

## 9. Anomaly Detection

### Statistical outliers (3σ)
After each ingestion run, the `co2e_kg` values within the batch are compared to their own distribution. A record is flagged as `outlier` if its value exceeds `mean + 3 × std_dev`. This catches data entry errors (wrong unit, extra zero) and genuine anomalies worth reviewing.

3σ corresponds to ~0.3% of records being flagged in a normal distribution — tight enough to be signal, not noise.

### Duplicate detection (SHA-256)
Described in the data model section. Hash collision probability with SHA-256 is negligible (~10⁻⁷⁷ for 1 billion records).

### Other flags
- `zero_value` — quantity or calculated CO₂e is zero (likely a data export artifact)
- `missing_factor` — no emission factor found for this category/unit combination (calculation falls back to 0, which would understate emissions)
- `future_date` — activity_date is in the future (likely a typo)
- `unit_mismatch` — the unit from source couldn't be mapped to a canonical unit

---

## 10. The Audit Trail

### Why it matters for ESG reporting
The EU CSRD and UK SECR both require that emissions figures can be independently verified. An auditor must be able to trace every reported tonne of CO₂e back to a source document (invoice, meter reading, booking confirmation). The audit trail in this platform provides that chain:

```
Source CSV row
    → RawRecord (verbatim parse)
    → EmissionRecord (calculated, with emission factor reference)
    → AuditEvent (who approved it, when, with what notes)
```

### Technical design
- `AuditEvent` stores `before_state` and `after_state` as JSON snapshots of the full `EmissionRecord` at each state change.
- Records use UUIDs (not integer IDs) in AuditEvent — even if an EmissionRecord is deleted (which shouldn't happen in normal operation), the audit event retains the historical state snapshot.
- Django admin removes `change` and `delete` permissions for `AuditEvent` — even superusers cannot modify audit records through the admin interface.

---

## 11. Technology Choices

### Backend: Django + Django REST Framework

**Why Django?**
- ORM with proper migration system — essential for an evolving data model
- Built-in admin for quick data inspection
- DRF provides authentication, serialization, filtering, and pagination out of the box
- Django's `AbstractUser` makes custom user models straightforward

**Why not FastAPI?**
FastAPI is faster for pure API services and better for async workloads. Django is the right choice here because the admin, ORM migrations, and the management command for seeding reference data (emission factors, demo users) are all native Django features that would need to be rebuilt from scratch.

### Authentication: SimpleJWT
- Access token (8 hours) + refresh token (7 days)
- Auto-refresh on 401 in the Axios interceptor — analysts can work all day without re-logging in
- Custom token view returns user + organization in the login response (avoids a second `/users/me/` call on login)

### Frontend: React + Vite + TanStack Query

**Why TanStack Query instead of Redux/Zustand?**
Server state (data from the API) is fundamentally different from client state (UI state). TanStack Query handles caching, stale-while-revalidate, background refetch, and optimistic updates without boilerplate. Redux would require action creators, reducers, and middleware for what TanStack does with a single `useQuery` call.

**Why Vite over CRA (Create React App)?**
CRA is unmaintained. Vite is 10–100× faster in development due to native ES modules (no bundling in dev mode) and esbuild-based transforms.

**Why Recharts?**
Lightweight (no D3 dependency), declarative React API, responsive containers built in. The alternative (Chart.js via react-chartjs-2) requires imperative canvas manipulation and is heavier.

### Static file serving: WhiteNoise
WhiteNoise compresses and caches static files at startup, then serves them without hitting Python on subsequent requests. Combined with `CompressedManifestStaticFilesStorage` (content-addressed filenames like `index-ehSrdoKJ.js`), files get infinite browser cache (`Cache-Control: max-age=31536000`). Performance comparable to nginx for static assets.

### Database: SQLite (dev) → PostgreSQL (prod)
SQLite is zero-config and perfectly fine for a single-process dev server. `dj_database_url` reads `DATABASE_URL` from environment — switching to PostgreSQL on Railway requires zero code changes.

---

## 12. Architecture Decisions

### Single URL (Django serves React)
The frontend is built by Vite into `frontend/dist/`, then copied to `backend/frontend_build/`. Django serves:
- `/api/*` → DRF views
- `/assets/*` → WhiteNoise serves from `WHITENOISE_ROOT = frontend_build/` (correct MIME types, before URL routing)
- `/*` → SPAView catch-all returns `index.html`; React Router handles client routing

**Why not separate Vercel + Railway?**  
Two URLs means CORS configuration, two separate deployment pipelines, and credentials in the frontend build that can leak. One URL is simpler and more secure. However, `VITE_API_URL` is configurable at build time for teams that prefer the split.

### Multi-tenancy via organization FK
Every table has `organization = ForeignKey(Organization, ...)`. Every queryset in every view starts with `queryset.filter(organization=request.user.organization)`. This is simple, auditable, and sufficient for a SaaS product with tens or hundreds of tenants.

Row-level security via PostgreSQL RLS would be more robust (defence in depth) but requires more infrastructure. Schema-per-tenant would be more isolated but complicates migrations.

### Immutable audit trail
`AuditEvent` has no `updated_at` field. The pipeline never calls `.update()` on audit events. Django admin has no change/delete form for the model. This is enforcement by convention (and admin config), not by database trigger — a stronger production implementation would use a PostgreSQL trigger to prevent any UPDATE/DELETE on the table.

---

## 13. Security

| Concern | Implementation |
|---|---|
| Authentication | JWT (Bearer token in Authorization header, not cookie — avoids CSRF) |
| Token refresh | Axios interceptor auto-refreshes on 401 without user interaction |
| Organisation isolation | Every queryset filters by `request.user.organization` |
| HTTPS | `SECURE_SSL_REDIRECT = True` in prod settings; `SECURE_PROXY_SSL_HEADER` for Railway's load balancer |
| Secrets | `django-decouple` reads from environment — no secrets in source code |
| File uploads | Django validates uploaded files; raw bytes stored in `FileField` with UUID-based filenames |
| SQL injection | Django ORM parameterizes all queries; no raw SQL |
| XSS | React escapes all interpolated content by default; `django.middleware.clickjacking.XFrameOptionsMiddleware` sends `X-Frame-Options: DENY` |
| CORS | `django-cors-headers` with explicit `CORS_ALLOWED_ORIGINS` |

**What's not production-hardened:**
- Rate limiting on the login endpoint (would add `django-ratelimit`)
- File size limit on uploads (would add `DATA_UPLOAD_MAX_MEMORY_SIZE`)
- Virus scanning on uploaded files (would integrate ClamAV)
- CSP headers (would add `django-csp`)

---

## 14. What's Not Built (and Why)

### Async ingestion (Celery + Redis)
Currently, ingestion is synchronous — the upload request blocks until parsing is complete. For files with 10,000+ rows, this would time out. The fix: process in a Celery task, return a `run_id` immediately, poll for status. This is omitted because it requires deploying Redis as a separate service, which adds operational complexity and cost for a demo.

### Period lock
In real reporting, once a quarter is "closed" (numbers submitted to the regulator), records for that period should be locked against modification. This requires a `ReportingPeriod` model with a `locked` flag, and middleware that checks the period before allowing any write. Omitted because it requires PM input on the business rules (who can lock? who can unlock? what's the exception process?).

### Market-based Scope 2
The EU taxonomy and RE100 initiative recognise "market-based" Scope 2 accounting: companies that purchase renewable energy certificates (RECs/GOOs) can claim a lower emission factor than the grid average. This requires storing contract data alongside meter readings and applying a separate calculation path. The current implementation uses location-based (grid average) factors only.

### Machine learning anomaly detection
The 3σ outlier detection is statistical. A production system would train a model on historical patterns per facility, per month, per category — detecting anomalies that are within 3σ globally but are abnormal for that specific meter. Requires sufficient historical data before it adds value.

### SSO / SAML
Enterprise customers expect to log in with their corporate identity provider (Okta, Azure AD). Django has `python-social-auth` and `djangosaml2` for this. Omitted because it requires customer-specific IdP configuration.

---

## 15. Business Metrics This Platform Enables

Once data is in and reviewed, the platform supports calculating:

**Total footprint**
```
Total CO₂e = Σ(approved EmissionRecord.co2e_kg) / 1000   [in tonnes]
```

**Intensity metrics** (normalized to business activity)
```
Emissions per employee   = Total CO₂e / headcount
Emissions per £ revenue  = Total CO₂e / revenue
Emissions per m² floor   = Total CO₂e / office_area
```

Intensity metrics are how companies compare year-over-year and benchmark against industry peers, even as the business grows.

**Scope breakdown**
```
Scope 1: 15%   (direct combustion — controllable)
Scope 2: 8%    (purchased electricity — switch to renewable)
Scope 3: 77%   (supply chain, travel — hardest to reduce)
```

**Reduction tracking**
Year-on-year comparison of approved records by period. The `activity_date` field (not upload date) ensures correct period attribution even if data is uploaded late.

**Hotspot analysis**
Category breakdown shows where effort has highest impact. If business travel is 60% of Scope 3, that's where reduction initiatives (video-first policy, sustainable travel guidelines) will move the needle.

**Data quality score**
```
Quality = approved_records / (approved_records + flagged_records + error_records)
```
High quality score → auditor can rely on the data. Low score → investigation needed.

---

## 16. Recruiter Q&A

**Q: Why not use a pre-built emissions platform like Watershed, Persefoni, or Greenly?**  
A: Those platforms exist for good reason. This assignment is about demonstrating the ability to build the underlying data infrastructure — parsing industry-specific formats, designing a normalized data model, building a review workflow. Understanding *how* it works is necessary for engineering roles at ESG platforms or corporates building their own solutions.

---

**Q: Is this production-ready?**  
A: The architecture and data model are production-appropriate. Three things would be needed before serving real customers: (1) async ingestion via Celery, (2) schema-level tenant isolation or PostgreSQL RLS, (3) proper secret management and security hardening (rate limiting, CSP, file size limits). The current code is structured to make all three additions without major refactoring.

---

**Q: How does it handle a 100,000-row SAP export?**  
A: Currently, it would time out during synchronous processing (~30–60 seconds for 100k rows with DB writes). The architectural fix is Celery: accept the file, return a run_id immediately, process in a background worker. The `IngestionRun` model already has the status/count fields designed for this pattern — the view would just return the run_id and the frontend would poll.

---

**Q: How do you know the emission factors are correct?**  
A: The factors are seeded from DEFRA's 2024 "Greenhouse gas reporting: conversion factors" spreadsheet, published by the UK government. DEFRA is the standard source for UK Scope 1, 2, and 3 factors and is used by most FTSE 350 companies. The `EmissionFactor` model stores `source` (e.g., "DEFRA 2024") and `valid_from`/`valid_to` dates for full traceability.

---

**Q: Why SAP CSV instead of connecting directly to SAP via API?**  
A: SAP does expose OData APIs (SAP Gateway) and IDocs for data exchange. However: (1) Every SAP installation has different custom configurations — the OData API for Materials Management at Company A is not the same as Company B's. (2) Getting API credentials requires involving the customer's SAP Basis team and a security review. (3) CSV exports are universal — every SAP user can run SE16N and export. The CSV approach is pragmatic for onboarding: faster to get data out, no integration project required.

---

**Q: How does multi-tenancy work? Could a bug expose Company A's data to Company B?**  
A: Every queryset in every DRF view starts with `.filter(organization=request.user.organization)`. The `Organization` FK on every model is the enforcement mechanism. A bug that removed that filter from one view would expose that view's data, but not all data — each view's queryset is independently filtered. A more robust approach is PostgreSQL row-level security (RLS), which enforces isolation at the database level regardless of application-level bugs.

---

**Q: Why use SHA-256 for deduplication instead of a database unique constraint?**  
A: A unique constraint on 8 fields would work but would cause `IntegrityError` exceptions on re-upload, requiring exception handling. The hash approach pre-checks existing hashes in a single query (`source_hash__in=...`), then skips gracefully with a `RawRecord(parse_status='skipped')` entry. It's also faster for bulk uploads: one `SELECT … IN (…)` vs one `INSERT` that might raise an exception for each row.

---

**Q: What is the Haversine formula and why use it for flights?**  
A: Haversine calculates the great-circle distance between two points on a sphere given their latitudes and longitudes. For flights, it gives the shortest possible distance between origin and destination airports. DEFRA recommends adding 9% to this distance to account for actual routing (planes don't fly straight-line due to air traffic control, weather, and jet streams). The alternative is a distance database (like OpenFlights or OAG), which is more accurate but requires licensing.

---

**Q: What would you improve first if this were a real product?**  
A: In order of impact:
1. **Async ingestion** — Celery + Redis. This is a blocking issue for large files.
2. **Real-time status polling** — WebSocket or SSE on the ingestion page to show progress.
3. **Emission factor management UI** — let admins update factors without a developer deploy.
4. **PDF report export** — the final deliverable for most reporting requirements is a PDF. ReportLab or WeasyPrint would generate SECR-compliant reports from the approved records.
5. **API integrations** — replace CSV upload with scheduled pulls from SAP APIs, utility APIs (Green Button Connect), and Concur's Trip API.

---

**Q: What does a typical user session look like?**  
A: An analyst logs in at the start of a reporting cycle:
1. Uploads 4 files (SAP fuel Q4, electricity Q4, travel Q4, procurement Q4) — ~2 minutes
2. Reviews the ingestion results — checks error counts and skipped rows
3. Opens the Review Queue — filters by `flagged` status, investigates anomalies, approves or rejects
4. Bulk-approves the remaining `pending` records after spot-checking a sample
5. Opens the Dashboard — verifies scope totals look reasonable vs. the prior quarter
6. Exports the audit log for the external auditor

Total time: 30–60 minutes for a quarterly cycle, down from 2–3 weeks with spreadsheets.

---

**Q: Why does the login page have credentials pre-filled?**  
A: This is a demo submission. In production, the credentials field would be empty and the demo box would be removed. Pre-filling removes friction for reviewers who might otherwise not test the full flow.

---

**Q: What does the "analyst" role mean? Are there other roles?**  
A: Three roles are defined:
- **analyst** — can upload files, review records (approve/flag/reject), view dashboard and audit log
- **admin** — same as analyst plus user management
- **auditor** — read-only; can view all records and audit log but cannot approve or upload

Role enforcement is currently at the view level (`request.user.role`). A more robust implementation uses DRF permission classes so roles are checked at the serializer/view class level rather than inside view methods.

---

**Q: How is this different from a simple CRUD app?**  
A: Several non-trivial components:
1. Format-aware parsers (SAP German dates + German decimals + column aliases, Haversine for flights)
2. Unit normalization pipeline (14 canonical units, 21 conversion factors)
3. Versioned emission factor lookup with fallback chain (DB → hardcoded constants)
4. SHA-256 deduplication with pre-fetched hash set (avoids N+1 queries on large files)
5. 3σ statistical outlier detection across each ingestion batch
6. Immutable audit trail with before/after state snapshots
7. Multi-tenant data isolation
8. Single-URL SPA serving (WhiteNoise root + SPAView catch-all)

---

*Built for the Breathe ESG Tech Intern assignment. Harshit Gupta, May 2026.*
