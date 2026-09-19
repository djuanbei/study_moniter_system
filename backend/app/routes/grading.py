"""Grading routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ensure_can_access_student, get_current_user
from app.middleware.audit import record_audit
from app.models.assignments import Assignment, Grading, QuestionSet, Submission
from app.models.auth import User
from app.models.students import Student
from app.schemas import GradingConfirmIn, GradingOut
# Note: stage_grading is imported lazily inside the route handler to allow the
# app to boot even when langchain-core is not installed.


router = APIRouter(prefix="/api/grading", tags=["grading"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


@router.get("", response_model=list[GradingOut])
def list_gradings(
    submission_id: int | None = None,
    confirmed_only: bool = False,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Grading]:
    q = db.query(Grading)
    if submission_id:
        q = q.filter(Grading.submission_id == submission_id)
    if confirmed_only:
        q = q.filter(Grading.confirmed == True)  # noqa: E712
    return q.order_by(Grading.created_at.desc()).all()


@router.post("/suggest", response_model=GradingOut)
def suggest(
    submission_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Grading:
    _teacher_only(current)
    sub = db.get(Submission, submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    assignment = db.get(Assignment, sub.assignment_id)
    qs = db.get(QuestionSet, assignment.question_set_id)

    from app.services.llm import stage_grading  # lazy: needs langchain
    from app.services.learning import grading_triage  # deterministic triage

    advisory = stage_grading(db, submission=sub, question_set=qs, user=current)

    grading = (
        db.query(Grading).filter(Grading.submission_id == sub.id).order_by(Grading.id.desc()).first()
    )
    if grading is None:
        grading = Grading(submission_id=sub.id, grader_id=current.id)
        db.add(grading)
    grading.llm_suggested_score = advisory.get("suggested_score")
    grading.llm_suggested_feedback = advisory.get("feedback")
    grading.llm_knowledge_mastery = advisory.get("knowledge_mastery")
    grading.per_question_scores = advisory.get("per_question")

    # PRD §47–48: high-confidence objective answers can be auto-suggested,
    # low-confidence / open-ended questions require parent review.
    per_question = advisory.get("per_question") or []
    qtypes = [q.qtype for q in qs.questions]
    confidence, needs_review = grading_triage(per_question, qtypes)
    grading.llm_confidence = confidence
    grading.needs_review = needs_review
    record_audit(db, action="llm_suggest_grading", user=current, request=request, target_type="submission", target_id=sub.id)
    db.commit()
    db.refresh(grading)
    return grading


@router.post("/confirm", response_model=GradingOut)
def confirm(
    payload: GradingConfirmIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Grading:
    _teacher_only(current)
    sub = db.get(Submission, payload.submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    grading = (
        db.query(Grading).filter(Grading.submission_id == sub.id).order_by(Grading.id.desc()).first()
    )
    if grading is None:
        grading = Grading(submission_id=sub.id, grader_id=current.id)
        db.add(grading)
    grading.grader_id = current.id
    grading.final_score = payload.final_score
    grading.feedback = payload.feedback
    grading.per_question_scores = payload.per_question_scores or grading.per_question_scores
    grading.confirmed = True
    grading.confirmed_at = datetime.utcnow()

    # Write back to student score_history
    student = db.get(Student, sub.student_id)
    if student:
        history = list(student.score_history or [])
        history.append(
            {
                "date": grading.confirmed_at.isoformat(),
                "score": payload.final_score,
                "assignment_id": sub.assignment_id,
                "submission_id": sub.id,
            }
        )
        student.score_history = history

    # Mark assignment complete
    assignment = db.get(Assignment, sub.assignment_id)
    if assignment:
        assignment.status = "graded"

    # PRD §49, §56, §59: parent-confirmed grading becomes official learning
    # evidence and updates the student knowledge state (the core loop).
    if student:
        from app.services.learning import record_evidence_for_submission

        created = record_evidence_for_submission(
            db, submission=sub, grading=grading, student=student, observed_by=current.id
        )
    else:
        created = 0

    record_audit(
        db,
        action="confirm_grading",
        user=current,
        request=request,
        target_type="submission",
        target_id=sub.id,
        detail={"final_score": payload.final_score, "evidence_created": created},
    )
    db.commit()
    db.refresh(grading)
    return grading


@router.get("/by-submission/{submission_id}", response_model=list[GradingOut])
def by_submission(submission_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Grading]:
    sub = db.get(Submission, submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    ensure_can_access_student(current, sub.student_id)
    return (
        db.query(Grading)
        .filter(Grading.submission_id == submission_id)
        .order_by(Grading.created_at.desc())
        .all()
    )