#!/usr/bin/env bash
# Loads secrets from secrets.json and exports as env vars before launching openclaw gateway.
# This is the canonical method — secrets.json is the single source of truth.

SECRETS_FILE="$HOME/.openclaw/secrets.json"

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "FATAL: $SECRETS_FILE not found" >&2
  exit 1
fi

export DISCORD_BOT_TOKEN=$(python3 -c "import json,sys; print(json.load(open('$SECRETS_FILE'))['discord-bot-token'])")
export GATEWAY_AUTH_TOKEN=$(python3 -c "import json,sys; print(json.load(open('$SECRETS_FILE'))['gateway-auth-token'])")
export ANTHROPIC_API_KEY=$(python3 -c "import json,sys; print(json.load(open('$SECRETS_FILE'))['anthropic-api-key'])")
export MINIMAX_API_KEY=$(python3 -c "import json,sys; print(json.load(open('$SECRETS_FILE'))['minimax-api-key'])")

exec openclaw gateway "$@"
