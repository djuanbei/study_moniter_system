"""Materials table (PRD §21): uploaded textbook/resource import pipeline.

Revision ID: 0005_materials
Revises: 0004_grade_versions
Create Date: 2026-09-19 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0005_materials"
down_revision: Union[str, None] = "0004_grade_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table("materials"):
        return
    op.create_table(
        "materials",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("material_type", sa.String(24), nullable=False, server_default="TEXTBOOK", index=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("textbook_version", sa.String(64), index=True),
        sa.Column("grade", sa.String(32), index=True),
        sa.Column("semester", sa.Integer),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("rel_path", sa.String(512), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False, index=True),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("ocr_text", sa.Text),
        sa.Column("analysis_json", sa.JSON),
        sa.Column("status", sa.String(16), nullable=False, server_default="uploaded", index=True),
        sa.Column("llm_run_id", sa.Integer, sa.ForeignKey("llm_runs.id", ondelete="SET NULL")),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("materials")
