"""Historical assessment import routes (PRD §54–55, §77)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ensure_can_access_student, get_current_user
from app.middleware.audit import record_audit
from app.models.auth import User
from app.models.historical import HistoricalAssessment
from app.models.materials import Material
from app.models.students import Student
from app.schemas import (
    HistoricalAssessmentOut,
    HistoryAnalyzeIn,
    HistoryConfirmIn,
)
from app.services.historical_import import analyze_history, confirm_history

router = APIRouter(prefix="/api/historical", tags=["historical"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


@router.post("/analyze", response_model=HistoricalAssessmentOut)
def analyze(
    payload: HistoryAnalyzeIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoricalAssessment:
    _teacher_only(current)
    material = db.get(Material, payload.material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    try:
        assessment = analyze_history(
            db,
            material=material,
            student_id=student.id,
            exam_title=payload.exam_title,
            exam_date=payload.exam_date,
            user=current,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=502, detail=f"历史试卷识别失败: {exc}") from exc
    record_audit(
        db, action="analyze_history", user=current, request=request,
        target_type="historical_assessment", target_id=assessment.id,
        detail={"material_id": material.id, "student_id": student.id},
    )
    db.commit()
    db.refresh(assessment)
    return assessment


@router.get("", response_model=list[HistoricalAssessmentOut])
def list_assessments(
    student_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HistoricalAssessment]:
    ensure_can_access_student(current, student_id)
    return (
        db.query(HistoricalAssessment)
        .filter(HistoricalAssessment.student_id == student_id)
        .order_by(HistoricalAssessment.id.desc())
        .limit(50)
        .all()
    )


@router.get("/{assessment_id}", response_model=HistoricalAssessmentOut)
def get_assessment(
    assessment_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoricalAssessment:
    _teacher_only(current)
    assessment = db.get(HistoricalAssessment, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


@router.post("/{assessment_id}/confirm", response_model=HistoricalAssessmentOut)
def confirm(
    assessment_id: int,
    payload: HistoryConfirmIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoricalAssessment:
    """Parent review boundary (PRD §57): confirmed items become evidence."""
    _teacher_only(current)
    assessment = db.get(HistoricalAssessment, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    result = confirm_history(db, assessment, item_payloads=[i.model_dump() for i in payload.items], user=current)
    record_audit(
        db, action="confirm_history", user=current, request=request,
        target_type="historical_assessment", target_id=assessment.id, detail=result,
    )
    db.commit()
    db.refresh(assessment)
    return assessment


@router.delete("/{assessment_id}")
def delete_assessment(
    assessment_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _teacher_only(current)
    assessment = db.get(HistoricalAssessment, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    db.delete(assessment)
    record_audit(
        db, action="delete_history", user=current, request=request,
        target_type="historical_assessment", target_id=assessment_id,
    )
    db.commit()
    return {"ok": True}
