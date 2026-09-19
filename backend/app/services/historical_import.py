"""Historical assessment import service (PRD §54–55).

Pipeline:
    scan OCR -> question/answer/score/annotation recovery (LLM, deterministic
    fallback) -> parent review -> LearningEvidence (PARENT_CONFIRMED) ->
    knowledge state update.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.historical import HistoricalAssessment, HistoricalQuestion
from app.models.materials import Material
from app.services.learning import ERROR_PATTERNS, record_evidence

logger = logging.getLogger(__name__)

# Deterministic fallback: split OCR text on numbered questions ("1." "2、" "12．")
_QUESTION_SPLIT_RE = re.compile(r"^\s*(\d{1,2})\s*[.、．)）]\s+", re.MULTILINE)


def extract_questions_fallback(ocr_text: str) -> list[dict]:
    """Split OCR text into numbered question blocks (answers/KP unknown)."""
    text = (ocr_text or "").strip()
    if not text:
        return []
    matches = list(_QUESTION_SPLIT_RE.finditer(text))
    if not matches:
        return [{"order": 1, "question_text": text[:500], "confidence": 0.2}]
    items: list[dict] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        if not block:
            continue
        items.append(
            {
                "order": int(m.group(1)),
                "question_text": block[:500],
                "confidence": 0.2,
            }
        )
    return items[:50]


def analyze_history(
    db: Session,
    *,
    material: Material,
    student_id: int,
    exam_title: str,
    exam_date=None,
    user=None,
) -> HistoricalAssessment:
    """OCR the material and recover question candidates for review."""
    if not material.ocr_text:
        from app.services.material_import import analyze_material

        analyze_material(db, material, user)  # runs OCR + chapter extraction
        db.flush()

    ocr_text = material.ocr_text or ""
    items: Optional[list[dict]] = None
    llm_run_id: Optional[int] = None
    extracted_by = "fallback"
    if ocr_text.strip():
        try:
            from app.services.llm import stage_history_analysis  # lazy

            items, llm_run_id = stage_history_analysis(db, ocr_text=ocr_text, user=user)
            if items:
                extracted_by = "llm"
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM history analysis failed: %s", exc)
    if not items:
        items = extract_questions_fallback(ocr_text)

    assessment = HistoricalAssessment(
        material_id=material.id,
        student_id=student_id,
        exam_title=exam_title[:128],
        exam_date=exam_date,
        ocr_text=ocr_text,
        analysis_json={"extracted_by": extracted_by, "item_count": len(items)},
        llm_run_id=llm_run_id,
        created_by=user.id if user else None,
    )
    db.add(assessment)
    db.flush()
    order_seq = 0
    for it in items[:50]:
        if not isinstance(it, dict):
            continue
        error_type = it.get("error_type")
        if error_type and error_type not in ERROR_PATTERNS:
            error_type = None
        order_seq += 1
        try:
            order = int(it.get("order") or order_seq)
        except (TypeError, ValueError):
            order = order_seq
        db.add(
            HistoricalQuestion(
                assessment_id=assessment.id,
                order=order,
                question_text=str(it.get("question_text") or "").strip() or "（未能识别题干）",
                student_answer=_clean(it.get("student_answer")),
                score=_float(it.get("score")),
                max_score=_float(it.get("max_score")),
                annotation=_clean(it.get("annotation")),
                knowledge_point_name=_clean(it.get("knowledge_point")),
                error_type=error_type,
                confidence=_float(it.get("confidence")),
                status="candidate",
            )
        )
    db.flush()
    return assessment


def confirm_history(
    db: Session,
    assessment: HistoricalAssessment,
    *,
    item_payloads: list[dict[str, Any]],
    user=None,
) -> dict:
    """Parent-confirmed items become official learning evidence (PRD §55).

    Payload per item: {id, knowledge_point_name, correct?, score?, error_type?}
    where score is 0-100 (already normalized by the parent/review UI).
    """
    created = 0
    skipped = 0
    by_id = {q.id: q for q in assessment.questions}
    for payload in item_payloads:
        try:
            qid = int(payload.get("id"))
        except (TypeError, ValueError):
            continue
        q = by_id.get(qid)
        if not q or q.status != "candidate":
            skipped += 1
            continue

        kp_name = (payload.get("knowledge_point_name") or q.knowledge_point_name or "").strip()
        if not kp_name:
            skipped += 1
            continue

        score = _float(payload.get("score"))
        if score is None and q.score is not None and q.max_score:
            score = round(max(0.0, min(100.0, q.score / q.max_score * 100.0)), 1)
        correct = payload.get("correct")
        if correct is None:
            correct = (score or 0.0) >= 60.0 if score is not None else True

        error_type = payload.get("error_type") or q.error_type
        if error_type and error_type not in ERROR_PATTERNS:
            error_type = None

        evidence = record_evidence(
            db,
            student_id=assessment.student_id,
            knowledge_point_name=kp_name,
            correct=bool(correct),
            score=score,
            difficulty=None,
            error_type=error_type,
            feedback=q.annotation or payload.get("comment"),
            confidence=q.confidence,
            trust_level="PARENT_CONFIRMED",
            source_type="HISTORICAL",
            observed_by=user.id if user else None,
            created_at=assessment.exam_date,
        )
        q.evidence_id = evidence.id
        q.status = "confirmed"
        if payload.get("knowledge_point_name"):
            q.knowledge_point_name = kp_name
        if score is not None:
            q.score = score
        created += 1

    remaining = (
        db.query(HistoricalQuestion)
        .filter(HistoricalQuestion.assessment_id == assessment.id,
                HistoricalQuestion.status == "candidate")
        .count()
    )
    assessment.status = "confirmed" if remaining == 0 else "analyzed"
    db.flush()
    return {"evidence_created": created, "skipped": skipped}


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in ("", "null", "none", "unknown", "不可读"):
        return None
    return text[:2000]


def _float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
