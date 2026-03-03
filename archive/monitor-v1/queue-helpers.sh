#!/usr/bin/env bash
# Shared task queue helpers — used by action-router.sh and action-approve.sh
# Serializes task spawning so only 1 runs at a time on this 16GB M4.

QUEUE_FILE="$HOME/.openclaw/monitor/task-queue.json"
QUEUE_PROMPTS_DIR="$HOME/.openclaw/monitor/queue-prompts"
TASK_REGISTRY="$HOME/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"

_ensure_queue_infra() {
    mkdir -p "$QUEUE_PROMPTS_DIR"
    if [[ ! -f "$QUEUE_FILE" ]]; then
        echo '{"queue": []}' > "$QUEUE_FILE"
    fi
}

has_running_tasks() {
    # Returns 0 (true) if any task in the registry has status "running"
    if [[ ! -f "$TASK_REGISTRY" ]]; then
        return 1
    fi
    local running_count
    running_count="$(jq '[.tasks[] | select(.status == "running")] | length' "$TASK_REGISTRY" 2>/dev/null || echo 0)"
    [[ "$running_count" -gt 0 ]]
}

enqueue_task() {
    # Usage: enqueue_task <task_id> <repo> <description> <prompt> <actions_file> <action_index> <issue_number>
    local task_id="$1"
    local repo="$2"
    local description="$3"
    local prompt="$4"
    local actions_file="$5"
    local action_index="$6"
    local issue_number="${7:-}"

    _ensure_queue_infra

    # Write prompt to file (avoids JSON escaping issues)
    local prompt_file="$QUEUE_PROMPTS_DIR/${task_id}.txt"
    printf '%s' "$prompt" > "$prompt_file"

    # Append entry to queue
    local queued_at
    queued_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

    jq --arg tid "$task_id" \
       --arg repo "$repo" \
       --arg desc "$description" \
       --arg pf "$prompt_file" \
       --arg af "$actions_file" \
       --argjson ai "$action_index" \
       --arg inum "$issue_number" \
       --arg qa "$queued_at" \
       '.queue += [{
           task_id: $tid,
           repo: $repo,
           description: $desc,
           prompt_file: $pf,
           actions_file: $af,
           action_index: ($ai | tonumber),
           issue_number: $inum,
           queued_at: $qa
       }]' "$QUEUE_FILE" > "${QUEUE_FILE}.tmp" && mv "${QUEUE_FILE}.tmp" "$QUEUE_FILE"

    # Return queue position
    local pos
    pos="$(jq '.queue | length' "$QUEUE_FILE")"
    echo "$pos"
}

queue_length() {
    _ensure_queue_infra
    jq '.queue | length' "$QUEUE_FILE"
}
