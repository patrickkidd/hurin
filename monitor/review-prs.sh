#!/bin/bash
# review-prs.sh - Automated Claude code review for open PRs.
#
# Runs every 15 minutes via cron. Reviews PRs that haven't been reviewed yet.
# Uses the `reviewed-by-claude` label to prevent re-reviewing.
#
# Usage:
#   review-prs.sh          - review all unreviewed open PRs
#   review-prs.sh --dry    - just list which PRs would be reviewed

set -euo pipefail

REPO="$HOME/Projects/theapp"
LABEL="reviewed-by-claude"
DRY_RUN=false
LOG="$HOME/.openclaw/monitor/review.log"

[[ "${1:-}" == "--dry" ]] && DRY_RUN=true

log() {
    local ts
    ts=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$ts] $1" | tee -a "$LOG"
}

cd "$REPO"

# Ensure the label exists (idempotent)
if ! gh label list --json name --jq '.[].name' 2>/dev/null | grep -qx "$LABEL"; then
    log "Creating '$LABEL' label..."
    gh label create "$LABEL" --description "PR has been reviewed by Claude" --color "7057ff" 2>/dev/null || true
fi

# Get open PRs without the reviewed label
PRS=$(gh pr list --state open --json number,title,headRefName \
    --jq '.[] | select(true) | "\(.number)\t\(.title)\t\(.headRefName)"')

if [[ -z "$PRS" ]]; then
    log "No open PRs found."
    exit 0
fi

while IFS=$'\t' read -r PR_NUM PR_TITLE PR_BRANCH; do
    # Check if already reviewed
    LABELS=$(gh pr view "$PR_NUM" --json labels --jq '.labels[].name' 2>/dev/null)
    if echo "$LABELS" | grep -qx "$LABEL"; then
        log "PR #$PR_NUM already reviewed, skipping."
        continue
    fi

    log "Reviewing PR #$PR_NUM: $PR_TITLE ($PR_BRANCH)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log "  [DRY RUN] Would review PR #$PR_NUM"
        continue
    fi

    # Get the diff
    DIFF=$(gh pr diff "$PR_NUM" 2>/dev/null)
    if [[ -z "$DIFF" ]]; then
        log "  No diff for PR #$PR_NUM, skipping."
        continue
    fi

    # Truncate very large diffs to avoid context issues
    DIFF_LINES=$(echo "$DIFF" | wc -l)
    if [[ "$DIFF_LINES" -gt 2000 ]]; then
        DIFF=$(echo "$DIFF" | head -2000)
        DIFF="$DIFF"$'\n\n[Diff truncated at 2000 lines]'
    fi

    # Run Claude review
    REVIEW=$(claude -p "You are reviewing a pull request for the Family Diagram project (Python/PyQt5/Flask monorepo).

PR #$PR_NUM: $PR_TITLE
Branch: $PR_BRANCH

Review this diff for:
1. Bugs or logic errors
2. Security issues (injection, XSS, auth bypass)
3. Missing error handling for edge cases
4. Test coverage gaps
5. Style/convention issues (only significant ones)

Be concise. Focus on actual problems, not style nitpicks. If the PR looks good, say so briefly.

Format your review as a bulleted list of findings, or 'LGTM - no issues found' if clean.

DIFF:
$DIFF" 2>/dev/null)

    if [[ -z "$REVIEW" ]]; then
        log "  Claude review returned empty for PR #$PR_NUM"
        continue
    fi

    # Post the review as a comment
    COMMENT="## Automated Claude Review

$REVIEW

---
*Automated review by Claude via \`review-prs.sh\`*"

    gh pr review "$PR_NUM" --comment --body "$COMMENT" 2>/dev/null

    # Add the label to prevent re-reviewing
    gh pr edit "$PR_NUM" --add-label "$LABEL" 2>/dev/null

    log "  Review posted on PR #$PR_NUM"

done <<< "$PRS"

log "Review pass complete."
