"""Knowledge-base update candidates (PRD §69).

Revision ID: 0011_knowledge_updates
Revises: 0010_bank_updates
Create Date: 2026-09-19 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0011_knowledge_updates"
down_revision: Union[str, None] = "0010_bank_updates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table("knowledge_update_candidates"):
        return
    op.create_table(
        "knowledge_update_candidates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("candidate_type", sa.String(16), nullable=False, index=True),
        sa.Column("target_kp_id", sa.Integer, sa.ForeignKey("knowledge_points.id", ondelete="SET NULL")),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("rationale", sa.Text),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending", index=True),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("review_note", sa.String(255)),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("knowledge_update_candidates")
