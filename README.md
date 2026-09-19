# 学习陪伴系统 (Learning Companion System)

A web-based learning companion system that helps teachers generate assignments, grade student submissions, and track each student's academic progress through an LLM-assisted workflow.

See `main_task.md` for the full system specification.

## Stack

- **Backend:** Python 3.11+ · FastAPI · SQLAlchemy · Alembic · SQLite (WAL)
- **Frontend:** React 18 · Vite · React Router
- **LLM:** LangChain agent framework (OpenAI / Anthropic)
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
    models/            14 SQLAlchemy models
    schemas/           Pydantic schemas
    routes/            REST endpoints
    services/
      llm/             LangChain agent (7-stage workflow)
      chapter.py       Chapter inference from calendar
      ocr.py           pytesseract + vision model
      svg.py           Diagram generator
      rubric.py        Rubric checker
      archive.py       PDF/CSV/ZIP export
  alembic/             Migrations
frontend/
  src/
    pages/             10 pages (Login, Dashboard, Students, ...)
    components/
    api.js             API client
    auth.jsx           Auth context
    styles.css         Visual style
systemd/               systemd unit
scripts/               backup / restore helpers
install.sh             One-shot installer
configure.json.example
.env.example
```

## Deployment

- `docker-compose.yml` — production-style multi-process setup
- `systemd/study-moniter.service` — example systemd unit

## Default Credentials

- Username: `yun`
- Password: set via `PASS_WORD` in `.env` (install.sh prompts for it on first run)
- The default teacher must change the password on first login.