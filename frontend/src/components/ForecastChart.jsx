import {
  ResponsiveContainer, LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts'

export default function ForecastChart({ telemetry, threshold = 0.72, detonationMin = null, markers = [] }) {
  const data = telemetry.map((t) => ({
    minute: t.simMinute,
    prob: t.prob,
  }))
  const detLine = detonationMin ?? telemetry.find((t) => t.detonation)?.simMinute ?? null

  return (
    <div className="rounded-2xl border border-line bg-ivory-soft shadow-soft p-4 h-72">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs tracking-widest text-ink-soft uppercase">
          Attack Probability — Live Forecast
        </span>
        <span className="text-[10px] text-ink-faint">
          alert threshold {Math.round(threshold * 100)}%
        </span>
      </div>
      <ResponsiveContainer width="100%" height="85%">
        <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -18 }}>
          <defs>
            <linearGradient id="probFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f97316" stopOpacity={0.45} />
              <stop offset="100%" stopColor="#f97316" stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#E7DFC8" strokeDasharray="3 3" />
          <XAxis dataKey="minute" tick={{ fill: '#8A8272', fontSize: 10 }} unit="m" />
          <YAxis domain={[0, 1]} tick={{ fill: '#8A8272', fontSize: 10 }} />
          <Tooltip
            contentStyle={{ background: '#FFFEF7', border: '1px solid #E7DFC8', borderRadius: 8, fontSize: 12, color: '#3F3A2E' }}
            labelFormatter={(m) => `sim-minute ${m}`}
          />
          <ReferenceLine y={threshold} stroke="#2563EB" strokeDasharray="6 3"
            label={{ value: 'ALERT', fill: '#2563EB', fontSize: 10, position: 'insideTopRight' }} />
          {detLine && (
            <ReferenceLine x={detLine} stroke="#ea580c"
              label={{ value: 'DETONATION', fill: '#ea580c', fontSize: 10, position: 'top' }} />
          )}
          {markers.map((m, i) => (
            <ReferenceLine key={i} x={m.simMinute} stroke="#2563EB" strokeDasharray="3 2"
              label={{ value: 'CONTAIN', fill: '#2563EB', fontSize: 9, position: 'insideBottomRight' }} />
          ))}
          <Area type="monotone" dataKey="prob" stroke="#f97316" strokeWidth={2}
            fill="url(#probFill)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
