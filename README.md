# 学习陪伴系统 (Learning Companion System)

A web-based learning companion system that helps teachers generate assignments, grade student submissions, and track each student's academic progress through an LLM-assisted workflow.

See `project_PRD.md` for the full system specification.

## Stack

- **Backend:** Python 3.11+ · FastAPI · SQLAlchemy · Alembic · SQLite (WAL)
- **Frontend:** React 18 · Vite · React Router
- **LLM:** LangChain agent framework (OpenAI / Anthropic / Minimax-compatible)
- **Auth:** Argon2 or bcrypt · HttpOnly cookies · CSRF · RBAC
- **Image processing:** Pillow · optional pytesseract · optional vision model
- **Diagrams:** SVG preferred, Mermaid optional

## Quick Start

```bash
./install.sh
```

`install.sh` is self-contained and idempotent. It creates a virtual environment, installs dependencies, builds the frontend, runs migrations, and creates the default teacher (`yun` with the password from `PASS_WORD` in `.env` — must change password on first login).

## Manual Start

```bash
# Backend
cd backend
uv sync
cp ../.env.example ../.env       # then edit .env
cp ../configure.json.example ../configure.json
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (dev mode)
cd frontend
npm install
npm run dev                       # serves on http://localhost:5173
```

## Configuration

- **`.env`** — secrets (LLM keys, session secret, etc.). Gitignored. Copy from `.env.example`.
- **`configure.json`** — business configuration (academic calendar, generation defaults, LLM settings, uploads). Gitignored. Copy from `configure.json.example`.

## Layout

```
backend/
  app/
    main.py            FastAPI entry
    config.py          Loads .env + configure.json
    database.py        SQLite + WAL
    security.py        Password hashing + cookies + CSRF
    models/            30+ SQLAlchemy models (extended.py holds PRD §80 entities)
    schemas/           Pydantic schemas
    routes/            REST endpoints (24 routers; ~120 paths)
    services/
      llm/             LangChain agent (12-stage workflow: curriculum,
                         planning, generation, diagram, validation, grading,
                         archive, learning-plan, material analysis, history,
                         bank question, diagnosis)
      job_worker.py    Serial async job worker (PRD §82–83)
      chapter.py       Chapter inference from calendar
      ocr.py           pytesseract + vision model
      svg.py           Diagram generator (SVG / Mermaid)
      rubric.py        Rubric checker
      archive.py       PDF / CSV / ZIP export
      policy.py        Student-specific learning policy (§94)
  alembic/             Migrations (13 revisions, head = extended_entities)
frontend/
  src/
    pages/             19 pages (Login, Dashboard, Students, Materials, ...)
    components/
    api.js             API client
    auth.jsx           Auth context
    styles.css         Visual style
systemd/               systemd unit (study-moniter.service)
scripts/               backup / restore helpers
install.sh             One-shot installer (self-contained)
docker-compose.yml     Production-style multi-process setup
server.sh              start / stop / restart wrapper
configure.json.example
.env.example
```

## Deployment

- `docker-compose.yml` — production-style multi-process setup
- `systemd/study-moniter.service` — systemd unit (path templated, rendered by `scripts/deploy.sh`)
- `deploy/nginx.conf` — reverse-proxy config (uploads, WebSocket, security headers)
- `scripts/deploy.sh` — one-shot installer: systemd + nginx + (optional) Let's Encrypt + smoke test

### Production deploy on a fresh Linux box

```bash
git clone <repo> /opt/study-moniter-system && cd /opt/study-moniter-system
./install.sh                          # venv + deps + migrations + default teacher + frontend build
sudo scripts/deploy.sh                # systemd + nginx (HTTP only)
sudo scripts/deploy.sh learning.example.com   # systemd + nginx + Let's Encrypt
```

Then open the URL shown in the deploy script output and log in with username `yun` and the `PASS_WORD` you set during `install.sh`.

### Maintenance

```bash
sudo systemctl status study-moniter    # backend status
sudo systemctl restart study-moniter
sudo journalctl -u study-moniter -f    # live backend logs
sudo nginx -t && sudo systemctl reload nginx
./scripts/backup.sh                    # DB + uploads snapshot
```

## Default Credentials

- Username: `yun`
- Password: set via `PASS_WORD` in `.env` (install.sh prompts for it on first run)
- The default teacher must change the password on first login.