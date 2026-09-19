"""Learning-loop domain tables.

Implements the PRD core loop:
    Learning Evidence -> Student Knowledge State -> Diagnosis -> Learning Plan

Entities (PRD §17, §24, §26–28, §56–58, §64, §80):
    KnowledgePoint, StudentKnowledgeState, StudentKnowledgeStateHistory,
    LearningObjective, LearningEvidence, ParentFeedback,
    LearningPlan, LearningPlanItem
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
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

# PRD §58 — supported error patterns.
ERROR_PATTERNS = (
    "SIGN_ERROR",
    "CONCEPT_MISUNDERSTANDING",
    "FORMULA_ERROR",
    "CALCULATION_ERROR",
    "READING_ERROR",
    "REASONING_GAP",
    "PROOF_GAP",
    "DIAGRAM_ERROR",
    "KNOWLEDGE_CONFUSION",
    "CARELESS_ERROR",
    "MODELING_ERROR",
)

# PRD §57 — evidence trust ladder; PARENT_CONFIRMED is the official boundary.
TRUST_LEVELS = ("RAW", "AI_EXTRACTED", "VALIDATED", "PARENT_CONFIRMED", "OFFICIAL")

# PRD §62 — intervention types.
INTERVENTION_TYPES = (
    "EXPLANATION",
    "EXAMPLE",
    "PRACTICE",
    "REVIEW",
    "QUIZ",
    "EXAM",
    "REFLECTION",
)


class KnowledgePoint(Base, TimestampMixin):
    """PRD §24 — knowledge point entity (synced from chapter JSON lists)."""

    __tablename__ = "knowledge_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[Optional[str]] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL")
    )
    chapter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), index=True
    )
    grade: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    textbook_version: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    difficulty: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)


class StudentKnowledgeState(Base, TimestampMixin):
    """PRD §26 — the core entity: per-student per-knowledge-point mastery."""

    __tablename__ = "student_knowledge_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True, nullable=False
    )
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_assessed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    last_practiced: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    trend: Mapped[str] = mapped_column(String(16), default="stable", nullable=False)
    decay_risk: Mapped[str] = mapped_column(String(16), default="LOW", nullable=False)
    review_interval_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    next_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    status: Mapped[str] = mapped_column(String(16), default="learning", nullable=False)

    knowledge_point: Mapped[KnowledgePoint] = relationship("KnowledgePoint")


class StudentKnowledgeStateHistory(Base):
    """PRD §28 — every state change must be recorded."""

    __tablename__ = "student_knowledge_state_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True, nullable=False
    )
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("learning_evidence.id", ondelete="SET NULL")
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )


class LearningObjective(Base, TimestampMixin):
    """PRD §17 — parent-set learning objective per knowledge point."""

    __tablename__ = "learning_objectives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL")
    )
    knowledge_point_name: Mapped[Optional[str]] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    current_mastery: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    target_mastery: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=2, nullable=False)  # 1=high 2=mid 3=low
    deadline: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)


class LearningEvidence(Base):
    """PRD §56 — learning evidence; parent-confirmed rows are official."""

    __tablename__ = "learning_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL")
    )
    submission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), index=True
    )
    knowledge_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL")
    )
    knowledge_point_name: Mapped[Optional[str]] = mapped_column(String(128))
    source_type: Mapped[str] = mapped_column(
        String(32), default="ASSIGNMENT", nullable=False, index=True
    )  # ASSIGNMENT | EXAM | PARENT_FEEDBACK | HISTORICAL
    correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float)  # 0..100 for the question
    difficulty: Mapped[Optional[str]] = mapped_column(String(16))
    error_type: Mapped[Optional[str]] = mapped_column(String(48))
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Float)  # AI grading confidence
    trust_level: Mapped[str] = mapped_column(
        String(24), default="RAW", nullable=False, index=True
    )
    observed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )


class ParentFeedback(Base, TimestampMixin):
    """PRD §64 — parent qualitative feedback that becomes evidence."""

    __tablename__ = "parent_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL")
    )
    knowledge_point_name: Mapped[Optional[str]] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    observation: Mapped[str] = mapped_column(
        String(16), default="neutral", nullable=False
    )  # understood | not_understood | careless | out_of_scope | neutral
    author_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    evidence_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("learning_evidence.id", ondelete="SET NULL")
    )


class LearningPlan(Base, TimestampMixin):
    """PRD §30–31 — AI generated learning plan; parent must approve."""

    __tablename__ = "learning_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    diagnosis_json: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(16), default="draft", nullable=False, index=True
    )  # draft | approved | completed | cancelled
    generated_by: Mapped[str] = mapped_column(String(16), default="ai", nullable=False)
    llm_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("llm_runs.id", ondelete="SET NULL")
    )
    approved_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))

    items: Mapped[list["LearningPlanItem"]] = relationship(
        "LearningPlanItem", back_populates="plan",
        cascade="all, delete-orphan", order_by="LearningPlanItem.day",
    )


class LearningPlanItem(Base, TimestampMixin):
    """One day/step of a learning plan; can be turned into an assignment."""

    __tablename__ = "learning_plan_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("learning_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    intervention_type: Mapped[str] = mapped_column(String(16), nullable=False)
    knowledge_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL")
    )
    knowledge_point_name: Mapped[Optional[str]] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    assignment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("assignments.id", ondelete="SET NULL")
    )

    plan: Mapped[LearningPlan] = relationship("LearningPlan", back_populates="items")
