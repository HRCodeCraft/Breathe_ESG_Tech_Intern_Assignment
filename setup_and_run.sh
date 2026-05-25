#!/bin/bash
# One command to set up and run the full app locally.
# Usage: bash setup_and_run.sh
# Then open: http://localhost:8000
# Login: analyst / analyst123

set -e

echo "==> Setting up Python environment..."
cd backend
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -r requirements.txt -q

echo "==> Building React frontend..."
cd ../frontend
npm install -q
VITE_API_URL=/api npm run build
cd ..
rm -rf backend/frontend_build
cp -r frontend/dist backend/frontend_build

echo "==> Running database migrations..."
cd backend
python manage.py migrate -v 0

echo "==> Seeding reference data and demo users..."
python manage.py seed_reference_data

echo "==> Collecting static files..."
python manage.py collectstatic --noinput -v 0

echo ""
echo "========================================="
echo " App ready at http://localhost:8000"
echo " Login: analyst / analyst123"
echo "========================================="
echo ""
python manage.py runserver
