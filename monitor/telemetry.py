"""
Telemetry — passive signal collection for system self-improvement.

Collects: PR review latency, master commit topics, compute ROI, attention signals.
Writes to: ~/.openclaw/knowledge/self/telemetry.jsonl
Called from: team-lead main loop (every GitHub poll cycle)
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

HOME = Path.home()
TELEMETRY_FILE = HOME / ".openclaw/knowledge/self/telemetry.jsonl"
REPOS = ["patrickkidd/familydiagram", "patrickkidd/btcopilot", "patrickkidd/fdserver"]
TASK_EVENTS = HOME / ".openclaw/monitor/task-events.jsonl"
TASK_REGISTRY = HOME / ".openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"
CHANNEL_THREADS = HOME / ".openclaw/monitor/channel-threads.json"


def _run(cmd, timeout=30):
    """Run shell command, return (rc, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


def _append(entry):
    """Append a telemetry entry to the JSONL file."""
    TELEMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry["collected_at"] = datetime.now(timezone.utc).isoformat()
    with open(TELEMETRY_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def collect_pr_review_latency():
    """Track time from PR creation to merge/close for bot PRs.

    Writes one telemetry entry per resolved PR not already recorded.
    """
    # Read existing telemetry to find already-recorded PRs
    recorded_prs = set()
    if TELEMETRY_FILE.exists():
        for line in TELEMETRY_FILE.read_text().splitlines():
            try:
                e = json.loads(line)
                if e.get("type") == "pr_review_latency":
                    recorded_prs.add(e.get("pr_key"))
            except json.JSONDecodeError:
                continue

    for repo in REPOS:
        rc, out, _ = _run(
            f'gh pr list --repo {repo} --author patrickkidd-hurin '
            f'--state all --json number,createdAt,mergedAt,closedAt,state '
            f'--limit 50'
        )
        if rc != 0 or not out:
            continue
        try:
            prs = json.loads(out)
        except json.JSONDecodeError:
            continue

        for pr in prs:
            pr_key = f"{repo}#{pr['number']}"
            if pr_key in recorded_prs:
                continue

            state = pr.get("state", "")
            created = pr.get("createdAt", "")
            resolved_at = pr.get("mergedAt") or pr.get("closedAt")

            if not resolved_at or not created:
                continue

            # Calculate hours between creation and resolution
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                resolved_dt = datetime.fromisoformat(resolved_at.replace("Z", "+00:00"))
                latency_hours = (resolved_dt - created_dt).total_seconds() / 3600
            except (ValueError, TypeError):
                continue

            _append({
                "type": "pr_review_latency",
                "pr_key": pr_key,
                "repo": repo,
                "pr_number": pr["number"],
                "state": state,
                "created_at": created,
                "resolved_at": resolved_at,
                "latency_hours": round(latency_hours, 1),
            })


def collect_master_topics():
    """Cluster recent master commits by topic area.

    Writes a single summary entry with commit topics.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    topics = {}  # topic -> count

    for repo in REPOS:
        rc, out, _ = _run(
            f'gh api "repos/{repo}/commits?sha=master&since={since}&per_page=100"'
        )
        if rc != 0 or not out:
            continue
        try:
            commits = json.loads(out)
        except json.JSONDecodeError:
            continue

        for c in commits:
            msg = c.get("commit", {}).get("message", "").split("\n")[0].lower()
            topic = _classify_commit_topic(msg)
            topics[topic] = topics.get(topic, 0) + 1

    if topics:
        _append({
            "type": "master_topics",
            "topics": topics,
            "total_commits": sum(topics.values()),
        })


def _classify_commit_topic(msg):
    """Classify a commit message into a topic bucket."""
    msg = msg.lower()
    if any(w in msg for w in ["test", "mock", "fixture", "ci", "pytest"]):
        return "testing"
    if any(w in msg for w in ["train", "training", "personal", "session"]):
        return "training_personal_app"
    if any(w in msg for w in ["extract", "llm", "gemini", "prompt", "ai"]):
        return "ai_extraction"
    if any(w in msg for w in ["ui", "qml", "view", "dialog", "widget"]):
        return "ui_frontend"
    if any(w in msg for w in ["api", "route", "endpoint", "server"]):
        return "backend_api"
    if any(w in msg for w in ["fix", "bug", "error", "crash"]):
        return "bugfix"
    if any(w in msg for w in ["refactor", "cleanup", "remove", "dead"]):
        return "refactoring"
    if any(w in msg for w in ["doc", "readme", "comment"]):
        return "docs"
    if any(w in msg for w in ["config", "deploy", "infra", "openclaw"]):
        return "infrastructure"
    return "other"


def collect_compute_roi():
    """Track Opus compute time per task vs outcome (merged/discarded).

    Reads task events and registry to compute time spent on merged vs closed PRs.
    """
    if not TASK_EVENTS.exists():
        return

    # Build duration map from events
    task_times = {}  # task_id -> {start, end}
    try:
        for line in TASK_EVENTS.read_text().splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            tid = e.get("task_id", "")
            evt = e.get("event", "")
            ts = e.get("ts", "")
            if evt == "task_started":
                task_times.setdefault(tid, {})["start"] = ts
            elif evt in ("task_completed", "task_failed"):
                task_times.setdefault(tid, {})["end"] = ts
    except (json.JSONDecodeError, IOError):
        return

    # Read registry for outcomes
    if not TASK_REGISTRY.exists():
        return
    try:
        reg = json.loads(TASK_REGISTRY.read_text())
        tasks = reg.get("tasks", []) if isinstance(reg, dict) else reg
    except (json.JSONDecodeError, IOError):
        return

    merged_time = 0
    discarded_time = 0
    merged_count = 0
    discarded_count = 0

    for t in tasks:
        tid = t.get("id", "")
        status = t.get("status", "")
        times = task_times.get(tid, {})
        if not times.get("start") or not times.get("end"):
            continue

        try:
            start_dt = datetime.fromisoformat(times["start"].replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(times["end"].replace("Z", "+00:00"))
            duration_min = (end_dt - start_dt).total_seconds() / 60
        except (ValueError, TypeError):
            continue

        if t.get("_outcome_recorded"):
            if status == "done":
                merged_time += duration_min
                merged_count += 1
            elif status == "closed":
                discarded_time += duration_min
                discarded_count += 1

    _append({
        "type": "compute_roi",
        "merged_tasks": merged_count,
        "merged_minutes": round(merged_time, 1),
        "discarded_tasks": discarded_count,
        "discarded_minutes": round(discarded_time, 1),
        "roi_ratio": round(merged_time / max(merged_time + discarded_time, 1), 3),
    })


def collect_attention_signals():
    """Track Discord reply latency per channel as proxy for engagement.

    Reads channel-threads.json to find threads, then checks for Patrick's replies.
    """
    if not CHANNEL_THREADS.exists():
        return

    try:
        threads = json.loads(CHANNEL_THREADS.read_text())
    except (json.JSONDecodeError, IOError):
        return

    # For each thread, check if there are replies (we can't distinguish Patrick
    # vs bot replies via REST without knowing Patrick's user ID, so we just
    # count total replies as a proxy)
    for thread in threads:
        thread_id = thread.get("thread_id", "")
        if not thread_id:
            continue

        channel_type = thread.get("channel_type", "unknown")
        created_at = thread.get("created_at", "")

        rc, out, _ = _run(
            f'curl -s -H "Authorization: Bot $DISCORD_BOT_TOKEN" '
            f'"https://discord.com/api/v10/channels/{thread_id}/messages?limit=10"'
        )
        if rc != 0 or not out:
            continue

        try:
            messages = json.loads(out)
            if not isinstance(messages, list):
                continue
            # Count non-bot messages (rough proxy for human engagement)
            human_replies = sum(
                1 for m in messages
                if not m.get("author", {}).get("bot", False)
            )
            _append({
                "type": "attention_signal",
                "channel_type": channel_type,
                "thread_id": thread_id,
                "created_at": created_at,
                "total_messages": len(messages),
                "human_replies": human_replies,
            })
        except json.JSONDecodeError:
            continue


def collect_all():
    """Run all telemetry collectors. Safe to call frequently — each collector
    handles its own dedup/idempotency."""
    collect_pr_review_latency()
    collect_master_topics()
    collect_compute_roi()
    # Note: collect_attention_signals() requires DISCORD_BOT_TOKEN in env
    # Only run if token is available
    if os.environ.get("DISCORD_BOT_TOKEN"):
        collect_attention_signals()
