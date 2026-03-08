# Co-Founder Briefing: project-pulse
**Date:** 2026-03-08 04:05 UTC
**Session:** 17aaffb4-5f6f-43d6-9e0a-54dbe9b9c0bc
**Turns:** 10 max

---

**Progress Since Last Check**

Busy 24 hours, mostly co-founder activity. 7 commits to theapp (all co-founder/chief-of-staff briefings). On the product side: voice input landed as PRs #121 (walkie-talkie press-hold) and #122 (unit tests) in familydiagram — both CI green, ready for review. Co-founder's Plan tab hiding (#119) and extract button relabeling (#120) were **closed without merge** — Patrick either disagreed or wants manual control. Same for btcopilot insights endpoint (#102, closed). The product-vision briefing's "hide Plan tab" recommendation was rejected in practice.

**Today's Priorities**

1. **Fix btcopilot master CI** — it's broken right now. Most recent master push (`bf7e2cb`) crashes on Docker import: `litreview.py:30` raises `FileNotFoundError` because it can't find `fdserver/prompts/private_prompts.py` in the Docker image. This is a hard blocker — no new btcopilot PRs can merge until fixed.
2. **Triage the PR backlog** — 21 open PRs in btcopilot, 9 in familydiagram. Many from the Mar 3-5 agent sprint are stale (btcopilot #44-#97). Several are duplicates (F1 breakdown: #75 and #89; dedup: #82 closed, #88 open). This backlog is growing faster than it's being reviewed.
3. **Review voice input PRs** — #121/#122 are the freshest work with passing CI. If voice input is wanted for MVP, merge while they're clean.

**Blockers & Risks**

- **btcopilot master CI failure** is the critical blocker. The task daemon's CI-fix auto-enqueue should trigger, but the underlying issue is an import-time `FileNotFoundError` that needs fdserver prompts available in Docker — may need a Dockerfile or `litreview.py` fix to handle missing prompts gracefully.
- PRs #72 and #74 in familydiagram are 2+ months old. Either merge or close them.
- btcopilot has PRs from 5 days ago that nobody's looked at (#84 dead-code cleanup, #88 T7-11 dedup, #73 idempotency tests). These are infra improvements that rot quickly.

**Agent System Health**

All 3 services running. Gateway restarted ~30min ago (co-founder lens running right now). Task daemon up 10h, clean. No failures in `~/.openclaw/monitor/failures/`. No tmux zombies. Two stale worktrees from closed PRs #119/#120 at `~/.openclaw/workspace-hurin/familydiagram-worktrees/cf-product-vision-*` — should be cleaned up.

**One Uncomfortable Question**

You have **21 open PRs in btcopilot** and **9 in familydiagram** — 30 open PRs total, with the oldest from November 2024 (btcopilot #16). The agents are producing PRs faster than you can review them. In the last 5 days, 6 btcopilot PRs were closed without merge. The co-founder spawned 4 tasks in the last 24 hours, 3 of which you closed. **At what point does "agent-generated PR" become noise rather than leverage?** The review queue is the bottleneck, not code generation. Would you get more value from a 2-hour PR triage session — merging, closing, or consolidating the 30 open PRs — than from letting the agents create more?

```proposed-actions
{
  "actions": [
    {
      "id": "project-pulse-2026-03-08-1",
      "title": "Fix btcopilot master CI: litreview import crash",
      "category": "infrastructure",
      "effort": "small",
      "confidence": 0.85,
      "repo": "btcopilot",
      "plan": "1. In btcopilot/training/litreview.py around line 30, change the FileNotFoundError raise to a warning + graceful fallback when prompts file is missing. 2. The litreview module should remain importable even without fdserver co-located — use a lazy-load pattern or guard the import behind a flag. 3. Verify Docker CI passes after the fix.",
      "spawn_prompt": "Fix the btcopilot master CI failure. The Docker test step crashes because `btcopilot/training/litreview.py` line 30 raises `FileNotFoundError` at import time when `fdserver/prompts/private_prompts.py` is not found.\n\nFile: `btcopilot/training/litreview.py`\n\nThe current code (around line 25-30) does something like:\n```python\nprompts_path = ...\nif not prompts_path.exists():\n    raise FileNotFoundError(f'Cannot find production prompts at {prompts_path}...')\n```\n\nThis crashes the entire app import in Docker where fdserver is not co-located.\n\nFix:\n1. Replace the `raise FileNotFoundError` with a warning log and set a module-level flag like `PROMPTS_AVAILABLE = False`\n2. Guard any functions that use the prompts with a check: if not PROMPTS_AVAILABLE, return an appropriate error response (e.g., 503 or raise a runtime error only when the feature is actually called)\n3. The app must remain importable and pass the Docker smoke test (`gunicorn 'btcopilot.app:create_app()'`) even without fdserver prompts\n4. Keep the existing `FDSERVER_PROMPTS_PATH` env var support\n\nAcceptance criteria:\n- `python -c 'from btcopilot.app import create_app; create_app()'` succeeds without fdserver present\n- Docker CI step passes (gunicorn smoke test)\n- Litreview routes return a clear error if prompts are unavailable at request time\n- No changes to behavior when fdserver IS available",
      "success_metric": "btcopilot master CI passes (Docker smoke test succeeds)"
    },
    {
      "id": "project-pulse-2026-03-08-2",
      "title": "Clean up stale worktrees from closed PRs",
      "category": "infrastructure",
      "effort": "trivial",
      "confidence": 0.95,
      "repo": "none",
      "plan": "1. Remove familydiagram worktrees for closed PRs 119 and 120. 2. Prune git worktree references. 3. Delete the corresponding remote branches if they exist.",
      "spawn_prompt": "Clean up stale git worktrees from closed PRs.\n\n1. Remove these directories:\n   - `~/.openclaw/workspace-hurin/familydiagram-worktrees/cf-product-vision-2026-03-08-1`\n   - `~/.openclaw/workspace-hurin/familydiagram-worktrees/cf-product-vision-2026-03-08-2`\n\n2. From the familydiagram repo at `~/.openclaw/workspace-hurin/theapp/familydiagram`, run:\n   - `git worktree prune`\n   - `git branch -D feat/cf-product-vision-2026-03-08-1` (if exists)\n   - `git branch -D feat/cf-product-vision-2026-03-08-2` (if exists)\n\n3. Delete remote branches:\n   - `git push origin --delete feat/cf-product-vision-2026-03-08-1` (if exists)\n   - `git push origin --delete feat/cf-product-vision-2026-03-08-2` (if exists)\n\n4. Update active-tasks.json at `~/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json`:\n   - For tasks `cf-product-vision-2026-03-08-1` and `cf-product-vision-2026-03-08-2`, set status to 'closed' and clear the worktree path\n\nAcceptance criteria:\n- No stale worktree directories remain\n- `git worktree list` from familydiagram repo shows no prunable entries\n- active-tasks.json reflects closed status",
      "success_metric": "No stale worktree directories, git worktree list is clean"
    }
  ]
}
```
