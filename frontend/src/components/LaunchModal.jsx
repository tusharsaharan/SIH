import { useState } from 'react'

const SPEEDS = [60, 120, 240]

/** Session launcher: kind cards + speed select instead of a bare button. */
export default function LaunchModal({ kinds, onStart, onClose }) {
  const [kind, setKind] = useState('multi')
  const [speed, setSpeed] = useState(150)

  return (
    <div className="fixed inset-0 z-40 grid place-items-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-ink/25" />
      <div className="relative w-full max-w-md rounded-2xl border border-line bg-ivory shadow-lift p-5"
        onClick={(e) => e.stopPropagation()}>
        <div className="text-xs tracking-widest text-ink-soft uppercase">Launch attack simulation</div>
        <div className="mt-3 flex flex-col gap-2">
          {(kinds || []).map((k) => (
            <button key={k.id} onClick={() => setKind(k.id)}
              className={`rounded-xl border px-3.5 py-2.5 text-left transition
                ${kind === k.id ? 'border-blue-400 bg-blue-50 shadow-soft' : 'border-line bg-ivory-soft hover:bg-ivory-deep/60'}`}>
              <div className={`text-xs font-bold ${kind === k.id ? 'text-blue-800' : 'text-ink'}`}>{k.label}</div>
              <div className="text-[10px] text-ink-soft">{k.hint}</div>
            </button>
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between">
          <span className="text-[11px] text-ink-soft">replay speed</span>
          <div className="flex rounded-lg border border-line overflow-hidden">
            {SPEEDS.map((s) => (
              <button key={s} onClick={() => setSpeed(s)}
                className={`px-3 py-1 text-[11px] font-semibold tabular-nums ${speed === s ? 'bg-blue-600 text-white' : 'text-ink-soft hover:bg-ivory-deep'}`}>
                {s}×
              </button>
            ))}
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <button onClick={onClose}
            className="flex-1 rounded-lg border border-line px-3 py-2 text-xs font-semibold text-ink-soft hover:bg-ivory-deep">Cancel</button>
          <button onClick={() => onStart(kind, speed)}
            className="flex-[2] rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white shadow-soft hover:bg-blue-500">
            ▶ Start session
          </button>
        </div>
      </div>
    </div>
  )
}
