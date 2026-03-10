# ADR-0008: Three-Agent Architecture + Daemon Decomposition

**Status:** Accepted

**Date:** 2026-03-10

**Deciders:** Patrick

**Supersedes:** [ADR-0006: Team Lead Daemon](ADR-0006-team-lead-daemon.md) (daemon aspect only; metrics/synthesis logic retained)

**Related:** [ADR-0001: Agent Swarm](ADR-0001-agent-swarm.md), [ADR-0004: Co-Founder System](ADR-0004-co-founder-system.md), [ADR-0007: Self-Evolving System](ADR-0007-self-evolving-system.md)

## Context

The single-agent architecture (hurin = everything) conflated platform with agent identity and created a monolithic responsibility problem. hurin was simultaneously the router, team lead, co-founder analyst, and chief of staff. Discord channel assignment was arbitrary. The team-lead daemon (`openclaw-teamlead.service`) ran continuously as a systemd service but only did meaningful work twice: every 15 minutes (GitHub poll) and once weekly (synthesis). A long-running daemon was over-engineered for what amounts to two cron jobs.

Patrick's goals:
- Clearly scoped specialist agents with distinct Discord channels
- Retain the two-tier intelligence architecture (MiniMax M2.5 → Claude Code Opus)
- Leverage native openclaw features (heartbeat, thread bindings, agent-to-agent)
- Eliminate unnecessary daemons in favor of cron
- Side-gig-appropriate cadence (daily/weekly, not hourly)

## Decision

### 1. Three Named Agents

| Agent | Role | Discord Channel | Workspace |
|-------|------|-----------------|-----------|
| **Huor** | Team Lead — task execution, GitHub monitoring, synthesis, anomaly detection | #team-lead, #tasks | `workspace-huor/` |
| **Tuor** | Co-Founder — strategic briefings (9 lenses), product vision, market research, action pipeline | #co-founder | `workspace-tuor/` |
| **Beren** | Chief of Staff — meta-orchestration, strategic digests, system evaluation | #chief-of-staff | `workspace-beren/` |

**Húrin** is now the **platform** (Linux VPS, repo, user account), not an agent. The old "hurin" agent identity is retired.

Each agent has its own:
- Discord bot account and token
- OpenClaw agent config with `sessions_send` capability
- Workspace with SOUL.md, AGENTS.md, USER.md, TOOLS.md, IDENTITY.md
- QMD memory directory

All three agents run on MiniMax M2.5 and delegate intelligence to Claude Code (Opus 4.6) via Agent SDK — the two-tier architecture is preserved.

### 2. Daemon → Cron Decomposition

The `openclaw-teamlead.service` daemon is replaced by two cron jobs:

| Schedule | Script | Purpose |
|----------|--------|---------|
| `*/15 7-21 * * *` | `github-poll.sh` → `github-poll.py` | GitHub data collection, metrics, anomaly detection, telemetry |
| `15 9 * * 1` | `manual-synthesis.sh` → `run-synthesis.py` | Weekly synthesis (Agent SDK Opus), Discord posting, auto-spawn, learning |

On-demand synthesis via `/teamlead` skill calls `manual-synthesis.sh` directly (no sentinel file).

Key changes:
- **Anomaly cooldowns** persisted to `anomaly-cooldowns.json` (was in-memory `_anomaly_cooldowns` dict)
- **Events** read from `task-events.jsonl` at synthesis time via `read_recent_events()` (was daemon event watcher polling every 5s)
- **`team_lead.py`** (renamed from `team-lead.py`) serves as importable library for both entry points
- **No state lost** — dedup cache, metrics log, syntheses dir all persist on disk already

### 3. Channel Consolidation

Dropped channels:
- `#planning` — redundant with `#team-lead` (Huor handles planning)
- `#quick-wins` — paused, no longer needed

### 4. What Stays Unchanged

- Task daemon (`openclaw-taskdaemon.service`) — stateful execution engine, unchanged
- OpenClaw gateway (`openclaw-gateway.service`) — unchanged except 3 bot tokens
- Co-founder system — scripts unchanged, just routed through Tuor
- Chief of Staff — script unchanged, just routed through Beren
- Ralph Loop, worktree strategy, definition of done — all unchanged

## File Layout (New)

```
~/.openclaw/
  openclaw.json              # 3 agents, 3 Discord accounts, agent-to-agent enabled
  gateway-wrapper.sh         # Exports 3 bot tokens from secrets.json
  secrets.json               # Added huor/tuor/beren-discord-bot-token keys

  agents/{huor,tuor,beren}/agent/
    models.json              # MiniMax model definitions (shared)

  workspace-huor/            # Huor (Team Lead)
    SOUL.md, AGENTS.md, USER.md, TOOLS.md, IDENTITY.md, HEARTBEAT.md
    PROJECT-BOARD-RULES.md

  workspace-tuor/            # Tuor (Co-Founder)
    SOUL.md, AGENTS.md, USER.md, TOOLS.md, IDENTITY.md

  workspace-beren/           # Beren (Chief of Staff)
    SOUL.md, AGENTS.md, USER.md, TOOLS.md, IDENTITY.md

  team-lead/
    team_lead.py             # Library (importable, renamed from team-lead.py)
    team-lead.py             # Original (kept for backward compat, daemon entry point)
    config.py                # Configuration constants
    github-poll.py           # Cron entry point: GitHub poll + anomaly detection
    github-poll.sh           # Shell wrapper for cron
    run-synthesis.py         # Cron entry point: full synthesis flow
    manual-synthesis.sh      # Shell wrapper for /teamlead skill + cron
    anomaly-cooldowns.json   # Persisted cooldown state (was in-memory)
    syntheses/               # Saved synthesis outputs
    dedup-cache.json         # 24h recommendation hashes
    metrics-log.jsonl        # Metrics history
```

## Consequences

### Positive

- Clear agent identities with scoped responsibilities
- Daemon eliminated — two cron jobs are simpler, more reliable, easier to debug
- No wasted resources (daemon polled events every 5 seconds, used only at synthesis time)
- Native openclaw features (thread bindings, heartbeat, agent-to-agent) now available
- Side-gig cadence: daily poll + weekly synthesis, not continuous monitoring

### Negative

- Three Discord bots to manage instead of one
- Agent-to-agent communication adds latency vs. direct function calls
- Cron has no event-driven reactivity (daemon could react to task events in seconds — now reactions wait for next 15-min poll)

### Risks

- MiniMax M2.5 may not produce high-quality agent-to-agent messages (mitigated: agents route to CC for anything complex)
- Discord bot permission issues if bots not properly invited to guild
- Cron timing gaps: a high-severity anomaly detected at 7:01 won't post until 7:15 (mitigated: anomalies are rare and cooldown is 6h anyway)

## Related

- [ADR-0001: Agent Swarm](ADR-0001-agent-swarm.md) — parent architecture (2-tier)
- [ADR-0004: Co-Founder System](ADR-0004-co-founder-system.md) — now routed through Tuor
- [ADR-0006: Team Lead Daemon](ADR-0006-team-lead-daemon.md) — superseded daemon, metrics/synthesis logic retained
- [ADR-0007: Self-Evolving System](ADR-0007-self-evolving-system.md) — KB, telemetry, spawn policy unchanged
