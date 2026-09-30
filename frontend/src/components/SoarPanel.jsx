/** SOAR console: incident state machine + analyst response buttons. */
const NEXT_ACTIONS = {
  detected: [['triage', 'Triage', 'secondary'], ['isolate', 'Isolate Host', 'error']],
  triaged: [['isolate', 'Isolate Host', 'error']],
  contained: [['verify', 'Verify Clean', 'secondary'], ['close', 'Close', 'muted']],
  verified: [['close', 'Close Incident', 'muted']],
  closed: [],
}

const BTN = {
  error: 'qf-btn qf-btn-error !h-8 !px-2 !text-[10px]',
  secondary: 'qf-btn qf-btn-secondary !h-8 !px-2 !text-[10px]',
  muted: 'rounded-sm border border-[#E2DED4] px-2 py-1 text-[10px] font-light text-[#57534E] hover:text-[#1C1917]',
}

export default function SoarPanel({ incidents, onRespond, autoSoar, onToggleAuto }) {
  const list = Object.entries(incidents || {})

  return (
    <div className="rounded-md border border-[#E2DED4] bg-[#FFFFFF] p-4 flex flex-col" style={{ minHeight: 280 }}>
      <div className="flex items-center justify-between mb-2">
        <span className="qf-section-title">
          SOAR Response Console
        </span>
        <button onClick={onToggleAuto}
          className="qf-chip">
          AUTO-SOAR {autoSoar ? 'ON' : 'OFF'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {!list.length ? (
          <div className="grid place-items-center h-full text-[#57534E] text-xs font-light">
            no open incidents
          </div>
        ) : list.map(([host, inc]) => (
          <div key={host} className="rounded-sm border border-[#E2DED4] bg-[#F4F3EF] px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-light text-[#1C1917]">
                {host}
              </span>
              <span className={`text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm border
                ${inc.state === 'closed' ? 'text-[#57534E] border-[#E2DED4]'
                  : inc.state === 'detected' ? 'text-[#B42318] border-[#B42318]'
                  : 'text-[#1C1917] border-[#0F766E]'}`}>
                {inc.state}
              </span>
            </div>
            <div className="flex gap-1.5 mt-1.5">
              {(NEXT_ACTIONS[inc.state] || []).map(([action, label, color]) => (
                <button key={action}
                  onClick={() => onRespond(host, action)}
                  className={BTN[color]}>
                  {label}
                </button>
              ))}
              {!(NEXT_ACTIONS[inc.state] || []).length && (
                <span className="text-[10px] font-light text-[#57534E]">no further actions</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
