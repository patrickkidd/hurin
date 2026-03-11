"""
Shared memory utilities for cross-agent communication.

Used by: team_lead.py, co-founder-sdk.py, chief-of-staff.py, task-daemon.py
Provides: signal bus, episode log, coordination state, calibration tracking

Part of the Collective Intelligence system (ADR-0009).
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

SHARED_DIR = Path.home() / ".openclaw/knowledge/shared"
BRIEFINGS_DIR = Path.home() / ".openclaw/co-founder/briefings"
DIGESTS_DIR = Path.home() / ".openclaw/chief-of-staff/digests"
SYNTHESES_DIR = Path.home() / ".openclaw/team-lead/syntheses"

VALID_SIGNAL_TYPES = {
    "anomaly", "metric", "priority_shift", "architecture_insight",
    "challenge", "red_team", "pre_mortem", "pre_mortem_request",
    "calibration", "process_correction", "cross_correlation",
    "lesson_learned",
}

VALID_AGENTS = {"huor", "tuor", "beren", "system", "all"}
VALID_URGENCY = {"digest", "priority", "critical"}


# --- Helpers ---

def get_latest_file(directory, pattern="*", max_chars=2000):
    """Return content of most recent file matching pattern in directory.
    Returns None if no files found. Truncates to max_chars."""
    d = Path(directory)
    if not d.exists():
        return None
    files = sorted(d.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return None
    content = files[0].read_text(errors="replace")
    return content[:max_chars] if max_chars else content


# --- State ---

def read_state():
    """Read the coordination state file."""
    path = SHARED_DIR / "state.json"
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"Failed to read state.json: {e}")
        return {}


def update_state_field(field, value, updated_by="system"):
    """Update a single field in state.json.
    Patrick-controlled fields require updated_by='patrick' (set via Discord commands).
    Agent-writable fields can be updated by any agent."""
    PATRICK_CONTROLLED = {"sprint_focus", "patrick_last_said", "do_not_touch", "current_week_theme"}
    if field in PATRICK_CONTROLLED and updated_by not in ("patrick", "discord"):
        log.warning(f"Field '{field}' is Patrick-controlled, skipping update by {updated_by}")
        return False
    state = read_state()
    state[field] = value
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    state["updated_by"] = updated_by
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    with open(SHARED_DIR / "state.json", "w") as f:
        json.dump(state, f, indent=2)
    return True


# --- Signals ---

def append_signal(from_agent, to_agent, signal_type, signal, confidence=0.8, source_artifact=None, urgency="digest"):
    """Append a signal to the bus.
    
    urgency: "digest" (normal, 2x/week), "priority" (read within 1hr), "critical" (wake agent)
    """
    if from_agent not in VALID_AGENTS:
        log.warning(f"Invalid from_agent: {from_agent}")
        return
    if to_agent not in VALID_AGENTS:
        log.warning(f"Invalid to_agent: {to_agent}")
        return
    if signal_type not in VALID_SIGNAL_TYPES:
        log.warning(f"Invalid signal_type: {signal_type}")
        return
    if urgency not in VALID_URGENCY:
        log.warning(f"Invalid urgency: {urgency}, defaulting to digest")
        urgency = "digest"
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "from": from_agent,
        "to": to_agent,
        "type": signal_type,
        "signal": str(signal)[:500],
        "confidence": round(min(max(float(confidence), 0.0), 1.0), 2),
        "consumed": False,
        "urgency": urgency,
    }
    if source_artifact:
        entry["source_artifact"] = source_artifact
    with open(SHARED_DIR / "signals.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_signals(for_agent, max_age_days=14, mark_consumed=True, session_key=None, action_taken=None):
    """Read unconsumed signals for an agent. If for_agent='all', reads all signals.
    
    Args:
        for_agent: Target agent name (or 'all')
        max_age_days: How old signals to consider
        mark_consumed: Whether to mark as consumed
        session_key: Session reading the signals (for impact tracking)
        action_taken: What action was taken based on signals (for impact tracking)
    """
    path = SHARED_DIR / "signals.jsonl"
    impact_path = SHARED_DIR / "signal_impact.jsonl"
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    signals = []
    all_lines = []
    consumed_count = 0
    
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                s = json.loads(line)
            except json.JSONDecodeError:
                all_lines.append(line)
                continue
            ts = datetime.fromisoformat(s["ts"].replace("Z", "+00:00"))
            match = (
                for_agent == "all"
                or s.get("to") in (for_agent, "all")
            )
            if match and ts > cutoff and not s.get("consumed"):
                signals.append(s)
                if mark_consumed:
                    s["consumed"] = True
                    s["consumed_at"] = datetime.now(timezone.utc).isoformat()
                    s["consumed_by_session"] = session_key
                    s["action_taken"] = action_taken
                    consumed_count += 1
                    
                    # Write impact entry
                    impact = {
                        "signal_ts": s["ts"],
                        "from": s["from"],
                        "to": s["to"],
                        "type": s["type"],
                        "consumed_at": s["consumed_at"],
                        "latency_seconds": (datetime.now(timezone.utc) - ts).total_seconds(),
                        "session_key": session_key,
                        "action_taken": action_taken,
                        "tracked_at": datetime.now(timezone.utc).isoformat()
                    }
                    with open(impact_path, "a") as impf:
                        impf.write(json.dumps(impact) + "\n")
            all_lines.append(json.dumps(s))
    if mark_consumed and signals:
        with open(path, "w") as f:
            f.write("\n".join(all_lines) + "\n")
    
    if consumed_count > 0:
        log.info(f"Consumed {consumed_count} signals with impact tracking")
    return signals


def prune_signals(max_age_days=14):
    """Remove signals older than max_age_days."""
    path = SHARED_DIR / "signals.jsonl"
    if not path.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    kept = []
    pruned = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                s = json.loads(line)
                ts = datetime.fromisoformat(s["ts"].replace("Z", "+00:00"))
                if ts > cutoff:
                    kept.append(json.dumps(s))
                else:
                    pruned += 1
            except (json.JSONDecodeError, KeyError):
                kept.append(line)
    with open(path, "w") as f:
        f.write("\n".join(kept) + "\n" if kept else "")
    return pruned


# --- Episodes ---

def append_episode(task_id, repo, outcome, duration_hrs, lessons, tags, signals_consumed=None, spawned_by="huor"):
    """Record a task outcome with lessons learned."""
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "repo": repo,
        "outcome": outcome,
        "duration_hrs": round(duration_hrs, 1),
        "spawned_by": spawned_by,
        "lessons": lessons[:5],
        "tags": tags,
        "cross_agent_signals_consumed": signals_consumed or [],
    }
    with open(SHARED_DIR / "episodes.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_recent_episodes(limit=10):
    """Read the most recent episodes."""
    path = SHARED_DIR / "episodes.jsonl"
    if not path.exists():
        return []
    episodes = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                episodes.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return episodes[-limit:]


# --- Calibrations ---

def append_calibration(challenger, challenged, topic, winner, lesson, category="general"):
    """Record an adversarial calibration outcome."""
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "challenge_id": f"cal-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "challenger": challenger,
        "challenged": challenged,
        "topic": topic,
        "patrick_decided": f"agree_with_{winner}",
        "lesson": lesson,
        "category": category,
    }
    with open(SHARED_DIR / "calibrations.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_recent_calibrations(limit=10):
    """Read the most recent calibrations."""
    path = SHARED_DIR / "calibrations.jsonl"
    if not path.exists():
        return []
    calibrations = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                calibrations.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return calibrations[-limit:]


def get_calibration_accuracy(agent, category=None):
    """Calculate an agent's challenge accuracy."""
    path = SHARED_DIR / "calibrations.jsonl"
    if not path.exists():
        return {"total": 0, "correct": 0, "accuracy": 0.0}
    correct = 0
    total = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                cal = json.loads(line)
                if cal["challenger"] != agent:
                    continue
                if category and cal.get("category") != category:
                    continue
                total += 1
                if cal["patrick_decided"] == f"agree_with_{agent}":
                    correct += 1
            except (json.JSONDecodeError, KeyError):
                continue
    return {"total": total, "correct": correct, "accuracy": correct / max(total, 1)}


# --- Cross-Agent Context Builders ---

def build_cross_context_for_huor():
    """Build the cross-agent context block for Huor's synthesis prompt."""
    parts = ["\n## Cross-Agent Context\n"]

    # Latest Tuor briefing
    latest_briefing = get_latest_file(BRIEFINGS_DIR, "*.md")
    if latest_briefing:
        parts.append(f"\n### Latest Co-Founder Briefing (Tuor)\n{latest_briefing[:2000]}\n")

    # Latest Beren digest
    latest_digest = get_latest_file(DIGESTS_DIR, "*.md")
    if latest_digest:
        parts.append(f"\n### Latest Chief of Staff Digest (Beren)\n{latest_digest[:2000]}\n")

    # Signals addressed to Huor
    huor_signals = read_signals("huor", mark_consumed=True)
    if huor_signals:
        parts.append("\n### Signals Addressed to You\n")
        for s in huor_signals[-5:]:
            parts.append(f"- [{s['type']}] from {s['from']}: {s['signal']} (confidence: {s['confidence']})\n")

    # Shared state
    state = read_state()
    if state:
        parts.append(f"\n### Current Sprint Focus\n{state.get('sprint_focus', 'Not set')}\n")
        parts.append(f"Patrick last said: {state.get('patrick_last_said', 'N/A')}\n")
        dnt = state.get('do_not_touch', [])
        if dnt:
            parts.append(f"Do NOT touch: {', '.join(dnt)}\n")

    # Recent episodes
    episodes = read_recent_episodes(limit=5)
    if episodes:
        parts.append("\n### Recent Task Outcomes\n")
        for ep in episodes:
            lessons = '; '.join(ep.get('lessons', [])[:2])
            parts.append(f"- {ep['task_id']} ({ep['outcome']}): {lessons}\n")

    # Instructions
    parts.append("""
### Cross-Pollination Instructions
- If Tuor has recommended a priority shift, address it explicitly — agree and reorder, or explain why current order is better.
- If Beren has issued a process correction, incorporate it.
- After completing your synthesis, emit up to 3 signals to Tuor and/or Beren about operational findings they should know about.
""")

    return "".join(parts)


def build_cross_context_for_tuor():
    """Build the cross-agent context block for Tuor's briefing prompt."""
    parts = ["\n## Operational Reality Check (from Huor)\n"]

    # Latest synthesis (JSON format)
    latest_synthesis = get_latest_file(SYNTHESES_DIR, "*.json", max_chars=10000)
    if latest_synthesis:
        try:
            data = json.loads(latest_synthesis)
            synthesis_text = data.get("synthesis", "")
            parts.append(f"\n### Latest Team Lead Synthesis\n{synthesis_text[:2000]}\n")
        except json.JSONDecodeError:
            pass

    # Latest Beren digest
    latest_digest = get_latest_file(DIGESTS_DIR, "*.md")
    if latest_digest:
        parts.append(f"\n### Latest Chief of Staff Digest (Beren)\n{latest_digest[:2000]}\n")

    # Signals for Tuor
    tuor_signals = read_signals("tuor", mark_consumed=True)
    if tuor_signals:
        parts.append("\n### Signals Addressed to You\n")
        for s in tuor_signals[-5:]:
            parts.append(f"- [{s['type']}] from {s['from']}: {s['signal']} (confidence: {s['confidence']})\n")

    # Shared state
    state = read_state()
    if state:
        parts.append(f"\n### Current Sprint Focus\n{state.get('sprint_focus', 'Not set')}\n")
        parts.append(f"Patrick last said: {state.get('patrick_last_said', 'N/A')}\n")
        dnt = state.get('do_not_touch', [])
        if dnt:
            parts.append(f"Do NOT touch: {', '.join(dnt)}\n")

    # Episodes
    episodes = read_recent_episodes(limit=5)
    if episodes:
        parts.append("\n### Recent Task Outcomes\n")
        for ep in episodes:
            lessons = '; '.join(ep.get('lessons', [])[:2])
            parts.append(f"- {ep['task_id']} ({ep['outcome']}, {ep.get('duration_hrs', '?')}h): {lessons}\n")

    # Instructions
    parts.append("""
### Cross-Pollination Instructions
- If your strategic recommendations conflict with the operational data above, explicitly acknowledge the tension and explain why your recommendation still holds — or revise it.
- Ground your analysis in real velocity and outcome data, not aspirational projections.
- After completing your briefing, emit up to 3 signals to Huor and/or Beren.
""")

    return "".join(parts)


def build_cross_context_for_beren():
    """Build the cross-agent context block for Beren's digest prompt."""
    parts = []

    # Signals for Beren
    beren_signals = read_signals("beren", mark_consumed=True)
    if beren_signals:
        parts.append("\n## Signals Addressed to You\n")
        for s in beren_signals[-5:]:
            parts.append(f"- [{s['type']}] from {s['from']}: {s['signal']} (confidence: {s['confidence']})\n")

    # Calibration history
    calibrations = read_recent_calibrations(limit=10)
    if calibrations:
        parts.append("\n## Recent Calibration History\n")
        for c in calibrations:
            parts.append(f"- {c['challenger']} vs {c['challenged']}: {c['topic']} → {c['patrick_decided']}\n")
        # Accuracy stats
        beren_acc = get_calibration_accuracy("beren")
        if beren_acc["total"] > 0:
            parts.append(f"\nYour challenge accuracy: {beren_acc['correct']}/{beren_acc['total']} ({beren_acc['accuracy']:.0%})\n")

    # Episodes
    episodes = read_recent_episodes(limit=10)
    if episodes:
        parts.append("\n## Recent Task Outcomes (Episodic Memory)\n")
        for ep in episodes:
            lessons = '; '.join(ep.get('lessons', [])[:2])
            parts.append(f"- {ep['task_id']} ({ep['repo']}, {ep['outcome']}, {ep.get('duration_hrs', '?')}h): {lessons}\n")
        # Stats
        merged = sum(1 for ep in episodes if ep.get('outcome') == 'merged')
        parts.append(f"\nRecent success rate: {merged}/{len(episodes)} merged\n")

    # Shared state
    state = read_state()
    if state:
        parts.append(f"\n## Shared State\n")
        parts.append(f"Sprint focus: {state.get('sprint_focus', 'Not set')}\n")
        parts.append(f"Patrick last said: {state.get('patrick_last_said', 'N/A')}\n")
        dnt = state.get('do_not_touch', [])
        if dnt:
            parts.append(f"Do NOT touch: {', '.join(dnt)}\n")

    # Cross-correlation + red-team instructions
    parts.append("""
## Cross-Correlation Task (MANDATORY)
After reading all inputs, perform this analysis:
1. Identify at least ONE pattern that spans Huor's operational data AND Tuor's strategic analysis that neither would catch alone. If none exists, say so — do not fabricate.
2. Check if any current task priorities conflict with the shared state sprint focus.
3. Review the calibration history — are your challenges getting more or less accurate over time?

## Red Team: Co-Founder's Top Recommendation
Take Tuor's highest-confidence recommendation from the latest briefing and argue AGAINST it:
- What evidence would need to be true for this recommendation to be wrong?
- What is Tuor's lens NOT seeing?
- What's the cost of following this if wrong vs ignoring if right?
Score: PROCEED / MODIFY / DELAY with reasoning.

## Cross-Pollination Instructions
After completing your digest, emit up to 3 signals. At least one MUST be a challenge or cross-correlation finding.
""")

    return "".join(parts)


# --- Signal Emission Parser ---

def extract_and_emit_signals(cc_output, from_agent, source_artifact=None):
    """Parse SIGNALS_JSON line from CC output and write to signal bus.
    Returns list of emitted signals."""
    import re
    emitted = []
    for line in cc_output.split("\n"):
        if line.strip().startswith("SIGNALS_JSON:"):
            json_str = line.split("SIGNALS_JSON:", 1)[1].strip()
            try:
                signals = json.loads(json_str)
                if not isinstance(signals, list):
                    continue
                for s in signals[:5]:  # Hard cap at 5
                    if not all(k in s for k in ("to", "type", "signal", "confidence")):
                        continue
                    append_signal(
                        from_agent=from_agent,
                        to_agent=s["to"],
                        signal_type=s["type"],
                        signal=str(s["signal"])[:500],
                        confidence=min(max(float(s.get("confidence", 0.5)), 0.0), 1.0),
                        source_artifact=source_artifact,
                    )
                    emitted.append(s)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                log.warning(f"Failed to parse signals JSON: {e}")
    return emitted


# --- Signal Emission Prompt Block ---

SIGNAL_EMISSION_PROMPT = """
## Signal Emission (MANDATORY)
After your main output, emit 1-5 signals for other agents on a SEPARATE line starting with `SIGNALS_JSON:`.
Format: SIGNALS_JSON: [{"to": "tuor", "type": "anomaly", "signal": "< 500 chars", "confidence": 0.8}, ...]

Valid "to" values: huor, tuor, beren
Valid "type" values: anomaly, metric, priority_shift, architecture_insight, challenge, red_team, calibration, process_correction, cross_correlation, lesson_learned
Only emit signals that would genuinely help the target agent. Do NOT emit low-value or obvious signals.
"""


# --- Anomaly Triangulation ---

def check_triangulation(anomaly_area, exclude_agent="huor"):
    """Check if multiple agents have flagged the same area. Boost confidence."""
    signals = read_signals("all", mark_consumed=False)
    related = [
        s for s in signals
        if anomaly_area.lower() in s.get("signal", "").lower()
        and s["from"] != exclude_agent
    ]
    if related:
        return {
            "triangulated": True,
            "confidence_boost": 1.3,
            "corroborating_agents": list(set(s["from"] for s in related)),
            "note": f"Triangulated with {related[0]['from']}: {related[0]['signal'][:100]}",
        }
    return {"triangulated": False, "confidence_boost": 1.0}


# --- Efficacy Metrics ---

def get_signal_stats():
    """Compute signal bus statistics for dashboard."""
    path = SHARED_DIR / "signals.jsonl"
    if not path.exists():
        return {}
    stats = {
        "total": 0,
        "consumed": 0,
        "influenced_decision": 0,
        "by_type": {},
        "by_flow": {},
        "by_agent": {},
    }
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                s = json.loads(line)
                stats["total"] += 1
                if s.get("consumed"):
                    stats["consumed"] += 1
                if s.get("influenced_decision"):
                    stats["influenced_decision"] += 1
                t = s.get("type", "unknown")
                stats["by_type"][t] = stats["by_type"].get(t, 0) + 1
                flow = f"{s['from']}->{s['to']}"
                stats["by_flow"][flow] = stats["by_flow"].get(flow, 0) + 1
                stats["by_agent"].setdefault(s["from"], {"sent": 0, "received": 0})["sent"] += 1
                stats["by_agent"].setdefault(s["to"], {"sent": 0, "received": 0})["received"] += 1
            except (json.JSONDecodeError, KeyError):
                continue
    return stats


def get_episode_stats():
    """Compute episode statistics for dashboard."""
    path = SHARED_DIR / "episodes.jsonl"
    if not path.exists():
        return {}
    stats = {
        "total": 0,
        "by_outcome": {},
        "by_repo": {},
        "avg_duration_hrs": 0,
        "total_lessons": 0,
        "with_signals": 0,
    }
    total_duration = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ep = json.loads(line)
                stats["total"] += 1
                outcome = ep.get("outcome", "unknown")
                stats["by_outcome"][outcome] = stats["by_outcome"].get(outcome, 0) + 1
                repo = ep.get("repo", "unknown")
                stats["by_repo"][repo] = stats["by_repo"].get(repo, 0) + 1
                total_duration += ep.get("duration_hrs", 0)
                stats["total_lessons"] += len(ep.get("lessons", []))
                if ep.get("cross_agent_signals_consumed"):
                    stats["with_signals"] += 1
            except (json.JSONDecodeError, KeyError):
                continue
    stats["avg_duration_hrs"] = round(total_duration / max(stats["total"], 1), 1)
    return stats

def detect_signal_influence(signals, agent_output):
    """Simple heuristic: if agent output references signal content, assume influence.
    
    Returns True if any signal content appears in the agent's output.
    """
    if not signals or not agent_output:
        return False
    
    output_lower = agent_output.lower()
    for s in signals:
        signal_text = s.get("signal", "").lower()
        # Check if signal content appears in output (with some flexibility)
        if signal_text and len(signal_text) > 10:
            # Check for significant overlap (at least 3 consecutive words)
            words = signal_text.split()
            for i in range(len(words) - 2):
                phrase = " ".join(words[i:i+3])
                if phrase in output_lower:
                    return True
    return False

def mark_signals_consumed(session_key, action_taken, signal_filter=None):
    """Mark previously-read signals as consumed, with impact data.
    
    Call this AFTER the agent has run to determine if signals influenced behavior.
    
    Args:
        session_key: The session that consumed the signals
        action_taken: Boolean - did the signals influence the agent's output?
        signal_filter: Optional dict to filter which signals to mark (e.g., {"from": "beren"})
    """
    path = SHARED_DIR / "signals.jsonl"
    impact_path = SHARED_DIR / "signal_impact.jsonl"
    
    if not session_key:
        log.warning("mark_signals_consumed called without session_key")
        return 0
    
    # Read all signals
    signals = []
    if path.exists():
        with open(path) as f:
            for line in f:
                if line.strip():
                    try:
                        signals.append(json.loads(line))
                    except:
                        pass
    
    # Filter to signals from this session that haven't been consumed
    to_consume = []
    for s in signals:
        if s.get("consumed"):
            continue
        if s.get("session_key") != session_key:
            continue
        if signal_filter:
            match = all(s.get(k) == v for k, v in signal_filter.items())
            if not match:
                continue
        to_consume.append(s)
    
    # Write impact entries
    consumed_count = 0
    ts = datetime.now(timezone.utc)
    for s in to_consume:
        s["consumed"] = True
        s["consumed_at"] = ts.isoformat()
        
        impact = {
            "signal_ts": s["ts"],
            "from": s["from"],
            "to": s["to"],
            "type": s["type"],
            "consumed_at": s["consumed_at"],
            "latency_seconds": (ts - ts).total_seconds(),  # Already consumed earlier
            "session_key": session_key,
            "action_taken": action_taken,
            "tracked_at": ts.isoformat()
        }
        with open(impact_path, "a") as impf:
            impf.write(json.dumps(impact) + "\n")
        consumed_count += 1
    
    # Rewrite signals file
    with open(path, "w") as f:
        for s in signals:
            f.write(json.dumps(s) + "\n")
    
    if consumed_count > 0:
        log.info(f"Marked {consumed_count} signals consumed with action_taken={action_taken}")
    
    return consumed_count

def read_signals_with_influence_check(for_agent, agent_output, max_age_days=14):
    """Read signals and check if they influenced the agent's output.
    
    Convenience function that:
    1. Reads signals (mark_consumed=False)
    2. Checks if any signals influenced the output
    3. Marks signals as consumed with the influence result
    
    Args:
        for_agent: Agent name to read signals for
        agent_output: The text output from the agent (to check for influence)
        max_age_days: Max age of signals to consider
    
    Returns:
        List of signal dicts (same as read_signals)
    """
    # Step 1: Read signals without consuming
    signals = read_signals(for_agent, max_age_days=max_age_days, mark_consumed=False)
    
    if not signals:
        return []
    
    # Step 2: Check if any signal content appears in output
    action_taken = detect_signal_influence(signals, agent_output)
    
    # Step 3: Mark consumed with influence data
    mark_signals_consumed_for_agent(for_agent, action_taken, signals)
    
    return signals

def mark_signals_consumed_for_agent(agent, action_taken, signals):
    """Mark specific signals as consumed for an agent."""
    path = SHARED_DIR / "signals.jsonl"
    impact_path = SHARED_DIR / "signal_impact.jsonl"
    
    if not signals:
        return 0
    
    # Read all signals
    all_signals = []
    if path.exists():
        with open(path) as f:
            for line in f:
                if line.strip():
                    try:
                        all_signals.append(json.loads(line))
                    except:
                        pass
    
    # Find signals to mark (matching by ts, from, to)
    signal_ids = set((s.get("ts"), s.get("from"), s.get("to")) for s in signals)
    ts = datetime.now(timezone.utc)
    consumed_count = 0
    
    for s in all_signals:
        if s.get("consumed"):
            continue
        sid = (s.get("ts"), s.get("from"), s.get("to"))
        if sid in signal_ids:
            s["consumed"] = True
            s["consumed_at"] = ts.isoformat()
            
            impact = {
                "signal_ts": s["ts"],
                "from": s["from"],
                "to": s["to"],
                "type": s["type"],
                "consumed_at": s["consumed_at"],
                "latency_seconds": 0,
                "action_taken": action_taken,
                "tracked_at": ts.isoformat()
            }
            with open(impact_path, "a") as impf:
                impf.write(json.dumps(impact) + "\n")
            consumed_count += 1
    
    # Rewrite
    with open(path, "w") as f:
        for s in all_signals:
            f.write(json.dumps(s) + "\n")
    
    if consumed_count > 0:
        log.info(f"Marked {consumed_count} signals consumed for {agent}, action_taken={action_taken}")
    
    return consumed_count

