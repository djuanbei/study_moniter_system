#!/usr/bin/env bash
# 学习陪伴系统 - 安装脚本
# Self-contained, idempotent, supports Ubuntu / Debian / CentOS / macOS.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOG_DIR="$PROJECT_ROOT/logs"

cd "$PROJECT_ROOT"

# --- Logging -----------------------------------------------------------------

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/install.log"
exec > >(tee -a "$LOG_FILE") 2>&1

step() { printf "\n\033[1;34m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
die() { printf "\033[1;31m[fatal]\033[0m %s\n" "$*"; exit 1; }

# --- OS detection ------------------------------------------------------------

step "Detecting operating system"
# Guard the source — `.` is a special builtin and can defeat `set -e` even with `|| true`.
if [ -r /etc/os-release ]; then . /etc/os-release; fi
OS_FAMILY="unknown"
OS_NAME="${NAME:-$(uname -s)}"
# Use tr instead of ${OS_NAME,,} for bash 3.x compatibility (macOS default bash).
OS_NAME_LC="$(printf '%s' "$OS_NAME" | tr '[:upper:]' '[:lower:]')"
case "$OS_NAME_LC" in
  ubuntu*|debian*) OS_FAMILY="debian" ;;
  centos*|rhel*|fedora*) OS_FAMILY="rhel" ;;
  darwin*) OS_FAMILY="macos" ;;
  *) OS_FAMILY="unknown" ;;
esac
echo "Detected OS family: $OS_FAMILY ($OS_NAME)"

# --- Python ------------------------------------------------------------------

step "Checking Python"
PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then PYTHON_BIN="python"
  else die "python3 not found. Install Python 3.11+ first."; fi
fi
PY_VERSION="$("$PYTHON_BIN" -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
echo "Found $PYTHON_BIN $PY_VERSION"
PY_MAJOR="${PY_VERSION%%.*}"
PY_MINOR="${PY_VERSION#*.}"
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
  die "Python 3.11+ is required (found $PY_VERSION)."
fi

# --- uv ----------------------------------------------------------------------

step "Checking uv (Python package manager)"
if ! command -v uv >/dev/null 2>&1; then
  warn "uv not found, attempting to install"
  if [ "$OS_FAMILY" = "macos" ]; then
    if command -v brew >/dev/null 2>&1; then brew install uv || true
    else curl -LsSf https://astral.sh/uv/install.sh | sh; fi
  else
    curl -LsSf https://astral.sh/uv/install.sh | sh
  fi
fi
# Re-source PATH so the just-installed uv is picked up.
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
if ! command -v uv >/dev/null 2>&1; then
  die "uv installation failed. Install manually: https://docs.astral.sh/uv/"
fi
echo "Using $(uv --version)"

# --- Node --------------------------------------------------------------------

step "Checking Node.js"
if ! command -v node >/dev/null 2>&1; then
  warn "Node.js not found, attempting to install"
  if [ "$OS_FAMILY" = "macos" ] && command -v brew >/dev/null 2>&1; then
    brew install node || true
  elif [ "$OS_FAMILY" = "debian" ]; then
    if command -v apt-get >/dev/null 2>&1; then
      if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; else SUDO=""; fi
      $SUDO apt-get update && $SUDO apt-get install -y nodejs npm || true
    fi
  elif [ "$OS_FAMILY" = "rhel" ]; then
    if command -v dnf >/dev/null 2>&1; then
      if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; else SUDO=""; fi
      $SUDO dnf install -y nodejs npm || true
    fi
  fi
fi
if ! command -v node >/dev/null 2>&1; then
  die "Node.js installation failed. Install Node 18+ manually."
fi
NODE_VERSION="$(node --version)"
echo "Found node $NODE_VERSION"

# --- Tesseract (optional) -----------------------------------------------------

step "Checking tesseract (optional, for OCR)"
if ! command -v tesseract >/dev/null 2>&1; then
  warn "tesseract not found (optional). OCR will be unavailable."
else
  echo "Found tesseract $(tesseract --version 2>&1 | head -1)"
fi

# --- Python virtualenv + dependencies ----------------------------------------

step "Creating Python virtual environment"
cd "$BACKEND_DIR"
if [ ! -d ".venv" ]; then
  uv venv .venv --python 3.11 || die "uv venv failed (need Python 3.11+)"
fi
# Make sure Python 3.11 is actually installed (uv downloads on demand).
uv python install 3.11 2>/dev/null || warn "Could not pre-install Python 3.11 via uv"

step "Installing Python dependencies"
# Honor a custom PyPI mirror if set (e.g. UV_INDEX_URL=https://mirrors.tencent.com/pypi/simple/).
if [ -n "${UV_INDEX_URL:-}" ]; then
  echo "Using PyPI mirror: $UV_INDEX_URL"
fi

# Prefer `uv sync --frozen` so the locked versions in backend/uv.lock win.
# Falls back to `uv pip install -e .` for editable installs when uv.lock is missing.
if [ -f "$BACKEND_DIR/uv.lock" ]; then
  echo "Using backend/uv.lock (reproducible install)"
  if uv sync --frozen --python "$BACKEND_DIR/.venv/bin/python" 2>&1 | tail -20; then :; else
    die "uv sync failed. Check the output above; common causes are network/PyPI issues or a stale uv.lock."
  fi
else
  warn "backend/uv.lock not found — falling back to loose pip install"
  if uv pip install --python "$BACKEND_DIR/.venv/bin/python" -e "$BACKEND_DIR" 2>&1 | tail -20; then :; else
    die "uv pip install failed. Check the output above."
  fi
fi

# Always install the dev extras (pytest, ruff) so users can run tests locally.
uv pip install --python "$BACKEND_DIR/.venv/bin/python" -e "$BACKEND_DIR[dev]" 2>&1 | tail -5 || warn "dev extras install failed (non-fatal)"

step "Verifying critical imports"
verify_imports=0
if ! "$BACKEND_DIR/.venv/bin/python" -c "import fastapi, uvicorn, sqlalchemy, alembic, pydantic, langchain_core, PIL, reportlab, docx; print('  fastapi', fastapi.__version__); print('  uvicorn', uvicorn.__version__); print('  sqlalchemy', sqlalchemy.__version__)" 2>&1; then
  verify_imports=1
fi
if [ "$verify_imports" -ne 0 ]; then
  die "Critical imports failed — the virtualenv is incomplete. Re-run install.sh or check uv output above."
fi
echo "  all critical imports OK"

# Make sure the runtime log dirs exist for uvicorn out-of-the-box.
mkdir -p "$BACKEND_DIR/logs" "$PROJECT_ROOT/data" "$PROJECT_ROOT/uploads" "$PROJECT_ROOT/logs"
echo "  log/data/upload dirs ready"

# --- .env --------------------------------------------------------------------

step "Preparing .env"
if [ ! -f "$PROJECT_ROOT/.env" ]; then
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
  chmod 600 "$PROJECT_ROOT/.env"
  echo "Created .env from template."
  NEEDS_PASS_WORD=1
else
  echo ".env already exists, leaving it alone."
  NEEDS_PASS_WORD=0
fi

# --- PASS_WORD handling -------------------------------------------------------

# Detect PASS_WORD by *value*, not just key presence (template ships with PASS_WORD= empty).
# Strips both single and double quotes so `PASS_WORD="foo"` and `PASS_WORD='foo'` both work.
pass_word_value() {
  grep -E '^PASS_WORD=' "$PROJECT_ROOT/.env" 2>/dev/null | head -1 \
    | sed -E 's/^PASS_WORD=//' | tr -d '"'"'" || true
}

if [ "$NEEDS_PASS_WORD" = "1" ] || [ -z "$(pass_word_value)" ]; then
  step "Setting PASS_WORD in .env"
  if [ -t 0 ]; then
    PW=""
    while [ -z "$PW" ]; do
      read -r -s -p "Enter initial password for default teacher (min 8 chars): " PW
      echo
      [ "${#PW}" -lt 8 ] && { warn "Password too short, try again"; PW=""; continue; }
      read -r -s -p "Confirm password: " PW2
      echo
      [ "$PW" != "$PW2" ] && { warn "Passwords do not match"; PW=""; continue; }
    done
    if grep -qE '^PASS_WORD=' "$PROJECT_ROOT/.env"; then
      # BSD/GNU-portable in-place edit; secrets never leave .env via a backup file.
      # Use a heredoc-fed python one-liner so backslashes in the password are preserved verbatim.
      tmp="$(mktemp "${PROJECT_ROOT}/.env.XXXXXX")"
      chmod 600 "$tmp"
      PW="$PW" DOTENV="$PROJECT_ROOT/.env" OUT="$tmp" python3 - <<'PY'
import os, pathlib
pw, path, out = os.environ["PW"], pathlib.Path(os.environ["DOTENV"]), pathlib.Path(os.environ["OUT"])
lines = path.read_text().splitlines()
new_lines, replaced = [], False
for ln in lines:
    if ln.startswith("PASS_WORD="):
        new_lines.append(f"PASS_WORD={pw}")
        replaced = True
    else:
        new_lines.append(ln)
if not replaced:
    new_lines.append(f"PASS_WORD={pw}")
out.write_text("\n".join(new_lines) + "\n")
PY
      mv "$tmp" "$PROJECT_ROOT/.env"
    else
      printf "\nPASS_WORD=%s\n" "$PW" >> "$PROJECT_ROOT/.env"
    fi
    chmod 600 "$PROJECT_ROOT/.env"
    echo "PASS_WORD set in .env"
  else
    warn "Non-interactive shell: cannot prompt for PASS_WORD."
    warn "Edit $PROJECT_ROOT/.env and set PASS_WORD=<at-least-8-chars> before starting the backend."
    warn "Aborting install because the backend cannot bootstrap without PASS_WORD."
    exit 1
  fi
fi

# Re-check after the prompt: we must not continue without a usable PASS_WORD.
# bash 3.2 (macOS default) does not support ${#$(...)}; capture the value first.
pw_value="$(pass_word_value)"
if [ -z "$pw_value" ] || [ "${#pw_value}" -lt 8 ]; then
  die "PASS_WORD is missing or too short in .env. Set PASS_WORD=<min 8 chars> and re-run install."
fi

# Warn if SECRET_KEY is left at the example value — sessions are signed with it
# (PRD §85). Use openssl if available to generate a strong replacement.
secret_key_value() {
  grep -E '^SECRET_KEY=' "$PROJECT_ROOT/.env" 2>/dev/null | head -1 \
    | sed -E 's/^SECRET_KEY=//' | tr -d '"'"'" || true
}
sk_value="$(secret_key_value)"
if [ -z "$sk_value" ] || [ "$sk_value" = "change-me-to-a-long-random-string" ]; then
  warn "SECRET_KEY is unset or still the example placeholder."
  warn "Session cookies are signed with it — leaving the default is a security risk (PRD §85)."
  if command -v openssl >/dev/null 2>&1; then
    new_sk="$(openssl rand -base64 48 | tr -d '\n')"
    if grep -qE '^SECRET_KEY=' "$PROJECT_ROOT/.env"; then
      tmp="$(mktemp "${PROJECT_ROOT}/.env.XXXXXX")"
      chmod 600 "$tmp"
      SK="$new_sk" DOTENV="$PROJECT_ROOT/.env" OUT="$tmp" python3 - <<'PY' 2>/dev/null || true
import os, pathlib
sk, path, out = os.environ["SK"], pathlib.Path(os.environ["DOTENV"]), pathlib.Path(os.environ["OUT"])
lines = path.read_text().splitlines()
new_lines = []
for ln in lines:
    if ln.startswith("SECRET_KEY="):
        new_lines.append(f"SECRET_KEY={sk}")
    else:
        new_lines.append(ln)
out.write_text("\n".join(new_lines) + "\n")
PY
      mv "$tmp" "$PROJECT_ROOT/.env"
    else
      printf "\nSECRET_KEY=%s\n" "$new_sk" >> "$PROJECT_ROOT/.env"
    fi
    chmod 600 "$PROJECT_ROOT/.env"
    echo "Generated a random SECRET_KEY (48 bytes, base64) and wrote it to .env."
  else
    warn "openssl not found — generate one manually with 'openssl rand -base64 48'"
    warn "and set SECRET_KEY=... in $PROJECT_ROOT/.env before starting the backend."
  fi
fi

# --- configure.json ---------------------------------------------------------

step "Preparing configure.json"
if [ ! -f "$PROJECT_ROOT/configure.json" ]; then
  cp "$PROJECT_ROOT/configure.json.example" "$PROJECT_ROOT/configure.json"
  echo "Created configure.json from template."
else
  echo "configure.json already exists, leaving it alone."
fi

# --- Database ----------------------------------------------------------------

step "Running database migrations"
( cd "$BACKEND_DIR" && "$BACKEND_DIR/.venv/bin/alembic" -c "$BACKEND_DIR/alembic.ini" upgrade head ) \
  || ( cd "$BACKEND_DIR" && uv run alembic -c "$BACKEND_DIR/alembic.ini" upgrade head ) \
  || die "alembic migration failed"

# --- Default teacher (PASS_WORD-driven) --------------------------------------

step "Ensuring default teacher exists"
( cd "$BACKEND_DIR" && .venv/bin/python -c "
from app.config import get_settings
from app.database import SessionLocal
from app.routes._helpers import ensure_default_teacher_exists
s = get_settings()
db = SessionLocal()
try:
    ensure_default_teacher_exists(db, s)
finally:
    db.close()
" ) || ( uv run --project "$BACKEND_DIR" python -c "
from app.config import get_settings
from app.database import SessionLocal
from app.routes._helpers import ensure_default_teacher_exists
s = get_settings()
db = SessionLocal()
try:
    ensure_default_teacher_exists(db, s)
finally:
    db.close()
" ) || die "default teacher bootstrap failed"

# --- Frontend build ----------------------------------------------------------

step "Building frontend"
cd "$FRONTEND_DIR"
# Honor a custom npm registry if set (e.g. NPM_REGISTRY=https://mirrors.tencent.com/npm/).
if [ -n "${NPM_REGISTRY:-}" ]; then
  echo "Using npm registry: $NPM_REGISTRY"
  npm config set registry "$NPM_REGISTRY"
elif [ ! -d "node_modules" ]; then
  # Default to a faster mirror if the public registry is unreachable / slow.
  if ! curl -sSI -m 5 https://registry.npmjs.org/ >/dev/null 2>&1; then
    warn "Public npm registry unreachable; falling back to mirrors.tencent.com"
    npm config set registry https://mirrors.tencent.com/npm/
  fi
fi
if [ ! -d "node_modules" ]; then
  npm install --no-audit --no-fund --prefer-offline
fi
# npm >= 11 sometimes writes wrapper scripts instead of symlinks in node_modules/.bin
# (regression in npm 11.x). Vite 5's bin/vite.js uses an import path that only
# resolves correctly when the entry is a real symlink; the wrapper script points
# to a non-existent node_modules/dist/node/cli.js. Fall back to invoking the
# package's bin script directly via node when the .bin entry is not a symlink.
run_vite_build() {
  if [ -L "node_modules/.bin/vite" ] || [ -f "node_modules/vite/bin/vite.js" ]; then
    npm run build && return 0
  fi
  if [ -f "node_modules/vite/bin/vite.js" ]; then
    warn "Detected npm 11+ wrapper-script bug; invoking vite via node directly."
    node node_modules/vite/bin/vite.js build && return 0
  fi
  die "vite not installed (no node_modules/vite)"
}
run_vite_build
echo "Frontend built to $FRONTEND_DIR/dist"

# --- Runtime directories -----------------------------------------------------

step "Creating runtime directories"
mkdir -p "$PROJECT_ROOT/data" "$PROJECT_ROOT/uploads" "$PROJECT_ROOT/logs"
# Family-learning system stores sensitive student data; lock down data/.
chmod 700 "$PROJECT_ROOT/data" 2>/dev/null || warn "Could not chmod 700 data/"

# --- Summary -----------------------------------------------------------------

# Resolve the host/port from configure.json so the hint matches the actual
# deployment configuration (PRD §87 — configure.json:web is authoritative).
CFG_HOST="0.0.0.0"
CFG_PORT="8000"
if command -v python3 >/dev/null 2>&1 && [ -f "$PROJECT_ROOT/configure.json" ]; then
  # Capture python's stdout via a temp file so quotes inside the python
  # string don't terminate the surrounding shell token (the previous
  # `eval "$(...)"` form tripped on the literal `(` in `web.get(...)`).
  cfg_tmp="$(mktemp "${PROJECT_ROOT}/.cfg.XXXXXX")"
  chmod 600 "$cfg_tmp"
  CFG_PATH="$PROJECT_ROOT/configure.json" python3 - "$cfg_tmp" <<'PY' 2>/dev/null || true
import json, os, sys
out = sys.argv[1]
try:
    cfg = json.load(open(os.environ.get("CFG_PATH", "")))
except Exception:
    cfg = {}
web = cfg.get("web") or {}
with open(out, "w") as fh:
    fh.write(f'CFG_HOST={web.get("host", "0.0.0.0")}\n')
    fh.write(f'CFG_PORT={web.get("port", 8000)}\n')
PY
  if [ -s "$cfg_tmp" ]; then
    . "$cfg_tmp"
  fi
  rm -f "$cfg_tmp"
fi

step "Installation complete"
cat <<EOF

Next steps:
  1. Edit .env if you need to set LLM API keys (OPENAI_API_KEY or ANTHROPIC_API_KEY).
  2. Start the backend:
       cd backend && uv run uvicorn app.main:app --host $CFG_HOST --port $CFG_PORT
  3. Open http://localhost:$CFG_PORT in your browser.
     - Dev frontend with hot-reload:  cd frontend && npm run dev
  4. Log in with the default teacher account (username: yun, password from PASS_WORD in .env).
     You will be asked to change the password on first login.

Service management (optional):
  systemd:    see systemd/study-moniter.service
  Docker:     docker compose up -d

EOF

# --- Optional systemd registration ------------------------------------------

if [ "$OS_FAMILY" != "macos" ] && [ "$(id -u)" -eq 0 ] && command -v systemctl >/dev/null 2>&1; then
  step "systemd detected"
  echo "To install as a daemon, run:"
  echo "  cp systemd/study-moniter.service /etc/systemd/system/"
  echo "  systemctl daemon-reload && systemctl enable --now study-moniter.service"
fi