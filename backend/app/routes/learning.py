"""Learning-loop routes.

Closes the PRD MVP loop (§91–92):
    evidence -> knowledge state -> diagnosis -> plan -> AI questions -> assignment

Endpoints (PRD §84):
    /api/knowledge-points          GET, POST /sync
    /api/student-knowledge-state   GET (per student, weak-across-students)
    /api/learning-evidence         GET, POST (parent feedback -> evidence)
    /api/learning-objectives       GET, POST, PATCH
    /api/diagnosis/{student_id}    GET
    /api/learning-plans            GET, POST /generate, /{id}/approve,
                                   /{id}/cancel, /{plan_id}/items/{item_id}/assign
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ensure_can_access_student, get_current_user
from app.middleware.audit import record_audit
from app.models.assignments import Assignment, Question, QuestionSet
from app.models.auth import User
from app.models.learning import (
    KnowledgePoint,
    LearningEvidence,
    LearningObjective,
    LearningPlan,
    LearningPlanItem,
    ParentFeedback,
    StudentKnowledgeState,
)
from app.models.students import Student
from app.schemas import (
    AssignmentOut,
    EvidenceCreateIn,
    KnowledgePointOut,
    LearningEvidenceOut,
    LearningObjectiveIn,
    LearningObjectiveOut,
    LearningPlanOut,
    PlanGenerateIn,
    StudentKnowledgeStateOut,
)
from app.services.learning import (
    _DIFFICULTY_BY_MASTERY,
    diagnose_student,
    generate_plan,
    get_state,
    record_evidence,
    sync_knowledge_points,
)
from app.services.svg import sanitize_diagram_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["learning"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


def _get_student(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


# ---------------------------------------------------------------------------
# Knowledge points
# ---------------------------------------------------------------------------

@router.get("/knowledge-points", response_model=list[KnowledgePointOut])
def list_knowledge_points(
    chapter_id: int | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[KnowledgePoint]:
    q = db.query(KnowledgePoint).filter(KnowledgePoint.status == "active")
    if chapter_id:
        q = q.filter(KnowledgePoint.chapter_id == chapter_id)
    return q.order_by(KnowledgePoint.name).all()


@router.post("/knowledge-points/sync", response_model=dict)
def sync_points(
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _teacher_only(current)
    created = sync_knowledge_points(db)
    record_audit(db, action="sync_knowledge_points", user=current, request=request, detail={"created": created})
    db.commit()
    return {"created": created}


# ---------------------------------------------------------------------------
# Student knowledge state
# ---------------------------------------------------------------------------

def _state_out(db: Session, st: StudentKnowledgeState) -> StudentKnowledgeStateOut:
    out = StudentKnowledgeStateOut.model_validate(st)
    kp = db.get(KnowledgePoint, st.knowledge_point_id)
    out.knowledge_point_name = kp.name if kp else None
    return out


@router.get("/student-knowledge-state", response_model=list[StudentKnowledgeStateOut])
def list_states(
    student_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StudentKnowledgeStateOut]:
    ensure_can_access_student(current, student_id)
    _get_student(db, student_id)
    rows = (
        db.query(StudentKnowledgeState)
        .filter(StudentKnowledgeState.student_id == student_id)
        .order_by(StudentKnowledgeState.mastery_score.asc())
        .all()
    )
    return [_state_out(db, st) for st in rows]


@router.get("/student-knowledge-state/weak", response_model=list[StudentKnowledgeStateOut])
def weak_states(
    limit: int = Query(default=8, ge=1, le=50),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StudentKnowledgeStateOut]:
    """Weakest knowledge states across all students (parent dashboard, PRD §13)."""
    _teacher_only(current)
    rows = (
        db.query(StudentKnowledgeState)
        .filter(StudentKnowledgeState.mastery_score < 0.6)
        .order_by(StudentKnowledgeState.mastery_score.asc())
        .limit(limit)
        .all()
    )
    return [_state_out(db, st) for st in rows]


# ---------------------------------------------------------------------------
# Learning evidence
# ---------------------------------------------------------------------------

@router.get("/learning-evidence", response_model=list[LearningEvidenceOut])
def list_evidence(
    student_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LearningEvidence]:
    ensure_can_access_student(current, student_id)
    _get_student(db, student_id)
    return (
        db.query(LearningEvidence)
        .filter(LearningEvidence.student_id == student_id)
        .order_by(LearningEvidence.created_at.desc())
        .limit(limit)
        .all()
    )


_OBSERVATION_MAP = {
    # PRD §64 — parent feedback becomes evidence
    "understood": (True, None, 90.0),
    "not_understood": (False, "CONCEPT_MISUNDERSTANDING", 20.0),
    "careless": (True, "CARELESS_ERROR", 55.0),  # knew it, slipped once
    "out_of_scope": (None, None, None),  # not counted as knowledge evidence
    "neutral": (None, None, None),
}


@router.post("/learning-evidence")
def create_evidence(
    payload: EvidenceCreateIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Parent qualitative feedback -> LearningEvidence (PRD §64)."""
    _teacher_only(current)
    student = _get_student(db, payload.student_id)
    correct, error_type, score = _OBSERVATION_MAP[payload.observation]
    if correct is None:
        # Out-of-scope / neutral notes are stored as parent feedback only.
        feedback = ParentFeedback(
            student_id=student.id,
            knowledge_point_id=payload.knowledge_point_id,
            knowledge_point_name=payload.knowledge_point_name,
            content=payload.comment or payload.observation,
            observation=payload.observation,
            author_id=current.id,
        )
        db.add(feedback)
        record_audit(db, action="parent_feedback_note", user=current, request=request,
                     target_type="student", target_id=student.id)
        db.commit()
        return {"recorded": False, "message": "已记录家长观察（不计入学习证据）"}

    evidence = record_evidence(
        db,
        student_id=student.id,
        knowledge_point_name=payload.knowledge_point_name,
        knowledge_point_id=payload.knowledge_point_id,
        correct=bool(correct),
        score=score,
        difficulty=None,
        error_type=error_type,
        feedback=payload.comment,
        confidence=None,
        trust_level="PARENT_CONFIRMED",
        source_type="PARENT_FEEDBACK",
        observed_by=current.id,
    )
    feedback = ParentFeedback(
        student_id=student.id,
        knowledge_point_id=evidence.knowledge_point_id,
        knowledge_point_name=evidence.knowledge_point_name,
        content=payload.comment or payload.observation,
        observation=payload.observation,
        author_id=current.id,
        evidence_id=evidence.id,
    )
    db.add(feedback)
    record_audit(db, action="create_parent_evidence", user=current, request=request,
                 target_type="student", target_id=student.id,
                 detail={"evidence_id": evidence.id, "observation": payload.observation})
    db.commit()
    db.refresh(evidence)
    return {
        "recorded": True,
        "message": "已生成学习证据并更新知识点掌握度",
        "evidence": LearningEvidenceOut.model_validate(evidence).model_dump(),
    }


# ---------------------------------------------------------------------------
# Learning objectives (PRD §16–17)
# ---------------------------------------------------------------------------

@router.get("/learning-objectives", response_model=list[LearningObjectiveOut])
def list_objectives(
    student_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LearningObjective]:
    ensure_can_access_student(current, student_id)
    _get_student(db, student_id)
    return (
        db.query(LearningObjective)
        .filter(LearningObjective.student_id == student_id)
        .order_by(LearningObjective.priority.asc(), LearningObjective.id.desc())
        .all()
    )


@router.post("/learning-objectives", response_model=LearningObjectiveOut)
def create_objective(
    payload: LearningObjectiveIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningObjective:
    _teacher_only(current)
    student = _get_student(db, payload.student_id)
    current_mastery = 0.0
    if payload.knowledge_point_id:
        st = (
            db.query(StudentKnowledgeState)
            .filter(
                StudentKnowledgeState.student_id == student.id,
                StudentKnowledgeState.knowledge_point_id == payload.knowledge_point_id,
            )
            .first()
        )
        if st:
            current_mastery = st.mastery_score
    obj = LearningObjective(**payload.model_dump(), current_mastery=current_mastery)
    db.add(obj)
    record_audit(db, action="create_objective", user=current, request=request,
                 target_type="student", target_id=student.id)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/learning-objectives/{objective_id}", response_model=LearningObjectiveOut)
def update_objective(
    objective_id: int,
    payload: dict,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningObjective:
    _teacher_only(current)
    obj = db.get(LearningObjective, objective_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found")
    for key in ("description", "target_mastery", "priority", "deadline", "status"):
        if key in payload:
            setattr(obj, key, payload[key])
    record_audit(db, action="update_objective", user=current, request=request,
                 target_type="learning_objective", target_id=objective_id)
    db.commit()
    db.refresh(obj)
    return obj


# ---------------------------------------------------------------------------
# Diagnosis (PRD §29)
# ---------------------------------------------------------------------------

@router.get("/diagnosis/{student_id}")
def diagnosis(
    student_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_can_access_student(current, student_id)
    _get_student(db, student_id)
    return diagnose_student(db, student_id)


# ---------------------------------------------------------------------------
# Learning plans (PRD §30–31)
# ---------------------------------------------------------------------------

@router.get("/learning-plans", response_model=list[LearningPlanOut])
def list_plans(
    student_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LearningPlan]:
    ensure_can_access_student(current, student_id)
    _get_student(db, student_id)
    return (
        db.query(LearningPlan)
        .filter(LearningPlan.student_id == student_id)
        .order_by(LearningPlan.id.desc())
        .limit(20)
        .all()
    )


@router.post("/learning-plans/generate", response_model=LearningPlanOut)
def generate(
    payload: PlanGenerateIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningPlan:
    _teacher_only(current)
    student = _get_student(db, payload.student_id)
    try:
        plan = generate_plan(db, student, user_id=current.id)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Plan generation failed")
        raise HTTPException(status_code=502, detail=f"学习计划生成失败: {exc}") from exc
    record_audit(db, action="generate_learning_plan", user=current, request=request,
                 target_type="student", target_id=student.id,
                 detail={"plan_id": plan.id, "generated_by": plan.generated_by})
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/learning-plans/{plan_id}/approve", response_model=LearningPlanOut)
def approve_plan(
    plan_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningPlan:
    _teacher_only(current)
    plan = db.get(LearningPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.status = "approved"
    plan.approved_by = current.id
    plan.approved_at = datetime.utcnow()
    record_audit(db, action="approve_learning_plan", user=current, request=request,
                 target_type="learning_plan", target_id=plan_id)
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/learning-plans/{plan_id}/cancel", response_model=LearningPlanOut)
def cancel_plan(
    plan_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningPlan:
    _teacher_only(current)
    plan = db.get(LearningPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.status = "cancelled"
    record_audit(db, action="cancel_learning_plan", user=current, request=request,
                 target_type="learning_plan", target_id=plan_id)
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/learning-plans/{plan_id}/items/{item_id}/assign", response_model=AssignmentOut)
def assign_plan_item(
    plan_id: int,
    item_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Turn a plan item into an assignment via the AI question pipeline.

    This is the loop-closing step (PRD §7): plan -> AI questions -> assignment.
    """
    _teacher_only(current)
    plan = db.get(LearningPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status == "cancelled":
        raise HTTPException(status_code=400, detail="计划已取消")
    item = db.get(LearningPlanItem, item_id)
    if not item or item.plan_id != plan.id:
        raise HTTPException(status_code=404, detail="Plan item not found")
    if item.status == "assigned":
        raise HTTPException(status_code=400, detail="该任务已生成作业")
    if item.question_count <= 0:
        raise HTTPException(status_code=400, detail="该任务不含练习题，无需生成作业")

    student = db.get(Student, plan.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    kp_name = item.knowledge_point_name or "综合练习"
    state = None
    if item.knowledge_point_id:
        state = get_state(db, student.id, item.knowledge_point_id)
    difficulty = _DIFFICULTY_BY_MASTERY(state.mastery_score if state else 0.0)

    student_payload = {
        "grade": student.grade,
        "textbook": student.textbook_version,
        "semester": student.current_semester,
        "current_chapter": student.current_chapter.title if student.current_chapter else None,
        "weak_points": [kp_name],
        "strengths": student.strengths or [],
        "score_history": student.score_history or [],
    }
    teacher_requirements = {
        "question_count": item.question_count,
        "difficulty": difficulty,
        "knowledge_points": [kp_name],
        "question_types": [],
        "semester": student.current_semester,
        "due_date": None,
        "estimated_minutes": item.estimated_minutes,
        "calculator_allowed": False,
        "notes": f"学习计划 Day{item.day} {item.intervention_type}: {item.description}",
    }

    try:
        from app.services.llm import generate_two_sets  # lazy

        result = generate_two_sets(
            db,
            student_payload=student_payload,
            teacher_requirements=teacher_requirements,
            user=current,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Plan item question generation failed")
        raise HTTPException(status_code=502, detail=f"AI 出题失败: {exc}") from exc

    set_data = (result.get("sets") or [{}])[0]
    qs = QuestionSet(
        label="PLAN",
        difficulty=difficulty,
        knowledge_points=[kp_name],
        question_count=len(set_data.get("questions", [])),
        summary=f"学习计划 #{plan.id} Day{item.day}",
        validator_notes=set_data.get("validator_notes", ""),
    )
    db.add(qs)
    db.flush()
    for q in set_data.get("questions", []):
        fmt, markup = sanitize_diagram_payload(q.get("diagram_format"), q.get("diagram_svg"))
        db.add(
            Question(
                question_set_id=qs.id,
                order=q.get("order", 0),
                qtype=q.get("qtype", ""),
                subject=q.get("subject", "math"),
                prompt=q.get("prompt", ""),
                rubric=q.get("rubric"),
                answer_key=q.get("answer_key"),
                knowledge_points=q.get("knowledge_points", [kp_name]),
                difficulty=q.get("difficulty", difficulty),
                estimated_minutes=q.get("estimated_minutes"),
                diagram_svg=markup,
                diagram_format=fmt,
            )
        )
    assignment = Assignment(
        title=f"Day{item.day} {item.intervention_type} · {kp_name}"[:128],
        description=item.description,
        student_id=student.id,
        question_set_id=qs.id,
        estimated_minutes=item.estimated_minutes,
        status="assigned",
    )
    db.add(assignment)
    db.flush()
    item.assignment_id = assignment.id
    item.status = "assigned"
    item.before_mastery = state.mastery_score if state else 0.0  # PRD §63
    record_audit(db, action="assign_plan_item", user=current, request=request,
                 target_type="learning_plan_item", target_id=item.id,
                 detail={"assignment_id": assignment.id, "plan_id": plan.id})
    db.commit()
    db.refresh(assignment)
    return assignment
