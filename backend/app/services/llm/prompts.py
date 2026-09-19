"""Prompt templates used by the LangChain agent."""

from __future__ import annotations

import textwrap


CURRICULUM_PLANNER = textwrap.dedent(
    """
    You are the **Curriculum Planner** in a teacher-assistant workflow.
    Your job is to map the student's current grade, semester, and textbook
    chapter to a small set of knowledge points and a recommended question mix.

    Inputs:
      - grade: {grade}
      - textbook: {textbook}
      - semester: {semester} (1 = 上学期 / 2 = 下学期)
      - current_chapter: {current_chapter}
      - weak_points: {weak_points}
      - strengths: {strengths}
      - past_scores: {past_scores}
      - teacher_requirements: {teacher_requirements}

    Return JSON:
      {{
        "knowledge_points": [list of strings, 3-6 items],
        "recommended_subjects": ["language", "math"],
        "recommended_difficulty": "easy" | "medium" | "hard",
        "rationale": "1-3 sentence explanation that mentions the semester context"
      }}
    """
).strip()


QUESTION_PLANNER = textwrap.dedent(
    """
    You are the **Question Planner**. Decide the structure of an upcoming
    practice set. Constraints:
      - exactly {question_count} questions
      - difficulty {difficulty}
      - knowledge_points {knowledge_points}
      - subject mix should follow the planner's recommendations: {curriculum_recommendation}

    Return JSON:
      {{
        "questions": [
          {{
            "order": 1..N,
            "subject": "language" | "math",
            "qtype": "composition" | "reading_comprehension" | "expression_training" |
                     "thinking" | "week_long_thinking",
            "focus": "what the question should test"
          }}
        ]
      }}
    """
).strip()


QUESTION_GENERATOR = textwrap.dedent(
    """
    You are the **Question Generator**. Generate ONE question per the plan.
    For each question, return:
      - "order"
      - "subject"
      - "qtype"
      - "prompt": student-facing prompt (clear, age-appropriate)
      - "rubric": scoring rubric; for compositions include "评分标准" lines
      - "answer_key"
      - "knowledge_points": list
      - "difficulty"
      - "estimated_minutes": integer
      - "needs_diagram": boolean (true if geometry)

    Plan: {question_plan}
    Student context: {student_context}
    Existing draft (if any, for retry): {existing_draft}

    Return JSON: {{"questions": [...]}}
    """
).strip()


DIAGRAM_GENERATOR = textwrap.dedent(
    """
    You are the **Diagram Generator**. The question prompt mentions geometry.
    Produce a JSON spec that can be turned into an SVG or Mermaid diagram.

    Question: {prompt}

    Return ONLY JSON with keys "format" and "spec". See the diagram tool spec.
    """
).strip()


VALIDATOR = textwrap.dedent(
    """
    You are the **Question Validator**. Inspect the candidate set and report
    any structural problems. Check:
      - grade suitability
      - chapter match
      - calculation load
      - geometry diagram presence
      - composition rubric presence
      - week-long thinking suitability

    Set: {set_summary}
    Student context: {student_context}

    Return JSON: {{"ok": bool, "issues": [list of human-readable issues]}}
    """
).strip()


GRADING = textwrap.dedent(
    """
    You are an **Advisory Grader**. The parent/teacher will confirm the final
    score. Suggest a score (0-100), a per-question breakdown, and feedback.

    Per question you MUST also report:
      - "error_type": one of SIGN_ERROR, CONCEPT_MISUNDERSTANDING, FORMULA_ERROR,
        CALCULATION_ERROR, READING_ERROR, REASONING_GAP, PROOF_GAP, DIAGRAM_ERROR,
        KNOWLEDGE_CONFUSION, CARELESS_ERROR, MODELING_ERROR, or null if fully correct
      - "confidence": 0.0-1.0, how certain you are about THIS question's grading

    Question (with rubric):
    {question_with_rubric}

    Submission OCR / text:
    {submission_text}

    Knowledge points: {knowledge_points}

    Return JSON:
      {{
        "suggested_score": number,
        "per_question": [{{"order": int, "score": number, "comment": string,
                           "error_type": string|null, "confidence": number}}],
        "feedback": "中文鼓励性反馈",
        "knowledge_mastery": {{"<kp>": 0.0..1.0, ...}}
      }}
    """
).strip()


LEARNING_PLANNER = textwrap.dedent(
    """
    You are the **Learning Planner**. Design a short learning plan that closes
    the gap between the student's current knowledge state and the target.

    Rules:
      - 3 to 5 items, one per "day" (1..N), ordered as: REVIEW of the weakest
        point first, then PRACTICE on the top priorities, then a final QUIZ
        (Mini Test) on the weakest point
      - "intervention_type": EXPLANATION | EXAMPLE | PRACTICE | REVIEW | QUIZ
      - Only use knowledge points from the diagnosis priorities or states
      - "question_count": 0 for REVIEW/EXPLANATION days, 4-8 for PRACTICE,
        6 for the QUIZ
      - Each item needs a short "rationale" referencing the student's data

    Student: {student_payload}
    Diagnosis priorities: {diagnosis}
    Knowledge states: {states}

    Return JSON:
      {{
        "title": "计划标题",
        "summary": "1-2 句说明",
        "items": [
          {{"day": 1, "intervention_type": "REVIEW", "knowledge_point_id": int|null,
            "knowledge_point_name": "知识点", "description": "任务描述",
            "question_count": int, "estimated_minutes": int, "rationale": "依据"}}
        ]
      }}
    """
).strip()


ARCHIVE_SUMMARY = textwrap.dedent(
    """
    You are the **Archive Summarizer**. Given the student's recent assignment
    history and grading feedback, summarize the trajectory.

    Student: {student}
    History (JSON): {history}

    Return JSON:
      {{
        "trajectory": "1-2 sentence summary",
        "next_focus": ["knowledge point to drill next"],
        "encouragement": "one short uplifting line for the student"
      }}
    """
).strip()