export default function AlertFeed({ alerts, containment, onSelectAlert }) {
  return (
    <div className="rounded-2xl border border-line bg-ivory-soft shadow-soft p-4 h-72 flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs tracking-widest text-ink-soft uppercase">Alert Feed</span>
        <span className="text-[10px] text-ink-faint">{alerts.length} alerts · {containment.length} contained</span>
      </div>
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {alerts.length === 0 && containment.length === 0 ? (
          <div className="grid place-items-center h-full text-ink-faint text-xs">
            no alerts — network nominal
          </div>
        ) : (
          <>
            {containment.map((c) => (
              <div key={`c-${c.id}`} className="rounded-lg border border-lime-300 bg-lime-50 px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-lime-700">
                    ✓ CONTAINMENT DISPATCHED
                  </span>
                  <span className="text-[10px] text-ink-faint">t+{c.simMinute}m</span>
                </div>
                <div className="text-[10px] text-lime-800/80 mt-1 truncate">{c.rule}</div>
              </div>
            ))}
            {alerts.map((a) => (
              <div key={a.id} onClick={() => onSelectAlert?.(a)}
                className={`rounded-lg border border-orange-300 bg-orange-50 px-3 py-2 ${onSelectAlert ? 'cursor-pointer hover:bg-orange-100/70' : ''}`}>
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-orange-700">
                    ⚠ ATTACK FORECAST — {a.mitre}
                  </span>
                  <span className="text-[10px] text-ink-faint">t+{a.simMinute}m</span>
                </div>
                <div className="text-[10px] text-ink-soft mt-1">
                  P(attack)={(a.attackProb * 100).toFixed(1)}% · ETA detonation ≈ {a.horizonMin}m · stage: {a.stage}
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}
