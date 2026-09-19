import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'

const ERROR_LABELS = {
  SIGN_ERROR: '符号错误',
  CONCEPT_MISUNDERSTANDING: '概念误解',
  FORMULA_ERROR: '公式错误',
  CALCULATION_ERROR: '计算错误',
  READING_ERROR: '审题错误',
  REASONING_GAP: '推理断层',
  PROOF_GAP: '证明缺口',
  DIAGRAM_ERROR: '图形错误',
  KNOWLEDGE_CONFUSION: '知识混淆',
  CARELESS_ERROR: '粗心错误',
  MODELING_ERROR: '建模错误',
}

function perQuestionList(raw) {
  if (Array.isArray(raw)) return raw
  if (raw && Array.isArray(raw.per_question)) return raw.per_question
  return []
}

export default function Grading() {
  const params = useParams()
  const submissionIdParam = params.submissionId

  const [submissions, setSubmissions] = useState([])
  const [active, setActive] = useState(null)
  const [grading, setGrading] = useState(null)
  const [score, setScore] = useState('')
  const [feedback, setFeedback] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  useEffect(() => { endpoints.submissions().then(setSubmissions) }, [])

  useEffect(() => {
    if (submissionIdParam) loadSubmission(Number(submissionIdParam))
  }, [submissionIdParam, submissions])

  async function loadSubmission(id) {
    const sub = submissions.find(s => s.id === id)
    if (sub) {
      setActive(sub); setScore(''); setFeedback(''); setMsg(''); setGrading(null); setError('')
      // restore an existing advisory grading if present
      try {
        const gs = await endpoints.gradingBySubmission(id)
        const latest = gs && gs.length ? gs[0] : null
        if (latest && latest.llm_suggested_score != null) {
          setGrading(latest)
          setScore(latest.llm_suggested_score)
          setFeedback(latest.llm_suggested_feedback ?? '')
          setMsg('已载入 LLM 建议，请核对后确认')
        }
      } catch {}
    }
  }

  async function suggest() {
    if (!active) return
    setError(''); setMsg('LLM 评分中…')
    try {
      const g = await endpoints.suggestGrading(active.id)
      setGrading(g)
      setScore(g.llm_suggested_score ?? '')
      setFeedback(g.llm_suggested_feedback ?? '')
      setMsg('已收到 LLM 建议，请核对后确认')
    } catch (err) { setError(err.message); setMsg('') }
  }

  async function confirm() {
    if (!active || score === '') { setError('请填写分数'); return }
    setError('')
    try {
      const g = await endpoints.confirmGrading({
        submission_id: active.id,
        final_score: Number(score),
        feedback,
      })
      setGrading(g)
      setMsg('已确认分数，已生成学习证据并更新知识点掌握度')
    } catch (err) { setError(err.message) }
  }

  const perQuestion = grading ? perQuestionList(grading.per_question_scores) : []

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>提交批改</h1>
      <div className="grid" style={{ gridTemplateColumns: '300px 1fr' }}>
        <Card title="待批改提交">
          {submissions.length === 0 ? <Empty>暂无提交</Empty> : (
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {submissions.map(s => (
                <li key={s.id}
                    onClick={() => loadSubmission(s.id)}
                    style={{ padding: '10px 12px', borderRadius: 8, cursor: 'pointer',
                             background: active?.id === s.id ? 'var(--primary-soft)' : 'transparent',
                             color: active?.id === s.id ? 'var(--primary)' : 'inherit' }}>
                  <div style={{ fontWeight: 500 }}>提交 #{s.id}</div>
                  <div className="muted" style={{ fontSize: 12 }}>作业 #{s.assignment_id} · {new Date(s.submitted_at).toLocaleString()}</div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div>
          {!active ? <Card><Empty>请从左侧选择一份提交</Empty></Card> : (
            <>
              <Card title={`提交 #${active.id} · 作业 #${active.assignment_id}`}
                    actions={<button className="btn" onClick={suggest}>获取 LLM 评分建议</button>}>
                <div className="muted">提交时间：{new Date(active.submitted_at).toLocaleString()}</div>
                {active.text_answer && (
                  <div className="mt-4">
                    <label>学生文字答案</label>
                    <div className="card">{active.text_answer}</div>
                  </div>
                )}
                <div className="mt-4">
                  <label>提交图片</label>
                  {active.images?.length === 0 && <Empty>无</Empty>}
                  <div className="grid grid-3 mt-2">
                    {active.images?.map(img => (
                      <div key={img.id} className="card" style={{ padding: 8 }}>
                        <div className="muted" style={{ fontSize: 12 }}>题号 {img.question_number ?? '—'}</div>
                        <img src={img.url} alt={img.filename} style={{ width: '100%', borderRadius: 8, marginTop: 4 }} />
                        <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>{img.sha256.slice(0, 12)}…</div>
                      </div>
                    ))}
                  </div>
                </div>
                {active.ocr_text && (
                  <details className="mt-4">
                    <summary className="muted" style={{ cursor: 'pointer' }}>OCR 文本</summary>
                    <div className="prompt">{active.ocr_text}</div>
                  </details>
                )}
              </Card>

              <Card title="确认分数">
                {grading && (
                  <div className="card" style={{ padding: 12, background: 'var(--primary-soft)', marginBottom: 12 }}>
                    <div className="row-between">
                      <div><b>LLM 建议分数：</b>{grading.llm_suggested_score ?? '—'}</div>
                      <div className="row" style={{ gap: 6 }}>
                        {grading.llm_confidence != null && (
                          <span className={'badge ' + (grading.llm_confidence >= 0.8 ? 'badge-success' : 'badge-warn')}>
                            置信度 {Math.round(grading.llm_confidence * 100)}%
                          </span>
                        )}
                        <span className={'badge ' + (grading.needs_review ? 'badge-warn' : 'badge-success')}>
                          {grading.needs_review ? '需要家长确认' : 'AI 高置信建议'}
                        </span>
                      </div>
                    </div>
                    {grading.llm_knowledge_mastery && (
                      <div className="mt-2">
                        <div className="muted" style={{ fontSize: 12 }}>知识点掌握度：</div>
                        {Object.entries(grading.llm_knowledge_mastery).map(([k, v]) => (
                          <div key={k} className="muted">{k}：{Math.round(v * 100)}%</div>
                        ))}
                      </div>
                    )}
                    {perQuestion.length > 0 && (
                      <div className="mt-2">
                        <div className="muted" style={{ fontSize: 12 }}>逐题分析：</div>
                        <table className="table">
                          <thead><tr><th>题</th><th>建议分</th><th>错误类型</th><th>置信度</th></tr></thead>
                          <tbody>
                            {perQuestion.map((q, i) => (
                              <tr key={i}>
                                <td>{q.order}</td>
                                <td>{q.score ?? '—'}</td>
                                <td>{q.error_type ? <span className="badge badge-warn">{ERROR_LABELS[q.error_type] || q.error_type}</span> : '—'}</td>
                                <td>{q.confidence != null ? `${Math.round(q.confidence * 100)}%` : '—'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
                <div className="grid grid-2">
                  <div><label>最终分数（0–100）</label>
                    <input type="number" min="0" max="100" value={score} onChange={e => setScore(e.target.value)} />
                  </div>
                </div>
                <div className="mt-2"><label>反馈</label>
                  <textarea rows={5} value={feedback} onChange={e => setFeedback(e.target.value)} />
                </div>
                {error && <div className="form-error">{error}</div>}
                {msg && <div className="badge badge-success mt-2">{msg}</div>}
                <div className="row mt-4">
                  <button className="btn btn-primary" onClick={confirm}>确认分数并生成学习证据</button>
                  {grading && grading.llm_suggested_score != null && (
                    <button className="btn" onClick={() => {
                      setScore(grading.llm_suggested_score)
                      setFeedback(grading.llm_suggested_feedback ?? '')
                    }}>接受 AI 建议</button>
                  )}
                </div>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  )
}