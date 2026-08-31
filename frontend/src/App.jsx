import Header from './components/Header.jsx'
import ThreatGauge from './components/ThreatGauge.jsx'
import ForecastChart from './components/ForecastChart.jsx'
import KillChain from './components/KillChain.jsx'
import ShapPanel from './components/ShapPanel.jsx'
import ShapRadar from './components/ShapRadar.jsx'
import AlertFeed from './components/AlertFeed.jsx'
import PlaybookPanel from './components/PlaybookPanel.jsx'
import TopologyMap from './components/TopologyMap.jsx'
import SoarPanel from './components/SoarPanel.jsx'
import CampaignPanel from './components/CampaignPanel.jsx'
import ABPanel from './components/ABPanel.jsx'
import HealthStrip from './components/HealthStrip.jsx'
import ModelChips from './components/ModelChips.jsx'
import Toasts from './components/Toasts.jsx'
import HostDrawer from './components/HostDrawer.jsx'
import AlertModal from './components/AlertModal.jsx'
import ReportModal from './components/ReportModal.jsx'
import EvasionPanel from './components/EvasionPanel.jsx'
import LaunchModal from './components/LaunchModal.jsx'
import { useAegisFeed } from './hooks/useAegisFeed.js'
import { usePlaybook } from './hooks/usePlaybook.js'
import {
  startSim, stopSim, pauseSim, resumeSim, respond, setAutoSoar as apiSetAutoSoar,
  fetchCampaigns, fetchHistory, reportUrl, useHealth,
} from './hooks/api.js'
import { useEffect, useRef, useState } from 'react'

const KINDS = [
  { id: 'multi', label: 'Lateral APT', hint: '5-host segment, kill-chain spread' },
  { id: 'single', label: 'Single Host', hint: 'classic APT vs one server' },
  { id: 'evasion', label: 'Red-Team', hint: 'stealth scan + mimicry (honest)' },
]

export default function App() {
  const { connected, telemetry, alerts, containment, events, incidents,
          soarLog, topologyEdges, latest } = useAegisFeed()
  const { playbook, loading: pbLoading, refresh: pbRefresh } = usePlaybook()
  const health = useHealth()
  const threshold = health?.threshold ?? 0.72
  const [running, setRunning] = useState(false)
  const [paused, setPaused] = useState(false)
  const [kind, setKind] = useState('multi')
  const [campaigns, setCampaigns] = useState([])
  const [autoSoar, setAutoSoar] = useState(true)
  const [sessionId, setSessionId] = useState(null)
  const [history, setHistory] = useState([])
  const [toasts, setToasts] = useState([])
  const [selectedAlert, setSelectedAlert] = useState(null)
  const [selectedHost, setSelectedHost] = useState(null)
  const [reportSid, setReportSid] = useState(null)
  const [showLauncher, setShowLauncher] = useState(false)
  const toastId = useRef(0)
  const prevCounts = useRef({ alerts: 0, containment: 0 })

  const pushToast = (title, body, tone = 'blue') => {
    const id = ++toastId.current
    setToasts((t) => [...t, { id, title, body, tone }].slice(-4))
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000)
  }

  // toast on new alerts / containments
  useEffect(() => {
    if (alerts.length > prevCounts.current.alerts && prevCounts.current.alerts > 0) {
      const a = alerts[0]
      pushToast('attack forecast', `${a.host} · ${(a.attackProb * 100).toFixed(0)}% · ${a.mitre}`, 'orange')
    }
    prevCounts.current.alerts = alerts.length
  }, [alerts.length])
  useEffect(() => {
    if (containment.length > prevCounts.current.containment && prevCounts.current.containment > 0) {
      pushToast('containment dispatched', containment[0].rule || 'firewall rule applied', 'lime')
    }
    prevCounts.current.containment = containment.length
  }, [containment.length])

  const detonation = events.find((e) => e.event === 'detonation')
  const detonationMin = detonation?.simMinute ?? null
  const multi = kind === 'multi' || kind === 'evasion'

  // refresh campaigns when alerts arrive (debounced via effect on alert count)
  useEffect(() => {
    if (!alerts.length) return
    fetchCampaigns().then(setCampaigns).catch(() => {})
  }, [alerts.length])

  useEffect(() => {
    fetchHistory().then(setHistory).catch(() => {})
  }, [events.find((e) => e.event === 'session_end')])

  const onLaunch = async (launchKind = kind, speed = 150) => {
    const r = await startSim({ kind: launchKind, speed })
    if (r.started) {
      setRunning(true); setPaused(false)
      setSessionId(r.sessionId)
      setKind(launchKind)
      setShowLauncher(false)
      prevCounts.current = { alerts: 0, containment: 0 }
    }
  }
  const onStop = async () => { await stopSim(); setRunning(false); setPaused(false) }
  const onTogglePause = async () => {
    if (paused) { await resumeSim(); setPaused(false) }
    else { await pauseSim(); setPaused(true) }
  }
  const onRespond = async (host, action) => { await respond(host, action) }
  const onToggleAutoSoar = async () => {
    const r = await apiSetAutoSoar(!autoSoar); setAutoSoar(!!r.autoSoar)
  }

  const topology = {
    hosts: Object.entries(latest?.hostRisks || {}).map(([name, risk]) => ({
      name, risk,
      role: { DC: 'domain-controller', WEB: 'web-server', DB: 'database',
              FILE: 'file-server', WS1: 'workstation' }[name],
      incident: incidents[name]?.state ?? null,
    })),
    edges: topologyEdges,
    campaignRisk: latest?.prob ?? 0,
    attackerIp: '203.0.113.50',
  }

  return (
    <div className="min-h-screen bg-ivory text-ink">
      <Header connected={connected} running={running} paused={paused} latest={latest}
        onLaunch={() => setShowLauncher(true)} onStop={onStop} onTogglePause={onTogglePause}
        kind={kind} setKind={setKind} kinds={KINDS} sessionId={sessionId} />
      <HealthStrip connected={connected} latest={latest} health={health} />

      <main className="max-w-7xl mx-auto p-4 grid grid-cols-1 lg:grid-cols-12 gap-4">
        <section className="lg:col-span-3 flex flex-col gap-4">
          <ThreatGauge prob={latest?.prob ?? 0} threshold={threshold} />
          <div className="rounded-2xl border border-line bg-ivory-soft shadow-soft p-4">
            <div className="text-xs tracking-widest text-ink-soft uppercase mb-2">Forecast</div>
            <Row k="Top host" v={latest?.host ?? '—'} />
            <Row k="Current stage" v={latest ? `${latest.stageName}` : '—'} />
            <Row k="MITRE tactic" v={latest?.mitre ?? '—'} />
            <Row k="Lead time" v={latest?.horizon ? `${latest.horizon} min` : '—'} />
            <Row k="Windows seen" v={telemetry.length} />
          </div>
          {sessionId && (
            <a href={reportUrl(sessionId)} target="_blank" rel="noreferrer"
              className="rounded-2xl border border-blue-200 bg-blue-50 shadow-soft px-4 py-3 text-center text-xs font-semibold text-blue-700 hover:bg-blue-100">
              ⬇ Download Incident Report ({sessionId})
            </a>
          )}
        </section>

        <section className="lg:col-span-6 flex flex-col gap-4">
          {multi && <TopologyMap topology={topology} onSelectHost={setSelectedHost} selectedHost={selectedHost} />}
          <ForecastChart telemetry={telemetry} threshold={threshold} detonationMin={detonationMin} markers={containment} />
          <KillChain stage={latest?.stage ?? 0} />
          {sessionId && <ABPanel sessionId={sessionId} />}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ShapPanel shap={latest?.shap} />
            <ShapRadar history={telemetry} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ModelChips />
            <EvasionPanel />
          </div>
        </section>

        <section className="lg:col-span-3 flex flex-col gap-4">
          <SoarPanel incidents={incidents} onRespond={onRespond}
            autoSoar={autoSoar} onToggleAuto={onToggleAutoSoar} />
          <CampaignPanel campaigns={campaigns} />
          <PlaybookPanel playbook={playbook} onRefresh={pbRefresh} loading={pbLoading} />
          <AlertFeed alerts={alerts} containment={containment} onSelectAlert={setSelectedAlert} />
        </section>
      </main>

      {history.length > 0 && (
        <footer className="max-w-7xl mx-auto px-4 pb-6">
          <div className="text-[10px] tracking-widest text-ink-faint uppercase mb-2">
            Session History ({history.length})
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {history.map((s) => (
              <button key={s.session_id} onClick={() => setReportSid(s.session_id)}
                className="shrink-0 rounded-lg border border-line bg-ivory-soft shadow-soft px-3 py-1.5 text-[10px] text-ink-soft hover:border-blue-300 hover:text-blue-700">
                {s.session_id} · {s.kind} · {s.n_alerts} alerts →
              </button>
            ))}
          </div>
        </footer>
      )}

      <footer className="max-w-7xl mx-auto px-4 pb-6 text-[10px] text-ink-faint flex justify-between">
        <span>AegisForecast v0.3 — SIH PS 25217 · zero-upload eBPF telemetry · Bi-LSTM+Attention · SOAR</span>
        <span>{telemetry.length ? `${telemetry.length} windows ingested` : 'idle'}</span>
      </footer>

      <Toasts toasts={toasts} onDismiss={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
      <AlertModal alert={selectedAlert} onClose={() => setSelectedAlert(null)} onRespond={onRespond} />
      <HostDrawer
        host={selectedHost}
        hostRisk={latest?.hostRisks?.[selectedHost]}
        incident={selectedHost ? incidents[selectedHost] : null}
        hostAlerts={selectedHost ? alerts.filter((a) => a.host === selectedHost) : []}
        history={telemetry}
        onClose={() => setSelectedHost(null)}
        onRespond={onRespond}
      />
      <ReportModal sessionId={reportSid} onClose={() => setReportSid(null)} />
      {showLauncher && (
        <LaunchModal kinds={KINDS} onStart={onLaunch} onClose={() => setShowLauncher(false)} />
      )}
    </div>
  )
}

function Row({ k, v }) {
  return (
    <div className="flex items-center justify-between py-1 border-b border-line last:border-0">
      <span className="text-[11px] text-ink-soft">{k}</span>
      <span className="text-[11px] text-ink">{v}</span>
    </div>
  )
}
