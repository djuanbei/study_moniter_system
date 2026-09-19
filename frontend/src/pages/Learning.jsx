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

const INTERVENTION_LABELS = {
  EXPLANATION: '讲解',
  EXAMPLE: '例题',
  PRACTICE: '练习',
  REVIEW: '复习',
  QUIZ: '测验',
  EXAM: '考试',
  REFLECTION: '反思',
}

export default function Learning() {
  const [students, setStudents] = useState([])
  const [studentId, setStudentId] = useState(null)
  const [states, setStates] = useState([])
  const [objectives, setObjectives] = useState([])
  const [diagnosis, setDiagnosis] = useState(null)
  const [plans, setPlans] = useState([])
  const [report, setReport] = useState(null)
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  // objective form
  const [objDesc, setObjDesc] = useState('')
  const [objTarget, setObjTarget] = useState(0.8)
  const [objKp, setObjKp] = useState('')
  const [objPriority, setObjPriority] = useState(1)

  // parent feedback form
  const [fbKp, setFbKp] = useState('')
  const [fbObs, setFbObs] = useState('understood')
  const [fbComment, setFbComment] = useState('')

  useEffect(() => {
    endpoints.students().then((list) => {
      setStudents(list)
      if (list.length) setStudentId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (!studentId) return
    setMsg(''); setError('')
    Promise.all([
      endpoints.knowledgeStates(studentId),
      endpoints.learningObjectives(studentId),
      endpoints.diagnosis(studentId),
      endpoints.learningPlans(studentId),
      endpoints.learningReport(studentId, 7).catch(() => null),
    ])
      .then(([st, ob, dg, pl, rp]) => {
        setStates(st); setObjectives(ob); setDiagnosis(dg); setPlans(pl); setReport(rp)
      })
      .catch((e) => setError(e.message))
  }, [studentId])

  async function run(action, okMsg) {
    setBusy(action); setError(''); setMsg('')
    try {
      await action()
      setMsg(okMsg)
      const [st, ob, dg, pl, rp] = await Promise.all([
        endpoints.knowledgeStates(studentId),
        endpoints.learningObjectives(studentId),
        endpoints.diagnosis(studentId),
        endpoints.learningPlans(studentId),
        endpoints.learningReport(studentId, 7).catch(() => null),
      ])
      setStates(st); setObjectives(ob); setDiagnosis(dg); setPlans(pl); setReport(rp)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy('')
    }
  }

  const student = students.find((s) => s.id === studentId)
  const currentPlan = plans.find((p) => p.status === 'approved') || plans.find((p) => p.status === 'draft')

  return (
    <div>
      <div className="row-between mb-4">
        <h1 style={{ margin: 0 }}>学习闭环</h1>
        <div>
          <select value={studentId ?? ''} onChange={(e) => setStudentId(Number(e.target.value))}>
            {students.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
      </div>
      {error && <div className="form-error mb-4">{error}</div>}
      {msg && <div className="badge badge-success mb-4">{msg}</div>}
      {!studentId ? <Card><Empty>请先创建学生</Empty></Card> : (
        <>
          <div className="grid grid-2">
            <Card title="知识点掌握（知识状态）">
              {states.length === 0 ? <Empty>暂无数据，完成一次批改确认后自动生成</Empty> : (
                <table className="table">
                  <thead>
                    <tr><th>知识点</th><th>掌握度</th><th>趋势</th><th>遗忘风险</th><th>证据</th></tr>
                  </thead>
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
                        <td>{trendBadge(st.trend)}</td>
                        <td>{decayBadge(st.decay_risk)}</td>
                        <td className="muted">{st.evidence_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>

            <Card title="学习诊断（AI 优先级）">
              {!diagnosis || diagnosis.priorities.length === 0 ? (
                <Empty>暂无薄弱点，状态良好</Empty>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {diagnosis.priorities.map((p) => (
                    <li key={p.rank} className="card" style={{ padding: 10, marginBottom: 8 }}>
                      <div className="row-between">
                        <b>Priority {p.rank}：{p.knowledge_point}</b>
                        <span className="muted">{Math.round(p.mastery * 100)}%</span>
                      </div>
                      <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{p.reason}</div>
                      {p.recent_errors?.length > 0 && (
                        <div className="mt-2">
                          {p.recent_errors.map((e, i) => (
                            <span key={i} className="badge badge-warn" style={{ marginRight: 4 }}>
                              {ERROR_LABELS[e] || e}
                            </span>
                          ))}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <Card
            title="学习计划"
            actions={
              <div className="row" style={{ gap: 8 }}>
                <button className="btn" disabled={!!busy}
                        onClick={() => run(
                          () => runJob('LEARNING_PLAN_GENERATION', { student_id: studentId }),
                          'AI 已生成新的学习计划（草稿），请审核')}>
                  生成 AI 学习计划
                </button>
                <button className="btn" disabled={!!busy}
                        onClick={() => run(() => endpoints.syncKnowledgePoints(), '知识点已同步')}>
                  同步知识点
                </button>
              </div>
            }
          >
            {!currentPlan ? <Empty>还没有学习计划，点击「生成 AI 学习计划」</Empty> : (
              <div>
                <div className="row-between mb-2">
                  <div><b>{currentPlan.title}</b> {planBadge(currentPlan.status)} <span className="muted">({currentPlan.generated_by === 'ai' ? 'AI 生成' : '规则生成'})</span></div>
                  <div className="row" style={{ gap: 8 }}>
                    {currentPlan.status === 'draft' && (
                      <button className="btn btn-primary" disabled={!!busy}
                              onClick={() => run(() => endpoints.approvePlan(currentPlan.id), '计划已确认')}>
                        确认学习计划
                      </button>
                    )}
                    <button className="btn-ghost" disabled={!!busy}
                            onClick={() => run(() => endpoints.cancelPlan(currentPlan.id), '计划已取消')}>
                      取消
                    </button>
                  </div>
                </div>
                {currentPlan.summary && <div className="muted mb-2">{currentPlan.summary}</div>}
                <table className="table">
                  <thead>
                    <tr><th>天</th><th>类型</th><th>任务</th><th>题量</th><th>状态</th><th></th></tr>
                  </thead>
                  <tbody>
                    {currentPlan.items.map((item) => (
                      <tr key={item.id}>
                        <td>Day {item.day}</td>
                        <td><span className="badge badge-primary">{INTERVENTION_LABELS[item.intervention_type] || item.intervention_type}</span></td>
                        <td>
                          {item.description}
                          {item.rationale && <div className="muted" style={{ fontSize: 12 }}>{item.rationale}</div>}
                        </td>
                        <td>{item.question_count || '—'}</td>
                        <td>{itemStatusBadge(item.status)}</td>
                        <td>
                          {item.question_count > 0 && item.status === 'pending' && currentPlan.status === 'approved' && (
                            <button className="btn" disabled={!!busy}
                                    onClick={() => run(() => endpoints.assignPlanItem(currentPlan.id, item.id), '已生成作业，学生可在「我的作业」中查看')}>
                              生成作业
                            </button>
                          )}
                          {item.assignment_id && (
                            <Link to="/assignments" className="muted">作业 #{item.assignment_id}</Link>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title="本周学习报告（近 7 天）">
            {!report ? <Empty>暂无数据</Empty> : (
              <div className="grid grid-2">
                <div>
                  <div className="muted" style={{ fontSize: 12 }}>学习证据 / 正确率</div>
                  <div style={{ fontSize: 20, fontWeight: 700 }}>
                    {report.evidence_count} 条 {report.accuracy != null ? `· ${Math.round(report.accuracy * 100)}%` : ''}
                  </div>
                  <div className="muted mt-2" style={{ fontSize: 12 }}>任务完成率</div>
                  <div style={{ fontSize: 20, fontWeight: 700 }}>
                    {report.completion_rate != null ? `${Math.round(report.completion_rate * 100)}%` : '—'}
                    <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>（批改 {report.graded_count} / 布置 {report.assigned_count}）</span>
                  </div>
                  {Object.keys(report.error_types || {}).length > 0 && (
                    <div className="mt-2">
                      <div className="muted" style={{ fontSize: 12 }}>主要错误：</div>
                      {Object.entries(report.error_types).map(([k, v]) => (
                        <span key={k} className="badge badge-warn" style={{ marginRight: 4 }}>
                          {ERROR_LABELS[k] || k} ×{v}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div>
                  <div className="muted" style={{ fontSize: 12 }}>主要进步</div>
                  {report.improving?.length === 0 && <div className="muted">—</div>}
                  {report.improving?.map((c) => (
                    <div key={c.knowledge_point}>{c.knowledge_point} <span className="badge badge-success">+{Math.round(c.delta * 100)}%</span></div>
                  ))}
                  <div className="muted mt-2" style={{ fontSize: 12 }}>仍在下滑</div>
                  {report.declining?.length === 0 && <div className="muted">—</div>}
                  {report.declining?.map((c) => (
                    <div key={c.knowledge_point}>{c.knowledge_point} <span className="badge badge-warn">{Math.round(c.delta * 100)}%</span></div>
                  ))}
                  {report.priorities?.length > 0 && (
                    <div className="muted mt-2" style={{ fontSize: 12 }}>
                      下周建议关注：{report.priorities.map((p) => p.knowledge_point).join('、')}
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>

          <div className="grid grid-2">
            <Card title="学习目标">
              <div className="row mb-2" style={{ flexWrap: 'wrap', gap: 8 }}>
                <input placeholder="目标描述" value={objDesc} onChange={(e) => setObjDesc(e.target.value)} style={{ flex: 1, minWidth: 160 }} />
                <input placeholder="知识点" value={objKp} onChange={(e) => setObjKp(e.target.value)} list="kp-list" />
                <datalist id="kp-list">
                  {states.map((st) => <option key={st.id} value={st.knowledge_point_name} />)}
                </datalist>
                <select value={objPriority} onChange={(e) => setObjPriority(Number(e.target.value))}>
                  <option value={1}>高优先</option>
                  <option value={2}>中优先</option>
                  <option value={3}>低优先</option>
                </select>
                <select value={objTarget} onChange={(e) => setObjTarget(Number(e.target.value))}>
                  <option value={0.6}>目标 60%</option>
                  <option value={0.8}>目标 80%</option>
                  <option value={0.9}>目标 90%</option>
                </select>
                <button className="btn btn-primary" disabled={!!busy || !objDesc}
                        onClick={() => run(() => endpoints.createObjective({
                          student_id: studentId,
                          description: objDesc,
                          knowledge_point_name: objKp || null,
                          target_mastery: objTarget,
                          priority: objPriority,
                        }), '目标已添加').then(() => setObjDesc(''))}>
                  添加目标
                </button>
              </div>
              {objectives.length === 0 ? <Empty>暂无学习目标</Empty> : (
                <table className="table">
                  <thead><tr><th>目标</th><th>当前 / 目标</th><th>优先级</th><th>状态</th></tr></thead>
                  <tbody>
                    {objectives.map((o) => (
                      <tr key={o.id}>
                        <td>{o.description}{o.knowledge_point_name ? <div className="muted" style={{ fontSize: 12 }}>{o.knowledge_point_name}</div> : null}</td>
                        <td>{Math.round(o.current_mastery * 100)}% → {Math.round(o.target_mastery * 100)}%</td>
                        <td>{o.priority === 1 ? '高' : o.priority === 2 ? '中' : '低'}</td>
                        <td>{o.status === 'active' ? <span className="badge badge-primary">进行中</span> : <span className="badge badge-neutral">{o.status}</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>

            <Card title="家长观察（成为学习证据）">
              <div className="row mb-2" style={{ flexWrap: 'wrap', gap: 8 }}>
                <input placeholder="知识点" value={fbKp} onChange={(e) => setFbKp(e.target.value)} list="kp-list" style={{ flex: 1, minWidth: 140 }} />
                <select value={fbObs} onChange={(e) => setFbObs(e.target.value)}>
                  <option value="understood">已理解</option>
                  <option value="not_understood">不理解</option>
                  <option value="careless">粗心（非知识问题）</option>
                  <option value="out_of_scope">超出当前范围</option>
                </select>
              </div>
              <textarea rows={2} placeholder="备注（选填）" value={fbComment} onChange={(e) => setFbComment(e.target.value)} />
              <div className="mt-2">
                <button className="btn btn-primary" disabled={!!busy || !fbKp}
                        onClick={() => run(() => endpoints.createEvidence({
                          student_id: studentId,
                          knowledge_point_name: fbKp,
                          observation: fbObs,
                          comment: fbComment || null,
                        }), '家长观察已记录').then(() => { setFbKp(''); setFbComment('') })}>
                  记录观察
                </button>
              </div>
              <div className="muted mt-2" style={{ fontSize: 12 }}>
                「不理解」会降低对应知识点掌握度，「已理解」会提升，「粗心」影响很小，「超出范围」仅记录。
              </div>
              {student && (
                <div className="card mt-2" style={{ padding: 10, background: 'var(--primary-soft)' }}>
                  <div className="muted" style={{ fontSize: 12 }}>当前薄弱点（同步至出题向导）</div>
                  <div>{(student.weak_points?.length ? student.weak_points.join('、') : '暂无')}</div>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

function trendBadge(t) {
  if (t === 'improving') return <span className="badge badge-success">进步 ↗</span>
  if (t === 'declining') return <span className="badge badge-warn">下滑 ↘</span>
  return <span className="badge badge-neutral">稳定 →</span>
}

function decayBadge(d) {
  if (d === 'CRITICAL') return <span className="badge badge-warn">高（需复习）</span>
  if (d === 'HIGH') return <span className="badge badge-warn">较高</span>
  if (d === 'MEDIUM') return <span className="badge badge-neutral">中</span>
  return <span className="badge badge-success">低</span>
}

function planBadge(s) {
  if (s === 'draft') return <span className="badge badge-warn">待家长确认</span>
  if (s === 'approved') return <span className="badge badge-success">已确认</span>
  if (s === 'completed') return <span className="badge badge-success">已完成</span>
  return <span className="badge badge-neutral">已取消</span>
}

function itemStatusBadge(s) {
  if (s === 'pending') return <span className="badge badge-neutral">待执行</span>
  if (s === 'assigned') return <span className="badge badge-primary">已布置</span>
  if (s === 'done') return <span className="badge badge-success">已完成</span>
  return <span className="badge badge-neutral">{s}</span>
}
