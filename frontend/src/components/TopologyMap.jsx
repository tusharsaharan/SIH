const POS = {
  ATTACKER: { x: 50, y: 8 },
  DC: { x: 50, y: 34 },
  WEB: { x: 16, y: 34 },
  DB: { x: 84, y: 34 },
  FILE: { x: 16, y: 72 },
  WS1: { x: 84, y: 72 },
}
const ROLE_LABEL = {
  'domain-controller': 'DC · auth',
  'web-server': 'WEB · 443',
  'database': 'DB · 3306',
  'file-server': 'FILE · SMB',
  'workstation': 'WS1 · client',
}

function riskColor(risk) {
  if (risk >= 0.8) return { fill: '#FFEDD5', stroke: '#ea580c', text: '#9a3412' }
  if (risk >= 0.5) return { fill: '#DBEAFE', stroke: '#2563EB', text: '#1d4ed8' }
  if (risk > 0.2) return { fill: '#EFF6FF', stroke: '#93c5fd', text: '#3b82f6' }
  return { fill: '#ECFCCB', stroke: '#65a30d', text: '#4d7c0f' }
}

export default function TopologyMap({ topology, onSelectHost, selectedHost }) {
  const hosts = topology?.hosts || []
  const edges = topology?.edges || []
  const byName = Object.fromEntries(hosts.map((h) => [h.name, h]))
  const edgeSet = new Set(edges.map((e) => e.to))

  return (
    <div className="rounded-2xl border border-line bg-ivory-soft shadow-soft p-3 h-80">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs tracking-widest text-ink-soft uppercase">
          Segment Topology — Live Risk
        </span>
        <span className="text-[10px] text-ink-faint">
          campaign P {((topology?.campaignRisk ?? 0) * 100).toFixed(0)}%
        </span>
      </div>
      <svg viewBox="0 0 100 100" className="w-full h-[calc(100%-1.5rem)]" preserveAspectRatio="xMidYMid meet">
        {/* benign segment links */}
        {['WEB-DC', 'DB-DC', 'FILE-DC', 'WS1-DC', 'WEB-DB'].map((l) => {
          const [a, b] = l.split('-')
          if (!POS[a] || !POS[b]) return null
          return <line key={l} x1={POS[a].x} y1={POS[a].y} x2={POS[b].x} y2={POS[b].y}
            stroke="#D8CFB6" strokeWidth={0.4} />
        })}

        {/* attack edges (animated) */}
        {edges.map((e, i) => {
          if (!POS[e.to]) return null
          return (
            <line key={i} x1={POS.ATTACKER.x} y1={POS.ATTACKER.y}
              x2={POS[e.to].x} y2={POS[e.to].y}
              stroke="#ea580c" strokeWidth={0.7}
              strokeDasharray="2 1.5">
              <animate attributeName="stroke-dashoffset" from="7" to="0" dur="0.8s" repeatCount="indefinite" />
            </line>
          )
        })}

        {/* attacker node */}
        {topology?.attackerIp && (
          <g>
            <circle cx={POS.ATTACKER.x} cy={POS.ATTACKER.y} r={4.4}
              fill="#FFEDD5" stroke="#ea580c" strokeWidth={0.8}
              className={edges.length ? 'animate-pulse' : ''} />
            <text x={POS.ATTACKER.x} y={POS.ATTACKER.y + 0.9} textAnchor="middle"
              fill="#9a3412" fontSize={2.6} fontWeight="bold">!</text>
            <text x={POS.ATTACKER.x} y={POS.ATTACKER.y + 7.4} textAnchor="middle"
              fill="#c2410c" fontSize={2.4} fontFamily="monospace">
              {topology.attackerIp}
            </text>
          </g>
        )}

        {/* host nodes */}
        {hosts.map((h) => {
          const p = POS[h.name]
          if (!p) return null
          const c = riskColor(h.risk)
          const attacked = edgeSet.has(h.name)
          const isolated = h.incident === 'contained' || h.incident === 'verified'
          return (
            <g key={h.name} onClick={() => onSelectHost?.(h.name)}
              style={onSelectHost ? { cursor: 'pointer' } : undefined}>
              <rect x={p.x - 9} y={p.y - 4} width={18} height={8} rx={1.6}
                fill={c.fill} stroke={selectedHost === h.name ? '#2563EB' : c.stroke} strokeWidth={attacked ? 0.9 : selectedHost === h.name ? 1.1 : 0.5} />
              {isolated && <rect x={p.x - 10} y={p.y - 5} width={20} height={10} rx={2}
                fill="none" stroke="#65a30d" strokeWidth={0.5} strokeDasharray="1.5 1" />}
              <text x={p.x} y={p.y - 0.4} textAnchor="middle" fill={c.text}
                fontSize={3} fontWeight="700">{h.name}</text>
              <text x={p.x} y={p.y + 2.6} textAnchor="middle" fill="#8A8272"
                fontSize={1.9} fontFamily="monospace">{ROLE_LABEL[h.role] || h.role}</text>
              <text x={p.x} y={p.y + 4.9} textAnchor="middle" fill={c.stroke}
                fontSize={2.1} fontFamily="monospace">
                P={(h.risk * 100).toFixed(0)}%
                {h.incident ? ` · ${h.incident}` : ''}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
