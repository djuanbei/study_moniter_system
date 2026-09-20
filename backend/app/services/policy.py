"""Phase-3 learning policy, adaptive sequencing, long-term path (PRD §94).

- Student-specific learning policy: aggregate InterventionOutcome rows to
  learn which intervention types actually move mastery for THIS student.
- Adaptive intervention sequencing: the plan builder consumes the policy to
  choose intervention types per day.
- Long-term learning path: a computed multi-phase roadmap over chapters,
  mastery and velocity (no new tables — derived on read).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.learning import (
    InterventionOutcome,
    KnowledgePoint,
    LearningObjective,
    LearningEvidence,
    StudentKnowledgeState,
    StudentKnowledgeStateHistory,
)
from app.models.students import Chapter

DEFAULT_EFFECTIVENESS = {  # sensible priors until outcome data exists (§63)
    "REVIEW": 0.06,
    "EXAMPLE": 0.08,
    "PRACTICE": 0.12,
    "REFLECTION": 0.04,
    "QUIZ": 0.0,
}
MIN_OUTCOMES_FOR_PERSONALIZATION = 3


def intervention_effectiveness(db: Session, student_id: int) -> dict[str, dict]:
    """avg mastery delta + sample count per intervention type for one student."""
    rows = (
        db.query(InterventionOutcome)
        .filter(InterventionOutcome.student_id == student_id,
                InterventionOutcome.delta.isnot(None))
        .all()
    )
    agg: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        agg[r.intervention_type].append(r.delta)
    result = {}
    for itype, deltas in agg.items():
        result[itype] = {
            "avg_delta": round(sum(deltas) / len(deltas), 4),
            "count": len(deltas),
        }
    return result


def learning_policy(db: Session, student_id: int) -> dict:
    """Student-specific policy (§94): preferred interventions + data coverage."""
    effectiveness = intervention_effectiveness(db, student_id)
    total = sum(v["count"] for v in effectiveness.values())
    personalized = total >= MIN_OUTCOMES_FOR_PERSONALIZATION

    merged = dict(DEFAULT_EFFECTIVENESS)
    for itype, stats in effectiveness.items():
        merged[itype] = stats["avg_delta"]
    preferred = sorted(merged, key=lambda k: merged[k], reverse=True)

    return {
        "student_id": student_id,
        "personalized": personalized,
        "outcomes_used": total,
        "effectiveness": effectiveness,
        "effectiveness_incl_priors": merged,
        "preferred_interventions": preferred,
    }


def preferred_practice_type(policy: dict) -> str:
    """Best intervention among practice-like types for adaptive sequencing."""
    practice_like = ("PRACTICE", "EXAMPLE", "REFLECTION", "REVIEW")
    for candidate in policy.get("preferred_interventions") or []:
        if candidate in practice_like:
            return candidate
    return "PRACTICE"


# ---------------------------------------------------------------------------
# Long-term learning path (§94) — computed roadmap
# ---------------------------------------------------------------------------

def learning_path(db: Session, student_id: int) -> dict:
    now = datetime.utcnow()
    chapters = (
        db.query(Chapter)
        .order_by(Chapter.grade.asc(), Chapter.order.asc())
        .all()
    )
    states = {
        st.knowledge_point_id: st
        for st in db.query(StudentKnowledgeState)
        .filter(StudentKnowledgeState.student_id == student_id)
        .all()
    }
    objectives = (
        db.query(LearningObjective)
        .filter(LearningObjective.student_id == student_id,
                LearningObjective.status == "active")
        .all()
    )

    # velocity: avg mastery gain per week from recent state history
    history = (
        db.query(StudentKnowledgeStateHistory)
        .filter(StudentKnowledgeStateHistory.student_id == student_id)
        .order_by(StudentKnowledgeStateHistory.changed_at.asc())
        .all()
    )
    velocity = 0.05  # conservative default: 5 points/week
    if len(history) >= 2:
        span_days = max(1, (history[-1].changed_at - history[0].changed_at).days)
        net_gain = history[-1].mastery_score - history[0].mastery_score
        velocity = max(0.01, round(net_gain / (span_days / 7), 4)) if span_days else velocity

    phases: dict[str, list] = {"behind": [], "current": [], "mastered": [], "review": []}
    for ch in chapters:
        for kp_name in ch.knowledge_points or []:
            kp = (
                db.query(KnowledgePoint)
                .filter(KnowledgePoint.name == str(kp_name).strip())
                .order_by(KnowledgePoint.id.asc())
                .first()
            )
            st = states.get(kp.id) if kp else None
            mastery = st.mastery_score if st else 0.0
            entry = {
                "knowledge_point": str(kp_name),
                "chapter": ch.title,
                "grade": ch.grade,
                "mastery": round(mastery, 3),
                "decay_risk": st.decay_risk if st else "CRITICAL",
            }
            if st is None or mastery < 0.4:
                phases["behind"].append(entry)
            elif mastery < 0.8:
                phases["current"].append(entry)
            elif st.decay_risk in ("HIGH", "CRITICAL"):
                phases["review"].append(entry)
            else:
                phases["mastered"].append(entry)

    # weeks-to-target estimate for the "current" band (0.4–0.8 → 0.8)
    gap_to_target = sum(max(0.0, 0.8 - e["mastery"]) for e in phases["current"])
    weeks_current = round(gap_to_target / velocity, 1) if gap_to_target > 0 else 0
    gap_behind = sum(max(0.0, 0.4 - e["mastery"]) for e in phases["behind"])
    weeks_behind = round(gap_behind / velocity, 1) if gap_behind > 0 else 0

    return {
        "student_id": student_id,
        "velocity_per_week": velocity,
        "phases": {k: v for k, v in phases.items() if v},
        "objectives": [
            {
                "description": o.description,
                "knowledge_point": o.knowledge_point_name,
                "current": round(o.current_mastery, 3),
                "target": o.target_mastery,
                "deadline": o.deadline.isoformat() if o.deadline else None,
            }
            for o in objectives
        ],
        "estimates": {
            "weeks_to_reach_current_target": weeks_current,
            "weeks_to_catch_up_behind": weeks_behind,
        },
        "generated_at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# Cross-textbook knowledge mapping (§94)
# ---------------------------------------------------------------------------

def _norm(name: str) -> str:
    import re

    return re.sub(r"[\s　·]", "", (name or "").lower())


def _bigrams(name: str) -> set[str]:
    t = _norm(name)
    return {t[i : i + 2] for i in range(len(t) - 1)} if len(t) > 1 else {t}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def knowledge_map(db: Session) -> dict:
    """Group equivalent knowledge points across textbook versions (§94)."""
    kps = db.query(KnowledgePoint).filter(KnowledgePoint.status == "active").all()
    exact: dict[str, list] = defaultdict(list)
    for kp in kps:
        exact[_norm(kp.name)].append(
            {
                "id": kp.id,
                "name": kp.name,
                "textbook_version": kp.textbook_version,
                "grade": kp.grade,
                "chapter_id": kp.chapter_id,
            }
        )
    groups = [entries for entries in exact.values() if len(entries) > 1]

    # near-matches across different textbook versions (likely same concept)
    near = []
    for i, a in enumerate(kps):
        for b in kps[i + 1:]:
            if (a.textbook_version or "") == (b.textbook_version or ""):
                continue
            if _norm(a.name) == _norm(b.name):
                continue  # already exact
            sim = _jaccard(_bigrams(a.name), _bigrams(b.name))
            if sim >= 0.7:
                near.append(
                    {
                        "a": {"id": a.id, "name": a.name, "textbook_version": a.textbook_version},
                        "b": {"id": b.id, "name": b.name, "textbook_version": b.textbook_version},
                        "similarity": round(sim, 3),
                    }
                )
    near.sort(key=lambda m: m["similarity"], reverse=True)
    return {
        "equivalent_groups": groups,
        "near_matches": near[:20],
        "kp_total": len(kps),
    }
