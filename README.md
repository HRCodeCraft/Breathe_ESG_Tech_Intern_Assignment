# Breathe ESG — Emissions Ingestion Platform

A Django REST + React app for ingesting, normalizing, and reviewing emissions data from SAP, utility portals, and corporate travel platforms. **Single URL — backend serves the built React frontend.**

**Live demo**: _[Add Railway URL after deployment]_  
**Login**: `analyst` / `analyst123`  (also: `admin` / `admin123`)

---

## Local setup — one command

Requires Python 3.10+ and Node 18+.

```bash
bash setup_and_run.sh
```

That's it. Opens at **http://localhost:8000**.

What the script does:
1. Creates a Python virtualenv and installs dependencies
2. Builds the React frontend (`npm run build`)
3. Copies the build into Django's static file tree
4. Runs migrations + seeds emission factors and demo users
5. Starts the Django dev server

---

## What it does

1. **Ingests** CSV exports from three source types:
   - **SAP Fuel** (SE16N/ME2M) — handles German + English column headers, DD.MM.YYYY dates, SAP unit codes (L, GL, KWH, NM3…)
   - **Utility Electricity** — Green Button CSV (US ESPI standard) and UK portal variant
   - **Corporate Travel** — SAP Concur Trip Detail Export, with Haversine great-circle distance for flights when distance isn't provided
2. **Normalizes** quantities to canonical units (litres, kWh, km, nights) and applies DEFRA 2024 emission factors
3. **Flags anomalies** automatically — statistical outliers (>3σ), duplicates (hash-based), missing factors, zero values
4. **Review queue** — filter by scope/status/flags, approve or flag in bulk, full state diff in the audit log
5. **Dashboard** — scope breakdown pie, category bar chart, monthly trend, pending count

---

## Deployment — Railway (single service)

1. Push this repo to GitHub
2. Create a new Railway project → **Deploy from GitHub repo**
3. Railway detects `nixpacks.toml` at the root and runs the correct build:
   - Installs Node + Python
   - Builds React → copies to `backend/frontend_build/`
   - Runs `collectstatic`, migrations, seed
   - Starts gunicorn
4. Add a PostgreSQL database (Railway → Add Plugin → PostgreSQL)
5. Set environment variables in Railway dashboard (see `backend/.env.example`):
   - `DATABASE_URL` — Railway injects this automatically when you add Postgres
   - `SECRET_KEY` — generate: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
   - `ALLOWED_HOSTS` — your Railway domain, e.g. `breathe-esg.up.railway.app`
   - `CORS_ALLOWED_ORIGINS` — same as above (same-origin, still good to set)
   - `DEBUG=False`

Single URL, everything served from Django.

---

## Architecture decision

The frontend is a Vite/React SPA. In production, Django:
- Serves `/api/*` — REST endpoints
- Serves `/static/*` — JS/CSS/assets (via WhiteNoise)
- Serves `/*` — `index.html` (React Router handles client-side routing)

In local dev, Vite's dev server proxies `/api` to `localhost:8000`, so you get hot-reload while hitting the real Django API.

---

## Data model

See [MODEL.md](./MODEL.md) — multi-tenancy, Scope 1/2/3, source-hash deduplication, immutable audit trail, unit normalization.

## Design decisions

See [DECISIONS.md](./DECISIONS.md) — why SE16N CSV over IDoc, why Green Button, why Concur, what I'd ask the PM.

## Tradeoffs

See [TRADEOFFS.md](./TRADEOFFS.md) — async ingestion, period lock, market-based Scope 2.

## Source research

See [SOURCES.md](./SOURCES.md) — SAP table names, ESPI standard, Concur booking type codes, what breaks in production.
