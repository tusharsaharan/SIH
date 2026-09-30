import {
  Radar, RadarChart, PolarAngleAxis, PolarGrid, ResponsiveContainer,
} from 'recharts'

/**
 * SHAP-over-time radar: importance of top features across recent forecasts.
 * props: history = [{shap: [{feature, importance}]}...]
 */
export default function ShapRadar({ history }) {
  // aggregate mean importance per feature over recent windows
  const recent = history.slice(-12)
  if (!recent.length) return null
  const acc = {}
  for (const h of recent) {
    for (const s of h.shap || []) {
      acc[s.feature] = (acc[s.feature] || 0) + s.importance
    }
  }
  const data = Object.entries(acc)
    .map(([feature, total]) => ({
      feature,
      importance: +(total / recent.length).toFixed(3),
    }))
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 6)

  return (
    <div className="rounded-md border border-[#E2DED4] bg-[#FFFFFF] p-4 h-64">
      <div className="qf-section-title mb-1">
        SHAP Attribution Radar — Recent Windows
      </div>
      <ResponsiveContainer width="100%" height="82%">
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke="#E2DED4" />
          <PolarAngleAxis dataKey="feature" tick={{ fill: '#57534E', fontSize: 9 }} />
          <Radar dataKey="importance" stroke="#0F766E" fill="#0F766E"
            fillOpacity={0.25} isAnimationActive={false} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
