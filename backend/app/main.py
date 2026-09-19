"""FastAPI application entry point.

Wires middleware (request logging + CSRF), routes, and serves the built
frontend as static files when present. Logging is configured via
`app.logging_config` so every log line carries the request_id and key
context (user, ip, duration, status).
"""

from __future__ import annotations

import logging
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    PROJECT_ROOT,
    ensure_runtime_dirs,
    get_business_config,
    get_settings,
)
from app.database import init_db
from app.logging_config import (
    current_request_id,
    current_user_id,
    setup_logging,
)
from app.middleware import CSRFMiddleware, RequestLoggingMiddleware
from app.routes import (
    accounts,
    archive,
    assignments,
    auth,
    chapters,
    classes,
    dashboard,
    errors,
    exams,
    exports,
    grading,
    historical,
    jobs,
    learning,
    materials,
    questions,
    question_bank,
    settings as settings_router,
    students,
    submissions,
)
from app.services.job_worker import start_worker, stop_worker


settings = get_settings()
ensure_runtime_dirs()
setup_logging(
    level=settings.log_level,
    log_file=settings.log_file or None,
    fmt=settings.log_format,
)
logger = logging.getLogger("sms")

init_db()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # PRD §82–83: one serial job worker per process (heavy jobs off the
    # request path). Disable with JOBS_WORKER_ENABLED=false on secondary
    # workers if needed.
    if os.environ.get("JOBS_WORKER_ENABLED", "true").lower() != "false":
        poll = float(
            (get_business_config().get("jobs") or {}).get("poll_seconds", 2.0)
        )
        start_worker(poll_seconds=poll)
    yield
    stop_worker()


app = FastAPI(
    title="学习陪伴系统 / Learning Companion System",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(CSRFMiddleware)
app.add_middleware(RequestLoggingMiddleware)
# CORS added last = outermost, so error responses (e.g. CSRF 403) still get
# CORS headers in the dev cross-origin setup.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        settings.csrf_header_name,
        "X-Request-ID",
    ],
)

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(students.router)
app.include_router(classes.router)
app.include_router(chapters.router)
app.include_router(assignments.router)
app.include_router(questions.router)
app.include_router(submissions.router)
app.include_router(grading.router)
app.include_router(learning.router)
app.include_router(exports.router)
app.include_router(materials.router)
app.include_router(historical.router)
app.include_router(jobs.router)
app.include_router(exams.router)
app.include_router(question_bank.router)
app.include_router(archive.router)
app.include_router(settings_router.router)
app.include_router(dashboard.router)
app.include_router(errors.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Capture full traceback + request context, then return a clean 500.

    The middleware logs the request line; this handler logs the failure
    itself with the same request_id so the two events can be tied together.
    """
    rid = (
        current_request_id()
        or request.headers.get("X-Request-ID")
        or ""
    )
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error(
        "unhandled_exception: %s",
        exc,
        extra={
            "http_method": request.method,
            "http_path": request.url.path,
            "http_query": str(request.url.query) or None,
            "client_ip": request.client.host if request.client else None,
            "exception_type": type(exc).__name__,
            "exception_module": type(exc).__module__,
        },
    )
    logger.error("traceback:\n%s", tb)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
            "request_id": rid or None,
        },
        headers={"X-Request-ID": rid},
    )


# --- Static frontend (built by `npm run build`) ------------------------------

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    def root_index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = Path(full_path)
        # Path traversal guard: reject absolute paths ("//etc/passwd") and
        # dot segments; enforce containment after resolving symlinks/.. .
        if candidate.is_absolute() or ".." in candidate.parts:
            return FileResponse(FRONTEND_DIST / "index.html")
        try:
            target = (FRONTEND_DIST / candidate).resolve()
            target.relative_to(FRONTEND_DIST.resolve())
        except (ValueError, OSError):
            return FileResponse(FRONTEND_DIST / "index.html")
        if target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
else:

    @app.get("/")
    def root_index_dev() -> dict:
        return {
            "message": "学习陪伴系统 backend is running. Build the frontend (cd frontend && npm run build) or run the dev server (npm run dev) on :5173.",
            "docs": "/api/docs",
            "health": "/api/health",
        }


if __name__ == "__main__":
    import uvicorn

    from app.config import get_server_bind

    host, port = get_server_bind()
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
    )
