import { useEffect, useState } from 'react'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'

export default function Settings() {
  const [cfg, setCfg] = useState(null)
  const [text, setText] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    endpoints.settings().then(s => { setCfg(s.config); setText(JSON.stringify(s.config, null, 2)) })
  }, [])

  async function save() {
    setError(''); setMsg('')
    let parsed
    try { parsed = JSON.parse(text) } catch { setError('JSON 格式错误'); return }
    try {
      const out = await endpoints.updateSettings(parsed)
      setCfg(out.config); setMsg('已保存')
    } catch (err) { setError(err.message) }
  }

  if (!cfg) return <Card><Empty>加载中…</Empty></Card>

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>系统设置</h1>
      <Card title="configure.json">
        <div className="muted" style={{ marginBottom: 8 }}>
          顶层字段：app / academic / generation / llm / uploads。保存后会立即生效。
        </div>
        <textarea rows={26} value={text} onChange={e => setText(e.target.value)}
                  style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 12 }} />
        {error && <div className="form-error">{error}</div>}
        {msg && <div className="badge badge-success mt-2">{msg}</div>}
        <div className="row mt-4">
          <button className="btn btn-primary" onClick={save}>保存</button>
          <button className="btn" onClick={() => setText(JSON.stringify(cfg, null, 2))}>重置</button>
        </div>
      </Card>
    </div>
  )
}