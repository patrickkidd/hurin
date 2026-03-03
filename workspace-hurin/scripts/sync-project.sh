#!/bin/bash
# sync-project.sh — Simple helper to sync a GitHub issue to the project board
#
# Usage:
#   sync-project.sh <repo> <issue-number> [--status <Todo|In Progress|Done>] [--owner <Patrick|Hurin|Beren|Tuor>]
#
# Examples:
#   sync-project.sh patrickkidd/familydiagram 156                    # Find item
#   sync-project.sh patrickkidd/familydiagram 156 --status Done      # Mark as Done
#   sync-project.sh patrickkidd/btcopilot 42 --owner Hurin --status "In Progress"

set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GH_FIND="$SCRIPTS_DIR/gh-project-find-item.sh"
GH_SYNC="$SCRIPTS_DIR/gh-project-sync.sh"

usage() {
    cat >&2 <<'USAGE'
Usage: sync-project.sh <repo> <issue-number> [--status <Todo|In Progress|Done>] [--owner <Patrick|Hurin|Beren|Tuor>]

Arguments:
  <repo>          GitHub repo (owner/name), e.g. patrickkidd/familydiagram
  <issue-number>  GitHub issue number

Options:
  --status <status>  Update status (Todo, In Progress, Done)
  --owner <owner>    Update owner (Patrick, Hurin, Beren, Tuor)

Examples:
  sync-project.sh patrickkidd/familydiagram 156
  sync-project.sh patrickkidd/familydiagram 156 --status Done
  sync-project.sh patrickkidd/btcopilot 42 --owner Hurin --status "In Progress"
USAGE
    exit 1
}

[[ $# -lt 2 ]] && usage

REPO="$1"
ISSUE_NUM="$2"
shift 2

STATUS=""
OWNER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --status) STATUS="$2"; shift 2 ;;
        --owner)  OWNER="$2";  shift 2 ;;
        *) echo "Unknown option: $1" >&2; usage ;;
    esac
done

echo "Finding project item for $REPO #$ISSUE_NUM..."
ITEM_ID=$("$GH_FIND" "$REPO" "$ISSUE_NUM" 2>/dev/null || echo "")

if [[ -z "$ITEM_ID" ]]; then
    echo "✗ Could not find project item for issue #$ISSUE_NUM"
    exit 1
fi

echo "✓ Found item: $ITEM_ID"

# Build sync command
SYNC_CMD="$GH_SYNC $ITEM_ID"
[[ -n "$STATUS" ]] && SYNC_CMD="$SYNC_CMD --status '$STATUS'"
[[ -n "$OWNER" ]] && SYNC_CMD="$SYNC_CMD --owner $OWNER"

echo "Syncing..."
eval "$SYNC_CMD"
echo "✓ Done"
