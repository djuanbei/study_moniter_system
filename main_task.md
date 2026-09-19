# 学习陪伴系统（Learning Companion System）

## Product Requirements Document / System Specification

**版本：1.0**

---

# 1. 产品概述

## 1.1 产品目标

构建一个面向教师和学生的 AI 学习陪伴系统，实现：

```text
学生
 ↓
学习档案
 ↓
教材 / 年级 / 章节
 ↓
知识点体系
 ↓
历史成绩与错题
 ↓
LLM 学习分析
 ↓
智能出题
 ↓
题库
 ↓
教师审核
 ↓
作业 / 考试
 ├── 在线考试
 └── PDF / Word 纸质考试
 ↓
学生作答
 ↓
OCR / Vision / 在线答案解析
 ↓
LLM 辅助批改
 ↓
教师确认
 ↓
学习证据
 ↓
学生学习档案
 ↓
知识点掌握度
 ↓
下一轮个性化出题
```

系统不是单纯的题目生成器，而是一个持续运行的：

> **学习数据 → 知识体系 → 题库 → 出题 → 作答 → 批改 → 学习分析 → 再出题**

闭环系统。

---

# 2. 用户角色

## 2.1 Teacher

教师可以：

* 管理学生
* 管理班级
* 管理教材和章节
* 管理知识点
* 管理题库
* 使用 LLM 生成题目
* 审核 AI 生成题
* 创建作业
* 创建考试
* 修改考试
* 发布考试
* 导出 PDF
* 导出 Word
* 查看在线考试状态
* 批改学生答案
* 查看 AI 批改建议
* 修改 AI 批改结果
* 查看学生学习档案
* 查看知识点掌握情况
* 管理系统设置
* 查看审计日志

## 2.2 Student

学生可以：

* 登录
* 查看个人学习档案
* 查看作业
* 在线完成考试
* 查看剩余考试时间
* 保存答案
* 提交考试
* 上传纸质作业/考试扫描件
* 查看教师确认后的成绩
* 查看教师反馈
* 查看知识点学习情况

---

# 3. 登录与账户

## 3.1 默认教师账户

默认用户名：

```text
yun
```

密码来自：

```text
.env
PASS_WORD
```

禁止将默认密码提交到 Git。

第一次登录必须修改密码。

## 3.2 密码安全

使用：

* Argon2 或 bcrypt
* 密码不可明文保存
* Session / HttpOnly Cookie
* CSRF 防护

## 3.3 RBAC

至少支持：

```text
TEACHER
STUDENT
ADMIN
```

学生只能访问自己的数据。

教师只能访问自己有权限的班级和学生。

---

# 4. 中文 UI

系统默认 UI 为中文。

包括：

* 登录
* 首页
* 学生管理
* 班级管理
* 教材
* 章节
* 知识点
* 题库
* 出题
* 作业
* 考试
* 在线考试
* 提交
* 批改
* 学习档案
* 数据分析
* 导出
* 系统设置

---

# 5. 教师 Dashboard

教师首页显示：

```text
学生数量
班级数量
待批改作业
待批改考试
近期考试
近期作业
AI 出题任务
题库更新任务
知识点更新任务
LLM Job 状态
学生学习趋势
```

---

# 6. 学生管理

## 6.1 Student

学生字段：

```text
student_id
name
grade
class_id
textbook_version
current_chapter
parent_contact(optional)
notes
created_at
updated_at
```

## 6.2 学习档案

系统保存：

* 历史成绩
* 知识点掌握度
* 错题
* 教师反馈
* 学习趋势
* 作业完成率
* 考试成绩
* 知识点错误率
* 最近评估时间

---

# 7. 班级管理

教师可以：

* 创建班级
* 修改班级
* 删除班级
* 添加学生
* 移除学生
* 查看班级成绩
* 查看班级知识点分布

---

# 8. 教材与章节系统

## 8.1 教材

支持：

```text
subject
grade
textbook_version
publisher
edition
school_year
```

## 8.2 Chapter

章节包括：

```text
chapter_id
textbook_id
parent_chapter_id
chapter_number
title
description
order_index
```

## 8.3 当前章节推断

系统可以根据：

```text
日期
+
学年
+
教材版本
+
学生年级
+
教师设置
+
历史章节进度
```

推断学生当前章节。

默认学年：

```text
9 月开始
```

教师可以手动覆盖。

必须区分：

```text
chapter_source = inferred
chapter_source = manual
```

如果教师手动设置，则优先使用 manual。

---

# 9. 知识点系统

## 9.1 KnowledgePoint

```text
knowledge_point_id
subject
name
description
parent_id
chapter_id
difficulty
status
created_at
updated_at
```

支持树状结构：

```text
数学
 ├── 代数
 │    ├── 方程
 │    ├── 不等式
 │    └── 函数
 └── 几何
      ├── 三角形
      ├── 圆
      └── 相似
```

---

# 10. 知识点版本化

知识点不能直接覆盖。

使用：

```text
KnowledgePoint
 ├── Version 1
 ├── Version 2
 └── Version 3
```

版本保存：

```text
knowledge_point_version_id
knowledge_point_id
version
name
description
parent_id
chapter_id
source
created_at
```

历史成绩必须引用当时使用的 KnowledgePointVersion。

因此教材体系发生变化后：

> 历史学习数据不会被重新解释。

---

# 11. LLM 增量更新知识点库

这是系统的长期后台能力。

## 11.1 更新来源

LLM 可以分析：

* 教材
* 章节
* 已有知识点
* 历史题目
* 新生成题目
* 学生错误
* 学生知识点掌握度
* 教师反馈

## 11.2 LLM 可以发现

```text
新增知识点
修改知识点
知识点合并
知识点拆分
知识点废弃
章节归属变化
知识点描述变化
```

## 11.3 不允许直接覆盖

流程：

```text
已有 Knowledge Base
       ↓
LLM Analysis
       ↓
Knowledge Update Candidate
       ↓
Validation
       ↓
Teacher Review
       ↓
Publish
       ↓
New KnowledgePointVersion
```

默认：

```text
auto_publish = false
```

可以配置自动发布低风险更新。

---

# 12. 知识库更新 Diff

每次更新必须保存：

```text
added
modified
merged
split
deprecated
unchanged
```

教师可以看到：

```text
本次更新：
新增 12 个知识点
修改 7 个知识点
合并 2 组知识点
废弃 3 个知识点
```

并可以逐项：

```text
接受
拒绝
修改后接受
```

---

# 13. 题库系统

## 13.1 Question

每道题具有：

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
created_at
updated_at
```

## 13.2 QuestionVersion

题目必须版本化：

```text
Question
 ├── v1
 ├── v2
 └── v3
```

考试一旦发布，使用固定 QuestionVersion。

已经发布的考试不会因为题库更新而改变。

---

# 14. 题目类型

至少支持：

```text
选择题
多选题
判断题
填空题
计算题
简答题
证明题
几何题
阅读题
表达题
作文题
开放题
思维题
```

---

# 15. 题目元数据

每道题必须包含：

```text
题目
标准答案
评分标准
知识点
难度
预计完成时间
题型
年级
章节
```

难度内部使用：

```text
0.0 ~ 1.0
```

UI 可以显示：

```text
简单
中等
困难
```

---

# 16. LLM 出题

教师可以输入：

```text
年级
教材
章节
知识点
题目数量
难度
题型
预计时间
特殊要求
截止日期
是否允许计算器
```

系统生成：

```text
Set A
Set B
```

默认每次生成两套。

---

# 17. 个性化出题

LLM 输入：

```text
学生信息
+
当前章节
+
历史成绩
+
薄弱知识点
+
优势知识点
+
近期错题
+
题库覆盖情况
+
教师要求
```

生成目标：

```text
知识点覆盖
难度控制
题型控制
计算量控制
学生个性化
```

---

# 18. 学科规则

## 18.1 语文 / Language

支持：

* 作文
* 阅读理解
* 表达
* 综合应用

作文必须包含评分维度。

例如：

```text
内容
结构
语言
表达
立意
```

## 18.2 数学

优先：

* 思维题
* 证明题
* 综合题
* 一题多解
* 开放题

避免题库过度集中于机械计算。

## 18.3 几何

几何题必须具有图形。

优先：

```text
SVG
```

必要时可以使用：

```text
Mermaid
```

但最终必须生成适合学生阅读的正式图形。

---

# 19. LLM 输出格式

LLM 不允许直接输出不可解析的自由文本作为正式题目。

使用结构化 JSON：

```json
{
  "questions": [
    {
      "prompt": "...",
      "answer": "...",
      "rubric": [],
      "knowledge_points": [],
      "difficulty": 0.6,
      "estimated_time_minutes": 10,
      "question_type": "proof"
    }
  ]
}
```

---

# 20. 题目 Validator

每道 AI 题必须经过验证。

检查：

```text
年级是否正确
章节是否正确
知识点是否匹配
答案是否存在
评分标准是否存在
难度是否符合要求
题型是否正确
预计时间是否合理
重复度
```

特殊检查：

```text
数学：
计算量

几何：
是否存在图形

作文：
是否存在评分标准

思维题：
是否适合作为长期思考题
```

---

# 21. 题库增量更新

题库不应该每次重新生成。

采用：

```text
Existing Question Bank
        +
Learning Evidence
        +
Knowledge Gaps
        +
Question Coverage
        +
Teacher Feedback
        +
New Textbook Content
        ↓
LLM Incremental Generation
        ↓
Duplicate Detection
        ↓
Question Validation
        ↓
Quality Filter
        ↓
Candidate Bank
        ↓
Teacher Review
        ↓
Published Question Bank
```

---

# 22. 题库更新触发条件

可以由以下条件触发：

```text
定时任务
知识点发生变化
新章节出现
某知识点题目不足
某知识点学生错误率高
某类题目重复率高
教师主动请求
```

例如：

```text
知识点 A 当前只有 3 道题
系统最低要求 20 道
→ 自动生成 17 道候选题
```

---

# 23. 题库质量控制

每道候选题可以进行：

```text
重复检测
语义相似检测
知识点匹配
难度验证
答案验证
格式验证
图形验证
```

题库状态：

```text
CANDIDATE
REVIEWING
APPROVED
PUBLISHED
DEPRECATED
REJECTED
```

---

# 24. 题库增量更新 Diff

每次更新保存：

```text
generated
accepted
rejected
duplicate
modified
deprecated
```

教师可以查看：

```text
本次新增 20 道
重复 5 道
拒绝 3 道
通过 12 道
```

---

# 25. 定时 LLM Job

系统建立统一 Job 系统。

Job 类型：

```text
KNOWLEDGE_UPDATE
QUESTION_BANK_UPDATE
QUESTION_GENERATION
OCR
VISION
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

# 26. 定时配置

`configure.json`：

```json
{
  "knowledge_base": {
    "incremental_update": {
      "enabled": true,
      "schedule": "weekly",
      "batch_size": 50,
      "auto_publish": false
    }
  },

  "question_bank": {
    "incremental_update": {
      "enabled": true,
      "schedule": "daily",
      "questions_per_batch": 20,
      "auto_publish": false
    }
  },

  "exam": {
    "allow_retake": false,
    "autosave_interval_seconds": 15
  }
}
```

支持：

```text
daily
weekly
custom cron
manual
```

---

# 27. LLM Traceability

每次 LLM 调用必须记录：

```text
agent
prompt_hash
input
output
model
model_version
tokens
latency
timestamp
job_id
```

禁止只保存最终结果而丢失 LLM 过程记录。

---

# 28. Question Bank 与 Learning Feedback 闭环

系统持续计算：

```text
知识点覆盖率
题目数量
题目使用次数
题目正确率
题目错误率
题目重复率
题目难度分布
```

例如：

```text
知识点 A
题目：8
学生错误率：62%
题目覆盖不足
        ↓
LLM
        ↓
增加 12 道不同难度题
```

---

# 29. 作业系统

Assignment 支持：

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

教师可以：

* 创建
* 编辑
* 删除
* 选择题目
* 混合 A/B 题目
* 指定学生
* 指定班级
* 设置截止时间
* 发布
* 关闭

---

# 30. 考试系统

Assignment 和 Exam 分离。

```text
Assignment
Exam
```

共享：

```text
QuestionVersion
StudentAnswer
Grading
StudentProgress
```

Exam 用于正式考试。

---

# 31. ExamVersion

考试发布后产生：

```text
ExamVersion
```

包含：

```text
考试名称
说明
题目顺序
QuestionVersion
分值
总分
考试时间
开始时间
结束时间
```

发布后的 ExamVersion immutable。

---

# 32. 考试编辑器

教师可以：

```text
添加题目
删除题目
调整顺序
修改分值
修改说明
修改考试时间
修改题目
修改答案
修改评分标准
```

发布之后：

> 不允许修改 ExamVersion。

如果需要修改，创建新的 ExamVersion。

---

# 33. PDF 导出

教师可以导出：

```text
学生试卷
答案版
评分标准版
```

PDF 必须支持：

* 中文
* 数学公式
* 图片
* SVG
* 几何图形
* 表格
* 页码
* 页眉
* 页脚
* 自动分页
* 题目编号
* 分值

学生试卷不得包含：

```text
答案
AI prompt
LLM trace
内部评分信息
```

---

# 34. Word 导出

支持：

```text
.docx
```

必须支持：

* 中文
* 数学公式
* 图片
* SVG 转换
* 表格
* 题目编号
* 分值
* 教师说明

Word 导出后的文件允许教师进一步手工编辑。

---

# 35. 在线考试

学生可以直接在线完成 Exam。

页面：

```text
考试名称
剩余时间
题目导航
当前题目
答案区域
上一题
下一题
提交考试
```

题目状态：

```text
未作答
已作答
当前题
```

---

# 36. 在线答案输入

支持：

### 选择题

Radio。

### 多选题

Checkbox。

### 判断题

True / False。

### 填空题

Text input。

### 简答题

多行文本。

### 数学题

支持：

```text
普通文本
LaTeX
```

### 作文

支持：

```text
Rich Text
```

### 证明题 / 开放题

支持：

```text
文本
LaTeX
图片
```

---

# 37. 在线考试计时

服务器负责计时。

记录：

```text
started_at
deadline
submitted_at
```

浏览器 JavaScript 的倒计时只用于 UI。

服务器时间才是最终依据。

---

# 38. 自动保存

学生输入答案时自动保存。

例如：

```text
debounce
+
每 15 秒同步
```

刷新页面后恢复服务器最新答案。

---

# 39. 网络异常恢复

支持：

```text
Browser Local Draft
        ↕
Server Answer
```

如果网络中断：

```text
继续答题
 ↓
本地保存
 ↓
网络恢复
 ↓
同步服务器
```

使用：

```text
answer_version
client_version
server_version
```

解决冲突。

---

# 40. 提交考试

学生点击：

```text
提交考试
```

显示：

```text
已完成：18 / 20
未完成：2
是否确认提交？
```

确认后：

```text
IN_PROGRESS
      ↓
SUBMITTED
```

提交后原则上不能继续修改。

---

# 41. 考试超时

服务器发现：

```text
now >= deadline
```

自动提交。

记录：

```text
submit_reason = timeout
```

正常提交：

```text
submit_reason = student_submit
```

---

# 42. ExamAttempt

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

默认：

```text
每个学生一个正式 attempt
```

可以通过配置允许重考。

---

# 43. 在线考试与纸质考试统一

系统不应该建立两套完全不同的批改体系。

统一模型：

```text
                 ExamVersion
                     ↓
          ┌──────────┴──────────┐
          ↓                     ↓
     Online Exam           Printed Exam
          ↓                     ↓
    Online Answer        Scan / Upload
          ↓                     ↓
          └──────────┬──────────┘
                     ↓
                StudentAnswer
                     ↓
                AI Grading
                     ↓
              Teacher Confirm
                     ↓
             Student Progress
```

---

# 44. 纸质考试

教师：

```text
创建考试
 ↓
导出 PDF / Word
 ↓
打印
```

学生：

```text
纸质作答
 ↓
拍照 / 扫描
 ↓
上传
```

系统：

```text
OCR / Vision
 ↓
结构化答案
 ↓
AI 批改
 ↓
教师确认
```

---

# 45. Submission

支持：

```text
JPG
JPEG
PNG
WebP
PDF
```

也可以提交文本答案。

支持多文件。

---

# 46. 文件存储

目录：

```text
data/
  students/
    {student_id}/
      submissions/
        {assignment_id_or_exam_id}/
          {timestamp}/
            original/
            metadata.json
            derived/
```

Original 文件 immutable。

---

# 47. Submission Metadata

保存：

```text
filename
size
SHA256
upload_time
question_number
OCR_text
mime_type
```

---

# 48. 上传安全

必须验证：

```text
文件扩展名
MIME
magic bytes
文件大小
文件名
路径
```

防止：

```text
Path Traversal
MIME Spoofing
恶意文件
超大文件
```

---

# 49. OCR / Vision

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
OCR / Vision
 ↓
Structured StudentAnswer
 ↓
Teacher Review
 ↓
AI Grading
```

OCR 失败：

> 原始文件仍然保留。

教师可以：

```text
重新 OCR
手工输入答案
跳过 OCR
```

---

# 50. StudentAnswer

统一在线和纸质答案。

```text
student_answer_id
question_id
student_id
source
content
image_path
ocr_text
version
created_at
updated_at
```

source：

```text
online
image
pdf
manual
```

---

# 51. AI 批改

AI 输入：

```text
题目
标准答案
评分标准
学生答案
```

输出：

```text
suggested_score
rubric_results
feedback
knowledge_point_results
confidence
```

状态：

```text
AI_SUGGESTED
TEACHER_CONFIRMED
```

---

# 52. 教师确认成绩

教师看到：

```text
原始答案
OCR 结果
标准答案
评分标准
AI 建议
建议分数
建议反馈
知识点判断
```

教师可以：

```text
接受
修改分数
修改反馈
修改知识点判断
完全手工评分
```

最终以教师确认为准。

---

# 53. 成绩版本化

保存：

```text
old_score
new_score
reason
changed_by
changed_at
```

不能无痕修改历史成绩。

---

# 54. 学习证据

只有：

```text
TEACHER_CONFIRMED
```

的结果才能作为正式学习证据。

AI 建议不能直接改变学生正式掌握度。

---

# 55. StudentProgress

知识点记录：

```text
knowledge_point_version_id
mastery_score
confidence
evidence_count
last_assessed_at
trend
```

例如：

```text
函数单调性
掌握度：0.72
证据：18
趋势：↑
```

---

# 56. 学习档案

学生档案包括：

```text
作业历史
考试历史
成绩趋势
知识点掌握度
错误知识点
教师反馈
学习趋势
```

支持：

```text
PDF
CSV
图片 ZIP
```

导出。

---

# 57. 学生学习分析

系统可以生成：

```text
成绩趋势
知识点掌握趋势
薄弱知识点
长期未训练知识点
题型错误分布
考试表现
```

这些结果作为下一轮 LLM 出题输入。

---

# 58. LLM Agent 架构

采用 LangChain Agent / Workflow。

主要 Agent：

```text
Curriculum Planning Agent
Question Planning Agent
Question Generation Agent
Diagram Generation Agent
Knowledge Update Agent
Question Bank Update Agent
Validation Agent
Grading Agent
Learning Analysis Agent
```

---

# 59. Agent Tools

提供：

```text
SQLite Query
Textbook Retrieval
Chapter Retrieval
KnowledgePoint Retrieval
QuestionBank Retrieval
OCR
Vision
SVG Generator
Rubric Checker
Duplicate Detector
Question Validator
StudentProgress Query
```

---

# 60. LLM 增量更新总架构

长期运行系统：

```text
                 ┌──────────────────┐
                 │    Textbook      │
                 └────────┬─────────┘
                          ↓
                  Knowledge Base
                          ↓
                  Knowledge Update
                          ↓
                  Question Bank
                          ↓
                    Assignments
                          ↓
                       Exams
                     ↙       ↘
                Online       Paper
                   ↓            ↓
                Answers      OCR/Vision
                     ↘       ↙
                       Grading
                          ↓
                  Teacher Confirm
                          ↓
                  Learning Evidence
                          ↓
                  Student Progress
                          ↓
              ┌───────────┴───────────┐
              ↓                       ↓
       Knowledge Update        Question Update
              └───────────┬───────────┘
                          ↓
                       下一轮
```

这是系统的核心学习闭环。

---

# 61. 数据库

SQLite + WAL。

主要表：

```text
users
classes
students

textbooks
chapters
knowledge_points
knowledge_point_versions
student_progress
student_progress_history

questions
question_versions
question_sets

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

gradings
grading_versions

llm_runs
jobs

knowledge_update_runs
knowledge_update_candidates

question_bank_update_runs
question_bank_candidates

exports
audit_logs
settings
```

---

# 62. 数据关系

核心关系：

```text
Student
  ↓
StudentProgress
  ↓
KnowledgePointVersion
```

```text
Question
  ↓
QuestionVersion
  ↓
ExamVersion
```

```text
ExamVersion
  ↓
ExamAttempt
  ↓
StudentAnswer
  ↓
Grading
```

最终：

```text
Grading
 ↓
Learning Evidence
 ↓
StudentProgress
```

---

# 63. 数据不可变原则

必须保证：

### 原始提交不可变

```text
Original Submission = immutable
```

### 已发布考试不可变

```text
Published ExamVersion = immutable
```

### 已使用题目版本不可变

```text
QuestionVersion = immutable
```

### AI Trace 不可删除

除非符合系统数据保留策略。

---

# 64. Job 系统

所有耗时任务进入 Job Queue：

```text
LLM
OCR
Vision
Grading
PDF
DOCX
Archive
Knowledge Update
Question Bank Update
```

状态：

```text
QUEUED
RUNNING
SUCCEEDED
FAILED
CANCELLED
```

失败时：

```text
保存输入
保存错误
保存 LLM Run
保留原始文件
```

重试必须创建新的 Job / Run。

---

# 65. API

## Auth

```text
POST /api/auth/login
POST /api/auth/logout
POST /api/auth/change-password
```

## Students

```text
GET /api/students
POST /api/students
GET /api/students/{id}
PUT /api/students/{id}
```

## Classes

```text
GET /api/classes
POST /api/classes
PUT /api/classes/{id}
```

## Knowledge

```text
GET /api/knowledge-points
POST /api/knowledge-points
PUT /api/knowledge-points/{id}
GET /api/knowledge-points/{id}/versions
```

## Question Bank

```text
GET /api/questions
POST /api/questions
GET /api/questions/{id}
PUT /api/questions/{id}
GET /api/questions/{id}/versions
```

## Generation

```text
POST /api/generation/question-set
GET /api/generation/{job_id}
```

## Knowledge Update

```text
POST /api/knowledge/update
GET /api/knowledge/update/{job_id}
GET /api/knowledge/candidates
POST /api/knowledge/candidates/{id}/approve
POST /api/knowledge/candidates/{id}/reject
```

## Question Bank Update

```text
POST /api/question-bank/update
GET /api/question-bank/update/{job_id}
GET /api/question-bank/candidates
POST /api/question-bank/candidates/{id}/approve
POST /api/question-bank/candidates/{id}/reject
```

## Assignment

```text
POST /api/assignments
GET /api/assignments
PUT /api/assignments/{id}
POST /api/assignments/{id}/publish
```

## Exam

```text
POST /api/exams
GET /api/exams
GET /api/exams/{id}
POST /api/exams/{id}/versions
POST /api/exams/{id}/publish
```

## Exam Attempt

```text
POST /api/exams/{id}/attempt
GET /api/exam-attempts/{id}
PUT /api/exam-attempts/{id}/answers
POST /api/exam-attempts/{id}/submit
```

## Submission

```text
POST /api/submissions
GET /api/submissions/{id}
```

## Grading

```text
POST /api/gradings/{id}/ai-grade
PUT /api/gradings/{id}
POST /api/gradings/{id}/confirm
```

## Export

```text
POST /api/exports/pdf
POST /api/exports/docx
POST /api/exports/archive
GET /api/exports/{id}
```

---

# 66. 前端

推荐：

```text
React
Vite
TypeScript
```

或者：

```text
HTMX
Jinja
```

在线考试页面必须特别处理：

```text
倒计时
自动保存
网络恢复
提交确认
防止重复提交
页面刷新恢复
```

---

# 67. 导出系统

Export Job：

```text
QUEUED
 ↓
RUNNING
 ↓
PDF/DOCX generation
 ↓
SUCCEEDED
```

失败：

```text
FAILED
```

不能阻塞普通 API。

---

# 68. 审计日志

记录：

```text
login
logout
student_create
student_update
question_generate
question_approve
knowledge_update
question_bank_update
assignment_create
exam_create
exam_publish
exam_submit
grading
grading_confirm
export
delete
account_change
```

---

# 69. 安全

必须实现：

```text
Argon2 / bcrypt
HttpOnly Cookie
CSRF
RBAC
Input Validation
Upload Validation
Path Traversal Protection
MIME Validation
File Size Limit
Authenticated File Access
Audit Log
```

---

# 70. 配置

`.env`：

```text
PASS_WORD=
DATABASE_URL=
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
```

禁止提交 Git。

`configure.json`：

```text
业务配置
考试配置
LLM 配置
题库更新策略
知识库更新策略
上传限制
```

同样禁止提交 Git。

仓库提供：

```text
.env.example
configure.example.json
```

---

# 71. 安装脚本

提供：

```text
install.sh
```

要求：

* 幂等
* 自动创建 Python venv
* 安装依赖
* 创建目录
* 数据库 migration
* 创建默认教师
* 构建前端
* 检查环境

不得覆盖：

```text
.env
configure.json
```

如果：

```text
PASS_WORD
```

不存在：

```text
交互式要求输入
 ↓
写入 .env
 ↓
创建默认教师
```

---

# 72. 支持平台

至少：

```text
Ubuntu
Debian
CentOS
macOS
```

---

# 73. SQLite

使用：

```text
SQLite
WAL
```

数据库负责：

```text
结构化数据
关系
状态
版本
审计
LLM trace
Job
```

文件系统负责：

```text
上传文件
扫描件
PDF
Word
图片
导出文件
```

数据库只保存：

```text
path
hash
metadata
```

---

# 74. Backup

备份必须包含：

```text
SQLite database
+
student submission files
+
generated documents
+
configuration metadata
```

恢复后必须能够继续：

```text
学生档案
题库
考试
提交
批改
学习历史
```

---

# 75. 性能要求

普通 API：

```text
< 500 ms
```

登录：

```text
< 1 s
```

不把以下任务计入普通 API 延迟：

```text
LLM
OCR
Vision
PDF
DOCX
```

这些任务异步执行。

---

# 76. LLM 失败处理

LLM 失败：

```text
保留原任务
保留输入
保留错误
保留 LLM Run
```

用户可以：

```text
Retry
Cancel
Continue Editing
```

不能因为 LLM 失败导致已有数据丢失。

---

# 77. 网络异常

上传支持：

```text
retry
```

在线考试支持：

```text
local draft
server autosave
reconnect
synchronization
```

---

# 78. 测试

必须包括：

## Unit Test

```text
知识点
题目
版本
成绩
考试计时
自动保存
```

## Integration Test

完整测试：

```text
学生
→ 出题
→ 题库
→ Exam
→ 在线考试
→ 提交
→ AI 批改
→ 教师确认
→ 学习档案
```

以及：

```text
Exam
→ PDF
→ 打印
→ 图片上传
→ OCR
→ AI Grading
→ Teacher Confirm
```

## Incremental Update Test

测试：

```text
Knowledge Update
Question Bank Update
Duplicate Detection
Version Creation
Candidate Approval
Candidate Rejection
```

## Security Test

测试：

```text
越权访问
CSRF
Path Traversal
MIME Spoofing
超大文件
非法文件
重复提交
```

## Install Test

在：

```text
Ubuntu
Debian
CentOS
macOS
```

测试 `install.sh`。

---

# 79. Git

必须：

```text
代码
配置模板
数据库 migration
测试
文档
```

进入 Git。

禁止：

```text
.env
configure.json
data/
logs/
uploads/
运行时数据库
个人学生数据
API Key
密码
```

进入 Git。

---

# 80. 项目结构

建议：

```text
learning-companion/
├── backend/
│   ├── app/
│   │   ├── auth/
│   │   ├── students/
│   │   ├── classes/
│   │   ├── textbooks/
│   │   ├── knowledge/
│   │   ├── questions/
│   │   ├── assignments/
│   │   ├── exams/
│   │   ├── submissions/
│   │   ├── grading/
│   │   ├── llm/
│   │   ├── jobs/
│   │   ├── exports/
│   │   └── audit/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── main.py
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── exams/
│   │   ├── questions/
│   │   └── students/
│
├── migrations/
├── tests/
├── data/
├── scripts/
├── docs/
├── .env.example
├── configure.example.json
├── install.sh
└── README.md
```

---

# 81. 核心数据生命周期

## Question

```text
LLM Generate
 ↓
Candidate
 ↓
Validate
 ↓
Teacher Review
 ↓
QuestionVersion
 ↓
QuestionBank
 ↓
ExamVersion
```

## Knowledge Point

```text
Textbook
 ↓
LLM Analysis
 ↓
Candidate
 ↓
Validation
 ↓
Teacher Review
 ↓
KnowledgePointVersion
```

## Student Answer

```text
Online / Paper
 ↓
StudentAnswer
 ↓
AI Grading
 ↓
Teacher Confirm
 ↓
Learning Evidence
 ↓
StudentProgress
```

---

# 82. 系统核心不变量

必须满足：

### 1. 学生隔离

学生只能访问自己的数据。

### 2. 原始提交不可变

任何 OCR、Vision、批改过程不能覆盖原始文件。

### 3. 已发布考试不可变

Published ExamVersion 永远固定。

### 4. 已发布题目版本不可变

QuestionVersion 一旦被考试引用不能修改。

### 5. 教师拥有最终评分权

AI 只能给建议。

### 6. LLM 可追踪

所有 LLM 生成结果必须能够追溯。

### 7. 知识库可版本化

知识点更新不能破坏历史学习数据。

### 8. 题库增量更新

不能因为一次 LLM 更新重新生成/覆盖整个题库。

### 9. AI 建议不是正式学习证据

只有教师确认后的结果才能进入正式 StudentProgress。

### 10. 所有重要操作可审计

---

# 83. MVP

第一阶段实现：

```text
Login
 ↓
Teacher
 ↓
Student
 ↓
Textbook / Chapter
 ↓
Knowledge Point
 ↓
LLM Question Generation
 ↓
Question Bank
 ↓
Assignment / Exam
 ↓
PDF Export
 ↓
Word Export
 ↓
Online Exam
 ↓
Paper Upload
 ↓
OCR
 ↓
AI Grading
 ↓
Teacher Confirm
 ↓
Student Archive
```

第二阶段：

```text
Knowledge Point Incremental Update
Question Bank Incremental Update
Scheduled LLM Jobs
Learning Analytics
```

第三阶段：

```text
自动发现知识缺口
自动生成候选题
自动题库维护
长期学习路径优化
```

---

# 84. Acceptance Criteria

系统验收至少包括：

1. 可以安装系统。
2. 可以创建默认教师 `yun`。
3. 默认密码来自 `.env`。
4. 首次登录必须修改密码。
5. 可以创建学生。
6. 可以创建班级。
7. 可以配置教材。
8. 可以配置章节。
9. 可以自动推断当前章节。
10. 教师可以手工覆盖章节。
11. 可以创建知识点。
12. 知识点支持版本。
13. 可以运行知识点 LLM 增量更新。
14. 增量更新产生 Candidate。
15. Candidate 可以审核。
16. 可以查看知识点 Diff。
17. 可以创建题目。
18. 题目支持 QuestionVersion。
19. 可以生成 A/B 两套题。
20. 生成结果为结构化 JSON。
21. 可以验证题目。
22. 可以进行重复检测。
23. 可以运行题库增量更新。
24. 题库更新不会覆盖旧题。
25. 可以查看题库更新 Diff。
26. 可以创建 Assignment。
27. 可以创建 Exam。
28. Exam 支持 ExamVersion。
29. 发布后 ExamVersion immutable。
30. 可以添加/删除/排序题目。
31. 可以设置分值。
32. 可以导出 PDF。
33. PDF 包含中文。
34. PDF 包含数学公式。
35. PDF 包含几何图形。
36. 可以导出 Word。
37. Word 可以继续编辑。
38. 可以创建学生在线考试。
39. 学生可以在线答题。
40. 支持数学 LaTeX。
41. 支持作文。
42. 支持证明题。
43. 支持图片答案。
44. 考试服务器端计时。
45. 答案自动保存。
46. 浏览器刷新可以恢复答案。
47. 网络恢复后可以同步答案。
48. 可以提交考试。
49. 超时可以自动提交。
50. 防止重复提交。
51. 可以上传 JPG/JPEG/PNG/WebP/PDF。
52. 原始文件 immutable。
53. 保存 SHA256。
54. 可以 OCR。
55. OCR 失败不会丢失原文件。
56. 可以手工输入答案。
57. AI 可以给出批改建议。
58. 教师可以修改 AI 建议。
59. 教师可以最终确认成绩。
60. 保存成绩修改历史。
61. 教师确认成绩进入学习档案。
62. 可以查看学生成绩趋势。
63. 可以查看知识点掌握度。
64. 学习数据可以作为下一轮出题输入。
65. 可以定时执行知识库 LLM 增量更新。
66. 可以定时执行题库 LLM 增量更新。
67. 所有 LLM Job 可以查看状态。
68. LLM 失败不会造成数据丢失。
69. 所有重要操作进入 Audit Log。
70. `.env`、`configure.json`、学生数据不会进入 Git。

---

# 85. Definition of Done

当以下闭环全部能够运行时，系统达到 MVP 完成：

```text
创建学生
    ↓
建立学习档案
    ↓
选择教材/章节
    ↓
建立知识点
    ↓
LLM 生成题目
    ↓
题目进入题库
    ↓
教师创建 Exam
    ↓
ExamVersion
    ↓
        ┌───────────────┐
        ↓               ↓
   在线考试          PDF/Word
        ↓               ↓
   StudentAnswer    纸质作答
        ↓               ↓
        │             OCR/Vision
        │               ↓
        └───────┬───────┘
                ↓
             AI Grading
                ↓
          Teacher Confirm
                ↓
        StudentProgress
                ↓
        Knowledge Analysis
                ↓
       ┌────────┴────────┐
       ↓                 ↓
Knowledge Update   Question Bank Update
       ↓                 ↓
       └────────┬────────┘
                ↓
             下一轮出题
```

---

# 86. 产品核心架构原则

整个系统围绕以下统一模型构建：

```text
Question
   ↓
QuestionVersion
   ↓
Assignment / Exam
   ↓
AssignmentVersion / ExamVersion
   ↓
ExamAttempt / Submission
   ↓
StudentAnswer
   ↓
AI Grading Suggestion
   ↓
Teacher Confirmed Grade
   ↓
Learning Evidence
   ↓
Student Progress
   ↓
Knowledge Point Analysis
   ↓
LLM Incremental Update
   ↓
Question Bank Incremental Update
   ↓
Next Generation
```

最终形成一个可以长期运行的：

> **Teacher + Student + Knowledge Base + Question Bank + LLM + Assessment + Learning Evidence 的持续学习系统。**

核心原则是：

> **LLM 负责生成、分析和提出更新候选；Validator 负责约束；版本系统负责稳定性；教师负责最终教育决策；学生的真实作答和教师确认结果负责形成学习证据。**
