"""PRD §80 extended entities + LLM traceability + rationale + magic-bytes.

Revision ID: 0013_extended_entities
Revises: 0012_material_agent
Create Date: 2026-09-21 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0013_extended_entities"
down_revision: Union[str, None] = "0012_material_agent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add(table: str, *columns: sa.Column) -> None:
    """Add plain (non-FK) columns to an existing table (SQLite ALTER TABLE OK)."""
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return
    existing = {col["name"] for col in insp.get_columns(table)}
    for col in columns:
        if col.name in existing:
            continue
        op.add_column(table, col)


def _add_fk(table: str, *columns: sa.Column) -> None:
    """Add columns that include FKs to an existing table.

    SQLite ALTER TABLE cannot add FK constraints, so we use batch mode which
    requires all constraints to be named. The column definitions passed in
    must already carry explicit `name=` on each ForeignKey.
    """
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return
    existing = {col["name"] for col in insp.get_columns(table)}
    with op.batch_alter_table(table) as batch_op:
        for col in columns:
            if col.name not in existing:
                batch_op.add_column(col)


def upgrade() -> None:
    # ---- llm_runs: model_version + job_id (PRD §72) ----
    _add("llm_runs", sa.Column("model_version", sa.String(64)))
    _add_fk(
        "llm_runs",
        sa.Column(
            "job_id",
            sa.Integer,
            sa.ForeignKey("jobs.id", ondelete="SET NULL", name="fk_llm_runs_job_id"),
        ),
    )
    op.create_index("ix_llm_runs_model_version", "llm_runs", ["model_version"], if_not_exists=True)
    op.create_index("ix_llm_runs_job_id", "llm_runs", ["job_id"], if_not_exists=True)

    # ---- students.school (PRD §15) ----
    _add("students", sa.Column("school", sa.String(128)))
    op.create_index("ix_students_school", "students", ["school"], if_not_exists=True)

    # ---- questions: per-question rationale (PRD §37) ----
    _add(
        "questions",
        sa.Column("rationale", sa.Text),
        sa.Column("error_type_hint", sa.String(48)),
        sa.Column("source_evidence_ids", sa.JSON, server_default=sa.text("'[]'")),
    )

    # ---- Textbook hierarchy (PRD §18) ----
    op.create_table(
        "textbooks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("subject", sa.String(32), nullable=False),
        sa.Column("publisher", sa.String(64)),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_textbooks_name", "textbooks", ["name"])
    op.create_index("ix_textbooks_subject", "textbooks", ["subject"])

    op.create_table(
        "textbook_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("textbook_id", sa.Integer, sa.ForeignKey("textbooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("year", sa.Integer),
        sa.Column("grade_band", sa.String(32)),
        sa.Column("isbn", sa.String(32)),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_textbook_versions_textbook_id", "textbook_versions", ["textbook_id"])
    op.create_index("ix_textbook_versions_grade_band", "textbook_versions", ["grade_band"])

    op.create_table(
        "sections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("textbook_version_id", sa.Integer, sa.ForeignKey("textbook_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", sa.Integer, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("parent_section_id", sa.Integer, sa.ForeignKey("sections.id", ondelete="SET NULL")),
        sa.Column("order", sa.Integer, nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sections_textbook_version_id", "sections", ["textbook_version_id"])
    op.create_index("ix_sections_chapter_id", "sections", ["chapter_id"])

    # ---- Knowledge point versions (PRD §24) ----
    op.create_table(
        "knowledge_point_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("knowledge_point_id", sa.Integer, sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("snapshot", sa.JSON, nullable=False),
        sa.Column("change_note", sa.String(255)),
        sa.Column("published_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("published_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_knowledge_point_versions_kp_id", "knowledge_point_versions", ["knowledge_point_id"])
    op.create_index("ix_knowledge_point_versions_published_at", "knowledge_point_versions", ["published_at"])

    # ---- Material versions / pages / chunks (PRD §20) ----
    op.create_table(
        "material_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("material_id", sa.Integer, sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("snapshot", sa.JSON, nullable=False),
        sa.Column("change_note", sa.String(255)),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_material_versions_material_id", "material_versions", ["material_id"])

    op.create_table(
        "material_pages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("material_id", sa.Integer, sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("image_rel_path", sa.String(512)),
        sa.Column("ocr_text", sa.Text),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("sha256", sa.String(64)),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_material_pages_material_id", "material_pages", ["material_id"])
    op.create_index("ix_material_pages_sha256", "material_pages", ["sha256"])

    op.create_table(
        "material_chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("material_id", sa.Integer, sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_id", sa.Integer, sa.ForeignKey("material_pages.id", ondelete="SET NULL")),
        sa.Column("order", sa.Integer, nullable=False),
        sa.Column("chunk_type", sa.String(32), nullable=False),
        sa.Column("text", sa.Text),
        sa.Column("payload", sa.JSON),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_material_chunks_material_id", "material_chunks", ["material_id"])
    op.create_index("ix_material_chunks_page_id", "material_chunks", ["page_id"])
    op.create_index("ix_material_chunks_chunk_type", "material_chunks", ["chunk_type"])

    # ---- Learning sessions + interventions (PRD §80, §62) ----
    op.create_table(
        "learning_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_item_id", sa.Integer, sa.ForeignKey("learning_plan_items.id", ondelete="SET NULL")),
        sa.Column("assignment_id", sa.Integer, sa.ForeignKey("assignments.id", ondelete="SET NULL")),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("ended_at", sa.DateTime),
        sa.Column("duration_minutes", sa.Integer),
        sa.Column("focus", sa.String(255)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_learning_sessions_student_id", "learning_sessions", ["student_id"])
    op.create_index("ix_learning_sessions_plan_item_id", "learning_sessions", ["plan_item_id"])
    op.create_index("ix_learning_sessions_assignment_id", "learning_sessions", ["assignment_id"])

    op.create_table(
        "learning_interventions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_item_id", sa.Integer, sa.ForeignKey("learning_plan_items.id", ondelete="SET NULL")),
        sa.Column("knowledge_point_id", sa.Integer, sa.ForeignKey("knowledge_points.id", ondelete="SET NULL")),
        sa.Column("intervention_type", sa.String(16), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("planned_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
        sa.Column("status", sa.String(16), nullable=False, server_default="planned"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_learning_interventions_student_id", "learning_interventions", ["student_id"])
    op.create_index("ix_learning_interventions_plan_item_id", "learning_interventions", ["plan_item_id"])
    op.create_index("ix_learning_interventions_kp_id", "learning_interventions", ["knowledge_point_id"])

    # ---- Assignment / exam versioning + per-exam question join (PRD §80) ----
    op.create_table(
        "assignment_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("assignment_id", sa.Integer, sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("snapshot", sa.JSON, nullable=False),
        sa.Column("change_note", sa.String(255)),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_assignment_versions_assignment_id", "assignment_versions", ["assignment_id"])

    op.create_table(
        "exam_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("exam_id", sa.Integer, sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("snapshot", sa.JSON, nullable=False),
        sa.Column("change_note", sa.String(255)),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_exam_versions_exam_id", "exam_versions", ["exam_id"])

    op.create_table(
        "exam_questions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("exam_id", sa.Integer, sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("order", sa.Integer, nullable=False),
        sa.Column("max_score", sa.Float, nullable=False, server_default=sa.text("10")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_exam_questions_exam_id", "exam_questions", ["exam_id"])
    op.create_index("ix_exam_questions_question_id", "exam_questions", ["question_id"])

    # ---- Student answers + versions (PRD §77, §80) ----
    op.create_table(
        "student_answers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id", ondelete="SET NULL")),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("submissions.id", ondelete="SET NULL")),
        sa.Column("exam_attempt_id", sa.Integer, sa.ForeignKey("exam_attempts.id", ondelete="SET NULL")),
        sa.Column("answer_text", sa.Text),
        sa.Column("answer_payload", sa.JSON),
        sa.Column("confidence", sa.Float),
        sa.Column("source_type", sa.String(16), nullable=False, server_default="ONLINE"),
        sa.Column("image_id", sa.Integer, sa.ForeignKey("submission_images.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_student_answers_student_id", "student_answers", ["student_id"])
    op.create_index("ix_student_answers_question_id", "student_answers", ["question_id"])
    op.create_index("ix_student_answers_submission_id", "student_answers", ["submission_id"])
    op.create_index("ix_student_answers_exam_attempt_id", "student_answers", ["exam_attempt_id"])

    op.create_table(
        "answer_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_answer_id", sa.Integer, sa.ForeignKey("student_answers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_text", sa.Text),
        sa.Column("new_text", sa.Text),
        sa.Column("changed_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("changed_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_answer_versions_student_answer_id", "answer_versions", ["student_answer_id"])
    op.create_index("ix_answer_versions_changed_at", "answer_versions", ["changed_at"])

    # ---- Parent annotation + parent score (PRD §46, §49) ----
    op.create_table(
        "parent_annotations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id", ondelete="SET NULL")),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("submissions.id", ondelete="SET NULL")),
        sa.Column("exam_attempt_id", sa.Integer, sa.ForeignKey("exam_attempts.id", ondelete="SET NULL")),
        sa.Column("annotation", sa.Text, nullable=False),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_parent_annotations_student_id", "parent_annotations", ["student_id"])

    op.create_table(
        "parent_scores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("submissions.id", ondelete="SET NULL")),
        sa.Column("exam_attempt_id", sa.Integer, sa.ForeignKey("exam_attempts.id", ondelete="SET NULL")),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id", ondelete="SET NULL")),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("max_score", sa.Float),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_parent_scores_student_id", "parent_scores", ["student_id"])

    # ---- Progress history + error patterns (PRD §58, §80) ----
    op.create_table(
        "student_progress_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("progress_id", sa.Integer, sa.ForeignKey("student_progress.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mastery", sa.Float, nullable=False),
        sa.Column("last_score", sa.Float),
        sa.Column("changed_at", sa.DateTime, nullable=False),
        sa.Column("reason", sa.String(255)),
    )
    op.create_index("ix_student_progress_history_progress_id", "student_progress_history", ["progress_id"])

    op.create_table(
        "error_patterns",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(48), nullable=False, unique=True),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("remediation", sa.Text),
        sa.Column("severity", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_error_patterns_code", "error_patterns", ["code"], unique=True)

    op.create_table(
        "student_error_evidence",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("error_pattern_id", sa.Integer, sa.ForeignKey("error_patterns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_point_id", sa.Integer, sa.ForeignKey("knowledge_points.id", ondelete="SET NULL")),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("submissions.id", ondelete="SET NULL")),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id", ondelete="SET NULL")),
        sa.Column("evidence_id", sa.Integer, sa.ForeignKey("learning_evidence.id", ondelete="SET NULL")),
        sa.Column("note", sa.Text),
        sa.Column("occurred_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_student_error_evidence_student_id", "student_error_evidence", ["student_id"])
    op.create_index("ix_student_error_evidence_pattern_id", "student_error_evidence", ["error_pattern_id"])
    op.create_index("ix_student_error_evidence_kp_id", "student_error_evidence", ["knowledge_point_id"])
    op.create_index("ix_student_error_evidence_occurred_at", "student_error_evidence", ["occurred_at"])

    # ---- Question embeddings + signatures (PRD §36, §41) ----
    op.create_table(
        "question_embeddings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("dim", sa.Integer, nullable=False),
        sa.Column("vector", sa.LargeBinary, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "question_signatures",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signature", sa.String(128), nullable=False),
        sa.Column("algorithm", sa.String(32), nullable=False, server_default="sha256-norm"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_question_signatures_question_id", "question_signatures", ["question_id"])
    op.create_index("ix_question_signatures_signature", "question_signatures", ["signature"])

    # ---- Agent runs + import reviews + exports (PRD §22, §68, §69, §78) ----
    op.create_table(
        "material_agent_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("triggered_by", sa.String(32), nullable=False, server_default="schedule"),
        sa.Column("candidates_created", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("llm_run_id", sa.Integer, sa.ForeignKey("llm_runs.id", ondelete="SET NULL")),
        sa.Column("payload", sa.JSON),
        sa.Column("error", sa.Text),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "knowledge_update_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("triggered_by", sa.String(32), nullable=False, server_default="schedule"),
        sa.Column("candidates_created", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("llm_run_id", sa.Integer, sa.ForeignKey("llm_runs.id", ondelete="SET NULL")),
        sa.Column("payload", sa.JSON),
        sa.Column("error", sa.Text),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "question_bank_update_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("triggered_by", sa.String(32), nullable=False, server_default="schedule"),
        sa.Column("candidates_created", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("llm_run_id", sa.Integer, sa.ForeignKey("llm_runs.id", ondelete="SET NULL")),
        sa.Column("payload", sa.JSON),
        sa.Column("error", sa.Text),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "import_reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="SET NULL")),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("llm_run_id", sa.Integer, sa.ForeignKey("llm_runs.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_import_reviews_student_id", "import_reviews", ["student_id"])
    op.create_index("ix_import_reviews_source_type", "import_reviews", ["source_type"])

    op.create_table(
        "import_review_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("review_id", sa.Integer, sa.ForeignKey("import_reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.Integer),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("decision_note", sa.Text),
        sa.Column("decided_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decided_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_import_review_items_review_id", "import_review_items", ["review_id"])

    op.create_table(
        "exports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="SET NULL")),
        sa.Column("export_type", sa.String(32), nullable=False),
        sa.Column("target_type", sa.String(32)),
        sa.Column("target_id", sa.Integer),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("rel_path", sa.String(512), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("sha256", sa.String(64)),
        sa.Column("requester_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_exports_student_id", "exports", ["student_id"])
    op.create_index("ix_exports_export_type", "exports", ["export_type"])


def downgrade() -> None:
    # Drop in reverse order; leave the new llm_runs columns in place (no FK removal)
    for tbl in [
        "exports",
        "import_review_items",
        "import_reviews",
        "question_bank_update_runs",
        "knowledge_update_runs",
        "material_agent_runs",
        "question_signatures",
        "question_embeddings",
        "student_error_evidence",
        "error_patterns",
        "student_progress_history",
        "parent_scores",
        "parent_annotations",
        "answer_versions",
        "student_answers",
        "exam_questions",
        "exam_versions",
        "assignment_versions",
        "learning_interventions",
        "learning_sessions",
        "material_chunks",
        "material_pages",
        "material_versions",
        "knowledge_point_versions",
        "sections",
        "textbook_versions",
        "textbooks",
    ]:
        op.drop_table(tbl)

    op.drop_column("questions", "source_evidence_ids")
    op.drop_column("questions", "error_type_hint")
    op.drop_column("questions", "rationale")
    op.drop_column("students", "school")
    op.drop_column("llm_runs", "job_id")
    op.drop_column("llm_runs", "model_version")