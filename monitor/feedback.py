#!/usr/bin/env python3
"""
Feedback capture — structured task outcomes for The Seed meta-layer.

Called by check-agents.py when tasks transition to done/failed.
Appends one JSONL line per outcome to the feedback log.
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

# GitHub auth — reuse bot token from check-agents.py pattern
_bot_token_file = Path.home() / ".openclaw/monitor/hurin-bot-token"
if _bot_token_file.exists():
    os.environ["GH_TOKEN"] = _bot_token_file.read_text().strip()

FEEDBACK_LOG = Path.home() / ".openclaw/workspace-hurin/feedback/log.jsonl"


def run(cmd, cwd=None):
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _infer_task_type(repo, files_changed):
    """Infer task type from repo and changed file paths."""
    if not files_changed:
        return "unknown"

    extensions = {Path(f).suffix for f in files_changed}
    paths_str = " ".join(files_changed)

    # Infrastructure paths (check first — these live in monitor/co-founder/adrs)
    infra_markers = ["monitor/", "co-founder/", "adrs/", ".openclaw/"]
    if any(m in paths_str for m in infra_markers):
        return "infrastructure"

    # All markdown → docs
    if extensions <= {".md", ""}:
        return "docs"

    if repo == "btcopilot":
        has_test_files = any("test" in f.lower() for f in files_changed)
        if has_test_files:
            return "backend_test"
        if ".py" in extensions:
            return "backend_logic"

    if repo == "familydiagram":
        if extensions & {".qml", ".js"}:
            return "training_frontend"
        if ".py" in extensions:
            return "qt_qml"

    return "unknown"


def _get_files_changed(pr_num, repo_dir):
    """Get list of files changed in a PR."""
    code, out, _ = run(f"gh pr diff {pr_num} --name-only", cwd=repo_dir)
    if code == 0 and out:
        return [f for f in out.splitlines() if f.strip()]
    return []


def _get_ci_status(pr_num, repo_dir):
    """Get overall CI status: pass/fail/pending/unknown."""
    code, out, _ = run(
        f"gh pr checks {pr_num} --json state,conclusion 2>/dev/null",
        cwd=repo_dir
    )
    if code != 0 or not out:
        return "unknown"
    try:
        checks = json.loads(out)
        if not checks:
            return "unknown"
        if any(c.get("conclusion") == "FAILURE" for c in checks):
            return "fail"
        if any(c.get("state") == "IN_PROGRESS" for c in checks):
            return "pending"
        return "pass"
    except (json.JSONDecodeError, TypeError):
        return "unknown"


def _get_pr_verdict(pr_num, repo_dir):
    """Get PR verdict: merged/closed/changes_requested/open/no_pr."""
    code, out, _ = run(
        f"gh pr view {pr_num} --json state,reviewDecision 2>/dev/null",
        cwd=repo_dir
    )
    if code != 0 or not out:
        return "open"
    try:
        pr = json.loads(out)
        state = pr.get("state", "").upper()
        review = pr.get("reviewDecision", "")
        if state == "MERGED":
            return "merged"
        if state == "CLOSED":
            return "closed"
        if review == "CHANGES_REQUESTED":
            return "changes_requested"
        return "open"
    except (json.JSONDecodeError, TypeError):
        return "open"


def _get_lines_changed(pr_num, repo_dir):
    """Get total lines changed (insertions + deletions) from PR diff stat."""
    code, out, _ = run(
        f"gh pr diff {pr_num} --stat 2>/dev/null | tail -1", cwd=repo_dir
    )
    if code != 0 or not out:
        return 0
    # Summary line looks like: "5 files changed, 120 insertions(+), 30 deletions(-)"
    import re
    nums = re.findall(r"(\d+)\s+(?:insertion|deletion)", out)
    return sum(int(n) for n in nums)


def _get_pr_created_at(pr_num, repo_dir):
    """Get PR creation timestamp as ISO string, or empty string."""
    code, out, _ = run(
        f"gh pr view {pr_num} --json createdAt --jq .createdAt 2>/dev/null",
        cwd=repo_dir
    )
    if code == 0 and out:
        return out
    return ""


def _get_review_comments(pr_num, repo_dir):
    """Get the latest review body text, truncated."""
    code, out, _ = run(
        f"gh pr view {pr_num} --json reviews "
        f"--jq '.reviews[-1].body' 2>/dev/null",
        cwd=repo_dir
    )
    if code == 0 and out:
        return out[:500]
    return ""


def capture_outcome(task):
    """Capture a structured outcome for a completed/failed task.

    Args:
        task: dict from active-tasks.json with keys like id, repo, status, etc.
    """
    FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)

    tid = task.get("id", "unknown")
    repo = task.get("repo", "unknown")
    repo_dir = task.get("repoDir")
    status = task.get("status", "unknown")
    pr_num = task.get("pr")
    started_at = task.get("startedAt", 0)

    # Compute duration
    duration_sec = 0
    if started_at:
        duration_sec = int((datetime.now().timestamp() * 1000 - started_at) / 1000)

    # Gather PR-dependent data
    files_changed = []
    lines_changed = 0
    ci_status = "unknown"
    pr_verdict = "no_pr"
    pr_created_at = ""
    review_comments = ""
    cycle_time_sec = 0
    review_time_sec = 0

    if pr_num and repo_dir:
        files_changed = _get_files_changed(pr_num, repo_dir)
        lines_changed = _get_lines_changed(pr_num, repo_dir)
        ci_status = _get_ci_status(pr_num, repo_dir)
        pr_verdict = _get_pr_verdict(pr_num, repo_dir)
        pr_created_at = _get_pr_created_at(pr_num, repo_dir)
        review_comments = _get_review_comments(pr_num, repo_dir)

        # Compute cycle_time and review_time from pr_created_at
        if pr_created_at:
            try:
                pr_ts = datetime.fromisoformat(
                    pr_created_at.replace("Z", "+00:00")
                ).timestamp()
                now_ts = datetime.now().timestamp()
                if started_at:
                    cycle_time_sec = max(0, int(pr_ts - started_at / 1000))
                review_time_sec = max(0, int(now_ts - pr_ts))
            except (ValueError, TypeError):
                pass

    outcome = {
        "timestamp": datetime.now().isoformat(),
        "task_id": tid,
        "repo": repo,
        "description": task.get("description", ""),
        "status": status,
        "task_type": _infer_task_type(repo, files_changed),
        "files_changed": files_changed,
        "files_count": len(files_changed),
        "lines_changed": lines_changed,
        "ci_status": ci_status,
        "pr_verdict": pr_verdict,
        "pr_created_at": pr_created_at,
        "review_comments": review_comments,
        "duration_sec": duration_sec,
        "cycle_time_sec": cycle_time_sec,
        "review_time_sec": review_time_sec,
        "respawn_count": task.get("respawnCount", 0),
    }

    with open(FEEDBACK_LOG, "a") as f:
        f.write(json.dumps(outcome) + "\n")
