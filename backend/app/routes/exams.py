"""Online exam routes (PRD §73–76)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ensure_can_access_student, get_current_user
from app.middleware.audit import record_audit
from app.models.assignments import Question
from app.models.auth import User
from app.models.exams import Exam, ExamAttempt
from app.models.students import Student
from app.schemas import (
    ExamAnswerSaveIn,
    ExamAttemptOut,
    ExamConfirmIn,
    ExamCreateIn,
    ExamOut,
    ExamSubmitIn,
)
from app.services.exams import (
    confirm_attempt,
    expire_attempt,
    save_answers,
    start_attempt,
    submit_attempt,
)

router = APIRouter(prefix="/api", tags=["exams"])

# Server-stripped question view for students (§73): no answer_key/rubric.


def _student_question(q: Question) -> dict:
    return {
        "id": q.id,
        "order": q.order,
        "qtype": q.qtype,
        "subject": q.subject,
        "prompt": q.prompt,
        "knowledge_points": list(q.knowledge_points or []),
        "difficulty": q.difficulty,
        "estimated_minutes": q.estimated_minutes,
        "diagram_svg": q.diagram_svg,
        "diagram_format": q.diagram_format,
    }


def _get_exam(db: Session, exam_id: int) -> Exam:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


def _get_attempt(db: Session, attempt_id: int) -> ExamAttempt:
    attempt = db.get(ExamAttempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt


def _exam_questions(db: Session, exam: Exam) -> list[Question]:
    qs = exam.question_set
    return sorted(qs.questions, key=lambda q: q.order) if qs else []


# ---------------------------------------------------------------------------
# Exam management (teacher)
# ---------------------------------------------------------------------------

@router.post("/exams", response_model=ExamOut)
def create_exam(
    payload: ExamCreateIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Exam:
    if current.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    from app.models.assignments import QuestionSet

    qs = db.get(QuestionSet, payload.question_set_id)
    if not qs:
        raise HTTPException(status_code=404, detail="Question set not found")
    exam = Exam(
        title=payload.title.strip()[:128] or "在线考试",
        student_id=student.id,
        question_set_id=qs.id,
        duration_minutes=payload.duration_minutes,
        total_score=payload.total_score,
        created_by=current.id,
    )
    db.add(exam)
    record_audit(db, action="create_exam", user=current, request=request,
                 target_type="exam", detail={"student_id": student.id, "qs": qs.id})
    db.commit()
    db.refresh(exam)
    return exam


@router.get("/exams", response_model=list[ExamOut])
def list_exams(
    student_id: int | None = Query(default=None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Exam]:
    q = db.query(Exam)
    if current.role == "student" and current.student_id:
        q = q.filter(Exam.student_id == current.student_id)
    elif student_id:
        q = q.filter(Exam.student_id == student_id)
    return q.order_by(Exam.id.desc()).limit(50).all()


@router.get("/exams/{exam_id}")
def get_exam(
    exam_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    exam = _get_exam(db, exam_id)
    ensure_can_access_student(current, exam.student_id)
    questions = _exam_questions(db, exam)
    attempts = (
        db.query(ExamAttempt)
        .filter(ExamAttempt.exam_id == exam.id)
        .order_by(ExamAttempt.id.desc())
        .all()
    )
    from app.schemas import ExamAttemptOut

    return {
        "exam": ExamOut.model_validate(exam).model_dump(),
        "questions": [
            (_full_question(q) if current.role == "teacher" else _student_question(q))
            for q in questions
        ],
        "attempts": [ExamAttemptOut.model_validate(a).model_dump() for a in attempts],
    }


def _full_question(q: Question) -> dict:
    return {
        "id": q.id, "order": q.order, "qtype": q.qtype, "subject": q.subject,
        "prompt": q.prompt, "knowledge_points": list(q.knowledge_points or []),
        "difficulty": q.difficulty, "estimated_minutes": q.estimated_minutes,
        "diagram_svg": q.diagram_svg, "diagram_format": q.diagram_format,
        "answer_key": q.answer_key, "rubric": q.rubric,
    }


# ---------------------------------------------------------------------------
# Student attempt flow (§74–76)
# ---------------------------------------------------------------------------

@router.post("/exam-attempts/start", response_model=ExamAttemptOut)
def start(
    exam_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExamAttempt:
    exam = _get_exam(db, exam_id)
    student_id = current.student_id if current.role == "student" else exam.student_id
    if current.role == "student" and current.student_id != exam.student_id:
        raise HTTPException(status_code=403, detail="Access denied")
    attempt = start_attempt(db, exam, student_id)
    record_audit(db, action="start_exam_attempt", user=current, request=request,
                 target_type="exam_attempt", target_id=attempt.id)
    db.commit()
    db.refresh(attempt)
    return attempt


@router.get("/exam-attempts", response_model=list[ExamAttemptOut])
def list_attempts(
    student_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ExamAttempt]:
    ensure_can_access_student(current, student_id)
    return (
        db.query(ExamAttempt)
        .filter(ExamAttempt.student_id == student_id)
        .order_by(ExamAttempt.id.desc())
        .limit(50)
        .all()
    )


@router.get("/exam-attempts/{attempt_id}", response_model=ExamAttemptOut)
def get_attempt(
    attempt_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExamAttempt:
    attempt = _get_attempt(db, attempt_id)
    ensure_can_access_student(current, attempt.student_id)
    # Lazy expiry on read (§74): past deadline while IN_PROGRESS → TIME_EXPIRED
    from datetime import datetime

    if attempt.status == "IN_PROGRESS" and datetime.utcnow() > attempt.deadline:
        expire_attempt(db, attempt, datetime.utcnow())
        db.commit()
        db.refresh(attempt)
    return attempt


@router.get("/exam-attempts/{attempt_id}/detail")
def get_attempt_detail(
    attempt_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Attempt + exam questions; answers included only for the owner/parent."""
    attempt = _get_attempt(db, attempt_id)
    ensure_can_access_student(current, attempt.student_id)
    exam = _get_exam(db, attempt.exam_id)
    questions = _exam_questions(db, exam)
    from app.schemas import ExamAttemptOut

    return {
        "attempt": ExamAttemptOut.model_validate(attempt).model_dump(),
        "exam": ExamOut.model_validate(exam).model_dump(),
        "questions": [
            _full_question(q) if current.role == "teacher" else _student_question(q)
            for q in questions
        ],
    }


@router.put("/exam-attempts/{attempt_id}/save", response_model=ExamAttemptOut)
def save(
    attempt_id: int,
    payload: ExamAnswerSaveIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExamAttempt:
    attempt = _get_attempt(db, attempt_id)
    ensure_can_access_student(current, attempt.student_id)
    from datetime import datetime

    try:
        attempt = save_answers(db, attempt, payload.answers)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(attempt)
    return attempt


@router.post("/exam-attempts/{attempt_id}/submit", response_model=ExamAttemptOut)
def submit(
    attempt_id: int,
    payload: ExamSubmitIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExamAttempt:
    attempt = _get_attempt(db, attempt_id)
    ensure_can_access_student(current, attempt.student_id)
    from datetime import datetime

    if attempt.status == "IN_PROGRESS" and datetime.utcnow() > attempt.deadline:
        expire_attempt(db, attempt, datetime.utcnow())
        db.commit()
        db.refresh(attempt)
        return attempt
    try:
        attempt = submit_attempt(db, attempt, reason=payload.reason)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(db, action="submit_exam", user=current, request=request,
                 target_type="exam_attempt", target_id=attempt.id,
                 detail={"reason": attempt.submit_reason})
    db.commit()
    db.refresh(attempt)
    return attempt


# ---------------------------------------------------------------------------
# Parent confirmation (§49: AI/auto suggestion -> parent -> official)
# ---------------------------------------------------------------------------

@router.post("/exam-attempts/{attempt_id}/confirm", response_model=ExamAttemptOut)
def confirm(
    attempt_id: int,
    payload: ExamConfirmIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExamAttempt:
    if current.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")
    attempt = _get_attempt(db, attempt_id)
    try:
        attempt = confirm_attempt(
            db,
            attempt,
            final_score=payload.final_score,
            feedback=payload.feedback,
            per_question=payload.per_question,
            user=current,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(db, action="confirm_exam", user=current, request=request,
                 target_type="exam_attempt", target_id=attempt.id,
                 detail={"final_score": payload.final_score})
    db.commit()
    db.refresh(attempt)
    return attempt
