# Breathe ESG — Emissions Ingestion Platform

> Ingest emissions data from SAP, utility portals, and corporate travel platforms. Normalize it. Review it. Sign it off. One URL.

**Live demo** → _[Add Railway URL after deployment]_  
**Login** `analyst` / `analyst123` &nbsp;|&nbsp; `admin` / `admin123`

---

## Run locally — one command

```bash
bash setup_and_run.sh
```

Requires Python 3.10+ and Node 18+. Opens at **http://localhost:8000**.

---

## What it does

| Capability | Detail |
|---|---|
| **Ingest** | SAP SE16N/ME2M fuel CSV, Green Button electricity CSV, SAP Concur travel export |
| **Normalize** | Canonical units (L, kWh, km, nights) · DEFRA 2024 emission factors · GWP-weighted CO₂e |
| **Detect** | Statistical outliers (>3σ), duplicate detection (SHA-256 hash), missing factors, zero values |
| **Review** | Approve / flag / reject individually or in bulk · notes on every action |
| **Audit** | Append-only event log · before/after state diff for every status change |
| **Dashboard** | Scope 1/2/3 totals · category bar chart · monthly trend · pending queue count |

---

## Architecture

```
Browser
  ├── /api/*      → Django REST Framework + SimpleJWT
  ├── /assets/*   → WhiteNoise (Vite build, served at root)
  └── /*          → React SPA (Django catch-all → index.html)
```

Single Railway service. No separate frontend host. No CORS issues.  
In local dev, Vite's proxy forwards `/api` to `localhost:8000` for hot-reload.

---

## Docs

| File | What's in it |
|---|---|
| [GUIDE.md](./GUIDE.md) | Full technical + business deep-dive. Every question a reviewer might ask, answered. |
| [DEPLOY.md](./DEPLOY.md) | Step-by-step Railway and Vercel deployment |
| [MODEL.md](./MODEL.md) | Data model — every field justified |
| [DECISIONS.md](./DECISIONS.md) | Why SAP CSV, Green Button, Concur — and what I'd ask the PM |
| [TRADEOFFS.md](./TRADEOFFS.md) | What's not built and what it would take to add it |
| [SOURCES.md](./SOURCES.md) | SAP table names, ESPI standard, Concur codes, what breaks in production |
