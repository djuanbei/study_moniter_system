# 学习陪伴系统（Learning Companion System）

## Product Requirements Document — PRD v4.0

---

# 1. 产品概述

## 1.1 产品名称

**Learning Companion System（学习陪伴系统）**

## 1.2 产品定位

本系统是一个面向**极小规模教学场景**的：

> **教材驱动 + 学生证据驱动 + LLM 辅助 + 持续学习更新的学习陪伴系统。**

目标用户规模：

```text
教师：1–2 人
学生：< 5 人
班级：1–2 个
同时在线学生：≤ 5 人
```

目标部署环境：

```text
CPU：2 cores
RAM：4 GB
GPU：无
```

系统必须能够在上述配置下运行。

---

# 2. 核心学习闭环

系统核心不是简单 AI 出题，而是建立：

```text
教材 / 学习资料
        ↓
教材章节
        ↓
知识点
        ↓
题库
        ↓
个性化出题
        ↓
作业 / 考试
        ↓
学生作答
        ↓
OCR / 规则 / LLM
        ↓
教师确认
        ↓
Learning Evidence
        ↓
学生知识状态
        ↓
下一轮个性化学习
```

历史纸质材料也进入同一条数据链：

```text
历史扫描试卷
        ↓
OCR / Vision / LLM
        ↓
Question
StudentAnswer
TeacherScore
TeacherAnnotation
        ↓
教师确认
        ↓
Learning Evidence
```

---

# 3. 核心产品目标

系统必须解决：

1. 教师使用什么教材？
2. 当前章节有哪些知识点？
3. 学生掌握哪些知识点？
4. 学生在哪些知识点上反复出错？
5. 历史考试成绩如何进入学生学习档案？
6. 如何根据学生真实表现生成下一轮题目？
7. 如何维护一个持续增长的题库？
8. 如何持续更新知识点体系？
9. 如何统一线上考试和纸质考试？
10. 如何把历史扫描试卷恢复成结构化学习数据？

---

# 4. 与普通 AI 出题器的区别

普通系统：

```text
教材
 ↓
LLM
 ↓
题目
```

本系统：

```text
教材
 +
知识点
 +
题库
 +
学生答案
 +
教师评分
 +
教师批注
 +
历史考试
 +
学习证据
 +
LLM
        ↓
持续更新
```

核心数据资产是：

> **学生长期学习证据。**

---

# 5. 用户角色

## 5.1 Teacher

可以：

* 管理学生
* 管理教材
* 上传资料
* 管理知识点
* 管理题库
* 生成题目
* 创建作业
* 创建考试
* 导出 PDF
* 导出 Word
* 发布在线考试
* 上传纸质考试
* AI 批改
* 确认最终成绩
* 查看学生学习档案
* 查看知识点掌握情况

## 5.2 Student

可以：

* 查看作业
* 查看考试
* 在线答题
* 提交答案
* 查看成绩
* 查看教师反馈
* 查看学习档案

## 5.3 Admin

可以：

* 系统配置
* 用户管理
* LLM 配置
* Agent 配置
* Job 管理
* Audit Log

在小规模部署中，Admin 可以由 Teacher 兼任。

---

# 6. 部署规模

系统明确定位为：

> **Single Machine / Small Classroom**

目标：

```text
Teachers       1–2
Students       < 5
Classes        1–2
Online Users   ≤ 5
```

不要求：

* 大规模 SaaS
* 高并发
* 微服务集群
* GPU 集群
* Kubernetes

---

# 7. 最低运行环境

## 7.1 CPU

```text
2 CPU cores
```

## 7.2 Memory

```text
4 GB RAM
```

## 7.3 GPU

```text
No GPU
```

## 7.4 Storage

最低：

```text
50 GB
```

推荐：

```text
100 GB+
```

因为扫描试卷、教材 PDF、图片和导出文件可能占用大量磁盘。

---

# 8. 支持操作系统

支持：

```text
Ubuntu 22.04+
Ubuntu 24.04+
macOS
```

CPU-only。

系统不得依赖：

```text
CUDA
NVIDIA
MPS
GPU driver
```

---

# 9. CPU-only AI 架构

由于没有 GPU，系统采用：

```text
FastAPI
   │
   ├── SQLite
   │
   ├── Local File Store
   │
   └── Async Job Queue
          │
          ├── CPU OCR
          ├── CPU embedding
          └── LLM API
```

LLM 可以有两种模式：

### Mode A：External LLM

推荐：

```text
System
   ↓
OpenAI-compatible API
   ↓
Remote LLM
```

本地只负责：

* prompt
* data preparation
* API request
* result validation
* database storage

### Mode B：Local Small LLM

允许运行小型 CPU 模型。

但是：

> 本地大模型不是系统运行前提。

---

# 10. CPU 使用原则

2 cores / 4 GB RAM 环境必须避免：

* 同时运行多个大型模型
* 多个 OCR 任务并行
* 大规模 embedding
* 大量 PDF 同时处理
* 内存中保存大型文档
* 将整个教材一次性送入 LLM

采用：

```text
Queue
 ↓
One Heavy Job
 ↓
Release Memory
 ↓
Next Job
```

默认：

```text
CPU workers = 1
```

可以配置为：

```text
max_workers = 1
```

必要时最多：

```text
2
```

但默认不建议。

---

# 11. 内存预算

4 GB RAM 环境下建议：

```text
OS                    ~1 GB
SQLite + FastAPI      ~0.5 GB
Frontend/browser      external
Job worker            ~0.5 GB
OCR                   ~0.5–1 GB
Other                  remainder
```

原则：

> 重型任务必须串行执行。

---

# 12. 技术栈

## Backend

```text
Python 3.11+
FastAPI
SQLAlchemy
Alembic
SQLite WAL
```

## Frontend

```text
React
TypeScript
Vite
```

## AI

```text
LLM API
OCR
Vision API（可选）
Embedding API（可选）
```

## Documents

```text
PDF
DOCX
SVG
PNG
JPEG
WebP
```

---

# 13. 数据库

使用：

> **SQLite + WAL**

原因：

* 学生数量 < 5
* 并发非常低
* 单机部署
* 数据量有限
* 安装简单
* 不需要数据库服务器

---

# 14. 文件存储

采用本地文件系统：

```text
data/
├── textbooks/
├── materials/
├── students/
├── submissions/
├── exports/
├── jobs/
└── cache/
```

---

# 15. 登录

默认教师：

```text
username = yun
```

密码：

```text
.env
PASS_WORD=
```

禁止：

* 将密码写入 Git
* 在源码中 hardcode 密码

第一次登录：

```text
Login
 ↓
Force Password Change
```

密码：

* Argon2
* 或 bcrypt

Session：

* HttpOnly Cookie
* CSRF
* Secure Cookie（HTTPS）

---

# 16. Teacher Dashboard

显示：

```text
学生数量
当前教材
当前章节
待批改
待确认 AI 批改
近期考试
薄弱知识点
最近成绩
Agent Job
```

---

# 17. Student Management

字段：

```text
student_id
name
grade
class
textbook_version
current_chapter
```

可选：

```text
parent_contact
notes
```

---

# 18. Student Learning Archive

包含：

```text
基本信息
教材
章节
作业历史
考试历史
成绩
错误
教师反馈
知识点状态
学习趋势
Learning Evidence
```

---

# 19. Knowledge Point

实体：

```text
KnowledgePoint
KnowledgePointVersion
KnowledgePointCandidate
```

字段：

```text
knowledge_point_id
subject
name
description
parent_id
chapter_id
difficulty
status
```

支持树结构。

例如：

```text
数学
└── 方程
    ├── 方程概念
    ├── 移项
    ├── 解方程
    └── 应用题
```

---

# 20. Knowledge Point Version

知识点不能直接覆盖。

采用：

```text
v1
v2
v3
...
```

历史成绩引用具体版本。

---

# 21. 学习证据

实体：

```text
LearningEvidence
```

字段：

```text
student_id
knowledge_point_id
mastery_score
confidence
evidence_count
last_assessed
trend
source
source_id
trust_level
```

---

# 22. Evidence Trust Level

```text
RAW
AI_EXTRACTED
VALIDATED
TEACHER_CONFIRMED
OFFICIAL
```

规则：

```text
AI result
   ↓
Teacher Review
   ↓
Teacher Confirm
   ↓
Learning Evidence
```

AI 不能直接生成正式学习证据。

---

# 23. 教材管理

教师可以：

* 创建教材
* 选择教材
* 上传教材
* 创建教材版本
* 查看章节
* 查看教材内容

支持：

```text
PDF
DOCX
JPG
JPEG
PNG
WebP
```

---

# 24. 扫描教材

流程：

```text
Scanned PDF
 ↓
OCR
 ↓
Layout Analysis
 ↓
Chapter Detection
 ↓
Section Detection
 ↓
Formula Detection
 ↓
Image Detection
 ↓
Table Detection
 ↓
Knowledge Point Extraction
```

原始数据必须保留。

---

# 25. Material Library

Material 类型：

```text
TEXTBOOK
TEXTBOOK_SECTION
EXERCISE_BOOK
WORKSHEET
EXAM
ANSWER_KEY
SOLUTION
TEACHER_NOTE
OTHER
```

来源：

```text
MANUAL
UPLOADED
IMPORTED
AGENT_DISCOVERED
```

---

# 26. Material Agent

教师选择教材后，Material Agent 可以周期性寻找：

* 教材资料
* 练习
* 公开试卷
* 公开答案
* 公开解析

流程：

```text
Textbook
 ↓
Material Agent
 ↓
Web Search
 ↓
Material Candidate
 ↓
Validation
 ↓
Teacher Review
 ↓
Material Library
```

默认：

```json
{
  "material_agent": {
    "enabled": true,
    "schedule": "weekly",
    "max_candidates_per_run": 50,
    "auto_import": false
  }
}
```

---

# 27. 网络资料版权

必须保存：

```text
URL
domain
retrieved_at
content_hash
source metadata
license information
```

原则：

* 网络发现 ≠ 官方资料
* 不自动重新发布第三方版权材料
* 优先保存来源和索引
* 教师确认后才进入正式材料库

---

# 28. Question

字段：

```text
question_id
subject
grade
chapter_id
knowledge_points
difficulty
question_type
prompt
answer
rubric
estimated_time
source
status
```

---

# 29. Question Version

题目版本化：

```text
Question
 ├── Version 1
 ├── Version 2
 └── Version 3
```

发布后的版本 immutable。

---

# 30. Question Generation

输入：

```text
grade
textbook
chapter
knowledge_points
student_scores
weak_points
question_count
difficulty
question_types
due_date
estimated_time
```

默认：

```text
Set A
Set B
```

---

# 31. 学科规则

## Language

重点：

* composition
* reading
* expression

作文必须有 Rubric。

## Math

重点：

* reasoning
* proof
* integrated problems
* open questions

避免大量机械计算。

## Geometry

要求图形。

优先：

```text
SVG
```

---

# 32. Question Validator

验证：

```text
Grade
Chapter
Knowledge Point
Difficulty
Question Type
Answer
Rubric
Estimated Time
Duplicate
Computation Load
Diagram
Composition Rubric
```

---

# 33. Question Bank

支持：

* 手工题
* 教材题
* 导入题
* AI 生成题
* 历史试卷题
* Agent 发现题

---

# 34. Similar Question Engine

Question Signature：

```text
knowledge_points
sub_knowledge
question_type
capability
cognitive_level
difficulty
estimated_time
solution_structure
error_types
```

支持：

```text
同知识点 + 同技能
同知识点 + 不同题型
同技能 + 不同知识点
更简单迁移题
更困难迁移题
```

不以文本相似度作为唯一标准。

---

# 35. Question Bank Incremental Update

输入：

```text
student_errors
knowledge_gaps
question_coverage
duplicate_rate
question_usage
difficulty
teacher_feedback
new_materials
```

流程：

```text
Question Bank
+
Learning Evidence
+
Knowledge Gaps
+
New Materials
 ↓
LLM
 ↓
Question Candidates
 ↓
Duplicate Detection
 ↓
Validation
 ↓
Teacher Review
 ↓
Question Bank
```

默认：

```text
auto_publish = false
```

---

# 36. 作业

状态：

```text
DRAFT
REVIEWING
PUBLISHED
OPEN
CLOSED
GRADING
GRADED
ARCHIVED
CANCELLED
```

---

# 37. 考试

支持：

```text
正式考试
模拟考试
章节考试
阶段考试
在线考试
纸质考试
```

Exam 独立于 Assignment。

---

# 38. ExamVersion

发布后 immutable。

包括：

```text
questions
QuestionVersion
order
points
total_score
instructions
time_limit
```

---

# 39. PDF Export

生成：

### Student Version

包括：

* 题目
* 图形
* 公式
* 分值
* 答题空间
* 页码

不包括：

* 答案
* AI Prompt
* 内部评分信息

### Answer Version

包括：

* 标准答案
* 解析

### Teacher Version

包括：

* Rubric
* 得分点
* 评分说明

---

# 40. DOCX Export

支持：

```text
Chinese
Formula
Image
SVG
Table
Question Number
Points
```

教师可以继续编辑 Word。

---

# 41. Online Exam

支持：

```text
单选
多选
判断
填空
简答
计算
证明
作文
开放题
```

---

# 42. Answer Input

支持：

```text
Radio
Checkbox
Text
Multiline
LaTeX
Rich Text
Image
```

---

# 43. Exam UI

显示：

```text
考试名称
剩余时间
题目导航
当前题
答题区域
上一题
下一题
提交
```

---

# 44. Server-authoritative Timer

保存：

```text
started_at
deadline
submitted_at
```

浏览器 timer 仅用于显示。

---

# 45. Autosave

默认：

```text
15 seconds
```

范围：

```text
10–30 seconds
```

机制：

```text
Change Debounce
+
Periodic Save
+
Browser Local Draft
```

服务器数据是最终数据源。

---

# 46. ExamAttempt

字段：

```text
attempt_id
exam_id
exam_version_id
student_id
started_at
last_saved_at
deadline
submitted_at
status
submit_reason
score
```

状态：

```text
NOT_STARTED
IN_PROGRESS
SUBMITTED
TIME_EXPIRED
GRADING
GRADED
```

---

# 47. Paper Exam

流程：

```text
Exam
 ↓
PDF / DOCX
 ↓
Print
 ↓
Student handwriting
 ↓
Scan / Photo
 ↓
Upload
 ↓
OCR
 ↓
AI Grading
 ↓
Teacher Confirm
```

---

# 48. Submission

接受：

```text
JPG
JPEG
PNG
WebP
PDF
```

存储：

```text
data/
students/
{student_id}/
submissions/
{exam_or_assignment_id}/
{timestamp}/
original/
metadata.json
derived/
```

Original 永远不覆盖。

---

# 49. Upload Security

检查：

```text
extension
MIME
magic bytes
file size
filename
path traversal
authentication
authorization
```

---

# 50. OCR

CPU-only。

建议：

> OCR 任务一次只处理一个文件/小批次。

流程：

```text
Upload
 ↓
Validate
 ↓
SHA256
 ↓
Store Original
 ↓
OCR
 ↓
Structured Answer
 ↓
Teacher Review
```

---

# 51. Vision

由于系统没有 GPU：

Vision 默认可以使用：

```text
Remote Vision API
```

而不是要求本地 GPU Vision Model。

支持：

* 手写答案
* 几何图形
* 教师批注
* 分数识别
* 页面布局

---

# 52. 历史考试导入

系统必须区分：

```text
Question
StudentAnswer
TeacherAnnotation
TeacherScore
```

例如：

```text
Question:
2x + 3 = 9

Student:
x = 2

Teacher:
×
0/10
```

不能只保存成一个 OCR 文本。

---

# 53. Historical Assessment

流程：

```text
Scan
 ↓
Identify Student
 ↓
Identify Exam
 ↓
Question Detection
 ↓
Student Answer Detection
 ↓
Teacher Score Detection
 ↓
Teacher Annotation Detection
 ↓
Question Matching
 ↓
Knowledge Point Matching
 ↓
Teacher Confirm
 ↓
Learning Evidence
```

---

# 54. Confidence

每个识别结果保存：

```text
answer_confidence
score_confidence
annotation_confidence
question_match_confidence
knowledge_point_confidence
```

低置信度：

```text
REVIEW_REQUIRED
```

系统禁止自动猜测。

---

# 55. AI Grading

输入：

```text
Question
Standard Answer
Rubric
Student Answer
```

输出：

```text
Suggested Score
Rubric Result
Feedback
Knowledge Point Result
Confidence
```

---

# 56. Teacher Final Authority

教师界面：

```text
Original Answer
OCR
Standard Answer
Rubric
AI Suggested Score
AI Feedback
Knowledge Point
Teacher Score
Teacher Feedback
```

操作：

```text
Accept
Edit
Manual Grade
```

最终：

```text
TEACHER_CONFIRMED
```

---

# 57. Grade Versioning

保存：

```text
previous_score
new_score
reason
changed_by
changed_at
```

---

# 58. Learning Evidence

正式学习证据只能来自：

```text
Teacher Confirmed
```

包括：

```text
Score
Knowledge Assessment
Teacher Feedback
```

---

# 59. LLM Knowledge Update

输入：

```text
Textbook
Chapter
Existing Knowledge Points
Historical Questions
New Questions
Student Errors
Teacher Feedback
```

候选：

```text
ADD
MODIFY
MERGE
SPLIT
DEPRECATE
```

流程：

```text
LLM
 ↓
Candidate
 ↓
Validator
 ↓
Teacher Review
 ↓
Version
```

---

# 60. Student Progress

系统持续维护：

```text
mastery
confidence
evidence_count
trend
```

趋势：

```text
Improving
Stable
Declining
Unknown
```

---

# 61. 个性化出题

下一次出题使用：

```text
Textbook
Chapter
Knowledge State
Weak Points
Historical Scores
Recent Errors
Teacher Feedback
Question Bank
```

系统生成针对性的练习。

---

# 62. Material Agent

周期：

```text
daily
weekly
monthly
manual
```

默认：

```text
weekly
```

由于 CPU 资源很低，Agent 任务默认：

> **串行执行，不允许多个 Material Agent Job 同时运行。**

---

# 63. Async Job

任务：

```text
MATERIAL_DISCOVERY
MATERIAL_IMPORT
OCR
VISION
KNOWLEDGE_UPDATE
QUESTION_BANK_UPDATE
QUESTION_GENERATION
SIMILAR_QUESTION_SEARCH
GRADING
PDF_EXPORT
DOCX_EXPORT
ARCHIVE_EXPORT
```

状态：

```text
QUEUED
RUNNING
SUCCEEDED
FAILED
CANCELLED
```

---

# 64. Job Resource Policy

由于：

```text
2 CPU
4 GB RAM
```

默认：

```text
max_concurrent_heavy_jobs = 1
```

即：

```text
OCR
  ↓
完成
  ↓
释放内存
  ↓
Grading
  ↓
完成
  ↓
Question Generation
```

而不是：

```text
OCR + LLM + PDF + Embedding
同时运行
```

---

# 65. LLM Trace

每次调用记录：

```text
agent
prompt_hash
input_json
output_json
model
model_version
tokens
timestamp
latency
job_id
```

---

# 66. Database Tables

```text
users
classes
students

textbooks
textbook_versions
chapters
materials
material_versions
material_pages
material_chunks
material_sources

knowledge_points
knowledge_point_versions
knowledge_point_candidates

questions
question_versions
question_candidates
question_sets

question_embeddings
question_signatures

assignments
assignment_versions

exams
exam_versions
exam_questions
exam_attempts

submissions
submission_files
student_answers
answer_versions

teacher_annotations
teacher_scores

gradings
grading_versions

historical_assessments
historical_assessment_questions

student_progress
student_progress_history
learning_evidence

llm_runs
jobs

material_agent_runs
knowledge_update_runs
question_bank_update_runs

import_reviews
import_review_items

exports
audit_logs
settings
```

---

# 67. API

```text
/auth

/students
/classes

/textbooks
/materials
/material-agent

/knowledge-points

/questions
/question-bank
/similar-questions

/assignments

/exams
/exam-attempts

/submissions
/gradings

/student-progress

/jobs

/exports

/audit
```

---

# 68. 页面

## Teacher

```text
/dashboard

/students
/students/:id

/classes

/textbooks
/materials

/knowledge-points

/questions
/question-bank
/similar-questions

/assignments

/exams
/exams/:id/editor

/submissions
/grading

/learning-analysis

/exports

/settings
/audit
```

## Student

```text
/dashboard
/assignments
/exams
/exams/:id
/exams/:id/attempt
/grades
/learning-archive
```

---

# 69. 性能要求

由于只有：

```text
< 5 students
2 CPU
4 GB RAM
```

目标不是高并发，而是稳定运行。

要求：

```text
普通 API P95 < 500 ms
登录 < 1 s
在线考试 ≤ 5 users
```

AI/OCR 等任务不计入普通 API latency。

---

# 70. CPU 性能策略

必须：

1. 异步处理 OCR。
2. 异步处理 LLM。
3. 大 PDF 分页处理。
4. 不一次性加载整个教材。
5. 使用 streaming/chunk。
6. OCR 完成后及时释放内存。
7. embedding 批量但小 batch。
8. LLM 使用远程 API 时不占本地 CPU 大量资源。
9. 大型任务串行。
10. 缓存已有 OCR 和 embedding。

---

# 71. Cache

缓存：

```text
OCR result
PDF extraction
Embedding
Question signature
Material hash
LLM response（允许时）
```

如果输入 SHA256 没有变化，不重复执行昂贵任务。

---

# 72. 安全

必须：

```text
Argon2 / bcrypt
HttpOnly Cookie
CSRF
RBAC
MIME Validation
Magic Bytes
File Size Limit
Path Traversal Protection
Authenticated File Access
Audit Log
Student Data Isolation
```

---

# 73. 隐私

LLM 外部调用必须可配置：

```text
provider
model
data retention
external transmission
```

敏感学生数据可以：

```text
redact
pseudonymize
```

再发送到外部 LLM。

---

# 74. Copyright

Material Agent：

* 保存 URL
* 保存 domain
* 保存 hash
* 保存 retrieved_at
* 保存 license 信息
* 不自动公开发布第三方材料

教师上传材料的版权责任由教师/机构承担。

---

# 75. 配置

`.env`：

```text
PASS_WORD=
DATABASE_URL=
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
```

`configure.json`：

```json
{
  "material_agent": {
    "enabled": true,
    "schedule": "weekly",
    "max_candidates_per_run": 50,
    "auto_import": false
  },
  "knowledge_base": {
    "incremental_update": {
      "enabled": true,
      "schedule": "weekly",
      "batch_size": 20,
      "auto_publish": false
    }
  },
  "question_bank": {
    "incremental_update": {
      "enabled": true,
      "schedule": "weekly",
      "questions_per_batch": 10,
      "auto_publish": false
    }
  },
  "exam": {
    "allow_retake": false,
    "autosave_interval_seconds": 15
  },
  "jobs": {
    "max_concurrent_heavy_jobs": 1
  },
  "llm": {
    "provider": "openai-compatible",
    "remote": true
  }
}
```

---

# 76. install.sh

安装脚本：

```text
install.sh
```

必须：

* 幂等
* 创建 Python venv
* 安装依赖
* 初始化 SQLite
* 执行 migration
* 创建 data/
* 创建默认教师
* 安装 frontend
* 构建 frontend
* 启动 backend
* 启动 worker

禁止：

* 覆盖 `.env`
* 覆盖 `configure.json`

---

# 77. 测试

## Unit Tests

```text
Question
KnowledgePoint
QuestionVersion
StudentProgress
Exam
ExamVersion
Score
LearningEvidence
```

## OCR Tests

```text
Printed Text
Scanned Text
Handwriting
Formula
Teacher Score
Teacher Annotation
Geometry
```

## Integration

```text
教材
 ↓
知识点
 ↓
题库
 ↓
考试
 ↓
学生作答
 ↓
AI 批改
 ↓
教师确认
 ↓
学习档案
```

## Historical Exam

```text
扫描试卷
 ↓
OCR
 ↓
Question Matching
 ↓
StudentAnswer
 ↓
TeacherScore
 ↓
TeacherAnnotation
 ↓
Teacher Confirm
 ↓
LearningEvidence
```

---

# 78. MVP Phase 1

必须首先完成：

```text
Login
 ↓
Student
 ↓
Textbook
 ↓
Material Upload
 ↓
OCR
 ↓
Chapter
 ↓
Knowledge Point
 ↓
Question Bank
 ↓
AI Question Generation
 ↓
Assignment
 ↓
Exam
 ↓
PDF
 ↓
DOCX
 ↓
Online Exam
 ↓
Scan Upload
 ↓
AI Grading
 ↓
Teacher Confirm
 ↓
Student Archive
```

---

# 79. Phase 2

增加：

```text
Material Discovery Agent
Knowledge Incremental Update
Question Bank Incremental Update
Similar Question Engine
Historical Exam Import
Teacher Annotation Recognition
```

---

# 80. Phase 3

增加：

```text
Automatic Knowledge Gap Discovery
Automatic Question Bank Maintenance
Long-term Learning Path
Cross-textbook Knowledge Mapping
```

---

# 81. 核心不变量

### 1

Original submission immutable。

### 2

Published ExamVersion immutable。

### 3

Published QuestionVersion immutable。

### 4

Historical assessment immutable。

### 5

AI grading ≠ final grade。

### 6

AI extraction ≠ learning evidence。

### 7

Teacher confirmation 是正式证据边界。

### 8

Internet material 默认不是 official material。

### 9

Knowledge Base 必须 versioned。

### 10

Question Bank 支持 incremental update。

### 11

重要操作必须 audit。

### 12

Student data 必须隔离。

### 13

Heavy AI/OCR jobs 默认串行。

### 14

系统在无 GPU 环境下必须可以完整运行。

### 15

系统不得依赖本地大型 LLM 才能完成核心业务流程。

---

# 82. 最终验收标准

系统在以下环境：

```text
Ubuntu / macOS
2 CPU cores
4 GB RAM
No GPU
```

且：

```text
Students < 5
```

必须能够完成：

```text
教师登录
   ↓
选择教材
   ↓
导入教材
   ↓
OCR
   ↓
章节识别
   ↓
知识点
   ↓
题库
   ↓
LLM 出题
   ↓
创建考试
   ↓
PDF / DOCX
   ↓
学生在线考试
   ↓
或扫描纸质考试
   ↓
OCR
   ↓
AI 批改
   ↓
教师确认
   ↓
Learning Evidence
   ↓
学生学习档案
   ↓
下一轮个性化出题
```

---

# 83. 最终产品架构

```text
                 Learning Companion
                         │
        ┌────────────────┼────────────────┐
        │                │                │
       教材             题库             学生
        │                │                │
        │                │                │
        └────────┬───────┴───────┬────────┘
                 │               │
               考试            学习证据
                 │               │
                 └───────┬───────┘
                         │
                        LLM
                         │
              ┌──────────┴──────────┐
              │                     │
          知识库更新             题库更新
              │                     │
              └──────────┬──────────┘
                         │
                    个性化学习
```

最终定位：

> **一个运行在普通 2-core / 4GB、无 GPU 环境上的小规模 AI Learning Companion System，以教材、学生答案、教师评分和学习证据为核心数据资产，通过外部 LLM/CPU AI 能力实现持续的知识库、题库和个性化学习更新。**
