"""Assignment CRUD routes."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT, get_settings
from app.database import get_db
from app.deps import ensure_can_access_student, get_current_user
from app.middleware.audit import record_audit
from app.models.assignments import Assignment, Question, QuestionSet, Submission, SubmissionImage
from app.models.auth import User
from app.models.students import Student
from app.routes._helpers import (
    assert_supported_upload,
    get_allowed_mime_table,
    safe_join_uploads,
)
from app.routes.submissions import _submission_to_out
from app.schemas import AssignmentOut, MixAssignIn, QuestionOut, QuestionSetOut, SubmissionOut
from app.services.ocr import ocr_image, ocr_pdf


router = APIRouter(prefix="/api/assignments", tags=["assignments"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


class StudentQuestionOut(BaseModel):
    """Question view for students — rubric / answer_key stripped."""

    id: int
    order: int
    qtype: str
    subject: str
    prompt: str
    knowledge_points: list[str]
    difficulty: str
    estimated_minutes: Optional[int]
    diagram_svg: Optional[str]
    diagram_format: Optional[str]

    model_config = {"from_attributes": True}


class StudentAssignmentDetail(BaseModel):
    assignment: AssignmentOut
    questions: list[StudentQuestionOut]


@router.get("", response_model=list[AssignmentOut])
def list_assignments(
    student_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Assignment]:
    q = db.query(Assignment)
    if current.role == "student" and current.student_id:
        q = q.filter(Assignment.student_id == current.student_id)
    elif student_id is not None:
        q = q.filter(Assignment.student_id == student_id)
    if status:
        q = q.filter(Assignment.status == status)
    return q.order_by(Assignment.due_date.is_(None), Assignment.due_date).all()


@router.get("/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Assignment:
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    ensure_can_access_student(current, a.student_id)
    return a


@router.get("/{assignment_id}/detail", response_model=StudentAssignmentDetail)
def get_assignment_detail(
    assignment_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudentAssignmentDetail:
    """Return assignment + questions for the student do-page.

    Rubric and answer_key are stripped for non-teacher viewers.
    """
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    ensure_can_access_student(current, a.student_id)
    qs = db.get(QuestionSet, a.question_set_id)
    if not qs:
        raise HTTPException(status_code=500, detail="Question set missing")
    questions = sorted(qs.questions, key=lambda q: q.order)
    if current.role == "teacher":
        return StudentAssignmentDetail(
            assignment=AssignmentOut.model_validate(a),
            questions=[QuestionOut.model_validate(q) for q in questions],
        )
    return StudentAssignmentDetail(
        assignment=AssignmentOut.model_validate(a),
        questions=[
            StudentQuestionOut(
                id=q.id,
                order=q.order,
                qtype=q.qtype,
                subject=q.subject,
                prompt=q.prompt,
                knowledge_points=list(q.knowledge_points or []),
                difficulty=q.difficulty,
                estimated_minutes=q.estimated_minutes,
                diagram_svg=q.diagram_svg,
                diagram_format=q.diagram_format,
            )
            for q in questions
        ],
    )


@router.post("/from-mix", response_model=AssignmentOut)
def create_from_mix(
    payload: MixAssignIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Assignment:
    """Create an assignment from a mix of selected questions across question sets."""
    _teacher_only(current)
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Create a new combined question set by cloning selected questions
    new_set = QuestionSet(
        label="MIX",
        difficulty="medium",
        knowledge_points=[],
        question_count=len(payload.selected_question_ids),
        summary=payload.title,
    )
    db.add(new_set)
    db.flush()

    cloned: list[Question] = []
    for order, qid in enumerate(payload.selected_question_ids, start=1):
        src = db.get(Question, qid)
        if not src:
            continue
        clone = Question(
            question_set_id=new_set.id,
            order=order,
            qtype=src.qtype,
            subject=src.subject,
            prompt=src.prompt,
            rubric=src.rubric,
            answer_key=src.answer_key,
            knowledge_points=list(src.knowledge_points or []),
            difficulty=src.difficulty,
            estimated_minutes=src.estimated_minutes,
            diagram_svg=src.diagram_svg,
            diagram_format=src.diagram_format,
        )
        db.add(clone)
        cloned.append(clone)
    new_set.question_count = len(cloned)
    db.flush()

    assignment = Assignment(
        title=payload.title,
        description=payload.description,
        student_id=payload.student_id,
        question_set_id=new_set.id,
        due_date=payload.due_date,
        estimated_minutes=payload.estimated_minutes,
        calculator_allowed=payload.calculator_allowed,
        status="assigned",
    )
    db.add(assignment)
    record_audit(
        db,
        action="create_assignment",
        user=current,
        request=request,
        target_type="assignment",
        detail={"student_id": payload.student_id, "question_count": len(cloned)},
    )
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/{assignment_id}/cancel", response_model=AssignmentOut)
def cancel(assignment_id: int, request: Request, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Assignment:
    _teacher_only(current)
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    a.status = "cancelled"
    record_audit(db, action="cancel_assignment", user=current, request=request, target_type="assignment", target_id=assignment_id)
    db.commit()
    db.refresh(a)
    return a


# ---------------------------------------------------------------------------
# Student submission flow
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

ALLOWED_MIMES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/pdf": "pdf",
}


@router.post("/{assignment_id}/submit", response_model=SubmissionOut)
async def submit_assignment(
    assignment_id: int,
    request: Request,
    text_answer: str = Form(default=""),
    files: List[UploadFile] = File(default=[]),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    """Student submits answers for an assignment.

    Accepts one optional text answer and one or more image/PDF files.
    Creates a Submission + SubmissionImage rows. Status moves to 'submitted'.
    Idempotent: a second submission replaces the previous one.
    """
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    ensure_can_access_student(current, a.student_id)
    if a.status == "cancelled":
        raise HTTPException(status_code=400, detail="该作业已取消")
    if a.status == "graded":
        raise HTTPException(status_code=400, detail="该作业已批改，不能重新提交")

    settings = get_settings()

    # Replace any existing submission for this assignment (idempotent).
    existing = (
        db.query(Submission)
        .filter(Submission.assignment_id == assignment_id)
        .order_by(Submission.id.desc())
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    now = datetime.utcnow()
    ts = now.strftime("%Y%m%dT%H%M%S%f")
    rel_parts = (f"{a.student_id}", f"{assignment_id}", ts)
    target_dir = safe_join_uploads(*rel_parts)
    target_dir.mkdir(parents=True, exist_ok=True)

    archive_rel = f"uploads/{'/'.join(rel_parts)}"
    submission = Submission(
        assignment_id=assignment_id,
        student_id=a.student_id,
        submitted_at=now,
        archive_path=archive_rel,
        text_answer=text_answer or None,
        status="submitted",
    )
    db.add(submission)
    db.flush()

    combined_ocr: list[str] = []
    for idx, upload in enumerate(files, start=1):
        raw = await upload.read()
        if len(raw) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(status_code=413, detail="文件过大")
        mime, ext = assert_supported_upload(
            raw=raw,
            declared_mime=upload.content_type or "",
            allowed_mimes=get_allowed_mime_table(ALLOWED_MIMES),
        )
        sha = hashlib.sha256(raw).hexdigest()
        safe_name = f"q{idx or 0}_{ts}.{ext}"
        full_path = target_dir / safe_name
        full_path.write_bytes(raw)
        img = SubmissionImage(
            submission_id=submission.id,
            question_number=idx,
            filename=safe_name,
            rel_path=str(full_path.relative_to(PROJECT_ROOT)),
            size_bytes=len(raw),
            sha256=sha,
            mime_type=mime,
        )
        db.add(img)
        db.flush()
        try:
            ocr_text = ocr_pdf(Path(full_path)) if ext == "pdf" else ocr_image(Path(full_path))
            img.ocr_text = ocr_text
            if ocr_text:
                combined_ocr.append(ocr_text)
        except Exception as exc:
            logger.warning("OCR failed: %s", exc)

    if combined_ocr:
        submission.ocr_text = "\n\n".join(combined_ocr)

    if a.status == "assigned":
        a.status = "submitted"

    record_audit(
        db,
        action="submit_assignment",
        user=current,
        request=request,
        target_type="assignment",
        target_id=assignment_id,
        detail={"file_count": len(files), "text_len": len(text_answer or "")},
    )
    db.commit()
    db.refresh(submission)
    return _submission_to_out(submission)