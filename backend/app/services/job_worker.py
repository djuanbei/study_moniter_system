"""Async jobs infrastructure (PRD §82–83).

One background thread per app process polls the `jobs` table and runs
queued jobs serially (max_concurrent_heavy_jobs = 1). Jobs are claimed
atomically so multiple uvicorn workers never double-run a job. Failures
retry up to max_attempts, then the job is FAILED with the error stored.

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
