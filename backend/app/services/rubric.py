"""Rubric checking and duplicate detection for generated questions."""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

from app.models.assignments import Question


# --- Rubric checks -----------------------------------------------------------

LANGUAGE_TYPES = {"composition", "reading_comprehension", "expression_training"}
MATH_TYPES = {"thinking", "week_long_thinking"}
GEOMETRY_KEYWORDS = re.compile(r"几何|图形|三角形|四边形|圆|角|平行|垂直|直角|钝角|锐角|△|∠", re.UNICODE)


def has_diagram_geometry(question: Question) -> bool:
    return bool(question.subject == "math" and question.diagram_svg and question.diagram_format)


def detect_geometry_subject(prompt: str) -> bool:
    return bool(GEOMETRY_KEYWORDS.search(prompt))


def validate_question(question: Question) -> list[str]:
    """Return a list of human-readable issues; empty list means the question passes."""
    issues: list[str] = []

    if not question.prompt or len(question.prompt.strip()) < 10:
        issues.append("prompt is too short or empty")
    if not question.rubric:
        issues.append("rubric is missing")
    if not question.knowledge_points:
        issues.append("knowledge_points is empty")
    if question.estimated_minutes is None or question.estimated_minutes <= 0:
        issues.append("estimated_minutes must be positive")

    if question.subject == "language":
        if question.qtype not in LANGUAGE_TYPES:
            issues.append(f"language question must be one of {sorted(LANGUAGE_TYPES)}")
        if question.qtype == "composition" and (question.rubric or "").count("评分标准") < 1:
            issues.append("composition rubric should contain explicit grading criteria")

    elif question.subject == "math":
        if question.qtype not in MATH_TYPES:
            issues.append(f"math question must be one of {sorted(MATH_TYPES)}")
        if _looks_computation_intensive(question.prompt):
            issues.append("math question should avoid computation-heavy workloads")
        if detect_geometry_subject(question.prompt) and not has_diagram_geometry(question):
            issues.append("geometry question must include a diagram (svg or mermaid)")

    return issues


def _looks_computation_intensive(prompt: str) -> bool:
    # Cheap heuristic: more than 5 digits in the prompt suggests heavy calculation.
    return len(re.findall(r"\d", prompt)) > 12


def validate_set(questions: Iterable[Question]) -> dict[str, list[str]]:
    return {f"Q.id_{q.id}": validate_question(q) for q in questions}


# --- Duplicate detection -----------------------------------------------------

def prompt_hash(prompt: str) -> str:
    norm = re.sub(r"\s+", " ", prompt.strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def is_duplicate(prompt: str, recent_hashes: Iterable[str]) -> bool:
    return prompt_hash(prompt) in set(recent_hashes)