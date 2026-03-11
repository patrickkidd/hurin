# Collective Intelligence KPI Dashboard

**Updated:** 2026-03-10 23:26 UTC

---

## 🎯 Key Performance Indicators

| KPI | Value | Status | Description |
|-----|-------|--------|-------------|
| **SDR** | 42.9% | 🟡 | Signal Delivery Rate (% signals consumed) |
| **MRL** | 1845s | 🟢 | Mean Response Latency (emit → consume) |
| **BC** | 83% | 🟢 | Bidirectional Coverage (% pairs communicating) |
| **SV** | 7.0/day | 🟢 | Signal Velocity (signals per day) |
| **IS** | 100% | 🟢 | Influence Score (% with actions) |

---

### KPI Definitions

**SDR (Signal Delivery Rate):** % of emitted signals that reached their target agent.
- 🟢 ≥70% — Healthy communication
- 🟡 40-69% — Some signals lost
- 🔴 <40% — Communication breakdown

**MRL (Mean Response Latency):** Average time from signal emission to consumption.
- 🟢 ≤1hr — Real-time awareness
- 🟡 1-24hr — Daily sync acceptable
- 🔴 >24hr — Slow response

**BC (Bidirectional Coverage):** % of possible agent pairs that have communicated.
- 🟢 ≥50% — Strong mesh
- 🟡 25-49% — Partial coverage
- 🔴 <25% — Siloed agents

**SV (Signal Velocity):** Average signals emitted per day.
- 🟢 ≥0.5/day — Active CI
- 🟡 0.1-0.4/day — Moderate
- 🔴 <0.1/day — Stagnant

**IS (Influence Score):** % of consumed signals that triggered documented action.
- 🟢 ≥50% — High influence
- 🟡 25-49% — Some influence
- 🔴 <25% — Low impact

---

## 📊 Communication Flow

### By Agent Pair

- beren → huor: 3
- beren → tuor: 1
- huor → beren: 1
- tuor → beren: 1
- huor → tuor: 1

### By Signal Type

- cross_correlation: 2
- process_correction: 1
- red_team: 1
- priority_shift: 1
- lesson_learned: 1
- metric: 1

---

## 📈 Recent Impact Records

### beren → huor [priority_shift]
**Latency:** 1845s | **Session:** `test-123...`

_test action_

---

---

## Summary

- **Total Signals:** 7
- **Consumed:** 3
- **Unique Sessions:** 1

---

## Usage

```bash
# Generate dashboard
python3 ~/.openclaw/monitor/impact_dashboard.py

# View
cat ~/.openclaw/knowledge/shared/SIGNAL_IMPACT.md
```
