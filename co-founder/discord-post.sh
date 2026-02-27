#!/usr/bin/env bash
set -euo pipefail

# Discord posting with message splitting and optional file attachment
# Usage: discord-post.sh "message text" [/path/to/attachment.md]
# Splits on line boundaries at ~1900 chars to stay under Discord's 2000-char limit.
# If a file path is provided, attaches it to the final message.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

MESSAGE="${1:?Usage: discord-post.sh \"message\" [attachment_path]}"
ATTACHMENT="${2:-}"
MAX_LEN=1900
API_URL="https://discord.com/api/v10/channels/${DISCORD_CHANNEL_ID}/messages"

post_chunk() {
    local chunk="$1"
    local attach_file="${2:-}"
    [[ -z "$chunk" ]] && return 0

    # Hard truncate as last resort (should never hit this)
    if [[ ${#chunk} -gt 2000 ]]; then
        chunk="${chunk:0:1997}..."
    fi

    local response
    if [[ -n "$attach_file" ]] && [[ -f "$attach_file" ]]; then
        # Post with file attachment (multipart form)
        response="$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
            -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
            -F "payload_json=$(jq -n --arg content "$chunk" '{content: $content}')" \
            -F "files[0]=@${attach_file}")"
    else
        # Post text only
        response="$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
            -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$(jq -n --arg content "$chunk" '{content: $content}')")"
    fi

    local http_code
    http_code="$(echo "$response" | tail -1)"
    local body
    body="$(echo "$response" | sed '$d')"

    if [[ "$http_code" -ge 400 ]]; then
        echo "ERROR: Discord API returned $http_code" >&2
        echo "$body" >&2
        return 1
    fi

    sleep 1
}

# Split message and post in chunks
split_and_post() {
    local msg="$1"
    local chunks=()
    local chunk=""
    local line

    # Collect all chunks first
    while IFS= read -r line; do
        if [[ -n "$chunk" ]] && [[ $(( ${#chunk} + ${#line} + 1 )) -gt $MAX_LEN ]]; then
            chunks+=("$chunk")
            chunk=""
        fi

        if [[ -n "$chunk" ]]; then
            chunk="${chunk}
${line}"
        else
            chunk="$line"
        fi
    done <<< "$msg"

    if [[ -n "$chunk" ]]; then
        chunks+=("$chunk")
    fi

    # Post all chunks; attach file to the last one
    local total=${#chunks[@]}
    for i in "${!chunks[@]}"; do
        if [[ $((i + 1)) -eq $total ]] && [[ -n "$ATTACHMENT" ]]; then
            post_chunk "${chunks[$i]}" "$ATTACHMENT"
        else
            post_chunk "${chunks[$i]}"
        fi
    done
}

split_and_post "$MESSAGE"
