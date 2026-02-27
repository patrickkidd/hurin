#!/usr/bin/env bash
# Co-Founder System — Configuration
# All paths, settings, and credentials in one place.

# Paths
COFOUNDER_DIR="$HOME/.openclaw/co-founder"
LENSES_DIR="$COFOUNDER_DIR/lenses"
JOURNAL="$COFOUNDER_DIR/journal.md"
THEAPP="$HOME/Projects/theapp"
CLAUDE_BIN="$HOME/.local/bin/claude"

# Journal settings
JOURNAL_MAX_LINES=1000
JOURNAL_CONTEXT_LINES=150

# Discord
DISCORD_BOT_TOKEN="MTQ3NDgzNDg0NTczNjg5NDYyNA.G9KNE_.CDsRXvfYJtB4zG_SLjbhmAqVcl3-Cx1aBeK64U"
DISCORD_GUILD_ID="1474833522710548490"
DISCORD_CHANNEL_ID="1476739270663213197"

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
