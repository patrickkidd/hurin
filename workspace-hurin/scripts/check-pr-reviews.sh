#!/bin/bash
# Check recent PRs for new review comments from bots
# Alerts when there are unaddressed bot reviews

REPOS=("patrickkidd/familydiagram" "patrickkidd/btcopilot")

for REPO in "${REPOS[@]}"; do
    # Get the 3 most recent open PRs (by updated time)
    PRS=$(gh pr list --repo "$REPO" --state open --limit 3 --json number --jq '.[].number')
    
    for PR in $PRS; do
        # Check for unresolved bot review comments
        BOT_COMMENTS=$(gh api "repos/$REPO/pulls/$PR/comments" --jq '[.[] | select(.user.type == "Bot")] | length')
        
        if [ "$BOT_COMMENTS" -gt 0 ]; then
            # Get PR title for context
            TITLE=$(gh pr view "$PR" --repo "$REPO" --json title --jq '.title')
            echo "🤖 $REPO #$PR: $TITLE - $BOT_COMMENTS bot comment(s)"
        fi
    done
done
