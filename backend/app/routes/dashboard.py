"""Dashboard summary endpoint (PRD §13 / §14)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ensure_can_access_student, get_current_user
from app.models.assignments import Assignment, Grading, Submission
from app.models.auth import User
from app.models.exams import Exam, ExamAttempt
from app.models.learning import (
    LearningObjective,
    LearningPlan,
    ParentFeedback,
    StudentKnowledgeState,
)
from app.models.students import Chapter, Student
from app.models.system import LLMRun
from app.schemas import DashboardStats
from app.services.learning import diagnose_student


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class StudentDashboardStats(BaseModel):
    pending_assignments: int
    submitted_assignments: int
    graded_assignments: int
    average_score: float
    recent_grades: list[dict]


class ParentDashboardOut(BaseModel):
    """PRD §13 — parent dashboard fields for one child."""

    student_id: int
    name: str
    today_plan: list[dict]
    current_objective: Optional[str] = None
    current_chapter: Optional[str] = None
    mastery_summary: dict
    weak_points: list[dict]
    today_tasks: list[dict]
    needs_parent_review: list[dict]
    upcoming_exams: list[dict]
    learning_trend: dict


@router.get("", response_model=DashboardStats)
def stats(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DashboardStats:
    return DashboardStats(
        student_count=db.query(func.count(Student.id)).scalar() or 0,
        active_assignment_count=db.query(func.count(Assignment.id))
        .filter(Assignment.status.in_(["assigned", "in_progress"]))
        .scalar()
        or 0,
        pending_grading_count=db.query(func.count(Grading.id))
        .filter(Grading.confirmed == False)  # noqa: E712  — suggested but not confirmed
        .scalar()
        or 0,
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


# ---------------------------------------------------------------------------
# PRD §13 — Parent dashboard per child
# ---------------------------------------------------------------------------

@router.get("/parent/{student_id}", response_model=ParentDashboardOut)
def parent_dashboard(
    student_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParentDashboardOut:
    ensure_can_access_student(current, student_id)
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # 当前目标 (highest-priority active objective)
    current_obj = (
        db.query(LearningObjective)
        .filter(LearningObjective.student_id == student_id, LearningObjective.status == "active")
        .order_by(LearningObjective.priority.asc(), LearningObjective.id.desc())
        .first()
    )
    # 当前章节
    chapter = db.get(Chapter, student.current_chapter_id) if student.current_chapter_id else None

    # 知识掌握 (overall mastery + breakdown)
    states = (
        db.query(StudentKnowledgeState)
        .filter(StudentKnowledgeState.student_id == student_id)
        .all()
    )
    overall = round(sum(s.mastery_score for s in states) / len(states), 4) if states else 0.0
    mastery_summary = {
        "overall": overall,
        "knowledge_point_count": len(states),
        "mastered": sum(1 for s in states if s.mastery_score >= 0.8),
        "learning": sum(1 for s in states if 0.4 <= s.mastery_score < 0.8),
        "weak": sum(1 for s in states if s.mastery_score < 0.4),
    }

    # 薄弱点
    diag = diagnose_student(db, student_id)
    weak_points = [
        {
            "knowledge_point": p["knowledge_point"],
            "mastery": p["mastery"],
            "trend": p["trend"],
            "decay_risk": p["decay_risk"],
            "reason": p["reason"],
            "rank": p.get("rank"),
        }
        for p in diag.get("priorities", [])[:3]
    ]

    # 今日任务 (pending assignments)
    today = datetime.utcnow().date()
    todays = (
        db.query(Assignment)
        .filter(Assignment.student_id == student_id, Assignment.status == "assigned")
        .order_by(Assignment.due_date.asc().nullslast())
        .limit(5)
        .all()
    )
    today_tasks = [
        {
            "assignment_id": a.id,
            "title": a.title,
            "due_date": a.due_date.isoformat() if a.due_date else None,
            "estimated_minutes": a.estimated_minutes,
        }
        for a in todays
    ]

    # 今日学习 (the latest approved plan's first day)
    plan = (
        db.query(LearningPlan)
        .filter(LearningPlan.student_id == student_id, LearningPlan.status == "approved")
        .order_by(LearningPlan.id.desc())
        .first()
    )
    today_plan = []
    if plan:
        for it in plan.items:
            today_plan.append(
                {
                    "day": it.day,
                    "intervention_type": it.intervention_type,
                    "knowledge_point": it.knowledge_point_name,
                    "description": it.description,
                    "question_count": it.question_count,
                    "status": it.status,
                }
            )

    # 待家长确认
    review_rows = (
        db.query(Grading, Submission)
        .join(Submission, Grading.submission_id == Submission.id)
        .filter(
            Submission.student_id == student_id,
            Grading.confirmed == False,  # noqa: E712
            Grading.needs_review == True,  # noqa: E712
        )
        .order_by(Grading.created_at.desc())
        .limit(10)
        .all()
    )
    needs_parent_review = [
        {
            "submission_id": s.id,
            "assignment_title": db.get(Assignment, s.assignment_id).title if s.assignment_id else "",
            "ai_suggested_score": g.llm_suggested_score,
            "ai_confidence": g.llm_confidence,
            "submitted_at": s.submitted_at.isoformat(),
        }
        for g, s in review_rows
    ]

    # 近期考试
    upcoming_exams = (
        db.query(Exam)
        .filter(Exam.student_id == student_id, Exam.status == "active")
        .order_by(Exam.id.desc())
        .limit(5)
        .all()
    )
    upcoming = [
        {
            "exam_id": e.id,
            "title": e.title,
            "duration_minutes": e.duration_minutes,
            "total_score": e.total_score,
            "attempts": len(e.attempts or []),
        }
        for e in upcoming_exams
    ]

    # 学习趋势 (last 10 graded scores)
    recent = (
        db.query(Grading.final_score, Submission.submitted_at)
        .join(Submission, Grading.submission_id == Submission.id)
        .filter(Submission.student_id == student_id, Grading.confirmed == True)  # noqa: E712
        .order_by(Grading.confirmed_at.desc())
        .limit(10)
        .all()
    )
    trend_series = [
        {"date": d.isoformat()[:10], "score": float(sc)} for sc, d in reversed(recent) if sc is not None
    ]
    avg_recent = (
        round(sum(sc for sc, _ in recent if sc is not None) / max(1, len([1 for sc, _ in recent if sc is not None])), 1)
        if recent
        else 0.0
    )
    learning_trend = {
        "series": trend_series,
        "average_recent": avg_recent,
        "samples": len(trend_series),
    }

    return ParentDashboardOut(
        student_id=student.id,
        name=student.name,
        today_plan=today_plan,
        current_objective=current_obj.description if current_obj else None,
        current_chapter=chapter.title if chapter else None,
        mastery_summary=mastery_summary,
        weak_points=weak_points,
        today_tasks=today_tasks,
        needs_parent_review=needs_parent_review,
        upcoming_exams=upcoming,
        learning_trend=learning_trend,
    )