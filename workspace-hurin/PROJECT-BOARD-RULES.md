# GitHub Project Board Maintenance Rules

**Project:** Family Diagram #4 — `https://github.com/users/patrickkidd/projects/4`

The project board is the **single source of truth** for all work tracking. These rules are permanent and must be followed by all agents.

## Structure

- **Milestones** (Goal 1, Goal 2, Goal 3) define sequential product goals.
- **Sub-issues** model dependencies within a milestone — if B can't start until A is done, B is a sub-issue of A.
- **Priority** (P0→P3) encodes execution order; same-priority issues are parallelizable.

## Sub-Issue Milestone Invariant (CRITICAL)

**Sub-issues must NEVER have the Milestone field set.**

GitHub duplicates them as sibling cards if the milestone matches the parent. Always clear the milestone when adding a sub-issue relationship. Only top-level parent issues get milestones.

## Required Fields

**Every open issue must have:** Status, Assignee, Priority.

**Every closed issue must have:** Status = Done.

## Assignee Rule

- `patrickkidd-hurin` — fully automatable tasks
- `patrickkidd` — anything requiring human judgment, credentials, or design decisions

## Lifecycle Rules

### On Creating an Issue

1. Determine milestone (Goal 1/2/3)
2. Check if it depends on an existing open issue in the same milestone → make it a sub-issue if so
3. Set Priority, Assignee, Status

### On Completing an Issue

1. Set Status = Done
2. Check sub-issues that were blocked solely by this one → they're now unblocked, re-evaluate priority
3. If it was the last open issue in a milestone → flag to Patrick

### Cross-Branch Dependencies

When blocked by issues from two unrelated chains:
- Use **sub-issue** for the primary blocker
- Use `Blocked by owner/repo#N` in the issue body for secondary blockers

## Periodic Review

At least weekly, or when asked. Verify:

1. Sub-issue DAG consistency (no cycles, correct parent-child relationships)
2. No sub-issues with milestone set
3. All issues have Assignee, Status, Priority
4. Identify critical path: longest chain of dependent issues to milestone completion

**Report format:**
```
{N} open in {milestone}, critical path is {chain}, next unblocked: {list}
```

## Object IDs

### Project

| Key | ID |
|---|---|
| Project | `PVT_kwHOABjmWc4BP0PU` |

### Status Field: `PVTSSF_lAHOABjmWc4BP0PUzg-HbRs`

| Value | Option ID |
|---|---|
| Todo | `1a206b7c` |
| In Progress | `f2e96042` |
| Done | `3fb3f387` |

### Priority Field: `PVTSSF_lAHOABjmWc4BP0PUzg-HbS4`

| Value | Option ID |
|---|---|
| P0 - Critical | `932aef5c` |
| P1 - High | `df1b629f` |
| P2 - Medium | `fcaadcab` |
| P3 - Low | `6b1dd892` |

### Owner Field: `PVTSSF_lAHOABjmWc4BP0PUzg-HbS8`

| Value | Option ID |
|---|---|
| Patrick | `2120b409` |
| Hurin | `4e27439a` |
| Beren | `fb745a0e` |
| Tuor | `e0b8b5b9` |

### Component Field: `PVTSSF_lAHOABjmWc4BP0PUzg-HbTo`

| Value | Option ID |
|---|---|
| Frontend | `053c7604` |
| Backend | `6f4da7de` |
| Infra | `636ff93f` |
| Design | `e39a507e` |
| Both | `f025646c` |

### Repos

- `patrickkidd/familydiagram`
- `patrickkidd/btcopilot`
- `patrickkidd/fdserver`
- `patrickkidd/hurin`

### Auth

Token needs `project` scope for project field mutations.
