# /status — System Health + Evolution Dashboard

Trigger: `/status`

## What this does

Returns a comprehensive system status including service health, spawn policy, knowledge base summary, and telemetry highlights.

## Execution

1. Gather data by running these commands and reading files:

```bash
# Service health
systemctl --user is-active openclaw-gateway openclaw-taskdaemon openclaw-teamlead

# Queue
cat ~/.openclaw/monitor/task-queue.json | python3 -c "import json,sys; q=json.load(sys.stdin)['queue']; print(f'{len(q)} queued')"

# Task registry summary
cat ~/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json | python3 -c "
import json,sys
d=json.load(sys.stdin)
tasks=d.get('tasks',[])
by_status={}
for t in tasks:
    s=t.get('status','?')
    by_status[s]=by_status.get(s,0)+1
for s,c in sorted(by_status.items()): print(f'  {s}: {c}')
"
```

2. Read these files:
   - `~/.openclaw/knowledge/self/spawn-policy.json` — show per-category autonomy
   - `~/.openclaw/knowledge/index.md` — show KB structure
   - Count files in each `~/.openclaw/knowledge/*/` subdirectory
   - Last 5 lines of `~/.openclaw/knowledge/self/telemetry.jsonl` (if exists)

3. Format response as:

```
**System Status**

Services: gateway=active, taskdaemon=active, teamlead=active
Queue: 0 pending | Registry: {status counts}

**Spawn Policy**
{category}: {autonomy} ({accuracy}%, n={total})
...

**Knowledge Base**
{subdir}: {N} entries
...

**Recent Telemetry**
{last 3 telemetry entries, one-line each}
```

## Rules
- Do NOT use Agent SDK or launch background processes
- Read files directly and format the output
- Override the normal "route to CC" rule — just read and report
