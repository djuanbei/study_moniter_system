"""Extended PRD entities (PRD §80).

Tables added to complete the canonical schema list:

  Textbook, TextbookVersion, Section, KnowledgePointVersion,
  MaterialVersion, MaterialPage, MaterialChunk,
  LearningSession, LearningIntervention,
  StudentAnswer, AnswerVersion,
  ExamVersion, ExamQuestion, AssignmentVersion,
  ParentAnnotation, ParentScore,
  StudentProgressHistory,
  QuestionEmbedding, QuestionSignature,
  ErrorPattern, StudentErrorEvidence,
  MaterialAgentRun, KnowledgeUpdateRun, QuestionBankUpdateRun,
  ImportReview, ImportReviewItem, Export.

These are mostly additive — they don't replace existing models. The few that
overlap (e.g. `ExamQuestion` alongside the existing `question_sets` join)
add the explicit link tables the PRD calls for so reporting and audit
pipelines can query per-question-per-exam intent directly.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._base import TimestampMixin


# ---------------------------------------------------------------------------
# Textbook hierarchy (PRD §18)
# ---------------------------------------------------------------------------

class Textbook(Base, TimestampMixin):
    __tablename__ = "textbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    publisher: Mapped[Optional[str]] = mapped_column(String(64))
    description: Mapped[Optional[str]] = mapped_column(Text)
    versions: Mapped[list["TextbookVersion"]] = relationship(
        "TextbookVersion", back_populates="textbook",
        cascade="all, delete-orphan", order_by="TextbookVersion.year.desc()",
    )


class TextbookVersion(Base, TimestampMixin):
    __tablename__ = "textbook_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    textbook_id: Mapped[int] = mapped_column(
        ForeignKey("textbooks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "人教版 2024"
    year: Mapped[Optional[int]] = mapped_column(Integer)
    grade_band: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    isbn: Mapped[Optional[str]] = mapped_column(String(32))

    textbook: Mapped[Textbook] = relationship("Textbook", back_populates="versions")
    sections: Mapped[list["Section"]] = relationship(
        "Section", back_populates="version",
        cascade="all, delete-orphan", order_by="Section.order",
    )


class Section(Base, TimestampMixin):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    textbook_version_id: Mapped[int] = mapped_column(
        ForeignKey("textbook_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chapter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), index=True
    )
    parent_section_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sections.id", ondelete="SET NULL")
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)

    version: Mapped[TextbookVersion] = relationship("TextbookVersion", back_populates="sections")


class KnowledgePointVersion(Base):
    """PRD §24 — immutable snapshot when a KP is published."""

    __tablename__ = "knowledge_point_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True, nullable=False
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


# ---------------------------------------------------------------------------
# Material versions + pages + chunks (PRD §20, §80)
# ---------------------------------------------------------------------------

class MaterialVersion(Base):
    """PRD §20 — every Material has versioned snapshots of its analysis."""

    __tablename__ = "material_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_note: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )


class MaterialPage(Base, TimestampMixin):
    """PRD §20 — one row per scanned page."""

    __tablename__ = "material_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True, nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    image_rel_path: Mapped[Optional[str]] = mapped_column(String(512))
    ocr_text: Mapped[Optional[str]] = mapped_column(Text)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), index=True)


class MaterialChunk(Base, TimestampMixin):
    """PRD §20 — chunked structured content for retrieval and KP extraction."""

    __tablename__ = "material_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True, nullable=False
    )
    page_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("material_pages.id", ondelete="SET NULL"), index=True
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(32), index=True)  # text | formula | image | table
    text: Mapped[Optional[str]] = mapped_column(Text)
    payload: Mapped[Optional[dict]] = mapped_column(JSON)


# ---------------------------------------------------------------------------
# Learning session + intervention (PRD §62, §80)
# ---------------------------------------------------------------------------

class LearningSession(Base, TimestampMixin):
    """PRD §80 — a single study/work session."""

    __tablename__ = "learning_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    plan_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("learning_plan_items.id", ondelete="SET NULL"), index=True
    )
    assignment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("assignments.id", ondelete="SET NULL"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    focus: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)


class LearningIntervention(Base, TimestampMixin):
    """PRD §62 — an intervention definition; outcome is tracked separately."""

    __tablename__ = "learning_interventions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    plan_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("learning_plan_items.id", ondelete="SET NULL"), index=True
    )
    knowledge_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), index=True
    )
    intervention_type: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    planned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    status: Mapped[str] = mapped_column(String(16), default="planned", nullable=False)


# ---------------------------------------------------------------------------
# Assignment / Exam versioning + per-question join (PRD §73, §76, §80)
# ---------------------------------------------------------------------------

class AssignmentVersion(Base):
    __tablename__ = "assignment_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_note: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )


class ExamVersion(Base):
    __tablename__ = "exam_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_note: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )


class ExamQuestion(Base, TimestampMixin):
    """PRD §80 — explicit exam -> question join with ordering + max score."""

    __tablename__ = "exam_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)


# ---------------------------------------------------------------------------
# Student answers + answer versioning (PRD §77, §80)
# ---------------------------------------------------------------------------

class StudentAnswer(Base, TimestampMixin):
    """One canonical answer per (attempt, question). Supersedes the
    `ExamAttempt.answers_json` blob and the inline `Submission.text_answer`
    storage so reporting can join directly."""

    __tablename__ = "student_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL"), index=True
    )
    submission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), index=True
    )
    exam_attempt_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="SET NULL"), index=True
    )
    answer_text: Mapped[Optional[str]] = mapped_column(Text)
    answer_payload: Mapped[Optional[dict]] = mapped_column(JSON)  # structured choices, etc.
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    source_type: Mapped[str] = mapped_column(
        String(16), default="ONLINE", nullable=False
    )  # ONLINE | PAPER_OCR | MANUAL
    image_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("submission_images.id", ondelete="SET NULL")
    )


class AnswerVersion(Base):
    """PRD §80 — every answer edit is versioned so we can audit re-grades."""

    __tablename__ = "answer_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_answer_id: Mapped[int] = mapped_column(
        ForeignKey("student_answers.id", ondelete="CASCADE"), index=True, nullable=False
    )
    previous_text: Mapped[Optional[str]] = mapped_column(Text)
    new_text: Mapped[Optional[str]] = mapped_column(Text)
    changed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )


# ---------------------------------------------------------------------------
# Parent annotation / parent score (PRD §46, §80)
# ---------------------------------------------------------------------------

class ParentAnnotation(Base, TimestampMixin):
    """PRD §46 — explicit per-question parent annotation row."""

    __tablename__ = "parent_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL"), index=True
    )
    submission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), index=True
    )
    exam_attempt_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="SET NULL"), index=True
    )
    annotation: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class ParentScore(Base, TimestampMixin):
    """PRD §49 — explicit parent-authored score (separate from the LLM suggestion)."""

    __tablename__ = "parent_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    submission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), index=True
    )
    exam_attempt_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="SET NULL"), index=True
    )
    question_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL"), index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[Optional[float]] = mapped_column(Float)
    author_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


# ---------------------------------------------------------------------------
# Progress / error pattern tables (PRD §58, §80)
# ---------------------------------------------------------------------------

class StudentProgressHistory(Base):
    __tablename__ = "student_progress_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    progress_id: Mapped[int] = mapped_column(
        ForeignKey("student_progress.id", ondelete="CASCADE"), index=True, nullable=False
    )
    mastery: Mapped[float] = mapped_column(Float, nullable=False)
    last_score: Mapped[Optional[float]] = mapped_column(Float)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255))


class ErrorPattern(Base, TimestampMixin):
    """PRD §58 — catalogue of known error patterns with remediation hints."""

    __tablename__ = "error_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    remediation: Mapped[Optional[str]] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)


class StudentErrorEvidence(Base, TimestampMixin):
    """PRD §58 — per-student-per-pattern error occurrence log."""

    __tablename__ = "student_error_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    error_pattern_id: Mapped[int] = mapped_column(
        ForeignKey("error_patterns.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), index=True
    )
    submission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), index=True
    )
    question_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL"), index=True
    )
    evidence_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("learning_evidence.id", ondelete="SET NULL"), index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )


# ---------------------------------------------------------------------------
# Question similarity (PRD §41)
# ---------------------------------------------------------------------------

class QuestionEmbedding(Base, TimestampMixin):
    """PRD §41 — vector representation of question prompts for similarity.

    Stored as packed float32 bytes (engine.sqlite has no native vector type).
    Dimension is recorded so callers can rebuild the array.
    """

    __tablename__ = "question_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class QuestionSignature(Base, TimestampMixin):
    """PRD §36 — normalized prompt signature for duplicate detection."""

    __tablename__ = "question_signatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    signature: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    algorithm: Mapped[str] = mapped_column(String(32), default="sha256-norm", nullable=False)


# ---------------------------------------------------------------------------
# Agent runs + import reviews + exports (PRD §22, §68, §69, §78–80)
# ---------------------------------------------------------------------------

class MaterialAgentRun(Base, TimestampMixin):
    """PRD §22 — one Material Agent discovery pass."""

    __tablename__ = "material_agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    triggered_by: Mapped[str] = mapped_column(String(32), default="schedule", nullable=False)
    candidates_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    llm_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("llm_runs.id", ondelete="SET NULL")
    )
    payload: Mapped[Optional[dict]] = mapped_column(JSON)
    error: Mapped[Optional[str]] = mapped_column(Text)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))


class KnowledgeUpdateRun(Base, TimestampMixin):
    """PRD §69 — one knowledge-base update pass."""

    __tablename__ = "knowledge_update_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    triggered_by: Mapped[str] = mapped_column(String(32), default="schedule", nullable=False)
    candidates_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    llm_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("llm_runs.id", ondelete="SET NULL")
    )
    payload: Mapped[Optional[dict]] = mapped_column(JSON)
    error: Mapped[Optional[str]] = mapped_column(Text)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))


class QuestionBankUpdateRun(Base, TimestampMixin):
    """PRD §68 — one question-bank incremental update pass."""

    __tablename__ = "question_bank_update_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    triggered_by: Mapped[str] = mapped_column(String(32), default="schedule", nullable=False)
    candidates_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    llm_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("llm_runs.id", ondelete="SET NULL")
    )
    payload: Mapped[Optional[dict]] = mapped_column(JSON)
    error: Mapped[Optional[str]] = mapped_column(Text)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))


class ImportReview(Base, TimestampMixin):
    """PRD §55 — batch container for candidate review (historical / material)."""

    __tablename__ = "import_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # HISTORICAL | MATERIAL_AGENT | KNOWLEDGE_UPDATE | QUESTION_BANK_UPDATE
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)
    llm_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("llm_runs.id", ondelete="SET NULL")
    )


class ImportReviewItem(Base, TimestampMixin):
    __tablename__ = "import_review_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("import_reviews.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)
    decision_note: Mapped[Optional[str]] = mapped_column(Text)
    decided_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))


class Export(Base, TimestampMixin):
    """PRD §78–79 — record of a PDF / DOCX / archive export."""

    __tablename__ = "exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), index=True
    )
    export_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # PDF_QUESTION_SET | DOCX_QUESTION_SET | REPORT_PDF | ARCHIVE_ZIP | REPORT_CSV
    target_type: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    rel_path: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    requester_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )