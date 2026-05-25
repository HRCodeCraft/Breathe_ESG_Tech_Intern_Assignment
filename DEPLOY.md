# Deployment Guide — Railway (Single Service)

Everything runs from one URL. Django serves the built React frontend, all API endpoints, and static files. No Vercel, no separate frontend host.

---

## Step 1 — Push to GitHub

```bash
# In the project root (already has a git commit):
git remote add origin https://github.com/YOUR_USERNAME/breathe-esg.git
git push -u origin main
```

Make the repo **public** so the reviewers can access it without authentication.

---

## Step 2 — Create a Railway Project

1. Go to [railway.app](https://railway.app) and log in (GitHub login works).
2. Click **New Project → Deploy from GitHub repo**.
3. Select your `breathe-esg` repo. Railway will detect `nixpacks.toml` at the root automatically.

**What Railway does during build** (defined in `nixpacks.toml`):
```
setup:   installs Python 3.11 + Node 20
install: npm ci (frontend) + pip install (backend)
build:   npm run build → copies dist → collectstatic
start:   gunicorn breathe_esg.wsgi --workers 2 --bind 0.0.0.0:$PORT
```

---

## Step 3 — Add PostgreSQL

1. In your Railway project dashboard, click **+ New** → **Database** → **PostgreSQL**.
2. Railway automatically injects `DATABASE_URL` into your service environment. No manual copy needed.

---

## Step 4 — Set Environment Variables

In Railway dashboard → your service → **Variables**, add:

| Variable | Value |
|---|---|
| `SECRET_KEY` | Generate: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `ALLOWED_HOSTS` | `your-app.up.railway.app` (Railway shows this under Settings → Domains) |
| `CORS_ALLOWED_ORIGINS` | `https://your-app.up.railway.app` |
| `DEBUG` | `False` |
| `DJANGO_SETTINGS_MODULE` | `breathe_esg.settings.prod` |

`DATABASE_URL` is injected automatically by the PostgreSQL plugin — do not add it manually.

---

## Step 5 — First Deploy

Railway re-deploys on every push. The **release command** (in `backend/Procfile`) runs automatically before the server starts:

```
python manage.py migrate
python manage.py collectstatic --noinput  
python manage.py seed_reference_data      # creates demo users + emission factors
```

After ~2 minutes the deploy completes. Open your Railway domain:

```
https://your-app.up.railway.app
```

Login: `analyst` / `analyst123`  
Admin: `admin` / `admin123`

---

## Step 6 — Update README with Live URL

Once deployed, edit `README.md` line 5:

```markdown
**Live demo**: https://your-app.up.railway.app
```

Push the change:

```bash
git add README.md
git commit -m "Add live demo URL"
git push
```

---

## Step 7 — Share with Reviewers

Email `saurav@breatheesg.com`, `rahul@breatheesg.com`, `shivang@breatheesg.com`:

```
Subject: Breathe ESG Tech Intern Assignment — Harshit

GitHub: https://github.com/YOUR_USERNAME/breathe-esg
Live:   https://your-app.up.railway.app
Login:  analyst / analyst123  (also admin / admin123)

Local setup (single command):
  bash setup_and_run.sh
  → opens at http://localhost:8000
```

---

## Troubleshooting

**Build fails at collectstatic**
- Check `DJANGO_SETTINGS_MODULE=breathe_esg.settings.prod` is set in Railway Variables.
- `SECRET_KEY` must be set — prod settings will raise if missing.

**500 error after deploy**
- Check Railway **Deploy Logs** tab for the Python traceback.
- Most common: `ALLOWED_HOSTS` not matching the Railway domain. Add both `your-app.up.railway.app` and `*.up.railway.app`.

**Database tables missing**
- The Procfile `release` command runs migrations. If it failed, check the release logs separately in Railway (different from deploy logs).
- You can re-run manually: Railway → your service → **Run Command** → `cd backend && python manage.py migrate --settings=breathe_esg.settings.prod`

**Frontend shows "Frontend not built yet"**
- The React build step failed. Check build logs for npm errors.
- Common cause: `node_modules` was cached but `package-lock.json` changed. Force a fresh deploy: Railway → Settings → **Clear Build Cache** → redeploy.

---

## Architecture Summary

```
Browser
  │
  ├── GET /api/*          → Django REST Framework (DRF)
  ├── GET /static/*       → WhiteNoise (compressed, cached)
  └── GET /*              → Django serves frontend/index.html → React Router
```

Single Railway service. Single URL. No CORS issues.
