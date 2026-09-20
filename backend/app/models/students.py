"""Student-domain tables: students, classes, chapters, student progress."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._base import TimestampMixin


class Class(Base, TimestampMixin):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    grade: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    textbook_version: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    year: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    students: Mapped[list["Student"]] = relationship("Student", back_populates="class_")


class Chapter(Base, TimestampMixin):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    textbook_version: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    grade: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    knowledge_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    semester: Mapped[Optional[int]] = mapped_column(Integer)
    start_week: Mapped[Optional[int]] = mapped_column(Integer)
    end_week: Mapped[Optional[int]] = mapped_column(Integer)

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    grade: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    school: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    class_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("classes.id", ondelete="SET NULL")
    )
    textbook_version: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    current_chapter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL")
    )
    current_semester: Mapped[Optional[int]] = mapped_column(Integer)  # 1 = 上学期, 2 = 下学期
    weak_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    score_history: Mapped[list[dict]] = mapped_column(JSON, default=list)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    parent_contact: Mapped[Optional[str]] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enrollment_date: Mapped[Optional[datetime]] = mapped_column(Date)

    class_: Mapped[Optional[Class]] = relationship("Class", back_populates="students")
    current_chapter: Mapped[Optional[Chapter]] = relationship("Chapter")
    progress: Mapped[list["StudentProgress"]] = relationship(
        "StudentProgress", back_populates="student", cascade="all, delete-orphan"
    )


class StudentProgress(Base, TimestampMixin):
    __tablename__ = "student_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chapter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL")
    )
    mastery: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_score: Mapped[Optional[float]] = mapped_column(Float)
    last_assessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    student: Mapped[Student] = relationship("Student", back_populates="progress")
    chapter: Mapped[Optional[Chapter]] = relationship("Chapter")