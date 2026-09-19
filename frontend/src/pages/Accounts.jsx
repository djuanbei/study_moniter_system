import { useEffect, useState } from 'react'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'

const EMPTY = { username: '', password: '', role: 'student', display_name: '', student_id: '' }

export default function Accounts() {
  const [list, setList] = useState([])
  const [students, setStudents] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [resetFor, setResetFor] = useState(null)
  const [newPw, setNewPw] = useState('')
  const [error, setError] = useState('')

  function load() {
    endpoints.accounts().then(setList)
    endpoints.students().then(setStudents)
  }
  useEffect(load, [])

  async function create(e) {
    e.preventDefault()
    setError('')
    try {
      await endpoints.createAccount({
        ...form,
        student_id: form.student_id ? Number(form.student_id) : null,
      })
      setForm(EMPTY); load()
    } catch (err) { setError(err.message) }
  }

  async function toggleActive(u) {
    if (u.is_active) await endpoints.disableAccount(u.id)
    else await endpoints.enableAccount(u.id)
    load()
  }

  async function reset(e) {
    e.preventDefault()
    await endpoints.resetPassword(resetFor.id, newPw)
    setResetFor(null); setNewPw(''); load()
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>账号管理</h1>
      <Card title="新增账号">
        <form onSubmit={create}>
          <div className="grid grid-3">
            <div><label>用户名 *</label><input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} required /></div>
            <div><label>密码 *</label><input type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required minLength={8} /></div>
            <div><label>角色 *</label>
              <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}>
                <option value="teacher">教师</option>
                <option value="student">学生</option>
              </select>
            </div>
            <div><label>显示名称</label><input value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })} /></div>
            {form.role === 'student' && (
              <div><label>关联学生</label>
                <select value={form.student_id} onChange={e => setForm({ ...form, student_id: e.target.value })}>
                  <option value="">未关联</option>
                  {students.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
            )}
          </div>
          {error && <div className="form-error">{error}</div>}
          <button className="btn btn-primary mt-4" type="submit">创建账号</button>
        </form>
      </Card>

      <Card title={`账号列表（${list.length}）`}>
        {list.length === 0 ? <Empty>暂无账号</Empty> : (
          <table className="table">
            <thead><tr><th>用户名</th><th>角色</th><th>显示名</th><th>关联学生</th><th>状态</th><th></th></tr></thead>
            <tbody>
              {list.map(u => (
                <tr key={u.id}>
                  <td>{u.username}{u.must_change_password && <span className="badge badge-warn" style={{ marginLeft: 6 }}>需改密</span>}</td>
                  <td>{u.role === 'teacher' ? '教师' : '学生'}</td>
                  <td>{u.display_name || '—'}</td>
                  <td>{u.student_id ? (students.find(s => s.id === u.student_id)?.name || `#${u.student_id}`) : '—'}</td>
                  <td>{u.is_active ? <span className="badge badge-success">启用</span> : <span className="badge badge-danger">停用</span>}</td>
                  <td className="right">
                    <button className="btn" onClick={() => setResetFor(u)}>重置密码</button>
                    <button className="btn" style={{ marginLeft: 8 }} onClick={() => toggleActive(u)}>{u.is_active ? '停用' : '启用'}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {resetFor && (
        <Card title={`为 ${resetFor.username} 重置密码`}>
          <form onSubmit={reset}>
            <label>新密码（至少 8 位）</label>
            <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)} minLength={8} required />
            <div className="row mt-4">
              <button className="btn btn-primary" type="submit">提交</button>
              <button className="btn" type="button" onClick={() => { setResetFor(null); setNewPw('') }}>取消</button>
            </div>
          </form>
        </Card>
      )}
    </div>
  )
}