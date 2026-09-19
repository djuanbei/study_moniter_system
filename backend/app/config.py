"""Configuration loader.

Reads from environment variables (loaded from .env) and the JSON business
configuration file (`configure.json`). Missing config files fall back to
`*example` templates in the project root.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AppSettings(BaseSettings):
    """Environment-loaded settings (secrets + low-level toggles)."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str = "dev-secret-please-change"
    session_cookie_name: str = "sms_session"
    session_cookie_secure: bool = False
    session_ttl_minutes: int = 720

    csrf_cookie_name: str = "sms_csrf"
    csrf_header_name: str = "X-CSRF-Token"

    password_hash: str = "argon2"  # argon2 | bcrypt

    pass_word: str = ""  # initial password for the default teacher (set via .env PASS_WORD)

    llm_provider: str = "minimax"
    llm_model: str = "MiniMax-Text-01"
    llm_temperature: float = 0.4
    llm_max_tokens: int = 4096
    openai_api_key: str = ""
    openai_base_url: str = ""
    anthropic_api_key: str = ""
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.chat/v1"

    ocr_use_vision: bool = False
    vision_model: str = "gpt-4o-mini"

    upload_dir: str = "uploads"
    data_dir: str = "data"
    log_dir: str = "logs"
    max_upload_mb: int = 20

    host: str = "0.0.0.0"
    port: int = 8000

    log_level: str = "INFO"
    log_file: str = "logs/app.log"
    log_format: str = "text"  # text | json


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    return AppSettings()


def _load_business_config() -> dict[str, Any]:
    """Load `configure.json` (or fall back to the example template)."""
    candidates = [
        PROJECT_ROOT / "configure.json",
        PROJECT_ROOT / "configure.json.example",
    ]
    for path in candidates:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc
    return {}


@lru_cache(maxsize=1)
def get_business_config() -> dict[str, Any]:
    return _load_business_config()


def resolve_path(*parts: str) -> Path:
    """Resolve a path under the project root unless it is already absolute."""
    p = Path(*parts)
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()


def ensure_runtime_dirs() -> dict[str, Path]:
    """Create runtime data / upload / log directories under the project root."""
    s = get_settings()
    dirs = {
        "data": resolve_path(s.data_dir),
        "uploads": resolve_path(s.upload_dir),
        "logs": resolve_path(s.log_dir),
        "sqlite": resolve_path(s.data_dir, "app.sqlite"),
    }
    for k, p in dirs.items():
        if k == "sqlite":
            p.parent.mkdir(parents=True, exist_ok=True)
        else:
            p.mkdir(parents=True, exist_ok=True)
    return dirs