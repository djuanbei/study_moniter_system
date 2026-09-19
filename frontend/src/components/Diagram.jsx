/**
 * Safe diagram renderer.
 * - "svg" markup is sanitized server-side (services/svg.py) before storage.
 * - "mermaid" source is plain text (no mermaid renderer bundled) — render as
 *   a <pre> block, never as HTML.
 */
export default function Diagram({ format, svg }) {
  if (!svg) return null
  if (format === 'mermaid') return <pre className="diagram-preview mt-2" style={{ whiteSpace: 'pre-wrap' }}>{svg}</pre>
  return <div className="diagram-preview mt-2" dangerouslySetInnerHTML={{ __html: svg }} />
}
