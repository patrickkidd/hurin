#!/usr/bin/env bash
set -euo pipefail

# Discord posting with threading and message splitting
# Usage: discord-post.sh "message text" [/path/to/attachment.md]
#
# Posts the first chunk as a message in #co-founder, creates a thread on it,
# then posts remaining chunks and attachment inside the thread.
# Outputs the thread ID to stdout (for use by action-router.sh).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

MESSAGE="${1:?Usage: discord-post.sh \"message\" [attachment_path]}"
ATTACHMENT="${2:-}"
MAX_LEN=1900
API_BASE="https://discord.com/api/v10"
CHANNEL_API="$API_BASE/channels/${DISCORD_CHANNEL_ID}/messages"

# Post a message, return the response body (JSON)
post_message() {
    local url="$1"
    local chunk="$2"
    local attach_file="${3:-}"
    [[ -z "$chunk" ]] && return 0

    if [[ ${#chunk} -gt 2000 ]]; then
        chunk="${chunk:0:1997}..."
    fi

    local response
    if [[ -n "$attach_file" ]] && [[ -f "$attach_file" ]]; then
        response="$(curl -s -w "\n%{http_code}" -X POST "$url" \
            -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
            -F "payload_json=$(jq -n --arg content "$chunk" '{content: $content}')" \
            -F "files[0]=@${attach_file}")"
    else
        response="$(curl -s -w "\n%{http_code}" -X POST "$url" \
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

    echo "$body"
    sleep 1
}

# Create a thread on a message, return the thread channel ID
create_thread() {
    local channel_id="$1"
    local message_id="$2"
    local thread_name="$3"

    # Truncate thread name to 100 chars (Discord limit)
    if [[ ${#thread_name} -gt 100 ]]; then
        thread_name="${thread_name:0:97}..."
    fi

    local response
    response="$(curl -s -w "\n%{http_code}" -X POST \
        "$API_BASE/channels/${channel_id}/messages/${message_id}/threads" \
        -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$(jq -n --arg name "$thread_name" '{name: $name}')")"

    local http_code
    http_code="$(echo "$response" | tail -1)"
    local body
    body="$(echo "$response" | sed '$d')"

    if [[ "$http_code" -ge 400 ]]; then
        echo "ERROR: Thread creation failed ($http_code)" >&2
        echo "$body" >&2
        return 1
    fi

    echo "$body" | jq -r '.id'
}

# Split message into chunks on line boundaries
split_message() {
    local msg="$1"
    local chunk=""
    local line

    CHUNKS=()
    while IFS= read -r line; do
        if [[ -n "$chunk" ]] && [[ $(( ${#chunk} + ${#line} + 1 )) -gt $MAX_LEN ]]; then
            CHUNKS+=("$chunk")
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
        CHUNKS+=("$chunk")
    fi
}

# --- Main flow ---

split_message "$MESSAGE"
TOTAL=${#CHUNKS[@]}

if [[ $TOTAL -eq 0 ]]; then
    echo "ERROR: Empty message" >&2
    exit 1
fi

# 1. Post the first chunk as a regular message in #co-founder
FIRST_RESPONSE="$(post_message "$CHANNEL_API" "${CHUNKS[0]}")"
FIRST_MSG_ID="$(echo "$FIRST_RESPONSE" | jq -r '.id')"

if [[ -z "$FIRST_MSG_ID" || "$FIRST_MSG_ID" == "null" ]]; then
    echo "ERROR: Failed to get message ID from first post" >&2
    exit 1
fi

THREAD_ID=""

# 2. If there are more chunks, create a thread and post the rest there
if [[ $TOTAL -gt 1 ]]; then
    # Extract lens name from the header line for thread name
    THREAD_NAME="$(echo "${CHUNKS[0]}" | head -1 | sed 's/🧠 //' | head -c 100)"
    THREAD_ID="$(create_thread "$DISCORD_CHANNEL_ID" "$FIRST_MSG_ID" "$THREAD_NAME")"

    if [[ -z "$THREAD_ID" || "$THREAD_ID" == "null" ]]; then
        echo "WARNING: Thread creation failed, falling back to flat posting" >&2
        # Fallback: post remaining chunks flat
        for i in $(seq 1 $((TOTAL - 1))); do
            if [[ $((i + 1)) -eq $TOTAL ]] && [[ -n "$ATTACHMENT" ]]; then
                post_message "$CHANNEL_API" "${CHUNKS[$i]}" "$ATTACHMENT" > /dev/null
            else
                post_message "$CHANNEL_API" "${CHUNKS[$i]}" > /dev/null
            fi
        done
    else
        THREAD_API="$API_BASE/channels/${THREAD_ID}/messages"
        for i in $(seq 1 $((TOTAL - 1))); do
            if [[ $((i + 1)) -eq $TOTAL ]] && [[ -n "$ATTACHMENT" ]]; then
                post_message "$THREAD_API" "${CHUNKS[$i]}" "$ATTACHMENT" > /dev/null
            else
                post_message "$THREAD_API" "${CHUNKS[$i]}" > /dev/null
            fi
        done
    fi
elif [[ -n "$ATTACHMENT" ]]; then
    # Single chunk with attachment — create thread for the attachment
    THREAD_NAME="$(echo "${CHUNKS[0]}" | head -1 | sed 's/🧠 //' | head -c 100)"
    THREAD_ID="$(create_thread "$DISCORD_CHANNEL_ID" "$FIRST_MSG_ID" "$THREAD_NAME")"

    if [[ -n "$THREAD_ID" && "$THREAD_ID" != "null" ]]; then
        THREAD_API="$API_BASE/channels/${THREAD_ID}/messages"
        post_message "$THREAD_API" "📎 Full briefing attached" "$ATTACHMENT" > /dev/null
    fi
fi

# Output thread ID for downstream use (action-router.sh)
if [[ -n "$THREAD_ID" && "$THREAD_ID" != "null" ]]; then
    echo "$THREAD_ID"
fi
