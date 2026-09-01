export default function Header({ connected, running, paused, latest, onLaunch,
  onStop, onTogglePause, kind, setKind, kinds = [], sessionId }) {
  return (
    <header className="flex items-center justify-between border-b border-line bg-ivory/85 px-6 py-3 backdrop-blur sticky top-0 z-10 shadow-soft">
      <div className="flex items-center gap-3">
        <div className="grid place-items-center w-9 h-9 rounded-xl bg-gradient-to-br from-blue-600 to-orange-500 font-black text-ivory shadow-soft">
          Æ
        </div>
        <div>
          <div className="text-sm font-bold tracking-wider text-ink">AEGISFORECAST</div>
          <div className="text-[10px] text-ink-soft">AI Network Attack Forecasting · SOC Command Center</div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {kinds.length > 0 && (
          <div className="hidden md:flex rounded-xl border border-line bg-ivory-soft overflow-hidden shadow-soft">
            {kinds.map((k) => (
              <button key={k.id} onClick={() => setKind(k.id)} disabled={running}
                title={k.hint}
                className={`px-3 py-1.5 text-[10px] font-semibold tracking-wide
                  ${kind === k.id
                    ? 'bg-blue-600 text-white'
                    : 'text-ink-soft hover:bg-ivory-deep'}
                  ${running ? 'opacity-50 cursor-not-allowed' : ''}`}>
                {k.label}
              </button>
            ))}
          </div>
        )}

        <div className="hidden lg:flex items-center gap-4 text-[11px]">
          <Status label="WS" ok={connected} />
          <Status label={paused ? 'PAUSED' : 'SIM'} ok={running && !paused} />
          {latest && (
            <span className="text-ink-faint">
              t+<span className="text-ink tabular-nums">{latest.simMinute.toFixed(1)}</span>m
              {latest.host ? ` · ${latest.host}` : ''}
            </span>
          )}
          {latest?.horizon > 0 && (
            <span className="text-orange-600">ETA detonation {latest.horizon}m</span>
          )}
        </div>

        {running ? (
          <button onClick={onLaunch} disabled
            className="rounded-lg border border-lime-600 bg-lime-50 px-4 py-1.5 text-xs font-semibold text-lime-700 opacity-60 cursor-not-allowed">
            ▶ {sessionId || 'live'}
          </button>
        ) : null}
        {running ? (
          <>
            <button onClick={onTogglePause}
              className="rounded-lg border border-blue-300 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-100">
              {paused ? '▶ Resume' : '⏸ Pause'}
            </button>
            <button onClick={onStop}
              className="rounded-lg border border-orange-300 bg-orange-50 px-4 py-1.5 text-xs font-semibold text-orange-700 hover:bg-orange-100">
              ■ Abort Session
            </button>
          </>
        ) : (
          <button onClick={onLaunch}
            className="rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white shadow-soft hover:bg-blue-500">
            ▶ Launch Attack Simulation
          </button>
        )}
      </div>
    </header>
  )
}

function Status({ label, ok }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-lime-500 animate-pulse' : 'bg-line'}`} />
      <span className={ok ? 'text-lime-700' : 'text-ink-faint'}>{label}</span>
    </span>
  )
}
