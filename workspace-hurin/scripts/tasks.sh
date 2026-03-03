#!/bin/bash
# tasks.sh - View active Claude Code task status and terminal output.
#
# Usage:
#   tasks.sh           - show status of all active tasks + last 20 lines each
#   tasks.sh <task-id> - attach to that task's tmux session (live, read-only)
#   tasks.sh -l        - just list active tasks (no output)
#   tasks.sh --kill <task-id> - kill a stuck task and clean up

DEV_REPO="${DEV_REPO:-$HOME/.openclaw/workspace-hurin/theapp}"
REGISTRY="$DEV_REPO/.clawdbot/active-tasks.json"

if [[ ! -f "$REGISTRY" ]]; then
    echo "No task registry found at $REGISTRY"
    exit 0
fi

# Handle kill command
if [[ "$1" == "--kill" ]]; then
    TASK_ID="$2"
    if [[ -z "$TASK_ID" ]]; then
        echo "Usage: tasks.sh --kill <task-id>"
        exit 1
    fi
    
    # Get task info from registry
    TASK_INFO=$(python3 -c "
import json
data = json.load(open('$REGISTRY'))
t = next((t for t in data['tasks'] if t['id'] == '$TASK_ID'), None)
if t:
    print(t.get('tmuxSession', '') + '|' + t.get('worktree', '') + '|' + t.get('repo', ''))
else:
    print('')
")
    
    if [[ -z "$TASK_INFO" ]]; then
        echo "Task '$TASK_ID' not found in registry."
        exit 1
    fi
    
    SESSION=$(echo "$TASK_INFO" | cut -d'|' -f1)
    WORKTREE=$(echo "$TASK_INFO" | cut -d'|' -f2)
    REPO=$(echo "$TASK_INFO" | cut -d'|' -f3)
    
    echo "→ Killing task: $TASK_ID"
    echo "  Session: $SESSION"
    echo "  Worktree: $WORKTREE"
    
    # Kill tmux session if exists
    if tmux has-session -t "$SESSION" 2>/dev/null; then
        echo "  → Killing tmux session..."
        tmux kill-session -t "$SESSION" 2>/dev/null || true
        echo "  ✓ tmux session killed"
    else
        echo "  (tmux session already dead)"
    fi
    
    # Remove worktree if exists
    if [[ -d "$WORKTREE" ]]; then
        echo "  → Removing worktree..."
        cd "$DEV_REPO"
        git worktree remove --force "$WORKTREE" 2>/dev/null || rm -rf "$WORKTREE"
        echo "  ✓ worktree removed"
    else
        echo "  (worktree already gone)"
    fi
    
    # Remove from registry (mark as killed instead of failed to avoid Ralph Loop)
    python3 - <<PYEOF
import json
registry_path = "$REGISTRY"
data = json.load(open(registry_path))
data["tasks"] = [t for t in data["tasks"] if t["id"] != "$TASK_ID"]
# Optionally add to a 'killed' list for history (skip for now)
registry_path = Path("$REGISTRY")
from pathlib import Path
Path(registry_path).write_text(json.dumps(data, indent=2))
PYEOF
    
    echo "✓ Task $TASK_ID killed and cleaned up"
    echo "  (Removed from registry - Ralph Loop will not attempt respawn)"
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
from pathlib import Path

dev_repo = Path.home() / ".openclaw/workspace-hurin/theapp"
registry_path = dev_repo / ".clawdbot/active-tasks.json"

if not registry_path.exists():
    print(f"Registry not found at {registry_path}")
    sys.exit(0)

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
            output = ""
            # Try tmux capture first
            result = subprocess.run(
                f"tmux capture-pane -t '{session}' -p",
                shell=True, capture_output=True, text=True
            )
            output = result.stdout.strip()
            # Fall back to task log if tmux pane is empty
            if not output:
                task_log = Path.home() / f".openclaw/monitor/task-logs/{tid}.log"
                if task_log.exists():
                    output = task_log.read_text().strip()
            if output:
                lines = output.splitlines()[-20:]
                print(f"\n  {'─'*20} last 20 lines {'─'*20}")
                for line in lines:
                    print(f"  {line}")

print(f"\n{'─'*60}")

# Show queued tasks
queue_file = Path.home() / ".openclaw/monitor/task-queue.json"
if queue_file.exists():
    try:
        queue_data = json.load(open(queue_file))
        queue = queue_data.get("queue", [])
        if queue:
            print(f"\nQueued ({len(queue)}):")
            for i, entry in enumerate(queue):
                qid = entry.get("task_id", "?")
                qrepo = entry.get("repo", "?")
                qdesc = entry.get("description", "")
                print(f"  {i+1}. {qid}  [{qrepo}]  {qdesc}")
    except (json.JSONDecodeError, IOError):
        pass

if inactive:
    done   = [t for t in inactive if t["status"] == "done"]
    failed = [t for t in inactive if t["status"] == "failed"]
    if done:
        print(f"\nCompleted: {', '.join(t['id'] for t in done)}")
    if failed:
        print(f"Failed:    {', '.join(t['id'] for t in failed)}")
PYEOF
