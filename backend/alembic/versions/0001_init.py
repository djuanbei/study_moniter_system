"""Initial schema - all 14 tables.

Revision ID: 0001_init
Revises:
Create Date: 2026-01-01 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0001_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="teacher"),
        sa.Column("display_name", sa.String(64)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("last_login_at", sa.DateTime(timezone=False)),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="SET NULL"), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "classes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("grade", sa.String(32)),
        sa.Column("textbook_version", sa.String(64)),
        sa.Column("year", sa.Integer),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("textbook_version", sa.String(64), nullable=False),
        sa.Column("grade", sa.String(32), nullable=False),
        sa.Column("order", sa.Integer, nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("knowledge_points", sa.JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("semester", sa.Integer),
        sa.Column("start_week", sa.Integer),
        sa.Column("end_week", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chapters_textbook_version", "chapters", ["textbook_version"])
    op.create_index("ix_chapters_grade", "chapters", ["grade"])

    op.create_table(
        "students",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("grade", sa.String(32)),
        sa.Column("class_id", sa.Integer, sa.ForeignKey("classes.id", ondelete="SET NULL")),
        sa.Column("textbook_version", sa.String(64)),
        sa.Column("current_chapter_id", sa.Integer, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("weak_points", sa.JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("strengths", sa.JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("score_history", sa.JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("notes", sa.Text),
        sa.Column("parent_contact", sa.String(128)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("enrollment_date", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_students_name", "students", ["name"])
    op.create_index("ix_students_grade", "students", ["grade"])

    op.create_table(
        "student_progress",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", sa.Integer, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("mastery", sa.Float, nullable=False, server_default=sa.text("0")),
        sa.Column("last_score", sa.Float),
        sa.Column("last_assessed_at", sa.DateTime(timezone=False)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_student_progress_student_id", "student_progress", ["student_id"])

    op.create_table(
        "llm_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("agent", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("input_json", sa.JSON, nullable=False),
        sa.Column("output_json", sa.JSON),
        sa.Column("model", sa.String(64)),
        sa.Column("tokens_in", sa.Integer),
        sa.Column("tokens_out", sa.Integer),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    op.create_index("ix_llm_runs_agent", "llm_runs", ["agent"])
    op.create_index("ix_llm_runs_purpose", "llm_runs", ["purpose"])
    op.create_index("ix_llm_runs_created_at", "llm_runs", ["created_at"])

    op.create_table(
        "question_sets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("label", sa.String(8), nullable=False),
        sa.Column("generation_run_id", sa.Integer, sa.ForeignKey("llm_runs.id", ondelete="SET NULL")),
        sa.Column("difficulty", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("estimated_minutes", sa.Integer),
        sa.Column("knowledge_points", sa.JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("question_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("summary", sa.Text),
        sa.Column("validator_notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_set_id", sa.Integer, sa.ForeignKey("question_sets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=False)),
        sa.Column("estimated_minutes", sa.Integer),
        sa.Column("calculator_allowed", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(16), nullable=False, server_default="assigned"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_assignments_student_id", "assignments", ["student_id"])

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("question_set_id", sa.Integer, sa.ForeignKey("question_sets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order", sa.Integer, nullable=False),
        sa.Column("qtype", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(16), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("rubric", sa.Text),
        sa.Column("answer_key", sa.Text),
        sa.Column("knowledge_points", sa.JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("difficulty", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("estimated_minutes", sa.Integer),
        sa.Column("diagram_svg", sa.Text),
        sa.Column("diagram_format", sa.String(16)),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_questions_qtype", "questions", ["qtype"])
    op.create_index("ix_questions_subject", "questions", ["subject"])

    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("assignment_id", sa.Integer, sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="submitted"),
        sa.Column("archive_path", sa.String(512), nullable=False),
        sa.Column("text_answer", sa.Text),
        sa.Column("ocr_text", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_submissions_assignment_id", "submissions", ["assignment_id"])
    op.create_index("ix_submissions_student_id", "submissions", ["student_id"])

    op.create_table(
        "submission_images",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_number", sa.Integer),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("rel_path", sa.String(512), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.Column("ocr_text", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_submission_images_submission_id", "submission_images", ["submission_id"])
    op.create_index("ix_submission_images_sha256", "submission_images", ["sha256"])

    op.create_table(
        "gradings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grader_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("llm_run_id", sa.Integer, sa.ForeignKey("llm_runs.id", ondelete="SET NULL")),
        sa.Column("llm_suggested_score", sa.Float),
        sa.Column("llm_suggested_feedback", sa.Text),
        sa.Column("llm_knowledge_mastery", sa.JSON),
        sa.Column("final_score", sa.Float),
        sa.Column("feedback", sa.Text),
        sa.Column("per_question_scores", sa.JSON),
        sa.Column("confirmed", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("confirmed_at", sa.DateTime(timezone=False)),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_gradings_submission_id", "gradings", ["submission_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64)),
        sa.Column("target_id", sa.Integer),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("detail", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("value", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_settings_key", "settings", ["key"], unique=True)


def downgrade() -> None:
    for tbl in [
        "gradings",
        "submission_images",
        "submissions",
        "questions",
        "assignments",
        "question_sets",
        "student_progress",
        "students",
        "chapters",
        "classes",
        "llm_runs",
        "users",
        "audit_logs",
        "settings",
    ]:
        op.drop_table(tbl)