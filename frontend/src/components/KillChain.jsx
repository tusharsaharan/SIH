const STAGES = [
  { id: 0, key: 'benign', label: 'BENIGN',        ta: '—',       },
  { id: 1, key: 'recon',  label: 'RECONNAISSANCE', ta: 'TA0043' },
  { id: 2, key: 'enum',   label: 'CREDENTIAL ACCESS', ta: 'TA0006' },
  { id: 3, key: 'c2',     label: 'COMMAND & CONTROL', ta: 'TA0011' },
  { id: 4, key: 'impact', label: 'IMPACT',         ta: 'TA0042' },
]

export default function KillChain({ stage }) {
  return (
    <div className="rounded-md border border-[#E2DED4] bg-[#FFFFFF] p-4">
      <div className="qf-section-title mb-3">
        MITRE ATT&CK Kill-Chain Progression
      </div>
      <div className="flex items-stretch" style={{ gap: 16 }}>
        {STAGES.map((s) => {
          const active = stage === s.id
          const passed = stage > s.id
          return (
            <div key={s.id}
              className={`flex-1 rounded-sm border px-2 py-3 text-center transition-all duration-500
                ${active ? 'border-[#B42318] bg-[#F0D3D1]' :
                  passed ? 'border-[#0F766E] bg-[#CFE4E2]' :
                  'border-[#E2DED4] bg-[#FFFFFF] opacity-60'}`}>
              <div className={`text-[9px] font-light tracking-wider ${active ? 'text-[#B42318]' : passed ? 'text-[#115E59]' : 'text-[#57534E]'}`}>
                {s.ta}
              </div>
              <div className={`mt-1 text-[10px] leading-tight font-light ${active ? 'text-[#B42318]' : passed ? 'text-[#115E59]' : 'text-[#57534E]'}`}>
                {s.label}
              </div>
            </div>
          )
        })}
      </div>
      <div className="mt-3 h-1.5 rounded-sm bg-[#F4F3EF] overflow-hidden border border-[#E2DED4]">
        <div
          className="h-full bg-[#0F766E] transition-all duration-700"
          style={{ width: `${(stage / 4) * 100}%` }}
        />
      </div>
    </div>
  )
}
