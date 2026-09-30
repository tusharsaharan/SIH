/** Campaign attribution panel: intel-enriched alert rollup. */
export default function CampaignPanel({ campaigns }) {
  const list = campaigns || []
  return (
    <div className="rounded-md border border-[#E2DED4] bg-[#FFFFFF] p-4 h-56 flex flex-col">
      <div className="qf-section-title mb-2">
        Campaign Attribution
      </div>
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {!list.length ? (
          <div className="grid place-items-center h-full text-[#57534E] text-xs font-light">
            no correlated campaigns yet
          </div>
        ) : list.map((c) => (
          <div key={c.campaign} className="rounded-sm border border-[#E2DED4] bg-[#F4F3EF] px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-light text-[#1C1917]">
                {c.campaign}
              </span>
              <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded-sm border
                ${c.verdict === 'known-bad' ? 'text-[#B42318] border-[#B42318]'
                  : 'text-[#57534E] border-[#E2DED4]'}`}>
                {c.verdict || 'unknown'}
              </span>
            </div>
            <div className="text-[10px] font-light text-[#57534E] mt-1">
              {c.nAlerts} alerts · max P={(c.maxProb * 100).toFixed(0)}% · hosts {c.hosts?.join(', ') || '—'}
              {c.geo ? ` · ${c.geo}` : ''}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
