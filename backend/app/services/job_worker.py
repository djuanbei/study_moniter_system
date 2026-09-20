"""Async jobs infrastructure (PRD §82–83).

One background thread per app process polls the `jobs` table and runs
queued jobs serially (max_concurrent_heavy_jobs = 1). Jobs are claimed
atomically so multiple uvicorn workers never double-run a job. Failures
retry up to max_attempts, then the job is FAILED with the error stored.

States (PRD §82): QUEUED -> RUNNING -> SUCCEEDED | FAILED; QUEUED jobs can
be CANCELLED before they are claimed.

Handlers registry maps PRD §82 job types to callables:
    handler(db, payload: dict, user_id) -> result dict (stored in job.result)
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.system import Job

logger = logging.getLogger(__name__)

Handler = Callable[[Session, dict, Optional[int]], dict]

_HANDLERS: dict[str, Handler] = {}
_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None
_worker_seq = 0
_worker_lock = threading.Lock()


def register(job_type: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _HANDLERS[job_type] = fn
        return fn
    return deco


def registered_types() -> list[str]:
    return sorted(_HANDLERS)


# ---------------------------------------------------------------------------
# Handlers (PRD §82 job types implemented so far)
# ---------------------------------------------------------------------------

@register("QUESTION_GENERATION")
def run_question_generation(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    from app.models.students import Student
    from app.services.llm import generate_two_sets

    student = db.get(Student, int(payload["student_id"]))
    if not student:
        raise ValueError("student not found")
    student_payload = {
        "grade": student.grade,
        "textbook": student.textbook_version,
        "semester": student.current_semester,
        "current_chapter": student.current_chapter.title if student.current_chapter else None,
        "weak_points": student.weak_points or [],
        "strengths": student.strengths or [],
        "score_history": student.score_history or [],
    }
    result = generate_two_sets(
        db,
        student_payload=student_payload,
        teacher_requirements={
            "question_count": payload.get("question_count", 6),
            "difficulty": payload.get("difficulty", "medium"),
            "knowledge_points": payload.get("knowledge_points", []),
            "question_types": payload.get("question_types", []),
            "semester": payload.get("semester") or student.current_semester,
            "due_date": payload.get("due_date"),
            "estimated_minutes": payload.get("estimated_minutes"),
            "calculator_allowed": bool(payload.get("calculator_allowed")),
            "notes": payload.get("requirements"),
        },
        user=None,
    )
    return result


@register("LEARNING_PLAN_GENERATION")
def run_learning_plan(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    from app.models.students import Student
    from app.services.learning import generate_plan

    student = db.get(Student, int(payload["student_id"]))
    if not student:
        raise ValueError("student not found")
    plan = generate_plan(db, student, user_id=user_id)
    return {"plan_id": plan.id, "generated_by": plan.generated_by, "item_count": len(plan.items)}


@register("MATERIAL_ANALYSIS")
def run_material_analysis(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    from app.models.materials import Material
    from app.services.material_import import analyze_material

    material = db.get(Material, int(payload["material_id"]))
    if not material:
        raise ValueError("material not found")
    analyze_material(db, material, None)
    analysis = material.analysis_json or {}
    return {
        "material_id": material.id,
        "status": material.status,
        "chapters": analysis.get("chapters", []),
        "extracted_by": analysis.get("extracted_by"),
    }


@register("HISTORY_ANALYSIS")
def run_history_analysis(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    from app.models.materials import Material
    from app.services.historical_import import analyze_history

    material = db.get(Material, int(payload["material_id"]))
    if not material:
        raise ValueError("material not found")
    assessment = analyze_history(
        db,
        material=material,
        student_id=int(payload["student_id"]),
        exam_title=payload.get("exam_title", "历史试卷"),
        exam_date=payload.get("exam_date"),
        user=None,
    )
    return {
        "assessment_id": assessment.id,
        "question_count": len(assessment.questions),
        "extracted_by": (assessment.analysis_json or {}).get("extracted_by"),
    }


@register("QUESTION_BANK_UPDATE")
def run_bank_update(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§68: analysis + AI candidates; parent reviews before anything is applied."""
    from app.services.bank_update import generate_candidates

    return generate_candidates(
        db, batch_size=int(payload.get("batch_size", 3)), user=None
    )


@register("KNOWLEDGE_UPDATE")
def run_knowledge_update(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§69: knowledge-base analysis + candidates; parent reviews before apply."""
    from app.services.knowledge_update import generate_knowledge_candidates

    return generate_knowledge_candidates(
        db, batch_size=int(payload.get("batch_size", 20))
    )


@register("MATERIAL_DISCOVERY")
def run_material_discovery(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§22: one agent discovery pass; candidates wait for parent approval."""
    from app.services.material_agent import discover_materials

    return discover_materials(db)


# ---- Additional PRD §82 job types: serialized, retryable, async ----

@register("MATERIAL_IMPORT")
def run_material_import(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§19-20: import a remote URL into the material library."""
    from app.services.material_import import import_from_url

    return import_from_url(
        db,
        url=str(payload["url"]),
        title=payload.get("title") or "",
        material_type=payload.get("material_type", "TEXTBOOK"),
        user=None,
    )


@register("OCR")
def run_ocr(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§51-52: run OCR on an uploaded file (heavy work off the request path)."""
    from pathlib import Path

    from app.services.ocr import ocr_image, ocr_pdf

    rel_path = payload.get("rel_path")
    if not rel_path:
        raise ValueError("rel_path is required")
    p = Path(rel_path)
    text = ocr_pdf(p) if p.suffix.lower() == ".pdf" else ocr_image(p)
    return {"rel_path": rel_path, "ocr_chars": len(text), "preview": text[:500]}


@register("VISION")
def run_vision(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§51-52: vision-model OCR / extraction."""
    from pathlib import Path

    from app.services.ocr import ocr_with_vision

    rel_path = payload.get("rel_path")
    if not rel_path:
        raise ValueError("rel_path is required")
    text = ocr_with_vision(Path(rel_path))
    return {"rel_path": rel_path, "vision_chars": len(text), "preview": text[:500]}


@register("QUESTION_VALIDATION")
def run_question_validation(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§38: deterministic + LLM validation pass for a candidate question set."""
    from app.models.assignments import QuestionSet
    from app.services.rubric import validate_question

    qs = db.get(QuestionSet, int(payload["question_set_id"]))
    if not qs:
        raise ValueError("question_set not found")
    issues: list[str] = []
    for q in qs.questions:
        issues.extend(validate_question(q))
    return {"question_set_id": qs.id, "issues": list({*issues})}


@register("SIMILAR_QUESTION_SEARCH")
def run_similar_search(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§41: async wrapper around similarity search so heavy loads don't block."""
    from app.services.question_bank import find_similar

    results = find_similar(
        db,
        question_id=int(payload["question_id"]),
        top_k=int(payload.get("top_k", 5)),
        same_kp_only=bool(payload.get("same_kp_only", False)),
    )
    return {"question_id": payload["question_id"], "matches": results}


@register("GRADING")
def run_grading(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§42-48: AI grading for a submission; result mirrors /grading/suggest."""
    from app.models.assignments import Grading, QuestionSet, Submission
    from app.services.learning import grading_triage

    sub = db.get(Submission, int(payload["submission_id"]))
    if not sub:
        raise ValueError("submission not found")
    from app.models.assignments import Assignment

    a = db.get(Assignment, sub.assignment_id)
    qs = db.get(QuestionSet, a.question_set_id) if a else None
    if qs is None:
        raise ValueError("question set not found")

    from app.services.llm import stage_grading

    advisory = stage_grading(db, submission=sub, question_set=qs, user=None)
    grading = (
        db.query(Grading).filter(Grading.submission_id == sub.id).order_by(Grading.id.desc()).first()
    )
    if grading is None:
        grading = Grading(submission_id=sub.id)
        db.add(grading)
    grading.llm_suggested_score = advisory.get("suggested_score")
    grading.llm_suggested_feedback = advisory.get("feedback")
    grading.llm_knowledge_mastery = advisory.get("knowledge_mastery")
    grading.per_question_scores = advisory.get("per_question")

    per_question = advisory.get("per_question") or []
    qtypes = [q.qtype for q in qs.questions]
    confidence, needs_review = grading_triage(per_question, qtypes)
    grading.llm_confidence = confidence
    grading.needs_review = needs_review
    db.commit()
    return {"grading_id": grading.id, "needs_review": needs_review, "confidence": confidence}


@register("STATE_UPDATE")
def run_state_update(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§60: refresh decay_risk / next_review_at (heavy on large student pools)."""
    from app.services.learning import compute_decay_refresh

    student_id = payload.get("student_id")
    compute_decay_refresh(db, int(student_id) if student_id else None)
    db.commit()
    return {"student_id": student_id, "ok": True}


@register("DIAGNOSIS")
def run_diagnosis(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§29 + §70: Diagnosis Agent (deterministic + optional LLM augmentation)."""
    from app.services.learning import diagnose_student

    sid = int(payload["student_id"])
    result = diagnose_student(db, sid)
    return {"student_id": sid, "priorities": result.get("priorities", [])}


@register("PDF_EXPORT")
def run_pdf_export(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§78: PDF export for a question set / report (heavy work)."""
    from app.services.archive import export_question_set_pdf

    out_path = export_question_set_pdf(
        db, int(payload["question_set_id"]), variant=payload.get("variant", "student")
    )
    return {"path": str(out_path), "question_set_id": payload["question_set_id"]}


@register("DOCX_EXPORT")
def run_docx_export(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§79: DOCX export for a question set."""
    from app.services.docx_export import export_question_set_docx

    out_path = export_question_set_docx(
        db, int(payload["question_set_id"]), variant=payload.get("variant", "student")
    )
    return {"path": str(out_path), "question_set_id": payload["question_set_id"]}


@register("ARCHIVE_EXPORT")
def run_archive_export(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """§67: archive ZIP/CSV/PDF for a student."""
    from app.services.archive import export_student_archive

    out_path = export_student_archive(
        db,
        int(payload["student_id"]),
        formats=tuple(payload.get("formats", ("pdf", "csv", "images_zip"))),
    )
    return {"path": str(out_path), "student_id": payload["student_id"]}


# ---------------------------------------------------------------------------
# Claim / run loop
# ---------------------------------------------------------------------------

def enqueue(db: Session, *, job_type: str, payload: dict, user_id: Optional[int] = None,
            max_attempts: int = 3) -> Job:
    if job_type not in _HANDLERS:
        raise ValueError(f"unknown job type: {job_type}")
    job = Job(
        job_type=job_type,
        payload=payload,
        created_by=user_id,
        max_attempts=max(1, max_attempts),
        status="QUEUED",
    )
    db.add(job)
    db.flush()
    return job


def cancel_job(db: Session, job_id: int) -> Job:
    """PRD §82 — cancel a QUEUED job. RUNNING jobs cannot be cancelled safely."""
    job = db.get(Job, job_id)
    if not job:
        raise ValueError("job not found")
    if job.status == "QUEUED":
        job.status = "CANCELLED"
        job.finished_at = datetime.utcnow()
        db.commit()
    return job


def claim_next_job(db: Session) -> Optional[Job]:
    """Atomically claim the oldest QUEUED job (safe across processes)."""
    candidate = (
        db.query(Job)
        .filter(Job.status == "QUEUED")
        .order_by(Job.id.asc())
        .first()
    )
    if candidate is None:
        return None
    claimed = (
        db.query(Job)
        .filter(Job.id == candidate.id, Job.status == "QUEUED")
        .update(
            {
                "status": "RUNNING",
                "started_at": datetime.utcnow(),
                "attempts": Job.attempts + 1,
                "worker_id": _worker_name(),
            }
        )
    )
    if not claimed:
        return None
    db.commit()
    return db.get(Job, candidate.id)


def run_job(db: Session, job: Job) -> Job:
    """Execute one claimed job with retry handling."""
    handler = _HANDLERS.get(job.job_type)
    try:
        if handler is None:
            raise ValueError(f"no handler for job type {job.job_type}")
        result = handler(db, dict(job.payload or {}), job.created_by)
        job.status = "SUCCEEDED"
        job.result = result
        job.error = None
        job.finished_at = datetime.utcnow()
        db.commit()
        logger.info("job %s (%s) succeeded", job.id, job.job_type)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        job = db.get(Job, job.id)
        job.error = str(exc)[:2000]
        if job.attempts < job.max_attempts:
            job.status = "QUEUED"  # retry
            logger.warning("job %s failed (attempt %s/%s), requeued: %s",
                           job.id, job.attempts, job.max_attempts, exc)
        else:
            job.status = "FAILED"
            job.finished_at = datetime.utcnow()
            logger.error("job %s (%s) failed permanently: %s", job.id, job.job_type, exc)
        db.commit()
    return job


def run_pending_jobs(db: Session, limit: int = 20) -> int:
    """Synchronously drain QUEUED jobs (used by tests and manual recovery)."""
    ran = 0
    while ran < limit:
        job = claim_next_job(db)
        if job is None:
            break
        run_job(db, job)
        ran += 1
    return ran


def _worker_name() -> str:
    with _worker_lock:
        global _worker_seq
        _worker_seq += 1
        return f"worker-{threading.get_ident()}-{_worker_seq}"


def worker_loop(poll_seconds: float = 2.0) -> None:
    """Long-running loop; started in a daemon thread by start_worker()."""
    logger.info("job worker started (poll %.1fs)", poll_seconds)
    while not _stop_event.is_set():
        db = SessionLocal()
        try:
            job = claim_next_job(db)
            if job is None:
                db.rollback()
                _stop_event.wait(poll_seconds)
                continue
            run_job(db, job)
        except Exception:  # noqa: BLE001
            logger.exception("job worker iteration failed")
            db.rollback()
            _stop_event.wait(poll_seconds)
        finally:
            db.close()
    logger.info("job worker stopped")


def start_worker(poll_seconds: float = 2.0) -> bool:
    """Start the daemon worker thread once per process."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return False
    _stop_event.clear()
    _thread = threading.Thread(target=worker_loop, args=(poll_seconds,), daemon=True,
                               name="job-worker")
    _thread.start()
    return True


def stop_worker() -> None:
    _stop_event.set()
