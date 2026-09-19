# 学习陪伴系统 (Learning Companion System) — System Specification

## 1. Overview

A web-based learning companion system that helps teachers generate assignments, grade student submissions, and track each student's academic progress through an LLM-assisted workflow.

---

## 2. Roles & Access Control

| Role   | Scope                                                                                  |
| ------ | -------------------------------------------------------------------------------------- |
| Teacher | Full administrative permissions over classes, students, assignments, grading, configuration. |
| Student | Access limited to own assignments, submissions, feedback, and grades.                  |

### Default Account
- Username: `yun`
- Password: configured via `PASS_WORD` in `.env` (no default value committed).
- The default teacher must change the password on first login.

---

## 3. User Interface

### Visual Style
- Simple, fresh, and consistent.
- 网站采用中文 (UI language is Chinese for all user-facing labels, messages, and prompts).

### Pages
1. Login
2. Teacher Dashboard
3. Student Management
4. Class Management
5. Question Generation Wizard
6. Assignment Management
7. Submission Grading
8. Student Archive
9. Account Management
10. System Settings

---

## 4. Account Management

The account manager supports: create, disable, reset password, change password, role assignment.

---

## 5. Student Profile

### Required Information
- Name
- Grade
- Class
- Textbook version
- Current chapter
- Weak points
- Strengths
- Score history
- Notes
- Parent contact (optional)

### Grade & Chapter Inference
The system infers current grade and chapter from current date, academic calendar, textbook version, and student profile if not manually provided.

### Academic Calendar
- Configured in `configure.json`.
- Default school year start month: September (unless configured otherwise).

---

## 6. Question Generation

### Generation Modes
- LLM generates **2 question sets (A/B)** per request for teacher selection.
- Default frequency: **weekly**.
- Supported frequencies: **daily**, **weekly**, **custom**.

### Generation Inputs
- Student grade, current chapter, past scores, weak points.
- Teacher requirements: question count, difficulty, knowledge points, question types, due date, estimated time, calculator allowance.

### Question Metadata (per question)
- Prompt
- Rubric
- Answer key
- Knowledge points
- Difficulty
- Estimated time

### Question Type Rules

| Subject  | Allowed Types                                                      | Constraints                                                       |
| -------- | ------------------------------------------------------------------ | ----------------------------------------------------------------- |
| Language | Composition, reading comprehension, expression training            | —                                                                 |
| Math     | Thinking questions, week-long open thinking problems               | Must avoid computation-intensive questions. Geometry questions must include diagrams (SVG preferred, Mermaid optional). |

### Output Format
- LLM output must be structured JSON.

---

## 7. LLM & Agent Framework

### Framework
- LangChain agent framework.

### Agent Workflow
1. Curriculum planning
2. Question planning
3. Question generation
4. Diagram generation
5. Validation
6. Grading
7. Archive summary

### Agent Tools
- SQLite query
- Textbook chapter retrieval
- OCR / vision
- SVG generation
- Rubric checking
- Duplicate detection

### Validator Agent
Checks: grade suitability, chapter match, calculation load, geometry diagram presence, composition rubric, week-long thinking suitability.

### Run Traceability
Each LLM run records: agent, prompt hash, input JSON, output JSON, tokens, timestamp.

---

## 8. Assignment & Submission Management

### Teacher Side
- View, edit, mix, select, and assign generated question sets.

### Student Submissions
- Accepts images, PDF, and optional text answers.
- Accepted image types: **JPG**, **JPEG**, **PNG**, **WebP**, **PDF**.

### Submission Archive
- Path format: `data/students/{student_id}/submissions/{assignment_id}/{timestamp}/`
- Original submission images are **immutable**.
- Metadata: filename, size, SHA256, upload time, question number, OCR text.

### Teacher Review
- Submission images, OCR text, LLM grading suggestion, final score, feedback, knowledge point mastery.

### Grading Policy
- LLM grading is **advisory only**.
- Final score and feedback are confirmed by the teacher.
- Confirmed grades and feedback are written back to the student archive for future question generation.

---

## 9. Student Archive

Supports per-student:
- Assignment history
- Score trends
- Knowledge point reports
- PDF export
- CSV export
- Image ZIP export

---

## 10. Data Storage

### Database
- **SQLite** in **WAL mode**.

### Tables
`users`, `students`, `classes`, `chapters`, `student_progress`, `assignments`, `question_sets`, `questions`, `submissions`, `submission_images`, `gradings`, `llm_runs`, `audit_logs`, `settings`.

### File Storage
- Images are stored on the filesystem; SQLite stores paths and hashes only.

### Secrets & Configuration Files
| File                  | Purpose                                                       | Git Status            |
| --------------------- | ------------------------------------------------------------- | --------------------- |
| `.env`                | LLM API keys and secrets                                      | Excluded from git     |
| `.env.example`        | Template                                                      | Tracked               |
| `configure.json`      | Single source of business configuration (app, academic, generation, llm, uploads) | Excluded from git |
| `configure.json.example` | Template                                                  | Tracked               |

### `.gitignore`
- `.env`, `configure.json`, `data/`, `logs/`, `uploads/`.

---

## 11. Installation

### `install.sh` Guarantees
- Self-contained and **idempotent** (repeated runs must not destroy existing data).
- Installs required libraries when missing.
- Creates directories and a virtual environment, installs dependencies, builds the frontend, runs migrations, and creates the default teacher if missing.
- Does **not** overwrite existing `.env` or `configure.json`.
- If `PASS_WORD` is missing from `.env`, prompts the operator interactively and writes it to `.env` before creating the default teacher.

### Supported Operating Systems
- Ubuntu, Debian, CentOS, macOS.

### Backup
- Includes the SQLite database and the image data directory.

---

## 12. Security

| Concern        | Implementation                              |
| -------------- | ------------------------------------------- |
| Passwords      | Argon2 or bcrypt hashing                    |
| Sessions       | HttpOnly cookies                            |
| CSRF           | CSRF protection enabled                     |
| Authorization  | Role-based access control (RBAC)            |
| Uploads        | Type, size, and path validation             |
| Image access   | Requires authentication                    |

### Audit Log
Records: login, question generation, grading, export, deletion, account changes.

---

## 13. Non-functional Requirements

| Requirement        | Target                                                       |
| ------------------ | ------------------------------------------------------------ |
| First screen load  | Under 2 seconds                                              |
| Scale              | 1 teacher, 100 students, 2 question sets per student per week |
| LLM failure       | Preserves draft and supports retry                           |
| Image upload       | Supports retry                                               |

---

## 14. Acceptance Criteria

1. A fresh machine can install and start with `./install.sh`.
2. Repeated `./install.sh` does not destroy existing data.
3. Default teacher `yun` can log in using the `PASS_WORD` from `.env` and is forced to change password.
4. Teacher can create students with grade, textbook, and chapter.
5. System can infer chapter from current time and configuration.
6. Teacher can generate A/B question sets with configured count, difficulty, and knowledge points.
7. Geometry questions include SVG diagrams.
8. Math questions avoid heavy computation.
9. Student can upload multiple image answers.
10. Images are archived per student, assignment, and time with SHA256.
11. Teacher can grade and write feedback.
12. Student can view own grades and feedback.
13. `.env` and `configure.json` are not in git.

---

## 15. Technical Stack

### Backend
- Python **FastAPI**
- **SQLAlchemy** ORM
- **Alembic** migrations
- **SQLite** database

### Frontend (choose one)
- **React + Vite**, or
- **HTMX + Jinja**

### Image Processing
- **Pillow**
- Optional **pytesseract** (OCR)
- Optional vision model

### Diagrams
- **SVG** preferred
- **Mermaid** optional

### Deployment
- **systemd** or **Docker Compose**