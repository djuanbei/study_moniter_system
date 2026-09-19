"""Online exam services (PRD §73–76): timing, autosave, scoring, evidence.

Server-authoritative rules:
  - deadline is set once at start (started_at + duration); the browser timer
    is display-only (§74)
  - autosave stores answers on the attempt; the server is the final source
    of truth (§75); saving after the deadline expires the attempt (§76
    TIME_EXPIRED)
  - objective question types are auto-scored against answer_key; subjective
    questions go to parent confirmation (§49)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.exams import OBJECTIVE_QTYPES, Exam, ExamAttempt
from app.services.learning import ERROR_PATTERNS, record_evidence

_PASS_THRESHOLD = 60.0


def _float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_answer(text: str) -> str:
    """Normalize for objective comparison: lowercase, strip spaces/punct."""
    return re.sub(r"[\s，。、；：？！,.:;?!'\"()（）\[\]【】]+", "", (text or "").lower())


def start_attempt(db: Session, exam: Exam, student_id: int) -> ExamAttempt:
    """Start (or resume) the attempt; deadline is server-set (§74)."""
    now = datetime.utcnow()
    existing = (
        db.query(ExamAttempt)
        .filter(ExamAttempt.exam_id == exam.id, ExamAttempt.student_id == student_id)
        .order_by(ExamAttempt.id.desc())
        .first()
    )
    if existing:
        if existing.status in ("SUBMITTED", "TIME_EXPIRED", "GRADED"):
            raise ValueError("该考试已提交，不能重新开始")
        # resume: apply expiry lazily
        if now > existing.deadline:
            existing.status = "TIME_EXPIRED"
            existing.submitted_at = existing.deadline
            existing.submit_reason = "time_expired"
            db.flush()
        return existing

    attempt = ExamAttempt(
        exam_id=exam.id,
        student_id=student_id,
        started_at=now,
        deadline=now + timedelta(minutes=exam.duration_minutes),
        status="IN_PROGRESS",
        answers_json={},
    )
    db.add(attempt)
    db.flush()
    return attempt


def save_answers(db: Session, attempt: ExamAttempt, answers: dict) -> ExamAttempt:
    """Autosave (§75); expires the attempt when past deadline."""
    now = datetime.utcnow()
    if attempt.status == "IN_PROGRESS" and now > attempt.deadline:
        expire_attempt(db, attempt, now)
        db.flush()
        return attempt
    if attempt.status != "IN_PROGRESS":
        raise ValueError(f"考试状态为 {attempt.status}，不能保存")
    clean: dict[str, str] = {}
    for k, v in (answers or {}).items():
        if v is None:
            continue
        clean[str(k)] = str(v)[:5000]
    attempt.answers_json = clean
    attempt.last_saved_at = now
    db.flush()
    return attempt


def expire_attempt(db: Session, attempt: ExamAttempt, now: datetime) -> None:
    attempt.status = "TIME_EXPIRED"
    attempt.submitted_at = now
    attempt.submit_reason = "time_expired"
    _auto_score(db, attempt)


def submit_attempt(
    db: Session, attempt: ExamAttempt, *, reason: str = "manual"
) -> ExamAttempt:
    now = datetime.utcnow()
    if attempt.status not in ("IN_PROGRESS", "TIME_EXPIRED"):
        raise ValueError(f"考试状态为 {attempt.status}，不能提交")
    if attempt.status == "IN_PROGRESS" and now > attempt.deadline:
        reason = "time_expired"
    attempt.submitted_at = now
    if reason == "time_expired":
        attempt.status = "TIME_EXPIRED"
    else:
        attempt.status = "SUBMITTED"
    attempt.submit_reason = reason
    _auto_score(db, attempt)
    db.flush()
    return attempt


def _auto_score(db: Session, attempt: ExamAttempt) -> None:
    """Deterministic scoring for objective questions; subjective → None."""
    exam = db.get(Exam, attempt.exam_id)
    qs = exam.question_set if exam else None
    answers = attempt.answers_json or {}
    per_question: dict[str, Optional[float]] = {}
    for q in sorted(qs.questions, key=lambda q: q.order) if qs else []:
        raw = answers.get(str(q.id), "")
        if q.qtype in OBJECTIVE_QTYPES and q.answer_key:
            expected = normalize_answer(q.answer_key)
            got = normalize_answer(raw)
            per_question[str(q.id)] = 100.0 if (got and got == expected) else 0.0
        else:
            per_question[str(q.id)] = None
    attempt.per_question = {"per_question": per_question, "auto": True}
    attempt.auto_scored = True
    values = [v for v in per_question.values() if v is not None]
    if values:
        attempt.score = round(sum(values) / len(values), 1)  # objective-only preview


def confirm_attempt(
    db: Session,
    attempt: ExamAttempt,
    *,
    final_score: float,
    feedback: Optional[str],
    per_question: Optional[dict],
    user=None,
) -> ExamAttempt:
    """Parent confirmation → official score + LearningEvidence (§49, §57)."""
    if attempt.status not in ("SUBMITTED", "TIME_EXPIRED", "GRADING"):
        raise ValueError(f"考试状态为 {attempt.status}，不能确认")
    exam = db.get(Exam, attempt.exam_id)
    qs = exam.question_set if exam else None
    existing = ((attempt.per_question or {}).get("per_question")) or {}
    # Accept {"per_question": {...}} or a flat {qid: score} map; values may be
    # numbers or {"score": n, "error_type": ..., "comment": ...}.
    input_map: dict = {}
    if isinstance(per_question, dict):
        input_map = per_question.get("per_question") or per_question
    merged: dict[str, Optional[float]] = {}
    error_types: dict[str, Optional[str]] = {}
    for q in sorted(qs.questions, key=lambda q: q.order) if qs else []:
        key = str(q.id)
        incoming = input_map.get(key) if isinstance(input_map, dict) else None
        if incoming is not None:
            if isinstance(incoming, dict):
                score = _float(incoming.get("score"))
                error_type = incoming.get("error_type")
                if error_type and error_type not in ERROR_PATTERNS:
                    error_type = None
                error_types[key] = error_type
            else:
                score = _float(incoming)
                error_types[key] = None
            merged[key] = score
        else:
            merged[key] = existing.get(key)
            error_types[key] = None

    attempt.status = "GRADED"
    attempt.score = final_score
    attempt.feedback = feedback
    attempt.per_question = {"per_question": merged, "auto": False}
    attempt.confirmed_by = user.id if user else None
    attempt.confirmed_at = datetime.utcnow()
    db.flush()

    # Evidence per (question, knowledge point) — same loop as assignments.
    count = 0
    for q in sorted(qs.questions, key=lambda q: q.order) if qs else []:
        score = merged.get(str(q.id))
        for kp_name in q.knowledge_points or ["未分类"]:
            record_evidence(
                db,
                student_id=attempt.student_id,
                knowledge_point_name=str(kp_name),
                correct=(score or 0.0) >= _PASS_THRESHOLD,
                score=score,
                difficulty=q.difficulty,
                error_type=error_types.get(str(q.id)),
                feedback=feedback,
                confidence=None,
                trust_level="PARENT_CONFIRMED",
                source_type="EXAM",
                observed_by=user.id if user else None,
                created_at=attempt.confirmed_at,
            )
            count += 1

    from app.models.students import Student
    from app.services.learning import _refresh_weak_points

    student = db.get(Student, attempt.student_id)
    if student:
        _refresh_weak_points(db, student)
    db.flush()
    return attempt
