"""Dashboard summary endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.assignments import Assignment, Grading, Submission
from app.models.auth import User
from app.models.students import Student
from app.models.system import LLMRun
from app.schemas import DashboardStats


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class StudentDashboardStats(BaseModel):
    pending_assignments: int
    submitted_assignments: int
    graded_assignments: int
    average_score: float
    recent_grades: list[dict]


@router.get("", response_model=DashboardStats)
def stats(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DashboardStats:
    return DashboardStats(
        student_count=db.query(func.count(Student.id)).scalar() or 0,
        active_assignment_count=db.query(func.count(Assignment.id))
        .filter(Assignment.status.in_(["assigned", "in_progress"]))
        .scalar()
        or 0,
        pending_grading_count=0,
        recent_llm_runs=db.query(func.count(LLMRun.id))
        .filter(LLMRun.created_at >= datetime.utcnow() - timedelta(days=7))
        .scalar()
        or 0,
        generated_this_week=0,
    )


@router.get("/student", response_model=StudentDashboardStats)
def student_stats(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StudentDashboardStats:
    if current.role != "student" or not current.student_id:
        return StudentDashboardStats(
            pending_assignments=0,
            submitted_assignments=0,
            graded_assignments=0,
            average_score=0.0,
            recent_grades=[],
        )

    sid = current.student_id
    pending = (
        db.query(func.count(Assignment.id))
        .filter(Assignment.student_id == sid, Assignment.status == "assigned")
        .scalar()
        or 0
    )
    submitted = (
        db.query(func.count(Assignment.id))
        .filter(Assignment.student_id == sid, Assignment.status == "submitted")
        .scalar()
        or 0
    )
    graded = (
        db.query(func.count(Assignment.id))
        .filter(Assignment.student_id == sid, Assignment.status == "graded")
        .scalar()
        or 0
    )

    graded_rows = (
        db.query(Grading.final_score, Submission.submitted_at, Assignment.title)
        .join(Submission, Grading.submission_id == Submission.id)
        .join(Assignment, Submission.assignment_id == Assignment.id)
        .filter(Submission.student_id == sid, Grading.confirmed == True)  # noqa: E712
        .order_by(Grading.confirmed_at.desc())
        .limit(10)
        .all()
    )
    scores = [r[0] for r in graded_rows if r[0] is not None]
    avg = sum(scores) / len(scores) if scores else 0.0

    return StudentDashboardStats(
        pending_assignments=pending,
        submitted_assignments=submitted,
        graded_assignments=graded,
        average_score=round(avg, 1),
        recent_grades=[
            {"score": r[0], "submitted_at": r[1].isoformat(), "title": r[2]} for r in graded_rows
        ],
    )