# ADR-0002: Prompt Caching Strategy

**Status:** Accepted (revised 2026-03-03)

**Date:** 2026-02-26

**Deciders:** Patrick

## Context

OpenClaw's hurin agent sends a stable system prompt every turn: SOUL.md, AGENTS.md, TOOLS.md, IDENTITY.md, USER.md, HEARTBEAT.md, tool schemas, and skill metadata. Without prompt caching, every API call pays full input price. Cache TTL and retention behavior depends on the model provider.

Additionally, `reserveTokensFloor: 4000` was too tight — compaction fired at 60K tokens with only 4K headroom for model response, risking truncated responses after compaction.

## Decision

Applied changes to `~/.openclaw/openclaw.json`:

### 1. Cache retention on MiniMax M2.5

```json
"minimax/MiniMax-M2.5": {
  "alias": "m25",
  "params": { "cacheRetention": "short" }
}
```

MiniMax M2.5 is hurin's model ($0.30/MTok input, $1.20/MTok output). Set to `"short"` (5-min TTL). MiniMax's caching behavior differs from Anthropic's — the short retention is appropriate for the conversation patterns (15-min idle session reset means most interactions cluster within minutes).

Note: The original ADR specified `cacheRetention: "long"` (1-hour TTL) on Anthropic Sonnet/Opus model entries. Those entries no longer exist — hurin was migrated from Haiku 4.5 to MiniMax M2.5 (see ADR-0001). CC runs via Agent SDK (Max plan, $0) and doesn't go through OpenClaw's caching layer.

### 2. Heartbeat interval: 55 minutes

```json
"heartbeat": {
  "model": "minimax/MiniMax-M2.5",
  "every": "55m"
}
```

Keeps the cache warm by hitting the API before TTL expires. Uses the same MiniMax M2.5 model as hurin.

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

## Consequences

### Positive

- Cheaper input cost on the stable system prompt prefix for multi-turn sessions
- Visibility into cache behavior via `cache-trace.jsonl`
- More compaction headroom reduces risk of truncated post-compaction responses

### Negative

- Cache write cost on first turn of a new session or after cache expires
- Heartbeat every 55m costs a small API call even when idle
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
