import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'
import { useAuth } from '../auth.jsx'

const STATUS_BADGES = {
  IN_PROGRESS: <span className="badge badge-primary">进行中</span>,
  SUBMITTED: <span className="badge badge-warn">已提交</span>,
  TIME_EXPIRED: <span className="badge badge-warn">已超时</span>,
  GRADING: <span className="badge badge-warn">批改中</span>,
  GRADED: <span className="badge badge-success">已出分</span>,
}

export default function Exams() {
  const { user } = useAuth()
  const [exams, setExams] = useState([])
  const [attempts, setAttempts] = useState([])
  const [students, setStudents] = useState([])
  const [questionSets, setQuestionSets] = useState([])
  const [error, setError] = useState('')

  // create form (teacher)
  const [setId, setSetId] = useState('')
  const [studentId, setStudentId] = useState('')
  const [title, setTitle] = useState('')
  const [duration, setDuration] = useState(30)

  function load() {
    endpoints.exams().then(async (list) => {
      setExams(list)
      if (user?.role === 'student' && list.length) {
        const at = await Promise.all(list.map((e) => endpoints.examAttempts(studentOf(e)).catch(() => [])))
        setAttempts(Object.fromEntries(list.map((e, i) => [e.id, (at[i] || [])[0]])))
      }
    }).catch((e) => setError(e.message))
  }

  function studentOf(e) { return e.student_id }

  useEffect(() => {
    load()
    if (user?.role === 'teacher') {
      endpoints.students().then(setStudents).catch(() => {})
      endpoints.listSets().then(setQuestionSets).catch(() => {})
    }
  }, [user?.role])

  async function createExam() {
    setError('')
    if (!setId || !studentId || !title) { setError('请选择题集、学生并填写标题'); return }
    try {
      await endpoints.createExam({
        student_id: Number(studentId),
        question_set_id: Number(setId),
        title,
        duration_minutes: Number(duration),
      })
      setTitle(''); load()
    } catch (e) { setError(e.message) }
  }

  if (user?.role === 'student') return <StudentExams exams={exams} attempts={attempts} />

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>在线考试</h1>
      {error && <div className="form-error mb-4">{error}</div>}

      <Card title="创建考试（从题集）">
        <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
          <input placeholder="考试标题" value={title} onChange={(e) => setTitle(e.target.value)} style={{ flex: 1, minWidth: 160 }} />
          <select value={setId} onChange={(e) => setSetId(e.target.value)}>
            <option value="">选择题集…</option>
            {questionSets.map((s) => (
              <option key={s.id} value={s.id}>{`题集 #${s.id}（${s.label}，${s.question_count} 题）`}</option>
            ))}
          </select>
          <select value={studentId} onChange={(e) => setStudentId(e.target.value)}>
            <option value="">学生…</option>
            {students.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <input type="number" min="1" max="300" value={duration} onChange={(e) => setDuration(e.target.value)} style={{ width: 80 }} title="时长（分钟）" />
          <button className="btn btn-primary" onClick={createExam}>创建考试</button>
        </div>
      </Card>

      <Card title={`考试列表（${exams.length}）`}>
        {exams.length === 0 ? <Empty>暂无考试</Empty> : (
          <table className="table">
            <thead><tr><th>标题</th><th>学生</th><th>时长</th><th>提交情况</th><th>分数</th><th></th></tr></thead>
            <tbody>
              {exams.map((e) => {
                const attemptsForExam = attempts.filter((a) => a.exam_id === e.id)
                const latest = attemptsForExam[0]
                return (
                  <tr key={e.id}>
                    <td>{e.title}</td>
                    <td>{students.find((s) => s.id === e.student_id)?.name || `#${e.student_id}`}</td>
                    <td>{e.duration_minutes} 分钟</td>
                    <td>{latest ? STATUS_BADGES[latest.status] : <span className="badge badge-neutral">未开始</span>}</td>
                    <td>{latest?.score != null ? latest.score : '—'}</td>
                    <td className="right">
                      {latest && ['SUBMITTED', 'TIME_EXPIRED', 'GRADING'].includes(latest.status) && (
                        <Link className="btn" to={`/exams/grading/${latest.id}`}>批改</Link>
                      )}
                      {latest?.status === 'GRADED' && <span className="muted">已完成</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}

function StudentExams({ exams, attempts }) {
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>我的考试</h1>
      <Card title={`考试（${exams.length}）`}>
        {exams.length === 0 ? <Empty>暂无考试</Empty> : (
          <table className="table">
            <thead><tr><th>标题</th><th>时长</th><th>状态</th><th></th></tr></thead>
            <tbody>
              {exams.map((e) => {
                const a = attempts[e.id]
                return (
                  <tr key={e.id}>
                    <td>{e.title}</td>
                    <td>{e.duration_minutes} 分钟</td>
                    <td>{a ? STATUS_BADGES[a.status] : <span className="badge badge-neutral">未开始</span>}</td>
                    <td className="right">
                      {!a || a.status === 'IN_PROGRESS' ? (
                        <Link className="btn btn-primary" to={`/exams/${e.id}/do`}>
                          {a ? '继续作答' : '开始考试'}
                        </Link>
                      ) : (
                        <span className="muted">{a.score != null ? `得分 ${a.score}` : '待批改'}</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
