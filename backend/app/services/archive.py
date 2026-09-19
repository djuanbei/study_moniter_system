"""Student archive export: PDF / CSV / image ZIP."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.config import resolve_path
from app.models.assignments import (
    Assignment,
    Grading,
    QuestionSet,
    Submission,
    SubmissionImage,
)
from app.models.students import Student


def _register_chinese_font() -> str:
    """Register a Chinese-capable font if available, else fall back to Helvetica."""
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


def student_csv(db: Session, student: Student) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "key", "value"])
    writer.writerow(["profile", "name", student.name])
    writer.writerow(["profile", "grade", student.grade or ""])
    writer.writerow(["profile", "textbook", student.textbook_version or ""])
    writer.writerow(["profile", "weak_points", json.dumps(student.weak_points, ensure_ascii=False)])
    writer.writerow(["profile", "strengths", json.dumps(student.strengths, ensure_ascii=False)])
    for entry in student.score_history or []:
        writer.writerow(["score_history", entry.get("date", ""), json.dumps(entry, ensure_ascii=False)])

    assignments = db.query(Assignment).filter(Assignment.student_id == student.id).all()
    for a in assignments:
        subs = db.query(Submission).filter(Submission.assignment_id == a.id).all()
        writer.writerow(["assignment", f"#{a.id}", a.title])
        for s in subs:
            grade = (
                db.query(Grading)
                .filter(Grading.submission_id == s.id, Grading.confirmed == True)  # noqa: E712
                .order_by(Grading.confirmed_at.desc())
                .first()
            )
            writer.writerow(
                [
                    "submission",
                    f"A#{a.id}/S#{s.id}",
                    json.dumps(
                        {
                            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else "",
                            "score": grade.final_score if grade else None,
                            "feedback": (grade.feedback or "") if grade else "",
                        },
                        ensure_ascii=False,
                    ),
                ]
            )
    return buf.getvalue().encode("utf-8")


def student_pdf(db: Session, student: Student) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    font = _register_chinese_font()
    c.setFont(font, 18)
    c.drawString(50, 800, f"学习档案 - {student.name}")
    c.setFont(font, 11)
    c.drawString(50, 780, f"年级: {student.grade or '-'}   教材: {student.textbook_version or '-'}")
    y = 750
    c.setFont(font, 13)
    c.drawString(50, y, "弱项:")
    c.setFont(font, 11)
    y -= 18
    for w in (student.weak_points or [])[:6]:
        c.drawString(60, y, f"• {w}")
        y -= 14
    y -= 6
    c.setFont(font, 13)
    c.drawString(50, y, "优势:")
    y -= 18
    c.setFont(font, 11)
    for s in (student.strengths or [])[:6]:
        c.drawString(60, y, f"• {s}")
        y -= 14

    y -= 10
    c.setFont(font, 13)
    c.drawString(50, y, "作业与成绩:")
    y -= 18
    c.setFont(font, 10)
    assignments = db.query(Assignment).filter(Assignment.student_id == student.id).all()
    if not assignments:
        c.drawString(60, y, "(暂无)")
    for a in assignments:
        subs = db.query(Submission).filter(Submission.assignment_id == a.id).all()
        line = f"#{a.id}  {a.title}  ({a.status})"
        c.drawString(60, y, line)
        y -= 14
        for s in subs:
            g = (
                db.query(Grading)
                .filter(Grading.submission_id == s.id, Grading.confirmed == True)  # noqa: E712
                .order_by(Grading.confirmed_at.desc())
                .first()
            )
            score = f"{g.final_score:.1f}" if g and g.final_score is not None else "-"
            fb = (g.feedback or "") if g else ""
            c.drawString(75, y, f"提交 {s.submitted_at:%Y-%m-%d %H:%M}  得分 {score}  {fb[:60]}")
            y -= 12
            if y < 60:
                c.showPage()
                c.setFont(font, 10)
                y = 800
    c.save()
    return buf.getvalue()


def images_zip(db: Session, student: Student) -> bytes:
    buf = io.BytesIO()
    zf = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)
    images: Iterable[SubmissionImage] = (
        db.query(SubmissionImage)
        .join(Submission, SubmissionImage.submission_id == Submission.id)
        .filter(Submission.student_id == student.id)
        .all()
    )
    for img in images:
        full = resolve_path(img.rel_path)
        if full.exists():
            arcname = f"{img.submission.assignment_id}/{img.submission_id}/{img.filename}"
            zf.write(full, arcname)
    zf.writestr(
        "README.txt",
        f"Archive generated {datetime.utcnow().isoformat()} for student {student.name} (#{student.id})\n",
    )
    zf.close()
    return buf.getvalue()