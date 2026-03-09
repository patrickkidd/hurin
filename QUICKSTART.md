# Quickstart — Self-Evolving Agent System

You just deployed the self-evolving system (ADR-0007, 2026-03-09). Here's what to do next.

## What's Running Right Now

Everything is live and autonomous:
- **Telemetry** collects every 15 min (PR latency, master topics, compute ROI)
- **Spawn policy** recalculates after every PR merge/close
- **Session learner + prompt archaeology** run weekly after Monday synthesis

Nothing requires your attention unless you want to steer it.

## Where to Run Commands

**All `/slash` commands go in `#planning`** — that's hurin's primary channel. hurin routes them to the right place.

Output lands in the relevant channel:
- Co-founder briefings → `#co-founder`
- COS digests → `#chief-of-staff`
- Task progress → `#tasks`
- Spawn candidates + synthesis → `#ops`
- Revenue-impacting PRs → `#quick-wins`

## First Week Checklist

### 1. Run a KB-aware co-founder lens (5 min of your time)

Pick one and fire it off in `#planning`. This seeds the knowledge base with real research:

```
/cofounder market-research    ← competitors, pricing, market landscape
/cofounder evolution          ← AI agent patterns, self-improvement
/cofounder product-vision     ← UX patterns, user needs
```

Wait ~10 min, then check `#co-founder` for the briefing. The lens will automatically write findings to `knowledge/`.

### 2. Check the COS digest Tuesday morning

COS runs automatically Tuesday 9:03 AM AKST. It now evaluates system evolution — is the KB growing? Are spawn categories improving? Read it in `#chief-of-staff` or:

```
/cos read
```

### 3. Seed one research topic (optional, 1 min)

```
/research family therapy software competitors 2025-2026
```

This runs a web research session and writes findings to `knowledge/market/competitors.md`.

### 4. Glance at the dashboard

```
/dashboard
```

This shows: what needs your attention, system health, what happened recently.

## Ongoing — The "Tired After Work" Workflow

When you come home from your day job and have 15 min:

1. **`/dashboard`** — 30-second glance. Green/yellow/red health. Items needing attention.
2. **Approve or reject** any propose-only spawn candidates in `#ops` (if any)
3. **Read COS digest** if it's Tuesday/Friday (`/cos read`) — 2 min
4. **Done.** The system handles the rest.

When you have more energy:
- `/cofounder <lens>` — run a strategic lens
- `/research <topic>` — seed the KB with market intelligence
- Check `knowledge/self/capability-gaps.md` — see what the system can't do yet

## Key Commands

| Command | When | Time |
|---------|------|------|
| `/dashboard` | Daily glance | 30 sec |
| `/cos read` | Tue/Fri digest | 2 min |
| `/cofounder <lens>` | Strategic analysis | 10 min async |
| `/research <topic>` | Seed KB | 5 min async |
| `/status` | Detailed system data | 1 min |
| `/trust` | Spawn accuracy data | 30 sec |

## How the System Gets Smarter

You don't need to do anything for these — they happen automatically:

1. **PRs get merged/closed** → spawn policy accuracy updates → categories graduate or get blocked
2. **You use interactive CC** → session learner extracts patterns → capability gaps identified
3. **Co-founder lenses run** → KB grows with market/domain intelligence
4. **COS evaluates** → flags stale KB, proposes self-improvements
5. **Prompt archaeology runs** → learns what makes good spawn prompts

The meta-metric: is `knowledge/index.md` growing and being updated? Check occasionally.
