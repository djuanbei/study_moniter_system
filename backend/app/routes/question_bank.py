"""Question bank routes (PRD §36, §39–41)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.middleware.audit import record_audit
from app.models.assignments import Assignment, Question, QuestionSet
from app.models.auth import User
from app.models.question_bank import QuestionBankItem
from app.models.students import Student
from app.services.question_bank import (
    find_duplicate,
    publish_from_question_row,
    publish_question,
    similar_questions,
    update_question,
)

router = APIRouter(prefix="/api/question-bank", tags=["question-bank"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


def _get_item(db: Session, item_id: int) -> QuestionBankItem:
    item = db.get(QuestionBankItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Question not found in bank")
    return item


class BankItemOut(BaseModel):
    id: int
    subject: str
    grade: Optional[str]
    knowledge_points: list[str]
    difficulty: str
    question_type: str
    prompt: str
    answer: Optional[str]
    rubric: Optional[str]
    estimated_time: Optional[int]
    source: str
    status: str
    version: int
    model_config = ConfigDict(from_attributes=True)


class BankPublishIn(BaseModel):
    subject: str = "math"
    grade: Optional[str] = None
    chapter_id: Optional[int] = None
    knowledge_points: list[str] = []
    difficulty: str = "medium"
    question_type: str = "thinking"
    prompt: str
    answer: Optional[str] = None
    rubric: Optional[str] = None
    estimated_time: Optional[int] = None
    source: str = Field(default="MANUAL", pattern="^(AI|MANUAL|EXAM|IMPORT)$")
    allow_duplicate: bool = False


class BankUpdateIn(BaseModel):
    subject: Optional[str] = None
    grade: Optional[str] = None
    knowledge_points: Optional[list[str]] = None
    difficulty: Optional[str] = None
    question_type: Optional[str] = None
    prompt: Optional[str] = None
    answer: Optional[str] = None
    rubric: Optional[str] = None
    estimated_time: Optional[int] = None
    change_note: Optional[str] = None


class BankFromSetIn(BaseModel):
    set_id: int
    question_ids: Optional[list[int]] = None  # default: all in set
    allow_duplicate: bool = False


class BankToAssignmentIn(BaseModel):
    question_ids: list[int]
    student_id: int
    title: str
    due_date: Optional[str] = None
    estimated_minutes: Optional[int] = None


@router.get("", response_model=list[BankItemOut])
def list_bank(
    knowledge_point: str | None = Query(default=None),
    subject: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    q: str | None = Query(default=None),
    include_deprecated: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuestionBankItem]:
    if current.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")
    query = db.query(QuestionBankItem)
    if not include_deprecated:
        query = query.filter(QuestionBankItem.status == "active")
    if subject:
        query = query.filter(QuestionBankItem.subject == subject)
    if difficulty:
        query = query.filter(QuestionBankItem.difficulty == difficulty)
    if q:
        query = query.filter(QuestionBankItem.prompt.like(f"%{q}%"))
    items = query.order_by(QuestionBankItem.id.desc()).limit(500).all()
    if knowledge_point:
        # SQLAlchemy serializes JSON with ensure_ascii, so SQL LIKE cannot
        # match CJK inside the JSON text — filter in Python (family-scale bank).
        items = [i for i in items if knowledge_point in (i.knowledge_points or [])]
    return items[:limit]


@router.post("", response_model=BankItemOut, status_code=201)
def publish(
    payload: BankPublishIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionBankItem:
    _teacher_only(current)
    item, is_dup = publish_question(
        db,
        fields=payload.model_dump(),
        source=payload.source,
        user_id=current.id,
        allow_duplicate=payload.allow_duplicate,
    )
    db.commit()
    if is_dup:
        raise HTTPException(
            status_code=409,
            detail=f"题库中已存在相同题干（#{item.id}）。如仍要添加，请设置 allow_duplicate。",
        )
    record_audit(db, action="bank_publish", user=current, request=request,
                 target_type="question_bank", target_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.get("/check-duplicate")
def check_duplicate(
    prompt: str = Query(...),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _teacher_only(current)
    dup = find_duplicate(db, prompt)
    return {"duplicate": dup is not None, "existing_id": dup.id if dup else None}


@router.get("/{item_id}", response_model=BankItemOut)
def get_item(
    item_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionBankItem:
    _teacher_only(current)
    return _get_item(db, item_id)


@router.get("/{item_id}/versions")
def get_versions(
    item_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _teacher_only(current)
    item = _get_item(db, item_id)
    return {
        "current_version": item.version,
        "versions": [
            {"version": v.version, "snapshot": v.snapshot,
             "change_note": v.change_note, "published_at": v.published_at.isoformat()}
            for v in item.versions
        ],
    }


@router.patch("/{item_id}", response_model=BankItemOut)
def patch_item(
    item_id: int,
    payload: BankUpdateIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionBankItem:
    _teacher_only(current)
    item = _get_item(db, item_id)
    fields = payload.model_dump(exclude_none=True, exclude={"change_note"})
    item = update_question(db, item, fields=fields, user_id=current.id,
                           change_note=payload.change_note)
    record_audit(db, action="bank_update", user=current, request=request,
                 target_type="question_bank", target_id=item.id,
                 detail={"new_version": item.version})
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/deprecate", response_model=BankItemOut)
def deprecate(
    item_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionBankItem:
    _teacher_only(current)
    item = _get_item(db, item_id)
    item.status = "deprecated"
    record_audit(db, action="bank_deprecate", user=current, request=request,
                 target_type="question_bank", target_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{item_id}/similar")
def similar(
    item_id: int,
    limit: int = Query(default=5, ge=1, le=20),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Similar-question engine (§41)."""
    _teacher_only(current)
    item = _get_item(db, item_id)
    return {"results": similar_questions(db, item, limit=limit)}


@router.post("/from-set", response_model=dict)
def publish_from_set(
    payload: BankFromSetIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Bulk-publish a generated question set into the bank (§36)."""
    _teacher_only(current)
    qs = db.get(QuestionSet, payload.set_id)
    if not qs:
        raise HTTPException(status_code=404, detail="Question set not found")
    questions = sorted(qs.questions, key=lambda q: q.order)
    if payload.question_ids:
        questions = [q for q in questions if q.id in set(payload.question_ids)]
    published, duplicates = 0, []
    for q in questions:
        item, is_dup = publish_from_question_row(db, q, user_id=current.id,
                                                 allow_duplicate=payload.allow_duplicate)
        if is_dup:
            duplicates.append(item.id)
        else:
            published += 1
    record_audit(db, action="bank_publish_from_set", user=current, request=request,
                 target_type="question_set", target_id=payload.set_id,
                 detail={"published": published, "duplicates": duplicates})
    db.commit()
    return {"published": published, "duplicates": duplicates}


@router.post("/to-assignment", response_model=dict)
def to_assignment(
    payload: BankToAssignmentIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Assign selected bank questions to a student (loop: bank → assignment)."""
    _teacher_only(current)
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    items = (
        db.query(QuestionBankItem)
        .filter(QuestionBankItem.id.in_(payload.question_ids),
                QuestionBankItem.status == "active")
        .all()
    )
    if not items:
        raise HTTPException(status_code=400, detail="没有可用的题库题目")

    new_set = QuestionSet(
        label="BANK", difficulty=items[0].difficulty,
        knowledge_points=sorted({kp for i in items for kp in (i.knowledge_points or [])}),
        question_count=len(items), summary=payload.title,
    )
    db.add(new_set)
    db.flush()
    for order, item in enumerate(items, start=1):
        db.add(
            Question(
                question_set_id=new_set.id, order=order, qtype=item.question_type,
                subject=item.subject, prompt=item.prompt, rubric=item.rubric,
                answer_key=item.answer, knowledge_points=list(item.knowledge_points or []),
                difficulty=item.difficulty, estimated_minutes=item.estimated_time,
            )
        )
    assignment = Assignment(
        title=payload.title[:128], student_id=student.id, question_set_id=new_set.id,
        estimated_minutes=payload.estimated_minutes, status="assigned",
    )
    db.add(assignment)
    db.flush()
    record_audit(db, action="bank_to_assignment", user=current, request=request,
                 target_type="assignment", target_id=assignment.id,
                 detail={"question_count": len(items)})
    db.commit()
    return {"assignment_id": assignment.id, "question_count": len(items)}
