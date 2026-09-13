#!/bin/bash
set -e

APP_DIR=/var/www/personal_chatbot

echo "=== System update ==="
apt update && apt upgrade -y

echo "=== Installing dependencies ==="
apt install -y git python3 python3-venv python3-pip nginx curl

# Node.js 20.x
if ! command -v node &> /dev/null; then
  echo "=== Installing Node.js ==="
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt install -y nodejs
fi

echo "=== Cloning repo ==="
rm -rf "$APP_DIR"
mkdir -p /var/www
git clone https://github.com/arthurmady/personal_chatbot.git "$APP_DIR"

cd "$APP_DIR"

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
cp deploy/chatbot.service /etc/systemd/system/chatbot.service
systemctl daemon-reload
systemctl enable chatbot
systemctl start chatbot

echo "=== Configuring Nginx ==="
cp deploy/nginx.conf /etc/nginx/sites-available/chatbot
ln -sf /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/chatbot
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "=== Setup complete ==="
echo "App should be running on http://$(hostname -I | awk '{print $1}'):8000"
