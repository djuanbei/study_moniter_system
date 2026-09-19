import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export default function Archive() {
  const { studentId } = useParams()
  const [student, setStudent] = useState(null)
  const [trend, setTrend] = useState([])
  const [assignments, setAssignments] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    if (!studentId) return
    Promise.all([
      endpoints.student(Number(studentId)).catch(() => null),
      endpoints.studentScoreTrend(Number(studentId)).catch(() => []),
      endpoints.studentAssignments(Number(studentId)).catch(() => []),
    ]).then(([s, t, a]) => { setStudent(s); setTrend(t); setAssignments(a) })
  }, [studentId])

  async function exportFile(kind) {
    setError('')
    try {
      const blob = kind === 'csv' ? await endpoints.exportCsv(studentId)
                : kind === 'pdf' ? await endpoints.exportPdf(studentId)
                : await endpoints.exportImagesZip(studentId)
      downloadBlob(blob, `student_${studentId}.${kind === 'images' ? 'zip' : kind}`)
    } catch (err) { setError(err.message) }
  }

  if (!student) return <Card><Empty>{error || '加载中…'}</Empty></Card>

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>{student.name} 的学习档案</h1>
      <div className="row mb-4">
        <button className="btn" onClick={() => exportFile('csv')}>导出 CSV</button>
        <button className="btn" onClick={() => exportFile('pdf')}>导出 PDF</button>
        <button className="btn" onClick={() => exportFile('images')}>导出图片 ZIP</button>
      </div>

      <Card title="基本信息">
        <div className="grid grid-3">
          <Field label="年级" value={student.grade} />
          <Field label="教材" value={student.textbook_version} />
          <Field label="班级" value={student.class_id} />
          <Field label="弱项" value={(student.weak_points || []).join('，')} />
          <Field label="优势" value={(student.strengths || []).join('，')} />
          <Field label="家长联系方式" value={student.parent_contact} />
        </div>
      </Card>

      <Card title="成绩趋势">
        {trend.length === 0 ? <Empty>暂无数据</Empty> : (
          <table className="table">
            <thead><tr><th>提交时间</th><th>分数</th></tr></thead>
            <tbody>
              {trend.map(t => (
                <tr key={t.submission_id}>
                  <td>{new Date(t.submitted_at).toLocaleString()}</td>
                  <td>{t.score?.toFixed?.(1) ?? t.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="作业历史">
        {assignments.length === 0 ? <Empty>暂无作业</Empty> : (
          <table className="table">
            <thead><tr><th>标题</th><th>状态</th><th>截止</th></tr></thead>
            <tbody>
              {assignments.map(a => (
                <tr key={a.id}>
                  <td>{a.title}</td>
                  <td>{a.status}</td>
                  <td>{a.due_date ? new Date(a.due_date).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}

function Field({ label, value }) {
  return (
    <div>
      <label>{label}</label>
      <div>{value || '—'}</div>
    </div>
  )
}