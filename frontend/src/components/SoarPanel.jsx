/** SOAR console: incident state machine + analyst response buttons. */
const NEXT_ACTIONS = {
  detected: [['triage', 'Triage', 'blue'], ['isolate', 'Isolate Host', 'orange']],
  triaged: [['isolate', 'Isolate Host', 'orange']],
  contained: [['verify', 'Verify Clean', 'blue'], ['close', 'Close', 'muted']],
  verified: [['close', 'Close Incident', 'muted']],
  closed: [],
}

const BTN = {
  orange: 'border-orange-300 bg-orange-50 text-orange-700 hover:bg-orange-100',
  blue: 'border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100',
  muted: 'border-line bg-ivory-deep/60 text-ink-soft hover:bg-ivory-deep',
}

export default function SoarPanel({ incidents, onRespond, autoSoar, onToggleAuto }) {
  const list = Object.entries(incidents || {})

  return (
    <div className="rounded-2xl border border-line bg-ivory-soft shadow-soft p-4 h-72 flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs tracking-widest text-ink-soft uppercase">
          SOAR Response Console
        </span>
        <button onClick={onToggleAuto}
          className={`rounded-full px-2.5 py-1 text-[10px] font-semibold border
            ${autoSoar
              ? 'border-lime-500 bg-lime-50 text-lime-700'
              : 'border-line bg-ivory-deep/60 text-ink-faint'}`}>
          AUTO-SOAR {autoSoar ? 'ON' : 'OFF'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {!list.length ? (
          <div className="grid place-items-center h-full text-ink-faint text-xs">
            no open incidents
          </div>
        ) : list.map(([host, inc]) => (
          <div key={host} className="rounded-lg border border-line bg-ivory px-3 py-2 shadow-soft">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-ink">
                {host}
              </span>
              <span className={`text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded
                ${inc.state === 'closed' ? 'bg-lime-100 text-lime-700'
                  : inc.state === 'detected' ? 'bg-orange-100 text-orange-700'
                  : 'bg-blue-100 text-blue-700'}`}>
                {inc.state}
              </span>
            </div>
            <div className="flex gap-1.5 mt-1.5">
              {(NEXT_ACTIONS[inc.state] || []).map(([action, label, color]) => (
                <button key={action}
                  onClick={() => onRespond(host, action)}
                  className={`rounded-md border px-2 py-1 text-[10px] font-semibold ${BTN[color]}`}>
                  {label}
                </button>
              ))}
              {!(NEXT_ACTIONS[inc.state] || []).length && (
                <span className="text-[10px] text-ink-faint">no further actions</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
