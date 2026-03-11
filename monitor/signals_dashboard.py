#!/usr/bin/env python3
"""
Signal Dashboard — generates a markdown dashboard of CI health.
Run via cron: 0 9 * * * cd ~/.openclaw/monitor && source .venv/bin/activate python signals_dashboard.py
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

SHARED_DIR = Path.home() / ".openclaw/knowledge/shared"
OUTPUT_PATH = Path.home() / ".openclaw/knowledge/shared/CI_DASHBOARD.md"

def get_signal_stats():
    """Calculate signal health metrics."""
    path = SHARED_DIR / "signals.jsonl"
    if not path.exists():
        return {"total": 0, "by_type": {}, "by_agent": {}, "consumed_rate": 0}
    
    signals = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                signals.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    
    if not signals:
        return {"total": 0, "by_type": {}, "by_agent": {}, "consumed_rate": 0}
    
    # By type
    by_type = defaultdict(int)
    # By agent pair
    by_agent = defaultdict(int)
    consumed = 0
    
    now = datetime.now(timezone.utc)
    
    for s in signals:
        by_type[s.get("type", "unknown")] += 1
        by_agent[f"{s.get('from', '?')} → {s.get('to', '?')}"] += 1
        if s.get("consumed"):
            consumed += 1
    
    # Last 7 days activity
    cutoff = now - timedelta(days=7)
    recent = [s for s in signals if datetime.fromisoformat(s["ts"].replace("Z", "+00:00")) > cutoff]
    
    return {
        "total": len(signals),
        "recent_7d": len(recent),
        "by_type": dict(by_type),
        "by_agent": dict(by_agent),
        "consumed_rate": consumed / len(signals) if signals else 0,
        "consumed": consumed,
    }

def generate_dashboard():
    """Generate the dashboard markdown."""
    stats = get_signal_stats()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Load recent signals
    path = SHARED_DIR / "signals.jsonl"
    recent_signals = []
    if path.exists():
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    s = json.loads(line)
                    ts = datetime.fromisoformat(s["ts"].replace("Z", "+00:00"))
                    if ts > cutoff:
                        recent_signals.append(s)
                except json.JSONDecodeError:
                    continue
    
    # Sort by time
    recent_signals.sort(key=lambda x: x["ts"], reverse=True)
    
    dashboard = f"""# Collective Intelligence Dashboard

**Updated:** {now}

## Health Metrics

| Metric | Value |
|--------|-------|
| Total Signals | {stats['total']} |
| Signals (7d) | {stats['recent_7d']} |
| Consumed | {stats['consumed']} ({stats['consumed_rate']*100:.0f}%) |
| Signal Types | {len(stats['by_type'])} |

### By Type

"""
    for t, c in sorted(stats['by_type'].items(), key=lambda x: -x[1]):
        dashboard += f"- {t}: {c}\n"
    
    dashboard += "\n### By Agent Pair\n\n"
    for pair, c in sorted(stats['by_agent'].items(), key=lambda x: -x[1]):
        dashboard += f"- {pair}: {c}\n"
    
    dashboard += "\n## Recent Signals (7d)\n\n"
    
    if not recent_signals:
        dashboard += "_No signals in last 7 days_\n"
    else:
        for s in recent_signals[:10]:
            ts = datetime.fromisoformat(s["ts"].replace("Z", "+00:00"))
            consumed = "✓" if s.get("consumed") else "○"
            dashboard += f"""### {consumed} {s['from']} → {s['to']} [{s['type']}]
**{ts.strftime('%Y-%m-%d %H:%M')}**

{s['signal'][:200]}

---
"""
    
    dashboard += """

## Usage

```bash
# List signals
~/.openclaw/monitor/signals_cli.py list

# Emit signal
~/.openclaw/monitor/signals_cli.py emit <to> <type> <message>
```

**Signal Types:** anomaly, metric, priority_shift, architecture_insight, challenge, red_team, pre_mortem, calibration, process_correction, cross_correlation, lesson_learned
"""
    
    OUTPUT_PATH.write_text(dashboard)
    print(f"Dashboard updated: {OUTPUT_PATH}")

if __name__ == "__main__":
    generate_dashboard()
