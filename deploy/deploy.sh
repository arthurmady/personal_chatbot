#!/bin/bash
set -e

APP_DIR="${APP_DIR:-/var/www/personal_chatbot}"

cd "$APP_DIR"

echo "=== Pulling latest code ==="
# Configure SSH key if needed: export GIT_SSH_COMMAND="ssh -i /path/to/key"
git pull origin main

echo "=== Installing Python dependencies ==="
source venv/bin/activate
pip install -r backend/requirements.txt -q

echo "=== Building frontend ==="
cd frontend
npm install --silent
npm run build
cd ..

echo "=== Restarting backend ==="
systemctl restart chatbot
sleep 2
systemctl is-active --quiet chatbot && echo "Backend running" || echo "Backend FAILED to start"

echo "=== Deploy complete ==="
