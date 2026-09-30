import { useEffect, useState } from 'react'
import { Dot } from './ui.jsx'

/** Slim connection vitals: backend + stream + latency only.
 *  Model/threshold detail lives in the Models tab — no duplication. */
export default function HealthStrip({ connected, latest, health }) {
  const [rtt, setRtt] = useState(null)

  useEffect(() => {
    let alive = true
    const ping = async () => {
      const t0 = performance.now()
      try {
        await fetch('/api/health')
        if (alive) setRtt(Math.round(performance.now() - t0))
      } catch { if (alive) setRtt(null) }
    }
    ping()
    const iv = setInterval(ping, 10000)
    return () => { alive = false; clearInterval(iv) }
  }, [])

  const emitMs = latest?.emitMs ?? null

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4">
      <div className="flex flex-wrap items-center rounded-md border border-[#E2DED4] bg-[#FFFFFF] px-4 text-[10px] font-light text-[#57534E]" style={{ gap: 20, paddingTop: 6, paddingBottom: 6 }}>
        <span className="flex items-center gap-1.5">
          <Dot tone={health ? 'primary' : 'muted'} pulse={!!health} />
          backend {health ? 'online' : 'offline'}
        </span>
        <span className="flex items-center gap-1.5">
          <Dot tone={connected ? 'primary' : 'muted'} pulse={connected} />
          stream {connected ? 'live' : 'reconnecting'}
        </span>
        <span>api rtt <b className="text-[#1C1917] tabular-nums font-light">{rtt != null ? `${rtt} ms` : '—'}</b></span>
        <span>infer <b className="text-[#1C1917] tabular-nums font-light">{emitMs != null ? `${emitMs} ms/win` : '—'}</b></span>
        <span className="ml-auto">zero-upload telemetry</span>
      </div>
    </div>
  )
}
