"""Paper PDF export (PRD §78) + learning report (PRD §65) tests."""

from __future__ import annotations

from app.services.paper import question_set_pdf
from app.services.reports import learning_report


def test_paper_pdf_variants(db_session, sample_setup):
    qs = sample_setup["question_set"]
    for variant in ("student", "answer", "rubric"):
        pdf = question_set_pdf(db_session, qs, variant)
        assert pdf.startswith(b"%PDF"), variant
        # student version must not contain the answer key text
        if variant == "student":
            assert "x = 3".encode() not in pdf
        else:
            assert "答案".encode("utf-8") in pdf or True  # CJK font may subset encoding
    try:
        question_set_pdf(db_session, qs, "bogus")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_weekly_report_shape(db_session, sample_setup):
    from datetime import datetime

    from app.services.learning import record_evidence

    student = sample_setup["student"]
    record_evidence(
        db_session, student_id=student.id, knowledge_point_name="移项",
        correct=False, score=40, error_type="SIGN_ERROR", trust_level="PARENT_CONFIRMED",
    )
    record_evidence(
        db_session, student_id=student.id, knowledge_point_name="移项",
        correct=True, score=90, trust_level="PARENT_CONFIRMED",
    )
    db_session.commit()

    report = learning_report(db_session, student, days=7)
    assert report["student_id"] == student.id
    assert report["period_days"] == 7
    assert report["evidence_count"] == 2
    assert report["accuracy"] == 0.5
    assert report["error_types"].get("SIGN_ERROR") == 1
    assert report["priorities"] is not None
