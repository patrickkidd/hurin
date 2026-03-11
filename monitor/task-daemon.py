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
    load_channel_threads,
    save_channel_threads,
    post_to_channel_thread,
    DISCORD_TASKS_CHANNEL_ID,
    DISCORD_QUICKWINS_CHANNEL_ID,
    DISCORD_GUILD_ID,
)
from trust_ledger import (
    record_proposal, record_outcome, get_summary as trust_summary,
    update_spawn_policy, store_prompt_text,
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
TASK_EVENTS = MONITOR_DIR / "task-events.jsonl"

BOT_TOKEN_FILE = MONITOR_DIR / "hurin-bot-token"

MAX_RESPAWNS = 3
POLL_INTERVAL = 30  # seconds
MAX_TASK_MINUTES = 120

# GitHub project sync
PROJECT_ID = "PVT_kwHOABjmWc4BP0PU"
SCRIPTS_DIR = HOME / ".openclaw/workspace-hurin/scripts"
GH_FIND_SCRIPT = SCRIPTS_DIR / "gh-project-find-item.sh"
GH_SYNC_SCRIPT = SCRIPTS_DIR / "gh-project-sync.sh"
GH_BIN = HOME / ".local/bin/gh"
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


def _post_reply_to_channel(channel_id, task_id, result_text, thread_id=None):
    """Post a follow-up result back to the originating Discord channel.

    Used by skill follow-ups (cos, cofounder, teamlead) so the response
    appears in the channel where the user asked, not just in #tasks.
    """
    # Build a concise reply with link to full thread
    thread_link = f"https://discord.com/channels/{DISCORD_GUILD_ID}/{thread_id}" if thread_id else ""

    # Truncate result for channel post (keep it readable)
    max_len = 1800
    text = result_text.strip()
    if len(text) > max_len:
        text = text[:max_len] + "\n\n*(truncated — see full response in thread)*"

    header = f"**Follow-up result** (`{task_id}`)"
    if thread_link:
        header += f" · [full thread]({thread_link})"

    content = f"{header}\n\n{text}"

    discord_api(
        "POST",
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        {"content": content[:2000]},
    )
    log.info(f"  Reply posted to channel {channel_id} for {task_id}")


# ---------------------------------------------------------------------------
# Event emission (for team-lead daemon)
# ---------------------------------------------------------------------------

def emit_event(event_type, **kwargs):
    """Append a structured event to task-events.jsonl for the team-lead daemon."""
    entry = {
        "event": event_type,
        "ts": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }
    try:
        with open(TASK_EVENTS, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except IOError as e:
        log.warning(f"Failed to emit event {event_type}: {e}")


# ---------------------------------------------------------------------------
# Collective Intelligence: Episode capture
# ---------------------------------------------------------------------------

def capture_episode(task_entry, result_text=""):
    """Record task outcome as an episode in the CI episodic memory.
    Extracts lessons from the result text and writes to episodes.jsonl."""
    try:
        from shared_memory import append_episode
        task_id = task_entry.get("id", "unknown")
        repo = task_entry.get("repo", "unknown")
        status = task_entry.get("status", "unknown")

        # Map daemon statuses to episode outcomes
        outcome_map = {"done": "merged", "failed": "abandoned", "killed": "killed"}
        outcome = outcome_map.get(status, status)
        if task_entry.get("pr") and status == "done":
            outcome = "merged"
        elif not task_entry.get("pr") and status == "done":
            outcome = "completed_no_pr"

        # Duration in hours
        started_at = task_entry.get("startedAt", 0)
        duration_hrs = 0
        if started_at:
            duration_hrs = (time.time() * 1000 - started_at) / (1000 * 3600)

        # Extract lessons from result text (simple heuristic — look for key phrases)
        lessons = []
        if result_text:
            # Look for lines that contain lesson-like patterns
            for line in result_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                lower = line.lower()
                if any(kw in lower for kw in [
                    "lesson", "learned", "note:", "important:", "gotcha",
                    "workaround", "the fix was", "root cause", "the issue was",
                    "key insight", "takeaway",
                ]):
                    lessons.append(line[:200])
                    if len(lessons) >= 5:
                        break
        if not lessons:
            desc = task_entry.get("description", "")
            if outcome == "merged":
                lessons.append(f"Task completed successfully: {desc[:150]}")
            elif outcome == "abandoned":
                lessons.append(f"Task failed: {desc[:150]}")

        # Tags from repo and description
        tags = [repo.split("/")[-1] if "/" in repo else repo]
        desc_lower = task_entry.get("description", "").lower()
        for tag in ["auth", "qml", "testing", "ci", "refactor", "bug", "feature", "ui"]:
            if tag in desc_lower:
                tags.append(tag)

        append_episode(
            task_id=task_id,
            repo=repo,
            outcome=outcome,
            duration_hrs=duration_hrs,
            lessons=lessons,
            tags=tags,
            spawned_by=task_entry.get("spawnedBy", "huor"),
        )
        log.info(f"CI: Episode captured for {task_id} ({outcome})")
    except Exception as e:
        log.warning(f"CI episode capture failed (non-fatal): {e}")


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
        f"{GH_BIN} pr list --head '{branch}' "
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
        f"{GH_BIN} pr checks {pr_num} --json name,state,conclusion 2>/dev/null",
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
        f"{GH_BIN} pr view {pr_num} --json reviews --jq '.reviews[-1].body' 2>/dev/null",
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
    # Force Max plan by clearing API key
    os.environ.pop("ANTHROPIC_API_KEY", None)

    task_id = entry["task_id"]
    repo = entry["repo"]
    description = entry.get("description", task_id)
    issue_number = entry.get("issue_number", "")
    branch = entry.get("branch", f"feat/{task_id}")
    session_id_to_resume = entry.get("session_id")  # For follow-ups/respawns
    existing_worktree = entry.get("worktree")  # For respawns
    reply_channel_id = entry.get("reply_channel_id")  # For channel-targeted replies

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
        "discordThreadId": entry.get("discordThreadId") or (existing.get("discordThreadId") if existing else None),
    }
    upsert_task(data, task_entry)

    # --- Set up logging ---
    log_writer = TaskLogWriter(task_id)
    log_writer.write_event("meta", key="START", task_id=task_id, repo=repo)

    # --- Set up Discord thread relay ---
    discord_relay = DiscordThreadRelay(task_id, description, repo)

    # Reuse existing thread on respawn/follow-up
    existing_thread_id = entry.get("discordThreadId") or (existing and existing.get("discordThreadId"))
    if existing_thread_id:
        discord_relay.thread_id = existing_thread_id
        thread_id = existing_thread_id
        prefix = "🔁 Respawn" if is_respawn else "📩 Follow-up"
        discord_relay._post(f"## {prefix}\nResuming in this thread.")
        discord_relay.set_status("running")
        log.info(f"  Reusing Discord thread: {thread_id}")
    else:
        thread_id = discord_relay.create_thread()

    if thread_id and not existing_thread_id:
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
        "PATH": "/usr/local/bin:" + str(HOME / ".local/bin") + ":" + os.environ.get("PATH", ""),
        "ANTHROPIC_API_KEY": "",  # Force Max plan — SDK merges os.environ first, this overrides
    }
    # Only set GH_TOKEN if we have a bot token; otherwise let gh use system auth
    if BOT_TOKEN:
        env["GH_TOKEN"] = BOT_TOKEN
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

            # Post prompt to Discord thread for visibility
            if is_respawn:
                prompt_label = "Respawn Prompt"
            elif session_id_to_resume and entry.get("follow_up_prompt"):
                prompt_label = "Follow-up Prompt"
            else:
                prompt_label = "System Prompt"
            discord_relay.post_prompt(full_prompt, label=prompt_label)

            # Send initial prompt
            await client.query(full_prompt)

            was_steered = False  # Track if the last response was from a steer

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
                        was_steered = True
                        break  # Restart receive_response loop

                if killed:
                    break

                if steered:
                    continue  # Re-enter receive_response loop

                # After a steered response completes, CC often stops instead
                # of continuing the original task. Auto-resume instead of
                # falling through to the follow-up timeout.
                if was_steered:
                    was_steered = False
                    log.info(f"  Auto-resuming {task_id} after steer")
                    discord_relay._post("🔄 Resuming original task...")
                    await client.query(
                        "[SYSTEM]: The steering message has been addressed. "
                        "Now continue working on your original task. "
                        "The task is NOT complete until you have created and pushed the PR."
                    )
                    continue

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

    # --- Reply to originating channel (for skill follow-ups) ---
    if reply_channel_id and result_text and not is_error:
        _post_reply_to_channel(reply_channel_id, task_id, result_text,
                               discord_relay.thread_id)

    if killed:
        task_entry["status"] = "killed"
        save_registry(data)
        emit_event("task_killed", task_id=task_id, repo=repo)
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
        _, diff_out, _ = run(f"{GH_BIN} pr diff {pr_num} --name-only", cwd=repo_dir)
        files_changed = [f for f in diff_out.splitlines() if f.strip()]
        risk = score_risk(files_changed)
        task_entry["riskLevel"] = risk

        # Check CI and review status
        checks = pr.get("statusCheckRollup") or []
        review = pr.get("reviewDecision", "")
        failed = [c for c in checks if c.get("conclusion") == "FAILURE"]
        pending = [c for c in checks if c.get("status") == "IN_PROGRESS"]
        passed = checks and not failed and not pending

        emit_event("pr_created", task_id=task_id, repo=repo, pr_number=pr_num, pr_url=pr_url)

        if passed and review != "CHANGES_REQUESTED":
            task_entry["status"] = "done"
            emit_event("task_completed", task_id=task_id, repo=repo, pr_number=pr_num)
            sync_project_board(task_entry, pr_num, "Done")
            ping_hurin(f"PR #{pr_num} ready for review ({task_id}, {repo}) | <{pr_url}>")
            try:
                capture_outcome(task_entry)
            except Exception as e:
                log.warning(f"  feedback capture failed: {e}")
            capture_episode(task_entry, result_text)
            # Label issue
            issue_num = task_entry.get("issueNumber")
            if issue_num:
                run(f"{GH_BIN} issue edit {issue_num} --repo {GITHUB_REPO} "
                    f"--add-label cf-done --remove-label cf-pr-open 2>/dev/null")
        else:
            task_entry["status"] = "pr_open"
            # Label issue
            issue_num = task_entry.get("issueNumber")
            if issue_num:
                run(f"{GH_BIN} issue edit {issue_num} --repo {GITHUB_REPO} "
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

        # Post to #quick-wins (only once per task)
        if not task_entry.get("quickwinsPosted"):
            risk_emoji = {"high": "🔴 HIGH RISK", "medium": "🟡 MEDIUM RISK", "low": "🟢 LOW RISK"}[risk]
            desc = task_entry.get("description", task_id)
            post_to_quickwins(
                f"{risk_emoji} ✅ **PR ready for review:** {desc}\n"
                f"   → <{pr_url}>"
            )
            task_entry["quickwinsPosted"] = True

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
            emit_event("task_respawned", task_id=task_id, repo=repo,
                       respawn_count=task_entry["respawnCount"] + 1)
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
            emit_event("task_failed", task_id=task_id, repo=repo,
                       respawn_count=task_entry["respawnCount"])
            discord_relay.set_status("failed")
            ping_hurin(
                f"FAILED — {task_id} ({repo}): task failed, no PR, "
                f"max respawns ({MAX_RESPAWNS}) reached."
            )
            try:
                capture_outcome(task_entry)
            except Exception as e:
                log.warning(f"  feedback capture failed: {e}")
            capture_episode(task_entry, result_text)
    else:
        # Completed without error but no PR found — recheck once (GH API can be slow)
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
            emit_event("pr_created", task_id=task_id, repo=repo, pr_number=pr_num, pr_url=pr_url)
            discord_relay.set_status("pr_open")
            log.info(f"  PR #{pr_num} found on recheck: {pr_url}")
        else:
            # No error + no PR = task legitimately completed without code changes
            # (e.g. evaluation tasks, investigations, "no change needed" conclusions)
            task_entry["status"] = "done"
            save_registry(data)
            emit_event("task_completed", task_id=task_id, repo=repo)
            discord_relay.set_status("done")
            log.info(f"  Task {task_id} completed successfully (no PR needed).")
            ping_hurin(
                f"Task `{task_id}` ({repo}) completed without a PR. "
                f"CC determined no code changes were needed. "
                f"Result: {result_text[:300]}"
            )
            try:
                capture_outcome(task_entry)
            except Exception as e:
                log.warning(f"  feedback capture failed: {e}")
            capture_episode(task_entry, result_text)


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
            emit_event("task_completed", task_id=tid, repo=task.get("repo", ""),
                       pr_number=pr_num)
            sync_project_board(task, pr_num, "Done")
            ping_hurin(f"PR #{pr_num} ready for review ({tid}, {task.get('repo')}) | <{task.get('prUrl')}>")
            try:
                capture_outcome(task)
            except Exception as e:
                log.warning(f"  feedback capture failed: {e}")
            capture_episode(task)
            issue_num = task.get("issueNumber")
            if issue_num:
                run(f"{GH_BIN} issue edit {issue_num} --repo {GITHUB_REPO} "
                    f"--add-label cf-done --remove-label cf-pr-open 2>/dev/null")
            changed = True

    # --- Track PR outcomes for trust ledger ---
    for task in data.get("tasks", []):
        if task["status"] not in ("done", "pr_open"):
            continue
        if task.get("_outcome_recorded"):
            continue

        pr_num = task.get("pr")
        if not pr_num:
            continue

        repo_dir = task.get("repoDir", str(DEV_REPO))
        tid = task["id"]

        # Check PR state via gh
        rc, out, _ = run(f"{GH_BIN} pr view {pr_num} --json state,mergedAt,closedAt", cwd=repo_dir)
        if rc != 0:
            continue
        try:
            pr_state = json.loads(out)
        except json.JSONDecodeError:
            continue

        state = pr_state.get("state", "").upper()

        if state == "MERGED":
            # Record as spawn proposal that was correct (merged)
            record_outcome(f"spawn:{tid}", "correct", detail=f"PR #{pr_num} merged")
            task["_outcome_recorded"] = True
            task["status"] = "done"
            changed = True
            log.info(f"  Trust ledger: {tid} PR #{pr_num} merged (correct)")

            # Sync board item to Done
            sync_project_board(task, pr_num, "Done")

            # Close linked issue if PR didn't auto-close it
            issue_num = task.get("issueNumber")
            if issue_num:
                repo = task.get("repo", "")
                if repo:
                    run(f"{GH_BIN} issue close {issue_num} --repo patrickkidd/{repo} 2>/dev/null")
                    run(f"{GH_BIN} issue edit {issue_num} --repo patrickkidd/{repo} "
                        f"--add-label cf-done --remove-label cf-pr-open 2>/dev/null")

            # Notify in task thread
            thread_id = task.get("discordThreadId")
            if thread_id:
                _discord_api(
                    "POST",
                    f"https://discord.com/api/v10/channels/{thread_id}/messages",
                    {"content": f"✅ PR #{pr_num} was **merged**. Board synced to Done."},
                )

        elif state == "CLOSED":
            record_outcome(f"spawn:{tid}", "wrong", detail=f"PR #{pr_num} closed without merge")
            task["_outcome_recorded"] = True
            task["status"] = "closed"
            changed = True
            log.info(f"  Trust ledger: {tid} PR #{pr_num} closed (wrong)")

            # Sync board item back to Todo (closed PR = work not done)
            sync_project_board(task, pr_num, "Todo")

            # Update labels
            issue_num = task.get("issueNumber")
            if issue_num:
                repo = task.get("repo", "")
                if repo:
                    run(f"{GH_BIN} issue edit {issue_num} --repo patrickkidd/{repo} "
                        f"--remove-label cf-pr-open 2>/dev/null")

            thread_id = task.get("discordThreadId")
            if thread_id:
                _discord_api(
                    "POST",
                    f"https://discord.com/api/v10/channels/{thread_id}/messages",
                    {"content": f"❌ PR #{pr_num} was **closed** without merge. Board reverted to Todo."},
                )

    # Update spawn policy after recording outcomes
    if changed:
        try:
            policy_changes = update_spawn_policy()
            for pc in policy_changes:
                log.info(
                    f"  Spawn policy: {pc['category']} {pc['old']} -> {pc['new']} "
                    f"(accuracy={pc['accuracy']}, n={pc['total']})"
                )
        except Exception as e:
            log.warning(f"  Spawn policy update failed: {e}")

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

        if not Path(repo_dir).exists():
            continue

        if repo in running_fix_ids:
            continue

        last_spawn = cooldowns.get(repo, 0)
        if time.time() - last_spawn < CI_FIX_COOLDOWN_SECS:
            continue

        code, out, _ = run(
            f"{GH_BIN} run list --branch master --limit 1 --json conclusion,databaseId",
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
            f"{GH_BIN} run view {run_id} --log-failed 2>/dev/null | tail -50",
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
# PR comment monitoring — auto follow-up from GitHub PR comments
# ---------------------------------------------------------------------------

PR_COMMENT_MAX_AGE = 7 * 24 * 3600  # Watch PRs from last 7 days
PR_COOLDOWN_SECS = 30 * 60  # 30 min cooldown after processing comments on a PR
PR_COOLDOWN_FILE = MONITOR_DIR / "pr-comment-cooldowns.json"
BOT_GITHUB_USER = "patrickkidd-hurin"
BOSS_GITHUB_USER = "patrickkidd"
REVIEWED_BY_CLAUDE_LABEL = "reviewed-by-claude"
PR_MENTION_REPOS = ["patrickkidd/familydiagram", "patrickkidd/btcopilot", "patrickkidd/fdserver"]

# Persistent tracking for PR comments (survives restarts)
PR_COMMENT_CURSOR_FILE = MONITOR_DIR / "pr-comment-cursors.json"
PR_MENTION_CURSOR_FILE = MONITOR_DIR / "pr-mention-cursors.json"

_pr_followup_pending = set()
_pr_mention_pending = set()


def _load_pr_comment_cursors():
    if PR_COMMENT_CURSOR_FILE.exists():
        try:
            return json.loads(PR_COMMENT_CURSOR_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_pr_comment_cursors(cursors):
    PR_COMMENT_CURSOR_FILE.write_text(json.dumps(cursors, indent=2))


def _load_pr_mention_cursors():
    if PR_MENTION_CURSOR_FILE.exists():
        try:
            return json.loads(PR_MENTION_CURSOR_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_pr_mention_cursors(cursors):
    PR_MENTION_CURSOR_FILE.write_text(json.dumps(cursors, indent=2))


def _load_pr_cooldowns():
    """Load per-PR cooldowns from disk (survives restarts)."""
    if PR_COOLDOWN_FILE.exists():
        try:
            return json.loads(PR_COOLDOWN_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_pr_cooldowns(cooldowns):
    """Persist per-PR cooldowns to disk."""
    PR_COOLDOWN_FILE.write_text(json.dumps(cooldowns, indent=2))


def _set_pr_cooldown(pr_key):
    """Set cooldown for a PR (key = 'repo:pr_num')."""
    cooldowns = _load_pr_cooldowns()
    cooldowns[pr_key] = time.time()
    _save_pr_cooldowns(cooldowns)


def _is_pr_on_cooldown(pr_key):
    """Check if a PR is still in cooldown period."""
    cooldowns = _load_pr_cooldowns()
    last = cooldowns.get(pr_key, 0)
    return (time.time() - last) < PR_COOLDOWN_SECS


def _is_task_running_for_pr(pr_key):
    """Check if a task is currently running or queued for this PR.

    pr_key format: 'repo:pr_num'
    """
    repo, pr_num_str = pr_key.split(":", 1)
    pr_num = int(pr_num_str)
    data = load_registry()

    # Check registry for running tasks on this PR
    for task in data.get("tasks", []):
        if task.get("repo") == repo and task.get("pr") == pr_num:
            if task["status"] == "running":
                return True

    # Check queue for pending tasks on this PR
    qdata = load_queue()
    for entry in qdata.get("queue", []):
        if entry.get("repo") == repo:
            # Match by task_id containing the PR number (mention tasks)
            # or by task_id matching a registry task with this PR
            tid = entry.get("task_id", "")
            # Check if this queued entry's task has this PR
            for task in data.get("tasks", []):
                if task["id"] == tid and task.get("pr") == pr_num:
                    return True
            # Check mention task IDs (format: pr-mention-{repo}-{pr_num}-{ts})
            if tid.startswith(f"pr-mention-{repo}-{pr_num}-"):
                return True

    return False


def _fetch_pr_comments(gh_repo, pr_num):
    """Fetch all comments/reviews on a PR, return unified sorted list."""
    all_comments = []

    # Issue comments (general PR comments)
    rc, out, _ = run(
        f"{GH_BIN} pr view {pr_num} --repo {gh_repo} "
        f"--json comments --jq '.comments | sort_by(.createdAt)'"
    )
    if rc == 0 and out:
        try:
            for c in json.loads(out):
                all_comments.append({
                    "id": c.get("id", c.get("url", "")),
                    "author": c.get("author", {}).get("login", ""),
                    "body": c.get("body", ""),
                    "created": c.get("createdAt", ""),
                    "type": "comment",
                })
        except json.JSONDecodeError:
            pass

    # Review comments (inline code comments)
    rc2, out2, _ = run(
        f"{GH_BIN} api repos/{gh_repo}/pulls/{pr_num}/comments "
        f"--jq 'sort_by(.created_at)'"
    )
    if rc2 == 0 and out2:
        try:
            for c in json.loads(out2):
                all_comments.append({
                    "id": str(c.get("id", "")),
                    "author": c.get("user", {}).get("login", ""),
                    "body": c.get("body", ""),
                    "created": c.get("created_at", ""),
                    "type": "review_comment",
                    "path": c.get("path", ""),
                    "diff_hunk": c.get("diff_hunk", ""),
                })
        except json.JSONDecodeError:
            pass

    # Review bodies (top-level review comments like from Gemini)
    rc3, out3, _ = run(
        f"{GH_BIN} pr view {pr_num} --repo {gh_repo} "
        f"--json reviews --jq '.reviews | sort_by(.submittedAt)'"
    )
    if rc3 == 0 and out3:
        try:
            for r in json.loads(out3):
                body = (r.get("body") or "").strip()
                if body:
                    all_comments.append({
                        "id": r.get("id", r.get("url", "")),
                        "author": r.get("author", {}).get("login", ""),
                        "body": body,
                        "created": r.get("submittedAt", ""),
                        "type": "review",
                        "state": r.get("state", ""),
                    })
        except json.JSONDecodeError:
            pass

    all_comments.sort(key=lambda c: c.get("created", ""))
    return all_comments


def _find_new_comments(all_comments, last_seen):
    """Find comments after last_seen, skipping bot's own comments.

    Returns (new_comments, new_cursor, valid). If last_seen wasn't found
    (e.g. deleted), returns ([], new_cursor, False).
    """
    if not all_comments:
        return [], last_seen, True

    found_last = False
    new_comments = []
    for c in all_comments:
        if str(c["id"]) == str(last_seen):
            found_last = True
            continue
        if found_last:
            if c.get("author") == BOT_GITHUB_USER:
                continue
            if (c.get("body") or "").strip():
                new_comments.append(c)

    new_cursor = all_comments[-1]["id"]
    return new_comments, new_cursor, found_last


def _build_comment_prompt(new_comments, pr_num, gh_repo):
    """Build a follow-up prompt from new PR comments."""
    parts = []
    for c in new_comments:
        header = f"**{c['author']}** ({c['type']}"
        if c.get("state"):
            header += f", {c['state']}"
        header += ")"
        if c.get("path"):
            header += f" on `{c['path']}`"
        if c.get("diff_hunk"):
            header += f"\n```\n{c['diff_hunk'][-300:]}\n```"
        parts.append(f"{header}:\n{c['body']}")

    combined = "\n\n---\n\n".join(parts)
    return (
        f"New PR comments on PR #{pr_num} (repo: {gh_repo}) that need to be addressed.\n\n"
        f"Respond like a team member would — use your judgment. Here are the comments:\n\n"
        f"{combined}\n\n"
        f"Decide the appropriate action for each comment. Examples of what you might do:\n"
        f"- **Code changes requested** → make changes, commit, push to the PR branch\n"
        f"- **Question asked** → investigate the codebase and reply on the PR\n"
        f"- **Prioritization/triage directive** → update labels, project board, close/reopen "
        f"PR or linked issues as appropriate\n"
        f"- **Request to close/deprioritize** → close the PR with a comment explaining why, "
        f"update linked issue labels\n"
        f"- **Request to rebase/update** → rebase, resolve conflicts, push\n"
        f"- **Review feedback (Gemini, Claude, human)** → address valid points with code "
        f"changes, push, and reply explaining what you fixed\n"
        f"- **Informational/already resolved** → no action needed, but acknowledge if appropriate\n\n"
        f"After pushing code changes, remove the `{REVIEWED_BY_CLAUDE_LABEL}` label to "
        f"trigger re-review:\n"
        f"  gh pr edit {pr_num} --repo {gh_repo} --remove-label {REVIEWED_BY_CLAUDE_LABEL}\n\n"
        f"Reply on the PR with `gh pr comment {pr_num} --repo {gh_repo} --body '...'` "
        f"summarizing what you did. Keep replies concise and professional."
    )


def _enqueue_pr_followup(task_id, repo, description, follow_up, session_id,
                          branch, worktree, discord_thread_id):
    """Enqueue a PR comment follow-up at the front of the queue."""
    qdata = load_queue()
    qdata.setdefault("queue", []).insert(0, {
        "task_id": task_id,
        "repo": repo,
        "description": description,
        "follow_up_prompt": follow_up,
        "session_id": session_id,
        "branch": branch,
        "worktree": worktree,
        "discordThreadId": discord_thread_id,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    })
    save_queue(qdata)


def check_pr_comments():
    """Check hurin-opened PRs for new comments → auto follow-up.

    Monitors tasks with status pr_open or done (PR may still be open after
    task completes). When Patrick or a reviewer (including Gemini) comments,
    enqueues a follow-up that resumes the saved session.

    Cursors persist to disk so restarts don't cause gaps.
    On first encounter, if the latest comment is from Patrick, process it
    immediately instead of skipping.

    Anti-thrashing:
    - Per-PR cooldown (30 min) after processing — prevents feedback loops
    - Running task gate — won't queue if task already running for this PR
    - Pending flag — won't double-queue
    """
    data = load_registry()
    now = time.time()
    cursors = _load_pr_comment_cursors()
    cursors_changed = False

    for task in data.get("tasks", []):
        tid = task["id"]

        # Check tasks with open or recently-completed PRs
        if task["status"] not in ("pr_open", "done"):
            continue
        pr_num = task.get("pr")
        session_id = task.get("session_id")
        repo = task.get("repo", "")
        if not pr_num or not session_id or not repo:
            continue

        pr_key = f"{repo}:{pr_num}"

        # Anti-thrashing: skip if on cooldown
        if _is_pr_on_cooldown(pr_key):
            continue

        # Anti-thrashing: skip if a task is already running/queued for this PR
        if _is_task_running_for_pr(pr_key):
            continue

        # Skip if a follow-up is already pending (in-memory dedup)
        if tid in _pr_followup_pending:
            continue

        # Skip old tasks
        started = task.get("startedAt", 0)
        if started and now - (started / 1000) > PR_COMMENT_MAX_AGE:
            continue

        gh_repo = f"patrickkidd/{repo}"

        # For 'done' tasks, verify the PR is actually still open
        if task["status"] == "done":
            rc, out, _ = run(f"{GH_BIN} pr view {pr_num} --repo {gh_repo} --json state --jq .state")
            if rc != 0 or out.strip().upper() != "OPEN":
                continue

        all_comments = _fetch_pr_comments(gh_repo, pr_num)
        if not all_comments:
            continue

        # Initialize cursor on first encounter — but if the latest comment
        # is from Patrick (the boss), process it immediately instead of skipping.
        if tid not in cursors:
            last = all_comments[-1]
            if last.get("author") == BOSS_GITHUB_USER and (last.get("body") or "").strip():
                # Set cursor to second-to-last so Patrick's comment gets detected
                if len(all_comments) >= 2:
                    cursors[tid] = all_comments[-2]["id"]
                else:
                    # Only comment is Patrick's — use a sentinel that won't match
                    cursors[tid] = "__init__"
                cursors_changed = True
                # Fall through to detection below
            else:
                cursors[tid] = last["id"]
                cursors_changed = True
                continue

        new_comments, new_cursor, valid = _find_new_comments(
            all_comments, cursors[tid]
        )
        cursors[tid] = new_cursor
        cursors_changed = True

        if not valid or not new_comments:
            continue

        follow_up = _build_comment_prompt(new_comments, pr_num, gh_repo)
        log.info(f"PR comment follow-up for {tid}: {len(new_comments)} new comment(s)")

        _enqueue_pr_followup(
            tid, repo, task.get("description", tid), follow_up, session_id,
            task.get("branch", ""), task.get("worktree", ""),
            task.get("discordThreadId", ""),
        )
        _pr_followup_pending.add(tid)
        _set_pr_cooldown(pr_key)

        # Acknowledge on the PR
        ack_body = (
            "📩 **Follow-up queued** — resuming agent session to address "
            f"{len(new_comments)} comment(s)."
        )
        repo_dir = task.get("repoDir", str(DEV_REPO))
        run(
            f"{GH_BIN} pr comment {pr_num} --repo {gh_repo} --body {json.dumps(ack_body)}",
            cwd=repo_dir,
        )

        # Also notify in Discord thread if present
        thread_id = task.get("discordThreadId")
        if thread_id:
            _discord_api(
                "POST",
                f"https://discord.com/api/v10/channels/{thread_id}/messages",
                {"content": f"📩 PR #{pr_num} has new comments — follow-up queued."},
            )

        log.info(f"  Enqueued PR comment follow-up for {tid}")

    if cursors_changed:
        _save_pr_comment_cursors(cursors)


def check_pr_mentions():
    """Check all open PRs for Patrick's comments or @patrickkidd-hurin mentions.

    Triggers on PRs NOT already tracked in the registry (those are handled by
    check_pr_comments). Two triggers:
    - Patrick comments on any open PR → always respond (he's the boss)
    - Anyone @mentions the bot → respond

    Spawns a fresh task since there's no session to resume.
    Cursors persist to disk so restarts don't cause gaps.

    Anti-thrashing:
    - One active task per PR (pending flag keyed by repo:pr_num)
    - Per-PR cooldown shared with check_pr_comments()
    - Running task gate — won't spawn if already running for this PR
    """
    # Build set of PR keys already tracked by check_pr_comments()
    data = load_registry()
    tracked_prs = set()
    for task in data.get("tasks", []):
        repo = task.get("repo", "")
        pr = task.get("pr")
        if repo and pr and task["status"] in ("pr_open", "done"):
            tracked_prs.add(f"{repo}:{pr}")

    mention_cursors = _load_pr_mention_cursors()
    mention_cursors_changed = False

    for gh_repo in PR_MENTION_REPOS:
        repo_short = gh_repo.split("/")[1]

        # Fetch open PRs
        rc, out, _ = run(
            f"{GH_BIN} pr list --repo {gh_repo} --json number,title,headRefName --limit 30"
        )
        if rc != 0 or not out:
            continue
        try:
            prs = json.loads(out)
        except json.JSONDecodeError:
            continue

        for pr in prs:
            pr_num = pr["number"]
            pr_key = f"{repo_short}:{pr_num}"

            # Skip PRs already tracked by check_pr_comments()
            if pr_key in tracked_prs:
                continue

            # Anti-thrashing: skip if on cooldown
            if _is_pr_on_cooldown(pr_key):
                continue

            # Anti-thrashing: skip if a task is already running/queued for this PR
            if _is_task_running_for_pr(pr_key):
                continue

            # Skip if already pending (one task per PR)
            if pr_key in _pr_mention_pending:
                continue

            all_comments = _fetch_pr_comments(gh_repo, pr_num)
            if not all_comments:
                continue

            # Initialize cursor on first encounter — but process if latest is from Patrick
            if pr_key not in mention_cursors:
                last = all_comments[-1]
                if last.get("author") == BOSS_GITHUB_USER and (last.get("body") or "").strip():
                    if len(all_comments) >= 2:
                        mention_cursors[pr_key] = all_comments[-2]["id"]
                    else:
                        mention_cursors[pr_key] = "__init__"
                    mention_cursors_changed = True
                else:
                    mention_cursors[pr_key] = last["id"]
                    mention_cursors_changed = True
                    continue

            new_comments, new_cursor, valid = _find_new_comments(
                all_comments, mention_cursors[pr_key]
            )
            mention_cursors[pr_key] = new_cursor
            mention_cursors_changed = True

            if not valid or not new_comments:
                continue

            # Act on: Patrick's comments (always) OR @mentions from anyone
            actionable_comments = [
                c for c in new_comments
                if c.get("author") == BOSS_GITHUB_USER
                or f"@{BOT_GITHUB_USER}" in (c.get("body") or "")
            ]
            if not actionable_comments:
                continue

            # Generate a task ID for the fresh task
            task_id = f"pr-mention-{repo_short}-{pr_num}-{int(time.time())}"
            branch = pr.get("headRefName", f"pr-{pr_num}")

            prompt = _build_comment_prompt(actionable_comments, pr_num, gh_repo)
            # Wrap in a full task prompt since there's no session to resume
            full_prompt = (
                f"You've been asked to respond to comments on PR #{pr_num} in {gh_repo}.\n"
                f"PR title: {pr.get('title', '')}\n"
                f"Branch: {branch}\n\n"
                f"First, check out the PR branch and understand the PR's changes:\n"
                f"  git fetch origin {branch} && git checkout {branch}\n"
                f"  gh pr diff {pr_num} --repo {gh_repo}\n\n"
                f"{prompt}"
            )

            log.info(f"PR comment/mention on {gh_repo} PR #{pr_num}: {len(actionable_comments)} comment(s)")

            # Write prompt to file
            prompt_path = QUEUE_PROMPTS / f"{task_id}.txt"
            prompt_path.write_text(full_prompt)

            # Enqueue as a fresh task (no session to resume)
            qdata = load_queue()
            qdata.setdefault("queue", []).insert(0, {
                "task_id": task_id,
                "repo": repo_short,
                "description": f"Respond to @mention on PR #{pr_num}",
                "prompt_file": str(prompt_path),
                "issue_number": "",
                "branch": branch,
                "queued_at": datetime.now(timezone.utc).isoformat(),
            })
            save_queue(qdata)
            _pr_mention_pending.add(pr_key)
            _set_pr_cooldown(pr_key)

            # Acknowledge on the PR
            ack_body = (
                "📩 **Task spawned** — addressing your comment."
            )
            run(f"{GH_BIN} pr comment {pr_num} --repo {gh_repo} --body {json.dumps(ack_body)}")

            log.info(f"  Spawned mention task {task_id} for {gh_repo} PR #{pr_num}")

    if mention_cursors_changed:
        _save_pr_mention_cursors(mention_cursors)


# ---------------------------------------------------------------------------
# Issue comment monitoring — route Patrick's issue comments to Huor
# ---------------------------------------------------------------------------

ISSUE_COMMENT_REPOS = ["patrickkidd/familydiagram", "patrickkidd/btcopilot", "patrickkidd/fdserver"]
ISSUE_COMMENT_COOLDOWN_SECS = 5 * 60  # 5 min cooldown per issue (short for conversational flow)
OPENCLAW_BIN = HOME / ".npm-global/bin/openclaw"

# Persistent tracking: {"repo:issue_num": last_comment_id}
ISSUE_CURSOR_FILE = MONITOR_DIR / "issue-comment-cursors.json"
ISSUE_COOLDOWN_FILE = MONITOR_DIR / "issue-comment-cooldowns.json"


def _load_issue_cursors():
    if ISSUE_CURSOR_FILE.exists():
        try:
            return json.loads(ISSUE_CURSOR_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_issue_cursors(cursors):
    ISSUE_CURSOR_FILE.write_text(json.dumps(cursors, indent=2))


def _load_issue_cooldowns():
    if ISSUE_COOLDOWN_FILE.exists():
        try:
            return json.loads(ISSUE_COOLDOWN_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_issue_cooldowns(cooldowns):
    ISSUE_COOLDOWN_FILE.write_text(json.dumps(cooldowns, indent=2))


def _openclaw_env():
    """Build env dict with secrets for openclaw CLI (needs Discord bot tokens to read config)."""
    env = os.environ.copy()
    secrets_file = HOME / ".openclaw/secrets.json"
    if secrets_file.exists():
        try:
            secrets = json.loads(secrets_file.read_text())
            env["HUOR_DISCORD_BOT_TOKEN"] = secrets.get("huor-discord-bot-token", "")
            env["TUOR_DISCORD_BOT_TOKEN"] = secrets.get("tuor-discord-bot-token", "")
            env["BEREN_DISCORD_BOT_TOKEN"] = secrets.get("beren-discord-bot-token", "")
            env["GATEWAY_AUTH_TOKEN"] = secrets.get("gateway-auth-token", "")
            env["MINIMAX_API_KEY"] = secrets.get("minimax-api-key", "")
        except (json.JSONDecodeError, IOError):
            pass
    # Never leak API key — Max plan only
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def send_to_huor(message):
    """Send a message directly to Huor agent via openclaw CLI.

    Runs with a 10-minute timeout (Huor may use exec to spawn tasks).
    Catches all exceptions so a failure never crashes the main loop.
    """
    try:
        result = subprocess.run(
            [str(OPENCLAW_BIN), "agent", "--agent", "huor", "--message", message],
            capture_output=True, text=True, env=_openclaw_env(), timeout=600,
        )
        if result.returncode != 0:
            log.warning(f"  send_to_huor failed: {result.stderr[:200]}")
        else:
            log.info("  Message delivered to Huor")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log.warning("  send_to_huor timed out after 600s")
        return False
    except Exception as e:
        log.warning(f"  send_to_huor error: {e}")
        return False


def check_issue_comments():
    """Check open issues for new comments from Patrick → route to Huor.

    Polls all open issues in the 3 product repos. When Patrick comments,
    sends the comment directly to Huor agent to triage (spawn task, update
    knowledge, or ignore).

    Cursors and cooldowns persist to disk so restarts don't cause gaps.

    Anti-thrashing:
    - Per-issue cooldown (5 min)
    - Skips bot's own comments
    - Initializes cursor on first encounter (no backlog processing)
    """
    now = time.time()
    cursors = _load_issue_cursors()
    cooldowns = _load_issue_cooldowns()
    cursors_changed = False
    cooldowns_changed = False

    for gh_repo in ISSUE_COMMENT_REPOS:
        repo_short = gh_repo.split("/")[1]

        # Fetch open issues (exclude PRs — gh issues list already does this)
        rc, out, _ = run(
            f"{GH_BIN} issue list --repo {gh_repo} --state open "
            f"--json number,title --limit 50"
        )
        if rc != 0 or not out:
            continue
        try:
            issues = json.loads(out)
        except json.JSONDecodeError:
            continue

        for issue in issues:
            issue_num = issue["number"]
            issue_key = f"{repo_short}:{issue_num}"

            # Anti-thrashing: skip if on cooldown
            cooldown_expiry = cooldowns.get(issue_key, 0)
            if now < cooldown_expiry:
                continue

            # Fetch issue comments
            rc, out, _ = run(
                f"{GH_BIN} api repos/{gh_repo}/issues/{issue_num}/comments "
                f"--jq 'sort_by(.created_at)'"
            )
            if rc != 0 or not out:
                continue
            try:
                all_comments = json.loads(out)
            except json.JSONDecodeError:
                continue

            if not all_comments:
                continue

            # Initialize cursor on first encounter — but process if latest is from Patrick
            if issue_key not in cursors:
                last = all_comments[-1]
                last_author = last.get("user", {}).get("login", "")
                if last_author == BOSS_GITHUB_USER and (last.get("body") or "").strip():
                    if len(all_comments) >= 2:
                        cursors[issue_key] = all_comments[-2]["id"]
                    else:
                        cursors[issue_key] = "__init__"
                    cursors_changed = True
                    # Fall through to detection below
                else:
                    cursors[issue_key] = last["id"]
                    cursors_changed = True
                    continue

            # Find new comments after cursor
            last_seen = cursors[issue_key]
            found_last = False
            new_comments = []
            for c in all_comments:
                if c["id"] == last_seen:
                    found_last = True
                    continue
                if found_last:
                    author = c.get("user", {}).get("login", "")
                    if author == BOT_GITHUB_USER:
                        continue
                    if author == BOSS_GITHUB_USER and (c.get("body") or "").strip():
                        new_comments.append(c)

            # Update cursor
            cursors[issue_key] = all_comments[-1]["id"]
            cursors_changed = True

            if not found_last or not new_comments:
                continue

            # Send directly to Huor agent
            for c in new_comments:
                body = (c.get("body") or "").strip()
                comment_url = c.get("html_url", "")
                msg = (
                    f"[GitHub issue comment] Patrick commented on "
                    f"{repo_short}#{issue_num} ({issue.get('title', '')}):\n\n"
                    f"> {body}\n\n"
                    f"{comment_url}\n\n"
                    f"Follow the 'GitHub Issue Comment Handling' section in your SOUL.md.\n"
                    f"Most issue comments require repo/code context — spawn a CC task:\n"
                    f"  exec: task spawn {repo_short} issue-{issue_num}-comment "
                    f"'Address Patrick comment on #{issue_num}' <<'PROMPT'\n"
                    f"Patrick commented on issue #{issue_num} ({issue.get('title', '')}) "
                    f"in {gh_repo}:\n> {body}\n\n"
                    f"Read the issue, understand the context, and do what Patrick asked.\n"
                    f"Reply on the issue when done: "
                    f"gh issue comment {issue_num} --repo {gh_repo} --body '...'\n"
                    f"PROMPT\n\n"
                    f"Then confirm on GitHub:\n"
                    f"  exec: gh issue comment {issue_num} --repo {gh_repo} "
                    f"--body 'Spawned a task to handle this.'\n\n"
                    f"Only handle directly if it's a simple label/close/status command."
                )
                send_to_huor(msg)
                log.info(f"  Routed issue comment to Huor: {repo_short}#{issue_num} ({comment_url})")

            # Set cooldown
            cooldowns[issue_key] = now + ISSUE_COMMENT_COOLDOWN_SECS
            cooldowns_changed = True

    if cursors_changed:
        _save_issue_cursors(cursors)
    if cooldowns_changed:
        _save_issue_cooldowns(cooldowns)


# ---------------------------------------------------------------------------
# Thread reply monitoring — auto follow-up from Discord thread replies
# ---------------------------------------------------------------------------

THREAD_REPLY_MAX_AGE = 24 * 3600  # Only watch threads from the last 24h

# In-memory tracking of last seen message per thread (initialized on first check)
_thread_last_seen = {}
_thread_followup_pending = set()


def check_thread_replies():
    """Check completed task threads for new human messages → auto follow-up.

    When Patrick replies in a completed task's Discord thread, enqueue
    a follow-up that resumes the saved session with full CC context.
    """
    data = load_registry()
    now = time.time()
    bot_user_id = get_bot_user_id() if DISCORD_BOT_TOKEN else None
    if not bot_user_id:
        return

    for task in data.get("tasks", []):
        tid = task["id"]

        # Only check recently completed tasks with threads and sessions
        if task["status"] not in ("done", "pr_open"):
            continue
        thread_id = task.get("discordThreadId")
        session_id = task.get("session_id")
        if not thread_id or not session_id:
            continue

        # Skip if a follow-up is already queued for this task
        if tid in _thread_followup_pending:
            continue

        # Skip if already queued (check queue directly)
        qdata = load_queue()
        if any(e.get("task_id") == tid for e in qdata.get("queue", [])):
            continue

        # Only watch tasks completed in the last 24h
        started = task.get("startedAt", 0)
        if now - (started / 1000) > THREAD_REPLY_MAX_AGE:
            continue

        # Initialize last_seen to latest message on first encounter
        if tid not in _thread_last_seen:
            init_result = _discord_api(
                "GET",
                f"https://discord.com/api/v10/channels/{thread_id}"
                f"/messages?limit=1",
            )
            if init_result and isinstance(init_result, list) and init_result:
                _thread_last_seen[tid] = init_result[0]["id"]
            else:
                _thread_last_seen[tid] = "0"
            continue  # Don't check for new messages on the init pass

        last_seen = _thread_last_seen[tid]

        # Fetch new messages since last check
        result = _discord_api(
            "GET",
            f"https://discord.com/api/v10/channels/{thread_id}"
            f"/messages?after={last_seen}&limit=10",
        )

        if not result or not isinstance(result, list) or not result:
            continue

        # Process newest-first → chronological
        result.sort(key=lambda m: m["id"])

        human_messages = []
        for msg in result:
            _thread_last_seen[tid] = msg["id"]  # Advance cursor
            author = msg.get("author", {})
            if author.get("id") == bot_user_id or author.get("bot"):
                continue
            content = msg.get("content", "").strip()
            if content:
                human_messages.append(content)

        if not human_messages:
            continue

        # Combine messages into a single follow-up prompt
        combined = "\n\n".join(human_messages)
        log.info(f"Thread reply for {tid}: {combined[:80]}")

        # Enqueue follow-up (insert at front of queue for priority)
        qdata = load_queue()
        qdata.setdefault("queue", []).insert(0, {
            "task_id": tid,
            "repo": task["repo"],
            "description": task.get("description", tid),
            "follow_up_prompt": combined,
            "session_id": session_id,
            "branch": task.get("branch", ""),
            "worktree": task.get("worktree", ""),
            "discordThreadId": thread_id,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        })
        save_queue(qdata)
        _thread_followup_pending.add(tid)

        # Acknowledge in the thread
        _discord_api(
            "POST",
            f"https://discord.com/api/v10/channels/{thread_id}/messages",
            {"content": "📩 **Follow-up queued** — resuming session with your message."},
        )

        log.info(f"  Enqueued thread reply follow-up for {tid}")


# ---------------------------------------------------------------------------
# Channel thread reply monitoring — COS, team-lead, co-founder
# ---------------------------------------------------------------------------

_channel_thread_last_seen = {}  # {thread_id: last_message_id}
_channel_followup_running = set()  # thread_ids with active follow-ups


def check_channel_thread_replies():
    """Check registered channel threads (COS, team-lead, co-founder) for replies.

    Unlike task thread replies which re-enter the task queue, channel thread
    replies are handled by run_channel_followup() — a lightweight SDK session
    that responds conversationally without worktrees, PRs, or git.
    """
    data = load_channel_threads()
    bot_user_id = get_bot_user_id() if DISCORD_BOT_TOKEN else None
    if not bot_user_id:
        return []

    followups = []

    for entry in data.get("threads", []):
        thread_id = entry.get("thread_id")
        if not thread_id:
            continue

        # Skip if a follow-up is already running for this thread
        if thread_id in _channel_followup_running:
            continue

        # Initialize last_seen on first encounter
        if thread_id not in _channel_thread_last_seen:
            init_result = _discord_api(
                "GET",
                f"https://discord.com/api/v10/channels/{thread_id}/messages?limit=1",
            )
            if init_result and isinstance(init_result, list) and init_result:
                _channel_thread_last_seen[thread_id] = init_result[0]["id"]
            else:
                _channel_thread_last_seen[thread_id] = "0"
            continue

        last_seen = _channel_thread_last_seen[thread_id]

        # Fetch new messages
        result = _discord_api(
            "GET",
            f"https://discord.com/api/v10/channels/{thread_id}/messages?after={last_seen}&limit=10",
        )
        if not result or not isinstance(result, list) or not result:
            continue

        result.sort(key=lambda m: m["id"])

        human_messages = []
        for msg in result:
            _channel_thread_last_seen[thread_id] = msg["id"]
            author = msg.get("author", {})
            if author.get("id") == bot_user_id or author.get("bot"):
                continue
            content = msg.get("content", "").strip()
            if content:
                human_messages.append(content)

        if not human_messages:
            continue

        combined = "\n\n".join(human_messages)
        log.info(f"Channel thread reply ({entry.get('channel_type')}): {combined[:80]}")

        # Acknowledge in thread
        _discord_api(
            "POST",
            f"https://discord.com/api/v10/channels/{thread_id}/messages",
            {"content": "📩 **Processing your reply...** Resuming session with full context."},
        )

        followups.append({
            "thread_id": thread_id,
            "channel_type": entry.get("channel_type", ""),
            "session_id": entry.get("session_id", ""),
            "context_file": entry.get("context_file", ""),
            "label": entry.get("label", ""),
            "user_message": combined,
        })

    return followups


async def run_channel_followup(followup):
    """Run a lightweight SDK follow-up session for a channel thread reply.

    No worktrees, no PRs, no git — just a conversational response using
    the saved session context. Posts the response back to the thread.
    """
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage

    thread_id = followup["thread_id"]
    channel_type = followup["channel_type"]
    session_id = followup.get("session_id", "")
    context_file = followup.get("context_file", "")
    user_message = followup["user_message"]

    _channel_followup_running.add(thread_id)
    log.info(f"Running channel follow-up ({channel_type}) in thread {thread_id}")

    try:
        # Build prompt with context
        context = ""
        if context_file and Path(context_file).exists():
            try:
                context = Path(context_file).read_text()
                if len(context) > 6000:
                    context = context[:6000] + "\n...(truncated)"
            except Exception:
                pass

        if session_id:
            # Resume the session — SDK has full context
            prompt = user_message
        else:
            # No session to resume — provide context in the prompt
            type_labels = {
                "cos": "Chief of Staff",
                "teamlead": "Team Lead",
                "cofounder": "Co-Founder",
            }
            role = type_labels.get(channel_type, channel_type)
            prompt = (
                f"You are the {role} for an AI agent system supporting Patrick's software development.\n\n"
                f"## Previous Output\n\n{context}\n\n"
                f"## Patrick's Reply\n\n{user_message}\n\n"
                f"Respond conversationally. Be concise and actionable. "
                f"You have access to the codebase and tools — investigate if needed."
            )

        # Force Max plan
        os.environ.pop("ANTHROPIC_API_KEY", None)

        gh_token = ""
        if BOT_TOKEN_FILE.exists():
            gh_token = BOT_TOKEN_FILE.read_text().strip()

        sdk_env = {
            "PATH": "/usr/local/bin:" + str(HOME / ".local/bin") + ":" + os.environ.get("PATH", ""),
            "HOME": str(HOME),
            "CLAUDECODE": "",
            "ANTHROPIC_API_KEY": "",  # Force Max plan — SDK merges os.environ first, this overrides
        }
        if gh_token:
            sdk_env["GH_TOKEN"] = gh_token

        options = ClaudeAgentOptions(
            model="claude-opus-4-6",
            permission_mode="bypassPermissions",
            cwd=str(DEV_REPO),
            env=sdk_env,
            cli_path=str(HOME / ".local/bin/claude"),
            max_turns=8,
            setting_sources=["project"],
        )
        if session_id:
            options.resume = session_id

        cc_output = ""
        new_session_id = ""

        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)
                async for message in client.receive_response():
                    if isinstance(message, ResultMessage):
                        cc_output = message.result or ""
                        new_session_id = getattr(message, 'session_id', '') or getattr(client, 'session_id', '') or ''
                        break
        except Exception as e:
            log.error(f"Channel follow-up SDK error: {e}")
            _discord_api(
                "POST",
                f"https://discord.com/api/v10/channels/{thread_id}/messages",
                {"content": f"❌ Follow-up failed: {type(e).__name__}"},
            )
            return

        if not cc_output:
            _discord_api(
                "POST",
                f"https://discord.com/api/v10/channels/{thread_id}/messages",
                {"content": "⚠️ Empty response from follow-up session."},
            )
            return

        # Post response to thread
        post_to_channel_thread(thread_id, cc_output)

        # Update session_id in the channel thread registry
        if new_session_id:
            ct_data = load_channel_threads()
            for entry in ct_data.get("threads", []):
                if entry.get("thread_id") == thread_id:
                    entry["session_id"] = new_session_id
                    break
            save_channel_threads(ct_data)

        log.info(f"Channel follow-up complete ({channel_type}), {len(cc_output)} chars")

    finally:
        _channel_followup_running.discard(thread_id)


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

                    # Record spawn proposal in trust ledger
                    if not entry.get("follow_up_prompt"):
                        record_proposal(
                            "spawn",
                            f"spawn:{task_id}",
                            entry.get("description", task_id),
                            metadata={"repo": entry.get("repo", "")},
                        )
                        # Store full prompt text for prompt archaeology
                        prompt_file = entry.get("prompt_file", "")
                        if prompt_file and Path(prompt_file).exists():
                            try:
                                store_prompt_text(
                                    f"spawn:{task_id}",
                                    Path(prompt_file).read_text(),
                                )
                            except Exception:
                                pass

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
                            f"{GH_BIN} issue edit {issue_number} --repo {GITHUB_REPO} "
                            f"--add-label cf-spawned 2>/dev/null"
                        )
                        run(
                            f"{GH_BIN} issue comment {issue_number} --repo {GITHUB_REPO} "
                            f"--body '🤖 Auto-spawned from queue as task `{task_id}`. PR incoming.'",
                            cwd=str(DEV_REPO),
                        )

                    # Clear follow-up pending flags if this was a reply follow-up
                    _thread_followup_pending.discard(task_id)
                    _pr_followup_pending.discard(task_id)
                    # Clear mention pending — extract repo:pr from task_id
                    # (format: pr-mention-{repo}-{pr_num}-{ts})
                    if task_id.startswith("pr-mention-"):
                        parts = task_id.split("-")
                        if len(parts) >= 4:
                            _pr_mention_pending.discard(f"{parts[2]}:{parts[3]}")

                    await run_task(entry)
                    continue  # Check for more work immediately

            # --- Monitor open PRs (every 5th cycle = ~2.5 min) ---
            if loop_count % 5 == 0:
                monitor_open_prs()

            # --- Check PR comments (every 4th cycle = ~2 min) ---
            if loop_count % 4 == 1:
                check_pr_comments()

            # --- Check PR @mentions (every 10th cycle = ~5 min) ---
            if loop_count % 10 == 4:
                check_pr_mentions()

            # --- Check issue comments (every 10th cycle = ~5 min) ---
            if loop_count % 10 == 7:
                check_issue_comments()

            # --- Check task thread replies (every 5th cycle = ~2.5 min) ---
            if loop_count % 5 == 2:
                check_thread_replies()

            # --- Check channel thread replies (every 5th cycle = ~2.5 min) ---
            if loop_count % 5 == 3:
                followups = check_channel_thread_replies()
                for fu in followups:
                    # Run channel follow-ups inline (they're conversational, not tasks)
                    # Only run if no task is currently running
                    if not has_running:
                        await run_channel_followup(fu)

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
