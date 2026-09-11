const STAGES = [
  { id: 0, key: 'benign', label: 'BENIGN',        ta: '—',       },
  { id: 1, key: 'recon',  label: 'RECONNAISSANCE', ta: 'TA0043' },
  { id: 2, key: 'enum',   label: 'CREDENTIAL ACCESS', ta: 'TA0006' },
  { id: 3, key: 'c2',     label: 'COMMAND & CONTROL', ta: 'TA0011' },
  { id: 4, key: 'impact', label: 'IMPACT',         ta: 'TA0042' },
]

export default function KillChain({ stage }) {
  return (
    <div className="rounded-2xl border border-line bg-ivory-soft shadow-soft p-4">
      <div className="text-xs tracking-widest text-ink-soft uppercase mb-3">
        MITRE ATT&CK Kill-Chain Progression
      </div>
      <div className="flex items-stretch gap-1">
        {STAGES.map((s) => {
          const active = stage === s.id
          const passed = stage > s.id
          return (
            <div key={s.id}
              className={`flex-1 rounded-lg border px-2 py-3 text-center transition-all duration-500
                ${active ? 'border-orange-400 bg-orange-100 shadow-soft' :
                  passed ? 'border-blue-200 bg-blue-50' :
                  'border-line bg-ivory-deep/60 opacity-60'}`}>
              <div className={`text-[9px] font-bold tracking-wider ${active ? 'text-orange-700' : passed ? 'text-blue-600' : 'text-ink-faint'}`}>
                {s.ta}
              </div>
              <div className={`mt-1 text-[10px] leading-tight ${active ? 'text-orange-800' : passed ? 'text-blue-700' : 'text-ink-faint'}`}>
                {s.label}
              </div>
            </div>
          )
        })}
      </div>
      <div className="mt-3 h-1.5 rounded-full bg-ivory-deep overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-lime-500 via-blue-500 to-orange-500 transition-all duration-700"
          style={{ width: `${(stage / 4) * 100}%` }}
        />
      </div>
    </div>
  )
}
