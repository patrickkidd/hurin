# TOOLS.md - Beren's Environment

## Machine

- **Hardware:** Mac Mini M4, 16GB RAM
- **OS:** macOS (Darwin/ARM64)
- **Shell:** zsh

## Project Layout

- **Monorepo:** ~/Projects/theapp
- **Your domain:** ~/Projects/theapp/btcopilot/
- **Worktrees:** ~/Projects/theapp-worktrees/

## Tech Stack (Backend)

- **Python:** 3.11, uv workspace with shared .venv at root
- **Framework:** Flask
- **Database:** PostgreSQL, SQLAlchemy ORM
- **Task queue:** Celery
- **AI/ML:** Gemini, OpenAI, ChromaDB (RAG), SARF clinical model
- **Package manager:** uv (not pip, not pip3)
- **Running commands:** always `uv run python` / `uv run pytest` — never bare `python` or `pytest`

## Spawning Claude Code

Use `spawn-task.sh` — it creates the worktree, starts the tmux session, and registers
the task for monitoring in one atomic step. Pass the prompt via stdin.

```bash
~/.openclaw/monitor/spawn-task.sh \
  --agent beren \
  --task {task-id} \
  --description "brief description" <<'PROMPT'
Your full prompt here...
PROMPT
```

This replaces manually creating a worktree, starting tmux, and writing to active-tasks.json.
Do not do those steps separately — use the script.

## Monitoring tmux Sessions

```bash
# List sessions
tmux list-sessions

# Read current output (non-destructive)
tmux capture-pane -t claude-beren-{task} -p

# Redirect mid-task
tmux send-keys -t claude-beren-{task} "Stop. Do X instead." Enter

# Kill session
tmux kill-session -t claude-beren-{task}
```

## Worktree Cleanup

After a PR is merged:

```bash
git worktree remove ~/Projects/theapp-worktrees/{task-id}
```

## PR Creation

```bash
cd ~/Projects/theapp-worktrees/feat-{task}
gh pr create --fill
```

## Project Docs to Read Before Prompting

- `~/Projects/theapp/CLAUDE.md` — root conventions
- `~/Projects/theapp/btcopilot/CLAUDE.md` — backend-specific conventions

## Team

- **hurin** — your orchestrator. Sends you tasks, reviews PRs.
- **tuor** — frontend coordinator. Handles familydiagram/. Not your domain.
