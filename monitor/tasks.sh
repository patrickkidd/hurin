#!/bin/bash
# tasks.sh - View active Claude Code task status and terminal output.
#
# Usage:
#   tasks.sh           - show status of all active tasks + last 20 lines each
#   tasks.sh <task-id> - attach to that task's tmux session (live, read-only)
#   tasks.sh -l        - just list active tasks (no output)

REGISTRY="$HOME/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"

if [[ ! -f "$REGISTRY" ]]; then
    echo "No task registry found."
    exit 0
fi

# Attach mode
if [[ $# -eq 1 && "$1" != "-l" ]]; then
    TASK_ID="$1"
    SESSION=$(python3 -c "
import json
data = json.load(open('$REGISTRY'))
t = next((t for t in data['tasks'] if t['id'] == '$TASK_ID'), None)
print(t['tmuxSession'] if t else '')
")
    if [[ -z "$SESSION" ]]; then
        echo "Task '$TASK_ID' not found."
        exit 1
    fi
    echo "Attaching to $SESSION (read-only, detach with Ctrl-B D)..."
    tmux attach -t "$SESSION" -r
    exit 0
fi

# Parse registry
python3 - "$1" <<'PYEOF'
import json, subprocess, sys
from datetime import datetime, timezone

registry_path = "/home/hurin/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"
data = json.load(open(registry_path))
tasks = data.get("tasks", [])

list_only = len(sys.argv) > 1 and sys.argv[1] == "-l"

active   = [t for t in tasks if t["status"] in ("running", "pr_open")]
inactive = [t for t in tasks if t["status"] not in ("running", "pr_open")]

if not active:
    print("No active tasks.")
else:
    for t in active:
        tid     = t["id"]
        repo    = t.get("repo", "?")
        session = t["tmuxSession"]
        branch  = t["branch"]
        status  = t["status"]
        started = datetime.fromtimestamp(t["startedAt"] / 1000, tz=timezone.utc)
        elapsed = datetime.now(tz=timezone.utc) - started
        hours, rem = divmod(int(elapsed.total_seconds()), 3600)
        mins = rem // 60

        alive = subprocess.run(
            f"tmux has-session -t '{session}' 2>/dev/null",
            shell=True
        ).returncode == 0

        pr_info = f"  PR: #{t['pr']} {t.get('prUrl','')}" if t.get("pr") else ""
        tmux_status = "● running" if alive else "✗ dead"

        print(f"\n{'─'*60}")
        print(f"  {tid}  [{repo}]  {tmux_status}  {hours}h{mins:02d}m elapsed")
        print(f"  Branch: {branch}{pr_info}")

        if not list_only and alive:
            result = subprocess.run(
                f"tmux capture-pane -t '{session}' -p",
                shell=True, capture_output=True, text=True
            )
            output = result.stdout.strip()
            if output:
                lines = output.splitlines()[-20:]
                print(f"\n  {'─'*20} last 20 lines {'─'*20}")
                for line in lines:
                    print(f"  {line}")

print(f"\n{'─'*60}")

if inactive:
    done   = [t for t in inactive if t["status"] == "done"]
    failed = [t for t in inactive if t["status"] == "failed"]
    if done:
        print(f"\nCompleted: {', '.join(t['id'] for t in done)}")
    if failed:
        print(f"Failed:    {', '.join(t['id'] for t in failed)}")
PYEOF
