# TOOLS.md — Huor's Environment

## Machine

- **Hardware:** Linux VPS, 2GB RAM
- **OS:** Linux (Ubuntu)
- **Shell:** bash
- **Python:** Always use `uv` (never pip)

## Project Location

- **Monorepo:** `~/.openclaw/workspace-hurin/theapp/`
- **Backend:** `~/.openclaw/workspace-hurin/theapp/btcopilot/`
- **Frontend:** `~/.openclaw/workspace-hurin/theapp/familydiagram/`

## Two-Tier Architecture

- **Huor** (you) — MiniMax M2.5. Routes, monitors, reports. Handles read-only queries and system admin directly.
- **Claude Code** — Opus 4.6 via Agent SDK on Max plan — **$0 cost**. Handles planning, investigation, diagnosis, and implementation.

**All CC work uses Agent SDK scripts. Never `claude -p`.**

## Operating Modes

### Mode 1: Sync Query (`exec` + `cc-query.py`)

```bash
exec(command="uv run --directory ~/.openclaw/monitor python cc-query.py --description '<brief>' --source-url 'https://discord.com/channels/1474833522710548490/<channel_id>/<message_id>' <<'PROMPT'\n...\nPROMPT")
```

- Blocks turn, creates Discord thread in #tasks, $0 cost
- Optional: `--cwd /path/to/repo`, `--max-turns 10`

### Mode 2: Background Task (`task spawn`)

```bash
exec(command="task spawn <repo> <task-id> '<description>' <<'PROMPT'\n...\nPROMPT")
```

- Enqueues to daemon (30s pickup), creates worktree, $0 cost

### Monitoring

```bash
task status        # Dashboard from registry
task list          # List all tasks
task watch <id>    # Tail JSONL log
task kill <id>     # Kill stuck task
task follow-up <id> "message"  # Resume completed task session
```

### Synthesis

```bash
# Trigger on-demand synthesis
exec(command="nohup /bin/bash /home/hurin/.openclaw/team-lead/manual-synthesis.sh >> /home/hurin/.openclaw/team-lead/manual-run.log 2>&1 &")
```

## GitHub Project Board

- **Project:** Family Diagram #4 — https://github.com/users/patrickkidd/projects/4
- **Project ID:** `PVT_kwHOABjmWc4BP0PU`
- **Sync scripts:** `~/.openclaw/workspace-hurin/scripts/gh-project-sync.sh` and `gh-project-find-item.sh`
- **Rules:** See `PROJECT-BOARD-RULES.md`

## Discord Channels

- **#team-lead** — syntheses, metrics, anomaly alerts, conversation with Patrick
- **#tasks** — real-time task execution streaming, thread follow-ups

## Key Paths

| Path | Purpose |
|------|---------|
| `~/.openclaw/monitor/task-queue.json` | Task queue |
| `~/.openclaw/monitor/task-logs/<id>.log` | Task logs (JSONL) |
| `~/.openclaw/monitor/queue-prompts/` | Task prompts |
| `~/.openclaw/monitor/kill-sentinels/` | Kill sentinels |
| `~/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json` | Task registry |
| `~/.openclaw/team-lead/syntheses/` | Synthesis outputs |
| `~/.openclaw/team-lead/metrics-log.jsonl` | Metrics log |
| `~/.openclaw/monitor/daemon.log` | Task daemon log |

## Prompt Target Rule

- `prompts.py` in btcopilot is a PUBLIC STUB
- ALL prompt improvement PRs must target `fdserver/private_prompts.py`

## MVP Milestones

GitHub Milestones on the project board now map to short references:

| Milestone | Description |
|-----------|-------------|
| MVP 1: Extraction E2E | Single-prompt extraction, GT-validated F1 targets |
| MVP 2: Human Beta | Hand to real human tester |
| MVP 3: Pro Viewing | Personal app diagrams work in Pro app |
| MVP 4: SARF Accuracy | Exhaustive lit review for prompt improvement |
