#!/usr/bin/env bash
set -euo pipefail

# Co-Founder Action System — Status
#
# Unified status view reading from GitHub Issues (source of truth),
# the task queue, and active-tasks registry.
#
# Usage: action-status.sh [--json]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"
source "$HOME/.openclaw/monitor/queue-helpers.sh"

GITHUB_REPO="patrickkidd/theapp"
REGISTRY="$HOME/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"
JSON_MODE=false
[[ "${1:-}" == "--json" ]] && JSON_MODE=true

# --- 1. Fetch all co-founder issues from GitHub ---
ISSUES="$(gh issue list --repo "$GITHUB_REPO" --label co-founder --state all --limit 100 \
    --json number,title,state,labels,url 2>/dev/null || echo '[]')"

# --- 2. Fetch all open PRs for this repo (to verify PRs exist) ---
ALL_PRS="$(gh pr list --repo "$GITHUB_REPO" --state open --json number,title,body 2>/dev/null || echo '[]')"

# --- 3. Read queue ---
QUEUE_LEN="$(queue_length)"
QUEUE_TASKS=""
if [[ -f "$QUEUE_FILE" ]]; then
    QUEUE_TASKS="$(jq -r '.queue[].task_id' "$QUEUE_FILE" 2>/dev/null || echo '')"
fi

# --- 4. Read registry for running tasks ---
RUNNING_TASKS=""
if [[ -f "$REGISTRY" ]]; then
    RUNNING_TASKS="$(jq -r '.tasks[] | select(.status == "running") | .id' "$REGISTRY" 2>/dev/null || echo '')"
fi

if [[ "$JSON_MODE" == true ]]; then
    echo "$ISSUES"
    exit 0
fi

# --- Helper: check if PR exists for issue ---
has_pr_for_issue() {
    local issue_num="$1"
    echo "$ALL_PRS" | jq -r --arg n "$issue_num" '.[] | select(.body | contains("#" + $n)) | .number' | head -1
}

# --- Format output ---
echo "**Co-Founder Status**"
echo ""

# Build list of queued issue numbers for deduplication
QUEUED_ISSUES=""
if [[ -f "$QUEUE_FILE" ]]; then
    QUEUED_ISSUES="$(jq -r '.queue[].issue_number // empty' "$QUEUE_FILE" 2>/dev/null)"
fi

# Categorize issues by lifecycle label
PR_REVIEW=""
SPAWNED=""
PENDING=""
DONE=""

ISSUE_COUNT="$(echo "$ISSUES" | jq 'length')"
for i in $(seq 0 $((ISSUE_COUNT - 1))); do
    ISSUE="$(echo "$ISSUES" | jq ".[$i]")"
    NUM="$(echo "$ISSUE" | jq -r '.number')"
    TITLE="$(echo "$ISSUE" | jq -r '.title' | sed 's/^\[co-founder\] //')"
    STATE="$(echo "$ISSUE" | jq -r '.state')"
    URL="$(echo "$ISSUE" | jq -r '.url')"
    LABELS="$(echo "$ISSUE" | jq -r '[.labels[].name] | join(",")')"

    if [[ "$STATE" == "CLOSED" ]]; then
        DONE="${DONE}  ✅ #${NUM} ${TITLE}\n"
        continue
    fi

    # Skip issues already shown in the queue section
    if echo "$QUEUED_ISSUES" | grep -q "^${NUM}$"; then
        continue
    fi

    # Determine lifecycle stage from labels
    if echo "$LABELS" | grep -q "cf-pr-open"; then
        PR_REVIEW="${PR_REVIEW}  🔍 #${NUM} ${TITLE}\n     <${URL}>\n"
    elif echo "$LABELS" | grep -q "cf-spawned"; then
        SPAWNED="${SPAWNED}  🤖 #${NUM} ${TITLE}\n"
    elif echo "$LABELS" | grep -q "cf-approved"; then
        # Already in pipeline (spawned or queued) — show as running
        SPAWNED="${SPAWNED}  🤖 #${NUM} ${TITLE}\n"
    elif echo "$LABELS" | grep -q "cf-done"; then
        DONE="${DONE}  ✅ #${NUM} ${TITLE}\n"
    else
        PENDING="${PENDING}  📋 #${NUM} ${TITLE}\n     \`/cofounder approve $(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | head -c 30)\` — see issue for ID\n"
    fi
done

# --- Print sections ---
if [[ -n "$PR_REVIEW" ]]; then
    echo "**🔍 Ready for Review** (PRs open — your action needed)"
    echo -e "$PR_REVIEW"
fi

if [[ -n "$SPAWNED" ]]; then
    echo "**🤖 Running** (task in progress)"
    echo -e "$SPAWNED"
fi

if [[ "$QUEUE_LEN" -gt 0 ]]; then
    echo "**⏳ Queued** ($QUEUE_LEN tasks waiting)"
    if [[ -f "$QUEUE_FILE" ]]; then
        jq -r '.queue[] | "  ⏳ \(.task_id): \(.description)"' "$QUEUE_FILE" 2>/dev/null
    fi
    echo ""
fi

if [[ -n "$PENDING" ]]; then
    echo "**📋 Awaiting Approval** (proposed by co-founder)"
    # Print pending with approve commands from action files
    for f in "$ACTIONS_DIR"/*.json; do
        [[ -f "$f" ]] || continue
        jq -r '.actions[] | select(.status == "pending_approval") | "  📋 \(.title) [\(.effort), \(.category)]\n     → `/cofounder approve \(.id)`"' "$f" 2>/dev/null
    done
    echo ""
fi

# Summary line
OPEN_COUNT="$(echo "$ISSUES" | jq '[.[] | select(.state == "OPEN")] | length')"
CLOSED_COUNT="$(echo "$ISSUES" | jq '[.[] | select(.state == "CLOSED")] | length')"
echo "---"
echo "**Total:** ${OPEN_COUNT} open | ${CLOSED_COUNT} closed | ${QUEUE_LEN} queued"
