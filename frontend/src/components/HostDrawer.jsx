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
      <div className="absolute inset-0 bg-black/60" />
      <aside className="absolute right-0 top-0 h-full w-80 bg-[#FFFFFF] border-l border-[#E2DED4] p-5 overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div>
            <div className="qf-h-sm text-[#1C1917]">{host}</div>
            <div className="text-[10px] font-light text-[#57534E]">{ROLE_LABEL[host] || 'segment host'}</div>
          </div>
          <button onClick={onClose} className="qf-btn qf-btn-secondary !h-8 !px-2">✕</button>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <span className="qf-h-md tabular-nums text-[#1C1917]">{Math.round(risk * 100)}</span>
          <div>
            <div className="qf-section-title">live risk</div>
            {incident
              ? <Badge tone={incident.state === 'closed' ? 'muted' : incident.state === 'detected' ? 'error' : 'secondary'}>{incident.state}</Badge>
              : <Badge tone="secondary">nominal</Badge>}
          </div>
        </div>

        <div className="mt-3 rounded-sm border border-[#E2DED4] bg-[#F4F3EF] p-2">
          <div className="qf-section-title mb-1">risk · last {pts.length} windows</div>
          {pts.length > 1 ? (
            <svg viewBox="0 0 100 30" className="w-full h-14" preserveAspectRatio="none">
              <polyline points={spark} fill="none" stroke={risk >= 0.72 ? '#B42318' : '#0F766E'} strokeWidth="1.5" />
            </svg>
          ) : <EmptyState glyph="～">no telemetry yet</EmptyState>}
        </div>

        {incident && incident.state !== 'closed' && (
          <div className="mt-3 flex gap-1.5">
            {incident.state === 'detected' && (
              <button onClick={() => onRespond(host, 'triage')}
                className="qf-btn qf-btn-secondary !h-8 !px-2 !text-[10px]">Triage</button>
            )}
            {['detected', 'triaged'].includes(incident.state) && (
              <button onClick={() => onRespond(host, 'isolate')}
                className="qf-btn qf-btn-error !h-8 !px-2 !text-[10px]">Isolate Host</button>
            )}
            {incident.state === 'contained' && (
              <button onClick={() => onRespond(host, 'verify')}
                className="qf-btn qf-btn-secondary !h-8 !px-2 !text-[10px]">Verify Clean</button>
            )}
            <button onClick={() => onRespond(host, 'close')}
              className="qf-btn-tertiary border border-[#E2DED4] rounded-sm px-2 py-1 text-[10px] font-light text-[#57534E] hover:text-[#1C1917]">Close</button>
          </div>
        )}

        <div className="mt-4 qf-section-title">recent alerts · {host}</div>
        <div className="mt-1.5 flex flex-col gap-1.5">
          {(hostAlerts || []).length === 0 && <div className="text-[11px] font-light text-[#57534E]">none this session</div>}
          {(hostAlerts || []).slice(0, 8).map((a) => (
            <div key={a.id} className="rounded-sm border border-[#B42318] bg-[#F0D3D1] px-2.5 py-1.5 text-[10px] font-light">
              <span className="text-[#B42318]">t+{a.simMinute}m · {(a.attackProb * 100).toFixed(0)}%</span>
              <span className="text-[#57534E]"> · {a.mitre} · ETA {a.horizonMin}m</span>
            </div>
          ))}
        </div>
      </aside>
    </div>
  )
}
