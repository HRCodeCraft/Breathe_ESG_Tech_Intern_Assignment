# Decision Log

Every meaningful ambiguity I resolved, with reasoning. Includes questions I'd ask the PM if I had access.

---

## Source 1: SAP

### Which SAP export format?

**Decision: CSV flat-file export (SE16N / ME2M report), not IDoc or OData.**

Reasons:
- IDoc requires SAP middleware (ALE/EDI) with a configured partner profile. Assuming we don't have a live SAP system to pair with — we're receiving files, not integrating directly. IDocs are for system-to-system EDI, not analyst exports.
- OData (SAP S/4HANA) requires API credentials and SAP Fiori gateway setup. Valid for a real-time integration but out of scope for a batch ingestion prototype.
- SE16N (table browser) and ME2M (purchase orders by material) are what sustainability managers actually export. You ask the SAP Basis team to run the report and email you the CSV. This is the 80% case.

**What I'd ask the PM**: Does this client have a sustainability team with SE16N access, or do they need IT involvement? If IT involvement is unavoidable, OData might be worth scoping.

### Which SAP tables / reports?

**Fuel**: MSEG (material document segment) via SE16N, or a custom ABAP report on MSEG/MKPF. Movement types 201/261/601 = goods issue (consumption). We treat goods issues from fuel materials as combustion.

**Procurement**: ME2M (purchase orders by material), which gives vendor, material, quantity, value, and date. Alternative is EKPO/EKKO join, but ME2M is the standard report a purchasing analyst would export.

**Decision: Handle movement types 261, 201, 601, 543 for fuel; 101, 103 for procurement receipts. Skip everything else (STO transfers 301/311, consignment 411, scrapping 551).**

Reason: STOs are internal stock transfers — no external emission boundary crossed. Consignment complicates ownership. Scrapping is rare and usually small. Starting with consumption goods issues captures the vast majority of Scope 1 fuel use.

### German column headers

SAP's display language depends on the logged-in user's language setting. A German-configured system exports `WERKS`, `MENGE`, `MEINS`, `BLDAT`, etc. An English system might export `Plant`, `Quantity`, `Base Unit`, `Document Date`. The parser handles both via an alias map. I verified the German variants against SAP documentation.

### Date format

SAP's default display date format for German locales is `DD.MM.YYYY` (e.g. `31.12.2024`). Internal date fields in ABAP are `YYYYMMDD`. BW/BO extracts sometimes use ISO `YYYY-MM-DD`. We try all three in order and fail with a clear error if none matches.

---

## Source 2: Utility Electricity

### Which format?

**Decision: Green Button CSV (ESPI standard) as the primary format, with a portal CSV variant as fallback.**

Green Button is the US ESPI (Energy Service Provider Interface) standard, mandated by many US utilities. PG&E, ConEd, Duke Energy, National Grid, Eversource, and most major US utilities support it. UK utilities (SSEN, Octopus, E.ON) use similar portal exports with slightly different column names.

Reasons to choose over alternatives:
- **PDF bills**: Require PDF parsing (layout-sensitive, fragile, expensive to maintain). Ruled out.
- **Direct API**: Utilities don't have a unified API standard. PG&E has a Green Button API but it requires OAuth setup per utility account. Too much per-utility config for a prototype.
- **Manual entry**: Not scalable, defeats the purpose.

Green Button CSV is what you get when you click "Export data" on most utility portals. It's machine-readable, has a defined schema, and I can test against sample files published by the DOE.

**What I'd ask the PM**: Is this client US-based or UK/EU? Green Button is US-standard; UK portals vary more. How many distinct meters does the client have — one combined export or one file per meter/site?

### Billing period vs. calendar month

Billing periods don't align with calendar months (a bill might cover Jan 15 – Feb 14). For the `activity_date` on Scope 2 records, I use the midpoint of the billing period. For records where only a single date is given (daily interval data), I use that date directly.

**Implication**: Month-level aggregation in the dashboard uses `activity_date`, so billing-period records land in the month of the midpoint. This is a known approximation documented in the UI.

---

## Source 3: Corporate Travel

### Which platform?

**Decision: SAP Concur Trip Detail Export CSV.**

Reasons:
- Concur has ~70% enterprise market share for T&E. Any Fortune 500 client is almost certainly using it.
- The Trip Detail Report is a standard export accessible via Reporting > Standard Reports > Travel. No API credentials needed.
- Navan (formerly TripActions) and Egencia export near-identical schemas — column names differ slightly (handled via alias map).
- TripActions/Navan have a REST API that could feed this in near-real-time, but a weekly CSV export is more realistic for the analyst workflow this prototype serves.

**What I'd ask the PM**: Is the client on Concur or Navan? Do they consolidate multi-employee trips into one export, or is it per-employee? Some Concur configurations export one row per segment (each flight leg) vs. one row per booking — how is theirs configured?

### Flight distance when not provided

Concur Trip Detail exports don't always include distance. When absent, we calculate great-circle (Haversine) distance between IATA airport codes from our `AirportCode` lookup table, then multiply by 1.09 (DEFRA's indirect routing uplift factor).

If the IATA code isn't in our lookup table, we create the record with `co2e_kg = null` and flag it as `missing_factor`. The analyst sees it in the flagged queue and can provide the distance manually.

### Cabin class emission factors

DEFRA 2024 provides separate factors for economy, premium economy, business/first. Cabin class comes from Concur's "Class of Service" field. We map common strings ("Economy Class", "business", "BUS", etc.) to the correct factor tier.

**Decision: Economy class is the default if cabin class is absent or unrecognised.** This is conservative (understates high-cabin emissions) but avoids inflating numbers when data is missing. Flagged as `incomplete` so analysts know to verify.

### Hotels

Emission factor: DEFRA 2024 global average of 16.10 kgCO₂e per hotel night. We know this is a rough estimate — it doesn't vary by country or hotel energy certification. For an enterprise client with operations in Germany vs. India vs. Australia, the real numbers could differ by 3×. But there's no widely-accepted per-country hotel factor that's publicly accessible without a paid GHG data subscription.

**What I'd ask the PM**: Does the client have a data subscription (e.g. EcoAct, Carbonfact) that gives country-level hotel factors? If so, we'd add a `country` field to the hotel record and look up accordingly.

---

## Emission Factor Source

**Decision: DEFRA 2024 (UK Government GHG Conversion Factors) as primary source.**

Reasons:
- Publicly available, annually updated, covers all our categories
- Widely accepted by UK/EU auditors under GHG Protocol
- Includes gas-level breakdown (CO₂/CH₄/N₂O) not just CO₂e

For US clients, EPA eGRID grid factors would be more appropriate for Scope 2. The `EmissionFactor` table supports multiple sources — we seed both.

---

## Deduplication Strategy

**Decision: Hash-based deduplication on (org, source_type, category, activity_date, facility, quantity, unit, supplier).**

The hash is computed before the record is written. If a matching hash exists, the raw record is marked `skipped` and no new `EmissionRecord` is created.

This means: uploading the same file twice is safe. The second upload shows `0 created, N skipped`.

**What's not covered**: If two different files legitimately contain the same activity (e.g. two overlapping SAP exports), we'd skip the second one. This is a known false-positive deduplication scenario. The analyst sees skipped rows in the run detail and can investigate.

---

## Anomaly Detection

**Decision: Flag records as `outlier` if their CO₂e is more than 3 standard deviations from the mean within the same ingestion run.**

This catches data entry errors (quantity in wrong unit creating a 1000× value), OCR errors from PDF conversion, and fat-finger entry. 3σ gives ~0.3% false positive rate on normally distributed data.

Applied only within a run (not across all records) to avoid false positives from genuinely different order-of-magnitude activities in the same organisation.

---

## What I would ask the PM

1. **Data freshness**: Is this a one-time inventory build or ongoing monthly ingestion? Ongoing changes the UX priority toward scheduled pulls and automatic deduplication significantly.
2. **Scope 2 methodology**: Location-based or market-based? Market-based requires supplier-specific EFs which are much harder to source.
3. **Geographic scope**: UK only, US only, or global? Material for which electricity grid factors apply.
4. **SAP configuration**: Is the client on SAP ECC 6.0 or S/4HANA? S/4HANA makes OData integration feasible.
5. **Auditor requirements**: Which standard is the client filing under (GRI, CDP, TCFD, CSRD)? Affects what level of GHG gas breakdown and uncertainty documentation is needed.
6. **Review SLA**: How quickly do records need to move from "pending" to "approved"? Affects whether email notifications and analyst assignment are needed.
