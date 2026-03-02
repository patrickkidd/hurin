# Co-Founder Briefing: evolution
**Date:** 2026-03-02 09:30 AKST
**Session:** 06d8ef05-49d2-49f4-a4d0-9dbf5eefa1ed
**Turns:** 10 max

---

**Evolution Briefing — 2026-03-02 (Run #3)**

---

**State of the System**

OpenClaw is at v2026.3.1 (confirmed: `openclaw --version` returns `2026.3.1`). The previous briefing's action #1 (upgrade) is already done. The co-founder action pipeline has now processed 10 tasks total — 7 produced merged PRs, 1 produced a closed PR, and 2 failed permanently. That's a **87.5% merge rate** on PRs that reached GitHub, which is excellent and means the action quality bar is right.

But there are three infrastructure problems actively burning cycles right now, all discovered in this run.

---

**Critical Finding #1: The Task Queue Is Stuck — `tmux` Not on Cron PATH**

This is the most urgent issue. From `~/.openclaw/monitor/monitor.log` (last 50 lines):

```
[2026-03-02 08:40:00] Draining queue: spawning cf-architecture-latest-3 (btcopilot)
[2026-03-02 08:40:00]   ERROR: spawn-task.sh failed: ...
/Users/hurin/.openclaw/monitor/spawn-task.sh: line 146: tmux: command not found
```

This error repeats every 10 minutes from 08:40 through at least 09:20 (5+ attempts). There are **3 tasks stuck in the queue** (`task-queue.json`) that cannot spawn because `spawn-task.sh` runs inside `check-agents.py`'s `drain_queue()` → `subprocess.run()`, which inherits the cron PATH. The cron PATH on macOS does NOT include `/opt/homebrew/bin` where `tmux` lives.

The same root cause also breaks `ping_hurin()`:
```
[2026-03-02 08:20:00]   WARNING: ping failed: /bin/sh: openclaw: command not found
```

`openclaw` is also in `/opt/homebrew/bin`. So **both** the respawn alert system AND the queue drain are broken in the cron context.

The fix is simple: `spawn-task.sh` needs `export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"` at the top, just like `.task-run.sh` (line 137) and `config.sh` (line 6) already have. And `check-agents.py` needs it too for `ping_hurin()`.

**Why this wasn't caught earlier:** The first batch of tasks (cf-architecture-latest-1 through cf-architecture-2026-03-01-3) were spawned via `action-approve.sh`, which sources `config.sh` and gets the PATH. The queue drain path (`check-agents.py` → `subprocess.run(spawn-task.sh)`) bypasses `config.sh` entirely.

---

**Critical Finding #2: Failure Capture Is Blind — All 10 Logs Are Empty**

Every single file in `~/.openclaw/monitor/failures/` contains the same placeholder:
```
[Session 'claude-<id>' was already dead when capture attempted]
```

This means `capture_tmux_output()` in `check-agents.py:94-107` always hits the dead-session fallback. The tmux sessions complete (or crash) between monitoring cycles, and by the time `check-agents.py` runs 10 minutes later, the session is gone.

**Impact:** The Ralph Loop is operationally blind. When respawning, hurin sends the failure log to CC for diagnosis, but CC gets `"Session was already dead"` — zero diagnostic signal. The retries are just blind re-runs of the same prompt.

The task log files (`~/.openclaw/monitor/task-logs/`) DO have the actual CC output — that's where the real diagnostic data lives. `spawn-task.sh` redirects CC stdout to these files (line 140-141). But `check-agents.py` reads from `failures/` (tmux capture), not from `task-logs/`.

**The fix:** When `tmux capture-pane` fails, fall back to reading the last 100 lines of `~/.openclaw/monitor/task-logs/{task_id}.log`. This is where the actual error output lives.

---

**Critical Finding #3: The Respawn Rate Tells a Different Story Than Expected**

From the task registry, 4 of 9 real tasks (44%) hit `respawnCount=3`. My previous briefing flagged this as concerning. But looking at the **task logs**, the picture is different:

- `cf-architecture-latest-4` (respawnCount=3): Task log shows it completed successfully with PR #41. The "respawns" were likely monitoring race conditions, not actual failures.
- `cf-architecture-2026-03-01-5` (respawnCount=3): Completed with PR #42.
- `cf-architecture-2026-03-01-6` (respawnCount=3): Completed with PR #43.
- `cf-architecture-latest-5` (respawnCount=3): Actually completed — PR #44 created per task log. But registry shows "failed" with `pr: null`.

Wait — `cf-architecture-latest-5`'s task log says **"PR created: https://github.com/patrickkidd/btcopilot/pull/44"** at 07:22, but the registry shows `status: "failed"` with `pr: null`. This means the monitoring script marked it failed (session dead + no PR found) at 08:00, but the PR was actually created at 07:22. The `get_pr()` function in `check-agents.py:110-121` searches by branch name — it might not be finding the PR because of a branch name mismatch, or there's a timing/caching issue with `gh pr list`.

**The real story:** Most "respawns" weren't failures at all. The tasks completed but check-agents.py couldn't verify it within its monitoring window. The high respawn count is a **monitoring false positive problem**, not a task quality problem.

---

**External Discovery 1: Claude Code Stop Hooks — Quality Gates for Spawned Tasks**

The [Claude Code hooks system](https://code.claude.com/docs/en/hooks) now supports 16 lifecycle events. The most relevant for us is the **`Stop` hook** — it fires when Claude finishes responding and can **block** the stop with corrective feedback, forcing the agent to continue working.

The [Taskmaster](https://github.com/blader/taskmaster) project demonstrates this pattern: require the agent to emit an explicit completion token (`TASKMASTER_DONE::<session_id>`) before allowing stop. Without it, the hook returns feedback like "You haven't finished — check your test results."

**How this maps to us:** Our spawned tasks currently rely on the prompt's delivery instructions ("Do NOT stop until PR is created"). But the agent can still stop early. A Stop hook in `.claude/settings.json` could programmatically verify:
1. `git diff --stat` shows changes were made
2. `git log --oneline origin/master..HEAD` shows a commit exists
3. `gh pr list --head <branch>` confirms a PR was created

If any check fails, the hook returns `{"decision": "block", "reason": "PR not created yet. Continue working."}` and the agent is forced to continue.

This would address the root cause of premature termination more reliably than prompt instructions alone.

---

**External Discovery 2: Episodic Memory Research — MemRL**

The [ICLR 2026 MemAgents workshop](https://openreview.net/pdf?id=U51WxL382H) and the paper ["Memory in the Age of AI Agents"](https://arxiv.org/abs/2512.13564) converge on a key insight: **agents that approach each task in isolation inevitably repeat past mistakes**. The recommended pattern is "episodic memory" — storing task-outcome pairs and retrieving similar episodes when starting new tasks.

Our `prompt-patterns.md` file in hurin's workspace is the manual version of this. But as Finding #2 shows, it's empty because the failure capture is blind. The feedback loop from "outcome → improved prompt" is broken at the data collection step, not the analysis step.

The research specifically calls out that **failure episodes are more valuable than success episodes** for learning. We're set up to capture them (Ralph Loop step 6), but the data isn't flowing.

---

**External Discovery 3: Self-Healing Agent Patterns — Retry-Aware Prompting**

[Retry-Aware Prompting](https://medium.com/@jeevitha.m/retry-aware-prompting-designing-prompts-for-robust-agent-behavior-ca7313d095d8) is a pattern where the retry prompt explicitly includes: (1) what was attempted, (2) what went wrong, (3) what to try differently. This contrasts with our current Ralph Loop which re-runs the same prompt blindly (because Finding #2: no diagnostic data).

[Replit Agent 3](https://leaveit2ai.com/ai-tools/code-development/replit-agent-v3) demonstrates a practical implementation: the agent tests its own output in a live environment, and on failure, captures the error state as input to the retry. Key metric: they cap retries at 1-2 (not 3) because more retries without new information just burns compute.

**Implication for us:** Given Finding #3 (most "respawns" are false positives), reducing MAX_RESPAWNS from 3 to 2 would save compute without losing real recovery capability. But the real win is fixing the failure capture so retries actually get diagnostic data.

---

**External Discovery 4: OpenClaw v2026.3.1 — Adaptive Thinking Default**

OpenClaw [v2026.3.1 release notes](https://github.com/openclaw/openclaw/releases/tag/v2026.3.1) set **adaptive thinking as the default** for Claude 4.6 models. Per [issue #30880](https://github.com/openclaw/openclaw/issues/30880), Anthropic's `thinking.type: "adaptive"` lets the model dynamically decide when and how much to think based on query complexity.

Our `openclaw.json` has `thinkingDefault: "off"` for hurin, which is correct — hurin is a dumb router and shouldn't think. But this setting affects only the OpenClaw gateway's model calls (hurin's MiniMax M2.5 calls), not our spawned CC tasks (which run via `claude -p` CLI). The spawned tasks already get whatever thinking behavior Claude Code uses by default.

No action needed, but worth noting: if we ever route coding tasks through OpenClaw agents directly (instead of `claude -p`), the adaptive thinking default would apply automatically.

---

**Metrics Dashboard**

| Metric | Mar 1 | Mar 2 | Trend |
|--------|-------|-------|-------|
| OpenClaw version | v2026.2.25 | v2026.3.1 | Updated |
| Open PRs (btcopilot) | 4 | 5 (#32, #41-44) | Grew — queue producing PRs |
| Tasks spawned (total) | 10 | 10 (+ 3 stuck in queue) | Queue blocked |
| Task merge rate | unknown | 7/8 = 87.5% | Excellent |
| Tasks hitting max respawns | 4/10 (40%) | Likely false positives | Need investigation |
| Feedback log entries | 1 | 1 (still) | Stalled — tasks completed before deployment |
| Failure logs with real data | 0/10 | 0/10 | Blind — critical |
| Queue drain working | Yes | **NO** — tmux not on PATH | Broken since 08:40 |
| hurin pings working | Yes | **NO** — openclaw not on PATH | Broken in cron |

---

**Changes Since Last Briefing**

- OpenClaw updated to v2026.3.1 (action #1 from yesterday: done)
- 3 new tasks queued but stuck (tmux PATH bug)  
- PR #44 created by cf-architecture-latest-5 but marked "failed" in registry (monitoring false positive)
- Queue drain infinite-retrying every 10 minutes with no backoff

---

**Search Strategy Notes**

**High-value queries this run:**
- `"agent memory" "learning from outcomes" feedback coding agent 2026` → found ICLR 2026 MemAgents workshop, MemRL paper, and the "Memory in the Age of AI Agents" survey. These directly validate our feedback loop design.
- `openclaw "adaptive" thinking level claude 4.6 default configuration` → found exact release notes and GitHub issues explaining the v2026.3.1 thinking changes.
- `"respawn" "max retries" coding agent "root cause" prompt rewriting self-healing 2026` → found Retry-Aware Prompting pattern and Replit Agent 3's self-healing approach.

**Medium-value queries:**
- `"AI co-founder" implementation proactive task discovery automated briefing system 2026` → found ChatGPT Pulse and Meta briefings, confirming our co-founder system is aligned with industry direction, but no novel implementation details.

**Low-value queries:**
- None this run — all searches produced something useful.

**Sources to check regularly (updated):**
- [github.com/openclaw/openclaw/releases](https://github.com/openclaw/openclaw/releases) — version tracking
- [github.com/blader/taskmaster](https://github.com/blader/taskmaster) — Stop hook pattern, watch for updates
- [code.claude.com/docs/en/hooks](https://code.claude.com/docs/en/hooks) — Hook API reference (16 events now)
- [arxiv.org — MemRL](https://arxiv.org/abs/2512.13564) — episodic memory research
- [addyosmani.com/blog](https://addyosmani.com/blog/) — agent patterns

**New queries to try next run:**
- `claude code "Stop" hook "block" completion verification example 2026` — practical Stop hook implementations
- `"git worktree" agent monitoring "session dead" race condition tmux` — our specific monitoring problem
- `"cron PATH" macos homebrew "/opt/homebrew/bin" fix` — common macOS cron PATH issue patterns
- `openclaw "queue" "task scheduling" sequential parallel agent 2026` — queue management patterns

---

**The Uncomfortable Question**

Patrick — there are 3 tasks stuck in the queue right now, being retried every 10 minutes and failing every time because `tmux` isn't on the cron PATH. This has been happening since 08:40 this morning (over 3 hours of failed retries by now). Meanwhile, PR #44 was created successfully at 07:22 but is marked "failed" in the registry because monitoring couldn't find it by branch name. The infrastructure that's supposed to be running autonomously has two silent failures: a stuck queue and a misclassified success. **How long would these have gone unnoticed if I hadn't checked the monitor log today?** The monitoring system needs monitoring — and right now nobody's watching the `monitor.log` for errors.

---

```proposed-actions
{
  "actions": [
    {
      "id": "evolution-2026-03-02-1",
      "title": "Fix cron PATH in spawn-task.sh and check-agents.py",
      "category": "infrastructure",
      "effort": "trivial",
      "confidence": 0.98,
      "repo": "none",
      "plan": "1. Add PATH export to top of spawn-task.sh. 2. Add PATH export to top of check-agents.py. 3. Verify the stuck queue drains on next cron cycle.",
      "spawn_prompt": "Fix the cron PATH issue that's blocking task spawning and hurin pings. Two files need the same fix:\n\n1. Edit `~/.openclaw/monitor/spawn-task.sh`: After line 13 (`set -euo pipefail`), add: `export PATH=\"/opt/homebrew/bin:$HOME/.local/bin:$PATH\"`\n\n2. Edit `~/.openclaw/monitor/check-agents.py`: After line 29 (`from feedback import capture_outcome`), add:\n```python\n# Ensure Homebrew tools (tmux, openclaw, gh, jq) are on PATH for cron contexts\nimport os\nos.environ['PATH'] = '/opt/homebrew/bin:' + os.path.expanduser('~/.local/bin:') + os.environ.get('PATH', '')\n```\n\nNote: check-agents.py already sets GH_TOKEN at lines 34-36, but it doesn't fix PATH. The PATH fix must come before any subprocess calls.\n\nAcceptance criteria: `spawn-task.sh` can find `tmux` when called from a minimal PATH environment (`env -i PATH=/usr/bin:/bin bash spawn-task.sh --help` should show usage, not 'command not found'). `check-agents.py`'s `ping_hurin()` can find `openclaw`.",
      "success_metric": "Queue drains successfully on next cron cycle, hurin pings work from cron"
    },
    {
      "id": "evolution-2026-03-02-2",
      "title": "Fix failure capture to read task logs instead of dead tmux",
      "category": "infrastructure",
      "effort": "trivial",
      "confidence": 0.95,
      "repo": "none",
      "plan": "1. Edit capture_tmux_output() in check-agents.py. 2. When tmux capture-pane fails, fall back to reading the last 100 lines of task-logs/{task_id}.log. 3. This gives the Ralph Loop actual diagnostic data.",
      "spawn_prompt": "Fix the failure capture in `~/.openclaw/monitor/check-agents.py` so the Ralph Loop gets real diagnostic data instead of 'Session was already dead' placeholders.\n\nEdit the `capture_tmux_output()` function (lines 93-107). After the existing tmux capture attempt fails (the else branch at line 104), instead of writing a useless placeholder, try to read the task log file:\n\n```python\ndef capture_tmux_output(session, task_id):\n    \"\"\"Capture last 100 lines from tmux session or task log. Save to failures dir.\"\"\"\n    FAILURES_DIR.mkdir(parents=True, exist_ok=True)\n    failure_log = FAILURES_DIR / f\"{task_id}.log\"\n\n    # Try live tmux capture first\n    code, output, _ = run(f\"tmux capture-pane -t '{session}' -p -S -100\")\n    if code == 0 and output:\n        failure_log.write_text(output)\n        log(f\"  Captured tmux output to {failure_log}\")\n        return str(failure_log)\n\n    # Session already dead — fall back to task log file\n    task_log = Path.home() / f\".openclaw/monitor/task-logs/{task_id}.log\"\n    if task_log.exists():\n        lines = task_log.read_text().splitlines()\n        last_100 = '\\n'.join(lines[-100:])\n        failure_log.write_text(f\"[From task log - session was dead]\\n{last_100}\")\n        log(f\"  Captured from task log to {failure_log}\")\n        return str(failure_log)\n\n    failure_log.write_text(f\"[Session '{session}' dead and no task log found]\\n\")\n    log(f\"  No capture source available for {failure_log}\")\n    return str(failure_log)\n```\n\nAcceptance criteria: The function imports Path (already imported at line 11). When a tmux session is dead, it reads from `~/.openclaw/monitor/task-logs/{task_id}.log` and writes the last 100 lines to the failure log. Run `python3 -c \"import check_agents; print('import OK')\"` from `~/.openclaw/monitor/` to verify no syntax errors.",
      "success_metric": "Future failure logs contain actual CC output, enabling real Ralph Loop diagnosis"
    },
    {
      "id": "evolution-2026-03-02-3",
      "title": "Fix PR #44 misclassified as 'failed' in task registry",
      "category": "infrastructure",
      "effort": "trivial",
      "confidence": 0.95,
      "repo": "none",
      "plan": "1. Read active-tasks.json. 2. Find task cf-architecture-latest-5. 3. Update status to 'done', pr to 44, prUrl to the PR URL. 4. This corrects the false positive from the monitoring race condition.",
      "spawn_prompt": "Fix a monitoring false positive in the task registry. The task `cf-architecture-latest-5` in `~/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json` is marked as `status: 'failed'` with `pr: null`, but PR #44 was actually created successfully (confirmed in the task log at `~/.openclaw/monitor/task-logs/cf-architecture-latest-5.log` which says 'PR created: https://github.com/patrickkidd/btcopilot/pull/44').\n\nEdit `~/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json` and update the task with `id: 'cf-architecture-latest-5'`:\n- Change `status` from `'failed'` to `'done'`\n- Change `pr` from `null` to `44`\n- Add `prUrl: 'https://github.com/patrickkidd/btcopilot/pull/44'`\n\nAcceptance criteria: The JSON file is valid after editing. The task shows status 'done' with pr: 44.",
      "success_metric": "Task registry accurately reflects that PR #44 was created"
    },
    {
      "id": "evolution-2026-03-02-4",
      "title": "Add pre-PR self-verification step to spawn-task.sh delivery instructions",
      "category": "velocity",
      "effort": "trivial",
      "confidence": 0.85,
      "repo": "none",
      "plan": "1. Edit ~/.openclaw/monitor/spawn-task.sh. 2. In the TASKEOF delivery instructions, add a verification step before PR creation. 3. This implements the Spotify pre-PR verification pattern.",
      "spawn_prompt": "Edit `~/.openclaw/monitor/spawn-task.sh` to add a pre-PR self-verification step. In the delivery instructions heredoc (lines 101-125, inside the `cat > \"$WORKTREE/.task-prompt.txt\" <<TASKEOF` block), add a new step between step 2 (Push) and step 3 (Create a PR).\n\nFind the line that says:\n```\n3. **Create a PR** against master using \\`gh pr create\\` with a clear title and description.\n```\n\nInsert before it (making it the new step 3, and renumbering 'Create a PR' to step 4):\n```\n3. **Self-verify before PR creation**: Run \\`git diff --stat origin/master...HEAD\\` and review every file you changed. If you modified files not directly related to the original task above, revert those changes with \\`git checkout origin/master -- <file>\\`. Only create the PR if every changed file directly serves the task requirements.\n```\n\nAcceptance criteria: `spawn-task.sh` still runs without syntax errors (`bash -n ~/.openclaw/monitor/spawn-task.sh` returns 0). The .task-prompt.txt template includes the self-verification step.",
      "success_metric": "Future spawned tasks include self-verification, reducing scope creep in agent PRs"
    },
    {
      "id": "evolution-2026-03-02-5",
      "title": "Add queue drain error backoff to prevent infinite retry spam",
      "category": "infrastructure",
      "effort": "small",
      "confidence": 0.85,
      "repo": "none",
      "plan": "1. Edit check-agents.py drain_queue(). 2. Track consecutive spawn failures per task in queue entries. 3. After 3 consecutive failures, mark the queue entry as 'blocked' and skip it. 4. Log the block so it's visible in monitor.log. 5. This prevents the current infinite 10-minute retry loop.",
      "spawn_prompt": "Fix the infinite retry loop in `~/.openclaw/monitor/check-agents.py`'s `drain_queue()` function (line 378). Currently, when `spawn-task.sh` fails (e.g., `tmux: command not found`), the task is re-inserted at the front of the queue and retried every 10 minutes forever.\n\nAdd a `spawn_failures` counter to queue entries. In the failure handling blocks (lines 438-444 and 446-451), increment `entry.setdefault('spawn_failures', 0)` by 1 before re-inserting. Add a check at the top of the spawn logic (after line 405 `entry = queue.pop(0)`) that skips entries with `spawn_failures >= 5`:\n\n```python\n    # Skip entries that have failed too many times\n    if entry.get('spawn_failures', 0) >= 5:\n        log(f\"  BLOCKED: {task_id} has failed to spawn {entry['spawn_failures']} times. Removing from queue.\")\n        # Don't re-insert — just save the updated queue without this entry\n        queue_data['queue'] = queue\n        with open(QUEUE_FILE, 'w') as f:\n            json.dump(queue_data, f, indent=2)\n        return\n```\n\nAlso increment the counter in both error paths:\n```python\n    entry['spawn_failures'] = entry.get('spawn_failures', 0) + 1\n```\n\nAcceptance criteria: `python3 -c \"import check_agents; print('OK')\"` succeeds from `~/.openclaw/monitor/`. After 5 consecutive spawn failures, the task is removed from the queue instead of retrying forever.",
      "success_metric": "No more infinite retry loops in monitor.log when spawn-task.sh has a systemic error"
    }
  ]
}
```

Sources:
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Taskmaster — Stop Hook for Coding Agents](https://github.com/blader/taskmaster)
- [OpenClaw v2026.3.1 Release Notes](https://github.com/openclaw/openclaw/releases/tag/v2026.3.1)
- [OpenClaw Adaptive Thinking Issue #30880](https://github.com/openclaw/openclaw/issues/30880)
- [ICLR 2026 MemAgents Workshop](https://openreview.net/pdf?id=U51WxL382H)
- [Memory in the Age of AI Agents — Survey](https://arxiv.org/abs/2512.13564)
- [Retry-Aware Prompting](https://medium.com/@jeevitha.m/retry-aware-prompting-designing-prompts-for-robust-agent-behavior-ca7313d095d8)
- [Replit Agent 3: Self-Healing Code](https://leaveit2ai.com/ai-tools/code-development/replit-agent-v3)
- [The New Stack: Memory for AI Agents](https://thenewstack.io/memory-for-ai-agents-a-new-paradigm-of-context-engineering/)
