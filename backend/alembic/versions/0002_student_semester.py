"""Add Student.current_semester.

Revision ID: 0002_student_semester
Revises: 0001_init
Create Date: 2026-09-19 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002_student_semester"
down_revision: Union[str, None] = "0001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("students") as batch_op:
        batch_op.add_column(sa.Column("current_semester", sa.Integer, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("students") as batch_op:
        batch_op.drop_column("current_semester")