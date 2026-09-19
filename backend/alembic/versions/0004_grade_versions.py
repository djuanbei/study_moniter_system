"""Grade versions (PRD §50) + intervention outcomes (PRD §63).

Revision ID: 0004_grade_versions
Revises: 0003_learning_loop
Create Date: 2026-09-19 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_grade_versions"
down_revision: Union[str, None] = "0003_learning_loop"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create(table: str, *columns: sa.Column) -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table(table):
        return
    op.create_table(table, *columns)


def _add_cols(table: str, **cols: sa.Column) -> None:
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
        "grade_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("grading_id", sa.Integer, sa.ForeignKey("gradings.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("submissions.id", ondelete="SET NULL"), index=True),
        sa.Column("previous_score", sa.Float),
        sa.Column("new_score", sa.Float, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("changed_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("changed_at", sa.DateTime, nullable=False, index=True),
    )

    _create(
        "intervention_outcomes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("plan_item_id", sa.Integer, sa.ForeignKey("learning_plan_items.id", ondelete="SET NULL"), index=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("knowledge_point_id", sa.Integer, sa.ForeignKey("knowledge_points.id", ondelete="SET NULL")),
        sa.Column("intervention_type", sa.String(16), nullable=False),
        sa.Column("before_mastery", sa.Float),
        sa.Column("after_mastery", sa.Float),
        sa.Column("delta", sa.Float),
        sa.Column("assessment_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, index=True),
    )

    _add_cols(
        "learning_plan_items",
        before_mastery=sa.Column("before_mastery", sa.Float, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("intervention_outcomes")
    op.drop_table("grade_versions")
    with op.batch_alter_table("learning_plan_items") as batch_op:
        batch_op.drop_column("before_mastery")
