"""DOCX export (PRD §79): editable exam papers parents can hand-modify.

Variants match the PDF paper export (§78):
    student — questions only (no answers, rubric, or AI internals)
    answer  — questions + answer key
    rubric  — questions + answer key + scoring rubric

Supports Chinese text, 题号, 分值, tables and heading styles. Vector diagrams
are noted as placeholders (print the PDF variant for those).
"""

from __future__ import annotations

import io
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from sqlalchemy.orm import Session

from app.models.assignments import Question, QuestionSet

_VARIANTS = ("student", "answer", "rubric")


def _set_font(document: Document) -> None:
    style = document.styles["Normal"]
    style.font.name = "PingFang SC"
    # Ensure East-Asian glyph mapping
    from docx.oxml.ns import qn

    style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    style.font.size = Pt(11)


def _add_question(document: Document, q: Question, variant: str) -> None:
    p = document.add_paragraph()
    run = p.add_run(f"{q.order}. ")
    run.bold = True
    meta = f"[{q.qtype} · {q.difficulty}"
    if q.estimated_minutes:
        meta += f" · 约{q.estimated_minutes}分钟"
    meta += "]"
    p.add_run(meta).italic = True

    document.add_paragraph(q.prompt)
    if (q.diagram_svg or q.diagram_format) and variant == "student":
        document.add_paragraph("（本题含图，请配合 PDF 版或打印图作答）").italic = True
    if variant in ("answer", "rubric") and q.answer_key:
        p = document.add_paragraph()
        run = p.add_run(f"答案：{q.answer_key}")
        run.bold = True
    if variant == "rubric" and q.rubric:
        p = document.add_paragraph(f"评分标准：{q.rubric}")
        p.runs[0].italic = True


def question_set_docx(db: Session, qs: QuestionSet, variant: str = "student") -> bytes:
    if variant not in _VARIANTS:
        raise ValueError(f"unknown variant: {variant}")

    questions: list[Question] = sorted(qs.questions, key=lambda q: q.order)
    document = Document()
    _set_font(document)

    # Header block (§79: 题号/中文)
    title = document.add_heading("练习卷", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta = document.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    variant_label = {"answer": "（答案版）", "rubric": "（评分标准版）"}.get(variant, "")
    meta.add_run(
        f"难度: {qs.difficulty}    题数: {len(questions)}    生成: {datetime.utcnow():%Y-%m-%d}"
        + (f"    {variant_label}" if variant_label else "")
    )
    document.add_paragraph()

    for q in questions:
        _add_question(document, q, variant)
        document.add_paragraph()

    #答题表 (§79: 表格) — a simple score table parents can fill in
    if questions:
        document.add_heading("评分表", level=1)
        table = document.add_table(rows=2, cols=len(questions) + 1)
        table.style = "Table Grid"
        header = table.rows[0].cells
        header[0].text = "题号"
        score_row = table.rows[1].cells
        score_row[0].text = "得分"
        for i, q in enumerate(questions, start=1):
            header[i].text = str(q.order)
            score_row[i].text = ""

    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()
