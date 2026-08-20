#!/usr/bin/env bash
# One-shot (and re-runnable) deploy script for job-alert's APP server (VM1):
# the FastAPI backend + nginx (serving the Flutter web build, reverse-proxying
# /api/, terminating TLS). Postgres and the ingestion/matching worker live on
# a separate VM2 -- see oci_deploy_db.sh -- reached over the private VCN IP,
# never the public internet.
#
# What it does:
#   1. Installs system packages (python3, nginx, git, certbot) and opens this
#      VM's own firewall (ufw) for HTTP/HTTPS/SSH.
#   2. Clones the repo on first run, `git pull`s (hard reset) on later runs.
#   3. Creates/updates a Python venv and installs backend/requirements-lock.txt.
#   4. Bootstraps backend/.env from .env.example if it doesn't exist yet
#      (never overwrites an existing .env -- your real secrets are safe).
#      Does NOT run Alembic migrations -- VM2 owns the schema, see
#      oci_deploy_db.sh, so two VMs never race `alembic upgrade` against the
#      same database.
#   5. Writes a systemd unit for the FastAPI backend (auto-start on boot,
#      auto-restart on crash) and (re)starts it.
#   6. If a Flutter web build has been uploaded to ~/web-build (see "Deploying
#      the frontend" in bot_docs/OPERATIONS.md), publishes it to
#      /var/www/job-alert-web.
#   7. Writes an nginx site (plain HTTP only, first run only -- see below) and,
#      if SERVER_NAME is a real domain, hands it to certbot to add TLS.
#   8. Optionally installs a DuckDNS updater cron job, if DUCKDNS_TOKEN/
#      DUCKDNS_SUBDOMAIN are set, so DNS keeps pointing at this VM's public IP
#      even if OCI ever reassigns it.
#   9. Runs health checks at the end.
#
# Safe to re-run any time (e.g. after `git push`ing new code) -- it pulls the
# latest code, reinstalls dependencies, and restarts the service. The nginx
# site file is only *written* on first run -- once certbot has edited it to
# add the TLS server block, this script leaves it alone rather than
# clobbering that edit back to plain HTTP on every re-run.
#
# Usage: see bot_docs/OPERATIONS.md.

set -euo pipefail

# --- Configuration (override via env vars if you need something different) ---
REPO_URL="${REPO_URL:-https://github.com/OmNaphade/job-bot.git}"
APP_DIR="${APP_DIR:-$HOME/job-bot}"
SERVICE_NAME="${SERVICE_NAME:-job-alert}"
SERVICE_USER="${SERVICE_USER:-$(whoami)}"
BACKEND_PORT="${BACKEND_PORT:-9000}"
WEB_ROOT="${WEB_ROOT:-/var/www/job-alert-web}"
WEB_BUILD_STAGING="${WEB_BUILD_STAGING:-$HOME/web-build}"
# Your DuckDNS (or other) domain, e.g. "job-alert-app.duckdns.org". Leave as
# "_" (nginx catch-all) to run IP-only with no TLS -- fine for a first smoke
# test, not for real use (no HTTPS, and certbot is skipped entirely below).
SERVER_NAME="${SERVER_NAME:-_}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"
# Optional: keep DuckDNS pointed at this VM's public IP even if it changes.
# Leave both empty to skip.
DUCKDNS_TOKEN="${DUCKDNS_TOKEN:-}"
DUCKDNS_SUBDOMAIN="${DUCKDNS_SUBDOMAIN:-}"

log() { echo -e "\n\033[1;36m==> $1\033[0m"; }

log "1/9 Installing system packages"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip nginx git ufw curl certbot python3-certbot-nginx

log "2/9 Configuring firewall (ufw)"
sudo ufw allow OpenSSH >/dev/null
sudo ufw allow 80/tcp >/dev/null
sudo ufw allow 443/tcp >/dev/null
sudo ufw --force enable

log "3/9 Fetching latest code"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin
  git -C "$APP_DIR" reset --hard origin/main
else
  git clone "$REPO_URL" "$APP_DIR"
fi

log "4/9 Python venv + dependencies"
cd "$APP_DIR/backend"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements-lock.txt -q
deactivate

log "5/9 Backend .env"
if [ ! -f "$APP_DIR/backend/.env" ]; then
  cp "$APP_DIR/backend/.env.example" "$APP_DIR/backend/.env"
  echo "Created backend/.env from .env.example -- at minimum, set DATABASE_URL to"
  echo "VM2's *private* IP (never expose Postgres publicly) and GOOGLE_API_KEY"
  echo "(needed here too -- resume upload/parsing happens synchronously in the API"
  echo "request path, see bot_docs/ARCHITECTURE.md). Edit it, then:"
  echo "  nano $APP_DIR/backend/.env"
  echo "  sudo systemctl restart $SERVICE_NAME"
else
  echo "backend/.env already exists -- leaving it untouched."
fi

log "6/9 systemd service"
sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<EOF
[Unit]
Description=Job Alert backend
After=network.target

[Service]
User=${SERVICE_USER}
WorkingDirectory=${APP_DIR}/backend
Environment="PATH=${APP_DIR}/backend/.venv/bin"
ExecStart=${APP_DIR}/backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port ${BACKEND_PORT}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME" >/dev/null
sudo systemctl restart "$SERVICE_NAME"

log "7/9 Frontend"
sudo mkdir -p "$WEB_ROOT"
if [ -d "$WEB_BUILD_STAGING" ] && [ -n "$(ls -A "$WEB_BUILD_STAGING" 2>/dev/null)" ]; then
  sudo rm -rf "${WEB_ROOT:?}"/*
  sudo cp -r "$WEB_BUILD_STAGING"/* "$WEB_ROOT"/
  echo "Published frontend build from $WEB_BUILD_STAGING to $WEB_ROOT"
else
  echo "No frontend build found at $WEB_BUILD_STAGING -- skipping frontend publish this run."
  echo "Build it locally (flutter build web), scp build/web/* to $WEB_BUILD_STAGING on this VM,"
  echo "then re-run this script to publish it."
fi

log "8/9 nginx + TLS"
sudo mkdir -p /var/www/certbot
NGINX_SITE=/etc/nginx/sites-available/job-alert
if [ ! -f "$NGINX_SITE" ]; then
  # Plain HTTP only -- once a real SERVER_NAME is set and certbot runs below,
  # certbot's nginx plugin edits this file in place to add the TLS server
  # block and an HTTP->HTTPS redirect. This script never overwrites it again
  # after this first write, so re-runs don't clobber certbot's edits.
  sudo tee "$NGINX_SITE" >/dev/null <<EOF
server {
    listen 80;
    server_name ${SERVER_NAME};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:${BACKEND_PORT}/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location / {
        root ${WEB_ROOT};
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
  sudo ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/job-alert
  sudo rm -f /etc/nginx/sites-enabled/default
else
  echo "nginx site already exists -- leaving it untouched (certbot may have edited it)."
fi
sudo nginx -t
sudo systemctl enable nginx >/dev/null
sudo systemctl restart nginx

if [ "$SERVER_NAME" != "_" ]; then
  if [ -z "$LETSENCRYPT_EMAIL" ]; then
    echo "SERVER_NAME is set but LETSENCRYPT_EMAIL is empty -- skipping certbot."
    echo "Set LETSENCRYPT_EMAIL and re-run to get a TLS cert for $SERVER_NAME."
  else
    echo "Requesting/renewing TLS cert for $SERVER_NAME via certbot..."
    sudo certbot --nginx -d "$SERVER_NAME" --non-interactive --agree-tos \
      -m "$LETSENCRYPT_EMAIL" --redirect || \
      echo "certbot failed -- check that $SERVER_NAME already resolves to this VM's public IP (DNS propagation, DuckDNS update, etc.) and re-run."
  fi
else
  echo "SERVER_NAME is \"_\" (no real domain) -- skipping certbot. IP-only access has no TLS."
fi

if [ -n "$DUCKDNS_TOKEN" ] && [ -n "$DUCKDNS_SUBDOMAIN" ]; then
  log "9/9 DuckDNS auto-updater"
  cat > "$HOME/duckdns_update.sh" <<EOF
#!/usr/bin/env bash
curl -fsS "https://www.duckdns.org/update?domains=${DUCKDNS_SUBDOMAIN}&token=${DUCKDNS_TOKEN}&ip=" >/dev/null
EOF
  chmod +x "$HOME/duckdns_update.sh"
  # Idempotent: drop any previous duckdns_update entry before adding the
  # current one, so re-running this script doesn't pile up duplicate cron
  # lines.
  (crontab -l 2>/dev/null | grep -v duckdns_update.sh; echo "*/5 * * * * $HOME/duckdns_update.sh >/dev/null 2>&1") | crontab -
  "$HOME/duckdns_update.sh" && echo "DuckDNS updated now; cron will keep it fresh every 5 minutes."
else
  log "9/9 DuckDNS auto-updater (skipped -- DUCKDNS_TOKEN/DUCKDNS_SUBDOMAIN not set)"
fi

log "Health checks"
if curl -sf "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null; then
  echo "Backend:  OK (http://127.0.0.1:${BACKEND_PORT}/health)"
else
  echo "Backend:  FAILED -- check: sudo systemctl status ${SERVICE_NAME} && sudo journalctl -u ${SERVICE_NAME} -n 50"
  echo "          (Most likely cause: DATABASE_URL in backend/.env doesn't point at a reachable, migrated Postgres on VM2.)"
fi
if curl -sf "http://127.0.0.1/api/health" >/dev/null; then
  echo "nginx -> API proxy: OK"
else
  echo "nginx -> API proxy: FAILED -- check: sudo nginx -t && sudo systemctl status nginx"
fi
if curl -sf "http://127.0.0.1/" >/dev/null; then
  echo "nginx -> frontend:  OK"
else
  echo "nginx -> frontend:  nothing published yet (see step 7 above)"
fi

log "Done"
echo "Backend service: sudo systemctl {status|restart|stop} ${SERVICE_NAME}"
echo "Backend logs:    sudo journalctl -u ${SERVICE_NAME} -f"
