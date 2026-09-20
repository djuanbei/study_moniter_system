"""Material Agent tests (PRD §22–23)."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.models.materials import Material, MaterialCandidate
from app.services.material_agent import (
    Discovered,
    agent_config,
    approve_candidate,
    build_queries,
    discover_materials,
)


@pytest.fixture()
def fake_provider(monkeypatch):
    """Inject a deterministic search provider (no network)."""
    import app.services.material_agent as agent

    calls = []

    def search(query: str):
        calls.append(query)
        return [
            Discovered(
                title=f"练习题 - {query}",
                url=f"https://example.com/ex/{len(calls)}",
                domain="example.com",
                snippet="公开练习题",
                license="CC-BY",
                raw={"title": "x"},
            ),
            # duplicate URL across queries must be deduped
            Discovered(
                title="重复页",
                url="https://example.com/ex/1",
                domain="example.com",
                snippet=None,
                license="unknown",
                raw={},
            ),
        ]

    monkeypatch.setattr(agent, "_provider", lambda cfg: search)
    return calls


def test_agent_disabled_without_provider(db_session):
    result = discover_materials(db_session)
    assert result.get("no_provider") is True


def test_discovery_creates_deduped_candidates(db_session, sample_setup, fake_provider):
    result = discover_materials(db_session)
    assert result.get("candidates", 0) >= 1
    total = db_session.query(MaterialCandidate).count()
    urls = {c.url for c in db_session.query(MaterialCandidate).all()}
    assert total == len(urls)  # deduped by content hash (§22 validation)

    cand = db_session.query(MaterialCandidate).first()
    # §23 provenance fields
    assert cand.domain == "example.com"
    assert cand.license == "CC-BY"
    assert cand.content_hash and len(cand.content_hash) == 64
    assert cand.retrieved_at is not None
    assert cand.status == "discovered"  # never auto-imported (§87)


def test_build_queries_uses_chapters(db_session, sample_setup):
    queries = build_queries(db_session, limit=3)
    assert queries
    assert all("knowledge_point" in q and "query" in q for q in queries)


def test_approve_fetches_into_material_library(db_session, sample_setup, fake_provider, monkeypatch):
    discover_materials(db_session)
    db_session.commit()
    cand = db_session.query(MaterialCandidate).first()

    class FakeResp:
        content = b"<html><body><h1>test</h1><p>content body</p></body></html>"
        text = "<html><body><h1>test</h1><p>content body</p></body></html>"
        headers = {"content-type": "text/html; charset=utf-8"}

        def raise_for_status(self):
            pass

    import app.services.material_agent as agent

    monkeypatch.setattr(agent.httpx, "get", lambda *a, **k: FakeResp())
    material = approve_candidate(db_session, cand, user=None)
    db_session.commit()
    assert material.source == "AGENT_DISCOVERED"  # §21
    assert material.license == "CC-BY"
    meta = material.source_metadata
    assert meta["url"] == cand.url and meta["domain"] == cand.domain  # §23
    assert "content body" in (material.ocr_text or "")
    assert cand.status == "approved" and cand.material_id == material.id


def test_double_approve_rejected(db_session, sample_setup, fake_provider, monkeypatch):
    discover_materials(db_session)
    db_session.commit()
    cand = db_session.query(MaterialCandidate).first()

    class FakeResp:
        content = b"x"
        text = "x"
        headers = {"content-type": "text/plain"}

        def raise_for_status(self):
            pass

    import app.services.material_agent as agent

    monkeypatch.setattr(agent.httpx, "get", lambda *a, **k: FakeResp())
    approve_candidate(db_session, cand)
    with pytest.raises(ValueError):
        approve_candidate(db_session, cand)


def test_material_discovery_job_registered():
    from app.services.job_worker import registered_types

    assert "MATERIAL_DISCOVERY" in registered_types()


def test_auto_import_stays_false():
    # §87: candidates must never be auto-imported
    assert agent_config()["auto_import"] is False
