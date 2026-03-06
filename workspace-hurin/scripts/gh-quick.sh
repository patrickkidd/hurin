#!/usr/bin/env bash
# gh-quick.sh — Quick GitHub queries with sensible defaults
# Usage: gh-quick.sh <command> [options]
#
# Commands:
#   prs              — List open PRs (default: familydiagram)
#   prs <repo>       — List open PRs for a repo
#   issues           — List open issues (default: familydiagram)
#   issues <repo>   — List open issues for a repo
#   mine             — List issues/PRs assigned to you
#   ci               — Show recent CI runs
#   status           — Quick status: open PRs + issues count
#
# Options:
#   --repo <name>    — Override default repo (btcopilot, familydiagram, fdserver)
#
# Examples:
#   gh-quick.sh prs                    # Open PRs in familydiagram
#   gh-quick.sh prs btcopilot          # Open PRs in btcopilot
#   gh-quick.sh issues                 # Open issues in familydiagram
#   gh-quick.sh issues btcopilot      # Open issues in btcopilot
#   gh-quick.sh mine                   # My assigned issues/PRs
#   gh-quick.sh ci                     # Recent CI runs
#   gh-quick.sh status                 # Quick status dashboard

set -euo pipefail

DEFAULT_REPO="patrickkidd/familydiagram"
COMMAND="${1:-}"
shift || true

# Parse global options
REPO="$DEFAULT_REPO"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    -h|--help|help) COMMAND="help"; break ;;
    # If arg looks like a repo name, treat it as the repo
    btcopilot|familydiagram|fdserver)
      REPO="patrickkidd/$1"
      shift
      ;;
    *) break ;;
  esac
done

case "$COMMAND" in
  prs|pr-list)
    # List open PRs
    gh pr list --repo "$REPO" --state open --limit 20 \
      --json number,title,author,url,createdAt,isDraft \
      -q '.[] | "[\(.number)] \(.title) — \(.author.login) (\(.createdAt[:10])) \(if .isDraft then "[DRAFT]" else "" end)"'
    ;;

  issues|issue-list)
    # List open issues (not PRs)
    gh issue list --repo "$REPO" --state open --limit 20 \
      --json number,title,author,labels,createdAt \
      -q '.[] | "[\(.number)] \(.title) — \(.author.login) (\(.createdAt[:10])) \(if (.labels | length) > 0 then "[\((.labels | map(.name) | join(", ")))]" else "" end)"'
    ;;

  mine|my-issues)
    # Issues/PRs assigned to current user
    echo "=== Issues assigned to you in $REPO ==="
    gh issue list --repo "$REPO" --assignee "@me" --state open --limit 10 \
      --json number,title,labels \
      -q '.[] | "  #\(.number) \(.title) \(if (.labels | length) > 0 then "[\((.labels | map(.name) | join(", ")))]" else "" end)"' || true
    echo ""
    echo "=== PRs assigned to you in $REPO ==="
    gh pr list --repo "$REPO" --assignee "@me" --state open --limit 10 \
      --json number,title,isDraft \
      -q '.[] | "  #\(.number) \(.title) \(if .isDraft then "[DRAFT]" else "" end)"' || true
    ;;

  ci|status-ci)
    # CI status - just show recent runs for the repo
    echo "=== Recent CI runs for $REPO ==="
    gh run list --repo "$REPO" --limit 10 \
      --json name,status,conclusion,updatedAt \
      -q '.[] | "  \(.status) — \(.conclusion // "pending") — \(.name) (\(.updatedAt[:10]))"'
    ;;

  status|dash|dashboard)
    # Quick dashboard
    echo "=== $REPO Status ==="
    echo ""
    echo "Open PRs:"
    COUNT=$(gh pr list --repo "$REPO" --state open --limit 100 2>/dev/null | wc -l | tr -d ' ')
    echo "  $COUNT PRs"
    if [[ "$COUNT" -gt 0 ]] && [[ "$COUNT" -lt 100 ]]; then
      gh pr list --repo "$REPO" --state open --limit 5 \
        --json number,title \
        -q '.[] | "    #\(.number) \(.title)"' 2>/dev/null || true
      if [[ "$COUNT" -gt 5 ]]; then
        echo "    ... and $((COUNT - 5)) more"
      fi
    fi
    echo ""
    echo "Open Issues:"
    COUNT=$(gh issue list --repo "$REPO" --state open --limit 100 2>/dev/null | wc -l | tr -d ' ')
    echo "  $COUNT issues"
    if [[ "$COUNT" -gt 0 ]] && [[ "$COUNT" -lt 100 ]]; then
      gh issue list --repo "$REPO" --state open --limit 5 \
        --json number,title \
        -q '.[] | "    #\(.number) \(.title)"' 2>/dev/null || true
      if [[ "$COUNT" -gt 5 ]]; then
        echo "    ... and $((COUNT - 5)) more"
      fi
    fi
    ;;

  ""|help)
    cat << 'USAGE'
gh-quick.sh — Quick GitHub queries with sensible defaults

Usage: gh-quick.sh <command> [options]

Commands:
  prs [repo]           List open PRs (default: familydiagram)
  issues [repo]        List open issues (default: familydiagram)  
  mine                 List issues/PRs assigned to you
  ci                   Show recent CI runs
  status               Quick status: open PRs + issues count

Options:
  --repo <name>        Override default repo

Examples:
  gh-quick.sh prs                    # Open PRs in familydiagram
  gh-quick.sh prs btcopilot          # Open PRs in btcopilot
  gh-quick.sh issues                 # Open issues in familydiagram
  gh-quick.sh issues btcopilot      # Open issues in btcopilot
  gh-quick.sh mine                   # My assigned issues/PRs
  gh-quick.sh ci                     # Recent CI runs
  gh-quick.sh status                 # Quick status dashboard
  gh-quick.sh --repo btcopilot prs   # Explicit repo with flag
USAGE
    exit 0
    ;;

  *)
    echo "Unknown command: $COMMAND" >&2
    echo "Run 'gh-quick.sh help' for usage" >&2
    exit 1
    ;;
esac
