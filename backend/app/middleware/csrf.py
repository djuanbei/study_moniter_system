"""CSRF middleware: double-submit cookie pattern.

GET / HEAD / OPTIONS are exempt. For unsafe methods, the `X-CSRF-Token` header
must equal the value of the `sms_csrf` cookie. The cookie is HttpOnly=false so
JS can echo it.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.security import constant_time_compare, issue_csrf_token, set_csrf_cookie


EXEMPT_METHODS = {"GET", "HEAD", "OPTIONS"}
EXEMPT_PATHS = {"/api/auth/login", "/api/health", "/api/auth/bootstrap"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        path = request.url.path

        # Issue / refresh cookie on safe requests
        if request.method in EXEMPT_METHODS:
            response = await call_next(request)
            token = request.cookies.get(settings.csrf_cookie_name)
            if not token:
                set_csrf_cookie(response, issue_csrf_token(session_id=request.cookies.get(
                    settings.session_cookie_name, "anon")))
            return response

        if path in EXEMPT_PATHS or not path.startswith("/api"):
            return await call_next(request)

        cookie_token = request.cookies.get(settings.csrf_cookie_name)
        header_token = request.headers.get(settings.csrf_header_name)
        if not cookie_token or not header_token or not constant_time_compare(cookie_token, header_token):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "CSRF token missing or invalid"},
            )

        return await call_next(request)