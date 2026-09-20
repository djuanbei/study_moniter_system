import { useEffect, useMemo, useState } from 'react'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'
import Diagram from '../components/Diagram.jsx'
import { SEMESTERS } from '../constants.js'

export default function QuestionWizard() {
  const [students, setStudents] = useState([])
  const [studentId, setStudentId] = useState('')
  const [count, setCount] = useState(6)
  const [difficulty, setDifficulty] = useState('medium')
  const [semester, setSemester] = useState('')
  const [chapterOptions, setChapterOptions] = useState([])
  const [selectedChapters, setSelectedChapters] = useState(new Set())
  const [customKps, setCustomKps] = useState('')
  const [types, setTypes] = useState([])
  const [notes, setNotes] = useState('')
  const [draft, setDraft] = useState(null)
  const [picked, setPicked] = useState({ A: new Set(), B: new Set() })
  const [persistMsg, setPersistMsg] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [chapterWarn, setChapterWarn] = useState('')

  useEffect(() => { endpoints.students().then(setStudents) }, [])

  const activeStudent = useMemo(
    () => students.find(s => s.id === Number(studentId)) || null,
    [students, studentId]
  )

  // Load chapters when student or semester changes.
  useEffect(() => {
    setChapterOptions([])
    setSelectedChapters(new Set())
    setChapterWarn('')
    if (!activeStudent) return
    const textbook = activeStudent.textbook_version
    const grade = activeStudent.grade
    if (!textbook || !grade) {
      setChapterWarn('该学生未设置教材/年级，无法加载章节知识点；可手动补充。')
      return
    }
    const sem = semester ? Number(semester) : (activeStudent.current_semester || undefined)
    endpoints.inferChapter(textbook, grade, sem)
      .then(data => {
        setChapterOptions(data.chapters || [])
        if ((data.chapters || []).length === 0) {
          setChapterWarn('未找到匹配的章节配置；可手动补充。')
        }
      })
      .catch(() => setChapterWarn('加载章节失败'))
  }, [activeStudent, semester])

  function toggleChapter(title) {
    setSelectedChapters(prev => {
      const next = new Set(prev)
      if (next.has(title)) next.delete(title); else next.add(title)
      return next
    })
  }

  async function generate() {
    if (!studentId) { setError('请选择学生'); return }
    setError(''); setLoading(true); setDraft(null); setPicked({ A: new Set(), B: new Set() }); setPersistMsg('')
    const customList = customKps.split(/[,，]/).map(s => s.trim()).filter(Boolean)
    const knowledge_points = [...selectedChapters, ...customList]
    try {
      const out = await endpoints.generateQuestions({
        student_id: Number(studentId),
        question_count: Number(count),
        difficulty,
        knowledge_points,
        question_types: types,
        semester: semester ? Number(semester) : undefined,
        requirements: notes,
      })
      setDraft(out)
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  function togglePick(label, qid) {
    setPicked(prev => {
      const next = new Set(prev[label])
      if (next.has(qid)) next.delete(qid); else next.add(qid)
      return { ...prev, [label]: next }
    })
  }

  async function persistAndAssign() {
    setError(''); setPersistMsg('')
    try {
      const pickedIds = [...picked.A, ...picked.B]
      if (pickedIds.length === 0) { setError('请至少选择一道题目'); return }
      const persisted = await endpoints.persistSets(draft)
      await endpoints.createFromMix({
        title: `${activeStudent?.name || ''} 的作业`,
        student_id: Number(studentId),
        source_set_ids: persisted.map(s => s.id),
        selected_question_ids: pickedIds,
      })
      setPersistMsg(`已创建作业，共 ${pickedIds.length} 题`)
    } catch (err) { setError(err.message) }
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>出题向导</h1>

      <Card title="生成参数">
        <div className="grid grid-3">
          <div><label>学生 *</label>
            <select value={studentId} onChange={e => setStudentId(e.target.value)}>
              <option value="">请选择</option>
              {students.map(s => <option key={s.id} value={s.id}>{s.name}（{s.grade || '—'}）</option>)}
            </select>
          </div>
          <div><label>题目数量</label><input type="number" min="1" max="30" value={count} onChange={e => setCount(e.target.value)} /></div>
          <div><label>难度</label>
            <select value={difficulty} onChange={e => setDifficulty(e.target.value)}>
              <option value="easy">简单</option>
              <option value="medium">中等</option>
              <option value="hard">困难</option>
            </select>
          </div>
          <div><label>学期</label>
            <select value={semester} onChange={e => setSemester(e.target.value)}>
              <option value="">自动（按学生档案）</option>
              {SEMESTERS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
          <div><label>题型偏好（可多选）</label>
            <select multiple value={types} onChange={e => setTypes([...e.target.selectedOptions].map(o => o.value))} style={{ height: 80 }}>
              <option value="composition">作文</option>
              <option value="reading_comprehension">阅读理解</option>
              <option value="expression_training">表达训练</option>
              <option value="thinking">数学思考题</option>
              <option value="week_long_thinking">数学长思考</option>
            </select>
          </div>
        </div>

        <div className="mt-4">
          <div className="row-between">
            <label style={{ marginBottom: 0 }}>知识点（按章节多选）</label>
            {chapterOptions.length > 0 && (
              <div className="row">
                <button type="button" className="btn-ghost" onClick={() => setSelectedChapters(new Set(chapterOptions))}>全选</button>
                <button type="button" className="btn-ghost" onClick={() => setSelectedChapters(new Set())}>清空</button>
                <span className="muted" style={{ marginLeft: 8 }}>已选 {selectedChapters.size} / {chapterOptions.length}</span>
              </div>
            )}
          </div>
          {chapterWarn
            ? <div className="muted mt-2">{chapterWarn}</div>
            : chapterOptions.length === 0
              ? <div className="empty">请先选择学生</div>
              : (
                <div className="mt-2" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
                  {chapterOptions.map(title => (
                    <label key={title} className="kp-chip" style={{ cursor: 'pointer', padding: '6px 10px', background: selectedChapters.has(title) ? 'var(--primary)' : 'var(--primary-soft)', color: selectedChapters.has(title) ? '#fff' : 'var(--primary)' }}>
                      <input type="checkbox" checked={selectedChapters.has(title)} onChange={() => toggleChapter(title)} style={{ marginRight: 6 }} />
                      {title}
                    </label>
                  ))}
                </div>
              )}
        </div>

        <div className="mt-2"><label>补充知识点（教材外，逗号分隔，可选）</label>
          <input value={customKps} onChange={e => setCustomKps(e.target.value)} placeholder="如：自定义拓展" />
        </div>

        <div className="mt-2"><label>教师附加要求（可选）</label><input value={notes} onChange={e => setNotes(e.target.value)} /></div>
        {error && <div className="form-error">{error}</div>}
        <div className="row mt-4">
          <button className="btn btn-primary" onClick={generate} disabled={loading}>
            {loading ? 'LLM 生成中…（可能需要数十秒）' : '生成 A/B 两套题目'}
          </button>
          {draft && <button className="btn" onClick={generate} disabled={loading}>重新生成</button>}
        </div>
      </Card>

      {draft && (
        <>
          <Card title={`课程规划：${draft.curriculum?.recommended_difficulty || difficulty}`}>
            <div className="muted">{draft.curriculum?.rationale}</div>
            <div className="mt-2">
              {(draft.curriculum?.knowledge_points || []).map(k => <span key={k} className="kp-chip">{k}</span>)}
            </div>
          </Card>
          {draft.sets?.map(set => (
            <Card key={set.label} title={`选项 ${set.label}（${set.questions.length} 题）`}
                  actions={<span className="muted">已选 {picked[set.label].size}</span>}>
              {set.validator_notes && set.validator_notes !== 'OK' && (
                <div className="badge badge-warn" style={{ marginBottom: 10 }}>校验：{set.validator_notes}</div>
              )}
              {set.questions.length === 0 ? <Empty>暂无题目</Empty> :
                set.questions.map(q => (
                  <div key={q.id || q.order} className="question-block">
                    <div className="row-between">
                      <div>
                        <span className="order">Q{q.order}</span>
                        <span className="badge badge-primary">{q.subject}</span>{' '}
                        <span className="badge badge-neutral">{q.qtype}</span>{' '}
                        <span className="badge badge-neutral">{q.difficulty}</span>{' '}
                        <span className="muted">约 {q.estimated_minutes} 分钟</span>
                      </div>
                      <label>
                        <input type="checkbox" checked={picked[set.label].has(q.id || q.order)}
                               onChange={() => togglePick(set.label, q.id || q.order)} />
                        {' '}选用
                      </label>
                    </div>
                    <div className="prompt mt-2">{q.prompt}</div>
                    <Diagram format={q.diagram_format} svg={q.diagram_svg} />
                    <div className="mt-2">
                      {(q.knowledge_points || []).map(k => <span key={k} className="kp-chip">{k}</span>)}
                    </div>
                    {q.rationale && (
                      <div className="card mt-2" style={{ background: 'var(--primary-soft)', fontSize: 13 }}>
                        <b>为什么生成这道题（PRD §37）</b>
                        <div style={{ marginTop: 4 }}>{q.rationale}</div>
                        {q.error_type_hint && (
                          <div className="muted" style={{ marginTop: 4, fontSize: 12 }}>
                            针对错误类型：{q.error_type_hint}
                          </div>
                        )}
                      </div>
                    )}
                    {q.rubric && (
                      <details className="mt-2">
                        <summary className="muted" style={{ cursor: 'pointer' }}>评分标准</summary>
                        <div className="prompt">{q.rubric}</div>
                      </details>
                    )}
                  </div>
                ))
              }
            </Card>
          ))}
          <Card>
            <div className="row">
              <button className="btn btn-primary" onClick={persistAndAssign}>保存选中题并创建作业</button>
              {persistMsg && <span className="badge badge-success">{persistMsg}</span>}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}