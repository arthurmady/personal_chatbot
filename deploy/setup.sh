#!/bin/bash
set -e

APP_DIR="${APP_DIR:-/var/www/personal_chatbot}"

cd "$APP_DIR"

echo "=== Installing dependencies ==="
apt install -y git python3 python3-venv python3-pip curl

# Node.js 20.x
if ! command -v node &> /dev/null; then
  echo "=== Installing Node.js ==="
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt install -y nodejs
fi

echo "=== Creating Python venv ==="
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

echo "=== Building frontend ==="
cd frontend
npm install
npm run build
cd ..

echo "=== Creating .env ==="
cp backend/.env.example backend/.env
echo ">>> Edit $APP_DIR/backend/.env with your real values <<<"

echo "=== Installing systemd service ==="
cat > /etc/systemd/system/chatbot.service << EOF
[Unit]
Description=Personal Chatbot API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}/backend
ExecStart=${APP_DIR}/venv/bin/python -m uvicorn api:app --host 0.0.0.0 --port 1234
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=${APP_DIR}/backend

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable chatbot
systemctl start chatbot

echo "=== Setup complete ==="
echo "Backend running on http://$(hostname -I | awk '{print $1}'):1234"
echo "Configure Traefik to proxy to http://127.0.0.1:1234"
