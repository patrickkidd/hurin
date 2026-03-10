# HEARTBEAT.md

# Check for new PR review comments from bots (Gemini, Claude, etc.)
~/.openclaw/workspace-hurin/scripts/check-pr-reviews.sh

# Ops health checks (cheap checks first — script handles detection + auto-restart)
- Run `~/.openclaw/workspace-hurin/scripts/ops-heartbeat.sh`
- If output starts with HEARTBEAT_ALERT, post the alert to #team-lead
- If output is HEARTBEAT_OK, do nothing
