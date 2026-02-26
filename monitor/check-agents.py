#!/usr/bin/env python3
"""
Agent monitoring script - runs every 10 minutes via cron.

Checks active Claude Code sessions (2-tier: hurin spawns directly):
- tmux session still alive?
- PR created? CI passing? Review status?
- Session dead + no PR → capture failure log, alert hurin (Ralph Loop V2)
- CI failing → include specific failures in alert
- Review CHANGES_REQUESTED → alert hurin
- PR approved + CI green → mark done, clean up worktree

Each task tracks its target repo (btcopilot or familydiagram) so gh commands
run in the correct repo context.

Pings hurin directly via `openclaw agent` when action is needed.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

REGISTRY     = Path.home() / "Projects/theapp/.clawdbot/active-tasks.json"
LOG          = Path.home() / ".openclaw/monitor/monitor.log"
FAILURES_DIR = Path.home() / ".openclaw/monitor/failures"
DEV_REPO     = Path.home() / "Projects/theapp"
MAX_RESPAWNS = 3


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def run(cmd, cwd=None):
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def tmux_alive(session):
    code, _, _ = run(f"tmux has-session -t '{session}' 2>/dev/null")
    return code == 0


def capture_tmux_output(session, task_id):
    """Capture last 100 lines from tmux session before it dies. Save to failures dir."""
    FAILURES_DIR.mkdir(parents=True, exist_ok=True)
    failure_log = FAILURES_DIR / f"{task_id}.log"

    code, output, _ = run(f"tmux capture-pane -t '{session}' -p -S -100")
    if code == 0 and output:
        failure_log.write_text(output)
        log(f"  Captured tmux output to {failure_log}")
        return str(failure_log)

    # Session already dead — try to capture from history if available
    failure_log.write_text(f"[Session '{session}' was already dead when capture attempted]\n")
    log(f"  Session dead, wrote placeholder to {failure_log}")
    return str(failure_log)


def get_pr(branch, repo_dir):
    """Get PR info. repo_dir is the subrepo (btcopilot or familydiagram) where PRs land."""
    code, out, _ = run(
        f"gh pr list --head '{branch}' "
        f"--json number,state,url,statusCheckRollup,reviewDecision --limit 1",
        cwd=repo_dir
    )
    if code == 0 and out and out != "[]":
        prs = json.loads(out)
        if prs:
            return prs[0]
    return None


def get_ci_failure_details(pr_num, repo_dir):
    """Pull specific check run failures via gh pr checks."""
    code, out, _ = run(
        f"gh pr checks {pr_num} --json name,state,conclusion 2>/dev/null",
        cwd=repo_dir
    )
    if code != 0 or not out:
        return ""

    try:
        checks = json.loads(out)
        failed = [c for c in checks if c.get("conclusion") == "FAILURE"]
        if failed:
            details = "\n".join(f"  - {c['name']}: FAILED" for c in failed)
            return f"CI failures:\n{details}"
    except json.JSONDecodeError:
        pass
    return ""


def get_review_comments(pr_num, repo_dir):
    """Get review comments if CHANGES_REQUESTED."""
    code, out, _ = run(
        f"gh pr view {pr_num} --json reviews --jq '.reviews[-1].body' 2>/dev/null",
        cwd=repo_dir
    )
    if code == 0 and out:
        return out[:500]  # Truncate long reviews
    return ""


def ping_hurin(msg):
    log(f"PINGING HURIN: {msg}")
    code, out, err = run(f"openclaw agent --agent hurin --message {json.dumps(msg)}")
    if code != 0:
        log(f"  WARNING: ping failed: {err}")


def cleanup_worktree(task):
    """Remove worktree for completed tasks."""
    worktree = task.get("worktree", "")
    if worktree and Path(worktree).exists():
        code, _, err = run(f"git worktree remove '{worktree}' --force", cwd=str(DEV_REPO))
        if code == 0:
            log(f"  Cleaned up worktree: {worktree}")
        else:
            log(f"  WARNING: worktree cleanup failed: {err}")


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    FAILURES_DIR.mkdir(parents=True, exist_ok=True)

    if not REGISTRY.exists():
        log("No task registry found. Nothing to check.")
        return

    with open(REGISTRY) as f:
        data = json.load(f)

    tasks  = data.get("tasks", [])
    active = [t for t in tasks if t["status"] in ("running", "pr_open")]

    if not active:
        log("No active tasks.")
        return

    changed = False

    for task in active:
        tid      = task["id"]
        session  = task["tmuxSession"]
        branch   = task["branch"]
        repo_dir = task.get("repoDir", str(DEV_REPO))
        repo     = task.get("repo", "unknown")
        respawns = task.get("respawnCount", 0)

        log(f"Checking {tid} ({repo})")

        # --- Check for PR first (task may have finished) ---
        pr = get_pr(branch, repo_dir)

        if pr:
            pr_num  = pr["number"]
            pr_url  = pr["url"]
            checks  = pr.get("statusCheckRollup") or []
            review  = pr.get("reviewDecision", "")

            if task.get("pr") != pr_num:
                task["pr"]     = pr_num
                task["prUrl"]  = pr_url
                task["status"] = "pr_open"
                changed = True
                log(f"  PR #{pr_num} found: {pr_url}")

            failed  = [c for c in checks if c.get("conclusion") == "FAILURE"]
            pending = [c for c in checks if c.get("status") == "IN_PROGRESS"]
            passed  = checks and not failed and not pending

            # Review-aware done condition
            if review == "CHANGES_REQUESTED":
                review_body = get_review_comments(pr_num, repo_dir)
                ping_hurin(
                    f"CHANGES REQUESTED on PR #{pr_num} ({tid}, {repo}) | {pr_url}\n"
                    f"Review feedback: {review_body}"
                )
            elif failed:
                ci_details = get_ci_failure_details(pr_num, repo_dir)
                names = ", ".join(c["name"] for c in failed)
                ping_hurin(
                    f"CI FAILING on PR #{pr_num} ({tid}, {repo}): {names} | {pr_url}\n"
                    f"{ci_details}"
                )
            elif passed and review != "CHANGES_REQUESTED":
                # PR is done: CI green AND no outstanding review changes
                ping_hurin(f"PR #{pr_num} READY TO MERGE ({tid}, {repo}) | {pr_url}")
                task["status"] = "done"
                changed = True
            else:
                log(f"  PR #{pr_num} open, CI pending.")
            continue

        # --- No PR yet — check tmux session ---
        if tmux_alive(session):
            log(f"  Session '{session}' alive, no PR yet.")
        else:
            log(f"  Session '{session}' DEAD, no PR.")
            # Capture output for Ralph Loop
            failure_log = capture_tmux_output(session, tid)

            if respawns >= MAX_RESPAWNS:
                ping_hurin(
                    f"FAILED — {tid} ({repo}): session dead, no PR, "
                    f"max respawns ({MAX_RESPAWNS}) reached. Manual intervention needed.\n"
                    f"Failure log: {failure_log}"
                )
                task["status"] = "failed"
            else:
                ping_hurin(
                    f"RESPAWN NEEDED — {tid} ({repo}): session died before creating PR. "
                    f"Attempt {respawns + 1}/{MAX_RESPAWNS}.\n"
                    f"Failure log: {failure_log}\n"
                    f"Worktree: {task.get('worktree')} | Branch: {branch}"
                )
                task["respawnCount"] = respawns + 1
            changed = True

    # --- Worktree cleanup for done tasks ---
    done_tasks = [t for t in tasks if t["status"] == "done"]
    for task in done_tasks:
        if task.get("worktree") and Path(task["worktree"]).exists():
            cleanup_worktree(task)

    if changed:
        with open(REGISTRY, "w") as f:
            json.dump(data, f, indent=2)

    log("Check complete.")


if __name__ == "__main__":
    main()
