"""Chapter routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.middleware.audit import record_audit
from app.models.auth import User
from app.models.students import Chapter
from app.schemas import ChapterIn, ChapterInferOut, ChapterOut
from app.services.chapter import all_chapter_titles, chapters_for_semester, infer_chapter


router = APIRouter(prefix="/api/chapters", tags=["chapters"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


@router.get("", response_model=list[ChapterOut])
def list_chapters(
    textbook: str | None = Query(default=None),
    grade: str | None = Query(default=None),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Chapter]:
    q = db.query(Chapter)
    if textbook:
        q = q.filter(Chapter.textbook_version == textbook)
    if grade:
        q = q.filter(Chapter.grade == grade)
    return q.order_by(Chapter.textbook_version, Chapter.grade, Chapter.order).all()


@router.post("", response_model=ChapterOut)
def create_chapter(
    payload: ChapterIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Chapter:
    _teacher_only(current)
    ch = Chapter(**payload.model_dump())
    db.add(ch)
    record_audit(db, action="create_chapter", user=current, request=request, target_type="chapter")
    db.commit()
    db.refresh(ch)
    return ch


@router.get("/infer", response_model=ChapterInferOut)
def infer(
    textbook: str | None = None,
    grade: str | None = None,
    semester: int | None = None,
):
    suggestion = infer_chapter(textbook=textbook, grade=grade, semester=semester)
    resolved_semester = suggestion.semester if suggestion else (semester if semester in (1, 2) else None)
    return ChapterInferOut(
        textbook=textbook,
        grade=grade,
        semester=resolved_semester,
        suggestion=(
            {
                "title": suggestion.title,
                "order": suggestion.order,
                "semester": suggestion.semester,
                "rationale": suggestion.rationale,
            }
            if suggestion
            else None
        ),
        chapters=chapters_for_semester(textbook, grade, resolved_semester),
    )