"""Learning-loop tables + grading triage columns.

Idempotent: the app's init_db() (create_all) may already have created some
tables in dev databases; each DDL step is guarded by an inspector check.

Revision ID: 0003_learning_loop
Revises: 0002_student_semester
Create Date: 2026-09-19 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0003_learning_loop"
down_revision: Union[str, None] = "0002_student_semester"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create(table: str, *columns: sa.Column) -> None:
    """create_table guarded by a table-existence check."""
    insp = sa.inspect(op.get_bind())
    if insp.has_table(table):
        return
    op.create_table(table, *columns)


def _add_cols(table: str, **cols: sa.Column) -> None:
    """add_column guarded by column-existence checks (batch mode for SQLite)."""
    insp = sa.inspect(op.get_bind())
    existing = {col["name"] for col in insp.get_columns(table)}
    missing = {name: col for name, col in cols.items() if name not in existing}
    if not missing:
        return
    with op.batch_alter_table(table) as batch_op:
        for col in missing.values():
            batch_op.add_column(col)


def upgrade() -> None:
    _create(
        "knowledge_points",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("subject", sa.String(16)),
        sa.Column("name", sa.String(128), nullable=False, index=True),
        sa.Column("description", sa.Text),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("knowledge_points.id", ondelete="SET NULL")),
        sa.Column("chapter_id", sa.Integer, sa.ForeignKey("chapters.id", ondelete="SET NULL"), index=True),
        sa.Column("grade", sa.String(32), index=True),
        sa.Column("textbook_version", sa.String(64), index=True),
        sa.Column("difficulty", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    _create(
        "learning_evidence",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id", ondelete="SET NULL")),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("submissions.id", ondelete="SET NULL"), index=True),
        sa.Column("knowledge_point_id", sa.Integer, sa.ForeignKey("knowledge_points.id", ondelete="SET NULL")),
        sa.Column("knowledge_point_name", sa.String(128)),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="ASSIGNMENT", index=True),
        sa.Column("correct", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("score", sa.Float),
        sa.Column("difficulty", sa.String(16)),
        sa.Column("error_type", sa.String(48)),
        sa.Column("feedback", sa.Text),
        sa.Column("confidence", sa.Float),
        sa.Column("trust_level", sa.String(24), nullable=False, server_default="RAW", index=True),
        sa.Column("observed_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, index=True),
    )

    _create(
        "student_knowledge_states",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("knowledge_point_id", sa.Integer, sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("mastery_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("evidence_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_assessed", sa.DateTime),
        sa.Column("last_practiced", sa.DateTime),
        sa.Column("trend", sa.String(16), nullable=False, server_default="stable"),
        sa.Column("decay_risk", sa.String(16), nullable=False, server_default="LOW"),
        sa.Column("review_interval_days", sa.Integer, nullable=False, server_default="7"),
        sa.Column("next_review_at", sa.DateTime),
        sa.Column("status", sa.String(16), nullable=False, server_default="learning"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    _create(
        "student_knowledge_state_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("knowledge_point_id", sa.Integer, sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("mastery_score", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("evidence_id", sa.Integer, sa.ForeignKey("learning_evidence.id", ondelete="SET NULL")),
        sa.Column("reason", sa.String(255)),
        sa.Column("changed_at", sa.DateTime, nullable=False, index=True),
    )

    _create(
        "learning_objectives",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("knowledge_point_id", sa.Integer, sa.ForeignKey("knowledge_points.id", ondelete="SET NULL")),
        sa.Column("knowledge_point_name", sa.String(128)),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("current_mastery", sa.Float, nullable=False, server_default="0"),
        sa.Column("target_mastery", sa.Float, nullable=False, server_default="0.8"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="2"),
        sa.Column("deadline", sa.Date),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    _create(
        "parent_feedback",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("knowledge_point_id", sa.Integer, sa.ForeignKey("knowledge_points.id", ondelete="SET NULL")),
        sa.Column("knowledge_point_name", sa.String(128)),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("observation", sa.String(16), nullable=False, server_default="neutral"),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("evidence_id", sa.Integer, sa.ForeignKey("learning_evidence.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    _create(
        "learning_plans",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("diagnosis_json", sa.JSON),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft", index=True),
        sa.Column("generated_by", sa.String(16), nullable=False, server_default="ai"),
        sa.Column("llm_run_id", sa.Integer, sa.ForeignKey("llm_runs.id", ondelete="SET NULL")),
        sa.Column("approved_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    _create(
        "learning_plan_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("plan_id", sa.Integer, sa.ForeignKey("learning_plans.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("day", sa.Integer, nullable=False),
        sa.Column("intervention_type", sa.String(16), nullable=False),
        sa.Column("knowledge_point_id", sa.Integer, sa.ForeignKey("knowledge_points.id", ondelete="SET NULL")),
        sa.Column("knowledge_point_name", sa.String(128)),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("question_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("estimated_minutes", sa.Integer),
        sa.Column("rationale", sa.Text),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("assignment_id", sa.Integer, sa.ForeignKey("assignments.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Grading triage columns (PRD §47–48).
    _add_cols(
        "gradings",
        llm_confidence=sa.Column("llm_confidence", sa.Float, nullable=True),
        needs_review=sa.Column("needs_review", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("gradings") as batch_op:
        batch_op.drop_column("needs_review")
        batch_op.drop_column("llm_confidence")

    op.drop_table("learning_plan_items")
    op.drop_table("learning_plans")
    op.drop_table("parent_feedback")
    op.drop_table("learning_objectives")
    op.drop_table("student_knowledge_state_history")
    op.drop_table("learning_evidence")
    op.drop_table("student_knowledge_states")
    op.drop_table("knowledge_points")
