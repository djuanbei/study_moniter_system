"""Learning reports (PRD §65–66): daily / weekly / monthly aggregation.

Deterministic (no LLM): aggregates evidence, grading activity and mastery
deltas from the knowledge-state history for a time window.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.assignments import Assignment, Grading, Submission
from app.models.learning import LearningEvidence, StudentKnowledgeStateHistory
from app.models.students import Student
from app.services.learning import diagnose_student


def learning_report(db: Session, student: Student, days: int = 7) -> dict:
    """Report for the last `days` days (1=每日, 7=每周, 30=每月, PRD §65)."""
    now = datetime.utcnow()
    start = now - timedelta(days=days)

    evidence = (
        db.query(LearningEvidence)
        .filter(
            LearningEvidence.student_id == student.id,
            LearningEvidence.created_at >= start,
        )
        .order_by(LearningEvidence.created_at.asc())
        .all()
    )
    correct = sum(1 for e in evidence if e.correct)
    error_counts: dict[str, int] = {}
    for e in evidence:
        if e.error_type:
            error_counts[e.error_type] = error_counts.get(e.error_type, 0) + 1

    graded_count = (
        db.query(func.count(Grading.id))
        .join(Submission, Grading.submission_id == Submission.id)
        .filter(
            Submission.student_id == student.id,
            Grading.confirmed == True,  # noqa: E712
            Grading.confirmed_at >= start,
        )
        .scalar()
        or 0
    )
    assigned_count = (
        db.query(func.count(Assignment.id))
        .filter(
            Assignment.student_id == student.id,
            Assignment.created_at >= start,
            Assignment.status != "cancelled",
        )
        .scalar()
        or 0
    )

    # Mastery deltas within the window, from the state history (PRD §28).
    history = (
        db.query(StudentKnowledgeStateHistory)
        .filter(
            StudentKnowledgeStateHistory.student_id == student.id,
            StudentKnowledgeStateHistory.changed_at >= start,
        )
        .order_by(StudentKnowledgeStateHistory.changed_at.asc())
        .all()
    )
    by_kp: dict[int, list[float]] = {}
    for h in history:
        by_kp.setdefault(h.knowledge_point_id, []).append(h.mastery_score)
    changes = []
    for kp_id, values in by_kp.items():
        if len(values) < 2:
            continue
        delta = round(values[-1] - values[0], 4)
        changes.append({"knowledge_point_id": kp_id, "delta": delta})
    changes.sort(key=lambda c: c["delta"], reverse=True)
    improving = changes[:3]
    declining = sorted(changes, key=lambda c: c["delta"])[:3]

    diagnosis = diagnose_student(db, student.id)

    def _kp_name(kp_id: int | None) -> str:
        if kp_id is None:
            return "未知知识点"
        from app.models.learning import KnowledgePoint

        kp = db.get(KnowledgePoint, kp_id)
        return kp.name if kp else f"#{kp_id}"

    return {
        "student_id": student.id,
        "student_name": student.name,
        "period_days": days,
        "start": start.isoformat(),
        "end": now.isoformat(),
        "evidence_count": len(evidence),
        "correct_count": correct,
        "accuracy": round(correct / len(evidence), 4) if evidence else None,
        "graded_count": int(graded_count),
        "assigned_count": int(assigned_count),
        "completion_rate": round(graded_count / assigned_count, 4) if assigned_count else None,
        "error_types": error_counts,
        "improving": [
            {"knowledge_point": _kp_name(c["knowledge_point_id"]), "delta": c["delta"]}
            for c in improving
        ],
        "declining": [
            {"knowledge_point": _kp_name(c["knowledge_point_id"]), "delta": c["delta"]}
            for c in declining
        ],
        "priorities": [
            {
                "knowledge_point": p["knowledge_point"],
                "mastery": p["mastery"],
                "reason": p["reason"],
            }
            for p in diagnosis.get("priorities", [])[:3]
        ],
    }
