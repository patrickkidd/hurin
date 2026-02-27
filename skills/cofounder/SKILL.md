---
name: cofounder
description: "Run a co-founder strategic briefing lens on demand. Usage: /cofounder <lens-name>. Available lenses: project-pulse, product-vision, architecture, wild-ideas, market-research, website-audit, customer-support, training-programs, process-retro."
user-invocable: true
metadata: { "openclaw": { "always": true, "emoji": "🧠" } }
---

## /cofounder — Co-Founder Lens Launcher

**If no lens name is provided** (just `/cofounder` with no arguments), reply with this message exactly:

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
> Usage: `/cofounder <lens-name>`

**If a lens name IS provided**, do exactly this and nothing else:

1. Run this exec command (replace `<lens-name>` with the provided name):

```
exec(command="nohup /bin/bash /Users/hurin/.openclaw/co-founder/co-founder.sh <lens-name> >> /Users/hurin/.openclaw/co-founder/cron.log 2>&1 &")
```

2. Reply: "Kicked off `<lens-name>` — check #co-founder in a few minutes."

**CRITICAL RULES for this skill:**
- Do NOT route to CC via `claude -p`. This skill handles everything itself.
- Do NOT read any files.
- Do NOT add commentary or summaries.
- The script internally calls CC, writes to journal, and posts to #co-founder. You are just a launch button.
- This overrides the normal "route everything to CC" rule. Just exec and confirm.
