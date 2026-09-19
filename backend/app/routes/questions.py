"""Question generation wizard + question set management."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.middleware.audit import record_audit
from app.models.assignments import Question, QuestionSet
from app.models.auth import User
from app.models.students import Student
from app.schemas import GenerateIn, GenerateOut, QuestionSetOut
# generate_two_sets is imported lazily inside the route handler to allow the
# app to boot even when langchain-core is not installed.


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


@router.post("/generate", response_model=GenerateOut)
def generate(
    payload: GenerateIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerateOut:
    _teacher_only(current)
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    student_payload = {
        "grade": student.grade,
        "textbook": student.textbook_version,
        "semester": student.current_semester,
        "current_chapter": (student.current_chapter.title if student.current_chapter else None),
        "weak_points": student.weak_points or [],
        "strengths": student.strengths or [],
        "score_history": student.score_history or [],
    }
    teacher_requirements = {
        "question_count": payload.question_count,
        "difficulty": payload.difficulty,
        "knowledge_points": payload.knowledge_points,
        "question_types": payload.question_types,
        "semester": payload.semester if payload.semester in (1, 2) else student.current_semester,
        "due_date": payload.due_date.isoformat() if payload.due_date else None,
        "estimated_minutes": payload.estimated_minutes,
        "calculator_allowed": payload.calculator_allowed,
        "notes": payload.requirements,
    }
    # If the wizard supplied an explicit semester, prefer it for the student payload too.
    if payload.semester in (1, 2):
        student_payload["semester"] = payload.semester

    try:
        from app.services.llm import generate_two_sets  # lazy

        result = generate_two_sets(
            db,
            student_payload=student_payload,
            teacher_requirements=teacher_requirements,
            user=current,
        )
        record_audit(
            db,
            action="generate_questions",
            user=current,
            request=request,
            target_type="student",
            target_id=student.id,
            detail={"question_count": payload.question_count, "difficulty": payload.difficulty},
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Question generation failed")
        db.rollback()
        # Preserve draft semantics: store a failed LLMRun and re-raise
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {exc}") from exc

    return GenerateOut(**result)


@router.post("/persist", response_model=list[QuestionSetOut])
def persist_sets(
    payload: GenerateOut,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuestionSet]:
    _teacher_only(current)
    persisted: list[QuestionSet] = []
    for set_data in payload.sets:
        qs = QuestionSet(
            label=set_data.get("label", "A"),
            difficulty=payload.curriculum.get("recommended_difficulty", "medium"),
            estimated_minutes=None,
            knowledge_points=payload.curriculum.get("knowledge_points", []),
            question_count=len(set_data.get("questions", [])),
            summary=set_data.get("validator_notes", ""),
            validator_notes=set_data.get("validator_notes", ""),
        )
        db.add(qs)
        db.flush()
        for q in set_data.get("questions", []):
            db.add(
                Question(
                    question_set_id=qs.id,
                    order=q.get("order", 0),
                    qtype=q.get("qtype", ""),
                    subject=q.get("subject", "math"),
                    prompt=q.get("prompt", ""),
                    rubric=q.get("rubric"),
                    answer_key=q.get("answer_key"),
                    knowledge_points=q.get("knowledge_points", []),
                    difficulty=q.get("difficulty", "medium"),
                    estimated_minutes=q.get("estimated_minutes"),
                    diagram_svg=q.get("diagram_svg"),
                    diagram_format=q.get("diagram_format"),
                )
            )
        persisted.append(qs)
    record_audit(db, action="persist_question_sets", user=current, request=request, detail={"count": len(persisted)})
    db.commit()
    for qs in persisted:
        db.refresh(qs)
    return persisted


@router.get("/sets", response_model=list[QuestionSetOut])
def list_sets(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[QuestionSet]:
    _teacher_only(current)
    return db.query(QuestionSet).order_by(QuestionSet.id.desc()).limit(50).all()


@router.get("/sets/{set_id}", response_model=QuestionSetOut)
def get_set(set_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> QuestionSet:
    _teacher_only(current)
    qs = db.get(QuestionSet, set_id)
    if not qs:
        raise HTTPException(status_code=404, detail="Question set not found")
    return qs


@router.patch("/questions/{question_id}")
def update_question(question_id: int, payload: dict, request: Request, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _teacher_only(current)
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    for k, v in payload.items():
        if hasattr(q, k):
            setattr(q, k, v)
    record_audit(db, action="update_question", user=current, request=request, target_type="question", target_id=question_id)
    db.commit()
    return {"ok": True}