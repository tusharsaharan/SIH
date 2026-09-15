import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, Legend,
} from 'recharts'

/**
 * Model A/B replay: same recorded session through current model (A, cyan)
 * vs a selectable challenger (B, violet): transformer, ensemble, baseline.
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
    <div className="rounded-2xl border border-line bg-ivory-soft shadow-soft p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs tracking-widest text-ink-soft uppercase">
          Model A/B Replay
        </span>
        <div className="flex items-center gap-1.5">
          <select value={challenger} onChange={(e) => setChallenger(e.target.value)}
            className="rounded-md border border-line bg-ivory px-1.5 py-1 text-[10px] text-ink-soft">
            {['ensemble', 'transformer', 'baseline'].map((m) => {
              const info = models.find((x) => x.name === m)
              const ok = info?.available !== false
              return <option key={m} value={m} disabled={!ok}>
                B: {m}{info?.val_auc ? ` (AUC ${info.val_auc})` : ''}{ok ? '' : ' (n/a)'}
              </option>
            })}
          </select>
          <button onClick={run} disabled={loading || !sessionId}
            className="rounded-lg border border-blue-300 bg-blue-50 px-2.5 py-1 text-[10px] text-blue-700
                       hover:bg-blue-100 disabled:opacity-40">
            {loading ? 'replaying…' : '▶ Compare'}
          </button>
        </div>
      </div>

      {data?.error && <div className="text-xs text-orange-600">replay failed</div>}

      {data && !data.error && (
        <>
          <div className="flex gap-4 text-[10px] text-ink-soft mb-2">
            <span>A first alert: <b className="text-blue-700">
              {data.firstAlertA != null ? `t+${data.firstAlertA}m` : '—'}</b></span>
            <span>B first alert: <b className="text-orange-600">
              {data.firstAlertB != null ? `t+${data.firstAlertB}m` : '—'}</b></span>
            <span>detonation: <b className="text-orange-700">t+{data.detonationMin}m</b></span>
          </div>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={merged} margin={{ top: 4, right: 8, bottom: 4, left: -18 }}>
                <CartesianGrid stroke="#E7DFC8" strokeDasharray="3 3" />
                <XAxis dataKey="minute" tick={{ fill: '#8A8272', fontSize: 9 }} unit="m" />
                <YAxis domain={[0, 1]} tick={{ fill: '#8A8272', fontSize: 9 }} />
                <Tooltip contentStyle={{ background: '#FFFEF7', border: '1px solid #E7DFC8', borderRadius: 8, fontSize: 11, color: '#3F3A2E' }} />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                <ReferenceLine y={0.72} stroke="#2563EB" strokeDasharray="6 3" />
                <Line type="monotone" dataKey="modelA" name="A: current BiLSTM" stroke="#2563EB"
                  strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="modelB" name={`B: ${data.modelB || 'challenger'}`} stroke="#ea580c"
                  strokeWidth={1.5} strokeDasharray="4 2" dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  )
}
