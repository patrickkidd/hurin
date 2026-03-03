# ADR-0005: Co-Founder Action System

**Status:** Accepted

**Date:** 2026-02-27

**Deciders:** Patrick

**Supersedes:** None

**Related:** [ADR-0004: Co-Founder System](ADR-0004-co-founder-system.md)

## Context

The co-founder briefing system (ADR-0004) generates deep 15-17K char analyses via 9 rotating lenses. The output is rich but creates mental load — actionable items are buried in prose. Patrick wants to wake up to low-lift approvals that could generate revenue, not walls of text to parse.

## Decision

Add a quality-gated action pipeline to the co-founder system. Most briefings produce zero actions — that's by design. Actions are only proposed when CC identifies something it can fully implement end-to-end that delivers clear value. All actions require Patrick's approval before spawning. Revenue-impacting items get a dedicated `#quick-wins` Discord channel.

**Source of truth:** GitHub Issues, not Discord. Every action becomes a GitHub Issue assigned to Patrick with structured labels. Discord is for notifications only.

**Design principle:** Quality over quantity. An action must be (1) fully automatable by CC, (2) clearly valuable, (3) trivial/small effort, and (4) high confidence. If any of these aren't met, it stays as prose in the briefing.

### Action Schema

When a briefing identifies genuine quick wins, it ends with a `proposed-actions` JSON code block:

```json
{
  "actions": [
    {
      "id": "<lens>-<YYYY-MM-DD>-<n>",
      "title": "Short imperative description",
      "category": "revenue|ux|velocity|bugfix|content|infrastructure",
      "effort": "trivial|small",
      "confidence": 0.0-1.0,
      "repo": "btcopilot|familydiagram|website|none",
      "plan": "Step-by-step implementation plan",
      "spawn_prompt": "Full self-contained prompt for CC",
      "success_metric": "How we know this worked"
    }
  ]
}
```

### Approval Model

All actions require Patrick's approval. There is no auto-spawn tier.

- `/cofounder approve <id>` — spawns via spawn-task.sh, PR created
- `/cofounder refine <id> <feedback>` — iterates on the plan before approving
- `/cofounder actions` — lists pending items

### Routing Rules

| Action category | Discord Channel | GitHub Issue |
|----------------|----------------|-------------|
| revenue | #quick-wins | Yes, assigned to Patrick |
| other | #co-founder | Yes, assigned to Patrick |

### Approval Flow

1. **Approve:** `/cofounder approve <id>` → spawns via spawn-task.sh, updates issue
2. **Refine:** `/cofounder refine <id> <feedback>` → resumes CC session, revises action, updates issue
3. **List:** `/cofounder actions` → shows pending actions

### WordPress Integration

Website actions (`repo="website"`) create **draft** posts/pages in WordPress via REST API. Drafts are invisible to visitors — same safety gate as PRs for code.

- Endpoint: `https://alaskafamilysystems.com/wp-json/wp/v2/posts|pages`
- Auth: HTTP Basic Auth with application password
- Always creates drafts (never publishes)
- Content also saved to `website-content/<action-id>.md` in git

## Architecture

```
co-founder.sh runs a lens
  └── CC produces briefing + optional proposed-actions JSON
        ├── Briefing (JSON stripped) → Discord #co-founder + briefings/<lens>-<date>.md
        └── Actions (if any) → actions/<lens>-<date>.json
              └── action-router.sh (background)
                    ├── GitHub Issue created (source of truth)
                    ├── Discord notification (link to issue)
                    │     ├── revenue category → #quick-wins
                    │     └── other category → #co-founder
                    └── All actions → await /cofounder approve
                          ├── /cofounder approve → action-approve.sh → spawn-task.sh
                          └── /cofounder refine → action-refine.sh → resume CC session
```

## File Layout

```
~/.openclaw/co-founder/
  action-router.sh        # Routes actions: GitHub Issues + Discord + spawning
  action-approve.sh       # Approves and spawns propose-tier actions
  action-refine.sh        # Iterative refinement via CC session resumption
  action-list.sh          # Dashboard of pending actions
  wp-draft.sh             # WordPress draft creator via REST API
  actions/                # Action JSON files (committed)
    <lens>-<date>.json    # e.g. project-pulse-2026-02-27.json
  actions.log             # Router execution log (gitignored)
  website-content/        # WordPress draft markdown backups (committed)
    <action-id>.md        # Content with frontmatter

~/.openclaw/skills/cofounder/
  SKILL.md                # Updated with approve/refine/actions modes
```

## GitHub Labels

The following labels are used on GitHub Issues:

- `co-founder` — all actions from the co-founder system
- `propose` — awaiting approval
- `revenue` / `ux` / `velocity` / `bugfix` / `content` / `infrastructure` / `strategic` — category

## How to Modify

### Add a new category
1. Add the category name to the schema docs in co-founder.sh prompt
2. Create the GitHub label in `patrickkidd/theapp`
3. No code changes needed — categories are just labels

### Change tier rules
1. Modify the tier classification rules in co-founder.sh prompt template
2. Update this ADR

### Change routing
1. Modify `action-router.sh` channel selection logic
2. Update this ADR's routing table

### Add a new action target (beyond spawn-task.sh)
1. Add handling in `action-router.sh` for the new target
2. Update this ADR

## Consequences

### Positive

- Patrick wakes up to genuinely actionable items, not walls of prose
- Revenue-impacting items get dedicated visibility in #quick-wins
- All actions require approval — no unsupervised spawning
- Most briefings produce zero actions, keeping signal-to-noise high
- Iterative refinement lets Patrick shape actions before committing
- GitHub Issues provide durable tracking (Discord is ephemeral)
- WordPress drafts keep website content flowing without manual creation

### Negative

- More moving parts (5 new scripts)
- CC may produce low-quality action suggestions early on (prompt will need tuning)
- Requires discipline: if CC starts padding with filler actions, prompt needs tightening

### Risks

- WordPress credentials in config.sh (plaintext, same risk as Discord token)
- GitHub API rate limits could affect high-volume days (unlikely — most briefings have 0 actions)

## Related

- [ADR-0004: Co-Founder System](ADR-0004-co-founder-system.md) — parent system
- [ADR-0001: Agent Swarm Setup](ADR-0001-agent-swarm.md) — spawn-task.sh infrastructure
