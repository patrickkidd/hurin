#!/usr/bin/env bash
# thread-followup.sh — Map a Discord thread ID to a task and enqueue a follow-up.
#
# Called by hurin when Patrick replies in a task thread.
#
# Usage: thread-followup.sh <discord_thread_id> <message>
#
# Looks up the task by discordThreadId in active-tasks.json,
# then calls `task follow-up <task-id> <message>`.
#
# If the task is currently running, exits with a special message —
# the steer system handles running tasks, not follow-ups.

set -euo pipefail

THREAD_ID="${1:?Usage: thread-followup.sh <discord_thread_id> <message>}"
MESSAGE="${2:?Usage: thread-followup.sh <discord_thread_id> <message>}"

REGISTRY="$HOME/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"

if [[ ! -f "$REGISTRY" ]]; then
    echo "ERROR: Registry not found at $REGISTRY" >&2
    exit 1
fi

# Find task by discordThreadId — return id and status
TASK_INFO=$(python3 -c "
import json, sys
with open('$REGISTRY') as f:
    reg = json.load(f)
for t in reg.get('tasks', []):
    if t.get('discordThreadId') == '$THREAD_ID':
        print(t['id'] + ' ' + t.get('status', 'unknown') + ' ' + (t.get('session_id') or ''))
        sys.exit(0)
sys.exit(1)
" 2>/dev/null) || {
    echo "ERROR: No task found with discordThreadId=$THREAD_ID" >&2
    exit 1
}

TASK_ID=$(echo "$TASK_INFO" | awk '{print $1}')
STATUS=$(echo "$TASK_INFO" | awk '{print $2}')
SESSION_ID=$(echo "$TASK_INFO" | awk '{print $3}')

# If task is running, the steer system handles it — do nothing
if [[ "$STATUS" == "running" ]]; then
    echo "RUNNING: Task $TASK_ID is currently running — your message will be delivered as a live steer (no action needed)."
    exit 0
fi

# Check task has a session_id (required for follow-up)
if [[ -z "$SESSION_ID" ]]; then
    echo "ERROR: Task $TASK_ID (status: $STATUS) has no session_id — cannot resume" >&2
    exit 1
fi

echo "Found task: $TASK_ID (status: $STATUS, thread: $THREAD_ID)"
echo "Enqueueing follow-up: $MESSAGE"

task follow-up "$TASK_ID" "$MESSAGE"
