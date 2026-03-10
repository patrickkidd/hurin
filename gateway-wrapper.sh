#!/usr/bin/env bash
# Loads secrets from secrets.json and exports as env vars before launching openclaw gateway.
# This is the canonical method — secrets.json is the single source of truth.

SECRETS_FILE="$HOME/.openclaw/secrets.json"

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "FATAL: $SECRETS_FILE not found" >&2
  exit 1
fi

# Discord bot tokens — three agents
export HUOR_DISCORD_BOT_TOKEN=$(python3 -c "import json,sys; print(json.load(open('$SECRETS_FILE'))['huor-discord-bot-token'])")
export TUOR_DISCORD_BOT_TOKEN=$(python3 -c "import json,sys; print(json.load(open('$SECRETS_FILE'))['tuor-discord-bot-token'])")
export BEREN_DISCORD_BOT_TOKEN=$(python3 -c "import json,sys; print(json.load(open('$SECRETS_FILE'))['beren-discord-bot-token'])")

# Legacy — kept for backward compatibility (task-daemon, discord_relay, etc.)
export DISCORD_BOT_TOKEN=$(python3 -c "import json,sys; print(json.load(open('$SECRETS_FILE'))['discord-bot-token'])")

# Gateway and API keys
export GATEWAY_AUTH_TOKEN=$(python3 -c "import json,sys; print(json.load(open('$SECRETS_FILE'))['gateway-auth-token'])")
export ANTHROPIC_API_KEY=$(python3 -c "import json,sys; print(json.load(open('$SECRETS_FILE'))['anthropic-api-key'])")
export MINIMAX_API_KEY=$(python3 -c "import json,sys; print(json.load(open('$SECRETS_FILE'))['minimax-api-key'])")

exec openclaw gateway "$@"
