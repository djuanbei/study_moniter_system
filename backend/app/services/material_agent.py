"""Material Agent (PRD §22): discover public learning materials.

    教材/知识点 -> search provider -> candidates -> validation (dedupe)
    -> parent review -> Material Library

Copyright (§23): every candidate stores url, domain, retrieved_at,
content_hash and license; third-party materials are never auto-imported
(auto_import is always false, §87).

Search is pluggable: any JSON HTTP search API works via configuration
(configure.json material_agent.search). With no endpoint configured the
agent reports itself disabled instead of failing.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
import re
import socket
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import quote, urlparse

import httpx
from sqlalchemy.orm import Session

from app.config import get_business_config
from app.models.materials import Material, MaterialCandidate
from app.models.students import Chapter

logger = logging.getLogger(__name__)

_CONTENT_TYPE_EXT = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/html": "txt",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


_LOCAL_NAMES = re.compile(r"^(localhost|.*\.local|.*\.internal|.*\.lan)$", re.IGNORECASE)


def _validate_public_url(url: str, resolve_hostnames: bool = True) -> bool:
    """SSRF guard (approve fetches server-side): only public http(s) hosts.

    Rejects non-http(s) schemes, local-looking names, and any host that
    resolves to private/loopback/link-local/reserved/multicast addresses.
    With resolve_hostnames=False only cheap checks run (used while scanning;
    approve always fully resolves).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        return not (
            ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified
        )
    if _LOCAL_NAMES.match(host):
        return False
    if not resolve_hostnames:
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False  # unresolvable hosts cannot be fetched either
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (
            addr.is_private or addr.is_loopback or addr.is_link_local
            or addr.is_reserved or addr.is_multicast or addr.is_unspecified
        ):
            return False
    return True


@dataclass
class Discovered:
    title: str
    url: str
    domain: str
    snippet: Optional[str]
    license: str
    raw: dict


def agent_config() -> dict:
    cfg = (get_business_config().get("material_agent") or {})
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "schedule": cfg.get("schedule", "weekly"),
        "max_candidates_per_run": int(cfg.get("max_candidates_per_run", 50)),
        "auto_import": bool(cfg.get("auto_import", False)),  # §87: always false
        "search": cfg.get("search") or {},
    }


def _provider(config: dict):
    """Return a search callable: query -> list[Discovered]. None if unset."""
    endpoint = (config.get("endpoint") or "").strip()
    if not endpoint:
        return None
    query_param = config.get("query_param", "q")
    result_path = config.get("result_path", "results")
    fields = config.get("fields") or {}
    api_key_env = (config.get("api_key_env") or "").strip()
    headers = {}
    if api_key_env and os.environ.get(api_key_env):
        headers["Authorization"] = f"Bearer {os.environ[api_key_env]}"

    def search(query: str) -> list[Discovered]:
        resp = httpx.get(
            endpoint, params={query_param: query}, headers=headers, timeout=15,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
        for key in result_path.split("."):
            data = data[key]
        out: list[Discovered] = []
        for row in data:
            get = lambda k: row.get(fields.get(k) or k)  # noqa: E731
            url = str(get("url") or "")
            if not url.startswith("http"):
                continue
            parsed = urlparse(url)
            out.append(
                Discovered(
                    title=str(get("title") or url)[:255],
                    url=url,
                    domain=parsed.netloc[:128],
                    snippet=str(get("snippet"))[:1000] if get("snippet") else None,
                    license=str(get("license") or "unknown")[:64],
                    raw=row,
                )
            )
        return out

    return search


def build_queries(db: Session, limit: int = 5) -> list[dict]:
    """Queries from textbook chapters + weakest knowledge points (§22)."""
    queries: list[dict] = []
    seen: set[str] = set()
    for ch in db.query(Chapter).order_by(Chapter.id.desc()).limit(limit * 2).all():
        for kp in (ch.knowledge_points or [])[:2]:
            q = f"{kp} 练习 {ch.grade or ''}".strip()
            if q not in seen:
                seen.add(q)
                queries.append({"query": q, "knowledge_point": str(kp), "grade": ch.grade})
        if len(queries) >= limit:
            break
    return queries


def discover_materials(db: Session, *, user=None) -> dict:
    """Run one discovery pass; dedupe by URL/content hash (§22 validation)."""
    cfg = agent_config()
    if not cfg["enabled"]:
        return {"disabled": True, "candidates": 0}
    search = _provider(cfg["search"])
    if search is None:
        return {"no_provider": True, "candidates": 0,
                "message": "未配置搜索源（configure.json material_agent.search.endpoint）"}

    max_new = cfg["max_candidates_per_run"]
    queries = build_queries(db)
    created = 0
    duplicates = 0
    scanned = 0
    now = datetime.utcnow()
    seen_hashes: set[str] = set()
    stop = False
    for entry in queries:
        if stop:
            break
        try:
            results = search(entry["query"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("material agent search failed for %r: %s", entry["query"], exc)
            continue
        for disc in results:
            scanned += 1
            if scanned >= max_new * 5:  # hard guard against unbounded corpora
                stop = True
                break
            if created >= max_new:
                stop = True
                break
            content_hash = hashlib.sha256(disc.url.encode("utf-8")).hexdigest()
            if content_hash in seen_hashes:
                duplicates += 1
                continue  # deduped within this run (autoflush is off)
            exists = (
                db.query(MaterialCandidate)
                .filter(MaterialCandidate.content_hash == content_hash)
                .first()
            )
            if exists:
                seen_hashes.add(content_hash)
                duplicates += 1
                continue
            if not _validate_public_url(disc.url, resolve_hostnames=False):
                duplicates += 1  # non-public hosts are skipped entirely
                continue
            db.add(
                MaterialCandidate(
                    title=disc.title,
                    url=disc.url,
                    domain=disc.domain,
                    snippet=disc.snippet,
                    query=entry["query"],
                    knowledge_point=entry["knowledge_point"],
                    grade=entry["grade"],
                    license=disc.license,
                    content_hash=content_hash,
                    source_metadata={"raw": disc.raw, "provider": cfg["search"].get("provider", "http_json")},
                    status="discovered",
                    retrieved_at=now,
                )
            )
            seen_hashes.add(content_hash)
            created += 1
    db.flush()
    # §87: auto_import is false — candidates wait for parent approval.
    return {"candidates": created, "duplicates": duplicates, "queries": len(queries)}


def _strip_html(html: str) -> str:
    import re

    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def approve_candidate(db: Session, candidate: MaterialCandidate, user=None) -> Material:
    """Parent-approved candidate -> fetched into the Material library (§22).

    §23: the original stays at its source; we store provenance + license and
    never republish third-party content automatically.
    """
    if candidate.status != "discovered":
        raise ValueError("该候选已处理")
    if not _validate_public_url(candidate.url):
        # full validation incl. DNS resolution (SSRF guard)
        raise ValueError("URL 指向非公开或不可解析地址，已拒绝抓取")
    resp = httpx.get(candidate.url, timeout=20, follow_redirects=True,
                     headers={"User-Agent": "LearningCompanion/0.1"})
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "text/html").split(";")[0].strip().lower()
    if content_type in ("text/html", "text/plain") or content_type.startswith("text/"):
        text = _strip_html(resp.text)[:50000]
        ext = "txt"
        mime = "text/plain"
    else:
        text = None
        # Extension comes from the URL *path* (not the whole URL — the last
        # dot is usually in the domain), falling back to content-type.
        path_ext = os.path.splitext(urlparse(candidate.url).path)[1].lstrip(".").lower()
        if re.fullmatch(r"[a-z0-9]{1,8}", path_ext):
            ext = path_ext
        else:
            ext = _CONTENT_TYPE_EXT.get(content_type, "bin")
        mime = content_type or "application/octet-stream"

    raw = resp.content
    sha = hashlib.sha256(raw).hexdigest()
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
    from app.config import resolve_path

    rel_dir = "data/materials"
    resolve_path(rel_dir).mkdir(parents=True, exist_ok=True)
    rel_path = f"{rel_dir}/{ts}_{sha[:8]}_agent.{ext}"
    resolve_path(rel_path).write_bytes(raw)

    material = Material(
        material_type="OTHER",
        title=candidate.title[:128],
        grade=candidate.grade,
        filename=candidate.title[:100] or "agent-material",
        rel_path=rel_path,
        sha256=sha,
        mime_type=mime,
        size_bytes=len(raw),
        source="AGENT_DISCOVERED",
        license=candidate.license,
        source_metadata={
            "url": candidate.url,
            "domain": candidate.domain,
            "retrieved_at": candidate.retrieved_at.isoformat(),
            "content_hash": candidate.content_hash,
            "query": candidate.query,
            "knowledge_point": candidate.knowledge_point,
        },
        ocr_text=text,
        created_by=user.id if user else None,
    )
    db.add(material)
    db.flush()
    candidate.status = "approved"
    candidate.material_id = material.id
    candidate.reviewed_by = user.id if user else None
    db.flush()
    return material
