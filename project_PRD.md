# 学习陪伴系统（Learning Companion System）

## 完整产品需求文档 PRD v7.0

---

# 1. 产品定位

## 1.1 产品名称

**Learning Companion System**

中文名称：

> **学习陪伴系统**

---

# 2. 产品核心定位

系统面向：

* 家长
* 学生
* 家庭学习场景

核心目标：

> **让家长不需要自己大量找教材、找题、出题、批改、分析错题和制定学习计划，而由 AI 协助完成这些工作，家长负责监督、确认和关键决策。**

系统不是：

```text
AI 自动教学
```

也不是：

```text
AI 完全替代家长
```

而是：

```text
家长
 ↓
AI 学习助手
 ↓
学生
```

---

# 3. 核心角色

## 3.1 家长

家长是系统的主要管理者和学习陪伴者。

负责：

```text
学习目标设置
教材选择
学习计划确认
AI 出题审核
AI 批改审核
重要错误确认
学习结果查看
学习策略调整
```

不要求家长承担大量重复工作。

---

# 3.2 学生

学生是实际学习者。

负责：

```text
学习
阅读教材
完成练习
完成作业
参加考试
查看反馈
订正错误
完成复习
```

---

# 3.3 Admin

小规模系统中可以由家长兼任。

主要用于：

```text
系统配置
账号管理
LLM 配置
文件管理
日志
备份
```

---

# 4. 产品核心理念

系统核心不是：

```text
题库
```

也不是：

```text
AI 出题
```

而是：

> **学生知识状态的持续改善。**

核心闭环：

```text id="8g0zq7"
教材
 ↓
知识点
 ↓
学生知识状态
 ↓
学习目标
 ↓
AI 学习规划
 ↓
AI 协助出题
 ↓
学生作答
 ↓
AI 协助批改
 ↓
家长确认
 ↓
学习证据
 ↓
学生知识状态更新
 ↓
下一轮学习
```

---

# 5. 家长角色的核心设计

传统教师系统：

```text
教师
 ↓
出题
 ↓
批改
 ↓
分析
```

本系统：

```text
AI
 ↓
出题建议
 ↓
AI 批改
 ↓
家长确认
```

家长的工作从：

> “做所有事情”

变成：

> **“审核 AI 的关键决策，并陪伴孩子学习。”**

---

# 6. 家长工作量目标

每天家长原则上只需要：

```text id="0x2a2j"
查看今日学习计划
        ↓
确认 AI 推荐任务
        ↓
必要时检查 AI 批改
        ↓
查看孩子学习状态
```

例如：

```text
今日学习：

数学
一元一次方程应用题
25 分钟

AI 已生成：
6 道题

预计：
5 道自动批改
1 道建议家长确认
```

家长只需要点击：

```text
确认学习计划
```

学习结束后：

```text
AI：
6 道题完成

4 道正确
1 道计算错误
1 道建模错误

需要家长确认：
1 道
```

家长查看后确认。

---

# 7. 产品核心闭环

完整闭环：

```text id="x1yk6w"
                  家长
                    │
                    ↓
                学习目标
                    │
                    ↓
                  AI
                    │
              学习规划
                    ↓
              AI 协助出题
                    ↓
                  学生
                    ↓
                 作答
                    ↓
             OCR / Vision
                    ↓
             AI 协助批改
                    ↓
                  家长
                    ↓
                确认结果
                    ↓
            Learning Evidence
                    ↓
         Student Knowledge State
                    ↓
              下一轮规划
                    ↓
              AI 再次出题
```

---

# 8. 部署规模

系统目标：

```text
家庭数量：1
学生：1–5
家长：1–5
```

或者小规模：

```text
学生 < 5
```

同时在线用户：

```text
≤ 5
```

部署：

```text
Single Machine
```

---

# 9. 硬件要求

最低运行环境：

```text
CPU：2 cores
RAM：4 GB
GPU：无
```

操作系统：

```text
Ubuntu
macOS
```

核心业务不得依赖 GPU。

---

# 10. AI 架构

由于只有 2 CPU + 4 GB RAM：

不要求本地运行大型 LLM。

推荐：

```text
React
 ↓
FastAPI
 ↓
SQLite
 ↓
Async Job Worker
 ↓
External LLM API
```

外部 API：

```text
OpenAI-compatible API
```

---

# 11. AI 的两个一级能力

系统 AI 最重要的两个功能：

```text
① AI 协助出题

② AI 协助批改
```

其他 AI 能力：

```text
OCR
Vision
学习诊断
学习计划
知识点分析
错因分析
题库更新
教材分析
```

都服务于这两个核心流程和学习闭环。

---

# 12. AI 的角色

AI：

```text
分析者
生成者
助手
建议者
```

不是：

```text
最终教师
```

原则：

```text id="2d4r8y"
AI
 ↓
Suggestion
 ↓
Parent Review
 ↓
Official Result
```

---

# 13. 家长 Dashboard

首页显示：

```text
孩子
今日学习
当前目标
当前章节
知识掌握
薄弱点
今日任务
待家长确认
近期考试
学习趋势
```

例如：

```text
小明

今日学习：
数学 / 一元一次方程

预计：
25 分钟

当前掌握：
72%

主要薄弱点：
应用题建模

AI 建议：
完成 6 道练习

待家长确认：
1 项
```

---

# 14. Student Dashboard

学生首页：

```text
Today's Learning
Learning Plan
Assignments
Exams
Practice
Knowledge Progress
Mistakes
Feedback
Learning Archive
```

核心问题：

> **“我今天应该学习什么？”**

---

# 15. Student Profile

```text
student_id
name
grade
school
class
textbook
textbook_version
current_chapter
```

以及：

```text
learning_goal
strengths
weak_points
score_history
notes
```

---

# 16. 学习目标

家长可以设置：

```text
长期目标
阶段目标
章节目标
知识点目标
考试目标
```

例如：

```text
目标：
掌握一元一次方程应用题

当前：
0.35

目标：
0.80
```

---

# 17. Learning Objective

数据库实体：

```text
LearningObjective
```

字段：

```text
objective_id
student_id
knowledge_point_id
description
current_mastery
target_mastery
priority
deadline
status
```

---

# 18. 教材体系

```text
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

家长可以选择：

```text
教材
年级
版本
章节
```

---

# 19. 教材导入

支持：

```text
PDF
DOCX
JPG
JPEG
PNG
WebP
```

可以：

```text
上传教材
上传章节
上传练习册
上传学习资料
```

---

# 20. 扫描教材

流程：

```text
扫描 PDF
 ↓
OCR
 ↓
Layout Analysis
 ↓
章节识别
 ↓
小节识别
 ↓
公式识别
 ↓
图片识别
 ↓
知识点提取
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

# 21. Material

类型：

```text
TEXTBOOK
TEXTBOOK_SECTION
EXERCISE_BOOK
WORKSHEET
EXAM
ANSWER_KEY
SOLUTION
PARENT_NOTE
OTHER
```

来源：

```text
UPLOADED
IMPORTED
AGENT_DISCOVERED
MANUAL
```

---

# 22. Material Agent

系统可以定期寻找：

```text
教材相关公开资料
公开练习
公开试卷
公开答案
公开解析
```

流程：

```text
教材
 ↓
Material Agent
 ↓
Internet Search
 ↓
Candidate
 ↓
Validation
 ↓
Parent Review
 ↓
Material Library
```

默认：

```text
auto_import = false
```

---

# 23. Copyright

网络材料保存：

```text
URL
domain
retrieved_at
content_hash
license
source_metadata
```

第三方材料不自动公开重新发布。

---

# 24. Knowledge Point

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

# 25. 知识点示例

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

# 26. Student Knowledge State

系统核心实体：

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

---

# 27. Knowledge State 示例

```text
一元一次方程
mastery = 0.72
confidence = 0.88
trend = improving

移项
mastery = 0.91
confidence = 0.94

应用题建模
mastery = 0.34
confidence = 0.79
trend = declining
```

---

# 28. Knowledge State History

每一次变化必须保存历史：

```text
StudentKnowledgeStateHistory
```

例如：

```text
01-01  0.35
01-10  0.47
01-20  0.58
02-01  0.71
```

---

# 29. 学习诊断

输入：

```text
Student Knowledge State
Learning Evidence
Error Pattern
Recent Performance
Learning Goal
```

输出：

```text
Weak Knowledge
Error Pattern
Learning Priority
Suggested Intervention
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

# 30. Learning Planner

AI 学习规划：

```text
Student State
+
Learning Goal
+
Available Material
+
Question Bank
+
Past Evidence
```

输出：

```text
Learning Plan
```

---

# 31. Learning Plan

例如：

```text
目标：
掌握应用题

Day 1：
概念复习

Day 2：
简单应用题

Day 3：
变式题

Day 4：
综合题

Day 5：
Mini Test
```

家长可以：

```text
接受
修改
跳过
调整
```

---

# 32. AI 协助出题

这是系统核心功能之一。

目标：

> **AI 根据学生当前学习状态，为家长生成有明确学习目的的题目。**

---

# 33. AI 出题输入

```text
学科
年级
教材
章节
知识点
学习目标
学生掌握度
薄弱点
错误类型
历史题目
题型
难度
数量
预计时间
是否需要图形
是否需要证明
```

---

# 34. AI 出题不是随机出题

例如：

```text
应用题建模
mastery = 0.34
```

AI 生成：

```text
2 道概念题
3 道简单建模题
2 道变式题
1 道综合题
```

而不是：

```text
随机 8 道题
```

---

# 35. AI Question Generation

输出：

```text
题目
标准答案
解析
评分标准
知识点
难度
题型
预计时间
错误类型
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
Parent Review
 ↓
QuestionVersion
 ↓
Question Bank
```

---

# 37. 家长审核 AI 题目

家长可以：

```text
接受
修改
重新生成
降低难度
提高难度
删除
加入题库
```

界面重点显示：

```text
为什么生成这道题？
```

例如：

```text
原因：

孩子“应用题建模”掌握度：
34%

最近 5 道相关题：
2 次建模错误

因此 AI 推荐：
3 道简单建模题
```

---

# 38. Question Validator

检查：

```text
年级
章节
知识点
难度
答案
解析
Rubric
预计时间
重复度
计算量
```

数学额外：

```text
推理
证明
计算量
答案一致性
```

---

# 39. Question Bank

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

# 40. Question Version

发布题目：

```text
QuestionVersion
```

发布后 immutable。

---

# 41. Similar Question

支持：

```text
同知识点
同技能
不同题型
简单迁移
困难迁移
相同解题结构
相同错误类型
```

目标：

> 找到学习功能相似的题。

---

# 42. AI 协助批改

第二个核心 AI 功能：

> **AI 协助家长批改学生作业和考试。**

---

# 43. 批改输入

```text
Question
Standard Answer
Rubric
Student Answer
```

纸质答案额外：

```text
Original Image
OCR
Vision
```

---

# 44. 批改输出

```text
suggested_score
correctness
rubric_results
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
建议分数：0
错误类型：SIGN_ERROR
知识点：移项
置信度：0.96
```

---

# 46. 家长批改审核

界面：

```text
原始答案
OCR
标准答案
Rubric
AI 建议分数
AI 错误类型
AI Feedback
Confidence
```

按钮：

```text
接受 AI
修改
人工批改
```

---

# 47. 家长不需要审核所有题

系统应该自动分类：

```text
HIGH_CONFIDENCE
```

可以自动进入：

```text
AI Suggested
```

而：

```text
LOW_CONFIDENCE
AMBIGUOUS
OPEN_QUESTION
PROOF
ESSAY
```

进入：

```text
Needs Parent Review
```

目标：

> **让家长只处理 AI 最不确定的部分。**

---

# 48. AI 批改置信度

例如：

```text
题 1：
0.99
自动建议

题 2：
0.97
自动建议

题 3：
0.61
需要家长确认

题 4：
0.42
需要家长人工判断
```

---

# 49. AI 不能直接成为正式成绩

正式成绩流程：

```text
AI Suggestion
 ↓
Parent Review
 ↓
Official Grade
```

---

# 50. Grade Versioning

保存：

```text
previous_score
new_score
reason
changed_by
changed_at
```

---

# 51. OCR / Vision

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
Validation
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

# 52. 手写答案

支持识别：

```text
文字
数字
数学公式
计算过程
几何图形
批注
分数
```

识别结果必须保留置信度。

---

# 53. OCR 失败

不能破坏原始文件。

家长可以：

```text
重新 OCR
手工输入
跳过 OCR
```

---

# 54. 历史试卷导入

支持家长上传：

```text
过去考试
过去作业
过去练习
过去试卷
```

系统尝试恢复：

```text
Question
StudentAnswer
Score
Parent/Teacher Annotation
```

然后形成历史学习证据。

---

# 55. Historical Assessment Pipeline

```text
扫描试卷
 ↓
OCR
 ↓
Question Detection
 ↓
Student Answer
 ↓
Score
 ↓
Annotation
 ↓
Question Matching
 ↓
Knowledge Point Matching
 ↓
Parent Review
 ↓
Learning Evidence
```

---

# 56. Learning Evidence

核心数据：

```text
evidence_id
student_id
question_id
knowledge_point_id
source_type
correct
score
difficulty
error_type
feedback
confidence
trust_level
```

---

# 57. Evidence Trust

```text
RAW
AI_EXTRACTED
VALIDATED
PARENT_CONFIRMED
OFFICIAL
```

家庭场景中：

> **Parent Confirmed 是正式学习证据边界。**

---

# 58. Error Pattern

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

# 59. 学生状态更新

```text
Old State
+
New Evidence
 ↓
State Update
 ↓
New State
```

考虑：

```text
难度
时间
错误类型
历史表现
家长确认
```

---

# 60. 知识遗忘

系统记录：

```text
last_practiced
last_assessed
decay_risk
```

例如：

```text
掌握：
0.82

但是：
90 天没有练习

Decay Risk：
HIGH
```

系统生成复习任务。

---

# 61. 间隔复习

初始策略：

```text
弱：
1 天

中：
3 天

好：
7 天

强：
14 天

稳定：
30 天
```

---

# 62. Learning Intervention

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

系统不是：

```text
错了
 ↓
再给 10 道一样的题
```

而是：

```text
诊断错误
 ↓
选择干预
 ↓
练习
 ↓
测量效果
```

---

# 63. Intervention Outcome

记录：

```text
intervention_id
before_mastery
after_mastery
delta
assessment_count
time_to_improvement
```

例如：

```text
讲解：
0.31 → 0.34

简单题：
0.34 → 0.45

变式题：
0.45 → 0.61
```

系统可以逐渐知道：

> 哪种学习方式对这个学生更有效。

---

# 64. Parent Feedback

家长可以添加：

```text
“孩子今天理解了这个概念”
“这个错误是粗心”
“孩子不会建模”
“这道题超出当前学习范围”
```

这些反馈成为 Learning Evidence。

---

# 65. 家长学习报告

每日：

```text
今日学习
完成率
正确率
新增错误
需要关注
```

每周：

```text
知识点变化
掌握度变化
错误类型
学习时间
学习计划完成率
AI 建议
```

每月：

```text
知识体系
长期趋势
薄弱点
改善点
遗忘风险
学习干预效果
```

---

# 66. 家长报告示例

```text
本周：

学习时间：
2h 35min

完成任务：
18 / 20

主要进步：
移项
0.61 → 0.84

仍需关注：
应用题建模
0.38

主要错误：
MODEL_ERROR

AI 建议：
下周安排
4 道基础建模题
+
2 道变式题
+
1 次 Mini Test
```

---

# 67. 学生学习档案

包含：

```text
Assignment History
Exam History
Score History
Knowledge State
Mistakes
Error Patterns
Learning Plans
Learning Sessions
Learning Evidence
Parent Feedback
```

支持：

```text
PDF
CSV
Image ZIP
```

---

# 68. Question Bank Incremental Update

系统定期分析：

```text
学生错误
知识缺口
题目覆盖
重复率
使用率
难度
家长反馈
教材变化
```

AI 生成候选：

```text
ADD
MODIFY
REPLACE
DEPRECATE
```

流程：

```text
LLM
 ↓
Candidate
 ↓
Duplicate Detection
 ↓
Validation
 ↓
Parent Review
 ↓
Question Bank
```

---

# 69. Knowledge Base Incremental Update

AI 可以根据：

```text
教材
历史题目
学生错误
新题目
家长反馈
```

建议：

```text
ADD
MODIFY
MERGE
SPLIT
DEPRECATE
```

必须经过验证和家长确认。

---

# 70. AI Agent

主要 Agent：

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

# 71. Agent 权限

默认：

```text
READ
ANALYZE
SUGGEST
GENERATE
```

不能直接修改：

```text
正式成绩
正式学习证据
发布题目
学生正式知识状态
```

除非经过明确确认流程。

---

# 72. LLM Traceability

保存：

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

# 73. Online Exam

支持：

```text
选择题
多选题
判断题
填空题
计算题
简答题
证明题
作文
开放题
```

---

# 74. Online Exam Timer

服务器保存：

```text
started_at
deadline
submitted_at
```

浏览器 Timer 仅显示。

---

# 75. Autosave

默认：

```text
15 秒
```

服务器是答案最终来源。

浏览器保留临时 Draft 用于断网恢复。

---

# 76. Exam Attempt

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
生成 PDF
 ↓
家长打印
 ↓
学生完成
 ↓
拍照 / 扫描
 ↓
上传
 ↓
OCR / Vision
 ↓
AI 批改
 ↓
家长确认
```

线上考试和纸质考试最终进入统一：

```text
StudentAnswer
```

---

# 78. PDF 导出

支持：

```text
学生版
答案版
评分标准版
```

学生版不包含：

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
SVG
表格
题号
分值
```

家长可以手工修改。

---

# 80. 数据库

核心表：

```text
users
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
parent_feedback

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

parent_annotations
parent_scores

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

# 81. 文件存储

```text
data/
├── textbooks/
├── materials/
├── students/
│   └── {student_id}/
│       └── submissions/
│           └── {assignment_or_exam_id}/
│               └── {timestamp}/
│                   ├── original/
│                   ├── derived/
│                   └── metadata.json
├── exports/
└── cache/
```

---

# 82. Async Jobs

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

# 83. CPU 资源策略

默认：

```text
CPU workers = 1
max_concurrent_heavy_jobs = 1
```

重任务必须：

```text
异步
串行
可重试
可恢复
```

普通 Web API 不得被重任务阻塞。

---

# 84. API

```text
/auth

/students

/textbooks
/materials
/material-agent

/knowledge-points

/student-knowledge-state
/learning-evidence

/diagnosis
/learning-objectives
/learning-plans
/learning-sessions

/questions
/question-generation
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

# 85. 安全

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
```

---

# 86. 家庭数据隐私

学生数据属于敏感学习数据。

外部 AI 调用需要支持：

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

# 87. 配置

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
      "parent_approval": true
    },
    "state_update": {
      "enabled": true,
      "parent_confirmed_only": true
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

# 88. 安装

提供：

```text
install.sh
```

功能：

```text
创建 Python venv
安装依赖
初始化 SQLite
执行 migration
创建 data directories
创建家长账号
Build frontend
```

不得覆盖：

```text
.env
configure.json
```

---

# 89. 测试

## AI 出题测试

必须测试：

```text
教材匹配
知识点匹配
年级匹配
难度
答案
解析
Rubric
重复题
题型
```

## AI 批改测试

必须测试：

```text
选择题
填空题
计算题
证明题
开放题
作文
手写答案
公式
几何题
```

---

# 90. 学习闭环测试

必须测试：

```text
学生状态
 ↓
学习目标
 ↓
AI 出题
 ↓
学生答题
 ↓
AI 批改
 ↓
家长确认
 ↓
Learning Evidence
 ↓
Knowledge State Update
 ↓
新学习计划
 ↓
AI 再出题
```

---

# 91. MVP

第一阶段：

```text
家长登录
 ↓
创建学生
 ↓
选择教材
 ↓
上传教材
 ↓
OCR
 ↓
章节
 ↓
知识点
 ↓
学生知识状态
 ↓
学习目标
 ↓
AI 学习计划
 ↓
AI 协助出题
 ↓
家长确认
 ↓
作业
 ↓
学生作答
 ↓
AI 协助批改
 ↓
家长确认
 ↓
Learning Evidence
 ↓
Knowledge State Update
 ↓
下一轮学习计划
```

---

# 92. MVP 最重要验收标准

不是：

> AI 能不能生成很多题。

也不是：

> AI 能不能自动批改所有题。

而是：

> **孩子完成一次学习后，系统能否根据真实学习结果，为孩子产生下一次有依据的学习任务。**

---

# 93. Phase 2

增加：

```text
Material Discovery Agent
Historical Exam Import
Similar Question Engine
Error Pattern Engine
Spaced Review
Knowledge Incremental Update
Question Bank Incremental Update
Intervention Outcome
```

---

# 94. Phase 3

增加：

```text
Student-specific Learning Policy
Cross-textbook Knowledge Mapping
Automatic Knowledge Gap Discovery
Adaptive Intervention Sequencing
Long-term Learning Path
Automatic Question Bank Maintenance
```

---

# 95. 核心产品闭环

最终：

```text
                    家长
                      │
              学习目标 / 确认
                      ↓
                 AI 学习助手
                      │
          ┌───────────┴───────────┐
          ↓                       ↓
      学习规划                 AI 出题
          │                       │
          └──────────┬────────────┘
                     ↓
                   学生
                     ↓
                  作答
                     ↓
               AI 协助批改
                     ↓
                   家长
                     ↓
                  确认
                     ↓
             Learning Evidence
                     ↓
          Student Knowledge State
                     ↓
                学习诊断
                     ↓
                下一轮计划
                     ↓
                 AI 再出题
```

---

# 96. 三方职责

| 角色     | 主要职责              |
| ------ | ----------------- |
| **学生** | 学习、阅读、练习、考试、订正    |
| **AI** | 分析、规划、出题、批改、反馈、推荐 |
| **家长** | 目标设置、审核、确认、监督、陪伴  |

核心原则：

> **AI 做重复工作，学生做学习工作，家长做关键决策和陪伴。**

---

# 97. 最终产品定义

> **学习陪伴系统是一个以学生知识状态为核心、以家长为主要学习陪伴者、以 AI 协助出题和 AI 协助批改为核心能力，通过 Learning Evidence 持续更新学生知识状态，并自动生成下一轮学习任务的家庭个性化学习系统。**

最终闭环：

```text
家长设定目标
      ↓
学生知识状态
      ↓
AI 学习规划
      ↓
AI 协助出题
      ↓
学生学习 / 作答
      ↓
AI 协助批改
      ↓
家长确认
      ↓
学习证据
      ↓
学生知识状态更新
      ↓
下一轮学习规划
      ↓
AI 再次出题
```

核心价值：

> **让家长从“亲自找题、出题、批改、分析”的低效率重复劳动中解放出来，把精力集中在真正重要的事情：理解孩子、确认关键判断、鼓励孩子和陪伴孩子持续学习。**
