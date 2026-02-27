#!/bin/bash
# spawn-task.sh - Spawn a Claude Code task and register it for monitoring.
#
# Usage:
#   spawn-task.sh --repo <btcopilot|familydiagram> --task <task-id> --description <desc> [--branch <branch>] [--full-sync]
#
# The prompt is read from stdin. Example:
#   spawn-task.sh --repo btcopilot --task fix-emotionalunit-crash \
#     --description "Fix crash in emotionalunit.py" <<'PROMPT'
#   Fix the crash in btcopilot/btcopilot/emotionalunit.py when Accept All is clicked...
#   PROMPT

set -euo pipefail

usage() {
    cat >&2 <<'EOF'
Usage: spawn-task.sh --repo <btcopilot|familydiagram> --task <task-id> --description <desc> [--branch <branch>] [--full-sync]
       Prompt is read from stdin.

Options:
  --repo         Target repo (btcopilot or familydiagram) — where PRs land
  --task         Task identifier (used for worktree, branch, tmux session)
  --description  Short description for the task registry
  --branch       Custom branch name (default: feat/<task-id>)
  --full-sync    Run 'uv sync' in worktree instead of symlinking .venv
EOF
    exit 1
}

TASK_ID=""
DESCRIPTION=""
BRANCH=""
TARGET_REPO=""
FULL_SYNC=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)        TARGET_REPO="$2"; shift 2 ;;
        --task)        TASK_ID="$2";     shift 2 ;;
        --description) DESCRIPTION="$2"; shift 2 ;;
        --branch)      BRANCH="$2";      shift 2 ;;
        --full-sync)   FULL_SYNC=true;   shift ;;
        -h|--help)     usage ;;
        *) echo "Unknown option: $1" >&2; usage ;;
    esac
done

[[ -z "$TASK_ID" || -z "$DESCRIPTION" || -z "$TARGET_REPO" ]] && usage
[[ "$TARGET_REPO" != "btcopilot" && "$TARGET_REPO" != "familydiagram" ]] && {
    echo "Error: --repo must be btcopilot or familydiagram" >&2; exit 1
}

BRANCH="${BRANCH:-feat/$TASK_ID}"
DEV_REPO="$HOME/.openclaw/workspace-hurin/theapp"
REPO_DIR="$DEV_REPO/$TARGET_REPO"
WORKTREE="$HOME/.openclaw/workspace-hurin/theapp-worktrees/$TASK_ID"
SESSION="claude-$TASK_ID"
REGISTRY="$DEV_REPO/.clawdbot/active-tasks.json"

# Read prompt from stdin
PROMPT=$(cat)
[[ -z "$PROMPT" ]] && { echo "Error: No prompt provided on stdin." >&2; exit 1; }

# --- 1. Create git worktree ---
# Worktrees are created from the dev monorepo (theapp), but PRs target the subrepo
echo "→ Creating worktree: $WORKTREE ($BRANCH)"
cd "$DEV_REPO"
git worktree add "$WORKTREE" -b "$BRANCH" origin/main

# --- 2. Set up .venv ---
if [[ "$FULL_SYNC" == "true" ]]; then
    echo "→ Running uv sync in worktree (--full-sync)"
    (cd "$WORKTREE" && uv sync)
else
    echo "→ Symlinking .venv from main repo"
    ln -s "$DEV_REPO/.venv" "$WORKTREE/.venv"
fi

# --- 3. Write prompt to worktree (avoids shell escaping issues in tmux) ---
printf '%s' "$PROMPT" > "$WORKTREE/.task-prompt.txt"

# --- 4. Spawn Claude Code in tmux ---
echo "→ Spawning session: $SESSION"
tmux new-session -d -s "$SESSION" \
    -c "$WORKTREE" \
    "claude --model claude-opus-4-6 --dangerously-skip-permissions -p \"\$(cat .task-prompt.txt)\""

# --- 5. Register in active-tasks.json ---
echo "→ Registering task"
mkdir -p "$(dirname "$REGISTRY")"
python3 - <<PYEOF
import json, time
from pathlib import Path

registry_path = Path("$REGISTRY")
data = json.loads(registry_path.read_text()) if registry_path.exists() else {"tasks": []}

# Replace any existing entry with the same id
data["tasks"] = [t for t in data["tasks"] if t["id"] != "$TASK_ID"]
data["tasks"].append({
    "id":           "$TASK_ID",
    "repo":         "$TARGET_REPO",
    "repoDir":      "$REPO_DIR",
    "tmuxSession":  "$SESSION",
    "worktree":     "$WORKTREE",
    "branch":       "$BRANCH",
    "description":  "$DESCRIPTION",
    "startedAt":    int(time.time() * 1000),
    "status":       "running",
    "respawnCount": 0,
    "pr":           None
})

registry_path.write_text(json.dumps(data, indent=2))
print(f"  Registered {len(data['tasks'])} task(s) in registry.")
PYEOF

echo ""
echo "✓ Task spawned: $TASK_ID"
echo "  Repo:     $TARGET_REPO"
echo "  Session:  $SESSION"
echo "  Branch:   $BRANCH"
echo "  Worktree: $WORKTREE"
echo "  .venv:    $( [[ "$FULL_SYNC" == "true" ]] && echo "full sync" || echo "symlinked" )"
echo "  Monitor:  tmux capture-pane -t $SESSION -p"
