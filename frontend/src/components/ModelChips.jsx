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
      <SectionTitle right={<Badge tone="lime">eval harness</Badge>}>Model Leaderboard</SectionTitle>
      {!models ? (
        <div className="text-[11px] text-ink-faint">loading checkpoints…</div>
      ) : models.length === 0 ? (
        <EmptyState glyph="◈">no checkpoints found</EmptyState>
      ) : (
        <div className="flex flex-col gap-1.5">
          {models.map((m) => (
            <div key={m.name} className={`flex items-center justify-between rounded-lg border px-2.5 py-1.5 ${m.name === 'current' ? 'border-blue-300 bg-blue-50' : 'border-line bg-ivory'}`}>
              <span className="text-[11px] font-semibold text-ink">
                {m.label || m.name}
                {m.name === 'current' && <Badge tone="blue" className="ml-2">live</Badge>}
              </span>
              <span className="text-[11px] tabular-nums text-ink-soft">
                {m.val_auc != null ? `AUC ${Number(m.val_auc).toFixed(3)}` : '—'}
              </span>
            </div>
          ))}
        </div>
      )}
      <div className="mt-2 text-[10px] text-ink-faint">compare any two live in the A/B replay panel</div>
    </Card>
  )
}
