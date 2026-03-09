# ADR-0007: Self-Evolving Agent System

**Status:** Accepted (2026-03-09)

**Context:** The agent system was sophisticated observation machinery that didn't learn, didn't act beyond code PRs, and didn't surprise. The co-founder lenses were paused. Auto-spawn was disabled at 10% accuracy. The system behaved identically on day 1 and day 100.

**Decision:** Build a self-evolving system with six capabilities: perception (telemetry), memory (knowledge base), reasoning (spawn policy engine), action (KB-aware lenses + research), evaluation (prompt archaeology + session learning), and adaptation (per-category autonomy graduation).

## Components

### 1. Knowledge Base (`~/.openclaw/knowledge/`)

Structured, retrievable, updatable memory across 6 domains:

```
knowledge/
  domain/       — Bowen theory, genograms, clinical workflow
  market/       — Competitors, conferences, AI therapy landscape, training programs
  technical/    — Agent architectures, self-improvement patterns, successful PR patterns
  strategy/     — MVP critical path, experiments log
  self/         — Spawn policy, telemetry, CC session learnings, capability gaps
  users/        — Communities, community signals
  index.md      — Structure + staleness policy
  research-log.md — Research agenda (one-time + ongoing)
```

**Staleness policy:** Entries > 30 days without update are flagged by COS. Each entry includes `Last verified:` date.

**Growth mechanism:** Co-founder lenses read KB before analysis, write NEW findings back. `/research <topic>` triggers targeted web research → KB.

### 2. Telemetry (`~/.openclaw/monitor/telemetry.py`)

Passive signal collection, runs every GitHub poll cycle (15 min) in team-lead:

| Collector | Signal | Why It Matters |
|-----------|--------|----------------|
| `collect_pr_review_latency()` | Hours from PR creation to merge/close | Which PRs get reviewed fast reveals what Patrick values |
| `collect_master_topics()` | Commit message topic clusters | Prevents agents from working in Patrick's active areas |
| `collect_compute_roi()` | Opus minutes on merged vs discarded work | Cost-effectiveness of agent compute |
| `collect_attention_signals()` | Discord thread reply counts | Proxy for which agent outputs Patrick reads |

Output: `knowledge/self/telemetry.jsonl` (JSONL, append-only).

### 3. Spawn Policy Engine (`trust_ledger.py` additions)

Per-category autonomy computed from trust ledger accuracy:

```
classify_task(description) → category (ci_fix, test_infra, feature, bugfix, ...)
get_spawn_autonomy(category) → "auto_spawn" | "propose_only" | "blocked"
update_spawn_policy() → recalculates from ledger, applies graduation rules
```

**Graduation rules:**
- `>= 80%` accuracy over `5+` proposals → `auto_spawn`
- `< 40%` accuracy over `5+` proposals → `blocked`
- Otherwise → `propose_only`

**Integration:**
- Task daemon calls `update_spawn_policy()` after each PR outcome
- Team-lead uses `get_spawn_autonomy()` instead of global `AUTONOMY_TIER` check
- `AUTONOMY_TIER=1` enables the policy engine (was 0 = all gated)
- Synthesis prompt includes spawn policy summary + PR patterns

### 4. CC Session Learner (`~/.openclaw/monitor/session_learner.py`)

Analyzes Patrick's interactive Claude Code sessions to identify capability gaps:

1. Scans `~/.claude/projects/` for JSONL transcripts
2. Classifies interactive (Patrick) vs daemon-spawned
3. Extracts problem type, files involved, tools used
4. Writes to `knowledge/self/cc-session-learnings.md` and `capability-gaps.md`
5. Runs weekly after synthesis in team-lead

**The insight:** Every time Patrick opens interactive CC, it means hurin failed to handle something. These sessions are both a failure signal and training data.

### 5. Prompt Archaeology (`~/.openclaw/monitor/analyze_prompts.py`)

Compares prompt characteristics of merged vs closed PRs:

- Scope (narrow vs broad)
- Specificity (file paths, line numbers, test commands)
- Error message presence
- Acceptance criteria
- Writes findings to `knowledge/technical/successful-pr-patterns.md`
- Runs weekly after synthesis

### 6. Enhanced COS + Co-Founder

**Chief of Staff** now reads: spawn policy, KB summary, telemetry, capability gaps. Output includes new SYSTEM EVOLUTION section evaluating whether the system is actually learning.

**Co-Founder** now: reads relevant KB entries before analysis, writes NEW findings back, checks research agenda for unfilled topics.

## Autonomy Model

| Tier | Actions | Examples |
|------|---------|---------|
| 0: Fully autonomous | No notification | KB updates, telemetry, policy recalc, logging |
| 1: Autonomous + notify | Post after | auto_spawn tasks, research → KB, drafts |
| 2: Propose + wait | Post before | propose_only tasks, content, experiments |
| 3: Never autonomous | Hard rules | Merge, push, external comms, spend money |

Tiers are NOT static — categories graduate from Tier 2 → Tier 1 by demonstrating accuracy. The spawn policy IS the graduation mechanism.

## Consequences

**Positive:**
- System accumulates institutional knowledge instead of losing it between sessions
- Spawn quality improves over time as patterns are identified and applied
- Patrick's interactive CC sessions teach the system what to automate next
- COS evaluates system evolution, not just project health
- Co-founder research builds competitive intelligence asset

**Negative:**
- More moving parts (6 new files, 6 modified files)
- KB could grow stale if lenses aren't run
- Spawn policy may be too conservative (80% threshold is high)
- Session learner uses keyword classification (not AI) — may miscategorize

**Risks:**
- KB entries could become contradictory without editorial review
- Telemetry JSONL could grow unbounded (needs rotation)
- Policy engine could block categories permanently if early data is bad

## Related

- [ADR-0006](ADR-0006-team-lead-daemon.md) — Team lead daemon (modified)
- [ADR-0005](ADR-0005-action-system.md) — Action system (unchanged)
- [ADR-0004](ADR-0004-co-founder-system.md) — Co-founder system (modified)
- Decision log entry: 2026-03-09 — Deploy self-evolving system
