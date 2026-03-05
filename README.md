# hurin — OpenClaw Agent Deployment

This is the configuration repo for **hurin**, an [OpenClaw](https://openclaw.ai) agent deployment running on a Mac Mini M4 (16GB RAM). It drives a 2-tier AI development team that autonomously implements features, reviews PRs, and provides strategic briefings for the [Family Diagram](https://alaskafamilysystems.com) product suite.

## What This Repo Contains

This is not application code. It's the operational configuration, scripts, prompts, and architecture decision records for a single-machine OpenClaw deployment. The product repos it operates on are:

| Repo | Role |
|------|------|
| `patrickkidd/familydiagram` | Desktop/mobile app (PyQt5/QML, existing product) |
| `patrickkidd/btcopilot` | Personal app backend (Flask, AI/ML, clinical model) |
| `patrickkidd/fdserver` | Server (Flask, PostgreSQL, Celery) |

All three repos are checked out as submodules under `workspace-hurin/theapp/`.

---

## Architecture Overview

A 2-tier agent architecture where a cheap, fast router delegates all code intelligence to Claude Code (Opus 4.6) running at $0 on the Anthropic Max plan.

```
Patrick (Discord)
  |
  v
OpenClaw Gateway (LaunchAgent, port 18789)
  |
  v
hurin (MiniMax M2.5, ~$0.01/message)
  |--- Handle directly: read-only queries, system admin, monitoring
  |--- Delegate to CC: anything touching application code
  |
  +-- Mode 1: Sync (cc-query.py)
  |     Agent SDK query() -> blocks -> reply in Discord
  |     Real-time progress streamed to #tasks thread
  |
  +-- Mode 2: Background (task spawn -> task-daemon.py)
  |     Agent SDK query() -> worktree -> PR
  |     Discord thread streaming, auto-retry on failure
  |
  +-- Co-Founder System (cron, 9 lenses)
  |     claude -p -> strategic briefings -> #co-founder channel
  |
  +-- Team Lead Daemon (LaunchAgent)
        Monitors GitHub + task events -> metrics -> synthesis
        Auto-spawns automatable tasks toward MVP goals
```

### Why 2-Tier?

An earlier 3-tier design (hurin -> beren/tuor coordinators -> Claude Code) had a Haiku-class intelligence bottleneck at the coordinator layer. Prompt quality turned out to be the single highest-leverage variable, and having a small model write coding prompts was a net negative. Collapsing to 2 tiers — smart router + Opus brain — eliminated the bottleneck entirely. See [ADR-0001](adrs/ADR-0001-agent-swarm.md) for the full rationale.

### Cost Model

| Component | Model | Cost |
|-----------|-------|------|
| hurin (router) | MiniMax M2.5 | ~$0.01/message ($3-27/month) |
| Claude Code (brain) | Opus 4.6 | $0 (Max plan CLI) |
| Co-founder briefings | Opus 4.6 | $0 (Max plan CLI) |
| Team lead synthesis | Sonnet 4.6 | $0 (Max plan CLI) |
| PR reviews | Opus 4.6 | $0 (Max plan CLI) |

All intelligence work is $0. The only API cost is hurin's routing decisions on MiniMax M2.5.

---

## Runtime Components

Three LaunchAgents and two cron jobs form the runtime:

### LaunchAgents

| Label | Script | Role |
|-------|--------|------|
| `ai.openclaw.gateway` | `openclaw gateway` | OpenClaw proxy on port 18789 (loopback) |
| `ai.openclaw.taskdaemon` | `monitor/task-daemon.py` | Drains task queue, executes CC tasks via Agent SDK |
| `ai.openclaw.teamlead` | `team-lead/team-lead.py` | Monitors GitHub, computes metrics, synthesizes hourly, auto-spawns tasks |

Restart any with: `launchctl kickstart -k gui/501/ai.openclaw.<label>`

### Cron

| Schedule | Script | Purpose |
|----------|--------|---------|
| Every 15 min | `monitor/review-prs.sh` | Automated Claude code review on new PRs |
| 9 rotating schedules | `co-founder/co-founder.sh <lens>` | Strategic briefings (currently paused) |

---

## How Work Gets Done

### The Workflow: Message to Merged PR

1. Patrick posts a task in Discord `#planning`
2. hurin triages: handle directly (simple query) or delegate to CC
3. For investigations: hurin calls `cc-query.py` (Mode 1 — sync), which creates a Discord thread in `#tasks` showing CC's progress in real time
4. CC investigates, hurin relays the report to Patrick
5. On approval, hurin runs `task spawn` (Mode 2 — background)
6. Task daemon picks up within 30 seconds, creates a git worktree, symlinks `.venv`, runs Agent SDK `query()`
7. Discord thread streams tool calls and text in real time
8. CC reads the repo's `CLAUDE.md` files, implements the change, creates a PR
9. `review-prs.sh` (every 15 min) posts an automated Claude review on the PR
10. On success: daemon pings with PR URL, posts to `#quick-wins` if revenue-impacting
11. On failure: Ralph Loop auto-respawns with session resume (up to 3x)
12. Patrick reviews and merges

### Definition of Done

A task is complete when:
- PR created (no direct commits to main)
- No merge conflicts
- CI passing (all checks green)
- Automated Claude review passed
- Screenshots included if UI change
- Tests added or updated

### Ralph Loop (Failure Recovery)

When a task fails without producing a PR:
1. Task daemon captures failure context from the last 50 lines of output
2. If respawn count < 3: auto-respawns with SDK session resume (full context preserved)
3. The respawn prompt includes the failure output and asks CC to try a different approach
4. After 3 failed attempts: marked as `failed`, Patrick notified

No human involvement in failure recovery — the daemon handles retries with full session context.

### Live Steering

Patrick can redirect running tasks by replying in the task's Discord thread. Thread replies are picked up by the steer poller and delivered to CC as live messages.

### Task CLI

```bash
task spawn <repo> <id> '<desc>' [--issue #]   # Enqueue (daemon picks up in <=30s)
task watch <id>                                # Tail JSONL log
task status [id]                               # Registry status
task list                                      # Queued + running + pr_open
task kill <id>                                 # Write kill sentinel
task follow-up <id> <message>                  # Resume completed task's session
```

---

## Hurin: The Router

hurin is a smart router with light operational capability. It runs on MiniMax M2.5 (Sonnet-tier) with a restricted tool set.

### Structural Enforcement

hurin's tool allowlist is limited to:
- `exec` — run shell commands
- `sessions_list`, `sessions_history`, `session_status` — read-only session introspection

The `read`, `write`, and `edit` tools are **removed at the OpenClaw config level**. This is structural enforcement, not a prompt-level suggestion — if MiniMax tries to read or write files, the tool call is rejected by the gateway. See [ADR-0003](adrs/ADR-0003-hurin-lockdown-validation.md) for the incident that motivated this.

### Triage Rule

For every message, hurin asks: *"Can I answer this with `exec` commands I already know, without needing to understand application code?"*
- **Yes** → handle directly (git status, task list, log checks, config edits)
- **No** → delegate to CC via `cc-query.py` or `task spawn`
- **Not sure** → delegate to CC (cost is $0)

### Config Tuning (16GB RAM)

```json
{
  "maxConcurrent": 2,
  "subagents": { "maxConcurrent": 4 },
  "contextTokens": 64000,
  "thinkingDefault": "off"
}
```

- `maxConcurrent: 2` — prevents swap thrashing
- `thinkingDefault: "off"` — hurin doesn't need reasoning, saves tokens
- Idle session reset at 15 minutes bounds context growth costs

---

## Co-Founder System

A scheduled strategic briefing system that runs Claude Code through different "lenses" on a cron schedule, posting to a dedicated Discord channel and maintaining a persistent journal.

### How It Works

1. Cron triggers `co-founder.sh <lens>`
2. Reads the lens prompt from `lenses/<name>.md`
3. Feeds the last 100 lines of `journal.md` for continuity
4. Runs `claude -p --model opus --max-turns 10` (multi-turn agentic: gather data, dig deeper, synthesize)
5. Saves the full briefing to `briefings/<lens>-<date>.md`
6. Appends to `journal.md` (capped at 1000 lines)
7. Extracts structured action items (if any)
8. Posts to Discord `#co-founder` (split at 1900 chars)

### Lens Rotation

| Time (AKST) | Days | Lens | Focus |
|-------------|------|------|-------|
| 6:00 AM | Mon, Thu | project-pulse | MVP progress, blockers, priorities |
| 2:00 PM | Mon, Thu | wild-ideas | Creative brainstorming |
| 2:00 PM | Tue, Fri | architecture | Tech debt, patterns, risks |
| 1:00 PM | Wed | product-vision | User experience, product direction |
| 3:00 PM | Wed | customer-support | Support patterns, community |
| 10:00 AM | Sat | market-research | Competitors, AI news |
| 11:00 AM | Sat | process-retro | Dev process efficiency |
| 10:00 AM | Sun | website-audit | Website conversion/UX/SEO |
| 10:01 AM | 1st & 15th | training-programs | Outreach, partnerships |

Each run gives CC 10 agentic turns. Output is unconstrained — CC writes as much as the analysis warrants. Session IDs are saved for follow-up conversations via `/cofounder followup <lens> <question>`.

### Action Pipeline

Briefings can optionally produce structured action items. These are quality-gated — most briefings produce zero actions by design. When they do appear:

- Every action becomes a GitHub Issue (source of truth)
- Revenue-impacting items go to `#quick-wins`, others to `#co-founder`
- All actions require Patrick's approval before spawning
- `/cofounder approve <id>` enqueues to the task daemon
- `/cofounder refine <id> <feedback>` iterates on the plan via session resumption

See [ADR-0004](adrs/ADR-0004-co-founder-system.md) and [ADR-0005](adrs/ADR-0005-action-system.md).

---

## Team Lead Daemon

A management layer that sits between strategy (co-founder briefings) and execution (task daemon), providing metrics, synthesis, and proactive task spawning.

### What It Does

- **Watches task events** — reacts to completions, failures, PR merges within seconds
- **Polls GitHub** — PRs, CI, issues, Project #4 state every 15 min (business hours only)
- **Computes metrics** — fuzzy goal completion %, velocity, cycle time, success rate
- **Detects anomalies** — stale PRs, broken CI, stuck tasks, goal regression, velocity stalls
- **Synthesizes hourly** — Agent SDK `query()` with Sonnet 4.6, 3-turn budget
- **Auto-spawns tasks** — 100% automatable tasks that map to MVP goals (Tier 1)
- **Morning brief** — first synthesis after 7AM summarizes overnight events

### Fuzzy Goal Completion

Goals are tracked via GitHub Project #4's Status field ("Goal 1", "Goal 2", "Goal 3"). Per-issue weighting:

| Issue State | Weight |
|-------------|--------|
| Open, no activity | 0% |
| Open, active branch commits | 20% |
| Open, PR in draft | 30% |
| Open, PR in review / CI running | 70% |
| PR merged / issue closed | 100% |

Effort labels (`effort:large` = 3x, `effort:medium` = 2x, `effort:small` = 1x) adjust the weighting.

### Progressive Autonomy (3 Tiers)

| Tier | Capabilities |
|------|-------------|
| **1** (default) | Observe + recommend. Auto-spawn 100% automatable tasks only. |
| **2** | Also: reorder queue, spawn follow-ups on stale PRs, flag blockers, kill stuck tasks |
| **3** | Full queue management: spawn human-in-loop tasks, reprioritize based on goal risk, decompose large tasks |

Currently running at Tier 1. Tier escalation via `autonomy_tier` in `team-lead/config.py`.

### Proactive Velocity Features

- **Unblocked task detection** — when a PR merges, checks what it unblocks and spawns if automatable
- **Parallelization** — identifies tasks with no mutual dependencies for concurrent execution
- **Decomposition suggestions** — suggests breaking down stale large tasks into CC-friendly subtasks
- **Quick win mining** — scans open issues, TODOs, and briefings for small automatable improvements

See [ADR-0006](adrs/ADR-0006-team-lead-daemon.md).

---

## Prompt Caching

hurin's system prompt (SOUL.md, AGENTS.md, TOOLS.md, etc.) is stable across turns. Caching reduces input costs.

- **MiniMax M2.5:** `cacheRetention: "short"` (5-min TTL, matches conversation patterns)
- **Heartbeat:** every 55 min to keep the cache warm
- **Compaction:** fires at 54K tokens (64K context - 10K reserve floor)
- **Cache trace:** logged to `logs/cache-trace.jsonl` for cost monitoring

See [ADR-0002](adrs/ADR-0002-prompt-caching.md).

---

## Discord Channels

| Channel | Purpose |
|---------|---------|
| `#planning` | Primary conversation with Patrick |
| `#tasks` | Task threads — daemon + cc-query stream progress, thread replies steer/resume tasks |
| `#reviews` | PR review notifications |
| `#co-founder` | Strategic briefings from the co-founder system |
| `#quick-wins` | Revenue-impacting PR notifications |
| `#ops` | Team lead synthesis + recommendations |

---

## File Layout

```
~/.openclaw/                          # This repo (patrickkidd/hurin)
  openclaw.json                       # Agent config, Discord bindings, model settings
  secrets.json                        # API keys (gitignored)
  adrs/                               # Architecture Decision Records
  co-founder/                         # Co-founder briefing system
    co-founder.sh                     # Main runner
    lenses/                           # 9+ lens prompt files
    journal.md                        # Persistent memory (1000 line cap)
    briefings/                        # Full briefing archives
    actions/                          # Parsed action JSON files
  monitor/                            # Task execution infrastructure
    task-daemon.py                    # Main daemon (Agent SDK, async Python)
    cc-query.py                       # Sync CC wrapper for Mode 1
    discord_relay.py                  # Discord thread streaming
    review-prs.sh                     # Automated Claude code review
    task-queue.json                   # Queue file (drained every 30s)
    queue-prompts/                    # Prompt files for queued tasks
    task-logs/                        # JSONL logs per task
    task-events.jsonl                 # Event stream (consumed by team-lead)
    kill-sentinels/                   # Write <id>.kill to terminate tasks
  team-lead/                          # Team lead daemon
    team-lead.py                      # Main daemon (async Python, Agent SDK)
    config.py                         # Thresholds, quiet hours, autonomy tier
    syntheses/                        # Saved synthesis outputs
  workspace-hurin/                    # hurin's workspace
    SOUL.md                           # Router role, triage rules, delegation protocol
    TOOLS.md                          # Local environment, commands, monitoring
    IDENTITY.md                       # Name, creature, vibe, emoji
    USER.md                           # Patrick's info
    theapp/                           # Monorepo (familydiagram + btcopilot + fdserver)
      .clawdbot/active-tasks.json     # Task registry
  workspace/                          # OpenClaw default workspace (templates)
  launchagents/                       # LaunchAgent plist backups
  archive/                            # Archived beren/tuor configs, monitor-v1
```

---

## Worktree Strategy

Each background task gets its own git worktree for isolation:
- **Default:** symlink `.venv` from the main repo (0 bytes, instant)
- **Dependency changes:** `uv sync` (fast via uv's hardlink cache)
- **Capacity:** 3-4 concurrent worktrees fit comfortably on 16GB
- **Cleanup:** automatic after PR creation

---

## GitHub Project Board

All work is tracked on [GitHub Project #4](https://github.com/users/patrickkidd/projects/4) ("Family Diagram"). Goals are encoded as Status field values ("Goal 1", "Goal 2", "Goal 3"), not milestones.

Key labels across all three product repos:
- `co-founder`, `cf-spawned`, `cf-approved`, `cf-done`, `cf-pr-open` — co-founder system lifecycle
- `velocity` — team-lead-spawned quick wins
- `effort:small/medium/large` — used for weighted goal completion %
- `reviewed-by-claude` — PR has been auto-reviewed

Sub-issues model dependencies within a milestone. Priority (P0-P3) encodes execution order. Same-priority issues are parallelizable.

---

## Administration

### Health Check

```bash
openclaw doctor
openclaw agents list              # Should show only hurin
openclaw channels status --probe  # Live Discord connectivity
```

### Restart Services

```bash
openclaw gateway restart
launchctl kickstart -k gui/501/ai.openclaw.taskdaemon
launchctl kickstart -k gui/501/ai.openclaw.teamlead
```

### Monitor Tasks

```bash
task list                          # All tasks
task status <id>                   # Single task detail
task watch <id>                    # Live log tail
```

### Check Logs

```bash
tail ~/.openclaw/monitor/daemon.log        # Task daemon
tail ~/.openclaw/team-lead/daemon.log      # Team lead
tail ~/.openclaw/co-founder/cron.log       # Co-founder runs
tail ~/.openclaw/logs/cache-trace.jsonl    # Prompt cache health
```

---

## Architecture Decision Records

| ADR | Status | Summary |
|-----|--------|---------|
| [ADR-0001](adrs/ADR-0001-agent-swarm.md) | Accepted | 2-tier agent architecture (hurin router + Claude Code brain) |
| [ADR-0002](adrs/ADR-0002-prompt-caching.md) | Accepted | Prompt caching: short TTL, heartbeat keep-warm, cache diagnostics |
| [ADR-0003](adrs/ADR-0003-hurin-lockdown-validation.md) | Accepted | Hurin tool lockdown after autonomous action incident |
| [ADR-0004](adrs/ADR-0004-co-founder-system.md) | Accepted | Co-founder strategic briefing system (9 lenses, journal memory) |
| [ADR-0005](adrs/ADR-0005-action-system.md) | Accepted | Quality-gated action pipeline with approval flow |
| [ADR-0006](adrs/ADR-0006-team-lead-daemon.md) | Accepted | Team lead daemon: metrics, synthesis, auto-spawning |

---

## Security Notes

- **Secrets** live in `secrets.json` (gitignored). Keys: `anthropic-api-key`, `minimax-api-key`, `discord-bot-token`.
- **Bot account:** `patrickkidd-hurin` (GitHub PAT in `monitor/hurin-bot-token`, also gitignored).
- **Sandbox mode:** off (trusted local machine).
- **`bypassPermissions`** on Agent SDK calls — appropriate for local execution.
- **This repo is public.** Never commit secrets, tokens, or API keys to tracked files.
