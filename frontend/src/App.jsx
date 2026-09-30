import Header from './components/Header.jsx'
import SituationStrip from './components/SituationStrip.jsx'
import DetailTabs from './components/DetailTabs.jsx'
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

  const pushToast = (title, body, tone = 'secondary') => {
    const id = ++toastId.current
    setToasts((t) => [...t, { id, title, body, tone }].slice(-4))
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000)
  }

  // toast on new alerts / containments
  useEffect(() => {
    if (alerts.length > prevCounts.current.alerts && prevCounts.current.alerts > 0) {
      const a = alerts[0]
      pushToast('attack forecast', `${a.host} · ${(a.attackProb * 100).toFixed(0)}% · ${a.mitre}`, 'error')
    }
    prevCounts.current.alerts = alerts.length
  }, [alerts.length])
  useEffect(() => {
    if (containment.length > prevCounts.current.containment && prevCounts.current.containment > 0) {
      pushToast('containment dispatched', containment[0].rule || 'firewall rule applied', 'primary')
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
    <div className="min-h-screen bg-[#F4F3EF] text-[#1C1917] font-fractul">
      <Header connected={connected} running={running} paused={paused} latest={latest}
        onLaunch={() => setShowLauncher(true)} onStop={onStop} onTogglePause={onTogglePause}
        kind={kind} setKind={setKind} kinds={KINDS} sessionId={sessionId} />
      <HealthStrip connected={connected} latest={latest} health={health} />

      <main className="max-w-7xl mx-auto flex flex-col" style={{ padding: 24, gap: 24 }}>
        {/* command view — the only thing visible above the fold */}
        <SituationStrip prob={latest?.prob ?? 0} threshold={threshold} latest={latest} windows={telemetry.length} />

        <div className="grid grid-cols-1 lg:grid-cols-12" style={{ gap: 16 }}>
          <section className="lg:col-span-8 flex flex-col" style={{ gap: 16 }}>
            {multi && <TopologyMap topology={topology} onSelectHost={setSelectedHost} selectedHost={selectedHost} />}
            <ForecastChart telemetry={telemetry} threshold={threshold} detonationMin={detonationMin} markers={containment} />
            <KillChain stage={latest?.stage ?? 0} />
          </section>

          {/* ops rail — live action only: alerts + response */}
          <section className="lg:col-span-4 flex flex-col" style={{ gap: 16 }}>
            <AlertFeed alerts={alerts} containment={containment} onSelectAlert={setSelectedAlert} />
            <SoarPanel incidents={incidents} onRespond={onRespond}
              autoSoar={autoSoar} onToggleAuto={onToggleAutoSoar} />
          </section>
        </div>

        {/* secondary analysis — one tab at a time, out of the command view */}
        <DetailTabs
          counts={{ respond: campaigns.length || '', models: '' }}
          renderExplain={() => (<>
            <ShapPanel shap={latest?.shap} />
            <ShapRadar history={telemetry} />
          </>)}
          renderRespond={() => (<>
            <CampaignPanel campaigns={campaigns} />
            <PlaybookPanel playbook={playbook} onRefresh={pbRefresh} loading={pbLoading} />
            <div className="rounded-md border border-[#E2DED4] bg-[#FFFFFF] p-4 flex flex-col" style={{ maxHeight: 384 }}>
              <div className="qf-section-title mb-2">Reports & history</div>
              {sessionId ? (
                <a href={reportUrl(sessionId)} target="_blank" rel="noreferrer"
                  className="qf-btn qf-btn-secondary w-full">
                  ⬇ Incident Report ({sessionId})
                </a>
              ) : (
                <div className="text-[11px] font-light text-[#57534E]">no live session — launch one to generate a report</div>
              )}
              <div className="mt-3 flex-1 overflow-y-auto flex flex-col gap-1.5">
                {history.length === 0 && (
                  <div className="text-[11px] font-light text-[#57534E]">no past sessions yet</div>
                )}
                {history.map((s) => (
                  <button key={s.session_id} onClick={() => setReportSid(s.session_id)}
                    className="rounded-sm border border-[#E2DED4] bg-[#F4F3EF] px-3 py-1.5 text-left text-[10px] font-light text-[#57534E] hover:text-[#1C1917] hover:border-[#0F766E]">
                    {s.session_id} · {s.kind} · {s.n_alerts} alerts →
                  </button>
                ))}
              </div>
            </div>
          </>)}
          renderModels={() => (<>
            {sessionId && <ABPanel sessionId={sessionId} />}
            <ModelChips />
            <EvasionPanel />
          </>)}
        />
      </main>

      <footer className="max-w-7xl mx-auto px-6 pb-6 qf-body-sm text-[#57534E] flex justify-between">
        <span>AegisForecast v0.3 · zero-upload telemetry · Bi-LSTM+Attention · SOAR</span>
        <span>{telemetry.length ? `${telemetry.length} windows` : 'idle'}</span>
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
