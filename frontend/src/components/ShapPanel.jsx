export default function ShapPanel({ shap }) {
  const top = (shap || []).slice(0, 6)
  const maxImp = Math.max(...top.map((s) => s.importance), 0.001)

  return (
    <div className="rounded-2xl border border-line bg-ivory-soft shadow-soft p-4 h-72 flex flex-col">
      <div className="text-xs tracking-widest text-ink-soft uppercase mb-3">
        SHAP Explainability — Why This Forecast
      </div>
      {top.length === 0 ? (
        <div className="flex-1 grid place-items-center text-ink-faint text-xs">
          awaiting attribution…
        </div>
      ) : (
        <div className="flex-1 flex flex-col gap-2 justify-center">
          {top.map((s) => (
            <div key={s.feature} className="flex items-center gap-2">
              <div className="w-36 text-[11px] text-ink-soft truncate">{s.feature}</div>
              <div className="flex-1 h-4 rounded bg-ivory-deep overflow-hidden">
                <div className="h-full rounded bg-gradient-to-r from-blue-500 to-blue-700 transition-all duration-500"
                  style={{ width: `${(s.importance / maxImp) * 100}%` }} />
              </div>
              <div className="w-12 text-right text-[10px] text-ink-faint tabular-nums">
                {(s.importance * 100).toFixed(1)}%
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
