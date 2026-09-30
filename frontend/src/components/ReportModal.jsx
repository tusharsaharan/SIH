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
      <div className="absolute inset-0 bg-black/60" />
      <div className="relative w-full max-w-3xl h-[85vh] flex flex-col rounded-md border border-[#E2DED4] bg-[#FFFFFF] overflow-hidden"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#E2DED4] bg-[#F4F3EF]">
          <span className="text-xs font-light text-[#1C1917]">Incident Report · {sessionId}</span>
          <div className="flex items-center gap-2">
            <a href={reportUrl(sessionId, 'html')} target="_blank" rel="noreferrer"
              className="rounded-sm border border-[#E2DED4] px-2 py-1 text-[10px] font-light text-[#57534E] hover:text-[#1C1917] hover:border-[#0F766E]">open ↗</a>
            <button onClick={onClose} className="rounded-sm border border-[#E2DED4] px-2 py-1 text-[10px] font-light text-[#57534E] hover:text-[#1C1917]">✕</button>
          </div>
        </div>
        <div className="flex-1 bg-[#FFFFFF]">
          {failed && <div className="p-6 text-xs font-light text-[#B42318]">report unavailable (session may still be running)</div>}
          {!failed && !html && <div className="p-6 text-xs font-light text-[#57534E]">rendering report…</div>}
          {html && <iframe title="report" srcDoc={html} sandbox="" className="w-full h-full border-0" />}
        </div>
      </div>
    </div>
  )
}
