"""Assignment-domain tables."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._base import TimestampMixin


class Assignment(Base, TimestampMixin):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_set_id: Mapped[int] = mapped_column(
        ForeignKey("question_sets.id", ondelete="RESTRICT"), nullable=False
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    estimated_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    calculator_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="assigned", nullable=False, index=True)

    student: Mapped["Student"] = relationship("Student")
    question_set: Mapped["QuestionSet"] = relationship("QuestionSet", back_populates="assignments")
    submissions: Mapped[list["Submission"]] = relationship(
        "Submission", back_populates="assignment", cascade="all, delete-orphan"
    )


class QuestionSet(Base, TimestampMixin):
    __tablename__ = "question_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(8), nullable=False)  # "A" / "B"
    generation_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("llm_runs.id", ondelete="SET NULL"), index=True
    )
    difficulty: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    estimated_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    knowledge_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    validator_notes: Mapped[Optional[str]] = mapped_column(Text)

    questions: Mapped[list["Question"]] = relationship(
        "Question", back_populates="question_set", cascade="all, delete-orphan", order_by="Question.order"
    )
    assignments: Mapped[list[Assignment]] = relationship(
        "Assignment", back_populates="question_set"
    )


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_set_id: Mapped[int] = mapped_column(
        ForeignKey("question_sets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    qtype: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # language|math
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    rubric: Mapped[Optional[str]] = mapped_column(Text)
    answer_key: Mapped[Optional[str]] = mapped_column(Text)
    knowledge_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    difficulty: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    estimated_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    diagram_svg: Mapped[Optional[str]] = mapped_column(Text)  # SVG markup or Mermaid source
    diagram_format: Mapped[Optional[str]] = mapped_column(String(16))  # svg | mermaid

    question_set: Mapped[QuestionSet] = relationship("QuestionSet", back_populates="questions")


class Submission(Base, TimestampMixin):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="submitted", nullable=False, index=True)
    archive_path: Mapped[str] = mapped_column(String(512), nullable=False)
    text_answer: Mapped[Optional[str]] = mapped_column(Text)
    ocr_text: Mapped[Optional[str]] = mapped_column(Text)

    assignment: Mapped[Assignment] = relationship("Assignment", back_populates="submissions")
    student: Mapped["Student"] = relationship("Student")
    images: Mapped[list["SubmissionImage"]] = relationship(
        "SubmissionImage", back_populates="submission", cascade="all, delete-orphan"
    )
    gradings: Mapped[list["Grading"]] = relationship(
        "Grading", back_populates="submission", cascade="all, delete-orphan"
    )


class SubmissionImage(Base, TimestampMixin):
    __tablename__ = "submission_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_number: Mapped[Optional[int]] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    rel_path: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ocr_text: Mapped[Optional[str]] = mapped_column(Text)

    submission: Mapped[Submission] = relationship("Submission", back_populates="images")


class Grading(Base, TimestampMixin):
    __tablename__ = "gradings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    grader_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    llm_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("llm_runs.id", ondelete="SET NULL")
    )
    llm_suggested_score: Mapped[Optional[float]] = mapped_column(Float)
    llm_suggested_feedback: Mapped[Optional[str]] = mapped_column(Text)
    llm_knowledge_mastery: Mapped[Optional[dict]] = mapped_column(JSON)
    llm_confidence: Mapped[Optional[float]] = mapped_column(Float)  # overall AI grading confidence 0..1
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    final_score: Mapped[Optional[float]] = mapped_column(Float)
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    per_question_scores: Mapped[Optional[dict]] = mapped_column(JSON)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))

    submission: Mapped[Submission] = relationship("Submission", back_populates="gradings")
    grader: Mapped[Optional["User"]] = relationship("User")


class GradeVersion(Base):
    """PRD §50 — score-change history: AI suggestion -> parent review -> official."""

    __tablename__ = "grade_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grading_id: Mapped[int] = mapped_column(
        ForeignKey("gradings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    submission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), index=True
    )
    previous_score: Mapped[Optional[float]] = mapped_column(Float)
    new_score: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    changed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )