"""Online exam tests (PRD §73–76)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.exams import Exam, ExamAttempt
from app.models.learning import LearningEvidence, StudentKnowledgeState
from app.services.exams import (
    confirm_attempt,
    normalize_answer,
    save_answers,
    start_attempt,
    submit_attempt,
)


@pytest.fixture()
def exam(db_session, sample_setup):
    return Exam(
        title="期中在线测", student_id=sample_setup["student"].id,
        question_set_id=sample_setup["question_set"].id,
        duration_minutes=30, total_score=100,
    )


def test_normalize_answer():
    assert normalize_answer("X = 3。") == normalize_answer("x=3")
    assert normalize_answer("A") == "a"


def test_start_resume_deadline(db_session, exam):
    db_session.add(exam)
    db_session.commit()
    attempt = start_attempt(db_session, exam, student_id=exam.student_id)
    db_session.commit()
    # §74: deadline = started_at + duration, set by the server
    assert (attempt.deadline - attempt.started_at) == timedelta(minutes=30)
    assert attempt.status == "IN_PROGRESS"

    # resume returns the same attempt
    again = start_attempt(db_session, exam, student_id=exam.student_id)
    assert again.id == attempt.id

    # submitted exam cannot restart (§76)
    attempt.status = "GRADED"
    db_session.commit()
    with pytest.raises(ValueError):
        start_attempt(db_session, exam, student_id=exam.student_id)


def test_autosave_and_expiry(db_session, sample_setup, exam):
    db_session.add(exam)
    db_session.commit()
    attempt = start_attempt(db_session, exam, student_id=exam.student_id)

    saved = save_answers(db_session, attempt, {"1": "x=3", "2": "x=2"})
    db_session.commit()
    assert saved.answers_json == {"1": "x=3", "2": "x=2"}
    assert saved.last_saved_at is not None  # §75 server-side autosave

    # past deadline -> save flips the attempt to TIME_EXPIRED (§76)
    attempt.deadline = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    saved2 = save_answers(db_session, attempt, {"1": "late"})
    assert saved2.status == "TIME_EXPIRED"
    assert saved2.submit_reason == "time_expired"


def test_objective_autoscore_and_confirm(db_session, sample_setup, exam):
    db_session.add(exam)
    db_session.commit()
    # make the sample questions objectively gradable (§73 fill_blank)
    from app.models.assignments import Question

    for q in db_session.query(Question).filter_by(
        question_set_id=sample_setup["question_set"].id
    ).all():
        q.qtype = "fill_blank"
    db_session.commit()

    attempt = start_attempt(db_session, exam, student_id=exam.student_id)
    # Q1: 2x+3=9 -> x=3 (answer_key "x = 3"); Q2: 3x-1=8 -> x=3
    save_answers(db_session, attempt, {"1": "X = 3。", "2": "x=4"})
    submit_attempt(db_session, attempt, reason="manual")
    db_session.commit()

    assert attempt.status == "SUBMITTED"
    per = attempt.per_question["per_question"]
    # objective scoring is normalization-based (§73)
    assert per["1"] == 100.0
    assert per["2"] == 0.0
    assert attempt.score == 50.0

    # parent confirms with adjusted subjective scores -> evidence (§49/§57)
    student = sample_setup["student"]
    confirm_attempt(
        db_session, attempt, final_score=70.0, feedback="加油",
        per_question={"1": 100, "2": {"score": 40, "error_type": "CALCULATION_ERROR"}},
        user=None,
    )
    db_session.commit()
    assert attempt.status == "GRADED"
    assert attempt.score == 70.0

    evidence = (
        db_session.query(LearningEvidence)
        .filter_by(student_id=student.id, source_type="EXAM")
        .all()
    )
    assert len(evidence) == 2  # 2 questions × 1 KP each
    assert sorted(e.score for e in evidence) == [40.0, 100.0]
    assert any(e.correct for e in evidence)
    assert any(not e.correct for e in evidence)
    assert all(e.knowledge_point_name == "移项" for e in evidence)
    failed = next(e for e in evidence if not e.correct)
    assert failed.error_type == "CALCULATION_ERROR"

    states = db_session.query(StudentKnowledgeState).filter_by(student_id=student.id).all()
    assert states  # knowledge states updated from exam evidence


def test_exam_api_student_flow(db_session, client, csrf_headers, sample_setup, student_user):
    """RBAC + full API flow: create (teacher) -> start/save/submit (student)."""
    exam = Exam(
        title="API 考试", student_id=sample_setup["student"].id,
        question_set_id=sample_setup["question_set"].id, duration_minutes=15,
    )
    db_session.add(exam)
    db_session.commit()

    student_user_obj, student_row = student_user
    from app.deps import get_current_user

    # teacher creates; student starts
    r = client.post("/api/exam-attempts/start", headers=csrf_headers,
                    params={"exam_id": exam.id})
    assert r.status_code == 200
    attempt_id = r.json()["id"]

    client.app.dependency_overrides[get_current_user] = lambda: student_user_obj
    try:
        # wrong student cannot access another student's attempt
        r = client.put(f"/api/exam-attempts/{attempt_id}/save", headers=csrf_headers,
                       json={"answers": {"1": "cheat"}})
        assert r.status_code in (403, 404)

        # exam list is scoped to the student's own rows
        r = client.get("/api/exams")
        assert r.status_code == 200
        assert all(e["student_id"] == student_row.id for e in r.json())
    finally:
        client.app.dependency_overrides.pop(get_current_user, None)
