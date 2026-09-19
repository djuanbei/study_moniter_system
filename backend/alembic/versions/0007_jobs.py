"""Async jobs table (PRD §82–83).

Revision ID: 0007_jobs
Revises: 0006_historical
Create Date: 2026-09-19 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0007_jobs"
down_revision: Union[str, None] = "0006_historical"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table("jobs"):
        return
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("job_type", sa.String(32), nullable=False, index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="QUEUED", index=True),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("result", sa.JSON),
        sa.Column("error", sa.Text),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("worker_id", sa.String(64)),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now(), index=True),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
    )


def downgrade() -> None:
    op.drop_table("jobs")
