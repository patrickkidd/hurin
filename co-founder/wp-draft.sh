#!/usr/bin/env bash
set -euo pipefail

# Co-Founder Action System — WordPress Draft Creator
# ADR: ~/.openclaw/adrs/ADR-0005-action-system.md
#
# Creates draft posts/pages in WordPress via REST API.
# Drafts are invisible to visitors — same safety gate as PRs for code.
# Also saves markdown to website-content/ for git tracking.
#
# Usage: wp-draft.sh --title "Title" --content "Content" --type post|page [--categories "cat1,cat2"] [--tags "tag1,tag2"] [--action-id "id"]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

usage() {
    cat >&2 <<'EOF'
Usage: wp-draft.sh --title "Title" --content "Content" --type post|page [--categories "cat1,cat2"] [--tags "tag1,tag2"] [--action-id "id"]

Options:
  --title       Post/page title (required)
  --content     Content body — HTML or markdown (required)
  --type        "post" or "page" (required)
  --categories  Comma-separated category names (posts only)
  --tags        Comma-separated tag names (posts only)
  --action-id   Action ID for file tracking
EOF
    exit 1
}

TITLE=""
CONTENT=""
POST_TYPE=""
CATEGORIES=""
TAGS=""
ACTION_ID=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --title)      TITLE="$2";      shift 2 ;;
        --content)    CONTENT="$2";    shift 2 ;;
        --type)       POST_TYPE="$2";  shift 2 ;;
        --categories) CATEGORIES="$2"; shift 2 ;;
        --tags)       TAGS="$2";       shift 2 ;;
        --action-id)  ACTION_ID="$2";  shift 2 ;;
        -h|--help)    usage ;;
        *)            echo "Unknown option: $1" >&2; usage ;;
    esac
done

[[ -z "$TITLE" || -z "$CONTENT" || -z "$POST_TYPE" ]] && usage
[[ "$POST_TYPE" != "post" && "$POST_TYPE" != "page" ]] && {
    echo "ERROR: --type must be 'post' or 'page'" >&2; exit 1
}

# WordPress API endpoint
if [[ "$POST_TYPE" == "post" ]]; then
    WP_ENDPOINT="${WP_SITE_URL}/wp-json/wp/v2/posts"
else
    WP_ENDPOINT="${WP_SITE_URL}/wp-json/wp/v2/pages"
fi

# Basic Auth (base64 of user:app_password)
# WP_APP_PASSWORD has spaces that are cosmetic — strip them for auth
WP_APP_PASSWORD_CLEAN="$(echo "$WP_APP_PASSWORD" | tr -d ' ')"
AUTH_HEADER="$(echo -n "${WP_USER}:${WP_APP_PASSWORD_CLEAN}" | base64)"

echo "[$(date '+%Y-%m-%d %H:%M')] Creating WordPress draft: $TITLE ($POST_TYPE)"

# Check for duplicates first
EXISTING="$(curl -s "${WP_ENDPOINT}?search=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$TITLE'))")&status=draft" \
    -H "Authorization: Basic $AUTH_HEADER" 2>/dev/null || echo "[]")"

if echo "$EXISTING" | jq -e '.[0].id' > /dev/null 2>&1; then
    EXISTING_ID="$(echo "$EXISTING" | jq -r '.[0].id')"
    EXISTING_LINK="$(echo "$EXISTING" | jq -r '.[0].link')"
    echo "WARNING: Existing draft found with similar title (ID: $EXISTING_ID)" >&2
    echo "  Link: $EXISTING_LINK" >&2
    echo "  Creating new draft anyway (check for duplicates)" >&2
fi

# Build JSON payload
PAYLOAD="$(jq -n \
    --arg title "$TITLE" \
    --arg content "$CONTENT" \
    --arg status "draft" \
    '{title: $title, content: $content, status: $status}')"

# Create the draft
RESPONSE="$(curl -s -w "\n%{http_code}" -X POST "$WP_ENDPOINT" \
    -H "Authorization: Basic $AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")"

HTTP_CODE="$(echo "$RESPONSE" | tail -1)"
BODY="$(echo "$RESPONSE" | sed '$d')"

if [[ "$HTTP_CODE" -ge 400 ]]; then
    echo "ERROR: WordPress API returned $HTTP_CODE" >&2
    echo "$BODY" >&2
    exit 1
fi

# Extract draft info
DRAFT_ID="$(echo "$BODY" | jq -r '.id')"
DRAFT_LINK="$(echo "$BODY" | jq -r '.link')"
EDIT_URL="${WP_SITE_URL}/wp-admin/post.php?post=${DRAFT_ID}&action=edit"

echo "  Draft created: ID=$DRAFT_ID"
echo "  Edit URL: $EDIT_URL"
echo "  Preview: $DRAFT_LINK"

# Save markdown to website-content/ for git tracking
CONTENT_DIR="$COFOUNDER_DIR/website-content"
mkdir -p "$CONTENT_DIR"
FILE_ID="${ACTION_ID:-draft-$(date '+%Y%m%d-%H%M%S')}"
CONTENT_FILE="$CONTENT_DIR/${FILE_ID}.md"

cat > "$CONTENT_FILE" <<EOF
---
title: "$TITLE"
type: $POST_TYPE
wp_draft_id: $DRAFT_ID
edit_url: $EDIT_URL
created: $(date -u '+%Y-%m-%dT%H:%M:%SZ')
action_id: ${ACTION_ID:-none}
---

$CONTENT
EOF

echo "  Saved to: $CONTENT_FILE"

# Commit content file
(
    cd "$HOME/.openclaw"
    git add "co-founder/website-content/${FILE_ID}.md" 2>/dev/null || true
    git commit -m "co-founder: WordPress draft — $TITLE" --no-gpg-sign 2>/dev/null || true
    git -c "credential.helper=!gh auth git-credential" push 2>/dev/null || true
)

# Output the edit URL (for callers to use)
echo "$EDIT_URL"
