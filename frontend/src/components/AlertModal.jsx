import { Badge } from './ui.jsx'

/** Full alert detail modal: probability, stage, SHAP, enrichment, guidance. */
export default function AlertModal({ alert, onClose, onRespond }) {
  if (!alert) return null
  const e = alert.enrichment || {}

  return (
    <div className="fixed inset-0 z-40 grid place-items-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60" />
      <div className="relative w-full max-w-lg rounded-md border border-[#E2DED4] bg-[#FFFFFF] p-5 max-h-[85vh] overflow-y-auto"
        onClick={(ev) => ev.stopPropagation()}>
        <div className="flex items-start justify-between">
          <div>
            <div className="qf-section-title">attack forecast · t+{alert.simMinute}m</div>
            <div className="mt-1 qf-h-sm text-[#1C1917]">
              {(alert.attackProb * 100).toFixed(1)}% <span className="qf-body-md text-[#57534E]">on {alert.host}</span>
            </div>
          </div>
          <button onClick={onClose} className="qf-btn qf-btn-secondary !h-8 !px-2">✕</button>
        </div>

        <div className="mt-3 flex flex-wrap gap-1.5">
          <Badge tone="error">{alert.mitre}</Badge>
          <Badge tone="secondary">{alert.stage}</Badge>
          <Badge tone="muted">ETA {alert.horizonMin}m</Badge>
          {e.verdict && <Badge tone={e.verdict === 'known-bad' ? 'error' : 'secondary'}>{e.verdict}</Badge>}
        </div>

        <div className="mt-4 qf-section-title">why this fired (SHAP)</div>
        <div className="mt-1.5 flex flex-col gap-1.5">
          {(alert.shap || []).slice(0, 6).map((s) => (
            <div key={s.feature} className="flex items-center gap-2">
              <div className="w-36 text-[11px] font-light text-[#57534E] truncate">{s.feature}</div>
              <div className="flex-1 h-3.5 rounded-sm bg-[#F4F3EF] border border-[#E2DED4] overflow-hidden">
                <div className="h-full bg-[#0F766E]"
                  style={{ width: `${Math.min(100, s.importance * 100)}%` }} />
              </div>
              <div className="w-12 text-right text-[10px] font-light tabular-nums text-[#57534E]">{(s.importance * 100).toFixed(1)}%</div>
            </div>
          ))}
        </div>

        <div className="mt-4 qf-section-title">threat intel</div>
        <div className="mt-1.5 rounded-sm border border-[#E2DED4] bg-[#F4F3EF] p-3 text-[11px] font-light text-[#57534E]">
          <div>source <b className="text-[#1C1917]"> {e.ip || '—'}</b> · {e.geo || 'unknown geo'} · reputation <b className="text-[#1C1917] tabular-nums">{e.reputation ?? '—'}</b></div>
          {e.campaigns?.length > 0 && <div className="mt-1">campaigns: <b className="text-[#1C1917]">{e.campaigns.join(', ')}</b></div>}
          {e.note && <div className="mt-1 italic">{e.note}</div>}
        </div>

        <div className="mt-4 flex gap-2">
          <button onClick={() => { onRespond(alert.host, 'triage'); onClose() }}
            className="qf-btn qf-btn-secondary">Triage incident</button>
          <button onClick={() => { onRespond(alert.host, 'isolate'); onClose() }}
            className="qf-btn qf-btn-error">Isolate {alert.host}</button>
        </div>
      </div>
    </div>
  )
}
