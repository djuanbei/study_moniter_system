"""Historical assessment import tests (PRD §54–55)."""

from __future__ import annotations

from datetime import date

from app.models.historical import HistoricalAssessment
from app.models.learning import KnowledgePoint, LearningEvidence, StudentKnowledgeState
from app.models.materials import Material
from app.services.historical_import import (
    analyze_history,
    confirm_history,
    extract_questions_fallback,
)

OCR_EXAM = """七年级数学期中考试
1. 计算：2x + 3 = 9，求 x。
答：x = 3
（5分）得5分
2. 解方程：3(x-1) = 6。
答：x = 1（错误）
（5分）得2分 老师批注：去括号符号错误
3. 一辆汽车每小时行驶 60 千米，行驶 120 千米需要几小时？
答：2 小时
（10分）得10分
"""


def test_fallback_question_split():
    items = extract_questions_fallback(OCR_EXAM)
    assert len(items) == 3
    assert items[0]["order"] == 1
    assert "2x + 3" in items[0]["question_text"]
    assert "120 千米" in items[2]["question_text"]


def test_analyze_without_llm_creates_candidates(db_session, teacher, sample_setup):
    material = Material(
        title="期中试卷扫描", material_type="EXAM",
        textbook_version="人教版", grade="初一", semester=1,
        filename="exam.png", rel_path="data/materials/none.png",
        sha256="hist123", mime_type="image/png", size_bytes=10,
        ocr_text=OCR_EXAM,
    )
    db_session.add(material)
    db_session.commit()

    student = sample_setup["student"]
    assessment = analyze_history(
        db_session, material=material, student_id=student.id,
        exam_title="七年级数学期中", exam_date=date(2026, 6, 1), user=teacher,
    )
    db_session.commit()
    assert assessment.status == "analyzed"
    assert assessment.analysis_json["extracted_by"] == "fallback"
    assert len(assessment.questions) == 3
    q2 = assessment.questions[1]
    assert "3(x-1)" in q2.question_text
    assert q2.status == "candidate"


def test_confirm_creates_evidence_and_updates_state(db_session, teacher, sample_setup):
    material = Material(
        title="期中试卷扫描", material_type="EXAM",
        textbook_version="人教版", grade="初一", semester=1,
        filename="exam.png", rel_path="data/materials/none.png",
        sha256="hist456", mime_type="image/png", size_bytes=10,
        ocr_text=OCR_EXAM,
    )
    db_session.add(material)
    db_session.commit()
    student = sample_setup["student"]
    assessment = analyze_history(
        db_session, material=material, student_id=student.id,
        exam_title="期中", user=teacher,
    )
    db_session.commit()

    q1, q2, q3 = assessment.questions
    payloads = [
        # parent fixes the knowledge point + normalized score for Q1
        {"id": q1.id, "knowledge_point_name": "解方程", "score": 100.0},
        # Q2: wrong answer, modeling error — parent overrides error type
        {"id": q2.id, "knowledge_point_name": "去括号", "score": 40.0,
         "error_type": "SIGN_ERROR"},
        # Q3: no KP given by parent -> skipped
        {"id": q3.id},
    ]
    result = confirm_history(db_session, assessment, item_payloads=payloads, user=teacher)
    db_session.commit()
    assert result["evidence_created"] == 2
    assert result["skipped"] == 1

    evidence = (
        db_session.query(LearningEvidence)
        .filter_by(student_id=student.id, source_type="HISTORICAL")
        .all()
    )
    assert len(evidence) == 2
    by_kp = {e.knowledge_point_name: e for e in evidence}
    assert by_kp["解方程"].correct is True
    assert by_kp["去括号"].correct is False
    assert by_kp["去括号"].error_type == "SIGN_ERROR"

    db_session.refresh(q3)
    assert q3.status == "candidate"  # untouched

    # knowledge states updated from historical evidence
    states = (
        db_session.query(StudentKnowledgeState)
        .filter_by(student_id=student.id)
        .all()
    )
    kp_names = set()
    for st in states:
        kp = db_session.get(KnowledgePoint, st.knowledge_point_id)
        kp_names.add(kp.name)
    assert {"解方程", "去括号"} <= kp_names

    # confirm is boundary-guarded: already-confirmed items are skipped
    result2 = confirm_history(db_session, assessment, item_payloads=payloads[:2], user=teacher)
    assert result2["evidence_created"] == 0
    assert result2["skipped"] == 2


def test_analyze_material_runs_ocr_first(db_session, teacher, sample_setup, monkeypatch):
    """If the material has no OCR text yet, analyze_history triggers OCR path."""
    material = Material(
        title="未OCR试卷", material_type="EXAM",
        filename="exam.png", rel_path="data/materials/missing.png",
        sha256="hist789", mime_type="image/png", size_bytes=10,
    )
    db_session.add(material)
    db_session.commit()

    import app.services.material_import as material_import

    monkeypatch.setattr(
        material_import, "analyze_material",
        lambda db, m, user: setattr(m, "ocr_text", "1. 题目一 \n2. 题目二") or m,
    )
    student = sample_setup["student"]
    assessment = analyze_history(
        db_session, material=material, student_id=student.id,
        exam_title="OCR-first", user=teacher,
    )
    db_session.commit()
    assert material.ocr_text == "1. 题目一 \n2. 题目二"
    assert len(assessment.questions) == 2
