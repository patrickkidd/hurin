# TOOLS.md - Local Environment

## Machine

- **Hardware:** Mac Mini M4, 16GB RAM
- **OS:** macOS (Darwin/ARM64)
- **Shell:** zsh

## Project Location

- **Monorepo:** ~/Projects/theapp
- **Backend:** ~/Projects/theapp/btcopilot/
- **Frontend:** ~/Projects/theapp/familydiagram/

## Tech Stack

- **Python:** 3.11, managed via uv workspace with shared .venv at root
- **Frontend:** PyQt5, QML, C++/SIP extensions
- **Backend:** Flask, PostgreSQL, Celery, SQLAlchemy
- **AI/ML:** Gemini, OpenAI, ChromaDB (RAG), SARF clinical model
- **Package manager:** uv (not pip)

## Your Team (2-tier architecture)

- **hurin** (you) — Orchestrator. Sonnet 4.6. Holds project/business context (MVP dashboard, decision log, GitHub issues). Writes task-scoped prompts describing the **what** and **why**.
- **Claude Code subprocesses** — The coders. Opus 4.6. Spawned in git worktrees via `spawn-task.sh`. Each one reads the repo's CLAUDE.md files and figures out the **how** autonomously.

### Context Separation

| | hurin (orchestrator) | Claude Code (coding agents) |
|---|---|---|
| **Reads** | MVP_DASHBOARD.md, decisions/log.md, GitHub issues/project board, architecture-level docs | CLAUDE.md files (root + per-package), code, tests, as-builts |
| **Decides** | What to build, why, task priority, when to ship | How to implement, which patterns, which files to change |
| **Writes** | Task-scoped prompts, status updates, PR reviews | Code, tests, PRs |

## Spawning and Monitoring Commands

### Spawn a task
```bash
spawn-task.sh --repo <btcopilot|familydiagram> --task <task-id> --description "<short desc>" <<'PROMPT'
<your prompt here>
PROMPT
```

Options:
- `--repo <name>` — target repo where PRs land (required: btcopilot or familydiagram)
- `--branch <name>` — custom branch name (default: `feat/<task-id>`)
- `--full-sync` — run `uv sync` in worktree instead of symlinking .venv (for dependency changes)

### Monitor tasks
```bash
tasks.sh              # Dashboard: all active tasks + last 20 lines of output
tasks.sh -l           # Just list active tasks
tasks.sh <task-id>    # Attach to task's tmux session (read-only)
```

### Direct tmux access
```bash
tmux capture-pane -t claude-<task-id> -p   # Capture current output
tmux send-keys -t claude-<task-id> "message" Enter   # Send mid-task redirect
tmux list-sessions                          # See all sessions
```

### Check monitoring
```bash
cat ~/.openclaw/monitor/monitor.log         # Monitor script output
ls ~/.openclaw/monitor/failures/            # Failure logs for Ralph Loop
```

## System As-Built

Full documentation of this agent setup, file layout, config, workflow, and admin procedures:

`https://github.com/patrickkidd/hurin/blob/main/adrs/ADR-0001-agent-swarm.md`

Local clone (if checked out): `~/Projects/hurin/adrs/ADR-0001-agent-swarm.md`

Read this when asked about how the system works or how to change something.

## GitHub Project Board

- **Project:** Family Diagram #4 — https://github.com/users/patrickkidd/projects/4
- **Project ID:** `PVT_kwHOABjmWc4BP0PU`
- **Sync scripts:** `~/workspace-hurin/scripts/gh-project-sync.sh` and `gh-project-find-item.sh`

**Workflow — always do this when spawning or completing tasks:**
1. When spawning a task → `gh-project-find-item.sh <repo> <issue>` then `gh-project-sync.sh <item_id> --status "In Progress" --owner Hurin`
2. When a PR merges → `gh-project-sync.sh <item_id> --status Done`
3. Items I'm investigating → `--owner Hurin`

## Communication

- Discord guild for team coordination
- #planning — where Patrick gives you tasks
- #reviews — where you report back with PR URLs and status updates
