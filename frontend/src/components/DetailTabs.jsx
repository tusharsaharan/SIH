import { useState } from 'react'

/** DetailTabs: one visible detail dock instead of six stacked panels.
 *  Tabs keep secondary analysis one click away without competing with
 *  the live command view above the fold. */
const TABS = [
  { id: 'explain', label: 'Explain' },
  { id: 'respond', label: 'Respond' },
  { id: 'models', label: 'Models' },
]

export default function DetailTabs({ renderExplain, renderRespond, renderModels, counts }) {
  const [tab, setTab] = useState('explain')

  return (
    <div className="rounded-md border border-[#E2DED4] bg-[#FFFFFF]">
      <div className="flex items-center border-b border-[#E2DED4]">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`qf-nav px-6 ${tab === t.id
                ? 'text-white bg-[#0F766E]'
                : 'text-[#57534E] hover:text-[#1C1917]'}`}
            style={{ height: 44 }}>
            {t.label}
            {counts?.[t.id] ? <span className="ml-2 tabular-nums opacity-70">{counts[t.id]}</span> : null}
          </button>
        ))}
        <span className="ml-auto pr-4 text-[10px] font-light text-[#57534E] hidden md:block">
          secondary analysis — kept out of the command view
        </span>
      </div>
      <div className="p-4">
        {tab === 'explain' && (
          <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: 16 }}>
            {renderExplain()}
          </div>
        )}
        {tab === 'respond' && (
          <div className="grid grid-cols-1 lg:grid-cols-3" style={{ gap: 16 }}>
            {renderRespond()}
          </div>
        )}
        {tab === 'models' && (
          <div className="flex flex-col" style={{ gap: 16 }}>
            {renderModels()?.[0]}
            <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: 16 }}>
              {renderModels()?.slice(1)}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
