#!/usr/bin/env bash
# Co-Founder System — Configuration
# All paths, settings, and credentials in one place.

# Ensure Homebrew tools (gh, jq, etc.) are on PATH for nohup/cron contexts
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"

# GitHub auth — use patrickkidd-hurin bot account for all gh commands
export GH_TOKEN="$(cat "$HOME/.openclaw/monitor/hurin-bot-token" 2>/dev/null)"

# Paths
COFOUNDER_DIR="$HOME/.openclaw/co-founder"
LENSES_DIR="$COFOUNDER_DIR/lenses"
JOURNAL="$COFOUNDER_DIR/journal.md"
THEAPP="$HOME/.openclaw/workspace-hurin/theapp"
CLAUDE_BIN="$HOME/.local/bin/claude"

# Journal settings
JOURNAL_MAX_LINES=1000
JOURNAL_CONTEXT_LINES=100

# Depth settings
MAX_TURNS=10

# Briefings & sessions (persistent output, session resumption)
BRIEFINGS_DIR="$COFOUNDER_DIR/briefings"
SESSIONS_DIR="$COFOUNDER_DIR/sessions"

# Discord
DISCORD_BOT_TOKEN="REDACTED_DISCORD_TOKEN_OLD"
DISCORD_GUILD_ID="1474833522710548490"
DISCORD_CHANNEL_ID="1476739270663213197"
DISCORD_QUICKWINS_CHANNEL_ID="1476950473893482587"

# Action system
ACTIONS_DIR="$COFOUNDER_DIR/actions"

# WordPress (alaskafamilysystems.com)
WP_SITE_URL="https://alaskafamilysystems.com"
WP_USER="patrick@vedanamedia.com"
WP_APP_PASSWORD="REDACTED_WP_PASSWORD"

# Claude settings
CLAUDE_MODEL="claude-opus-4-6"

# Prompt assembly
PROMPT_TMPFILE="/tmp/co-founder-prompt.txt"

# Project file pointers for lens prompts
PROJECT_FILES=(
    "$THEAPP/TODO.md"
    "$THEAPP/CLAUDE.md"
    "$THEAPP/btcopilot/decisions/log.md"
    "$HOME/.openclaw/adrs/ADR-0001-agent-swarm.md"
    "$HOME/.openclaw/adrs/ADR-0001-status.md"
)
