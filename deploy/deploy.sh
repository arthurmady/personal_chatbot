#!/bin/bash
set -e

cd /opt/chatbot

echo "=== Pulling latest code ==="
git -c credential.helper="store --file=/opt/chatbot/.git-credentials" pull origin main

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
