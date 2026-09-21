"""Route helpers: bootstrap, role checks, audit shortcuts, file validation."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, Request, status

from app.config import get_business_config, resolve_path
from app.security import sha256_of_bytes


# --- Magic Bytes validation (PRD §85) ----------------------------------------
# File-signature sniffing so a client cannot lie about Content-Type.

_MAGIC_BYTES: list[tuple[bytes, str, str]] = [
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"RIFF", "image/webp", "webp"),  # followed by ....WEBP at offset 8
    (b"%PDF-", "application/pdf", "pdf"),
    (b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
]

_WEBP_TRAILER_OFFSET = 8


def sniff_mime(data: bytes) -> tuple[str, str] | None:
    """Return (mime, ext) by inspecting the first few bytes; None when unrecognised.

    PDF/DOCX are sniffed but not part of the standard image allow-list (caller
    chooses what to accept). WEBP needs a trailer check because RIFF is also
    used by WAV/AVI.
    """
    if not data:
        return None
    head = data[:16]
    for magic, mime, ext in _MAGIC_BYTES:
        if head.startswith(magic):
            if mime == "image/webp":
                if len(data) > _WEBP_TRAILER_OFFSET + 4 and data[8:12] == b"WEBP":
                    return mime, ext
                continue
            return mime, ext
    return None


def assert_supported_upload(
    *,
    raw: bytes,
    declared_mime: str,
    allowed_mimes: dict[str, str],
) -> tuple[str, str]:
    """PRD §85 — verify both Content-Type header and file magic bytes match.

    Returns the (mime, ext) actually used for storage. Raises 400 when the
    declared MIME is not in `allowed_mimes` OR when the magic bytes do not
    agree with the declared MIME (i.e. the client lied).

    The MIME allow-list may carry legacy aliases (e.g. ``image/jpg``) that
    map to the same extension as their canonical form (``image/jpeg``). We
    compare the *extension* rather than the literal MIME string so that
    legacy aliases do not get falsely rejected.
    """
    declared = (declared_mime or "").lower().strip()
    ext = allowed_mimes.get(declared)
    if not ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {declared or '(none)'}",
        )
    sniffed = sniff_mime(raw)
    if sniffed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File contents do not match declared type: {declared}",
        )
    # Compare extensions, not MIME strings, so ``image/jpg`` (legacy alias)
    # and ``image/jpeg`` (canonical) both pass for a real JPEG.
    if sniffed[1] != ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File contents do not match declared type: {declared}",
        )
    return sniffed[0], ext


logger = logging.getLogger(__name__)


def require_teacher_role(user) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher role required")


def ensure_default_teacher_exists(db, settings) -> bool:
    """Returns True if a default teacher was created.

    Reads the initial password from `settings.pass_word` (populated by
    `get_settings()` from `PASS_WORD` in the environment / `.env`).
    If missing, the function refuses to create the user; install.sh is
    responsible for ensuring `PASS_WORD` is set.
    """
    from app.models.auth import User
    from app.security import hash_password

    cfg = get_business_config()
    default = (cfg.get("app") or {}).get("default_teacher") or {}
    username = default.get("username", "yun")
    if db.query(User).filter(User.username == username).first():
        return False
    initial_password = settings.pass_word or ""
    if not initial_password:
        raise RuntimeError(
            "PASS_WORD is not set. Run ./install.sh or set PASS_WORD in .env first."
        )
    if len(initial_password) < 8:
        raise RuntimeError("PASS_WORD must be at least 8 characters long.")
    user = User(
        username=username,
        password_hash=hash_password(initial_password),
        role="teacher",
        display_name=default.get("display_name", username),
        must_change_password=default.get("must_change_password", True),
        is_active=True,
    )
    db.add(user)
    db.commit()
    logger.info("Created default teacher '%s'", username)
    return True


def safe_join_uploads(*parts: str) -> Path:
    """Sanitize a relative path under the uploads directory.

    Resolves ``..`` segments and rejects paths that escape the base via
    sibling directories (e.g. ``uploads_evil`` when base is ``uploads``).
    """
    base = resolve_path("uploads").resolve()
    candidate = base.joinpath(*parts).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path") from None
    return candidate


def get_keep_original_filename() -> bool:
    """PRD §87 — honour ``uploads.keep_original_filename`` (default false)."""
    return bool((get_business_config().get("uploads") or {}).get("keep_original_filename", False))


def get_compute_sha256() -> bool:
    """PRD §87 — honour ``uploads.compute_sha256`` (default true)."""
    val = (get_business_config().get("uploads") or {}).get("compute_sha256", True)
    return bool(val)


def get_allowed_mime_table(defaults: dict[str, str]) -> dict[str, str]:
    """Honour ``app.allowed_image_types`` when present.

    ``configure.json`` lists extensions (jpg/jpeg/png/webp/pdf). We map each
    extension to its canonical MIME type. Synonyms that are not in the
    defaults table (e.g. ``jpeg`` is a common alias for ``jpg``) are
    resolved through a fixed alias table.
    """
    cfg_exts = (get_business_config().get("app") or {}).get("allowed_image_types")
    if not cfg_exts:
        return defaults
    # Canonical ext → list of equivalent extensions that map to the same MIME.
    ext_synonyms: dict[str, tuple[str, ...]] = {
        "jpg": ("jpeg",),
        "jpeg": ("jpg",),
    }
    # Resolve each cfg ext to a canonical ext present in defaults.
    ext_to_mime = {v: k for k, v in defaults.items()}
    out: dict[str, str] = {}
    for raw_ext in cfg_exts:
        ext = str(raw_ext).lower().lstrip(".")
        # If ext is itself a key in defaults (most common case), use it.
        canonical = ext if ext in ext_to_mime else None
        if canonical is None:
            # Try synonyms of known canonicals.
            for canon, syns in ext_synonyms.items():
                if ext == canon or ext in syns:
                    if canon in ext_to_mime:
                        canonical = canon
                        break
        if canonical is None:
            continue
        mime = ext_to_mime[canonical]
        out[mime] = defaults[mime]
    return out or defaults


def sha256_bytes(data: bytes) -> str:
    return sha256_of_bytes(data)


def now() -> datetime:
    return datetime.utcnow()