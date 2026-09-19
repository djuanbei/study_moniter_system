export function Card({ title, actions, children, className = '' }) {
  return (
    <section className={'card ' + className}>
      {(title || actions) && (
        <header className="card-header">
          <h2 className="card-title">{title}</h2>
          <div className="card-actions">{actions}</div>
        </header>
      )}
      <div className="card-body">{children}</div>
    </section>
  )
}

export function Empty({ children = '暂无数据' }) {
  return <div className="empty">{children}</div>
}

export function Spinner() {
  return <div className="spinner" />
}

export function Toast({ message, kind = 'info' }) {
  if (!message) return null
  return <div className={'toast toast-' + kind}>{message}</div>
}

export function Badge({ children, kind = 'neutral' }) {
  return <span className={'badge badge-' + kind}>{children}</span>
}