#!/usr/bin/env bash
# gh-project-sync.sh — Update a Family Diagram project item's fields
# Usage: gh-project-sync.sh <item_id> [--status Todo|"In Progress"|Done]
#        [--owner Patrick|Hurin] [--priority P0|P1|P2|P3]
#        [--component Frontend|Backend|Infra|Design|Both]

PROJECT_ID="PVT_kwHOABjmWc4BP0PU"
STATUS_FIELD_ID="PVTSSF_lAHOABjmWc4BP0PUzg-HbRs"
OWNER_FIELD_ID="PVTSSF_lAHOABjmWc4BP0PUzg-HbS8"
PRIORITY_FIELD_ID="PVTSSF_lAHOABjmWc4BP0PUzg-HbS4"
COMPONENT_FIELD_ID="PVTSSF_lAHOABjmWc4BP0PUzg-HbTo"

# Status option IDs
STATUS_TODO="1a206b7c"
STATUS_IN_PROGRESS="f2e96042"
STATUS_DONE="3fb3f387"

# Owner option IDs (Beren/Tuor are archived agents — kept for backward compat)
OWNER_PATRICK="2120b409"
OWNER_HURIN="4e27439a"
OWNER_BEREN="fb745a0e"  # archived
OWNER_TUOR="e0b8b5b9"   # archived

# Priority option IDs
PRIORITY_P0="932aef5c"
PRIORITY_P1="df1b629f"
PRIORITY_P2="fcaadcab"
PRIORITY_P3="6b1dd892"

# Component option IDs
COMPONENT_FRONTEND="053c7604"
COMPONENT_BACKEND="6f4da7de"
COMPONENT_INFRA="636ff93f"
COMPONENT_DESIGN="e39a507e"
COMPONENT_BOTH="f025646c"

ITEM_ID=""
NEW_STATUS=""
NEW_OWNER=""
NEW_PRIORITY=""
NEW_COMPONENT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --status)    NEW_STATUS="$2";    shift 2 ;;
    --owner)     NEW_OWNER="$2";     shift 2 ;;
    --priority)  NEW_PRIORITY="$2";  shift 2 ;;
    --component) NEW_COMPONENT="$2"; shift 2 ;;
    *)           ITEM_ID="$1";       shift   ;;
  esac
done

if [[ -z "$ITEM_ID" ]]; then
  echo "Usage: gh-project-sync.sh <item_id> [--status Todo|In Progress|Done] [--owner Patrick|Hurin] [--priority P0|P1|P2|P3] [--component Frontend|Backend|Infra|Design|Both]"
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

if [[ -n "$NEW_PRIORITY" ]]; then
  case "$NEW_PRIORITY" in
    "P0") set_field "$PRIORITY_FIELD_ID" "$PRIORITY_P0" ;;
    "P1") set_field "$PRIORITY_FIELD_ID" "$PRIORITY_P1" ;;
    "P2") set_field "$PRIORITY_FIELD_ID" "$PRIORITY_P2" ;;
    "P3") set_field "$PRIORITY_FIELD_ID" "$PRIORITY_P3" ;;
    *) echo "Unknown priority: $NEW_PRIORITY"; exit 1 ;;
  esac
  echo "Priority → $NEW_PRIORITY"
fi

if [[ -n "$NEW_COMPONENT" ]]; then
  case "$NEW_COMPONENT" in
    "Frontend") set_field "$COMPONENT_FIELD_ID" "$COMPONENT_FRONTEND" ;;
    "Backend")  set_field "$COMPONENT_FIELD_ID" "$COMPONENT_BACKEND" ;;
    "Infra")    set_field "$COMPONENT_FIELD_ID" "$COMPONENT_INFRA" ;;
    "Design")   set_field "$COMPONENT_FIELD_ID" "$COMPONENT_DESIGN" ;;
    "Both")     set_field "$COMPONENT_FIELD_ID" "$COMPONENT_BOTH" ;;
    *) echo "Unknown component: $NEW_COMPONENT"; exit 1 ;;
  esac
  echo "Component → $NEW_COMPONENT"
fi
