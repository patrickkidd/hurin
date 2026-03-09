#!/usr/bin/env python3
"""
Team Lead Management Daemon — bridges strategy and execution.

Monitors task execution, GitHub state, and goal progress. Produces metrics,
synthesis, and proactive task spawning. Runs as a LaunchAgent alongside
the task daemon.

Architecture:
  task-daemon → task-events.jsonl → [team-lead watches]
  GitHub (PRs, CI, Issues, Project #4) → [team-lead polls every 15min]
    → Metrics Engine (local, no AI)
    → Synthesis Engine (Agent SDK, hourly during biz hours)
    → Auto-spawn pipeline + Discord #ops
"""

import asyncio
import hashlib
import json
import logging
import os
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config import *

# Import shared channel thread registry from discord_relay
sys.path.insert(0, str(HOME / ".openclaw/monitor"))
from discord_relay import (
    load_discord_token as _load_relay_token,
    create_channel_thread,
    register_channel_thread,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

TEAM_LEAD_DIR.mkdir(parents=True, exist_ok=True)
SYNTHESES_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(DAEMON_LOG), mode="a"),
    ],
)
log = logging.getLogger("team-lead")

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
    if DISCORD_TOKEN_FILE.exists():
        DISCORD_BOT_TOKEN = DISCORD_TOKEN_FILE.read_text().strip()


# ---------------------------------------------------------------------------
# Shell helper
# ---------------------------------------------------------------------------

def run(cmd, cwd=None, timeout=60):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            cwd=cwd, timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


# ---------------------------------------------------------------------------
# Discord posting
# ---------------------------------------------------------------------------

def discord_api(method, url, payload=None):
    """Low-level Discord REST API call."""
    if not DISCORD_BOT_TOKEN:
        log.warning("No Discord bot token — skipping Discord post")
        return None
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "TeamLead (https://openclaw.ai, 2.0)",
    }
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log.error(f"Discord API error: {e}")
        return None


def post_to_ops(content, session_id="", synthesis_file=""):
    """Post a message to #ops as a thread for reply monitoring.

    If session_id is provided, registers the thread for conversational follow-up.
    Falls back to flat posting if thread creation fails.
    """
    if not content:
        return

    # Split content into chunks
    chunks = []
    current = ""
    for line in content.split("\n"):
        if current and len(current) + len(line) + 1 > 1900:
            chunks.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)

    if not chunks:
        return

    first_chunk = chunks[0][:2000]

    # Try to create a thread
    now = datetime.now(timezone.utc)
    thread_name = f"TL {now.strftime('%b %d %H:%M')}"

    # Initialize discord_relay token for thread registry
    _load_relay_token()

    thread_id, msg_id = create_channel_thread(
        DISCORD_OPS_CHANNEL_ID, first_chunk, thread_name
    )

    if thread_id:
        # Post remaining chunks in thread
        for chunk in chunks[1:]:
            discord_api(
                "POST",
                f"https://discord.com/api/v10/channels/{thread_id}/messages",
                {"content": chunk[:2000]},
            )

        # Register for reply monitoring if we have a session
        if session_id:
            register_channel_thread(
                thread_id=thread_id,
                channel_type="teamlead",
                channel_id=DISCORD_OPS_CHANNEL_ID,
                session_id=session_id,
                context_file=synthesis_file,
                label=thread_name,
            )
    else:
        # Fallback: flat posting (original behavior)
        for chunk in chunks:
            discord_api(
                "POST",
                f"https://discord.com/api/v10/channels/{DISCORD_OPS_CHANNEL_ID}/messages",
                {"content": chunk[:2000]},
            )


# ---------------------------------------------------------------------------
# Registry helpers (read-only — task-daemon owns writes)
# ---------------------------------------------------------------------------

def load_registry():
    if not REGISTRY.exists():
        return {"tasks": []}
    try:
        return json.loads(REGISTRY.read_text())
    except (json.JSONDecodeError, IOError):
        return {"tasks": []}


def get_running_tasks():
    data = load_registry()
    return [t for t in data.get("tasks", []) if t.get("status") == "running"]


def get_tasks_by_status(*statuses):
    data = load_registry()
    return [t for t in data.get("tasks", []) if t.get("status") in statuses]


def get_completed_since(since_ts):
    """Get tasks completed after a timestamp (epoch ms)."""
    data = load_registry()
    completed = []
    for t in data.get("tasks", []):
        if t.get("status") in ("done", "pr_open"):
            started = t.get("startedAt", 0)
            if started >= since_ts:
                completed.append(t)
    return completed


# ---------------------------------------------------------------------------
# Queue helpers (append-only — team-lead enqueues, task-daemon dequeues)
# ---------------------------------------------------------------------------

def load_queue():
    if not QUEUE_FILE.exists():
        return {"queue": []}
    try:
        return json.loads(QUEUE_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {"queue": []}


def enqueue_task(task_id, repo, description, prompt, issue_number=None):
    """Enqueue a task for the task daemon to pick up."""
    QUEUE_PROMPTS.mkdir(parents=True, exist_ok=True)
    prompt_file = QUEUE_PROMPTS / f"{task_id}.txt"
    prompt_file.write_text(prompt)

    qdata = load_queue()
    entry = {
        "task_id": task_id,
        "repo": repo,
        "description": description,
        "prompt_file": str(prompt_file),
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    if issue_number:
        entry["issue_number"] = str(issue_number)
    qdata["queue"].append(entry)
    QUEUE_FILE.write_text(json.dumps(qdata, indent=2))
    log.info(f"Enqueued task: {task_id}")


def count_team_lead_spawned():
    """Count currently running tasks that were spawned by the team lead."""
    data = load_registry()
    return sum(
        1 for t in data.get("tasks", [])
        if t.get("status") == "running" and t.get("id", "").startswith("tl-")
    )


# ---------------------------------------------------------------------------
# Event watcher (task-events.jsonl)
# ---------------------------------------------------------------------------

class EventWatcher:
    """Tails task-events.jsonl for new events since last read."""

    def __init__(self):
        self._offset = 0
        if TASK_EVENTS.exists():
            self._offset = TASK_EVENTS.stat().st_size

    def poll(self):
        """Return new events since last poll."""
        if not TASK_EVENTS.exists():
            return []
        size = TASK_EVENTS.stat().st_size
        if size <= self._offset:
            if size < self._offset:
                # File was truncated/rotated
                self._offset = 0
            return []
        events = []
        with open(TASK_EVENTS, "r") as f:
            f.seek(self._offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            self._offset = f.tell()
        return events


# ---------------------------------------------------------------------------
# GitHub data collection
# ---------------------------------------------------------------------------

_github_cache = {}
_github_cache_ts = 0


def gh_graphql(query_str, variables=None):
    """Run a GitHub GraphQL query via gh CLI."""
    cmd = ["gh", "api", "graphql", "-f", f"query={query_str}"]
    if variables:
        for k, v in variables.items():
            cmd.extend(["-f", f"{k}={v}"])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        log.error(f"GraphQL error: {result.stderr}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        log.error(f"GraphQL parse error: {result.stdout[:200]}")
        return None


def fetch_project_items():
    """Fetch all items from Project #4 with status, labels, PR state."""
    all_items = []
    cursor = None

    for _ in range(10):  # Max 1000 items
        after = f', after: "{cursor}"' if cursor else ""
        query = """
        {
          user(login: "patrickkidd") {
            projectV2(number: 4) {
              items(first: 100%s) {
                pageInfo { hasNextPage endCursor }
                nodes {
                  id
                  content {
                    ... on Issue {
                      number
                      title
                      state
                      createdAt
                      updatedAt
                      labels(first: 10) { nodes { name } }
                      milestone { number title }
                      assignees(first: 5) { nodes { login } }
                    }
                  }
                  fieldValues(first: 20) {
                    nodes {
                      ... on ProjectV2ItemFieldSingleSelectValue {
                        field { ... on ProjectV2SingleSelectField { name } }
                        name
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """ % after

        data = gh_graphql(query)
        if not data:
            break

        project = data.get("data", {}).get("user", {}).get("projectV2", {})
        items_data = project.get("items", {})
        nodes = items_data.get("nodes", [])
        all_items.extend(nodes)

        page_info = items_data.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")

    return all_items


def parse_project_items(raw_items):
    """Parse raw GraphQL items into structured goal/issue data."""
    goals = {"Goal 1": [], "Goal 2": [], "Goal 3": []}
    ungrouped = []

    for item in raw_items:
        content = item.get("content")
        if not content or "number" not in content:
            continue  # Skip drafts/notes

        issue_number = content["number"]
        title = content.get("title", "")
        state = content.get("state", "OPEN")
        labels = [n["name"] for n in content.get("labels", {}).get("nodes", [])]
        updated_at = content.get("updatedAt", "")
        milestone = content.get("milestone")

        # Extract field values
        fields = {}
        for fv in item.get("fieldValues", {}).get("nodes", []):
            field_info = fv.get("field")
            if field_info and "name" in field_info:
                fields[field_info["name"]] = fv.get("name", "")

        status = fields.get("Status", "")
        owner = fields.get("Owner", "")
        priority = fields.get("Priority", "")

        # Determine effort weight
        effort = DEFAULT_EFFORT
        for label in labels:
            if label in EFFORT_WEIGHTS:
                effort = EFFORT_WEIGHTS[label]
                break

        parsed = {
            "number": issue_number,
            "title": title,
            "state": state,
            "status": status,
            "owner": owner,
            "priority": priority,
            "labels": labels,
            "effort": effort,
            "updated_at": updated_at,
            "milestone": milestone.get("title") if milestone else None,
            "project_item_id": item["id"],
        }

        # Assign to goal based on Status field OR milestone
        goal = None
        if status in GOAL_STATUSES:
            goal = status
        elif milestone and milestone.get("title") in GOAL_STATUSES:
            goal = milestone["title"]

        if goal:
            goals[goal].append(parsed)
        else:
            ungrouped.append(parsed)

    return goals, ungrouped


def fetch_open_prs():
    """Fetch open PRs for the repo."""
    code, out, _ = run(
        f'gh pr list --repo {GITHUB_REPO} --json number,title,state,headRefName,'
        f'isDraft,reviewDecision,statusCheckRollup,updatedAt --limit 50'
    )
    if code != 0 or not out:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def fetch_ci_status(branch="master"):
    """Check CI status for a branch."""
    code, out, _ = run(
        f'gh api repos/{GITHUB_REPO}/commits/{branch}/status --jq .state'
    )
    return out if code == 0 else "unknown"


def get_pr_for_issue(issue_number):
    """Check if an issue has a linked PR and its state."""
    code, out, _ = run(
        f'gh pr list --repo {GITHUB_REPO} --search "closes #{issue_number}" '
        f'--json number,state,isDraft,reviewDecision,statusCheckRollup --limit 1'
    )
    if code != 0 or not out:
        return None
    try:
        prs = json.loads(out)
        return prs[0] if prs else None
    except json.JSONDecodeError:
        return None


def fetch_master_activity(days=7):
    """Check recent direct commit activity on master across product repos.

    This captures Patrick's interactive CC work that bypasses the task daemon
    (branch-by-abstraction, pushing straight to master).
    """
    repos = ["patrickkidd/familydiagram", "patrickkidd/btcopilot", "patrickkidd/fdserver"]
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    activity = {}

    for repo in repos:
        code, out, _ = run(
            f'gh api "repos/{repo}/commits?sha=master&since={since}&per_page=100"',
            timeout=30,
        )
        if code != 0 or not out:
            continue
        try:
            raw = json.loads(out)
            if not raw:
                continue
            commits = []
            for c in raw:
                msg = c.get("commit", {}).get("message", "")
                # Take first line only
                first_line = msg.split("\n")[0] if msg else ""
                commits.append({
                    "sha": c.get("sha", "")[:8],
                    "message": first_line,
                    "author": c.get("commit", {}).get("author", {}).get("name", ""),
                    "date": c.get("commit", {}).get("author", {}).get("date", ""),
                })
            if commits:
                activity[repo.split("/")[1]] = {
                    "commit_count": len(commits),
                    "latest": commits[0]["date"] if commits else "",
                    "recent_messages": [c["message"] for c in commits[:10]],
                }
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

    return activity


def collect_github_data():
    """Full GitHub data collection pass."""
    log.info("Collecting GitHub data...")

    raw_items = fetch_project_items()
    goals, ungrouped = parse_project_items(raw_items)
    open_prs = fetch_open_prs()
    ci_master = fetch_ci_status("master")
    master_activity = fetch_master_activity(7)

    # Cross-reference: for In Progress/Done items, try to find linked PRs
    for items in goals.values():
        for item in items:
            _enrich_with_pr(item, open_prs)

    for item in ungrouped:
        _enrich_with_pr(item, open_prs)

    data = {
        "goals": goals,
        "ungrouped": ungrouped,
        "open_prs": open_prs,
        "ci_master": ci_master,
        "master_activity": master_activity,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

    total_direct_commits = sum(r["commit_count"] for r in master_activity.values())
    log.info(
        f"  Goals: {', '.join(f'{k}: {len(v)} issues' for k, v in goals.items())} "
        f"| Ungrouped: {len(ungrouped)} | Open PRs: {len(open_prs)} | CI: {ci_master}"
        f" | Direct master commits (7d): {total_direct_commits}"
    )
    return data


def _enrich_with_pr(item, open_prs):
    """Add PR state info to an issue item by matching branch names."""
    issue_num = item["number"]
    for pr in open_prs:
        branch = pr.get("headRefName", "")
        # Match patterns like feat/cf-123, fix/issue-123, etc.
        if str(issue_num) in branch:
            ci_state = "unknown"
            checks = pr.get("statusCheckRollup", [])
            if checks:
                conclusions = [c.get("conclusion", "") for c in checks if c.get("conclusion")]
                if all(c == "SUCCESS" for c in conclusions) and conclusions:
                    ci_state = "success"
                elif any(c == "FAILURE" for c in conclusions):
                    ci_state = "failure"
                else:
                    ci_state = "pending"

            item["pr"] = {
                "number": pr["number"],
                "isDraft": pr.get("isDraft", False),
                "reviewDecision": pr.get("reviewDecision", ""),
                "ci_state": ci_state,
            }
            return


# ---------------------------------------------------------------------------
# Metrics engine (no AI)
# ---------------------------------------------------------------------------

def compute_issue_completion(item):
    """Compute fuzzy completion % for a single issue."""
    if item["state"] == "CLOSED":
        return COMPLETION_WEIGHTS["closed"]

    pr = item.get("pr")
    if pr:
        if pr["isDraft"]:
            return COMPLETION_WEIGHTS["open_pr_draft"]
        return COMPLETION_WEIGHTS["open_pr_review"]

    # Check if there's recent activity (commits on a branch)
    updated = item.get("updated_at", "")
    if updated:
        try:
            updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - updated_dt < timedelta(days=7):
                return COMPLETION_WEIGHTS["open_active_commits"]
        except (ValueError, TypeError):
            pass

    return COMPLETION_WEIGHTS["open_no_activity"]


def compute_goal_completion(items):
    """Compute weighted fuzzy completion % for a goal's issues."""
    if not items:
        return 0.0

    total_weight = 0
    weighted_completion = 0

    for item in items:
        effort = item.get("effort", DEFAULT_EFFORT)
        completion = compute_issue_completion(item)
        weighted_completion += completion * effort
        total_weight += effort

    return (weighted_completion / total_weight) if total_weight > 0 else 0.0


def compute_velocity(days=7):
    """Compute tasks completed per day over the given window."""
    since_ts = int((time.time() - days * 86400) * 1000)
    completed = get_completed_since(since_ts)
    return len(completed) / max(days, 1)


def compute_cycle_time():
    """Compute average cycle time for recently completed tasks (hours)."""
    data = load_registry()
    cycle_times = []
    for t in data.get("tasks", []):
        if t.get("status") == "done" and t.get("startedAt"):
            # Approximate end time as startedAt + some estimate
            # (registry doesn't store completedAt directly)
            started = t["startedAt"] / 1000
            # Use last modified time of the task log as proxy for completion
            log_file = TASK_LOGS / f"{t['id']}.log"
            if log_file.exists():
                ended = log_file.stat().st_mtime
                hours = (ended - started) / 3600
                if 0 < hours < 48:  # Filter outliers
                    cycle_times.append(hours)

    return sum(cycle_times) / len(cycle_times) if cycle_times else 0.0


def compute_success_rate(days=30):
    """Compute task success rate over the given window."""
    data = load_registry()
    since_ts = int((time.time() - days * 86400) * 1000)
    recent = [
        t for t in data.get("tasks", [])
        if t.get("startedAt", 0) >= since_ts
        and t.get("status") in ("done", "failed", "pr_open")
    ]
    if not recent:
        return 1.0
    succeeded = sum(1 for t in recent if t.get("status") in ("done", "pr_open"))
    return succeeded / len(recent)


def compute_metrics(github_data):
    """Compute all metrics from GitHub data and registry."""
    goals = github_data.get("goals", {})

    goal_metrics = {}
    for goal_name, items in goals.items():
        completion = compute_goal_completion(items)

        # Momentum: any activity in last 48h?
        has_momentum = False
        cutoff = datetime.now(timezone.utc) - timedelta(hours=MOMENTUM_WINDOW_HOURS)
        for item in items:
            updated = item.get("updated_at", "")
            if updated:
                try:
                    updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    if updated_dt > cutoff:
                        has_momentum = True
                        break
                except (ValueError, TypeError):
                    pass

        goal_metrics[goal_name] = {
            "completion_pct": round(completion * 100, 1),
            "total_issues": len(items),
            "closed_issues": sum(1 for i in items if i["state"] == "CLOSED"),
            "with_pr": sum(1 for i in items if i.get("pr")),
            "has_momentum": has_momentum,
        }

    velocity = compute_velocity(7)
    cycle_time = compute_cycle_time()
    success_rate = compute_success_rate(30)

    # Queue stats
    qdata = load_queue()
    queue_len = len(qdata.get("queue", []))
    running = get_running_tasks()

    # Direct master commit activity (Patrick's interactive CC work)
    master_activity = github_data.get("master_activity", {})
    total_direct_commits = sum(r["commit_count"] for r in master_activity.values())

    metrics = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "goals": goal_metrics,
        "velocity_7d": round(velocity, 2),
        "cycle_time_hours": round(cycle_time, 1),
        "success_rate_30d": round(success_rate, 2),
        "queue_length": queue_len,
        "running_tasks": len(running),
        "ci_master": github_data.get("ci_master", "unknown"),
        "direct_master_commits_7d": total_direct_commits,
        "master_activity": {k: v["commit_count"] for k, v in master_activity.items()},
    }

    return metrics


def log_metrics(metrics):
    """Append metrics to the JSONL log, rotating if needed."""
    with open(METRICS_LOG, "a") as f:
        f.write(json.dumps(metrics) + "\n")

    # Rotate if too large
    if METRICS_LOG.exists():
        line_count = sum(1 for _ in open(METRICS_LOG))
        if line_count > METRICS_MAX_LINES:
            lines = open(METRICS_LOG).readlines()
            # Keep last half
            with open(METRICS_LOG, "w") as f:
                f.writelines(lines[len(lines) // 2:])
            log.info(f"Rotated metrics log ({line_count} → {line_count // 2} lines)")


def load_previous_metrics():
    """Load the most recent metrics entry."""
    if not METRICS_LOG.exists():
        return None
    try:
        with open(METRICS_LOG) as f:
            last_line = None
            for line in f:
                if line.strip():
                    last_line = line
            if last_line:
                return json.loads(last_line)
    except (json.JSONDecodeError, IOError):
        pass
    return None


# ---------------------------------------------------------------------------
# Anomaly detection (no AI)
# ---------------------------------------------------------------------------

_anomaly_cooldowns = {}


def detect_anomalies(github_data, metrics, events):
    """Detect anomalies and return a list of {type, severity, message}."""
    now = time.time()
    anomalies = []

    def _emit(atype, severity, message):
        last = _anomaly_cooldowns.get(atype, 0)
        if now - last < ANOMALY_COOLDOWN_SECS:
            return
        _anomaly_cooldowns[atype] = now
        anomalies.append({"type": atype, "severity": severity, "message": message})

    # Stale PRs: CI green, no activity >48h
    for pr in github_data.get("open_prs", []):
        updated = pr.get("updatedAt", "")
        if updated:
            try:
                updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                age_hours = (datetime.now(timezone.utc) - updated_dt).total_seconds() / 3600
                if age_hours > STALE_PR_HOURS:
                    checks = pr.get("statusCheckRollup", [])
                    conclusions = [c.get("conclusion", "") for c in checks if c.get("conclusion")]
                    if all(c == "SUCCESS" for c in conclusions) and conclusions:
                        _emit(
                            f"stale_pr_{pr['number']}",
                            "medium",
                            f"PR #{pr['number']} ({pr.get('title', '')}) is stale — "
                            f"CI green, no activity in {int(age_hours)}h",
                        )
            except (ValueError, TypeError):
                pass

    # CI drift: master CI failing >2h
    if metrics.get("ci_master") == "failure":
        _emit("ci_drift", "high", "Master CI is failing")

    # Stuck tasks: running, no log activity >1h
    for task in get_running_tasks():
        task_id = task.get("id", "")
        log_file = TASK_LOGS / f"{task_id}.log"
        if log_file.exists():
            age_hours = (now - log_file.stat().st_mtime) / 3600
            if age_hours > STUCK_TASK_HOURS:
                _emit(
                    f"stuck_task_{task_id}",
                    "high",
                    f"Task {task_id} appears stuck — no log activity in {age_hours:.1f}h",
                )

    # Goal regression: completion % decreased
    prev_metrics = load_previous_metrics()
    if prev_metrics:
        for goal_name, goal_data in metrics.get("goals", {}).items():
            prev_goal = prev_metrics.get("goals", {}).get(goal_name, {})
            prev_pct = prev_goal.get("completion_pct", 0)
            curr_pct = goal_data.get("completion_pct", 0)
            if prev_pct > 0 and curr_pct < prev_pct - 5:  # >5% regression
                _emit(
                    f"goal_regression_{goal_name}",
                    "high",
                    f"{goal_name} completion regressed: {prev_pct}% → {curr_pct}%",
                )

    # Velocity stall: zero tasks completed in N days AND no direct master commits
    direct_commits = metrics.get("direct_master_commits_7d", 0)
    if metrics.get("velocity_7d", 0) == 0 and direct_commits == 0:
        data = load_registry()
        has_any_done = any(
            t.get("status") == "done" for t in data.get("tasks", [])
        )
        if has_any_done:  # Only alert if we've ever completed tasks
            _emit(
                "velocity_stall",
                "medium",
                f"Zero tasks completed and no direct master commits in the last 7 days",
            )

    # Queue backup: >3 items queued for >1h
    qdata = load_queue()
    queue = qdata.get("queue", [])
    if len(queue) >= QUEUE_BACKUP_ITEMS:
        oldest = queue[0].get("queued_at", "")
        if oldest:
            try:
                queued_dt = datetime.fromisoformat(oldest)
                age_hours = (datetime.now(timezone.utc) - queued_dt).total_seconds() / 3600
                if age_hours > QUEUE_BACKUP_HOURS:
                    _emit(
                        "queue_backup",
                        "medium",
                        f"{len(queue)} tasks queued, oldest waiting {age_hours:.1f}h",
                    )
            except (ValueError, TypeError):
                pass

    return anomalies


# ---------------------------------------------------------------------------
# Dedup cache
# ---------------------------------------------------------------------------

def load_dedup_cache():
    if not DEDUP_CACHE.exists():
        return {}
    try:
        return json.loads(DEDUP_CACHE.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def save_dedup_cache(cache):
    DEDUP_CACHE.write_text(json.dumps(cache, indent=2))


def is_duplicate(key):
    cache = load_dedup_cache()
    entry = cache.get(key)
    if not entry:
        return False
    try:
        ts = datetime.fromisoformat(entry)
        return datetime.now(timezone.utc) - ts < timedelta(hours=DEDUP_TTL_HOURS)
    except (ValueError, TypeError):
        return False


def mark_seen(key):
    cache = load_dedup_cache()
    cache[key] = datetime.now(timezone.utc).isoformat()
    # Prune old entries
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_TTL_HOURS)
    cache = {
        k: v for k, v in cache.items()
        if datetime.fromisoformat(v) > cutoff
    }
    save_dedup_cache(cache)


def dedup_key(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def normalize_recommendation_title(title):
    """Normalize a recommendation title for fuzzy dedup.

    Strips numbers, PR refs, punctuation, and lowercases so that
    semantically similar recommendations like 'Review 2 pending co-founder PRs'
    and 'Review and merge co-founder PRs #119 and #120' produce the same key.
    """
    import re
    t = title.lower().strip()
    # Remove PR/issue references like #119, #120
    t = re.sub(r'#\d+', '', t)
    # Remove standalone numbers (e.g., "2 pending" -> "pending")
    t = re.sub(r'\b\d+\b', '', t)
    # Remove punctuation
    t = re.sub(r'[^\w\s]', '', t)
    # Collapse whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    # Remove filler words and action verbs that vary between phrasings
    stopwords = {'and', 'the', 'a', 'an', 'to', 'of', 'for', 'with', 'on', 'in',
                 'pending', 'open', 'current', 'all', 'across', 'existing',
                 'review', 'merge', 'verify', 'check', 'ensure', 'confirm',
                 'consider', 'map', 'populate', 'assign', 'update', 'add'}
    words = [w for w in t.split() if w not in stopwords]
    return ' '.join(sorted(words))


def load_recent_recommendations(n=5):
    """Load recommendation titles from the last N syntheses for dedup context.

    Returns a list of unique recommendation titles from recent syntheses,
    ordered newest-first.
    """
    synthesis_files = sorted(SYNTHESES_DIR.glob("*.json"), reverse=True)[:n]
    seen_normalized = set()
    titles = []
    for f in synthesis_files:
        try:
            data = json.loads(f.read_text())
            for rec in data.get("recommendations", []):
                title = rec.get("title", "")
                norm = normalize_recommendation_title(title)
                if norm and norm not in seen_normalized:
                    seen_normalized.add(norm)
                    titles.append(title)
        except (json.JSONDecodeError, IOError):
            continue
    return titles[:15]  # Cap to avoid bloating the prompt


# ---------------------------------------------------------------------------
# Synthesis engine (Agent SDK)
# ---------------------------------------------------------------------------

async def run_synthesis(metrics, events, github_data, anomalies):
    """Run weekly Agent SDK synthesis — deep investigation + recommendations."""
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage

    goal_summary = ""
    for goal_name, goal_data in metrics.get("goals", {}).items():
        issues = github_data.get("goals", {}).get(goal_name, [])
        issue_list = "\n".join(
            f"  - #{i['number']}: {i['title']} [{i['state']}] "
            f"(effort={i['effort']}, pr={'yes' if i.get('pr') else 'no'})"
            for i in issues[:15]  # Cap to avoid huge prompts
        )
        goal_summary += (
            f"\n### {goal_name} — {goal_data['completion_pct']}% complete "
            f"({goal_data['closed_issues']}/{goal_data['total_issues']} closed, "
            f"momentum={'yes' if goal_data['has_momentum'] else 'no'})\n"
            f"{issue_list}\n"
        )

    event_summary = ""
    if events:
        recent = events[-20:]  # Last 20 events
        event_summary = "\n".join(
            f"  - [{e.get('event', 'unknown')}] {e.get('task_id', '')} "
            f"at {e.get('ts', '')}"
            for e in recent
        )

    anomaly_summary = ""
    if anomalies:
        anomaly_summary = "\n".join(
            f"  - [{a['severity'].upper()}] {a['message']}"
            for a in anomalies
        )

    registry_tasks = load_registry().get("tasks", [])
    running = [t for t in registry_tasks if t.get("status") == "running"]
    pr_open = [t for t in registry_tasks if t.get("status") == "pr_open"]

    # Trust ledger summary
    trust_summary_text = ""
    try:
        from trust_ledger import get_summary as _trust_summary
        trust = _trust_summary()
        parts = []
        for cat, stats in trust.items():
            if stats["total"] > 0:
                parts.append(
                    f"  {cat}: {stats['accuracy']*100:.0f}% accuracy "
                    f"({stats['correct']}/{stats['total']} correct, "
                    f"{stats['pending']} pending)"
                )
        trust_summary_text = "\n".join(parts) if parts else "  No data yet"
    except Exception:
        trust_summary_text = "  Trust ledger not available"

    # Master activity summary for synthesis
    master_activity = github_data.get("master_activity", {})
    master_summary = ""
    if master_activity:
        total = sum(r["commit_count"] for r in master_activity.values())
        master_summary = f"  Total: {total} commits in last 7 days\n"
        for repo, data in master_activity.items():
            msgs = "\n".join(f"      - {m}" for m in data.get("recent_messages", [])[:5])
            master_summary += f"  {repo}: {data['commit_count']} commits (latest: {data.get('latest', '?')})\n{msgs}\n"
    else:
        master_summary = "  No direct master commits in last 7 days"

    prompt = f"""You are the Team Lead for the FamilyDiagram/BTCoPilot MVP project — Patrick's operational co-founder doing the weekly check-in.

## Your Role

You combine operational awareness with strategic depth. You track MVP progress, identify blockers, set priorities, and ask the hard questions Patrick might be avoiding.

You have **{SYNTHESIS_MAX_TURNS} turns**. Use them to investigate deeply:

1. **Turns 1-3: Gather data.** Run these commands and inspect results:
   - `git log --oneline -30` across all repos — recent commit activity
   - `git log --oneline --since="7 days ago"` — what happened this week
   - `gh pr list --state all --limit 20` — PR activity (open, merged, closed)
   - `gh issue list --limit 20` — open issues and labels
   - `gh run list --limit 10` — CI runs (pass/fail)
   - Read `TODO.md` and the decision log for priorities
   - Check `.clawdbot/active-tasks.json` for running agent tasks
   - `ls -la ~/.openclaw/monitor/failures/` — recent agent failures
   - Investigate anything that looks off. Read source files if a PR or commit looks important.

2. **Turns 4-7: Analyze.** Cross-reference what you found with the metrics below. Identify patterns, blockers, risks. Check agent system health.

3. **Turns 8+: Produce the synthesis.**

## Pre-Collected Metrics
- Velocity (7d): {metrics.get('velocity_7d', 0)} tasks/day (task daemon only)
- Direct master commits (7d): {metrics.get('direct_master_commits_7d', 0)} (Patrick's interactive CC work)
- Cycle time: {metrics.get('cycle_time_hours', 0)}h average
- Success rate (30d): {metrics.get('success_rate_30d', 0) * 100:.0f}%
- Queue: {metrics.get('queue_length', 0)} pending
- Running: {metrics.get('running_tasks', 0)}
- Master CI: {metrics.get('ci_master', 'unknown')}

## IMPORTANT: Direct Master Activity
Patrick often works interactively with Claude Code, pushing directly to master
(branch by abstraction strategy for the training/personal app MVP).
This work does NOT go through the task daemon or create PRs.
Do NOT report the project as stalled if there are recent direct commits.
{master_summary}

## Goal Status
{goal_summary}

## Recent Events
{event_summary or "  No recent events"}

## Anomalies
{anomaly_summary or "  None detected"}

## Running Tasks
{chr(10).join(f"  - {t.get('id', '')}: {t.get('description', '')}" for t in running) or "  None"}

## Trust Ledger (System Performance)
{trust_summary_text}

## PRs Awaiting Review
{chr(10).join(f"  - PR #{t.get('pr', '')}: {t.get('description', '')}" for t in pr_open) or "  None"}

## Recent Recommendations (DO NOT REPEAT)
The following recommendations have already appeared in recent syntheses.
Do NOT produce recommendations that are substantially similar to these.
Only recommend something again if there is genuinely NEW information or a
changed situation that warrants repeating it.
{chr(10).join(f"  - {t}" for t in load_recent_recommendations(DEDUP_RECENT_SYNTHESES)) or "  (none)"}

## Output Format

Respond with ONLY valid JSON in this exact format:
```json
{{
  "health_summary": "1-2 sentence overall health assessment",
  "progress_this_week": "What got done — specific PRs, commits, decisions with numbers/hashes. What shipped or merged.",
  "priorities": "The 1-3 most important things to work on this week. Critical path to MVP. Back up with codebase evidence.",
  "blockers_and_risks": "Anything stuck or at risk. Dependencies. PRs open too long.",
  "agent_system_health": "Are agents running smoothly? Failure patterns. Stale worktrees. Effectiveness assessment.",
  "uncomfortable_question": "One hard question about priorities, scope, or pace Patrick might be avoiding. Ground it in evidence.",
  "goal_status": [
    {{
      "goal": "Goal 1",
      "risk": "low|medium|high",
      "risk_reason": "brief explanation",
      "next_action": "what should happen next for this goal"
    }}
  ],
  "recommendations": [
    {{
      "title": "short imperative action",
      "rationale": "why this matters now",
      "for_human": true,
      "priority": "P0|P1|P2|P3"
    }}
  ],
  "auto_spawn_candidates": [
    {{
      "title": "task title",
      "description": "what to implement",
      "repo": "theapp|btcopilot|familydiagram",
      "goal": "Goal 1|Goal 2|Goal 3",
      "issue_title": "GitHub issue title",
      "spawn_prompt": "full self-contained prompt for Claude Code",
      "rationale": "why this is 100% automatable"
    }}
  ]
}}
```

Rules for auto_spawn_candidates:
- ONLY include tasks that are 100% automatable by Claude Code (no human judgment)
- Must map to an existing goal
- Must be concrete and self-contained (Claude Code must be able to do it with no clarification)
- If in doubt, put it in recommendations instead
- Empty array is fine — don't force it
"""

    log.info("Running weekly synthesis...")

    # CLAUDECODE intentionally absent — prevents nested session detection
    synthesis_env = {
        "PATH": "/usr/local/bin:" + str(HOME / ".local/bin") + ":" + os.environ.get("PATH", ""),
        "HOME": str(HOME),
    }
    # Only set GH_TOKEN if we have a bot token; otherwise let gh use system auth
    if BOT_TOKEN:
        synthesis_env["GH_TOKEN"] = BOT_TOKEN

    options = ClaudeAgentOptions(
        model=SYNTHESIS_MODEL,
        permission_mode="bypassPermissions",
        cwd=str(DEV_REPO),
        env=synthesis_env,
        cli_path=str(CLAUDE_BIN),
        setting_sources=["project"],
    )

    result_text = ""
    session_id = ""
    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    result_text = message.result or ""
                    session_id = getattr(message, 'session_id', '') or getattr(client, 'session_id', '') or ''
                    break
    except Exception as e:
        log.error(f"Synthesis SDK error: {e}")
        return None, ""

    # Parse JSON from result
    synthesis = _parse_synthesis(result_text)
    if synthesis:
        # Save synthesis
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")
        save_path = SYNTHESES_DIR / f"weekly-{ts}.json"
        save_path.write_text(json.dumps(synthesis, indent=2))
        log.info(f"Synthesis saved to {save_path.name}")
        synthesis["_session_id"] = session_id
        synthesis["_save_path"] = str(save_path)

    return synthesis, session_id


def _parse_synthesis(text):
    """Extract JSON from synthesis result text."""
    # Try to find JSON in code blocks
    import re
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    # Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # Try to find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

    log.error(f"Failed to parse synthesis JSON: {text[:200]}")
    return None


# ---------------------------------------------------------------------------
# Auto-spawn pipeline
# ---------------------------------------------------------------------------

def auto_spawn(candidate, github_data):
    """Execute the auto-spawn flow for a 100% automatable task.

    1. Create GitHub Issue
    2. Add to Project #4
    3. Enqueue to task-daemon
    4. Post to Discord #ops
    """
    # Guard: check concurrent spawn limit
    if count_team_lead_spawned() >= MAX_CONCURRENT_SPAWNS:
        log.info(f"  Spawn limit reached ({MAX_CONCURRENT_SPAWNS}), deferring: {candidate['title']}")
        return False

    title = candidate["title"]
    description = candidate.get("description", "")
    repo = candidate.get("repo", "theapp")
    goal = candidate.get("goal", "")
    spawn_prompt = candidate.get("spawn_prompt", description)
    issue_title = candidate.get("issue_title", title)

    # Dedup
    dk = dedup_key(f"spawn:{issue_title}")
    if is_duplicate(dk):
        log.info(f"  Dedup: skipping spawn of '{issue_title}'")
        return False

    log.info(f"AUTO-SPAWNING: {issue_title} (goal={goal}, repo={repo})")

    # 1. Create GitHub Issue
    labels = "co-founder,velocity,cf-spawned"
    code, out, err = run(
        f'gh issue create --repo {GITHUB_REPO} '
        f'--title {json.dumps(issue_title)} '
        f'--body {json.dumps(f"Auto-spawned by team lead daemon.{chr(10)}{chr(10)}{description}")} '
        f'--label "{labels}"'
    )
    if code != 0:
        log.error(f"  Failed to create issue: {err}")
        return False

    # Extract issue number from output (e.g., "https://github.com/.../issues/123")
    issue_url = out.strip()
    issue_number = issue_url.rstrip("/").split("/")[-1] if "/" in issue_url else ""
    log.info(f"  Created issue #{issue_number}: {issue_url}")

    # 2. Add to Project #4
    if issue_number:
        code, out, err = run(
            f'gh project item-add {PROJECT_NUMBER} --owner patrickkidd '
            f'--url {issue_url}'
        )
        if code == 0:
            log.info(f"  Added to Project #4")
            # Set Status to In Progress and Owner to Hurin
            # Extract item ID from the add output
            try:
                item_data = json.loads(out) if out else {}
                item_id = item_data.get("id", "")
            except json.JSONDecodeError:
                item_id = ""
            if item_id:
                run(f'{GH_SYNC_SCRIPT} {item_id} --status "In Progress" --owner Hurin')
        else:
            log.warning(f"  Failed to add to project: {err}")

    # 3. Enqueue to task-daemon
    task_id = f"tl-{issue_number or hashlib.sha256(title.encode()).hexdigest()[:8]}"
    enqueue_task(task_id, repo, title, spawn_prompt, issue_number=issue_number or None)

    # 4. Post to Discord #ops
    post_to_ops(
        f"**Auto-spawned:** `{task_id}`\n"
        f"> {title}\n"
        f"Issue: {issue_url}\n"
        f"Goal: {goal}"
    )

    mark_seen(dk)
    log.info(f"  Spawn complete: {task_id}")
    return True


# ---------------------------------------------------------------------------
# Process synthesis results
# ---------------------------------------------------------------------------

def process_synthesis(synthesis, github_data, session_id=""):
    """Post weekly synthesis to Discord and execute auto-spawns."""
    if not synthesis:
        return

    health = synthesis.get("health_summary", "")
    progress = synthesis.get("progress_this_week", "")
    priorities = synthesis.get("priorities", "")
    blockers = synthesis.get("blockers_and_risks", "")
    agent_health = synthesis.get("agent_system_health", "")
    uncomfortable = synthesis.get("uncomfortable_question", "")
    goal_status = synthesis.get("goal_status", [])
    recommendations = synthesis.get("recommendations", [])
    spawn_candidates = synthesis.get("auto_spawn_candidates", [])

    # Build Discord message
    parts = ["## Team Lead — Weekly Synthesis"]

    if health:
        parts.append(f"\n{health}")

    if progress:
        parts.append(f"\n### Progress This Week\n{progress}")

    if priorities:
        parts.append(f"\n### Priorities\n{priorities}")

    if blockers:
        parts.append(f"\n### Blockers & Risks\n{blockers}")

    if agent_health:
        parts.append(f"\n### Agent System Health\n{agent_health}")

    if goal_status:
        parts.append("\n### Goal Status")
        for g in goal_status:
            risk_emoji = {"low": "", "medium": "", "high": ""}.get(
                g.get("risk", ""), ""
            )
            parts.append(
                f"- **{g['goal']}** {risk_emoji} Risk: {g.get('risk', 'unknown')} "
                f"— {g.get('risk_reason', '')}\n"
                f"  Next: {g.get('next_action', '')}"
            )

    if recommendations:
        parts.append("\n### Recommendations")
        for r in recommendations:
            norm_title = normalize_recommendation_title(r['title'])
            dk = dedup_key(f"rec:{norm_title}")
            if is_duplicate(dk):
                log.info(f"  Dedup: skipping recommendation '{r['title']}' (normalized: '{norm_title}')")
                continue
            mark_seen(dk)
            human_tag = " (human)" if r.get("for_human") else ""
            parts.append(
                f"- **[{r.get('priority', 'P2')}]** {r['title']}{human_tag}\n"
                f"  {r.get('rationale', '')}"
            )

    if uncomfortable:
        parts.append(f"\n### The Uncomfortable Question\n{uncomfortable}")

    message = "\n".join(parts)
    synthesis_file = synthesis.get("_save_path", "")
    post_to_ops(message, session_id=session_id, synthesis_file=synthesis_file)

    # Execute auto-spawns
    if spawn_candidates and AUTONOMY_TIER >= 1:
        for candidate in spawn_candidates:
            auto_spawn(candidate, github_data)


# ---------------------------------------------------------------------------
# Business hours check
# ---------------------------------------------------------------------------

def is_business_hours():
    now = datetime.now(TZ)
    return BIZ_HOUR_START <= now.hour < BIZ_HOUR_END


def is_morning_brief_time():
    """Check if it's time for the morning brief (first synthesis after 7AM)."""
    now = datetime.now(TZ)
    if now.hour < BIZ_HOUR_START or now.hour >= BIZ_HOUR_START + 1:
        return False

    # Check if we already did a morning brief today
    today = now.strftime("%Y-%m-%d")
    morning_file = SYNTHESES_DIR / f"morning-{today}*.json"

    # Look for any morning synthesis file from today
    for f in SYNTHESES_DIR.glob(f"morning-{today}*.json"):
        return False

    return True


# ---------------------------------------------------------------------------
# Main daemon
# ---------------------------------------------------------------------------

async def main_loop():
    """Main daemon loop."""
    log.info("=" * 60)
    log.info("Team Lead daemon starting")
    log.info(f"  Autonomy tier: {AUTONOMY_TIER}")
    log.info(f"  Business hours: {BIZ_HOUR_START}:00-{BIZ_HOUR_END}:00 AKST")
    log.info(f"  GitHub poll: every {GITHUB_POLL_INTERVAL}s")
    log.info(f"  Synthesis: weekly (Monday {SYNTHESIS_HOUR}:00 AKST) + on-demand via /teamlead")
    log.info("=" * 60)

    load_tokens()

    event_watcher = EventWatcher()

    github_data = None
    last_github_poll = 0
    last_synthesis = 0
    all_events = []  # Rolling window of recent events

    while True:
        now = time.time()
        biz_hours = is_business_hours()

        # --- 1. Poll events (always, every 5s) ---
        new_events = event_watcher.poll()
        if new_events:
            log.info(f"  {len(new_events)} new event(s) from task-events.jsonl")
            all_events.extend(new_events)
            # Keep last 100 events
            all_events = all_events[-100:]

            # React to high-priority events immediately
            for event in new_events:
                etype = event.get("event", "")
                if etype == "task_completed":
                    log.info(f"  Task completed: {event.get('task_id', '')}")
                elif etype == "task_failed":
                    log.info(f"  Task failed: {event.get('task_id', '')}")

        # --- 2. GitHub poll (every 15 min during biz hours, every 30 min off hours) ---
        poll_interval = GITHUB_POLL_INTERVAL if biz_hours else GITHUB_POLL_INTERVAL * 2
        if now - last_github_poll >= poll_interval:
            try:
                github_data = collect_github_data()
                metrics = compute_metrics(github_data)
                log_metrics(metrics)

                anomalies = detect_anomalies(github_data, metrics, all_events)
                if anomalies:
                    log.info(f"  {len(anomalies)} anomaly(ies) detected")
                    for a in anomalies:
                        log.info(f"    [{a['severity']}] {a['message']}")
                        # High-severity anomalies bypass quiet hours
                        if a["severity"] == "high":
                            post_to_ops(
                                f"**[{a['severity'].upper()}]** {a['message']}"
                            )

                last_github_poll = now
            except Exception as e:
                log.error(f"GitHub poll error: {e}")

        # --- 3. Weekly synthesis (or on-demand via sentinel / /teamlead command) ---
        synthesis_sentinel = TEAM_LEAD_DIR / "run-synthesis-now"
        manual_trigger = synthesis_sentinel.exists()
        if manual_trigger:
            synthesis_sentinel.unlink()
            log.info("Manual synthesis trigger detected")

        # Weekly schedule: check if it's the right day/hour and enough time has passed
        now_local = datetime.now(TZ)
        weekly_due = (
            biz_hours
            and github_data
            and now_local.isoweekday() == SYNTHESIS_DAY
            and now_local.hour == SYNTHESIS_HOUR
            and now - last_synthesis >= 23 * 3600  # At least 23h since last (prevents double-fire)
        )

        if weekly_due or manual_trigger:
            try:
                anomalies = detect_anomalies(github_data, metrics, all_events)
                synthesis, session_id = await run_synthesis(
                    metrics, all_events, github_data, anomalies,
                )
                if synthesis:
                    process_synthesis(synthesis, github_data,
                                     session_id=session_id)
                last_synthesis = now
            except Exception as e:
                log.error(f"Synthesis error: {e}")

        # --- Sleep ---
        await asyncio.sleep(EVENT_POLL_INTERVAL)


def main():
    # Handle signals for clean shutdown
    loop = asyncio.new_event_loop()

    def shutdown(sig, frame):
        log.info(f"Received signal {sig}, shutting down...")
        loop.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        loop.run_until_complete(main_loop())
    except KeyboardInterrupt:
        log.info("Interrupted, shutting down...")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
