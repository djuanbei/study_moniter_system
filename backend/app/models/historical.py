"""Historical assessment import (PRD §54–55, §80).

Parents upload scans of past exams/homework; the system recovers
Question / StudentAnswer / Score / Annotation candidates for parent review,
then converts confirmed items into LearningEvidence.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._base import TimestampMixin


class HistoricalAssessment(Base, TimestampMixin):
    """One imported historical paper, awaiting parent review."""

    __tablename__ = "historical_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("materials.id", ondelete="SET NULL"), index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    exam_title: Mapped[str] = mapped_column(String(128), nullable=False)
    exam_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(16), default="analyzed", nullable=False, index=True
    )  # analyzed | confirmed
    ocr_text: Mapped[Optional[str]] = mapped_column(Text)
    analysis_json: Mapped[Optional[dict]] = mapped_column(JSON)
    llm_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("llm_runs.id", ondelete="SET NULL")
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    questions: Mapped[list["HistoricalQuestion"]] = relationship(
        "HistoricalQuestion", back_populates="assessment",
        cascade="all, delete-orphan", order_by="HistoricalQuestion.order",
    )


class HistoricalQuestion(Base):
    """One recovered question candidate (PRD §55)."""

    __tablename__ = "historical_assessment_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("historical_assessments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    student_answer: Mapped[Optional[str]] = mapped_column(Text)
    score: Mapped[Optional[float]] = mapped_column(Float)
    max_score: Mapped[Optional[float]] = mapped_column(Float)
    annotation: Mapped[Optional[str]] = mapped_column(Text)
    knowledge_point_name: Mapped[Optional[str]] = mapped_column(String(128))
    error_type: Mapped[Optional[str]] = mapped_column(String(48))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="candidate", nullable=False, index=True)
    evidence_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("learning_evidence.id", ondelete="SET NULL")
    )

    assessment: Mapped[HistoricalAssessment] = relationship("HistoricalAssessment", back_populates="questions")
