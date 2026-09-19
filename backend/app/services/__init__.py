"""Services package."""

from app.services.archive import images_zip, student_csv, student_pdf
from app.services.chapter import (
    all_chapter_titles,
    chapters_for_semester,
    infer_chapter,
)
from app.services.ocr import ocr_image, ocr_pdf
from app.services.rubric import (
    LANGUAGE_TYPES,
    MATH_TYPES,
    is_duplicate,
    prompt_hash,
    validate_question,
    validate_set,
)
from app.services.svg import (
    build_diagram_prompt,
    diagram_from_json,
    render_mermaid,
    render_svg,
)

__all__ = [
    "infer_chapter",
    "all_chapter_titles",
    "chapters_for_semester",
    "ocr_image",
    "ocr_pdf",
    "render_svg",
    "render_mermaid",
    "build_diagram_prompt",
    "diagram_from_json",
    "validate_question",
    "validate_set",
    "is_duplicate",
    "prompt_hash",
    "LANGUAGE_TYPES",
    "MATH_TYPES",
    "student_csv",
    "student_pdf",
    "images_zip",
]