import { useEffect, useState } from 'react'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'
import { GRADES, SEMESTERS } from '../constants.js'

const EMPTY = {
  name: '', grade: '', class_id: '', textbook_version: '',
  current_semester: '', weak_points: '', strengths: '', notes: '', parent_contact: '',
}

export default function Students() {
  const [list, setList] = useState([])
  const [classes, setClasses] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState('')
  const [chapterHint, setChapterHint] = useState('')

  function load() {
    Promise.all([endpoints.students(), endpoints.classes()])
      .then(([s, c]) => { setList(s); setClasses(c) })
  }
  useEffect(load, [])

  async function infer() {
    if (!form.textbook_version || !form.grade) {
      setChapterHint('')
      return
    }
    try {
      const sem = form.current_semester ? Number(form.current_semester) : undefined
      const data = await endpoints.inferChapter(form.textbook_version, form.grade, sem)
      setChapterHint(data.suggestion?.title ? `推断建议章节：${data.suggestion.title}` : '未找到匹配的章节配置')
    } catch { setChapterHint('推断失败') }
  }

  async function save(e) {
    e.preventDefault()
    setError('')
    const payload = {
      ...form,
      class_id: form.class_id ? Number(form.class_id) : null,
      current_semester: form.current_semester ? Number(form.current_semester) : null,
      weak_points: form.weak_points.split(/[,，]/).map(s => s.trim()).filter(Boolean),
      strengths: form.strengths.split(/[,，]/).map(s => s.trim()).filter(Boolean),
    }
    try {
      if (editing) await endpoints.updateStudent(editing, payload)
      else await endpoints.createStudent(payload)
      setForm(EMPTY); setEditing(null); setChapterHint(''); load()
    } catch (err) { setError(err.message) }
  }

  async function del(id) {
    if (!confirm('确认删除该学生及其所有数据？')) return
    await endpoints.deleteStudent(id); load()
  }

  function edit(s) {
    setEditing(s.id)
    setForm({
      name: s.name,
      grade: s.grade || '',
      class_id: s.class_id || '',
      textbook_version: s.textbook_version || '',
      current_semester: s.current_semester ?? '',
      weak_points: (s.weak_points || []).join('，'),
      strengths: (s.strengths || []).join('，'),
      notes: s.notes || '',
      parent_contact: s.parent_contact || '',
    })
    setChapterHint('')
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>学生管理</h1>
      <Card title={editing ? '编辑学生' : '新增学生'}>
        <form onSubmit={save}>
          <div className="grid grid-3">
            <div><label>姓名 *</label><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required /></div>
            <div><label>年级</label>
              <select value={form.grade} onChange={e => { setForm({ ...form, grade: e.target.value }); setTimeout(infer, 0) }}>
                <option value="">请选择</option>
                {GRADES.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div><label>学期</label>
              <select value={form.current_semester} onChange={e => { setForm({ ...form, current_semester: e.target.value }); setTimeout(infer, 0) }}>
                <option value="">未指定</option>
                {SEMESTERS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div><label>教材版本</label><input value={form.textbook_version} onChange={e => { setForm({ ...form, textbook_version: e.target.value }); setTimeout(infer, 0) }} placeholder="如：人教版" /></div>
            <div><label>班级</label>
              <select value={form.class_id} onChange={e => setForm({ ...form, class_id: e.target.value })}>
                <option value="">未分班</option>
                {classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div><label>弱项（逗号分隔）</label><input value={form.weak_points} onChange={e => setForm({ ...form, weak_points: e.target.value })} /></div>
            <div><label>优势（逗号分隔）</label><input value={form.strengths} onChange={e => setForm({ ...form, strengths: e.target.value })} /></div>
            <div><label>家长联系方式（可选）</label><input value={form.parent_contact} onChange={e => setForm({ ...form, parent_contact: e.target.value })} /></div>
            <div><label>备注</label><input value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} /></div>
          </div>
          {chapterHint && <div className="muted mt-2">{chapterHint}</div>}
          {error && <div className="form-error">{error}</div>}
          <div className="row mt-4">
            <button className="btn btn-primary" type="submit">{editing ? '保存修改' : '创建学生'}</button>
            {editing && <button className="btn" type="button" onClick={() => { setEditing(null); setForm(EMPTY); setChapterHint('') }}>取消</button>}
          </div>
        </form>
      </Card>

      <Card title={`学生列表（${list.length}）`}>
        {list.length === 0 ? <Empty>暂无学生</Empty> : (
          <table className="table">
            <thead><tr><th>姓名</th><th>年级</th><th>学期</th><th>教材</th><th>班级</th><th>弱项</th><th></th></tr></thead>
            <tbody>
              {list.map(s => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.grade || '—'}</td>
                  <td>{s.current_semester === 1 ? '上学期' : s.current_semester === 2 ? '下学期' : '—'}</td>
                  <td>{s.textbook_version || '—'}</td>
                  <td>{s.class_id ? (classes.find(c => c.id === s.class_id)?.name || '—') : '—'}</td>
                  <td>{(s.weak_points || []).slice(0, 3).join('，') || '—'}</td>
                  <td className="right">
                    <a className="btn" href={`/archive/${s.id}`} style={{ marginRight: 8 }}>档案</a>
                    <button className="btn" onClick={() => edit(s)}>编辑</button>
                    <button className="btn btn-danger" style={{ marginLeft: 8 }} onClick={() => del(s.id)}>删除</button>
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