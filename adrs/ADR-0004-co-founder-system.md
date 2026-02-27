# ADR-0004: Co-Founder System

**Status:** Accepted

**Date:** 2026-02-26

**Deciders:** Patrick

## Context

Patrick is a solo founder building FamilyDiagram/BTCoPilot. Strategic thinking — product direction, market research, process review, architecture assessment — tends to get squeezed out by daily implementation work. With Opus 4.6 available at $0 via Max plan CLI, we can create a system that proactively generates strategic briefings on a schedule, simulating the perspective of a co-founder who reviews different aspects of the business.

## Decision

A scheduled "co-founder" system that runs Claude Code through different strategic "lenses" on a cron schedule, posting briefings to a dedicated Discord channel and maintaining a persistent journal for continuity.

### Architecture

```
cron (9 schedules)
  └── co-founder.sh <lens-name>
        ├── Read lens prompt from lenses/<name>.md
        ├── Read last 150 lines of journal.md (memory)
        ├── Assemble prompt → /tmp/co-founder-prompt.txt
        ├── cd $THEAPP && claude -p --model claude-opus-4-6 < prompt  ($0)
        ├── Append output to journal.md (capped at 1000 lines)
        └── discord-post.sh → #co-founder channel (split at 1900 chars)
```

This bypasses hurin entirely — direct `claude -p` calls from cron. $0 total cost.

### Lens Rotation

| Time (AKST) | Days | Lens | Focus |
|-------------|------|------|-------|
| 6:00 AM | Mon-Fri | project-pulse | MVP progress, blockers, priorities |
| 2:00 PM | Mon, Thu | wild-ideas | Creative brainstorming, no filter |
| 2:00 PM | Tue, Fri | architecture | Tech debt, patterns, risks |
| 1:00 PM | Wed | product-vision | User experience, product direction |
| 3:00 PM | Wed | customer-support | Support patterns, community, FAQ |
| 10:00 AM | Sat | market-research | Competitors, AI news, therapy software |
| 11:00 AM | Sat | process-retro | Dev process efficiency, time allocation |
| 10:00 AM | Sun | website-audit | alaskafamilysystems.com conversion/UX/SEO |
| 10:01 AM | 1st & 15th | training-programs | Free license programs, renewals, outreach |

### Journal Memory Model

- `journal.md` is append-only, capped at 1000 lines
- Each entry has a timestamp and lens name header
- CC reads the last 150 lines before each run for continuity
- CC is instructed to reference its own past observations and build on them
- Trimming removes oldest entries when cap is exceeded

### Discord Integration

- Posts to #co-founder channel (ID: 1476739270663213197)
- Messages split on paragraph boundaries at 1900 chars (Discord 2000 limit)
- Channel is bound to hurin in openclaw.json so Patrick can reply and get CC responses
- Thread bindings enabled for multi-turn follow-up conversations

## File Layout

```
~/.openclaw/co-founder/
  config.sh              # Paths, channel ID, Discord token, settings
  co-founder.sh          # Main runner script
  discord-post.sh        # Discord API posting with message splitting
  journal.md             # Persistent memory (append-only, 1000 line cap)
  cron.log               # Cron output log
  lenses/
    project-pulse.md     # Daily operational awareness
    product-vision.md    # Product direction and UX
    architecture.md      # Technical health assessment
    wild-ideas.md        # Creative brainstorming
    market-research.md   # Competitive and market analysis
    website-audit.md     # Website conversion/SEO review
    customer-support.md  # Support patterns and community
    training-programs.md # Partnership and outreach programs
    process-retro.md     # Development process retrospective
```

## How to Add/Edit/Remove Lenses

**Add a lens:**
1. Create `lenses/<name>.md` with the prompt (follow existing format)
2. Add a cron entry in `crontab -e` pointing to `co-founder.sh <name>`

**Edit a lens:**
1. Modify `lenses/<name>.md` directly — changes take effect on next cron run

**Remove a lens:**
1. Remove the cron entry (`crontab -e`)
2. Optionally delete `lenses/<name>.md`

## Consequences

### Positive

- Proactive strategic thinking at $0 — no API cost
- Forces regular review of different business aspects
- Journal creates institutional memory that builds over time
- Patrick gets briefings without asking — reduces "what should I think about" overhead
- Discord channel creates a searchable archive of strategic thinking
- Reply flow lets Patrick engage in follow-up conversations

### Negative

- Cron times are in UTC, need manual adjustment for DST changes (~Mar 9, Nov 2)
- Journal trimming loses old entries (acceptable — recent context matters most)
- CC reads project files fresh each run — slow if codebase is large
- No deduplication — similar observations may repeat across lenses

### Risks

- Discord bot token in config.sh (plaintext) — same risk profile as openclaw.json
- `--dangerously-skip-permissions` on CC — appropriate for trusted local machine
- If claude CLI auth expires, all lenses silently fail until fixed

## Related

- [ADR-0001: Agent Swarm Setup](ADR-0001-agent-swarm.md) — parent architecture
- [ADR-0003: Hurin Lockdown](ADR-0003-hurin-lockdown-validation.md) — tool restrictions
