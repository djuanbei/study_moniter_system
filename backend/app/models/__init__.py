"""SQLAlchemy ORM models.

Layout:
  - `auth`     : User, AuditLog
  - `students` : Student, Class, Chapter, StudentProgress
  - `assignments`: Assignment, QuestionSet, Question, Submission, SubmissionImage, Grading
  - `learning` : KnowledgePoint, StudentKnowledgeState(+History), LearningObjective,
                 LearningEvidence, ParentFeedback, LearningPlan(+Item)
  - `system`   : LLMRun, Setting
"""

from app.models.auth import AuditLog, User
from app.models.assignments import (
    Assignment,
    GradeVersion,
    Grading,
    Question,
    QuestionSet,
    Submission,
    SubmissionImage,
)
from app.models.learning import (
    InterventionOutcome,
    KnowledgePoint,
    LearningEvidence,
    LearningObjective,
    LearningPlan,
    LearningPlanItem,
    ParentFeedback,
    StudentKnowledgeState,
    StudentKnowledgeStateHistory,
)
from app.models.materials import Material
from app.models.students import Chapter, Class, Student, StudentProgress
from app.models.system import LLMRun, Setting

ALL_MODELS = [
    User,
    Student,
    Class,
    Chapter,
    StudentProgress,
    Assignment,
    QuestionSet,
    Question,
    Submission,
    SubmissionImage,
    Grading,
    GradeVersion,
    KnowledgePoint,
    StudentKnowledgeState,
    StudentKnowledgeStateHistory,
    LearningObjective,
    LearningEvidence,
    ParentFeedback,
    LearningPlan,
    LearningPlanItem,
    InterventionOutcome,
    Material,
    LLMRun,
    AuditLog,
    Setting,
]


def register_all() -> None:
    """Import all model modules so their tables register with the metadata."""
    from app.models import assignments, auth, learning, materials, students, system  # noqa: F401


__all__ = [
    "ALL_MODELS",
    "register_all",
    "User",
    "AuditLog",
    "Student",
    "Class",
    "Chapter",
    "StudentProgress",
    "Assignment",
    "QuestionSet",
    "Question",
    "Submission",
    "SubmissionImage",
    "Grading",
    "GradeVersion",
    "KnowledgePoint",
    "StudentKnowledgeState",
    "StudentKnowledgeStateHistory",
    "LearningObjective",
    "LearningEvidence",
    "ParentFeedback",
    "LearningPlan",
    "LearningPlanItem",
    "InterventionOutcome",
    "Material",
    "LLMRun",
    "Setting",
]