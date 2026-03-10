---
name: dashboard
description: "Executive dashboard — 30-second glance at what matters. Director-level: product progress, system evolution, items needing your decision."
user-invocable: true
metadata: { "openclaw": { "always": true, "emoji": "📊" } }
---

# /dashboard — Director's Dashboard

You are producing a dashboard for a **Director of Engineering** who just got home from a cognitively heavy day job. He has 30 seconds. He does NOT care about PRs, CI, queues, or agent plumbing. He cares about:

1. Is the product moving forward?
2. Is the agent system getting smarter?
3. Do I need to decide anything right now?

## Execution

Run these exec commands and read these files. Then format the output EXACTLY as specified below.

### Data to collect

```bash
# 1. Product momentum — what did I accomplish this week?
gh api "repos/patrickkidd/btcopilot/commits?sha=master&since=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)&per_page=5" --jq '.[].commit.message' 2>/dev/null | head -5
gh api "repos/patrickkidd/familydiagram/commits?sha=master&since=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)&per_page=5" --jq '.[].commit.message' 2>/dev/null | head -5

# 2. Service health — one line
systemctl --user is-active openclaw-gateway openclaw-taskdaemon openclaw-teamlead

# 3. Items needing decision — open bot PRs across repos
gh pr list --repo patrickkidd/btcopilot --author patrickkidd-hurin --state open --json number,title --jq '.[] | "#\(.number): \(.title)"' 2>/dev/null
gh pr list --repo patrickkidd/familydiagram --author patrickkidd-hurin --state open --json number,title --jq '.[] | "#\(.number): \(.title)"' 2>/dev/null
```

Also read (exec cat or similar):
- Last 3 lines of `~/.openclaw/knowledge/self/telemetry.jsonl` — for master_topics entry (what areas you've been working in)
- `~/.openclaw/knowledge/self/spawn-policy.json` — just the category count and best accuracy
- Count of files in `~/.openclaw/knowledge/` subdirs — is KB growing?
- When was last COS digest? `ls -t ~/.openclaw/chief-of-staff/digests/digest-*.md | head -1`
- When was last synthesis? `ls -t ~/.openclaw/team-lead/syntheses/*.json | head -1`

### Output format

Output EXACTLY this structure. Skip empty sections. **UNDER 12 LINES TOTAL.**

```
📊 **Dashboard**

🟢/🟡/🔴 **System:** <all services up|issue> | Last digest: <date> | Last synthesis: <date>

🚀 **Product This Week**
  <N> commits across repos. Focus areas: <top 2-3 topics from telemetry, human-readable>
  (e.g. "AI extraction pipeline, personal app UI, test fixes")

🧠 **System Evolution**
  KB: <N> entries | Spawn policy: <N> categories, best at <N>% | <growing|stagnant>

📬 **Needs Your Decision** (<N> items)
  - <item description> — <what to do>
  (or: Nothing. System is autonomous. ✨)

⚡ <one contextual suggestion, e.g. "/cofounder market-research to seed competitor intel" or "/cos read for Tuesday's digest">
```

### Rules for each section

**System** — ONE emoji color. 🟢 = all 3 services active + synthesis this week. 🟡 = synthesis overdue or service bounced. 🔴 = service down. Just the facts, no detail.

**Product This Week** — This is about PATRICK's work, not the agents. Summarize master commit topics in plain English. "AI extraction pipeline" not "btcopilot commits". This is the most important section — it reminds Patrick what he accomplished.

**System Evolution** — Is the self-evolving system actually evolving? KB entry count, best spawn category accuracy, trend direction. One line.

**Needs Your Decision** — ONLY items requiring a human yes/no. Open bot PRs to merge or close. Spawn candidates to approve. If nothing, say "Nothing." Do NOT list informational items here.

**Quick action** — ONE line. Pick the most useful thing right now. If COS digest is unread, suggest that. If KB is empty, suggest a research topic. If nothing is pressing, suggest nothing.

## Hard rules
- Do NOT route to CC. Do NOT use Agent SDK. Just exec + read + format.
- Do NOT list PR details, CI status, queue depth, task registry, or agent plumbing.
- Do NOT exceed 12 lines. If you're over, cut the least important content.
- Speak like a dashboard, not a report. No prose. No explanations.

---

## /dashboard ci — Collective Intelligence Dashboard

**If the first argument is "ci"** (e.g., `/dashboard ci`):

Show the CI system health. Run this exec command:

```bash
cd /home/hurin/.openclaw/monitor && python3 -c "
import json, sys
sys.path.insert(0, '.')
from shared_memory import (
    read_state, get_signal_stats, get_episode_stats,
    read_recent_calibrations, get_calibration_accuracy,
    read_signals, read_recent_episodes,
)

state = read_state()
sig = get_signal_stats()
ep = get_episode_stats()
cals = read_recent_calibrations(5)
beren_acc = get_calibration_accuracy('beren')

# Recent unconsumed signals (peek, don't mark consumed)
pending = read_signals('all', mark_consumed=False)
unconsumed = [s for s in pending if not s.get('consumed')]

print('STATE|' + json.dumps(state))
print('SIGNALS|' + json.dumps(sig))
print('EPISODES|' + json.dumps(ep))
print('CALS|' + json.dumps(cals))
print('BEREN_ACC|' + json.dumps(beren_acc))
print('UNCONSUMED|' + str(len(unconsumed)))
print('RECENT_SIGNALS|' + json.dumps([{'from': s['from'], 'to': s['to'], 'type': s['type'], 'signal': s['signal'][:80]} for s in pending[-5:]]))
print('RECENT_EPISODES|' + json.dumps([{'task_id': e['task_id'], 'outcome': e['outcome'], 'lessons': e.get('lessons',[])[0] if e.get('lessons') else ''} for e in read_recent_episodes(3)]))
"
```

Format the output EXACTLY like this. **UNDER 20 LINES TOTAL.**

```
🧬 **Collective Intelligence**

🎯 **Sprint Focus:** <from state.sprint_focus>
   Patrick last said: "<from state.patrick_last_said>"

📡 **Signal Bus:** <total> signals | <consumed>/<total> consumed (<rate>%) | <unconsumed> pending
   Recent: <last 2-3 signals, one line each: "[type] from→to: signal text">

🧠 **Episodic Memory:** <total> episodes | <by_outcome breakdown> | avg <duration>h
   Lessons captured: <total_lessons> | Signal-influenced: <with_signals>

⚔️ **Adversarial Health:**
   Calibrations: <total> | Beren accuracy: <correct>/<total> (<rate>%)
   <last calibration topic + outcome, if any>

🔗 **Cross-Pollination:** <signals by flow, e.g. "huor→tuor: 5, tuor→huor: 3, beren→tuor: 2">

🌐 Full dashboard: ssh -L 8787:localhost:8787 hurin → http://localhost:8787
```

### Rules for /dashboard ci
- Do NOT route to CC. Just exec + read + format.
- If signal bus is empty, say "No signals yet — system bootstrapping."
- If episodes are empty, say "No episodes yet — waiting for first task completion."
- Show the SSH tunnel link at the bottom for the full visual dashboard.
- Do NOT exceed 20 lines.
