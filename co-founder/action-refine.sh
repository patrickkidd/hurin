#!/usr/bin/env bash
set -euo pipefail

# Co-Founder Action System — Refine
# ADR: ~/.openclaw/adrs/ADR-0005-action-system.md
#
# Iterative refinement: Patrick shapes a proposal before approving.
# Resumes the CC session from the original briefing with feedback,
# CC revises the action plan and spawn_prompt.
#
# Usage: action-refine.sh <action-id> <feedback...>

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

ACTION_ID="${1:?Usage: action-refine.sh <action-id> <feedback...>}"
shift
FEEDBACK="${*:?Usage: action-refine.sh <action-id> <feedback...>}"

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
    exit 1
fi

# Read action details
ACTION="$(jq ".actions[$ACTION_INDEX]" "$ACTIONS_FILE")"
TIER="$(echo "$ACTION" | jq -r '.tier')"
STATUS="$(echo "$ACTION" | jq -r '.status // "unknown"')"
TITLE="$(echo "$ACTION" | jq -r '.title')"
ISSUE_URL="$(echo "$ACTION" | jq -r '.issue_url // ""')"
ISSUE_NUMBER="$(echo "$ISSUE_URL" | grep -o '[0-9]*$' || true)"

if [[ "$STATUS" != "pending_approval" ]]; then
    echo "ERROR: Action $ACTION_ID status is '$STATUS'. Can only refine pending_approval actions." >&2
    exit 1
fi

# Find the lens name from the action ID to get the session
LENS_NAME="$(echo "$ACTION_ID" | sed 's/-[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}.*//')"
SESSION_FILE="$SESSIONS_DIR/${LENS_NAME}-session.txt"

if [[ ! -f "$SESSION_FILE" ]]; then
    echo "ERROR: No session found for lens '$LENS_NAME'. Cannot resume for refinement." >&2
    exit 1
fi

SESSION_ID="$(cat "$SESSION_FILE")"

echo "[$(date '+%Y-%m-%d %H:%M')] Refining action: $ACTION_ID"
echo "  Title:    $TITLE"
echo "  Feedback: $FEEDBACK"
echo "  Session:  $SESSION_ID"

# Build refinement prompt
REFINE_PROMPT="$(cat <<EOF
I want to refine one of the actions you proposed in your last briefing.

**Action ID:** $ACTION_ID
**Title:** $TITLE

**My feedback:** $FEEDBACK

Please revise the action based on my feedback. Output ONLY the revised action as a JSON code block with the key "revised_action", using the same schema as before:

\`\`\`proposed-actions
{
  "revised_action": {
    "id": "$ACTION_ID",
    "title": "...",
    "tier": "...",
    "category": "...",
    "effort": "...",
    "confidence": ...,
    "repo": "...",
    "plan": "...",
    "spawn_prompt": "...",
    "success_metric": "..."
  }
}
\`\`\`

After the JSON block, briefly explain what you changed and why.
EOF
)"

# Resume CC session for refinement
# Unset CLAUDECODE to allow nested CC invocation
unset CLAUDECODE
CC_RESULT="$(cd "$THEAPP" && "$CLAUDE_BIN" -p \
    --model "$CLAUDE_MODEL" \
    --dangerously-skip-permissions \
    --resume "$SESSION_ID" \
    <<< "$REFINE_PROMPT" 2>&1)" || {
    echo "ERROR: Claude Code refinement failed" >&2
    echo "$CC_RESULT" >&2
    exit 1
}

# Try to parse revised action from CC's output
# Look for JSON result in the output
CC_TEXT=""
if echo "$CC_RESULT" | jq -e '.result' > /dev/null 2>&1; then
    CC_TEXT="$(echo "$CC_RESULT" | jq -r '.result')"
else
    CC_TEXT="$CC_RESULT"
fi

REVISED_JSON="$(echo "$CC_TEXT" | sed -n '/```proposed-actions/,/```/p' | sed '1d;$d' 2>/dev/null || true)"

if [[ -n "$REVISED_JSON" ]] && echo "$REVISED_JSON" | jq -e '.revised_action' > /dev/null 2>&1; then
    # Update the action in the JSON file with revised fields
    REVISED="$(echo "$REVISED_JSON" | jq '.revised_action')"

    # Merge revised fields into the existing action, preserving status/issue_url
    jq --argjson revised "$REVISED" "
        .actions[$ACTION_INDEX].title = \$revised.title |
        .actions[$ACTION_INDEX].tier = \$revised.tier |
        .actions[$ACTION_INDEX].category = \$revised.category |
        .actions[$ACTION_INDEX].effort = \$revised.effort |
        .actions[$ACTION_INDEX].confidence = \$revised.confidence |
        .actions[$ACTION_INDEX].repo = \$revised.repo |
        .actions[$ACTION_INDEX].plan = \$revised.plan |
        .actions[$ACTION_INDEX].spawn_prompt = \$revised.spawn_prompt |
        .actions[$ACTION_INDEX].success_metric = \$revised.success_metric |
        .actions[$ACTION_INDEX].refined_at = \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\"
    " "$ACTIONS_FILE" > "${ACTIONS_FILE}.tmp" && mv "${ACTIONS_FILE}.tmp" "$ACTIONS_FILE"

    echo "[$(date '+%Y-%m-%d %H:%M')] Action revised successfully"

    # Comment on GitHub issue with revision
    if [[ -n "$ISSUE_NUMBER" ]]; then
        REVISED_TITLE="$(echo "$REVISED" | jq -r '.title')"
        REVISED_PLAN="$(echo "$REVISED" | jq -r '.plan')"
        gh issue comment "$ISSUE_NUMBER" --repo "$GITHUB_REPO" \
            --body "$(cat <<COMMENT
🔄 **Refined** based on feedback: "$FEEDBACK"

**Revised title:** $REVISED_TITLE

**Revised plan:**
$REVISED_PLAN

\`/cofounder approve $ACTION_ID\` to spawn, or \`/cofounder refine $ACTION_ID <more feedback>\` to iterate further.
COMMENT
)" 2>/dev/null || true
    fi

    # Commit and push
    (
        cd "$HOME/.openclaw"
        git add "co-founder/actions/$(basename "$ACTIONS_FILE")" 2>/dev/null || true
        git commit -m "co-founder: refined $ACTION_ID" --no-gpg-sign 2>/dev/null || true
        git -c "credential.helper=!gh auth git-credential" push 2>/dev/null || true
    )
else
    echo "WARNING: Could not parse revised action JSON from CC output." >&2
    echo "CC's full response follows:" >&2
fi

# Output CC's response for relay to Discord
echo ""
echo "$CC_TEXT"
