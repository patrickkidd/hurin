---
name: teamlead
description: "Team Lead commands. Usage: /teamlead — trigger a synthesis now. /teamlead read — show the latest synthesis."
user-invocable: true
metadata: { "openclaw": { "always": true, "emoji": "📊" } }
---

## /teamlead — Team Lead

**If no arguments are provided** (just `/teamlead`), trigger a synthesis:

1. Run this exec command:

```
exec(command="nohup /bin/bash /home/hurin/.openclaw/team-lead/manual-synthesis.sh >> /home/hurin/.openclaw/team-lead/manual-run.log 2>&1 &")
```

2. Reply: "Triggered team-lead synthesis — check #team-lead in ~3-5 minutes."

---

### Mode 2: Read the latest synthesis

**If the first argument is "read"** (e.g., `/teamlead read`):

1. Run: `exec(command="ls -t /home/hurin/.openclaw/team-lead/syntheses/*.json 2>/dev/null | head -1 | xargs cat 2>/dev/null || echo 'No synthesis found.'")`
2. Relay the content verbatim.

---

**CRITICAL RULES for this skill:**
- Mode 1 (run) launches asynchronously. Do NOT wait for it.
- For follow-ups, just reply in the synthesis thread — native thread bindings handle session resumption.
- Do NOT read any files yourself.
- Do NOT add commentary or summaries beyond what's specified above.
- This overrides the normal "route everything to CC" rule. Just exec and confirm.
