# ADR-0001: OpenClaw 2-Tier Agent Swarm Setup

**Status:** Accepted

**Date:** 2026-02-26 (revised 2026-03-03)

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
  ├── hurin (MiniMax M2.5) — smart router + light operator
  │     ├── Mode 1: sync (exec + cc-query.py, blocks, reply in Discord)
  │     │     └── Agent SDK query() → Discord thread in #tasks ($0, Max plan)
  │     └── Mode 2: background (task spawn → task-daemon.py, PR expected)
  │           └── Agent SDK query() → worktree → PR ($0, Max plan)
  │
  ├── Task Daemon (LaunchAgent, ai.openclaw.taskdaemon)
  │     └── task-daemon.py — drains task-queue.json, runs SDK query()
  │           ├── Discord thread relay (live streaming to #tasks)
  │           ├── Live steering (thread replies → steer queue)
  │           ├── Session persistence (resume/follow-up)
  │           ├── Ralph Loop (auto-respawn, max 3x, with session resume)
  │           ├── PR detection, CI monitoring, project board sync
  │           └── Worktree lifecycle (create → symlink .venv → cleanup)
  │
  ├── Team Lead Daemon (LaunchAgent, ai.openclaw.teamlead)
  │     └── team-lead.py — see ADR-0006
  │
  └── Co-Founder System (cron, no hurin)
        └── co-founder.sh <lens> → claude -p  ($0, Max plan CLI)
              ├── 9 strategic lenses on rotating schedule
              ├── Journal memory (last 100 lines fed back each run)
              └── Posts to #co-founder Discord channel
```

> **Important:** hurin is a smart router with light operational capability. It handles read-only queries, system admin, and file summarization directly via `exec`. All code intelligence is delegated to CC via `cc-query.py` (Mode 1) or `task spawn` (Mode 2). See [ADR-0003](ADR-0003-hurin-lockdown-validation.md) for the lockdown rationale and tool restrictions.

### Context Isolation Model

| | hurin (router) | Claude Code (brain) |
|---|---|---|
| **Model** | MiniMax M2.5 ($0.30/$1.20 per MTok) | Opus 4.6 (Max plan CLI, $0) |
| **Thinking** | Off | N/A (CC manages its own) |
| **Tools** | `exec` only (+ session read-only) | Full codebase access |
| **Reads** | Simple queries via exec (git status, task list, logs) | CLAUDE.md files, code, tests, project state |
| **Decides** | Triage: handle directly or delegate to CC | Everything: plans, priorities, implementation |
| **Writes** | Nothing — relays CC output for code tasks | Code, tests, PRs |

hurin triages each message: handle directly if it's a simple query/admin task, delegate to CC if it requires code intelligence. CC does all code work. hurin relays CC's response verbatim.

### Worktree Strategy

Default: symlink `.venv` from main repo into worktrees (0 bytes, 0 seconds).
For dependency changes: `uv sync` (fast via uv's hardlink cache).
Capacity: 3-4 concurrent worktrees easily fit on 16GB.

## File Layout

### OpenClaw Config

```
~/.openclaw/
  openclaw.json               # Agent config (hurin only), Discord, bindings
  workspace-hurin/             # hurin's workspace
    SOUL.md                    # Smart router role, CC delegation, task thread handling
    AGENTS.md                  # Standard OpenClaw agent conventions
    USER.md                    # Patrick's info, project overview
    TOOLS.md                   # Local environment, 2-tier team structure, commands
    IDENTITY.md                # hurin, 🏰
    HEARTBEAT.md               # (empty — hurin is event-driven)
    memory/
  monitor/
    task-daemon.py             # Main task execution daemon (Agent SDK, async Python)
    cc-query.py                # Sync CC wrapper for hurin Mode 1 (Agent SDK)
    discord_relay.py           # Discord thread streaming (shared by daemon + cc-query)
    thread-followup.sh         # Maps Discord thread → task ID → task follow-up
    discord-react.sh           # Add/remove Discord reactions (brain emoji indicator)
    feedback.py                # Post-task outcome capture
    review-prs.sh              # Automated Claude code review (cron, every 15 min)
    task-queue.json            # Queue file (daemon drains every 30s)
    queue-prompts/             # Prompt files for queued tasks
    task-logs/                 # JSONL logs per task (<task-id>.log)
    task-events.jsonl          # Event stream (consumed by team-lead)
    kill-sentinels/            # Write <task-id>.kill to terminate a running task
    hurin-bot-token            # GitHub PAT for bot account (patrickkidd-hurin)
    discord-bot-token          # Discord bot token
    cron.log                   # cron stdout/stderr
    review.log                 # review-prs.sh run log
    daemon.log                 # task-daemon.py operational log
  team-lead/                   # Team lead daemon (ADR-0006)
    team-lead.py               # Main daemon (async Python, Agent SDK)
    config.py                  # Paths, thresholds, quiet hours, autonomy_tier
  co-founder/                  # Co-founder strategic briefing system (ADR-0004)
    config.sh                  # Paths, channel ID, settings
    co-founder.sh              # Main runner (lens → CC → journal → Discord)
    extract-actions-json.py    # Parse actions from briefing output
    discord-post.sh            # Discord API posting with message splitting
    journal.md                 # Persistent memory (append-only, 1000 line cap)
    lenses/                    # 9 strategic lens prompts
  launchagents/                # Copies of LaunchAgent plists (disaster recovery)
  adrs/                        # Architecture Decision Records
  archive/                     # Archived beren/tuor configs, monitor-v1
```

### Project Files

```
~/.openclaw/workspace-hurin/theapp/    # Monorepo (moved from ~/Projects/theapp)
  .clawdbot/                           # Gitignored. Agent task tracking.
    active-tasks.json                   # Registry of active Claude Code sessions

~/.openclaw/adrs/                      # ADRs (this repo)
  ADR-0001-agent-swarm.md              # This file (as-built)
  ADR-0001-status.md                   # Gap analysis tracker
  ADR-0003-hurin-lockdown-validation.md # Lockdown rationale + cost experiments
  ADR-0004-co-founder-system.md        # Co-founder strategic briefing system
  ADR-0005-action-system.md            # Action pipeline
  ADR-0006-team-lead-daemon.md         # Team lead management daemon

~/Library/LaunchAgents/
  ai.openclaw.gateway.plist            # OpenClaw gateway (port 18789, loopback)
  ai.openclaw.taskdaemon.plist         # Task daemon
  ai.openclaw.teamlead.plist           # Team lead daemon
```

## Discord Setup

- **Guild:** 1474833522710548490
- **Authorized user (Patrick):** 1237951508742672431
- **Bot account:** hurin (single bot, token in openclaw.json)
- **Channel bindings:**

| Channel | ID | Bot | Purpose |
|---------|-----|-----|---------|
| #planning | 1475607956698562690 | hurin | Primary conversation channel |
| #reviews | 1475608130040762482 | hurin | PR review notifications |
| #tasks | 1476635425777914007 | hurin | Task threads (daemon + cc-query), thread reply follow-ups |
| #co-founder | 1476739270663213197 | hurin | Co-founder briefings (replies only; posts via direct API) |
| #quick-wins | 1476950473893482587 | hurin | Revenue-impacting PR notifications |
| #team-lead | 1478507314427334950 | (direct API) | Team lead synthesis + recommendations |

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
- `thinkingDefault: "off"` — hurin doesn't need reasoning, saves tokens
- `sandbox: { "mode": "off" }` — local trusted machine
- Agent-to-agent comms enabled (hurin only)
- **hurin tools restricted to:** `exec`, `sessions_list`, `sessions_history`, `session_status`
- `read`, `write`, `edit` removed — see [ADR-0003](ADR-0003-hurin-lockdown-validation.md)
- Thread bindings enabled (idleHours: 24) — thread replies route to the bound agent

## Workflow: Patrick → Code → PR

1. Patrick posts a task in #planning
2. hurin triages: handle directly (simple query) or delegate to CC
3. For investigations/planning: hurin runs `cc-query.py` via `exec` (Mode 1: sync), which creates a Discord thread in #tasks showing CC's progress in real time
4. CC reads project context, investigates, relays via the #tasks thread. hurin posts the summary in #planning.
5. On Patrick's approval, hurin runs `task spawn <repo> <id> '<desc>'` with prompt on stdin (Mode 2: background)
6. `task-daemon.py` picks up the task (≤30s), creates worktree, symlinks .venv, runs Agent SDK query()
7. Discord thread in #tasks streams tool calls and text in real time
8. Claude Code reads the repo's CLAUDE.md files, implements, creates PR
9. Task daemon monitors: PR created? CI passing? Review status?
10. `review-prs.sh` (every 15 min) posts automated Claude review on new PRs
11. On success: daemon pings hurin with PR URL, posts to #quick-wins
12. On failure: Ralph Loop — daemon auto-respawns with session resume (max 3x)
13. Patrick can steer running tasks by replying in the Discord thread

### Ralph Loop (Failure Recovery)

When a task completes without a PR:
1. Task daemon captures failure context from the last 50 lines of task output
2. If respawn count < 3: daemon auto-respawns with session resume (full context preserved)
3. The respawn prompt includes the failure output and asks CC to try a different approach
4. After 3 failed respawns: task marked as `failed`, Patrick notified

No hurin involvement in failure recovery — the daemon handles it directly with SDK session resume.

### Task Thread Follow-ups

When Patrick replies in a completed task's Discord thread:
1. hurin detects the thread reply in #tasks
2. hurin runs `thread-followup.sh <thread_id> <message>`
3. Script maps thread ID → task ID via registry, calls `task follow-up`
4. Daemon resumes the CC session with full context

For running tasks, thread replies are picked up by the steer poller and delivered as live steering messages.

### Automated Code Review

`review-prs.sh` runs every 15 minutes:
1. Lists open PRs without `reviewed-by-claude` label
2. Gets diff via `gh pr diff`
3. Runs `claude -p` with a review prompt (bugs, security, test gaps)
4. Posts review as PR comment via `gh pr review --comment`
5. Adds `reviewed-by-claude` label to prevent re-reviewing

## Monitoring

| Component | Type | Purpose |
|-----------|------|---------|
| `task-daemon.py` | LaunchAgent (ai.openclaw.taskdaemon) | Task execution, PR detection, CI monitoring, respawns, steering |
| `team-lead.py` | LaunchAgent (ai.openclaw.teamlead) | Goal tracking, synthesis, auto-spawning. See [ADR-0006](ADR-0006-team-lead-daemon.md). |
| `review-prs.sh` | Cron (every 15 min) | Automated code review on new PRs |
| `co-founder.sh` | Cron (9 schedules) | Strategic briefings via rotating lenses. See [ADR-0004](ADR-0004-co-founder-system.md). |

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
task spawn <repo> <id> '<desc>' [--issue #]   # Enqueue (daemon picks up ≤30s)
task watch <id>                                # Tail JSONL log with formatting
task status [id]                               # Registry status
task list                                      # Queued + running + pr_open
task kill <id>                                 # Write kill sentinel
task follow-up <id> <message>                  # Resume session
```

### Cleaning up

Worktrees for completed tasks are automatically cleaned up by the task daemon after PR creation.

## Consequences

### Positive

- Simpler architecture: smart router + one brain
- All CC intelligence at $0 via Max plan — hurin API cost is ~$0.30-1.20/MTok (MiniMax M2.5)
- Structural enforcement: hurin literally cannot read/write/edit files (tools removed)
- Thinking disabled: no wasted output tokens on router reasoning
- Ralph Loop: automatic failure recovery with session resume
- Live steering: Patrick can redirect running tasks via thread replies
- Discord thread streaming: real-time visibility into CC's work
- Automated code reviews catch issues before Patrick sees the PR
- Fewer moving parts to break, configure, and maintain

### Negative

- hurin cannot self-correct if CC call fails (e.g. wrong path) — limited to `exec` only
- Session context growth increases per-message cost (mitigated by 15-min idle reset)

### Risks

- Discord bot token is embedded in openclaw.json (plaintext). Don't commit this file.
- `bypassPermissions` on Agent SDK calls — appropriate for trusted local machine
- `review-prs.sh` uses `claude -p` which costs API tokens per review
- The monitoring scripts use `gh` CLI — requires `gh auth login` to be done first

## Related

- [ADR-0003: Hurin Lockdown & Validation](ADR-0003-hurin-lockdown-validation.md) — tool restrictions, thinking-off, and cost validation experiments
- [ADR-0004: Co-Founder System](ADR-0004-co-founder-system.md) — scheduled strategic briefings via rotating lenses
- [ADR-0005: Action System](ADR-0005-action-system.md) — action pipeline, approval flow
- [ADR-0006: Team Lead Daemon](ADR-0006-team-lead-daemon.md) — goal tracking, synthesis, auto-spawning
