"""Material import pipeline tests (PRD §19–21)."""

from __future__ import annotations

from app.models.learning import KnowledgePoint
from app.models.materials import Material
from app.models.students import Chapter
from app.services.material_import import (
    analyze_material,
    extract_chapters_fallback,
    publish_material,
)

OCR_SAMPLE = """第三章 一元一次方程
3.1 从算式到方程
方程的概念
等式的性质
3.2 解一元一次方程
移项
去括号
习题3.1
复习题
"""


def test_fallback_extraction():
    chapters = extract_chapters_fallback(OCR_SAMPLE)
    # "第三章" heading has no own KP lines before "3.1" starts, so the
    # fallback keeps only sections with knowledge points.
    assert len(chapters) == 2
    titles = " ".join(c["title"] for c in chapters)
    assert "一元一次方程" in titles  # via "3.2 解一元一次方程"
    all_kps = " ".join(" ".join(c["knowledge_points"]) for c in chapters)
    assert "移项" in all_kps
    assert "方程的概念" in all_kps
    # stopwords / exercise lines are not treated as knowledge points
    assert "习题3.1" not in all_kps
    assert "复习题" not in all_kps


def test_analyze_falls_back_without_llm(db_session, teacher, sample_setup):
    material = Material(
        title="扫描教材", material_type="TEXTBOOK",
        textbook_version="人教版", grade="初一", semester=1,
        filename="scan.png", rel_path="data/materials/none.png",
        sha256="abc123", mime_type="image/png", size_bytes=10,
        ocr_text=OCR_SAMPLE,
    )
    db_session.add(material)
    db_session.commit()

    analyze_material(db_session, material, teacher)
    db_session.commit()
    assert material.status == "analyzed"
    assert material.analysis_json["extracted_by"] == "fallback"
    chapters = material.analysis_json["chapters"]
    assert len(chapters) == 2


def test_publish_creates_chapters_and_kps(db_session, sample_setup):
    material = Material(
        title="扫描教材", material_type="TEXTBOOK",
        textbook_version="人教版", grade="初一", semester=1,
        filename="scan.png", rel_path="data/materials/none.png",
        sha256="def456", mime_type="image/png", size_bytes=10,
        ocr_text=OCR_SAMPLE,
        analysis_json={
            "extracted_by": "fallback",
            "chapters": [
                {"title": "扫描章节：方程与不等式", "knowledge_points": ["绝对值方程", "含参方程", "  ", "绝对值方程"]},
            ],
        },
    )
    db_session.add(material)
    db_session.commit()

    result = publish_material(db_session, material)
    db_session.commit()
    assert result["chapters_created"] == 1
    # "  " filtered out, "绝对值方程" deduplicated within the chapter
    assert result["knowledge_points_created"] == 2

    chapter = db_session.query(Chapter).filter_by(title="扫描章节：方程与不等式").first()
    assert chapter is not None
    assert chapter.grade == "初一"
    kp_names = {kp.name for kp in db_session.query(KnowledgePoint).filter_by(chapter_id=chapter.id).all()}
    assert {"绝对值方程", "含参方程"} <= kp_names


def test_material_upload_analyze_publish_api(db_session, client, csrf_headers, sample_setup, monkeypatch):
    """API-level: upload (1×1 PNG) -> analyze (fallback) -> publish."""
    import app.services.llm as llm_pkg

    def _no_llm(*args, **kwargs):
        raise RuntimeError("tests: llm disabled")

    monkeypatch.setattr(llm_pkg, "stage_material_analysis", _no_llm)
    # Smallest valid PNG
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d4944415478da63fcffff3f030005fe02fea72d1e480000000049454e44ae426082"
    )

    r = client.post("/api/materials", headers=csrf_headers, data={
        "title": "教材扫描",
        "material_type": "TEXTBOOK",
        "textbook_version": "人教版",
        "grade": "初一",
        "semester": "1",
    }, files={"file": ("scan.png", png, "image/png")})
    assert r.status_code == 200, r.text
    material = r.json()
    assert material["status"] == "uploaded"
    assert len(material["sha256"]) == 64

    # Empty OCR -> no chapters, but pipeline completes
    r = client.post(f"/api/materials/{material['id']}/analyze", headers=csrf_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "analyzed"

    r = client.post(f"/api/materials/{material['id']}/publish", headers=csrf_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "published"


def test_materials_teacher_only(db_session, client, sample_setup, student_user):
    """Students cannot access material endpoints (PRD §71 agent/parent boundary)."""
    student_user_obj, _student = student_user
    from app.deps import get_current_user

    client.app.dependency_overrides[get_current_user] = lambda: student_user_obj
    try:
        r = client.get("/api/materials")
        assert r.status_code == 403
        r = client.post("/api/materials/1/analyze", headers={"X-CSRF-Token": "test-token"})
        assert r.status_code == 403
    finally:
        client.app.dependency_overrides.pop(get_current_user, None)
