# Co-Founder Briefing: project-pulse
**Date:** 2026-02-27 09:06 AKST
**Session:** 19c486b5-3dbe-44d0-acf5-d5bc3907588f
**Turns:** 10 max

---

**Progress Since Last Check**

Quiet 24 hours. The only commits were T7-12 related, all on the feature branch — not master:

- **btcopilot `0fa8ac1`**: T7-12 auto-detect cluster tests (already noted yesterday)
- **familydiagram `406afa1`, `506dae9`**: T7-12 frontend tests + implementation
- **familydiagram CI run 22493336557**: Latest push to `feature/t7-12-auto-detect-clusters` — all green, "zoom non-clusters" commit message suggests a polish pass happened today

No new commits to master in either repo. No new decisions logged. No agent tasks spawned. The swarm has been completely idle for 24+ hours.

**PR Activity:**

| Repo | PR | State | Age | CI | Notes |
|------|----|-------|-----|----|-------|
| btcopilot #32 | T7-12: Auto-detect cluster tests | OPEN | 1 day | N/A | Ready to merge |
| familydiagram #86 | T7-12: Auto-detect clusters on PDP accept | OPEN, MERGEABLE | 1 day | Passing | Gemini reviewed (positive). Additional commit pushed today. |
| familydiagram #74 | FD-310: Event halos | OPEN | 9 days | Passing | Related to T3-7. No review. |
| familydiagram #72 | FD-307: Baseline View | OPEN | **50 days** | Unknown | Stale. T2-5 related (Goal 3, post-MVP). |
| btcopilot #16 | Synthetic client prompts | DRAFT | 10 days | N/A | Still draft. |
| btcopilot #10 | FD-300-proto | OPEN | **81 days** | N/A | Superseded by FD-300 (merged Dec 2025). Should be closed. |

---

**CRITICAL FINDING: T7-4 Is Not Actually Done**

The MVP Dashboard lists T7-4 ("Build my diagram" button) as **Done**. It's not. I checked familydiagram master for any trace of the extract button:

- `grep -r "extractFullDiscussion\|onExtract\|extractButton"` in `personalappcontroller.py` on master: **empty**
- Same grep in `DiscussView.qml` on master: **empty**
- `git log --oneline master | grep -i 'T7-4\|extract.*button\|build.*diagram'`: **empty**

The code exists only in the stale worktree at `/Users/hurin/Projects/theapp-worktrees/feat-T7-4-build-diagram-button` with **196 lines of uncommitted changes** across 3 files:

```
personalappcontroller.py      |  42 ++++++++
DiscussView.qml               |  30 ++++++
test_discussview.py            | 125 +++++++++++++
```

The agent tried 3 times, failed, and left the code uncommitted. `active-tasks.json` shows `status: "failed"`, `respawnCount: 3`, `pr: null`. **The extract button — the central UX of the single-prompt extraction pivot — has never been committed, branched, PR'd, or merged.** The dashboard was incorrectly updated.

This means the E2E flow described in decision 2026-02-24 ("User taps 'Build my diagram'") doesn't actually work in the shipped app. The btcopilot backend has `extract_full()` and the extract endpoint (T7-1, T7-2), but the Personal app has no button to call them.

**This is the highest priority item today — higher than T7-12, higher than GT coding.** Without the extract button, there's no user-facing way to trigger extraction. Goals 1 and 2 are both blocked on this.

---

**Today's Priorities**

**1. Rescue T7-4 from the stale worktree.**

The uncommitted code in the T7-4 worktree needs to be reviewed, committed, PR'd, and merged. The 3 modified files (controller, QML view, test) total 196 lines — this is a small, focused change. Verify the code works against current master (there have been ~15 commits since the worktree was created), fix any conflicts, and ship it.

**2. Merge the T7-12 PRs.**

Both PRs are MERGEABLE, CI passing, Gemini-reviewed. btcopilot #32 and familydiagram #86. Merge, delete branches, remove the `T7-12` worktree.

**3. GT Coding (T7-5).**

Same story as yesterday. The critical path remains:

```
T7-4 (rescue!) → T7-5 (Code GT) → T7-7 (Validate F1) → T7-8 (Prompt tune)
```

4 discussions coded (36/37/39/48), target 5-8. Each takes ~60 min. This is human-only and has been the bottleneck since Feb 24.

---

**Blockers & Risks**

- **T7-4 not merged** (NEW, CRITICAL): The extract button doesn't exist in the shipped app. The entire single-prompt extraction UX is non-functional. The worktree code may have conflicts with 15+ commits that landed on master since it was created.
- **GT coding bottleneck**: Unchanged since Feb 24. Patrick is sole coder. 4/5-8 discussions coded.
- **Events F1 at 0.29** (target 0.4): Can't improve until GT (T7-5) + prompt tuning (T7-8).
- **PairBond F1 at 0.33** (target 0.5): Same.
- **T7-10 (birth event self-reference)**: Flagged as "needs design discussion first." Could affect F1 measurement.
- **PR #72**: 50 days old, accumulating merge debt.

---

**Agent System Health**

- **Monitor**: Running every 10 minutes. "No active tasks" logged continuously — **288 entries in the last 48 hours**. The swarm is idle.

- **active-tasks.json**: Stale. Shows T7-4 as `failed` with `respawnCount: 3`, `pr: null`. Now we know why — the code never made it out of the worktree. This JSON should be cleared after T7-4 is rescued manually.

- **review-prs.sh**: **Broken since Feb 26 03:45.** Two root causes found in the log:

  1. **`gh: command not found`** (line 36) — cron doesn't have `gh` in its PATH. First error at 03:45:00.
  2. **`cd: /Users/hurin/Projects/theapp/btcopilot: No such file or directory`** (line 35) — early runs had wrong repo paths (since fixed in the script, but the PATH issue persists).

  The failure loop: `gh label list` fails (no `gh` in PATH) → stderr suppressed by `2>/dev/null` → `grep -qx` fails (no input) → enters label creation block → logs "Creating label" → `gh label create` also fails → `|| true` swallows it → `gh pr list` fails → `set -e` kills the script. Repeats every 15 minutes. **226 lines of "Creating label" in the log, zero PRs reviewed.** The `reviewed-by-claude` label doesn't exist in either repo because label creation also fails.

  **Fix**: Add `export PATH="/opt/homebrew/bin:$PATH"` (or wherever `gh` lives) to the top of the script. Then manually create the labels or let the fixed script do it.

- **Stale worktrees** (2):
  - `feat-T7-4-build-diagram-button` — **contains unmerged T7-4 code**. Do NOT delete — rescue first.
  - `T7-12` — clean, on master. Safe to remove after T7-12 PRs merge.

- **No tmux sessions running.** No agent failures in `~/.openclaw/monitor/failures/`. The infrastructure is healthy but completely inactive.

---

**One Uncomfortable Question**

Patrick — the dashboard said T7-4 was Done. It wasn't. The agent failed 3 times, left 196 lines of uncommitted code in a worktree, and the dashboard was updated anyway. Nobody noticed for at least a day. The review bot has been broken for 30+ hours, failing every 15 minutes, and nobody noticed that either.

This isn't an infrastructure problem — the monitoring, the dashboard, the review bot are all there. The problem is **nobody is watching the watchers**. The monitor logs "No active tasks" 288 times and nobody reads it. The review log fills with 226 identical error lines and nobody reads it. The dashboard says Done and nobody verifies it.

**What's your verification process?** When the dashboard says a task is Done, do you test the actual app? When the agent says it shipped, do you check that the code is on master? You built a sophisticated system (ADR-0001, spawn-task.sh, check-agents.py) but the feedback loop from "agent says done" to "human confirms done" doesn't exist yet. The T7-4 gap could have been caught with a 30-second `grep` on master. What would it take to add a verification step — even just a `git log master | grep T7-X` — before marking tasks Done on the dashboard?

---

```proposed-actions
{
  "actions": [
    {
      "id": "project-pulse-2026-02-27-1",
      "title": "Fix review-prs.sh PATH issue for cron",
      "category": "infrastructure",
      "effort": "trivial",
      "confidence": 0.95,
      "repo": "none",
      "plan": "1. Find gh binary path (which gh)\n2. Add PATH export to top of review-prs.sh\n3. Create reviewed-by-claude label in both repos\n4. Run review-prs.sh --dry to verify it works\n5. Truncate the review.log to remove 226 lines of noise",
      "spawn_prompt": "Fix the broken review-prs.sh automated PR review system.\n\nProblem: The cron environment doesn't have `gh` in PATH, causing review-prs.sh to fail silently every 15 minutes since Feb 26.\n\nSteps:\n1. Run: which gh\n2. Edit /Users/hurin/.openclaw/monitor/review-prs.sh — add after line 1 (after #!/bin/bash):\n   export PATH=\"/opt/homebrew/bin:$PATH\"\n   (Use the actual path from step 1)\n3. Create labels:\n   cd /Users/hurin/.openclaw/workspace-hurin/theapp/btcopilot && gh label create 'reviewed-by-claude' --description 'PR has been reviewed by Claude' --color '7057ff'\n   cd /Users/hurin/.openclaw/workspace-hurin/theapp/familydiagram && gh label create 'reviewed-by-claude' --description 'PR has been reviewed by Claude' --color '7057ff'\n4. Truncate the noisy log: > /Users/hurin/.openclaw/monitor/review.log\n5. Run: bash /Users/hurin/.openclaw/monitor/review-prs.sh --dry\n6. Verify output shows PR listing (not just 'Creating label')\n\nSuccess criteria: review-prs.sh --dry lists open PRs or says 'No open PRs' for each repo. No 'gh: command not found' errors.",
      "success_metric": "review-prs.sh --dry completes full cycle, listing PRs or saying 'No open PRs'"
    },
    {
      "id": "project-pulse-2026-02-27-2",
      "title": "Close superseded btcopilot PR #10",
      "category": "velocity",
      "effort": "trivial",
      "confidence": 0.95,
      "repo": "btcopilot",
      "plan": "1. Close PR #10 with comment that it was superseded by FD-300 (PR #11, merged Dec 2025)\n2. Delete remote branch if possible",
      "spawn_prompt": "Close the stale PR #10 in btcopilot repo.\n\ncd /Users/hurin/.openclaw/workspace-hurin/theapp/btcopilot\ngh pr close 10 --comment 'Closing: superseded by FD-300 (PR #11, merged Dec 2025). The synthetic user generator was fully implemented in that PR.'\ngh pr view 10 --json headRefName --jq '.headRefName' | xargs -I {} git push origin --delete {} 2>/dev/null || echo 'Branch already deleted or protected'\n\nSuccess: PR #10 shows as closed.",
      "success_metric": "btcopilot PR #10 is closed"
    },
    {
      "id": "project-pulse-2026-02-27-3",
      "title": "Rescue T7-4 extract button from stale worktree",
      "category": "bugfix",
      "effort": "small",
      "confidence": 0.75,
      "repo": "familydiagram",
      "plan": "1. Review the 196 lines of uncommitted changes in the T7-4 worktree\n2. Check for conflicts with current master (15+ commits since worktree created)\n3. Create a branch, commit the changes, push, open PR\n4. If conflicts exist, resolve them\n5. Update active-tasks.json to clear the stale T7-4 entry\n6. Do NOT update dashboard until PR is merged and verified",
      "spawn_prompt": "Rescue the T7-4 extract button code from the stale worktree and get it into a PR.\n\nContext: T7-4 adds the 'Build my diagram' extract button to the Personal app. An agent attempted this 3 times and failed, leaving 196 lines of uncommitted code in a worktree. The code is NOT on master. The dashboard incorrectly says T7-4 is Done.\n\nFiles with changes (in the worktree):\n- pkdiagram/personal/personalappcontroller.py (+42 lines)\n- pkdiagram/resources/qml/Personal/DiscussView.qml (+30 lines)\n- pkdiagram/tests/personal/test_discussview.py (+125 lines)\n\nSteps:\n1. cd /Users/hurin/Projects/theapp-worktrees/feat-T7-4-build-diagram-button\n2. Read all 3 modified files (git diff) to understand the changes\n3. Check if the changes apply cleanly to current familydiagram master:\n   cd /Users/hurin/.openclaw/workspace-hurin/theapp/familydiagram\n   git checkout -b feat/T7-4-rescue master\n   git diff --no-index /dev/null /dev/null  # just to verify we're on the right branch\n4. Apply the changes from the worktree to the new branch. Read each file from the worktree and compare with master to manually apply.\n5. Run tests: uv run pytest pkdiagram/tests/personal/test_discussview.py -x -v\n6. If tests pass, commit and push:\n   git add pkdiagram/personal/personalappcontroller.py pkdiagram/resources/qml/Personal/DiscussView.qml pkdiagram/tests/personal/test_discussview.py\n   git commit -m 'T7-4: Add Build my diagram extract button to Personal app'\n   git push -u origin feat/T7-4-rescue\n   gh pr create --title 'T7-4: Add extract button to Personal app DiscussView' --body 'Rescues T7-4 implementation from stale worktree. Adds extract button to trigger single-prompt full-conversation extraction.'\n7. Update active-tasks.json: write {\"tasks\": []} to /Users/hurin/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json\n\nIMPORTANT: The extract button should call the backend POST /extract endpoint (T7-2, already on btcopilot master). Check btcopilot/personal/routes/discussions.py for the endpoint signature. The controller method should POST to /api/personal/discussions/<id>/extract.\n\nSuccess criteria: PR opened with extract button implementation, tests passing, active-tasks.json cleared.",
      "success_metric": "PR opened for T7-4 with passing tests; extract button visible in DiscussView.qml"
    }
  ]
}
```
