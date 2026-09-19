"""Question bank tables (PRD §39–41, §80).

QuestionBankItem is the persistent bank entry; QuestionVersion rows are
immutable snapshots created on publish/edit (§40). Duplicate detection uses
a normalized-prompt hash (§36).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._base import TimestampMixin


class QuestionBankItem(Base, TimestampMixin):
    """PRD §39 — persistent question bank entry."""

    __tablename__ = "question_bank"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # PRD §39 field names
    subject: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    grade: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    chapter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL")
    )
    knowledge_points: Mapped[list] = mapped_column(JSON, default=list)
    difficulty: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    question_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text)
    rubric: Mapped[Optional[str]] = mapped_column(Text)
    estimated_time: Mapped[Optional[int]] = mapped_column(Integer)  # minutes
    source: Mapped[str] = mapped_column(String(16), default="AI", nullable=False)  # AI|MANUAL|EXAM|IMPORT
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False, index=True)

    # Duplicate detection (§36): sha256 of the normalized prompt
    duplicate_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    versions: Mapped[list["QuestionVersion"]] = relationship(
        "QuestionVersion", back_populates="question",
        cascade="all, delete-orphan", order_by="QuestionVersion.version",
    )


class QuestionVersion(Base):
    """PRD §40 — immutable snapshot; publishing/editing appends a new row."""

    __tablename__ = "question_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("question_bank.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_note: Mapped[Optional[str]] = mapped_column(String(255))
    published_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )

    question: Mapped[QuestionBankItem] = relationship("QuestionBankItem", back_populates="versions")
