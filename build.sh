#!/bin/bash
# Railway build script: builds the React frontend and places it where Django can serve it
set -e

echo "==> Installing frontend dependencies..."
cd frontend
npm ci

echo "==> Building React frontend..."
VITE_API_URL=/api npm run build

echo "==> Copying frontend build into Django..."
cd ..
rm -rf backend/frontend_build
cp -r frontend/dist backend/frontend_build

echo "==> Frontend build complete."
