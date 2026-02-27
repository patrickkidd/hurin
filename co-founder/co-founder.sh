#!/usr/bin/env bash
set -euo pipefail

# Co-Founder System — Main Runner
# Usage: co-founder.sh <lens-name>
# Example: co-founder.sh project-pulse

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

LENS="${1:?Usage: co-founder.sh <lens-name>}"
LENS_FILE="$LENSES_DIR/$LENS.md"

if [[ ! -f "$LENS_FILE" ]]; then
    echo "ERROR: Lens not found: $LENS_FILE" >&2
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M')] Running co-founder lens: $LENS"

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

## Output Format

Format your response for Discord:
- Use **bold** for section labels
- Use bullet points (- ) for items
- Do NOT use # headers (Discord renders them poorly)
- Keep total response under 3500 characters
- End with one uncomfortable question for Patrick
PROMPT_EOF

# 4. Run Claude Code
echo "[$(date '+%Y-%m-%d %H:%M')] Calling Claude Code..."
CC_OUTPUT="$(cd "$THEAPP" && "$CLAUDE_BIN" -p --model "$CLAUDE_MODEL" --dangerously-skip-permissions < "$PROMPT_TMPFILE" 2>/dev/null)" || {
    echo "ERROR: Claude Code failed for lens $LENS" >&2
    exit 1
}

if [[ -z "$CC_OUTPUT" ]]; then
    echo "ERROR: Empty response from Claude Code" >&2
    exit 1
fi

# 5. Append to journal
{
    echo ""
    echo "## [$LENS] $(date '+%Y-%m-%d %H:%M %Z')"
    echo ""
    echo "$CC_OUTPUT"
    echo ""
    echo "---"
} >> "$JOURNAL"

# 6. Trim journal to max lines
CURRENT_LINES="$(wc -l < "$JOURNAL")"
if [[ "$CURRENT_LINES" -gt "$JOURNAL_MAX_LINES" ]]; then
    TRIM_COUNT=$((CURRENT_LINES - JOURNAL_MAX_LINES))
    tail -n +"$((TRIM_COUNT + 1))" "$JOURNAL" > "${JOURNAL}.tmp"
    mv "${JOURNAL}.tmp" "$JOURNAL"
    echo "[$(date '+%Y-%m-%d %H:%M')] Trimmed journal by $TRIM_COUNT lines"
fi

# 7. Post to Discord
DISCORD_HEADER="🧠 **Co-Founder — ${LENS}** | $(date '+%a %b %d, %H:%M %Z')"
DISCORD_MESSAGE="${DISCORD_HEADER}

${CC_OUTPUT}"

"$SCRIPT_DIR/discord-post.sh" "$DISCORD_MESSAGE"

echo "[$(date '+%Y-%m-%d %H:%M')] Done: $LENS"
