import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'
import Diagram from '../components/Diagram.jsx'

export default function DoAssignment() {
  const { id } = useParams()
  const nav = useNavigate()
  const [data, setData] = useState(null)
  const [answers, setAnswers] = useState({})        // questionId -> string
  const [files, setFiles] = useState({})            // questionNumber -> File[]
  const [globalText, setGlobalText] = useState('')
  const [globalFiles, setGlobalFiles] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const fileInputs = useRef({})

  useEffect(() => {
    endpoints.assignmentDetail(Number(id))
      .then(d => { setData(d); setGlobalText('') })
      .catch(e => setError(e.message))
  }, [id])

  if (!data) return <Card><Empty>{error || '加载中…'}</Empty></Card>

  const { assignment, questions } = data

  function setAnswer(qid, val) { setAnswers(prev => ({ ...prev, [qid]: val })) }
  function addFiles(qNumber, list) {
    setFiles(prev => ({ ...prev, [qNumber]: [...(prev[qNumber] || []), ...list] }))
  }
  function removeFile(qNumber, idx) {
    setFiles(prev => ({ ...prev, [qNumber]: prev[qNumber].filter((_, i) => i !== idx) }))
  }

  async function submit() {
    setSubmitting(true); setError('')
    try {
      const form = new FormData()
      // Backend reads ONE text_answer field — combine global + per-question
      // answers here, otherwise extra fields are silently dropped.
      const parts = []
      if (globalText) parts.push(globalText)
      for (const q of questions) {
        if (answers[q.id]) parts.push(`Q${q.order}: ${answers[q.id]}`)
      }
      form.append('text_answer', parts.join('\n\n'))
      const allFiles = [...globalFiles]
      for (const q of questions) {
        for (const f of (files[q.order] || [])) allFiles.push(f)
      }
      for (const f of allFiles) form.append('files', f)
      const submission = await endpoints.submitAssignment(Number(id), form)
      nav(`/result/${submission.id}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>{assignment.title}</h1>
      {assignment.description && <Card><div className="muted">{assignment.description}</div></Card>}

      <Card title={`题目（共 ${questions.length} 题）`}>
        {questions.length === 0 ? <Empty>暂无题目</Empty> : questions.map(q => (
          <div key={q.id} className="question-block">
            <div>
              <span className="order">Q{q.order}</span>
              <span className="badge badge-primary">{q.subject}</span>{' '}
              <span className="badge badge-neutral">{q.qtype}</span>{' '}
              <span className="badge badge-neutral">{q.difficulty}</span>{' '}
              {q.estimated_minutes && <span className="muted">约 {q.estimated_minutes} 分钟</span>}
            </div>
            <div className="prompt mt-2">{q.prompt}</div>
            <Diagram format={q.diagram_format} svg={q.diagram_svg} />
            <div className="mt-2">
              {(q.knowledge_points || []).map(k => <span key={k} className="kp-chip">{k}</span>)}
            </div>
            <div className="mt-4">
              <label>作答（可选）</label>
              <textarea
                rows={4}
                value={answers[q.id] || ''}
                onChange={e => setAnswer(q.id, e.target.value)}
                placeholder="输入你的答案…"
              />
            </div>
            <div className="mt-2">
              <label>上传作答图片（可多张）</label>
              <input
                ref={el => (fileInputs.current[q.order] = el)}
                type="file"
                accept="image/jpeg,image/png,image/webp,application/pdf"
                multiple
                onChange={e => {
                  const list = Array.from(e.target.files || [])
                  if (list.length) addFiles(q.order, list)
                  e.target.value = ''
                }}
              />
              {(files[q.order] || []).length > 0 && (
                <div className="mt-2 row" style={{ flexWrap: 'wrap', gap: 8 }}>
                  {(files[q.order] || []).map((f, i) => (
                    <div key={i} className="badge badge-neutral">
                      {f.name} <button className="btn-ghost" onClick={() => removeFile(q.order, i)}>×</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </Card>

      <Card title="整体作答（可选）">
        <label>整体文字作答</label>
        <textarea rows={3} value={globalText} onChange={e => setGlobalText(e.target.value)} placeholder="可在最后统一说明..." />
        <div className="mt-2">
          <label>整体图片（可多张）</label>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            multiple
            onChange={e => {
              const list = Array.from(e.target.files || [])
              if (list.length) setGlobalFiles(prev => [...prev, ...list])
              e.target.value = ''
            }}
          />
          {globalFiles.length > 0 && (
            <div className="mt-2 row" style={{ flexWrap: 'wrap', gap: 8 }}>
              {globalFiles.map((f, i) => (
                <div key={i} className="badge badge-neutral">
                  {f.name} <button className="btn-ghost" onClick={() => setGlobalFiles(prev => prev.filter((_, x) => x !== i))}>×</button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {error && <div className="form-error">{error}</div>}
      <Card>
        <div className="row">
          <button className="btn btn-primary" onClick={submit} disabled={submitting}>
            {submitting ? '提交中…' : '提交作业'}
          </button>
          <button className="btn" onClick={() => nav('/assignments')} disabled={submitting}>取消</button>
        </div>
      </Card>
    </div>
  )
}