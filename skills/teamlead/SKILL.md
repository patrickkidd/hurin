---
name: teamlead
description: "Team Lead commands. Usage: /teamlead — trigger a synthesis now. /teamlead read — show the latest synthesis. /teamlead followup <message> — continue the conversation from the last synthesis."
user-invocable: true
metadata: { "openclaw": { "always": true, "emoji": "📊" } }
---

## /teamlead — Team Lead

**If no arguments are provided** (just `/teamlead`), trigger a synthesis:

1. Run this exec command:

```
exec(command="nohup /home/hurin/.openclaw/monitor/.venv/bin/python -c 'import asyncio, sys; sys.path.insert(0, \"/home/hurin/.openclaw/team-lead\"); from team_lead_synthesis import run_synthesis_now; asyncio.run(run_synthesis_now())' >> /home/hurin/.openclaw/team-lead/manual-run.log 2>&1 &")
```

Actually, the team-lead daemon runs continuously and synthesizes hourly. To trigger an immediate synthesis, use the helper script:

```
exec(command="nohup /bin/bash /home/hurin/.openclaw/team-lead/manual-synthesis.sh >> /home/hurin/.openclaw/team-lead/manual-run.log 2>&1 &")
```

2. Reply: "Triggered team-lead synthesis — check #ops in ~3-5 minutes."

---

### Mode 2: Read the latest synthesis

**If the first argument is "read"** (e.g., `/teamlead read`):

1. Run: `exec(command="ls -t /home/hurin/.openclaw/team-lead/syntheses/*.json 2>/dev/null | head -1 | xargs cat 2>/dev/null || echo 'No synthesis found.'")`
2. Relay the content verbatim.

---

### Mode 3: Follow up on the latest synthesis

**If the first argument is "followup"** (e.g., `/teamlead followup What about CI failures?`):

1. Parse the message (everything after "followup").
2. Run this exec command:

```
exec(command="cd /home/hurin/.openclaw/workspace-hurin/theapp && SESSION_FILE=$(ls -t /home/hurin/.openclaw/team-lead/syntheses/*.json 2>/dev/null | head -1) && SESSION_ID=$(python3 -c \"import json,sys; d=json.load(open('$SESSION_FILE')); print(d.get('_session_id',''))\" 2>/dev/null) && /home/hurin/.local/bin/claude -p --model claude-opus-4-6 --dangerously-skip-permissions --resume \"$SESSION_ID\" <<'PROMPT'\n<the follow-up message>\nPROMPT")
```

3. Relay CC's response **verbatim**. This resumes the synthesis session with full context.

If no session is found, reply: "No synthesis session found. The team-lead runs syntheses hourly during business hours, or run `/teamlead` to trigger one."

---

**CRITICAL RULES for this skill:**
- Mode 1 (run) launches asynchronously. Do NOT wait for it.
- Mode 3 (followup) DOES call CC directly — this resumes the synthesis session.
- Do NOT read any files yourself.
- Do NOT add commentary or summaries beyond what's specified above.
- This overrides the normal "route everything to CC" rule. Just exec and confirm.
