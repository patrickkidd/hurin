# ADR-0001 Status: Agent Swarm Gap Analysis

**As-built:** [ADR-0001-agent-swarm.md](ADR-0001-agent-swarm.md)
**Reference article:** [elvis-agent-swarm-article.md](elvis-agent-swarm-article.md) (Elvis Sun, @elvissun, Feb 23 2026)
**Last updated:** 2026-03-03

## Architecture Comparison

| Layer | Elvis (2-tier) | Ours (2-tier) | Notes |
|-------|---------------|---------------|-------|
| Human | Elvis via Telegram | Patrick via Discord | Equivalent |
| Orchestrator | Zoe (single agent, Sonnet-class) | hurin (MiniMax M2.5) | Ours is cheaper; MiniMax is Sonnet-tier |
| Coding agents | Codex / Claude Code in tmux+worktrees | Claude Code (Opus 4.6) via Agent SDK + worktrees | Ours uses SDK instead of tmux |
| Communication | Telegram (one-way notifications) | Discord (native OpenClaw plugin, bidirectional + live steering) | Ours is more integrated |

## Feature Gap Tracker

Each row is a capability Elvis describes. Status indicates where we stand.

| # | Capability | Elvis | Us | Status | Priority | Notes |
|---|-----------|-------|----|--------|----------|-------|
| 1 | **Worktree isolation per task** | `git worktree add` + tmux | `task-daemon.py` automates worktree + SDK query + registry | DONE | — | SDK replaces tmux |
| 2 | **Task registry** | `.clawdbot/active-tasks.json` | `.clawdbot/active-tasks.json` | DONE | — | Identical pattern |
| 3 | **Continuous monitoring** | Shell script every 10 min | `task-daemon.py` LaunchAgent (continuous, ≤30s response) | DONE | — | Upgraded from cron to daemon |
| 4 | **Mid-task redirection** | `tmux send-keys` | Live steering via Discord thread replies | DONE | — | Better UX than tmux |
| 5 | **Respawn on failure** | Max 3 retries | `MAX_RESPAWNS = 3` + SDK session resume (full context) | DONE | — | Enhanced with session persistence |
| 6 | **Automated AI code review** | 3 reviewers: Codex, Gemini Code Assist (free), Claude Code | `review-prs.sh` (Claude) every 15 min | DONE | — | Gemini Code Assist is manual install step for Patrick |
| 7 | **Explicit definition of done** | PR + no conflicts + CI + 3 reviews + screenshots | Codified in SOUL.md, enforced in task-daemon.py | DONE | — | Review-aware done condition |
| 8 | **Proactive task discovery** | Zoe scans Sentry, meeting notes, git log; spawns agents unprompted | Team lead daemon (ADR-0006): scans GitHub, co-founder briefings, auto-spawns | DONE | — | Implemented via team-lead.py |
| 9 | **Auto-respawn with improved prompts** | Zoe analyzes failure + rewrites prompt with business context | Ralph Loop: SDK session resume with failure context, max 3x | DONE | — | |
| 10 | **Worktree cleanup automation** | Daily cron cleans orphaned worktrees + registry | task-daemon.py auto-cleans after PR creation | DONE | — | |
| 11 | **Model diversity / task routing** | Codex (backend), Claude Code (frontend/git), Gemini (design) | All-Anthropic: MiniMax router, Opus coders, Sonnet synthesis | DIFFERENT | Low | Not necessarily a gap |
| 12 | **Prompt pattern logging** | Logs what prompt structures work per task type | Not yet implemented (planned in SOUL.md Ralph Loop) | GAP | Low | |
| 13 | **Screenshot requirement for UI PRs** | CI fails if UI PR lacks screenshots | PR template + SOUL.md protocol + MCP servers | DONE | — | Not CI-enforced but documented and prompted |

### Status legend
- **DONE** — Implemented and working
- **GAP** — Elvis has it, we don't
- **DIFFERENT** — Different approach, not necessarily worse

## Resolved: 2-Tier vs 3-Tier

**Decision: Collapsed to 2-tier.** (2026-02-26)

The Haiku intelligence bottleneck at the coordinator layer (beren/tuor) was a net negative. Prompt quality is the highest-leverage variable, and Sonnet writing prompts directly beats Haiku with narrow context. beren/tuor archived.

See [archived 3-tier ADR](archive/ADR-0001-agent-swarm_2026-02-25_3tier.md) for the full analysis.

## Action Items

Ordered by priority. Check off as completed.

- [x] **(High)** Install automated Claude code review (`review-prs.sh`)
- [x] **(High)** Codify "definition of done" in hurin SOUL.md and enforce in task-daemon.py
- [ ] **(High)** Install Gemini Code Assist as a GitHub App (free) — manual step for Patrick: https://github.com/apps/gemini-code-assist
- [x] **(Medium)** Add proactive scanning — team lead daemon (ADR-0006) handles this
- [x] **(Medium)** Enhance failure handling: Ralph Loop with SDK session resume
- [x] **(Low)** Add worktree cleanup to task-daemon.py for completed tasks
- [ ] **(Low)** Add prompt pattern logging to hurin's memory system
- [x] **(Resolved)** 2-tier vs 3-tier decision — collapsed to 2-tier
