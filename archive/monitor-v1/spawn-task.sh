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

export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"

usage() {
    cat >&2 <<'EOF'
Usage: spawn-task.sh --repo <btcopilot|familydiagram> --task <task-id> --description <desc> [--branch <branch>] [--issue <number>] [--full-sync]
       Prompt is read from stdin.

Options:
  --repo         Target repo (btcopilot or familydiagram) — where PRs land
  --task         Task identifier (used for worktree, branch, tmux session)
  --description  Short description for the task registry
  --branch       Custom branch name (default: feat/<task-id>)
  --issue        GitHub issue number in theapp repo (enables cross-repo linking)
  --full-sync    Run 'uv sync' in worktree instead of symlinking .venv
EOF
    exit 1
}

TASK_ID=""
DESCRIPTION=""
BRANCH=""
TARGET_REPO=""
FULL_SYNC=false
ISSUE_NUMBER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)        TARGET_REPO="$2"; shift 2 ;;
        --task)        TASK_ID="$2";     shift 2 ;;
        --description) DESCRIPTION="$2"; shift 2 ;;
        --branch)      BRANCH="$2";      shift 2 ;;
        --issue)       ISSUE_NUMBER="$2"; shift 2 ;;
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
WORKTREES_DIR="$HOME/.openclaw/workspace-hurin/${TARGET_REPO}-worktrees"
WORKTREE="$WORKTREES_DIR/$TASK_ID"
SESSION="claude-$TASK_ID"
REGISTRY="$DEV_REPO/.clawdbot/active-tasks.json"

# Read prompt from stdin
PROMPT=$(cat)
[[ -z "$PROMPT" ]] && { echo "Error: No prompt provided on stdin." >&2; exit 1; }

# Read repo-specific CLAUDE.md for context
REPO_CONTEXT=""
if [[ -f "$REPO_DIR/CLAUDE.md" ]]; then
    REPO_CONTEXT=$(head -100 "$REPO_DIR/CLAUDE.md")
fi

# --- 1. Create git worktree in the TARGET repo (btcopilot or familydiagram) ---
# Each nested repo has its own .git — worktrees go there so changes land on the right branch.
echo "→ Creating worktree: $WORKTREE ($BRANCH)"
mkdir -p "$WORKTREES_DIR"
cd "$REPO_DIR"
# Detect default branch (origin/main or origin/master)
DEFAULT_BRANCH="$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/||')"
DEFAULT_BRANCH="${DEFAULT_BRANCH:-origin/main}"

# Clean up stale worktree/branch from previous failed runs
if [[ -d "$WORKTREE" ]]; then
    echo "→ Removing stale worktree: $WORKTREE"
    git worktree remove "$WORKTREE" --force 2>/dev/null || rm -rf "$WORKTREE"
fi
git worktree prune 2>/dev/null
if git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null; then
    echo "→ Deleting stale local branch: $BRANCH"
    git branch -D "$BRANCH" 2>/dev/null
fi

git worktree add "$WORKTREE" -b "$BRANCH" "$DEFAULT_BRANCH"

# --- 2. Set up .venv (symlink from the monorepo root) ---
if [[ "$FULL_SYNC" == "true" ]]; then
    echo "→ Running uv sync in worktree (--full-sync)"
    (cd "$WORKTREE" && uv sync)
else
    echo "→ Symlinking .venv from main repo"
    ln -s "$DEV_REPO/.venv" "$WORKTREE/.venv"
fi

# --- 3. Write prompt to worktree (avoids shell escaping issues in tmux) ---
# Append delivery instructions so Claude commits, pushes, and creates a PR.
cat > "$WORKTREE/.task-prompt.txt" <<TASKEOF
$PROMPT

## Project Context (auto-injected from ${TARGET_REPO}/CLAUDE.md)

${REPO_CONTEXT}

---

## Delivery Instructions (MANDATORY)

After completing the code changes above, you MUST do all of the following:

1. **Commit** all changes on this branch (\`$BRANCH\`) with a descriptive message.
2. **Push** the branch to origin: \`git push -u origin $BRANCH\`
3. **Create a PR** against master using \`gh pr create\` with a clear title and description.

$(if [[ -n "$ISSUE_NUMBER" ]]; then echo "4. In the PR description body, include on its own line: \`Closes patrickkidd/theapp#${ISSUE_NUMBER}\`"; fi)

Do NOT stop after editing files. The task is NOT complete until the PR is created.

## PROHIBITED ACTIONS — NEVER DO THESE:

- **NEVER merge any PR** — no \`gh pr merge\`, no merge buttons, no merge commits. Only Patrick merges.
- **NEVER push to master/main** — only push to your feature branch (\`$BRANCH\`).
- **NEVER delete branches** — only Patrick deletes branches.
- **NEVER close issues** — only Patrick closes issues.
- This is a PRODUCTION SYSTEM with paying subscribers. Unauthorized merges can break production.
TASKEOF

# --- 4. Spawn Claude Code in tmux ---
# Write an init script into the worktree to avoid shell escaping nightmares in tmux.
# Uses hurin-bot GitHub token so PRs are created by patrickkidd-hurin (not patrickkidd).
TASK_LOG="$HOME/.openclaw/monitor/task-logs/${TASK_ID}.log"
BOT_TOKEN="$(cat "$HOME/.openclaw/monitor/hurin-bot-token")"

cat > "$WORKTREE/.task-run.sh" <<RUNEOF
#!/bin/bash
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT
export GH_TOKEN="$BOT_TOKEN"
export PATH="/opt/homebrew/bin:\$HOME/.local/bin:\$PATH"
git config credential.helper '!f() { echo protocol=https; echo host=github.com; echo username=patrickkidd-hurin; echo "password=\$GH_TOKEN"; }; f'
echo "[START] \$(date)" > "$TASK_LOG"
claude --model claude-opus-4-6 --dangerously-skip-permissions --verbose --output-format stream-json -p "\$(cat .task-prompt.txt)" >> "$TASK_LOG" 2>&1
echo "[EXIT] code=\$? \$(date)" >> "$TASK_LOG"
RUNEOF
chmod +x "$WORKTREE/.task-run.sh"

echo "→ Spawning session: $SESSION (log: $TASK_LOG)"
tmux new-session -d -s "$SESSION" -c "$WORKTREE" "bash .task-run.sh"

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
    "maxMinutes":   120,
    "pr":           None,
    "issueNumber":  int("$ISSUE_NUMBER") if "$ISSUE_NUMBER" else None
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
