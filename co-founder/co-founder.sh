#!/usr/bin/env bash
set -euo pipefail

# Co-Founder System — Main Runner
# Usage: co-founder.sh <lens-name>
# Example: co-founder.sh project-pulse
#
# Runs Claude Code in agentic mode (multi-turn) for deep strategic analysis.
# Saves full output to briefings/, session ID for resumption, journal for continuity.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

LENS="${1:?Usage: co-founder.sh <lens-name>}"
LENS_FILE="$LENSES_DIR/$LENS.md"

if [[ ! -f "$LENS_FILE" ]]; then
    echo "ERROR: Lens not found: $LENS_FILE" >&2
    echo "Available lenses:" >&2
    ls "$LENSES_DIR"/*.md 2>/dev/null | xargs -I{} basename {} .md >&2
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M')] Running co-founder lens: $LENS"

# Ensure directories exist
mkdir -p "$BRIEFINGS_DIR" "$SESSIONS_DIR"

# 1. Read lens prompt
LENS_PROMPT="$(cat "$LENS_FILE")"

# 2. Read journal context (last N lines)
JOURNAL_CONTEXT=""
if [[ -f "$JOURNAL" ]]; then
    JOURNAL_CONTEXT="$(tail -n "$JOURNAL_CONTEXT_LINES" "$JOURNAL")"
fi

# 3. Assemble full prompt
cat > "$PROMPT_TMPFILE" <<PROMPT_EOF
$LENS_PROMPT

---

## Your Previous Journal Entries (last ${JOURNAL_CONTEXT_LINES} lines)

Use these to build continuity — reference your own past observations, track how things evolve, and avoid repeating yourself.

$JOURNAL_CONTEXT

---

## Key Project Locations

Read these files for current project state:
- TODO/roadmap: $THEAPP/TODO.md
- Project instructions: $THEAPP/CLAUDE.md
- Decision log: $THEAPP/btcopilot/decisions/log.md
- Agent architecture: $HOME/.openclaw/adrs/ADR-0001-agent-swarm.md
- Architecture status: $HOME/.openclaw/adrs/ADR-0001-status.md
- FamilyDiagram app: $THEAPP/familydiagram/
- BTCoPilot backend: $THEAPP/btcopilot/
- Pro app: $THEAPP/btcopilot-sources/

## Analysis Approach

You have **${MAX_TURNS} turns** available. Use them. Do not rush to produce output on the first turn.

**Suggested workflow:**
1. **Turn 1-3: Gather data.** Read project files, run shell commands (git log, gh pr list, find, wc -l, grep, etc.), explore the codebase. Collect concrete evidence.
2. **Turn 4-6: Dig deeper.** Investigate specific areas that warrant attention. Read source files, check test coverage, analyze patterns. Follow threads that surprise you.
3. **Turn 7+: Synthesize.** Write your briefing with specific citations — file paths, line numbers, PR numbers, commit hashes, concrete metrics.

**Do NOT constrain your output length.** A 2000-word briefing with concrete evidence is better than a 500-word summary of vibes. Write as much as the analysis warrants. Be specific and cite your sources.

## Output Format

Format your response for readability:
- Use **bold** for section labels
- Use bullet points (- ) for items
- Do NOT use markdown # headers
- End with one uncomfortable question for Patrick

## Quick Wins

If your analysis surfaces anything that meets ALL of these criteria, propose it as an action:

1. **Claude Code can fully implement it end-to-end** — no human judgment calls, no design decisions, no ambiguous scope
2. **It delivers clear, concrete value** — fixes a real bug, removes dead code that causes confusion, adds a missing index that prevents a production issue, removes redundant operations, unblocks a stuck PR, or creates content that drives traffic/signups
3. **The effort is genuinely trivial/small** — a focused CC session can ship it in one PR
4. **You are highly confident it's correct** — you've read the relevant code and understand the change

**Be thorough.** Every concrete finding in your briefing that has a clear mechanical fix should become an action. If you describe a problem with a known solution (dead code, missing index, redundant call, deprecated dependency with a drop-in replacement), propose it. Propose every action that genuinely clears this bar — whether that's zero or ten.

**Not quick wins:** speculative improvements, large-scale refactors requiring design decisions, test additions without a concrete bug, things requiring Patrick's product judgment, anything where you're unsure about the approach, "nice to have" architectural changes.

If something genuinely qualifies, add a \`\`\`proposed-actions code block at the very end:

\`\`\`
\`\`\`proposed-actions
{
  "actions": [
    {
      "id": "${LENS}-$(date '+%Y-%m-%d')-<n>",
      "title": "Short imperative description",
      "category": "revenue|ux|velocity|bugfix|content|infrastructure",
      "effort": "trivial|small",
      "confidence": 0.0-1.0,
      "repo": "btcopilot|familydiagram|website|none",
      "plan": "Step-by-step implementation plan",
      "spawn_prompt": "Full self-contained prompt for Claude Code — include file paths, context, acceptance criteria",
      "success_metric": "How we know this worked"
    }
  ]
}
\`\`\`
\`\`\`

Every action requires Patrick's approval before spawning. There is no auto-spawn tier.

**spawn_prompt quality bar:** It must be a complete, self-contained prompt that another CC instance could execute cold — specific files, specific changes, specific acceptance criteria. If you can't write a crisp spawn_prompt, the action isn't ready.
PROMPT_EOF

# 4. Run Claude Code (agentic, multi-turn)
# Unset CLAUDECODE to allow launching from within another CC session (e.g. /cofounder skill)
unset CLAUDECODE
echo "[$(date '+%Y-%m-%d %H:%M')] Calling Claude Code (max $MAX_TURNS turns)..."
CC_JSON="$(cd "$THEAPP" && "$CLAUDE_BIN" -p \
    --model "$CLAUDE_MODEL" \
    --dangerously-skip-permissions \
    --max-turns "$MAX_TURNS" \
    --output-format json \
    < "$PROMPT_TMPFILE" 2>&1)" || {
    echo "ERROR: Claude Code failed for lens $LENS" >&2
    echo "Output: $CC_JSON" >&2
    exit 1
}

# 5. Parse JSON output
CC_OUTPUT="$(echo "$CC_JSON" | jq -r '.result // empty')"
SESSION_ID="$(echo "$CC_JSON" | jq -r '.session_id // empty')"

# If result is empty but we have a session (e.g. error_max_turns — CC used all turns on tool calls),
# resume the session to get the final briefing text.
if [[ -z "$CC_OUTPUT" ]] && [[ -n "$SESSION_ID" ]]; then
    CC_SUBTYPE="$(echo "$CC_JSON" | jq -r '.subtype // "unknown"')"
    echo "[$(date '+%Y-%m-%d %H:%M')] No result text (subtype: $CC_SUBTYPE), resuming session for output..."
    CC_OUTPUT="$(cd "$THEAPP" && "$CLAUDE_BIN" -p \
        --model "$CLAUDE_MODEL" \
        --dangerously-skip-permissions \
        --max-turns 1 \
        --resume "$SESSION_ID" \
        <<< "Please write your complete briefing now based on everything you've gathered." 2>/dev/null)" || true
fi

if [[ -z "$CC_OUTPUT" ]]; then
    echo "ERROR: Empty response from Claude Code" >&2
    echo "JSON keys: $(echo "$CC_JSON" | jq -r 'keys | join(", ")' 2>/dev/null)" >&2
    echo "Subtype: $(echo "$CC_JSON" | jq -r '.subtype // "unknown"' 2>/dev/null)" >&2
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M')] CC returned $(echo "$CC_OUTPUT" | wc -c | tr -d ' ') chars"

# 6. Save session ID for follow-up resumption
if [[ -n "$SESSION_ID" ]]; then
    echo "$SESSION_ID" > "$SESSIONS_DIR/${LENS}-session.txt"
    echo "[$(date '+%Y-%m-%d %H:%M')] Session saved: $SESSION_ID"
fi

# 7. Save full briefing to file
BRIEFING_DATE="$(date '+%Y-%m-%d')"
BRIEFING_FILE="$BRIEFINGS_DIR/${LENS}-${BRIEFING_DATE}.md"
{
    echo "# Co-Founder Briefing: $LENS"
    echo "**Date:** $(date '+%Y-%m-%d %H:%M %Z')"
    echo "**Session:** ${SESSION_ID:-unknown}"
    echo "**Turns:** $MAX_TURNS max"
    echo ""
    echo "---"
    echo ""
    echo "$CC_OUTPUT"
} > "$BRIEFING_FILE"

# Update latest symlink
ln -sf "${LENS}-${BRIEFING_DATE}.md" "$BRIEFINGS_DIR/${LENS}-latest.md"
echo "[$(date '+%Y-%m-%d %H:%M')] Briefing saved: $BRIEFING_FILE"

# 7b. Commit and push briefing to git
(
    cd "$HOME/.openclaw"
    git add "co-founder/briefings/${LENS}-${BRIEFING_DATE}.md"
    git commit -m "co-founder: ${LENS} briefing ${BRIEFING_DATE}" --no-gpg-sign 2>/dev/null || true
    git -c "credential.helper=!gh auth git-credential" push 2>/dev/null || {
        echo "[$(date '+%Y-%m-%d %H:%M')] WARNING: git push failed for briefing" >&2
    }
    echo "[$(date '+%Y-%m-%d %H:%M')] Briefing committed and pushed"
)

# 7c. Extract actions JSON and strip from output
ACTIONS_DATE="$(date '+%Y-%m-%d')"
ACTIONS_JSON_FILE="$ACTIONS_DIR/${LENS}-${ACTIONS_DATE}.json"
mkdir -p "$ACTIONS_DIR"

# Extract JSON from code fence — standalone script handles nested ``` in spawn_prompt strings
EXTRACTED_JSON="$(echo "$CC_OUTPUT" | python3 "$SCRIPT_DIR/extract-actions-json.py" 2>/dev/null || true)"

# Strip the actions JSON block from CC_OUTPUT for clean Discord/journal posting
CC_OUTPUT_CLEAN="$CC_OUTPUT"
if [[ -n "$EXTRACTED_JSON" ]]; then
    CC_OUTPUT_CLEAN="$(echo "$CC_OUTPUT" | perl -0777 -pe 's/\n*```(?:proposed-actions|json)\s*\n\s*\{[^`]*"actions"[^`]*\}\s*\n```\s*//gs' 2>/dev/null || echo "$CC_OUTPUT")"
fi

HAS_ACTIONS=false
if [[ -n "$EXTRACTED_JSON" ]] && echo "$EXTRACTED_JSON" | jq -e '.actions' > /dev/null 2>&1; then
    echo "$EXTRACTED_JSON" > "$ACTIONS_JSON_FILE"
    ACTION_COUNT="$(jq '.actions | length' "$ACTIONS_JSON_FILE")"
    echo "[$(date '+%Y-%m-%d %H:%M')] Extracted $ACTION_COUNT actions to $ACTIONS_JSON_FILE"
    HAS_ACTIONS=true

    # Commit actions file
    (
        cd "$HOME/.openclaw"
        git add "co-founder/actions/${LENS}-${ACTIONS_DATE}.json" 2>/dev/null || true
        git commit -m "co-founder: ${LENS} actions ${ACTIONS_DATE}" --no-gpg-sign 2>/dev/null || true
        git -c "credential.helper=!gh auth git-credential" push 2>/dev/null || true
    )
elif [[ -n "$EXTRACTED_JSON" ]]; then
    echo "$EXTRACTED_JSON" > "${ACTIONS_JSON_FILE}.malformed"
    echo "[$(date '+%Y-%m-%d %H:%M')] WARNING: Malformed actions JSON saved to ${ACTIONS_JSON_FILE}.malformed" >&2
else
    echo "[$(date '+%Y-%m-%d %H:%M')] No actions proposed (normal — most briefings shouldn't have any)"
fi

# 8. Append to journal (clean output, no JSON block)
{
    echo ""
    echo "## [$LENS] $(date '+%Y-%m-%d %H:%M %Z')"
    echo ""
    echo "$CC_OUTPUT_CLEAN"
    echo ""
    echo "---"
} >> "$JOURNAL"

# 9. Trim journal to max lines
CURRENT_LINES="$(wc -l < "$JOURNAL")"
if [[ "$CURRENT_LINES" -gt "$JOURNAL_MAX_LINES" ]]; then
    TRIM_COUNT=$((CURRENT_LINES - JOURNAL_MAX_LINES))
    tail -n +"$((TRIM_COUNT + 1))" "$JOURNAL" > "${JOURNAL}.tmp"
    mv "${JOURNAL}.tmp" "$JOURNAL"
    echo "[$(date '+%Y-%m-%d %H:%M')] Trimmed journal by $TRIM_COUNT lines"
fi

# 10. Post to Discord — creates a thread, outputs thread ID
DISCORD_HEADER="🧠 **Co-Founder — ${LENS}** | $(date '+%a %b %d, %H:%M %Z')"
DISCORD_FOOTER="💬 Follow up: \`/cofounder followup ${LENS} <your question>\`"

DISCORD_MESSAGE="${DISCORD_HEADER}

${CC_OUTPUT_CLEAN}

${DISCORD_FOOTER}"

THREAD_ID="$("$SCRIPT_DIR/discord-post.sh" "$DISCORD_MESSAGE" "$BRIEFING_FILE")"
if [[ -n "$THREAD_ID" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M')] Discord thread created: $THREAD_ID"
fi

# 11. Route actions (after Discord post so we have the thread ID)
if [[ "$HAS_ACTIONS" == "true" ]]; then
    nohup "$SCRIPT_DIR/action-router.sh" "$ACTIONS_JSON_FILE" "${THREAD_ID:-}" >> "$COFOUNDER_DIR/actions.log" 2>&1 &
    echo "[$(date '+%Y-%m-%d %H:%M')] Action router launched in background (PID: $!)"
fi

echo "[$(date '+%Y-%m-%d %H:%M')] Done: $LENS"
