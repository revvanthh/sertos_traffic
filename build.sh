#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

# Install production dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Build and copy the React frontend into Django static assets
npm ci --prefix frontend
npm run build --prefix frontend
rm -rf staticfiles/frontend
mkdir -p staticfiles/frontend
cp -r frontend/dist/. staticfiles/frontend/
mkdir -p staticfiles/assets
cp -r frontend/dist/assets/. staticfiles/assets/
mkdir -p templates
cp frontend/dist/index.html templates/index.html

# Collect static files into STATIC_ROOT using WhiteNoise
python manage.py collectstatic --no-input

# Apply database migrations
python manage.py migrate
