export default function ShapPanel({ shap }) {
  const top = (shap || []).slice(0, 6)
  const maxImp = Math.max(...top.map((s) => s.importance), 0.001)

  return (
    <div className="rounded-md border border-[#E2DED4] bg-[#FFFFFF] p-4 h-72 flex flex-col">
      <div className="qf-section-title mb-3">
        SHAP Explainability — Why This Forecast
      </div>
      {top.length === 0 ? (
        <div className="flex-1 grid place-items-center text-[#57534E] text-xs font-light">
          awaiting attribution…
        </div>
      ) : (
        <div className="flex-1 flex flex-col gap-2 justify-center">
          {top.map((s) => (
            <div key={s.feature} className="flex items-center gap-2">
              <div className="w-36 text-[11px] font-light text-[#57534E] truncate">{s.feature}</div>
              <div className="flex-1 h-4 rounded-sm bg-[#F4F3EF] border border-[#E2DED4] overflow-hidden">
                <div className="h-full bg-[#0F766E] transition-all duration-500"
                  style={{ width: `${(s.importance / maxImp) * 100}%` }} />
              </div>
              <div className="w-12 text-right text-[10px] font-light text-[#57534E] tabular-nums">
                {(s.importance * 100).toFixed(1)}%
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
