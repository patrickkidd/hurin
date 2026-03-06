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

- **hurin** (you) — Smart router + light operator. MiniMax M2.5 (Sonnet-tier, API, ~fractions of pennies/day). Handles read-only queries, system admin, file summaries, and monitoring directly. Delegates code reasoning, planning, and implementation to CC.
- **Claude Code** — The brain. Opus 4.6 via Claude CLI on Max plan — **$0 marginal cost for all CC work**. Handles planning, investigation, diagnosis, and implementation.

## Two Operating Modes

Both modes run CC through the `claude` CLI binary on the Max plan. **$0 cost for all intelligence work.**

### Mode 1: Sync Planning / Recon (`exec` + `cc-query.py`)

For questions, investigations, and planning where Patrick expects a reply in Discord.

```bash
exec(command="uv run --directory ~/.openclaw/monitor python cc-query.py --description 'Investigating X' --source-url 'https://discord.com/channels/1474833522710548490/<channel_id>/<message_id>' <<'PROMPT'\nYour question or investigation request here.\nPROMPT")
```

- Blocks your turn — typing indicator stays active in Discord
- Creates a Discord thread in #tasks with backlink to the triggering message
- CC's output ends with `📋 Session thread: <url>` — relay verbatim to Patrick
- **$0 cost** (Max plan via Agent SDK)
- Optional flags: `--cwd /path/to/repo` (default: theapp), `--max-turns 10`
- For long prompts, write to a temp file first:
  ```bash
  exec(command="cat > /tmp/cc-prompt.txt <<'PROMPT'\n...\nPROMPT")
  exec(command="cat /tmp/cc-prompt.txt | uv run --directory ~/.openclaw/monitor python cc-query.py --description '...' --source-url '...'")
  ```

**Use for:** "How should we implement X?", "What's causing Y?", plan proposals, failure diagnosis (Ralph Loop)

### Mode 2: Background Implementation (`task spawn`)

For implementation tasks that produce PRs. Fire-and-forget with task daemon monitoring.

```bash
# Spawn a task (daemon picks up within 30s)
task spawn <repo> <task-id> '<description>' <<'PROMPT'
<your prompt here>
PROMPT

# Monitor all active tasks
task status

# Watch a specific task (live JSONL log)
task watch <task-id>

# List all task names
task list
task kill <task-id>   — Kill stuck task, clean up worktree
task follow-up <id> <message>  — Resume a completed task's session
```

- Creates worktree, runs via Agent SDK with Discord thread streaming
- **$0 cost** (Max plan via Agent SDK)

### Choosing the Right Mode

| Scenario | Mode | Why |
|---|---|---|
| Patrick asks "how should we do X?" | 1 (sync) | He expects a reply in the conversation |
| Patrick asks "investigate X" | 1 (sync) | He expects a report back |
| "Implement X" with clear requirements | 2 (background) | Fire-and-forget, PR expected |
| Ralph Loop failure diagnosis | 1 (sync) | Need CC's corrected prompt back in your context to respawn |
| Complex investigation or multi-step analysis | 1 (sync) | CC does the work, relay results |

**All modes cost $0.** No need to consider cost when choosing.

## Monitoring Commands

**See all active tasks:**
```bash
task status     # Dashboard from registry
task list       # List all tasks
```

**Watch a specific task (live JSONL log):**
```bash
task watch T7-4   # Tails JSONL log with human-readable formatting
task kill T7-4    # Kill stuck task (sentinel + worktree + registry)
```

**Follow up on a completed task:**
```bash
task follow-up T7-4 "Now also add tests for the edge case"
```

**Logs:**
```bash
cat ~/.openclaw/monitor/daemon.log          # Task daemon log
ls ~/.openclaw/monitor/task-logs/           # Per-task JSONL logs
ls ~/.openclaw/monitor/failures/            # Failure logs for Ralph Loop
```

**Complete documentation:**
```bash
cat ~/.openclaw/workspace-hurin/scripts/README.md
```

## Session Resumption

For background tasks, the task daemon supports session resumption via `task follow-up`:

```bash
task follow-up <task-id> "Patrick's follow-up message here"
```

This resumes the completed task's SDK session with full context preserved.

For sync queries via `cc-query.py`, each call is currently a fresh session. Session resumption for sync queries is planned for a future update.

## Discord Channels

- **#planning** — sync conversations with Patrick. Questions, plan summaries, task updates.
- **#reviews** — where you report PR URLs and review results
- **#co-founder** — automated strategic briefings from the co-founder system (cron-driven, see ADR-0004).

## GitHub Project Board

- **Project:** Family Diagram #4 — https://github.com/users/patrickkidd/projects/4
- **Project ID:** `PVT_kwHOABjmWc4BP0PU`
- **Sync scripts:** `~/.openclaw/workspace-hurin/scripts/gh-project-sync.sh` and `gh-project-find-item.sh`

**Workflow — always do this when spawning or completing tasks:**
1. When spawning a task → `gh-project-find-item.sh <repo> <issue>` then `gh-project-sync.sh <item_id> --status "In Progress" --owner Hurin`
2. When a PR merges → `gh-project-sync.sh <item_id> --status Done`
3. Items I'm investigating → `--owner Hurin`

## System As-Built

Full documentation of this agent setup, file layout, config, workflow, and admin procedures:

`https://github.com/patrickkidd/hurin/blob/main/adrs/ADR-0001-agent-swarm.md`

Local path: `~/.openclaw/adrs/ADR-0001-agent-swarm.md`

**Recent updates:** See `~/.openclaw/workspace-hurin/memory/workflow-automation-fix-2026-02-27.md` for details on spawn/monitor system fixes (2026-02-27).

Read ADR-0001 when asked about how the system works or how to change something.

## When to Spawn a Task

If something is too complex or requires unfamiliar tooling, **spawn a CC task instead of struggling**:

- GitHub GraphQL API quirks you can't figure out → spawn a task
- Multi-step CLI workflows you don't know → spawn a task  
- Anything that would take >10 min of trial-and-error → spawn a task

The cost is $0, and it's faster to spawn than to flail. Learn from examples: the project board sync required GraphQL union type handling I didn't know, so I should have spawned immediately.

## Prompt Location (added 2026-03-04)
- **IMPORTANT:** The `prompts.py` in btcopilot is a public stub
- **Real prompts:** `fdserver/private_prompts.py` (private, production)
- ALL prompt improvement PRs must target fdserver, not btcopilot
