---
name: cofounder
description: "Run a co-founder strategic briefing lens on demand. Usage: /cofounder <lens-name>. Available lenses: project-pulse, product-vision, architecture, wild-ideas, market-research, website-audit, customer-support, training-programs, process-retro, evolution. Also: read, approve, refine, actions, status."
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
> - `/cofounder read <lens>` — Show the latest briefing for a lens
> - `/cofounder approve <action-id>` — Approve and spawn a proposed action
> - `/cofounder refine <action-id> <feedback>` — Refine an action before approving
> - `/cofounder actions` — List pending actions awaiting approval
> - `/cofounder status` — Global status dashboard (PRs to review, running tasks, queue, pending approvals)
>
> For follow-ups, reply in the briefing thread — native thread bindings handle session resumption.

---

### Mode 1: Run a lens

**If a single lens name IS provided** (e.g., `/cofounder architecture`), do exactly this:

1. Run this exec command (replace `<lens-name>` with the provided name):

```
exec(command="nohup /bin/bash /home/hurin/.openclaw/co-founder/co-founder.sh <lens-name> >> /home/hurin/.openclaw/co-founder/cron.log 2>&1 &")
```

2. Reply: "Kicked off `<lens-name>` — check #co-founder in ~5-10 minutes. The analysis runs multiple passes now so it takes a bit longer."

---

### Mode 2: Read the latest briefing

**If the first argument is "read"** (e.g., `/cofounder read architecture`):

1. Run: `exec(command="cat /home/hurin/.openclaw/co-founder/briefings/<lens-name>-latest.md 2>/dev/null || echo 'No briefing found for <lens-name>. Run /cofounder <lens-name> first.'")`
2. Relay the content verbatim.

---

### Mode 3: Approve an action

**If the first argument is "approve"** (e.g., `/cofounder approve project-pulse-2026-02-27-1`):

1. Parse the action ID (second word).
2. Run this exec command:

```
exec(command="/bin/bash /home/hurin/.openclaw/co-founder/action-approve.sh <action-id>")
```

3. Relay the output verbatim. This spawns the approved action via spawn-task.sh.

---

### Mode 4: Refine an action

**If the first argument is "refine"** (e.g., `/cofounder refine project-pulse-2026-02-27-1 change the approach to use React instead`):

1. Parse the action ID (second word) and the feedback (everything after the action ID).
2. Run this exec command:

```
exec(command="/bin/bash /home/hurin/.openclaw/co-founder/action-refine.sh <action-id> <feedback>")
```

3. Relay CC's response **verbatim**. This resumes the original briefing CC session with the feedback, so CC revises the action plan with full context.

---

### Mode 5: List pending actions

**If the first argument is "actions"** (e.g., `/cofounder actions`):

1. Run: `exec(command="/bin/bash /home/hurin/.openclaw/co-founder/action-list.sh")`
2. Relay the output verbatim.

---

### Mode 6: Global status dashboard

**If the first argument is "status"** (e.g., `/cofounder status`):

1. Run: `exec(command="/bin/bash /home/hurin/.openclaw/co-founder/action-status.sh")`
2. Relay the output verbatim. This shows the unified status across GitHub Issues, the task queue, and running tasks.

---

**CRITICAL RULES for this skill:**
- Do NOT route to CC directly for Mode 1. The script internally calls CC. You are just a launch button.
- Mode 4 (refine) resumes the CC session via the script — async, not blocking.
- Mode 3 (approve) and Mode 5 (actions) are simple script executions — just run and relay.
- Do NOT read any files yourself.
- Do NOT add commentary or summaries beyond what's specified above.
- This overrides the normal "route everything to CC" rule. Just exec and confirm.
