"""Material-domain tables (PRD §21): uploaded textbooks / exercises / papers."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models._base import TimestampMixin

MATERIAL_TYPES = (
    "TEXTBOOK", "TEXTBOOK_SECTION", "EXERCISE_BOOK", "WORKSHEET",
    "EXAM", "ANSWER_KEY", "SOLUTION", "PARENT_NOTE", "OTHER",
)
MATERIAL_STATUSES = ("uploaded", "analyzed", "published")


class Material(Base, TimestampMixin):
    """An uploaded learning resource awaiting OCR / chapter extraction / publish."""

    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_type: Mapped[str] = mapped_column(String(24), default="TEXTBOOK", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    textbook_version: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    grade: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    semester: Mapped[Optional[int]] = mapped_column(Integer)  # 1 / 2

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    rel_path: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    ocr_text: Mapped[Optional[str]] = mapped_column(Text)
    # Extracted chapter candidates awaiting parent review (PRD §20, §22):
    # {"chapters": [{"title": ..., "knowledge_points": [...]}], "extracted_by": "llm"|"fallback"}
    analysis_json: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="uploaded", nullable=False, index=True)
    llm_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("llm_runs.id", ondelete="SET NULL")
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
