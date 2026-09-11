import { useEffect, useState } from 'react'

const API = '/api'

export async function startSim({ kind = 'single', reconMin = 18, detMin = 26, speed = 120 } = {}) {
  const r = await fetch(`${API}/sim/start?kind=${kind}&recon_min=${reconMin}&det_min=${detMin}&speed=${speed}`, {
    method: 'POST',
  })
  return r.json()
}

export async function stopSim() {
  await fetch(`${API}/sim/stop`, { method: 'POST' })
}

export async function pauseSim() {
  await fetch(`${API}/sim/pause`, { method: 'POST' })
}

export async function resumeSim() {
  await fetch(`${API}/sim/resume`, { method: 'POST' })
}

export async function respond(host, action) {
  const r = await fetch(`${API}/respond?host=${host}&action=${action}`, { method: 'POST' })
  return r.json()
}

export async function setAutoSoar(enabled) {
  const r = await fetch(`${API}/soar/auto?enabled=${enabled}`, { method: 'POST' })
  return r.json()
}

export async function fetchCampaigns() {
  const r = await fetch(`${API}/campaigns`)
  return (await r.json()).campaigns
}

export async function fetchHistory() {
  const r = await fetch(`${API}/history`)
  return (await r.json()).sessions
}

export function reportUrl(sid, fmt = 'html') {
  return `${API}/report/${sid}.${fmt}`
}

export function useHealth() {
  const [health, setHealth] = useState(null)
  useEffect(() => {
    const tick = async () => {
      try { setHealth(await (await fetch(`${API}/health`)).json()) } catch { setHealth(null) }
    }
    tick()
    const iv = setInterval(tick, 5000)
    return () => clearInterval(iv)
  }, [])
  return health
}
