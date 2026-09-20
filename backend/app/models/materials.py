"""Material-domain tables (PRD §21): uploaded textbooks / exercises / papers."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models._base import TimestampMixin

MATERIAL_TYPES = (
    "TEXTBOOK", "TEXTBOOK_SECTION", "EXERCISE_BOOK", "WORKSHEET",
    "EXAM", "ANSWER_KEY", "SOLUTION", "PARENT_NOTE", "OTHER",
)
MATERIAL_STATUSES = ("uploaded", "analyzed", "published")
MATERIAL_SOURCES = ("UPLOADED", "IMPORTED", "AGENT_DISCOVERED", "MANUAL")  # PRD §21


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

    # PRD §21 provenance
    source: Mapped[str] = mapped_column(String(16), default="UPLOADED", nullable=False, index=True)
    license: Mapped[Optional[str]] = mapped_column(String(64))  # §23: unknown until verified
    source_metadata: Mapped[Optional[dict]] = mapped_column(JSON)  # §23: url/domain/retrieved_at

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


class MaterialCandidate(Base, TimestampMixin):
    """PRD §22 — agent-discovered public material awaiting parent review.

    §23 fields: url, domain, retrieved_at, content_hash, license,
    source_metadata. Third-party materials are never auto-published
    (auto_import=false, §87).
    """

    __tablename__ = "material_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(768), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(128), nullable=False)
    snippet: Mapped[Optional[str]] = mapped_column(Text)
    query: Mapped[Optional[str]] = mapped_column(String(255))
    knowledge_point: Mapped[Optional[str]] = mapped_column(String(128))
    grade: Mapped[Optional[str]] = mapped_column(String(32))
    license: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(16), default="discovered", nullable=False, index=True
    )  # discovered | approved | rejected
    material_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("materials.id", ondelete="SET NULL")
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
