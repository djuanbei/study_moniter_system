"""Phase-3 tests (PRD §94): policy, adaptive sequencing, path, knowledge map."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.learning import (
    InterventionOutcome,
    KnowledgePoint,
    StudentKnowledgeStateHistory,
)
from app.services.learning import build_heuristic_plan, diagnose_student
from app.services.policy import (
    intervention_effectiveness,
    knowledge_map,
    learning_path,
    learning_policy,
    preferred_practice_type,
)


def _seed_outcomes(db, student_id, itype, deltas):
    for d in deltas:
        db.add(InterventionOutcome(
            student_id=student_id, intervention_type=itype,
            before_mastery=0.4, after_mastery=0.4 + d, delta=d,
            assessment_count=2, created_at=datetime.utcnow(),
        ))
    db.commit()  # autoflush is off — pending adds are invisible to queries


def test_policy_prefers_effective_interventions(db_session, sample_setup):
    student = sample_setup["student"]
    # EXAMPLE works great for this student; REFLECTION barely moves the needle
    _seed_outcomes(db_session, student.id, "EXAMPLE", [0.15, 0.12, 0.18])
    _seed_outcomes(db_session, student.id, "REFLECTION", [0.01, -0.01])
    db_session.commit()

    eff = intervention_effectiveness(db_session, student.id)
    assert eff["EXAMPLE"]["avg_delta"] > eff["REFLECTION"]["avg_delta"]

    policy = learning_policy(db_session, student.id)
    assert policy["personalized"] is True
    assert policy["preferred_interventions"][0] == "EXAMPLE"
    assert preferred_practice_type(policy) == "EXAMPLE"


def test_policy_falls_back_to_priors_without_data(db_session, sample_setup):
    policy = learning_policy(db_session, sample_setup["student"].id)
    assert policy["personalized"] is False
    assert policy["outcomes_used"] == 0
    assert "PRACTICE" in policy["preferred_interventions"]


def test_plan_uses_adaptive_sequencing(db_session, sample_setup, monkeypatch):
    from app.services import llm as llm_pkg

    monkeypatch.setattr(llm_pkg, "stage_learning_plan",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no llm")))
    student = sample_setup["student"]
    from app.services.learning import record_evidence as _re

    _re(db_session, student_id=student.id, knowledge_point_name="应用题建模",
        correct=False, score=20, trust_level="PARENT_CONFIRMED")
    db_session.commit()
    diag = diagnose_student(db_session, student.id)

    # this student responds best to EXAMPLE -> practice days become EXAMPLE
    _seed_outcomes(db_session, student.id, "EXAMPLE", [0.2, 0.15, 0.1])
    policy = learning_policy(db_session, student.id)
    plan = build_heuristic_plan(db_session, student, diag, policy=policy)
    db_session.commit()
    kinds = [i["intervention_type"] for i in plan["items"] if i["intervention_type"] != "QUIZ"]
    assert "EXAMPLE" in kinds
    assert "PRACTICE" not in kinds  # fully replaced by the adaptive choice
    assert plan["items"][-1]["intervention_type"] == "QUIZ"


def test_learning_path_shape_and_estimates(db_session, sample_setup):
    from datetime import datetime as dt

    student = sample_setup["student"]
    from app.services.learning import record_evidence as _re

    # rising history -> positive velocity
    for score in (20, 40, 60):
        _re(db_session, student_id=student.id, knowledge_point_name="应用题建模",
            correct=score >= 60, score=score, trust_level="PARENT_CONFIRMED")
    db_session.commit()
    # backdate the first history row so the span is ~14 days
    hist = db_session.query(StudentKnowledgeStateHistory).all()
    if hist:
        hist[0].changed_at = dt.utcnow() - timedelta(days=14)
        db_session.commit()

    path = learning_path(db_session, student.id)
    assert path["velocity_per_week"] > 0
    assert "behind" in path["phases"] or "current" in path["phases"]
    assert path["estimates"]["weeks_to_catch_up_behind"] >= 0
    assert isinstance(path["objectives"], list)


def test_knowledge_map_groups_cross_textbook(db_session, sample_setup):
    db_session.add(KnowledgePoint(name="移项", textbook_version="北师大版", grade="初一"))
    db_session.add(KnowledgePoint(name="一元二次方程", textbook_version="北师大版", grade="初三"))
    db_session.commit()
    km = knowledge_map(db_session)
    # "移项" exists in both 人教版 (from sync) and 北师大版 -> exact group
    assert any(
        {e["textbook_version"] for e in g} >= {"人教版", "北师大版"}
        and {e["name"] for e in g} == {"移项"}
        for g in km["equivalent_groups"]
    )
