"""Settings routes (academic calendar, generation defaults, etc.)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT, get_business_config
from app.database import get_db
from app.deps import get_current_user
from app.middleware.audit import record_audit
from app.models.auth import User
from app.schemas import SettingsOut, SettingsUpdateIn


router = APIRouter(prefix="/api/settings", tags=["settings"])


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


@router.get("", response_model=SettingsOut)
def read_settings(_: User = Depends(get_current_user)) -> SettingsOut:
    return SettingsOut(config=get_business_config())


@router.put("", response_model=SettingsOut)
def update_settings(
    payload: SettingsUpdateIn,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SettingsOut:
    _teacher_only(current)
    path = PROJECT_ROOT / "configure.json"
    path.write_text(json.dumps(payload.config, ensure_ascii=False, indent=2), encoding="utf-8")
    record_audit(db, action="update_settings", user=current, request=request)
    db.commit()
    # invalidate cached config
    from app.config import get_business_config
    get_business_config.cache_clear()
    return SettingsOut(config=get_business_config())


@router.get("/config-file-path")
def config_file_path(_: User = Depends(get_current_user)) -> dict:
    return {"path": str((PROJECT_ROOT / "configure.json").resolve())}