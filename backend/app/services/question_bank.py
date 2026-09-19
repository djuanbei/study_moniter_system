"""Question bank service (PRD §36, §39–41): publish, versioning, duplicates,
similar-question search.

Similar questions (§41) rank candidates by a blend of:
    - knowledge-point overlap (same knowledge point / skill)
    - prompt n-gram similarity (same solution structure, heuristic)
    - difficulty closeness (easy/hard transfer neighbours)
No external embedding service is required (CPU-only constraint, §9).
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models.question_bank import QuestionBankItem, QuestionVersion


def normalize_prompt(text: str) -> str:
    return re.sub(r"[\s，。、；：？！,.:;?!'\"()（）\[\]【】]+", "", (text or "").lower())


def duplicate_hash(prompt: str) -> str:
    return hashlib.sha256(normalize_prompt(prompt).encode("utf-8")).hexdigest()


def find_duplicate(db: Session, prompt: str, exclude_id: Optional[int] = None) -> Optional[QuestionBankItem]:
    h = duplicate_hash(prompt)
    q = db.query(QuestionBankItem).filter(
        QuestionBankItem.duplicate_hash == h,
        QuestionBankItem.status == "active",
    )
    if exclude_id:
        q = q.filter(QuestionBankItem.id != exclude_id)
    return q.first()


def _snapshot(item: QuestionBankItem) -> dict:
    return {
        "subject": item.subject,
        "grade": item.grade,
        "chapter_id": item.chapter_id,
        "knowledge_points": list(item.knowledge_points or []),
        "difficulty": item.difficulty,
        "question_type": item.question_type,
        "prompt": item.prompt,
        "answer": item.answer,
        "rubric": item.rubric,
        "estimated_time": item.estimated_time,
        "source": item.source,
    }


def publish_question(
    db: Session,
    *,
    fields: dict,
    source: str = "AI",
    user_id: Optional[int] = None,
    change_note: Optional[str] = None,
    allow_duplicate: bool = False,
) -> tuple[QuestionBankItem, bool]:
    """Publish a new bank question as v1. Returns (item, is_duplicate).

    Raises nothing on duplicates — the caller decides (§36: duplicate
    detection warns before parent review).
    """
    prompt = str(fields.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    dup = find_duplicate(db, prompt)
    if dup and not allow_duplicate:
        return dup, True

    item = QuestionBankItem(
        subject=str(fields.get("subject") or "math"),
        grade=fields.get("grade"),
        chapter_id=fields.get("chapter_id"),
        knowledge_points=list(fields.get("knowledge_points") or []),
        difficulty=str(fields.get("difficulty") or "medium"),
        question_type=str(fields.get("question_type") or "thinking"),
        prompt=prompt,
        answer=fields.get("answer"),
        rubric=fields.get("rubric"),
        estimated_time=fields.get("estimated_time"),
        source=source,
        duplicate_hash=duplicate_hash(prompt),
        version=1,
        created_by=user_id,
    )
    db.add(item)
    db.flush()
    db.add(
        QuestionVersion(
            question_id=item.id,
            version=1,
            snapshot=_snapshot(item),
            change_note=change_note or "发布 v1",
            published_by=user_id,
            published_at=item.created_at,
        )
    )
    db.flush()
    return item, False


def update_question(
    db: Session,
    item: QuestionBankItem,
    *,
    fields: dict,
    user_id: Optional[int] = None,
    change_note: Optional[str] = None,
) -> QuestionBankItem:
    """Edit = publish a new immutable version (§40). Old versions untouched."""
    allowed = ("subject", "grade", "chapter_id", "knowledge_points", "difficulty",
               "question_type", "prompt", "answer", "rubric", "estimated_time")
    for key in allowed:
        if key in fields and fields[key] is not None:
            setattr(item, key, fields[key])
    item.duplicate_hash = duplicate_hash(item.prompt)
    item.version += 1
    db.flush()
    db.add(
        QuestionVersion(
            question_id=item.id,
            version=item.version,
            snapshot=_snapshot(item),
            change_note=change_note or f"更新 v{item.version}",
            published_by=user_id,
            published_at=item.updated_at,
        )
    )
    db.flush()
    return item


# ---------------------------------------------------------------------------
# Similar questions (§41)
# ---------------------------------------------------------------------------

def _bigrams(text: str) -> set[str]:
    t = normalize_prompt(text)
    return {t[i : i + 2] for i in range(len(t) - 1)} if len(t) > 1 else {t}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _difficulty_distance(a: str, b: str) -> float:
    order = {"easy": 0, "medium": 1, "hard": 2}
    return abs(order.get(a, 1) - order.get(b, 1))


def similar_questions(
    db: Session, item: QuestionBankItem, limit: int = 5
) -> list[dict]:
    """Rank active bank items by learning-function similarity (§41)."""
    kp_a = {str(k).strip() for k in (item.knowledge_points or [])}
    grams_a = _bigrams(item.prompt)
    results = []
    candidates = (
        db.query(QuestionBankItem)
        .filter(QuestionBankItem.status == "active", QuestionBankItem.id != item.id)
        .all()
    )
    for cand in candidates:
        kp_b = {str(k).strip() for k in (cand.knowledge_points or [])}
        kp_overlap = kp_a & kp_b
        kp_jaccard = _jaccard(kp_a, kp_b)
        prompt_sim = _jaccard(grams_a, _bigrams(cand.prompt))
        diff_dist = _difficulty_distance(item.difficulty, cand.difficulty)
        score = 0.5 * kp_jaccard + 0.3 * prompt_sim + 0.2 * (1 - diff_dist / 2)
        relations = []
        if kp_overlap:
            relations.append("同知识点")
        if cand.question_type == item.question_type:
            relations.append("同题型")
        else:
            relations.append("不同题型")
        if diff_dist == 0:
            relations.append("同难度")
        elif diff_dist == 1:
            relations.append("难度相邻迁移")
        else:
            relations.append("困难迁移")
        if prompt_sim > 0.6:
            relations.append("结构相似")
        results.append(
            {
                "id": cand.id,
                "prompt": cand.prompt,
                "question_type": cand.question_type,
                "difficulty": cand.difficulty,
                "knowledge_points": list(kp_b),
                "score": round(score, 4),
                "relations": relations,
            }
        )
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


def publish_from_question_row(db: Session, q, user_id: Optional[int] = None,
                              allow_duplicate: bool = False) -> tuple[QuestionBankItem, bool]:
    """Publish a generated `questions` table row into the bank (§36 flow)."""
    return publish_question(
        db,
        fields={
            "subject": q.subject,
            "grade": None,
            "knowledge_points": list(q.knowledge_points or []),
            "difficulty": q.difficulty,
            "question_type": q.qtype,
            "prompt": q.prompt,
            "answer": q.answer_key,
            "rubric": q.rubric,
            "estimated_time": q.estimated_minutes,
        },
        source="AI",
        user_id=user_id,
        allow_duplicate=allow_duplicate,
    )
