import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'
import { useAuth } from '../auth.jsx'

export default function Assignments() {
  const { user } = useAuth()
  const [list, setList] = useState([])
  const [filter, setFilter] = useState('')
  const [students, setStudents] = useState([])
  const [submissionsByAssignment, setSubmissionsByAssignment] = useState({})
  const [error, setError] = useState('')

  function load() {
    endpoints.assignments(filter ? { status: filter } : {}).then(async (items) => {
      setList(items)
      if (user?.role !== 'student') {
        endpoints.students().then(setStudents).catch(() => {})
      }
      // For students, fetch latest submission per assignment so we can show "已批改 / 已提交 / 待完成".
      const ids = items.map(a => a.id)
      const submissions = await Promise.all(
        ids.map(id => endpoints.submissions({ assignment_id: id }).catch(() => []))
      )
      const map = {}
      ids.forEach((id, i) => { map[id] = (submissions[i] || [])[0] })
      setSubmissionsByAssignment(map)
    })
  }
  useEffect(() => { load() /* eslint-disable-line react-hooks/exhaustive-deps */ }, [filter])

  async function cancel(id) {
    if (!confirm('确认取消该作业？')) return
    try { await endpoints.cancelAssignment(id); load() } catch (e) { setError(e.message) }
  }

  if (user?.role === 'student') {
    return <StudentView list={list} submissions={submissionsByAssignment} />
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>作业管理</h1>
      <Card>
        <div className="row">
          <label style={{ marginBottom: 0 }}>状态：</label>
          <select value={filter} onChange={e => setFilter(e.target.value)} style={{ width: 180 }}>
            <option value="">全部</option>
            <option value="assigned">已分配</option>
            <option value="submitted">已提交</option>
            <option value="graded">已批改</option>
            <option value="cancelled">已取消</option>
          </select>
        </div>
      </Card>
      <Card title={`作业列表（${list.length}）`}>
        {list.length === 0 ? <Empty>暂无作业</Empty> : (
          <table className="table">
            <thead><tr><th>标题</th><th>学生</th><th>状态</th><th>截止</th><th></th></tr></thead>
            <tbody>
              {list.map(a => (
                <tr key={a.id}>
                  <td>{a.title}</td>
                  <td>{students.find(s => s.id === a.student_id)?.name || `#${a.student_id}`}</td>
                  <td>{badge(a.status)}</td>
                  <td>{a.due_date ? new Date(a.due_date).toLocaleString() : '—'}</td>
                  <td className="right">
                    {submissionsByAssignment[a.id]
                      ? <Link className="btn" to={`/grading/${submissionsByAssignment[a.id].id}`} style={{ marginRight: 8 }}>批改</Link>
                      : <span className="muted" style={{ marginRight: 8 }}>未提交</span>}
                    <a className="btn-ghost" style={{ marginRight: 8 }}
                       href={endpoints.paperPdfUrl(a.question_set_id, 'student')}
                       target="_blank" rel="noreferrer">导出试卷</a>
                    <a className="btn-ghost" style={{ marginRight: 8 }}
                       href={endpoints.paperDocxUrl(a.question_set_id, 'student')}
                       target="_blank" rel="noreferrer">DOCX</a>
                    {a.status === 'assigned' && <button className="btn btn-danger" onClick={() => cancel(a.id)}>取消</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {error && <div className="form-error">{error}</div>}
    </div>
  )
}

function StudentView({ list, submissions }) {
  const grouped = useMemo(() => {
    const pending = []
    const submitted = []
    const graded = []
    for (const a of list) {
      const sub = submissions[a.id]
      const row = { ...a, latest_submission: sub }
      if (a.status === 'cancelled') continue
      if ((sub && sub.status === 'graded') || a.status === 'graded') graded.push(row)
      else if (sub || a.status === 'submitted') submitted.push(row)
      else pending.push(row)
    }
    return { pending, submitted, graded }
  }, [list, submissions])

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>我的作业</h1>
      <Card title={`待完成（${grouped.pending.length}）`}>
        {grouped.pending.length === 0 ? <Empty>暂无待完成作业</Empty> : (
          <AssignmentTable rows={grouped.pending} mode="pending" />
        )}
      </Card>
      <Card title={`已提交 / 待批改（${grouped.submitted.length}）`}>
        {grouped.submitted.length === 0 ? <Empty>暂无</Empty> : (
          <AssignmentTable rows={grouped.submitted} mode="submitted" />
        )}
      </Card>
      <Card title={`已批改（${grouped.graded.length}）`}>
        {grouped.graded.length === 0 ? <Empty>暂无</Empty> : (
          <AssignmentTable rows={grouped.graded} mode="graded" />
        )}
      </Card>
    </div>
  )
}

function AssignmentTable({ rows, mode }) {
  return (
    <table className="table">
      <thead>
        <tr><th>标题</th><th>截止</th><th>题数</th><th></th></tr>
      </thead>
      <tbody>
        {rows.map(a => (
          <tr key={a.id}>
            <td>{a.title}</td>
            <td>{a.due_date ? new Date(a.due_date).toLocaleString() : '—'}</td>
            <td>{a.estimated_minutes ? `约 ${a.estimated_minutes} 分钟` : '—'}</td>
            <td className="right">
              {mode === 'pending' && <Link className="btn btn-primary" to={`/assignments/${a.id}/do`}>开始做题</Link>}
              {mode === 'submitted' && a.latest_submission && <Link className="btn" to={`/result/${a.latest_submission.id}`}>查看提交</Link>}
              {mode === 'graded' && a.latest_submission && <Link className="btn" to={`/result/${a.latest_submission.id}`}>查看成绩</Link>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function badge(s) {
  if (s === 'graded') return <span className="badge badge-success">已批改</span>
  if (s === 'submitted') return <span className="badge badge-warn">已提交</span>
  if (s === 'assigned') return <span className="badge badge-primary">已分配</span>
  if (s === 'cancelled') return <span className="badge badge-neutral">已取消</span>
  return <span className="badge badge-neutral">{s}</span>
}