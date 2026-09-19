import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'
import Diagram from '../components/Diagram.jsx'

const AUTOSAVE_MS = 15000 // PRD §75: 默认 15 秒

export default function ExamDo() {
  const { attemptId } = useParams()
  const [data, setData] = useState(null)
  const [answers, setAnswers] = useState({})
  const [savedAt, setSavedAt] = useState(null)
  const [remaining, setRemaining] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const dirtyRef = useRef(false)
  const answersRef = useRef({})

  useEffect(() => {
    endpoints.examAttemptDetail(Number(attemptId)).then((d) => {
      setData(d)
      setAnswers(d.attempt.answers_json || {})
      answersRef.current = d.attempt.answers_json || {}
    }).catch((e) => setError(e.message))
  }, [attemptId])

  const deadline = useMemo(() => (data ? new Date(data.attempt.deadline).getTime() : 0), [data])

  // Server-authoritative countdown (§74): browser timer is display-only.
  useEffect(() => {
    if (!deadline) return
    const t = setInterval(() => {
      const diff = deadline - Date.now()
      if (diff <= 0) { setRemaining('00:00'); autoExpire(); return }
      const m = Math.floor(diff / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      setRemaining(`${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`)
    }, 500)
    return () => clearInterval(t)
  }, [deadline])

  function setAnswer(qid, val) {
    setAnswers((prev) => { const next = { ...prev, [qid]: val }; answersRef.current = next; return next })
    dirtyRef.current = true
  }

  async function save() {
    if (!dirtyRef.current) return
    try {
      const a = await endpoints.saveExamAnswers(Number(attemptId), answersRef.current)
      setSavedAt(a.last_saved_at); dirtyRef.current = false
    } catch (e) { /* transient: next tick retries */ }
  }

  // Autosave every 15s (§75)
  useEffect(() => {
    const t = setInterval(save, AUTOSAVE_MS)
    return () => clearInterval(t)
  }, [])

  async function autoExpire() {
    // Past deadline: server flips to TIME_EXPIRED on the next save/submit.
    try { await endpoints.submitExam(Number(attemptId), 'time_expired') } catch {}
    setError('考试时间已到，系统已自动交卷')
  }

  async function submit() {
    setSubmitting(true); setError('')
    try {
      if (dirtyRef.current) await save()
      await endpoints.submitExam(Number(attemptId), 'manual')
      window.location.reload()
    } catch (e) { setError(e.message) } finally { setSubmitting(false) }
  }

  if (!data) return <Card><Empty>{error || '加载中…'}</Empty></Card>
  if (data.attempt.status === 'GRADED' || data.attempt.status === 'SUBMITTED' || data.attempt.status === 'TIME_EXPIRED') {
    return (
      <div>
        <h1 style={{ marginTop: 0 }}>{data.exam.title}</h1>
        <Card>
          <div>本考试已交卷（{data.attempt.status === 'GRADED' ? `得分 ${data.attempt.score}` : '待家长批改'}）。</div>
          <Link className="btn mt-2" to="/exams">返回我的考试</Link>
        </Card>
      </div>
    )
  }

  return (
    <div>
      <div className="row-between" style={{ position: 'sticky', top: 0, background: 'var(--bg, #fff)', zIndex: 5, padding: '8px 0' }}>
        <h1 style={{ margin: 0 }}>{data.exam.title}</h1>
        <div className="row" style={{ gap: 10 }}>
          <span className="badge badge-warn" style={{ fontSize: 16, padding: '4px 12px' }}>⏱ {remaining}</span>
          <span className="muted" style={{ fontSize: 12 }}>
            {savedAt ? `已自动保存 ${new Date(savedAt).toLocaleTimeString()}` : '自动保存每 15 秒'}
          </span>
          <button className="btn btn-primary" disabled={submitting} onClick={submit}>交卷</button>
        </div>
      </div>
      {error && <div className="form-error mt-2">{error}</div>}

      {data.questions.map((q) => (
        <Card key={q.id}>
          <div>
            <span className="order">Q{q.order}</span>
            <span className="badge badge-neutral">{q.qtype}</span>{' '}
            <span className="badge badge-neutral">{q.difficulty}</span>
          </div>
          <div className="prompt mt-2">{q.prompt}</div>
          <Diagram format={q.diagram_format} svg={q.diagram_svg} />
          <div className="mt-2">
            <label>你的答案</label>
            <textarea rows={3}
                      value={answers[q.id] || ''}
                      onChange={(e) => setAnswer(q.id, e.target.value)}
                      placeholder="输入答案…" />
          </div>
        </Card>
      ))}

      <Card>
        <button className="btn btn-primary" disabled={submitting} onClick={submit}>
          {submitting ? '交卷中…' : '交卷'}
        </button>
        <span className="muted ml-2" style={{ fontSize: 12 }}>答案每 15 秒自动保存到服务器，断网后重新打开可恢复</span>
      </Card>
    </div>
  )
}
