import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'
import Diagram from '../components/Diagram.jsx'

const ERROR_LABELS = {
  SIGN_ERROR: '符号错误', CONCEPT_MISUNDERSTANDING: '概念误解', FORMULA_ERROR: '公式错误',
  CALCULATION_ERROR: '计算错误', READING_ERROR: '审题错误', REASONING_GAP: '推理断层',
  PROOF_GAP: '证明缺口', DIAGRAM_ERROR: '图形错误', KNOWLEDGE_CONFUSION: '知识混淆',
  CARELESS_ERROR: '粗心错误', MODELING_ERROR: '建模错误',
}

export default function ExamGrading() {
  const { attemptId } = useParams()
  const [data, setData] = useState(null)
  const [scores, setScores] = useState({})
  const [errorTypes, setErrorTypes] = useState({})
  const [finalScore, setFinalScore] = useState('')
  const [feedback, setFeedback] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    endpoints.examAttemptDetail(Number(attemptId)).then((d) => {
      setData(d)
      const auto = (d.attempt.per_question || {}).per_question || {}
      const initScores = {}
      d.questions.forEach((q) => { initScores[q.id] = auto[q.id] ?? '' })
      setScores(initScores)
      if (d.attempt.score != null) setFinalScore(d.attempt.score)
      if (d.attempt.feedback) setFeedback(d.attempt.feedback)
    }).catch((e) => setError(e.message))
  }, [attemptId])

  async function confirm() {
    setError(''); setMsg('')
    if (finalScore === '') { setError('请填写总评分'); return }
    try {
      const per_question = Object.fromEntries(
        Object.entries(scores).map(([qid, s]) => {
          const et = errorTypes[qid]
          if (s === '' || s == null) return [qid, null]
          return [qid, { score: Number(s), error_type: et || null }]
        })
      )
      await endpoints.confirmExam(Number(attemptId), {
        final_score: Number(finalScore),
        feedback,
        per_question,
      })
      setMsg('已确认成绩并生成学习证据，知识点掌握度已更新')
    } catch (e) { setError(e.message) }
  }

  if (!data) return <Card><Empty>{error || '加载中…'}</Empty></Card>
  const { attempt, exam, questions } = data
  const answers = attempt.answers_json || {}
  const answerFor = (q) => answers[String(q.id)] || ''

  return (
    <div>
      <div className="row-between mb-4">
        <h1 style={{ margin: 0 }}>批改考试：{exam.title}</h1>
        <Link className="btn-ghost" to="/exams">← 返回</Link>
      </div>
      {error && <div className="form-error mb-4">{error}</div>}
      {msg && <div className="badge badge-success mb-4">{msg}</div>}
      <div className="muted mb-4" style={{ fontSize: 13 }}>
        状态：{attempt.status} · 提交方式：{attempt.submit_reason || '—'} ·
        自动评分（客观题）已填入，主观题请手动给分；总分请直接填写。
      </div>

      <Card title="逐题批改">
        {questions.map((q) => (
          <div key={q.id} className="card" style={{ padding: 12, marginBottom: 10 }}>
            <div>
              <span className="order">Q{q.order}</span>
              <span className="badge badge-neutral">{q.qtype}</span>{' '}
              <span className="badge badge-neutral">{q.difficulty}</span>
              {(q.knowledge_points || []).map((k) => <span key={k} className="kp-chip">{k}</span>)}
            </div>
            <div className="prompt mt-2">{q.prompt}</div>
            <Diagram format={q.diagram_format} svg={q.diagram_svg} />
            {q.answer_key && <div className="muted mt-2" style={{ fontSize: 13 }}>参考答案：{q.answer_key}</div>}
            <div className="mt-2">
              <label>学生答案</label>
              <div className="card" style={{ padding: 8 }}>{answerFor(q) || '（未作答）'}</div>
            </div>
            <div className="row mt-2" style={{ gap: 8 }}>
              <div>
                <label>得分（0–100）</label>
                <input type="number" min="0" max="100" style={{ width: 90 }}
                       value={scores[q.id] ?? ''}
                       onChange={(e) => setScores((p) => ({ ...p, [q.id]: e.target.value }))} />
              </div>
              <div>
                <label>错误类型</label>
                <select value={errorTypes[q.id] ?? ''}
                        onChange={(e) => setErrorTypes((p) => ({ ...p, [q.id]: e.target.value }))}>
                  <option value="">—</option>
                  {Object.entries(ERROR_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
            </div>
          </div>
        ))}
      </Card>

      <Card title="确认成绩">
        <div className="grid grid-2">
          <div>
            <label>总评分（0–100）</label>
            <input type="number" min="0" max="100" value={finalScore}
                   onChange={(e) => setFinalScore(e.target.value)} />
          </div>
          <div>
            <label>反馈（可选）</label>
            <input value={feedback} onChange={(e) => setFeedback(e.target.value)} />
          </div>
        </div>
        <div className="row mt-4">
          <button className="btn btn-primary" onClick={confirm}>确认成绩并生成学习证据</button>
        </div>
      </Card>
    </div>
  )
}
