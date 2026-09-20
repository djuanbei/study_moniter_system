"""Missing PRD §84 endpoint groups.

Provides the explicit top-level routes the PRD §84 list calls for that
are not already mounted by another router:
    /textbooks
    /learning-sessions
    /question-generation      (alias of /questions/generate)
    /similar-questions        (alias of /question-bank/{id}/similar)
    /student-progress         (per-chapter progress + history)
    /audit                    (audit log viewer)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ensure_can_access_student, get_current_user
from app.middleware.audit import record_audit
from app.models.auth import AuditLog, User
from app.models.extended import (
    LearningSession,
    StudentProgressHistory,
)
from app.models.students import Student, StudentProgress
from app.services.job_worker import enqueue
from app.services.question_bank import similar_questions as _similar


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


# ---------------------------------------------------------------------------
# /textbooks  (PRD §18)
# ---------------------------------------------------------------------------

textbooks_router = APIRouter(prefix="/api/textbooks", tags=["textbooks"])


class TextbookIn(BaseModel):
    name: str
    subject: str
    publisher: Optional[str] = None
    description: Optional[str] = None


class TextbookVersionIn(BaseModel):
    textbook_id: int
    label: str
    year: Optional[int] = None
    grade_band: Optional[str] = None
    isbn: Optional[str] = None


class TextbookOut(BaseModel):
    id: int
    name: str
    subject: str
    publisher: Optional[str]
    description: Optional[str]
    versions: list[dict]


class SectionIn(BaseModel):
    textbook_version_id: int
    chapter_id: Optional[int] = None
    parent_section_id: Optional[int] = None
    order: int
    title: str
    summary: Optional[str] = None


class SectionOut(BaseModel):
    id: int
    textbook_version_id: int
    chapter_id: Optional[int]
    parent_section_id: Optional[int]
    order: int
    title: str
    summary: Optional[str]


@textbooks_router.get("", response_model=list[dict])
def list_textbooks(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    _teacher_only(current)
    from app.models.extended import Section, Textbook, TextbookVersion

    rows = db.query(Textbook).order_by(Textbook.name).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "subject": t.subject,
            "publisher": t.publisher,
            "description": t.description,
            "versions": [
                {
                    "id": v.id,
                    "label": v.label,
                    "year": v.year,
                    "grade_band": v.grade_band,
                    "isbn": v.isbn,
                }
                for v in t.versions
            ],
        }
        for t in rows
    ]


@textbooks_router.post("", response_model=dict)
def create_textbook(
    payload: TextbookIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _teacher_only(current)
    from app.models.extended import Textbook

    t = Textbook(
        name=payload.name,
        subject=payload.subject,
        publisher=payload.publisher,
        description=payload.description,
    )
    db.add(t)
    db.flush()
    record_audit(db, action="create_textbook", user=current, request=request,
                 target_type="textbook", target_id=t.id)
    db.commit()
    return {"id": t.id, "name": t.name}


@textbooks_router.post("/versions", response_model=dict)
def create_textbook_version(
    payload: TextbookVersionIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _teacher_only(current)
    from app.models.extended import Textbook, TextbookVersion

    t = db.get(Textbook, payload.textbook_id)
    if not t:
        raise HTTPException(status_code=404, detail="Textbook not found")
    v = TextbookVersion(
        textbook_id=payload.textbook_id,
        label=payload.label,
        year=payload.year,
        grade_band=payload.grade_band,
        isbn=payload.isbn,
    )
    db.add(v)
    db.flush()
    record_audit(db, action="create_textbook_version", user=current, request=request,
                 target_type="textbook_version", target_id=v.id)
    db.commit()
    return {"id": v.id, "textbook_id": v.textbook_id, "label": v.label}


@textbooks_router.get("/sections", response_model=list[dict])
def list_sections(
    textbook_version_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    _teacher_only(current)
    from app.models.extended import Section

    rows = (
        db.query(Section)
        .filter(Section.textbook_version_id == textbook_version_id)
        .order_by(Section.order.asc())
        .all()
    )
    return [
        {
            "id": s.id,
            "textbook_version_id": s.textbook_version_id,
            "chapter_id": s.chapter_id,
            "parent_section_id": s.parent_section_id,
            "order": s.order,
            "title": s.title,
            "summary": s.summary,
        }
        for s in rows
    ]


@textbooks_router.post("/sections", response_model=dict)
def create_section(
    payload: SectionIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _teacher_only(current)
    from app.models.extended import Section

    s = Section(**payload.model_dump())
    db.add(s)
    db.flush()
    record_audit(db, action="create_section", user=current, request=request,
                 target_type="section", target_id=s.id)
    db.commit()
    return {"id": s.id, "title": s.title}


# ---------------------------------------------------------------------------
# /learning-sessions  (PRD §80)
# ---------------------------------------------------------------------------

sessions_router = APIRouter(prefix="/api/learning-sessions", tags=["learning-sessions"])


class LearningSessionIn(BaseModel):
    student_id: int
    plan_item_id: Optional[int] = None
    assignment_id: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    focus: Optional[str] = None
    notes: Optional[str] = None


class LearningSessionOut(BaseModel):
    id: int
    student_id: int
    plan_item_id: Optional[int]
    assignment_id: Optional[int]
    started_at: datetime
    ended_at: Optional[datetime]
    duration_minutes: Optional[int]
    focus: Optional[str]
    notes: Optional[str]


@sessions_router.get("", response_model=list[LearningSessionOut])
def list_sessions(
    student_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LearningSession]:
    ensure_can_access_student(current, student_id)
    return (
        db.query(LearningSession)
        .filter(LearningSession.student_id == student_id)
        .order_by(LearningSession.started_at.desc())
        .limit(limit)
        .all()
    )


@sessions_router.post("", response_model=LearningSessionOut)
def create_session(
    payload: LearningSessionIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningSession:
    ensure_can_access_student(current, payload.student_id)
    s = LearningSession(
        student_id=payload.student_id,
        plan_item_id=payload.plan_item_id,
        assignment_id=payload.assignment_id,
        started_at=payload.started_at or datetime.utcnow(),
        ended_at=payload.ended_at,
        duration_minutes=payload.duration_minutes,
        focus=payload.focus,
        notes=payload.notes,
    )
    db.add(s)
    db.flush()
    record_audit(db, action="create_learning_session", user=current, request=request,
                 target_type="learning_session", target_id=s.id,
                 detail={"student_id": s.student_id})
    db.commit()
    db.refresh(s)
    return s


@sessions_router.post("/{session_id}/end", response_model=LearningSessionOut)
def end_session(
    session_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningSession:
    s = db.get(LearningSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    ensure_can_access_student(current, s.student_id)
    s.ended_at = datetime.utcnow()
    if s.started_at:
        s.duration_minutes = int((s.ended_at - s.started_at).total_seconds() // 60)
    record_audit(db, action="end_learning_session", user=current, request=request,
                 target_type="learning_session", target_id=s.id)
    db.commit()
    db.refresh(s)
    return s


# ---------------------------------------------------------------------------
# /question-generation  (PRD §84 — top-level alias of /questions/generate)
# ---------------------------------------------------------------------------

question_generation_router = APIRouter(
    prefix="/api/question-generation", tags=["question-generation"]
)


@question_generation_router.post("/enqueue")
def enqueue_generation(
    payload: dict,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Async wrapper around /api/questions/generate (PRD §82, §84)."""
    _teacher_only(current)
    if not payload.get("student_id"):
        raise HTTPException(status_code=400, detail="student_id is required")
    job = enqueue(
        db,
        job_type="QUESTION_GENERATION",
        payload=payload,
        user_id=current.id,
    )
    record_audit(db, action="enqueue_question_generation", user=current, request=request,
                 target_type="job", target_id=job.id)
    db.commit()
    return {"job_id": job.id, "status": job.status}


# ---------------------------------------------------------------------------
# /similar-questions  (PRD §41, §84 — top-level alias)
# ---------------------------------------------------------------------------

similar_router = APIRouter(prefix="/api/similar-questions", tags=["similar-questions"])


@similar_router.get("/{question_id}")
def list_similar(
    question_id: int,
    top_k: int = Query(default=5, ge=1, le=20),
    same_kp_only: bool = Query(default=False),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    _teacher_only(current)
    return _similar(db, question_id=question_id, top_k=top_k, same_kp_only=same_kp_only)


# ---------------------------------------------------------------------------
# /student-progress  (PRD §80)
# ---------------------------------------------------------------------------

progress_router = APIRouter(prefix="/api/student-progress", tags=["student-progress"])


class StudentProgressOut(BaseModel):
    id: int
    student_id: int
    chapter_id: Optional[int]
    mastery: float
    last_score: Optional[float]
    last_assessed_at: Optional[datetime]
    notes: Optional[str]


class StudentProgressHistoryOut(BaseModel):
    id: int
    progress_id: int
    mastery: float
    last_score: Optional[float]
    changed_at: datetime
    reason: Optional[str]


@progress_router.get("", response_model=list[StudentProgressOut])
def list_progress(
    student_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StudentProgress]:
    ensure_can_access_student(current, student_id)
    return (
        db.query(StudentProgress)
        .filter(StudentProgress.student_id == student_id)
        .order_by(StudentProgress.chapter_id.asc())
        .all()
    )


@progress_router.get("/{progress_id}/history", response_model=list[StudentProgressHistoryOut])
def progress_history(
    progress_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StudentProgressHistory]:
    p = db.get(StudentProgress, progress_id)
    if not p:
        raise HTTPException(status_code=404, detail="Progress not found")
    ensure_can_access_student(current, p.student_id)
    return (
        db.query(StudentProgressHistory)
        .filter(StudentProgressHistory.progress_id == progress_id)
        .order_by(StudentProgressHistory.changed_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# /audit  (PRD §84)
# ---------------------------------------------------------------------------

audit_router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    target_type: Optional[str]
    target_id: Optional[int]
    ip_address: Optional[str]
    user_agent: Optional[str]
    detail: Optional[dict]
    created_at: datetime


@audit_router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    target_type: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    _teacher_only(current)
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if target_type:
        q = q.filter(AuditLog.target_type == target_type)
    return q.order_by(AuditLog.id.desc()).limit(limit).all()