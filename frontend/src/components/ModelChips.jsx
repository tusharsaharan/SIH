import { useEffect, useState } from 'react'
import { Card, SectionTitle, Badge, EmptyState } from './ui.jsx'

/** Model leaderboard chips: val AUC per checkpoint, current highlighted. */
export default function ModelChips() {
  const [models, setModels] = useState(null)

  useEffect(() => {
    fetch('/api/models').then((r) => r.json()).then((j) => setModels(j.models || [])).catch(() => setModels([]))
  }, [])

  return (
    <Card>
      <SectionTitle right={<Badge tone="secondary">eval harness</Badge>}>Model Leaderboard</SectionTitle>
      {!models ? (
        <div className="text-[11px] font-light text-[#57534E]">loading checkpoints…</div>
      ) : models.length === 0 ? (
        <EmptyState glyph="◈">no checkpoints found</EmptyState>
      ) : (
        <div className="flex flex-col gap-1.5">
          {models.map((m) => (
            <div key={m.name} className={`flex items-center justify-between rounded-sm border px-2.5 py-1.5 ${m.name === 'current' ? 'border-[#0F766E] bg-[#CFE4E2]' : 'border-[#E2DED4] bg-[#FFFFFF]'}`}>
              <span className="text-[11px] font-light text-[#1C1917]">
                {m.label || m.name}
                {m.name === 'current' && <Badge tone="primary" className="ml-2">live</Badge>}
              </span>
              <span className="text-[11px] font-light tabular-nums text-[#57534E]">
                {m.val_auc != null ? `AUC ${Number(m.val_auc).toFixed(3)}` : '—'}
              </span>
            </div>
          ))}
        </div>
      )}
      <div className="mt-2 text-[10px] font-light text-[#57534E]">compare any two live in the A/B replay panel</div>
    </Card>
  )
}
