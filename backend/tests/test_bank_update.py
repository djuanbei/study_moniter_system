"""Question bank incremental update tests (PRD §68)."""

from __future__ import annotations

import pytest

from app.models.learning import KnowledgePoint
from app.models.question_bank import BankUpdateCandidate, QuestionBankItem
from app.services.bank_update import analyze_gaps, apply_candidate, generate_candidates
from app.services.question_bank import publish_question

BASE_FIELDS = {
    "subject": "math",
    "knowledge_points": ["移项"],
    "difficulty": "easy",
    "question_type": "fill_blank",
    "prompt": "解方程：2x + 3 = 9，求 x。",
    "answer": "x = 3",
    "rubric": "移项 1 分",
    "estimated_time": 5,
}


def test_analyze_gaps_detects_uncovered_kp(db_session, sample_setup):
    # sample_setup seeds exactly two KPs: 移项, 应用题建模
    publish_question(db_session, fields=dict(BASE_FIELDS), user_id=None)
    publish_question(db_session, fields={**BASE_FIELDS, "prompt": "解方程：4x - 2 = 10，求 x。"},
                     user_id=None)
    db_session.commit()
    analysis = analyze_gaps(db_session)
    assert analysis["bank_size"] == 2
    gap_kps = {g["knowledge_point"] for g in analysis["gaps"]}
    assert gap_kps == {"应用题建模"}  # 移项 now covered (2 questions)


def test_generate_candidates_deprecates_duplicates(db_session, sample_setup):
    publish_question(db_session, fields=dict(BASE_FIELDS), user_id=None)
    dup, _ = publish_question(db_session, fields=dict(BASE_FIELDS),
                              user_id=None, allow_duplicate=True)  # exact duplicate
    db_session.commit()
    result = generate_candidates(db_session, batch_size=2, user=None)
    db_session.commit()
    assert result["deprecates"] == 1
    cand = db_session.query(BankUpdateCandidate).filter_by(
        candidate_type="DEPRECATE", status="pending"
    ).first()
    assert cand is not None and cand.target_bank_id == dup.id

    # parent approves -> the duplicate is deprecated, original kept (§68)
    apply_candidate(db_session, cand)
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(QuestionBankItem, dup.id).status == "deprecated"


def test_generate_candidates_add_with_llm(db_session, sample_setup, monkeypatch):
    from app.models.auth import User

    def fake_stage(db, *, knowledge_point, grade, difficulty, estimated_time,
                   existing_prompts, user):
        return {
            "prompt": f"关于{knowledge_point}的新练习题：解方程 5x - 5 = 10，求 x。",
            "answer": "x = 3",
            "rubric": "列式 1 分，求解 1 分",
            "question_type": "fill_blank",
            "difficulty": difficulty,
            "estimated_time": estimated_time,
        }

    from app.services import llm as llm_pkg

    monkeypatch.setattr(llm_pkg, "stage_bank_question", fake_stage)
    result = generate_candidates(db_session, batch_size=1)
    db_session.commit()
    assert result["adds"] >= 1

    cand = db_session.query(BankUpdateCandidate).filter_by(
        candidate_type="ADD", status="pending"
    ).first()
    assert cand is not None
    assert cand.knowledge_point in {kp.name for kp in db_session.query(KnowledgePoint).all()}

    # parent approve -> bank item published as v1 (§68 last step)
    summary = apply_candidate(db_session, cand)
    db_session.commit()
    assert summary["applied"] is True
    item = db_session.get(QuestionBankItem, summary["bank_id"])
    assert item.version == 1
    assert cand.knowledge_point in (item.knowledge_points or [])

    # double-approve guarded
    with pytest.raises(ValueError):
        apply_candidate(db_session, cand)


def test_add_candidate_with_duplicate_autorejected(db_session, sample_setup, monkeypatch):
    def fake_dup_stage(db, *, knowledge_point, grade, difficulty, estimated_time,
                       existing_prompts, user):
        return dict(BASE_FIELDS)  # identical to the already-published question

    from app.services import llm as llm_pkg

    monkeypatch.setattr(llm_pkg, "stage_bank_question", fake_dup_stage)
    publish_question(db_session, fields=dict(BASE_FIELDS), user_id=None)
    db_session.commit()
    generate_candidates(db_session, batch_size=1)
    db_session.commit()
    cand = db_session.query(BankUpdateCandidate).filter_by(candidate_type="ADD").first()
    assert cand is not None and cand.duplicate_of_id is not None

    apply_candidate(db_session, cand)
    db_session.commit()
    assert cand.status == "rejected"
    assert "重复" in (cand.review_note or "")


def test_bank_update_job_registered():
    from app.services.job_worker import registered_types

    assert "QUESTION_BANK_UPDATE" in registered_types()
