/** Campaign attribution panel: intel-enriched alert rollup. */
export default function CampaignPanel({ campaigns }) {
  const list = campaigns || []
  return (
    <div className="rounded-2xl border border-line bg-ivory-soft shadow-soft p-4 h-56 flex flex-col">
      <div className="text-xs tracking-widest text-ink-soft uppercase mb-2">
        Campaign Attribution
      </div>
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {!list.length ? (
          <div className="grid place-items-center h-full text-ink-faint text-xs">
            no correlated campaigns yet
          </div>
        ) : list.map((c) => (
          <div key={c.campaign} className="rounded-lg border border-line bg-ivory px-3 py-2 shadow-soft">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-blue-700 font-mono">
                {c.campaign}
              </span>
              <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded
                ${c.verdict === 'known-bad' ? 'bg-orange-100 text-orange-700'
                  : 'bg-blue-100 text-blue-700'}`}>
                {c.verdict || 'unknown'}
              </span>
            </div>
            <div className="text-[10px] text-ink-soft mt-1">
              {c.nAlerts} alerts · max P={(c.maxProb * 100).toFixed(0)}% · hosts {c.hosts?.join(', ') || '—'}
              {c.geo ? ` · ${c.geo}` : ''}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
