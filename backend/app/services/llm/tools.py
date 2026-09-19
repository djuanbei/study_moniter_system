"""LangChain tools used by the agent.

Each tool is a thin wrapper around a service or DB query:
  - sqlite_query
  - textbook_chapter_lookup
  - ocr_vision
  - svg_generate
  - rubric_check
  - duplicate_check
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from langchain_core.tools import tool
from sqlalchemy import text

from app.config import get_business_config
from app.database import SessionLocal
from app.services.chapter import all_chapter_titles
from app.services.ocr import ocr_image, ocr_pdf
from app.services.rubric import (
    is_duplicate,
    prompt_hash,
    validate_question,
)
from app.services.svg import diagram_from_json


logger = logging.getLogger(__name__)


@tool("sqlite_query", parse_docstring=True)
def sqlite_query(sql: str) -> str:
    """Run a read-only SELECT against the application database.

    Args:
        sql: A SELECT statement. Must not contain DDL/DML keywords.

    Returns:
        JSON-encoded rows (max 200).
    """
    blocked = ("insert", "update", "delete", "drop", "alter", "create", "pragma", "attach")
    lowered = sql.lower().strip()
    if not lowered.startswith("select"):
        return json.dumps({"error": "Only SELECT is allowed"})
    if any(token in lowered for token in blocked):
        return json.dumps({"error": "Statement contains blocked keyword"})

    db = SessionLocal()
    try:
        result = db.execute(text(sql))
        rows = [dict(r._mapping) for r in result][:200]
        return json.dumps(rows, default=str, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})
    finally:
        db.close()


@tool("textbook_chapter_lookup", parse_docstring=True)
def textbook_chapter_lookup(textbook: str, grade: str) -> str:
    """Return the configured chapter list for the given textbook + grade.

    Args:
        textbook: e.g. "人教版"
        grade: e.g. "初一"

    Returns:
        JSON list of chapter titles in order.
    """
    chapters = all_chapter_titles(textbook, grade)
    return json.dumps(chapters, ensure_ascii=False)


@tool("ocr_vision", parse_docstring=True)
def ocr_vision(image_path: str, is_pdf: bool = False) -> str:
    """Run OCR on a stored submission image or PDF.

    Args:
        image_path: absolute path to the image or PDF
        is_pdf: set true if the input is a PDF

    Returns:
        Extracted text (possibly empty if OCR failed).
    """
    path = Path(image_path)
    if not path.exists():
        return ""
    if is_pdf:
        return ocr_pdf(path)
    return ocr_image(path)


@tool("svg_generate", parse_docstring=True)
def svg_generate(llm_json_output: str) -> str:
    """Convert a JSON diagram spec (from the LLM) into SVG or Mermaid markup.

    Args:
        llm_json_output: the raw text the LLM emitted for the diagram step

    Returns:
        Either an SVG or Mermaid string.
    """
    try:
        fmt, payload = diagram_from_json(llm_json_output)
        return f"[{fmt}]\n{payload}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("svg_generate failed: %s", exc)
        return ""


@tool("rubric_check", parse_docstring=True)
def rubric_check(question_json: str) -> str:
    """Validate a single question JSON for required fields.

    Args:
        question_json: JSON string of a question dict.

    Returns:
        JSON list of issues. Empty list means OK.
    """
    try:
        q = json.loads(question_json)
    except Exception as exc:  # noqa: BLE001
        return json.dumps([f"invalid JSON: {exc}"])

    from app.models.assignments import Question

    fake = Question(
        id=0,
        question_set_id=0,
        order=q.get("order", 0),
        qtype=q.get("qtype", ""),
        subject=q.get("subject", ""),
        prompt=q.get("prompt", ""),
        rubric=q.get("rubric"),
        answer_key=q.get("answer_key"),
        knowledge_points=q.get("knowledge_points", []),
        difficulty=q.get("difficulty", "medium"),
        estimated_minutes=q.get("estimated_minutes"),
        diagram_svg=q.get("diagram_svg"),
        diagram_format=q.get("diagram_format"),
    )
    return json.dumps(validate_question(fake), ensure_ascii=False)


@tool("duplicate_check", parse_docstring=True)
def duplicate_check(prompt: str, recent_prompts_json: str) -> str:
    """Check whether a question prompt is a duplicate of a recent one.

    Args:
        prompt: candidate question prompt
        recent_prompts_json: JSON list of recent prompt strings

    Returns:
        JSON {{"duplicate": bool, "hash": "16-char hex"}}.
    """
    try:
        recent = json.loads(recent_prompts_json)
    except Exception:
        recent = []
    return json.dumps(
        {"duplicate": is_duplicate(prompt, [prompt_hash(p) for p in recent])},
        ensure_ascii=False,
    )


ALL_TOOLS = [
    sqlite_query,
    textbook_chapter_lookup,
    ocr_vision,
    svg_generate,
    rubric_check,
    duplicate_check,
]