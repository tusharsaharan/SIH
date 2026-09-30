/** SituationStrip: the single "how bad is it" band. Merges the old
 *  ThreatGauge card + Forecast meta box into one horizontal strip so the
 *  command view has exactly one hero element instead of two. */
export default function SituationStrip({ prob, threshold = 0.72, latest, windows }) {
  const pct = Math.round((prob ?? 0) * 100)
  const crit = (prob ?? 0) >= threshold
  const level = crit ? 'CRITICAL' : prob >= 0.5 ? 'ELEVATED' : prob >= 0.25 ? 'GUARDED' : 'NORMAL'
  const levelColor = crit ? 'text-[#B42318]' : prob >= 0.5 ? 'text-[#115E59]' : 'text-[#57534E]'

  const facts = [
    ['Top host', latest?.host ?? '—'],
    ['Stage', latest ? latest.stageName : '—'],
    ['MITRE', latest?.mitre ?? '—'],
    ['Lead time', latest?.horizon ? `${latest.horizon} min` : '—'],
    ['Windows', windows],
  ]

  return (
    <div className={`rounded-md border bg-[#FFFFFF] px-6 py-4 flex items-center ${crit ? 'border-[#B42318] alert-pulse' : 'border-[#E2DED4]'}`} style={{ gap: 40 }}>
      <div className="shrink-0 flex items-baseline" style={{ gap: 12 }}>
        <span className={`qf-h-md tabular-nums ${crit ? 'text-[#B42318]' : 'text-[#1C1917]'}`}>{pct}</span>
        <span className="flex flex-col">
          <span className="qf-section-title">threat</span>
          <span className={`qf-label-md tracking-widest ${levelColor}`}>{level}</span>
        </span>
      </div>
      <div className="w-px self-stretch bg-[#E2DED4]" />
      <div className="flex-1 grid grid-cols-2 md:grid-cols-5" style={{ gap: 24 }}>
        {facts.map(([k, v]) => (
          <div key={k}>
            <div className="qf-section-title">{k}</div>
            <div className="mt-1 text-[15px] font-light text-[#1C1917] truncate">{v}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
