"""Knowledge-base incremental update tests (PRD §69)."""

from __future__ import annotations

import pytest

from app.models.learning import (
    KnowledgePoint,
    KnowledgeUpdateCandidate,
    LearningEvidence,
)
from app.services.knowledge_update import (
    analyze_knowledge,
    apply_knowledge_candidate,
    generate_knowledge_candidates,
)
from app.services.learning import record_evidence
from app.services.question_bank import publish_question


def test_analysis_finds_missing_and_merge_and_unused(db_session, sample_setup):
    # sample chapter seeds KPs: 移项, 应用题建模
    # 1) a generated question references a KP missing from the table -> ADD
    #    (note: record_evidence auto-creates KPs, so use a Question row)
    from app.models.assignments import Question

    db_session.add(Question(
        question_set_id=sample_setup["question_set"].id, order=9,
        qtype="fill_blank", subject="math", prompt="去括号练习",
        knowledge_points=["去括号"], difficulty="easy",
    ))
    # 2) name variant -> MERGE candidate
    db_session.add(KnowledgePoint(name="移 项"))  # space variant of 移项
    # 3) KP not in chapters and never used -> DEPRECATE candidate
    db_session.add(KnowledgePoint(name="孤立知识点"))
    db_session.commit()

    analysis = analyze_knowledge(db_session)
    assert "去括号" in analysis["add_candidates"]
    assert any(m["keep"] == "移项" and "移 项" in m["merge"] for m in analysis["merge_candidates"])
    assert "孤立知识点" in analysis["deprecate_candidates"]
    assert "移项" not in analysis["deprecate_candidates"]  # in chapter + has evidence


def test_generate_and_apply_add(db_session, sample_setup):
    # a generated Question references 去括号, missing from the KP table
    from app.models.assignments import Question

    db_session.add(Question(
        question_set_id=sample_setup["question_set"].id, order=9,
        qtype="fill_blank", subject="math", prompt="去括号练习",
        knowledge_points=["去括号"], difficulty="easy",
    ))
    db_session.commit()
    result = generate_knowledge_candidates(db_session)
    db_session.commit()
    assert result["adds"] == 1

    cand = db_session.query(KnowledgeUpdateCandidate).filter_by(
        candidate_type="ADD", status="pending"
    ).first()
    summary = apply_knowledge_candidate(db_session, cand)
    db_session.commit()
    assert summary["applied"] is True
    kp = db_session.get(KnowledgePoint, summary["kp_id"])
    assert kp.name == "去括号"

    # idempotent: re-adding an existing name approves without duplicating
    cand2 = KnowledgeUpdateCandidate(
        candidate_type="ADD", payload={"name": "去括号"}, status="pending"
    )
    db_session.add(cand2)
    db_session.commit()
    apply_knowledge_candidate(db_session, cand2)
    names = [k.name for k in db_session.query(KnowledgePoint).filter_by(name="去括号").all()]
    assert len(names) == 1


def test_apply_merge_moves_references(db_session, sample_setup):
    student = sample_setup["student"]
    kp_variant = KnowledgePoint(name="移 项")
    db_session.add(kp_variant)
    db_session.commit()
    record_evidence(db_session, student_id=student.id, knowledge_point_name="移 项",
                    correct=True, score=95, trust_level="PARENT_CONFIRMED")
    db_session.commit()
    variant_id = kp_variant.id
    ev = db_session.query(LearningEvidence).filter_by(knowledge_point_name="移 项").first()
    assert ev.knowledge_point_id == variant_id

    keep = db_session.query(KnowledgePoint).filter_by(name="移项").first()
    cand = KnowledgeUpdateCandidate(
        candidate_type="MERGE", target_kp_id=keep.id,
        payload={"keep": "移项", "merge": ["移 项"]}, status="pending",
    )
    db_session.add(cand)
    db_session.commit()
    summary = apply_knowledge_candidate(db_session, cand)
    db_session.commit()
    assert summary["applied"] is True and summary["moved"] >= 1

    db_session.expire_all()
    db_session.refresh(ev)
    assert ev.knowledge_point_id == keep.id  # reference moved to canonical KP
    assert db_session.get(KnowledgePoint, variant_id).status == "deprecated"


def test_deprecate_unused_kp(db_session, sample_setup):
    kp = KnowledgePoint(name="孤立知识点")
    db_session.add(kp)
    db_session.commit()
    generate_knowledge_candidates(db_session)
    db_session.commit()
    cand = db_session.query(KnowledgeUpdateCandidate).filter_by(
        candidate_type="DEPRECATE", status="pending"
    ).first()
    assert cand is not None
    apply_knowledge_candidate(db_session, cand)
    db_session.commit()
    assert db_session.get(KnowledgePoint, kp.id).status == "deprecated"


def test_knowledge_update_job_registered():
    from app.services.job_worker import registered_types

    assert "KNOWLEDGE_UPDATE" in registered_types()
