# Source Research

For each of the three data sources: what I researched, what I learned, what the sample data looks like and why, and what would break in a real deployment.

---

## Source 1: SAP Fuel & Procurement

### What I researched

SAP's data model for material movements centres on two key tables:
- **MKPF** (Material Document Header): `BLDAT` (document date), `BUDAT` (posting date), `USNAM` (created by)
- **MSEG** (Material Document Segment): `MATNR` (material), `WERKS` (plant), `MENGE` (quantity), `MEINS` (base unit of measure), `BWART` (movement type), `KOSTL` (cost centre)

SAP stores units as internal codes: `L` (litre), `GL` (gallon), `KG`, `M3` (cubic metre), `KWH`, `ST` (piece). These are drawn from table `T006` (units of measure), which also contains the ISO code and conversion factors. I mapped the most common ones.

Movement types control what a goods movement means:
- **261**: Goods issue to production order (consumption)
- **201**: Goods issue to cost centre (consumption for overhead)
- **601**: Delivery to customer (outbound logistics fuel, if applicable)
- **101**: Goods receipt against purchase order
- **303/311**: Plant-to-plant stock transfer (no external boundary — excluded)

For procurement, the ME2M report joins EKKO (PO header) and EKPO (PO line item) and exports `LIFNR` (vendor number), `MATNR`, `NETWR` (net value in local currency), `WAERS` (currency key), `MENGE`, `MEINS`, `BEDAT` (PO date).

German column headers: SAP's language-dependent texts come from table `DD04T`. In a German-language system, `WERKS` displays as "Werk", `MENGE` as "Menge", `MEINS` as "Basismengeneinheit", `BLDAT` as "Belegdatum". The parser handles both.

Date formats: SAP's standard DD.MM.YYYY display format derives from the user's country settings in SU01. BW/SAP Analytics Cloud extracts often export YYYYMMDD (the internal format). Both are handled.

Decimal separators: German locale uses `.` as thousands separator and `,` as decimal separator, so `1.234,56` means 1234.56. This is common in SAP exports from German-configured systems. The `parse_decimal()` function in `parsers/base.py` detects and handles this.

### What I learned

The hardest part isn't the CSV parsing — it's material classification. SAP stores materials in `MATNR` (up to 18 characters) with no mandatory classification for fuel type. A diesel entry might be `DIESEL-001`, `FUEL-D-EU`, `1000000042`, or `KRAFTSTOFF-DIESEL`. You need a material description lookup (`MAKTX` from MARA/MAKT) and fuzzy keyword matching. My parser does keyword matching against the description and material number. In production, you'd maintain a `MaterialClassification` table that the client's procurement team maintains.

### Why the sample data looks the way it does

The sample SAP fuel file (`sap_fuel_sample.csv`) uses:
- German column headers (`WERKS`, `MATNR`, `MENGE`, `MEINS`, `BLDAT`, `BWART`, `KOSTL`)
- Plant codes `1000`, `2000`, `3000` — realistic SAP plant numbering (4-digit, often starting at 1000)
- Movement type 261 for most rows (goods issue to production)
- German material descriptions ("Diesel Kraftstoff (EN590)", "Benzin Super (RON 95)", "Erdgas H (Brennwert)", "Flüssiggas (Propan)", "Heizöl EL (leicht)")
- Units: `L` (litre), `KWH` (natural gas energy basis)
- Two intentionally bad rows: one with missing quantity, one with an unclassifiable material — to demonstrate error handling

The procurement file uses English headers to show the parser handles both variants.

### What would break in a real deployment

1. **Material classification**: If the client uses numeric material numbers with no descriptive name in the export, fuel type detection will fail and every record gets `missing_factor` flagged.
2. **Custom movement types**: Some companies use Z-movement types (custom) for specific workflows. Our filter of `{261, 201, 601}` would miss them.
3. **Multi-currency procurement**: The sample uses EUR throughout. A client with USD/GBP/EUR procurement would need currency conversion for spend-based emission factors.
4. **Plant-to-company mapping**: Emission factors may vary by plant location (different grid regions, different fuel suppliers). We don't have a `Plant → Country` lookup.
5. **SAP HANA JSON exports**: Some S/4HANA embedded analytics export JSON, not CSV. Parser would need extension.

---

## Source 2: Utility Electricity

### What I researched

**Green Button** is the US ESPI (Energy Service Provider Interface) standard, developed by the DOE and NIST. It defines a standard export format for smart meter data. The standard has two delivery modes:
- **Connect My Data (CMD)**: Real-time push to third-party apps via OAuth 2.0
- **Download My Data (DMD)**: Manual CSV or XML export from the utility portal

The CSV export format is called "Green Button CSV" and has columns: `TYPE`, `DATE`, `START TIME`, `END TIME`, `USAGE`, `UNITS`, `COST`, `NOTES`. Data can be 15-minute intervals, hourly, or monthly billing.

UK portal exports from utilities like SSEN, Octopus, E.ON use a "portal variant" with columns: `Billing Period Start`, `Billing Period End`, `Consumption (kWh)`, `Tariff`, `Cost`, `Meter Point` (MPAN).

Meter readings vs. consumption: Some exports give cumulative meter readings (`READING_TYPE = "Current"`) not consumption. You need to diff consecutive readings to get consumption. Our parser handles only consumption records (TYPE = "Electric usage" in Green Button).

**Emission factors**: UK grid average from DEFRA 2024 is 0.20705 kgCO₂e/kWh. This is the location-based factor. It varies by year: 2021 was 0.2556, 2022 was 0.1934, 2023 was 0.2068, 2024 is 0.20705 — reflecting the changing generation mix (more renewables).

### What I learned

The biggest practical problem with utility data is **meter boundaries**. A company with 5 offices has 5 meters, but the facilities team might get one export per meter, or one combined export, or exports with overlapping billing periods due to billing cycle differences. The `facility` field (populated from the MPAN/meter ID) is essential for per-site analysis.

Zero-consumption rows are common when: a meter fault occurred, a site was empty (holiday period), or the export covers more periods than the site was occupied. We flag them as `zero_value` rather than silently dropping them.

### Why the sample data looks the way it does

The sample (`utility_electricity_sample.csv`) uses Green Button format:
- Daily readings for a single meter, January–March 2024
- Realistic consumption values: 2200–3100 kWh/day for a light-industrial facility
- Seasonal variation (higher Jan/Feb, lower April) consistent with UK heating loads
- One intentional zero row (March 5) with a note "Meter fault — reading unavailable" — demonstrates the `zero_value` flag and shows the parser preserves the note

### What would break in a real deployment

1. **15-minute interval data**: Green Button interval data can have 96 rows per day per meter. 50 meters × 365 days × 96 intervals = 1.75 million rows. The synchronous pipeline would time out. Aggregation to daily before DB write is needed.
2. **Mixed electricity/gas**: Some utility exports include gas consumption. Our parser skips non-electricity rows (`TYPE = "Gas usage"`). Gas would need a separate Scope 1 parser with different emission factors.
3. **US vs. UK grid factors**: The US EPA eGRID provides state-level factors. A US client needs grid-region-specific factors (e.g. WECC for California vs. RFC West for Ohio). We seed the UK DEFRA factor only.
4. **Reactive power / demand charges**: Green Button sometimes includes kVAh (reactive) or kW (demand) readings. These aren't direct emission contributors and should be filtered.
5. **Solar generation export**: If a facility has on-site solar and exports to the grid, negative consumption values appear. Our parser skips negative usage, but the renewable generation offsets Scope 2 and should ideally be tracked separately.

---

## Source 3: Corporate Travel

### What I researched

**SAP Concur** is the dominant enterprise T&E platform (~70% enterprise market share as of 2024). The Trip Detail Report is the standard export for GHG inventory purposes.

I reviewed the SAP Concur documentation for:
- Trip Detail Report output columns (standard vs. custom)
- Booking type codes: AIR, HTL, CAR, TRN (train), LIM (limousine/taxi), BUS
- Class of Service values: Economy, Premium Economy, Business, First (airline-specific variants like "J", "C", "Y")

**Navan (formerly TripActions)** exports a near-identical CSV from its analytics portal with slightly different column names (`Traveler Name` instead of `Employee Name`, `Segment Type` instead of `Booking Type`).

**GHG Protocol for Business Travel (Scope 3, Category 6)** methodology:
- Flights: distance-based using IATA codes + Haversine formula, with 9% routing uplift (DEFRA methodology), with radiative forcing multiplier for upper atmosphere effects
- Cabin class multipliers (DEFRA 2024): Economy 1.0×, Premium Economy 1.26×, Business/First 2.40×
- Hotels: DEFRA 2024 global average 16.10 kgCO₂e/night
- Ground: DEFRA 2024 per-km factors by mode (car, taxi, train)

**Radiative forcing index (RFI)**: Some methodologies apply a multiplier (1.9× in the IPCC AR4) to flight emissions to account for non-CO₂ effects (contrails, water vapour). DEFRA 2024 includes this in their published per-km factors already, so we don't apply an additional multiplier.

### What I learned

Flight distance is the most common data gap. Concur's Trip Detail Report has a `Distance` column but it's only populated if the booking tool calculated it, which depends on configuration. In practice, 30–50% of rows have blank distance. The IATA code lookup + Haversine calculation fills this gap well for direct routes. The 9% uplift compensates for indirect routing.

Hotel stay duration in Concur: Not all configurations export a "Nights" column. We fall back to `trip_end_date - trip_start_date` if "Nights" is blank. If both are missing, we assume 1 night and flag as `incomplete`.

### Why the sample data looks the way it does

The sample (`travel_sample.csv`) uses SAP Concur Trip Detail format with:
- Mix of booking types: Air, HTL (hotel), CAR, TRN (train) — realistic for a British manufacturing company
- Routes reflecting a UK-headquartered company: LHR as primary origin, European (FRA, CDG, AMS, BCN) and long-haul (JFK, DXB, SIN, NRT) destinations
- Business and Economy class — business trips to New York and Dubai use Business class, European trips use Economy (realistic spend policy)
- Intentionally missing distance on most air rows — to demonstrate the IATA code distance calculation
- One TRN (train) row London–Edinburgh with explicit distance (630km) — to show ground transport handling
- Employee departments: Engineering, Sales, Finance, HR, Operations — reflect realistic cost centre distribution

### What would break in a real deployment

1. **IATA codes not in lookup table**: Our seeded table has 250+ airports covering all major business travel hubs across Europe, North America, Asia-Pacific, Middle East, Africa, and Latin America — sourced from the ourairports.com public domain dataset and verified against IATA reference data. This covers the vast majority of enterprise business travel routes. A production deployment would load the full ~9,000-airport ourairports.com CSV at startup rather than hard-coding the list.
2. **Multi-leg itineraries**: Concur sometimes exports one row per flight leg (LHR→FRA→SIN as two rows) vs. one row per booking. If a booking is LHR→FRA→SIN, we'd compute LHR→FRA + FRA→SIN separately, which is correct. But if Concur exports it as one row with Origin=LHR, Destination=SIN, we'd compute great-circle distance LHR→SIN and miss the layover leg. Need to ask the client how their Concur is configured.
3. **Currency normalization**: Hotel costs are in GBP in the sample. A global client would have EUR, USD, SGD, AED in the same file. The `Amount` field is informational only for now, but if we wanted to validate against spend-based factors, we'd need currency conversion.
4. **Rail emissions outside UK**: DEFRA UK rail factor (0.03549 kgCO₂e/km) is for UK National Rail. French TGV, German ICE, and Indian rail have very different emission profiles. We use the UK factor for all rail which could understate significantly for diesel rail in developing markets.
5. **Remote work / no travel**: If a company has reduced business travel significantly (post-COVID), a sample with 30 rows over 4 months might trigger outlier flags on high-emission individual trips. Real deployment needs baseline calibration of the outlier threshold.
