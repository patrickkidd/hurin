#!/usr/bin/env bash
set -euo pipefail

# Co-Founder Action System — List
# ADR: ~/.openclaw/adrs/ADR-0005-action-system.md
#
# Lists pending/recent actions across all actions/*.json files.
#
# Usage: action-list.sh [--all]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

SHOW_ALL=false
[[ "${1:-}" == "--all" ]] && SHOW_ALL=true

if [[ ! -d "$ACTIONS_DIR" ]] || ! ls "$ACTIONS_DIR"/*.json > /dev/null 2>&1; then
    echo "No actions found. Run a co-founder lens to generate actions."
    exit 0
fi

echo "**Co-Founder Actions**"
echo ""

PENDING_COUNT=0
SPAWNED_COUNT=0
APPROVED_COUNT=0
NOTED_COUNT=0

for f in "$ACTIONS_DIR"/*.json; do
    [[ -f "$f" ]] || continue
    ACTIONS_COUNT="$(jq '.actions | length' "$f")"

    for i in $(seq 0 $((ACTIONS_COUNT - 1))); do
        ACTION="$(jq ".actions[$i]" "$f")"
        ID="$(echo "$ACTION" | jq -r '.id')"
        TITLE="$(echo "$ACTION" | jq -r '.title')"
        TIER="$(echo "$ACTION" | jq -r '.tier')"
        CATEGORY="$(echo "$ACTION" | jq -r '.category')"
        EFFORT="$(echo "$ACTION" | jq -r '.effort')"
        STATUS="$(echo "$ACTION" | jq -r '.status // "unknown"')"
        ISSUE_URL="$(echo "$ACTION" | jq -r '.issue_url // ""')"

        case "$STATUS" in
            pending_approval) ((PENDING_COUNT++)) ;;
            spawned)          ((SPAWNED_COUNT++)) ;;
            approved)         ((APPROVED_COUNT++)) ;;
            noted)            ((NOTED_COUNT++)) ;;
        esac

        # Filter: show only actionable items unless --all
        if [[ "$SHOW_ALL" == false ]] && [[ "$STATUS" != "pending_approval" ]]; then
            continue
        fi

        # Format output
        case "$STATUS" in
            pending_approval)
                if [[ "$CATEGORY" == "revenue" ]]; then
                    echo "💰 **$TITLE** [$EFFORT, $CATEGORY]"
                else
                    echo "📋 **$TITLE** [$EFFORT, $CATEGORY]"
                fi
                echo "   ID: \`$ID\`"
                [[ -n "$ISSUE_URL" ]] && echo "   Issue: $ISSUE_URL"
                echo "   → \`/cofounder approve $ID\` or \`/cofounder refine $ID <feedback>\`"
                echo ""
                ;;
            spawned)
                echo "🤖 **$TITLE** [$EFFORT, $CATEGORY] — spawned"
                echo "   ID: \`$ID\`"
                [[ -n "$ISSUE_URL" ]] && echo "   Issue: $ISSUE_URL"
                echo ""
                ;;
            approved)
                echo "✅ **$TITLE** [$EFFORT, $CATEGORY] — approved"
                echo "   ID: \`$ID\`"
                [[ -n "$ISSUE_URL" ]] && echo "   Issue: $ISSUE_URL"
                echo ""
                ;;
            noted)
                if [[ "$SHOW_ALL" == true ]]; then
                    echo "📝 **$TITLE** [$EFFORT, $CATEGORY] — noted"
                    echo ""
                fi
                ;;
        esac
    done
done

echo "---"
echo "**Summary:** $PENDING_COUNT pending | $SPAWNED_COUNT spawned | $APPROVED_COUNT approved | $NOTED_COUNT noted"
if [[ "$SHOW_ALL" == false ]] && [[ $((SPAWNED_COUNT + APPROVED_COUNT + NOTED_COUNT)) -gt 0 ]]; then
    echo "_(showing pending only — use \`--all\` to see everything)_"
fi
