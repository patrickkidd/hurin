# Co-Founder System — Operator's Guide

The co-founder system runs Claude Code through strategic "lenses" on a schedule, producing deep briefings and actionable items. Briefings post to #co-founder, revenue items go to #quick-wins, and everything is tracked via GitHub Issues.

## Commands

| Command | What it does |
|---------|-------------|
| `/cofounder` | List available lenses and commands |
| `/cofounder <lens>` | Run a lens (~5-10 min, posts to #co-founder) |
| `/cofounder followup <lens> <question>` | Continue the conversation from last briefing |
| `/cofounder read <lens>` | Show the latest briefing |
| `/cofounder approve <id>` | Approve and spawn a proposed action |
| `/cofounder refine <id> <feedback>` | Shape an action before approving |
| `/cofounder actions` | Show pending actions awaiting approval |

## How Actions Work

Most briefings produce **zero actions** — that's by design. Actions only appear when CC identifies something it can fully implement end-to-end that delivers clear value. Every action requires your approval before anything spawns.

### Reading Notifications

```
💰 Quick Win: Add free-tier signup page [small, revenue]
   → github.com/patrickkidd/theapp/issues/43
   /cofounder approve project-pulse-2026-02-27-1

📋 Quick Win: Fix confusing error on save [trivial, ux]
   → github.com/patrickkidd/theapp/issues/44
   /cofounder approve architecture-2026-02-27-1
```

### Approving an Action

```
/cofounder approve project-pulse-2026-02-27-2
```

This spawns the action as a CC task. A PR will be created. The GitHub Issue is updated with spawn info.

### Refining an Action

Don't like the approach? Shape it first:

```
/cofounder refine project-pulse-2026-02-27-2 Use React instead of Vue for this
```

This resumes the CC session from the original briefing, gives it your feedback, and it revises the action plan. You can refine multiple times before approving.

### Ignoring an Action

Just don't approve it. The GitHub Issue stays open for reference. Close it manually on GitHub if you want to dismiss it.

## Where Files Live

| What | Where |
|------|-------|
| Briefings | `~/.openclaw/co-founder/briefings/<lens>-<date>.md` |
| Action JSONs | `~/.openclaw/co-founder/actions/<lens>-<date>.json` |
| Website drafts | `~/.openclaw/co-founder/website-content/<action-id>.md` |
| Sessions | `~/.openclaw/co-founder/sessions/<lens>-session.txt` |
| Journal | `~/.openclaw/co-founder/journal.md` |
| Config | `~/.openclaw/co-founder/config.sh` |
| Lens prompts | `~/.openclaw/co-founder/lenses/*.md` |
| ADR | `~/.openclaw/adrs/ADR-0005-action-system.md` |

## Knowledge Base Integration (NEW)

Each lens now reads relevant KB entries before analysis and writes NEW findings back:

1. **Before analysis:** Loads entries from `~/.openclaw/knowledge/` relevant to the lens (e.g., `market-research` reads `knowledge/market/`)
2. **After analysis:** Prompted to write new findings to appropriate KB files using the Write tool
3. **Research log:** Checks `knowledge/research-log.md` for unfilled research topics and fills them if the lens covers them

This means lenses build cumulative intelligence instead of starting fresh each run.

## Available Lenses

| Lens | Focus | Schedule |
|------|-------|----------|
| project-pulse | MVP progress, blockers, priorities | Mon-Fri 6AM |
| architecture | Tech debt, patterns, risks | Tue, Fri 2PM |
| website-audit | Website conversion/UX/SEO | Sun 10AM |
| wild-ideas | Creative brainstorming | Mon, Thu 2PM |
| market-research | Competitors, AI, therapy software | Sat 10AM |
| product-vision | UX, product direction | Wed 1PM |
| customer-support | Support patterns, FAQ | Wed 3PM |
| process-retro | Dev process efficiency | Sat 11AM |
| training-programs | Partnerships, outreach | 1st & 15th |
| evolution | AI agent patterns, self-improvement | Monday |

**Note:** All cron schedules are currently **paused** (see decision log 2026-03-01). Planned reactivation: 2-3 lenses per week (Mon/Wed/Fri). Run on-demand via `/cofounder <lens>`.

## Troubleshooting

**Actions not appearing:** Check `~/.openclaw/co-founder/actions.log` for router errors. Common cause: malformed JSON from CC (saved as `.malformed` file).

**GitHub Issue creation failing:** Verify `gh auth status` is valid and `patrickkidd/theapp` repo exists with required labels.

**WordPress draft failing:** Check `config.sh` credentials. Test: `curl -s -u "user:pass" https://alaskafamilysystems.com/wp-json/wp/v2/posts?per_page=1`

**Approval failing:** Run `/cofounder actions` to verify the action ID and status. Only `pending_approval` actions can be approved.

**Refinement failing:** Requires a valid CC session for the lens. Run the lens first (`/cofounder <lens>`) to create a session, then refine.

**Discord not posting:** Check bot token in `config.sh`. Verify channel ID `1476950473893482587` is correct for #quick-wins.
