---
name: cos
description: "Chief of Staff commands. Usage: /cos — run a new strategic digest. /cos read — show the latest digest."
user-invocable: true
metadata: { "openclaw": { "always": true, "emoji": "📋" } }
---

## /cos — Chief of Staff

**If no arguments are provided** (just `/cos`), run a new digest:

1. Run this exec command:

```
exec(command="nohup /home/hurin/.openclaw/monitor/.venv/bin/python /home/hurin/.openclaw/chief-of-staff/chief-of-staff.py >> /home/hurin/.openclaw/chief-of-staff/cron.log 2>&1 &")
```

2. Reply: "Running Chief of Staff digest — check #chief-of-staff in ~5-10 minutes."

---

### Mode 2: Read the latest digest

**If the first argument is "read"** (e.g., `/cos read`):

1. Run: `exec(command="cat $(ls -t /home/hurin/.openclaw/chief-of-staff/digests/digest-*.md 2>/dev/null | head -1) 2>/dev/null || echo 'No digest found. Run /cos first.'")`
2. Relay the content verbatim.

---

**CRITICAL RULES for this skill:**
- Mode 1 (run) launches the script asynchronously. Do NOT wait for it.
- For follow-ups, just reply in the digest thread — native thread bindings handle session resumption.
- Do NOT read any files yourself.
- Do NOT add commentary or summaries beyond what's specified above.
- This overrides the normal "route everything to CC" rule. Just exec and confirm.
