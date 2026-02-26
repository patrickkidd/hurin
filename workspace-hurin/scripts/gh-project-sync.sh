#!/usr/bin/env bash
# gh-project-sync.sh — Update a Family Diagram project item's fields
# Usage: gh-project-sync.sh <item_id> [--status Todo|"In Progress"|Done] [--owner Patrick|Hurin|Beren|Tuor]

PROJECT_ID="PVT_kwHOABjmWc4BP0PU"
STATUS_FIELD_ID="PVTSSF_lAHOABjmWc4BP0PUzg-HbRs"
OWNER_FIELD_ID="PVTSSF_lAHOABjmWc4BP0PUzg-HbS8"

# Status option IDs
STATUS_TODO="f75ad846"
STATUS_IN_PROGRESS="47fc9ee4"
STATUS_DONE="98236657"

# Owner option IDs
OWNER_PATRICK="2120b409"
OWNER_HURIN="4e27439a"
OWNER_BEREN="fb745a0e"
OWNER_TUOR="e0b8b5b9"

ITEM_ID=""
NEW_STATUS=""
NEW_OWNER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --status) NEW_STATUS="$2"; shift 2 ;;
    --owner)  NEW_OWNER="$2";  shift 2 ;;
    *)        ITEM_ID="$1";    shift   ;;
  esac
done

if [[ -z "$ITEM_ID" ]]; then
  echo "Usage: gh-project-sync.sh <item_id> [--status Todo|In Progress|Done] [--owner Patrick|Hurin|Beren|Tuor]"
  exit 1
fi

set_field() {
  local field_id="$1"
  local option_id="$2"
  gh api graphql -f query='
    mutation($proj: ID!, $item: ID!, $field: ID!, $opt: String!) {
      updateProjectV2ItemFieldValue(input: {
        projectId: $proj
        itemId: $item
        fieldId: $field
        value: { singleSelectOptionId: $opt }
      }) { projectV2Item { id } }
    }' \
    -f proj="$PROJECT_ID" \
    -f item="$ITEM_ID" \
    -f field="$field_id" \
    -f opt="$option_id"
}

if [[ -n "$NEW_STATUS" ]]; then
  case "$NEW_STATUS" in
    "Todo")        set_field "$STATUS_FIELD_ID" "$STATUS_TODO" ;;
    "In Progress") set_field "$STATUS_FIELD_ID" "$STATUS_IN_PROGRESS" ;;
    "Done")        set_field "$STATUS_FIELD_ID" "$STATUS_DONE" ;;
    *) echo "Unknown status: $NEW_STATUS"; exit 1 ;;
  esac
  echo "Status → $NEW_STATUS"
fi

if [[ -n "$NEW_OWNER" ]]; then
  case "$NEW_OWNER" in
    "Patrick") set_field "$OWNER_FIELD_ID" "$OWNER_PATRICK" ;;
    "Hurin")   set_field "$OWNER_FIELD_ID" "$OWNER_HURIN" ;;
    "Beren")   set_field "$OWNER_FIELD_ID" "$OWNER_BEREN" ;;
    "Tuor")    set_field "$OWNER_FIELD_ID" "$OWNER_TUOR" ;;
    *) echo "Unknown owner: $NEW_OWNER"; exit 1 ;;
  esac
  echo "Owner → $NEW_OWNER"
fi
