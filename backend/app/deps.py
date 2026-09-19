"""FastAPI dependencies: session resolution, RBAC."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.auth import User
from app.security import (
    CREDENTIALS_EXC,
    read_session_token,
)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Resolve the current user from the HttpOnly session cookie."""
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise CREDENTIALS_EXC
    payload = read_session_token(token)
    if not payload:
        raise CREDENTIALS_EXC
    user = db.get(User, payload.get("uid"))
    if not user or not user.is_active:
        raise CREDENTIALS_EXC
    return user


def require_teacher(user: User = Depends(get_current_user)) -> User:
    if user.role != "teacher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher role required")
    return user


def require_role(*roles: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {','.join(roles)} required",
            )
        return user

    return _dep


def optional_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    payload = read_session_token(token)
    if not payload:
        return None
    return db.get(User, payload.get("uid"))


def ensure_can_access_student(user: User, student_id: int) -> None:
    """A student can only see their own data; teachers can see everything."""
    if user.role == "teacher":
        return
    if user.role == "student" and user.student_id == student_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")