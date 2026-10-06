#!/bin/bash
set -e

APP_DIR="${APP_DIR:-/var/www/personal_chatbot}"

cd "$APP_DIR"

echo "=== Backing up data/ ==="
# data/ is not in git: keep the last 14 archives next to the app (copy them off the VPS too)
mkdir -p backups
if [ -d backend/data ]; then
  tar czf "backups/data-$(date +%Y%m%d-%H%M%S).tgz" -C backend data
  ls -1t backups/data-*.tgz | tail -n +15 | xargs -r rm --
fi

echo "=== Pulling latest code ==="
# Configure SSH key if needed: export GIT_SSH_COMMAND="ssh -i /path/to/key"
git pull origin main

echo "=== Installing Python dependencies ==="
source venv/bin/activate
pip install -r backend/requirements.txt -q

echo "=== Building frontend ==="
cd frontend
npm ci --silent
npm run build
cd ..

echo "=== Restarting backend ==="
systemctl restart chatbot
sleep 2
if systemctl is-active --quiet chatbot; then
  echo "Backend running"
else
  echo "Backend FAILED to start" >&2
  journalctl -u chatbot -n 30 --no-pager >&2 || true
  exit 1
fi

echo "=== Deploy complete ==="
