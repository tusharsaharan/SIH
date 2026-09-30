export default function AlertFeed({ alerts, containment, onSelectAlert }) {
  return (
    <div className="rounded-md border border-[#E2DED4] bg-[#FFFFFF] p-4 flex flex-col" style={{ minHeight: 420 }}>
      <div className="flex items-center justify-between mb-2">
        <span className="qf-section-title">Alert Feed</span>
        <span className="text-[10px] font-light text-[#57534E]">{alerts.length} alerts · {containment.length} contained</span>
      </div>
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {alerts.length === 0 && containment.length === 0 ? (
          <div className="grid place-items-center h-full text-[#57534E] text-xs font-light">
            no alerts — network nominal
          </div>
        ) : (
          <>
            {containment.map((c) => (
              <div key={`c-${c.id}`} className="rounded-sm border border-[#9BC8B5] bg-[#CDE4DA] px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-light text-[#067647]">
                    ✓ CONTAINMENT DISPATCHED
                  </span>
                  <span className="text-[10px] font-light text-[#57534E]">t+{c.simMinute}m</span>
                </div>
                <div className="text-[10px] font-light text-[#57534E] mt-1 truncate">{c.rule}</div>
              </div>
            ))}
            {alerts.map((a) => (
              <div key={a.id} onClick={() => onSelectAlert?.(a)}
                className={`rounded-sm border border-[#B42318] bg-[#F0D3D1] px-3 py-2 ${onSelectAlert ? 'cursor-pointer hover:border-[#0F766E]' : ''}`}>
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-light text-[#B42318]">
                    ⚠ ATTACK FORECAST — {a.mitre}
                  </span>
                  <span className="text-[10px] font-light text-[#57534E]">t+{a.simMinute}m</span>
                </div>
                <div className="text-[10px] font-light text-[#57534E] mt-1">
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
