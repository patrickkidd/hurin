#!/usr/bin/env bash
set -euo pipefail

# The Seed — Weekly Retrospective Runner
# Analyzes task outcomes and proposes system improvements as PRs.
# Cron: 0 20 * * 0 (11:00 AM AKST Sunday)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$HOME/.openclaw/co-founder/config.sh"

FEEDBACK_LOG="$HOME/.openclaw/workspace-hurin/feedback/log.jsonl"
PROMPT_FILE="$SCRIPT_DIR/retrospective-prompt.md"
RETRO_LOG="$SCRIPT_DIR/retro.log"

echo "[$(date '+%Y-%m-%d %H:%M')] Starting weekly retrospective"

# Guard: need feedback data
if [[ ! -s "$FEEDBACK_LOG" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M')] No feedback data yet — skipping retrospective"
    exit 0
fi

OUTCOME_COUNT="$(wc -l < "$FEEDBACK_LOG" | tr -d ' ')"
echo "[$(date '+%Y-%m-%d %H:%M')] Feedback log has $OUTCOME_COUNT outcomes"

# Assemble prompt
PROMPT="$(cat "$PROMPT_FILE")

---

## Data File Paths

- Feedback log: $FEEDBACK_LOG
- Trust tiers: $HOME/.openclaw/workspace-hurin/feedback/trust.yaml
- Prompt patterns: $HOME/.openclaw/workspace-hurin/memory/prompt-patterns.md
- System CLAUDE.md: $HOME/.openclaw/CLAUDE.md

Read these files to begin your analysis."

# Run Claude Code — working dir is ~/.openclaw (the hurin config repo)
unset CLAUDECODE
echo "[$(date '+%Y-%m-%d %H:%M')] Calling Claude Code (max 10 turns)..."
CC_OUTPUT="$(cd "$HOME/.openclaw" && "$CLAUDE_BIN" -p \
    --model "$CLAUDE_MODEL" \
    --dangerously-skip-permissions \
    --max-turns 10 \
    <<< "$PROMPT" 2>&1)" || {
    echo "[$(date '+%Y-%m-%d %H:%M')] ERROR: Claude Code failed" >&2
    echo "Output: $CC_OUTPUT" >&2
    exit 1
}

echo "[$(date '+%Y-%m-%d %H:%M')] CC returned $(echo "$CC_OUTPUT" | wc -c | tr -d ' ') chars"

# Post summary to Discord #co-founder
DISCORD_MESSAGE="🔄 **The Seed — Weekly Retrospective** | $(date '+%a %b %d, %H:%M %Z')

${CC_OUTPUT}"

"$HOME/.openclaw/co-founder/discord-post.sh" "$DISCORD_MESSAGE" || {
    echo "[$(date '+%Y-%m-%d %H:%M')] WARNING: Discord post failed" >&2
}

echo "[$(date '+%Y-%m-%d %H:%M')] Retrospective complete"
