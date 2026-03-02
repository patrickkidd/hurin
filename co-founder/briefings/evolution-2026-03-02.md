# Co-Founder Briefing: evolution
**Date:** 2026-03-02 09:05 AKST
**Session:** dcb2d738-55f4-435a-ae63-319946477bef
**Turns:** 10 max

---

Here's today's evolution briefing.

---

**Evolution Briefing — 2026-03-02**

**System State Snapshot**

- OpenClaw version: v2026.2.25 (latest: v2026.3.1, released today)
- Task registry: 10 tasks total — 8 done, 2 failed
- Feedback log: 1 entry (only failed task T999)
- Open btcopilot PRs: 4 (#44 today, #32 stale since Feb 26, #16 since Feb 17, #10 since Dec 8)
- Co-founder action pipeline: 8/10 tasks completed → PRs #36-#43 created. That's a real production line.
- Agent swarm gap #8 (proactive task discovery) still unaddressed

---

**Domain 1: Agent Architecture Patterns**

**Discovery 1: Claude Code Agent Teams (native, experimental)**

This is the biggest external development relevant to our system. Anthropic shipped native multi-agent coordination as an experimental feature in Claude Code: [Agent Teams documentation](https://code.claude.com/docs/en/agent-teams).

Key capabilities:
- **Shared task list** with dependency tracking — tasks can block other tasks, and when a blocking task completes, downstream tasks auto-unblock
- **Inter-agent messaging** — teammates message each other directly via a mailbox system, not just reporting back to the lead
- **Task self-claiming** with file locking to prevent race conditions
- **Split-pane tmux display** where each teammate gets its own pane
- **Quality gate hooks**: `TeammateIdle` and `TaskCompleted` hooks that can send feedback to keep agents working or prevent premature task completion

How this compares to our `spawn-task.sh` architecture:

| Feature | Our system | Agent Teams |
|---------|-----------|-------------|
| Task isolation | git worktrees (robust) | Same context, own window |
| Monitoring | check-agents.py cron (10 min) | Lead agent watches directly |
| Failure recovery | Ralph Loop (capture → diagnose → rewrite → respawn) | Manual: "spawn a replacement" |
| Outcome tracking | feedback.py JSONL | None |
| PR creation | Automated via delivery instructions | Up to lead coordination |
| Session persistence | Survives lead death (tmux) | Lost if lead dies |

**Assessment**: Our custom infrastructure is actually more robust for production use — especially the Ralph Loop, persistent task registry, and automated code review. But the Agent Teams concept of **dependency-tracked task lists** and **inter-agent messaging** are features we lack. The quality gate hooks (`TeammateIdle`, `TaskCompleted`) are particularly interesting — they let you enforce rules at task boundaries. Worth monitoring as it matures past experimental status.

**No action needed now** — our architecture is better for async, fire-and-forget tasks. But if Agent Teams stabilizes, it could handle intra-session coordination (like "implement feature X by having one agent do backend, one do frontend, one do tests") more elegantly than our spawn-per-task model.

**Discovery 2: Composio Agent Orchestrator**

[github.com/ComposioHQ/agent-orchestrator](https://github.com/ComposioHQ/agent-orchestrator) — a mature open-source tool (61 merged PRs, 3,288 tests) with a plugin architecture:

```yaml
reactions:
  ci-failed:
    auto: true
    action: send-to-agent
    retries: 2
```

Their "reactions" system is declarative configuration for what happens on CI failure, review feedback, or PR approval. Our `check-agents.py` handles the same scenarios, but in imperative Python. The declarative approach is cleaner for adding new reaction types.

Concrete takeaway: their `ao session restore <session>` for reviving crashed agents is worth looking at — our Ralph Loop captures the failure log but always starts a fresh session. A restore-from-checkpoint approach could preserve the agent's in-progress work rather than starting from scratch.

**Discovery 3: Self-Improving Agents — The "Ralph Wiggum" Pattern**

Addy Osmani wrote a comprehensive guide on [self-improving coding agents](https://addyosmani.com/blog/self-improving-agents/) that closely mirrors our Ralph Loop. The pattern is named "Ralph" (not after Ralph Wiggum, ironically) and describes:

1. Pick task from JSON list → implement → validate → commit → update status → reset context → repeat
2. Four channels of memory: git history, progress.txt, task state JSON, and an AGENTS.md knowledge base
3. **Compound learning**: each failure generates AGENTS.md entries that prevent identical mistakes

This is exactly what our Ralph Loop + `prompt-patterns.md` + `feedback.py` is designed to do. But there's a gap: **our feedback loop isn't closing**. The feedback log has exactly 1 entry (the T999 test failure). The 8 successful tasks that produced PRs #36-#43 apparently completed without `capture_outcome()` being called, OR the capture happened but the outcome was only for done tasks and the log shows only the failed one.

Looking at `check-agents.py:312-316`, `capture_outcome(task)` IS called when tasks transition to "done". But only 1 entry in the log suggests either: (a) most tasks were cleaned up before the feedback system was deployed, or (b) there's a bug in the path resolution. This needs investigation.

The Addy Osmani pattern adds something we don't have: **a progress.txt file per task** that the agent reads on restart, so if a task is respawned, the agent knows what was already attempted. Currently our Ralph Loop captures the failure log and rewrites the prompt, but the respawned agent has no memory of the previous attempt beyond what's in the rewritten prompt.

**Discovery 4: Spotify's Two-Layer Verification**

[Spotify's background coding agents](https://engineering.atspotify.com/2025/12/feedback-loops-background-coding-agents-part-3/) use a pre-PR verification architecture:

- **Layer 1**: Deterministic verifiers (build, test, lint) triggered automatically based on file types
- **Layer 2**: LLM-as-judge that compares the diff against the original prompt to catch scope creep

Key stat: **"the judge vetoes about a quarter of [agent] PRs"** and "the agent is able to course correct half the time." The most common rejection trigger is **"the agent going outside the instructions outlined in the prompt."**

This maps to a real problem we've seen — agents that wander off-task or make unnecessary changes. Our `review-prs.sh` catches these AFTER PR creation, but Spotify's approach catches them BEFORE. The difference matters: a PR with review comments requires manual intervention, while a pre-PR veto lets the agent self-correct.

**Concrete implication**: We could add a "stop hook" or post-implementation verification step to `spawn-task.sh` that runs before the PR is created. The delivery instructions in `.task-prompt.txt` already have a "create PR" step — we could insert a "verify your changes match the original prompt before creating the PR" step before it.

---

**Domain 2: OpenClaw Ecosystem**

**Discovery 5: We're 2 releases behind (v2026.2.25 → v2026.3.1)**

Checking the [OpenClaw releases](https://github.com/openclaw/openclaw/releases):

**v2026.2.26** (Feb 27):
- Fixes for thread binding lifecycle (we use `threadBindings: { enabled: true }`)
- Gateway error handling for early closure scenarios

**v2026.3.1** (Mar 2 — today):
- **"Prevent stuck typing indicators by sealing channel typing keepalive callbacks after idle/cleanup"** — this directly affects our Discord UX when CC calls take several minutes
- Embed handling improvements for message parsing
- Lightweight bootstrap mode for automation runs
- Thread binding lifecycle now uses inactivity-based TTL instead of fixed TTL

The stuck typing indicator fix is relevant — if hurin's CC calls take >2 minutes (common), the typing indicator may have been getting stuck in v2026.2.25. And the lightweight bootstrap mode for automation could reduce overhead for our co-founder cron runs.

**Discovery 6: Cheap-First Heartbeat Pattern**

The [cheap checks first](https://dev.to/damogallagher/heartbeats-in-openclaw-cheap-checks-first-models-only-when-you-need-them-4bfi) pattern formalizes what our `check-agents.py` already does partially:

- **Stage 1 (free)**: Run shell commands to check state (tmux alive? PR exists? CI status?)
- **Stage 2 (conditional)**: Only invoke the LLM when there's an actual alert

Our `check-agents.py` does Stage 1 perfectly. Stage 2 (pinging hurin → CC) only triggers on failures. The article suggests this can be formalized via OpenClaw's native heartbeat system with HEARTBEAT.md — but our cron-based approach is working fine and gives us more control.

**Discovery 7: OpenClaw Native Heartbeat vs Our Cron**

Our HEARTBEAT.md is empty (`hurin is event-driven via check-agents.py pings`). The ecosystem shows a trend toward using OpenClaw's native heartbeat for proactive monitoring. But for our use case — 10-minute check intervals with Python logic for task state management — external cron is the right choice. The native heartbeat is better for simpler "check if anything needs attention" use cases.

One thing worth noting: OpenClaw's `bootstrap mode` (v2026.3.1) could reduce overhead for co-founder runs by "keeping only HEARTBEAT.md for heartbeat runs." We're already running co-founder as external cron → `claude -p`, so this is N/A for us.

---

**Domain 3: AI Co-Founder / CTO Patterns**

**Discovery 8: Proactive Task Discovery — The Remaining Gap**

Our ADR-0001-status.md lists proactive task discovery as the only remaining GAP (item #8). Multiple patterns emerged from the ecosystem:

From [OpenClaw proactive AI patterns](https://www.aifire.co/p/5-best-openclaw-use-cases-for-2026-proactive-ai-guide):
- **Night shift work**: autonomous coding sessions that "open pull requests for review" during off hours
- **Task API integration**: monitoring task managers to distinguish human-assigned vs self-identified work
- **Independent prioritization**: agent identifies improvement candidates and stages PRs

From our own architecture, the infrastructure already exists:
- `check-agents.py` can scan for new GitHub issues and stale PRs
- `spawn-task.sh` can fire off implementation tasks
- The co-founder pipeline already produces structured actions with spawn prompts
- `drain_queue()` already handles sequential task spawning

The missing piece is a **scanner that converts signals into queued tasks**. Signals:
1. GitHub issues labeled `cf-approved` without `cf-spawned`
2. Failing tests on master (could auto-file bug fixes)
3. Open PRs with review comments that haven't been addressed
4. TODO comments in code that match open issues

This would close the gap between "co-founder proposes action" and "action gets spawned automatically after approval."

**Discovery 9: Memory Architecture — Mem0 and Cross-Session Context**

The [memory landscape for AI agents](https://thenewstack.io/memory-for-ai-agents-a-new-paradigm-of-context-engineering/) has matured significantly. [Mem0](https://techcrunch.com/2025/10/28/mem0-raises-24m-from-yc-peak-xv-and-basis-set-to-build-the-memory-layer-for-ai-apps/) (raised $24M) provides a dedicated memory layer that extracts "memories" from interactions, stores them, and retrieves them for personalization.

Our journal.md + CLAUDE.md + prompt-patterns.md system is a manual version of this. The journal provides recency (last 150 lines), CLAUDE.md provides stable project knowledge, and prompt-patterns.md captures failure/fix patterns.

The interesting development from [Reload/Epic](https://techcrunch.com/2026/02/19/reload-an-ai-employee-agent-management-platform-raises-2-275m-and-launches-an-ai-employee/) is **shared project-level context across agents and sessions** — a centralized memory that all agents in a team can read and write to. Our agents share context via CLAUDE.md files and the monorepo, but they don't have a shared "what we learned in the last 24 hours" artifact that persists across spawn-task.sh sessions.

**Discovery 10: The Anthropic Agentic Coding Trends Report**

Anthropic published their [2026 Agentic Coding Trends Report](https://resources.anthropic.com/2026-agentic-coding-trends-report) with 8 key trends. Most relevant to us:

- **Trend 2: Multi-agent systems replace single-agent workflows** — "an orchestrator delegates subtasks to specialized agents working simultaneously — then stitches everything together." We're already doing this.
- **Task horizons expand from minutes to days or weeks** — agents moving beyond one-off fixes to full systems. Our spawn-task.sh handles multi-hour sessions; the max-turns limit of 25 is the practical boundary.
- Developers use AI in 60% of work but fully delegate only 0-20% — which matches our experience. The co-founder actions that work are trivial mechanical fixes; the complex stuff still needs Patrick.

---

**Feedback Loop Gap Analysis — The Critical Missing Piece**

This is the finding I didn't expect. Our system captures feedback (`feedback.py`) but has **only 1 entry** in the log despite 8 completed tasks. And even if the log were full, nothing reads it to improve future behavior.

The self-improvement loop should be:

```
spawn task → agent works → outcome captured → patterns analyzed → next prompt improved
```

Currently we have:
```
spawn task → agent works → outcome captured (maybe) → [dead end]
```

The `prompt-patterns.md` file in hurin's workspace is supposed to close this loop (Ralph Loop step 6: "log the failure+fix pattern"), but it only captures failure patterns, not success patterns. We're learning from mistakes but not from successes.

Spotify found that the most valuable learning signal is **"the agent going outside the instructions"** — scope creep. We should track: what did the prompt ask for vs. what did the PR actually change? The `feedback.py` already captures `description` and `files_changed` — adding the original prompt text would enable a "prompt fidelity" analysis.

---

**Changes Since Last Review**

| Metric | Mar 1 | Mar 2 | Trend |
|--------|-------|-------|-------|
| OpenClaw version | v2026.2.25 | v2026.2.25 (v2026.3.1 available) | Behind |
| Open PRs (btcopilot) | 6 | 4 | Improved — stale PRs #34, #36 closed (per co-founder action) |
| Task registry | unknown | 10 tasks (8 done, 2 failed) | Active pipeline |
| Feedback log entries | 0 | 1 | Growing (slowly) |
| Co-founder actions spawned | ~6 | 8+ (PRs #36-#43) | Productive |
| Agent architecture gap #8 | Open | Still open | No progress |

The co-founder action pipeline is working. 8 tasks spawned, PRs created for most. The pipeline from "briefing proposes action → Patrick approves → agent spawns → PR lands" is operational. But the feedback loop from "PR outcome → improve next spawn" is not yet closing.

---

**Search Strategy Notes**

**High-value queries:**
- `"agent orchestration" "task queue" coding agents worktree tmux Claude 2026` → found Composio, ccswarm, Overstory, and Claude Code Agent Teams
- `openclaw github releases changelog 2026 march` → found exact version info and changelogs
- `"agent feedback loop" "outcome tracking" "prompt improvement" coding agent 2026` → found Addy Osmani and Spotify articles

**Low-value queries:**
- `"AI CTO" "AI co-founder" proactive task discovery` → mostly marketing/prediction content, not implementations
- `"openclaw AI agent gateway configuration 2026"` → generic guides, not useful for someone already running OpenClaw

**Sources to check regularly:**
- [github.com/openclaw/openclaw/releases](https://github.com/openclaw/openclaw/releases) — version tracking
- [code.claude.com/docs/en/agent-teams](https://code.claude.com/docs/en/agent-teams) — watch for experimental → stable
- [addyosmani.com/blog](https://addyosmani.com/blog/) — solid technical content on agent patterns
- [engineering.atspotify.com](https://engineering.atspotify.com/) — real production agent experience
- [github.com/ComposioHQ/agent-orchestrator](https://github.com/ComposioHQ/agent-orchestrator) — similar architecture, watch for new features

**New queries to try next time:**
- `claude code "stop hook" pre-commit verification agent` — Spotify's pre-PR verification
- `"agent memory" "learning from outcomes" JSONL feedback coding` — closing the feedback loop
- `openclaw v2026.3 migration breaking changes` — if we update
- `"git worktree" agent "merge conflict" resolution automated` — a pattern we'll need as task parallelism grows

---

**One Uncomfortable Question**

Patrick — the co-founder system has now spawned 8+ tasks that created PRs #36-#43. But of those PRs, how many has Patrick actually reviewed and merged? The open PR list shows #44 (today), #32 (stale 5 days), #16 (13 days), #10 (84 days). PRs #36-#43 aren't in the open list, which means they were either merged or closed.

If they were merged without review: that's a governance gap — the whole point of "agents create PRs, Patrick merges" is human oversight. If they were closed without merging: that's 8 wasted agent sessions.

**What's the merge rate on co-founder-spawned PRs?** This is the highest-signal metric for whether the action pipeline is delivering value or creating noise. If Patrick is merging most of them, we should spawn more aggressively. If Patrick is closing most of them, the action quality bar needs to go up. Right now we have no data on this — and the feedback log with its 1 entry can't tell us.

---

```proposed-actions
{
  "actions": [
    {
      "id": "evolution-2026-03-02-1",
      "title": "Update OpenClaw to v2026.3.1",
      "category": "infrastructure",
      "effort": "trivial",
      "confidence": 0.90,
      "repo": "none",
      "plan": "1. Run openclaw gateway stop. 2. Run brew upgrade openclaw (or the appropriate update command). 3. Run openclaw gateway start. 4. Verify with openclaw doctor. 5. Test Discord connectivity with openclaw channels status --probe.",
      "spawn_prompt": "Update OpenClaw from v2026.2.25 to v2026.3.1. Steps: 1. Stop the gateway: `openclaw gateway stop`. 2. Update: check if installed via brew (`brew list openclaw`) — if so, `brew upgrade openclaw`. If installed via npm, `npm update -g openclaw`. If neither, check `which openclaw` and report the install method. 3. Start the gateway: `openclaw gateway start`. 4. Verify: `openclaw --version` should show 2026.3.1. 5. Run `openclaw doctor` and report results. 6. Run `openclaw channels status --probe` to verify Discord is connected. Acceptance criteria: openclaw --version shows 2026.3.1, gateway running, Discord connected.",
      "success_metric": "openclaw --version shows 2026.3.1, stuck typing indicators fixed"
    },
    {
      "id": "evolution-2026-03-02-2",
      "title": "Add pre-PR verification step to spawn-task.sh delivery instructions",
      "category": "velocity",
      "effort": "trivial",
      "confidence": 0.85,
      "repo": "none",
      "plan": "1. Edit ~/.openclaw/monitor/spawn-task.sh. 2. In the TASKEOF delivery instructions (line 101-125), add a step before 'Create a PR' that says: 'Before creating the PR, verify your changes match the original task. Run git diff --stat to see what you changed. If you modified files not directly related to the task, revert those changes. Only proceed to PR creation if all changes serve the original request.' 3. This implements Spotify's pre-PR verification pattern at zero cost.",
      "spawn_prompt": "Edit ~/.openclaw/monitor/spawn-task.sh to add a pre-PR self-verification step. In the delivery instructions block (the heredoc starting at line 101 with `cat > \"$WORKTREE/.task-prompt.txt\"`), add a new step between the existing steps. After the current numbered steps (Commit, Push), add a new step BEFORE 'Create a PR' that reads: '**Self-verify before PR creation**: Run `git diff --stat` and review every file you changed. If you modified files not directly related to the original task above, revert those changes with `git checkout -- <file>`. Only create the PR if every changed file directly serves the task requirements. This prevents scope creep.' Acceptance criteria: the .task-prompt.txt template now includes the verification step, spawn-task.sh still runs without errors.",
      "success_metric": "Future spawned tasks include self-verification, reducing scope creep in agent PRs"
    },
    {
      "id": "evolution-2026-03-02-3",
      "title": "Investigate and fix feedback.py capture gap",
      "category": "velocity",
      "effort": "small",
      "confidence": 0.80,
      "repo": "none",
      "plan": "1. Read feedback.py and check-agents.py. 2. The feedback log has only 1 entry (T999 failed) despite 8 completed tasks. 3. Investigate why capture_outcome() isn't being called for done tasks — check if the tasks completed before feedback.py was deployed, or if there's a path issue. 4. Verify the FEEDBACK_LOG path exists and is writable. 5. Add a test by manually running capture_outcome with a mock task dict.",
      "spawn_prompt": "Investigate why ~/.openclaw/workspace-hurin/feedback/log.jsonl has only 1 entry despite 8 tasks having status 'done' in ~/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json. Read both files. Check check-agents.py to see when capture_outcome() is called (it should be called at line 312-315 when task status transitions to 'done'). Possible causes: (1) tasks were marked done before feedback.py existed, (2) the import fails silently, (3) the FEEDBACK_LOG path is wrong. Test by running: `cd ~/.openclaw/monitor && python3 -c \"from feedback import capture_outcome; print('import OK')\"`. Then check if the feedback directory exists: `ls -la ~/.openclaw/workspace-hurin/feedback/`. Report findings and fix any issues found. Acceptance criteria: capture_outcome() successfully imports and writes to the log, next task completion will generate a feedback entry.",
      "success_metric": "Feedback log captures outcomes for all future task completions"
    },
    {
      "id": "evolution-2026-03-02-4",
      "title": "Add original prompt text to feedback.py outcome records",
      "category": "velocity",
      "effort": "trivial",
      "confidence": 0.90,
      "repo": "none",
      "plan": "1. Edit ~/.openclaw/monitor/feedback.py. 2. In capture_outcome(), read the original prompt from the task's worktree (.task-prompt.txt) if it still exists. 3. Add a 'prompt_excerpt' field (first 500 chars) to the outcome dict. 4. This enables future 'prompt fidelity' analysis — comparing what was asked vs what was changed.",
      "spawn_prompt": "Edit ~/.openclaw/monitor/feedback.py to capture the original prompt in outcome records. In the capture_outcome() function, after line 140 (pr_num = task.get('pr')), add logic to read the original prompt: `worktree = task.get('worktree', ''); prompt_excerpt = ''; prompt_path = Path(worktree) / '.task-prompt.txt' if worktree else None; if prompt_path and prompt_path.exists(): prompt_excerpt = prompt_path.read_text()[:500]`. Then add 'prompt_excerpt': prompt_excerpt to the outcome dict (around line 159). This enables future analysis of prompt fidelity — comparing what was asked vs what files were changed. Acceptance criteria: feedback.py still imports cleanly (`python3 -c 'from feedback import capture_outcome'`), and the outcome dict now includes prompt_excerpt field.",
      "success_metric": "Future feedback entries include prompt text, enabling prompt fidelity analysis"
    }
  ]
}
```

Sources:
- [Claude Code Agent Teams Documentation](https://code.claude.com/docs/en/agent-teams)
- [Composio Agent Orchestrator](https://github.com/ComposioHQ/agent-orchestrator)
- [OpenClaw Releases](https://github.com/openclaw/openclaw/releases)
- [OpenClaw v2026.3.1 Release](https://github.com/openclaw/openclaw/releases/tag/v2026.3.1)
- [Self-Improving Coding Agents — Addy Osmani](https://addyosmani.com/blog/self-improving-agents/)
- [Spotify: Feedback Loops for Background Coding Agents](https://engineering.atspotify.com/2025/12/feedback-loops-background-coding-agents-part-3)
- [Heartbeats in OpenClaw: Cheap Checks First](https://dev.to/damogallagher/heartbeats-in-openclaw-cheap-checks-first-models-only-when-you-need-them-4bfi)
- [Memory for AI Agents — The New Stack](https://thenewstack.io/memory-for-ai-agents-a-new-paradigm-of-context-engineering/)
- [OpenClaw Proactive AI Use Cases](https://www.aifire.co/p/5-best-openclaw-use-cases-for-2026-proactive-ai-guide)
- [Anthropic 2026 Agentic Coding Trends Report](https://resources.anthropic.com/2026-agentic-coding-trends-report)
- [Overstory Multi-Agent Orchestration](https://github.com/jayminwest/overstory)
- [ccswarm — Claude Code Multi-Agent](https://github.com/nwiizo/ccswarm)
- [OpenClaw Configuration Docs](https://docs.openclaw.ai/gateway/configuration)
- [OpenClaw Heartbeat Docs](https://docs.openclaw.ai/gateway/heartbeat)
