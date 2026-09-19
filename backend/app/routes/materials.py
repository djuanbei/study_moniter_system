"""Material import routes (PRD §19–21).

Upload textbook/exercise files, run OCR + chapter extraction, review the
candidates and publish them into chapters + knowledge points.
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT, get_settings, resolve_path
from app.database import get_db
from app.deps import get_current_user
from app.middleware.audit import record_audit
from app.models.auth import User
from app.models.materials import MATERIAL_TYPES, Material
from app.schemas import MaterialOut
from app.services.material_import import analyze_material, publish_material, save_upload

router = APIRouter(prefix="/api/materials", tags=["materials"])

ALLOWED_MATERIAL_MIMES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
# PRD §19 also lists DOCX; accepted as-is (no OCR, extraction runs on empty text).
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _teacher_only(user: User) -> None:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")


def _get_material(db: Session, material_id: int) -> Material:
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@router.get("", response_model=list[MaterialOut])
def list_materials(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Material]:
    _teacher_only(current)
    return db.query(Material).order_by(Material.id.desc()).limit(100).all()


@router.post("", response_model=MaterialOut)
async def upload_material(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    material_type: str = Form(default="TEXTBOOK"),
    textbook_version: str = Form(default=""),
    grade: str = Form(default=""),
    semester: int | None = Form(default=None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Material:
    _teacher_only(current)
    if material_type not in MATERIAL_TYPES:
        raise HTTPException(status_code=400, detail=f"未知资料类型: {material_type}")
    settings = get_settings()
    mime = (file.content_type or "").lower()
    if mime != DOCX_MIME and mime not in ALLOWED_MATERIAL_MIMES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {mime}")

    raw = await file.read()
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件过大")

    rel_path, sha = save_upload(raw=raw, filename=file.filename or "upload", mime_type=mime)
    material = Material(
        material_type=material_type,
        title=title.strip()[:128] or (file.filename or "未命名"),
        textbook_version=textbook_version.strip() or None,
        grade=grade.strip() or None,
        semester=semester if semester in (1, 2) else None,
        filename=file.filename or "upload",
        rel_path=rel_path,
        sha256=sha,
        mime_type=mime,
        size_bytes=len(raw),
        created_by=current.id,
    )
    db.add(material)
    record_audit(
        db, action="upload_material", user=current, request=request,
        target_type="material", detail={"sha256": sha, "size": len(raw)},
    )
    db.commit()
    db.refresh(material)
    return material


class MaterialAnalyzeOut(BaseModel):
    id: int
    status: str
    ocr_chars: int
    chapters: list[dict]
    extracted_by: str


@router.post("/{material_id}/analyze", response_model=MaterialAnalyzeOut)
def analyze(
    material_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MaterialAnalyzeOut:
    _teacher_only(current)
    material = _get_material(db, material_id)
    try:
        analyze_material(db, material, current)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=502, detail=f"识别失败: {exc}") from exc
    record_audit(
        db, action="analyze_material", user=current, request=request,
        target_type="material", target_id=material.id,
    )
    db.commit()
    analysis = material.analysis_json or {}
    return MaterialAnalyzeOut(
        id=material.id,
        status=material.status,
        ocr_chars=len(material.ocr_text or ""),
        chapters=analysis.get("chapters", []),
        extracted_by=analysis.get("extracted_by", "fallback"),
    )


@router.post("/{material_id}/publish")
def publish(
    material_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Parent confirms the extracted chapters -> creates chapters + KPs (PRD §20)."""
    _teacher_only(current)
    material = _get_material(db, material_id)
    if not material.analysis_json:
        raise HTTPException(status_code=400, detail="请先运行识别")
    result = publish_material(db, material)
    record_audit(
        db, action="publish_material", user=current, request=request,
        target_type="material", target_id=material.id, detail=result,
    )
    db.commit()
    return {"status": "published", **result}


@router.get("/{material_id}/file")
def get_file(
    material_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    _teacher_only(current)
    material = _get_material(db, material_id)
    full = resolve_path(material.rel_path)
    if not full.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(full, filename=material.filename)


@router.delete("/{material_id}")
def delete_material(
    material_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _teacher_only(current)
    material = _get_material(db, material_id)
    # Original file stays on disk (immutable storage); only the DB row goes.
    db.delete(material)
    record_audit(
        db, action="delete_material", user=current, request=request,
        target_type="material", target_id=material_id,
    )
    db.commit()
    return {"ok": True}
