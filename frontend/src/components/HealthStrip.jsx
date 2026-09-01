import { useEffect, useState } from 'react'
import { Dot } from './ui.jsx'

/** Thin system-status strip: backend, WS link, inference latency, model, threshold. */
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
    <div className="max-w-7xl mx-auto px-4 pt-3">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 rounded-xl border border-line bg-ivory-soft shadow-soft px-4 py-1.5 text-[10px] text-ink-soft">
        <span className="flex items-center gap-1.5">
          <Dot tone={health ? 'lime' : 'muted'} pulse={!!health} />
          backend {health ? 'online' : 'offline'}
        </span>
        <span className="flex items-center gap-1.5">
          <Dot tone={connected ? 'lime' : 'muted'} pulse={connected} />
          stream {connected ? 'live' : 'reconnecting'}
        </span>
        <span>api rtt <b className="text-ink tabular-nums">{rtt != null ? `${rtt} ms` : '—'}</b></span>
        <span>infer <b className="text-ink tabular-nums">{emitMs != null ? `${emitMs} ms/win` : '—'}</b></span>
        <span>model <b className="text-ink">BiLSTM seq48+slope</b></span>
        <span>threshold <b className="text-ink tabular-nums">{health ? `${Math.round(health.threshold * 100)}%` : '—'}</b></span>
        <span className="ml-auto">AegisForecast v0.3 · zero-upload telemetry</span>
      </div>
    </div>
  )
}
