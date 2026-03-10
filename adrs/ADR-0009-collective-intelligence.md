# ADR-0009: Collective Intelligence Architecture

**Status:** Accepted

**Date:** 2026-03-10

**Deciders:** Patrick

**Related:** [ADR-0008: Three-Agent Architecture](ADR-0008-three-agent-architecture.md), [ADR-0007: Self-Evolving System](ADR-0007-self-evolving-system.md)

## Context

Three agents (Huor, Tuor, Beren) operate independently — each produces valuable intelligence but none sees the others' outputs. This creates blind spots:
- Huor optimizes task execution without strategic context from Tuor
- Tuor recommends priorities without grounding in Huor's operational reality
- Beren evaluates the system without structured feedback from either agent

Research findings that shaped this decision:
- Adversarial debate > cooperative consensus (Mitsubishi Electric, Jan 2026)
- 36.9% of multi-agent failures stem from inconsistent shared state (Cemri et al.)
- Sparse systems (< 5 agents) benefit more from strong per-agent memory than shared traces (MIT)
- Five memory types needed: Working, Episodic, Semantic, Procedural, Shared

## Decision

### 1. Shared State Layer

Add `knowledge/shared/` with four files:
- **`state.json`** — Alignment anchor. Patrick controls sprint focus, do_not_touch. All agents read before every run.
- **`signals.jsonl`** — Cross-agent signal bus. Append-only, max 5 signals/agent/run, 14-day expiry.
- **`episodes.jsonl`** — Task outcome histories with extracted lessons. Written by task-daemon on completion.
- **`calibrations.jsonl`** — Adversarial challenge outcomes. Written by Patrick when resolving disagreements.

### 2. Cross-Read Injection

Each agent's prompt is augmented with the other two agents' latest artifacts + addressed signals:
- Huor reads Tuor's latest briefing + Beren's latest digest + addressed signals
- Tuor reads Huor's latest synthesis + Beren's latest digest + addressed signals
- Beren reads both + performs mandatory cross-correlation + red-teams Tuor's top recommendation

### 3. Signal Emission

After each run, agents emit 1-5 structured signals parsed from their CC output (SIGNALS_JSON format). Signal types: anomaly, metric, priority_shift, architecture_insight, challenge, red_team, pre_mortem, calibration, process_correction, cross_correlation, lesson_learned.

### 4. Adversarial Protocols

- **Priority Challenges** (Tuor → Huor): Tuor challenges one priority per briefing
- **Red-Teaming** (Beren → Tuor): Beren argues against Tuor's top recommendation
- **Spawn Pre-Mortems** (System → Beren): Low-confidence spawns get pre-mortem signals
- **Calibration Loop**: Patrick records outcomes, all agents calibrate future reasoning

### 5. Episodic Memory

Task-daemon writes episodes on completion with extracted lessons, duration, outcome, tags. All agents read recent episodes to improve decision-making.

### 6. Weekly Cross-Correlation

`scripts/weekly-insight.py` runs 1hr after Monday synthesis, reads all agents' outputs + signal bus + episodes, asks Opus for patterns that span multiple agents' data.

## Implementation

- `monitor/shared_memory.py` — Utility module (signal bus, episodes, calibrations, state, context builders)
- `scripts/calibrate.sh` — CLI helper for recording calibrations
- `scripts/weekly-insight.py` — Weekly cross-correlation round
- Modified: `team_lead.py`, `co-founder-sdk.py`, `chief-of-staff.py`, `task-daemon.py`
- `ci-dashboard.py` already reads shared data files

## Consequences

**Positive:**
- Agents produce better-informed outputs grounded in each other's data
- Adversarial protocols catch blind spots before they reach Patrick
- Episodic memory creates a learning loop across task executions
- Shared state prevents the 36.9% interagent misalignment failure mode
- All communication is file-based and auditable

**Negative:**
- Larger prompts (cross-context adds ~2-4K tokens per agent run)
- Signal bus requires weekly pruning (automated via cron)
- New failure mode: stale/corrupted shared files could degrade agent reasoning

**Risks mitigated:**
- All CI integration is wrapped in try/except — failures are non-fatal
- Signal budget (5/agent/run) prevents noise
- 14-day expiry prevents stale signals
- Only Patrick writes to Patrick-controlled state fields

## Anti-Patterns Avoided

- No naive consensus or voting
- No real-time debate loops (all async via files)
- No agents modifying each other's configs
- No unbounded signal history
- Signals are inputs to reasoning, not commands
