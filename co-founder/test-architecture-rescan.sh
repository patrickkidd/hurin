#!/usr/bin/env bash
set -euo pipefail

# Test script: Re-scan an existing architecture briefing for quick wins
# and run the full pipeline (extract → route → auto-spawn).
#
# Usage: ./test-architecture-rescan.sh [briefing-file]
# Default: latest architecture briefing
#
# This is a true e2e test of the updated co-founder action pipeline:
# 1. Feeds the briefing back to CC with updated action criteria
# 2. Saves extracted actions JSON
# 3. Posts to Discord (#co-founder thread + #quick-wins)
# 4. Auto-spawns architecture actions with a target repo

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

BRIEFING="${1:-$BRIEFINGS_DIR/architecture-latest.md}"

if [[ ! -f "$BRIEFING" ]]; then
    echo "ERROR: Briefing not found: $BRIEFING" >&2
    exit 1
fi

echo "=== Architecture Briefing Rescan ==="
echo "Briefing: $BRIEFING"
echo ""

# Check for existing actions from this briefing (to skip duplicates)
BRIEFING_DATE="$(basename "$BRIEFING" .md | sed 's/architecture-//')"
EXISTING_ACTIONS="$ACTIONS_DIR/architecture-${BRIEFING_DATE}.json"
SKIP_IDS=""
if [[ -f "$EXISTING_ACTIONS" ]]; then
    SKIP_IDS="$(jq -r '.actions[].id' "$EXISTING_ACTIONS" 2>/dev/null | tr '\n' ', ')"
    echo "Existing actions found: $SKIP_IDS"
    echo "These will be skipped in extraction."
fi

# Count existing actions to set the starting index
NEXT_INDEX=1
if [[ -n "$SKIP_IDS" ]]; then
    NEXT_INDEX=$(( $(jq '.actions | length' "$EXISTING_ACTIONS") + 1 ))
fi

echo ""
echo "[1/3] Extracting actions from briefing via CC..."

# Build the skip instruction
SKIP_INSTRUCTION=""
if [[ -n "$SKIP_IDS" ]]; then
    SKIP_INSTRUCTION="Skip anything already covered by these existing action IDs (already routed): ${SKIP_IDS}"
fi

# Unset CLAUDECODE to allow nested launch
unset CLAUDECODE

PROMPT_FILE="/tmp/architecture-rescan-prompt.txt"
cat > "$PROMPT_FILE" <<PROMPT
Read this architecture briefing and extract ALL concrete mechanical fixes as proposed actions. Every finding that has a known, mechanical solution should become an action.

The briefing is at: ${BRIEFING}

Rules:
1. Only propose fixes where you can confirm the code exists by reading the actual source files. Verify before proposing.
2. ${SKIP_INSTRUCTION}
3. Use repo "btcopilot" or "familydiagram" — never "none"
4. Every spawn_prompt must be fully self-contained with file paths, exact code changes, and acceptance criteria
5. Use IDs starting at architecture-${BRIEFING_DATE}-${NEXT_INDEX}
6. Include: dead code removal, missing indexes, redundant operations, commented-out code, deprecated dependency fixes (when drop-in)
7. Exclude: large refactors, things requiring design decisions, speculative improvements

Output ONLY a \`\`\`proposed-actions JSON block, nothing else:

\`\`\`proposed-actions
{
  "actions": [
    {
      "id": "architecture-${BRIEFING_DATE}-N",
      "title": "Short imperative description",
      "category": "velocity|infrastructure|bugfix",
      "effort": "trivial|small",
      "confidence": 0.0-1.0,
      "repo": "btcopilot|familydiagram",
      "plan": "Step-by-step",
      "spawn_prompt": "Full self-contained prompt for Claude Code",
      "success_metric": "How we know it worked"
    }
  ]
}
\`\`\`
PROMPT

CC_JSON="$(cd "$THEAPP" && "$CLAUDE_BIN" -p \
    --model "$CLAUDE_MODEL" \
    --dangerously-skip-permissions \
    --max-turns 10 \
    --output-format json \
    < "$PROMPT_FILE" 2>&1)" || {
    echo "ERROR: CC extraction failed" >&2
    echo "$CC_JSON" >&2
    exit 1
}

CC_OUTPUT="$(echo "$CC_JSON" | jq -r '.result // empty')"
SESSION_ID="$(echo "$CC_JSON" | jq -r '.session_id // empty')"

if [[ -z "$CC_OUTPUT" ]]; then
    echo "ERROR: Empty CC output" >&2
    exit 1
fi

echo "CC returned $(echo "$CC_OUTPUT" | wc -c | tr -d ' ') chars"

# Extract the proposed-actions JSON — standalone script handles nested ``` in spawn_prompt strings
EXTRACTED_JSON="$(echo "$CC_OUTPUT" | python3 "$SCRIPT_DIR/extract-actions-json.py" 2>/dev/null || true)"

if [[ -z "$EXTRACTED_JSON" ]] || ! echo "$EXTRACTED_JSON" | jq -e '.actions' > /dev/null 2>&1; then
    echo "ERROR: No valid actions JSON extracted from CC output" >&2
    echo "Raw output:" >&2
    echo "$CC_OUTPUT" >&2
    exit 1
fi

ACTION_COUNT="$(echo "$EXTRACTED_JSON" | jq '.actions | length')"
echo "Extracted $ACTION_COUNT new actions"
echo ""

# If there are existing actions, merge
RESCAN_ACTIONS_FILE="$ACTIONS_DIR/architecture-${BRIEFING_DATE}-rescan.json"
echo "$EXTRACTED_JSON" > "$RESCAN_ACTIONS_FILE"

echo "Actions saved to: $RESCAN_ACTIONS_FILE"
echo ""

# Show what was found
echo "=== Extracted Actions ==="
echo "$EXTRACTED_JSON" | jq -r '.actions[] | "  [\(.id)] \(.title) (\(.effort), \(.repo))"'
echo ""

# Post a thread in #co-founder for this rescan
echo "[2/3] Posting to Discord..."
RESCAN_HEADER="🔄 **Architecture Rescan** | $(date '+%a %b %d, %H:%M %Z')
Re-scanned briefing from ${BRIEFING_DATE} with updated action criteria.
Found **${ACTION_COUNT}** additional mechanical fixes."

THREAD_ID="$("$SCRIPT_DIR/discord-post.sh" "$RESCAN_HEADER")"
if [[ -n "$THREAD_ID" ]]; then
    echo "Thread created: $THREAD_ID"
fi

# Commit
(
    cd "$HOME/.openclaw"
    git add "co-founder/actions/$(basename "$RESCAN_ACTIONS_FILE")" 2>/dev/null || true
    git commit -m "co-founder: architecture rescan actions ${BRIEFING_DATE}" --no-gpg-sign 2>/dev/null || true
    git -c "credential.helper=!gh auth git-credential" push 2>/dev/null || true
)

# Route actions (this creates issues, posts to #quick-wins, auto-spawns, and notifies thread)
echo ""
echo "[3/3] Routing actions (auto-spawn for architecture)..."
"$SCRIPT_DIR/action-router.sh" "$RESCAN_ACTIONS_FILE" "${THREAD_ID:-}"

echo ""
echo "=== Done ==="
echo "Actions file: $RESCAN_ACTIONS_FILE"
echo "Check #co-founder and #quick-wins in Discord for results."

# Cleanup
rm -f "$PROMPT_FILE"
