#!/usr/bin/env bash
set -euo pipefail

# Co-Founder Action System — Approve
# ADR: ~/.openclaw/adrs/ADR-0005-action-system.md
#
# Approves a propose-tier action and spawns it via spawn-task.sh.
#
# Usage: action-approve.sh <action-id>

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"
# Queue helpers — inline enqueue (daemon picks up in ≤30s)
QUEUE_FILE="$HOME/.openclaw/monitor/task-queue.json"
QUEUE_PROMPTS_DIR="$HOME/.openclaw/monitor/queue-prompts"

_ensure_queue_infra() {
    mkdir -p "$QUEUE_PROMPTS_DIR"
    [[ -f "$QUEUE_FILE" ]] || echo '{"queue":[]}' > "$QUEUE_FILE"
}

enqueue_task() {
    local task_id="$1" repo="$2" description="$3" prompt="$4" actions_file="${5:-}" action_index="${6:-0}" issue_number="${7:-}"
    _ensure_queue_infra
    echo "$prompt" > "$QUEUE_PROMPTS_DIR/${task_id}.txt"
    local entry
    entry="$(jq -n \
        --arg tid "$task_id" --arg repo "$repo" --arg desc "$description" \
        --arg pf "$QUEUE_PROMPTS_DIR/${task_id}.txt" \
        --arg af "$actions_file" --argjson ai "$action_index" \
        --arg issue "$issue_number" \
        --arg ts "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
        '{task_id: $tid, repo: $repo, description: $desc, prompt_file: $pf, actions_file: $af, action_index: $ai, issue_number: $issue, queued_at: $ts}')"
    local tmp="${QUEUE_FILE}.tmp.$$"
    jq --argjson entry "$entry" '.queue += [$entry]' "$QUEUE_FILE" > "$tmp" && mv "$tmp" "$QUEUE_FILE"
    jq '.queue | length' "$QUEUE_FILE"
}

has_running_tasks() {
    local TASK_REGISTRY="$HOME/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"
    [[ -f "$TASK_REGISTRY" ]] || return 1
    local count
    count="$(jq '[.tasks[] | select(.status == "running")] | length' "$TASK_REGISTRY" 2>/dev/null)"
    [[ "$count" -gt 0 ]]
}

ACTION_ID="${1:?Usage: action-approve.sh <action-id>}"

GITHUB_REPO="patrickkidd/theapp"

# Find the action across all actions/*.json files
ACTIONS_FILE=""
ACTION_INDEX=""

for f in "$ACTIONS_DIR"/*.json; do
    [[ -f "$f" ]] || continue
    IDX="$(jq -r --arg id "$ACTION_ID" '[.actions[] | .id] | to_entries[] | select(.value == $id) | .key' "$f" 2>/dev/null)"
    if [[ -n "$IDX" ]]; then
        ACTIONS_FILE="$f"
        ACTION_INDEX="$IDX"
        break
    fi
done

if [[ -z "$ACTIONS_FILE" ]]; then
    echo "ERROR: Action not found: $ACTION_ID" >&2
    echo "Run '/cofounder actions' to see pending actions." >&2
    exit 1
fi

# Read action details
ACTION="$(jq ".actions[$ACTION_INDEX]" "$ACTIONS_FILE")"
TIER="$(echo "$ACTION" | jq -r '.tier')"
STATUS="$(echo "$ACTION" | jq -r '.status // "unknown"')"
TITLE="$(echo "$ACTION" | jq -r '.title')"
REPO="$(echo "$ACTION" | jq -r '.repo // "none"')"
SPAWN_PROMPT="$(echo "$ACTION" | jq -r '.spawn_prompt // ""')"
ISSUE_URL="$(echo "$ACTION" | jq -r '.issue_url // ""')"
ISSUE_NUMBER="$(echo "$ISSUE_URL" | grep -o '[0-9]*$' || true)"

# Validate
if [[ "$STATUS" != "pending_approval" ]]; then
    echo "ERROR: Action $ACTION_ID status is '$STATUS', expected 'pending_approval'." >&2
    exit 1
fi

if [[ -z "$SPAWN_PROMPT" ]]; then
    echo "ERROR: Action $ACTION_ID has no spawn_prompt." >&2
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M')] Approving action: $ACTION_ID"
echo "  Title: $TITLE"
echo "  Repo:  $REPO"

# Handle website actions differently
if [[ "$REPO" == "website" ]]; then
    echo "  → Website action: creating WordPress draft"
    "$SCRIPT_DIR/wp-draft.sh" \
        --title "$TITLE" \
        --content "$SPAWN_PROMPT" \
        --type "post" \
        --action-id "$ACTION_ID" 2>&1 || {
        echo "ERROR: WordPress draft creation failed" >&2
        exit 1
    }
    jq ".actions[$ACTION_INDEX].status = \"queued\" | .actions[$ACTION_INDEX].approved_at = \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\"" "$ACTIONS_FILE" > "${ACTIONS_FILE}.tmp" && mv "${ACTIONS_FILE}.tmp" "$ACTIONS_FILE"
elif [[ "$REPO" != "none" ]]; then
    TASK_ID="cf-${ACTION_ID}"

    # Always enqueue — daemon picks up in ≤30s
    echo "  → Enqueuing task: $TASK_ID"
    QUEUE_POS="$(enqueue_task "$TASK_ID" "$REPO" "[co-founder] $TITLE" "$SPAWN_PROMPT" "$ACTIONS_FILE" "$ACTION_INDEX" "$ISSUE_NUMBER")"
    jq ".actions[$ACTION_INDEX].status = \"queued\" | .actions[$ACTION_INDEX].approved_at = \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\"" "$ACTIONS_FILE" > "${ACTIONS_FILE}.tmp" && mv "${ACTIONS_FILE}.tmp" "$ACTIONS_FILE"

    if [[ -n "$ISSUE_NUMBER" ]]; then
        gh issue edit "$ISSUE_NUMBER" --repo "$GITHUB_REPO" --add-label "cf-approved" 2>/dev/null || true
        gh issue comment "$ISSUE_NUMBER" --repo "$GITHUB_REPO" \
            --body "✅ Approved and enqueued as task \`$TASK_ID\` (position $QUEUE_POS). Daemon picks up in ≤30s." 2>/dev/null || true
    fi

    echo "  → Enqueued: $TASK_ID (position $QUEUE_POS)"
elif [[ "$REPO" == "none" ]]; then
    # Infrastructure/monitor task — execute directly via Claude CLI
    echo "  → Infrastructure action (repo=none): executing via Claude CLI"
    cd "$HOME/.openclaw/workspace-hurin/theapp"
    RESULT=$(claude -p --model claude-opus-4-6 --dangerously-skip-permissions <<PROMPT
$SPAWN_PROMPT
PROMPT
) || {
        echo "ERROR: Claude CLI execution failed" >&2
        exit 1
    }
    echo "$RESULT"

    # Update status
    jq ".actions[$ACTION_INDEX].status = \"queued\" | .actions[$ACTION_INDEX].approved_at = \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\"" "$ACTIONS_FILE" > "${ACTIONS_FILE}.tmp" && mv "${ACTIONS_FILE}.tmp" "$ACTIONS_FILE"

    # Comment on GitHub issue
    if [[ -n "$ISSUE_NUMBER" ]]; then
        gh issue comment "$ISSUE_NUMBER" --repo "$GITHUB_REPO" \
            --body "✅ Approved and executed directly (infrastructure task). Result:\n\n\`\`\`\n$(echo "$RESULT" | head -20)\n\`\`\`" 2>/dev/null || true
    fi

    echo "  → Infrastructure action executed."
else
    echo "ERROR: Action $ACTION_ID has unknown repo value: '$REPO'" >&2
    exit 1
fi
# Commit and push
(
    cd "$HOME/.openclaw"
    git add "co-founder/actions/$(basename "$ACTIONS_FILE")" 2>/dev/null || true
    git commit -m "co-founder: approved $ACTION_ID" --no-gpg-sign || true
    
    # Push to feature-sign 2>/ branch (NEVER push to main/master)
    git -c "credential.helper=!gh auth git-credential" push 2>/dev/null || {
        echo "WARNING: git push failed" >&2
    }
    
    # Create PR if it doesn't exist (NEVER commit directly to main)
    PR_BRANCH="feat/co-founder-system"
    if ! gh pr view "$PR_BRANCH" --repo "patrickkidd/hurin" >/dev/null 2>&1; then
        gh pr create --base main --head "$PR_BRANCH" \
            --title "co-founder: approved $ACTION_ID" \
            --body "Automated PR from co-founder action system" 2>/dev/null || true
    fi
)


echo "[$(date '+%Y-%m-%d %H:%M')] Action $ACTION_ID approved and enqueued."
