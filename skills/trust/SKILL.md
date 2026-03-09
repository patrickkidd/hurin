---
name: trust
description: "View the trust ledger — tracks system proposal accuracy. Usage: /trust — show accuracy summary. /trust pending — show proposals awaiting outcomes. /trust decisions — show the decision log."
user-invocable: true
metadata: { "openclaw": { "always": true, "emoji": "📈" } }
---

## /trust — Trust Ledger & Decision Log

**If no arguments or "summary"** (just `/trust`):

1. Run:

```
exec(command="cd /home/hurin/.openclaw/monitor && python3 -c 'from trust_ledger import get_summary; import json; s=get_summary(); [print(f\"**{cat}**: {d[\"accuracy\"]*100:.0f}% accuracy ({d[\"correct\"]}/{d[\"total\"]} correct, {d[\"pending\"]} pending)\") if d[\"total\"]>0 else print(f\"**{cat}**: no data yet ({d[\"pending\"]} pending)\") for cat,d in s.items()]'")
```

2. Relay the output verbatim.

---

### Mode 2: Pending proposals

**If the first argument is "pending"** (e.g., `/trust pending`):

1. Run:

```
exec(command="cd /home/hurin/.openclaw/monitor && python3 -c 'from trust_ledger import get_pending; ps=get_pending(); [print(f\"- [{p[\"category\"]}] {p[\"proposal_id\"]}: {p[\"description\"][:80]}\") for p in ps] if ps else print(\"No pending proposals.\")'")
```

2. Relay the output verbatim.

---

### Mode 3: Decision log

**If the first argument is "decisions"** (e.g., `/trust decisions`):

1. Run: `exec(command="cat /home/hurin/.openclaw/decisions/log.md")`
2. Relay the content verbatim.

---

**CRITICAL RULES for this skill:**
- All modes are simple script/command executions. Just run and relay.
- Do NOT add commentary beyond what's specified above.
