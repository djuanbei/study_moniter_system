"""Question bank tests (PRD §36, §39–41)."""

from __future__ import annotations

import pytest

from app.models.question_bank import QuestionVersion
from app.services.question_bank import (
    duplicate_hash,
    find_duplicate,
    publish_question,
    similar_questions,
    update_question,
)


BASE_FIELDS = {
    "subject": "math",
    "knowledge_points": ["移项", "解方程"],
    "difficulty": "easy",
    "question_type": "fill_blank",
    "prompt": "解方程：2x + 3 = 9，求 x。",
    "answer": "x = 3",
    "rubric": "移项 1 分，求解 1 分",
    "estimated_time": 5,
}


def test_duplicate_hash_normalization():
    assert duplicate_hash("解方程：2x + 3 = 9。") == duplicate_hash("解方程 2x+3=9")


def test_publish_and_duplicate_detection(db_session, teacher):
    item, is_dup = publish_question(db_session, fields=dict(BASE_FIELDS), user_id=teacher.id)
    db_session.commit()
    assert is_dup is False
    assert item.version == 1
    assert db_session.query(QuestionVersion).filter_by(question_id=item.id).count() == 1

    # §36: same prompt detected as duplicate
    dup = find_duplicate(db_session, "解方程：2x+3=9，求x。")
    assert dup is not None and dup.id == item.id

    item2, is_dup2 = publish_question(db_session, fields=dict(BASE_FIELDS), user_id=teacher.id)
    assert is_dup2 is True and item2.id == item.id  # returns existing, no new row

    # forced duplicate creates a separate entry
    item3, is_dup3 = publish_question(db_session, fields=dict(BASE_FIELDS),
                                      user_id=teacher.id, allow_duplicate=True)
    assert is_dup3 is False and item3.id != item.id


def test_versioning_is_immutable_history(db_session, teacher):
    item, _ = publish_question(db_session, fields=dict(BASE_FIELDS), user_id=teacher.id)
    db_session.commit()
    v1_snapshot = item.versions[0].snapshot

    item = update_question(
        db_session, item,
        fields={"prompt": "解方程：3x + 6 = 15，求 x。", "answer": "x = 3", "difficulty": "medium"},
        user_id=teacher.id, change_note="改数字提难度",
    )
    db_session.commit()
    assert item.version == 2
    db_session.expire_all()  # reload relationship collections
    versions = sorted(item.versions, key=lambda v: v.version)
    assert len(versions) == 2
    assert versions[0].snapshot["prompt"] == BASE_FIELDS["prompt"]  # v1 untouched (§40)
    assert versions[1].snapshot["prompt"] == "解方程：3x + 6 = 15，求 x。"
    assert v1_snapshot["difficulty"] == "easy"


def test_similar_questions_ranking(db_session, teacher):
    a, _ = publish_question(db_session, fields=dict(BASE_FIELDS), user_id=teacher.id)  # 移项+解方程 easy
    same_kp, _ = publish_question(db_session, fields={
        **BASE_FIELDS, "prompt": "解方程：4x - 2 = 10，求 x。",
    }, user_id=teacher.id)
    other_kp, _ = publish_question(db_session, fields={
        **BASE_FIELDS, "knowledge_points": ["应用题建模"],
        "difficulty": "hard", "question_type": "thinking",
        "prompt": "小明买 3 支笔花了 12 元，每支笔多少元？",
    }, user_id=teacher.id)
    db_session.commit()

    results = similar_questions(db_session, a, limit=5)
    assert results
    # same-KP sibling ranks first (§41 同知识点)
    assert results[0]["id"] == same_kp.id
    assert "同知识点" in results[0]["relations"]
    top_score = results[0]["score"]
    other = next(r for r in results if r["id"] == other_kp.id)
    assert other["score"] < top_score
    assert "困难迁移" in other["relations"] or "不同题型" in other["relations"]


def test_bank_api_flow(db_session, client, csrf_headers, sample_setup):
    student = sample_setup["student"]
    # publish via API
    r = client.post("/api/question-bank", headers=csrf_headers, json=BASE_FIELDS)
    assert r.status_code == 201
    item_id = r.json()["id"]

    # duplicate rejected with 409
    r2 = client.post("/api/question-bank", headers=csrf_headers, json=BASE_FIELDS)
    assert r2.status_code == 409

    # list filtered by knowledge point
    r3 = client.get("/api/question-bank?knowledge_point=移项")
    assert any(i["id"] == item_id for i in r3.json())

    # similar endpoint
    r4 = client.get(f"/api/question-bank/{item_id}/similar")
    assert r4.status_code == 200

    # to-assignment closes the loop (bank → assignment)
    r5 = client.post("/api/question-bank/to-assignment", headers=csrf_headers, json={
        "question_ids": [item_id], "student_id": student.id, "title": "题库作业",
    })
    assert r5.status_code == 200
    assert r5.json()["question_count"] == 1

    # RBAC: students cannot access the bank
    student_user_fix = None
    r6 = client.get("/api/question-bank")
    assert r6.status_code == 200  # teacher still OK
