"""Online exam tables (PRD §73–76, §80)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._base import TimestampMixin

# PRD §76 attempt states
ATTEMPT_STATES = ("NOT_STARTED", "IN_PROGRESS", "SUBMITTED", "TIME_EXPIRED", "GRADING", "GRADED")
# Question types that can be auto-scored against answer_key (PRD §73)
OBJECTIVE_QTYPES = {"choice", "multiple_choice", "true_false", "fill_blank"}


class Exam(Base, TimestampMixin):
    """An online exam for one student, backed by a question set (§73)."""

    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_set_id: Mapped[int] = mapped_column(
        ForeignKey("question_sets.id", ondelete="RESTRICT"), nullable=False
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False, index=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    question_set: Mapped["QuestionSet"] = relationship("QuestionSet")
    attempts: Mapped[list["ExamAttempt"]] = relationship(
        "ExamAttempt", back_populates="exam", cascade="all, delete-orphan"
    )


class ExamAttempt(Base):
    """PRD §76 — server-authoritative attempt: timing, autosaved answers, score."""

    __tablename__ = "exam_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    exam_version_id: Mapped[Optional[int]] = mapped_column(Integer)  # reserved (§76)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    last_saved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    status: Mapped[str] = mapped_column(String(16), default="IN_PROGRESS", nullable=False, index=True)
    submit_reason: Mapped[Optional[str]] = mapped_column(String(16))  # manual | time_expired
    score: Mapped[Optional[float]] = mapped_column(Float)
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    # Autosaved answers (§75): {"<question_id>": "answer text"} — the server
    # is the final source of truth.
    answers_json: Mapped[Optional[dict]] = mapped_column(JSON)
    per_question: Mapped[Optional[dict]] = mapped_column(JSON)
    auto_scored: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    llm_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("llm_runs.id", ondelete="SET NULL")
    )
    confirmed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))

    exam: Mapped[Exam] = relationship("Exam", back_populates="attempts")
