"""Material import pipeline (PRD §19–20).

    Upload -> immutable storage (sha256) -> OCR -> chapter extraction
           -> parent review -> Chapter + KnowledgePoint rows

Chapter extraction tries the LLM first (stage_material_analysis) and falls
back to a deterministic heading scanner (`第…章/节/课` lines) so the pipeline
works without a configured LLM.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config import resolve_path
from app.models.learning import KnowledgePoint
from app.models.materials import Material
from app.models.students import Chapter

logger = logging.getLogger(__name__)

# Deterministic fallback: textbook-style headings, e.g. "第三章 一元一次方程" / "1.2 移项"
_HEADING_RE = re.compile(
    r"^\s*(?:第\s*[一二三四五六七八九十百\d]+\s*[章节课单元]|\d+\.\d+[^，。;；\n]{0,30})\s*[:：]?\s*(.*)$"
)
_KP_STOPWORDS = {"练习", "习题", "复习题", "小结", "复习", "思考", "探究"}


def save_upload(*, raw: bytes, filename: str, mime_type: str) -> tuple[str, str]:
    """Store the file immutably under data/materials/. Returns (rel_path, sha256)."""
    sha = hashlib.sha256(raw).hexdigest()
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
    safe_stem = re.sub(r"[^\w\u4e00-\u9fff.-]", "_", Path(filename).stem)[:60] or "material"
    rel_dir = "data/materials"
    target_dir = resolve_path(rel_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    rel_path = f"{rel_dir}/{ts}_{sha[:8]}_{safe_stem}{Path(filename).suffix.lower()}"
    (resolve_path(rel_path)).write_bytes(raw)
    return rel_path, sha


def extract_chapters_fallback(ocr_text: str) -> list[dict]:
    """Scan OCR text for `第…章/节/课` / `1.2 …` headings deterministically."""
    chapters: list[dict] = []
    current: Optional[dict] = None
    for raw_line in (ocr_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _HEADING_RE.match(line)
        if m and len(line) <= 40:
            title = line.strip(" :：")
            current = {"title": title, "knowledge_points": []}
            chapters.append(current)
            continue
        if current is not None and 2 <= len(line) <= 24 and not any(w in line for w in _KP_STOPWORDS):
            cleaned = line.strip("•·-—.、 　")
            if cleaned and cleaned not in current["knowledge_points"]:
                current["knowledge_points"].append(cleaned)
    return [c for c in chapters if c["knowledge_points"]][:20]


def analyze_material(db: Session, material: Material, user) -> Material:
    """Run OCR (if needed) + chapter extraction; store candidates for review."""
    if not material.ocr_text:
        from app.services.ocr import ocr_image, ocr_pdf

        path = resolve_path(material.rel_path)
        try:
            if material.mime_type == "application/pdf":
                material.ocr_text = ocr_pdf(path)
            else:
                material.ocr_text = ocr_image(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Material OCR failed: %s", exc)
            material.ocr_text = material.ocr_text or ""

    analysis: Optional[dict] = None
    llm_run_id: Optional[int] = None
    if material.ocr_text and material.ocr_text.strip():
        try:
            from app.services.llm import stage_material_analysis  # lazy

            analysis, llm_run_id = stage_material_analysis(
                db,
                material_type=material.material_type,
                grade=material.grade,
                ocr_text=material.ocr_text,
                user=user,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM material analysis failed: %s", exc)

    if not analysis:
        chapters = extract_chapters_fallback(material.ocr_text)
        analysis = {"chapters": chapters, "extracted_by": "fallback"}
    else:
        analysis = {**analysis, "extracted_by": "llm"}

    material.analysis_json = analysis
    material.llm_run_id = llm_run_id
    material.status = "analyzed"
    db.flush()
    return material


def publish_material(db: Session, material: Material) -> dict:
    """Parent-confirmed publish: create Chapter + KnowledgePoint rows (PRD §20)."""
    analysis = material.analysis_json or {}
    chapters = [c for c in analysis.get("chapters", []) if isinstance(c, dict) and c.get("title")]
    created_chapters = 0
    created_kps = 0
    for idx, ch in enumerate(chapters, start=1):
        existing = (
            db.query(Chapter)
            .filter(
                Chapter.textbook_version == (material.textbook_version or "未指定教材"),
                Chapter.grade == (material.grade or "未指定"),
                Chapter.title == str(ch["title"])[:128],
            )
            .first()
        )
        if existing:
            chapter = existing
        else:
            chapter = Chapter(
                textbook_version=material.textbook_version or "未指定教材",
                grade=material.grade or "未指定",
                order=idx,
                title=str(ch["title"])[:128],
                knowledge_points=[],
                semester=material.semester,
            )
            db.add(chapter)
            db.flush()
            created_chapters += 1
        for kp_name in ch.get("knowledge_points", []) or []:
            if not isinstance(kp_name, str) or not kp_name.strip():
                continue
            kp = (
                db.query(KnowledgePoint)
                .filter(KnowledgePoint.name == kp_name.strip())
                .order_by(KnowledgePoint.id.asc())
                .first()
            )
            if kp is None:
                db.add(
                    KnowledgePoint(
                        name=kp_name.strip(),
                        grade=chapter.grade,
                        textbook_version=chapter.textbook_version,
                        chapter_id=chapter.id,
                    )
                )
                db.flush()  # visible to the dedupe query below (autoflush off)
                created_kps += 1
            elif kp.chapter_id is None:
                kp.chapter_id = chapter.id
    material.status = "published"
    db.flush()
    return {"chapters_created": created_chapters, "knowledge_points_created": created_kps}
