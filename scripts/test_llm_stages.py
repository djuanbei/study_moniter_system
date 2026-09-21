"""End-to-end smoke test for every LLM stage.

Hits the live Minimax API through each stage in services/llm/agent.py
and verifies a corresponding LLMRun row is written with non-empty
output. Designed to be runnable against the same SQLite the running
server uses (idempotent: cleans up its own test rows).

Usage:
    cd backend && .venv/bin/python ../scripts/test_llm_stages.py
"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from app.config import get_business_config, get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.learning import KnowledgePoint  # noqa: E402
from app.models.students import Chapter, Student  # noqa: E402
from app.models.system import LLMRun  # noqa: E402
from app.services.llm import (  # noqa: E402
    stage_archive_summary,
    stage_bank_question,
    stage_curriculum_planning,
    stage_diagnosis,
    stage_grading,
    stage_history_analysis,
    stage_learning_plan,
    stage_material_analysis,
    stage_question_generation,
    stage_question_planning,
    stage_validation,
)


PASS = "[PASS]"
FAIL = "[FAIL]"


def banner(label: str) -> None:
    print(f"\n=== {label} ===")


def ensure_setup(db: Session) -> tuple[Student, Chapter, KnowledgePoint]:
    """Make sure at least one student + chapter + KP exist for tests."""
    student = (
        db.query(Student)
        .filter(Student.name == "__llm_test_student")
        .first()
    )
    if student is None:
        student = Student(
            name="__llm_test_student",
            grade="初一",
            textbook_version="人教版",
            current_semester=1,
            weak_points=["一元一次方程"],
            strengths=[],
            score_history=[],
        )
        db.add(student)
        db.flush()

    chapter = (
        db.query(Chapter)
        .filter(Chapter.grade == "初一", Chapter.textbook_version == "人教版")
        .order_by(Chapter.id.asc())
        .first()
    )
    if chapter is None:
        chapter = Chapter(
            textbook_version="人教版",
            grade="初一",
            order=1,
            title="一元一次方程",
            knowledge_points=["一元一次方程", "移项", "解方程"],
        )
        db.add(chapter)
        db.flush()

    kp = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.name == "一元一次方程")
        .first()
    )
    if kp is None:
        kp = KnowledgePoint(
            subject="math",
            name="一元一次方程",
            chapter_id=chapter.id,
            grade="初一",
            textbook_version="人教版",
        )
        db.add(kp)
        db.flush()

    db.commit()
    db.refresh(student)
    db.refresh(chapter)
    db.refresh(kp)
    return student, chapter, kp


def latest_run(db: Session, purpose: str) -> LLMRun | None:
    return (
        db.query(LLMRun)
        .filter(LLMRun.purpose == purpose)
        .order_by(LLMRun.id.desc())
        .first()
    )


def assert_run_recorded(db: Session, purpose: str) -> LLMRun:
    run = latest_run(db, purpose)
    if run is None:
        raise AssertionError(f"no LLMRun recorded for purpose={purpose}")
    if run.status != "ok":
        raise AssertionError(
            f"LLMRun {run.id} purpose={purpose} status={run.status} error={run.error!r}"
        )
    if not run.output_json:
        raise AssertionError(f"LLMRun {run.id} has empty output_json")
    return run


def test_curriculum(db: Session, student: Student) -> None:
    banner("stage_curriculum_planning")
    out = stage_curriculum_planning(
        db,
        student_payload={
            "grade": student.grade,
            "textbook": student.textbook_version,
            "semester": "上学期",
            "current_chapter": "一元一次方程",
            "weak_points": student.weak_points or [],
            "strengths": student.strengths or [],
            "score_history": student.score_history or [],
        },
        teacher_requirements={"question_count": 4, "difficulty": "medium"},
        user=None,
    )
    print(f"  knowledge_points: {out.get('knowledge_points')}")
    print(f"  rationale: {(out.get('rationale') or '')[:120]}")
    run = assert_run_recorded(db, "curriculum_planning")
    print(f"  {PASS} LLMRun #{run.id} agent={run.agent} model={run.model}")


def test_question_planning(db: Session) -> None:
    banner("stage_question_planning")
    out = stage_question_planning(
        db,
        curriculum={
            "knowledge_points": ["一元一次方程"],
            "recommended_difficulty": "medium",
            "rationale": "test",
        },
        teacher_requirements={"question_count": 4, "difficulty": "medium"},
        user=None,
    )
    print(f"  questions planned: {len(out.get('questions', []))}")
    run = assert_run_recorded(db, "question_planning")
    print(f"  {PASS} LLMRun #{run.id}")


def test_question_generation(db: Session, student: Student) -> None:
    banner("stage_question_generation")
    out = stage_question_generation(
        db,
        plan={
            "questions": [
                {
                    "order": 1,
                    "subject": "math",
                    "qtype": "thinking",
                    "focus": "移项",
                }
            ]
        },
        student_payload={
            "grade": student.grade,
            "weak_points": ["一元一次方程"],
        },
        existing_draft=None,
        user=None,
    )
    qs = out.get("questions", [])
    print(f"  generated: {len(qs)} question(s)")
    if qs:
        first = qs[0]
        print(f"  rationale: {(first.get('rationale') or '')[:140]}")
        print(f"  error_type_hint: {first.get('error_type_hint')}")
    run = assert_run_recorded(db, "question_generation")
    print(f"  {PASS} LLMRun #{run.id}")


def test_validation(db: Session) -> None:
    banner("stage_validation")
    out = stage_validation(
        db,
        generated={
            "questions": [
                {
                    "order": 1,
                    "subject": "math",
                    "qtype": "thinking",
                    "prompt": "解方程 2x + 3 = 9",
                    "rubric": "步骤明确",
                    "answer_key": "x=3",
                    "knowledge_points": ["一元一次方程"],
                    "difficulty": "medium",
                    "estimated_minutes": 5,
                }
            ]
        },
        student_payload={"grade": "初一"},
        user=None,
    )
    print(f"  ok={out.get('ok')} issues={out.get('issues')}")
    run = assert_run_recorded(db, "validation")
    print(f"  {PASS} LLMRun #{run.id}")


def test_grading(db: Session, kp: KnowledgePoint) -> None:
    banner("stage_grading")
    # We don't have a real submission+question_set; pass minimal stubs.
    from app.models.assignments import QuestionSet, Submission  # noqa: F401

    qs = QuestionSet(label="LLMTEST", difficulty="medium", question_count=1,
                     knowledge_points=[kp.name])
    db.add(qs)
    db.flush()

    from app.models.assignments import Question  # noqa: F401

    q = Question(
        question_set_id=qs.id,
        order=1,
        qtype="thinking",
        subject="math",
        prompt="解方程 2x + 3 = 9",
        rubric="步骤明确",
        answer_key="x=3",
        knowledge_points=[kp.name],
        difficulty="medium",
        estimated_minutes=5,
    )
    db.add(q)
    db.flush()

    sub = Submission(
        assignment_id=0,  # dummy — not persisted; we don't commit this submission
        student_id=1,
        submitted_at=datetime.utcnow(),
        archive_path="__test__",
        text_answer="2x = 9 - 3 = 6\nx = 3",
    )
    out = stage_grading(db, submission=sub, question_set=qs, user=None)
    print(f"  suggested_score: {out.get('suggested_score')}")
    print(f"  feedback: {(out.get('feedback') or '')[:140]}")
    print(f"  per_question entries: {len(out.get('per_question', []))}")
    run = assert_run_recorded(db, "grading")
    print(f"  {PASS} LLMRun #{run.id}")
    db.rollback()  # don't commit the dummy QuestionSet/Question


def test_learning_plan(db: Session, student: Student) -> None:
    banner("stage_learning_plan")
    plan, run_id = stage_learning_plan(
        db,
        student_payload={"name": student.name, "grade": student.grade,
                        "textbook": student.textbook_version},
        diagnosis={"priorities": [
            {"knowledge_point": "一元一次方程", "mastery": 0.35,
             "trend": "stable", "decay_risk": "MEDIUM"}
        ]},
        states=[{"knowledge_point": "一元一次方程", "mastery": 0.35,
                "trend": "stable", "decay_risk": "MEDIUM",
                "evidence_count": 3, "confidence": 0.6}],
        user_id=None,
    )
    print(f"  plan items: {len(plan.get('items', []))}")
    if plan.get('items'):
        print(f"  first item: {plan['items'][0]}")
    print(f"  {PASS} LLMRun #{run_id}")


def test_diagnosis(db: Session) -> None:
    banner("stage_diagnosis")
    out = stage_diagnosis(
        db,
        priorities=[{
            "knowledge_point": "一元一次方程",
            "rank": 1,
            "mastery": 0.35,
            "trend": "declining",
            "decay_risk": "HIGH",
            "recent_errors": ["SIGN_ERROR", "MODELING_ERROR"],
        }],
        student_context={"name": "test", "grade": "初一"},
        user=None,
    )
    print(f"  summary: {(out.get('summary') or '')[:140]}")
    print(f"  priorities: {len(out.get('priorities', []))}")
    if out.get('priorities'):
        first = out['priorities'][0]
        print(f"  first reasoning: {(first.get('reasoning') or '')[:140]}")
        print(f"  first next_steps: {first.get('next_steps')}")
    run = assert_run_recorded(db, "diagnosis")
    print(f"  {PASS} LLMRun #{run.id}")


def test_archive_summary(db: Session) -> None:
    banner("stage_archive_summary")
    out = stage_archive_summary(
        db,
        student_payload={"name": "test"},
        history=[{"date": "2026-01-01", "score": 80},
                {"date": "2026-01-15", "score": 85}],
        user=None,
    )
    print(f"  trajectory: {(out.get('trajectory') or '')[:140]}")
    print(f"  next_focus: {out.get('next_focus')}")
    run = assert_run_recorded(db, "archive_summary")
    print(f"  {PASS} LLMRun #{run.id}")


def test_material_analysis(db: Session) -> None:
    banner("stage_material_analysis")
    # Tiny OCR stub; the LLM just has to return valid chapters.
    fake_ocr = "第一章 有理数\n1.1 正数和负数\n1.2 有理数\n第二章 整式的加减\n2.1 整式\n2.2 整式的加减\n"
    analysis, run_id = stage_material_analysis(
        db,
        material_type="TEXTBOOK",
        grade="初一",
        ocr_text=fake_ocr,
        user=None,
    )
    if analysis is None:
        run = latest_run(db, "material_analysis")
        print(f"  (LLM returned nothing usable; LLMRun #{run.id} status={run.status})")
        return
    chapters = analysis.get("chapters", [])
    print(f"  chapters extracted: {len(chapters)}")
    if chapters:
        print(f"  first chapter: {chapters[0]}")
    print(f"  {PASS} LLMRun #{run_id}")


def test_history_analysis(db: Session) -> None:
    banner("stage_history_analysis")
    fake_ocr = (
        "1. 计算 2 + 3 = ?\n答：5\n得分：5\n"
        "2. 解方程 2x = 8\n答：x = 4\n得分：8\n"
    )
    items, run_id = stage_history_analysis(db, ocr_text=fake_ocr, user=None)
    if items is None:
        run = latest_run(db, "history_analysis")
        print(f"  (LLM returned nothing usable; LLMRun #{run.id} status={run.status})")
        return
    print(f"  questions recovered: {len(items)}")
    if items:
        print(f"  first item: {items[0]}")
    print(f"  {PASS} LLMRun #{run_id}")


def test_bank_question(db: Session) -> None:
    banner("stage_bank_question")
    out = stage_bank_question(
        db,
        knowledge_point="一元一次方程",
        grade="初一",
        difficulty="medium",
        estimated_time=10,
        existing_prompts=["解方程 2x + 3 = 7"],
        user=None,
    )
    if out is None:
        run = latest_run(db, "question_bank_update")
        print(f"  (LLM returned nothing; LLMRun #{run.id} status={run.status})")
        return
    print(f"  prompt: {(out.get('prompt') or '')[:140]}")
    print(f"  question_type: {out.get('question_type')}")
    print(f"  {PASS} LLMRun (latest={latest_run(db, 'question_bank_update').id})")


def main() -> int:
    s = get_settings()
    cfg = get_business_config().get("llm", {})
    print(f"provider: {s.llm_provider}  model: {s.llm_model}")
    print(f"base url: {s.minimax_base_url}")
    print(f"api key set: {bool(s.minimax_api_key)}")
    print(f"cfg model: {cfg.get('model')}")

    db = SessionLocal()
    try:
        student, chapter, kp = ensure_setup(db)
        tests = [
            ("curriculum_planning", lambda: test_curriculum(db, student)),
            ("question_planning", lambda: test_question_planning(db)),
            ("question_generation", lambda: test_question_generation(db, student)),
            ("validation", lambda: test_validation(db)),
            ("grading", lambda: test_grading(db, kp)),
            ("learning_plan", lambda: test_learning_plan(db, student)),
            ("diagnosis", lambda: test_diagnosis(db)),
            ("archive_summary", lambda: test_archive_summary(db)),
            ("material_analysis", lambda: test_material_analysis(db)),
            ("history_analysis", lambda: test_history_analysis(db)),
            ("bank_question", lambda: test_bank_question(db)),
        ]
        passed = 0
        failed = 0
        for name, fn in tests:
            try:
                fn()
                passed += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  {FAIL} {name}: {exc}")
                traceback.print_exc()
        print(f"\n=== {passed} passed, {failed} failed ===")
        return 0 if failed == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())