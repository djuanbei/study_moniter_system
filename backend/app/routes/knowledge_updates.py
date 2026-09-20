"""Knowledge-base update routes (PRD §69)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.middleware.audit import record_audit
from app.models.auth import User
from app.models.learning import KnowledgeUpdateCandidate
from app.schemas import KnowledgeCandidateOut, KnowledgeRejectIn
from app.services.knowledge_update import (
    analyze_knowledge,
    apply_knowledge_candidate,
    generate_knowledge_candidates,
)

router = APIRouter(prefix="/api/knowledge-updates", tags=["knowledge-updates"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


@router.get("/analysis")
def analysis(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _teacher_only(current)
    return analyze_knowledge(db)


@router.post("/generate")
def generate(
    request: Request,
    batch_size: int = Query(default=20, ge=1, le=50),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Deterministic candidate generation (also available as KNOWLEDGE_UPDATE job)."""
    _teacher_only(current)
    result = generate_knowledge_candidates(db, batch_size=batch_size)
    record_audit(db, action="generate_knowledge_candidates", user=current,
                 request=request, detail=result)
    db.commit()
    return result


@router.get("/candidates", response_model=list[KnowledgeCandidateOut])
def candidates(
    status: str = Query(default="pending", pattern="^(pending|approved|rejected)$"),
    limit: int = Query(default=50, ge=1, le=200),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[KnowledgeUpdateCandidate]:
    _teacher_only(current)
    return (
        db.query(KnowledgeUpdateCandidate)
        .filter(KnowledgeUpdateCandidate.status == status)
        .order_by(KnowledgeUpdateCandidate.id.desc())
        .limit(limit)
        .all()
    )


@router.post("/candidates/{candidate_id}/approve", response_model=KnowledgeCandidateOut)
def approve(
    candidate_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeUpdateCandidate:
    """Parent confirmation mutates the knowledge base (§69 必须家长确认)."""
    _teacher_only(current)
    candidate = db.get(KnowledgeUpdateCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    try:
        apply_knowledge_candidate(db, candidate, user=current)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(db, action="knowledge_candidate_approve", user=current,
                 request=request, target_type="knowledge_update_candidate",
                 target_id=candidate.id,
                 detail={"type": candidate.candidate_type, "note": candidate.review_note})
    db.commit()
    db.refresh(candidate)
    return candidate


@router.post("/candidates/{candidate_id}/reject", response_model=KnowledgeCandidateOut)
def reject(
    candidate_id: int,
    payload: KnowledgeRejectIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeUpdateCandidate:
    _teacher_only(current)
    candidate = db.get(KnowledgeUpdateCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status != "pending":
        raise HTTPException(status_code=400, detail="该候选已处理")
    candidate.status = "rejected"
    candidate.reviewed_by = current.id
    candidate.review_note = payload.note
    record_audit(db, action="knowledge_candidate_reject", user=current,
                 request=request, target_type="knowledge_update_candidate",
                 target_id=candidate.id)
    db.commit()
    db.refresh(candidate)
    return candidate
