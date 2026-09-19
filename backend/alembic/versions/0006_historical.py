"""Historical assessment import tables (PRD §54-55, §80).

Revision ID: 0006_historical
Revises: 0005_materials
Create Date: 2026-09-19 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0006_historical"
down_revision: Union[str, None] = "0005_materials"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("historical_assessments"):
        op.create_table(
            "historical_assessments",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("material_id", sa.Integer, sa.ForeignKey("materials.id", ondelete="SET NULL"), index=True),
            sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("exam_title", sa.String(128), nullable=False),
            sa.Column("exam_date", sa.Date),
            sa.Column("status", sa.String(16), nullable=False, server_default="analyzed", index=True),
            sa.Column("ocr_text", sa.Text),
            sa.Column("analysis_json", sa.JSON),
            sa.Column("llm_run_id", sa.Integer, sa.ForeignKey("llm_runs.id", ondelete="SET NULL")),
            sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
    if not insp.has_table("historical_assessment_questions"):
        op.create_table(
            "historical_assessment_questions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("assessment_id", sa.Integer, sa.ForeignKey("historical_assessments.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("order", sa.Integer, nullable=False),
            sa.Column("question_text", sa.Text, nullable=False),
            sa.Column("student_answer", sa.Text),
            sa.Column("score", sa.Float),
            sa.Column("max_score", sa.Float),
            sa.Column("annotation", sa.Text),
            sa.Column("knowledge_point_name", sa.String(128)),
            sa.Column("error_type", sa.String(48)),
            sa.Column("confidence", sa.Float),
            sa.Column("status", sa.String(16), nullable=False, server_default="candidate", index=True),
            sa.Column("evidence_id", sa.Integer, sa.ForeignKey("learning_evidence.id", ondelete="SET NULL")),
        )


def downgrade() -> None:
    op.drop_table("historical_assessment_questions")
    op.drop_table("historical_assessments")
