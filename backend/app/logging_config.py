"""Unified logging configuration.

Provides:
  - JSON log formatter with request_id propagation via contextvar
  - `setup_logging()` to configure root logger
  - `bind_request_id()` / `current_request_id()` helpers
  - Optional file handler in addition to stdout

Format (JSON):
  {"ts": "...", "level": "INFO", "logger": "...",
   "msg": "...", "request_id": "...", "user_id": int|null,
   "exception": "traceback" if any}
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import time
import traceback
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_user_id_var: ContextVar[Optional[int]] = ContextVar("user_id", default=None)


def bind_request_id(request_id: Optional[str], user_id: Optional[int] = None) -> Any:
    """Bind request_id + user_id to the current async context; returns reset tokens."""
    rid_token = _request_id_var.set(request_id)
    uid_token = _user_id_var.set(user_id)
    return rid_token, uid_token


def reset_request_id(rid_token: Any, uid_token: Any) -> None:
    _request_id_var.reset(rid_token)
    _user_id_var.reset(uid_token)


def current_request_id() -> Optional[str]:
    return _request_id_var.get()


def current_user_id() -> Optional[int]:
    return _user_id_var.get()


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    DEFAULT_FIELDS = {
        "name", "levelname", "levelno", "pathname", "lineno",
        "funcName", "msg", "args", "exc_info", "created",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": _request_id_var.get(),
            "user_id": _user_id_var.get(),
        }
        # Custom fields via `extra=`
        for k, v in record.__dict__.items():
            if k in self.DEFAULT_FIELDS or k.startswith("_"):
                continue
            if k in payload:
                continue
            try:
                json.dumps(v)
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = repr(v)
        if record.exc_info:
            payload["exception"] = "".join(
                traceback.format_exception(*record.exc_info)
            ).rstrip()
        if record.stack_info:
            payload["stack"] = record.stack_info
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Human-friendly format with request_id prefix."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.utcfromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        rid = _request_id_var.get()
        prefix = f"[{rid[:8]}] " if rid else ""
        base = f"{ts} {record.levelname:<5} {prefix}{record.name}: {record.getMessage()}"
        if record.exc_info:
            base += "\n" + "".join(traceback.format_exception(*record.exc_info)).rstrip()
        return base


_configured = False


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    fmt: str = "text",
) -> None:
    """Configure the root logger. Idempotent."""
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    # Clear any existing handlers (e.g. uvicorn's default).
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(stream=sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())

    if log_file:
        path = Path(log_file)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
        root.addHandler(file_handler)

    # Tame noisy libraries.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _configured = True