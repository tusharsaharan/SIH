import { useState } from 'react'

const SPEEDS = [60, 120, 240]

/** Session launcher: kind cards + speed select instead of a bare button. */
export default function LaunchModal({ kinds, onStart, onClose }) {
  const [kind, setKind] = useState('multi')
  const [speed, setSpeed] = useState(150)

  return (
    <div className="fixed inset-0 z-40 grid place-items-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60" />
      <div className="relative w-full max-w-md rounded-md border border-[#E2DED4] bg-[#FFFFFF] p-5"
        onClick={(e) => e.stopPropagation()}>
        <div className="qf-section-title">Launch attack simulation</div>
        <div className="mt-3 flex flex-col" style={{ gap: 16 }}>
          {(kinds || []).map((k) => (
            <button key={k.id} onClick={() => setKind(k.id)}
              className={`rounded-sm border px-3.5 py-2.5 text-left transition
                ${kind === k.id ? 'border-[#0F766E] bg-[#CFE4E2]' : 'border-[#E2DED4] bg-[#FFFFFF] hover:border-[#57534E]'}`}>
              <div className={`text-xs font-light ${kind === k.id ? 'text-[#115E59]' : 'text-[#1C1917]'}`}>{k.label}</div>
              <div className="text-[10px] font-light text-[#57534E]">{k.hint}</div>
            </button>
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between">
          <span className="text-[11px] font-light text-[#57534E]">replay speed</span>
          <div className="flex rounded-sm border border-[#E2DED4] overflow-hidden">
            {SPEEDS.map((s) => (
              <button key={s} onClick={() => setSpeed(s)}
                className={`px-3 py-1 text-[11px] font-light tabular-nums ${speed === s ? 'bg-[#0F766E] text-white' : 'text-[#57534E] hover:text-[#1C1917]'}`}>
                {s}×
              </button>
            ))}
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <button onClick={onClose}
            className="qf-btn qf-btn-secondary flex-1">Cancel</button>
          <button onClick={() => onStart(kind, speed)}
            className="qf-btn qf-btn-primary qf-btn-hero flex-[2]">
            ▶ Start session
          </button>
        </div>
      </div>
    </div>
  )
}
