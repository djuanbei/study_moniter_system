"""Client error reporting endpoint.

The frontend installs a global handler that POSTs JS errors / unhandled
rejections / failed API calls here. Server logs them with the client's
request_id so a single incident can be correlated across both sides.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.deps import get_current_user
from app.models.auth import User


router = APIRouter(prefix="/api/errors", tags=["errors"])
logger = logging.getLogger("sms.client_error")


class ClientErrorIn(BaseModel):
    kind: str = Field(default="js_error", pattern="^(js_error|unhandledrejection|api_failure)$")
    message: str
    stack: Optional[str] = None
    url: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    request_id: Optional[str] = None
    detail: Optional[dict] = None


@router.post("/client", status_code=204)
async def report_client_error(
    payload: ClientErrorIn,
    request: Request,
    _: User = Depends(get_current_user),
):
    logger.warning(
        "client_error: %s",
        payload.message,
        extra={
            "kind": payload.kind,
            "client_url": payload.url,
            "client_line": payload.line,
            "client_column": payload.column,
            "client_request_id": payload.request_id,
            "stack": payload.stack,
            "detail": payload.detail,
            "user_id": _.id if _ else None,
            "ip": request.client.host if request.client else None,
        },
    )
    return None