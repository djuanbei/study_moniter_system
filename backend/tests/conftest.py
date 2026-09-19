"""Pytest fixtures: isolated SQLite DB + auth/CSRF-ready TestClient."""

from __future__ import annotations

import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Keep test runs from touching real external services.
os.environ.setdefault("OCR_USE_VISION", "false")

from app.database import Base, get_db  # noqa: E402
from app.deps import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models import register_all  # noqa: E402
from app.models.assignments import (  # noqa: E402
    Assignment,
    Grading,
    Question,
    QuestionSet,
    Submission,
)
from app.models.auth import User  # noqa: E402
from app.models.students import Chapter, Student  # noqa: E402

register_all()


@pytest.fixture()
def db_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.sqlite",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = factory()
    yield session
    session.close()


@pytest.fixture()
def teacher(db_session):
    user = User(
        username="teacher1",
        password_hash="x",
        role="teacher",
        display_name="家长",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def student_user(db_session):
    """A student account linked to student #2 (for RBAC tests)."""
    student = Student(name="小明", grade="初一", textbook_version="人教版")
    db_session.add(student)
    db_session.flush()
    user = User(
        username="student1",
        password_hash="x",
        role="student",
        student_id=student.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user, student


@pytest.fixture()
def client(db_engine, teacher):
    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: teacher
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def csrf_headers():
    """Satisfy the double-submit CSRF check on unsafe methods."""
    return {"X-CSRF-Token": "test-token"}


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Hermetic tests: block every LLM entry point (deterministic fallbacks run)."""
    import app.services.llm.agent as agent
    import app.services.llm as pkg

    def _boom(*args, **kwargs):
        raise RuntimeError("tests: llm disabled")

    monkeypatch.setattr(pkg, "stage_material_analysis", _boom, raising=False)
    monkeypatch.setattr(pkg, "stage_learning_plan", _boom, raising=False)
    monkeypatch.setattr(pkg, "stage_history_analysis", _boom, raising=False)
    monkeypatch.setattr(pkg, "stage_bank_question", _boom, raising=False)
    monkeypatch.setattr(pkg, "generate_two_sets", _boom, raising=False)
    monkeypatch.setattr(agent, "get_chat_model", _boom, raising=False)


@pytest.fixture(autouse=True)
def _seed_csrf_cookie(client):
    client.cookies.set("sms_csrf", "test-token")


@pytest.fixture()
def sample_setup(db_session):
    """Chapter + KPs + a question set with 2 questions + assignment."""
    ch = Chapter(
        textbook_version="人教版", grade="初一", order=3, semester=1,
        title="一元一次方程", knowledge_points=["移项", "应用题建模"],
    )
    db_session.add(ch)
    db_session.flush()
    student = Student(
        name="测试学生", grade="初一", textbook_version="人教版",
        current_chapter_id=ch.id, current_semester=1,
    )
    db_session.add(student)
    db_session.flush()
    qs = QuestionSet(label="A", difficulty="easy", knowledge_points=["移项"], question_count=2)
    db_session.add(qs)
    db_session.flush()
    db_session.add(
        Question(
            question_set_id=qs.id, order=1, qtype="thinking", subject="math",
            prompt="解方程 2x + 3 = 9", answer_key="x = 3",
            rubric="移项 1 分，求解 1 分", knowledge_points=["移项"],
            difficulty="easy", estimated_minutes=5,
        )
    )
    db_session.add(
        Question(
            question_set_id=qs.id, order=2, qtype="thinking", subject="math",
            prompt="解方程 3x - 1 = 8", answer_key="x = 3",
            knowledge_points=["移项"], difficulty="easy", estimated_minutes=5,
        )
    )
    assignment = Assignment(
        title="移项练习", student_id=student.id, question_set_id=qs.id, status="assigned"
    )
    db_session.add(assignment)
    db_session.flush()
    submission = Submission(
        assignment_id=assignment.id, student_id=student.id,
        submitted_at=datetime.utcnow(), archive_path="uploads/test",
        text_answer="Q1: x=3\nQ2: x=4", status="submitted",
    )
    db_session.add(submission)
    db_session.flush()

    from app.services.learning import sync_knowledge_points

    sync_knowledge_points(db_session)  # chapter JSON -> KnowledgePoint rows
    db_session.commit()
    return {
        "chapter": ch, "student": student, "question_set": qs,
        "assignment": assignment, "submission": submission,
    }
