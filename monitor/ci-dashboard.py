#!/usr/bin/env python3
"""
Collective Intelligence Dashboard Generator

Reads all CI data sources and generates a self-contained HTML dashboard.
Run on-demand or via cron.

Usage: uv run --directory ~/.openclaw/monitor python ci-dashboard.py
Output: ~/.openclaw/monitor/ci-dashboard.html

Serve: cd ~/.openclaw/monitor && python -m http.server 8787
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

HOME = Path.home()
SHARED_DIR = HOME / ".openclaw/knowledge/shared"
MONITOR_DIR = HOME / ".openclaw/monitor"
TELEMETRY_FILE = HOME / ".openclaw/knowledge/self/telemetry.jsonl"
TRUST_LEDGER_FILE = MONITOR_DIR / "trust-ledger.json"
METRICS_LOG = HOME / ".openclaw/team-lead/metrics-log.jsonl"
TASK_EVENTS = MONITOR_DIR / "task-events.jsonl"
TASK_REGISTRY = HOME / ".openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"
SYNTHESES_DIR = HOME / ".openclaw/team-lead/syntheses"
DIGESTS_DIR = HOME / ".openclaw/chief-of-staff/digests"
BRIEFINGS_DIR = HOME / ".openclaw/co-founder/briefings"
SPAWN_POLICY = HOME / ".openclaw/knowledge/self/spawn-policy.json"
OUTPUT_FILE = MONITOR_DIR / "ci-dashboard.html"


def read_jsonl(path, max_lines=500):
    """Read a JSONL file, return list of dicts."""
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().splitlines()[-max_lines:]:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def read_json(path):
    """Read a JSON file."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def count_files(directory, pattern="*"):
    """Count files matching pattern in directory."""
    if not directory.exists():
        return 0
    return len(list(directory.glob(pattern)))


def latest_file_date(directory, pattern="*"):
    """Get modification date of latest file."""
    if not directory.exists():
        return None
    files = sorted(directory.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return None
    return datetime.fromtimestamp(files[0].stat().st_mtime, tz=timezone.utc)


# ---------------------------------------------------------------------------
# Data Collection
# ---------------------------------------------------------------------------

def collect_signal_data():
    signals = read_jsonl(SHARED_DIR / "signals.jsonl")
    impacts = read_jsonl(SHARED_DIR / "signal_impact.jsonl")
    
    total = len(signals)
    consumed = sum(1 for s in signals if s.get("consumed"))
    latencies = [i.get("latency_seconds", 0) for i in impacts if i.get("latency_seconds")]
    
    # KPIs
    sdr = round(consumed / max(total, 1) * 100, 1)
    mrl = round(sum(latencies) / max(len(latencies), 1), 0) if latencies else 0
    
    # SV: signals per day
    if signals:
        dates = [datetime.fromisoformat(s.get("ts", "").replace("Z", "+00:00")).date() for s in signals if s.get("ts")]
        if dates:
            days = max((max(dates) - min(dates)).days, 1)
            sv = round(total / days, 1)
        else:
            sv = 0
    else:
        sv = 0
    
    # IS: Influence Score
    is_score = round(len([i for i in impacts if i.get("action_taken")]) / max(len(impacts), 1) * 100, 1) if impacts else 0
    
    stats = {
        "total": total,
        "consumed": consumed,
        "influenced": sum(1 for s in signals if s.get("influenced_decision")),
        "by_type": {},
        "by_flow": {},
        "by_agent_sent": {},
        "by_agent_received": {},
        "timeline": [],
        "recent": signals[-20:],
        "sdr": sdr,
        "mrl": mrl,
        "sv": sv,
        "is_score": is_score,
    }
    for s in signals:
        t = s.get("type", "unknown")
        stats["by_type"][t] = stats["by_type"].get(t, 0) + 1
        fr, to = s.get("from", "?"), s.get("to", "?")
        flow = f"{fr}→{to}"
        stats["by_flow"][flow] = stats["by_flow"].get(flow, 0) + 1
        stats["by_agent_sent"][fr] = stats["by_agent_sent"].get(fr, 0) + 1
        stats["by_agent_received"][to] = stats["by_agent_received"].get(to, 0) + 1
        # Daily bucketing
        ts = s.get("ts", "")[:10]
        stats["timeline"].append({"date": ts, "from": fr, "to": to, "type": t})
    return stats


def collect_episode_data():
    episodes = read_jsonl(SHARED_DIR / "episodes.jsonl")
    stats = {
        "total": len(episodes),
        "by_outcome": {},
        "by_repo": {},
        "total_lessons": 0,
        "with_signals": 0,
        "avg_duration": 0,
        "recent": episodes[-10:],
        "lessons": [],
    }
    total_dur = 0
    for ep in episodes:
        outcome = ep.get("outcome", "unknown")
        stats["by_outcome"][outcome] = stats["by_outcome"].get(outcome, 0) + 1
        repo = ep.get("repo", "unknown")
        stats["by_repo"][repo] = stats["by_repo"].get(repo, 0) + 1
        lessons = ep.get("lessons", [])
        stats["total_lessons"] += len(lessons)
        stats["lessons"].extend(lessons[-2:])
        if ep.get("cross_agent_signals_consumed"):
            stats["with_signals"] += 1
        total_dur += ep.get("duration_hrs", 0)
    stats["avg_duration"] = round(total_dur / max(len(episodes), 1), 1)
    return stats


def collect_calibration_data():
    calibrations = read_jsonl(SHARED_DIR / "calibrations.jsonl")
    stats = {
        "total": len(calibrations),
        "by_challenger": {},
        "accuracy_by_agent": {},
        "recent": calibrations[-10:],
        "categories": {},
    }
    agent_correct = {}
    agent_total = {}
    for cal in calibrations:
        challenger = cal.get("challenger", "unknown")
        stats["by_challenger"][challenger] = stats["by_challenger"].get(challenger, 0) + 1
        agent_total[challenger] = agent_total.get(challenger, 0) + 1
        if f"agree_with_{challenger}" in cal.get("patrick_decided", ""):
            agent_correct[challenger] = agent_correct.get(challenger, 0) + 1
        cat = cal.get("category", "general")
        stats["categories"][cat] = stats["categories"].get(cat, 0) + 1
    for agent in agent_total:
        correct = agent_correct.get(agent, 0)
        total = agent_total[agent]
        stats["accuracy_by_agent"][agent] = {
            "correct": correct, "total": total,
            "accuracy": round(correct / max(total, 1) * 100, 1)
        }
    return stats


def collect_telemetry_data():
    entries = read_jsonl(TELEMETRY_FILE, max_lines=200)
    stats = {
        "pr_latency": [],
        "compute_roi": [],
        "master_topics": [],
        "attention": [],
    }
    for e in entries:
        t = e.get("type", "")
        if t == "pr_review_latency":
            stats["pr_latency"].append({
                "pr": e.get("pr_key", ""),
                "hours": e.get("latency_hours", 0),
                "state": e.get("state", ""),
            })
        elif t == "compute_roi":
            stats["compute_roi"].append({
                "merged": e.get("merged_tasks", 0),
                "discarded": e.get("discarded_tasks", 0),
                "roi": e.get("roi_ratio", 0),
                "ts": e.get("collected_at", "")[:10],
            })
        elif t == "master_topics":
            stats["master_topics"].append(e.get("topics", {}))
        elif t == "attention_signal":
            stats["attention"].append(e)
    return stats


def collect_trust_data():
    ledger = read_json(TRUST_LEDGER_FILE)
    entries = ledger.get("entries", [])
    global_stats = ledger.get("global_stats", {})
    return {
        "total_entries": len(entries),
        "global_accuracy": global_stats.get("accuracy", 0),
        "global_correct": global_stats.get("correct", 0),
        "global_total": global_stats.get("total", 0),
        "recent": entries[-10:] if entries else [],
    }


def collect_spawn_policy():
    policy = read_json(SPAWN_POLICY)
    categories = policy.get("categories", {})
    return {
        "last_updated": policy.get("last_updated", ""),
        "categories": {k: {
            "autonomy": v.get("autonomy", "unknown"),
            "accuracy": v.get("accuracy", 0),
            "total": v.get("total", 0),
        } for k, v in categories.items()},
    }


def collect_metrics_data():
    entries = read_jsonl(METRICS_LOG, max_lines=30)
    return {
        "count": len(entries),
        "latest": entries[-1] if entries else {},
        "velocity_trend": [
            {"ts": e.get("ts", "")[:10], "velocity": e.get("velocity_7d", 0)}
            for e in entries[-14:]
        ],
    }


def collect_task_data():
    events = read_jsonl(TASK_EVENTS, max_lines=100)
    registry = read_json(TASK_REGISTRY)
    tasks = registry.get("tasks", registry) if isinstance(registry, dict) else registry
    if not isinstance(tasks, list):
        tasks = []
    status_counts = {}
    for t in tasks:
        s = t.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1
    return {
        "total_events": len(events),
        "total_tasks": len(tasks),
        "status_counts": status_counts,
        "recent_events": events[-10:],
    }


def collect_artifact_data():
    return {
        "syntheses": count_files(SYNTHESES_DIR, "*.json"),
        "digests": count_files(DIGESTS_DIR, "*.md"),
        "briefings": count_files(BRIEFINGS_DIR, "*.md"),
        "latest_synthesis": str(latest_file_date(SYNTHESES_DIR, "*.json") or "none"),
        "latest_digest": str(latest_file_date(DIGESTS_DIR, "*.md") or "none"),
        "latest_briefing": str(latest_file_date(BRIEFINGS_DIR, "*.md") or "none"),
    }


def collect_state_data():
    return read_json(SHARED_DIR / "state.json")


# ---------------------------------------------------------------------------
# HTML Generation
# ---------------------------------------------------------------------------

def generate_html(data):
    """Generate the complete self-contained HTML dashboard."""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    signals = data["signals"]
    episodes = data["episodes"]
    calibrations = data["calibrations"]
    telemetry = data["telemetry"]
    trust = data["trust"]
    spawn = data["spawn_policy"]
    metrics = data["metrics"]
    tasks = data["tasks"]
    artifacts = data["artifacts"]
    state = data["state"]

    # Compute CI-specific KPIs
    consumption_rate = round(signals["consumed"] / max(signals["total"], 1) * 100, 1)
    influence_rate = round(signals["influenced"] / max(signals["consumed"], 1) * 100, 1)
    episode_count = episodes["total"]

    # === VALUE KPIs: Compare outcomes with vs without signals ===
    impacts = read_jsonl(SHARED_DIR / "signal_impact.jsonl")
    
    # Signal Influence KPIs
    total_consumed = len([i for i in impacts if i.get("consumed_at")])
    influenced = len([i for i in impacts if i.get("action_taken")])
    not_influenced = total_consumed - influenced
    
    # Calculate delta metrics (episodes with signals vs without)
    eps_with_signals = [e for e in episodes.get("recent", []) if e.get("cross_agent_signals_consumed")]
    eps_without_signals = [e for e in episodes.get("recent", []) if not e.get("cross_agent_signals_consumed")]
    
    # Cycle time comparison
    cycle_with = sum(e.get("duration_hrs", 0) for e in eps_with_signals) / max(len(eps_with_signals), 1)
    cycle_without = sum(e.get("duration_hrs", 0) for e in eps_without_signals) / max(len(eps_without_signals), 1)
    cycle_delta = cycle_with - cycle_without  # Negative = signals help (faster)
    
    # Success rate comparison
    success_with = len([e for e in eps_with_signals if e.get("outcome") == "completed"]) / max(len(eps_with_signals), 1)
    success_without = len([e for e in eps_without_signals if e.get("outcome") == "completed"]) / max(len(eps_without_signals), 1)
    success_delta = (success_with - success_without) * 100  # In percentage points
    
    # Signal quality score (influenced / consumed)
    signal_quality = round(influenced / max(total_consumed, 1) * 100, 1) if total_consumed > 0 else 0
    
    # Pack KPIs for template
    value_kpis = {
        "signal_quality": signal_quality,
        "cycle_delta": round(cycle_delta, 1),
        "cycle_with": round(cycle_with, 1),
        "cycle_without": round(cycle_without, 1),
        "success_delta": round(success_delta, 1),
        "success_with": round(success_with * 100, 1),
        "success_without": round(success_without * 100, 1),
        "eps_with_signals": len(eps_with_signals),
        "eps_without_signals": len(eps_without_signals),
        "total_impacts": total_consumed,
    }
    lesson_count = episodes["total_lessons"]
    challenge_count = calibrations["total"]
    signal_total = signals["total"]

    # Flow data for Sankey-like visualization
    flows_json = json.dumps(signals["by_flow"])
    type_json = json.dumps(signals["by_type"])
    episode_outcome_json = json.dumps(episodes["by_outcome"])
    episode_repo_json = json.dumps(episodes["by_repo"])
    velocity_json = json.dumps(metrics.get("velocity_trend", []))
    task_status_json = json.dumps(tasks["status_counts"])
    spawn_cats_json = json.dumps(spawn["categories"])

    # Calibration accuracy
    cal_accuracy_json = json.dumps(calibrations["accuracy_by_agent"])

    # PR latency data
    pr_latency = telemetry.get("pr_latency", [])
    pr_latency_json = json.dumps(pr_latency[-20:])

    # Recent signals for table
    recent_signals_html = ""
    for s in reversed(signals.get("recent", [])):
        consumed_badge = '<span class="badge badge-green">consumed</span>' if s.get("consumed") else '<span class="badge badge-gray">pending</span>'
        influenced_badge = '<span class="badge badge-blue">influenced</span>' if s.get("influenced_decision") else ""
        recent_signals_html += f"""
        <tr>
            <td class="mono">{s.get('ts', '')[:16]}</td>
            <td><span class="agent agent-{s.get('from', '')}">{s.get('from', '?')}</span></td>
            <td><span class="agent agent-{s.get('to', '')}">{s.get('to', '?')}</span></td>
            <td><span class="signal-type">{s.get('type', '')}</span></td>
            <td class="signal-text">{s.get('signal', '')[:120]}</td>
            <td class="center">{s.get('confidence', 0):.2f}</td>
            <td class="center">{consumed_badge} {influenced_badge}</td>
        </tr>"""

    # Recent episodes for table
    recent_episodes_html = ""
    for ep in reversed(episodes.get("recent", [])):
        outcome_class = "green" if ep.get("outcome") == "merged" else "red" if ep.get("outcome") in ("abandoned", "failed") else "yellow"
        lessons_str = "; ".join(ep.get("lessons", [])[:2])
        signal_badge = '<span class="badge badge-blue">CI</span>' if ep.get("cross_agent_signals_consumed") else ""
        recent_episodes_html += f"""
        <tr>
            <td class="mono">{ep.get('ts', '')[:10]}</td>
            <td class="mono">{ep.get('task_id', '')}</td>
            <td>{ep.get('repo', '')}</td>
            <td><span class="badge badge-{outcome_class}">{ep.get('outcome', '')}</span></td>
            <td class="center">{ep.get('duration_hrs', 0)}h</td>
            <td class="lesson-text">{lessons_str}</td>
            <td class="center">{signal_badge}</td>
        </tr>"""

    # Recent calibrations for table
    recent_cals_html = ""
    for cal in reversed(calibrations.get("recent", [])):
        winner = cal.get("patrick_decided", "").replace("agree_with_", "")
        recent_cals_html += f"""
        <tr>
            <td class="mono">{cal.get('ts', '')[:10]}</td>
            <td><span class="agent agent-{cal.get('challenger', '')}">{cal.get('challenger', '')}</span></td>
            <td><span class="agent agent-{cal.get('challenged', '')}">{cal.get('challenged', '')}</span></td>
            <td>{cal.get('topic', '')[:80]}</td>
            <td><span class="agent agent-{winner}">{winner}</span></td>
            <td class="lesson-text">{cal.get('lesson', '')[:100]}</td>
        </tr>"""

    # Sprint focus
    sprint_focus = state.get("sprint_focus", "Not configured — create knowledge/shared/state.json")
    patrick_last = state.get("patrick_last_said", "N/A")

    # Spawn policy table
    spawn_html = ""
    for cat, info in spawn.get("categories", {}).items():
        acc = info.get("accuracy", 0)
        color = "green" if acc >= 0.8 else "yellow" if acc >= 0.5 else "red"
        spawn_html += f"""
        <tr>
            <td>{cat}</td>
            <td><span class="badge badge-{'green' if info.get('autonomy') == 'auto_spawn' else 'yellow' if info.get('autonomy') == 'propose_only' else 'red'}">{info.get('autonomy', '?')}</span></td>
            <td class="center"><span class="badge badge-{color}">{acc:.0%}</span></td>
            <td class="center">{info.get('total', 0)}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Collective Intelligence Dashboard — Húrin</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
:root {{
    --bg: #0f1117;
    --bg-card: #1a1d27;
    --bg-card-hover: #22263a;
    --border: #2a2e3e;
    --text: #e0e0e6;
    --text-dim: #8b8fa3;
    --text-bright: #ffffff;
    --accent: #6c63ff;
    --accent-glow: rgba(108, 99, 255, 0.15);
    --green: #2dd4a0;
    --green-dim: rgba(45, 212, 160, 0.15);
    --red: #f87171;
    --red-dim: rgba(248, 113, 113, 0.15);
    --yellow: #fbbf24;
    --yellow-dim: rgba(251, 191, 36, 0.15);
    --blue: #60a5fa;
    --blue-dim: rgba(96, 165, 250, 0.15);
    --orange: #fb923c;
    --purple: #a78bfa;
    --huor: #2dd4a0;
    --tuor: #60a5fa;
    --beren: #a78bfa;
    --system: #8b8fa3;
    --radius: 12px;
    --shadow: 0 4px 24px rgba(0,0,0,0.3);
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
    padding: 24px;
    min-height: 100vh;
}}
h1 {{
    font-size: 28px;
    font-weight: 700;
    color: var(--text-bright);
    margin-bottom: 4px;
}}
.subtitle {{
    color: var(--text-dim);
    font-size: 14px;
    margin-bottom: 28px;
}}
.subtitle span {{ color: var(--accent); font-weight: 600; }}

/* Grid */
.grid {{ display: grid; gap: 20px; margin-bottom: 24px; }}
.grid-5 {{ grid-template-columns: repeat(5, 1fr); }}
.grid-4 {{ grid-template-columns: repeat(4, 1fr); }}
.grid-3 {{ grid-template-columns: repeat(3, 1fr); }}
.grid-2 {{ grid-template-columns: repeat(2, 1fr); }}
.grid-1 {{ grid-template-columns: 1fr; }}
@media (max-width: 1400px) {{ .grid-5 {{ grid-template-columns: repeat(3, 1fr); }} }}
@media (max-width: 1200px) {{ .grid-5, .grid-4 {{ grid-template-columns: repeat(2, 1fr); }} }}
@media (max-width: 768px) {{ .grid-5, .grid-4, .grid-3, .grid-2 {{ grid-template-columns: 1fr; }} }}

/* Cards */
.card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    box-shadow: var(--shadow);
    transition: border-color 0.2s;
}}
.card:hover {{ border-color: var(--accent); }}
.card-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}}
.card-title {{
    font-size: 14px;
    font-weight: 600;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.card-icon {{
    font-size: 20px;
    opacity: 0.7;
}}

/* KPI */
.kpi-value {{
    font-size: 36px;
    font-weight: 700;
    color: var(--text-bright);
    line-height: 1.1;
}}
.kpi-unit {{
    font-size: 14px;
    color: var(--text-dim);
    font-weight: 400;
    margin-left: 4px;
}}
.kpi-detail {{
    font-size: 13px;
    color: var(--text-dim);
    margin-top: 6px;
}}
.kpi-good {{ color: var(--green); }}
.kpi-warn {{ color: var(--yellow); }}
.kpi-bad {{ color: var(--red); }}

/* Section headers */
.section-header {{
    font-size: 20px;
    font-weight: 700;
    color: var(--text-bright);
    margin: 32px 0 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--border);
    display: flex;
    align-items: center;
    gap: 10px;
}}
.section-header .icon {{ font-size: 22px; }}

/* Tables */
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}
th {{
    text-align: left;
    padding: 10px 12px;
    color: var(--text-dim);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-size: 11px;
    border-bottom: 2px solid var(--border);
    position: sticky;
    top: 0;
    background: var(--bg-card);
}}
td {{
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
}}
tr:hover td {{ background: var(--bg-card-hover); }}
.mono {{ font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 12px; }}
.center {{ text-align: center; }}
.signal-text, .lesson-text {{
    max-width: 400px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}
.table-scroll {{
    max-height: 400px;
    overflow-y: auto;
    border-radius: var(--radius);
}}

/* Badges */
.badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}}
.badge-green {{ background: var(--green-dim); color: var(--green); }}
.badge-red {{ background: var(--red-dim); color: var(--red); }}
.badge-yellow {{ background: var(--yellow-dim); color: var(--yellow); }}
.badge-blue {{ background: var(--blue-dim); color: var(--blue); }}
.badge-gray {{ background: rgba(139,143,163,0.15); color: var(--text-dim); }}

/* Agent badges */
.agent {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
}}
.agent-huor {{ background: rgba(45,212,160,0.15); color: var(--huor); }}
.agent-tuor {{ background: rgba(96,165,250,0.15); color: var(--tuor); }}
.agent-beren {{ background: rgba(167,139,250,0.15); color: var(--beren); }}
.agent-system {{ background: rgba(139,143,163,0.15); color: var(--system); }}
.agent-all {{ background: rgba(251,191,36,0.15); color: var(--yellow); }}
.signal-type {{
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    background: var(--accent-glow);
    color: var(--accent);
    font-weight: 600;
}}

/* Topology SVG */
.topology-container {{
    display: flex;
    justify-content: center;
    padding: 20px 0;
}}
.topology-container svg {{ max-width: 100%; }}

/* Sprint focus */
.sprint-focus {{
    background: var(--accent-glow);
    border: 1px solid rgba(108, 99, 255, 0.3);
    border-radius: var(--radius);
    padding: 16px 20px;
    margin-bottom: 24px;
}}
.sprint-label {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--accent);
    font-weight: 700;
    margin-bottom: 6px;
}}
.sprint-text {{
    font-size: 18px;
    color: var(--text-bright);
    font-weight: 600;
}}
.sprint-subtext {{
    font-size: 13px;
    color: var(--text-dim);
    margin-top: 4px;
    font-style: italic;
}}

/* Chart containers */
.chart-container {{
    min-height: 180px;
}}

.chart-container-sm {{
    position: relative;
    height: 250px;
    width: 100%;
}}
.chart-container-sm {{
    position: relative;
    height: 180px;
    width: 100%;
}}

/* Footer */
.footer {{
    text-align: center;
    color: var(--text-dim);
    font-size: 12px;
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid var(--border);
}}

/* Empty state */
.empty-state {{
    text-align: center;
    padding: 40px;
    color: var(--text-dim);
}}
.empty-state .icon {{ font-size: 48px; margin-bottom: 12px; opacity: 0.3; }}
.empty-state p {{ font-size: 14px; }}
</style>
</head>
<body>

<h1>Collective Intelligence Dashboard</h1>
<div class="subtitle">Húrin Agent System &mdash; <span>Huor</span> &middot; <span>Tuor</span> &middot; <span>Beren</span> &mdash; Generated {generated_at}</div>

<!-- Sprint Focus -->
<div class="sprint-focus">
    <div class="sprint-label">Current Sprint Focus</div>
    <div class="sprint-text">{sprint_focus}</div>
    <div class="sprint-subtext">Patrick: &ldquo;{patrick_last}&rdquo;</div>
</div>

<!-- CI KPIs: 5-column layout -->
<div class="grid grid-5">
    <div class="card" title="Signals successfully received by target agents">
        <div class="card-header"><span class="card-title">Delivery Rate</span><span class="card-icon">&#x1F4E6;</span></div>
        <div class="kpi-value {'kpi-good' if signals.get('sdr', 0) >= 70 else 'kpi-warn' if signals.get('sdr', 0) >= 40 else 'kpi-bad'}">{signals.get('sdr', 0):.0f}<span class="kpi-unit">%</span></div>
        <div class="kpi-detail">% of signals consumed</div>
    </div>
    <div class="card" title="Average time for agents to act on signals">
        <div class="card-header"><span class="card-title">Response Latency</span><span class="card-icon">&#x23F1;</span></div>
        <div class="kpi-value {'kpi-good' if signals.get('mrl', 0) <= 3600 else 'kpi-warn' if signals.get('mrl', 0) <= 86400 else 'kpi-bad'}">{signals.get('mrl', 0):.0f}<span class="kpi-unit">s</span></div>
        <div class="kpi-detail">avg seconds to respond</div>
    </div>
    <div class="card" title="How often signals are being sent">
        <div class="card-header"><span class="card-title">Signal Velocity</span><span class="card-icon">&#x26A1;</span></div>
        <div class="kpi-value {'kpi-good' if signals.get('sv', 0) >= 0.5 else 'kpi-warn' if signals.get('sv', 0) >= 0.1 else 'kpi-bad'}">{signals.get('sv', 0):.1f}<span class="kpi-unit">/d</span></div>
        <div class="kpi-detail">signals per day</div>
    </div>
    <div class="card" title="Signals that changed agent decisions">
        <div class="card-header"><span class="card-title">Influence</span><span class="card-icon">&#x1F4A1;</span></div>
        <div class="kpi-value {'kpi-good' if signals.get('is_score', 0) >= 50 else 'kpi-warn' if signals.get('is_score', 0) >= 25 else 'kpi-bad'}">{signals.get('is_score', 0):.0f}<span class="kpi-unit">%</span></div>
        <div class="kpi-detail">% with action taken</div>
    </div>
    <div class="card" title="Learning episodes captured from work">
        <div class="card-header"><span class="card-title">Episodes</span><span class="card-icon">&#x1F4DA;</span></div>
        <div class="kpi-value">{episode_count}</div>
        <div class="kpi-detail">{lesson_count} lessons</div>
    </div>
</div>

<!-- VALUE KPIs: Is CI adding value? -->
<div class="section-header"><span class="icon">&#x1F4B0;</span> Value KPIs: Is CI Adding Value?</div>
<div class="grid grid-5">
    <div class="card" title="% of consumed signals that influenced decisions">
        <div class="card-header"><span class="card-title">Signal Quality</span><span class="card-icon">&#x2728;</span></div>
        <div class="kpi-value {'kpi-good' if value_kpis.get('signal_quality', 0) >= 50 else 'kpi-warn' if value_kpis.get('signal_quality', 0) >= 25 else 'kpi-bad'}">{value_kpis.get('signal_quality', 0):.0f}<span class="kpi-unit">%</span></div>
        <div class="kpi-detail">{value_kpis.get('total_impacts', 0)} consumed signals</div>
    </div>
    <div class="card" title="Avg cycle time with signals - avg cycle time without">
        <div class="card-header"><span class="card-title">Cycle Time Delta</span><span class="card-icon">&#x1F504;</span></div>
        <div class="kpi-value {'kpi-good' if value_kpis.get('cycle_delta', 0) < 0 else 'kpi-warn' if value_kpis.get('cycle_delta', 0) < 5 else 'kpi-bad'}">{value_kpis.get('cycle_delta', 0):+.1f}<span class="kpi-unit">h</span></div>
        <div class="kpi-detail">{value_kpis.get('cycle_with', 0):.1f}h with / {value_kpis.get('cycle_without', 0):.1f}h without</div>
    </div>
    <div class="card" title="Success rate with signals - success rate without">
        <div class="card-header"><span class="card-title">Success Delta</span><span class="card-icon">&#x1F3C6;</span></div>
        <div class="kpi-value {'kpi-good' if value_kpis.get('success_delta', 0) > 0 else 'kpi-warn' if value_kpis.get('success_delta', 0) > -10 else 'kpi-bad'}">{value_kpis.get('success_delta', 0):+.1f}<span class="kpi-unit">pp</span></div>
        <div class="kpi-detail">{value_kpis.get('success_with', 0):.0f}% with / {value_kpis.get('success_without', 0):.0f}% without</div>
    </div>
    <div class="card" title="Episodes where signals were consumed">
        <div class="card-header"><span class="card-title">Episodes w/Signals</span><span class="card-icon">&#x1F4E7;</span></div>
        <div class="kpi-value">{value_kpis.get('eps_with_signals', 0)}</div>
        <div class="kpi-detail">{value_kpis.get('eps_without_signals', 0)} without</div>
    </div>
    <div class="card" title="Raw influence tracking from signal_impact.jsonl">
        <div class="card-header"><span class="card-title">Influence Tracked</span><span class="card-icon">&#x1F4CB;</span></div>
        <div class="kpi-value">{value_kpis.get('total_impacts', 0)}</div>
        <div class="kpi-detail">signal_impact entries</div>
    </div>
</div>
<div class="kpi-note">
    <strong>Note:</strong> Negative cycle delta = signals help tasks complete faster. Positive success delta = signals improve outcomes.
    Compare episodes with signals consumed vs. without to compute deltas.
</div>

<!-- Agent Topology -->
<div class="section-header"><span class="icon">&#x1F310;</span> Agent Topology &amp; Information Flow</div>
<div class="grid grid-2">
    <div class="card">
        <div class="card-header"><span class="card-title">Network Topology</span></div>
        <div class="topology-container">
            <svg viewBox="0 0 600 400" width="700" height="450" xmlns="http://www.w3.org/2000/svg">
                <!-- Definitions -->
                <defs>
                    <filter id="glow">
                        <feGaussianBlur stdDeviation="3" result="blur"/>
                        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
                    </filter>
                    <marker id="arrow-huor" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                        <polygon points="0 0, 8 3, 0 6" fill="#2dd4a0" opacity="0.7"/>
                    </marker>
                    <marker id="arrow-tuor" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                        <polygon points="0 0, 8 3, 0 6" fill="#60a5fa" opacity="0.7"/>
                    </marker>
                    <marker id="arrow-beren" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                        <polygon points="0 0, 8 3, 0 6" fill="#a78bfa" opacity="0.7"/>
                    </marker>
                </defs>

                <!-- Background grid -->
                <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1a1d27" stroke-width="1"/>
                </pattern>
                <rect width="600" height="400" fill="url(#grid)" rx="12"/>

                <!-- Shared Memory (center) -->
                <rect x="215" y="155" width="170" height="90" rx="10" fill="#1a1d27" stroke="#2a2e3e" stroke-width="2"/>
                <text x="300" y="185" text-anchor="middle" fill="#8b8fa3" font-size="11" font-weight="600">SHARED MEMORY</text>
                <text x="300" y="205" text-anchor="middle" fill="#6c63ff" font-size="10">state.json · signals.jsonl</text>
                <text x="300" y="220" text-anchor="middle" fill="#6c63ff" font-size="10">episodes.jsonl · calibrations</text>

                <!-- Huor (top-left) -->
                <circle cx="150" cy="80" r="44" fill="rgba(45,212,160,0.1)" stroke="#2dd4a0" stroke-width="2.5" filter="url(#glow)"/>
                <text x="150" y="75" text-anchor="middle" fill="#2dd4a0" font-size="16" font-weight="700">Huor</text>
                <text x="150" y="93" text-anchor="middle" fill="#8b8fa3" font-size="10">Team Lead</text>

                <!-- Tuor (top-right) -->
                <circle cx="450" cy="80" r="44" fill="rgba(96,165,250,0.1)" stroke="#60a5fa" stroke-width="2.5" filter="url(#glow)"/>
                <text x="450" y="75" text-anchor="middle" fill="#60a5fa" font-size="16" font-weight="700">Tuor</text>
                <text x="450" y="93" text-anchor="middle" fill="#8b8fa3" font-size="10">Co-Founder</text>

                <!-- Beren (bottom-center) -->
                <circle cx="300" cy="340" r="44" fill="rgba(167,139,250,0.1)" stroke="#a78bfa" stroke-width="2.5" filter="url(#glow)"/>
                <text x="300" y="335" text-anchor="middle" fill="#a78bfa" font-size="16" font-weight="700">Beren</text>
                <text x="300" y="353" text-anchor="middle" fill="#8b8fa3" font-size="10">Chief of Staff</text>

                <!-- Patrick (below center, governance) -->
                <rect x="245" y="270" width="110" height="30" rx="6" fill="rgba(251,191,36,0.1)" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="4,3"/>
                <text x="300" y="290" text-anchor="middle" fill="#fbbf24" font-size="11" font-weight="600">Patrick</text>

                <!-- Flow: Huor → Tuor (anomalies, metrics) -->
                <path d="M 194 74 Q 300 40 406 74" fill="none" stroke="#2dd4a0" stroke-width="2" opacity="0.6" marker-end="url(#arrow-huor)"/>
                <text x="300" y="42" text-anchor="middle" fill="#2dd4a0" font-size="9" opacity="0.8">anomalies · metrics</text>

                <!-- Flow: Tuor → Huor (priorities) -->
                <path d="M 406 92 Q 300 120 194 92" fill="none" stroke="#60a5fa" stroke-width="2" opacity="0.6" marker-end="url(#arrow-tuor)"/>
                <text x="300" y="126" text-anchor="middle" fill="#60a5fa" font-size="9" opacity="0.8">priority shifts · strategy</text>

                <!-- Flow: Huor → Beren (spawn data) -->
                <path d="M 138 122 Q 170 230 268 320" fill="none" stroke="#2dd4a0" stroke-width="1.5" opacity="0.5" marker-end="url(#arrow-huor)"/>
                <text x="155" y="230" text-anchor="start" fill="#2dd4a0" font-size="9" opacity="0.7">outcomes</text>

                <!-- Flow: Beren → Huor (corrections) -->
                <path d="M 260 318 Q 130 250 130 124" fill="none" stroke="#a78bfa" stroke-width="1.5" opacity="0.5" marker-end="url(#arrow-beren)"/>
                <text x="140" y="260" text-anchor="start" fill="#a78bfa" font-size="9" opacity="0.7">corrections</text>

                <!-- Flow: Tuor → Beren (recommendations) -->
                <path d="M 462 122 Q 430 230 332 320" fill="none" stroke="#60a5fa" stroke-width="1.5" opacity="0.5" marker-end="url(#arrow-tuor)"/>
                <text x="440" y="230" text-anchor="end" fill="#60a5fa" font-size="9" opacity="0.7">recommendations</text>

                <!-- Flow: Beren → Tuor (red-team) -->
                <path d="M 340 318 Q 470 250 470 124" fill="none" stroke="#a78bfa" stroke-width="2" opacity="0.6" marker-end="url(#arrow-beren)" stroke-dasharray="6,3"/>
                <text x="465" y="260" text-anchor="end" fill="#a78bfa" font-size="9" opacity="0.7">red-team</text>

                <!-- Flow: Tuor → Huor (red-team) -->
                <path d="M 406 74 Q 300 20 194 74" fill="none" stroke="#a78bfa" stroke-width="2" opacity="0.5" marker-end="url(#arrow-tuor)" stroke-dasharray="6,3"/>
                
                <!-- Flow: Beren → Huor (red-team) -->
                <path d="M 138 122 Q 100 180 100 165" fill="none" stroke="#a78bfa" stroke-width="1.5" opacity="0.4" marker-end="url(#arrow-huor)" stroke-dasharray="4,2"/>

                <!-- Flow: All → Shared Memory -->
                <line x1="165" y1="120" x2="220" y2="165" stroke="#2a2e3e" stroke-width="1" stroke-dasharray="3,3" opacity="0.4"/>
                <line x1="435" y1="120" x2="380" y2="165" stroke="#2a2e3e" stroke-width="1" stroke-dasharray="3,3" opacity="0.4"/>
                <line x1="300" y1="296" x2="300" y2="245" stroke="#2a2e3e" stroke-width="1" stroke-dasharray="3,3" opacity="0.4"/>

                <!-- Flow counts (dynamic) -->
                <text x="300" y="16" text-anchor="middle" fill="#8b8fa3" font-size="10">{signal_total} signals total</text>
            </svg>
            <!-- Legend -->

        </div>
    </div>
    <div class="card">
        <div class="card-header"><span class="card-title">Signal Flow Volume</span></div>
        <div class="chart-container">
            <canvas id="flowChart"></canvas>
        </div>
    </div>
</div>

<!-- Cross-Pollination Metrics -->
<div class="section-header"><span class="icon">&#x1F331;</span> Cross-Pollination Efficacy</div>
<div class="grid grid-3">
    <div class="card">
        <div class="card-header"><span class="card-title">Signal Types Distribution</span></div>
        <div class="chart-container-sm" style="min-height: 160px;">
            <canvas id="typeChart"></canvas>
        </div>
    </div>
    <div class="card">
        <div class="card-header"><span class="card-title">Agent Activity Balance</span></div>
        <div class="chart-container">
            <canvas id="agentActivityChart"></canvas>
        </div>
        <div class="kpi-detail" style="text-align: center; margin-top: 12px;">
            Shows which agents are sending vs receiving signals.<br>
            <strong>Team Lead (Huor)</strong> should send more than receive.<br>
            <strong>Co-Founder (Tuor)</strong> signals strategic priorities.<br>
            <strong>Chief of Staff (Beren)</strong> coordinates corrections.
        </div>
    </div>
</div>

<!-- Adversarial Health -->
<div class="section-header"><span class="icon">&#x2694;&#xFE0F;</span> Adversarial Improvement</div>
<div class="adversarial-note">
    <strong>Red-team</strong> is when Beren challenges Tuor's recommendations or Huor's priorities — 
    like a devil's advocate to stress-test decisions before execution. This is <em>productive</em> conflict.
</div>
<div class="grid grid-2">
    <div class="card">
        <div class="card-header"><span class="card-title">Challenge Accuracy by Agent</span></div>
        {'<div class="chart-container-sm"><canvas id="calAccuracyChart"></canvas></div>' if challenge_count > 0 else '<div class="empty-state"><div class="icon">&#x1F3AF;</div><p>No calibration data yet. When Patrick resolves agent disagreements,<br>accuracy tracking will appear here.</p></div>'}
    </div>
    <div class="card">
        <div class="card-header"><span class="card-title">Calibration History</span></div>
        {'<div class="table-scroll"><table><thead><tr><th>Date</th><th>Challenger</th><th>Challenged</th><th>Topic</th><th>Winner</th><th>Lesson</th></tr></thead><tbody>' + recent_cals_html + '</tbody></table></div>' if challenge_count > 0 else '<div class="empty-state"><div class="icon">&#x1F4DD;</div><p>Calibrations will appear here as adversarial challenges<br>are resolved by Patrick.</p></div>'}
    </div>
</div>

<!-- Episodic Memory -->
<div class="section-header"><span class="icon">&#x1F4DA;</span> Episodic Memory</div>
<div class="grid grid-3">
    <div class="card">
        <div class="card-header"><span class="card-title">Task Outcomes</span></div>
        <div class="chart-container-sm">
            <canvas id="outcomeChart"></canvas>
        </div>
    </div>
    <div class="card">
        <div class="card-header"><span class="card-title">Outcomes by Repo</span></div>
        <div class="chart-container-sm">
            <canvas id="repoChart"></canvas>
        </div>
    </div>
    <div class="card">
        <div class="card-header">
            <span class="card-title">Episode Stats</span>
        </div>
        <div style="padding: 10px 0;">
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border);">
                <span style="color: var(--text-dim);">Total Episodes</span>
                <span style="font-weight: 700;">{episode_count}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border);">
                <span style="color: var(--text-dim);">Total Lessons</span>
                <span style="font-weight: 700;">{lesson_count}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border);">
                <span style="color: var(--text-dim);">Avg Duration</span>
                <span style="font-weight: 700;">{episodes['avg_duration']}h</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border);">
                <span style="color: var(--text-dim);">CI-Informed Tasks</span>
                <span style="font-weight: 700; color: var(--blue);">{episodes['with_signals']}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                <span style="color: var(--text-dim);">Lessons per Episode</span>
                <span style="font-weight: 700;">{round(lesson_count / max(episode_count, 1), 1)}</span>
            </div>
        </div>
    </div>
</div>

{f'<div class="grid grid-1"><div class="card"><div class="card-header"><span class="card-title">Recent Episodes</span></div><div class="table-scroll"><table><thead><tr><th>Date</th><th>Task</th><th>Repo</th><th>Outcome</th><th>Duration</th><th>Lessons</th><th>CI</th></tr></thead><tbody>{recent_episodes_html}</tbody></table></div></div></div>' if episode_count > 0 else ''}

<!-- Signal Bus Activity -->
<div class="section-header"><span class="icon">&#x1F4E1;</span> Signal Bus Activity</div>
<div class="grid grid-1">
    <div class="card">
        <div class="card-header"><span class="card-title">Recent Signals</span></div>
        {f'<div class="table-scroll"><table><thead><tr><th>Timestamp</th><th>From</th><th>To</th><th>Type</th><th>Signal</th><th>Conf</th><th>Status</th></tr></thead><tbody>{recent_signals_html}</tbody></table></div>' if signal_total > 0 else '<div class="empty-state"><div class="icon">&#x1F4E1;</div><p>No signals yet. Once cross-pollination is implemented,<br>inter-agent signals will appear here.</p></div>'}
    </div>
</div>

<!-- System Vitals -->
<div class="section-header"><span class="icon">&#x1F4CA;</span> System Vitals</div>
<div class="grid grid-3">
    <div class="card">
        <div class="card-header"><span class="card-title">Velocity Trend</span></div>
        <div class="chart-container-sm">
            <canvas id="velocityChart"></canvas>
        </div>
    </div>
    <div class="card">
        <div class="card-header"><span class="card-title">Task Status</span></div>
        <div class="chart-container-sm">
            <canvas id="taskChart"></canvas>
        </div>
    </div>
    <div class="card">
        <div class="card-header"><span class="card-title">PR Review Latency</span></div>
        <div class="chart-container-sm">
            <canvas id="prLatencyChart"></canvas>
        </div>
    </div>
</div>

<!-- Spawn Policy -->
<div class="grid grid-2">
    <div class="card">
        <div class="card-header"><span class="card-title">Spawn Policy</span></div>
        <div class="table-scroll">
            <table>
                <thead><tr><th>Category</th><th>Autonomy</th><th>Accuracy</th><th>Proposals</th></tr></thead>
                <tbody>{spawn_html}</tbody>
            </table>
        </div>
    </div>
    <div class="card">
        <div class="card-header"><span class="card-title">Trust Ledger Summary</span></div>
        <div style="padding: 10px 0;">
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border);">
                <span style="color: var(--text-dim);">Total Entries</span>
                <span style="font-weight: 700;">{trust['total_entries']}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border);">
                <span style="color: var(--text-dim);">Global Accuracy</span>
                <span class="{'kpi-good' if trust['global_accuracy'] >= 0.7 else 'kpi-warn' if trust['global_accuracy'] >= 0.5 else 'kpi-bad'}" style="font-weight: 700;">{trust['global_accuracy']:.0%}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border);">
                <span style="color: var(--text-dim);">Correct / Total</span>
                <span style="font-weight: 700;">{trust['global_correct']} / {trust['global_total']}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                <span style="color: var(--text-dim);">Artifacts Produced</span>
                <span style="font-weight: 700;">{artifacts['syntheses']}S &middot; {artifacts['digests']}D &middot; {artifacts['briefings']}B</span>
            </div>
        </div>
    </div>
</div>

<div class="footer">
    Collective Intelligence Dashboard v1.0 &mdash; Húrin Agent System &mdash; Generated {generated_at}
</div>

<script>
// Chart.js defaults
Chart.defaults.color = '#8b8fa3';
Chart.defaults.borderColor = '#2a2e3e';
Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Inter', sans-serif";
Chart.defaults.font.size = 11;
const COLORS = {{
    huor: '#2dd4a0', tuor: '#60a5fa', beren: '#a78bfa',
    system: '#8b8fa3', all: '#fbbf24',
    green: '#2dd4a0', red: '#f87171', yellow: '#fbbf24',
    blue: '#60a5fa', purple: '#a78bfa', orange: '#fb923c',
}};

// Signal Flow Chart (horizontal bar)
const flowData = {flows_json};
const flowLabels = Object.keys(flowData);
const flowValues = Object.values(flowData);
const flowColors = flowLabels.map(l => {{
    const from = l.split('→')[0];
    return COLORS[from] || COLORS.system;
}});
if (flowLabels.length > 0) {{
    new Chart(document.getElementById('flowChart'), {{
        type: 'bar',
        data: {{
            labels: flowLabels,
            datasets: [{{ data: flowValues, backgroundColor: flowColors.map(c => c + '40'), borderColor: flowColors, borderWidth: 2 }}]
        }},
        options: {{
            indexAxis: 'y',
            plugins: {{ legend: {{ display: false }} }},
            scales: {{ x: {{ grid: {{ color: '#2a2e3e' }} }}, y: {{ grid: {{ display: false }} }} }}
        }}
    }});
}} else {{
    document.getElementById('flowChart').parentElement.innerHTML = '<div class="empty-state"><p>Signal flow data will appear after cross-pollination begins.</p></div>';
}}

// Signal Types (doughnut)
const typeData = {type_json};
const typeLabels = Object.keys(typeData);
const typeValues = Object.values(typeData);
if (typeLabels.length > 0) {{
    new Chart(document.getElementById('typeChart'), {{
        type: 'doughnut',
        data: {{
            labels: typeLabels,
            datasets: [{{ data: typeValues, backgroundColor: ['#6c63ff', '#2dd4a0', '#60a5fa', '#a78bfa', '#fbbf24', '#fb923c', '#f87171', '#8b8fa3', '#22d3ee', '#e879f9', '#34d399'] }}]
        }},
        options: {{
            plugins: {{ legend: {{ position: 'right', labels: {{ boxWidth: 12, padding: 6 }} }} }},
            cutout: '55%'
        }}
    }});
}}

// Agent Activity (radar)
const sentData = {json.dumps(signals['by_agent_sent'])};
const recvData = {json.dumps(signals['by_agent_received'])};
const agentLabels = [...new Set([...Object.keys(sentData), ...Object.keys(recvData)])].filter(a => ['huor','tuor','beren'].includes(a));
if (agentLabels.length > 0) {{
    new Chart(document.getElementById('agentActivityChart'), {{
        type: 'radar',
        data: {{
            labels: agentLabels.map(a => a.charAt(0).toUpperCase() + a.slice(1)),
            datasets: [
                {{ label: 'Sent', data: agentLabels.map(a => sentData[a] || 0), borderColor: '#6c63ff', backgroundColor: 'rgba(108,99,255,0.1)', borderWidth: 2 }},
                {{ label: 'Received', data: agentLabels.map(a => recvData[a] || 0), borderColor: '#2dd4a0', backgroundColor: 'rgba(45,212,160,0.1)', borderWidth: 2 }}
            ]
        }},
        options: {{
            plugins: {{ legend: {{ labels: {{ boxWidth: 12 }} }} }},
            scales: {{ r: {{ grid: {{ color: '#2a2e3e' }}, angleLines: {{ color: '#2a2e3e' }}, pointLabels: {{ font: {{ size: 12 }} }} }} }}
        }}
    }});
}} else {{
    document.getElementById('agentActivityChart').parentElement.innerHTML = '<div class="empty-state"><p>Agent activity balance appears after signals flow.</p></div>';
}}

// Calibration Accuracy (bar)
const calData = {cal_accuracy_json};
const calAgents = Object.keys(calData);
if (calAgents.length > 0 && document.getElementById('calAccuracyChart')) {{
    new Chart(document.getElementById('calAccuracyChart'), {{
        type: 'bar',
        data: {{
            labels: calAgents.map(a => a.charAt(0).toUpperCase() + a.slice(1)),
            datasets: [
                {{ label: 'Accuracy %', data: calAgents.map(a => calData[a].accuracy), backgroundColor: calAgents.map(a => COLORS[a] + '60'), borderColor: calAgents.map(a => COLORS[a]), borderWidth: 2 }},
            ]
        }},
        options: {{
            plugins: {{ legend: {{ display: false }} }},
            scales: {{ y: {{ max: 100, grid: {{ color: '#2a2e3e' }} }}, x: {{ grid: {{ display: false }} }} }}
        }}
    }});
}}

// Episode outcomes (doughnut)
const outcomeData = {episode_outcome_json};
const outcomeLabels = Object.keys(outcomeData);
if (outcomeLabels.length > 0) {{
    new Chart(document.getElementById('outcomeChart'), {{
        type: 'doughnut',
        data: {{
            labels: outcomeLabels,
            datasets: [{{ data: Object.values(outcomeData), backgroundColor: outcomeLabels.map(l => l === 'merged' ? COLORS.green : l === 'abandoned' || l === 'failed' ? COLORS.red : COLORS.yellow) }}]
        }},
        options: {{ plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 12 }} }} }}, cutout: '55%' }}
    }});
}} else {{
    document.getElementById('outcomeChart').parentElement.innerHTML = '<div class="empty-state"><p>Episode outcomes appear after tasks complete with CI.</p></div>';
}}

// Repo distribution (bar)
const repoData = {episode_repo_json};
if (Object.keys(repoData).length > 0) {{
    new Chart(document.getElementById('repoChart'), {{
        type: 'bar',
        data: {{
            labels: Object.keys(repoData),
            datasets: [{{ data: Object.values(repoData), backgroundColor: [COLORS.green + '60', COLORS.blue + '60', COLORS.purple + '60'], borderColor: [COLORS.green, COLORS.blue, COLORS.purple], borderWidth: 2 }}]
        }},
        options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ grid: {{ color: '#2a2e3e' }} }}, x: {{ grid: {{ display: false }} }} }} }}
    }});
}} else {{
    document.getElementById('repoChart').parentElement.innerHTML = '<div class="empty-state"><p>Repo distribution appears after episodes are captured.</p></div>';
}}

// Velocity trend (line)
const velData = {velocity_json};
if (velData.length > 0) {{
    new Chart(document.getElementById('velocityChart'), {{
        type: 'line',
        data: {{
            labels: velData.map(v => v.ts),
            datasets: [{{ label: '7d Velocity', data: velData.map(v => v.velocity), borderColor: COLORS.green, backgroundColor: 'rgba(45,212,160,0.1)', fill: true, tension: 0.3, borderWidth: 2, pointRadius: 3 }}]
        }},
        options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ grid: {{ color: '#2a2e3e' }} }}, x: {{ grid: {{ display: false }}, ticks: {{ maxTicksLimit: 7 }} }} }} }}
    }});
}} else {{
    document.getElementById('velocityChart').parentElement.innerHTML = '<div class="empty-state"><p>Velocity data from metrics log.</p></div>';
}}

// Task status (doughnut)
const taskData = {task_status_json};
if (Object.keys(taskData).length > 0) {{
    const statusColors = {{ done: COLORS.green, running: COLORS.blue, pr_open: COLORS.yellow, failed: COLORS.red, closed: COLORS.orange, queued: COLORS.purple }};
    new Chart(document.getElementById('taskChart'), {{
        type: 'doughnut',
        data: {{
            labels: Object.keys(taskData),
            datasets: [{{ data: Object.values(taskData), backgroundColor: Object.keys(taskData).map(k => statusColors[k] || COLORS.system) }}]
        }},
        options: {{ plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 12 }} }} }}, cutout: '55%' }}
    }});
}}

// PR Latency (bar)
const prData = {pr_latency_json};
if (prData.length > 0) {{
    new Chart(document.getElementById('prLatencyChart'), {{
        type: 'bar',
        data: {{
            labels: prData.map(p => p.pr.split('#')[1] || p.pr),
            datasets: [{{ label: 'Hours', data: prData.map(p => p.hours), backgroundColor: prData.map(p => p.hours > 24 ? COLORS.red + '60' : p.hours > 8 ? COLORS.yellow + '60' : COLORS.green + '60'), borderColor: prData.map(p => p.hours > 24 ? COLORS.red : p.hours > 8 ? COLORS.yellow : COLORS.green), borderWidth: 2 }}]
        }},
        options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ grid: {{ color: '#2a2e3e' }} }}, x: {{ grid: {{ display: false }}, ticks: {{ maxTicksLimit: 10 }} }} }} }}
    }});
}} else {{
    document.getElementById('prLatencyChart').parentElement.innerHTML = '<div class="empty-state"><p>PR latency data from telemetry.</p></div>';
}}
</script>
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Collecting data...")

    data = {
        "signals": collect_signal_data(),
        "episodes": collect_episode_data(),
        "calibrations": collect_calibration_data(),
        "telemetry": collect_telemetry_data(),
        "trust": collect_trust_data(),
        "spawn_policy": collect_spawn_policy(),
        "metrics": collect_metrics_data(),
        "tasks": collect_task_data(),
        "artifacts": collect_artifact_data(),
        "state": collect_state_data(),
    }

    print("Generating dashboard...")
    html = generate_html(data)

    OUTPUT_FILE.write_text(html)
    print(f"Dashboard written to: {OUTPUT_FILE}")
    print(f"Serve: cd {MONITOR_DIR} && python -m http.server 8787")
    print(f"Then open: http://localhost:8787/ci-dashboard.html")


if __name__ == "__main__":
    main()
