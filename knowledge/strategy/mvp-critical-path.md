# MVP Critical Path

Last verified: 2026-03-10

## Status: ~87% complete

FamilyDiagram is the first AI+Bowen-family-systems clinical tool. No direct competitor exists.

## Product Components

| Component | Repo | Status |
|-----------|------|--------|
| Pro app (existing) | familydiagram | Mature, needs personal app integration |
| Personal app backend | btcopilot | Active development — Patrick working on training/extraction |
| Server | fdserver | Supporting both apps |
| Dev harness | theapp | Monorepo dev environment |

## Patrick's Current Focus

Patrick works interactively with Claude Code pushing to master (branch by abstraction). Primary focus areas:
- Training pipeline / personal app MVP
- AI extraction features (Gemini + Claude)
- UI/UX for personal app

## What's Left for MVP

Tracked in GitHub Project #4 as Goal 1/2/3 status values.
See TODO.md in theapp for current task breakdown.

## Important Context (from Patrick)

- **familydiagram CI** has never run in GitHub Actions due to infra issues. Patrick runs it manually. Team-lead should stop recommending "run familydiagram master CI."
- **Extraction dedup** (T7-11) is no longer an issue — PDP is cleared on re-extract and there's no reliable way to match people by name. Team-lead should stop recommending dedup work.
- **Quick-wins channel** definition has been thrashed on repeatedly. The only real team-lead data so far is Patrick cleaning up floods of low-quality duplicate PRs. Patrick is considering pausing quick-wins in favor of briefings.

## Key Risks

1. Solo founder bandwidth — Patrick's time is the bottleneck
2. Market validation not started — no users testing the product yet
3. Agent system ROI uncertain — 15.9% spawn accuracy (7/44 merged). Most agent time creates cleanup work for Patrick.
4. Agent system is a net time sink — Patrick spends more time triaging low-quality output than he saves from the occasional successful PR
