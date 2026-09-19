"""Route helpers: bootstrap, role checks, audit shortcuts."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, Request, status

from app.config import get_business_config, resolve_path
from app.security import sha256_of_bytes


logger = logging.getLogger(__name__)


def require_teacher_role(user) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher role required")


def ensure_default_teacher_exists(db, settings) -> bool:
    """Returns True if a default teacher was created.

    Reads the initial password from `settings.pass_word` (populated by
    `get_settings()` from `PASS_WORD` in the environment / `.env`).
    If missing, the function refuses to create the user; install.sh is
    responsible for ensuring `PASS_WORD` is set.
    """
    from app.models.auth import User
    from app.security import hash_password

    cfg = get_business_config()
    default = (cfg.get("app") or {}).get("default_teacher") or {}
    username = default.get("username", "yun")
    if db.query(User).filter(User.username == username).first():
        return False
    initial_password = settings.pass_word or ""
    if not initial_password:
        raise RuntimeError(
            "PASS_WORD is not set. Run ./install.sh or set PASS_WORD in .env first."
        )
    if len(initial_password) < 8:
        raise RuntimeError("PASS_WORD must be at least 8 characters long.")
    user = User(
        username=username,
        password_hash=hash_password(initial_password),
        role="teacher",
        display_name=default.get("display_name", username),
        must_change_password=default.get("must_change_password", True),
        is_active=True,
    )
    db.add(user)
    db.commit()
    logger.info("Created default teacher '%s'", username)
    return True


def safe_join_uploads(*parts: str) -> Path:
    """Sanitize a relative path under the uploads directory.

    Resolves ``..`` segments and rejects paths that escape the base via
    sibling directories (e.g. ``uploads_evil`` when base is ``uploads``).
    """
    base = resolve_path("uploads").resolve()
    candidate = base.joinpath(*parts).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path") from None
    return candidate


def sha256_bytes(data: bytes) -> str:
    return sha256_of_bytes(data)


def now() -> datetime:
    return datetime.utcnow()