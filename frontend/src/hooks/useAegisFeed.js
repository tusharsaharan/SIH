import { useEffect, useRef, useState } from 'react'

/**
 * Live WebSocket feed from the AegisForecast backend.
 * Reconnects automatically; keeps rolling buffers of telemetry/alerts/etc.
 */
export function useAegisFeed() {
  const [connected, setConnected] = useState(false)
  const [telemetry, setTelemetry] = useState([])       // [{simMinute, prob, stage...}]
  const [alerts, setAlerts] = useState([])
  const [containment, setContainment] = useState([])
  const [events, setEvents] = useState([])
  const [incidents, setIncidents] = useState({})      // host -> {state}
  const [soarLog, setSoarLog] = useState([])
  const [topologyEdges, setTopologyEdges] = useState([])
  const [latest, setLatest] = useState(null)
  const wsRef = useRef(null)

  useEffect(() => {
    let closed = false
    let retry

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws`)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        if (!closed) retry = setTimeout(connect, 1500)
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'telemetry') {
          const f = msg.forecast
          const point = {
            simMinute: f.simMinute,
            prob: f.attackProb,
            host: f.host,
            hostRisks: f.hostRisks || {},
            stage: f.stage,
            stageName: f.stageName,
            tactic: f.tactic,
            mitre: f.mitre,
            horizon: f.horizonMin,
            alert: f.alert,
            shap: f.shap,
            emitMs: msg.emitMs ?? null,
          }
          setLatest(point)
          setTelemetry((t) => {
            const next = [...t, point]
            return next.length > 400 ? next.slice(-400) : next
          })
        } else if (msg.type === 'alert') {
          setAlerts((a) => [msg, ...a].slice(0, 100))
        } else if (msg.type === 'containment') {
          setContainment((c) => [msg, ...c].slice(0, 50))
        } else if (msg.type === 'soar') {
          setSoarLog((l) => [msg, ...l].slice(0, 50))
          setIncidents((inc) => ({
            ...inc,
            [msg.host]: { ...inc[msg.host], host: msg.host, state: msg.toState },
          }))
        } else if (msg.type === 'topology_edge') {
          setTopologyEdges((e) => {
            if (e.some((x) => x.to === msg.to)) return e
            return [...e, { from: 'ATTACKER', to: msg.to, simMinute: msg.simMinute }]
          })
        } else if (msg.type === 'event') {
          setEvents((e) => [msg, ...e].slice(0, 30))
        }
      }
    }

    connect()
    return () => { closed = true; clearTimeout(retry); wsRef.current?.close() }
  }, [])

  return { connected, telemetry, alerts, containment, events, incidents, soarLog, topologyEdges, latest }
}
