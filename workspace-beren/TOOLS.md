# TOOLS.md — Beren's Environment

## Machine

- **Hardware:** Linux VPS, 2GB RAM
- **OS:** Linux (Ubuntu)
- **Shell:** bash
- **Python:** Always use `uv` (never pip)

## Two-Tier Architecture

- **Beren** (you) — MiniMax M2.5. Routes meta-level queries, manages digest system.
- **Claude Code** — Opus 4.6 via Agent SDK on Max plan — **$0 cost**. Runs deep system analysis through chief-of-staff.py.

**All CC work uses Agent SDK scripts. Never `claude -p`.**

## Running a Digest

```bash
# Run a new digest (async, ~5-10 min)
exec(command="nohup /home/hurin/.openclaw/monitor/.venv/bin/python /home/hurin/.openclaw/chief-of-staff/chief-of-staff.py >> /home/hurin/.openclaw/chief-of-staff/cron.log 2>&1 &")
```

## Reading Digests

```bash
# Latest digest
exec(command="cat $(ls -t /home/hurin/.openclaw/chief-of-staff/digests/digest-*.md 2>/dev/null | head -1) 2>/dev/null || echo 'No digest found.'")
```

## Key Paths

| Path | Purpose |
|------|---------|
| `~/.openclaw/chief-of-staff/digests/` | Saved digests |
| `~/.openclaw/chief-of-staff/cron.log` | Execution log |
| `~/.openclaw/team-lead/syntheses/` | Team-lead syntheses (input data) |
| `~/.openclaw/co-founder/briefings/` | Co-founder briefings (input data) |
| `~/.openclaw/monitor/task-events.jsonl` | Task events (input data) |
| `~/.openclaw/knowledge/` | Knowledge base (input data) |
| `~/.openclaw/knowledge/self/spawn-policy.json` | Spawn policy (input data) |
| `~/.openclaw/knowledge/self/telemetry.jsonl` | Telemetry (input data) |
| `~/.openclaw/knowledge/self/capability-gaps.md` | Capability gaps (input data) |

## Discord Channel

- **#chief-of-staff** — digests, system evaluation, strategic conversation with Patrick
