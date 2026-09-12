import { Badge, EmptyState } from './ui.jsx'

const ROLE_LABEL = {
  DC: 'domain-controller · auth',
  WEB: 'web-server · 443',
  DB: 'database · 3306',
  FILE: 'file-server · SMB',
  WS1: 'workstation · client',
}

/** Slide-over host inspector: risk sparkline, incident, recent host alerts, actions. */
export default function HostDrawer({ host, hostRisk, incident, hostAlerts, history, onClose, onRespond }) {
  if (!host) return null
  const risk = hostRisk ?? 0
  const pts = (history || [])
    .map((t) => t.hostRisks?.[host])
    .filter((v) => v != null)
    .slice(-40)
  const max = Math.max(0.05, ...pts)
  const spark = pts.map((v, i) => `${(i / Math.max(1, pts.length - 1)) * 100},${28 - (v / max) * 26}`).join(' ')

  return (
    <div className="fixed inset-0 z-40" onClick={onClose}>
      <div className="absolute inset-0 bg-ink/20" />
      <aside className="absolute right-0 top-0 h-full w-80 bg-ivory shadow-lift border-l border-line p-5 overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-lg font-bold text-ink">{host}</div>
            <div className="text-[10px] text-ink-faint">{ROLE_LABEL[host] || 'segment host'}</div>
          </div>
          <button onClick={onClose} className="rounded-lg border border-line px-2 py-1 text-xs text-ink-soft hover:bg-ivory-deep">✕</button>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <span className="text-3xl font-bold tabular-nums text-ink">{Math.round(risk * 100)}</span>
          <div>
            <div className="text-[10px] uppercase tracking-widest text-ink-soft">live risk</div>
            {incident
              ? <Badge tone={incident.state === 'closed' ? 'lime' : incident.state === 'detected' ? 'orange' : 'blue'}>{incident.state}</Badge>
              : <Badge tone="lime">nominal</Badge>}
          </div>
        </div>

        <div className="mt-3 rounded-xl border border-line bg-white/60 p-2">
          <div className="text-[10px] uppercase tracking-widest text-ink-faint mb-1">risk · last {pts.length} windows</div>
          {pts.length > 1 ? (
            <svg viewBox="0 0 100 30" className="w-full h-14" preserveAspectRatio="none">
              <polyline points={spark} fill="none" stroke={risk >= 0.72 ? '#ea580c' : risk >= 0.4 ? '#2563EB' : '#65a30d'} strokeWidth="1.5" />
            </svg>
          ) : <EmptyState glyph="～">no telemetry yet</EmptyState>}
        </div>

        {incident && incident.state !== 'closed' && (
          <div className="mt-3 flex gap-1.5">
            {incident.state === 'detected' && (
              <button onClick={() => onRespond(host, 'triage')}
                className="rounded-md border border-blue-300 bg-blue-50 px-2 py-1 text-[10px] font-semibold text-blue-700 hover:bg-blue-100">Triage</button>
            )}
            {['detected', 'triaged'].includes(incident.state) && (
              <button onClick={() => onRespond(host, 'isolate')}
                className="rounded-md border border-orange-300 bg-orange-50 px-2 py-1 text-[10px] font-semibold text-orange-700 hover:bg-orange-100">Isolate Host</button>
            )}
            {incident.state === 'contained' && (
              <button onClick={() => onRespond(host, 'verify')}
                className="rounded-md border border-blue-300 bg-blue-50 px-2 py-1 text-[10px] font-semibold text-blue-700 hover:bg-blue-100">Verify Clean</button>
            )}
            <button onClick={() => onRespond(host, 'close')}
              className="rounded-md border border-line bg-ivory-deep/60 px-2 py-1 text-[10px] font-semibold text-ink-soft hover:bg-ivory-deep">Close</button>
          </div>
        )}

        <div className="mt-4 text-[10px] uppercase tracking-widest text-ink-faint">recent alerts · {host}</div>
        <div className="mt-1.5 flex flex-col gap-1.5">
          {(hostAlerts || []).length === 0 && <div className="text-[11px] text-ink-faint">none this session</div>}
          {(hostAlerts || []).slice(0, 8).map((a) => (
            <div key={a.id} className="rounded-lg border border-orange-200 bg-orange-50 px-2.5 py-1.5 text-[10px]">
              <span className="font-semibold text-orange-700">t+{a.simMinute}m · {(a.attackProb * 100).toFixed(0)}%</span>
              <span className="text-ink-soft"> · {a.mitre} · ETA {a.horizonMin}m</span>
            </div>
          ))}
        </div>
      </aside>
    </div>
  )
}
