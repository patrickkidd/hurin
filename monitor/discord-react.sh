#!/bin/bash
# discord-react.sh - Add or remove a reaction on a Discord message.
#
# Usage:
#   discord-react.sh add <channel_id> <message_id> [emoji]
#   discord-react.sh remove <channel_id> <message_id> [emoji]
#
# Default emoji: 🧠 (brain)
# The bot token is read from openclaw.json.

set -euo pipefail

ACTION="${1:-}"
CHANNEL="${2:-}"
MSG_ID="${3:-}"
EMOJI="${4:-🧠}"

if [[ -z "$ACTION" || -z "$CHANNEL" || -z "$MSG_ID" ]]; then
    echo "Usage: discord-react.sh <add|remove> <channel_id> <message_id> [emoji]" >&2
    exit 1
fi

TOKEN=$(python3 -c "
import json
with open('$HOME/.openclaw/openclaw.json') as f:
    c = json.load(f)
print(c['channels']['discord']['accounts']['hurin']['token'])
")

# URL-encode the emoji
ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$EMOJI'))")

case "$ACTION" in
    add)
        curl -s -o /dev/null -w "" -X PUT \
            -H "Authorization: Bot $TOKEN" \
            "https://discord.com/api/v10/channels/$CHANNEL/messages/$MSG_ID/reactions/$ENCODED/@me"
        ;;
    remove)
        curl -s -o /dev/null -w "" -X DELETE \
            -H "Authorization: Bot $TOKEN" \
            "https://discord.com/api/v10/channels/$CHANNEL/messages/$MSG_ID/reactions/$ENCODED/@me"
        ;;
    *)
        echo "Unknown action: $ACTION (use add or remove)" >&2
        exit 1
        ;;
esac
