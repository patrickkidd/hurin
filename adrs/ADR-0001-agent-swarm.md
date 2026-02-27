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
  ├── hurin (Haiku 4.5) — dumb router, no intelligence
  │     └── exec: claude -p --model opus  ($0, Max plan CLI)
  │           ├── Mode 1: sync (blocks, reply in Discord)
  │           └── Mode 2: background (spawn-task.sh, PR expected)
  │
  └── Co-Founder System (cron, no hurin)
        └── co-founder.sh <lens> → claude -p  ($0, Max plan CLI)
              ├── 9 strategic lenses on rotating schedule
              ├── Journal memory (last 150 lines fed back each run)
              └── Posts to #co-founder Discord channel
```

> **Important:** hurin is a dumb pipe, not an orchestrator. It does not read files, reason about code, or make decisions. All intelligence is delegated to CC via `exec` + `claude -p`. See [ADR-0003](ADR-0003-hurin-lockdown-validation.md) for the lockdown rationale and validation.

### Context Isolation Model

| | hurin (router) | Claude Code (brain) |
|---|---|---|
| **Model** | Haiku 4.5 (API, ~$0.01-0.03/msg) | Opus 4.6 (Max plan CLI, $0) |
| **Thinking** | Off | N/A (CC manages its own) |
| **Tools** | `exec` only (+ session read-only) | Full codebase access |
| **Reads** | Nothing — routes to CC | CLAUDE.md files, code, tests, project state |
| **Decides** | Nothing — routes to CC | Everything: plans, priorities, implementation |
| **Writes** | Nothing — relays CC output | Code, tests, PRs |

hurin receives Patrick's message and passes it verbatim to CC via `exec` + `claude -p`. CC does all the work. hurin relays CC's response verbatim.

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
  co-founder/                   # Co-founder strategic briefing system (ADR-0004)
    config.sh                  # Paths, channel ID, settings
    co-founder.sh              # Main runner (lens → CC → journal → Discord)
    discord-post.sh            # Discord API posting with message splitting
    journal.md                 # Persistent memory (append-only, 1000 line cap)
    lenses/                    # 9 strategic lens prompts
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
~/.openclaw/workspace-hurin/theapp/    # Monorepo (moved from ~/Projects/theapp)
  .clawdbot/                           # Gitignored. Agent task tracking.
    active-tasks.json                   # Registry of active Claude Code sessions
  .github/
    PULL_REQUEST_TEMPLATE.md            # Summary, screenshots, testing, checklist

~/.openclaw/adrs/                      # ADRs (this repo)
  ADR-0001-agent-swarm.md              # This file (as-built)
  ADR-0001-status.md                   # Gap analysis tracker
  ADR-0003-hurin-lockdown-validation.md # Lockdown rationale + cost experiments
  ADR-0004-co-founder-system.md        # Co-founder strategic briefing system
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
| #claude | 1476629409980219533 | hurin |
| #co-founder | 1476739270663213197 | hurin (replies only; posts via direct API) |

beren/tuor Discord accounts archived. #beren-work and #tuor-work channels no longer bound.

## Key Config Settings (openclaw.json)

Tuned for 16GB RAM:

```json
"maxConcurrent": 2,
"subagents": { "maxConcurrent": 4 },
"contextTokens": 64000,
"thinkingDefault": "off"
```

- `maxConcurrent: 2` — prevents swap thrashing
- `contextTokens: 64000` — sufficient for router context
- `thinkingDefault: "off"` — hurin doesn't need reasoning, saves ~50% on output tokens
- `sandbox: { "mode": "off" }` — local trusted machine
- Agent-to-agent comms enabled (hurin only)
- **hurin tools restricted to:** `exec`, `sessions_list`, `sessions_history`, `session_status`
- `read`, `write`, `edit` removed — see [ADR-0003](ADR-0003-hurin-lockdown-validation.md)

## Workflow: Patrick → Code → PR

1. Patrick posts a task in #planning
2. hurin routes message to CC via `exec` + `claude -p` (Mode 1: sync)
3. CC reads project context, proposes plan, relays via hurin
4. On Patrick's approval, hurin runs `spawn-task.sh --task {id} --description "..."` with prompt on stdin (Mode 2: background)
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
3. hurin delegates diagnosis to CC via `exec` + `claude -p` (Mode 1)
4. CC reads the failure log, diagnoses root cause, writes corrected prompt
5. hurin takes CC's corrected prompt and respawns via `spawn-task.sh` (max 3 attempts)
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
| `co-founder.sh` | 9 schedules | Strategic briefings via rotating lenses. See [ADR-0004](ADR-0004-co-founder-system.md). |

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
Manual cleanup: `cd ~/.openclaw/workspace-hurin/theapp && git worktree remove ~/.openclaw/workspace-hurin/theapp-worktrees/{task}`

## Consequences

### Positive

- Simpler architecture: dumb router + one brain
- All intelligence at $0 via Max plan CLI — hurin API cost is ~$0.01-0.03/msg
- Structural enforcement: hurin literally cannot read/write/edit files (tools removed)
- Thinking disabled: no wasted output tokens on router reasoning
- Ralph Loop: systematic failure recovery with prompt improvement
- Automated code reviews catch issues before Patrick sees the PR
- Fewer moving parts to break, configure, and maintain

### Negative

- hurin cannot self-correct if CC call fails (e.g. wrong path) — limited to `exec` only
- hurin cannot read its own workspace files — relies on system prompt context
- Session context growth increases per-message cost (mitigated by 15-min idle reset)

### Risks

- Discord bot token is embedded in openclaw.json (plaintext). Don't commit this file.
- `--dangerously-skip-permissions` on Claude Code subprocesses — appropriate for trusted local machine
- `review-prs.sh` uses `claude -p` which costs API tokens per review
- The monitoring scripts use `gh` CLI — requires `gh auth login` to be done first

## Related

- [ADR-0003: Hurin Lockdown & Validation](ADR-0003-hurin-lockdown-validation.md) — tool restrictions, thinking-off, and cost validation experiments
- [ADR-0004: Co-Founder System](ADR-0004-co-founder-system.md) — scheduled strategic briefings via rotating lenses
