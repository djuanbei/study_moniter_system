"""Knowledge-base incremental update (PRD §69).

Analysis sources (§69): 教材 (chapter KP lists), 历史题目/学生错误/新题目
(bank questions + evidence referencing KP names missing from the table),
家长反馈 (parent feedback names).

Candidate types: ADD | MERGE | DEPRECATE (MODYFY/SPLIT are parent-entered
via the same review table). Everything requires parent confirmation —
auto_publish is never assumed (§87 auto_publish: false).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models.assignments import Question
from app.models.learning import (
    KnowledgePoint,
    KnowledgeUpdateCandidate,
    LearningEvidence,
    ParentFeedback,
    StudentKnowledgeState,
)
from app.models.students import Chapter

logger = logging.getLogger(__name__)


def _norm_name(name: str) -> str:
    return re.sub(r"[\s　·]", "", (name or "").lower())


def analyze_knowledge(db: Session) -> dict:
    """Deterministic analysis for §69 candidates."""
    kps = {kp.name: kp for kp in db.query(KnowledgePoint).all()}
    norm_map: dict[str, list[str]] = {}
    for name in kps:
        norm_map.setdefault(_norm_name(name), []).append(name)

    chapter_names: set[str] = set()
    for ch in db.query(Chapter).all():
        for kp in ch.knowledge_points or []:
            if str(kp).strip():
                chapter_names.add(str(kp).strip())

    # names referenced by evidence / bank questions / parent feedback but
    # missing from the knowledge point table
    evidence_names: set[str] = set()
    for (name,) in db.query(LearningEvidence.knowledge_point_name).distinct().all():
        if name and name.strip() and name != "未分类":
            evidence_names.add(name.strip())
    for q in db.query(Question).all():
        for kp in q.knowledge_points or []:
            if str(kp).strip() and str(kp).strip() != "未分类":
                evidence_names.add(str(kp).strip())
    for fb in db.query(ParentFeedback).all():
        if fb.knowledge_point_name and fb.knowledge_point_name.strip():
            evidence_names.add(fb.knowledge_point_name.strip())

    missing_adds = sorted(
        n for n in (chapter_names | evidence_names)
        if n not in kps and _norm_name(n) not in norm_map
    )

    # MERGE: distinct names normalizing to the same key (e.g. 全角/空格 variants)
    merges: list[dict] = []
    for key, names in norm_map.items():
        if len(names) > 1:
            keep = min(names, key=lambda n: len(n))
            merges.append({"keep": keep, "merge": [n for n in names if n != keep]})

    # DEPRECATE: KPs with no evidence, no bank questions, not in any chapter
    unused: list[str] = []
    for name, kp in kps.items():
        if kp.status != "active":
            continue
        has_evidence = (
            db.query(LearningEvidence.id)
            .filter(LearningEvidence.knowledge_point_id == kp.id)
            .first()
            is not None
        )
        if has_evidence or name in chapter_names:
            continue
        unused.append(name)

    return {
        "add_candidates": missing_adds[:20],
        "merge_candidates": merges[:10],
        "deprecate_candidates": unused[:20],
        "kp_total": len(kps),
    }


def generate_knowledge_candidates(db: Session, *, batch_size: int = 20) -> dict:
    """Create pending candidates from the §69 analysis (idempotent per source)."""
    analysis = analyze_knowledge(db)
    adds = merges = deprecates = 0

    for name in analysis["add_candidates"][:batch_size]:
        pending_adds = (
            db.query(KnowledgeUpdateCandidate)
            .filter(KnowledgeUpdateCandidate.candidate_type == "ADD",
                    KnowledgeUpdateCandidate.status == "pending")
            .all()
        )
        if any((c.payload or {}).get("name") == name for c in pending_adds):
            continue
        from_chapter = name in _chapter_names(db)
        from_evidence = (
            db.query(LearningEvidence.id)
            .filter(LearningEvidence.knowledge_point_name == name)
            .first()
            is not None
        )
        source = "教材章节" if from_chapter else "学生练习记录"
        if from_chapter and from_evidence:
            source = "教材章节 + 学生练习"
        db.add(
            KnowledgeUpdateCandidate(
                candidate_type="ADD",
                payload={"name": name, "description": f"来自{source}的知识点"},
                rationale=f"「{name}」出现在{source}中，但知识库中不存在（§69）",
                status="pending",
            )
        )
        adds += 1

    for m in analysis["merge_candidates"][:batch_size]:
        keep_kp = kps.get(m["keep"])
        exists = (
            db.query(KnowledgeUpdateCandidate)
            .filter(KnowledgeUpdateCandidate.candidate_type == "MERGE",
                    KnowledgeUpdateCandidate.status == "pending",
                    KnowledgeUpdateCandidate.payload["keep"] == m["keep"])
            .first()
        )
        if exists or not keep_kp:
            continue
        db.add(
            KnowledgeUpdateCandidate(
                candidate_type="MERGE",
                target_kp_id=keep_kp.id,
                payload={"keep": m["keep"], "merge": m["merge"]},
                rationale=(
                    f"同名变体知识点：{', '.join(m['merge'])} 将并入「{m['keep']}」"
                    "（练习记录与掌握度一并迁移，§69）"
                ),
                status="pending",
            )
        )
        merges += 1

    for name in analysis["deprecate_candidates"][:batch_size]:
        kp = (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.name == name)
            .first()
        )
        exists = (
            db.query(KnowledgeUpdateCandidate)
            .filter(KnowledgeUpdateCandidate.candidate_type == "DEPRECATE",
                    KnowledgeUpdateCandidate.status == "pending",
                    KnowledgeUpdateCandidate.target_kp_id == kp.id)
            .first()
        )
        if exists or not kp:
            continue
        db.add(
            KnowledgeUpdateCandidate(
                candidate_type="DEPRECATE",
                target_kp_id=kp.id,
                payload={"reason": "无练习记录、无题库引用、不在任何章节"},
                rationale=f"「{name}」从未被使用，建议废弃（§69）",
                status="pending",
            )
        )
        deprecates += 1

    db.flush()
    return {"adds": adds, "merges": merges, "deprecates": deprecates}


def apply_knowledge_candidate(db: Session, candidate: KnowledgeUpdateCandidate, user=None) -> dict:
    if candidate.status != "pending":
        raise ValueError("该候选已处理")

    ctype = candidate.candidate_type

    if ctype == "ADD":
        name = str(candidate.payload.get("name") or "").strip()
        if not name:
            candidate.status = "rejected"
            candidate.review_note = "名称为空"
            return {"applied": False}
        existing = db.query(KnowledgePoint).filter(KnowledgePoint.name == name).first()
        if existing:
            candidate.status = "approved"
            candidate.review_note = f"已存在 #{existing.id}，无需新增"
            return {"applied": False, "kp_id": existing.id}
        kp = KnowledgePoint(
            name=name,
            description=candidate.payload.get("description"),
            grade=candidate.payload.get("grade"),
            textbook_version=candidate.payload.get("textbook_version"),
        )
        db.add(kp)
        db.flush()
        candidate.status = "approved"
        candidate.review_note = f"已新增 #{kp.id}"
        return {"applied": True, "kp_id": kp.id}

    if ctype == "MERGE":
        keep_id = candidate.target_kp_id
        keep = db.get(KnowledgePoint, keep_id) if keep_id else None
        if not keep:
            candidate.status = "rejected"
            candidate.review_note = "目标知识点不存在"
            return {"applied": False}
        moved = 0
        for name in candidate.payload.get("merge", []):
            sources = db.query(KnowledgePoint).filter(KnowledgePoint.name == name).all()
            for src in sources:
                if src.id == keep.id:
                    continue
                # move references
                for table, col in (
                    (LearningEvidence, "knowledge_point_id"),
                    (StudentKnowledgeState, "knowledge_point_id"),
                ):
                    rows = db.query(table).filter_by(**{col: src.id}).all()
                    for row in rows:
                        setattr(row, col, keep.id)
                        moved += 1
                src.status = "deprecated"
        candidate.status = "approved"
        candidate.review_note = f"已并入 #{keep.id}（迁移 {moved} 条引用）"
        return {"applied": True, "kp_id": keep.id, "moved": moved}

    if ctype == "DEPRECATE":
        kp = db.get(KnowledgePoint, candidate.target_kp_id) if candidate.target_kp_id else None
        if not kp:
            candidate.status = "rejected"
            candidate.review_note = "知识点不存在"
            return {"applied": False}
        kp.status = "deprecated"
        candidate.status = "approved"
        candidate.review_note = f"已废弃 #{kp.id}"
        return {"applied": True, "kp_id": kp.id}

    if ctype == "MODIFY":
        kp = db.get(KnowledgePoint, candidate.target_kp_id) if candidate.target_kp_id else None
        if not kp:
            candidate.status = "rejected"
            return {"applied": False}
        for key in ("name", "description"):
            if candidate.payload.get(key):
                setattr(kp, key, candidate.payload[key])
        candidate.status = "approved"
        return {"applied": True, "kp_id": kp.id}

    raise ValueError(f"unknown candidate type: {ctype}")


def _chapter_names(db: Session) -> set[str]:
    names: set[str] = set()
    for ch in db.query(Chapter).all():
        for kp in ch.knowledge_points or []:
            if str(kp).strip():
                names.add(str(kp).strip())
    return names
