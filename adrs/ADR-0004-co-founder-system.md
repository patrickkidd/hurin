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
cron (9 schedules) or /cofounder skill (on-demand)
  └── co-founder.sh <lens-name>
        ├── Read lens prompt from lenses/<name>.md
        ├── Read last 150 lines of journal.md (memory)
        ├── Assemble prompt → /tmp/co-founder-prompt.txt
        ├── claude -p --model opus --max-turns 10 --output-format json  ($0)
        │     └── CC uses multiple turns: gather data → dig deeper → synthesize
        ├── Parse JSON → extract result + session_id
        ├── Save session ID to sessions/<lens>-session.txt (for follow-up)
        ├── Save full briefing to briefings/<lens>-<date>.md
        ├── Append output to journal.md (capped at 1000 lines)
        └── discord-post.sh → #co-founder channel (split at 1900 chars)
```

Runs from cron (scheduled) or on-demand via `/cofounder <lens>` skill in Discord. $0 total cost.

### Depth Model

Each run gives CC **10 agentic turns** (configurable via `MAX_TURNS` in config.sh). The prompt instructs CC to:
1. **Turns 1-3:** Gather data — read project files, run git/gh commands, explore the codebase
2. **Turns 4-6:** Dig deeper — investigate specific areas, read source files, check patterns
3. **Turns 7+:** Synthesize — write the briefing with concrete citations (file paths, line numbers, PR numbers)

Output is **unconstrained** — no character limit. CC writes as much as the analysis warrants. Discord posting handles splitting across messages. Full output is saved to `briefings/` for reference.

### Session Resumption

Each run saves its Claude session ID to `sessions/<lens>-session.txt`. Patrick can continue the conversation with:

```
/cofounder followup <lens> <question>
```

This resumes the original CC session via `--resume <session-id>`, giving CC full context of its analysis. The follow-up runs synchronously through hurin and replies in the current channel.

### On-Demand Triggering

The `/cofounder` OpenClaw skill allows Patrick to run any lens on demand:
- `/cofounder` — list available lenses
- `/cofounder <lens>` — run a lens (async, posts to #co-founder in ~5-10 min)
- `/cofounder followup <lens> <question>` — continue a briefing conversation
- `/cofounder read <lens>` — show the latest briefing

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
| 8:00 AM | Daily | evolution | External intelligence: agent patterns, OpenClaw, AI co-founder techniques |

### Journal Memory Model

- `journal.md` is append-only, capped at 1000 lines
- Each entry has a timestamp and lens name header
- CC reads the last 150 lines before each run for continuity
- CC is instructed to reference its own past observations and build on them
- Trimming removes oldest entries when cap is exceeded
- Full briefings are also saved to `briefings/<lens>-<date>.md` (not trimmed)

### Discord Integration

- Posts to #co-founder channel (ID: 1476739270663213197)
- Messages split on line boundaries at 1900 chars (Discord 2000 limit)
- Full briefing saved to `briefings/` regardless of Discord posting
- Channel is bound to hurin in openclaw.json so Patrick can reply and get CC responses
- `/cofounder followup` resumes the CC session for context-aware follow-ups

### Action Pipeline

Each briefing may also produce structured action items (most don't — by design). See [ADR-0005: Action System](ADR-0005-action-system.md) for full details.

- All actions require Patrick's approval — no auto-spawning
- Quality over quantity: only genuine quick wins that CC can fully implement
- Revenue items → `#quick-wins` channel, others → `#co-founder`
- GitHub Issues are the source of truth; Discord is for notifications only
- `/cofounder approve <id>` to spawn, `/cofounder refine <id> <feedback>` to iterate

## File Layout

```
~/.openclaw/co-founder/
  config.sh              # Paths, channel ID, Discord token, depth settings
  co-founder.sh          # Main runner script (agentic, multi-turn)
  discord-post.sh        # Discord API posting with message splitting
  action-router.sh       # Routes actions: GitHub Issues + Discord + spawning
  action-approve.sh      # Approves and spawns propose-tier actions
  action-refine.sh       # Iterative refinement via CC session resumption
  action-list.sh         # Dashboard of pending actions
  wp-draft.sh            # WordPress draft creator via REST API
  README.md              # Operator's quick-reference guide
  journal.md             # Persistent memory (append-only, 1000 line cap)
  cron.log               # Cron output log
  actions.log            # Action router log (gitignored)
  briefings/             # Full briefing output files
    <lens>-<date>.md     # e.g. architecture-2026-02-26.md
    <lens>-latest.md     # Symlink to most recent briefing per lens
  sessions/              # CC session IDs for resumption (gitignored)
    <lens>-session.txt   # Session ID from last run of each lens
  actions/               # Action JSON files (committed)
    <lens>-<date>.json   # Parsed actions from each briefing
  website-content/       # WordPress draft backups (committed)
    <action-id>.md       # Markdown with frontmatter
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
    evolution.md         # External intelligence and system evolution

~/.openclaw/skills/cofounder/
  SKILL.md               # /cofounder slash command (run, followup, read, approve, refine, actions)
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
- [ADR-0005: Action System](ADR-0005-action-system.md) — action pipeline, approval flow, WordPress integration
