#!/bin/bash
# task-board.sh — Quick summary of GitHub project board
#
# Usage:
#   task-board.sh              # Show summary (default: all in-progress)
#   task-board.sh --owner Hurin   # Show issues assigned to owner
#   task-board.sh --status Done   # Show issues with status
#   task-board.sh --all            # Show all issues
#
# Examples:
#   task-board.sh                   # What's in progress?
#   task-board.sh --owner Hurin      # What's assigned to me?
#   task-board.sh --priority P0      # What's urgent?
#   task-board.sh --all              # Full board dump

PROJECT_ID="PVT_kwHOABjmWc4BP0PU"

# Parse arguments
SHOW_ALL=""
FILTER_STATUS=""
FILTER_OWNER=""
FILTER_PRIORITY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all) SHOW_ALL=1; shift ;;
        --owner) FILTER_OWNER="$2"; shift 2 ;;
        --status) FILTER_STATUS="$2"; shift 2 ;;
        --priority) FILTER_PRIORITY="$2"; shift 2 ;;
        -h|--help) cat <<'HELP'
Usage: task-board.sh [options]

Show a quick summary of the Family Diagram project board.

Options:
  --all              Show all issues (not just in-progress)
  --owner <name>     Filter by owner (Patrick, Hurin)
  --status <status>  Filter by status (Todo, Todo, Done)
  --priority <prio>  Filter by priority (P0, P1, P2, P3)

Examples:
  task-board.sh                   # What's in progress?
  task-board.sh --owner Hurin      # What's assigned to me?
  task-board.sh --priority P0      # What's urgent?
  task-board.sh --all              # Full board dump
HELP
        exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# Build filter
FILTER=""
if [[ -n "$FILTER_STATUS" ]]; then
    FILTER="Status=$FILTER_STATUS"
fi
if [[ -n "$FILTER_OWNER" ]]; then
    [[ -n "$FILTER" ]] && FILTER="${FILTER},"
    FILTER="${FILTER}Owner=$FILTER_OWNER"
fi
if [[ -n "$FILTER_PRIORITY" ]]; then
    [[ -n "$FILTER" ]] && FILTER="${FILTER},"
    FILTER="${FILTER}Priority=$FILTER_PRIORITY"
fi

# If no filter and no --all, default to Todo
if [[ -z "$SHOW_ALL" && -z "$FILTER" ]]; then
    FILTER="Status=Todo"
fi

# Fetch items
ITEMS=$(gh api graphql -f query='{ node(id: "PVT_kwHOABjmWc4BP0PU") { ... on ProjectV2 { items(first: 100) { nodes { id content { ... on Issue { number title repository { nameWithOwner } } } } } } } }' 2>/dev/null)

# Extract item IDs and basic info
ITEM_IDS=$(echo "$ITEMS" | jq -r '.data.node.items.nodes[] | select(.content != null) | "\(.id)|\(.content.number)|\(.content.title)|\(.content.repository.nameWithOwner)"')

COUNT=0
while IFS='|' read -r item_id num title repo; do
    [[ -z "$item_id" ]] && continue
    
    # Get field values for this item
    FIELDS=$(gh api graphql -f query="{ node(id: \"$item_id\") { ... on ProjectV2Item { fieldValues(first: 10) { nodes { ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2FieldCommon { name } } } } } } } }" 2>/dev/null)
    
    status=$(echo "$FIELDS" | jq -r '.data.node.fieldValues.nodes[] | select(.field.name == "Status") | .name // empty')
    owner=$(echo "$FIELDS" | jq -r '.data.node.fieldValues.nodes[] | select(.field.name == "Owner") | .name // empty')
    priority=$(echo "$FIELDS" | jq -r '.data.node.fieldValues.nodes[] | select(.field.name == "Priority") | .name // empty')
    
    # Apply filters
    if [[ -n "$FILTER" ]]; then
        if [[ "$FILTER" == "Status=Todo" && "$status" != "Todo" ]]; then continue; fi
        if [[ "$FILTER" == "Status=Todo" && "$status" != "Todo" ]]; then continue; fi
        if [[ "$FILTER" == "Status=Done" && "$status" != "Done" ]]; then continue; fi
        if [[ "$FILTER" == "Owner=Hurin" && "$owner" != "Hurin" ]]; then continue; fi
        if [[ "$FILTER" == "Owner=Patrick" && "$owner" != "Patrick" ]]; then continue; fi
        if [[ "$FILTER" == "Owner=Beren" && "$owner" != "Beren" ]]; then continue; fi
        if [[ "$FILTER" == "Owner=Tuor" && "$owner" != "Tuor" ]]; then continue; fi
        if [[ "$FILTER" == "Priority=P0"* ]] && [[ "$priority" != "P0 - Critical" ]]; then continue; fi
        if [[ "$FILTER" == "Priority=P1"* ]] && [[ "$priority" != "P1 - High" ]]; then continue; fi
        if [[ "$FILTER" == "Priority=P2"* ]] && [[ "$priority" != "P2 - Medium" ]]; then continue; fi
        if [[ "$FILTER" == "Priority=P3"* ]] && [[ "$priority" != "P3 - Low" ]]; then continue; fi
    fi
    
    repo_short=$(echo "$repo" | sed 's/patrickkidd\///')
    priority_short=$(echo "$priority" | sed 's/ - .*//')
    printf "#%-3s [%s] %-4s %-12s %s\n" "$num" "$repo_short" "${priority_short:-—}" "${status:-—}" "$title"
    COUNT=$((COUNT + 1))
done <<< "$ITEM_IDS"

if [[ $COUNT -eq 0 ]]; then
    if [[ -n "$FILTER" ]]; then
        echo "No issues match: $FILTER"
    else
        echo "No issues found."
    fi
else
    echo ""
    echo "($COUNT issues)"
fi
