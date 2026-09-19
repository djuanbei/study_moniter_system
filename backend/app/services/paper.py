"""Question-set paper export (PRD §78): printable PDF in three variants.

Variants:
    student — questions only (no answers, rubric, or AI internals)
    answer  — questions + answer key (答案版)
    rubric  — questions + answer key + scoring rubric (评分标准版)

Chinese-capable font is auto-detected (same candidates as the archive PDF).
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.models.assignments import Question, QuestionSet

_VARIANTS = ("student", "answer", "rubric")


def _register_chinese_font() -> str:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("CJK", path))
                return "CJK"
            except Exception:
                continue
    return "Helvetica"


def _wrap(text: str, width: int) -> list[str]:
    """Char-count wrapping; adequate for CJK exam layout."""
    lines: list[str] = []
    for raw_line in (text or "").strip().splitlines():
        raw_line = raw_line.rstrip()
        if not raw_line:
            lines.append("")
            continue
        for i in range(0, len(raw_line), width):
            lines.append(raw_line[i : i + width])
    return lines


def question_set_pdf(db: Session, qs: QuestionSet, variant: str = "student") -> bytes:
    if variant not in _VARIANTS:
        raise ValueError(f"unknown variant: {variant}")

    questions: list[Question] = sorted(qs.questions, key=lambda q: q.order)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    font = _register_chinese_font()
    width, height = A4
    page_num = 1

    def header() -> None:
        c.setFont(font, 16)
        c.drawString(50, height - 50, "练习卷")
        c.setFont(font, 10)
        c.drawString(
            50, height - 66,
            f"难度: {qs.difficulty}   题数: {len(questions)}   生成: {datetime.utcnow():%Y-%m-%d}",
        )
        if variant != "student":
            label = {"answer": "（答案版 · 家长保留）", "rubric": "（评分标准版 · 家长保留）"}[variant]
            c.drawRightString(width - 50, height - 66, label)
        c.line(50, height - 74, width - 50, height - 74)

    def footer() -> None:
        c.setFont(font, 9)
        c.drawCentredString(width / 2, 40, f"第 {page_num} 页 · 学习陪伴系统")

    header()
    y = height - 96
    for q in questions:
        if y < 90:
            footer()
            c.showPage()
            page_num += 1
            header()
            y = height - 96
        c.setFont(font, 12)
        c.drawString(50, y, f"{q.order}. [{q.qtype} · {q.difficulty}]")
        y -= 18
        c.setFont(font, 11)
        for line in _wrap(q.prompt, 46):
            c.drawString(60, y, line)
            y -= 15
        if variant in ("answer", "rubric") and q.answer_key:
            c.setFillColorRGB(0, 0, 0.55)
            for line in _wrap(f"答案：{q.answer_key}", 46):
                c.drawString(60, y, line)
                y -= 15
            c.setFillColorRGB(0, 0, 0)
        if variant == "rubric" and q.rubric:
            c.setFillColorRGB(0.35, 0.35, 0.35)
            for line in _wrap(f"评分标准：{q.rubric}", 50):
                c.drawString(60, y, line)
                y -= 13
            c.setFillColorRGB(0, 0, 0)
        if q.estimated_minutes:
            c.setFont(font, 9)
            c.setFillColorRGB(0.4, 0.4, 0.4)
            c.drawString(60, y, f"（约 {q.estimated_minutes} 分钟）")
            c.setFillColorRGB(0, 0, 0)
            y -= 13
        y -= 8

    footer()
    c.save()
    return buf.getvalue()
