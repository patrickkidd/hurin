---
name: cofounder
description: "Run a co-founder strategic briefing lens on demand. Usage: /cofounder <lens-name>. Available lenses: project-pulse, product-vision, architecture, wild-ideas, market-research, website-audit, customer-support, training-programs, process-retro, evolution. Also: followup, read, approve, refine, actions, status."
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
> - `evolution` — External intelligence: agent patterns, OpenClaw, AI co-founder techniques
>
> **Commands:**
> - `/cofounder <lens>` — Run a lens (posts to #co-founder in ~5-10 min)
> - `/cofounder followup <lens> <question>` — Continue the conversation from the last briefing
> - `/cofounder read <lens>` — Show the latest briefing for a lens
> - `/cofounder approve <action-id>` — Approve and spawn a proposed action
> - `/cofounder refine <action-id> <feedback>` — Refine an action before approving
> - `/cofounder actions` — List pending actions awaiting approval
> - `/cofounder status` — Global status dashboard (PRs to review, running tasks, queue, pending approvals)

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

### Mode 4: Approve an action

**If the first argument is "approve"** (e.g., `/cofounder approve project-pulse-2026-02-27-1`):

1. Parse the action ID (second word).
2. Run this exec command:

```
exec(command="/bin/bash /Users/hurin/.openclaw/co-founder/action-approve.sh <action-id>")
```

3. Relay the output verbatim. This spawns the approved action via spawn-task.sh.

---

### Mode 5: Refine an action

**If the first argument is "refine"** (e.g., `/cofounder refine project-pulse-2026-02-27-1 change the approach to use React instead`):

1. Parse the action ID (second word) and the feedback (everything after the action ID).
2. Run this exec command:

```
exec(command="/bin/bash /Users/hurin/.openclaw/co-founder/action-refine.sh <action-id> <feedback>")
```

3. Relay CC's response **verbatim**. This resumes the original briefing CC session with the feedback, so CC revises the action plan with full context.

---

### Mode 6: List pending actions

**If the first argument is "actions"** (e.g., `/cofounder actions`):

1. Run: `exec(command="/bin/bash /Users/hurin/.openclaw/co-founder/action-list.sh")`
2. Relay the output verbatim.

---

### Mode 7: Global status dashboard

**If the first argument is "status"** (e.g., `/cofounder status`):

1. Run: `exec(command="/bin/bash /Users/hurin/.openclaw/co-founder/action-status.sh")`
2. Relay the output verbatim. This shows the unified status across GitHub Issues, the task queue, and running tasks.

---

**CRITICAL RULES for this skill:**
- Do NOT route to CC via `claude -p` for Mode 1. The script internally calls CC. You are just a launch button.
- Mode 2 (followup) and Mode 5 (refine) DO call CC directly — this is intentional, they resume the briefing session.
- Mode 4 (approve) and Mode 6 (actions) are simple script executions — just run and relay.
- Do NOT read any files yourself.
- Do NOT add commentary or summaries beyond what's specified above.
- This overrides the normal "route everything to CC" rule. Just exec and confirm.
