"""7-stage LangChain workflow.

Stages:
  1. Curriculum planning
  2. Question planning
  3. Question generation (per A/B set)
  4. Diagram generation (for geometry)
  5. Validation
  6. Grading
  7. Archive summary

Each stage logs an LLMRun row for traceability (agent, prompt hash, input
JSON, output JSON, tokens, timestamp).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.config import get_business_config
from app.models.assignments import Grading, Question, QuestionSet, Submission
from app.models.auth import User
from app.models.system import LLMRun
from app.services.llm.prompts import (
    ARCHIVE_SUMMARY,
    CURRICULUM_PLANNER,
    DIAGRAM_GENERATOR,
    GRADING,
    LEARNING_PLANNER,
    QUESTION_GENERATOR,
    QUESTION_PLANNER,
    VALIDATOR,
)
from app.services.llm.provider import get_chat_model
from app.services.llm.tools import ALL_TOOLS
from app.services.rubric import validate_question
from app.services.svg import build_diagram_prompt, diagram_from_json


logger = logging.getLogger(__name__)


def _hash_prompt(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_json_loads(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


def _record_run(
    db: Session,
    *,
    agent: str,
    purpose: str,
    prompt: str,
    output: Optional[dict],
    user_id: Optional[int],
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    duration_ms: Optional[int] = None,
    status: str = "ok",
    error: Optional[str] = None,
) -> LLMRun:
    run = LLMRun(
        agent=agent,
        purpose=purpose,
        prompt_hash=_hash_prompt(prompt),
        input_json={"prompt": prompt},
        output_json=output,
        model=get_business_config().get("llm", {}).get("model"),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        duration_ms=duration_ms,
        status=status,
        error=error,
        created_at=datetime.utcnow(),
        user_id=user_id,
    )
    db.add(run)
    db.flush()
    return run


def _invoke_json(prompt: str, *, purpose: str, user_id: Optional[int], db: Session) -> dict:
    llm = get_chat_model(purpose=purpose)
    started = time.time()
    try:
        msg = llm.invoke(
            [
                SystemMessage(content="You are a deterministic assistant. Return ONLY JSON."),
                HumanMessage(content=prompt),
            ]
        )
        duration = int((time.time() - started) * 1000)
        parsed = _safe_json_loads(msg.content)
        out = parsed if isinstance(parsed, dict) else {"value": parsed}
        _record_run(
            db,
            agent="llm",
            purpose=purpose,
            prompt=prompt,
            output=out,
            user_id=user_id,
            duration_ms=duration,
            tokens_in=getattr(msg, "usage_metadata", {}).get("input_tokens") if hasattr(msg, "usage_metadata") else None,
            tokens_out=getattr(msg, "usage_metadata", {}).get("output_tokens") if hasattr(msg, "usage_metadata") else None,
        )
        return out
    except Exception as exc:  # noqa: BLE001
        duration = int((time.time() - started) * 1000)
        _record_run(
            db,
            agent="llm",
            purpose=purpose,
            prompt=prompt,
            output=None,
            user_id=user_id,
            duration_ms=duration,
            status="error",
            error=str(exc),
        )
        raise


# ---------------------------------------------------------------------------
# Stage 1: Curriculum planning
# ---------------------------------------------------------------------------

def stage_curriculum_planning(
    db: Session, *, student_payload: dict, teacher_requirements: dict, user: Optional[User]
) -> dict:
    semester = student_payload.get("semester")
    semester_label = (
        "上学期" if semester == 1 else "下学期" if semester == 2 else "(未指定)"
    )
    prompt = CURRICULUM_PLANNER.format(
        grade=student_payload.get("grade", ""),
        textbook=student_payload.get("textbook", ""),
        semester=semester_label,
        current_chapter=student_payload.get("current_chapter", ""),
        weak_points=json.dumps(student_payload.get("weak_points", []), ensure_ascii=False),
        strengths=json.dumps(student_payload.get("strengths", []), ensure_ascii=False),
        past_scores=json.dumps(student_payload.get("score_history", []), ensure_ascii=False),
        teacher_requirements=json.dumps(teacher_requirements, ensure_ascii=False),
    )
    return _invoke_json(prompt, purpose="curriculum_planning", user_id=user.id if user else None, db=db)


# ---------------------------------------------------------------------------
# Stage 2: Question planning
# ---------------------------------------------------------------------------

def stage_question_planning(
    db: Session, *, curriculum: dict, teacher_requirements: dict, user: Optional[User]
) -> dict:
    prompt = QUESTION_PLANNER.format(
        question_count=teacher_requirements.get("question_count", 6),
        difficulty=teacher_requirements.get("difficulty", "medium"),
        knowledge_points=json.dumps(curriculum.get("knowledge_points", []), ensure_ascii=False),
        curriculum_recommendation=json.dumps(curriculum, ensure_ascii=False),
    )
    return _invoke_json(prompt, purpose="question_planning", user_id=user.id if user else None, db=db)


# ---------------------------------------------------------------------------
# Stage 3: Question generation (per A/B set)
# ---------------------------------------------------------------------------

def stage_question_generation(
    db: Session, *, plan: dict, student_payload: dict, existing_draft: Optional[dict], user: Optional[User]
) -> dict:
    prompt = QUESTION_GENERATOR.format(
        question_plan=json.dumps(plan, ensure_ascii=False),
        student_context=json.dumps(student_payload, ensure_ascii=False),
        existing_draft=json.dumps(existing_draft or {}, ensure_ascii=False),
    )
    return _invoke_json(prompt, purpose="question_generation", user_id=user.id if user else None, db=db)


# ---------------------------------------------------------------------------
# Stage 4: Diagram generation
# ---------------------------------------------------------------------------

def stage_diagram_generation(db: Session, *, prompt: str, user: Optional[User]) -> tuple[str, str]:
    """Return (format, markup). Empty string if generation failed."""
    llm_prompt = build_diagram_prompt(prompt)
    llm = get_chat_model(purpose="diagram_generation")
    started = time.time()
    try:
        msg = llm.invoke(
            [
                SystemMessage(content="Return ONLY JSON."),
                HumanMessage(content=llm_prompt),
            ]
        )
        duration = int((time.time() - started) * 1000)
        fmt, payload = diagram_from_json(msg.content)
        _record_run(
            db,
            agent="diagram",
            purpose="diagram_generation",
            prompt=llm_prompt,
            output={"format": fmt, "spec": payload},
            user_id=user.id if user else None,
            duration_ms=duration,
        )
        return fmt, payload
    except Exception as exc:  # noqa: BLE001
        _record_run(
            db,
            agent="diagram",
            purpose="diagram_generation",
            prompt=llm_prompt,
            output=None,
            user_id=user.id if user else None,
            status="error",
            error=str(exc),
        )
        return "", ""


# ---------------------------------------------------------------------------
# Stage 5: Validation
# ---------------------------------------------------------------------------

def stage_validation(
    db: Session, *, generated: dict, student_payload: dict, user: Optional[User]
) -> dict:
    prompt = VALIDATOR.format(
        set_summary=json.dumps(generated, ensure_ascii=False),
        student_context=json.dumps(student_payload, ensure_ascii=False),
    )
    out = _invoke_json(prompt, purpose="validation", user_id=user.id if user else None, db=db)

    # Cross-check with deterministic local rubric.
    deterministic_issues: list[str] = []
    for q in generated.get("questions", []):
        from app.models.assignments import Question as _Q

        fake = _Q(
            id=0,
            question_set_id=0,
            order=q.get("order", 0),
            qtype=q.get("qtype", ""),
            subject=q.get("subject", ""),
            prompt=q.get("prompt", ""),
            rubric=q.get("rubric"),
            answer_key=q.get("answer_key"),
            knowledge_points=q.get("knowledge_points", []),
            difficulty=q.get("difficulty", "medium"),
            estimated_minutes=q.get("estimated_minutes"),
            diagram_svg=q.get("diagram_svg"),
            diagram_format=q.get("diagram_format"),
        )
        deterministic_issues.extend(validate_question(fake))

    if deterministic_issues:
        out["ok"] = False
        out["issues"] = list({*out.get("issues", []), *deterministic_issues})
    return out


# ---------------------------------------------------------------------------
# Stage 6: Grading (advisory)
# ---------------------------------------------------------------------------

def stage_grading(
    db: Session, *, submission: Submission, question_set: QuestionSet, user: Optional[User]
) -> dict:
    question_blob = []
    for q in question_set.questions:
        question_blob.append(
            {
                "order": q.order,
                "prompt": q.prompt,
                "rubric": q.rubric,
                "answer_key": q.answer_key,
                "knowledge_points": q.knowledge_points,
            }
        )
    prompt = GRADING.format(
        question_with_rubric=json.dumps(question_blob, ensure_ascii=False),
        submission_text=submission.ocr_text or submission.text_answer or "",
        knowledge_points=json.dumps(
            [kp for q in question_set.questions for kp in (q.knowledge_points or [])],
            ensure_ascii=False,
        ),
    )
    return _invoke_json(prompt, purpose="grading", user_id=user.id if user else None, db=db)


# ---------------------------------------------------------------------------
# Stage 7: Archive summary
# ---------------------------------------------------------------------------

def stage_archive_summary(
    db: Session, *, student_payload: dict, history: list[dict], user: Optional[User]
) -> dict:
    prompt = ARCHIVE_SUMMARY.format(
        student=json.dumps(student_payload, ensure_ascii=False),
        history=json.dumps(history, ensure_ascii=False),
    )
    return _invoke_json(prompt, purpose="archive_summary", user_id=user.id if user else None, db=db)


# ---------------------------------------------------------------------------
# Stage 8: Learning plan (PRD §30)
# ---------------------------------------------------------------------------

def stage_learning_plan(
    db: Session,
    *,
    student_payload: dict,
    diagnosis: dict,
    states: list[dict],
    user_id: Optional[int],
) -> tuple[dict, int]:
    """Generate a learning plan. Returns (plan_data, llm_run_id)."""
    prompt = LEARNING_PLANNER.format(
        student_payload=json.dumps(student_payload, ensure_ascii=False),
        diagnosis=json.dumps(diagnosis, ensure_ascii=False),
        states=json.dumps(states, ensure_ascii=False),
    )
    llm = get_chat_model(purpose="learning_planning")
    started = time.time()
    try:
        msg = llm.invoke(
            [
                SystemMessage(content="You are a deterministic assistant. Return ONLY JSON."),
                HumanMessage(content=prompt),
            ]
        )
        duration = int((time.time() - started) * 1000)
        parsed = _safe_json_loads(msg.content)
        out = parsed if isinstance(parsed, dict) else {"value": parsed}
        run = _record_run(
            db,
            agent="learning_planner",
            purpose="learning_planning",
            prompt=prompt,
            output=out,
            user_id=user_id,
            duration_ms=duration,
        )
        return out, run.id
    except Exception as exc:  # noqa: BLE001
        duration = int((time.time() - started) * 1000)
        _record_run(
            db,
            agent="learning_planner",
            purpose="learning_planning",
            prompt=prompt,
            output=None,
            user_id=user_id,
            duration_ms=duration,
            status="error",
            error=str(exc),
        )
        raise


# ---------------------------------------------------------------------------
# Top-level driver: produce 2 question sets (A and B) end-to-end
# ---------------------------------------------------------------------------

def generate_two_sets(
    db: Session,
    *,
    student_payload: dict,
    teacher_requirements: dict,
    user: Optional[User],
) -> dict:
    """Generate two candidate question sets (A/B) and return them as JSON.

    Returns:
        {
          "curriculum": {...},
          "plan": {...},
          "sets": [
              {"label": "A", "questions": [...], "validator_notes": "..."},
              {"label": "B", "questions": [...], "validator_notes": "..."}
          ]
        }
    """
    curriculum = stage_curriculum_planning(db, student_payload=student_payload, teacher_requirements=teacher_requirements, user=user)
    plan = stage_question_planning(db, curriculum=curriculum, teacher_requirements=teacher_requirements, user=user)

    sets: list[dict] = []
    for label in ("A", "B"):
        generated = stage_question_generation(
            db, plan=plan, student_payload=student_payload, existing_draft=None, user=user
        )
        # Fill geometry diagrams where missing.
        for q in generated.get("questions", []):
            if q.get("subject") == "math" and q.get("needs_diagram") and not q.get("diagram_svg"):
                fmt, payload = stage_diagram_generation(db, prompt=q.get("prompt", ""), user=user)
                if fmt:
                    q["diagram_format"] = fmt
                    q["diagram_svg"] = payload
        validation = stage_validation(db, generated=generated, student_payload=student_payload, user=user)
        sets.append(
            {
                "label": label,
                "questions": generated.get("questions", []),
                "validator_notes": (
                    "OK" if validation.get("ok") else "; ".join(validation.get("issues", []))
                ),
            }
        )

    return {"curriculum": curriculum, "plan": plan, "sets": sets}