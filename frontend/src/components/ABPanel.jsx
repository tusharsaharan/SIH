import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, Legend,
} from 'recharts'

/**
 * Model A/B replay: same recorded session through current model (A)
 * vs a selectable challenger (B): transformer, ensemble, baseline.
 * Shows which model alerts earlier.
 */
export default function ABPanel({ sessionId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [challenger, setChallenger] = useState('ensemble')
  const [models, setModels] = useState([])

  useEffect(() => {
    fetch('/api/models').then((r) => r.json()).then((j) => setModels(j.models || [])).catch(() => {})
  }, [])

  const run = async () => {
    if (!sessionId) return
    setLoading(true)
    try {
      const r = await fetch(`/api/replay/${sessionId}?host=WEB&model_b=${challenger}`)
      setData(await r.json())
    } catch { setData({ error: true }) }
    finally { setLoading(false) }
  }

  // merge trajectories on simMinute for one chart
  let merged = []
  if (data?.trajectoryA) {
    const byMin = {}
    for (const t of data.trajectoryA) byMin[t.simMinute] = { minute: t.simMinute, modelA: t.prob }
    for (const t of data.trajectoryB || []) {
      byMin[t.simMinute] = { ...(byMin[t.simMinute] || { minute: t.simMinute }), modelB: t.prob }
    }
    merged = Object.values(byMin).sort((a, b) => a.minute - b.minute)
  }

  return (
    <div className="rounded-md border border-[#E2DED4] bg-[#FFFFFF] p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="qf-section-title">
          Model A/B Replay
        </span>
        <div className="flex items-center gap-1.5">
          <select value={challenger} onChange={(e) => setChallenger(e.target.value)}
            className="qf-input !p-1.5 !text-[10px]">
            {['ensemble', 'transformer', 'baseline'].map((m) => {
              const info = models.find((x) => x.name === m)
              const ok = info?.available !== false
              return <option key={m} value={m} disabled={!ok}>
                B: {m}{info?.val_auc ? ` (AUC ${info.val_auc})` : ''}{ok ? '' : ' (n/a)'}
              </option>
            })}
          </select>
          <button onClick={run} disabled={loading || !sessionId}
            className="qf-btn qf-btn-secondary !h-8 !px-3 !text-[10px]">
            {loading ? 'replaying…' : '▶ Compare'}
          </button>
        </div>
      </div>

      {data?.error && <div className="text-xs font-light text-[#B42318]">replay failed</div>}

      {data && !data.error && (
        <>
          <div className="flex gap-4 text-[10px] font-light text-[#57534E] mb-2">
            <span>A first alert: <b className="text-[#1C1917] font-light">
              {data.firstAlertA != null ? `t+${data.firstAlertA}m` : '—'}</b></span>
            <span>B first alert: <b className="text-[#B45309] font-light">
              {data.firstAlertB != null ? `t+${data.firstAlertB}m` : '—'}</b></span>
            <span>detonation: <b className="text-[#B42318] font-light">t+{data.detonationMin}m</b></span>
          </div>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={merged} margin={{ top: 4, right: 8, bottom: 4, left: -18 }}>
                <CartesianGrid stroke="#E2DED4" strokeDasharray="3 3" />
                <XAxis dataKey="minute" tick={{ fill: '#57534E', fontSize: 9 }} unit="m" />
                <YAxis domain={[0, 1]} tick={{ fill: '#57534E', fontSize: 9 }} />
                <Tooltip contentStyle={{ background: '#FFFFFF', border: '1px solid #E2DED4', borderRadius: 4, fontSize: 11, color: '#1C1917' }} />
                <Legend wrapperStyle={{ fontSize: 10, color: '#57534E' }} />
                <ReferenceLine y={0.72} stroke="#1C1917" strokeDasharray="6 3" />
                <Line type="monotone" dataKey="modelA" name="A: current BiLSTM" stroke="#0F766E"
                  strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="modelB" name={`B: ${data.modelB || 'challenger'}`} stroke="#D97706"
                  strokeWidth={1.5} strokeDasharray="4 2" dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  )
}
