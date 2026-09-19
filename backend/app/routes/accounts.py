"""Account management routes (teacher only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.middleware.audit import record_audit
from app.models.auth import User
from app.schemas import PasswordResetIn, UserCreateIn, UserOut, UserUpdateIn
from app.security import hash_password


router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher role required")


@router.get("", response_model=list[UserOut])
def list_users(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[User]:
    _teacher_only(current)
    return db.query(User).order_by(User.id).all()


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreateIn,
    request: Request,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    current = _
    _teacher_only(current)
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    if payload.student_id and db.query(User).filter(User.student_id == payload.student_id).first():
        raise HTTPException(status_code=400, detail="该学生已绑定登录账号")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        display_name=payload.display_name,
        student_id=payload.student_id,
        is_active=True,
        must_change_password=True,
    )
    db.add(user)
    record_audit(db, action="create_user", user=current, request=request, target_type="user", detail={"username": payload.username})
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdateIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    _teacher_only(current)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = payload.model_dump(exclude_none=True)
    for k, v in data.items():
        setattr(user, k, v)
    record_audit(db, action="update_user", user=current, request=request, target_type="user", target_id=user.id, detail=data)
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/disable", response_model=UserOut)
def disable_user(
    user_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    _teacher_only(current)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    record_audit(db, action="disable_user", user=current, request=request, target_type="user", target_id=user.id)
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/enable", response_model=UserOut)
def enable_user(
    user_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    _teacher_only(current)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    record_audit(db, action="enable_user", user=current, request=request, target_type="user", target_id=user.id)
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=UserOut)
def reset_password(
    user_id: int,
    payload: PasswordResetIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    _teacher_only(current)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = True
    record_audit(db, action="reset_password", user=current, request=request, target_type="user", target_id=user.id)
    db.commit()
    db.refresh(user)
    return user