import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'
import { useAuth } from '../auth.jsx'

export default function Dashboard() {
  const { user } = useAuth()
  const [stats, setStats] = useState(null)
  const [studentStats, setStudentStats] = useState(null)
  const [students, setStudents] = useState([])
  const [assignments, setAssignments] = useState([])
  const [weakStates, setWeakStates] = useState([])

  useEffect(() => {
    if (user?.role === 'student') {
      endpoints.studentDashboard().then(setStudentStats)
      endpoints.assignments({ status: 'graded' }).then(setAssignments)
    } else {
      Promise.all([
        endpoints.dashboard(),
        endpoints.students(),
        endpoints.assignments(),
        endpoints.weakStates(6).catch(() => []),
      ]).then(([s, st, a, weak]) => { setStats(s); setStudents(st); setAssignments(a); setWeakStates(weak) })
    }
  }, [user?.role])

  if (user?.role === 'student') return <StudentView stats={studentStats} assignments={assignments} />

  return (
    <div>
      <div className="row-between mb-4">
        <h1 style={{ margin: 0 }}>工作台</h1>
      </div>
      <div className="grid grid-4">
        <Stat label="学生总数" value={stats?.student_count ?? '—'} />
        <Stat label="进行中的作业" value={stats?.active_assignment_count ?? '—'} />
        <Stat label="待批改提交" value={stats?.pending_grading_count ?? '—'} />
        <Stat label="LLM 运行（7天）" value={stats?.recent_llm_runs ?? '—'} />
      </div>

      <Card title="需要关注的知识点（全部学生）" actions={<Link className="btn-ghost" to="/learning">进入学习闭环 →</Link>}>
        {weakStates.length === 0 ? (
          <Empty>暂无薄弱知识点数据，批改确认后自动生成</Empty>
        ) : (
          <table className="table">
            <thead>
              <tr><th>学生</th><th>知识点</th><th>掌握度</th><th>趋势</th><th>遗忘风险</th></tr>
            </thead>
            <tbody>
              {weakStates.map((w) => (
                <tr key={w.id}>
                  <td>{students.find((s) => s.id === w.student_id)?.name || `#${w.student_id}`}</td>
                  <td>{w.knowledge_point_name}</td>
                  <td>{Math.round(w.mastery_score * 100)}%</td>
                  <td>{w.trend === 'improving' ? '进步 ↗' : w.trend === 'declining' ? '下滑 ↘' : '稳定 →'}</td>
                  <td><span className={'badge ' + (w.decay_risk === 'HIGH' || w.decay_risk === 'CRITICAL' ? 'badge-warn' : 'badge-neutral')}>{w.decay_risk}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="最近学生">
        {students.length === 0 ? (
          <Empty>暂无学生</Empty>
        ) : (
          <table className="table">
            <thead>
              <tr><th>姓名</th><th>年级</th><th>教材</th><th>状态</th></tr>
            </thead>
            <tbody>
              {students.slice(0, 5).map(s => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.grade || '—'}</td>
                  <td>{s.textbook_version || '—'}</td>
                  <td>{s.is_active ? <span className="badge badge-success">活跃</span> : <span className="badge badge-neutral">停用</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="最近作业">
        {assignments.length === 0 ? (
          <Empty>暂无作业</Empty>
        ) : (
          <table className="table">
            <thead>
              <tr><th>标题</th><th>学生</th><th>状态</th><th>截止日期</th></tr>
            </thead>
            <tbody>
              {assignments.slice(0, 5).map(a => (
                <tr key={a.id}>
                  <td>{a.title}</td>
                  <td>{a.student_id}</td>
                  <td>{statusBadge(a.status)}</td>
                  <td>{a.due_date ? new Date(a.due_date).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}

function StudentView({ stats, assignments }) {
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>我的学习</h1>
      <div className="grid grid-4">
        <Stat label="待完成作业" value={stats?.pending_assignments ?? '—'} />
        <Stat label="已提交待批改" value={stats?.submitted_assignments ?? '—'} />
        <Stat label="已批改" value={stats?.graded_assignments ?? '—'} />
        <Stat label="平均分" value={stats ? stats.average_score : '—'} />
      </div>
      <Card title="最近成绩">
        {!stats || stats.recent_grades.length === 0 ? (
          <Empty>暂无成绩</Empty>
        ) : (
          <table className="table">
            <thead><tr><th>作业</th><th>提交时间</th><th>分数</th></tr></thead>
            <tbody>
              {stats.recent_grades.map((g, i) => (
                <tr key={i}>
                  <td>{g.title}</td>
                  <td>{new Date(g.submitted_at).toLocaleString()}</td>
                  <td>{g.score?.toFixed?.(1) ?? g.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <Card>
        <Link className="btn btn-primary" to="/assignments">去做作业</Link>
      </Card>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <Card>
      <div className="muted" style={{ fontSize: 12 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, marginTop: 6 }}>{value}</div>
    </Card>
  )
}

function statusBadge(s) {
  if (s === 'graded') return <span className="badge badge-success">已批改</span>
  if (s === 'submitted') return <span className="badge badge-warn">已提交</span>
  if (s === 'assigned') return <span className="badge badge-primary">已分配</span>
  if (s === 'cancelled') return <span className="badge badge-neutral">已取消</span>
  return <span className="badge badge-neutral">{s}</span>
}