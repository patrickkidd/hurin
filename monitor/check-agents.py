#!/usr/bin/env python3
"""
Agent monitoring script - runs every 10 minutes via cron.

Checks active Claude Code sessions (2-tier: hurin spawns directly):
- tmux session still alive?
- PR created? CI passing? Review status?
- Session dead + no PR → capture failure log, alert hurin (Ralph Loop V2)
- CI failing → include specific failures in alert
- Review CHANGES_REQUESTED → alert hurin
- PR approved + CI green → auto-sync project board to "Done", clean up worktree

Each task tracks its target repo (btcopilot or familydiagram) so gh commands
run in the correct repo context.

Pings hurin directly via `openclaw agent` when action is needed.

NEW: Automatically syncs GitHub project board when:
- PR is found → updates project item with PR reference
- PR is ready to merge → syncs to "Done" status automatically
- PR has issues → alerts hurin
"""

import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from feedback import capture_outcome

# GitHub auth — use patrickkidd-hurin bot account for all gh commands
_bot_token_file = Path.home() / ".openclaw/monitor/hurin-bot-token"
if _bot_token_file.exists():
    os.environ["GH_TOKEN"] = _bot_token_file.read_text().strip()

GH_BIN       = Path.home() / ".local/bin/gh"
REGISTRY     = Path.home() / ".openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"
LOG          = Path.home() / ".openclaw/monitor/monitor.log"
FAILURES_DIR = Path.home() / ".openclaw/monitor/failures"
DEV_REPO     = Path.home() / ".openclaw/workspace-hurin/theapp"
QUEUE_FILE   = Path.home() / ".openclaw/monitor/task-queue.json"
QUEUE_PROMPTS= Path.home() / ".openclaw/monitor/queue-prompts"
SPAWN_SCRIPT = Path.home() / ".openclaw/monitor/spawn-task.sh"
MAX_RESPAWNS = 3
CI_FIX_COOLDOWN_FILE = Path.home() / ".openclaw/monitor/ci-fix-cooldown.json"
CI_FIX_COOLDOWN_SECS = 6 * 3600  # 6 hours
CI_FIX_REPOS = ["btcopilot", "familydiagram"]

# GitHub project sync config
PROJECT_ID = "PVT_kwHOABjmWc4BP0PU"
SCRIPTS_DIR = Path.home() / ".openclaw/workspace-hurin/scripts"
GH_FIND_SCRIPT = SCRIPTS_DIR / "gh-project-find-item.sh"
GH_SYNC_SCRIPT = SCRIPTS_DIR / "gh-project-sync.sh"

# Discord config for #quick-wins notifications
_discord_token_file = Path.home() / ".openclaw/monitor/discord-bot-token"
DISCORD_BOT_TOKEN = _discord_token_file.read_text().strip() if _discord_token_file.exists() else ""
DISCORD_QUICKWINS_CHANNEL_ID = "1476950473893482587"


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def post_to_quickwins(message):
    """Post a notification to #quick-wins via Discord bot API."""
    try:
        payload = json.dumps({"content": message[:2000]}).encode("utf-8")
        url = f"https://discord.com/api/v10/channels/{DISCORD_QUICKWINS_CHANNEL_ID}/messages"
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Authorization", f"Bot {DISCORD_BOT_TOKEN}")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "CoFounderBot (https://openclaw.ai, 1.0)")
        urllib.request.urlopen(req, timeout=10)
        log(f"  Posted to #quick-wins")
    except Exception as e:
        log(f"  WARNING: #quick-wins post failed: {e}")


def run(cmd, cwd=None):
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def tmux_alive(session):
    code, _, _ = run(f"tmux has-session -t '{session}' 2>/dev/null")
    return code == 0


def capture_tmux_output(session, task_id):
    """Capture last 100 lines from tmux session or task log. Save to failures dir."""
    FAILURES_DIR.mkdir(parents=True, exist_ok=True)
    failure_log = FAILURES_DIR / f"{task_id}.log"

    # Try live tmux capture first
    code, output, _ = run(f"tmux capture-pane -t '{session}' -p -S -100")
    if code == 0 and output:
        failure_log.write_text(output)
        log(f"  Captured tmux output to {failure_log}")
        return str(failure_log)

    # Session already dead — fall back to task log file
    task_log = Path.home() / f".openclaw/monitor/task-logs/{task_id}.log"
    if task_log.exists():
        lines = task_log.read_text().splitlines()
        last_100 = '\n'.join(lines[-100:])
        failure_log.write_text(f"[From task log - session was dead]\n{last_100}")
        log(f"  Captured from task log to {failure_log}")
        return str(failure_log)

    failure_log.write_text(f"[Session '{session}' dead and no task log found]\n")
    log(f"  No capture source available for {failure_log}")
    return str(failure_log)


def get_pr(branch, repo_dir):
    """Get PR info. repo_dir is the subrepo (btcopilot or familydiagram) where PRs land."""
    code, out, _ = run(
        f"{GH_BIN} pr list --head '{branch}' "
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
        f"{GH_BIN} pr checks {pr_num} --json name,state,conclusion 2>/dev/null",
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
        f"{GH_BIN} pr view {pr_num} --json reviews --jq '.reviews[-1].body' 2>/dev/null",
        cwd=repo_dir
    )
    if code == 0 and out:
        return out[:500]  # Truncate long reviews
    return ""


HIGH_RISK_PATTERNS = ['auth', 'security', 'payment', 'secret', 'migration', 'deploy', 'config.py', 'ios/', 'testflight', 'build/', 'xcodeproj', 'simulator', '.github/workflows/']
MEDIUM_RISK_PATTERNS = ['models/', 'engine.py', 'routes/', 'views/', 'api/']

def score_risk(files_changed):
    if not files_changed:
        return 'low'
    paths = ' '.join(f.lower() for f in files_changed)
    if any(p in paths for p in HIGH_RISK_PATTERNS):
        return 'high'
    if any(p in paths for p in MEDIUM_RISK_PATTERNS) or len(files_changed) > 10:
        return 'medium'
    return 'low'


def sync_project_board(task, pr_num, status):
    """
    Sync GitHub project board to given status when PR is in final state.
    
    Requires issue number in task registry (from spawn-task-with-project.sh).
    If issue number is not available, logs warning but doesn't fail.
    """
    if not GH_FIND_SCRIPT.exists() or not GH_SYNC_SCRIPT.exists():
        log(f"  Project sync scripts not found, skipping sync")
        return False
    
    issue_num = task.get("issueNumber")
    if not issue_num:
        log(f"  No issue number in registry (not spawned with --issue), skipping project sync")
        return False
    
    try:
        repo = task.get("repo", "unknown")
        gh_repo = f"patrickkidd/{repo}"
        
        # Find the project item ID for this issue
        code, item_id, err = run(f"bash {GH_FIND_SCRIPT} {gh_repo} {issue_num}")
        
        if code != 0 or not item_id:
            log(f"  WARNING: Could not find project item for issue #{issue_num} in {gh_repo}")
            return False
        
        # Sync to the given status
        status_arg = status if status in ["Todo", "In Progress", "Done"] else "Done"
        code, out, err = run(f"bash {GH_SYNC_SCRIPT} {item_id} --status \"{status_arg}\"")
        
        if code == 0:
            log(f"  ✓ Project board synced: issue #{issue_num} → {status_arg}")
            return True
        else:
            log(f"  WARNING: Project board sync failed: {err}")
            return False
    
    except Exception as e:
        log(f"  Project board sync failed with exception: {e}")
        return False


def ping_hurin(msg):
    log(f"PINGING HURIN: {msg}")
    code, out, err = run(f"openclaw agent --agent hurin --message {json.dumps(msg)}")
    if code != 0:
        log(f"  WARNING: ping failed: {err}")


def cleanup_worktree(task):
    """Remove worktree for completed tasks."""
    worktree = task.get("worktree", "")
    if worktree and Path(worktree).exists():
        # Use repoDir (the repo that owns the worktree) if available, else fall back to DEV_REPO
        repo_dir = task.get("repoDir", str(DEV_REPO))
        code, _, err = run(f"git worktree remove '{worktree}' --force", cwd=repo_dir)
        if code == 0:
            log(f"  Cleaned up worktree: {worktree}")
        else:
            log(f"  WARNING: worktree cleanup failed: {err}")


def check_master_ci():
    """Auto-spawn a CI fix task when master is failing.

    For each repo, checks the latest master workflow run.  If it failed and
    no fix-ci task is already running and the repo isn't in cooldown, spawns
    a new fix-ci-{repo}-{timestamp} task via spawn-task.sh.

    Rate-limited to one auto-spawn per 6 hours per repo.
    """
    # Load cooldown state
    cooldowns = {}
    if CI_FIX_COOLDOWN_FILE.exists():
        try:
            cooldowns = json.loads(CI_FIX_COOLDOWN_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            cooldowns = {}

    # Load registry to check for already-running fix tasks
    running_fix_ids = set()
    if REGISTRY.exists():
        try:
            with open(REGISTRY) as f:
                reg = json.load(f)
            for t in reg.get("tasks", []):
                if t["status"] == "running" and t["id"].startswith("fix-ci-"):
                    running_fix_ids.add(t.get("repo", ""))
        except (json.JSONDecodeError, KeyError):
            pass

    cooldown_changed = False

    for repo in CI_FIX_REPOS:
        repo_dir = str(DEV_REPO / repo)

        # Skip if a fix-ci task is already running for this repo
        if repo in running_fix_ids:
            log(f"  CI-fix: {repo} already has a running fix-ci task, skipping.")
            continue

        # Check cooldown
        last_spawn = cooldowns.get(repo, 0)
        if time.time() - last_spawn < CI_FIX_COOLDOWN_SECS:
            remaining = int(CI_FIX_COOLDOWN_SECS - (time.time() - last_spawn))
            log(f"  CI-fix: {repo} in cooldown ({remaining}s remaining), skipping.")
            continue

        # Check latest master CI run
        code, out, _ = run(
            f"{GH_BIN} run list --branch master --limit 1 --json conclusion,databaseId",
            cwd=repo_dir,
        )
        if code != 0 or not out:
            log(f"  CI-fix: {repo} could not fetch CI runs.")
            continue

        try:
            runs = json.loads(out)
        except json.JSONDecodeError:
            log(f"  CI-fix: {repo} bad JSON from gh run list.")
            continue

        if not runs:
            continue

        latest = runs[0]
        conclusion = latest.get("conclusion", "")
        run_id = latest.get("databaseId", "")

        if conclusion != "failure":
            continue

        log(f"  CI-fix: {repo} master CI FAILED (run {run_id}). Spawning fix task.")

        # Get failure log
        _, fail_log, _ = run(
            f"{GH_BIN} run view {run_id} --log-failed 2>/dev/null | tail -50",
            cwd=repo_dir,
        )

        # Build prompt
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        task_id = f"fix-ci-{repo}-{ts}"
        prompt = (
            f"The master branch CI is failing in {repo}.\n\n"
            f"## Failure log (last 50 lines of gh run view {run_id} --log-failed)\n\n"
            f"```\n{fail_log}\n```\n\n"
            f"Diagnose the failure, fix it, and ensure CI passes.\n"
            f"Run the failing tests locally before pushing.\n"
        )

        # Spawn via spawn-task.sh
        try:
            result = subprocess.run(
                [str(SPAWN_SCRIPT), "--repo", repo, "--task", task_id,
                 "--description", f"Auto-fix master CI for {repo}"],
                input=prompt, text=True, capture_output=True, timeout=120,
            )
            if result.returncode != 0:
                log(f"  CI-fix: spawn failed for {repo}: {result.stderr}")
                continue
        except subprocess.TimeoutExpired:
            log(f"  CI-fix: spawn timed out for {repo}")
            continue

        log(f"  CI-fix: spawned {task_id}")
        cooldowns[repo] = time.time()
        cooldown_changed = True

    if cooldown_changed:
        CI_FIX_COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
        CI_FIX_COOLDOWN_FILE.write_text(json.dumps(cooldowns, indent=2))


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    FAILURES_DIR.mkdir(parents=True, exist_ok=True)

    if not REGISTRY.exists():
        log("No task registry found. Nothing to check.")
        drain_queue()
        log("Check complete.")
        return

    with open(REGISTRY) as f:
        data = json.load(f)

    tasks  = data.get("tasks", [])
    active = [t for t in tasks if t["status"] in ("running", "pr_open")]

    if not active:
        log("No active tasks.")
        # Skip monitoring loop but still drain the queue below
    else:
        _monitor_active_tasks(data, tasks, active)

    # Always attempt to drain the queue (even with no active tasks)
    drain_queue()

    # Auto-spawn CI fix tasks for failing master branches
    check_master_ci()

    log("Check complete.")


def _monitor_active_tasks(data, tasks, active):
    """Monitor running/pr_open tasks — extracted from main() for queue drain flow."""
    changed = False

    for task in active:
        tid      = task["id"]
        session  = task["tmuxSession"]
        branch   = task["branch"]
        repo_dir = task.get("repoDir", str(DEV_REPO))
        repo     = task.get("repo", "unknown")
        respawns = task.get("respawnCount", 0)

        log(f"Checking {tid} ({repo})")

        # --- Wall-clock timeout check ---
        max_minutes = task.get("maxMinutes", 0)
        started_at = task.get("startedAt", 0)
        if max_minutes > 0 and started_at > 0:
            elapsed_ms = int(time.time() * 1000) - started_at
            if elapsed_ms > max_minutes * 60 * 1000:
                log(f"  TIMEOUT: {tid} exceeded {max_minutes}min")
                capture_tmux_output(session, tid)
                run(f"tmux kill-session -t '{session}' 2>/dev/null")
                task["status"] = "timed_out"
                changed = True
                try:
                    capture_outcome(task)
                except Exception as e:
                    log(f"  WARNING: feedback capture failed: {e}")
                continue

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
                # Compute risk level from files changed
                _, diff_out, _ = run(
                    f"{GH_BIN} pr diff {pr_num} --name-only",
                    cwd=repo_dir
                )
                files_changed = [f for f in diff_out.splitlines() if f.strip()]
                risk = score_risk(files_changed)
                task["riskLevel"] = risk
                log(f"  Risk: {risk} ({len(files_changed)} files)")
                # Label the GitHub issue as having an open PR
                issue_num = task.get("issueNumber")
                if issue_num:
                    run(f"{GH_BIN} issue edit {issue_num} --repo patrickkidd/theapp "
                        f"--add-label cf-pr-open --remove-label cf-spawned 2>/dev/null")
                # Post approvable artifact to #quick-wins
                risk_emoji = {"high": "🔴 HIGH RISK", "medium": "🟡 MEDIUM RISK", "low": "🟢 LOW RISK"}[risk]
                desc = task.get("description", tid)
                post_to_quickwins(
                    f"{risk_emoji} ✅ **PR ready for review:** {desc}\n"
                    f"   → <{pr_url}>"
                )

            failed  = [c for c in checks if c.get("conclusion") == "FAILURE"]
            pending = [c for c in checks if c.get("status") == "IN_PROGRESS"]
            passed  = checks and not failed and not pending

            # Review-aware done condition
            if review == "CHANGES_REQUESTED":
                review_body = get_review_comments(pr_num, repo_dir)
                ping_hurin(
                    f"CHANGES REQUESTED on PR #{pr_num} ({tid}, {repo}) | <{pr_url}>\n"
                    f"Review feedback: {review_body}"
                )
            elif failed:
                ci_details = get_ci_failure_details(pr_num, repo_dir)
                names = ", ".join(c["name"] for c in failed)
                ping_hurin(
                    f"CI FAILING on PR #{pr_num} ({tid}, {repo}): {names} | <{pr_url}>\n"
                    f"{ci_details}"
                )
            elif passed and review != "CHANGES_REQUESTED":
                # PR is done: CI green AND no outstanding review changes
                # AUTO-SYNC PROJECT BOARD to "Done"
                sync_project_board(task, pr_num, "Done")
                
                ping_hurin(f"PR #{pr_num} ready for review ({tid}, {repo}) | <{pr_url}>")
                task["status"] = "done"
                try:
                    capture_outcome(task)
                except Exception as e:
                    log(f"  WARNING: feedback capture failed: {e}")
                changed = True
                # Label the GitHub issue as done
                issue_num = task.get("issueNumber")
                if issue_num:
                    run(f"{GH_BIN} issue edit {issue_num} --repo patrickkidd/theapp "
                        f"--add-label cf-done --remove-label cf-pr-open 2>/dev/null")
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
                try:
                    capture_outcome(task)
                except Exception as e:
                    log(f"  WARNING: feedback capture failed: {e}")
            else:
                # Read failure context for the respawned agent
                try:
                    failure_path = Path(failure_log)
                    if failure_path.exists():
                        lines = failure_path.read_text().splitlines()
                        failure_context = "\n".join(lines[-50:])
                    else:
                        failure_context = "No diagnostic output captured"
                except Exception:
                    failure_context = "No diagnostic output captured"
                ping_hurin(
                    f"RESPAWN NEEDED — {tid} ({repo}): session died before creating PR. "
                    f"Attempt {respawns + 1}/{MAX_RESPAWNS}.\n"
                    f"Worktree: {task.get('worktree')} | Branch: {branch}\n"
                    f"--- Previous attempt output (last 50 lines) ---\n"
                    f"{failure_context}"
                )
                task["respawnCount"] = respawns + 1
            changed = True

    # --- Worktree cleanup for done tasks ---
    done_tasks = [t for t in tasks if t["status"] in ("done", "timed_out")]
    for task in done_tasks:
        if task.get("worktree") and Path(task["worktree"]).exists():
            cleanup_worktree(task)

    if changed:
        with open(REGISTRY, "w") as f:
            json.dump(data, f, indent=2)


def _has_running_tasks():
    """Check if any task in the registry has status 'running'."""
    if not REGISTRY.exists():
        return False
    try:
        with open(REGISTRY) as f:
            data = json.load(f)
        return any(t["status"] == "running" for t in data.get("tasks", []))
    except (json.JSONDecodeError, KeyError):
        return False


def drain_queue():
    """Pop the next queued task and spawn it if nothing is currently running.

    Called at the end of main() — after the monitoring loop has already
    transitioned tasks (so a task that just finished won't block the drain).
    Re-reads the registry to get the freshest state.
    """
    if not QUEUE_FILE.exists():
        return

    try:
        with open(QUEUE_FILE) as f:
            queue_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        log("WARNING: Could not read task-queue.json")
        return

    queue = queue_data.get("queue", [])
    if not queue:
        return

    # Re-read registry for freshest state (monitoring loop may have changed it)
    if _has_running_tasks():
        log(f"Queue has {len(queue)} task(s) but a task is still running. Waiting.")
        return

    # Pop the first entry
    entry = queue.pop(0)
    task_id = entry["task_id"]
    repo = entry["repo"]
    description = entry["description"]
    prompt_file = entry["prompt_file"]
    actions_file = entry.get("actions_file", "")
    action_index = entry.get("action_index", 0)
    issue_number = entry.get("issue_number", "")

    log(f"Draining queue: spawning {task_id} ({repo})")

    # Read prompt from file
    prompt_path = Path(prompt_file)
    if not prompt_path.exists():
        log(f"  ERROR: Prompt file not found: {prompt_file}. Skipping.")
        # Write queue back without this broken entry
        queue_data["queue"] = queue
        with open(QUEUE_FILE, "w") as f:
            json.dump(queue_data, f, indent=2)
        return

    prompt = prompt_path.read_text()

    # Spawn via spawn-task.sh
    try:
        spawn_cmd = [str(SPAWN_SCRIPT), "--repo", repo, "--task", task_id, "--description", description]
        if issue_number:
            spawn_cmd.extend(["--issue", str(issue_number)])
        result = subprocess.run(
            spawn_cmd,
            input=prompt, text=True, capture_output=True, timeout=120
        )
        if result.returncode != 0:
            log(f"  ERROR: spawn-task.sh failed: {result.stderr}")
            # Leave in queue for retry next cycle
            queue.insert(0, entry)
            queue_data["queue"] = queue
            with open(QUEUE_FILE, "w") as f:
                json.dump(queue_data, f, indent=2)
            return
    except subprocess.TimeoutExpired:
        log(f"  ERROR: spawn-task.sh timed out for {task_id}")
        queue.insert(0, entry)
        queue_data["queue"] = queue
        with open(QUEUE_FILE, "w") as f:
            json.dump(queue_data, f, indent=2)
        return

    log(f"  Spawned {task_id} from queue.")

    # Update action status in the actions file
    if actions_file and Path(actions_file).exists():
        try:
            approved_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            code, _, _ = run(
                f"jq '.actions[{action_index}].status = \"queued\" | "
                f".actions[{action_index}].approved_at = \"{approved_at}\"' "
                f"'{actions_file}' > '{actions_file}.tmp' && mv '{actions_file}.tmp' '{actions_file}'"
            )
        except Exception as e:
            log(f"  WARNING: Could not update action status: {e}")

    # Comment on GitHub issue and update labels
    if issue_number:
        run(
            f"{GH_BIN} issue edit {issue_number} --repo patrickkidd/theapp "
            f"--add-label cf-spawned 2>/dev/null"
        )
        run(
            f"{GH_BIN} issue comment {issue_number} --repo patrickkidd/theapp "
            f"--body '🤖 Auto-spawned from queue as task `{task_id}`. PR incoming.'",
            cwd=str(DEV_REPO)
        )

    # Clean up prompt file
    try:
        prompt_path.unlink()
    except OSError:
        pass

    # Write updated queue
    queue_data["queue"] = queue
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue_data, f, indent=2)

    remaining = len(queue)
    if remaining > 0:
        log(f"  {remaining} task(s) remaining in queue.")


if __name__ == "__main__":
    main()
