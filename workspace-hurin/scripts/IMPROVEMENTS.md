# Workflow Automation Improvements — February 27, 2026

## Problem Identified

The workflow scripts (`spawn-task.sh`, `tasks.sh`) existed in `~/.openclaw/monitor/` but had critical issues preventing reliable use:

1. **Scripts were undiscoverable** — Not in workspace scripts directory alongside gh-project tools
2. **Hardcoded broken path** — `tasks.sh` had `REGISTRY="$HOME/Projects/theapp/..."` (wrong location)
3. **Missing documentation** — No guide on how to use the complete workflow
4. **Not in PATH** — TOOLS.md referenced these as simple commands, but they required full paths
5. **Missing convenience wrapper** — No easy entry point for the most common task workflow

## Improvements Made

### 1. Fixed and Relocated Core Scripts ✓

- **spawn-task.sh**: Copied to `~/.openclaw/workspace-hurin/scripts/`, added DEV_REPO environment variable support for flexibility
- **tasks.sh**: Copied to `~/.openclaw/workspace-hurin/scripts/`, fixed hardcoded registry path, now uses environment variable

Both scripts now use:
```bash
DEV_REPO="${DEV_REPO:-$HOME/.openclaw/workspace-hurin/theapp}"
REGISTRY="$DEV_REPO/.clawdbot/active-tasks.json"
```

This allows overriding the repo location if needed, and points to the correct registry.

### 2. Created Comprehensive Documentation ✓

**README.md** — Complete guide covering:
- Quick reference table for all scripts
- Detailed usage examples for each command
- Typical workflow walkthrough (find issue → spawn task → monitor → PR created)
- Troubleshooting guide
- System flow diagram
- Environment variable reference

### 3. Built Convenience Wrapper ✓

**task** — New unified script providing shorter syntax:

```bash
# Before (spawn-task.sh)
spawn-task.sh --repo familydiagram --task T7-4 --description "..." <<PROMPT
...
PROMPT

# After (task wrapper)
task spawn familydiagram T7-4 "..." <<PROMPT
...
PROMPT
```

The wrapper provides:
- Simpler command syntax
- Helpful error checking
- Built-in help
- Consistent interface with tasks.sh commands

Example:
```bash
task spawn familydiagram T7-4 'Build diagram button' <<'PROMPT'
Implement the button...
PROMPT

task status        # View all
task watch T7-4    # Live view
task list          # Names only
```

## Why This Matters

**Before:**
- Patrick had to remember full paths to scripts in ~/.openclaw/monitor/
- `tasks.sh` would fail silently because registry path was wrong
- No documented workflow for the complete spawn → monitor → review cycle
- Easy to make mistakes in complex command syntax

**After:**
- All automation scripts are co-located with gh-project tools
- Paths are correct and environment-configurable
- Clear, documented workflow with examples
- Simpler syntax reduces user error
- One unified entry point (`task`) for the most common operations

## Testing

✓ spawn-task.sh: Verified it creates worktree, registers task, spawns tmux session  
✓ tasks.sh: Verified it reads correct registry path, shows task status  
✓ task wrapper: Verified all commands (spawn, status, watch, list, help)  
✓ Registry path fix: Confirmed scripts now find `.clawdbot/active-tasks.json` correctly  
✓ README: Tested example commands and workflow

## Files Changed

- **Created/Updated:**
  - `~/.openclaw/workspace-hurin/scripts/spawn-task.sh` (fixed + relocated)
  - `~/.openclaw/workspace-hurin/scripts/tasks.sh` (fixed + relocated)
  - `~/.openclaw/workspace-hurin/scripts/task` (new wrapper)
  - `~/.openclaw/workspace-hurin/scripts/README.md` (new comprehensive guide)
  - `~/.openclaw/workspace-hurin/scripts/IMPROVEMENTS.md` (this file)

- **Not modified:**
  - `~/.openclaw/monitor/spawn-task.sh` (original still there for backward compat)
  - `~/.openclaw/monitor/tasks.sh` (original still there for backward compat)

## How to Use

### Quick reference:
```bash
cd ~/.openclaw/workspace-hurin/scripts

# Show all available scripts
ls -la

# Read the complete guide
cat README.md

# Use the convenience wrapper for fastest workflow
./task spawn familydiagram T7-4 "description" <<PROMPT
your prompt here
PROMPT

./task status   # Check all tasks
./task watch T7-4  # Watch specific task
```

### For direct calls to lower-level scripts:
```bash
./spawn-task.sh --repo familydiagram --task T7-4 --description "..." <<PROMPT
...
PROMPT

./tasks.sh        # Dashboard
./tasks.sh T7-4   # Specific task
./tasks.sh -l     # List only
```

---

**Created:** Feb 27, 2026, 9:00 AM  
**Duration:** ~20 minutes of audit + implementation + testing  
**Zero-cost improvement:** Uses existing scripts, no new dependencies
