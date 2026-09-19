"""Authentication routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.middleware.audit import record_audit
from app.models.auth import User
from app.routes._helpers import ensure_default_teacher_exists
from app.schemas import BootstrapOut, ChangePasswordIn, LoginIn
from app.security import (
    clear_session_cookie,
    issue_csrf_token,
    issue_session_token,
    read_session_token,
    set_csrf_cookie,
    set_session_cookie,
    verify_password,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/bootstrap")
def bootstrap(request: Request, response: Response, db: Session = Depends(get_db)) -> BootstrapOut:
    """Bootstrap endpoint: ensure default teacher exists and return CSRF token + user."""
    ensure_default_teacher_exists(db, get_settings())

    settings = get_settings()
    user: User | None = None
    must_change = False
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        payload = read_session_token(token)
        if payload:
            user = db.get(User, payload.get("uid"))
            if user and user.is_active:
                must_change = user.must_change_password

    csrf_token = issue_csrf_token(session_id=token or "anon")
    set_csrf_cookie(response, csrf_token)

    return BootstrapOut(
        csrf_token=csrf_token,
        user={"id": user.id, "username": user.username, "role": user.role} if user else None,
        must_change_password=must_change,
    )


@router.post("/login")
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    settings = get_settings()
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        record_audit(db, action="login_failed", request=request, detail={"username": payload.username})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = issue_session_token(user.id, user.role, {"must_change": user.must_change_password})
    set_session_cookie(response, token)
    user.last_login_at = datetime.utcnow()
    record_audit(db, action="login", user=user, request=request)
    db.commit()

    csrf_token = issue_csrf_token(session_id=token)
    set_csrf_cookie(response, csrf_token)

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "must_change_password": user.must_change_password,
        "csrf_token": csrf_token,
    }


@router.post("/logout")
def logout(request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record_audit(db, action="logout", user=user, request=request)
    db.commit()
    clear_session_cookie(response)
    return {"ok": True}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    from app.security import hash_password

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    record_audit(db, action="change_password", user=user, request=request)
    db.commit()
    return {"ok": True}