"""Export + report routes (PRD §65, §78)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ensure_can_access_student, get_current_user
from app.middleware.audit import record_audit
from app.models.assignments import QuestionSet
from app.models.auth import User
from app.models.students import Student
from app.services.docx_export import question_set_docx
from app.services.paper import question_set_pdf
from app.services.reports import learning_report

router = APIRouter(prefix="/api", tags=["exports"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


@router.get("/exports/question-sets/{set_id}/pdf")
def export_paper(
    request: Request,
    set_id: int,
    variant: str = Query(default="student", pattern="^(student|answer|rubric)$"),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Printable exam paper (PRD §78): student / answer / rubric versions."""
    _teacher_only(current)
    qs = db.get(QuestionSet, set_id)
    if not qs:
        raise HTTPException(status_code=404, detail="Question set not found")
    try:
        pdf = question_set_pdf(db, qs, variant)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(
        db, action="export_paper", user=current, request=request,
        target_type="question_set", target_id=set_id, detail={"variant": variant},
    )
    db.commit()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="paper-{set_id}-{variant}.pdf"'},
    )


@router.get("/exports/question-sets/{set_id}/docx")
def export_paper_docx(
    request: Request,
    set_id: int,
    variant: str = Query(default="student", pattern="^(student|answer|rubric)$"),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Editable DOCX paper (PRD §79) — parents can hand-modify."""
    _teacher_only(current)
    qs = db.get(QuestionSet, set_id)
    if not qs:
        raise HTTPException(status_code=404, detail="Question set not found")
    try:
        blob = question_set_docx(db, qs, variant)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(
        db, action="export_paper_docx", user=current, request=request,
        target_type="question_set", target_id=set_id, detail={"variant": variant},
    )
    db.commit()
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="paper-{set_id}-{variant}.docx"'},
    )


@router.get("/reports/learning/{student_id}")
def learning_report_endpoint(
    student_id: int,
    days: int = Query(default=7, ge=1, le=365),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Daily / weekly / monthly learning report (PRD §65–66)."""
    ensure_can_access_student(current, student_id)
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return learning_report(db, student, days=days)
