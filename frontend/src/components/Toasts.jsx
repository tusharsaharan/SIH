/** Toast notifications (bottom-right, auto-dismiss). Controlled by App. */
export default function Toasts({ toasts, onDismiss }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80">
      {toasts.map((t) => (
        <div key={t.id}
          className="rounded-sm border border-[#E2DED4] bg-[#FFFFFF] px-3.5 py-2.5 text-[11px] font-light cursor-pointer border-l-2"
          style={{ borderLeftColor: t.tone === 'error' ? '#B42318' : '#0F766E' }}
          onClick={() => onDismiss(t.id)}>
          <div className={`font-light tracking-wide text-[10px] uppercase
            ${t.tone === 'error' ? 'text-[#B42318]' : 'text-[#1C1917]'}`}>
            {t.title}
          </div>
          <div className="mt-0.5 text-[#57534E]">{t.body}</div>
        </div>
      ))}
    </div>
  )
}
