"""FastAPI application entry point.

Wires middleware (request logging + CSRF), routes, and serves the built
frontend as static files when present. Logging is configured via
`app.logging_config` so every log line carries the request_id and key
context (user, ip, duration, status).
"""

from __future__ import annotations

import logging
import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import PROJECT_ROOT, ensure_runtime_dirs, get_settings
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
    grading,
    learning,
    questions,
    settings as settings_router,
    students,
    submissions,
)


settings = get_settings()
ensure_runtime_dirs()
setup_logging(
    level=settings.log_level,
    log_file=settings.log_file or None,
    fmt=settings.log_format,
)
logger = logging.getLogger("sms")

init_db()

app = FastAPI(
    title="学习陪伴系统 / Learning Companion System",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

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
app.add_middleware(CSRFMiddleware)
app.add_middleware(RequestLoggingMiddleware)

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
        target = FRONTEND_DIST / full_path
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

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
