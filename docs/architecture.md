# AegisForecast — SOC Platform Architecture (Phase 3)

## Overview

AegisForecast evolved from a single-host attack forecaster (Phase 2) into a
**full SOC platform** (Phase 3): multi-host lateral movement is simulated,
per-host perimeter isolation keeps attack signal visible, each host runs its
own forecast engine, campaign correlation groups alerts by actor, a SOAR
state machine triages and contains incidents, every session is recorded and
replayable (A/B across model variants), and executive incident reports are
auto-generated.

## Segment Topology

```
                  [ ATTACKER 203.0.113.50 ]
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
        ┌─────┐         ┌─────┐         ┌─────┐
        │ WEB │────────▶│ FILE│────────▶│  DB │──┐
        │.10  │  SMB    │.30  │  dump   │.20  │  │
        └──┬──┘         └─────┘         └──┬──┘  │
           │                               │     │
           └──────────────┬────────────────┘     │
                          ▼                      ▼
                       ┌─────┐              ┌─────┐
                       │ WS1 │              │  DC │◀─ detonation (wiper)
                       │.40  │              │ .5  │
                       └─────┘              └─────┘
   DC: domain controller (389/88/53)   WEB: 443/80   DB: 3306/1433
   FILE: 445/2049                      WS1: client
```

Benign profiles are role-specific (rates, ports, sizes). Attack kill-chain
traverses WEB → FILE → DB → DC with per-hop dwells (minutes), visible as
animated edges on the dashboard topology map.

## Data Plane — Train/Serve Parity

```
packets ──▶ bucket_perimeter_windows (per-host, non-internal peer only)
              │
         FlowAggregator per window ──▶ rows ──▶ SequenceFeaturizer
                                                    │  (shared class)
                              ┌─────────────────────┤  slope over last 12 windows
                              │                     ▼
                         window_to_features  ──▶  22-dim vector
```

`SequenceFeaturizer` is the **single shared code path** for both training
(`aegis/ml/dataset.py`) and live inference (`aegis/ml/inference.py`).
Perimeter isolation (only traffic with a non-10.20.x peer) is applied
identically on both sides — internal chatter is the learned benign baseline.

## Models

| Variant | Params | Val AUC | Stage acc | Horizon MAE | Notes |
|---------|--------|---------|-----------|-------------|-------|
| BiLSTM+Attention (seq48+slope, perimeter) | 219k | 0.961 | 0.822 | 6.5 min | default, perimeter-aware |
| Transformer (seq48+slope) | 78k | **0.984** | 0.917 | 3.9 min | challenger, replay A/B |
| Ablation D (seq24 base) | 219k | 0.875 | 0.835 | 4.7 min | old baseline, replay B |

Checkpoints store `{state_dict, seq_len, feature_dim, use_slope, model_name}`
so `ForecastEngine` rebuilds the exact architecture (BiLSTM vs Transformer)
from the file.

## Control Plane — SOC Workflow

```
alert (per-host, enriched with intel) ──▶ Incident (host-scoped) ──▶ SOAR
  │  intel: reputation, geo, campaigns        │  detected → triaged → contained
  │  pacing: 1 per host per 3 windows        │  → verified → closed
  │  persisted: SQLite alerts                │  actions persisted, broadcast
  └──────────────────────────────────────────┘
         │
    Campaign rollup (intel.campaign_rollup) ──▶ dashboard campaign panel
         │
    Containment (sustained P≥threshold for 3 windows, auto-SOAR optional)
```

Persistence is `aegis/data/aegis.db` (stdlib sqlite3, WAL). Tables:
`sessions`, `alerts` (with enrichment JSON), `actions` (SOAR trail),
`intel` (seed campaign KB), `reports` (markdown+html).

## Replay & Evasion

*Recorder* saves the packet timeline JSON on session end
(`aegis/data/replays/*.json`). *Replay* reruns the same packets through
two engines (A=current, B=transformer) with identical per-host perimeter
featurization, producing aligned trajectories for the dashboard A/B chart.

*Evasion* (`kind=evasion`): two families — `slow_scan` (one probe per
~20s, stays below ramp detectors — expected to **evade**) and `mimicry`
(attack shaped like benign HTTPS — usually **caught** by C2 heartbeat
variance). Analysis at `GET /api/evasion/analysis`.

## API Surface (Phase 3 additions in bold)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/health, /api/state, /api/alerts, /api/containment | live session |
| **GET** | **/api/topology** | **hosts, edges, live risk scores** |
| **GET** | **/api/campaigns** | **intel campaign rollup** |
| **GET** | **/api/history, /api/history/{sid}** | **persisted sessions** |
| **GET** | **/api/report/{sid}(.md|.html)** | **incident report** |
| **GET** | **/api/replays, /api/replay/{sid}?host=WEB** | **recorded sessions + A/B** |
| **GET** | **/api/evasion/analysis** | **red-team analysis** |
| **GET** | **/api/playbook(.md)** | **guardrailed playbook** |
| POST | /api/sim/start?kind=single\|multi\|evasion | start session |
| POST | /api/respond?host=WEB&action=triage | SOAR manual action |
| POST | /api/soar/auto?enabled=true | auto-SOAR toggle |
| WS | /ws | telemetry (<500ms) + soar + topology_edge events |

## Frontend — SOC Dashboard

```
Header: AegisForecast  ·  kind picker (Lateral APT / Single Host / Red-Team)  ·  WS/SIM status  ·  top-host + horizon
Left:   ThreatGauge  ·  Forecast meta (top host, stage, lead, window count)  ·  Report download
Center: TopologyMap (risk-colored hosts, animated attack edges) · ForecastChart · KillChain · ShapPanel + ShapRadar · ABPanel
Right:  SoarPanel (incidents + respond buttons + auto-SOAR toggle) · CampaignPanel · PlaybookPanel · AlertFeed
Footer: Session history (past replays) + build info
```

## Security Posture

* Zero-upload: raw packets never leave the generating host / kernel; only
  5s flow aggregates exist, in-memory, per-host perimeter view.
* Sandbox `internal: true` — attack traffic cannot leave the host.
* Playbook guardrails: vetted template library, deterministic assembly.
* Evasion honesty: the red-team mode documents both caught and evaded
  cases with root-cause and mitigations.
