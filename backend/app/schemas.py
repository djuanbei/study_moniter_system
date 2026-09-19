"""Pydantic request / response schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# --- Auth ---

class LoginIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class BootstrapOut(BaseModel):
    csrf_token: str
    user: Optional[dict[str, Any]] = None
    must_change_password: bool = False


# --- Users / accounts ---

class UserOut(BaseModel):
    id: int
    username: str
    role: str
    display_name: Optional[str]
    is_active: bool
    must_change_password: bool
    student_id: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class UserCreateIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(pattern="^(teacher|student)$")
    display_name: Optional[str] = None
    student_id: Optional[int] = None


class UserUpdateIn(BaseModel):
    role: Optional[str] = Field(default=None, pattern="^(teacher|student)$")
    display_name: Optional[str] = None
    is_active: Optional[bool] = None


class PasswordResetIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


# --- Classes ---

class ClassIn(BaseModel):
    name: str
    grade: Optional[str] = None
    textbook_version: Optional[str] = None
    year: Optional[int] = None
    notes: Optional[str] = None


class ClassOut(ClassIn):
    id: int
    model_config = ConfigDict(from_attributes=True)


# --- Chapters ---

class ChapterIn(BaseModel):
    textbook_version: str
    grade: str
    order: int
    title: str
    knowledge_points: list[str] = []
    semester: Optional[int] = None
    start_week: Optional[int] = None
    end_week: Optional[int] = None


class ChapterOut(ChapterIn):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ChapterInferOut(BaseModel):
    textbook: Optional[str]
    grade: Optional[str]
    semester: Optional[int] = None
    suggestion: Optional[dict[str, Any]]
    chapters: list[str] = []


# --- Students ---

class StudentIn(BaseModel):
    name: str
    grade: Optional[str] = None
    class_id: Optional[int] = None
    textbook_version: Optional[str] = None
    current_chapter_id: Optional[int] = None
    current_semester: Optional[int] = Field(default=None, ge=1, le=2)
    weak_points: list[str] = []
    strengths: list[str] = []
    score_history: list[dict[str, Any]] = []
    notes: Optional[str] = None
    parent_contact: Optional[str] = None
    enrollment_date: Optional[date] = None


class StudentOut(StudentIn):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Question sets / questions ---

class QuestionIn(BaseModel):
    order: int
    qtype: str
    subject: str
    prompt: str
    rubric: Optional[str] = None
    answer_key: Optional[str] = None
    knowledge_points: list[str] = []
    difficulty: str = "medium"
    estimated_minutes: Optional[int] = None
    diagram_svg: Optional[str] = None
    diagram_format: Optional[str] = None


class QuestionOut(QuestionIn):
    id: int
    model_config = ConfigDict(from_attributes=True)


class QuestionSetOut(BaseModel):
    id: int
    label: str
    difficulty: str
    estimated_minutes: Optional[int]
    knowledge_points: list[str]
    question_count: int
    summary: Optional[str]
    validator_notes: Optional[str]
    questions: list[QuestionOut] = []
    model_config = ConfigDict(from_attributes=True)


class GenerateIn(BaseModel):
    student_id: int
    question_count: int = Field(default=6, ge=1, le=30)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    knowledge_points: list[str] = []
    question_types: list[str] = []
    due_date: Optional[datetime] = None
    estimated_minutes: Optional[int] = None
    calculator_allowed: bool = False
    requirements: Optional[str] = None
    use_existing_draft: Optional[dict[str, Any]] = None


class GenerateOut(BaseModel):
    curriculum: dict[str, Any]
    plan: dict[str, Any]
    sets: list[dict[str, Any]]


class MixAssignIn(BaseModel):
    title: str
    description: Optional[str] = None
    source_set_ids: list[int]
    selected_question_ids: list[int]
    student_id: int
    due_date: Optional[datetime] = None
    estimated_minutes: Optional[int] = None
    calculator_allowed: bool = False


# --- Assignments ---

class AssignmentOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    student_id: int
    question_set_id: int
    due_date: Optional[datetime]
    estimated_minutes: Optional[int]
    calculator_allowed: bool
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Submissions ---

class SubmissionImageOut(BaseModel):
    id: int
    question_number: Optional[int]
    filename: str
    size_bytes: int
    sha256: str
    mime_type: str
    url: str
    ocr_text: Optional[str]
    model_config = ConfigDict(from_attributes=True)


class SubmissionOut(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    submitted_at: datetime
    status: str
    text_answer: Optional[str]
    ocr_text: Optional[str]
    images: list[SubmissionImageOut] = []
    model_config = ConfigDict(from_attributes=True)


# --- Grading ---

class GradingConfirmIn(BaseModel):
    submission_id: int
    final_score: float = Field(ge=0, le=100)
    feedback: str
    per_question_scores: Optional[list[dict[str, Any]] | dict[str, Any]] = None
    reason: Optional[str] = None  # required when modifying an already-confirmed score (PRD §50)


class GradingOut(BaseModel):
    id: int
    submission_id: int
    llm_suggested_score: Optional[float]
    llm_suggested_feedback: Optional[str]
    llm_knowledge_mastery: Optional[dict[str, Any]]
    llm_confidence: Optional[float]
    needs_review: bool
    final_score: Optional[float]
    feedback: Optional[str]
    per_question_scores: Optional[Any]
    confirmed: bool
    confirmed_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)


# --- Learning loop (PRD §17, §24, §26, §29, §30, §56, §64) ---

class KnowledgePointOut(BaseModel):
    id: int
    name: str
    subject: Optional[str]
    description: Optional[str]
    chapter_id: Optional[int]
    grade: Optional[str]
    textbook_version: Optional[str]
    difficulty: str
    status: str
    model_config = ConfigDict(from_attributes=True)


class StudentKnowledgeStateOut(BaseModel):
    id: int
    student_id: int
    knowledge_point_id: int
    knowledge_point_name: Optional[str] = None
    mastery_score: float
    confidence: float
    evidence_count: int
    last_assessed: Optional[datetime]
    last_practiced: Optional[datetime]
    trend: str
    decay_risk: str
    review_interval_days: int
    next_review_at: Optional[datetime]
    status: str

    model_config = ConfigDict(from_attributes=True)


class EvidenceCreateIn(BaseModel):
    student_id: int
    knowledge_point_name: Optional[str] = None
    knowledge_point_id: Optional[int] = None
    correct: bool = True
    score: Optional[float] = Field(default=None, ge=0, le=100)
    comment: Optional[str] = None
    observation: str = Field(
        default="understood",
        pattern="^(understood|not_understood|careless|out_of_scope|neutral)$",
    )


class LearningEvidenceOut(BaseModel):
    id: int
    student_id: int
    question_id: Optional[int]
    submission_id: Optional[int]
    knowledge_point_id: Optional[int]
    knowledge_point_name: Optional[str]
    source_type: str
    correct: bool
    score: Optional[float]
    difficulty: Optional[str]
    error_type: Optional[str]
    feedback: Optional[str]
    confidence: Optional[float]
    trust_level: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LearningObjectiveIn(BaseModel):
    student_id: int
    knowledge_point_id: Optional[int] = None
    knowledge_point_name: Optional[str] = None
    description: str
    target_mastery: float = Field(default=0.8, ge=0, le=1)
    priority: int = Field(default=2, ge=1, le=3)
    deadline: Optional[date] = None


class LearningObjectiveOut(LearningObjectiveIn):
    id: int
    current_mastery: float
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LearningPlanItemOut(BaseModel):
    id: int
    plan_id: int
    day: int
    intervention_type: str
    knowledge_point_id: Optional[int]
    knowledge_point_name: Optional[str]
    description: str
    question_count: int
    estimated_minutes: Optional[int]
    rationale: Optional[str]
    status: str
    assignment_id: Optional[int]
    model_config = ConfigDict(from_attributes=True)


class LearningPlanOut(BaseModel):
    id: int
    student_id: int
    title: str
    summary: Optional[str]
    diagnosis_json: Optional[dict[str, Any]]
    status: str
    generated_by: str
    approved_at: Optional[datetime]
    created_at: datetime
    items: list[LearningPlanItemOut] = []
    model_config = ConfigDict(from_attributes=True)


class PlanGenerateIn(BaseModel):
    student_id: int


# --- Materials (PRD §21) ---

class MaterialOut(BaseModel):
    id: int
    material_type: str
    title: str
    textbook_version: Optional[str]
    grade: Optional[str]
    semester: Optional[int]
    filename: str
    sha256: str
    mime_type: str
    size_bytes: int
    status: str
    ocr_text: Optional[str]
    analysis_json: Optional[dict[str, Any]]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Historical assessment import (PRD §54–55) ---

class HistoricalQuestionOut(BaseModel):
    id: int
    order: int
    question_text: str
    student_answer: Optional[str]
    score: Optional[float]
    max_score: Optional[float]
    annotation: Optional[str]
    knowledge_point_name: Optional[str]
    error_type: Optional[str]
    confidence: Optional[float]
    status: str
    evidence_id: Optional[int]
    model_config = ConfigDict(from_attributes=True)


class HistoricalAssessmentOut(BaseModel):
    id: int
    material_id: Optional[int]
    student_id: int
    exam_title: str
    exam_date: Optional[date]
    status: str
    analysis_json: Optional[dict[str, Any]]
    questions: list[HistoricalQuestionOut] = []
    model_config = ConfigDict(from_attributes=True)


class HistoryAnalyzeIn(BaseModel):
    material_id: int
    student_id: int
    exam_title: str
    exam_date: Optional[date] = None


class HistoryConfirmItemIn(BaseModel):
    id: int
    knowledge_point_name: Optional[str] = None
    correct: Optional[bool] = None
    score: Optional[float] = Field(default=None, ge=0, le=100)
    error_type: Optional[str] = None
    comment: Optional[str] = None


class HistoryConfirmIn(BaseModel):
    items: list[HistoryConfirmItemIn]


# --- Async jobs (PRD §82–83) ---

class JobEnqueueIn(BaseModel):
    job_type: str
    payload: dict[str, Any] = {}


class JobOut(BaseModel):
    id: int
    job_type: str
    status: str
    payload: dict[str, Any]
    result: Optional[dict[str, Any]]
    error: Optional[str]
    attempts: int
    max_attempts: int
    created_by: Optional[int]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)


# --- Online exams (PRD §73–76) ---

class ExamCreateIn(BaseModel):
    student_id: int
    question_set_id: int
    title: str
    duration_minutes: int = Field(default=30, ge=1, le=300)
    total_score: float = Field(default=100.0, ge=1, le=1000)


class ExamOut(BaseModel):
    id: int
    title: str
    student_id: int
    question_set_id: int
    duration_minutes: int
    total_score: float
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ExamAttemptOut(BaseModel):
    id: int
    exam_id: int
    student_id: int
    started_at: datetime
    last_saved_at: Optional[datetime]
    deadline: datetime
    submitted_at: Optional[datetime]
    status: str
    submit_reason: Optional[str]
    score: Optional[float]
    feedback: Optional[str]
    answers_json: Optional[dict[str, Any]]
    per_question: Optional[dict[str, Any]]
    model_config = ConfigDict(from_attributes=True)


class ExamAnswerSaveIn(BaseModel):
    answers: dict[str, str]


class ExamSubmitIn(BaseModel):
    reason: str = Field(default="manual", pattern="^(manual|time_expired)$")


class ExamConfirmIn(BaseModel):
    final_score: float = Field(ge=0, le=100)
    feedback: Optional[str] = None
    per_question: Optional[dict[str, Any]] = None


# --- Settings ---

class SettingsOut(BaseModel):
    config: dict[str, Any]


class SettingsUpdateIn(BaseModel):
    config: dict[str, Any]


# --- Dashboard ---

class DashboardStats(BaseModel):
    student_count: int
    active_assignment_count: int
    pending_grading_count: int
    recent_llm_runs: int
    generated_this_week: int


# --- Audit ---

class AuditOut(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    target_type: Optional[str]
    target_id: Optional[int]
    ip_address: Optional[str]
    created_at: datetime
    detail: Optional[dict[str, Any]]
    model_config = ConfigDict(from_attributes=True)