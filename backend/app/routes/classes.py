"""Class CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.middleware.audit import record_audit
from app.models.auth import User
from app.models.students import Class
from app.schemas import ClassIn, ClassOut


router = APIRouter(prefix="/api/classes", tags=["classes"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


@router.get("", response_model=list[ClassOut])
def list_classes(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Class]:
    return db.query(Class).order_by(Class.id).all()


@router.post("", response_model=ClassOut)
def create_class(
    payload: ClassIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Class:
    _teacher_only(current)
    if db.query(Class).filter(Class.name == payload.name).first():
        raise HTTPException(status_code=400, detail="Class name already exists")
    cls = Class(**payload.model_dump())
    db.add(cls)
    record_audit(db, action="create_class", user=current, request=request, target_type="class")
    db.commit()
    db.refresh(cls)
    return cls


@router.patch("/{class_id}", response_model=ClassOut)
def update_class(
    class_id: int,
    payload: ClassIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Class:
    _teacher_only(current)
    cls = db.get(Class, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    for k, v in payload.model_dump().items():
        setattr(cls, k, v)
    record_audit(db, action="update_class", user=current, request=request, target_type="class", target_id=cls.id)
    db.commit()
    db.refresh(cls)
    return cls


@router.delete("/{class_id}")
def delete_class(
    class_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _teacher_only(current)
    cls = db.get(Class, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    db.delete(cls)
    record_audit(db, action="delete_class", user=current, request=request, target_type="class", target_id=class_id)
    db.commit()
    return {"ok": True}