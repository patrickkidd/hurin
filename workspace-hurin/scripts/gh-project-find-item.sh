#!/usr/bin/env bash
# gh-project-find-item.sh — Find a project item ID by issue number and repo
# Usage: gh-project-find-item.sh <repo> <issue_number>
# Example: gh-project-find-item.sh patrickkidd/btcopilot 21
# Returns the project item ID (PVTI_...) or empty if not found

REPO="$1"
ISSUE_NUM="$2"

if [[ -z "$REPO" || -z "$ISSUE_NUM" ]]; then
  echo "Usage: gh-project-find-item.sh <owner/repo> <issue_number>"
  exit 1
fi

gh api graphql -f query='{ node(id: "PVT_kwHOABjmWc4BP0PU") { ... on ProjectV2 { items(first: 50) { nodes { id content { ... on Issue { number repository { nameWithOwner } } ... on PullRequest { number repository { nameWithOwner } } } } } } } }' \
  | jq -r --arg repo "$REPO" --argjson num "$ISSUE_NUM" \
    '.data.node.items.nodes[] | select(.content.repository.nameWithOwner == $repo and .content.number == $num) | .id'
