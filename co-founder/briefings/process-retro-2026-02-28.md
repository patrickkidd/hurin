# Co-Founder Briefing: process-retro
**Date:** 2026-02-28 20:04 AKST
**Session:** 611e10e9-da2e-4c06-9fcd-4d18f6a95eae
**Turns:** 10 max

---

Now I have all the data. Let me synthesize this into the briefing.

---

**PROCESS RETRO — Week of 2026-02-22 to 2026-02-28**

---

**Velocity Check**

Hard numbers this week:

| Metric | This Week | Last Week | Delta |
|--------|-----------|-----------|-------|
| btcopilot commits | 20 | 20 | Flat |
| familydiagram commits | 9* | 18 | -50% |
| btcopilot lines added | 6,212 | 9,116 | -32% |
| btcopilot lines deleted | 1,335 | 3,135 | -57% |
| familydiagram lines added | 525 | — | — |
| PRs opened | 2 (btcopilot #33, btcopilot #32 / FD #86) | — | — |
| PRs merged | 0 | 0 | Flat |

*The 9 familydiagram commits include 2 that are hurin's (T7-12 auto-detect clusters).

**Commit classification (btcopilot):**
- Bug fixes: 2 (10%)
- Features/code: 9 (45%)
- Tests: 2 (10%)
- Docs/planning: 6 (30%)
- Other: 1 (5%)

The ratio of planning vs. building is roughly 30/70. That's better than many weeks — you're actually building. But the net output is declining: 4,877 net lines this week vs. 5,981 last week (down 18%).

**Most telling metric: zero PRs merged in two weeks.** The T7-12 PR (btcopilot #32) is massive — +6,835/-916 across 90 files — and still open since Feb 26. That's either scope creep or a PR too big to review. The newer PR #33 is also open.

Commit timing pattern: Saturday Feb 22 was a 10-commit day (half the week's btcopilot output). Tuesday and Thursday had scattered commits across early morning (4-7 AM) and midday hours. Activity is bursty, not steady.

**Verdict: decelerating.** Lower net lines, lower familydiagram activity, zero merges. The raw commit count held steady but the delivered-and-merged output dropped to zero.

---

**Agent System ROI**

This is where it gets uncomfortable.

**Agent utilization this week: near zero.** The monitor.log shows "No active tasks" every 10 minutes for the entire day today (Feb 28). Before that, it found "No task registry found" since Feb 26 at 10:40 AM. The last actual agent task was **T7-4** ("Build Diagram" button), which **died 3 times without creating a PR** and hit max respawns at 3:10 AM on Feb 26.

That's the agent system's entire contribution this week: one task, three failures, zero output.

**Agent commits this week:**
- btcopilot: 1 commit from hurin ("T7-12: Add auto-detect cluster tests")
- familydiagram: 2 commits from hurin ("T7-12: Auto-detect/Add ClusterModel tests")

So 3 out of 29 total commits (10%) came from the autonomous agent system. But these are likely from Claude Code interactive sessions co-authoring with Patrick, not from the hurin orchestrator dispatching agents to tmux. Evidence: 10 out of 20 btcopilot commits have `Co-Authored-By: Claude Opus 4.6` — meaning Patrick was driving Claude Code directly, not spawning autonomous agents.

**The infrastructure investment vs. utilization:**
- ADR-0001 documents 11/13 Elvis capabilities as "DONE"
- ADR-0004 (co-founder system) was accepted Feb 26
- ADR-0005 (action system) was accepted Feb 27
- Monitoring cron runs every 10 minutes (monitor.log, review.log)
- review-prs.sh runs every 15 minutes

All of this infrastructure is operational... and idle. The agent swarm had zero active tasks for the entire back half of the week. The monitoring system has been logging "No active tasks" or "No task registry found" continuously.

**Review system bug:** `review-prs.sh` has logged "Reviewing PR #33" **106 times today** (every 15 minutes since 12:45 AM). It's supposed to skip PRs with the `reviewed-by-claude` label. The label is either not being applied (the `gh pr edit --add-label` call at line 145 is failing silently) or the label check (line 78) isn't working because PR #33 only has 1 actual review on GitHub. This means the cron job is burning Claude API calls (or at minimum, `claude -p` invocations) reviewing the same PR over and over. **106 redundant reviews in one day.**

**Cost analysis:** With Max plan, the Claude API calls are $0 — but CPU time, I/O, and process overhead are real. More importantly, the human time spent building the agent system (ADRs 0001-0005, spawn-task.sh, check-agents.py, review-prs.sh, discord-react.sh, SOUL.md, prompt-patterns.md, the 3-tier→2-tier architectural collapse) represents at minimum 1-2 full working days that could have been spent on MVP tasks.

---

**Process Friction**

**1. CI is a 60% failure rate and nobody's fixing it.**

btcopilot CI: 8 success / 12 failure out of last 20 runs (40% pass rate). familydiagram CI: identical 8/12 split (40% pass rate). The btcopilot failures span the entire week — Feb 20 through Feb 26 — multiple commits landing on a broken CI pipeline. This means tests are either not being run locally before commit, or CI failures are being ignored.

When CI is red 60% of the time, it becomes noise. Nobody looks at a CI failure if the previous 5 were also failures. This erodes the value of the test suite entirely.

**2. PR #32 (T7-12) is +6,835 lines across 90 files.**

That's not a PR. That's a release. A 90-file PR cannot be meaningfully reviewed by a human or an AI. The automated Claude review truncated the diff at 2,000 lines — it literally couldn't see 70% of the changes. This PR will be merged on faith, not on review.

**3. The review-prs.sh cron is broken (re-reviews same PR endlessly).**

106 review attempts on PR #33 today alone. The `reviewed-by-claude` label isn't being applied. The script logs the attempt but silently fails on `gh pr edit --add-label`. This has been running all day without anyone noticing.

**4. Direct-to-master workflow with no test gates.**

20 commits landed directly on master this week. No branch, no PR, no review. This is fine for solo development speed, but it means the CI failures (60% rate) are landing on master. The main branch is broken and nobody's accountable because there's no gatekeeper.

**5. The T7-4 task failure burned 3 respawn cycles with no output.**

The agent took the task, died, was respawned 3 times, and produced nothing. Total elapsed: ~40 minutes of monitoring (2:50 AM to 3:10 AM on Feb 26). The `openclaw` command wasn't even found (`/bin/sh: openclaw: command not found`), suggesting a PATH issue in the cron environment that was never fixed.

---

**Time Allocation**

Based on commit classification and activity patterns:

| Activity | Estimated % | Notes |
|----------|-------------|-------|
| Coding (features + bugfixes) | ~55% | 11 code commits out of 20 btcopilot commits |
| Docs/planning/dashboard updates | ~25% | 6 doc commits, CLAUDE.md optimizations, dashboard maintenance |
| Agent infrastructure | ~10% | ADR-0004, ADR-0005, co-founder system, action system |
| Testing | ~10% | 2 explicit test commits, integration tests |
| Agent wrangling | ~0% | Agent system was idle all week |

**Is this the right allocation for MVP stage?** The 55% coding is good. The 25% docs/planning is arguably high — you have 10 open dashboard tasks and you're spending a quarter of your time maintaining the dashboard and documentation system rather than closing those tasks. The 10% agent infrastructure is investment-grade work... but the investment is yielding 0% returns this week because the agents aren't running.

**What should shift:** The entire 10% agent-infrastructure allocation should redirect to T7-5 (GT coding — the blocker), T7-9 (idempotent re-extraction), or T7-11 (extraction dedup). Those three tasks gate everything else.

---

**Week-Over-Week Trends**

This is the first retro, so I'm establishing baselines. Here's what I see from the available data:

- **The single-prompt pivot (Feb 24) was the week's biggest win.** Aggregate F1 jumped from 0.25 to 0.45, Events from 0.099 to 0.29, People FP dropped from 12 to 2. This is a legitimate architectural improvement documented in the decision log. One decision delivered more F1 improvement than months of delta-by-delta tuning.

- **The agent swarm peaked around Feb 26 and went completely idle.** The 3-tier→2-tier collapse happened Feb 25-26. The co-founder system (ADR-0004) and action system (ADR-0005) were designed Feb 26-27. Since then, zero autonomous tasks dispatched.

- **Dashboard is well-maintained but becoming overhead.** The verification log shows 4 manual checks in 8 days (Feb 20, 24, 24, 26). Each check results in task updates, reclassifications, and doc changes — not code shipped.

**Baselines for next retro:**
- Commits/week (both repos): 29 this week
- PRs merged/week: 0
- CI pass rate: 40%
- Agent autonomous commits: 3 (10%)
- Net lines shipped: ~5,300
- Open dashboard tasks: 10 (Goal 1: 8, Goal 2: 2)

---

**Concrete Recommendations**

**1. Fix CI before anything else.**

A 60% failure rate means CI is decoration, not protection. Spend one focused session getting btcopilot and familydiagram CI green on master. Then add a pre-commit hook or alias that runs the test suite before push. The payoff: every future commit is validated, and CI failures become actionable signals instead of background noise.

*Expected impact:* Prevents regressions from accumulating. Makes the agent system viable (agents check CI as part of "definition of done" — if CI is always red, this check is meaningless).

*How to measure:* CI pass rate > 90% next week.

**2. Stop building agent infrastructure. Start using agents.**

You built the swarm. It works. It has 11/13 Elvis capabilities. ADRs 0001-0005 are written. Now dispatch agents to actual MVP tasks. T7-9 (idempotent re-extraction validation) and T7-11 (extraction dedup) are both CC-friendly tasks that a Claude Code agent could tackle autonomously. Spawn them. If they fail, you learn something. If they succeed, you saved 4 hours.

*Expected impact:* 2-4 MVP tasks completed by agents, demonstrating ROI and clearing the path to T7-5 (which only Patrick can do).

*How to measure:* Number of agent-completed PRs merged next week (target: >= 2).

**3. Break PR #32 into smaller PRs or merge it.**

A 90-file, 6,835-line PR is unreviable. Either split it into logical chunks (tests in one PR, backend in another, frontend in a third) or accept that this is too big to review and merge it with a manual smoke test. Stale PRs create merge conflicts that compound over time.

*Expected impact:* Unblocks T7-12 (which is on the MVP dashboard), reduces merge conflict risk, sets a precedent for PR size discipline.

*How to measure:* PR merged or split within 2 days.

---

**One Uncomfortable Question**

Patrick — your agent swarm infrastructure has 5 ADRs, 7 monitoring scripts, a Discord integration, a review bot, a task registry, a spawn system, and a respawn loop with failure capture. It's been documented, designed, collapsed from 3-tier to 2-tier, and enhanced with prompt pattern logging.

And this week it produced 3 commits and 0 merged PRs, while simultaneously failing on T7-4 three times and reviewing PR #33 a hundred and six times.

Meanwhile, you — working directly with Claude Code as a co-pilot, not through the orchestrator — produced 26 commits, implemented the single-prompt extraction pivot, fixed crashes, added validation, and moved the dashboard forward.

**The question: are you building an agent army, or are you building FamilyDiagram?**

The git log has an answer. Of the 29 commits this week, 26 came from you driving Claude Code interactively. 3 came from the autonomous system. Your interactive workflow (Patrick + Claude Code pair programming) is delivering at 9x the rate of the autonomous system. That ratio should make you question whether the agent swarm is your highest-leverage investment right now.

The swarm might pay off later. But right now, you have 10 open MVP dashboard tasks, a 60% CI failure rate, zero PRs merged in two weeks, and a GT coding bottleneck that only you can solve. Every hour spent on ADR-0006 or spawn-task-v3.sh is an hour not spent on T7-5 (GT coding), which is the literal critical path to Goal 1.

The agent system isn't wrong. It's premature. Ship the MVP first, then automate the maintenance.

---

```proposed-actions
{
  "actions": [
    {
      "id": "process-retro-2026-02-28-1",
      "title": "Fix review-prs.sh label application bug",
      "category": "infrastructure",
      "effort": "trivial",
      "confidence": 0.95,
      "repo": "none",
      "plan": "1. Read review-prs.sh line 145 — gh pr edit --add-label is failing silently. 2. The likely issue is that the label doesn't exist or the gh command is running from the wrong directory. 3. Add error logging and fix the label application. 4. Verify by running --dry and checking label state.",
      "spawn_prompt": "Fix the review-prs.sh script at ~/.openclaw/monitor/review-prs.sh. The script is supposed to add the 'reviewed-by-claude' label to PRs after reviewing them (line 145: `gh pr edit \"$PR_NUM\" --add-label \"$LABEL\"`), but it's failing silently — the label is never applied, causing the script to re-review the same PR every 15 minutes (106 times today for PR #33). Debug by: (1) running `cd ~/.openclaw/workspace-hurin/theapp/btcopilot && gh pr view 33 --json labels` to see current labels, (2) trying `gh pr edit 33 --add-label 'reviewed-by-claude'` manually to see the error, (3) fixing the script. Also add better error logging — the `|| { log ... }` block should capture stderr. Acceptance criteria: after fix, running review-prs.sh twice in a row should show 'already reviewed, skipping' on the second run for the same PR.",
      "success_metric": "review.log shows 'already reviewed, skipping' for PRs that have been reviewed; no more redundant 15-minute review cycles"
    }
  ]
}
```
