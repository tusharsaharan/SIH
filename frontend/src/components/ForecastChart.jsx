import {
  ResponsiveContainer, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts'

export default function ForecastChart({ telemetry, threshold = 0.72, detonationMin = null, markers = [] }) {
  const data = telemetry.map((t) => ({
    minute: t.simMinute,
    prob: t.prob,
  }))
  const detLine = detonationMin ?? telemetry.find((t) => t.detonation)?.simMinute ?? null

  return (
    <div className="rounded-md border border-[#E2DED4] bg-[#FFFFFF] p-4 h-72">
      <div className="flex items-center justify-between mb-2">
        <span className="qf-section-title">
          Attack Probability — Live Forecast
        </span>
        <span className="text-[10px] font-light text-[#57534E]">
          alert threshold {Math.round(threshold * 100)}%
        </span>
      </div>
      <ResponsiveContainer width="100%" height="85%">
        <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -18 }}>
          <defs>
            <linearGradient id="probFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0F766E" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#0F766E" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#E2DED4" strokeDasharray="3 3" />
          <XAxis dataKey="minute" tick={{ fill: '#57534E', fontSize: 10 }} unit="m" />
          <YAxis domain={[0, 1]} tick={{ fill: '#57534E', fontSize: 10 }} />
          <Tooltip
            contentStyle={{ background: '#FFFFFF', border: '1px solid #E2DED4', borderRadius: 4, fontSize: 12, color: '#1C1917' }}
            labelFormatter={(m) => `sim-minute ${m}`}
          />
          <ReferenceLine y={threshold} stroke="#1C1917" strokeDasharray="6 3"
            label={{ value: 'ALERT', fill: '#1C1917', fontSize: 10, position: 'insideTopRight' }} />
          {detLine && (
            <ReferenceLine x={detLine} stroke="#B42318"
              label={{ value: 'DETONATION', fill: '#B42318', fontSize: 10, position: 'top' }} />
          )}
          {markers.map((m, i) => (
            <ReferenceLine key={i} x={m.simMinute} stroke="#A8A29E" strokeDasharray="3 2"
              label={{ value: 'CONTAIN', fill: '#57534E', fontSize: 9, position: 'insideBottomRight' }} />
          ))}
          <Area type="monotone" dataKey="prob" stroke="#0F766E" strokeWidth={2}
            fill="url(#probFill)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
