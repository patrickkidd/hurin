# ADR-0002: Prompt Caching Strategy

**Status:** Accepted

**Date:** 2026-02-26

**Deciders:** Patrick

## Context

OpenClaw's hurin agent (Sonnet 4.6) sends ~11,845 tokens of stable system prompt every turn: SOUL.md, AGENTS.md, TOOLS.md, IDENTITY.md, USER.md, HEARTBEAT.md, tool schemas, and skill metadata. Without prompt caching, every API call pays full input price ($3/MTok for Sonnet). With the implicit default (`cacheRetention: "short"`, 5-min TTL), cache expired between most real interactions due to the 15-minute idle session reset.

No cache trace diagnostics were enabled, so there was no visibility into whether caching was working at all.

Additionally, `reserveTokensFloor: 4000` was too tight — compaction fired at 60K tokens with only 4K headroom for model response, risking truncated responses after compaction.

## Decision

Applied four changes to `~/.openclaw/openclaw.json`:

### 1. Explicit `cacheRetention: "long"` on Sonnet and Opus

```json
"anthropic/claude-sonnet-4-6": {
  "alias": "sonnet",
  "params": { "cacheRetention": "long" }
},
"anthropic/claude-opus-4-6": {
  "params": { "cacheRetention": "long" }
}
```

1-hour TTL. Write cost is 2x base ($6/MTok for Sonnet, $10/MTok for Opus), but cache reads are 90% cheaper ($0.30/MTok for Sonnet, $0.50/MTok for Opus). The stable system prompt (~11.8K tokens) is written once and read on every subsequent turn within the hour.

Haiku set to `"short"` (5-min) — its 4,096-token minimum means heartbeat prompts likely won't cache regardless.

### 2. Heartbeat interval: 55 minutes

```json
"heartbeat": {
  "model": "anthropic/claude-haiku-4-5",
  "every": "55m"
}
```

Keeps the Anthropic cache warm by hitting it before the 1-hour TTL expires. Each cache hit resets the TTL for free. This prevents full cache-write costs after idle periods between tasks.

Note: This is distinct from the cron-based `check-agents.py` (10-min), which is an external process monitor. The heartbeat is an API-level cache warmer.

### 3. Raised `reserveTokensFloor` from 4,000 to 10,000

```json
"compaction": {
  "mode": "safeguard",
  "reserveTokensFloor": 10000,
  "memoryFlush": { "enabled": true }
}
```

Compaction now fires at 54K tokens (64K - 10K) instead of 60K. Gives the model more headroom to generate a full response after compaction runs.

### 4. Cache trace diagnostics enabled

```json
"diagnostics": {
  "cacheTrace": { "enabled": true }
}
```

Logs to `~/.openclaw/logs/cache-trace.jsonl`. Each API call records `cacheRead`, `cacheWrite`, and `input` token counts for ongoing cost monitoring.

## Verification

Tested 2026-02-26 with two consecutive `openclaw agent` turns:

| Turn | cacheWrite | cacheRead | input | Result |
|------|-----------|-----------|-------|--------|
| 1 | 11,845 | 0 | 3 | Full write (expected) |
| 2 | 30 | 11,845 | 3 | **Cache hit — 11,845 tokens at 90% discount** |

Gateway log confirmed `cacheRetention: "long"` active post-restart.

## Consequences

### Positive

- ~10x cheaper input cost on the stable system prompt prefix for multi-turn sessions
- Cache survives idle gaps up to 1 hour (vs 5 minutes before)
- Heartbeat keeps cache warm between real conversations
- Visibility into cache behavior via `cache-trace.jsonl`
- More compaction headroom reduces risk of truncated post-compaction responses

### Negative

- 2x write cost on first turn of a new session or after cache expires (amortized quickly over subsequent turns)
- Heartbeat every 55m costs a small Haiku API call even when idle
- `cache-trace.jsonl` will grow over time — needs periodic cleanup or rotation

### Risks

- Compaction invalidates the prompt cache (replaces messages with summaries, breaking byte-for-byte match). First turn after compaction pays full input cost. With compaction now at 54K, this fires slightly more often.
- OpenClaw issue #24800: compaction doesn't trigger mid-tool-use-loop. Long tool chains can overflow past 64K before compaction fires.
- OpenClaw issue #21785: dynamic content (message IDs) injected into system prompts can silently invalidate cache every turn. Watch for `cacheRead: 0` on turn 2+ in trace logs.

## Monitoring

Check cache health periodically:

```bash
# Recent cache trace entries
tail -5 ~/.openclaw/logs/cache-trace.jsonl | python3 -m json.tool

# Quick check: are cache reads happening?
grep -o '"cacheRead":[0-9]*' ~/.openclaw/logs/cache-trace.jsonl | tail -10
```

If `cacheRead` is consistently 0 on turn 2+, investigate dynamic content injection per issue #21785.
