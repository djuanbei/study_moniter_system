"""Material Agent candidates (PRD §22-23) + Material source fields (§21).

Revision ID: 0012_material_agent
Revises: 0011_knowledge_updates
Create Date: 2026-09-19 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0012_material_agent"
down_revision: Union[str, None] = "0011_knowledge_updates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    if not insp.has_table("material_candidates"):
        op.create_table(
            "material_candidates",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("url", sa.String(768), nullable=False),
            sa.Column("domain", sa.String(128), nullable=False),
            sa.Column("snippet", sa.Text),
            sa.Column("query", sa.String(255)),
            sa.Column("knowledge_point", sa.String(128)),
            sa.Column("grade", sa.String(32)),
            sa.Column("license", sa.String(64), server_default="unknown"),
            sa.Column("content_hash", sa.String(64), nullable=False, index=True),
            sa.Column("source_metadata", sa.JSON),
            sa.Column("status", sa.String(16), nullable=False, server_default="discovered", index=True),
            sa.Column("material_id", sa.Integer, sa.ForeignKey("materials.id", ondelete="SET NULL")),
            sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("retrieved_at", sa.DateTime, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        )

    existing = {col["name"] for col in insp.get_columns("materials")}
    additions = {}
    if "source" not in existing:
        additions["source"] = sa.Column("source", sa.String(16), nullable=False, server_default="UPLOADED")
    if "license" not in existing:
        additions["license"] = sa.Column("license", sa.String(64))
    if "source_metadata" not in existing:
        additions["source_metadata"] = sa.Column("source_metadata", sa.JSON)
    if additions:
        with op.batch_alter_table("materials") as batch_op:
            for col in additions.values():
                batch_op.add_column(col)


def downgrade() -> None:
    with op.batch_alter_table("materials") as batch_op:
        batch_op.drop_column("source_metadata")
        batch_op.drop_column("license")
        batch_op.drop_column("source")
    op.drop_table("material_candidates")
