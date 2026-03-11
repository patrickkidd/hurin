#!/usr/bin/env python3
"""Signal Impact Dashboard — CI KPIs and metrics."""

import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

SHARED_DIR = Path.home() / '.openclaw/knowledge/shared'
SIGNALS_FILE = SHARED_DIR / "signals.jsonl"
IMPACT_FILE = SHARED_DIR / "signal_impact.jsonl"
OUTPUT_FILE = SHARED_DIR / "SIGNAL_IMPACT.md"


def load_impacts():
    if not IMPACT_FILE.exists():
        return []
    return [json.loads(l) for l in IMPACT_FILE.read_text().strip().split('\n') if l.strip()]


def load_signals():
    if not SIGNALS_FILE.exists():
        return []
    return [json.loads(l) for l in SIGNALS_FILE.read_text().strip().split('\n') if l.strip()]


def calculate_kpis():
    """Calculate CI KPIs."""
    signals = load_signals()
    impacts = load_impacts()
    
    if not signals:
        return {
            "total_signals": 0,
            "kpis": {},
            "by_pair": {},
            "by_type": {},
            "sessions": set(),
            "recent": []
        }
    
    # === KPI 1: Signal Delivery Rate (SDR) ===
    # % of signals that were consumed by target agent
    consumed = sum(1 for s in signals if s.get('consumed'))
    total = len(signals)
    sdr = (consumed / total * 100) if total > 0 else 0
    
    # === KPI 2: Mean Response Latency (MRL) ===
    # Average time from emit to consumption
    latencies = [i['latency_seconds'] for i in impacts if i.get('latency_seconds')]
    mrl = sum(latencies) / len(latencies) if latencies else 0
    
    # === KPI 3: Bidirectional Coverage (BC) ===
    # % of possible agent pairs that have communicated
    all_pairs = set()
    for s in signals:
        all_pairs.add((s['from'], s['to']))
    # Possible pairs: beren-huor, beren-tuor, huor-tuor (and reverse)
    possible = {('beren','huor'), ('beren','tuor'), ('huor','tuor'), 
                ('huor','beren'), ('tuor','beren'), ('tuor','huor')}
    bc = (len(all_pairs & possible) / len(possible) * 100) if possible else 0
    
    # === KPI 4: Signal Velocity (SV) ===
    # Signals per day (volume indicator)
    if signals:
        dates = [datetime.fromisoformat(s['ts'].replace('Z','+00:00')).date() for s in signals]
        if dates:
            days_span = (max(dates) - min(dates)).days + 1
            sv = len(signals) / days_span if days_span > 0 else len(signals)
        else:
            sv = 0
    else:
        sv = 0
    
    # === KPI 5: Influence Score (IS) ===
    # % of consumed signals with documented action
    actions = [i for i in impacts if i.get('action_taken')]
    is_rate = (len(actions) / len(impacts) * 100) if impacts else 0
    
    # === KPI 6: Cross-Agent Loop (CAL) ===
    # Did any signal trigger a response signal? (emit → consume → emit pattern)
    # For now, check if same agent pair has signals both directions
    pairs_bidirectional = set()
    for s in signals:
        pair = tuple(sorted([s['from'], s['to']]))
        if pair in pairs_bidirectional:
            pairs_bidirectional.add((s['from'], s['to']))  # Already seen reverse, add forward
        pairs_bidirectional.add(pair)
    cal = len([p for p in pairs_bidirectional if len(p) == 2])  # Simplified
    
    # By agent pair
    by_pair = defaultdict(int)
    for s in signals:
        by_pair[f"{s['from']} → {s['to']}"] += 1
    
    # By type
    by_type = defaultdict(int)
    for s in signals:
        by_type[s.get('type', 'unknown')] += 1
    
    # Sessions
    sessions = set(i['session_key'] for i in impacts if i.get('session_key'))
    
    return {
        "total_signals": total,
        "consumed": consumed,
        "kpis": {
            "SDR": {"value": sdr, "unit": "%", "desc": "Signal Delivery Rate (% signals consumed)"},
            "MRL": {"value": mrl, "unit": "s", "desc": "Mean Response Latency (emit → consume)"},
            "BC":  {"value": bc, "unit": "%", "desc": "Bidirectional Coverage (% pairs communicating)"},
            "SV":  {"value": sv, "unit": "/day", "desc": "Signal Velocity (signals per day)"},
            "IS":  {"value": is_rate, "unit": "%", "desc": "Influence Score (% with actions)"},
        },
        "by_pair": dict(by_pair),
        "by_type": dict(by_type),
        "sessions": sessions,
        "recent": impacts[-10:] if impacts else []
    }


def generate_impact_dashboard():
    now = datetime.now(timezone.utc)
    data = calculate_kpis()
    kpis = data['kpis']
    
    # KPI Status Colors
    def status(k, v):
        if k == "SDR": return "🟢" if v >= 70 else "🟡" if v >= 40 else "🔴"
        if k == "MRL": return "🟢" if v <= 3600 else "🟡" if v <= 86400 else "🔴"  # <1hr, <1day, >1day
        if k == "BC":  return "🟢" if v >= 50 else "🟡" if v >= 25 else "🔴"
        if k == "SV":  return "🟢" if v >= 0.5 else "🟡" if v >= 0.1 else "🔴"
        if k == "IS":  return "🟢" if v >= 50 else "🟡" if v >= 25 else "🔴"
        return "⚪"
    
    md = f"""# Collective Intelligence KPI Dashboard

**Updated:** {now.strftime('%Y-%m-%d %H:%M UTC')}

---

## 🎯 Key Performance Indicators

| KPI | Value | Status | Description |
|-----|-------|--------|-------------|
| **SDR** | {kpis['SDR']['value']:.1f}% | {status('SDR', kpis['SDR']['value'])} | {kpis['SDR']['desc']} |
| **MRL** | {kpis['MRL']['value']:.0f}s | {status('MRL', kpis['MRL']['value'])} | {kpis['MRL']['desc']} |
| **BC** | {kpis['BC']['value']:.0f}% | {status('BC', kpis['BC']['value'])} | {kpis['BC']['desc']} |
| **SV** | {kpis['SV']['value']:.1f}/day | {status('SV', kpis['SV']['value'])} | {kpis['SV']['desc']} |
| **IS** | {kpis['IS']['value']:.0f}% | {status('IS', kpis['IS']['value'])} | {kpis['IS']['desc']} |

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

"""
    for pair, count in sorted(data['by_pair'].items(), key=lambda x: -x[1]):
        md += f"- {pair}: {count}\n"
    
    md += f"""
### By Signal Type

"""
    for t, count in sorted(data['by_type'].items(), key=lambda x: -x[1]):
        md += f"- {t}: {count}\n"
    
    md += f"""
---

## 📈 Recent Impact Records

"""
    for i in data['recent']:
        md += f"""### {i['from']} → {i['to']} [{i['type']}]
**Latency:** {i.get('latency_seconds', 0):.0f}s | **Session:** `{i.get('session_key', '?')[:8]}...`

_{i.get('action_taken', 'No action recorded')}_

---
"""
    
    md += f"""
---

## Summary

- **Total Signals:** {data['total_signals']}
- **Consumed:** {data['consumed']}
- **Unique Sessions:** {len(data['sessions'])}

---

## Usage

```bash
# Generate dashboard
python3 ~/.openclaw/monitor/impact_dashboard.py

# View
cat ~/.openclaw/knowledge/shared/SIGNAL_IMPACT.md
```
"""
    
    OUTPUT_FILE.write_text(md)
    print(f"KPI Dashboard: {OUTPUT_FILE}")
    return md


if __name__ == "__main__":
    generate_impact_dashboard()
