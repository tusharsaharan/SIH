import { Badge } from './ui.jsx'

/** Full alert detail modal: probability, stage, SHAP, enrichment, guidance. */
export default function AlertModal({ alert, onClose, onRespond }) {
  if (!alert) return null
  const e = alert.enrichment || {}

  return (
    <div className="fixed inset-0 z-40 grid place-items-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-ink/25" />
      <div className="relative w-full max-w-lg rounded-2xl border border-line bg-ivory shadow-lift p-5 max-h-[85vh] overflow-y-auto"
        onClick={(ev) => ev.stopPropagation()}>
        <div className="flex items-start justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-ink-faint">attack forecast · t+{alert.simMinute}m</div>
            <div className="mt-1 text-xl font-bold text-ink">
              {(alert.attackProb * 100).toFixed(1)}% <span className="text-sm font-semibold text-ink-soft">on {alert.host}</span>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg border border-line px-2 py-1 text-xs text-ink-soft hover:bg-ivory-deep">✕</button>
        </div>

        <div className="mt-3 flex flex-wrap gap-1.5">
          <Badge tone="orange">{alert.mitre}</Badge>
          <Badge tone="blue">{alert.stage}</Badge>
          <Badge tone="muted">ETA {alert.horizonMin}m</Badge>
          {e.verdict && <Badge tone={e.verdict === 'known-bad' ? 'orange' : 'blue'}>{e.verdict}</Badge>}
        </div>

        <div className="mt-4 text-[10px] uppercase tracking-widest text-ink-faint">why this fired (SHAP)</div>
        <div className="mt-1.5 flex flex-col gap-1.5">
          {(alert.shap || []).slice(0, 6).map((s) => (
            <div key={s.feature} className="flex items-center gap-2">
              <div className="w-36 text-[11px] text-ink-soft truncate">{s.feature}</div>
              <div className="flex-1 h-3.5 rounded bg-ivory-deep overflow-hidden">
                <div className="h-full rounded bg-gradient-to-r from-blue-500 to-blue-700"
                  style={{ width: `${Math.min(100, s.importance * 100)}%` }} />
              </div>
              <div className="w-12 text-right text-[10px] tabular-nums text-ink-faint">{(s.importance * 100).toFixed(1)}%</div>
            </div>
          ))}
        </div>

        <div className="mt-4 text-[10px] uppercase tracking-widest text-ink-faint">threat intel</div>
        <div className="mt-1.5 rounded-xl border border-line bg-ivory-soft p-3 text-[11px] text-ink-soft">
          <div>source <b className="text-ink font-mono">{e.ip || '—'}</b> · {e.geo || 'unknown geo'} · reputation <b className="text-ink tabular-nums">{e.reputation ?? '—'}</b></div>
          {e.campaigns?.length > 0 && <div className="mt-1">campaigns: <b className="text-blue-700">{e.campaigns.join(', ')}</b></div>}
          {e.note && <div className="mt-1 italic">{e.note}</div>}
        </div>

        <div className="mt-4 flex gap-2">
          <button onClick={() => { onRespond(alert.host, 'triage'); onClose() }}
            className="rounded-lg border border-blue-300 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-100">Triage incident</button>
          <button onClick={() => { onRespond(alert.host, 'isolate'); onClose() }}
            className="rounded-lg border border-orange-300 bg-orange-50 px-3 py-1.5 text-xs font-semibold text-orange-700 hover:bg-orange-100">Isolate {alert.host}</button>
        </div>
      </div>
    </div>
  )
}
