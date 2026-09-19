import { useEffect, useState } from 'react'
import { endpoints, runJob } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'

const CANDIDATE_LABELS = { ADD: '新增', MODIFY: '修改', REPLACE: '替换', DEPRECATE: '废弃' }

export default function QuestionBank() {
  const [items, setItems] = useState([])
  const [students, setStudents] = useState([])
  const [sets, setSets] = useState([])
  const [kp, setKp] = useState('')
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState(new Set())
  const [detail, setDetail] = useState(null) // {item, versions, similar}
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [assignStudent, setAssignStudent] = useState('')
  const [assignTitle, setAssignTitle] = useState('')
  const [fromSetId, setFromSetId] = useState('')
  const [analysis, setAnalysis] = useState(null)
  const [candidates, setCandidates] = useState([])

  function loadUpdates() {
    endpoints.bankUpdateAnalysis().then(setAnalysis).catch(() => {})
    endpoints.bankCandidates('pending').then(setCandidates).catch(() => {})
  }

  function load() {
    endpoints.bankList({ knowledge_point: kp || undefined, q: q || undefined })
      .then(setItems)
      .catch((e) => setError(e.message))
  }
  useEffect(() => {
    load()
    endpoints.students().then(setStudents).catch(() => {})
    endpoints.listSets().then(setSets).catch(() => {})
    loadUpdates()
  }, [])

  async function run(action, okMsg) {
    setBusy('work'); setError(''); setMsg('')
    try {
      await action()
      setMsg(okMsg)
      load()
      loadUpdates()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy('')
    }
  }

  async function openDetail(id) {
    try {
      const [item, versions, similar] = await Promise.all([
        endpoints.bankItem(id), endpoints.bankVersions(id), endpoints.bankSimilar(id),
      ])
      setDetail({ item, versions, similar: similar.results })
    } catch (e) { setError(e.message) }
  }

  async function assignSelected() {
    if (!selected.size || !assignStudent || !assignTitle) {
      setError('请选择题目、学生并填写作业标题'); return
    }
    await run(async () => {
      await endpoints.bankToAssignment({
        question_ids: [...selected],
        student_id: Number(assignStudent),
        title: assignTitle,
      })
      setSelected(new Set())
    }, '已从题库生成作业')
  }

  async function publishFromSet() {
    if (!fromSetId) { setError('请选择题集'); return }
    await run(() => endpoints.bankFromSet({ set_id: Number(fromSetId) }), '题集已发布到题库（重复题已跳过）')
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>题库</h1>
      {error && <div className="form-error mb-4">{error}</div>}
      {msg && <div className="badge badge-success mb-4">{msg}</div>}

      <Card title="从生成题集批量入库">
        <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
          <select value={fromSetId} onChange={(e) => setFromSetId(e.target.value)}>
            <option value="">选择题集…</option>
            {sets.map((s) => <option key={s.id} value={s.id}>{`题集 #${s.id}（${s.label}，${s.question_count} 题）`}</option>)}
          </select>
          <button className="btn" disabled={!!busy} onClick={publishFromSet}>发布到题库</button>
        </div>
      </Card>

      <Card
        title="题库更新（AI 增量维护，PRD §68）"
        actions={
          <button className="btn" disabled={!!busy}
                  onClick={() => run(
                    () => runJob('QUESTION_BANK_UPDATE', { batch_size: 3 }, { timeoutMs: 300000 }),
                    'AI 分析完成，请审核下方候选（入库前需家长确认）')}>
            AI 分析并生成候选
          </button>
        }
      >
        {analysis && (
          <div className="muted mb-2" style={{ fontSize: 13 }}>
            题库 {analysis.bank_size} 题 · 知识点覆盖 {analysis.covered_kp}/{analysis.kp_total} ·
            重复对 {analysis.duplicates.length} · 覆盖缺口 {analysis.gaps.length}
            {analysis.gaps.length > 0 && `（最缺：${analysis.gaps.slice(0, 3).map((g) => g.knowledge_point).join('、')}）`}
          </div>
        )}
        {candidates.length === 0 ? <Empty>暂无待审核候选</Empty> : (
          <table className="table">
            <thead><tr><th>类型</th><th>内容</th><th>依据</th><th>校验</th><th></th></tr></thead>
            <tbody>
              {candidates.map((c) => (
                <tr key={c.id}>
                  <td><span className={'badge ' + (c.candidate_type === 'ADD' ? 'badge-primary' : 'badge-warn')}>
                    {CANDIDATE_LABELS[c.candidate_type] || c.candidate_type}
                  </span></td>
                  <td style={{ maxWidth: 340 }}>
                    {c.candidate_type === 'ADD' ? (
                      <div>
                        <div style={{ whiteSpace: 'pre-wrap' }}>{c.payload.prompt}</div>
                        <div className="muted" style={{ fontSize: 12 }}>答：{c.payload.answer || '—'}</div>
                      </div>
                    ) : (
                      <div>废弃题目 #{c.target_bank_id}（{c.payload.reason}）</div>
                    )}
                  </td>
                  <td className="muted" style={{ fontSize: 12, maxWidth: 220 }}>{c.rationale}</td>
                  <td>
                    {c.duplicate_of_id
                      ? <span className="badge badge-warn">与 #{c.duplicate_of_id} 重复</span>
                      : c.validation_notes
                        ? <span className="badge badge-warn">{c.validation_notes}</span>
                        : <span className="badge badge-success">通过</span>}
                  </td>
                  <td className="right" style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn btn-primary" style={{ marginRight: 6 }} disabled={!!busy}
                            onClick={() => run(() => endpoints.bankApproveCandidate(c.id), '已应用到题库')}>
                      确认
                    </button>
                    <button className="btn-ghost" disabled={!!busy}
                            onClick={() => run(() => endpoints.bankRejectCandidate(c.id), '已拒绝')}>
                      拒绝
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card
        title={`题库题目（${items.length}）`}
        actions={
          <button className="btn-ghost" onClick={load}>刷新</button>
        }
      >
        <div className="row mb-2" style={{ flexWrap: 'wrap', gap: 8 }}>
          <input placeholder="知识点" value={kp} onChange={(e) => setKp(e.target.value)} />
          <input placeholder="题干搜索" value={q} onChange={(e) => setQ(e.target.value)} style={{ flex: 1, minWidth: 140 }} />
          <button className="btn" onClick={load}>筛选</button>
        </div>
        {items.length === 0 ? <Empty>题库为空。可在出题向导生成后批量入库。</Empty> : (
          <table className="table">
            <thead><tr><th></th><th>题干</th><th>知识点</th><th>难度 / 题型</th><th>v</th><th></th></tr></thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.id}>
                  <td>
                    <input type="checkbox" checked={selected.has(it.id)}
                           onChange={(e) => {
                             const next = new Set(selected)
                             if (e.target.checked) next.add(it.id); else next.delete(it.id)
                             setSelected(next)
                           }} />
                  </td>
                  <td style={{ maxWidth: 320 }}>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{it.prompt.slice(0, 90)}{it.prompt.length > 90 ? '…' : ''}</div>
                  </td>
                  <td>{(it.knowledge_points || []).map((k) => <span key={k} className="kp-chip">{k}</span>)}</td>
                  <td className="muted">{it.difficulty} / {it.question_type}</td>
                  <td className="muted">v{it.version}</td>
                  <td className="right" style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn-ghost" style={{ marginRight: 6 }} onClick={() => openDetail(it.id)}>详情</button>
                    <button className="btn-ghost" disabled={!!busy}
                            onClick={() => { if (confirm('废弃该题？')) run(() => endpoints.bankDeprecate(it.id), '已废弃') }}>
                      废弃
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="从选中题目布置作业">
        <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
          <span className="muted">已选 {selected.size} 题</span>
          <select value={assignStudent} onChange={(e) => setAssignStudent(e.target.value)}>
            <option value="">学生…</option>
            {students.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <input placeholder="作业标题" value={assignTitle} onChange={(e) => setAssignTitle(e.target.value)} style={{ flex: 1, minWidth: 160 }} />
          <button className="btn btn-primary" disabled={!!busy} onClick={assignSelected}>布置作业</button>
        </div>
      </Card>

      {detail && (
        <Card title={`题目 #${detail.item.id} 详情`} actions={<button className="btn-ghost" onClick={() => setDetail(null)}>关闭</button>}>
          <div className="prompt">{detail.item.prompt}</div>
          {detail.item.answer && <div className="muted mt-2">答案：{detail.item.answer}</div>}
          {detail.item.rubric && <div className="muted mt-2">评分标准：{detail.item.rubric}</div>}
          <div className="mt-2">
            <b>版本历史（发布后不可变，PRD §40）</b>
            {detail.versions.versions.map((v) => (
              <div key={v.version} className="muted" style={{ fontSize: 13 }}>
                v{v.version} · {v.change_note} · {new Date(v.published_at).toLocaleString()}
              </div>
            ))}
          </div>
          <div className="mt-2">
            <b>相似题（§41）</b>
            {detail.similar.length === 0 ? <div className="muted">暂无相似题</div> : (
              detail.similar.map((s) => (
                <div key={s.id} className="card" style={{ padding: 8, marginTop: 6 }}>
                  <div className="row-between">
                    <span>#{s.id} {s.prompt.slice(0, 60)}…</span>
                    <span className="badge badge-primary">相关度 {Math.round(s.score * 100)}%</span>
                  </div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    {s.relations.join(' · ')} — {(s.knowledge_points || []).join('、')}
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      )}
    </div>
  )
}
