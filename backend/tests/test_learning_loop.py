"""Learning-loop tests (PRD §90): state update, diagnosis, plan, grading→evidence."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.deps import get_current_user
from app.models.assignments import Assignment, Grading, GradeVersion, Submission
from app.models.learning import (
    InterventionOutcome,
    KnowledgePoint,
    LearningEvidence,
    LearningPlanItem,
    StudentKnowledgeStateHistory,
)
from app.services.learning import (
    compute_decay_risk,
    diagnose_student,
    get_state,
    grading_triage,
    record_evidence,
)


def test_state_update_and_history(db_session, sample_setup):
    student = sample_setup["student"]
    kp = db_session.query(KnowledgePoint).filter_by(name="移项").first()
    for _ in range(3):
        record_evidence(
            db_session, student_id=student.id, knowledge_point_name="移项",
            correct=False, score=20, difficulty="medium", error_type="SIGN_ERROR",
            trust_level="PARENT_CONFIRMED",
        )
    db_session.commit()
    state = get_state(db_session, student.id, kp.id)
    assert state.mastery_score < 0.3
    assert state.status == "weak"
    assert state.evidence_count == 3

    history = (
        db_session.query(StudentKnowledgeStateHistory)
        .filter_by(student_id=student.id)
        .all()
    )
    assert len(history) == 3  # PRD §28: every change recorded

    # PRD §59: careless mistakes move mastery far less than real gaps.
    # Observation is 0.0 (no score -> incorrect), so mastery must drop.
    before = state.mastery_score
    record_evidence(
        db_session, student_id=student.id, knowledge_point_name="移项",
        correct=False, score=None, error_type="CARELESS_ERROR",
        trust_level="PARENT_CONFIRMED",
    )
    db_session.commit()
    careless_drop = before - get_state(db_session, student.id, kp.id).mastery_score
    record_evidence(
        db_session, student_id=student.id, knowledge_point_name="移项",
        correct=False, score=None, error_type="MODELING_ERROR",
        trust_level="PARENT_CONFIRMED",
    )
    db_session.commit()
    modeling_drop = (
        before - careless_drop - get_state(db_session, student.id, kp.id).mastery_score
    )
    assert careless_drop > 0
    assert modeling_drop > careless_drop


def test_triage_rules():
    # PRD §47–48: high-confidence objective answers auto-suggest
    conf, review = grading_triage(
        [{"order": 1, "confidence": 0.99}, {"order": 2, "confidence": 0.97}],
        ["thinking", "thinking"],
    )
    assert conf == 0.98 and review is False
    # low confidence → parent review
    assert grading_triage([{"order": 1, "confidence": 0.61}], ["thinking"])[1] is True
    # open-ended (composition) always reviewed
    assert grading_triage([{"order": 1, "confidence": 0.95}], ["composition"])[1] is True


def test_decay_bands():
    # PRD §60: 0.82 mastery + 90 days no practice → HIGH
    assert compute_decay_risk(datetime.utcnow() - timedelta(days=90)) == "HIGH"
    assert compute_decay_risk(datetime.utcnow() - timedelta(days=5)) == "LOW"
    assert compute_decay_risk(None) == "CRITICAL"


def test_diagnosis_ranks_weak_points(db_session, sample_setup):
    student = sample_setup["student"]
    record_evidence(
        db_session, student_id=student.id, knowledge_point_name="应用题建模",
        correct=False, score=15, difficulty="medium", error_type="MODELING_ERROR",
        trust_level="PARENT_CONFIRMED",
    )
    record_evidence(
        db_session, student_id=student.id, knowledge_point_name="移项",
        correct=True, score=95, difficulty="medium", trust_level="PARENT_CONFIRMED",
    )
    db_session.commit()
    diag = diagnose_student(db_session, student.id)
    priorities = diag["priorities"]
    assert priorities
    assert priorities[0]["knowledge_point"] == "应用题建模"


def test_grading_confirm_creates_evidence_once(db_session, client, csrf_headers, sample_setup):
    sub = sample_setup["submission"]
    r = client.post("/api/grading/confirm", headers=csrf_headers, json={
        "submission_id": sub.id, "final_score": 85.0, "feedback": "不错",
        "per_question_scores": [
            {"order": 1, "score": 90, "confidence": 0.95},
            {"order": 2, "score": 80, "confidence": 0.9},
        ],
    })
    assert r.status_code == 200

    count1 = db_session.query(LearningEvidence).filter_by(submission_id=sub.id).count()
    assert count1 == 2  # 2 questions × 1 KP each

    # Idempotent: re-confirm must not duplicate evidence
    r2 = client.post("/api/grading/confirm", headers=csrf_headers, json={
        "submission_id": sub.id, "final_score": 90.0, "feedback": "改分",
    })
    assert r2.status_code == 200
    count2 = db_session.query(LearningEvidence).filter_by(submission_id=sub.id).count()
    assert count2 == count1

    # PRD §50: the score change is versioned
    versions = db_session.query(GradeVersion).filter_by(submission_id=sub.id).all()
    assert len(versions) == 1
    assert versions[0].previous_score == 85.0
    assert versions[0].new_score == 90.0


def test_resubmit_graded_assignment_rejected(db_session, client, csrf_headers, sample_setup):
    assignment = sample_setup["assignment"]
    assignment.status = "graded"
    db_session.commit()
    r = client.post(
        f"/api/assignments/{assignment.id}/submit",
        headers=csrf_headers,
        data={"text_answer": "resubmit"},
    )
    assert r.status_code == 400


def test_text_answer_survives_submit(db_session, client, csrf_headers, sample_setup):
    """Regression: multiple text_answer fields used to be silently dropped."""
    assignment = sample_setup["assignment"]
    r = client.post(
        f"/api/assignments/{assignment.id}/submit",
        headers=csrf_headers,
        data={"text_answer": "Q1: x=3\n\nQ2: x=2"},
    )
    assert r.status_code == 200
    db_session.expire_all()
    assert sample_setup["submission"].text_answer == "Q1: x=3\n\nQ2: x=2"


def test_plan_generate_approve_assign_loop(db_session, client, csrf_headers, sample_setup, monkeypatch):
    """Full loop: plan → approve → assign → grading confirm → outcome (PRD §90)."""
    import app.services.llm as llm_pkg

    def _no_llm(*args, **kwargs):
        raise RuntimeError("tests: llm disabled")

    monkeypatch.setattr(llm_pkg, "stage_learning_plan", _no_llm)
    monkeypatch.setattr(
        llm_pkg, "generate_two_sets",
        lambda db, *, student_payload, teacher_requirements, user: {
            "sets": [{
                "label": "A",
                "questions": [{
                    "order": 1, "qtype": "thinking", "subject": "math",
                    "prompt": "练习题", "rubric": "按步骤给分", "answer_key": "x=3",
                    "knowledge_points": ["移项"], "difficulty": "easy",
                    "estimated_minutes": 5,
                }],
                "validator_notes": "OK",
            }],
        },
    )

    student = sample_setup["student"]
    r = client.post("/api/learning-plans/generate", headers=csrf_headers, json={"student_id": student.id})
    assert r.status_code == 200
    plan = r.json()
    assert plan["status"] == "draft" and plan["generated_by"] == "heuristic"

    r = client.post(f"/api/learning-plans/{plan['id']}/approve", headers=csrf_headers)
    assert r.json()["status"] == "approved"

    item = next(i for i in plan["items"] if i["question_count"] > 0)
    r = client.post(
        f"/api/learning-plans/{plan['id']}/items/{item['id']}/assign", headers=csrf_headers
    )
    assert r.status_code == 200, r.text
    assignment_id = r.json()["id"]
    db_session.commit()
    item_row = db_session.get(LearningPlanItem, item["id"])
    assert item_row.status == "assigned"
    assert item_row.before_mastery is not None

    # student answers; parent confirms → evidence + intervention outcome (§63)
    assignment = db_session.get(Assignment, assignment_id)
    submission = Submission(
        assignment_id=assignment_id, student_id=student.id,
        submitted_at=datetime.utcnow(), archive_path="uploads/test2",
        text_answer="x=3", status="submitted",
    )
    db_session.add(submission)
    db_session.commit()

    r = client.post("/api/grading/confirm", headers=csrf_headers, json={
        "submission_id": submission.id, "final_score": 90.0, "feedback": "好",
        "per_question_scores": [{"order": 1, "score": 90, "confidence": 0.9}],
    })
    assert r.status_code == 200
    outcome = db_session.query(InterventionOutcome).filter_by(plan_item_id=item["id"]).first()
    assert outcome is not None
    assert outcome.after_mastery is not None
    db_session.expire_all()  # the confirm ran in the request's own session
    assert db_session.get(LearningPlanItem, item["id"]).status == "done"


def test_grading_list_rbac(db_session, client, sample_setup, student_user):
    """Students can only list gradings of their own submissions (PRD §85)."""
    student_user_obj, _own_student = student_user
    sub = sample_setup["submission"]  # belongs to the sample student, not student_user
    db_session.add(Grading(
        submission_id=sub.id, final_score=88.0, confirmed=True,
        confirmed_at=datetime.utcnow(),
    ))
    db_session.commit()

    previous = client.app.dependency_overrides[get_current_user]
    client.app.dependency_overrides[get_current_user] = lambda: student_user_obj
    try:
        r = client.get("/api/grading")
        assert r.status_code == 200
        assert r.json() == []  # other students' gradings are invisible
    finally:
        client.app.dependency_overrides[get_current_user] = previous


def test_question_generation_validates_input(db_session, client, csrf_headers, sample_setup):
    """PRD §89: the deterministic validator must reject malformed questions."""
    from app.services.rubric import validate_question

    from app.models.assignments import Question

    bad = Question(
        question_set_id=0, order=1, qtype="composition", subject="language",
        prompt="太短", knowledge_points=[], difficulty="easy",
    )
    issues = validate_question(bad)
    assert issues  # composition without rubric / short prompt must be flagged
