# ADR-0001: OpenClaw Multi-Agent Swarm Setup

**Status:** Accepted

**Date:** 2026-02-25

**Deciders:** Patrick

## Context

Patrick previously ran a 3-agent OpenClaw setup on an underpowered Ubuntu VPS. It was
unstable, expensive, and never got past "standing by." The Mac Mini M4 (16GB) is now
the dedicated machine. The goal is a scaled-down Elvis Sun-style agent swarm for the
Family Diagram project: an orchestrator that delegates to specialist coordinators, who
in turn spawn Claude Code subprocesses to do the actual coding.

Reference article: [elvis-agent-swarm-article.md](elvis-agent-swarm-article.md) (Elvis Sun, Feb 23 2026)
Gap analysis & status: [ADR-0001-status.md](ADR-0001-status.md)

## Decision

A 3-tier agent architecture running on the Mac Mini via OpenClaw:

```
Patrick (Discord)
  └── hurin (Sonnet 4.6) — orchestrator, holds project context
        ├── beren (Haiku 4.5) — backend coordinator (btcopilot/)
        │     └── claude --model claude-opus-4-6  (does the actual coding)
        └── tuor (Haiku 4.5) — frontend coordinator (familydiagram/)
              └── claude --model claude-opus-4-6  (does the actual coding)
```

**Key insight from the article:** Specialization through context, not through different
models. hurin/beren/tuor don't need expensive models because they're not coding — they're
assembling context and crafting prompts. The coding quality comes from Opus subprocesses
given precise, well-contextualized prompts.

## File Layout

### OpenClaw Config

```
~/.openclaw/
  openclaw.json               # Full multi-agent config (agents, Discord, bindings)
  workspace-hurin/            # hurin's workspace
    SOUL.md                   # Orchestrator role + delegation chain
    AGENTS.md                 # Standard OpenClaw agent conventions
    USER.md                   # Patrick's info, project overview
    TOOLS.md                  # Local environment, team structure
    IDENTITY.md               # hurin, 🏰
    HEARTBEAT.md              # Check alerts.txt; act or HEARTBEAT_OK
  workspace-beren/            # beren's workspace
    SOUL.md                   # Backend coordinator role + spawn workflow
    AGENTS.md
    USER.md
    TOOLS.md                  # Includes tmux/worktree/registry commands
    IDENTITY.md               # beren, 🗡️
  workspace-tuor/             # tuor's workspace
    SOUL.md                   # Frontend coordinator role + spawn workflow
    AGENTS.md
    USER.md
    TOOLS.md                  # Includes tmux/worktree/registry commands
    IDENTITY.md               # tuor, 🌊
  monitor/
    check-agents.py           # Monitoring script (cron, every 10 min)
    alerts.txt                # Written by script; read by hurin heartbeat
    monitor.log               # Script run log
    cron.log                  # cron stdout/stderr
  agents/
    hurin/agent/auth-profiles.json   # Anthropic API key
    beren/agent/auth-profiles.json   # Anthropic API key (copied from main)
    tuor/agent/auth-profiles.json    # Anthropic API key (copied from main)
```

### Project Files

```
~/Projects/theapp/
  .clawdbot/                  # Gitignored. Agent task tracking.
    active-tasks.json         # Registry of active Claude Code sessions
  adrs/
    ADR-0001-agent-swarm.md   # This file

~/Projects/theapp-worktrees/  # Git worktrees for active tasks
  feat-{task-name}/           # One per active Claude Code job
```

## Discord Setup

- **Guild:** 1474833522710548490
- **Authorized user (Patrick):** 1237951508742672431
- **Bot accounts:** hurin, beren, tuor (tokens in openclaw.json)
- **Channel bindings:**

| Channel | ID | Bot |
|---------|-----|-----|
| #planning | 1475607956698562690 | hurin |
| #reviews | 1475608130040762482 | hurin |
| #beren-work | 1475608068967370945 | beren |
| #tuor-work | 1475608101632868474 | tuor |

Settings: `requireMention: false`, `allowBots: true`, `groupPolicy: allowlist`

## Key Config Settings (openclaw.json)

Tuned for 16GB RAM:

```json
"maxConcurrent": 2,
"subagents": { "maxConcurrent": 4 },
"contextTokens": 64000
```

- `maxConcurrent: 2` — prevents swap thrashing (Elvis hit his ceiling at 4-5 agents on 16GB)
- `contextTokens: 64000` — old VPS config had constant low-context warnings at 32000
- `sandbox: { "mode": "off" }` — local trusted machine
- Agent-to-agent comms enabled: `tools.agentToAgent.enabled: true`
- hurin has `sessions_spawn`; beren/tuor do not (they're not orchestrators)

## Workflow: Patrick → Code → PR

1. Patrick posts a task in #planning
2. hurin reads project context, breaks work into backend/frontend sub-tasks
3. hurin uses `sessions_spawn` to delegate to beren (backend) or tuor (frontend)
4. beren/tuor reads relevant CLAUDE.md files, crafts a precise prompt
5. beren/tuor creates a git worktree and registers the task in `active-tasks.json`
6. beren/tuor spawns Claude Code via tmux:
   ```bash
   tmux new-session -d -s "claude-{agent}-{task}" \
     -c "/Users/hurin/Projects/theapp-worktrees/feat-{task}" \
     "claude --model claude-opus-4-6 --dangerously-skip-permissions -p '{prompt}'"
   ```
7. beren/tuor monitors via `tmux capture-pane`; redirects mid-task if needed
8. When done: `gh pr create --fill` from the worktree
9. beren/tuor updates `active-tasks.json` and reports PR URL to hurin
10. hurin notifies Patrick in #reviews

## Monitoring Loop

Two complementary systems (no redundancy — different jobs):

### Cron script (deterministic, zero tokens)

```
crontab: */10 * * * * python3 ~/.openclaw/monitor/check-agents.py
```

Checks each "running" task in `active-tasks.json`:
- tmux session alive?
- PR created? CI passing?
- Session dead + no PR → write RESPAWN NEEDED alert (max 3 attempts)
- CI failing → write CI FAILING alert
- CI passing, no pending checks → write PR READY alert

Writes to `~/.openclaw/monitor/alerts.txt`.

### hurin (event-driven, not polling)

The cron script calls `openclaw agent --agent hurin --message "..."` directly when
action is needed. Hurin wakes up only when there is something to do:
- PR READY → notify Patrick in #reviews
- CI FAILING → notify Patrick; optionally route to beren/tuor
- RESPAWN NEEDED → re-delegate to the relevant agent with failure context
- FAILED (max respawns) → notify Patrick, needs human intervention

The OpenClaw heartbeat is disabled (HEARTBEAT.md is empty).

## Administration

### Restarting the gateway

```bash
openclaw gateway restart
```

The gateway runs as a LaunchAgent on port 18789 (loopback).

### Verifying health

```bash
openclaw doctor
openclaw agents list
openclaw channels status --probe   # live Discord connectivity check
```

### Modifying agent config

Edit `~/.openclaw/openclaw.json` directly, then restart gateway. The file is standard
JSON (no comments). Key sections: `agents.list`, `bindings`, `channels.discord.accounts`.

### Updating workspace files

Edit files in `~/.openclaw/workspace-{agent}/` directly. Changes take effect on the
agent's next session (no restart needed).

### Updating the monitoring script

Edit `~/.openclaw/monitor/check-agents.py`. The cron picks it up automatically.

### Checking monitor logs

```bash
cat ~/.openclaw/monitor/alerts.txt    # pending alerts
tail -f ~/.openclaw/monitor/monitor.log  # live script output
tail -f ~/.openclaw/monitor/cron.log     # cron stdout/stderr
```

### Cleaning up completed worktrees

```bash
cd ~/Projects/theapp
git worktree list                          # see all active worktrees
git worktree remove ~/Projects/theapp-worktrees/feat-{task}
```

### Adding a new agent

1. Add entry to `agents.list` in `openclaw.json`
2. Add Discord account and channel bindings if needed
3. Create `~/.openclaw/workspace-{id}/` with SOUL.md, AGENTS.md, USER.md, TOOLS.md, IDENTITY.md
4. Copy `auth-profiles.json` from `~/.openclaw/agents/main/agent/`
5. Restart gateway

## Consequences

### Positive

- Parallelism: beren and tuor can have independent Claude Code sessions running simultaneously
- Context isolation: each tier holds only what it needs (business context vs. code context)
- Cost efficiency: coordinator agents on Haiku; coding on Opus only when actually coding
- Monitoring: cron handles cheap checks; hurin handles nuanced decisions
- Proven architecture: based directly on Elvis Sun's working production setup

### Negative

- More moving parts than a single-agent setup
- beren/tuor must write good prompts — quality depends on their context assembly
- Worktrees accumulate if not cleaned up after merges

### Risks

- Discord bot tokens are embedded in openclaw.json (plaintext). Don't commit this file.
- `--dangerously-skip-permissions` on Claude Code subprocesses — appropriate for trusted
  local machine, but subprocesses can modify any file in the worktree.
- The monitoring script uses `gh` CLI — requires `gh auth login` to be done first.
