# TOOLS.md — Tuor's Environment

## Machine

- **Hardware:** Linux VPS, 2GB RAM
- **OS:** Linux (Ubuntu)
- **Shell:** bash
- **Python:** Always use `uv` (never pip)

## Two-Tier Architecture

- **Tuor** (you) — MiniMax M2.5. Routes strategic queries, manages lens system, handles KB reads.
- **Claude Code** — Opus 4.6 via Agent SDK on Max plan — **$0 cost**. Runs deep strategic analysis through co-founder-sdk.py.

**All CC work uses Agent SDK scripts. Never `claude -p`.**

## Running Lenses

```bash
# Run a lens (async, ~5-10 min)
exec(command="nohup /bin/bash /home/hurin/.openclaw/co-founder/co-founder.sh <lens-name> >> /home/hurin/.openclaw/co-founder/cron.log 2>&1 &")
```

## Action Management

```bash
# List pending actions
exec(command="/bin/bash /home/hurin/.openclaw/co-founder/action-list.sh")

# Approve an action (spawns task)
exec(command="/bin/bash /home/hurin/.openclaw/co-founder/action-approve.sh <action-id>")

# Refine an action
exec(command="/bin/bash /home/hurin/.openclaw/co-founder/action-refine.sh <action-id> '<feedback>'")

# Global status
exec(command="/bin/bash /home/hurin/.openclaw/co-founder/action-status.sh")
```

## Key Paths

| Path | Purpose |
|------|---------|
| `~/.openclaw/co-founder/briefings/` | Saved briefings (per-lens) |
| `~/.openclaw/co-founder/actions/` | Proposed actions |
| `~/.openclaw/co-founder/sessions/` | Session IDs for follow-up |
| `~/.openclaw/co-founder/journal.md` | Append-only continuity journal |
| `~/.openclaw/co-founder/lenses/` | Lens prompt templates |
| `~/.openclaw/knowledge/` | Knowledge base (6 domains) |
| `~/.openclaw/knowledge/index.md` | KB structure and staleness policy |

## Knowledge Base Domains

| Domain | Path | What's There |
|--------|------|-------------|
| domain | `knowledge/domain/` | Family therapy, clinical psychology, SARF model |
| market | `knowledge/market/` | Competitors, pricing, AI therapy landscape |
| technical | `knowledge/technical/` | Architecture, patterns, PR learnings |
| strategy | `knowledge/strategy/` | Business model, growth, partnerships |
| users | `knowledge/users/` | Personas, feedback, usage patterns |
| self | `knowledge/self/` | Agent telemetry, spawn policy, capability gaps |

## Discord Channel

- **#co-founder** — briefings, action discussions, strategic conversation with Patrick
