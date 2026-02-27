---
name: cofounder
description: "Run a co-founder strategic briefing lens on demand. Usage: /cofounder <lens-name>. Available lenses: project-pulse, product-vision, architecture, wild-ideas, market-research, website-audit, customer-support, training-programs, process-retro. Also: /cofounder followup <lens> <question> to continue a briefing conversation."
user-invocable: true
metadata: { "openclaw": { "always": true, "emoji": "🧠" } }
---

## /cofounder — Co-Founder Lens Launcher

**If no arguments are provided** (just `/cofounder`), reply with this message exactly:

> **Available co-founder lenses:**
> - `project-pulse` — Daily MVP progress, blockers, priorities
> - `product-vision` — User experience, product direction
> - `architecture` — Tech debt, patterns, risks
> - `wild-ideas` — Creative brainstorming, no filter
> - `market-research` — Competitors, AI news, therapy software
> - `website-audit` — alaskafamilysystems.com conversion/UX/SEO
> - `customer-support` — Support patterns, community, FAQ
> - `training-programs` — Free license programs, renewals, outreach
> - `process-retro` — Dev process efficiency, time allocation
>
> **Commands:**
> - `/cofounder <lens>` — Run a lens (posts to #co-founder in ~5-10 min)
> - `/cofounder followup <lens> <question>` — Continue the conversation from the last briefing
> - `/cofounder read <lens>` — Show the latest briefing for a lens

---

### Mode 1: Run a lens

**If a single lens name IS provided** (e.g., `/cofounder architecture`), do exactly this:

1. Run this exec command (replace `<lens-name>` with the provided name):

```
exec(command="nohup /bin/bash /Users/hurin/.openclaw/co-founder/co-founder.sh <lens-name> >> /Users/hurin/.openclaw/co-founder/cron.log 2>&1 &")
```

2. Reply: "Kicked off `<lens-name>` — check #co-founder in ~5-10 minutes. The analysis runs multiple passes now so it takes a bit longer."

---

### Mode 2: Follow up on a briefing

**If the first argument is "followup"** (e.g., `/cofounder followup architecture What about the database schema?`):

1. Parse the lens name (second word) and the message (everything after the lens name).
2. Run this exec command:

```
exec(command="cd /Users/hurin/Projects/theapp && SESSION_ID=$(cat /Users/hurin/.openclaw/co-founder/sessions/<lens-name>-session.txt 2>/dev/null) && /Users/hurin/.local/bin/claude -p --model claude-opus-4-6 --dangerously-skip-permissions --resume \"$SESSION_ID\" <<'PROMPT'\n<the follow-up message>\nPROMPT")
```

3. Relay CC's response **verbatim** to the channel. This resumes the original briefing session, so CC has full context of its analysis.

If the session file doesn't exist, reply: "No session found for `<lens-name>`. Run `/cofounder <lens-name>` first to generate a briefing, then follow up."

---

### Mode 3: Read the latest briefing

**If the first argument is "read"** (e.g., `/cofounder read architecture`):

1. Run: `exec(command="cat /Users/hurin/.openclaw/co-founder/briefings/<lens-name>-latest.md 2>/dev/null || echo 'No briefing found for <lens-name>. Run /cofounder <lens-name> first.'")`
2. Relay the content verbatim.

---

**CRITICAL RULES for this skill:**
- Do NOT route to CC via `claude -p` for Mode 1. The script internally calls CC. You are just a launch button.
- Mode 2 (followup) DOES call CC directly — this is intentional, it resumes the briefing session.
- Do NOT read any files yourself.
- Do NOT add commentary or summaries beyond what's specified above.
- This overrides the normal "route everything to CC" rule. Just exec and confirm.
