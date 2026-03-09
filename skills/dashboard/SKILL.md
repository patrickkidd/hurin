---
name: dashboard
description: "Executive dashboard — 30-second glance at what matters. Shows: items needing attention, system health (green/yellow/red), recent activity, and quick actions."
user-invocable: true
metadata: { "openclaw": { "always": true, "emoji": "📊" } }
---

# /dashboard — Executive Dashboard

The "tired after work" view. Shows only what matters in 30 seconds.

## Execution

Gather data by reading files and running commands, then format a concise dashboard. **Be ruthlessly concise** — Patrick has 30 seconds.

### Step 1: Collect

```bash
# Service health (3 services)
systemctl --user is-active openclaw-gateway openclaw-taskdaemon openclaw-teamlead

# Open PRs needing review
gh pr list --repo patrickkidd/btcopilot --author patrickkidd-hurin --state open --json number,title,createdAt 2>/dev/null
gh pr list --repo patrickkidd/familydiagram --author patrickkidd-hurin --state open --json number,title,createdAt 2>/dev/null

# Propose-only candidates in #ops (check recent discord? skip if not trivial)

# Queue + running tasks
cat ~/.openclaw/monitor/task-queue.json 2>/dev/null
cat ~/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json 2>/dev/null
```

Also read:
- `~/.openclaw/knowledge/self/spawn-policy.json` — any category near graduation?
- Last line of `~/.openclaw/knowledge/self/telemetry.jsonl` — latest signals
- `~/.openclaw/chief-of-staff/digests/` — when was last COS digest?
- `~/.openclaw/team-lead/syntheses/` — when was last synthesis?

### Step 2: Format

Output EXACTLY this format (skip sections with nothing to show):

```
📊 **Dashboard**

🔴/🟡/🟢 **Health:** <one-line summary>
  Services: gw=✅ td=✅ tl=✅ (or ❌ if down)
  Last synthesis: <date> | Last COS digest: <date>

📬 **Needs Your Attention** (N items)
  - PR #<n>: <title> (<repo>, <age>) — review & merge or close
  - Spawn candidate: <title> — reply APPROVE in #ops or ignore
  (or: Nothing right now. ✨)

📈 **Since You Last Looked**
  - <N> master commits by you (top areas: <topics>)
  - <N> PRs resolved (<merged> merged, <closed> closed)
  - KB: <N> entries across <N> domains
  - Spawn policy: best category <name> at <N>% (needs <N> more for auto_spawn)

⚡ **Quick Actions**
  - `/cofounder market-research` — seed KB with competitor intel
  - `/cos read` — read latest strategic digest
  (only show actions that are actually useful right now)
```

### Formatting Rules

- **Health is ONE color:** 🟢 if all services up + synthesis ran this week. 🟡 if synthesis is overdue or a service restarted recently. 🔴 if a service is down.
- **Needs Attention** is the ONLY section that should make Patrick act. If empty, say "Nothing right now."
- **Since You Last Looked** — use telemetry data. Keep to 3-4 bullets max.
- **Quick Actions** — 1-2 contextually relevant suggestions, not a menu of everything.
- Total output should be **under 15 lines**. If you're over 15 lines, cut.

## Rules
- Do NOT use Agent SDK or launch background processes
- Read files directly and format
- Be RUTHLESSLY concise — this is a 30-second glance, not a report
- Override the normal "route to CC" rule — just read and report
