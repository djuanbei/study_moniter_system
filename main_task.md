# 学习陪伴系统（Learning Companion System）

## 完整产品需求文档 PRD v6.0

---

# 1. 产品概述

## 1.1 产品名称

**Learning Companion System（学习陪伴系统）**

## 1.2 产品定位

一个面向小规模教学场景的：

> **教材驱动、AI 协助出题、AI 协助批改、学生知识状态驱动、教师确认、持续学习闭环系统。**

系统核心不是单纯：

* AI 出题
* AI 批改
* 题库
* 在线考试
* OCR

而是把这些能力连接起来：

```text
教材
 ↓
知识点
 ↓
学生知识状态
 ↓
学习目标
 ↓
AI 协助出题
 ↓
学生作答
 ↓
AI 协助批改
 ↓
教师确认
 ↓
学习证据
 ↓
学生知识状态更新
 ↓
下一轮 AI 出题
```

---

# 2. 产品核心目标

系统需要解决两个核心问题：

## 问题 A：如何更好地出题？

根据：

* 教材
* 当前章节
* 知识点
* 学生掌握情况
* 学生错误类型
* 历史题目
* 学习目标

由 AI **辅助教师生成合适的题目**。

---

## 问题 B：如何更高效地批改？

根据：

* 题目
* 标准答案
* Rubric
* 学生答案
* OCR / Vision 结果

由 AI **辅助教师批改**。

---

# 3. AI 的定位

AI 是：

> **Teacher Assistant，而不是 Teacher Replacement。**

AI 可以：

```text
生成
分析
识别
建议
批改
归类
推荐
```

但不能默认：

```text
AI = 最终教师判断
```

核心原则：

```text
AI Suggestion
      ↓
Teacher Review
      ↓
Official Result
```

---

# 4. 核心学习闭环

系统完整闭环：

```text
教材 / 课程
      ↓
知识体系
      ↓
学生知识状态
      ↓
学习目标
      ↓
AI 协助出题
      ↓
作业 / 练习 / 考试
      ↓
学生作答
      ↓
OCR / Vision
      ↓
AI 协助批改
      ↓
教师确认
      ↓
Learning Evidence
      ↓
学生知识状态更新
      ↓
下一轮学习目标
      ↓
AI 协助出题
```

最终形成：

> **AI 出题 → 学生学习 → AI 批改 → 教师确认 → 状态更新 → AI 再出题**

---

# 5. 产品核心数据闭环

系统核心不是“题目”，而是：

```text
Student
   ↓
Student Knowledge State
   ↓
Learning Objective
   ↓
Learning Plan
   ↓
Question
   ↓
Student Answer
   ↓
AI Grading
   ↓
Teacher Confirmation
   ↓
Learning Evidence
   ↓
Student Knowledge State
```

---

# 6. 部署规模

目标规模：

```text
教师：1–2
学生：< 5
班级：1–2
在线用户：≤ 5
```

部署：

```text
Single Machine
```

不是大型 SaaS。

---

# 7. 硬件约束

最低目标：

```text
CPU：2 cores
RAM：4 GB
GPU：None
```

系统核心功能不得依赖 GPU。

---

# 8. CPU-only 架构

```text
Browser
   ↓
React
   ↓
FastAPI
   ↓
SQLite
   ↓
Job Queue
   ↓
AI / OCR / Vision
```

AI 优先使用：

```text
External OpenAI-compatible API
```

本地不要求运行大型 LLM。

---

# 9. 技术栈

## Backend

```text
Python
FastAPI
SQLAlchemy
Alembic
SQLite
```

## Frontend

```text
React
TypeScript
Vite
```

## AI

```text
LLM
Vision
OCR
Embedding
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

# 10. 数据库

使用：

```text
SQLite + WAL
```

原因：

* 小规模
* 单机
* 低并发
* 易部署
* 4GB RAM
* 不需要 PostgreSQL

大型文件不得直接存入 SQLite BLOB。

---

# 11. 用户角色

```text
ADMIN
TEACHER
STUDENT
```

小型部署允许：

```text
ADMIN = TEACHER
```

---

# 12. 登录

默认教师：

```text
username = yun
```

密码：

```text
.env

PASS_WORD=
```

密码不得提交 Git。

首次登录：

```text
Login
 ↓
Force Password Change
```

使用：

```text
Argon2 / bcrypt
HttpOnly Cookie
CSRF
RBAC
```

---

# 13. Teacher 页面

```text
Dashboard

Students
Classes
Student Archive

Textbooks
Materials

Knowledge Points
Knowledge Graph

AI Question Generation
Question Bank
Question Sets
Similar Questions

Learning Diagnosis
Learning Plans
Learning Sessions

Assignments
Exams
Exam Editor

Submissions
AI Grading
Teacher Review

Learning Analysis

Material Agent
Knowledge Update
Question Bank Update

PDF Export
DOCX Export

Settings
Audit
```

---

# 14. Student 页面

```text
Dashboard

Today's Learning
Learning Plan

Assignments
Exams
Online Exam

Answer Submission

Grades
AI/Teacher Feedback

Knowledge Progress
Learning Archive
```

---

# 15. Student Profile

字段：

```text
student_id
name
grade
class
textbook_version
current_chapter

strengths
weak_points
notes
score_history
```

可选：

```text
parent_contact
```

---

# 16. 教材体系

```text
Curriculum
    ↓
Textbook
    ↓
TextbookVersion
    ↓
Chapter
    ↓
Section
    ↓
KnowledgePoint
```

---

# 17. 教材管理

教师可以：

```text
选择教材
上传教材
创建教材版本
管理章节
查看教材
```

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

# 18. 扫描教材 OCR

流程：

```text
Scanned PDF
 ↓
Page Extraction
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

保存：

```text
Original
Page Image
OCR
Structured Content
Page Number
```

---

# 19. Material

类型：

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

# 20. Material Agent

Material Agent 可以定期发现：

```text
教材相关材料
公开练习
公开试卷
公开答案
公开解析
```

流程：

```text
Textbook
 ↓
Material Agent
 ↓
Search
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

```text
auto_import = false
```

---

# 21. Internet Material

保存：

```text
URL
domain
retrieved_at
content_hash
source_metadata
license
```

网络发现的材料默认：

```text
NOT_OFFICIAL
```

教师确认之后才能进入正式材料体系。

---

# 22. Knowledge Point

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

---

# 23. 知识点示例

```text
数学
└── 一元一次方程
    ├── 方程概念
    ├── 等式性质
    ├── 移项
    ├── 解方程
    └── 应用题
```

---

# 24. Knowledge Point Version

知识点必须版本化：

```text
v1
v2
v3
...
```

历史学习证据引用具体版本。

---

# 25. 学生知识状态

核心实体：

```text
StudentKnowledgeState
```

字段：

```text
student_id
knowledge_point_id
mastery_score
confidence
evidence_count
last_assessed
last_practiced
trend
decay_risk
status
```

例如：

```text
一元一次方程
mastery = 0.72
confidence = 0.88
trend = improving

移项
mastery = 0.61

应用题建模
mastery = 0.34
trend = declining
```

---

# 26. Knowledge State History

状态不能覆盖。

保存：

```text
StudentKnowledgeStateHistory
```

例如：

```text
01-01    0.35
01-10    0.47
01-20    0.58
02-01    0.71
```

---

# 27. Learning Objective

定义学习目标：

```text
LearningObjective
```

例如：

```text
Knowledge:
一元一次方程应用题

Current:
0.34

Target:
0.80
```

每一个重要学习任务都应该能够追溯到一个 Learning Objective。

---

# 28. Learning Diagnosis

系统根据：

```text
Student Knowledge State
+
Learning Evidence
+
Error Patterns
+
Curriculum
+
Teacher Feedback
```

生成：

```text
Diagnosis
```

例如：

```text
Priority 1:
应用题建模

Priority 2:
移项

Priority 3:
综合迁移
```

---

# 29. Learning Planner

核心 Agent：

```text
Learning Planner Agent
```

输入：

```text
StudentKnowledgeState
LearningEvidence
ErrorPatterns
LearningObjectives
Textbook
QuestionBank
TeacherConstraints
```

输出：

```text
LearningPlan
```

---

# 30. Learning Plan

例如：

```text
学生：
S001

目标：
掌握一元一次方程应用题

Current:
0.34

Target:
0.80
```

计划：

```text
Day 1:
概念复习

Day 2:
简单应用题

Day 3:
变式题

Day 4:
综合题

Day 5:
Mini Test
```

---

# 31. Learning Intervention

支持：

```text
EXPLANATION
EXAMPLE
PRACTICE
REVIEW
QUIZ
EXAM
REFLECTION
```

一个典型干预：

```text
Diagnosis
 ↓
Concept Explanation
 ↓
Simple Practice
 ↓
Variation
 ↓
Assessment
```

---

# 32. AI 核心能力一：协助出题

AI Question Generation 是系统的一级能力。

目标：

> 根据教材、知识点、学习目标和学生状态，帮助教师快速生成合适题目。

---

# 33. AI 出题输入

```text
学科
年级
教材
章节
知识点
学生知识状态
薄弱知识点
错误类型
学习目标
题目数量
难度
题型
预计答题时间
是否需要图形
是否需要证明
是否需要开放题
历史题目
```

---

# 34. AI 出题输出

每道题：

```text
question
answer
solution
rubric
knowledge_points
difficulty
question_type
estimated_time
error_patterns
```

例如：

```text
题目：
……

知识点：
移项

难度：
0.55

题型：
应用题

预计时间：
5 min

标准答案：
……

评分标准：
……
```

---

# 35. AI 出题不是随机生成

系统应该从：

```text
Student State
```

开始。

例如：

```text
应用题建模
mastery = 0.34
```

AI 不应该简单生成：

```text
10 道应用题
```

而应该生成具有学习目的的题组：

```text
2 道概念题
3 道简单建模题
2 道变式题
1 道综合题
```

---

# 36. AI 出题流程

```text
Learning Objective
       ↓
Student Knowledge State
       ↓
Question Planning
       ↓
LLM
       ↓
Question Candidates
       ↓
Validation
       ↓
Duplicate Detection
       ↓
Teacher Review
       ↓
QuestionVersion
       ↓
Question Bank
```

---

# 37. Question Validator

检查：

```text
年级是否匹配
章节是否匹配
知识点是否正确
答案是否存在
答案是否一致
难度是否合理
题型是否正确
预计时间是否合理
是否重复
是否超出教材
是否需要图形
是否需要 Rubric
```

数学题额外检查：

```text
计算量
答案可验证性
推理要求
证明完整性
```

---

# 38. 教师出题审核

教师可以：

```text
接受
修改题干
修改答案
修改知识点
修改难度
修改评分标准
重新生成
删除
加入题库
```

只有教师发布后成为正式题目。

---

# 39. Question Bank

Question：

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

# 40. Question Version

```text
Question
 ├── Version 1
 ├── Version 2
 └── Version 3
```

已发布版本：

```text
IMMUTABLE
```

---

# 41. Similar Question Engine

每道题生成：

```text
QuestionSignature
```

包括：

```text
knowledge_points
sub_knowledge
question_type
capability
cognitive_level
difficulty
solution_structure
error_types
```

搜索：

```text
同知识点 + 同技能
同知识点 + 不同题型
同技能 + 不同知识点
更简单
更困难
迁移题
```

目标：

> 找到“学习功能相同”的题，而不是只找文字相似题。

---

# 42. AI 核心能力二：协助批改

AI Grading 是系统第二个一级 AI 能力。

目标：

> **降低教师批改工作量，同时保留教师最终判断权。**

---

# 43. AI 批改输入

```text
Question
Standard Answer
Rubric
Student Answer
```

如果是纸质答案：

```text
Original Image
+
OCR Result
+
Vision Result
```

---

# 44. AI 批改输出

```text
suggested_score
rubric_results
correctness
error_type
knowledge_points
feedback
confidence
```

---

# 45. AI 批改示例

题目：

```text
2x + 3 = 9
```

学生：

```text
2x = 9 + 3
x = 6
```

AI：

```text
suggested_score = 0
error_type = SIGN_ERROR
knowledge_point = 移项
confidence = 0.96
```

建议反馈：

```text
移项时符号发生错误。
```

---

# 46. AI 批改流程

```text
Student Answer
      ↓
OCR / Vision
      ↓
Structured Answer
      ↓
Question Matching
      ↓
AI Grading
      ↓
Score Suggestion
      ↓
Error Analysis
      ↓
Knowledge Point Analysis
      ↓
Teacher Review
```

---

# 47. 教师批改界面

同时显示：

```text
原始答案
OCR
标准答案
Rubric
AI 建议分数
AI 错误类型
AI 知识点
AI Feedback
Confidence
```

操作：

```text
Accept AI
Edit
Manual Grade
```

---

# 48. AI 不能直接成为正式成绩

必须：

```text
AI Suggestion
       ↓
Teacher Confirmation
       ↓
Official Grade
```

AI 不能直接修改：

```text
正式成绩
正式学习证据
学生知识状态
```

---

# 49. Grade Versioning

保存：

```text
previous_score
new_score
reason
changed_by
changed_at
```

---

# 50. OCR / Vision

支持：

```text
JPG
JPEG
PNG
WebP
PDF
```

流程：

```text
Upload
 ↓
Validate
 ↓
Immutable Storage
 ↓
SHA256
 ↓
OCR
 ↓
Vision
 ↓
Structured Answer
 ↓
AI Grading
```

---

# 51. 原始文件不可修改

必须：

```text
Original = Immutable
```

派生：

```text
OCR
Vision
Grading
Annotation
```

均不得覆盖原始文件。

---

# 52. OCR Confidence

保存：

```text
answer_confidence
score_confidence
annotation_confidence
question_match_confidence
```

低置信度：

```text
REVIEW_REQUIRED
```

教师可以：

```text
重新 OCR
手工输入
跳过 OCR
```

---

# 53. Teacher Annotation

支持识别：

```text
圈错
批注
扣分
得分
文字反馈
```

最终统一：

```text
TeacherAnnotation
TeacherScore
```

---

# 54. Historical Exam Import

支持：

```text
历史试卷
历史作业
扫描试卷
```

流程：

```text
Scan
 ↓
Question Detection
 ↓
Student Answer
 ↓
Teacher Score
 ↓
Teacher Annotation
 ↓
Question Matching
 ↓
Knowledge Point Matching
 ↓
Teacher Confirmation
 ↓
Learning Evidence
```

---

# 55. Learning Evidence

核心实体：

```text
LearningEvidence
```

字段：

```text
evidence_id
student_id
knowledge_point_id
question_id
source_type
source_id
correct
score
difficulty
error_type
teacher_feedback
confidence
trust_level
created_at
```

来源：

```text
HOMEWORK
QUIZ
EXAM
ONLINE_EXAM
PAPER_EXAM
HISTORICAL_EXAM
PRACTICE
TEACHER_OBSERVATION
```

---

# 56. Evidence Trust Level

```text
RAW
AI_EXTRACTED
VALIDATED
TEACHER_CONFIRMED
OFFICIAL
```

规则：

> 只有 Teacher Confirmed 数据才能进入正式学习状态。

---

# 57. Error Pattern

支持：

```text
SIGN_ERROR
CONCEPT_MISUNDERSTANDING
FORMULA_ERROR
CALCULATION_ERROR
READING_ERROR
REASONING_GAP
PROOF_GAP
DIAGRAM_ERROR
KNOWLEDGE_CONFUSION
CARELESS_ERROR
MODELING_ERROR
```

---

# 58. 学生状态更新

```text
Old Knowledge State
+
New Learning Evidence
 ↓
State Update Engine
 ↓
New Knowledge State
```

考虑：

```text
difficulty
recency
correctness
error_type
teacher_confirmation
historical_performance
```

不是简单：

```text
正确率 = mastery
```

---

# 59. Knowledge Decay

考虑遗忘：

```text
Last Evidence:
120 days ago

Mastery:
0.82

Effective Mastery:
下降
```

因此自动安排：

```text
Review
```

---

# 60. Spaced Review

初始策略：

```text
Weak:
1 day

Medium:
3 days

Good:
7 days

Strong:
14 days

Stable:
30 days
```

---

# 61. AI 出题与 AI 批改的完整闭环

核心：

```text
Student Knowledge State
        ↓
Learning Objective
        ↓
AI Question Planning
        ↓
AI Question Generation
        ↓
Teacher Review
        ↓
Assignment / Exam
        ↓
Student Answer
        ↓
OCR / Vision
        ↓
AI Grading
        ↓
Teacher Confirmation
        ↓
Learning Evidence
        ↓
Knowledge State Update
        ↓
New Diagnosis
        ↓
New Learning Objective
        ↓
AI Question Generation
```

---

# 62. 典型学生场景

初始状态：

```text
应用题建模 = 0.31
```

系统诊断：

```text
建模能力不足
```

AI 出题：

```text
2 道简单建模题
3 道普通应用题
2 道变式题
1 道综合题
```

学生作答。

AI 批改：

```text
5 / 8 正确

3 个错误：

2 × MODELING_ERROR
1 × CALCULATION_ERROR
```

教师确认。

状态更新：

```text
0.31 → 0.45
```

三天后复习。

AI 再出题：

```text
2 道迁移题
```

AI 批改：

```text
2 / 2 正确
```

状态：

```text
0.45 → 0.58
```

系统继续：

```text
综合题
```

这就是：

```text
出题
 ↓
作答
 ↓
批改
 ↓
证据
 ↓
状态
 ↓
再出题
```

---

# 63. AI Question Bank Incremental Update

输入：

```text
学生错误
知识缺口
题目覆盖率
题目重复率
题目使用次数
难度
教师反馈
教材变化
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

---

# 64. AI Knowledge Base Incremental Update

输入：

```text
教材
已有知识点
历史题目
新题目
学生错误
教师反馈
```

AI 可以建议：

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
KnowledgePointCandidate
 ↓
Validator
 ↓
Teacher Review
 ↓
KnowledgePointVersion
```

---

# 65. AI Agent 划分

系统主要 AI Agent：

```text
Material Agent

Question Planning Agent

Question Generation Agent

Question Validation Agent

Grading Agent

Error Analysis Agent

Diagnosis Agent

Learning Planner Agent

Knowledge Update Agent

Question Bank Update Agent
```

---

# 66. Agent 权限原则

Agent 默认：

```text
READ
ANALYZE
SUGGEST
GENERATE
```

不允许直接修改：

```text
Official Grade
Official Evidence
Published Exam
Published QuestionVersion
Student Knowledge State
```

除非经过明确的系统规则和教师确认。

---

# 67. Agent Tools

可以访问：

```text
SQLite
Textbook Retrieval
Material Retrieval
OCR
Vision
Question Bank
Question Signature
Student Knowledge State
Learning Evidence
Rubric
PDF
SVG
```

---

# 68. LLM Traceability

每次调用保存：

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

# 69. Assignment

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

# 70. Exam

支持：

```text
Formal Exam
Mock Exam
Chapter Test
Stage Test
Online Exam
Paper Exam
```

---

# 71. ExamVersion

发布后：

```text
IMMUTABLE
```

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

# 72. Online Exam

支持：

```text
MCQ
Multi-select
True/False
Fill-in
Short Answer
Calculation
Proof
Composition
Open Question
```

---

# 73. Online Answer

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

# 74. Server-authoritative Timer

保存：

```text
started_at
deadline
submitted_at
```

浏览器 Timer 仅显示。

服务器决定：

```text
是否超时
```

---

# 75. Autosave

默认：

```text
15 seconds
```

范围：

```text
10–30 seconds
```

使用：

```text
Debounce
+
Periodic Save
+
Browser Draft
```

---

# 76. ExamAttempt

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

# 77. Paper Exam

```text
Exam
 ↓
PDF / DOCX
 ↓
Print
 ↓
Student Handwriting
 ↓
Scan / Photo
 ↓
OCR / Vision
 ↓
AI Grading
 ↓
Teacher Confirm
```

---

# 78. PDF 导出

教师创建试卷后可以生成：

```text
Student Version
Answer Version
Rubric Version
```

学生版不能包含：

```text
答案
AI Prompt
内部评分信息
```

支持：

```text
中文
公式
图片
SVG
表格
题号
分值
页眉
页脚
页码
```

---

# 79. DOCX 导出

支持：

```text
中文
公式
图片
SVG 转换
表格
题号
分值
```

教师可以继续手工修改 Word。

---

# 80. Student Learning Archive

保存：

```text
Assignment History
Exam History
Score Trends
Knowledge Trends
Mistakes
Error Patterns
Teacher Feedback
Learning Plans
Learning Sessions
Learning Evidence
```

支持：

```text
PDF
CSV
Image ZIP
```

---

# 81. 数据库完整表

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

student_knowledge_states
student_knowledge_state_history

learning_objectives
learning_plans
learning_plan_items
learning_sessions
learning_interventions

learning_evidence

error_patterns
student_error_evidence
teacher_feedback

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

# 82. 文件存储

```text
data/
├── textbooks/
├── materials/
├── students/
│   └── {student_id}/
│       └── submissions/
│           └── {exam_or_assignment_id}/
│               └── {timestamp}/
│                   ├── original/
│                   ├── derived/
│                   └── metadata.json
├── exports/
└── cache/
```

原始文件 immutable。

---

# 83. Async Job

类型：

```text
MATERIAL_DISCOVERY
MATERIAL_IMPORT
OCR
VISION
KNOWLEDGE_UPDATE
QUESTION_BANK_UPDATE
QUESTION_GENERATION
QUESTION_VALIDATION
SIMILAR_QUESTION_SEARCH
GRADING
DIAGNOSIS
LEARNING_PLAN_GENERATION
STATE_UPDATE
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

# 84. CPU 资源策略

默认：

```text
CPU workers = 1
max_concurrent_heavy_jobs = 1
```

原则：

```text
Web API
不被 AI/OCR 阻塞
```

重任务：

```text
异步
串行
可恢复
可重试
```

---

# 85. Job Failure

失败保存：

```text
input
job
error
stack_trace
llm_run
```

Retry：

```text
创建新 Job
```

不覆盖旧 Job。

---

# 86. API

```text
/auth

/students
/classes

/textbooks
/materials
/material-agent

/knowledge-points
/knowledge-graph

/student-knowledge-state
/learning-evidence

/diagnosis
/learning-objectives
/learning-plans
/learning-sessions

/questions
/question-bank
/question-generation
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

# 87. Security

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

# 88. Privacy

外部 LLM API 配置：

```text
provider
model
data_retention
external_transmission
```

必要时：

```text
Pseudonymization
Redaction
```

---

# 89. Copyright

网络材料：

```text
URL
Domain
Retrieved Time
Content Hash
License
Source Metadata
```

第三方材料不得自动重新公开发布。

---

# 90. 配置

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
  "learning": {
    "diagnosis": {
      "enabled": true,
      "schedule": "after_assessment"
    },
    "planning": {
      "enabled": true,
      "teacher_approval": true
    },
    "state_update": {
      "enabled": true,
      "teacher_confirmed_only": true
    },
    "spaced_review": {
      "enabled": true
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

# 91. Installation

提供：

```text
install.sh
```

功能：

```text
创建 venv
安装依赖
初始化数据库
执行 migrations
创建目录
创建默认教师
Build frontend
```

必须幂等。

不得覆盖：

```text
.env
configure.json
```

---

# 92. 测试

## Unit Test

测试：

```text
Question
QuestionVersion
KnowledgePoint
KnowledgePointVersion
StudentKnowledgeState
LearningEvidence
LearningPlan
LearningSession
Exam
ExamVersion
Score
```

## AI Question Test

测试：

```text
教材匹配
知识点匹配
答案
难度
重复题
Rubric
```

## AI Grading Test

测试：

```text
客观题
数学计算题
证明题
开放题
作文
手写答案
公式
图形题
```

---

# 93. End-to-End Test

必须能够完整运行：

```text
教师登录
 ↓
创建学生
 ↓
选择教材
 ↓
导入教材
 ↓
OCR
 ↓
建立知识点
 ↓
建立学生知识状态
 ↓
诊断
 ↓
生成学习目标
 ↓
AI 协助出题
 ↓
教师确认
 ↓
发布作业
 ↓
学生作答
 ↓
AI 协助批改
 ↓
教师确认
 ↓
Learning Evidence
 ↓
Knowledge State Update
 ↓
重新诊断
 ↓
生成下一轮学习计划
 ↓
AI 再次出题
```

---

# 94. MVP

第一阶段：

```text
Login
 ↓
Student
 ↓
Textbook
 ↓
Material
 ↓
OCR
 ↓
Chapter
 ↓
Knowledge Point
 ↓
Student Knowledge State
 ↓
Diagnosis
 ↓
Learning Objective
 ↓
Learning Plan
 ↓
Question Bank
 ↓
AI Question Generation
 ↓
Teacher Review
 ↓
Assignment
 ↓
Exam
 ↓
Online Exam
 ↓
Paper Exam
 ↓
Scan
 ↓
AI Grading
 ↓
Teacher Confirm
 ↓
Learning Evidence
 ↓
State Update
 ↓
Next Learning Plan
```

MVP 最重要的验收条件：

> **学生完成一次学习后，系统能够根据学习结果产生下一次有依据的学习任务。**

---

# 95. Phase 2

```text
Material Discovery Agent
Knowledge Incremental Update
Question Bank Incremental Update
Similar Question Engine
Historical Exam Import
Teacher Annotation Recognition
Error Pattern Engine
Spaced Review
Intervention Outcome
```

---

# 96. Phase 3

```text
Automatic Knowledge Gap Discovery
Student-specific Learning Policy
Cross-textbook Knowledge Mapping
Adaptive Intervention Sequencing
Automatic Question Bank Maintenance
Long-term Learning Path
```

---

# 97. 核心产品原则

## 原则 1：AI 协助出题

```text
AI Generate
    ↓
Validation
    ↓
Teacher Review
```

## 原则 2：AI 协助批改

```text
AI Grade
    ↓
Teacher Review
    ↓
Official Grade
```

## 原则 3：教师是正式判断边界

```text
AI
 ↓
Suggestion
 ↓
Teacher
 ↓
Official Evidence
```

## 原则 4：学生知识状态是系统核心

```text
Question
不是核心

Score
不是核心

Student Knowledge State
才是核心
```

## 原则 5：每一次学习产生证据

```text
Learning
 ↓
Evidence
```

## 原则 6：每一次证据影响下一次学习

```text
Evidence
 ↓
Knowledge State
 ↓
Learning Plan
 ↓
Question
```

---

# 98. 最终系统闭环

最终系统：

```text
                         ┌───────────────┐
                         │    教材课程     │
                         └───────┬───────┘
                                 ↓
                         ┌───────────────┐
                         │    知识体系     │
                         └───────┬───────┘
                                 ↓
                         ┌───────────────┐
                         │ 学生知识状态    │
                         └───────┬───────┘
                                 ↓
                         ┌───────────────┐
                         │     诊断       │
                         └───────┬───────┘
                                 ↓
                         ┌───────────────┐
                         │   学习目标      │
                         └───────┬───────┘
                                 ↓
                         ┌───────────────┐
                         │   学习计划      │
                         └───────┬───────┘
                                 ↓
                    ┌────────────────────────┐
                    │    AI 协助出题          │
                    └───────────┬────────────┘
                                ↓
                         ┌───────────────┐
                         │   教师审核      │
                         └───────┬───────┘
                                 ↓
                         ┌───────────────┐
                         │ 作业 / 考试     │
                         └───────┬───────┘
                                 ↓
                         ┌───────────────┐
                         │   学生作答      │
                         └───────┬───────┘
                                 ↓
                         ┌───────────────┐
                         │ OCR / Vision   │
                         └───────┬───────┘
                                 ↓
                    ┌────────────────────────┐
                    │    AI 协助批改          │
                    └───────────┬────────────┘
                                ↓
                         ┌───────────────┐
                         │   教师确认      │
                         └───────┬───────┘
                                 ↓
                         ┌───────────────┐
                         │ Learning       │
                         │ Evidence       │
                         └───────┬───────┘
                                 ↓
                         ┌───────────────┐
                         │ 状态更新        │
                         └───────┬───────┘
                                 │
                                 └──────────────→ 重新诊断
```

---

# 99. 一句话产品定义

> **这是一个以学生知识状态为核心，由 AI 协助教师出题和批改，通过真实学习证据持续更新学生状态，并自动产生下一轮学习任务的学习陪伴系统。**

核心闭环最终定义为：

```text
AI 出题
 ↓
学生作答
 ↓
AI 批改
 ↓
教师确认
 ↓
学习证据
 ↓
学生知识状态
 ↓
学习计划
 ↓
AI 再出题
```

这就是系统最核心的产品闭环。
