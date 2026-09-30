export default function Header({ connected, running, paused, latest, onLaunch,
  onStop, onTogglePause, kind, setKind, kinds = [], sessionId }) {
  return (
    <header className="flex items-center justify-between border-b border-[#E2DED4] bg-[#FFFFFF] px-6 sticky top-0 z-10" style={{ height: 88 }}>
      <div className="flex items-center gap-4">
        <div className="grid place-items-center w-11 h-11 rounded-sm bg-[#0F766E] text-white text-xl">
          Æ
        </div>
        <div>
          <div className="qf-label-lg tracking-wider text-[#1C1917]">AEGISFORECAST</div>
          <div className="qf-body-sm text-[#57534E]">AI Network Attack Forecasting · SOC Command Center</div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {kinds.length > 0 && (
          <div className="hidden md:flex rounded-sm border border-[#E2DED4] overflow-hidden">
            {kinds.map((k) => (
              <button key={k.id} onClick={() => setKind(k.id)} disabled={running}
                title={k.hint}
                className={`qf-nav px-4 ${kind === k.id
                    ? 'bg-[#0F766E] text-white'
                    : 'text-[#57534E] hover:text-[#1C1917]'}
                  ${running ? 'opacity-50 cursor-not-allowed' : ''}`}
                style={{ height: 44 }}>
                {k.label}
              </button>
            ))}
          </div>
        )}

        <div className="hidden lg:flex items-center gap-4 qf-body-sm text-[#57534E]">
          <Status label="WS" ok={connected} />
          <Status label={paused ? 'PAUSED' : 'SIM'} ok={running && !paused} />
          {latest && (
            <span>
              t+<span className="text-[#1C1917] tabular-nums">{latest.simMinute.toFixed(1)}</span>m
              {latest.host ? ` · ${latest.host}` : ''}
            </span>
          )}
          {latest?.horizon > 0 && (
            <span className="text-[#B42318]">ETA detonation {latest.horizon}m</span>
          )}
        </div>

        {running ? (
          <span className="qf-chip tabular-nums">
            ▶ {sessionId || 'live'}
          </span>
        ) : null}
        {running ? (
          <>
            <button onClick={onTogglePause} className="qf-btn qf-btn-secondary">
              {paused ? '▶ Resume' : '⏸ Pause'}
            </button>
            <button onClick={onStop} className="qf-btn qf-btn-error">
              ■ Abort Session
            </button>
          </>
        ) : (
          <button onClick={onLaunch} className="qf-btn qf-btn-primary">
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
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-[#0F766E] animate-pulse' : 'bg-[#E2DED4]'}`} />
      <span className={ok ? 'text-[#1C1917]' : 'text-[#57534E]'}>{label}</span>
    </span>
  )
}
