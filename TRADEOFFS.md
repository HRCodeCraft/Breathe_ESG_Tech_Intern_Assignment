# Tradeoffs

Three things I deliberately did not build, and why.

---

## 1. Asynchronous ingestion (Celery + Redis)

**What it would give you**: File uploads return immediately with a job ID. Parsing happens in a background worker. The frontend polls or uses WebSockets for status updates. This is essential if you're processing files over ~5,000 rows or if parsing involves external API calls (e.g. fetching live grid emission factors from a utility API).

**Why I didn't build it**: The prototype runs synchronously — the API endpoint blocks until parsing completes, then returns the result. For the sample data sizes (20–100 rows per file), this is fine. The ingestion UI shows a spinner.

**What breaks in production**: A 50,000-row SAP export will time out the HTTP request (Railway's default is 30s). Concurrent uploads from multiple analysts will block on the same process pool. This is the highest-priority production gap.

**What it would take**: Add Celery with a Redis broker. The `run_ingestion()` function in `pipeline.py` is already written as a pure function — you'd just wrap it in a `@shared_task` and call `.delay()` from the upload view. The frontend would poll `/api/ingestion/<id>/` until status changes from `processing` to `completed`.

---

## 2. Reporting period lock / audit sign-off workflow

**What it would give you**: Once an analyst clicks "Close period" for Q1 2024, all `approved` records in that period become immutable. No edits, no status changes. The auditor (read-only role) can then export a signed report. This is how real GHG inventories work — you sign off a boundary period, not individual records.

**Why I didn't build it**: The record-level approve/flag workflow covers the review step. Period-level locking is a separate concern that requires additional model fields (`period_locked_at`, `locked_by`), a lock enforcement layer in the serializer/view, and a separate auditor-facing export view (PDF or structured JSON). That's ~2 days of work and touches every write path.

**The risk of omitting it**: Without a lock, an analyst can approve a record, the auditor reviews it, and then another analyst edits it before the report is filed. The audit trail would catch this, but it's a process control gap. Any production ESG platform needs period close.

**What it would take**: Add `reporting_period` (FK to a `ReportingPeriod` model), `is_locked` bool on `ReportingPeriod`, and a middleware check that blocks writes to locked periods. The `AuditEvent` table already captures all changes, so the audit trail is ready.

---

## 3. Market-based Scope 2 and supplier-specific emission factors

**What it would give you**: The GHG Protocol allows two methods for Scope 2: location-based (grid average, what we implement) and market-based (supplier-specific factors from renewable energy contracts, RECs, PPAs, or supplier EACs). Most CDP and CSRD disclosures now require both. Market-based can reduce Scope 2 to near-zero for clients with 100% renewable procurement.

**Why I didn't build it**: Market-based Scope 2 requires:
- A `SupplierFactor` table with contract-specific EFs per utility supplier and period
- Logic to match electricity records to the right contract (which meter, which period)
- Handling for residual mix factors when coverage is partial
- Separate `co2e_kg_market_based` column on `EmissionRecord`

This is a substantial data model extension that requires real client contract data to test against. The location-based method is always calculated regardless, and it's what small-to-mid clients typically file.

**What it would take**: Add `EmissionRecord.co2e_kg_market_based` (nullable), a `SupplierEmissionFactor` table keyed on (supplier, valid_from, valid_to), and a second pass in the normalizer after the location-based calculation. The UI dashboard would show both figures side by side.

---

## Honourable mentions (not full tradeoffs, but worth noting)

- **Email notifications**: No alerts when records enter the flagged queue or pending count exceeds a threshold. Would need Django email backend + a notification preference model.
- **Bulk CSV export of approved records**: The auditor would want to download all approved Scope 1/2/3 records as a structured CSV for their own tools. Straightforward to add as a streaming view.
- **Dark mode**: The CSS variables are wired up for it (`:root` and `.dark` both defined), and the theme is standard shadcn/ui — toggling is a one-liner. Omitted because it doesn't affect the review workflow.
