#!/usr/bin/env bash
set -euo pipefail

# Discord posting with message splitting
# Usage: discord-post.sh "message text"
# Splits on paragraph boundaries at ~1900 chars to stay under Discord's 2000-char limit.
# Falls back to line-level splitting for long paragraphs.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

MESSAGE="${1:?Usage: discord-post.sh \"message\"}"
MAX_LEN=1900
API_URL="https://discord.com/api/v10/channels/${DISCORD_CHANNEL_ID}/messages"

post_chunk() {
    local chunk="$1"
    [[ -z "$chunk" ]] && return 0

    # Hard truncate as last resort (should never hit this)
    if [[ ${#chunk} -gt 2000 ]]; then
        chunk="${chunk:0:1997}..."
    fi

    local response
    response="$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
        -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$(jq -n --arg content "$chunk" '{content: $content}')")"

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
    local chunk=""
    local line

    while IFS= read -r line; do
        # If adding this line would exceed limit, post current chunk
        if [[ -n "$chunk" ]] && [[ $(( ${#chunk} + ${#line} + 1 )) -gt $MAX_LEN ]]; then
            post_chunk "$chunk"
            chunk=""
        fi

        if [[ -n "$chunk" ]]; then
            chunk="${chunk}
${line}"
        else
            chunk="$line"
        fi
    done <<< "$msg"

    # Post remaining chunk
    if [[ -n "$chunk" ]]; then
        post_chunk "$chunk"
    fi
}

# Always use split_and_post for consistency
split_and_post "$MESSAGE"
