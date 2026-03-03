#!/usr/bin/env python3
"""
Task Daemon — replaces spawn-task.sh + check-agents.py + tmux with a single
async Python daemon using the Claude Agent SDK.

Runs as a LaunchAgent (ai.openclaw.taskdaemon). Picks up tasks from
task-queue.json, executes them via SDK query(), streams output to JSONL logs,
and handles post-completion workflows (PR detection, Discord, project sync,
feedback capture).

Key improvements over the old system:
- Errors are typed exceptions, not empty log files
- Streaming messages arrive in real-time
- No tmux, no capture-pane, no shell escaping
- Post-completion runs inline (not 10 min later via cron)
- Orphan recovery on daemon restart
- Queue drain in ≤30s instead of 10 min
- Session persistence enables resume/follow-up
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query, ClaudeSDKClient
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    UserMessage,
    SystemMessage,
)
from claude_agent_sdk.types import TextBlock, ToolUseBlock, ToolResultBlock

from discord_relay import (
    discord_api as _discord_api,
    DiscordThreadRelay,
    load_discord_token,
    set_discord_token,
    get_bot_user_id,
    poll_discord_thread,
    DISCORD_TASKS_CHANNEL_ID,
    DISCORD_QUICKWINS_CHANNEL_ID,
)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

HOME = Path.home()
MONITOR_DIR = HOME / ".openclaw/monitor"
DEV_REPO = HOME / ".openclaw/workspace-hurin/theapp"
REGISTRY = DEV_REPO / ".clawdbot/active-tasks.json"
QUEUE_FILE = MONITOR_DIR / "task-queue.json"
QUEUE_PROMPTS = MONITOR_DIR / "queue-prompts"
TASK_LOGS = MONITOR_DIR / "task-logs"
FAILURES_DIR = MONITOR_DIR / "failures"
DAEMON_LOG = MONITOR_DIR / "daemon.log"
KILL_DIR = MONITOR_DIR / "kill-sentinels"

BOT_TOKEN_FILE = MONITOR_DIR / "hurin-bot-token"

MAX_RESPAWNS = 3
POLL_INTERVAL = 30  # seconds
MAX_TASK_MINUTES = 120

# GitHub project sync
PROJECT_ID = "PVT_kwHOABjmWc4BP0PU"
SCRIPTS_DIR = HOME / ".openclaw/workspace-hurin/scripts"
GH_FIND_SCRIPT = SCRIPTS_DIR / "gh-project-find-item.sh"
GH_SYNC_SCRIPT = SCRIPTS_DIR / "gh-project-sync.sh"
GITHUB_REPO = "patrickkidd/theapp"

# Discord channel IDs imported from discord_relay

# CI fix
CI_FIX_COOLDOWN_FILE = MONITOR_DIR / "ci-fix-cooldown.json"
CI_FIX_COOLDOWN_SECS = 6 * 3600
CI_FIX_REPOS = ["btcopilot", "familydiagram"]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(DAEMON_LOG), mode="a"),
    ],
)
log = logging.getLogger("task-daemon")

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

BOT_TOKEN = ""
DISCORD_BOT_TOKEN = ""

def load_tokens():
    global BOT_TOKEN, DISCORD_BOT_TOKEN
    if BOT_TOKEN_FILE.exists():
        BOT_TOKEN = BOT_TOKEN_FILE.read_text().strip()
        os.environ["GH_TOKEN"] = BOT_TOKEN
    DISCORD_BOT_TOKEN = load_discord_token()

# ---------------------------------------------------------------------------
# Shell helpers (reused from check-agents.py)
# ---------------------------------------------------------------------------

def run(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def post_to_quickwins(message):
    """Post to #quick-wins via Discord bot API."""
    result = _discord_api(
        "POST",
        f"https://discord.com/api/v10/channels/{DISCORD_QUICKWINS_CHANNEL_ID}/messages",
        {"content": message[:2000]},
    )
    if result:
        log.info("  Posted to #quick-wins")


def ping_hurin(msg):
    log.info(f"PINGING HURIN: {msg}")
    code, out, err = run(f"openclaw agent --agent hurin --message {json.dumps(msg)}")
    if code != 0:
        log.warning(f"  ping failed: {err}")



# _discord_api and DiscordThreadRelay imported from discord_relay module


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def load_registry():
    """Load the task registry, creating it if missing."""
    if not REGISTRY.exists():
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY.write_text(json.dumps({"tasks": []}, indent=2))
        return {"tasks": []}
    try:
        return json.loads(REGISTRY.read_text())
    except (json.JSONDecodeError, IOError):
        return {"tasks": []}


def save_registry(data):
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(data, indent=2))


def get_task(data, task_id):
    for t in data.get("tasks", []):
        if t["id"] == task_id:
            return t
    return None


def upsert_task(data, task_entry):
    """Insert or replace a task entry by id."""
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_entry["id"]]
    data["tasks"].append(task_entry)
    save_registry(data)

# ---------------------------------------------------------------------------
# Queue helpers
# ---------------------------------------------------------------------------

def load_queue():
    if not QUEUE_FILE.exists():
        return {"queue": []}
    try:
        return json.loads(QUEUE_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {"queue": []}


def save_queue(data):
    QUEUE_FILE.write_text(json.dumps(data, indent=2))


def pop_queue():
    """Pop the first entry from the queue. Returns (entry, remaining_count) or (None, 0)."""
    qdata = load_queue()
    queue = qdata.get("queue", [])
    if not queue:
        return None, 0
    entry = queue.pop(0)
    qdata["queue"] = queue
    save_queue(qdata)
    return entry, len(queue)

# ---------------------------------------------------------------------------
# Git worktree management
# ---------------------------------------------------------------------------

def create_worktree(repo, task_id, branch):
    """Create a git worktree for a task. Returns (worktree_path, repo_dir)."""
    repo_dir = str(DEV_REPO / repo)
    worktrees_dir = HOME / f".openclaw/workspace-hurin/{repo}-worktrees"
    worktree = str(worktrees_dir / task_id)

    worktrees_dir.mkdir(parents=True, exist_ok=True)

    # Detect default branch
    code, default_branch, _ = run(
        "git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/||'",
        cwd=repo_dir,
    )
    if not default_branch:
        default_branch = "origin/main"

    # Clean up stale worktree/branch
    if Path(worktree).exists():
        log.info(f"  Removing stale worktree: {worktree}")
        run(f"git worktree remove '{worktree}' --force", cwd=repo_dir)
        if Path(worktree).exists():
            import shutil
            shutil.rmtree(worktree, ignore_errors=True)

    run("git worktree prune", cwd=repo_dir)
    code, _, _ = run(f"git show-ref --verify --quiet refs/heads/{branch}", cwd=repo_dir)
    if code == 0:
        run(f"git branch -D '{branch}'", cwd=repo_dir)

    # Create worktree
    code, out, err = run(
        f"git worktree add '{worktree}' -b '{branch}' '{default_branch}'",
        cwd=repo_dir,
    )
    if code != 0:
        raise RuntimeError(f"git worktree add failed: {err}")

    # Symlink .venv
    venv_link = Path(worktree) / ".venv"
    if not venv_link.exists():
        os.symlink(str(DEV_REPO / ".venv"), str(venv_link))

    # Configure git credential helper for bot account
    run(
        "git config credential.helper "
        "'!f() { echo protocol=https; echo host=github.com; "
        "echo username=patrickkidd-hurin; echo \"password=$GH_TOKEN\"; }; f'",
        cwd=worktree,
    )

    return worktree, repo_dir


def cleanup_worktree(task):
    """Remove worktree for completed tasks."""
    worktree = task.get("worktree", "")
    if worktree and Path(worktree).exists():
        repo_dir = task.get("repoDir", str(DEV_REPO))
        code, _, err = run(f"git worktree remove '{worktree}' --force", cwd=repo_dir)
        if code == 0:
            log.info(f"  Cleaned up worktree: {worktree}")
        else:
            log.warning(f"  worktree cleanup failed: {err}")

# ---------------------------------------------------------------------------
# PR detection & CI (ported from check-agents.py)
# ---------------------------------------------------------------------------

def get_pr(branch, repo_dir):
    code, out, _ = run(
        f"gh pr list --head '{branch}' "
        f"--json number,state,url,statusCheckRollup,reviewDecision --limit 1",
        cwd=repo_dir,
    )
    if code == 0 and out and out != "[]":
        prs = json.loads(out)
        if prs:
            return prs[0]
    return None


def get_ci_failure_details(pr_num, repo_dir):
    code, out, _ = run(
        f"gh pr checks {pr_num} --json name,state,conclusion 2>/dev/null",
        cwd=repo_dir,
    )
    if code != 0 or not out:
        return ""
    try:
        checks = json.loads(out)
        failed = [c for c in checks if c.get("conclusion") == "FAILURE"]
        if failed:
            return "CI failures:\n" + "\n".join(f"  - {c['name']}: FAILED" for c in failed)
    except json.JSONDecodeError:
        pass
    return ""


def get_review_comments(pr_num, repo_dir):
    code, out, _ = run(
        f"gh pr view {pr_num} --json reviews --jq '.reviews[-1].body' 2>/dev/null",
        cwd=repo_dir,
    )
    if code == 0 and out:
        return out[:500]
    return ""


HIGH_RISK_PATTERNS = ["auth", "security", "payment", "secret", "migration", "deploy", "config.py"]
MEDIUM_RISK_PATTERNS = ["models/", "engine.py", "routes/", "views/", "api/"]

def score_risk(files_changed):
    if not files_changed:
        return "low"
    paths = " ".join(f.lower() for f in files_changed)
    if any(p in paths for p in HIGH_RISK_PATTERNS):
        return "high"
    if any(p in paths for p in MEDIUM_RISK_PATTERNS) or len(files_changed) > 10:
        return "medium"
    return "low"


def sync_project_board(task, pr_num, status):
    if not GH_FIND_SCRIPT.exists() or not GH_SYNC_SCRIPT.exists():
        return False
    issue_num = task.get("issueNumber")
    if not issue_num:
        return False
    try:
        repo = task.get("repo", "unknown")
        gh_repo = f"patrickkidd/{repo}"
        code, item_id, _ = run(f"bash {GH_FIND_SCRIPT} {gh_repo} {issue_num}")
        if code != 0 or not item_id:
            return False
        status_arg = status if status in ("Todo", "In Progress", "Done") else "Done"
        code, _, err = run(f'bash {GH_SYNC_SCRIPT} {item_id} --status "{status_arg}"')
        if code == 0:
            log.info(f"  Project board synced: issue #{issue_num} -> {status_arg}")
            return True
        else:
            log.warning(f"  Project board sync failed: {err}")
            return False
    except Exception as e:
        log.warning(f"  Project board sync exception: {e}")
        return False

# ---------------------------------------------------------------------------
# Feedback (import from existing module)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(MONITOR_DIR))
from feedback import capture_outcome

# ---------------------------------------------------------------------------
# JSONL log writer
# ---------------------------------------------------------------------------

class TaskLogWriter:
    """Writes structured JSONL to task-logs/<task-id>.log."""

    def __init__(self, task_id):
        TASK_LOGS.mkdir(parents=True, exist_ok=True)
        self.path = TASK_LOGS / f"{task_id}.log"
        self._f = open(self.path, "w")

    def write_event(self, event_type, data=None, **kwargs):
        entry = {
            "type": event_type,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if data:
            entry.update(data)
        entry.update(kwargs)
        self._f.write(json.dumps(entry) + "\n")
        self._f.flush()

    def write_message(self, message):
        """Write an SDK message to the log in a format compatible with `task watch`."""
        ts = datetime.now(timezone.utc).isoformat()

        if isinstance(message, AssistantMessage):
            content_blocks = []
            for block in message.content:
                if isinstance(block, TextBlock):
                    content_blocks.append({"type": "text", "text": block.text})
                elif isinstance(block, ToolUseBlock):
                    content_blocks.append({
                        "type": "tool_use",
                        "name": block.name,
                        "input": block.input,
                    })
                elif isinstance(block, ToolResultBlock):
                    content_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": block.tool_use_id,
                        "is_error": block.is_error,
                    })
            entry = {
                "type": "assistant",
                "message": {"content": content_blocks},
                "ts": ts,
            }
            self._f.write(json.dumps(entry) + "\n")
            self._f.flush()

        elif isinstance(message, ResultMessage):
            entry = {
                "type": "result",
                "session_id": message.session_id,
                "duration_ms": message.duration_ms,
                "num_turns": message.num_turns,
                "is_error": message.is_error,
                "result": message.result,
                "ts": ts,
            }
            self._f.write(json.dumps(entry) + "\n")
            self._f.flush()

        elif isinstance(message, UserMessage):
            entry = {"type": "user", "content": str(message.content), "ts": ts}
            self._f.write(json.dumps(entry) + "\n")
            self._f.flush()

        elif isinstance(message, SystemMessage):
            entry = {"type": "system", "subtype": message.subtype, "ts": ts}
            self._f.write(json.dumps(entry) + "\n")
            self._f.flush()

    def close(self):
        self._f.close()

# ---------------------------------------------------------------------------
# Build task prompt (delivery instructions)
# ---------------------------------------------------------------------------

def build_prompt(raw_prompt, repo, branch, issue_number=None):
    """Wrap the raw prompt with project context and delivery instructions."""
    repo_dir = DEV_REPO / repo
    repo_context = ""
    claude_md = repo_dir / "CLAUDE.md"
    if claude_md.exists():
        lines = claude_md.read_text().splitlines()[:100]
        repo_context = "\n".join(lines)

    issue_line = ""
    if issue_number:
        issue_line = (
            f"4. In the PR description body, include on its own line: "
            f"`Closes patrickkidd/theapp#{issue_number}`\n"
        )

    return f"""{raw_prompt}

## Project Context (auto-injected from {repo}/CLAUDE.md)

{repo_context}

---

## Delivery Instructions (MANDATORY)

After completing the code changes above, you MUST do all of the following:

1. **Commit** all changes on this branch (`{branch}`) with a descriptive message.
2. **Push** the branch to origin: `git push -u origin {branch}`
3. **Create a PR** against master using `gh pr create` with a clear title and description.
{issue_line}
Do NOT stop after editing files. The task is NOT complete until the PR is created.

## PROHIBITED ACTIONS — NEVER DO THESE:

- **NEVER merge any PR** — no `gh pr merge`, no merge buttons, no merge commits. Only Patrick merges.
- **NEVER push to master/main** — only push to your feature branch (`{branch}`).
- **NEVER delete branches** — only Patrick deletes branches.
- **NEVER close issues** — only Patrick closes issues.
- This is a PRODUCTION SYSTEM with paying subscribers. Unauthorized merges can break production.
"""

# ---------------------------------------------------------------------------
# Kill sentinel management
# ---------------------------------------------------------------------------

def check_kill_sentinel(task_id):
    """Check if a .kill sentinel file exists for this task."""
    sentinel = KILL_DIR / f"{task_id}.kill"
    return sentinel.exists()


def clear_kill_sentinel(task_id):
    sentinel = KILL_DIR / f"{task_id}.kill"
    if sentinel.exists():
        sentinel.unlink()

# ---------------------------------------------------------------------------
# Core: run a single task via SDK
# ---------------------------------------------------------------------------

async def run_task(entry, is_respawn=False, respawn_context=""):
    """
    Execute a single task using the Agent SDK.

    For fresh tasks: creates worktree, runs query(), handles completion.
    For respawns: resumes session or re-runs with failure context.
    For follow-ups: resumes session with new prompt.
    """
    task_id = entry["task_id"]
    repo = entry["repo"]
    description = entry.get("description", task_id)
    issue_number = entry.get("issue_number", "")
    branch = entry.get("branch", f"feat/{task_id}")
    session_id_to_resume = entry.get("session_id")  # For follow-ups/respawns
    existing_worktree = entry.get("worktree")  # For respawns

    log.info(f"{'RESPAWN' if is_respawn else 'STARTING'} task: {task_id} ({repo})")

    # --- Set up worktree ---
    if existing_worktree and Path(existing_worktree).exists():
        worktree = existing_worktree
        repo_dir = str(DEV_REPO / repo)
        log.info(f"  Reusing worktree: {worktree}")
    else:
        try:
            worktree, repo_dir = create_worktree(repo, task_id, branch)
        except Exception as e:
            log.error(f"  Worktree creation failed: {e}")
            # Register as failed
            data = load_registry()
            upsert_task(data, {
                "id": task_id,
                "repo": repo,
                "repoDir": repo_dir if 'repo_dir' in dir() else str(DEV_REPO / repo),
                "worktree": "",
                "branch": branch,
                "description": description,
                "startedAt": int(time.time() * 1000),
                "status": "failed",
                "respawnCount": 0,
                "maxMinutes": MAX_TASK_MINUTES,
                "pr": None,
                "issueNumber": int(issue_number) if issue_number else None,
            })
            return

    # --- Read prompt ---
    if session_id_to_resume and entry.get("follow_up_prompt"):
        # Follow-up: use the follow-up prompt directly
        full_prompt = entry["follow_up_prompt"]
    elif is_respawn and respawn_context:
        full_prompt = (
            f"Your previous attempt on this task failed or was incomplete.\n\n"
            f"## Previous attempt output (last 50 lines):\n```\n{respawn_context}\n```\n\n"
            f"Try a different approach. The task was:\n{description}\n\n"
            f"Important: Check if a PR already exists on branch `{branch}` before creating a new one."
        )
    else:
        # Fresh task: read prompt from file or entry
        prompt_file = entry.get("prompt_file", "")
        if prompt_file and Path(prompt_file).exists():
            raw_prompt = Path(prompt_file).read_text()
            # Clean up prompt file
            try:
                Path(prompt_file).unlink()
            except OSError:
                pass
        elif entry.get("prompt"):
            raw_prompt = entry["prompt"]
        else:
            log.error(f"  No prompt found for {task_id}")
            return
        full_prompt = build_prompt(raw_prompt, repo, branch, issue_number)

    # --- Register task ---
    data = load_registry()
    existing = get_task(data, task_id)
    respawn_count = existing.get("respawnCount", 0) if existing else 0
    if is_respawn:
        respawn_count += 1

    task_entry = {
        "id": task_id,
        "repo": repo,
        "repoDir": repo_dir,
        "tmuxSession": "",  # No longer using tmux
        "worktree": worktree,
        "branch": branch,
        "description": description,
        "startedAt": int(time.time() * 1000),
        "status": "running",
        "respawnCount": respawn_count,
        "maxMinutes": MAX_TASK_MINUTES,
        "pr": existing.get("pr") if existing else None,
        "prUrl": existing.get("prUrl") if existing else None,
        "issueNumber": int(issue_number) if issue_number else None,
        "session_id": session_id_to_resume or "",
    }
    upsert_task(data, task_entry)

    # --- Set up logging ---
    log_writer = TaskLogWriter(task_id)
    log_writer.write_event("meta", key="START", task_id=task_id, repo=repo)

    # --- Set up Discord thread relay ---
    discord_relay = DiscordThreadRelay(task_id, description, repo)
    thread_id = discord_relay.create_thread()
    if thread_id:
        discord_relay.set_status("running")
        task_entry["discordThreadId"] = thread_id
        upsert_task(load_registry(), task_entry)  # Save thread_id to registry

        # Post backlink from briefing thread → task thread
        briefing_thread_id = entry.get("briefing_thread_id", "")
        if briefing_thread_id:
            _discord_api(
                "POST",
                f"https://discord.com/api/v10/channels/{briefing_thread_id}/messages",
                {"content": (
                    f"🔗 Task `{task_id}` started — follow progress in <#{thread_id}>"
                )},
            )

    # --- Build SDK options ---
    env = {
        "GH_TOKEN": BOT_TOKEN,
        "PATH": "/opt/homebrew/bin:" + str(HOME / ".local/bin") + ":" + os.environ.get("PATH", ""),
    }
    # CLAUDECODE intentionally absent — prevents nested session detection

    options = ClaudeAgentOptions(
        model="claude-opus-4-6",
        permission_mode="bypassPermissions",
        cwd=worktree,
        env=env,
        cli_path=str(HOME / ".local/bin/claude"),  # Use installed CLI, not bundled
        setting_sources=["project"],  # Loads CLAUDE.md from worktree
    )

    # If resuming a session, set the resume field
    if session_id_to_resume:
        options.resume = session_id_to_resume

    # --- Steering setup ---
    steer_queue = asyncio.Queue()
    poller_task = None
    bot_user_id = get_bot_user_id() if DISCORD_BOT_TOKEN else None

    # --- Run the SDK query (ClaudeSDKClient for steering support) ---
    session_id = ""
    is_error = False
    result_text = ""
    num_turns = 0
    duration_ms = 0
    killed = False

    try:
        async with ClaudeSDKClient(options=options) as client:
            # Start Discord thread poller for live steering
            if thread_id and bot_user_id:
                poller_task = asyncio.create_task(
                    poll_discord_thread(
                        thread_id, steer_queue,
                        bot_user_id=bot_user_id,
                    )
                )

            # Send initial prompt
            await client.query(full_prompt)

            while True:
                steered = False

                async for message in client.receive_response():
                    # Kill sentinel — hard stop, priority over steering
                    if check_kill_sentinel(task_id):
                        log.info(f"  Kill sentinel detected for {task_id}")
                        killed = True
                        break

                    # Log the message
                    log_writer.write_message(message)

                    # Forward to Discord thread
                    discord_relay.on_message(message)

                    # Extract result
                    if isinstance(message, ResultMessage):
                        session_id = message.session_id
                        is_error = message.is_error
                        result_text = message.result or ""
                        num_turns = message.num_turns
                        duration_ms = message.duration_ms
                        break

                    # Non-blocking steer check (soft redirect)
                    try:
                        steer = steer_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        steer = None

                    if steer:
                        await client.interrupt()
                        log.info(f"  Steering {task_id}: {steer[:80]}")
                        log_writer.write_event("steer", content=steer)
                        discord_relay._post(f"📩 **Steering received:**\n> {steer}")
                        discord_relay._post("🔄 Interrupting and redirecting...")
                        discord_relay.set_status("steering")
                        await client.query(f"[STEERING from human operator]: {steer}")
                        discord_relay.set_status("running")
                        steered = True
                        break  # Restart receive_response loop

                if killed:
                    break

                if steered:
                    continue  # Re-enter receive_response loop

                # Response complete — wait for follow-up steering (30s for background tasks)
                try:
                    steer = await asyncio.wait_for(steer_queue.get(), timeout=30.0)
                    log.info(f"  Post-completion follow-up for {task_id}: {steer[:80]}")
                    log_writer.write_event("steer", content=steer, phase="post-completion")
                    discord_relay._post(f"📩 **Follow-up:**\n> {steer}")
                    discord_relay.set_status("steering")
                    await client.query(steer)
                    discord_relay.set_status("running")
                    session_id = ""  # Reset so we re-enter the loop
                    continue
                except asyncio.TimeoutError:
                    break  # No follow-up — done

    except Exception as e:
        is_error = True
        error_type = type(e).__name__
        error_msg = str(e)
        log.error(f"  SDK error ({error_type}): {error_msg}")
        log_writer.write_event("error", error_type=error_type, message=error_msg)

        # Capture stderr if available
        if hasattr(e, "stderr") and e.stderr:
            log_writer.write_event("stderr", content=e.stderr)
        if hasattr(e, "exit_code"):
            log_writer.write_event("meta", key="EXIT_CODE", value=str(e.exit_code))

    finally:
        if poller_task:
            poller_task.cancel()
            try:
                await poller_task
            except asyncio.CancelledError:
                pass
        discord_relay.close()
        log_writer.write_event(
            "meta",
            key="EXIT",
            value=f"error={is_error}",
            session_id=session_id,
            duration_ms=duration_ms,
            num_turns=num_turns,
            killed=killed,
        )
        log_writer.close()
        clear_kill_sentinel(task_id)

    # --- Post-completion ---
    data = load_registry()
    task_entry = get_task(data, task_id)
    if not task_entry:
        log.error(f"  Task {task_id} vanished from registry!")
        return

    # Store session_id for future resume/follow-up
    if session_id:
        task_entry["session_id"] = session_id

    if killed:
        task_entry["status"] = "killed"
        save_registry(data)
        discord_relay.set_status("killed")
        log.info(f"  Task {task_id} killed.")
        return

    # --- Check for PR ---
    pr = get_pr(branch, repo_dir)

    if pr:
        pr_num = pr["number"]
        pr_url = pr["url"]
        task_entry["pr"] = pr_num
        task_entry["prUrl"] = pr_url

        # Score risk
        _, diff_out, _ = run(f"gh pr diff {pr_num} --name-only", cwd=repo_dir)
        files_changed = [f for f in diff_out.splitlines() if f.strip()]
        risk = score_risk(files_changed)
        task_entry["riskLevel"] = risk

        # Check CI and review status
        checks = pr.get("statusCheckRollup") or []
        review = pr.get("reviewDecision", "")
        failed = [c for c in checks if c.get("conclusion") == "FAILURE"]
        pending = [c for c in checks if c.get("status") == "IN_PROGRESS"]
        passed = checks and not failed and not pending

        if passed and review != "CHANGES_REQUESTED":
            task_entry["status"] = "done"
            sync_project_board(task_entry, pr_num, "Done")
            ping_hurin(f"PR #{pr_num} ready for review ({task_id}, {repo}) | <{pr_url}>")
            try:
                capture_outcome(task_entry)
            except Exception as e:
                log.warning(f"  feedback capture failed: {e}")
            # Label issue
            issue_num = task_entry.get("issueNumber")
            if issue_num:
                run(f"gh issue edit {issue_num} --repo {GITHUB_REPO} "
                    f"--add-label cf-done --remove-label cf-pr-open 2>/dev/null")
        else:
            task_entry["status"] = "pr_open"
            # Label issue
            issue_num = task_entry.get("issueNumber")
            if issue_num:
                run(f"gh issue edit {issue_num} --repo {GITHUB_REPO} "
                    f"--add-label cf-pr-open --remove-label cf-spawned 2>/dev/null")

            if failed:
                ci_details = get_ci_failure_details(pr_num, repo_dir)
                ping_hurin(
                    f"CI FAILING on PR #{pr_num} ({task_id}, {repo}) | <{pr_url}>\n"
                    f"{ci_details}"
                )
            elif review == "CHANGES_REQUESTED":
                review_body = get_review_comments(pr_num, repo_dir)
                ping_hurin(
                    f"CHANGES REQUESTED on PR #{pr_num} ({task_id}, {repo}) | <{pr_url}>\n"
                    f"Review feedback: {review_body}"
                )

        # Post to #quick-wins
        risk_emoji = {"high": "🔴 HIGH RISK", "medium": "🟡 MEDIUM RISK", "low": "🟢 LOW RISK"}[risk]
        desc = task_entry.get("description", task_id)
        post_to_quickwins(
            f"{risk_emoji} ✅ **PR ready for review:** {desc}\n"
            f"   → <{pr_url}>"
        )

        # Post PR link to Discord thread
        discord_relay.post_pr(pr_url, risk)

        # Update Discord thread status
        if task_entry["status"] == "done":
            discord_relay.set_status("done")
        else:
            discord_relay.set_status("pr_open")

        save_registry(data)
        log.info(f"  Task {task_id} completed with PR #{pr_num}: {pr_url}")

    elif is_error:
        # No PR and errored — attempt respawn
        if task_entry["respawnCount"] < MAX_RESPAWNS:
            log.info(f"  Task {task_id} failed, scheduling respawn "
                     f"({task_entry['respawnCount'] + 1}/{MAX_RESPAWNS})")
            task_entry["status"] = "respawn_pending"
            save_registry(data)
            discord_relay.set_status("respawn")

            # Read failure context from log
            failure_context = _get_failure_context(task_id)
            ping_hurin(
                f"RESPAWN NEEDED — {task_id} ({repo}): task failed before creating PR. "
                f"Attempt {task_entry['respawnCount'] + 1}/{MAX_RESPAWNS}.\n"
                f"Worktree: {worktree} | Branch: {branch}"
            )
        else:
            task_entry["status"] = "failed"
            save_registry(data)
            discord_relay.set_status("failed")
            ping_hurin(
                f"FAILED — {task_id} ({repo}): task failed, no PR, "
                f"max respawns ({MAX_RESPAWNS}) reached."
            )
            try:
                capture_outcome(task_entry)
            except Exception as e:
                log.warning(f"  feedback capture failed: {e}")
    else:
        # Completed without error but no PR found — might need a second check
        # Sometimes GH API is slow to index the PR
        log.info(f"  Task {task_id} finished (no error) but no PR detected. Will recheck.")
        await asyncio.sleep(15)
        pr = get_pr(branch, repo_dir)
        if pr:
            pr_num = pr["number"]
            pr_url = pr["url"]
            task_entry["pr"] = pr_num
            task_entry["prUrl"] = pr_url
            task_entry["status"] = "pr_open"
            save_registry(data)
            discord_relay.set_status("pr_open")
            log.info(f"  PR #{pr_num} found on recheck: {pr_url}")
            # Let the monitoring pass handle the rest
        else:
            log.warning(f"  Task {task_id} completed but no PR found even after recheck.")
            if task_entry["respawnCount"] < MAX_RESPAWNS:
                task_entry["status"] = "respawn_pending"
                save_registry(data)
                discord_relay.set_status("respawn")
            else:
                task_entry["status"] = "failed"
                save_registry(data)
                discord_relay.set_status("failed")
                try:
                    capture_outcome(task_entry)
                except Exception as e:
                    log.warning(f"  feedback capture failed: {e}")


def _get_failure_context(task_id):
    """Read the last 50 lines of a task log for respawn context."""
    log_file = TASK_LOGS / f"{task_id}.log"
    if not log_file.exists():
        return "No diagnostic output captured"
    try:
        lines = log_file.read_text().splitlines()
        return "\n".join(lines[-50:])
    except Exception:
        return "No diagnostic output captured"

# ---------------------------------------------------------------------------
# Monitoring pass: check pr_open tasks (replaces parts of check-agents.py)
# ---------------------------------------------------------------------------

def monitor_open_prs():
    """Check pr_open tasks for CI/review status changes."""
    data = load_registry()
    changed = False

    for task in data.get("tasks", []):
        if task["status"] != "pr_open":
            continue

        tid = task["id"]
        branch = task["branch"]
        repo_dir = task.get("repoDir", str(DEV_REPO))
        pr_num = task.get("pr")

        if not pr_num:
            continue

        pr = get_pr(branch, repo_dir)
        if not pr:
            continue

        checks = pr.get("statusCheckRollup") or []
        review = pr.get("reviewDecision", "")
        failed = [c for c in checks if c.get("conclusion") == "FAILURE"]
        pending = [c for c in checks if c.get("status") == "IN_PROGRESS"]
        passed = checks and not failed and not pending

        if passed and review != "CHANGES_REQUESTED":
            task["status"] = "done"
            sync_project_board(task, pr_num, "Done")
            ping_hurin(f"PR #{pr_num} ready for review ({tid}, {task.get('repo')}) | <{task.get('prUrl')}>")
            try:
                capture_outcome(task)
            except Exception as e:
                log.warning(f"  feedback capture failed: {e}")
            issue_num = task.get("issueNumber")
            if issue_num:
                run(f"gh issue edit {issue_num} --repo {GITHUB_REPO} "
                    f"--add-label cf-done --remove-label cf-pr-open 2>/dev/null")
            changed = True

    # Clean up worktrees for done tasks
    for task in data.get("tasks", []):
        if task["status"] in ("done", "timed_out") and task.get("worktree") and Path(task["worktree"]).exists():
            cleanup_worktree(task)

    if changed:
        save_registry(data)

# ---------------------------------------------------------------------------
# Orphan recovery
# ---------------------------------------------------------------------------

def recover_orphans():
    """On startup, check for 'running' tasks that have no active process."""
    data = load_registry()
    changed = False

    for task in data.get("tasks", []):
        if task["status"] != "running":
            continue

        tid = task["id"]
        branch = task["branch"]
        repo_dir = task.get("repoDir", str(DEV_REPO))

        log.info(f"Orphan check: {tid}")

        # Check if a PR exists
        pr = get_pr(branch, repo_dir)
        if pr:
            pr_num = pr["number"]
            pr_url = pr["url"]
            task["pr"] = pr_num
            task["prUrl"] = pr_url
            task["status"] = "pr_open"
            log.info(f"  Orphan {tid}: PR #{pr_num} found, marking pr_open")
            changed = True
        elif task.get("respawnCount", 0) < MAX_RESPAWNS:
            task["status"] = "respawn_pending"
            log.info(f"  Orphan {tid}: no PR, marking for respawn")
            changed = True
        else:
            task["status"] = "failed"
            log.info(f"  Orphan {tid}: no PR, max respawns, marking failed")
            changed = True

    if changed:
        save_registry(data)

# ---------------------------------------------------------------------------
# CI fix (ported from check-agents.py)
# ---------------------------------------------------------------------------

STALE_THRESHOLD_MINUTES = 60  # No log activity for 1 hour = stale

def detect_stale_tasks():
    """Detect tasks stuck in 'running' with no recent log activity.

    Marks stale tasks as failed and updates their Discord thread status.
    A task is considered stale if its log file hasn't been modified in
    STALE_THRESHOLD_MINUTES.
    """
    data = load_registry()
    changed = False
    now = time.time()

    for task in data.get("tasks", []):
        if task["status"] != "running":
            continue

        tid = task["id"]
        log_file = TASK_LOGS / f"{tid}.log"

        if log_file.exists():
            mtime = log_file.stat().st_mtime
            age_min = (now - mtime) / 60
            if age_min < STALE_THRESHOLD_MINUTES:
                continue  # Recently active — not stale
        else:
            # No log file at all for a "running" task — started_at check
            started = task.get("started_at", "")
            if started:
                try:
                    start_ts = datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp()
                    age_min = (now - start_ts) / 60
                    if age_min < STALE_THRESHOLD_MINUTES:
                        continue
                except (ValueError, TypeError):
                    pass

        # Task is stale
        log.warning(f"Stale task detected: {tid} (no log activity for >{STALE_THRESHOLD_MINUTES}min)")

        # Update Discord thread if we have one
        thread_id = task.get("discordThreadId")
        if thread_id:
            _discord_api(
                "PATCH",
                f"https://discord.com/api/v10/channels/{thread_id}",
                {"name": f"💀 {tid}"},
            )
            _discord_api(
                "POST",
                f"https://discord.com/api/v10/channels/{thread_id}/messages",
                {"content": f"## ⚠️ Task stale\nNo log activity for >{STALE_THRESHOLD_MINUTES} minutes. Marking as failed."},
            )

        task["status"] = "failed"
        changed = True
        ping_hurin(f"STALE — {tid} ({task.get('repo', '?')}): no activity for >{STALE_THRESHOLD_MINUTES}min, marked failed.")

    if changed:
        save_registry(data)


def check_master_ci():
    """Auto-enqueue CI fix tasks when master is failing."""
    cooldowns = {}
    if CI_FIX_COOLDOWN_FILE.exists():
        try:
            cooldowns = json.loads(CI_FIX_COOLDOWN_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            cooldowns = {}

    data = load_registry()
    running_fix_ids = {
        t.get("repo", "")
        for t in data.get("tasks", [])
        if t["status"] == "running" and t["id"].startswith("fix-ci-")
    }

    cooldown_changed = False

    for repo in CI_FIX_REPOS:
        repo_dir = str(DEV_REPO / repo)

        if repo in running_fix_ids:
            continue

        last_spawn = cooldowns.get(repo, 0)
        if time.time() - last_spawn < CI_FIX_COOLDOWN_SECS:
            continue

        code, out, _ = run(
            "gh run list --branch master --limit 1 --json conclusion,databaseId",
            cwd=repo_dir,
        )
        if code != 0 or not out:
            continue

        try:
            runs = json.loads(out)
        except json.JSONDecodeError:
            continue

        if not runs or runs[0].get("conclusion") != "failure":
            continue

        run_id = runs[0].get("databaseId", "")
        log.info(f"  CI-fix: {repo} master CI FAILED (run {run_id}). Enqueuing fix task.")

        _, fail_log, _ = run(
            f"gh run view {run_id} --log-failed 2>/dev/null | tail -50",
            cwd=repo_dir,
        )

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        task_id = f"fix-ci-{repo}-{ts}"
        prompt = (
            f"The master branch CI is failing in {repo}.\n\n"
            f"## Failure log (last 50 lines)\n```\n{fail_log}\n```\n\n"
            f"Diagnose the failure, fix it, and ensure CI passes.\n"
            f"Run the failing tests locally before pushing.\n"
        )

        # Enqueue instead of spawning directly
        qdata = load_queue()
        QUEUE_PROMPTS.mkdir(parents=True, exist_ok=True)
        prompt_path = QUEUE_PROMPTS / f"{task_id}.txt"
        prompt_path.write_text(prompt)

        qdata.setdefault("queue", []).append({
            "task_id": task_id,
            "repo": repo,
            "description": f"Auto-fix master CI for {repo}",
            "prompt_file": str(prompt_path),
            "issue_number": "",
            "queued_at": datetime.now(timezone.utc).isoformat(),
        })
        save_queue(qdata)

        cooldowns[repo] = time.time()
        cooldown_changed = True

    if cooldown_changed:
        CI_FIX_COOLDOWN_FILE.write_text(json.dumps(cooldowns, indent=2))

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def main_loop():
    """The daemon's main loop: drain queue, run tasks, monitor, repeat."""
    KILL_DIR.mkdir(parents=True, exist_ok=True)
    TASK_LOGS.mkdir(parents=True, exist_ok=True)
    FAILURES_DIR.mkdir(parents=True, exist_ok=True)
    QUEUE_PROMPTS.mkdir(parents=True, exist_ok=True)

    load_tokens()
    log.info("Task daemon starting.")

    # --- Orphan recovery ---
    recover_orphans()

    loop_count = 0

    while True:
        try:
            # --- Check for respawn-pending tasks ---
            data = load_registry()
            respawn_task = None
            for t in data.get("tasks", []):
                if t["status"] == "respawn_pending":
                    respawn_task = t
                    break

            if respawn_task:
                failure_context = _get_failure_context(respawn_task["id"])
                entry = {
                    "task_id": respawn_task["id"],
                    "repo": respawn_task["repo"],
                    "description": respawn_task["description"],
                    "issue_number": str(respawn_task.get("issueNumber", "") or ""),
                    "branch": respawn_task["branch"],
                    "worktree": respawn_task.get("worktree", ""),
                    "session_id": respawn_task.get("session_id", ""),
                }
                await run_task(entry, is_respawn=True, respawn_context=failure_context)
                continue  # Don't sleep — check for more work immediately

            # --- Check for running tasks (only one at a time) ---
            has_running = any(
                t["status"] == "running"
                for t in data.get("tasks", [])
            )

            if not has_running:
                # --- Drain queue ---
                entry, remaining = pop_queue()

                if entry:
                    task_id = entry["task_id"]
                    log.info(f"Dequeued: {task_id} ({remaining} remaining)")

                    # Update action status if applicable
                    actions_file = entry.get("actions_file", "")
                    action_index = entry.get("action_index", 0)
                    if actions_file and Path(actions_file).exists():
                        try:
                            approved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                            run(
                                f"jq '.actions[{action_index}].status = \"queued\" | "
                                f".actions[{action_index}].approved_at = \"{approved_at}\"' "
                                f"'{actions_file}' > '{actions_file}.tmp' && "
                                f"mv '{actions_file}.tmp' '{actions_file}'"
                            )
                        except Exception as e:
                            log.warning(f"  Could not update action status: {e}")

                    # Comment on GitHub issue
                    issue_number = entry.get("issue_number", "")
                    if issue_number:
                        run(
                            f"gh issue edit {issue_number} --repo {GITHUB_REPO} "
                            f"--add-label cf-spawned 2>/dev/null"
                        )
                        run(
                            f"gh issue comment {issue_number} --repo {GITHUB_REPO} "
                            f"--body '🤖 Auto-spawned from queue as task `{task_id}`. PR incoming.'",
                            cwd=str(DEV_REPO),
                        )

                    await run_task(entry)
                    continue  # Check for more work immediately

            # --- Monitor open PRs (every 5th cycle = ~2.5 min) ---
            if loop_count % 5 == 0:
                monitor_open_prs()

            # --- Stale task detection (every 10th cycle = ~5 min) ---
            if loop_count % 10 == 0:
                detect_stale_tasks()

            # --- Check master CI (every 20th cycle = ~10 min) ---
            if loop_count % 20 == 0:
                check_master_ci()

            loop_count += 1
            await asyncio.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log.info("Daemon shutting down (KeyboardInterrupt).")
            break
        except Exception as e:
            log.error(f"Main loop error: {type(e).__name__}: {e}")
            await asyncio.sleep(POLL_INTERVAL)


def main():
    """Entry point."""
    asyncio.run(main_loop())


if __name__ == "__main__":
    main()
