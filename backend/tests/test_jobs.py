"""Async job worker tests (PRD §82–83)."""

from __future__ import annotations

import pytest

from app.services import job_worker
from app.services.job_worker import (
    claim_next_job,
    enqueue,
    registered_types,
    run_job,
    run_pending_jobs,
)


@pytest.fixture(autouse=True)
def _echo_handler(monkeypatch):
    """Register a deterministic handler without touching global state."""
    monkeypatch.setitem(job_worker._HANDLERS, "TEST_ECHO", lambda db, payload, user_id: {"echo": payload})
    monkeypatch.setitem(
        job_worker._HANDLERS, "TEST_ALWAYS_FAILS",
        lambda db, payload, user_id: (_ for _ in ()).throw(RuntimeError("boom")),
    )


def test_enqueue_rejects_unknown_type(db_session):
    import pytest as _pytest

    with _pytest.raises(ValueError):
        enqueue(db_session, job_type="NO_SUCH_TYPE", payload={})


def test_registered_types_include_prd_jobs():
    types = registered_types()
    for expected in ("QUESTION_GENERATION", "LEARNING_PLAN_GENERATION",
                     "MATERIAL_ANALYSIS", "HISTORY_ANALYSIS"):
        assert expected in types


def test_lifecycle_succeeded(db_session):
    job = enqueue(db_session, job_type="TEST_ECHO", payload={"x": 1})
    db_session.commit()
    assert job.status == "QUEUED"

    claimed = claim_next_job(db_session)
    assert claimed is not None and claimed.id == job.id
    assert claimed.status == "RUNNING"
    assert claimed.attempts == 1

    job = run_job(db_session, claimed)
    assert job.status == "SUCCEEDED"
    assert job.result == {"echo": {"x": 1}}
    assert job.finished_at is not None


def test_retry_then_failed(db_session):
    job = enqueue(db_session, job_type="TEST_ALWAYS_FAILS", payload={}, max_attempts=2)
    db_session.commit()

    for attempt in range(1, 3):
        claimed = claim_next_job(db_session)
        assert claimed.attempts == attempt
        job = run_job(db_session, claimed)
        if attempt < 2:
            assert job.status == "QUEUED"  # requeued for retry (PRD §83)
            assert "boom" in (job.error or "")
        else:
            assert job.status == "FAILED"
            assert job.finished_at is not None

    # FAILED jobs are not re-claimed
    assert claim_next_job(db_session) is None


def test_cancel_queued_job(db_session, client, csrf_headers):
    job = enqueue(db_session, job_type="TEST_ECHO", payload={})
    db_session.commit()

    r = client.post(f"/api/jobs/{job.id}/cancel", headers=csrf_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"

    # cancelled jobs are never claimed
    assert claim_next_job(db_session) is None


def test_run_pending_drains_queue(db_session):
    for i in range(3):
        enqueue(db_session, job_type="TEST_ECHO", payload={"i": i})
    db_session.commit()
    ran = run_pending_jobs(db_session)
    assert ran == 3
    assert db_session.query(job_worker.Job).filter_by(status="QUEUED").count() == 0


def test_jobs_api_flow(db_session, client, csrf_headers, sample_setup):
    """API enqueue with the real MATERIAL_ANALYSIS handler (deterministic)."""
    r = client.post("/api/jobs", headers=csrf_headers, json={
        "job_type": "LEARNING_PLAN_GENERATION",
        "payload": {"student_id": sample_setup["student"].id},
    })
    assert r.status_code == 202
    job_id = r.json()["id"]

    ran = run_pending_jobs(db_session)
    assert ran == 1
    r = client.get(f"/api/jobs/{job_id}")
    body = r.json()
    assert body["status"] == "SUCCEEDED"
    assert body["result"]["plan_id"] > 0


def test_jobs_api_requires_teacher(db_session, client, student_user):
    student_user_obj, _student = student_user
    from app.deps import get_current_user

    client.app.dependency_overrides[get_current_user] = lambda: student_user_obj
    try:
        r = client.post("/api/jobs", headers={"X-CSRF-Token": "test-token"},
                        json={"job_type": "TEST_ECHO", "payload": {}})
        assert r.status_code == 403
        r = client.get("/api/jobs")
        assert r.status_code == 403
    finally:
        client.app.dependency_overrides.pop(get_current_user, None)
