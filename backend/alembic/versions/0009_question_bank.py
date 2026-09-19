"""Question bank tables (PRD §39-41, §80).

Revision ID: 0009_question_bank
Revises: 0008_exams
Create Date: 2026-09-19 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0009_question_bank"
down_revision: Union[str, None] = "0008_exams"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("question_bank"):
        op.create_table(
            "question_bank",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("subject", sa.String(16), nullable=False, index=True),
            sa.Column("grade", sa.String(32), index=True),
            sa.Column("chapter_id", sa.Integer, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
            sa.Column("knowledge_points", sa.JSON),
            sa.Column("difficulty", sa.String(16), nullable=False, server_default="medium"),
            sa.Column("question_type", sa.String(32), nullable=False, index=True),
            sa.Column("prompt", sa.Text, nullable=False),
            sa.Column("answer", sa.Text),
            sa.Column("rubric", sa.Text),
            sa.Column("estimated_time", sa.Integer),
            sa.Column("source", sa.String(16), nullable=False, server_default="AI"),
            sa.Column("status", sa.String(16), nullable=False, server_default="active", index=True),
            sa.Column("duplicate_hash", sa.String(64), nullable=False, index=True),
            sa.Column("version", sa.Integer, nullable=False, server_default="1"),
            sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
    if not insp.has_table("question_versions"):
        op.create_table(
            "question_versions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("question_id", sa.Integer, sa.ForeignKey("question_bank.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("version", sa.Integer, nullable=False),
            sa.Column("snapshot", sa.JSON, nullable=False),
            sa.Column("change_note", sa.String(255)),
            sa.Column("published_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("published_at", sa.DateTime, nullable=False, index=True),
        )


def downgrade() -> None:
    op.drop_table("question_versions")
    op.drop_table("question_bank")
