import { useEffect, useState } from 'react'
import { Card, SectionTitle, Badge, EmptyState } from './ui.jsx'

/** Red-team honesty panel: measured evasion outcomes per family. */
export default function EvasionPanel() {
  const [data, setData] = useState(null)

  useEffect(() => {
    fetch('/api/evasion/analysis').then((r) => r.json()).then(setData).catch(() => setData({}))
  }, [])

  const fams = data ? Object.entries(data) : []

  return (
    <Card>
      <SectionTitle right={<Badge tone="secondary">red-team</Badge>}>Evasion Analysis</SectionTitle>
      {!data ? (
        <div className="text-[11px] font-light text-[#57534E]">loading analysis…</div>
      ) : fams.length === 0 ? (
        <EmptyState glyph="◍">analysis unavailable</EmptyState>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {fams.map(([fam, b]) => {
            const caught = /CAUGHT/.test(b.measuredOutcome || '')
            return (
              <div key={fam} className="rounded-sm border border-[#E2DED4] bg-[#F4F3EF] p-3">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-light text-[#1C1917]">{fam}</span>
                  <Badge tone={caught ? 'ok' : 'error'}>{caught ? 'caught' : 'review'}</Badge>
                </div>
                <div className="mt-1.5 text-[10px] font-light leading-relaxed text-[#57534E]">{b.measuredOutcome}</div>
                {b.whyCaught && <div className="mt-1 text-[10px] font-light leading-relaxed text-[#57534E]">{b.whyCaught}</div>}
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}
