# Plan: Collective Intelligence Architecture for Húrin

**Status:** Implemented — deployed 2026-03-10 (ADR-0009), cron entries pending Patrick approval
**Created:** 2026-03-10
**Author:** Patrick Kidd + Claude Opus 4.6
**Dependencies:** Three-agent architecture (ADR-0008, plans/three-agents.md)

---

## 1. Executive Summary

Transform three independently-operating AI agents (Huor, Tuor, Beren) into a genuine collective intelligence. The core intervention is **structured asynchronous cross-pollination with adversarial checkpoints** — not real-time negotiation (too expensive), not naive consensus (degrades quality), but directed signals that improve decisions beyond what any single agent would produce.

**Key principles from CI research:**
- Adversarial debate > cooperative consensus (Mitsubishi Electric, Jan 2026)
- 36.9% of multi-agent failures stem from inconsistent shared state (Cemri et al.)
- Sparse systems (< 5 agents) benefit more from strong per-agent memory than shared traces (MIT)
- Five memory types needed: Working, Episodic, Semantic, Procedural, Shared
- Communication topology matters: modular with loose inter-group connections outperforms both isolation and excessive density

**What this plan adds to the existing system:**

| Memory Type | Current State | After This Plan |
|-------------|--------------|-----------------|
| Working | Per-agent prompt context | No change (correct as-is) |
| Episodic | None | `knowledge/shared/episodes.jsonl` — task outcome histories |
| Semantic | `knowledge/` KB (6 domains) | No change (correct as-is) |
| Procedural | spawn-policy, prompt archaeology | Enhanced with cross-agent calibration |
| Shared | None | `knowledge/shared/state.json` + `signals.jsonl` |

---

## 2. Architecture: The Signal Bus Model

### 2.1 Design Philosophy

Agents communicate **asynchronously via structured files**, not real-time message passing. This is optimal for our constraints:
- 2GB RAM VPS — no room for persistent WebSocket connections or message queues
- 3 agents — too sparse for environmental trace coordination (MIT ρ ≥ 0.20 threshold)
- Cron-scheduled runs — agents activate at predictable intervals, not continuously
- Auditability — file-based communication creates a complete paper trail

### 2.2 New Shared State Files

```
~/.openclaw/knowledge/shared/
├── state.json          # Alignment anchor — ground truth for all agents
├── signals.jsonl       # Cross-agent signal bus (append-only)
├── episodes.jsonl      # Task outcome histories with extracted lessons
├── calibrations.jsonl  # Adversarial challenge outcomes (who was right)
└── weekly-insights.md  # Cross-correlation insights (generated weekly)
```

### 2.3 Coordination File: `state.json`

The **single source of truth** that prevents the 36.9% interagent misalignment failure mode. All agents read this before every run. Only Patrick writes to `sprint_focus`, `patrick_last_said`, and `do_not_touch`.

```json
{
  "last_updated": "2026-03-10T09:00:00Z",
  "updated_by": "patrick",
  "sprint_focus": "btcopilot auth layer + fd issue backlog",
  "active_decisions": [
    {
      "id": "dec-001",
      "decision": "Whether to split fdserver into separate auth service",
      "status": "pending_tuor_analysis",
      "deadline": "2026-03-14",
      "assigned_to": "tuor"
    }
  ],
  "blocked_on": [
    "Patrick review of PR #142",
    "CI fix for fdserver"
  ],
  "patrick_last_said": "Focus on btcopilot MVP. Don't touch fdserver architecture yet.",
  "do_not_touch": ["fdserver auth architecture until decision resolved"],
  "current_week_theme": "Unblock btcopilot personal app MVP"
}
```

**Rules:**
- Patrick-controlled fields: `sprint_focus`, `patrick_last_said`, `do_not_touch`, `current_week_theme`
- Agent-writable fields: `active_decisions[].status`, `blocked_on` (append only, Patrick removes)
- All agents read before every run — violations logged as alignment misses

### 2.4 Signal Bus: `signals.jsonl`

Lightweight append-only log of cross-agent information. Each entry is a structured signal from one agent to another.

```jsonl
{"ts": "2026-03-10T09:15:00Z", "from": "huor", "to": "tuor", "type": "anomaly", "signal": "fdserver PR cycle time 3x baseline — 4 consecutive PRs", "confidence": 0.87, "source_artifact": "synthesis-2026-03-10"}
{"ts": "2026-03-10T09:15:00Z", "from": "huor", "to": "beren", "type": "metric", "signal": "spawn accuracy dropped to 62% this week (5/8)", "confidence": 0.95, "source_artifact": "synthesis-2026-03-10"}
{"ts": "2026-03-11T09:03:00Z", "from": "tuor", "to": "huor", "type": "priority_shift", "signal": "btcopilot auth layer blocks 3 downstream features — suggest reprioritize", "confidence": 0.78, "source_artifact": "briefing-architecture-2026-03-11"}
{"ts": "2026-03-11T09:03:00Z", "from": "beren", "to": "tuor", "type": "challenge", "signal": "Your architecture lens recommended microservices split but velocity data shows team is faster with monolith — reconcile", "confidence": 0.82, "source_artifact": "digest-2026-03-11"}
```

**Schema:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ts` | ISO 8601 | Yes | Timestamp of signal emission |
| `from` | string | Yes | Emitting agent: `huor`, `tuor`, `beren`, `system` |
| `to` | string | Yes | Target agent (or `all` for broadcast) |
| `type` | enum | Yes | Signal type (see below) |
| `signal` | string | Yes | Human-readable signal content (< 500 chars) |
| `confidence` | float | Yes | 0.0–1.0 emitter's confidence in the signal |
| `source_artifact` | string | No | Which artifact generated this signal |
| `consumed` | bool | No | Whether target agent has read this signal |
| `influenced_decision` | string | No | Set after the fact if signal influenced a decision |

**Signal Types:**

| Type | Flow | Description |
|------|------|-------------|
| `anomaly` | Huor → Tuor, Beren | Operational anomaly detected |
| `metric` | Huor → Beren | Key metric change |
| `priority_shift` | Tuor → Huor | Strategic priority recommendation |
| `architecture_insight` | Tuor → Huor, Beren | Technical architecture finding |
| `challenge` | Beren → Tuor, Huor | Adversarial challenge to a recommendation |
| `red_team` | Beren → Tuor | Red-team result on a recommendation |
| `pre_mortem` | Beren → system | Pre-mortem on a spawn proposal |
| `calibration` | Any → Any | Feedback on a previous signal's accuracy |
| `process_correction` | Beren → Huor | System improvement directive |
| `cross_correlation` | Beren → all | Pattern spanning multiple agents' data |
| `lesson_learned` | system → all | Extracted lesson from task completion |

**Rules:**
- Max **5 signals per agent per run** (forces prioritization)
- Signals expire after **14 days** (pruned weekly by cron)
- Signals are *inputs to reasoning*, not commands
- Consumed signals are marked `consumed: true` (prevents re-processing)
- Signals that influenced a decision get `influenced_decision` annotated (for efficacy tracking)

### 2.5 Episodic Memory: `episodes.jsonl`

Task outcome histories with extracted lessons — the missing memory type.

```jsonl
{"ts": "2026-03-10T14:30:00Z", "task_id": "fd-142", "repo": "familydiagram", "outcome": "merged", "duration_hrs": 3.2, "spawned_by": "huor", "lessons": ["QML property bindings need explicit null checks", "Test setup for Scene required mock Timeline"], "tags": ["qml", "testing"], "cross_agent_signals_consumed": ["signal-tuor-2026-03-09"]}
{"ts": "2026-03-09T11:00:00Z", "task_id": "bt-87", "repo": "btcopilot", "outcome": "abandoned", "duration_hrs": 6.1, "spawned_by": "huor", "lessons": ["Auth middleware refactor too large for single task — split into 3"], "tags": ["scope", "btcopilot", "auth"], "cross_agent_signals_consumed": []}
```

**Written by:** `task-daemon.py` on task completion. CC extracts lessons from the session transcript.
**Read by:** All three agents — Huor for spawn sizing, Tuor for grounding strategy, Beren for system evaluation.

### 2.6 Calibrations: `calibrations.jsonl`

Tracks adversarial challenge outcomes — who was right when agents disagreed.

```jsonl
{"ts": "2026-03-12T10:00:00Z", "challenge_id": "cal-001", "challenger": "beren", "challenged": "tuor", "topic": "fdserver microservices split", "beren_position": "Monolith velocity advantage outweighs architecture concerns", "tuor_position": "Separation of concerns critical for long-term maintainability", "patrick_decided": "agree_with_beren", "lesson": "Tuor over-weights architectural elegance vs delivery speed for current team size", "category": "architecture"}
```

**Written by:** Patrick (via a simple CLI or manual edit) when resolving a disagreement.
**Read by:** All agents — calibrates future reasoning. Beren tracks challenge accuracy.

---

## 3. Cross-Pollination Protocols

### 3.1 Directed Information Flows

| From → To | What Flows | When | Why |
|-----------|-----------|------|-----|
| Huor → Tuor | Velocity anomalies, PR pattern shifts, CI failure clusters, task outcome patterns | Each synthesis | Grounds strategy in operational reality |
| Huor → Beren | Spawn outcomes, task durations, metric deltas, success/failure rates | Each synthesis | Feeds meta-evaluation |
| Tuor → Huor | Priority recommendations, strategic context, architecture decisions | Each briefing | Prevents Huor optimizing for wrong goals |
| Tuor → Beren | Recommendations + confidence levels, strategic assumptions | Each briefing | Enables red-teaming |
| Beren → Huor | Process corrections, system improvement tasks, calibration feedback | Each digest | Closes feedback loop |
| Beren → Tuor | Recommendation quality scores, blind spots, challenge results | Each digest | Calibrates strategic confidence |

### 3.2 Cross-Read Injection

Each agent's prompt is modified to include the other two agents' latest artifacts + addressed signals.

**Prerequisite:** The `shared_memory` module (§6) must be installed at `~/.openclaw/monitor/shared_memory.py` and importable. All agent scripts already have `sys.path.insert(0, str(HOME / ".openclaw/monitor"))`.

**Helper function** (add to each agent script or to `shared_memory.py`):

```python
import glob as _glob

def get_latest_file(directory, pattern="*", max_chars=2000):
    """Return content of most recent file matching pattern in directory.
    Returns None if no files found. Truncates to max_chars."""
    from pathlib import Path
    d = Path(directory)
    if not d.exists():
        return None
    files = sorted(d.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return None
    content = files[0].read_text(errors="replace")
    return content[:max_chars] if max_chars else content
```

**Key paths used below:**

| Variable | Path | Format |
|----------|------|--------|
| `BRIEFINGS_DIR` | `~/.openclaw/co-founder/briefings/` | Markdown (`.md`) |
| `DIGESTS_DIR` | `~/.openclaw/chief-of-staff/digests/` | Markdown (`.md`) |
| `SYNTHESES_DIR` | `~/.openclaw/team-lead/syntheses/` | JSON (`.json`) with `synthesis` key containing markdown text |

#### Huor Synthesis (`team_lead.py :: run_synthesis()`)

Add before the synthesis prompt (around line 1231 in `team_lead.py`):

```python
# === Cross-Agent Context ===
cross_context = "\n## Cross-Agent Context\n"

# Latest Tuor briefing (markdown)
latest_briefing = get_latest_file(BRIEFINGS_DIR, "*.md")
if latest_briefing:
    cross_context += f"\n### Latest Co-Founder Briefing (Tuor)\n{latest_briefing[:2000]}\n"

# Latest Beren digest (markdown)
latest_digest = get_latest_file(DIGESTS_DIR, "*.md")
if latest_digest:
    cross_context += f"\n### Latest Chief of Staff Digest (Beren)\n{latest_digest[:2000]}\n"

# Signals addressed to Huor
from shared_memory import read_signals
huor_signals = read_signals("huor")
if huor_signals:
    cross_context += "\n### Signals Addressed to You\n"
    for s in huor_signals[-5:]:
        cross_context += f"- [{s['type']}] from {s['from']}: {s['signal']} (confidence: {s['confidence']})\n"

# Shared state
from shared_memory import read_state
state = read_state()
if state:
    cross_context += f"\n### Current Sprint Focus\n{state.get('sprint_focus', 'Not set')}\n"
    cross_context += f"Patrick last said: {state.get('patrick_last_said', 'N/A')}\n"

# Recent episodes
from shared_memory import read_recent_episodes
episodes = read_recent_episodes(limit=5)
if episodes:
    cross_context += "\n### Recent Task Outcomes\n"
    for ep in episodes:
        cross_context += f"- {ep['task_id']} ({ep['outcome']}): {'; '.join(ep['lessons'][:2])}\n"

# Append instruction
cross_context += """
### Cross-Pollination Instructions
- If Tuor has recommended a priority shift, address it explicitly — agree and reorder, or explain why current order is better.
- If Beren has issued a process correction, incorporate it.
- After completing your synthesis, emit up to 3 signals to Tuor and/or Beren about operational findings they should know about.
"""

prompt = cross_context + "\n" + prompt  # Prepend to existing synthesis prompt
```

#### Tuor Briefing (`co-founder-sdk.py`)

Add similar cross-read section. Note: synthesis files are JSON with a `synthesis` key containing markdown.

```python
cross_context = "\n## Operational Reality Check (from Huor)\n"

# Latest synthesis (JSON format — extract the 'synthesis' markdown field)
latest_synthesis_path = get_latest_file(SYNTHESES_DIR, "*.json")
if latest_synthesis_path:
    # get_latest_file returns content as string; parse JSON to extract synthesis text
    try:
        data = json.loads(latest_synthesis_path)
        cross_context += f"\n### Latest Team Lead Synthesis\n{data.get('synthesis', '')[:2000]}\n"
    except json.JSONDecodeError:
        pass  # Skip if malformed

# Latest Beren digest
latest_digest = get_latest_file(DIGESTS_DIR, "*.md")
if latest_digest:
    cross_context += f"\n### Latest Chief of Staff Digest (Beren)\n{latest_digest[:2000]}\n"

# Signals for Tuor
tuor_signals = read_signals("tuor")
if tuor_signals:
    cross_context += "\n### Signals Addressed to You\n"
    for s in tuor_signals[-5:]:
        cross_context += f"- [{s['type']}] from {s['from']}: {s['signal']} (confidence: {s['confidence']})\n"

# Episodes
episodes = read_recent_episodes(limit=5)
if episodes:
    cross_context += "\n### Recent Task Outcomes\n"
    for ep in episodes:
        cross_context += f"- {ep['task_id']} ({ep['outcome']}, {ep['duration_hrs']}h): {'; '.join(ep['lessons'][:2])}\n"

cross_context += """
### Cross-Pollination Instructions
- If your strategic recommendations conflict with the operational data above, explicitly acknowledge the tension and explain why your recommendation still holds — or revise it.
- Ground your analysis in real velocity and outcome data, not aspirational projections.
- After completing your briefing, emit up to 3 signals to Huor and/or Beren.
"""
```

#### Beren Digest (`chief-of-staff.py`)

Already reads multiple sources. Add:

```python
# Signals for Beren
beren_signals = read_signals("beren")

# Calibration history
calibrations = read_recent_calibrations(limit=10)

# Episodes
episodes = read_recent_episodes(limit=10)

# Add to prompt:
cross_additions = """
## Cross-Correlation Task (MANDATORY)
After reading all inputs, perform this analysis:
1. Identify at least ONE pattern that spans Huor's operational data AND Tuor's strategic analysis that neither would catch alone. If none exists, say so — do not fabricate.
2. Check if any current task priorities conflict with the shared state sprint focus.
3. Review the calibration history — are your challenges getting more or less accurate over time?

## Red Team: Co-Founder's Top Recommendation
Take Tuor's highest-confidence recommendation from the latest briefing and argue AGAINST it:
- What evidence would need to be true for this recommendation to be wrong?
- What is Tuor's lens NOT seeing?
- What's the cost of following this if wrong vs ignoring if right?
Score: PROCEED / MODIFY / DELAY with reasoning.

## Signals Addressed to You
{formatted_signals}

## Recent Calibration History
{formatted_calibrations}

## Cross-Pollination Instructions
After completing your digest, emit up to 3 signals. At least one MUST be a challenge or cross-correlation finding.
"""
```

### 3.3 Signal Emission (Post-Run)

After each agent completes its main task, it emits signals. Two approaches:

**Approach A (Recommended): In-prompt emission with structured output parsing.**

Add to the end of each agent's prompt:

```
## Signal Emission (MANDATORY)
After your main output, emit 1-5 signals for other agents on a SEPARATE line starting with `SIGNALS_JSON:`.
Format: SIGNALS_JSON: [{"to": "tuor", "type": "anomaly", "signal": "< 500 chars", "confidence": 0.8}, ...]

Valid "to" values: huor, tuor, beren
Valid "type" values: anomaly, metric, priority_shift, architecture_insight, challenge, red_team, calibration, process_correction, cross_correlation, lesson_learned
Only emit signals that would genuinely help the target agent. Do NOT emit low-value or obvious signals.
```

**Parsing code** (add to each agent script after receiving CC output):

```python
import re
from shared_memory import append_signal

def extract_and_emit_signals(cc_output, from_agent, source_artifact=None):
    """Parse SIGNALS_JSON line from CC output and write to signal bus.
    Returns list of emitted signals."""
    emitted = []
    for line in cc_output.split("\n"):
        if line.strip().startswith("SIGNALS_JSON:"):
            json_str = line.split("SIGNALS_JSON:", 1)[1].strip()
            try:
                signals = json.loads(json_str)
                if not isinstance(signals, list):
                    continue
                for s in signals[:5]:  # Hard cap at 5
                    if not all(k in s for k in ("to", "type", "signal", "confidence")):
                        continue  # Skip malformed entries
                    append_signal(
                        from_agent=from_agent,
                        to_agent=s["to"],
                        signal_type=s["type"],
                        signal=str(s["signal"])[:500],
                        confidence=min(max(float(s.get("confidence", 0.5)), 0.0), 1.0),
                        source_artifact=source_artifact,
                    )
                    emitted.append(s)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                log.warning(f"Failed to parse signals JSON: {e}")
    return emitted

# Usage in each agent script, after receiving synthesis/briefing/digest:
signals = extract_and_emit_signals(cc_output, from_agent="huor", source_artifact=f"synthesis-{date}")
log.info(f"Emitted {len(signals)} cross-agent signals")
```

**Approach B (Simpler, lower quality):** Post-process output with a second lightweight CC call to extract signals. More expensive (extra API call) but doesn't require modifying the main prompt. Use Approach A unless prompt changes are blocked.

---

## 4. Adversarial Improvement Protocols

### 4.1 Priority Challenges (Tuor → Huor)

**Schedule:** Every Tuor briefing (currently triggered by cron when lenses resume)
**Mechanism:** Add to Tuor's briefing prompt

```
## Priority Challenge (MANDATORY)
Review Huor's current task queue and active tasks (from the synthesis above).
Identify the single highest-priority task that you believe is WRONG to prioritize right now.
Argue why — cite strategic context, opportunity cost, or dependency analysis that
Huor's operational lens would miss.

If the current prioritization is actually correct, say so and explain why.
Do NOT manufacture disagreement — only challenge when you genuinely see a problem.

Output format:
### Priority Challenge
**Target task:** [task ID or description]
**My argument:** [why this is wrong to prioritize now]
**What should be prioritized instead:** [alternative]
**Confidence:** [0.0-1.0]
```

### 4.2 Red-Teaming Recommendations (Beren → Tuor)

**Schedule:** Every Beren digest (Tuesday + Friday)
**Mechanism:** Included in Beren's digest prompt (see §3.2 above)

The red-team output becomes a first-class section of the digest. Patrick sees:
1. Tuor's recommendation
2. Beren's counter-argument
3. Beren's score (PROCEED / MODIFY / DELAY)

This is the adversarial debate pattern (Mitsubishi Electric, 2026) implemented asynchronously.

### 4.3 Spawn Pre-Mortems (Beren → System)

**Trigger:** When a spawn is proposed with confidence < 0.85
**Mechanism:** In `task-daemon.py`

```python
def maybe_request_premortem(task_id, description, confidence, repo):
    """Request a pre-mortem from Beren for low-confidence spawns."""
    if confidence >= 0.85:
        return

    from shared_memory import append_signal
    append_signal(
        from_agent="system",
        to_agent="beren",
        signal_type="pre_mortem_request",
        signal=f"Proposed spawn: {task_id} in {repo} — '{description}'. "
               f"Confidence: {confidence}. Argue why this will fail.",
        confidence=confidence,
    )
```

Beren picks this up in the next digest run and produces a pre-mortem. Patrick sees both the proposal and the pre-mortem before approving.

### 4.4 Calibration Loop

After Patrick makes a decision that resolves an agent disagreement:

1. Write a calibration entry to `calibrations.jsonl` (via CLI helper or manual)
2. Both agents read the calibration in their next run
3. Beren tracks challenge accuracy over time
4. Trust ledger categories can be extended to include "adversarial_accuracy"

**CLI helper:**

```bash
# ~/.openclaw/scripts/calibrate.sh
#!/bin/bash
# Usage: calibrate.sh <challenger> <challenged> <topic> <winner> <lesson>
echo "{\"ts\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"challenger\": \"$1\", \"challenged\": \"$2\", \"topic\": \"$3\", \"patrick_decided\": \"agree_with_$4\", \"lesson\": \"$5\"}" >> ~/.openclaw/knowledge/shared/calibrations.jsonl
```

---

## 5. Emergent Capability Design

### 5.1 Cross-Domain Correlation (Beren's Superpower)

Beren reads both Huor's operational data and Tuor's strategic analysis. The explicit cross-correlation prompt (§3.2) produces insights like:

- Huor sees: "PR cycle time for fdserver 3x baseline"
- Tuor sees: "Architecture lens flags fdserver as high coupling"
- **Beren synthesizes:** "fdserver needs targeted refactoring before more features — velocity data confirms the architecture concern"

### 5.2 Anomaly Triangulation

When Huor detects an anomaly, check if other agents have recently flagged the same area:

```python
def check_triangulation(anomaly_area, signals):
    """Boost confidence when multiple agents flag the same area."""
    related = [s for s in signals if anomaly_area.lower() in s['signal'].lower() and s['from'] != 'huor']
    if related:
        return {
            'triangulated': True,
            'confidence_boost': 1.3,
            'corroborating_agents': [s['from'] for s in related],
            'note': f"Triangulated with {related[0]['from']}: {related[0]['signal'][:100]}"
        }
    return {'triangulated': False, 'confidence_boost': 1.0}
```

### 5.3 Weekly Cross-Correlation Round

**Schedule:** 1 hour after Monday synthesis (cron: `0 10 * * 1`)
**Script:** `~/.openclaw/scripts/weekly-insight.py`

```python
#!/usr/bin/env python3
"""
Weekly Cross-Correlation — emergent insight extraction.

Reads all three agents' latest outputs + signal bus + episodes.
Asks Opus to find patterns that span multiple agents' data.
Writes to knowledge/shared/weekly-insights.md and posts to Discord.

Usage: uv run --directory ~/.openclaw/monitor python ~/.openclaw/scripts/weekly-insight.py
Cron:  0 10 * * 1   (1hr after Monday synthesis)
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
sys.path.insert(0, str(HOME / ".openclaw/monitor"))

from shared_memory import read_signals, read_recent_episodes, read_recent_calibrations, read_state

SYNTHESES_DIR = HOME / ".openclaw/team-lead/syntheses"
DIGESTS_DIR = HOME / ".openclaw/chief-of-staff/digests"
BRIEFINGS_DIR = HOME / ".openclaw/co-founder/briefings"
INSIGHTS_FILE = HOME / ".openclaw/knowledge/shared/weekly-insights.md"


def get_latest_file_content(directory, pattern="*", max_chars=3000):
    d = Path(directory)
    if not d.exists():
        return "No data available."
    files = sorted(d.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return "No data available."
    return files[0].read_text(errors="replace")[:max_chars]


async def main():
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

    # Gather all context
    synthesis = get_latest_file_content(SYNTHESES_DIR, "*.json")
    digest = get_latest_file_content(DIGESTS_DIR, "*.md")
    briefing = get_latest_file_content(BRIEFINGS_DIR, "*.md")
    signals = read_signals("all", mark_consumed=False)  # Read all, don't mark consumed
    episodes = read_recent_episodes(limit=10)
    calibrations = read_recent_calibrations(limit=5)
    state = read_state()

    signals_text = "\n".join(
        f"- [{s['type']}] {s['from']}→{s['to']}: {s['signal']}" for s in signals[-20:]
    ) or "No signals yet."

    episodes_text = "\n".join(
        f"- {ep['task_id']} ({ep['outcome']}): {'; '.join(ep.get('lessons', [])[:2])}" for ep in episodes
    ) or "No episodes yet."

    cal_text = "\n".join(
        f"- {c['challenger']} vs {c['challenged']}: {c['topic']} → {c['patrick_decided']}" for c in calibrations
    ) or "No calibrations yet."

    prompt = f"""You are analyzing a 3-agent AI system (Huor=operations, Tuor=strategy, Beren=meta-evaluation).

## Latest Huor Synthesis (operations)
{synthesis[:2000]}

## Latest Tuor Briefing (strategy)
{briefing[:2000]}

## Latest Beren Digest (meta-evaluation)
{digest[:2000]}

## Signal Bus (recent cross-agent signals)
{signals_text}

## Recent Task Outcomes (episodic memory)
{episodes_text}

## Calibration History (adversarial outcomes)
{cal_text}

## Current Sprint Focus
{state.get('sprint_focus', 'Not set')}

## Your Task
Identify the 1-3 most important insights that SPAN MULTIPLE agents' data — patterns that no individual agent stated but that emerge from combining their perspectives.

For each insight:
1. Which agents' data does it combine?
2. What is the insight?
3. What action does it suggest?
4. How confident are you? (0.0-1.0)

If there are no genuine cross-agent insights this week, say so honestly. Do not fabricate.
"""

    client = ClaudeSDKClient()
    options = ClaudeAgentOptions(model="claude-opus-4-6", max_turns=3)
    result = await client.query(prompt, options=options)

    # Write insight
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    header = f"\n\n---\n## Week of {date}\n\n"
    INSIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing = INSIGHTS_FILE.read_text() if INSIGHTS_FILE.exists() else "# Weekly Cross-Correlation Insights\n"
    INSIGHTS_FILE.write_text(existing + header + result.text + "\n")

    print(f"Insight written to {INSIGHTS_FILE}")
    # Optionally post to Discord (import discord_relay if available)


if __name__ == "__main__":
    asyncio.run(main())
```

### 5.4 Feedback-Driven Calibration

Track calibration accuracy by agent and category over time. This creates a meta-learning loop:

```
calibration accuracy → agent prompt weighting → better decisions → more calibrations
```

---

## 6. Shared Memory Utility Module

### `~/.openclaw/monitor/shared_memory.py`

```python
"""
Shared memory utilities for cross-agent communication.

Used by: team_lead.py, co-founder-sdk.py, chief-of-staff.py, task-daemon.py
Provides: signal bus, episode log, coordination state, calibration tracking
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

SHARED_DIR = Path.home() / ".openclaw/knowledge/shared"

# --- State ---

def read_state():
    """Read the coordination state file."""
    path = SHARED_DIR / "state.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)

# --- Signals ---

def append_signal(from_agent, to_agent, signal_type, signal, confidence=0.8, source_artifact=None):
    """Append a signal to the bus."""
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "from": from_agent,
        "to": to_agent,
        "type": signal_type,
        "signal": signal[:500],  # Enforce max length
        "confidence": round(confidence, 2),
        "consumed": False,
    }
    if source_artifact:
        entry["source_artifact"] = source_artifact
    with open(SHARED_DIR / "signals.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")

def read_signals(for_agent, max_age_days=14, mark_consumed=True):
    """Read unconsumed signals for an agent."""
    path = SHARED_DIR / "signals.jsonl"
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    signals = []
    all_lines = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                s = json.loads(line)
            except json.JSONDecodeError:
                all_lines.append(line)
                continue
            ts = datetime.fromisoformat(s["ts"].replace("Z", "+00:00"))
            if s.get("to") in (for_agent, "all") and ts > cutoff and not s.get("consumed"):
                signals.append(s)
                if mark_consumed:
                    s["consumed"] = True
            all_lines.append(json.dumps(s))
    if mark_consumed:
        with open(path, "w") as f:
            f.write("\n".join(all_lines) + "\n")
    return signals

def prune_signals(max_age_days=14):
    """Remove signals older than max_age_days."""
    path = SHARED_DIR / "signals.jsonl"
    if not path.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    kept = []
    pruned = 0
    with open(path) as f:
        for line in f:
            try:
                s = json.loads(line.strip())
                ts = datetime.fromisoformat(s["ts"].replace("Z", "+00:00"))
                if ts > cutoff:
                    kept.append(line.rstrip())
                else:
                    pruned += 1
            except (json.JSONDecodeError, KeyError):
                kept.append(line.rstrip())
    with open(path, "w") as f:
        f.write("\n".join(kept) + "\n" if kept else "")
    return pruned

# --- Episodes ---

def append_episode(task_id, repo, outcome, duration_hrs, lessons, tags, signals_consumed=None):
    """Record a task outcome with lessons learned."""
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "repo": repo,
        "outcome": outcome,
        "duration_hrs": round(duration_hrs, 1),
        "lessons": lessons[:5],  # Max 5 lessons per episode
        "tags": tags,
        "cross_agent_signals_consumed": signals_consumed or [],
    }
    with open(SHARED_DIR / "episodes.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")

def read_recent_episodes(limit=10):
    """Read the most recent episodes."""
    path = SHARED_DIR / "episodes.jsonl"
    if not path.exists():
        return []
    episodes = []
    with open(path) as f:
        for line in f:
            try:
                episodes.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    return episodes[-limit:]

# --- Calibrations ---

def append_calibration(challenger, challenged, topic, winner, lesson, category="general"):
    """Record an adversarial calibration outcome."""
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "challenger": challenger,
        "challenged": challenged,
        "topic": topic,
        "patrick_decided": f"agree_with_{winner}",
        "lesson": lesson,
        "category": category,
    }
    with open(SHARED_DIR / "calibrations.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")

def read_recent_calibrations(limit=10):
    """Read the most recent calibrations."""
    path = SHARED_DIR / "calibrations.jsonl"
    if not path.exists():
        return []
    calibrations = []
    with open(path) as f:
        for line in f:
            try:
                calibrations.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    return calibrations[-limit:]

def get_calibration_accuracy(agent, category=None):
    """Calculate an agent's challenge accuracy."""
    path = SHARED_DIR / "calibrations.jsonl"
    if not path.exists():
        return {"total": 0, "correct": 0, "accuracy": 0.0}
    correct = 0
    total = 0
    with open(path) as f:
        for line in f:
            try:
                cal = json.loads(line.strip())
                if cal["challenger"] != agent:
                    continue
                if category and cal.get("category") != category:
                    continue
                total += 1
                if cal["patrick_decided"] == f"agree_with_{agent}":
                    correct += 1
            except (json.JSONDecodeError, KeyError):
                continue
    return {"total": total, "correct": correct, "accuracy": correct / max(total, 1)}

# --- Efficacy Metrics ---

def get_signal_stats():
    """Compute signal bus statistics for dashboard."""
    path = SHARED_DIR / "signals.jsonl"
    if not path.exists():
        return {}
    stats = {
        "total": 0,
        "consumed": 0,
        "influenced_decision": 0,
        "by_type": {},
        "by_flow": {},  # "from->to" -> count
        "by_agent": {},  # agent -> {sent, received}
    }
    with open(path) as f:
        for line in f:
            try:
                s = json.loads(line.strip())
                stats["total"] += 1
                if s.get("consumed"):
                    stats["consumed"] += 1
                if s.get("influenced_decision"):
                    stats["influenced_decision"] += 1
                t = s.get("type", "unknown")
                stats["by_type"][t] = stats["by_type"].get(t, 0) + 1
                flow = f"{s['from']}->{s['to']}"
                stats["by_flow"][flow] = stats["by_flow"].get(flow, 0) + 1
                stats["by_agent"].setdefault(s["from"], {"sent": 0, "received": 0})["sent"] += 1
                stats["by_agent"].setdefault(s["to"], {"sent": 0, "received": 0})["received"] += 1
            except (json.JSONDecodeError, KeyError):
                continue
    return stats

def get_episode_stats():
    """Compute episode statistics for dashboard."""
    path = SHARED_DIR / "episodes.jsonl"
    if not path.exists():
        return {}
    stats = {
        "total": 0,
        "by_outcome": {},
        "by_repo": {},
        "avg_duration_hrs": 0,
        "total_lessons": 0,
        "with_signals": 0,
    }
    total_duration = 0
    with open(path) as f:
        for line in f:
            try:
                ep = json.loads(line.strip())
                stats["total"] += 1
                outcome = ep.get("outcome", "unknown")
                stats["by_outcome"][outcome] = stats["by_outcome"].get(outcome, 0) + 1
                repo = ep.get("repo", "unknown")
                stats["by_repo"][repo] = stats["by_repo"].get(repo, 0) + 1
                total_duration += ep.get("duration_hrs", 0)
                stats["total_lessons"] += len(ep.get("lessons", []))
                if ep.get("cross_agent_signals_consumed"):
                    stats["with_signals"] += 1
            except (json.JSONDecodeError, KeyError):
                continue
    stats["avg_duration_hrs"] = round(total_duration / max(stats["total"], 1), 1)
    return stats
```

---

## 7. Collective Intelligence Dashboard

### 7.1 Purpose

A professional, data-driven visualization of the collective intelligence system that:
- Shows how information flows between agents
- Measures whether cross-pollination improves decision quality
- Tracks adversarial challenge accuracy
- Visualizes the signal bus, episode memory, and calibration history
- Provides an at-a-glance view of system health and CI efficacy

### 7.2 Implementation

A Python script (`~/.openclaw/monitor/ci-dashboard.py`) that:
1. Reads all data sources (signals, episodes, calibrations, telemetry, trust ledger, metrics)
2. Computes CI-specific metrics
3. Generates a self-contained HTML file with inline CSS/JS + Chart.js from CDN
4. Can be served via `python -m http.server` or opened locally

### 7.3 Dashboard Sections

1. **Agent Topology** — SVG network diagram showing 3 agents + signal flows with volume/type annotations
2. **Signal Bus Activity** — Timeline of signals, filterable by agent/type, with consumption and influence rates
3. **Cross-Pollination Efficacy** — % of signals consumed, % that influenced decisions, trend over time
4. **Adversarial Health** — Challenge frequency, accuracy by agent, calibration trends
5. **Episodic Memory** — Task outcomes, lessons learned, signal-influenced tasks vs baseline
6. **Alignment Score** — % of agent actions aligned with shared state sprint focus
7. **System Vitals** — Existing telemetry (PR latency, compute ROI, spawn accuracy) contextualized for CI

### 7.4 Key Metrics (CI-Specific)

| Metric | Formula | Target | Why |
|--------|---------|--------|-----|
| Signal Consumption Rate | consumed / total signals | > 80% | Signals are being read |
| Signal Influence Rate | influenced_decision / consumed | > 20% | Signals change behavior |
| Cross-Pollination Density | signals per agent per week | 3-10 | Not too sparse, not too noisy |
| Adversarial Challenge Rate | challenges per digest | 1-2 | Beren is doing its job |
| Challenge Accuracy | correct challenges / total | > 50% | Challenges are valuable |
| Episode Capture Rate | episodes / completed tasks | > 90% | Learning from outcomes |
| Lesson Reuse Rate | episodes cited in spawn prompts / total | > 30% | Memory is being applied |
| Alignment Score | aligned actions / total actions | > 90% | Agents respect shared state |
| Triangulation Events | anomalies flagged by 2+ agents | tracked | Emergent detection |
| Decision Quality Delta | outcomes with CI input vs without | tracked | The bottom line |

### 7.5 Dashboard Script Location

`~/.openclaw/monitor/ci-dashboard.py` — generates `~/.openclaw/monitor/ci-dashboard.html`

**Already implemented and tested.** The script reads all data sources listed in §7.4, computes CI-specific metrics, and generates a self-contained HTML dashboard with Chart.js visualizations + inline SVG topology diagram. Run:

```bash
uv run --directory ~/.openclaw/monitor python ci-dashboard.py
# Then serve:
cd ~/.openclaw/monitor && python -m http.server 8787
# Open: http://localhost:8787/ci-dashboard.html
```

Dashboard data sources: `knowledge/shared/signals.jsonl`, `knowledge/shared/episodes.jsonl`, `knowledge/shared/calibrations.jsonl`, `knowledge/shared/state.json`, `knowledge/self/telemetry.jsonl`, `monitor/trust-ledger.json`, `team-lead/metrics-log.jsonl`, `monitor/task-events.jsonl`, `workspace-hurin/theapp/.clawdbot/active-tasks.json`, `knowledge/self/spawn-policy.json`, plus file counts from `team-lead/syntheses/`, `chief-of-staff/digests/`, `co-founder/briefings/`.

---

## 8. Whitepaper

Full whitepaper notes maintained separately in **`plans/whitepaper-ci-psychology.md`** — self-contained for use in a separate drafting conversation.

Core thesis: Psychological systems theory (Bowen) provides a predictive framework for failure modes in multi-agent AI that pure CS approaches miss. Each concept maps to a design decision with a measurable metric. If a concept doesn't change a design choice or improve a KPI, it gets cut.

---

## 9. Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | What To Do Instead |
|---|---|---|
| **Naive consensus** ("agents vote on priority") | Averages expert + non-expert views, degrades quality | Adversarial challenges — each argues, Patrick decides |
| **Real-time debate loops** | Token burn, VPS fragility, audit trail gaps | Asynchronous artifacts — challenge in next run |
| **Shared full context** | Token bloat, agents drown in noise | Directed signals — 5 max per agent per run |
| **Agents modifying each other's configs** | Cascading failures | Only Patrick modifies configs |
| **Over-communication** | More channels = more noise | One signal bus, one state file, one episode log |
| **Consensus-seeking Beren** | Defeats metacognitive purpose | Beren's job is to disagree and find blind spots |
| **Adding a 4th agent** | Overhead > value at this scale | 3 is optimal for now |
| **Synchronous inter-agent calls** | SPOF, blocks on hangs | All communication is file-based, async |
| **Unbounded signal history** | Stale signals pollute reasoning | 14-day expiry + weekly prune |
| **Treating signals as commands** | Removes agent autonomy | Signals are *inputs to reasoning* |
| **Calibrating without Patrick** | Agents grading their own work | Only Patrick writes calibration entries |

---

## 10. Implementation Schedule

### Day 1: Foundation

- [ ] Create `~/.openclaw/knowledge/shared/` directory
- [ ] Create `state.json` (Patrick writes initial sprint focus)
- [ ] Create empty `signals.jsonl`, `episodes.jsonl`, `calibrations.jsonl`
- [ ] Write `~/.openclaw/monitor/shared_memory.py`
- [ ] Write `~/.openclaw/scripts/calibrate.sh`

### Day 2: Cross-Read Injection

- [ ] Modify `team_lead.py :: run_synthesis()` — add cross-agent context section
- [ ] Modify `co-founder-sdk.py` — add operational reality check section
- [ ] Modify `chief-of-staff.py` — add cross-correlation + red-team sections
- [ ] Test each modification with a dry-run

### Day 3: Signal Emission + Episode Capture

- [ ] Add signal emission to synthesis post-processing
- [ ] Add signal emission to co-founder briefing post-processing
- [ ] Add signal emission to COS digest post-processing
- [ ] Modify `task-daemon.py` completion handler to write episodes
- [ ] Add spawn pre-mortem signal generation

### Day 4: Adversarial Protocols + Dashboard

- [ ] Add Priority Challenge section to Tuor's prompt
- [ ] Add Red Team section to Beren's prompt
- [ ] Write `ci-dashboard.py`
- [ ] Add signal pruning to weekly cron

### Day 5: Validation + Documentation

- [ ] Manually trigger each agent, verify cross-reads
- [ ] Verify signal bus has entries
- [ ] Verify dashboard renders correctly
- [ ] Write ADR-0009
- [ ] Update CLAUDE.md with new paths
- [ ] Start baseline data collection for whitepaper

### Ongoing

- [ ] Weekly: Review dashboard metrics, write calibration entries
- [ ] Weeks 2-3: Literature review for whitepaper
- [ ] Weeks 3-6: Collect CI data, draft whitepaper sections
- [ ] Week 7: Polish whitepaper
- [ ] Week 8: Prepare Micron presentation

---

## 11. Files Created/Modified

| File | Change | Effort |
|---|---|---|
| `knowledge/shared/state.json` | NEW — alignment anchor | 10 min |
| `knowledge/shared/signals.jsonl` | NEW — signal bus | 5 min |
| `knowledge/shared/episodes.jsonl` | NEW — episodic memory | 5 min |
| `knowledge/shared/calibrations.jsonl` | NEW — adversarial tracking | 5 min |
| `knowledge/shared/weekly-insights.md` | NEW — cross-correlation output | auto-generated |
| `monitor/shared_memory.py` | NEW — utility module | 1 hr |
| `monitor/ci-dashboard.py` | NEW — dashboard generator | 2 hr |
| `scripts/calibrate.sh` | NEW — CLI helper | 10 min |
| `scripts/weekly-insight.py` | NEW — cross-correlation round | 30 min |
| `team-lead/team_lead.py` | MODIFIED — cross-read + signal emission | 1 hr |
| `co-founder/co-founder-sdk.py` | MODIFIED — cross-read + signal emission | 1 hr |
| `chief-of-staff/chief-of-staff.py` | MODIFIED — cross-correlation + red-team + signals | 1 hr |
| `monitor/task-daemon.py` | MODIFIED — episode capture + pre-mortem | 1 hr |
| `adrs/ADR-0009-collective-intelligence.md` | NEW — architecture decision | 30 min |
| `CLAUDE.md` | MODIFIED — new paths + CI references | 15 min |

**Total implementation effort: ~8-10 hours across the week.**

---

## 12. Success Criteria

After 4 weeks of operation:

1. **Signal bus has 50+ entries** — agents are communicating
2. **Signal consumption rate > 80%** — agents are reading signals
3. **At least 5 calibration entries** — Patrick is resolving disagreements
4. **Episode capture rate > 80%** — learning from outcomes
5. **At least 2 cross-correlation insights** — Beren finding patterns neither agent saw
6. **At least 1 priority challenge that changed task ordering** — adversarial improvement working
7. **Dashboard renders clean** — all metrics populated
8. **Whitepaper outline approved** — ready for drafting

After 8 weeks:

9. **Measurable decision quality delta** — comparing CI-informed vs baseline decisions
10. **Whitepaper draft complete** — ready for internal review at Micron
