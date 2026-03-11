#!/usr/bin/env python3
"""
Signal CLI — view and emit signals from command line.
Usage:
  signals_cli.py list [agent]              — list recent signals
  signals_cli.py emit <to> <type> <message> — emit a signal (urgency: digest)
  signals_cli.py emit <to> <type> <message> --urgency priority
"""

import json
import sys
import getopt
from datetime import datetime, timezone, timedelta
from pathlib import Path

SHARED_DIR = Path.home() / ".openclaw/knowledge/shared"

VALID_AGENTS = {"huor", "tuor", "beren", "system", "all"}
VALID_TYPES = {
    "anomaly", "metric", "priority_shift", "architecture_insight",
    "challenge", "red_team", "pre_mortem", "pre_mortem_request",
    "calibration", "process_correction", "cross_correlation", "lesson_learned"
}
VALID_URGENCY = {"digest", "priority", "critical"}

def list_signals(agent=None, max_age_days=14):
    """List recent signals."""
    path = SHARED_DIR / "signals.jsonl"
    if not path.exists():
        print("No signals found.")
        return
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    signals = []
    
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                s = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = datetime.fromisoformat(s["ts"].replace("Z", "+00:00"))
            if ts < cutoff:
                continue
            if agent and s.get("to") not in (agent, "all"):
                continue
            signals.append(s)
    
    if not signals:
        print(f"No signals found for {agent or 'all'} in last {max_age_days} days.")
        return
    
    print(f"## Recent Signals ({len(signals)})")
    print()
    for s in signals:
        ts = datetime.fromisoformat(s["ts"].replace("Z", "+00:00"))
        consumed = "✓" if s.get("consumed") else "○"
        urgency = s.get("urgency", "digest")
        urgency_emoji = {"critical": "🔴", "priority": "🟡", "digest": "⚪"}.get(urgency, "⚪")
        print(f"{consumed}{urgency_emoji} [{ts.strftime('%Y-%m-%d %H:%M')}] {s['from']} → {s['to']}")
        print(f"  type: {s['type']} | urgency: {urgency}")
        print(f"  {s['signal'][:80]}...")
        print()

def emit_signal(from_agent, to_agent, signal_type, message, confidence=0.8, urgency="digest"):
    """Emit a new signal."""
    if from_agent not in VALID_AGENTS:
        print(f"Error: invalid from_agent. Must be one of: {VALID_AGENTS}")
        sys.exit(1)
    if to_agent not in VALID_AGENTS:
        print(f"Error: invalid to_agent. Must be one of: {VALID_AGENTS}")
        sys.exit(1)
    if signal_type not in VALID_TYPES:
        print(f"Error: invalid signal_type. Must be one of: {VALID_TYPES}")
        sys.exit(1)
    if urgency not in VALID_URGENCY:
        print(f"Error: invalid urgency. Must be one of: {VALID_URGENCY}")
        sys.exit(1)
    
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "from": from_agent,
        "to": to_agent,
        "type": signal_type,
        "signal": message[:500],
        "confidence": confidence,
        "consumed": False,
        "urgency": urgency,
        "source_artifact": "cli"
    }
    
    with open(SHARED_DIR / "signals.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    print(f"✓ Signal emitted: {from_agent} → {to_agent} [{signal_type}] (urgency: {urgency})")
    print(f"  {message[:100]}...")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    cmd = sys.argv[1]
    urgency = "digest"
    
    # Parse global options
    try:
        opts, args = getopt.getopt(sys.argv[2:], "", ["urgency="])
        for o, v in opts:
            if o == "--urgency":
                urgency = v
    except getopt.GetoptError:
        pass
    
    if cmd == "list":
        agent = args[0] if args else None
        list_signals(agent)
    elif cmd == "emit":
        if len(args) < 3:
            print("Usage: signals_cli.py emit <to> <type> <message> [--urgency priority|critical]")
            sys.exit(1)
        emit_signal("beren", args[0], args[1], " ".join(args[2:]), urgency=urgency)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)

if __name__ == "__main__":
    main()
