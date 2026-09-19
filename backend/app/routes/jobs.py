"""Async job routes (PRD §82–83)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.middleware.audit import record_audit
from app.models.auth import User
from app.models.system import Job
from app.schemas import JobEnqueueIn, JobOut
from app.services.job_worker import enqueue, registered_types

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


@router.post("", response_model=JobOut, status_code=202)
def create_job(
    payload: JobEnqueueIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    _teacher_only(current)
    try:
        job = enqueue(db, job_type=payload.job_type, payload=payload.payload, user_id=current.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(
        db, action="enqueue_job", user=current, request=request,
        target_type="job", target_id=job.id,
        detail={"job_type": job.job_type, "payload": payload.payload},
    )
    db.commit()
    db.refresh(job)
    return job


@router.get("/types")
def job_types(current: User = Depends(get_current_user)) -> dict:
    _teacher_only(current)
    return {"types": registered_types()}


@router.get("", response_model=list[JobOut])
def list_jobs(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Job]:
    _teacher_only(current)
    q = db.query(Job)
    if status:
        q = q.filter(Job.status == status)
    return q.order_by(Job.id.desc()).limit(limit).all()


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    _teacher_only(current)
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    _teacher_only(current)
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "QUEUED":
        raise HTTPException(status_code=400, detail=f"任务状态为 {job.status}，无法取消")
    job.status = "CANCELLED"
    job.finished_at = job.finished_at or datetime.utcnow()
    record_audit(db, action="cancel_job", user=current, request=request,
                 target_type="job", target_id=job.id)
    db.commit()
    db.refresh(job)
    return job
