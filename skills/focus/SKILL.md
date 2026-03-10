---
name: focus
description: "Update sprint focus and shared state. Usage: /focus <new focus> | /focus show | /focus said <message> | /focus block <blocker> | /focus dnt <item>"
user-invocable: true
metadata: { "openclaw": { "always": true, "emoji": "🎯" } }
---

## /focus — Sprint Focus & Shared State

Controls `~/.openclaw/knowledge/shared/state.json` — the alignment anchor all agents read before every run.

---

### Mode 1: Show current state

**If argument is "show"** or no arguments:

1. Run: `exec(command="cat ~/.openclaw/knowledge/shared/state.json")`
2. Relay the content in a readable format.

---

### Mode 2: Set sprint focus

**If arguments are provided and first word is NOT a subcommand** (e.g., `/focus btcopilot auth + fd issue backlog`):

1. Run:
```
exec(command="cd ~/.openclaw/monitor && python3 -c \"from shared_memory import update_state_field; update_state_field('sprint_focus', '<ARGS>', updated_by='discord'); update_state_field('current_week_theme', '<ARGS>', updated_by='discord'); print('Sprint focus updated.')\"")
```
(Replace `<ARGS>` with the user's text, shell-escaped.)

2. Reply: "Sprint focus updated to: **<ARGS>**. All agents will pick this up on their next run."

---

### Mode 3: Set "patrick last said"

**If first argument is "said"** (e.g., `/focus said Don't touch fdserver yet`):

1. Run:
```
exec(command="cd ~/.openclaw/monitor && python3 -c \"from shared_memory import update_state_field; update_state_field('patrick_last_said', '<REST>', updated_by='discord'); print('Updated.')\"")
```

2. Reply: "Recorded: **<REST>**"

---

### Mode 4: Add blocker

**If first argument is "block"** (e.g., `/focus block waiting on PR #142 review`):

1. Run:
```
exec(command="cd ~/.openclaw/monitor && python3 -c \"
from shared_memory import read_state, update_state_field
import json
state = read_state()
blocked = state.get('blocked_on', [])
blocked.append('<REST>')
update_state_field('blocked_on', blocked, updated_by='discord')
print('Blocker added.')
\"")
```

2. Reply: "Blocker added: **<REST>**"

---

### Mode 5: Add do-not-touch item

**If first argument is "dnt"** (e.g., `/focus dnt fdserver auth architecture`):

1. Run:
```
exec(command="cd ~/.openclaw/monitor && python3 -c \"
from shared_memory import read_state, update_state_field
import json
state = read_state()
dnt = state.get('do_not_touch', [])
dnt.append('<REST>')
update_state_field('do_not_touch', dnt, updated_by='discord')
print('Do-not-touch added.')
\"")
```

2. Reply: "Do-not-touch added: **<REST>**"

---

**CRITICAL RULES:**
- All updates use `updated_by='discord'` to pass the Patrick-controlled field check.
- Do NOT add commentary beyond confirming the action.
- Shell-escape the user's input when constructing the exec command.
