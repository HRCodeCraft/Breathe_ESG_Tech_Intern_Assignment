# Deployment Guide

Two options:

| Option | URLs | Best for |
|---|---|---|
| **Railway (single service)** | One URL — Django serves everything | Simplest, recommended |
| **Vercel + Railway (split)** | Frontend on Vercel, backend on Railway | If you prefer Vercel's global CDN |

---

## Option A — Railway (Single Service, Recommended)

Everything from one URL. Django serves the React build, all API endpoints, and static files.

### Step 1 — Push to GitHub

```bash
git remote add origin https://github.com/YOUR_USERNAME/breathe-esg.git
git push -u origin main
```

Make the repo **public** so reviewers can access it.

### Step 2 — Create Railway Project

1. [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**
2. Select your repo. Railway detects `nixpacks.toml` automatically.

What Railway does (from `nixpacks.toml`):
```
setup:   Python 3.11 + Node 20
install: npm ci  +  pip install
build:   npm run build → copy dist → collectstatic
start:   gunicorn breathe_esg.wsgi --workers 2 --bind 0.0.0.0:$PORT
```

### Step 3 — Add PostgreSQL

Railway dashboard → **+ New → Database → PostgreSQL**  
`DATABASE_URL` is injected automatically — do not set it manually.

### Step 4 — Environment Variables

Railway dashboard → your service → **Variables**:

| Variable | Value |
|---|---|
| `SECRET_KEY` | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `ALLOWED_HOSTS` | `your-app.up.railway.app` |
| `CORS_ALLOWED_ORIGINS` | `https://your-app.up.railway.app` |
| `DEBUG` | `False` |
| `DJANGO_SETTINGS_MODULE` | `breathe_esg.settings.prod` |

### Step 5 — First Deploy

The `Procfile` release command runs before the server starts:
```
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_reference_data    ← creates demo users + emission factors
```

After ~2 minutes: `https://your-app.up.railway.app`  
Login: `analyst` / `analyst123` · `admin` / `admin123`

### Step 6 — Update README

```markdown
**Live demo** → https://your-app.up.railway.app
```

---

## Option B — Vercel (Frontend) + Railway (Backend)

Frontend on Vercel's CDN, backend API on Railway.

### Backend — Railway

Follow Option A Steps 1–5, but also add:

| Variable | Value |
|---|---|
| `CORS_ALLOWED_ORIGINS` | `https://your-vercel-app.vercel.app` |

### Frontend — Vercel

1. [vercel.com](https://vercel.com) → **New Project → Import Git Repository**
2. Vercel auto-detects the `vercel.json` at root.
3. In Vercel **Environment Variables**, add:

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://your-railway-app.up.railway.app/api` |

4. Deploy. Vercel builds the frontend and serves it at `your-app.vercel.app`.
5. All `/api/*` calls from the browser go directly to the Railway backend.

> **Note:** CORS must be configured on the backend to allow the Vercel domain. The `CORS_ALLOWED_ORIGINS` variable handles this.

---

## Local Setup

```bash
bash setup_and_run.sh
```

Opens at **http://localhost:8000**. Requires Python 3.10+ and Node 18+.

---

## Troubleshooting

**Build fails at collectstatic**  
→ `DJANGO_SETTINGS_MODULE=breathe_esg.settings.prod` must be set. `SECRET_KEY` must not be empty.

**500 on first request**  
→ Check Railway Deploy Logs. Most likely: `ALLOWED_HOSTS` doesn't match the Railway domain.

**Database tables missing**  
→ Migration ran but failed. Railway → your service → **Run Command**:  
`cd backend && python manage.py migrate --settings=breathe_esg.settings.prod`

**Blank page on frontend (JS loads, nothing renders)**  
→ Check browser DevTools console for errors. Most likely: `VITE_API_URL` is wrong or CORS is blocking the API call.

**npm install fails**  
→ Force fresh: Railway → Settings → **Clear Build Cache** → redeploy.

---

## Architecture

```
Browser
  ├── /api/*       → Django REST Framework
  ├── /assets/*    → WhiteNoise (from WHITENOISE_ROOT = frontend_build/)
  └── /*           → SPAView → index.html → React Router
```

Single Railway service. Single URL. No CORS. WhiteNoise serves JS/CSS assets with correct MIME types and infinite browser cache (`Cache-Control: max-age=31536000`).
