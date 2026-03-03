#!/bin/bash
# spawn-task-with-project.sh — Enhanced spawn-task.sh with automatic project board sync
#
# Usage (with project sync):
#   spawn-task-with-project.sh --repo <btcopilot|familydiagram> --task <task-id> \
#     --description '<desc>' --issue <number> <<'PROMPT'
#   Your prompt here
#   PROMPT
#
# Usage (without project sync, backward compatible):
#   spawn-task-with-project.sh --repo <btcopilot|familydiagram> --task <task-id> \
#     --description '<desc>' <<'PROMPT'
#   Your prompt here
#   PROMPT

set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPAWN="$SCRIPTS_DIR/spawn-task.sh"
GH_FIND="$SCRIPTS_DIR/gh-project-find-item.sh"
GH_SYNC="$SCRIPTS_DIR/gh-project-sync.sh"

usage() {
    cat >&2 <<'USAGE'
Usage: spawn-task-with-project.sh [options]

Options (all optional except --repo, --task, --description):
  --repo         Target repo (btcopilot or familydiagram, required)
  --task         Task ID (required)
  --description  Short description (required)
  --issue        GitHub issue number (optional, enables auto project sync)
  --branch       Custom branch name (default: feat/<task-id>)
  --full-sync    Run 'uv sync' instead of symlinking .venv

Prompt is read from stdin.

Examples:
  # With project board sync (auto-mark as "In Progress", owner "Hurin")
  spawn-task-with-project.sh --repo familydiagram --task T7-4 \
    --description 'Build button' --issue 156 <<'PROMPT'
  Implement the button...
  PROMPT

  # Without project sync (backward compatible)
  spawn-task-with-project.sh --repo familydiagram --task T7-4 \
    --description 'Build button' <<'PROMPT'
  Implement the button...
  PROMPT
USAGE
    exit 1
}

TASK_ID=""
DESCRIPTION=""
BRANCH=""
TARGET_REPO=""
FULL_SYNC=false
ISSUE_NUM=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)        TARGET_REPO="$2"; shift 2 ;;
        --task)        TASK_ID="$2";     shift 2 ;;
        --description) DESCRIPTION="$2"; shift 2 ;;
        --branch)      BRANCH="$2";      shift 2 ;;
        --issue)       ISSUE_NUM="$2";   shift 2 ;;
        --full-sync)   FULL_SYNC=true;   shift ;;
        -h|--help)     usage ;;
        *) echo "Unknown option: $1" >&2; usage ;;
    esac
done

[[ -z "$TASK_ID" || -z "$DESCRIPTION" || -z "$TARGET_REPO" ]] && usage

# Read prompt from stdin
PROMPT=$(cat)
[[ -z "$PROMPT" ]] && { echo "Error: No prompt provided on stdin." >&2; exit 1; }

# --- Step 1: Spawn the task (before syncing project, so worktree is ready) ---
echo "→ Spawning task in background..."
SPAWN_ARGS="--repo $TARGET_REPO --task $TASK_ID --description '$DESCRIPTION'"
[[ -n "$BRANCH" ]] && SPAWN_ARGS="$SPAWN_ARGS --branch $BRANCH"
[[ -n "$ISSUE_NUM" ]] && SPAWN_ARGS="$SPAWN_ARGS --issue $ISSUE_NUM"
[[ "$FULL_SYNC" == "true" ]] && SPAWN_ARGS="$SPAWN_ARGS --full-sync"

echo "$PROMPT" | eval "$SPAWN $SPAWN_ARGS" || {
    echo "Error: Failed to spawn task" >&2
    exit 1
}

# --- Step 2: Store issue number in task registry (for check-agents.py to use later) ---
if [[ -n "$ISSUE_NUM" ]]; then
    DEV_REPO="${DEV_REPO:-$HOME/.openclaw/workspace-hurin/theapp}"
    REGISTRY="$DEV_REPO/.clawdbot/active-tasks.json"
    
    python3 - <<PYEOF
import json
from pathlib import Path

registry_path = Path("$REGISTRY")
if registry_path.exists():
    data = json.loads(registry_path.read_text())
    for task in data.get("tasks", []):
        if task["id"] == "$TASK_ID":
            task["issueNumber"] = int($ISSUE_NUM)
            registry_path.write_text(json.dumps(data, indent=2))
            print("  Stored issue #$ISSUE_NUM in task registry")
            break
PYEOF
fi

# --- Step 3: Sync project board (if issue number provided) ---
if [[ -n "$ISSUE_NUM" ]]; then
    echo "→ Syncing GitHub project board..."
    
    # Need to infer the repo path from TARGET_REPO
    # e.g., if TARGET_REPO is "btcopilot", then it's patrickkidd/btcopilot
    # if TARGET_REPO is "familydiagram", then it's patrickkidd/familydiagram
    GH_REPO="patrickkidd/$TARGET_REPO"
    
    # Find project item
    ITEM_ID=$("$GH_FIND" "$GH_REPO" "$ISSUE_NUM" 2>/dev/null || echo "")
    
    if [[ -z "$ITEM_ID" ]]; then
        echo "  ⚠ Warning: Could not find project item for issue #$ISSUE_NUM in $GH_REPO"
        echo "  (Project board sync skipped, but task spawned successfully)"
    else
        # Sync to "In Progress" with owner "Hurin"
        if "$GH_SYNC" "$ITEM_ID" --status "In Progress" --owner Hurin 2>/dev/null; then
            echo "  ✓ Project item synced to 'In Progress' (owner: Hurin)"
        else
            echo "  ⚠ Warning: Could not sync project board (but task spawned successfully)"
        fi
    fi
fi

echo ""
echo "✓ Complete! Monitor with: task watch $TASK_ID"
