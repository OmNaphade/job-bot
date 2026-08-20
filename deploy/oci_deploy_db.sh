#!/usr/bin/env bash
# One-shot (and re-runnable) deploy script for job-alert's DB/WORKER server
# (VM2): Postgres+pgvector, plus a systemd timer that runs the ingestion and
# job-embedding pass every 15 minutes. This is the ONLY place migrations run
# in production -- see oci_deploy_app.sh, which does not touch schema, so the
# two VMs never race `alembic upgrade` against the same database.
#
# What it does:
#   1. Installs Postgres 16 + pgvector from the PGDG apt repo, plus git/python3.
#   2. Configures Postgres to listen on this VM's private IP only (never the
#      public internet) and to accept connections only from APP_HOST (VM1's
#      private IP) -- both at the Postgres level (pg_hba.conf) and the OS
#      firewall level (ufw), matching bot_docs/ARCHITECTURE.md's design.
#   3. Creates the job_alert database/role and enables the vector extension,
#      idempotently (safe to re-run).
#   4. Clones the repo, builds a venv, installs backend/requirements-lock.txt.
#   5. Bootstraps backend/.env from .env.example if missing.
#   6. Runs `alembic upgrade head`.
#   7. Writes job-alert-worker.service (oneshot: one ingestion pass) +
#      job-alert-worker.timer (every 15 minutes, Persistent=true so a missed
#      tick from a reboot catches up), replacing both the old GitHub-Actions
#      cron and the app's old in-process APScheduler -- see
#      bot_docs/ARCHITECTURE.md for why there must be exactly one scheduling
#      mechanism, not "don't run more than one" as a manual rule.
#   8. Runs health checks.
#
# Required env vars (no sane default exists for these -- the script refuses
# to run without them):
#   DB_PASSWORD    - password for the app_user Postgres role this script creates.
#   APP_HOST       - VM1's *private* IP (e.g. 10.0.0.153) -- the only host
#                    allowed to connect to Postgres here.
#
# Usage: see bot_docs/OPERATIONS.md.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/OmNaphade/job-bot.git}"
APP_DIR="${APP_DIR:-$HOME/job-bot}"
SERVICE_USER="${SERVICE_USER:-$(whoami)}"
DB_NAME="${DB_NAME:-job_alert}"
DB_USER="${DB_USER:-app_user}"
DB_PASSWORD="${DB_PASSWORD:-}"
APP_HOST="${APP_HOST:-}"
PG_VERSION="${PG_VERSION:-16}"
PG_CONF_DIR="/etc/postgresql/${PG_VERSION}/main"

log() { echo -e "\n\033[1;36m==> $1\033[0m"; }

if [ -z "$DB_PASSWORD" ]; then
  echo "DB_PASSWORD is required (password for the app_user Postgres role). Example:" >&2
  echo "  DB_PASSWORD='...' APP_HOST=10.0.0.153 ./oci_deploy_db.sh" >&2
  exit 1
fi
if [ -z "$APP_HOST" ]; then
  echo "APP_HOST is required -- VM1's *private* IP, the only host allowed to reach" >&2
  echo "Postgres on this VM. Example:" >&2
  echo "  DB_PASSWORD='...' APP_HOST=10.0.0.153 ./oci_deploy_db.sh" >&2
  exit 1
fi

log "1/8 Installing Postgres ${PG_VERSION} + pgvector (via PGDG) and base packages"
sudo apt-get update -y
sudo apt-get install -y curl ca-certificates git python3-venv python3-pip ufw postgresql-common
if [ ! -f /etc/apt/sources.list.d/pgdg.list ]; then
  yes | sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
fi
sudo apt-get install -y "postgresql-${PG_VERSION}" "postgresql-${PG_VERSION}-pgvector"

log "2/8 Configuring Postgres (listen address, pg_hba, memory)"
PRIVATE_IP="$(hostname -I | awk '{print $1}')"

# listen_addresses: bind to this VM's own private IP explicitly (not 0.0.0.0,
# not localhost-only) -- VM1 needs to reach it, but it must never be reachable
# from the public internet.
sudo sed -i "s/^#\?listen_addresses.*/listen_addresses = '${PRIVATE_IP}'/" "${PG_CONF_DIR}/postgresql.conf"
# Conservative memory tuning -- this VM has only 1GB RAM total, shared with
# the ingestion/matching worker process. See bot_docs/ARCHITECTURE.md.
sudo sed -i "s/^#\?shared_buffers.*/shared_buffers = 128MB/" "${PG_CONF_DIR}/postgresql.conf"
sudo sed -i "s/^#\?max_connections.*/max_connections = 20/" "${PG_CONF_DIR}/postgresql.conf"

HBA_LINE="host    ${DB_NAME}    ${DB_USER}    ${APP_HOST}/32    scram-sha-256"
if ! sudo grep -qF "$HBA_LINE" "${PG_CONF_DIR}/pg_hba.conf"; then
  echo "$HBA_LINE" | sudo tee -a "${PG_CONF_DIR}/pg_hba.conf" >/dev/null
fi

sudo systemctl restart postgresql

log "3/8 Firewall (ufw) -- Postgres reachable only from APP_HOST"
sudo ufw allow OpenSSH >/dev/null
sudo ufw allow from "$APP_HOST" to any port 5432 proto tcp >/dev/null
sudo ufw --force enable

log "4/8 Creating database, role, and pgvector extension (idempotent)"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
  ELSE
    ALTER ROLE ${DB_USER} PASSWORD '${DB_PASSWORD}';
  END IF;
END
\$\$;
SQL
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}"
fi
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER}"
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector"

log "5/8 Fetching latest code"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin
  git -C "$APP_DIR" reset --hard origin/main
else
  git clone "$REPO_URL" "$APP_DIR"
fi

log "6/8 Python venv + dependencies"
cd "$APP_DIR/backend"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements-lock.txt -q

log "7/8 Backend .env + migrations"
if [ ! -f "$APP_DIR/backend/.env" ]; then
  cp "$APP_DIR/backend/.env.example" "$APP_DIR/backend/.env"
  # DATABASE_URL points at Postgres on *this* VM (localhost) -- unlike VM1's
  # .env, which points at this VM's private IP instead.
  sed -i "s#^DATABASE_URL=.*#DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}#" "$APP_DIR/backend/.env"
  echo "Created backend/.env with DATABASE_URL set. Still needs GOOGLE_API_KEY and"
  echo "the ingestion-source secrets (ALERT_EMAIL_*, ADZUNA_*, etc. -- see"
  echo "bot_docs/SOURCES.md) filled in:"
  echo "  nano $APP_DIR/backend/.env"
  echo "  sudo systemctl restart job-alert-worker.timer   # picks up new env on next tick"
else
  echo "backend/.env already exists -- leaving it untouched."
fi

DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}" python -m alembic upgrade head
deactivate

log "8/8 systemd worker service + timer"
sudo tee /etc/systemd/system/job-alert-worker.service >/dev/null <<EOF
[Unit]
Description=Job Alert ingestion + matching worker (one pass)
After=network.target postgresql.service

[Service]
Type=oneshot
User=${SERVICE_USER}
WorkingDirectory=${APP_DIR}/backend
ExecStart=${APP_DIR}/backend/.venv/bin/python -m scripts.run_ingestion_once
EOF

sudo tee /etc/systemd/system/job-alert-worker.timer >/dev/null <<EOF
[Unit]
Description=Run the Job Alert worker every 15 minutes

[Timer]
OnCalendar=*:0/15
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable job-alert-worker.timer >/dev/null
sudo systemctl restart job-alert-worker.timer

log "Health checks"
if sudo -u postgres pg_isready -h "$PRIVATE_IP" >/dev/null 2>&1; then
  echo "Postgres:      OK, listening on ${PRIVATE_IP}:5432"
else
  echo "Postgres:      FAILED -- check: sudo systemctl status postgresql"
fi
echo "Worker timer:  $(systemctl is-active job-alert-worker.timer) (next run: $(systemctl list-timers job-alert-worker.timer --no-legend | awk '{print $1, $2}'))"
echo ""
echo "Run one pass right now to confirm it actually works end-to-end:"
echo "  sudo systemctl start job-alert-worker.service && sudo journalctl -u job-alert-worker.service -n 50"
