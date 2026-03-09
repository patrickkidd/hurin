---
name: cos
description: "Chief of Staff commands. Usage: /cos — run a new strategic digest. /cos read — show the latest digest. /cos followup <message> — continue the conversation from the last digest."
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

1. Run: `exec(command="cat /home/hurin/.openclaw/chief-of-staff/digests/$(ls -t /home/hurin/.openclaw/chief-of-staff/digests/digest-*.md 2>/dev/null | head -1) 2>/dev/null || echo 'No digest found. Run /cos first.'")`
2. Relay the content verbatim.

---

### Mode 3: Follow up on the latest digest

**If the first argument is "followup"** (e.g., `/cos followup What about the PR backlog?`):

1. Parse the message (everything after "followup").
2. Run this exec command:

```
exec(command="cd /home/hurin/.openclaw/workspace-hurin/theapp && SESSION_ID=$(cat /home/hurin/.openclaw/chief-of-staff/digests/last-session.json 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"session_id\",\"\"))' 2>/dev/null) && /home/hurin/.local/bin/claude -p --model claude-opus-4-6 --dangerously-skip-permissions --resume \"$SESSION_ID\" <<'PROMPT'\n<the follow-up message>\nPROMPT")
```

3. Relay CC's response **verbatim** to the channel. This resumes the original digest session, so CC has full context.

If the session file doesn't exist or session_id is empty, reply: "No digest session found. Run `/cos` first to generate a digest, then follow up."

---

**CRITICAL RULES for this skill:**
- Mode 1 (run) launches the script asynchronously. Do NOT wait for it.
- Mode 3 (followup) DOES call CC directly — this resumes the digest session.
- Do NOT read any files yourself.
- Do NOT add commentary or summaries beyond what's specified above.
- This overrides the normal "route everything to CC" rule. Just exec and confirm.
