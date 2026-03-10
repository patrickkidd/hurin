#!/bin/bash
# task-cli.sh — Simple task CLI for Discord skill integration
# Usage: task-cli.sh <command> [args...]

REGISTRY="$HOME/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"
QUEUE_FILE="$HOME/.openclaw/monitor/task-queue.json"
QUEUE_PROMPTS="$HOME/.openclaw/monitor/queue-prompts"
KILL_DIR="$HOME/.openclaw/monitor/kill-sentinels"
TASK_LOGS="$HOME/.openclaw/monitor/task-logs"

CMD="${1:-help}"
shift

case "$CMD" in
    list)
        python3 <<'PYEOF'
import json
from datetime import datetime, timezone
from pathlib import Path

reg = Path.home() / ".openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"
queue = Path.home() / ".openclaw/monitor/task-queue.json"

if reg.exists():
    data = json.load(open(reg))
    tasks = data.get("tasks", [])
else:
    tasks = []

# Group by status
running = [t for t in tasks if t["status"] == "running"]
queued_tasks = []
if queue.exists():
    qdata = json.load(open(queue))
    queued_tasks = qdata.get("queue", [])
pr_open = [t for t in tasks if t["status"] == "pr_open"]
done = [t for t in tasks if t["status"] == "done"]
failed = [t for t in tasks if t["status"] in ("failed", "killed")]

def fmt_elapsed(t):
    started = t.get("startedAt", 0)
    if not started:
        return "?"
    elapsed = datetime.now(tz=timezone.utc) - datetime.fromtimestamp(started / 1000, tz=timezone.utc)
    hours, rem = divmod(int(elapsed.total_seconds()), 3600)
    mins = rem // 60
    return f"{hours}h{mins:02d}m"

if queued_tasks:
    print("**Queued:**")
    for q in queued_tasks:
        print(f"  ⏳ `{q.get('task_id', '?')}` — {q.get('description', '')[:80]}")

if running:
    print("**Running:**")
    for t in running:
        print(f"  🔄 `{t['id']}` [{t.get('repo','?')}] — {fmt_elapsed(t)} — {t.get('description','')[:60]}")

if pr_open:
    print("**PR Open:**")
    for t in pr_open:
        pr = f"#{t.get('pr','?')}" if t.get('pr') else ""
        print(f"  📝 `{t['id']}` [{t.get('repo','?')}] {pr} — {t.get('description','')[:60]}")

if done:
    print(f"**Done:** {len(done)} tasks")

if failed:
    print(f"**Failed/Killed:** {', '.join(t['id'] for t in failed)}")

if not any([queued_tasks, running, pr_open, done, failed]):
    print("No tasks found.")
PYEOF
        ;;

    spawn)
        REPO="$1"
        TASK_ID="$2"
        shift 2
        DESC="$*"

        if [[ -z "$REPO" || -z "$TASK_ID" || -z "$DESC" ]]; then
            echo "Usage: task spawn <repo> <task-id> '<description>'"
            echo "Repos: btcopilot, familydiagram, fdserver"
            exit 1
        fi

        # Write prompt file
        mkdir -p "$QUEUE_PROMPTS"
        PROMPT_FILE="$QUEUE_PROMPTS/$TASK_ID.txt"
        echo "$DESC" > "$PROMPT_FILE"

        # Add to queue
        python3 - "$REPO" "$TASK_ID" "$DESC" "$PROMPT_FILE" <<'PYEOF'
import json, sys, time
from pathlib import Path

repo, task_id, desc, prompt_file = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
queue_file = Path.home() / ".openclaw/monitor/task-queue.json"

if queue_file.exists():
    data = json.load(open(queue_file))
else:
    data = {"queue": []}

data.setdefault("queue", []).append({
    "task_id": task_id,
    "repo": repo,
    "description": desc,
    "prompt_file": prompt_file,
    "branch": f"feat/{task_id}",
    "queued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
})
queue_file.write_text(json.dumps(data, indent=2))
print(f"✅ Task `{task_id}` queued for `{repo}`. Daemon picks up within 30s.")
PYEOF
        ;;

    status)
        TASK_ID="$1"
        if [[ -z "$TASK_ID" ]]; then
            # Show all statuses
            python3 <<'PYEOF'
import json
from pathlib import Path

reg = Path.home() / ".openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"
if not reg.exists():
    print("No registry found.")
    exit()
data = json.load(open(reg))
for t in data.get("tasks", []):
    pr = f" PR#{t.get('pr','')}" if t.get('pr') else ""
    print(f"`{t['id']}` — **{t['status']}**{pr} [{t.get('repo','?')}]")
PYEOF
        else
            python3 - "$TASK_ID" <<'PYEOF'
import json, sys
from pathlib import Path
from datetime import datetime, timezone

tid = sys.argv[1]
reg = Path.home() / ".openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"
if not reg.exists():
    print("No registry found.")
    exit()
data = json.load(open(reg))
task = next((t for t in data.get("tasks", []) if t["id"] == tid), None)
if not task:
    print(f"Task `{tid}` not found.")
    exit()

started = task.get("startedAt", 0)
if started:
    elapsed = datetime.now(tz=timezone.utc) - datetime.fromtimestamp(started / 1000, tz=timezone.utc)
    hours, rem = divmod(int(elapsed.total_seconds()), 3600)
    mins = rem // 60
    elapsed_str = f"{hours}h{mins:02d}m"
else:
    elapsed_str = "?"

pr = f"\n  PR: #{task.get('pr','')} {task.get('prUrl','')}" if task.get('pr') else ""
print(f"**{tid}** [{task.get('repo','?')}]")
print(f"  Status: {task['status']}")
print(f"  Branch: {task.get('branch','?')}")
print(f"  Elapsed: {elapsed_str}")
print(f"  Respawns: {task.get('respawnCount',0)}{pr}")
print(f"  Description: {task.get('description','')[:200]}")
PYEOF
        fi
        ;;

    kill)
        TASK_ID="$1"
        if [[ -z "$TASK_ID" ]]; then
            echo "Usage: task kill <task-id>"
            exit 1
        fi
        mkdir -p "$KILL_DIR"
        touch "$KILL_DIR/$TASK_ID.kill"
        echo "💀 Kill sentinel written for \`$TASK_ID\`. Should stop within seconds."
        ;;

    watch)
        TASK_ID="$1"
        if [[ -z "$TASK_ID" ]]; then
            echo "Usage: task watch <task-id>"
            exit 1
        fi
        LOG_FILE="$TASK_LOGS/$TASK_ID.log"
        if [[ ! -f "$LOG_FILE" ]]; then
            echo "No log found for \`$TASK_ID\`."
            exit 1
        fi
        tail -30 "$LOG_FILE" | python3 -c '
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        d = json.loads(line)
        t = d.get("type", "?")
        if t == "text":
            print(f"📝 {d.get(\"content\",\"\")[:200]}")
        elif t == "tool_use":
            print(f"🔧 {d.get(\"tool\",\"?\")} — {d.get(\"content\",\"\")[:150]}")
        elif t == "meta":
            print(f"ℹ️  {d.get(\"key\",\"\")} {d.get(\"content\",d.get(\"value\",\"\"))}")
        else:
            print(f"   {t}: {d.get(\"content\",\"\")[:150]}")
    except json.JSONDecodeError:
        print(f"   {line[:150]}")
'
        ;;

    follow-up)
        TASK_ID="$1"
        shift

        # Parse optional flags
        SESSION_ID=""
        REPO=""
        REPLY_CHANNEL=""
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --session) SESSION_ID="$2"; shift 2 ;;
                --repo) REPO="$2"; shift 2 ;;
                --reply-channel) REPLY_CHANNEL="$2"; shift 2 ;;
                *) break ;;
            esac
        done
        MESSAGE="$*"

        if [[ -z "$TASK_ID" || -z "$MESSAGE" ]]; then
            echo "Usage: task follow-up <task-id> '<message>' [--session <id>] [--repo <repo>] [--reply-channel <channel-id>]"
            exit 1
        fi

        # If no session provided, look up from registry
        if [[ -z "$SESSION_ID" ]]; then
            SESSION_ID=$(python3 - "$TASK_ID" <<'PYEOF'
import json, sys
from pathlib import Path
tid = sys.argv[1]
reg = Path.home() / ".openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"
if not reg.exists():
    sys.exit(1)
data = json.load(open(reg))
task = next((t for t in data.get("tasks", []) if t["id"] == tid), None)
if not task or not task.get("session_id"):
    sys.exit(1)
print(task["session_id"])
PYEOF
            )
            if [[ -z "$SESSION_ID" ]]; then
                echo "❌ No session found for \`$TASK_ID\`. Task may not exist or has no saved session."
                exit 1
            fi
        fi

        # Look up repo from registry if not provided
        if [[ -z "$REPO" ]]; then
            REPO=$(python3 - "$TASK_ID" <<'PYEOF'
import json, sys
from pathlib import Path
tid = sys.argv[1]
reg = Path.home() / ".openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"
if reg.exists():
    data = json.load(open(reg))
    task = next((t for t in data.get("tasks", []) if t["id"] == tid), None)
    if task and task.get("repo"):
        print(task["repo"])
        sys.exit(0)
print("theapp")
PYEOF
            )
        fi

        # Enqueue follow-up
        python3 - "$REPO" "$TASK_ID" "$MESSAGE" "$SESSION_ID" "$REPLY_CHANNEL" <<'PYEOF'
import json, sys, time
from pathlib import Path

repo, task_id, message, session_id, reply_channel = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
queue_file = Path.home() / ".openclaw/monitor/task-queue.json"

if queue_file.exists():
    data = json.load(open(queue_file))
else:
    data = {"queue": []}

entry = {
    "task_id": task_id,
    "repo": repo,
    "description": f"Follow-up on {task_id}",
    "follow_up_prompt": message,
    "session_id": session_id,
    "branch": f"feat/{task_id}",
    "queued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
if reply_channel:
    entry["reply_channel_id"] = reply_channel

data.setdefault("queue", []).insert(0, entry)
queue_file.write_text(json.dumps(data, indent=2))
print(f"✅ Follow-up for `{task_id}` queued. Daemon picks up within 30s.")
PYEOF
        ;;

    *)
        echo "**Task CLI commands:**"
        echo "  \`/task list\` — Show all tasks"
        echo "  \`/task spawn <repo> <id> '<desc>'\` — Spawn a new task"
        echo "  \`/task status [id]\` — Show task status"
        echo "  \`/task kill <id>\` — Kill a running task"
        echo "  \`/task watch <id>\` — Show recent log output"
        echo "  \`/task follow-up <id> '<msg>'\` — Resume a task session"
        ;;
esac
