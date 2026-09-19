#!/usr/bin/env bash
# Learning Companion System — web server control.
#
# Usage: ./server.sh {start|stop|restart|status}
#
# Binds to the host/port from configure.json ("web" section), falling back
# to .env / defaults (see backend/app/config.py::get_server_bind).
# Override worker count with WEB_WORKERS (default: 2).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
PYTHON="$BACKEND/.venv/bin/python"
PID_FILE="$ROOT/logs/server.pid"
LOG_FILE="$ROOT/logs/server.log"
WORKERS="${WEB_WORKERS:-2}"
HEALTH_TIMEOUT=30

if [ ! -x "$PYTHON" ]; then
  echo "ERROR: venv not found at $BACKEND/.venv — run ./install.sh first" >&2
  exit 1
fi

read_bind() {
  # Prints "host port" from configure.json (web section) or settings defaults.
  (cd "$BACKEND" && "$PYTHON" -c '
from app.config import get_server_bind
h, p = get_server_bind()
print(h, p)
')
}

is_running() {
  [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

health_host() {
  case "$1" in
    127.0.0.1|localhost|::1) echo "$1" ;;
    *) echo "127.0.0.1" ;;
  esac
}

start() {
  if is_running; then
    echo "already running (pid $(cat "$PID_FILE")) — use ./server.sh restart to reload"
    return 0
  fi
  mkdir -p "$ROOT/logs" "$ROOT/data"
  read -r HOST PORT <<<"$(read_bind)"
  HHOST="$(health_host "$HOST")"
  echo "starting uvicorn on ${HOST}:${PORT} (${WORKERS} workers) ..."
  nohup "$PYTHON" -m uvicorn app.main:app \
    --host "$HOST" --port "$PORT" --workers "$WORKERS" \
    >>"$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"

  i=0
  while [ "$i" -lt "$HEALTH_TIMEOUT" ]; do
    if curl -fsS "http://${HHOST}:${PORT}/api/health" >/dev/null 2>&1; then
      echo "started: pid $(cat "$PID_FILE") — http://${HOST}:${PORT} (docs: /api/docs)"
      return 0
    fi
    if ! is_running; then
      echo "ERROR: server exited during startup — see $LOG_FILE" >&2
      rm -f "$PID_FILE"
      return 1
    fi
    sleep 1
    i=$((i + 1))
  done
  echo "WARNING: no health response within ${HEALTH_TIMEOUT}s — see $LOG_FILE" >&2
}

stop() {
  if ! is_running; then
    echo "not running"
    rm -f "$PID_FILE"
    return 0
  fi
  PID="$(cat "$PID_FILE")"
  echo "stopping pid $PID ..."
  kill "$PID" 2>/dev/null || true
  i=0
  while kill -0 "$PID" 2>/dev/null && [ "$i" -lt 10 ]; do
    sleep 1
    i=$((i + 1))
  done
  if kill -0 "$PID" 2>/dev/null; then
    echo "force killing ..."
    pkill -9 -P "$PID" 2>/dev/null || true
    kill -9 "$PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
  echo "stopped"
}

status() {
  if is_running; then
    echo "running (pid $(cat "$PID_FILE"))"
  else
    echo "stopped"
  fi
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}" >&2
    exit 2
    ;;
esac
