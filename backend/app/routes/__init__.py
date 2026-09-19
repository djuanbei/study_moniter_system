"""Routes package."""

from app.routes import (
    accounts,
    archive,
    assignments,
    auth,
    chapters,
    classes,
    dashboard,
    errors,
    grading,
    questions,
    settings,
    students,
    submissions,
)

__all__ = [
    "auth",
    "accounts",
    "students",
    "classes",
    "chapters",
    "assignments",
    "questions",
    "submissions",
    "grading",
    "archive",
    "settings",
    "dashboard",
    "errors",
]