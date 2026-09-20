import { useEffect, useMemo, useState } from 'react'
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
  const [selectedStudentId, setSelectedStudentId] = useState(null)
  const [parentView, setParentView] = useState(null)

  useEffect(() => {
    if (user?.role === 'student') {
      endpoints.studentDashboard().then(setStudentStats)
      endpoints.assignments({ status: 'graded' }).then(setAssignments)
      if (user.student_id) {
        endpoints.knowledgeStates(user.student_id).then(setWeakStates).catch(() => {})
      }
    } else {
      Promise.all([
        endpoints.dashboard(),
        endpoints.students(),
        endpoints.assignments(),
        endpoints.weakStates(6).catch(() => []),
      ]).then(([s, st, a, weak]) => { setStats(s); setStudents(st); setAssignments(a); setWeakStates(weak) })
    }
  }, [user?.role])

  // Auto-select the first student for the teacher parent view.
  useEffect(() => {
    if (user?.role !== 'student' && students.length && !selectedStudentId) {
      setSelectedStudentId(students[0].id)
    }
  }, [students, user?.role, selectedStudentId])

  useEffect(() => {
    if (!selectedStudentId) {
      setParentView(null)
      return
    }
    endpoints.parentDashboard(selectedStudentId).then(setParentView).catch(() => setParentView(null))
  }, [selectedStudentId])

  if (user?.role === 'student') return <StudentView stats={studentStats} assignments={assignments} states={weakStates} />

  return (
    <div>
      <div className="row-between mb-4">
        <h1 style={{ margin: 0 }}>工作台</h1>
        {students.length > 0 && (
          <select
            value={selectedStudentId ?? ''}
            onChange={(e) => setSelectedStudentId(Number(e.target.value))}
            className="select"
          >
            {students.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        )}
      </div>
      <div className="grid grid-4">
        <Stat label="学生总数" value={stats?.student_count ?? '—'} />
        <Stat label="进行中的作业" value={stats?.active_assignment_count ?? '—'} />
        <Stat label="待批改提交" value={stats?.pending_grading_count ?? '—'} />
        <Stat label="LLM 运行（7天）" value={stats?.recent_llm_runs ?? '—'} />
      </div>

      {parentView && <ParentDashboardView view={parentView} />}

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
              <tr><th>姓名</th><th>年级</th><th>学校</th><th>教材</th><th>状态</th></tr>
            </thead>
            <tbody>
              {students.slice(0, 5).map(s => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.grade || '—'}</td>
                  <td>{s.school || '—'}</td>
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

function ParentDashboardView({ view }) {
  const m = view.mastery_summary || {}
  return (
    <>
      <Card title={`${view.name} · 家长看板（PRD §13）`}>
        <div className="grid grid-3">
          <Stat label="当前目标" value={view.current_objective || '—'} />
          <Stat label="当前章节" value={view.current_chapter || '—'} />
          <Stat
            label="整体掌握"
            value={`${Math.round((m.overall || 0) * 100)}%`}
          />
        </div>
      </Card>

      <div className="grid grid-2">
        <Card title="主要薄弱点">
          {view.weak_points?.length ? (
            <ul style={{ paddingLeft: 16, margin: 0 }}>
              {view.weak_points.map((w, i) => (
                <li key={i} style={{ marginBottom: 8 }}>
                  <strong>{w.knowledge_point}</strong>
                  {' '}— 掌握度 {Math.round((w.mastery || 0) * 100)}%
                  <div className="muted" style={{ fontSize: 12 }}>{w.reason}</div>
                  {w.llm_reasoning && (
                    <div className="muted" style={{ fontSize: 12 }}>AI 解读：{w.llm_reasoning}</div>
                  )}
                </li>
              ))}
            </ul>
          ) : <Empty>暂无薄弱点</Empty>}
        </Card>

        <Card title="学习趋势（最近 10 次）">
          {view.learning_trend?.series?.length ? (
            <TrendMini series={view.learning_trend.series} />
          ) : <Empty>暂无评分记录</Empty>}
          <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
            平均分：{view.learning_trend?.average_recent ?? 0}
          </div>
        </Card>
      </div>

      <Card title="今日任务">
        {view.today_tasks?.length ? (
          <table className="table">
            <thead><tr><th>作业</th><th>截止</th><th>预计</th></tr></thead>
            <tbody>
              {view.today_tasks.map((t) => (
                <tr key={t.assignment_id}>
                  <td><Link to={`/assignments`}>{t.title}</Link></td>
                  <td>{t.due_date ? new Date(t.due_date).toLocaleDateString() : '—'}</td>
                  <td>{t.estimated_minutes ?? '—'} 分钟</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty>暂无今日任务</Empty>}
      </Card>

      <Card title="今日学习计划">
        {view.today_plan?.length ? (
          <ol style={{ paddingLeft: 18 }}>
            {view.today_plan.map((it, i) => (
              <li key={i} style={{ marginBottom: 6 }}>
                <strong>Day {it.day}</strong> · {it.intervention_type} · {it.knowledge_point}
                <div className="muted" style={{ fontSize: 12 }}>{it.description}</div>
              </li>
            ))}
          </ol>
        ) : <Empty>暂无学习计划</Empty>}
      </Card>

      <Card title={`待家长确认（${view.needs_parent_review?.length || 0}）`}>
        {view.needs_parent_review?.length ? (
          <table className="table">
            <thead><tr><th>作业</th><th>AI 建议分</th><th>置信度</th><th>提交时间</th></tr></thead>
            <tbody>
              {view.needs_parent_review.map((r) => (
                <tr key={r.submission_id}>
                  <td>{r.assignment_title}</td>
                  <td>{r.ai_suggested_score ?? '—'}</td>
                  <td>{r.ai_confidence != null ? Math.round(r.ai_confidence * 100) + '%' : '—'}</td>
                  <td>{new Date(r.submitted_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty>全部批改已完成 ✅</Empty>}
      </Card>

      <Card title="近期考试">
        {view.upcoming_exams?.length ? (
          <ul style={{ paddingLeft: 16 }}>
            {view.upcoming_exams.map((e) => (
              <li key={e.exam_id}>
                <strong>{e.title}</strong> · {e.duration_minutes} 分钟 · 满分 {e.total_score}
                <span className="muted"> · 已尝试 {e.attempts} 次</span>
              </li>
            ))}
          </ul>
        ) : <Empty>暂无安排</Empty>}
      </Card>
    </>
  )
}

function TrendMini({ series }) {
  const { max, min, w } = useMemo(() => {
    const values = series.map((p) => Number(p.score) || 0)
    return {
      max: Math.max(100, ...values),
      min: Math.min(0, ...values),
      w: Math.max(320, series.length * 30),
    }
  }, [series])
  const stepX = w / Math.max(1, series.length - 1)
  const points = series.map((p, i) => `${i * stepX},${100 - (Number(p.score) / max) * 100}`).join(' ')
  return (
    <svg width="100%" viewBox={`0 0 ${w} 100`} preserveAspectRatio="none" style={{ background: '#f8fafc', borderRadius: 6 }}>
      <polyline fill="none" stroke="#2563eb" strokeWidth="2" points={points} />
    </svg>
  )
}

function StudentView({ stats, assignments, states = [] }) {
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>我的学习</h1>
      <div className="grid grid-4">
        <Stat label="待完成作业" value={stats?.pending_assignments ?? '—'} />
        <Stat label="已提交待批改" value={stats?.submitted_assignments ?? '—'} />
        <Stat label="已批改" value={stats?.graded_assignments ?? '—'} />
        <Stat label="平均分" value={stats ? stats.average_score : '—'} />
      </div>
      {states.length > 0 && (
        <Card title="我的知识点掌握（PRD §14）">
          <table className="table">
            <thead><tr><th>知识点</th><th>掌握度</th><th>下次复习</th></tr></thead>
            <tbody>
              {states.map((st) => (
                <tr key={st.id}>
                  <td>{st.knowledge_point_name}</td>
                  <td>
                    <div className="mastery-bar">
                      <div className="mastery-fill" style={{ width: `${Math.round(st.mastery_score * 100)}%` }} />
                      <span>{Math.round(st.mastery_score * 100)}%</span>
                    </div>
                  </td>
                  <td className="muted">{st.next_review_at ? new Date(st.next_review_at).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
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
      <div style={{ fontSize: 22, fontWeight: 700, marginTop: 6, wordBreak: 'break-word' }}>{value}</div>
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