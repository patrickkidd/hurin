# ADR-0001 Status: Agent Swarm Gap Analysis

**As-built:** [ADR-0001-agent-swarm.md](ADR-0001-agent-swarm.md)
**Reference article:** [elvis-agent-swarm-article.md](elvis-agent-swarm-article.md) (Elvis Sun, @elvissun, Feb 23 2026)
**Last updated:** 2026-02-26

## Architecture Comparison

| Layer | Elvis (2-tier) | Ours (2-tier) | Notes |
|-------|---------------|---------------|-------|
| Human | Elvis via Telegram | Patrick via Discord | Equivalent |
| Orchestrator | Zoe (single agent, Sonnet-class) | hurin (Sonnet 4.6) | Equivalent |
| Coding agents | Codex / Claude Code in tmux+worktrees | Claude Code (Opus 4.6) in tmux+worktrees | Match |
| Communication | Telegram (one-way notifications) | Discord (native OpenClaw plugin, bidirectional) | Ours is more integrated |

## Feature Gap Tracker

Each row is a capability Elvis describes. Status indicates where we stand.

| # | Capability | Elvis | Us | Status | Priority | Notes |
|---|-----------|-------|----|--------|----------|-------|
| 1 | **Worktree isolation per task** | `git worktree add` + tmux | `spawn-task.sh` automates worktree+tmux+registry | DONE | — | Ours is more automated |
| 2 | **Task registry** | `.clawdbot/active-tasks.json` | `.clawdbot/active-tasks.json` | DONE | — | Identical pattern |
| 3 | **Cron monitoring (tmux/PR/CI)** | Shell script every 10 min | `check-agents.py` every 10 min | DONE | — | Same approach |
| 4 | **Mid-task redirection** | `tmux send-keys` | Documented in hurin's TOOLS.md | DONE | — | |
| 5 | **Respawn on failure** | Max 3 retries | `MAX_RESPAWNS = 3` + Ralph Loop V2 | DONE | — | Enhanced with failure capture + prompt rewriting |
| 6 | **Automated AI code review** | 3 reviewers: Codex, Gemini Code Assist (free), Claude Code | `review-prs.sh` (Claude) every 15 min | DONE | — | Gemini Code Assist is manual install step for Patrick |
| 7 | **Explicit definition of done** | PR + no conflicts + CI + 3 reviews + screenshots | Codified in SOUL.md, enforced in check-agents.py | DONE | — | Review-aware done condition |
| 8 | **Proactive task discovery** | Zoe scans Sentry, meeting notes, git log; spawns agents unprompted | hurin waits for Patrick in #planning | GAP | Medium | Could scan GitHub issues, failing tests, stale PRs |
| 9 | **Auto-respawn with improved prompts** | Zoe analyzes failure + rewrites prompt with business context | Ralph Loop V2: failure capture + hurin rewrite + prompt-patterns.md | DONE | — | |
| 10 | **Worktree cleanup automation** | Daily cron cleans orphaned worktrees + registry | check-agents.py auto-cleans "done" task worktrees | DONE | — | |
| 11 | **Model diversity / task routing** | Codex (backend), Claude Code (frontend/git), Gemini (design) | All-Anthropic: Sonnet orchestrator, Opus coders | DIFFERENT | Low | Not necessarily a gap |
| 12 | **Prompt pattern logging** | Logs what prompt structures work per task type | `memory/prompt-patterns.md` in hurin workspace | DONE | — | |
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
- [x] **(High)** Codify "definition of done" in hurin SOUL.md and enforce in `check-agents.py`
- [ ] **(High)** Install Gemini Code Assist as a GitHub App (free) — manual step for Patrick: https://github.com/apps/gemini-code-assist
- [ ] **(Medium)** Add proactive scanning to hurin (open issues, failing tests, stale PRs)
- [x] **(Medium)** Enhance failure handling: Ralph Loop V2 with failure capture + prompt rewriting
- [x] **(Low)** Add worktree cleanup pass to `check-agents.py` for tasks with status "done"
- [x] **(Low)** Add prompt pattern logging to hurin's memory system
- [x] **(Resolved)** 2-tier vs 3-tier decision — collapsed to 2-tier
