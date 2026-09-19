"""Per-request logging middleware.

Generates a request_id, binds it to the current context so every log line
carries it, logs request completion with method/path/status/duration/user,
and emits an `X-Request-ID` response header for client correlation.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import bind_request_id, reset_request_id


logger = logging.getLogger("sms.request")
SKIP_PATHS = {"/api/health", "/api/auth/bootstrap"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Honor a client-provided request id (e.g. from frontend logger)
        # so a single failure can be correlated across client + server.
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        rid_token, uid_token = bind_request_id(request_id, user_id=None)

        # We can't reliably resolve the user before the dependency runs,
        # so we leave user_id to be filled in later if needed (the audit
        # helper handles its own commit). For the access log we use the
        # session cookie to peek at user_id without DB lookup.
        user_id = _peek_user_id(request)
        from app.logging_config import _user_id_var

        try:
            _user_id_var.set(user_id)
        except Exception:
            pass

        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception("Unhandled exception during %s %s", request.method, request.url.path)
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            if request.url.path not in SKIP_PATHS:
                logger.info(
                    "request",
                    extra={
                        "http_method": request.method,
                        "http_path": request.url.path,
                        "http_query": str(request.url.query) or None,
                        "http_status": status,
                        "duration_ms": duration_ms,
                        "client_ip": request.client.host if request.client else None,
                        "user_agent": request.headers.get("user-agent"),
                    },
                )
            reset_request_id(rid_token, uid_token)


def _peek_user_id(request: Request) -> Optional[int]:
    """Best-effort user_id from the session cookie without DB hit."""
    try:
        from app.config import get_settings
        from app.security import read_session_token

        token = request.cookies.get(get_settings().session_cookie_name)
        if not token:
            return None
        payload = read_session_token(token)
        return payload.get("uid") if payload else None
    except Exception:
        return None