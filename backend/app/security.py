"""Security primitives: password hashing, session cookies, CSRF tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings


# --- Optional Argon2 import ---------------------------------------------------

try:  # pragma: no cover
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError

    _hasher = PasswordHasher()
    _ARGON2_AVAILABLE = True
except ImportError:  # argon2-cffi missing (build deps unavailable)
    _hasher = None
    _ARGON2_AVAILABLE = False
    VerifyMismatchError = Exception  # type: ignore[misc,assignment]


def hash_password(password: str) -> str:
    settings = get_settings()
    if settings.password_hash == "bcrypt" or not _ARGON2_AVAILABLE:
        import bcrypt

        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    settings = get_settings()
    try:
        if settings.password_hash == "bcrypt" or not _ARGON2_AVAILABLE:
            import bcrypt

            if bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8")):
                return True
        else:
            if _hasher.verify(hashed, password):
                return True
    except (VerifyMismatchError, ValueError):
        pass
    # Cross-check: try bcrypt against argon2 hashes (legacy) and vice-versa
    try:
        import bcrypt

        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def needs_rehash(hashed: str) -> bool:
    settings = get_settings()
    if settings.password_hash == "bcrypt" or not _ARGON2_AVAILABLE:
        return False
    try:
        return _hasher.check_needs_rehash(hashed)
    except Exception:
        return False


# --- Session signing ---------------------------------------------------------

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="sms-session")


def issue_session_token(user_id: int, role: str, extra: Optional[dict[str, Any]] = None) -> str:
    payload = {
        "uid": user_id,
        "role": role,
        "iat": int(datetime.utcnow().timestamp()),
    }
    if extra:
        payload.update(extra)
    return _serializer().dumps(payload)


def read_session_token(token: str) -> Optional[dict[str, Any]]:
    settings = get_settings()
    try:
        return _serializer().loads(token, max_age=settings.session_ttl_minutes * 60)
    except SignatureExpired:
        return None
    except BadSignature:
        return None


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")


# --- CSRF tokens -------------------------------------------------------------

def _csrf_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key + "-csrf", salt="sms-csrf")


def issue_csrf_token(session_id: str) -> str:
    return _csrf_serializer().dumps({"sid": session_id, "n": secrets.token_hex(8)})


def read_csrf_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return _csrf_serializer().loads(token, max_age=24 * 3600)
    except (SignatureExpired, BadSignature):
        return None


def set_csrf_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=24 * 3600,
        httponly=False,  # must be readable by JS
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# --- SHA256 helper -----------------------------------------------------------

def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_file(path: str, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# --- Common errors ------------------------------------------------------------

CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Cookie"},
)