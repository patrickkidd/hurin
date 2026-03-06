# Workflow Automation Scripts

Helper scripts for managing GitHub projects and background Claude Code tasks.

## Quick Reference

### Task Management (use the `task` wrapper)

| Command | Use Case |
|---------|----------|
| `task spawn <repo> <id> '<desc>'` | Start a background Claude Code task |
| `task status` | Dashboard of all active tasks |
| `task watch <task-id>` | Watch a specific task (live JSONL log) |
| `task list` | List all task names |
| `task kill <task-id>` | Kill stuck task, clean up worktree |
| `task follow-up <id> "<msg>"` | Resume a completed task's session |

### GitHub Project Integration

| Command | Use Case |
|---------|----------|
| `gh-project-find-item.sh <repo> <issue>` | Find GitHub issue in project board |
| `gh-project-sync.sh <item-id> --status <status> --owner <owner>` | Update project item status/owner |

## Detailed Usage

### spawn-task.sh — Background Implementation

Spawns a Claude Code agent in a background tmux session to implement a task. Automatically creates a git worktree, registers the task, and makes it monitorable via `tasks.sh`.

**Usage:**
```bash
spawn-task.sh --repo <btcopilot|familydiagram> \
  --task <task-id> \
  --description '<short description>' \
  [--branch <custom-branch>] \
  [--full-sync] \
  <<'PROMPT'
Your detailed prompt here, with context and requirements.
PROMPT
```

**Options:**
- `--repo` (required): Which repo the PR will target (btcopilot or familydiagram)
- `--task` (required): Task identifier (used for branch, worktree, and tmux session names). Example: `T7-4`, `fix-crash-29`
- `--description` (required): Human-readable task description
- `--branch`: Override the branch name (default: `feat/<task-id>`)
- `--full-sync`: Run `uv sync` in the worktree instead of symlinking .venv. Use when dependencies change.

**Example:**
```bash
spawn-task.sh --repo familydiagram --task T7-4 --description "Add Build Diagram button" <<'PROMPT'
Implement the 'Build my diagram' button in Personal app. Should:
- Appear on main toolbar
- Be disabled when no session is active
- Show progress indicator during extraction
Done = button works end-to-end, tests pass, PR created with screenshot.
PROMPT
```

**After spawning:**
```bash
tasks.sh        # See dashboard of all active tasks
tasks.sh T7-4   # Watch just this task (live)
```

### tasks.sh — Monitor Tasks

Shows status of all active Claude Code tasks with last 20 lines of output from each.

**Usage:**
```bash
tasks.sh           # Dashboard: status + output for all active tasks
tasks.sh -l        # List only (no output capture)
tasks.sh <task-id> # Attach to specific task in tmux (live, read-only)
```

**Output example:**
```
────────────────────────────────────────────────────────────
  T7-4  [familydiagram]  ● running  2h13m elapsed
  Branch: feat/T7-4

  ──────────────── last 20 lines ────────────────
  > Analyzing the codebase...
  > Found DiscussView class at Personal/DiscussView.qml
  > Added button to toolbar
  > Running tests...
  ✓ All tests pass
  > Creating PR #156

────────────────────────────────────────────────────────────
```

**What's happening behind the scenes:**
- Each spawned task runs in its own tmux session named `claude-<task-id>`
- Task state is tracked in `.clawdbot/active-tasks.json` in the monorepo
- The task daemon (`~/.openclaw/monitor/task-daemon.py`) manages task execution, auto-respawns failures (up to 3x), and streams progress to Discord

### gh-project-find-item.sh — Locate Issue in Project

Finds the GitHub project item ID for an issue. Useful before calling `gh-project-sync.sh`.

**Usage:**
```bash
gh-project-find-item.sh <owner/repo> <issue-number>
```

**Example:**
```bash
$ gh-project-find-item.sh patrickkidd/familydiagram 156
PVTI_kwHOABjmWc4BP0PUzg...

# Use this ID with gh-project-sync.sh
gh-project-sync.sh PVTI_kwHOABjmWc4BP0PUzg... --status Done
```

### gh-project-sync.sh — Update Project Item

Updates a GitHub project item's status or owner.

**Usage:**
```bash
gh-project-sync.sh <item-id> [--status <status>] [--owner <owner>]
```

**Valid statuses:** `Todo`, `In Progress`, `Done`
**Valid owners:** `Patrick`, `Hurin`
**Valid priorities:** `P0`, `P1`, `P2`, `P3`
**Valid components:** `Frontend`, `Backend`, `Infra`, `Design`, `Both`

**Example:**
```bash
# Mark issue as In Progress and assign to Hurin
gh-project-sync.sh PVTI_kwHOABjmWc4BP0PUzg... \
  --status "In Progress" \
  --owner Hurin
```

## Typical Workflow

### 1. Spawn a task for a GitHub issue

```bash
# Find the issue and get its item ID
ITEM_ID=$(gh-project-find-item.sh patrickkidd/familydiagram 156)

# Mark as In Progress + assign to yourself
gh-project-sync.sh "$ITEM_ID" --status "In Progress" --owner Hurin

# Spawn the task (prompt from SOUL.md or TOOLS.md pattern)
spawn-task.sh --repo familydiagram --task T7-4 \
  --description "Build my diagram button" <<'PROMPT'
Implement the 'Build my diagram' button in Personal app.
See issue #156. Button should appear on toolbar, be disabled when no session,
show progress during extraction. Done = PR created, tests pass, screenshot included.
PROMPT
```

### 2. Monitor the task

```bash
# Check all tasks
tasks.sh

# Watch this specific task
tasks.sh T7-4

# If it fails, the monitor script will alert you with the failure log
# Read ~/.openclaw/monitor/failures/T7-4.log to diagnose
```

### 3. When PR is created

The monitor script automatically:
- Captures the PR number and URL
- Runs CI checks
- Runs an automated review
- Updates the project item status to "PR Open"

When CI passes and review is approved:
- Updates project status to `Done`
- Cleans up the worktree

## Environment Variables

These can override defaults:

```bash
# Point to a different dev repo (default: ~/.openclaw/workspace-hurin/theapp)
export DEV_REPO=/path/to/your/monorepo

spawn-task.sh --repo btcopilot --task my-fix ...
```

## Troubleshooting

**"Task not found" when running `tasks.sh <task-id>`**
- Check that the registry exists: `cat ~/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json`
- Verify the task ID matches exactly

**Task appears stuck (no output for a long time)**
- Check task logs: `task watch <task-id>`
- If truly stuck, kill and re-spawn:
  ```bash
  task kill <task-id>
  task spawn <repo> <new-id> '<desc>' <<'PROMPT'
  ...
  PROMPT
  ```

**`gh-project-sync.sh` returns empty or errors**
- Verify gh CLI is authenticated: `gh auth status`
- Verify the item ID format is correct (starts with `PVTI_`)

## Reference: Full System Flow

```
┌─ Patrick sends message to Hurin (Discord)
│
├─ Hurin routes to CC via claude -p (sync planning)
│  OR
├─ Hurin spawns background task via spawn-task.sh
│  │
│  ├─ Creates git worktree + branch
│  ├─ Starts tmux session running `claude -p`
│  ├─ Registers task in .clawdbot/active-tasks.json
│  └─ Returns immediately (fire-and-forget)
│
├─ Task daemon (~/.openclaw/monitor/task-daemon.py) manages execution
│  │
│  ├─ Streams progress to Discord thread in real time
│  ├─ Watches for PR creation
│  ├─ Auto-respawns on failure (up to 3x with session resume)
│  ├─ Syncs project board on completion
│  └─ On max respawns exhausted: escalates to Hurin (Ralph Loop)
│
└─ When complete: PR merged, worktree cleaned, task marked Done
```

---

**Last updated:** February 2026  
**Related docs:** SOUL.md, TOOLS.md, AGENTS.md

---

## Quick Start: The `task` Wrapper

For the fastest workflow, use the `task` wrapper script:

```bash
# Start a task
task spawn familydiagram T7-4 'Build diagram button' <<'PROMPT'
Implement the 'Build my diagram' button...
PROMPT

# Check status
task status       # All tasks
task status T7-4  # Just T7-4

# Watch it run
task watch T7-4

# List active
task list
```

This is equivalent to the longer commands but with less typing.

## NEW: Automated GitHub Project Board Sync

**Problem:** The documented workflow requires manual project board updates:
```bash
# Manual workflow (before)
gh-project-find-item.sh patrickkidd/familydiagram 156
gh-project-sync.sh <item-id> --status "In Progress" --owner Hurin
```

**Solution:** Automated sync integrated into spawn and monitor:

### spawn-task-with-project.sh — Spawn with Automatic Project Sync

When you provide a GitHub issue number, the task spawning automatically syncs the project board.

**Usage:**
```bash
spawn-task-with-project.sh --repo familydiagram --task T7-4 \
  --description 'Build diagram button' --issue 156 <<'PROMPT'
Implement the 'Build my diagram' button in Personal app.
Done = button works end-to-end, tests pass, PR created with screenshot.
PROMPT
```

**What happens:**
1. Task is spawned in background (same as spawn-task.sh)
2. GitHub project item for issue #156 is found automatically
3. Project item is synced to "In Progress" with owner "Hurin"
4. Issue number is stored in task registry for later reference

### task spawn — Unified Command with Project Sync

The `task` wrapper now supports `--issue` for automatic project sync:

```bash
task spawn familydiagram T7-4 'Build button' --issue 156 <<'PROMPT'
Implement the button...
PROMPT
```

This is equivalent to the full spawn-task-with-project.sh command but shorter.

### sync-project.sh — Manual Project Board Sync

Standalone helper to sync issues to the project board:

```bash
# Find project item for issue
sync-project.sh patrickkidd/familydiagram 156

# Mark as Done
sync-project.sh patrickkidd/familydiagram 156 --status Done

# Full sync with owner
sync-project.sh patrickkidd/btcopilot 42 --owner Hurin --status "In Progress"
```

### task kill — Kill a Stuck Task

Sometimes a task gets stuck (tmux session alive but Claude Code not responding). The `kill` command:
- Kills the tmux session
- Removes the git worktree
- Removes the task from the registry (prevents Ralph Loop from trying to respawn)

**Usage:**
```bash
task kill T7-4
```

**What it does:**
```
→ Killing task: T7-4
  Session: claude-T7-4
  Worktree: ~/.openclaw/workspace-hurin/theapp-worktrees/T7-4
  → Killing tmux session...
  ✓ tmux session killed
  → Removing worktree...
  ✓ worktree removed
✓ Task T7-4 killed and cleaned up
  (Removed from registry - Ralph Loop will not attempt respawn)
```

**When to use:**
- Task appears "running" but Claude Code is hung (no output for a long time)
- You want to stop a task without waiting for Ralph Loop to detect failure
- You need to free up resources (tmux session, worktree)

**Note:** If you want to restart the task, spawn a new one with a new task ID.

### task sync — Unified Command for Project Sync

Same as sync-project.sh but via the `task` wrapper:

```bash
task sync patrickkidd/familydiagram 156 --status Done
task sync patrickkidd/btcopilot 42 --owner Hurin --status "In Progress"
```

## Workflow Comparison

### Before (Manual Sync)

```bash
# Spawn task
spawn-task.sh --repo familydiagram --task T7-4 \
  --description 'Build button' <<'PROMPT'
Implement the button...
PROMPT

# Manually find and sync project (separate commands)
gh-project-find-item.sh patrickkidd/familydiagram 156
gh-project-sync.sh <item-id> --status "In Progress" --owner Hurin

# Monitor task
task watch T7-4

# When PR is ready (still manual)
gh-project-sync.sh <item-id> --status Done
```

### After (Automatic Sync)

```bash
# Spawn task WITH automatic project sync (one command)
task spawn familydiagram T7-4 'Build button' --issue 156 <<'PROMPT'
Implement the button...
PROMPT

# Monitor task
task watch T7-4

# When PR is ready (check-agents.py handles it automatically)
# → You'll be notified when PR is ready to merge
```

## Implementation Details

- **spawn-task-with-project.sh** stores the issue number in the task registry
- **check-agents.py** (monitor script) can use the stored issue number for future enhancements
- **Project item lookup** is done via `gh-project-find-item.sh`
- **Project item sync** is done via `gh-project-sync.sh`
- All project sync operations fail gracefully—if sync fails, the task still spawns successfully

## Benefits

✓ **Fewer manual steps** — Project sync happens automatically with task spawn
✓ **Consistent state** — Project board stays in sync with actual work
✓ **Error-safe** — Project sync failures don't break task spawning
✓ **Backward compatible** — Old spawn-task.sh still works without changes
✓ **Flexible** — You can always use sync-project.sh/task sync manually if needed

---

**Added:** Feb 28, 2026  
**Status:** Ready for production use

---

## Automatic GitHub Project Board Sync (NEW — March 1, 2026)

### What Changed

When a background task's PR reaches "ready to merge" state (CI passing + review approved), the GitHub project board is **now automatically synced to "Done"** status.

### The Improvement

**Before:** After PR is ready to merge, you must manually run `gh-project-sync.sh` to update the project board.

**After:** The monitor script (`check-agents.py`) automatically syncs the project board to "Done" when it detects the PR is ready.

### How to Use

When spawning a task, include the `--issue` flag with the GitHub issue number:

```bash
task spawn familydiagram T7-4 'Build button' --issue 156 <<'PROMPT'
Implement the 'Build my diagram' button in Personal app.
See issue #156. The button should appear on the main toolbar,
be disabled when no session is active, and show a progress indicator.
Done = button works end-to-end, tests pass, PR created with screenshot.
PROMPT
```

The `--issue 156` flag:
- Stores the issue number in the task registry
- Allows the monitor to find and sync the GitHub project item automatically
- Eliminates the need for manual `gh-project-sync.sh` after PR is ready

### What Happens Automatically

1. **On spawn** → Project board synced to "In Progress" (already existed)
2. **On PR creation** → Monitor detects it (already existed)
3. **On PR ready** → Monitor automatically syncs project board to "Done" (NEW)
4. **After sync** → Worktree cleaned up (already existed)

### Fallback Behavior

If you spawn a task **without** the `--issue` flag:
- The monitor still works normally
- When PR is ready, it pings you: "PR READY TO MERGE"
- You can manually sync if needed: `task sync patrickkidd/familydiagram 156 --status Done`

### How It's Logged

Monitor logs show the automatic sync:
```
[2026-03-01 09:15:00] Checking T7-4 (familydiagram)
[2026-03-01 09:15:01]   PR #156 found: https://github.com/patrickkidd/familydiagram/pull/156
[2026-03-01 09:15:02]   ✓ Project board synced: issue #156 → Done
[2026-03-01 09:15:03]   Cleaned up worktree: ~/.openclaw/workspace-hurin/theapp-worktrees/T7-4
[2026-03-01 09:15:04] Check complete.
```

### Edge Cases

- **No issue number in registry:** Logs a note, continues without sync. Sync is still available manually.
- **GitHub project item not found:** Logs a warning, continues. PR is still created successfully.
- **Sync fails:** Logs error, doesn't block other cleanup. Sync can be attempted manually.

### Reliability

- ✓ Graceful fallback if issue number not provided
- ✓ No blocking failures (sync is optional)
- ✓ Full audit trail in monitor.log
- ✓ Works with existing gh-project-find-item.sh and gh-project-sync.sh scripts
- ✓ Zero new dependencies


---

## gh-quick.sh — Quick GitHub Queries (NEW!)

Fast GitHub queries with sensible defaults. No more remembering complex `gh` flags.

**Default repo:** `patrickkidd/familydiagram`

### Usage

```bash
gh-quick.sh <command> [repo]

# Commands:
#   prs        — List open PRs
#   issues     — List open issues
#   mine       — Issues/PRs assigned to you
#   ci         — Recent CI runs
#   status     — Quick dashboard (PRs + issues count)
#   recent     — Recent commits on main
#   branches   — Recently updated branches
```

### Examples

```bash
# Quick status check (most common)
gh-quick.sh status

# Open PRs in familydiagram (default)
gh-quick.sh prs

# Open PRs in btcopilot
gh-quick.sh prs btcopilot

# Open issues
gh-quick.sh issues

# Issues in btcopilot
gh-quick.sh issues btcopilot

# Recent CI runs
gh-quick.sh ci

# Issues assigned to you
gh-quick.sh mine
```

### Output Examples

```
$ gh-quick.sh status
=== patrickkidd/familydiagram Status ===

Open PRs:
  5 PRs
    #98 Add project board sync script (T7)
    #88 Add Pattern Intelligence UI for LearnView
    ...

Open Issues:
  12 issues
    #101 T7-21: Build Personal app for iPhone simulator and TestFlight
    ...

$ gh-quick.sh prs btcopilot
[97] Fix CI: mock gemini_structured for Pass 3 review — patrickkidd-hurin (2026-03-05) 
[89] Add per-entity-type F1 breakdown to eval harness — patrickkidd-hurin (2026-03-04) 
...
```

### Why This Matters

**Before:** To check open PRs, you'd type:
```bash
gh pr list --repo patrickkidd/familydiagram --state open --limit 20 ...
```

**After:**
```bash
gh-quick.sh prs
```

- Sensible defaults (familydiagram repo, 20 items)
- Consistent output format
- Fast to type
- Easy to remember

---

**Added:** March 5, 2026

---

## gh-quick.sh — Quick GitHub Queries (NEW!)

Fast GitHub queries with sensible defaults. No more remembering complex `gh` flags.

**Default repo:** `patrickkidd/familydiagram`

### Usage

```bash
gh-quick.sh <command> [repo]

# Commands:
#   prs        — List open PRs
#   issues     — List open issues
#   mine       — Issues/PRs assigned to you
#   ci         — Recent CI runs
#   status     — Quick dashboard (PRs + issues count)
```

### Examples

```bash
# Quick status check (most common)
gh-quick.sh status

# Open PRs in familydiagram (default)
gh-quick.sh prs

# Open PRs in btcopilot
gh-quick.sh prs btcopilot

# Open issues
gh-quick.sh issues

# Issues in btcopilot
gh-quick.sh issues btcopilot

# Recent CI runs
gh-quick.sh ci

# Issues assigned to you
gh-quick.sh mine
```

### Output Examples

```
$ gh-quick.sh status
=== patrickkidd/familydiagram Status ===

Open PRs:
  5 PRs
    #98 Add project board sync script (T7)
    #88 Add Pattern Intelligence UI for LearnView
    ...

Open Issues:
  12 issues
    #101 T7-21: Build Personal app for iPhone simulator and TestFlight
    ...

$ gh-quick.sh prs btcopilot
[97] Fix CI: mock gemini_structured for Pass 3 review — patrickkidd-hurin (2026-03-05) 
[89] Add per-entity-type F1 breakdown to eval harness — patrickkidd-hurin (2026-03-04) 
...
```

### Why This Matters

**Before:** To check open PRs, you'd type:
```bash
gh pr list --repo patrickkidd/familydiagram --state open --limit 20 ...
```

**After:**
```bash
gh-quick.sh prs
```

- Sensible defaults (familydiagram repo, 20 items)
- Consistent output format
- Fast to type
- Easy to remember

**Added:** March 5, 2026
