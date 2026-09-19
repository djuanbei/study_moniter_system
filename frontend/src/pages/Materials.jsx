import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'

const TYPE_LABELS = {
  TEXTBOOK: '教材',
  TEXTBOOK_SECTION: '教材章节',
  EXERCISE_BOOK: '练习册',
  WORKSHEET: '练习卷',
  EXAM: '试卷',
  ANSWER_KEY: '答案',
  SOLUTION: '解析',
  PARENT_NOTE: '家长笔记',
  OTHER: '其他',
}

const STATUS_BADGES = {
  uploaded: <span className="badge badge-neutral">已上传</span>,
  analyzed: <span className="badge badge-warn">待确认</span>,
  published: <span className="badge badge-success">已发布</span>,
}

export default function Materials() {
  const [materials, setMaterials] = useState([])
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState(null)

  // upload form
  const [title, setTitle] = useState('')
  const [materialType, setMaterialType] = useState('TEXTBOOK')
  const [textbookVersion, setTextbookVersion] = useState('人教版')
  const [grade, setGrade] = useState('初一')
  const [semester, setSemester] = useState('')
  const [file, setFile] = useState(null)

  function load() {
    endpoints.materials().then(setMaterials).catch((e) => setError(e.message))
  }
  useEffect(() => { load() }, [])

  async function run(action, okMsg) {
    setBusy(action); setError(''); setMsg('')
    try {
      await action()
      setMsg(okMsg)
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy('')
    }
  }

  async function upload() {
    if (!file) { setError('请选择文件'); return }
    const form = new FormData()
    form.append('file', file)
    form.append('title', title || file.name)
    form.append('material_type', materialType)
    form.append('textbook_version', textbookVersion)
    form.append('grade', grade)
    if (semester) form.append('semester', semester)
    await run(() => endpoints.uploadMaterial(form), '已上传，点击「识别」提取章节')
    setTitle(''); setFile(null)
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>教材资料</h1>
      {error && <div className="form-error mb-4">{error}</div>}
      {msg && <div className="badge badge-success mb-4">{msg}</div>}

      <Card title="上传教材 / 学习资料（PDF、图片、DOCX）">
        <div className="row mb-2" style={{ flexWrap: 'wrap', gap: 8 }}>
          <input placeholder="标题" value={title} onChange={(e) => setTitle(e.target.value)} style={{ flex: 1, minWidth: 160 }} />
          <select value={materialType} onChange={(e) => setMaterialType(e.target.value)}>
            {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <input placeholder="教材版本" value={textbookVersion} onChange={(e) => setTextbookVersion(e.target.value)} style={{ width: 120 }} />
          <input placeholder="年级" value={grade} onChange={(e) => setGrade(e.target.value)} style={{ width: 100 }} />
          <select value={semester} onChange={(e) => setSemester(e.target.value)}>
            <option value="">学期</option>
            <option value="1">上学期</option>
            <option value="2">下学期</option>
          </select>
          <input type="file" accept="application/pdf,image/jpeg,image/png,image/webp,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                 onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <button className="btn btn-primary" disabled={!!busy || !file} onClick={upload}>上传</button>
        </div>
        <div className="muted" style={{ fontSize: 12 }}>
          上传后运行「识别」：OCR → AI 提取章节与知识点 → 家长确认后发布到章节管理，供出题与学习规划使用。
        </div>
      </Card>

      <Card title={`资料库（${materials.length}）`}>
        {materials.length === 0 ? <Empty>暂无资料</Empty> : (
          <table className="table">
            <thead><tr><th>标题</th><th>类型</th><th>教材 / 年级</th><th>状态</th><th></th></tr></thead>
            <tbody>
              {materials.map((m) => (
                <tr key={m.id}>
                  <td>
                    <a href={endpoints.materialFileUrl(m.id)} target="_blank" rel="noreferrer" style={{ marginRight: 6 }}>{m.title}</a>
                    {expanded === m.id && (
                      <div className="muted" style={{ fontSize: 12, maxWidth: 420, whiteSpace: 'pre-wrap' }}>
                        {(m.ocr_text || '').slice(0, 600) || '（无 OCR 文本）'}
                      </div>
                    )}
                    {expanded === m.id && (m.analysis_json?.chapters || []).length > 0 && (
                      <div className="card mt-2" style={{ padding: 8, fontSize: 13 }}>
                        <div className="muted" style={{ fontSize: 12 }}>
                          提取到 {m.analysis_json.chapters.length} 个章节（{m.analysis_json.extracted_by === 'llm' ? 'AI' : '规则'}）
                        </div>
                        {m.analysis_json.chapters.map((c, i) => (
                          <div key={i} style={{ marginTop: 4 }}>
                            <b>{c.title}</b>
                            <div className="muted">{(c.knowledge_points || []).join('、')}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </td>
                  <td>{TYPE_LABELS[m.material_type] || m.material_type}</td>
                  <td className="muted">{m.textbook_version || '—'} / {m.grade || '—'}</td>
                  <td>{STATUS_BADGES[m.status] || m.status}</td>
                  <td className="right" style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn" style={{ marginRight: 6 }} disabled={!!busy}
                            onClick={() => run(() => endpoints.analyzeMaterial(m.id), '识别完成，请核对章节后发布')}>
                      识别
                    </button>
                    {m.status === 'analyzed' && (
                      <button className="btn btn-primary" style={{ marginRight: 6 }} disabled={!!busy}
                              onClick={() => run(() => endpoints.publishMaterial(m.id), '已发布到章节管理')}>
                        确认发布
                      </button>
                    )}
                    <button className="btn-ghost" style={{ marginRight: 6 }}
                            onClick={() => setExpanded(expanded === m.id ? null : m.id)}>
                      {expanded === m.id ? '收起' : '详情'}
                    </button>
                    <button className="btn-ghost" disabled={!!busy}
                            onClick={() => { if (confirm('删除该资料记录？')) run(() => endpoints.deleteMaterial(m.id), '已删除') }}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="mt-2">
          <Link className="btn-ghost" to="/classes">前往章节管理 →</Link>
        </div>
      </Card>
    </div>
  )
}
