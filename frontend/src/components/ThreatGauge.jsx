export default function ThreatGauge({ prob, threshold = 0.72 }) {
  const pct = Math.round(prob * 100)
  const crit = prob >= threshold
  const level =
    crit ? 'CRITICAL' : prob >= 0.5 ? 'ELEVATED' : prob >= 0.25 ? 'GUARDED' : 'NORMAL'
  const color =
    crit ? 'text-orange-600' : prob >= 0.5 ? 'text-blue-600' :
    prob >= 0.25 ? 'text-blue-400' : 'text-lime-600'
  const ring =
    crit ? 'border-orange-500' : prob >= 0.5 ? 'border-blue-400' :
    prob >= 0.25 ? 'border-blue-200' : 'border-lime-500'

  return (
    <div className={`relative flex flex-col items-center justify-center rounded-2xl border-2 ${ring} bg-ivory-soft shadow-soft p-6 h-64 w-full transition-colors duration-500 ${crit ? 'alert-pulse' : ''}`}>
      <div className="text-[10px] tracking-[0.3em] text-ink-soft uppercase">Threat Level</div>
      <div className={`mt-3 text-6xl font-bold tabular-nums ${color}`}>{pct}</div>
      <div className="text-xs text-ink-soft mt-1">attack probability</div>
      <div className={`mt-3 text-sm font-semibold tracking-widest ${color}`}>{level}</div>
      {crit && (
        <div className="absolute -top-2 right-4 rounded bg-orange-500 px-2 py-0.5 text-[10px] font-bold tracking-wider text-white shadow-soft">
          FORECAST ALERT
        </div>
      )}
    </div>
  )
}
