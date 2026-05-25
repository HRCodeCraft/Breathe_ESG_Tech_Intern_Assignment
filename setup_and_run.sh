#!/bin/sh
# Works with: bash setup_and_run.sh  OR  sh setup_and_run.sh  OR  ./setup_and_run.sh
# Opens at http://localhost:8000  |  Login: analyst / analyst123

# If running under sh/dash, re-exec under bash for full compatibility
if [ -z "$BASH_VERSION" ]; then
  exec bash "$0" "$@"
fi

set -e

# Load nvm if available (so Node version is correct even if system Node is old)
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  . "$NVM_DIR/nvm.sh"
  nvm use 20 2>/dev/null || nvm use 18 2>/dev/null || true
fi

# Detect project root regardless of where the script is called from
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Checking requirements..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.10+ from https://python.org and re-run."
  exit 1
fi
if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: node not found. Install Node 18+ from https://nodejs.org and re-run."
  exit 1
fi

NODE_MAJOR=$(node --version | sed 's/v//' | cut -d. -f1)
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "ERROR: Node $(node --version) is too old. Need Node 18+."
  echo "  Install via nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash"
  echo "  Then: source ~/.bashrc && nvm install 20 && bash setup_and_run.sh"
  exit 1
fi

echo "==> Python: $(python3 --version)  |  Node: $(node --version)"

echo "==> Setting up Python environment..."
cd "$SCRIPT_DIR/backend"
python3 -m venv .venv 2>/dev/null || true
. .venv/bin/activate
pip install -r requirements.txt -q

echo "==> Building React frontend..."
cd "$SCRIPT_DIR/frontend"
npm install -q
VITE_API_URL=/api npm run build
rm -rf "$SCRIPT_DIR/backend/frontend_build"
cp -r "$SCRIPT_DIR/frontend/dist" "$SCRIPT_DIR/backend/frontend_build"

echo "==> Running database migrations..."
cd "$SCRIPT_DIR/backend"
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
