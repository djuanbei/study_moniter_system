"""Student CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ensure_can_access_student, get_current_user
from app.middleware.audit import record_audit
from app.models.assignments import Assignment, Grading, Submission
from app.models.auth import User
from app.models.students import Student
from app.schemas import StudentIn, StudentOut
from app.services.chapter import infer_chapter


router = APIRouter(prefix="/api/students", tags=["students"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


@router.get("", response_model=list[StudentOut])
def list_students(
    class_id: int | None = Query(default=None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Student]:
    if current.role == "student":
        if current.student_id is None:
            return []
        return [db.get(Student, current.student_id)]
    q = db.query(Student)
    if class_id:
        q = q.filter(Student.class_id == class_id)
    return q.order_by(Student.id).all()


@router.post("", response_model=StudentOut)
def create_student(
    payload: StudentIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    auto_infer: bool = Query(default=True),
) -> Student:
    _teacher_only(current)
    data = payload.model_dump()
    if auto_infer and (not data.get("current_chapter_id")):
        suggestion = infer_chapter(textbook=data.get("textbook_version"), grade=data.get("grade"))
        if suggestion:
            data["_inferred_chapter_title"] = suggestion.title  # not a column; used for hint
    data.pop("_inferred_chapter_title", None)
    student = Student(**data)
    db.add(student)
    record_audit(db, action="create_student", user=current, request=request, target_type="student")
    db.commit()
    db.refresh(student)
    return student


@router.get("/{student_id}", response_model=StudentOut)
def get_student(student_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Student:
    ensure_can_access_student(current, student_id)
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.patch("/{student_id}", response_model=StudentOut)
def update_student(
    student_id: int,
    payload: StudentIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Student:
    _teacher_only(current)
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    for k, v in payload.model_dump().items():
        setattr(student, k, v)
    record_audit(db, action="update_student", user=current, request=request, target_type="student", target_id=student_id)
    db.commit()
    db.refresh(student)
    return student


@router.delete("/{student_id}")
def delete_student(
    student_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _teacher_only(current)
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    db.delete(student)
    record_audit(db, action="delete_student", user=current, request=request, target_type="student", target_id=student_id)
    db.commit()
    return {"ok": True}


@router.get("/{student_id}/assignments")
def student_assignments(student_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_can_access_student(current, student_id)
    return (
        db.query(Assignment)
        .filter(Assignment.student_id == student_id)
        .order_by(Assignment.created_at.desc())
        .all()
    )


@router.get("/{student_id}/score-trend")
def score_trend(student_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_can_access_student(current, student_id)
    rows = (
        db.query(Submission.id, Submission.submitted_at, Grading.final_score, Grading.confirmed)
        .join(Grading, Grading.submission_id == Submission.id)
        .filter(Submission.student_id == student_id, Grading.confirmed == True)  # noqa: E712
        .order_by(Submission.submitted_at)
        .all()
    )
    return [
        {"submission_id": r[0], "submitted_at": r[1].isoformat(), "score": r[2]}
        for r in rows
    ]