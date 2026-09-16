/** Toast notifications (bottom-right, auto-dismiss). Controlled by App. */
export default function Toasts({ toasts, onDismiss }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80">
      {toasts.map((t) => (
        <div key={t.id}
          className={`rounded-xl border shadow-lift px-3.5 py-2.5 text-[11px] bg-ivory-soft cursor-pointer
            ${t.tone === 'orange' ? 'border-orange-300' : t.tone === 'lime' ? 'border-lime-300' : 'border-blue-300'}`}
          onClick={() => onDismiss(t.id)}>
          <div className={`font-bold tracking-wide text-[10px] uppercase
            ${t.tone === 'orange' ? 'text-orange-700' : t.tone === 'lime' ? 'text-lime-700' : 'text-blue-700'}`}>
            {t.title}
          </div>
          <div className="mt-0.5 text-ink-soft">{t.body}</div>
        </div>
      ))}
    </div>
  )
}
