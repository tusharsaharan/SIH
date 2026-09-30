const SEV_STYLE = {
  HIGH: 'border-[#B42318] text-[#B42318]',
  MEDIUM: 'border-[#0F766E] text-[#1C1917]',
  LOW: 'border-[#E2DED4] text-[#57534E]',
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
    <div className="rounded-md border border-[#E2DED4] bg-[#FFFFFF] p-4 flex flex-col h-96">
      <div className="flex items-center justify-between mb-2">
        <div>
          <span className="qf-section-title">
            Guardrailed Playbook
          </span>
          <div className="text-[10px] font-light text-[#57534E]">
            AST scan {steps.length ? `· ${steps.length} finding families` : ''}
            {ctx.mitre ? ` · context ${ctx.mitre}` : ''}
          </div>
        </div>
        <button onClick={onRefresh} disabled={loading}
          className="qf-btn qf-btn-secondary !h-8 !px-3 !text-[10px]">
          {loading ? 'scanning…' : '↻ Rescan'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {!steps.length && !unmapped.length ? (
          <div className="grid place-items-center h-full text-[#57534E] text-xs font-light">
            no findings — code clean
          </div>
        ) : (
          <>
            {steps.map((s, i) => (
              <details key={i} className={`rounded-sm border bg-[#F4F3EF] px-3 py-2 ${SEV_STYLE[s.severity] || SEV_STYLE.LOW}`}>
                <summary className="cursor-pointer text-[11px] font-light list-none flex justify-between text-[#1C1917]">
                  <span>{i + 1}. {s.family} <span className="opacity-60">({s.severity})</span></span>
                  <span className="opacity-50 text-[9px]">{s.evidence.length} site{s.evidence.length > 1 ? 's' : ''}</span>
                </summary>
                <div className="mt-2 space-y-2">
                  {s.evidence.map((ev, j) => (
                    <div key={j} className="text-[9px] font-light text-[#57534E] truncate">
                      {ev.loc} — {ev.desc}
                    </div>
                  ))}
                  {['contain', 'harden', 'verify'].map((phase) => (
                    <div key={phase}>
                      <div className="text-[9px] uppercase tracking-wider opacity-60 text-[#57534E]">{phase}</div>
                      {s[phase].map((x, k) => (
                        <div key={k} className="text-[10px] font-light text-[#1C1917]">☐ {x}</div>
                      ))}
                    </div>
                  ))}
                </div>
              </details>
            ))}
            {unmapped.map((u, i) => (
              <div key={`u-${i}`} className="rounded-sm border border-[#E2DED4] bg-[#F4F3EF] px-3 py-2 text-[10px] font-light text-[#57534E]">
                unmapped: {u.rule} @ {u.loc} — manual triage
              </div>
            ))}
          </>
        )}
      </div>

      <div className="mt-2 pt-2 border-t border-[#E2DED4] text-[9px] font-light text-[#57534E]">
        generated from vetted templates — deterministic, zero-hallucination
      </div>
    </div>
  )
}
