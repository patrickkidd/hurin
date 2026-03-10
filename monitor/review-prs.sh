#!/bin/bash
# review-prs.sh - Automated Claude code review for open PRs.
#
# Runs every 15 minutes via cron. Reviews PRs that haven't been reviewed yet.
# Uses the `reviewed-by-claude` label to prevent re-reviewing.
# Checks both btcopilot and familydiagram repos.
#
# Usage:
#   review-prs.sh          - review all unreviewed open PRs
#   review-prs.sh --dry    - just list which PRs would be reviewed

set -euo pipefail

# Ensure PATH includes homebrew for cron environment
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# GitHub auth — use patrickkidd-hurin bot account
export GH_TOKEN="$(cat "$HOME/.openclaw/monitor/hurin-bot-token" 2>/dev/null)"

REPOS=(
    "$HOME/.openclaw/workspace-hurin/theapp/btcopilot"
    "$HOME/.openclaw/workspace-hurin/theapp/familydiagram"
)
LABEL="reviewed-by-claude"
DRY_RUN=false
LOG="$HOME/.openclaw/monitor/review.log"
FAIL_DIR="$HOME/.openclaw/monitor/review-failures"
MAX_RETRIES=3

mkdir -p "$FAIL_DIR"

[[ "${1:-}" == "--dry" ]] && DRY_RUN=true

log() {
    local ts
    ts=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$ts] $1" >> "$LOG"
}

ensure_label() {
    local repo_name="$1"
    local owner_repo
    owner_repo=$(gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null) || {
        log "[$repo_name] WARNING: Cannot determine repo owner/name, skipping label check"
        return 1
    }
    # Check if label exists via API — gives clear 200/404, no ambiguity
    if gh api "repos/$owner_repo/labels/$LABEL" --silent 2>/dev/null; then
        return 0
    fi
    # Label doesn't exist — create it
    log "[$repo_name] Creating '$LABEL' label..."
    if ! gh label create "$LABEL" --description "PR has been reviewed by Claude" --color "7057ff" 2>&1; then
        log "[$repo_name] WARNING: Failed to create label '$LABEL' (may already exist)"
    fi
}

review_repo() {
    local REPO_DIR="$1"
    local REPO_NAME
    REPO_NAME=$(basename "$REPO_DIR")

    if [[ ! -d "$REPO_DIR" ]]; then
        log "[$REPO_NAME] ERROR: Repo directory not found: $REPO_DIR"
        return 0
    fi

    cd "$REPO_DIR"

    # Ensure the label exists (idempotent)
    ensure_label "$REPO_NAME"

    # Get open PRs
    local PRS
    PRS=$(gh pr list --state open --json number,title,headRefName \
        --jq '.[] | select(true) | "\(.number)\t\(.title)\t\(.headRefName)"') || {
        log "[$REPO_NAME] ERROR: Failed to list PRs"
        return 0
    }

    if [[ -z "$PRS" ]]; then
        log "[$REPO_NAME] No open PRs."
        return
    fi

    while IFS=$'\t' read -r PR_NUM PR_TITLE PR_BRANCH; do
        # Check if already reviewed
        local LABELS
        LABELS=$(gh pr view "$PR_NUM" --json labels --jq '.labels[].name' 2>/dev/null) || true
        if echo "$LABELS" | grep -qx "$LABEL"; then
            continue
        fi

        # Check if this PR has exceeded retry limit
        local FAIL_FILE="$FAIL_DIR/${REPO_NAME}-${PR_NUM}"
        local FAIL_COUNT=0
        if [[ -f "$FAIL_FILE" ]]; then
            FAIL_COUNT=$(cat "$FAIL_FILE")
        fi
        if [[ "$FAIL_COUNT" -ge "$MAX_RETRIES" ]]; then
            continue
        fi

        log "[$REPO_NAME] Reviewing PR #$PR_NUM: $PR_TITLE ($PR_BRANCH)"

        if [[ "$DRY_RUN" == "true" ]]; then
            log "  [DRY RUN] Would review PR #$PR_NUM"
            continue
        fi

        # Get the diff
        local DIFF
        DIFF=$(gh pr diff "$PR_NUM" 2>/dev/null) || true
        if [[ -z "$DIFF" ]]; then
            log "  No diff for PR #$PR_NUM, skipping."
            continue
        fi

        # Truncate very large diffs to avoid context issues
        local DIFF_LINES
        DIFF_LINES=$(echo "$DIFF" | wc -l)
        if [[ "$DIFF_LINES" -gt 2000 ]]; then
            DIFF=$(echo "$DIFF" | head -2000)
            DIFF="$DIFF"$'\n\n[Diff truncated at 2000 lines]'
        fi

        # Run Claude review via Agent SDK (cc-query.py)
        local REVIEW
        REVIEW=$(echo "You are reviewing a pull request for the Family Diagram project ($REPO_NAME repo — Python/PyQt5/Flask).

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
$DIFF" | uv run --directory "$HOME/.openclaw/monitor" python "$HOME/.openclaw/monitor/cc-query.py" --description "PR review: $REPO_NAME #$PR_NUM" --max-turns 3 2>/dev/null) || true

        if [[ -z "$REVIEW" ]]; then
            FAIL_COUNT=$((FAIL_COUNT + 1))
            echo "$FAIL_COUNT" > "$FAIL_FILE"
            log "  Claude review returned empty for PR #$PR_NUM (attempt $FAIL_COUNT/$MAX_RETRIES)"
            continue
        fi

        # Review succeeded — clear any failure tracking
        rm -f "$FAIL_FILE"

        # Post the review as a comment
        local COMMENT="## Automated Claude Review

$REVIEW

---
*Automated review by Claude via \`review-prs.sh\`*"

        gh pr review "$PR_NUM" --comment --body "$COMMENT" 2>/dev/null || {
            log "[$REPO_NAME] WARNING: Failed to post review on PR #$PR_NUM"
        }

        # Add the label to prevent re-reviewing
        gh pr edit "$PR_NUM" --add-label "$LABEL" 2>/dev/null || {
            log "[$REPO_NAME] WARNING: Failed to add label to PR #$PR_NUM"
        }

        log "[$REPO_NAME] Review posted on PR #$PR_NUM"

    done <<< "$PRS"
}

for REPO in "${REPOS[@]}"; do
    review_repo "$REPO"
done

log "Review pass complete."
