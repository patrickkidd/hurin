---
name: task
description: "Task daemon commands. Usage: /task list — show queued, running, and completed tasks. /task spawn <repo> <id> '<desc>' — spawn a new task. /task status <id> — show task status. /task kill <id> — kill a running task. /task watch <id> — tail a task's log."
user-invocable: true
metadata: { "openclaw": { "always": true, "emoji": "⚙️" } }
---

## /task — Task Daemon Control

All modes use the task-cli.sh script. Parse the arguments and pass them through.

**If no arguments are provided** (just `/task`), show help:

> **Task commands:**
> - `/task list` — Show all tasks (queued, running, completed)
> - `/task spawn <repo> <id> '<description>'` — Spawn a new task
> - `/task status [id]` — Show task status (all or specific)
> - `/task kill <id>` — Kill a running task
> - `/task watch <id>` — Show recent log output for a task
>
> **Repos:** `btcopilot`, `familydiagram`, `fdserver`

---

### For ALL other modes (list, spawn, status, kill, watch):

Pass all arguments directly to the CLI script:

```
exec(command="/bin/bash /home/hurin/.openclaw/monitor/task-cli.sh <all arguments>")
```

For example:
- `/task list` → `exec(command="/bin/bash /home/hurin/.openclaw/monitor/task-cli.sh list")`
- `/task spawn btcopilot fix-login 'Fix the login bug'` → `exec(command="/bin/bash /home/hurin/.openclaw/monitor/task-cli.sh spawn btcopilot fix-login Fix the login bug")`
- `/task status fix-login` → `exec(command="/bin/bash /home/hurin/.openclaw/monitor/task-cli.sh status fix-login")`
- `/task kill fix-login` → `exec(command="/bin/bash /home/hurin/.openclaw/monitor/task-cli.sh kill fix-login")`
- `/task watch fix-login` → `exec(command="/bin/bash /home/hurin/.openclaw/monitor/task-cli.sh watch fix-login")`

Relay the output verbatim.

---

**CRITICAL RULES for this skill:**
- All modes are simple script executions. Just run and relay.
- Do NOT read any files yourself.
- Do NOT add commentary beyond what's specified above.
- This overrides the normal "route everything to CC" rule. Just exec and confirm.
