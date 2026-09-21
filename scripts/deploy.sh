#!/usr/bin/env bash
# 学习陪伴系统 - One-shot remote-server deploy.
#
# Assumes install.sh has already run (so .venv, .env, configure.json, the
# built frontend, alembic migrations and the default teacher all exist).
# This script:
#
#   1. Starts the backend under systemd (auto-restart on crash/reboot).
#   2. Installs nginx + copies deploy/nginx.conf.
#   3. (optional) Calls certbot for HTTPS when a domain is supplied.
#   4. Smoke-tests the deployment end-to-end.
#
# Usage:
#   sudo scripts/deploy.sh                              # HTTP only
#   sudo scripts/deploy.sh learning.example.com         # HTTP + HTTPS
#
# Environment overrides (all optional):
#   SERVICE_USER=study-moniter      # systemd service account (created if absent)
#   BIND_HOST=0.0.0.0               # uvicorn bind host (default: 127.0.0.1, nginx fronts it)
#   BIND_PORT=8000                  # uvicorn bind port
#   WORKERS=2                       # uvicorn workers
#   NGINX_SITE=/etc/nginx/sites-available/study-moniter
#
# Run as root (or with sudo) because it installs systemd units, nginx, and
# may call certbot.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
SERVICE_USER="${SERVICE_USER:-study-moniter}"
SERVICE_NAME="study-moniter"
BIND_HOST="${BIND_HOST:-127.0.0.1}"
BIND_PORT="${BIND_PORT:-8000}"
WORKERS="${WORKERS:-2}"
NGINX_SITE="${NGINX_SITE:-/etc/nginx/sites-available/study-moniter}"
DOMAIN="${1:-}"

step() { printf "\n\033[1;34m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
die()  { printf "\033[1;31m[fatal]\033[0m %s\n" "$*"; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Please run as root: sudo scripts/deploy.sh"

# --- Preflight --------------------------------------------------------------

step "Preflight"
[ -d "$BACKEND_DIR/.venv" ] || die "backend/.venv not found — run ./install.sh first"
[ -f "$PROJECT_ROOT/.env" ] || die ".env not found — run ./install.sh first"
[ -f "$BACKEND_DIR/alembic.ini" ] || die "alembic.ini missing — repo incomplete"
[ -f "$PROJECT_ROOT/deploy/nginx.conf" ] || die "deploy/nginx.conf missing"

# --- 1. systemd --------------------------------------------------------------

step "Installing systemd unit ($SERVICE_NAME)"

# Create the service account on first install.
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd -r -s /bin/false -d "$PROJECT_ROOT" "$SERVICE_USER"
fi

# chown runtime dirs so the service can write.
mkdir -p "$PROJECT_ROOT/data" "$PROJECT_ROOT/uploads" "$PROJECT_ROOT/logs"
chown -R "$SERVICE_USER":"$SERVICE_USER" "$PROJECT_ROOT/data" "$PROJECT_ROOT/uploads" "$PROJECT_ROOT/logs"
chmod 700 "$PROJECT_ROOT/data"

# Render the unit from the template, substituting our paths and bind addr.
UNIT_TMP="$(mktemp /tmp/study-moniter.service.XXXXXX)"
sed -e "s|/opt/study-moniter-system|$PROJECT_ROOT|g" \
    -e "s|^ExecStart=.*|ExecStart=$BACKEND_DIR/.venv/bin/uvicorn --app-dir $BACKEND_DIR app.main:app --host $BIND_HOST --port $BIND_PORT --workers $WORKERS|" \
    "$PROJECT_ROOT/systemd/study-moniter.service" > "$UNIT_TMP"

install -m 0644 "$UNIT_TMP" "/etc/systemd/system/$SERVICE_NAME.service"
rm -f "$UNIT_TMP"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME.service"
systemctl restart "$SERVICE_NAME.service"

# Wait briefly for the listener to come up.
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "http://${BIND_HOST}:${BIND_PORT}/api/health" >/dev/null 2>&1; then
    echo "  backend up (PID $(systemctl show -p MainPID --value "$SERVICE_NAME.service"))"
    break
  fi
  sleep 1
done

# --- 2. nginx ----------------------------------------------------------------

step "Configuring nginx reverse proxy"

if ! command -v nginx >/dev/null 2>&1; then
  warn "nginx not installed; installing via package manager"
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update && apt-get install -y nginx
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y nginx
  elif command -v yum >/dev/null 2>&1; then
    yum install -y nginx
  else
    die "no supported package manager found; install nginx manually"
  fi
fi

install -m 0644 "$PROJECT_ROOT/deploy/nginx.conf" "$NGINX_SITE"

# Enable the site, disable the default server block.
SITES_ENABLED="$(dirname "$NGINX_SITE")/../sites-enabled/study-moniter"
mkdir -p "$(dirname "$SITES_ENABLED")"
ln -sf "$NGINX_SITE" "$SITES_ENABLED"
if [ -f /etc/nginx/sites-enabled/default ]; then
  rm -f /etc/nginx/sites-enabled/default
fi

nginx -t
systemctl enable nginx
systemctl restart nginx

# --- 3. HTTPS (optional) -----------------------------------------------------

if [ -n "$DOMAIN" ]; then
  step "Provisioning Let's Encrypt cert for $DOMAIN"
  if ! command -v certbot >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
      apt-get install -y certbot python3-certbot-nginx
    else
      die "certbot install path not implemented for this distro"
    fi
  fi
  certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email \
    -d "$DOMAIN" || warn "certbot failed — site is still served over HTTP"
fi

# --- 4. Smoke test -----------------------------------------------------------

step "Smoke test"
HEALTH_HTTP="$(curl -fsS -o /dev/null -w '%{http_code}' http://127.0.0.1:80/api/health || echo 'fail')"
HEALTH_LOCAL="$(curl -fsS -o /dev/null -w '%{http_code}' "http://${BIND_HOST}:${BIND_PORT}/api/health" || echo 'fail')"
echo "  nginx -> backend : HTTP $HEALTH_HTTP"
echo "  direct :${BIND_PORT}    : HTTP $HEALTH_LOCAL"
if [ "$HEALTH_HTTP" != "200" ] && [ "$HEALTH_LOCAL" != "200" ]; then
  die "Health check failed on both paths — inspect 'journalctl -u $SERVICE_NAME -n 50' and 'nginx -t'."
fi

echo
step "Deployment complete"
cat <<EOF

Service:
  systemctl status $SERVICE_NAME       # backend
  systemctl restart $SERVICE_NAME
  journalctl -u $SERVICE_NAME -f        # live logs

nginx:
  nginx -t                              # config check
  systemctl reload nginx

URLs:
  http://${DOMAIN:-$(curl -s ifconfig.me 2>/dev/null || echo '<server-ip>')}/$([ -n "$DOMAIN" ] && echo "https://${DOMAIN}/" || echo "")

Login:
  username: yun
  password: value of PASS_WORD in $PROJECT_ROOT/.env

EOF