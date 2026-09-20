"""Material Agent routes (PRD §22–23)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.middleware.audit import record_audit
from app.models.auth import User
from app.models.materials import MaterialCandidate
from app.schemas import MaterialOut
from app.services.material_agent import (
    agent_config,
    approve_candidate,
    discover_materials,
)

router = APIRouter(prefix="/api/material-agent", tags=["material-agent"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


class AgentStatusOut(BaseModel):
    enabled: bool
    schedule: str
    max_candidates_per_run: int
    auto_import: bool
    provider_configured: bool


class CandidateOut(BaseModel):
    id: int
    title: str
    url: str
    domain: str
    snippet: str | None
    knowledge_point: str | None
    grade: str | None
    license: str
    status: str
    material_id: int | None
    retrieved_at: str

    model_config = {"from_attributes": True}


def _to_out(c: MaterialCandidate) -> dict:
    return CandidateOut(
        id=c.id, title=c.title, url=c.url, domain=c.domain, snippet=c.snippet,
        knowledge_point=c.knowledge_point, grade=c.grade, license=c.license,
        status=c.status, material_id=c.material_id,
        retrieved_at=c.retrieved_at.isoformat(),
    ).model_dump()


@router.get("/status", response_model=AgentStatusOut)
def status(current: User = Depends(get_current_user)) -> AgentStatusOut:
    _teacher_only(current)
    cfg = agent_config()
    from app.services.material_agent import _provider

    return AgentStatusOut(
        enabled=cfg["enabled"],
        schedule=cfg["schedule"],
        max_candidates_per_run=cfg["max_candidates_per_run"],
        auto_import=cfg["auto_import"],
        provider_configured=_provider(cfg["search"]) is not None,
    )


@router.post("/run")
def run(
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """One discovery pass (also available as MATERIAL_DISCOVERY job, §82)."""
    _teacher_only(current)
    result = discover_materials(db)
    record_audit(db, action="material_agent_run", user=current, request=request,
                 detail=result)
    db.commit()
    return result


@router.get("/candidates")
def candidates(
    status: str = Query(default="discovered",
                        pattern="^(discovered|approved|rejected)$"),
    limit: int = Query(default=50, ge=1, le=200),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    _teacher_only(current)
    rows = (
        db.query(MaterialCandidate)
        .filter(MaterialCandidate.status == status)
        .order_by(MaterialCandidate.id.desc())
        .limit(limit)
        .all()
    )
    return [_to_out(c) for c in rows]


@router.post("/candidates/{candidate_id}/approve", response_model=MaterialOut)
def approve(
    candidate_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Material:
    """Parent approves -> fetch into the Material library (§22, §23 provenance)."""
    _teacher_only(current)
    candidate = db.get(MaterialCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    try:
        material = approve_candidate(db, candidate, user=current)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=502, detail=f"抓取失败: {exc}") from exc
    record_audit(db, action="material_candidate_approve", user=current,
                 request=request, target_type="material_candidate",
                 target_id=candidate.id, detail={"material_id": material.id,
                                                 "url": candidate.url})
    db.commit()
    db.refresh(material)
    return material


@router.post("/candidates/{candidate_id}/reject")
def reject(
    candidate_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _teacher_only(current)
    candidate = db.get(MaterialCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status != "discovered":
        raise HTTPException(status_code=400, detail="该候选已处理")
    candidate.status = "rejected"
    candidate.reviewed_by = current.id
    record_audit(db, action="material_candidate_reject", user=current,
                 request=request, target_type="material_candidate", target_id=candidate.id)
    db.commit()
    return {"ok": True}
