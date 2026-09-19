"""Bank update candidates (PRD §68).

Revision ID: 0010_bank_updates
Revises: 0009_question_bank
Create Date: 2026-09-19 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0010_bank_updates"
down_revision: Union[str, None] = "0009_question_bank"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table("bank_update_candidates"):
        return
    op.create_table(
        "bank_update_candidates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("candidate_type", sa.String(16), nullable=False, index=True),
        sa.Column("target_bank_id", sa.Integer, sa.ForeignKey("question_bank.id", ondelete="SET NULL")),
        sa.Column("knowledge_point", sa.String(128), index=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("rationale", sa.Text),
        sa.Column("duplicate_of_id", sa.Integer, sa.ForeignKey("question_bank.id", ondelete="SET NULL")),
        sa.Column("validation_notes", sa.Text),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending", index=True),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("review_note", sa.String(255)),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("bank_update_candidates")
