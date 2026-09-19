"""Question bank incremental update (PRD §68).

    analyze bank coverage / student errors / duplicates
      -> LLM generates candidate questions for gaps (ADD)
      -> deterministic DEPRECATE candidates for duplicate pairs
      -> duplicate detection + validation on every candidate
      -> parent review (approve/reject)
      -> approved candidates mutate the question bank
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.learning import KnowledgePoint, LearningEvidence, StudentKnowledgeState
from app.models.question_bank import BankUpdateCandidate, QuestionBankItem
from app.services.question_bank import (
    _bigrams,
    _jaccard,
    duplicate_hash,
    find_duplicate,
    publish_question,
    update_question,
)

logger = logging.getLogger(__name__)

MIN_BANK_COVERAGE = 2  # questions per knowledge point considered "covered"


def analyze_gaps(db: Session) -> dict:
    """Deterministic analysis inputs (§68): coverage, errors, duplicates."""
    kps = db.query(KnowledgePoint).filter(KnowledgePoint.status == "active").all()
    bank = db.query(QuestionBankItem).filter(QuestionBankItem.status == "active").all()
    by_kp: dict[str, list[QuestionBankItem]] = {}
    for item in bank:
        for kp in item.knowledge_points or []:
            by_kp.setdefault(str(kp).strip(), []).append(item)

    gaps: list[dict] = []
    for kp in kps:
        items = by_kp.get(kp.name, [])
        if len(items) < MIN_BANK_COVERAGE:
            # student error context (§68: 学生错误/知识缺口)
            st = (
                db.query(StudentKnowledgeState)
                .filter(StudentKnowledgeState.knowledge_point_id == kp.id)
                .order_by(StudentKnowledgeState.mastery_score.asc())
                .first()
            )
            gaps.append(
                {
                    "knowledge_point": kp.name,
                    "grade": kp.grade,
                    "bank_count": len(items),
                    "mastery": st.mastery_score if st else None,
                    "suggested_difficulty": (
                        "easy" if (st is None or st.mastery_score < 0.4) else
                        "medium" if st.mastery_score < 0.7 else "hard"
                    ),
                }
            )
    gaps.sort(key=lambda g: (g["bank_count"], g["mastery"] if g["mastery"] is not None else 1))

    # duplicate pairs (§68: 重复率) — near-identical prompts share a hash or
    # have very high bigram overlap
    duplicates: list[dict] = []
    seen: dict[str, QuestionBankItem] = {}
    exact_hash = {}
    for item in bank:
        h = item.duplicate_hash
        if h in exact_hash:
            duplicates.append({"keep_id": exact_hash[h].id, "dup_id": item.id,
                               "reason": "题干完全相同"})
        else:
            exact_hash[h] = item
    # near-duplicates: >0.9 bigram overlap, same KP
    for i, a in enumerate(bank):
        for b in bank[i + 1:]:
            if a.id == b.id or any(
                (d["keep_id"], d["dup_id"]) in ((a.id, b.id), (b.id, a.id)) for d in duplicates
            ):
                continue
            shared = len({str(k) for k in (a.knowledge_points or [])} & {str(k) for k in (b.knowledge_points or [])})
            sim = _jaccard(_bigrams(a.prompt), _bigrams(b.prompt))
            if sim > 0.9 and shared > 0:
                duplicates.append({"keep_id": min(a.id, b.id), "dup_id": max(a.id, b.id),
                                   "reason": f"题干相似度 {sim:.0%}"})

    return {
        "gaps": gaps[:10],
        "duplicates": duplicates[:10],
        "bank_size": len(bank),
        "kp_total": len(kps),
        "covered_kp": sum(1 for kp in kps if len(by_kp.get(kp.name, [])) >= MIN_BANK_COVERAGE),
    }


def generate_candidates(
    db: Session,
    *,
    batch_size: int = 3,
    user=None,
) -> dict:
    """Run analysis, generate candidates (§68). LLM ADDs; rule DEPRECATEs."""
    analysis = analyze_gaps(db)
    created_adds = 0
    created_deprecates = 0

    # DEPRECATE candidates for duplicate pairs (deterministic)
    for dup in analysis["duplicates"]:
        exists = (
            db.query(BankUpdateCandidate)
            .filter(
                BankUpdateCandidate.candidate_type == "DEPRECATE",
                BankUpdateCandidate.target_bank_id == dup["dup_id"],
                BankUpdateCandidate.status == "pending",
            )
            .first()
        )
        if exists:
            continue
        db.add(
            BankUpdateCandidate(
                candidate_type="DEPRECATE",
                target_bank_id=dup["dup_id"],
                payload={"reason": dup["reason"], "keep_id": dup["keep_id"]},
                rationale=f"与题目 #{dup['keep_id']} 重复：{dup['reason']}（§68 重复率分析）",
                status="pending",
            )
        )
        created_deprecates += 1

    # ADD candidates for coverage gaps (LLM per §68)
    user_obj = user
    for gap in analysis["gaps"][:batch_size]:
        try:
            from app.services.llm import stage_bank_question  # lazy

            existing_prompts = [
                i.prompt
                for i in db.query(QuestionBankItem)
                .filter(QuestionBankItem.status == "active")
                .limit(30)
                .all()
                if gap["knowledge_point"] in (i.knowledge_points or [])
            ]
            fields = stage_bank_question(
                db,
                knowledge_point=gap["knowledge_point"],
                grade=gap["grade"],
                difficulty=gap["suggested_difficulty"],
                estimated_time=5,
                existing_prompts=existing_prompts,
                user=user_obj,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("bank candidate generation failed: %s", exc)
            fields = None
        if not fields:
            continue

        # §68 flow: duplicate detection + validation before review
        dup = find_duplicate(db, fields["prompt"])
        notes = []
        if not fields.get("rubric"):
            notes.append("缺少评分标准")
        if not fields.get("answer"):
            notes.append("缺少答案")
        candidate = BankUpdateCandidate(
            candidate_type="ADD",
            knowledge_point=gap["knowledge_point"],
            payload={
                **fields,
                "grade": gap["grade"],
                "knowledge_points": [gap["knowledge_point"]],
                "source": "AI",
            },
            rationale=(
                f"知识点「{gap['knowledge_point']}」题库仅 {gap['bank_count']} 题"
                + (f"，学生掌握度 {int(gap['mastery'] * 100)}%" if gap["mastery"] is not None else "")
                + "（§68 覆盖/错误分析）"
            ),
            duplicate_of_id=dup.id if dup else None,
            validation_notes="；".join(notes) or None,
            status="pending",
        )
        db.add(candidate)
        created_adds += 1

    db.flush()
    return {
        "adds": created_adds,
        "deprecates": created_deprecates,
        "gaps_found": len(analysis["gaps"]),
    }


def apply_candidate(db: Session, candidate: BankUpdateCandidate, user=None) -> dict:
    """Parent-approved candidate mutates the bank (§68 last step)."""
    if candidate.status != "pending":
        raise ValueError("该候选已处理")

    if candidate.candidate_type == "ADD":
        if candidate.duplicate_of_id:
            candidate.status = "rejected"
            candidate.review_note = "题干与题库重复，自动拒绝"
            db.flush()
            return {"applied": False, "reason": "duplicate"}
        item, is_dup = publish_question(
            db,
            fields=candidate.payload,
            source=str(candidate.payload.get("source") or "AI"),
            user_id=user.id if user else None,
            allow_duplicate=False,
        )
        if is_dup:
            candidate.status = "rejected"
            candidate.review_note = "题干与题库重复，自动拒绝"
            db.flush()
            return {"applied": False, "reason": "duplicate", "bank_id": item.id}
        candidate.status = "approved"
        candidate.review_note = f"已入库 #{item.id} v{item.version}"
        db.flush()
        return {"applied": True, "bank_id": item.id}

    if candidate.candidate_type == "DEPRECATE":
        item = db.get(QuestionBankItem, candidate.target_bank_id) if candidate.target_bank_id else None
        if item:
            item.status = "deprecated"
        candidate.status = "approved"
        candidate.review_note = f"已废弃 #{candidate.target_bank_id}"
        db.flush()
        return {"applied": True, "deprecated_id": candidate.target_bank_id}

    if candidate.candidate_type in ("MODIFY", "REPLACE"):
        item = db.get(QuestionBankItem, candidate.target_bank_id) if candidate.target_bank_id else None
        if not item:
            candidate.status = "rejected"
            candidate.review_note = "目标题目不存在"
            return {"applied": False, "reason": "missing target"}
        if candidate.candidate_type == "REPLACE":
            item.status = "deprecated"
            new_item, is_dup = publish_question(
                db, fields=candidate.payload, source="AI",
                user_id=user.id if user else None, allow_duplicate=False,
            )
            candidate.status = "approved"
            candidate.review_note = f"已替换为 #{new_item.id}"
            db.flush()
            return {"applied": not is_dup, "bank_id": new_item.id}
        item = update_question(
            db, item, fields=candidate.payload, user_id=user.id if user else None,
            change_note="AI 修改候选（§68 家长确认）",
        )
        candidate.status = "approved"
        candidate.review_note = f"已更新 v{item.version}"
        db.flush()
        return {"applied": True, "bank_id": item.id, "version": item.version}

    raise ValueError(f"unknown candidate type: {candidate.candidate_type}")
