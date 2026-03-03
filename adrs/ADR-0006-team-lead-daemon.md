# ADR-0006: Team Lead Management Daemon

**Status:** Accepted

**Date:** 2026-03-03

**Deciders:** Patrick

**Related:** [ADR-0004: Co-Founder System](ADR-0004-co-founder-system.md), [ADR-0005: Action System](ADR-0005-action-system.md)

## Context

The co-founder system (ADR-0004) provides strategic briefings. The task daemon executes work. But nothing sits between strategy and execution to manage work as a whole. Goals live in prose, velocity is unmeasured, and nobody asks "which goals are at risk?" or "what can be spawned right now?" Patrick wants a team lead that observes the full picture, proactively drives velocity toward goals, and spawns automatable work without waiting for permission.

## Decision

A separate daemon (`team-lead.py`) that continuously monitors task execution, GitHub state, and goal progress — producing metrics, synthesis, and proactive task spawning. Runs as a LaunchAgent alongside the task daemon.

### Architecture

```
task-daemon.py ──writes──> task-events.jsonl ──watches──> team-lead.py
                                                              │
GitHub (PRs, CI, Issues, Project #4) ──polls every 15min──────┘
                                        (business hours only)
                                                              │
                              ┌────────────────────────────────┘
                              ▼
                    Metrics Engine (local, no AI)
                    ├── Fuzzy goal completion %
                    ├── Velocity, cycle time, success rate
                    ├── Anomaly detection
                    └── Append to metrics-log.jsonl
                              │
                              ▼
                    Synthesis Engine (Agent SDK, hourly during biz hours)
                    ├── Morning brief (first synthesis after 7AM AKST)
                    ├── Goal risk assessment
                    ├── Velocity opportunity identification
                    ├── 3-5 recommendations (for human tasks)
                    └── Auto-spawn decisions (for CC-only tasks)
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
              Discord #ops     Task Queue
              (recommendations)     (auto-spawned)
                                         │
                                    ┌────┘
                                    ▼
                              GitHub Issue created
                              + added to Project #4
                              + linked in Discord thread
```

### Goal State: GitHub-Native

Goals are tracked entirely in GitHub — no local goal-map.json.

- **Project #4 Status field** = Goal assignment via "Goal 1", "Goal 2", "Goal 3" options (existing)
- Issues move: Goal X → In Progress → Done
- **Milestones** = supported as fallback if added later
- **Issue references** = dependency tracking ("blocked by #NNN")

The daemon reads Project #4 via GraphQL as the sole source of truth for goal definitions and issue membership.

### Fuzzy Completion %

Per goal, computed from its issues on the project board:

| Issue State | Weight |
|-------------|--------|
| Open, no activity | 0% |
| Open, active branch commits | 20% |
| Open, PR in draft | 30% |
| Open, PR in review / CI running | 70% |
| PR merged / issue closed | 100% |

Effort weighting via labels: `effort:large` = 3x, `effort:medium` = 2x, `effort:small` = 1x.

Momentum factor: goals with activity in the last 48h get favorable risk assessment.

Goal completion = weighted average across all milestone issues.

### 3-Tier Progressive Autonomy

| Tier | Capabilities | Unlock |
|------|-------------|--------|
| **Tier 1** (default) | Observe + recommend for human tasks. **Auto-spawn 100% automatable tasks** (creates GH issue, adds to project, spawns task, links in Discord thread). Read-only for everything else. | On deploy |
| **Tier 2** | Also: reorder task queue, spawn follow-ups on stale PRs, flag blockers as GH comments, kill stuck tasks | `autonomy_tier: 2` in config |
| **Tier 3** | Full queue management: spawn human-in-loop tasks, reprioritize based on goal risk, decompose large tasks | `autonomy_tier: 3` in config |

**Auto-spawn guard rails (Tier 1):**

- Only tasks where `Auto: CC` (no human judgment needed)
- Must map to an existing MVP goal (has a milestone)
- Creates GH issue first (source of truth), then spawns
- Posts to Discord #ops with issue link before spawning
- Concurrent spawn limit: max 2 team-lead-originated tasks at once

### Proactive Velocity Features

The team lead doesn't just monitor — it actively looks for ways to accelerate:

1. **Unblocked task detection** — When a PR merges or task completes, check what it unblocks. If the unblocked task is CC-automatable, spawn it immediately.
2. **Parallelization** — Identify tasks with no mutual dependencies that could run concurrently. Spawn in parallel if automatable.
3. **Decomposition suggestions** — When a large human task is stale (>3 days no activity), suggest breaking it into CC-friendly subtasks.
4. **Pattern matching** — Notice when a task type that previously failed (50% success rate in registry) is about to be spawned. Suggest prompt improvements based on failure logs.
5. **Quick win mining** — Scan open issues, TODO.md, and co-founder briefings for small automatable improvements that aren't yet tracked as tasks.

### Lens Specialization

The team lead and project-pulse co-founder lens serve different purposes and should not overlap:

**Team lead** (continuous, operational):
- "What should happen next?"
- "What's blocked and what can unblock it?"
- "Which automatable tasks are ready to spawn?"
- Metrics-driven, event-driven

**Project-pulse** (Mon/Thu, strategic — rewritten prompt):
- "Are we working on the right things?"
- "Should priorities shift based on what we've learned?"
- "Is the MVP scope still right?"
- Judgment-driven, reads team lead metrics for context

### Event Model (Hybrid)

**Local events** (immediate, file watch):
- Task daemon writes to `task-events.jsonl`: `task_completed`, `task_failed`, `task_respawned`, `pr_created`, `pr_merged`
- Team lead reacts within seconds

**GitHub polling** (every 15 min, business hours 7AM-10PM AKST):
- PR merges, reviews, CI status, issue updates, milestone changes
- Cached to avoid redundant processing

**Data collection:** 24/7 (events always captured).
**Synthesis + Discord + spawning:** Business hours only (7AM-10PM AKST).
**Exception:** High-severity anomalies (master CI broken, goal regression) bypass quiet hours.

**Morning brief:** First synthesis after 7AM — summarizes overnight events, pre-computed action plan.

### Anomaly Detection

Handled entirely in the metrics engine (no AI). Each anomaly type has a 6h cooldown.

| Anomaly | Condition | Severity |
|---------|-----------|----------|
| Stale PR | CI green, no activity >48h | Medium |
| CI drift | Master CI failing >2h | High (bypasses quiet hours) |
| Stuck task | Running, no log activity >1h | High |
| Goal regression | Completion % decreased | High (bypasses quiet hours) |
| Velocity stall | Zero tasks completed in 3 days | Medium |
| Queue backup | >3 items queued for >1h | Medium |

### Synthesis (Agent SDK, Hourly)

Uses `claude-agent-sdk` `query()` with 3-turn budget:

1. **Turn 1:** Digest metrics + events
2. **Turn 2:** Assess goal risk, identify velocity opportunities
3. **Turn 3:** Produce structured JSON: `goal_status[]`, `recommendations[]`, `auto_spawn_candidates[]`, `health_summary`

Auto-spawn candidates that pass guard rails are immediately executed.
Recommendations for human tasks are posted to Discord #ops.
Both are deduplicated against a 24h cache.

### Auto-Spawn Flow

When the team lead identifies a 100% automatable task:

1. **Create GitHub Issue** — title, description, milestone (goal), labels
2. **Add to Project #4** — set Goal, Status=In Progress, Owner=Hurin, Priority
3. **Enqueue to task-daemon** — write to `task-queue.json` with issue number linked
4. **Post to Discord #ops** — "Spawned T-XX: [description] (Issue #NNN, Goal 1)"
5. **Track in Discord thread** — task daemon's existing Discord relay handles progress updates

## File Layout

```
~/.openclaw/team-lead/
  team-lead.py           # Main daemon (async Python, Agent SDK)
  config.py              # Paths, thresholds, quiet hours, autonomy_tier
  metrics-log.jsonl      # Event snapshots (rotated at 10K lines)
  metrics-daily.jsonl    # Daily rollups
  syntheses/             # Saved synthesis outputs per run
  dedup-cache.json       # 24h recommendation hashes
  daemon.log             # Operational log

~/.openclaw/monitor/
  task-events.jsonl      # Written by task-daemon, watched by team-lead

~/Library/LaunchAgents/
  ai.openclaw.teamlead.plist
```

Shares `~/.openclaw/monitor/.venv`. No new dependencies beyond what the task daemon already uses.

## Implementation Phases

1. **GitHub setup** — Create milestones for 3 goals. Add `Goal` field to Project #4. Tag existing issues with milestones + Goal field. Add effort labels.
2. **Data layer** — GitHub reader (milestones, project items, PRs, CI). Registry reader. Event file watcher for `task-events.jsonl`.
3. **Metrics engine** — Fuzzy completion %, velocity, anomaly detection, JSONL logging.
4. **Synthesis engine** — Agent SDK `query()`. Prompt design. Dedup. Discord posting to #planning.
5. **Auto-spawn pipeline** — GH issue creation, project sync, task-queue enqueue, Discord thread linking.
6. **LaunchAgent + morning brief** — plist, business hours gating, morning brief, lens prompt rewrite for project-pulse specialization.

## Consequences

### Positive

- Bridges the gap between strategic briefings (co-founder) and execution (task daemon)
- Proactive spawning of automatable tasks reduces Patrick's queue management overhead
- Fuzzy completion % gives real-time goal health without manual tracking
- GitHub-native goal state avoids local file drift and leverages existing tooling
- Morning brief pre-computes the day's action plan from overnight events
- Anomaly detection catches stuck tasks, broken CI, and stale PRs without manual monitoring
- Lens specialization sharpens both team-lead (operational) and project-pulse (strategic) outputs
- $0 cost — Agent SDK runs via Max plan CLI

### Negative

- Another daemon to monitor and maintain alongside task-daemon
- GitHub polling adds API calls (mitigated by 15-min interval and business hours gating)
- Fuzzy completion % is an approximation — may not match intuition on complex tasks
- Auto-spawning creates issues and tasks that Patrick didn't explicitly request (mitigated by guard rails and Tier 1 restrictions)

### Risks

- Auto-spawned tasks could produce low-quality PRs if guard rails aren't tight enough — Tier 1 limits exposure
- GitHub API rate limiting on heavy polling days (mitigated by caching and 15-min intervals)
- Agent SDK `query()` costs are $0 via Max plan but count against usage — hourly during business hours only
- Concurrent spawn limit (max 2) may need tuning as the system proves itself
- Goal regression detection could false-positive if issues are reorganized between milestones

## Related

- [ADR-0004: Co-Founder System](ADR-0004-co-founder-system.md) — strategic briefings, project-pulse lens
- [ADR-0005: Action System](ADR-0005-action-system.md) — action pipeline (human-approved; team lead auto-spawns separately)
- [ADR-0001: Agent Swarm Setup](ADR-0001-agent-swarm.md) — parent architecture
