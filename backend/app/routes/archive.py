"""Archive export routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ensure_can_access_student, get_current_user
from app.middleware.audit import record_audit
from app.models.auth import User
from app.models.students import Student
from app.services.archive import images_zip, student_csv, student_pdf


router = APIRouter(prefix="/api/archive", tags=["archive"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


@router.get("/students/{student_id}/csv")
def csv_export(student_id: int, request: Request, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_can_access_student(current, student_id)
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    record_audit(db, action="export_csv", user=current, request=request, target_type="student", target_id=student_id)
    db.commit()
    return Response(
        content=student_csv(db, student),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="student_{student_id}.csv"'},
    )


@router.get("/students/{student_id}/pdf")
def pdf_export(student_id: int, request: Request, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_can_access_student(current, student_id)
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    record_audit(db, action="export_pdf", user=current, request=request, target_type="student", target_id=student_id)
    db.commit()
    return Response(
        content=student_pdf(db, student),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="student_{student_id}.pdf"'},
    )


@router.get("/students/{student_id}/images.zip")
def images_export(student_id: int, request: Request, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_can_access_student(current, student_id)
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    record_audit(db, action="export_images_zip", user=current, request=request, target_type="student", target_id=student_id)
    db.commit()
    return Response(
        content=images_zip(db, student),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="student_{student_id}_images.zip"'},
    )