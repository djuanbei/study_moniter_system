"""Online exam tables (PRD §73-76, §80).

Revision ID: 0008_exams
Revises: 0007_jobs
Create Date: 2026-09-19 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0008_exams"
down_revision: Union[str, None] = "0007_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("exams"):
        op.create_table(
            "exams",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("title", sa.String(128), nullable=False),
            sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("question_set_id", sa.Integer, sa.ForeignKey("question_sets.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("duration_minutes", sa.Integer, nullable=False, server_default="30"),
            sa.Column("total_score", sa.Float, nullable=False, server_default="100"),
            sa.Column("status", sa.String(16), nullable=False, server_default="active", index=True),
            sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
    if not insp.has_table("exam_attempts"):
        op.create_table(
            "exam_attempts",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("exam_id", sa.Integer, sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("exam_version_id", sa.Integer),
            sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("started_at", sa.DateTime, nullable=False),
            sa.Column("last_saved_at", sa.DateTime),
            sa.Column("deadline", sa.DateTime, nullable=False),
            sa.Column("submitted_at", sa.DateTime),
            sa.Column("status", sa.String(16), nullable=False, server_default="IN_PROGRESS", index=True),
            sa.Column("submit_reason", sa.String(16)),
            sa.Column("score", sa.Float),
            sa.Column("feedback", sa.Text),
            sa.Column("answers_json", sa.JSON),
            sa.Column("per_question", sa.JSON),
            sa.Column("auto_scored", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("llm_run_id", sa.Integer, sa.ForeignKey("llm_runs.id", ondelete="SET NULL")),
            sa.Column("confirmed_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("confirmed_at", sa.DateTime),
        )


def downgrade() -> None:
    op.drop_table("exam_attempts")
    op.drop_table("exams")
