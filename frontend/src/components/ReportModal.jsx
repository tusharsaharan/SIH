/** In-app incident report preview (fetches HTML, renders in sandboxed iframe). */
import { useEffect, useState } from 'react'
import { reportUrl } from '../hooks/api.js'

export default function ReportModal({ sessionId, onClose }) {
  const [html, setHtml] = useState(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!sessionId) return
    setHtml(null); setFailed(false)
    fetch(reportUrl(sessionId, 'html'))
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.text() })
      .then(setHtml)
      .catch(() => setFailed(true))
  }, [sessionId])

  if (!sessionId) return null
  return (
    <div className="fixed inset-0 z-40 grid place-items-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-ink/25" />
      <div className="relative w-full max-w-3xl h-[85vh] flex flex-col rounded-2xl border border-line bg-ivory shadow-lift overflow-hidden"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-line bg-ivory-soft">
          <span className="text-xs font-semibold text-ink">Incident Report · {sessionId}</span>
          <div className="flex items-center gap-2">
            <a href={reportUrl(sessionId, 'html')} target="_blank" rel="noreferrer"
              className="rounded-md border border-line px-2 py-1 text-[10px] text-ink-soft hover:bg-ivory-deep">open ↗</a>
            <button onClick={onClose} className="rounded-md border border-line px-2 py-1 text-[10px] text-ink-soft hover:bg-ivory-deep">✕</button>
          </div>
        </div>
        <div className="flex-1 bg-white">
          {failed && <div className="p-6 text-xs text-orange-600">report unavailable (session may still be running)</div>}
          {!failed && !html && <div className="p-6 text-xs text-ink-faint">rendering report…</div>}
          {html && <iframe title="report" srcDoc={html} sandbox="" className="w-full h-full border-0" />}
        </div>
      </div>
    </div>
  )
}
