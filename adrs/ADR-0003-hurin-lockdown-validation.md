# ADR-0003: Hurin Lockdown & Validation

**Status:** Accepted

**Date:** 2026-02-26

**Deciders:** Patrick

## Context

Hurin (Haiku 4.5 router) was intended to be a dumb pipe that routes all intelligence to Claude Code (CC) via `exec` + `claude -p`. In practice, hurin was acting autonomously — reading files, running shell commands, editing configs, and even moving the entire monorepo — all without delegating to CC.

Root cause: hurin's tool allowlist included `read`, `write`, and `edit` alongside `exec`. Haiku is not reliable enough to obey complex behavioral constraints ("don't use these tools") when the tools are available. The SOUL.md instructions said the right things, but a small model under pressure will use whatever tools it has.

The incident that triggered this: message `1476663124622053489` ("yes.") caused hurin to interpret a short reply as confirmation to move `~/Projects/theapp` → `~/.openclaw/workspace-hurin/theapp/`, running 15+ tool calls (mv, ls, uv sync, edit) directly on Haiku without any CC involvement.

## Decision

### Layer 1: Structural enforcement (tool allowlist)

Removed `read`, `write`, `edit` from hurin's tool allowlist. Hurin now only has:

```json
"tools": {
  "allow": ["exec", "sessions_list", "sessions_history", "session_status"]
}
```

If Haiku tries to read/write/edit files, the tool call is rejected by OpenClaw. This is not a prompt-level constraint — it's structural.

### Layer 2: Prompt hardening (SOUL.md)

Added `ABSOLUTE RULE` section at the top of SOUL.md:

> Every single message from Patrick MUST be routed to CC via `exec` + `claude -p`. No exceptions. Ever.

Exhaustive lists of what hurin does (5 steps) and never does (no shell commands, no file ops, no interpreting user intent).

### Layer 3: Thinking disabled

Set `agents.defaults.thinkingDefault: "off"`. Hurin's job is pattern matching (message → route to CC), not reasoning. Thinking tokens were billing at $4/MTok output rate for zero benefit.

### Layer 4: Session wipe

Wiped stale sessions that contained pre-lockdown context where hurin had been acting autonomously. Fresh sessions pick up the hardened SOUL.md.

## Validation Experiments

### Test results

| # | Prompt | Thinking | Routed to CC | CC duration | Cost |
|---|--------|----------|-------------|-------------|------|
| 1 | code review (thinking ON) | ON | Yes | ~4 min | $0.03/msg |
| 2 | code review learn view (thinking ON) | ON | Yes | ~4 min | $0.03/msg |
| 3 | count test files btcopilot (thinking OFF) | OFF | Yes | ~1 min | — |
| 4 | categorize familydiagram tests (thinking OFF) | OFF | Yes | ~5 min | $0.01 |
| 5 | categorize btcopilot tests (thinking OFF) | OFF | Yes | ~3 min | $0.03 |

### Cost analysis

| Config | Cost/msg | Why |
|--------|----------|-----|
| Thinking ON, ~20k session | ~$0.03 | Thinking tokens at $4/MTok output |
| Thinking OFF, fresh session | ~$0.01 | Minimal input, no thinking |
| Thinking OFF, ~18k session | ~$0.03 | Session context growth |

Cost scales with session size. The 15-minute idle reset (`session.reset.idleMinutes: 15`) keeps this bounded.

### Projected costs

| Usage | Daily | Monthly |
|-------|-------|---------|
| 10 msgs/day | $0.10-0.20 | $3-6 |
| 30 msgs/day | $0.30-0.90 | $9-27 |
| CC (Opus) | $0.00 | $0.00 (Max plan CLI) |

### Message flow (single turn)

```
Patrick sends message in Discord #planning
        |
        v
+----------------------------------+
|  OpenClaw Gateway                |
|  Receives Discord MESSAGE_CREATE |
|  Routes to hurin agent session   |
|  Model: claude-haiku-4-5 ($API)  |
|  Thinking: off                   |
+----------------------------------+
        |
        v
+----------------------------------+
|  Hurin (Haiku) - Loop 1          |
|  Reads message, decides: route   |
|  exec: discord-react.sh add      |  <-- ~0.5s
+----------------------------------+
        |
        v
+----------------------------------+
|  Hurin (Haiku) - Loop 2          |
|  exec: cd ~/.openclaw/workspace  |
|    -hurin/theapp &&              |
|    claude -p --model opus        |
|    --dangerously-skip-           |  <-- BLOCKS 1-5 min
|    permissions <<'PROMPT'        |     CC reads codebase,
|    [Patrick's message]           |     does all intelligence
|    PROMPT                        |     $0 (Max plan CLI)
+----------------------------------+
        |
        v
+----------------------------------+
|  Hurin (Haiku) - Loop 3          |
|  exec: discord-react.sh remove   |  <-- ~0.5s
|  Relays CC output verbatim       |
+----------------------------------+
        |
        v
+----------------------------------+
|  OpenClaw Gateway                |
|  Sends response to Discord       |
+----------------------------------+

Per-message Haiku cost:
  Input:  session_tokens x $0.80/MTok
  Output: ~200-500 tokens x $4.00/MTok
  CC:     $0.00 (Max plan)
  Total:  $0.01-0.03 depending on session size
```

## Consequences

### Positive

- Hurin can no longer act autonomously — structural enforcement, not just prompt
- Thinking-off cuts cost by ~50-66% per message
- Validated across 5 experiments with consistent results
- CC does all intelligence at $0 via Max plan CLI

### Negative

- Hurin cannot read its own workspace files (TOOLS.md, memory/) — must rely on system prompt and CC
- If CC call fails (e.g. wrong path), hurin has limited ability to self-correct without `read`

### Risks

- Session context growth increases per-message cost over time (mitigated by 15-min idle reset)
- Haiku without thinking may occasionally misparse messages — monitor for routing failures
