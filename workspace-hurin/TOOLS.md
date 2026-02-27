# TOOLS.md - Local Environment

## Machine

- **Hardware:** Mac Mini M4, 16GB RAM
- **OS:** macOS (Darwin/ARM64)
- **Shell:** zsh

## Project Location

- **Monorepo:** `~/.openclaw/workspace-hurin/theapp/`
- **Backend:** `~/.openclaw/workspace-hurin/theapp/btcopilot/`
- **Frontend:** `~/.openclaw/workspace-hurin/theapp/familydiagram/`

## Tech Stack

- **Python:** 3.11, managed via uv workspace with shared .venv at root
- **Frontend:** PyQt5, QML, C++/SIP extensions
- **Backend:** Flask, PostgreSQL, Celery, SQLAlchemy
- **AI/ML:** Gemini, OpenAI, ChromaDB (RAG), SARF clinical model
- **Package manager:** uv (not pip)

## Your Team (2-tier architecture)

- **hurin** (you) — Router. Haiku 4.5 (API, ~pennies/day). Holds project/business context (MVP dashboard, decision log, GitHub issues). Routes all intelligence work to CC. Never reasons about code.
- **Claude Code** — The brain. Opus 4.6 via Claude CLI on Max plan — **$0 marginal cost for all CC work**. Handles planning, investigation, diagnosis, and implementation.

## Two Operating Modes

Both modes run CC through the `claude` CLI binary on the Max plan. **$0 cost for all intelligence work.**

### Mode 1: Sync Planning / Recon (`exec` + `claude -p`)

For questions, investigations, and planning where Patrick expects a reply in Discord.

```bash
exec(command="cd ~/.openclaw/workspace-hurin/theapp && claude -p --model opus --dangerously-skip-permissions <<'PROMPT'\nYour question or investigation request here.\nPROMPT")
```

- Blocks your turn — typing indicator stays active in Discord
- CC's response comes back in your `exec` result — relay verbatim to Patrick
- **$0 cost** (Max plan via CLI)
- For long prompts, write to a temp file first:
  ```bash
  exec(command="cat > /tmp/cc-prompt.txt <<'PROMPT'\n...\nPROMPT")
  exec(command="cd ~/.openclaw/workspace-hurin/theapp && claude -p --model opus --dangerously-skip-permissions < /tmp/cc-prompt.txt")
  ```

**Use for:** "How should we implement X?", "What's causing Y?", plan proposals, failure diagnosis (Ralph Loop)

### Mode 2: Background Implementation (`spawn-task.sh`)

For implementation tasks that produce PRs. Fire-and-forget with tmux monitoring.

```bash
exec(command="spawn-task.sh --repo <btcopilot|familydiagram> --task <task-id> --description '<short desc>' <<'PROMPT'\n<your prompt here>\nPROMPT")
```

Options:
- `--repo <name>` — target repo where PRs land (required: btcopilot or familydiagram)
- `--branch <name>` — custom branch name (default: `feat/<task-id>`)
- `--full-sync` — run `uv sync` in worktree instead of symlinking .venv (for dependency changes)

**Use for:** Feature implementation, bug fixes, refactors — anything that ends in a PR

### Choosing the Right Mode

| Scenario | Mode | Why |
|---|---|---|
| Patrick asks "how should we do X?" | 1 (sync) | He expects a reply in the conversation |
| Patrick asks "investigate X" | 1 (sync) | He expects a report back |
| "Implement X" with clear requirements | 2 (background) | Fire-and-forget, PR expected |
| Ralph Loop failure diagnosis | 1 (sync) | Need CC's corrected prompt back in your context to respawn |
| Complex investigation or multi-step analysis | 1 (sync) | CC does the work, relay results |

**All modes cost $0.** No need to consider cost when choosing.

## Session Resumption

The `claude` CLI supports resuming previous sessions with `--resume <session-id>` or `--continue` (most recent session in the same directory).

**Use case: Multi-turn recon.** When Patrick asks a follow-up question about something CC already investigated, resume the session so CC has full context:

```bash
# First call — save the session ID from CC's output
exec(command="cd ~/.openclaw/workspace-hurin/theapp && claude -p --model opus --dangerously-skip-permissions --output-format json <<'PROMPT'\nInvestigate the auth system...\nPROMPT")
# Parse session_id from JSON output

# Follow-up — resume with context
exec(command="cd ~/.openclaw/workspace-hurin/theapp && claude -p --model opus --dangerously-skip-permissions --resume <session-id> <<'PROMPT'\nPatrick's follow-up question here\nPROMPT")
```

This keeps CC's full investigation context across multiple questions without re-reading the codebase.

## Monitoring Commands

### Active tmux sessions (mode 2)
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

### Failure logs
```bash
cat ~/.openclaw/monitor/monitor.log         # Monitor script output
ls ~/.openclaw/monitor/failures/            # Failure logs for Ralph Loop
```

## Discord Channels

- **#planning** — sync conversations with Patrick. Questions, plan summaries, task updates.
- **#reviews** — where you report PR URLs and review results
- **#co-founder** — automated strategic briefings from the co-founder system (cron-driven, see ADR-0004).

## GitHub Project Board

- **Project:** Family Diagram #4 — https://github.com/users/patrickkidd/projects/4
- **Project ID:** `PVT_kwHOABjmWc4BP0PU`
- **Sync scripts:** `~/workspace-hurin/scripts/gh-project-sync.sh` and `gh-project-find-item.sh`

**Workflow — always do this when spawning or completing tasks:**
1. When spawning a task → `gh-project-find-item.sh <repo> <issue>` then `gh-project-sync.sh <item_id> --status "In Progress" --owner Hurin`
2. When a PR merges → `gh-project-sync.sh <item_id> --status Done`
3. Items I'm investigating → `--owner Hurin`

## System As-Built

Full documentation of this agent setup, file layout, config, workflow, and admin procedures:

`https://github.com/patrickkidd/hurin/blob/main/adrs/ADR-0001-agent-swarm.md`

Local clone (if checked out): `~/Projects/hurin/adrs/ADR-0001-agent-swarm.md`

Read this when asked about how the system works or how to change something.
