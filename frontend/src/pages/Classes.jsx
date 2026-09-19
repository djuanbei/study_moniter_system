import { useEffect, useState } from 'react'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'
import { GRADES } from '../constants.js'

const EMPTY = { name: '', grade: '', textbook_version: '', year: '', notes: '' }

export default function Classes() {
  const [list, setList] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState('')

  function load() { endpoints.classes().then(setList) }
  useEffect(load, [])

  async function save(e) {
    e.preventDefault()
    setError('')
    const payload = { ...form, year: form.year ? Number(form.year) : null }
    try {
      if (editing) await endpoints.updateClass(editing, payload)
      else await endpoints.createClass(payload)
      setForm(EMPTY); setEditing(null); load()
    } catch (err) { setError(err.message) }
  }

  async function del(id) {
    if (!confirm('确认删除该班级？')) return
    await endpoints.deleteClass(id); load()
  }

  function edit(c) {
    setEditing(c.id)
    setForm({ name: c.name, grade: c.grade || '', textbook_version: c.textbook_version || '', year: c.year || '', notes: c.notes || '' })
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>班级管理</h1>
      <Card title={editing ? '编辑班级' : '新增班级'}>
        <form onSubmit={save}>
          <div className="grid grid-2">
            <div><label>班级名称 *</label><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required /></div>
            <div><label>年级</label>
              <select value={form.grade} onChange={e => setForm({ ...form, grade: e.target.value })}>
                <option value="">请选择</option>
                {GRADES.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div><label>教材版本</label><input value={form.textbook_version} onChange={e => setForm({ ...form, textbook_version: e.target.value })} /></div>
            <div><label>学年</label><input type="number" value={form.year} onChange={e => setForm({ ...form, year: e.target.value })} /></div>
          </div>
          <div className="mt-2"><label>备注</label><input value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} /></div>
          {error && <div className="form-error">{error}</div>}
          <div className="row mt-4">
            <button className="btn btn-primary" type="submit">{editing ? '保存修改' : '创建班级'}</button>
            {editing && <button className="btn" type="button" onClick={() => { setEditing(null); setForm(EMPTY) }}>取消</button>}
          </div>
        </form>
      </Card>

      <Card title={`班级列表（${list.length}）`}>
        {list.length === 0 ? <Empty>暂无班级</Empty> : (
          <table className="table">
            <thead><tr><th>名称</th><th>年级</th><th>教材</th><th>学年</th><th></th></tr></thead>
            <tbody>
              {list.map(c => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{c.grade || '—'}</td>
                  <td>{c.textbook_version || '—'}</td>
                  <td>{c.year || '—'}</td>
                  <td className="right">
                    <button className="btn" onClick={() => edit(c)}>编辑</button>
                    <button className="btn btn-danger" style={{ marginLeft: 8 }} onClick={() => del(c.id)}>删除</button>
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