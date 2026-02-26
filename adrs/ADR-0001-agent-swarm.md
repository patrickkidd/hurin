# ADR-0001: OpenClaw 2-Tier Agent Swarm Setup

**Status:** Accepted

**Date:** 2026-02-26

**Deciders:** Patrick

**Supersedes:** [ADR-0001 3-tier version (archived)](archive/ADR-0001-agent-swarm_2026-02-25_3tier.md)

## Context

The initial 3-tier setup (hurin → beren/tuor → Claude Code) had a Haiku intelligence bottleneck at the coordinator layer. Analysis showed that prompt quality is the single highest-leverage variable, and having Haiku 4.5 write coding prompts was a net negative compared to having the Sonnet orchestrator spawn coding agents directly.

Elvis Sun's article demonstrates high productivity with a simpler 2-tier architecture (orchestrator → coding agents). We collapsed to match that pattern.

Reference article: [elvis-agent-swarm-article.md](elvis-agent-swarm-article.md) (Elvis Sun, Feb 23 2026)
Gap analysis & status: [ADR-0001-status.md](ADR-0001-status.md)

## Decision

A 2-tier agent architecture running on the Mac Mini via OpenClaw:

```
Patrick (Discord)
  └── hurin (Sonnet 4.6) — orchestrator, holds project/business context
        ├── claude --model claude-opus-4-6  (coding agent in worktree)
        ├── claude --model claude-opus-4-6  (coding agent in worktree)
        └── ...  (3-4 concurrent max)
```

### Context Isolation Model

| | hurin (orchestrator) | Claude Code (coding agents) |
|---|---|---|
| **Reads** | MVP_DASHBOARD.md, decisions/log.md, GitHub issues/project board | CLAUDE.md files (root + per-package), code, tests, as-builts |
| **Decides** | What to build, why, task priority | How to implement, which patterns, which files |
| **Writes** | Task-scoped prompts, status updates | Code, tests, PRs |

hurin writes prompts describing the **what** and **why**. The coding agent reads the repo's CLAUDE.md system and figures out the **how**.

### Worktree Strategy

Default: symlink `.venv` from main repo into worktrees (0 bytes, 0 seconds).
For dependency changes: `spawn-task.sh --full-sync` runs `uv sync` (fast via uv's hardlink cache).
Capacity: 3-4 concurrent worktrees easily fit on 16GB.

## File Layout

### OpenClaw Config

```
~/.openclaw/
  openclaw.json               # Agent config (hurin only), Discord, bindings
  workspace-hurin/             # hurin's workspace
    SOUL.md                    # 2-tier orchestrator role, Ralph Loop, definition of done
    AGENTS.md                  # Standard OpenClaw agent conventions
    USER.md                    # Patrick's info, project overview
    TOOLS.md                   # Local environment, 2-tier team structure, commands
    IDENTITY.md                # hurin, 🏰
    HEARTBEAT.md               # (empty — hurin is event-driven via check-agents.py pings)
    memory/
      prompt-patterns.md       # Ralph Loop memory — what works/fails per task type
  monitor/
    spawn-task.sh              # Spawn Claude Code in worktree+tmux, register task
    check-agents.py            # Cron monitoring (tmux/PR/CI/review), Ralph Loop alerts
    tasks.sh                   # Task dashboard and tmux attach
    review-prs.sh              # Automated Claude code review (cron, every 15 min)
    failures/                  # Captured tmux output from failed sessions
    monitor.log                # check-agents.py run log
    review.log                 # review-prs.sh run log
    cron.log                   # cron stdout/stderr
  archive/                     # Archived beren/tuor configs
    workspace-beren/
    workspace-tuor/
    agents-beren/
    agents-tuor/
  agents/
    hurin/agent/auth-profiles.json   # Anthropic API key
```

### Project Files

```
~/Projects/theapp/
  .clawdbot/                  # Gitignored. Agent task tracking.
    active-tasks.json          # Registry of active Claude Code sessions
  .github/
    PULL_REQUEST_TEMPLATE.md   # Summary, screenshots, testing, checklist
  adrs/
    ADR-0001-agent-swarm.md    # This file
    ADR-0001-status.md         # Gap analysis tracker
    archive/
      ADR-0001-agent-swarm_2026-02-25_3tier.md  # Previous 3-tier version

~/Projects/theapp-worktrees/   # Git worktrees for active tasks
  {task-id}/                   # One per active Claude Code job
```

## Discord Setup

- **Guild:** 1474833522710548490
- **Authorized user (Patrick):** 1237951508742672431
- **Bot account:** hurin (single bot, token in openclaw.json)
- **Channel bindings:**

| Channel | ID | Bot |
|---------|-----|-----|
| #planning | 1475607956698562690 | hurin |
| #reviews | 1475608130040762482 | hurin |

beren/tuor Discord accounts archived. #beren-work and #tuor-work channels no longer bound.

## Key Config Settings (openclaw.json)

Tuned for 16GB RAM:

```json
"maxConcurrent": 2,
"subagents": { "maxConcurrent": 4 },
"contextTokens": 64000
```

- `maxConcurrent: 2` — prevents swap thrashing
- `contextTokens: 64000` — sufficient for orchestrator context
- `sandbox: { "mode": "off" }` — local trusted machine
- Agent-to-agent comms enabled (hurin only)
- hurin has `sessions_spawn` for potential future use

## Workflow: Patrick → Code → PR

1. Patrick posts a task in #planning (or hurin picks up from GitHub issues)
2. hurin reads project context (MVP dashboard, decision log, issue details)
3. hurin crafts a task-scoped prompt — what to build, why, done condition
4. hurin runs `spawn-task.sh --task {id} --description "..."` with prompt on stdin
5. `spawn-task.sh` creates worktree, symlinks .venv, spawns Claude Code in tmux, registers task
6. Claude Code reads the repo's CLAUDE.md files, implements, creates PR
7. `check-agents.py` (every 10 min) monitors: tmux alive? PR created? CI? Review status?
8. `review-prs.sh` (every 15 min) posts automated Claude review on new PRs
9. On success: hurin notifies Patrick in #reviews with PR URL
10. On failure: Ralph Loop — hurin reads failure log, rewrites prompt, respawns

### Ralph Loop (Failure Recovery)

When `check-agents.py` detects a dead session with no PR:
1. Captures last 100 lines of tmux output to `~/.openclaw/monitor/failures/{task}.log`
2. Pings hurin with failure log path + context
3. hurin reads the failure, consults `memory/prompt-patterns.md`
4. hurin rewrites the prompt addressing the failure mode
5. hurin respawns via `spawn-task.sh` (max 3 attempts)
6. hurin logs the failure+fix pattern to `memory/prompt-patterns.md`

### Automated Code Review

`review-prs.sh` runs every 15 minutes:
1. Lists open PRs without `reviewed-by-claude` label
2. Gets diff via `gh pr diff`
3. Runs `claude -p` with a review prompt (bugs, security, test gaps)
4. Posts review as PR comment via `gh pr review --comment`
5. Adds `reviewed-by-claude` label to prevent re-reviewing

Future: Gemini Code Assist (free GitHub App) for a second reviewer.

## Monitoring

Two complementary cron scripts:

| Script | Frequency | Purpose |
|--------|-----------|---------|
| `check-agents.py` | Every 10 min | Task health: tmux alive, PR status, CI, reviews. Pings hurin on failures. |
| `review-prs.sh` | Every 15 min | Automated code review on new PRs. |

hurin is event-driven (not polling). Only wakes up when pinged by `check-agents.py`.

## Administration

### Restarting the gateway

```bash
openclaw gateway restart
```

### Verifying health

```bash
openclaw doctor
openclaw agents list              # Should show only hurin
openclaw channels status --probe  # Live Discord connectivity
```

### Task management

```bash
spawn-task.sh --task <id> --description "<desc>" <<< "prompt"   # Spawn
tasks.sh                     # Dashboard
tasks.sh <task-id>           # Attach to tmux (read-only)
tasks.sh -l                  # List only
```

### Cleaning up

Worktrees for "done" tasks are automatically cleaned up by `check-agents.py`.
Manual cleanup: `cd ~/Projects/theapp && git worktree remove ~/Projects/theapp-worktrees/{task}`

## Consequences

### Positive

- Simpler architecture: one orchestrator, direct to coding agents
- No Haiku intelligence bottleneck at the prompting layer
- Ralph Loop: systematic failure recovery with prompt improvement
- Automated code reviews catch issues before Patrick sees the PR
- Context isolation: orchestrator holds business context, coding agents hold code context via CLAUDE.md
- Fewer moving parts to break, configure, and maintain

### Negative

- Less parallelism in prompt crafting (hurin is serial vs beren+tuor parallel)
- hurin must context-switch between backend and frontend tasks
- Worktrees accumulate if cleanup fails

### Risks

- Discord bot token is embedded in openclaw.json (plaintext). Don't commit this file.
- `--dangerously-skip-permissions` on Claude Code subprocesses — appropriate for trusted local machine
- `review-prs.sh` uses `claude -p` which costs API tokens per review
- The monitoring scripts use `gh` CLI — requires `gh auth login` to be done first
