"""Submission upload + listing routes."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT, get_settings
from app.database import get_db
from app.deps import ensure_can_access_student, get_current_user
from app.middleware.audit import record_audit
from app.models.assignments import Assignment, Grading, Submission, SubmissionImage
from app.models.auth import User
from app.routes._helpers import (
    assert_supported_upload,
    get_allowed_mime_table,
    get_compute_sha256,
    get_keep_original_filename,
    safe_join_uploads,
)
from app.schemas import GradingOut, SubmissionImageOut, SubmissionOut
from app.services.ocr import ocr_image, ocr_pdf


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/submissions", tags=["submissions"])

ALLOWED_MIMES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/pdf": "pdf",
}


def _image_to_out(img: SubmissionImage) -> SubmissionImageOut:
    return SubmissionImageOut(
        id=img.id,
        question_number=img.question_number,
        filename=img.filename,
        size_bytes=img.size_bytes,
        sha256=img.sha256,
        mime_type=img.mime_type,
        url=f"/api/submissions/{img.submission_id}/image/{img.id}",
        ocr_text=img.ocr_text,
    )


def _submission_to_out(sub: Submission) -> SubmissionOut:
    return SubmissionOut(
        id=sub.id,
        assignment_id=sub.assignment_id,
        student_id=sub.student_id,
        submitted_at=sub.submitted_at,
        status=sub.status,
        text_answer=sub.text_answer,
        ocr_text=sub.ocr_text,
        images=[_image_to_out(i) for i in (sub.images or [])],
    )


@router.get("", response_model=list[SubmissionOut])
def list_submissions(
    assignment_id: int | None = None,
    student_id: int | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SubmissionOut]:
    q = db.query(Submission)
    if current.role == "student" and current.student_id:
        q = q.filter(Submission.student_id == current.student_id)
    if assignment_id:
        q = q.filter(Submission.assignment_id == assignment_id)
    elif student_id:
        q = q.filter(Submission.student_id == student_id)
    items = q.order_by(Submission.submitted_at.desc()).all()
    return [_submission_to_out(s) for s in items]


@router.get("/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SubmissionOut:
    sub = db.get(Submission, submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    ensure_can_access_student(current, sub.student_id)
    return _submission_to_out(sub)


class SubmissionResultOut(BaseModel):
    """Student-facing view of their own submission + grading."""

    submission: SubmissionOut
    grading: Optional[GradingOut] = None
    assignment_title: str
    assignment_status: str


@router.get("/{submission_id}/result", response_model=SubmissionResultOut)
def get_submission_result(
    submission_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubmissionResultOut:
    sub = db.get(Submission, submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    ensure_can_access_student(current, sub.student_id)
    assignment = db.get(Assignment, sub.assignment_id)
    grading = (
        db.query(Grading)
        .filter(Grading.submission_id == submission_id, Grading.confirmed == True)  # noqa: E712
        .order_by(Grading.confirmed_at.desc())
        .first()
    )
    return SubmissionResultOut(
        submission=_submission_to_out(sub),
        grading=GradingOut.model_validate(grading) if grading else None,
        assignment_title=assignment.title if assignment else "",
        assignment_status=assignment.status if assignment else "",
    )


@router.post("", response_model=SubmissionOut)
async def upload_submission(
    request: Request,
    assignment_id: int = Form(...),
    question_number: int | None = Form(default=None),
    text_answer: str | None = Form(default=None),
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    settings = get_settings()
    assignment = db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    ensure_can_access_student(current, assignment.student_id)
    if assignment.status == "graded":
        raise HTTPException(status_code=400, detail="该作业已批改，不能重新提交")

    raw = await file.read()
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")
    mime, ext = assert_supported_upload(
        raw=raw,
        declared_mime=file.content_type or "",
        allowed_mimes=get_allowed_mime_table(ALLOWED_MIMES),
    )

    sha = hashlib.sha256(raw).hexdigest() if get_compute_sha256() else ""
    now = datetime.utcnow()
    ts = now.strftime("%Y%m%dT%H%M%S%f")
    rel_path_parts = (
        f"{assignment.student_id}",
        f"{assignment_id}",
        ts,
    )
    target_dir = safe_join_uploads(*rel_path_parts)
    target_dir.mkdir(parents=True, exist_ok=True)
    # PRD §87 — honour uploads.keep_original_filename (default false).
    if get_keep_original_filename() and file.filename:
        stem = Path(file.filename).stem
        # Strip path components and reject empty / hostile stems.
        stem = "".join(c for c in stem if c.isalnum() or c in ("-", "_", ".")).strip(".")
        if stem:
            safe_name = f"{stem}.{ext}"
        else:
            safe_name = f"q{question_number or 0}_{ts}.{ext}"
    else:
        safe_name = f"q{question_number or 0}_{ts}.{ext}"
    full_path = target_dir / safe_name
    full_path.write_bytes(raw)

    # Find or create a submission container for this timestamp
    sub = (
        db.query(Submission)
        .filter(Submission.assignment_id == assignment_id, Submission.archive_path == f"uploads/{'/'.join(rel_path_parts)}")
        .first()
    )
    archive_rel = f"uploads/{'/'.join(rel_path_parts)}"
    if not sub:
        sub = Submission(
            assignment_id=assignment_id,
            student_id=assignment.student_id,
            submitted_at=now,
            archive_path=archive_rel,
            text_answer=text_answer,
        )
        db.add(sub)
        db.flush()

    img = SubmissionImage(
        submission_id=sub.id,
        question_number=question_number,
        filename=safe_name,
        rel_path=str(full_path.relative_to(PROJECT_ROOT)),
        size_bytes=len(raw),
        sha256=sha,
        mime_type=mime,
    )
    db.add(img)
    db.flush()

    # OCR (best effort)
    try:
        ocr_text = ocr_pdf(Path(full_path)) if ext == "pdf" else ocr_image(Path(full_path))
        img.ocr_text = ocr_text
        if ocr_text:
            sub.ocr_text = (sub.ocr_text or "") + ("\n\n" if sub.ocr_text else "") + ocr_text
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR failed: %s", exc)

    if assignment.status == "assigned":
        assignment.status = "submitted"
    record_audit(
        db,
        action="upload_submission",
        user=current,
        request=request,
        target_type="submission",
        detail={"assignment_id": assignment_id, "sha256": sha, "size": len(raw)},
    )
    db.commit()
    db.refresh(sub)
    return _submission_to_out(sub)


@router.get("/{submission_id}/image/{image_id}")
def get_image(
    submission_id: int,
    image_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = db.get(Submission, submission_id)
    img = db.get(SubmissionImage, image_id)
    if not sub or not img or img.submission_id != sub.id:
        raise HTTPException(status_code=404, detail="Image not found")
    ensure_can_access_student(current, sub.student_id)
    full = Path(img.rel_path)
    if not full.is_absolute():
        full = PROJECT_ROOT / full
    if not full.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(full)