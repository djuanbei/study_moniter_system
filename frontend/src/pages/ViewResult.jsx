import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { endpoints } from '../api.js'
import { Card, Empty } from '../components/ui.jsx'

export default function ViewResult() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    endpoints.submissionResult(Number(id))
      .then(setData)
      .catch(e => setError(e.message))
  }, [id])

  if (!data) return <Card><Empty>{error || '加载中…'}</Empty></Card>
  const { submission, grading, assignment_title, assignment_status } = data

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>{assignment_title}</h1>
      <div className="row mb-4">
        <span className="badge badge-primary">{labelStatus(assignment_status)}</span>
        <span className="muted">提交时间：{new Date(submission.submitted_at).toLocaleString()}</span>
      </div>

      <Card title="成绩">
        {grading ? (
          <div className="grid grid-3">
            <div>
              <div className="muted">最终分数</div>
              <div style={{ fontSize: 28, fontWeight: 700 }}>{grading.final_score?.toFixed?.(1) ?? grading.final_score}</div>
            </div>
            <div style={{ gridColumn: 'span 2' }}>
              <div className="muted">教师反馈</div>
              <div>{grading.feedback || '—'}</div>
            </div>
            {grading.llm_knowledge_mastery && Object.keys(grading.llm_knowledge_mastery).length > 0 && (
              <div style={{ gridColumn: 'span 3' }}>
                <div className="muted">知识点掌握</div>
                <div className="row mt-2" style={{ flexWrap: 'wrap', gap: 6 }}>
                  {Object.entries(grading.llm_knowledge_mastery).map(([k, v]) => (
                    <span key={k} className="badge badge-neutral">{k}: {Math.round((v || 0) * 100)}%</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <Empty>尚未批改，请耐心等待老师反馈。</Empty>
        )}
      </Card>

      {submission.text_answer && (
        <Card title="你提交的作答（文字）">
          <div style={{ whiteSpace: 'pre-wrap' }}>{submission.text_answer}</div>
        </Card>
      )}

      {submission.images && submission.images.length > 0 && (
        <Card title={`你提交的作答图片（${submission.images.length} 张）`}>
          <div className="grid grid-3">
            {submission.images.map(img => (
              <div key={img.id} className="card" style={{ padding: 8 }}>
                <div className="muted" style={{ fontSize: 12 }}>题号 {img.question_number ?? '—'}</div>
                <img src={img.url} alt={img.filename} style={{ width: '100%', borderRadius: 8, marginTop: 4 }} />
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <Link className="btn" to="/assignments">返回我的作业</Link>
      </Card>
    </div>
  )
}

function labelStatus(s) {
  if (s === 'graded') return '已批改'
  if (s === 'submitted') return '已提交'
  if (s === 'assigned') return '已分配'
  if (s === 'cancelled') return '已取消'
  return s
}