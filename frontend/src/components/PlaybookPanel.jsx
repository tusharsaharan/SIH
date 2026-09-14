const SEV_COLOR = {
  HIGH: 'border-orange-400 bg-orange-50 text-orange-800',
  MEDIUM: 'border-blue-300 bg-blue-50 text-blue-800',
  LOW: 'border-line bg-ivory-deep/60 text-ink-soft',
}

/**
 * Guardrailed playbook viewer: AST findings -> contain/harden/verify steps.
 * Every step comes from the vetted template library (zero hallucination).
 */
export default function PlaybookPanel({ playbook, onRefresh, loading }) {
  const steps = playbook?.steps || []
  const ctx = playbook?.attackContext || {}
  const unmapped = playbook?.unmapped || []

  return (
    <div className="rounded-2xl border border-line bg-ivory-soft shadow-soft p-4 flex flex-col h-96">
      <div className="flex items-center justify-between mb-2">
        <div>
          <span className="text-xs tracking-widest text-ink-soft uppercase">
            Guardrailed Playbook
          </span>
          <div className="text-[10px] text-ink-faint">
            AST scan {steps.length ? `· ${steps.length} finding families` : ''}
            {ctx.mitre ? ` · context ${ctx.mitre}` : ''}
          </div>
        </div>
        <button onClick={onRefresh} disabled={loading}
          className="rounded-lg border border-line bg-ivory px-2.5 py-1 text-[10px] text-ink-soft
                     hover:bg-ivory-deep disabled:opacity-40 shadow-soft">
          {loading ? 'scanning…' : '↻ Rescan'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {!steps.length && !unmapped.length ? (
          <div className="grid place-items-center h-full text-ink-faint text-xs">
            no findings — code clean
          </div>
        ) : (
          <>
            {steps.map((s, i) => (
              <details key={i} className={`rounded-lg border px-3 py-2 ${SEV_COLOR[s.severity] || SEV_COLOR.LOW}`}>
                <summary className="cursor-pointer text-[11px] font-semibold list-none flex justify-between">
                  <span>{i + 1}. {s.family} <span className="opacity-60">({s.severity})</span></span>
                  <span className="opacity-50 text-[9px]">{s.evidence.length} site{s.evidence.length > 1 ? 's' : ''}</span>
                </summary>
                <div className="mt-2 space-y-2">
                  {s.evidence.map((ev, j) => (
                    <div key={j} className="text-[9px] text-ink-soft truncate">
                      {ev.loc} — {ev.desc}
                    </div>
                  ))}
                  {['contain', 'harden', 'verify'].map((phase) => (
                    <div key={phase}>
                      <div className="text-[9px] uppercase tracking-wider opacity-60">{phase}</div>
                      {s[phase].map((x, k) => (
                        <div key={k} className="text-[10px] text-ink">☐ {x}</div>
                      ))}
                    </div>
                  ))}
                </div>
              </details>
            ))}
            {unmapped.map((u, i) => (
              <div key={`u-${i}`} className="rounded-lg border border-line bg-ivory-deep/60 px-3 py-2 text-[10px] text-ink-soft">
                unmapped: {u.rule} @ {u.loc} — manual triage
              </div>
            ))}
          </>
        )}
      </div>

      <div className="mt-2 pt-2 border-t border-line text-[9px] text-ink-faint">
        generated from vetted templates — deterministic, zero-hallucination
      </div>
    </div>
  )
}
