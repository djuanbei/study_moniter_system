import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { endpoints, runJob } from '../api.js'
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

const ERROR_OPTIONS = ['', ...Object.keys(ERROR_LABELS)]

export default function History() {
  const [materials, setMaterials] = useState([])
  const [students, setStudents] = useState([])
  const [assessments, setAssessments] = useState([])
  const [detail, setDetail] = useState(null)
  const [edits, setEdits] = useState({})
  const [materialId, setMaterialId] = useState('')
  const [studentId, setStudentId] = useState('')
  const [examTitle, setExamTitle] = useState('')
  const [examDate, setExamDate] = useState('')
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      endpoints.materials().catch(() => []),
      endpoints.students().catch(() => []),
    ]).then(([m, s]) => {
      setMaterials(m); setStudents(s)
      if (s.length) setStudentId(String(s[0].id))
    })
  }, [])

  function loadList(sid) {
    if (!sid) return
    endpoints.historyList(sid).then(setAssessments).catch(() => setAssessments([]))
  }
  useEffect(() => { loadList(studentId) }, [studentId])

  function setEdit(id, patch) {
    setEdits((prev) => ({ ...prev, [id]: { ...(prev[id] || {}), ...patch } }))
  }

  async function run(action, okMsg) {
    setBusy(action); setError(''); setMsg('')
    try {
      await action()
      setMsg(okMsg)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy('')
    }
  }

  async function analyze() {
    if (!materialId || !studentId || !examTitle) { setError('请选择资料、学生并填写试卷标题'); return }
    await run(async () => {
      const job = await runJob('HISTORY_ANALYSIS', {
        material_id: Number(materialId),
        student_id: Number(studentId),
        exam_title: examTitle,
        exam_date: examDate || null,
      }, { timeoutMs: 300000 })
      const a = await endpoints.historyDetail(job.result.assessment_id)
      setDetail(a)
      setEdits({})
      loadList(studentId)
    }, '识别完成，请核对每题后确认导入')
  }

  async function confirmAll() {
    if (!detail) return
    const items = detail.questions
      .filter((q) => q.status === 'candidate')
      .map((q) => {
        const e = edits[q.id] || {}
        return {
          id: q.id,
          knowledge_point_name: e.knowledge_point_name ?? q.knowledge_point_name ?? '',
          correct: e.correct ?? null,
          score: e.score ?? null,
          error_type: e.error_type ?? null,
        }
      })
    if (items.length === 0) { setError('没有待确认的题目'); return }
    await run(async () => {
      const a = await endpoints.confirmHistory(detail.id, items)
      setDetail(a)
      setMsg(`已导入为学习证据并更新知识点掌握度`)
      loadList(studentId)
    })
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>历史试卷导入</h1>
      {error && <div className="form-error mb-4">{error}</div>}
      {msg && <div className="badge badge-success mb-4">{msg}</div>}

      <Card title="第一步：选择已上传的试卷扫描件">
        <div className="muted mb-2" style={{ fontSize: 12 }}>
          先在 <Link to="/materials">教材资料</Link> 上传过去的试卷/作业扫描件（类型选「试卷」），然后在这里恢复题目与答案。
        </div>
        <div className="row mb-2" style={{ flexWrap: 'wrap', gap: 8 }}>
          <select value={materialId} onChange={(e) => setMaterialId(e.target.value)}>
            <option value="">选择资料…</option>
            {materials.map((m) => (
              <option key={m.id} value={m.id}>{`#${m.id} ${m.title}`}</option>
            ))}
          </select>
          <select value={studentId} onChange={(e) => setStudentId(e.target.value)}>
            {students.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <input placeholder="试卷标题" value={examTitle} onChange={(e) => setExamTitle(e.target.value)} style={{ width: 180 }} />
          <input type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
          <button className="btn btn-primary" disabled={!!busy} onClick={analyze}>
            {busy ? '识别中…' : '开始识别'}
          </button>
        </div>
      </Card>

      {detail && (
        <Card title={`第二步：家长核对 — ${detail.exam_title}（${detail.questions.length} 题）`}>
          <div className="muted mb-2" style={{ fontSize: 12 }}>
            每题请补全知识点（必填），可修正得分（0–100）和错误类型；确认后生成学习证据并更新掌握度。
          </div>
          <table className="table">
            <thead><tr><th>题</th><th>题干 / 学生答案</th><th>得分</th><th>知识点</th><th>错误类型</th><th>状态</th></tr></thead>
            <tbody>
              {detail.questions.map((q) => {
                const e = edits[q.id] || {}
                return (
                  <tr key={q.id}>
                    <td>{q.order}</td>
                    <td style={{ maxWidth: 320 }}>
                      <div style={{ whiteSpace: 'pre-wrap' }}>{q.question_text.slice(0, 160)}</div>
                      {q.student_answer && <div className="muted" style={{ fontSize: 12 }}>答：{q.student_answer.slice(0, 120)}</div>}
                      {q.annotation && <div className="muted" style={{ fontSize: 12 }}>批注：{q.annotation}</div>}
                    </td>
                    <td>
                      <input type="number" min="0" max="100" style={{ width: 70 }}
                             value={e.score ?? (q.score != null ? Math.round(q.score) : '')}
                             onChange={(ev) => setEdit(q.id, { score: ev.target.value === '' ? null : Number(ev.target.value) })} />
                    </td>
                    <td>
                      <input placeholder="必填" style={{ width: 120 }}
                             value={e.knowledge_point_name ?? q.knowledge_point_name ?? ''}
                             onChange={(ev) => setEdit(q.id, { knowledge_point_name: ev.target.value })} />
                    </td>
                    <td>
                      <select value={e.error_type ?? q.error_type ?? ''}
                              onChange={(ev) => setEdit(q.id, { error_type: ev.target.value || null })}>
                        {ERROR_OPTIONS.map((k) => <option key={k} value={k}>{k ? ERROR_LABELS[k] : '—'}</option>)}
                      </select>
                    </td>
                    <td>{q.status === 'confirmed'
                      ? <span className="badge badge-success">已导入</span>
                      : <span className="badge badge-warn">待确认</span>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div className="row mt-2">
            <button className="btn btn-primary" disabled={!!busy} onClick={confirmAll}>确认导入为学习证据</button>
          </div>
        </Card>
      )}

      <Card title={`导入记录（学生视角，${assessments.length}）`}>
        {assessments.length === 0 ? <Empty>暂无导入记录</Empty> : (
          <table className="table">
            <thead><tr><th>试卷</th><th>日期</th><th>题数</th><th>状态</th><th></th></tr></thead>
            <tbody>
              {assessments.map((a) => (
                <tr key={a.id}>
                  <td>{a.exam_title}</td>
                  <td>{a.exam_date || '—'}</td>
                  <td>{a.questions.length}</td>
                  <td>{a.status === 'confirmed'
                    ? <span className="badge badge-success">已确认</span>
                    : <span className="badge badge-warn">待确认</span>}</td>
                  <td className="right">
                    <button className="btn-ghost" onClick={() => setDetail(a)}>查看</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
