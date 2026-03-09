#!/usr/bin/env python3
"""
Chief of Staff — Opus-powered meta-orchestrator.

Runs 2x/week (Tuesday + Friday). Evaluates the entire agent system,
curates a strategic digest, and posts to #chief-of-staff for Patrick.

Usage: uv run --directory ~/.openclaw/monitor python ~/.openclaw/chief-of-staff/chief-of-staff.py

Architecture position:
  Patrick
    └── chief-of-staff (Opus, 2x/week)
          ├── co-founder (Opus, lenses)
          ├── team-lead (Opus, hourly)
          ├── heartbeat (shell, cron)
          └── task daemon (Opus, continuous)
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

HOME = Path.home()
COS_DIR = HOME / ".openclaw/chief-of-staff"
DIGESTS_DIR = COS_DIR / "digests"
CLAUDE_BIN = HOME / ".local/bin/claude"
THEAPP = HOME / ".openclaw/workspace-hurin/theapp"

# Agent system paths
SYNTHESES_DIR = HOME / ".openclaw/team-lead/syntheses"
METRICS_LOG = HOME / ".openclaw/team-lead/metrics-log.jsonl"
BRIEFINGS_DIR = HOME / ".openclaw/co-founder/briefings"
ACTIONS_DIR = HOME / ".openclaw/co-founder/actions"
TASK_EVENTS = HOME / ".openclaw/monitor/task-events.jsonl"
TASK_REGISTRY = THEAPP / ".clawdbot/active-tasks.json"
SECRETS_FILE = HOME / ".openclaw/secrets.json"
BOT_TOKEN_FILE = HOME / ".openclaw/monitor/hurin-bot-token"

# Discord — #planning channel
# Update this once the channel exists, or create it first
DISCORD_PLANNING_CHANNEL_ID = "1479984919353626674"  # #chief-of-staff

# Knowledge base
KNOWLEDGE_DIR = HOME / ".openclaw/knowledge"
SPAWN_POLICY_FILE = KNOWLEDGE_DIR / "self/spawn-policy.json"
TELEMETRY_FILE = KNOWLEDGE_DIR / "self/telemetry.jsonl"
KB_INDEX = KNOWLEDGE_DIR / "index.md"
CAPABILITY_GAPS = KNOWLEDGE_DIR / "self/capability-gaps.md"

# Add monitor dir to path for discord_relay import
sys.path.insert(0, str(HOME / ".openclaw/monitor"))
from discord_relay import (
    discord_api as _discord_api,
    load_discord_token as _load_relay_token,
    create_channel_thread,
    post_to_channel_thread,
    register_channel_thread,
)

CLAUDE_MODEL = "claude-opus-4-6"
MAX_TURNS = 12

# Product repos
REPOS = ["patrickkidd/familydiagram", "patrickkidd/btcopilot", "patrickkidd/fdserver"]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M",
)
log = logging.getLogger("chief-of-staff")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_discord_token():
    if SECRETS_FILE.exists():
        try:
            secrets = json.loads(SECRETS_FILE.read_text())
            token = secrets.get("discord-bot-token", "")
            if token:
                return token
        except (json.JSONDecodeError, KeyError):
            pass
    token_file = HOME / ".openclaw/monitor/discord-bot-token"
    if token_file.exists():
        return token_file.read_text().strip()
    return ""


def load_gh_token():
    if BOT_TOKEN_FILE.exists():
        return BOT_TOKEN_FILE.read_text().strip()
    return ""


def run_shell(cmd, cwd=None, timeout=60):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            cwd=cwd, timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


# ---------------------------------------------------------------------------
# Data collection — gather inputs for the prompt
# ---------------------------------------------------------------------------


def collect_recent_syntheses(days=4):
    """Read team-lead syntheses from the last N days."""
    if not SYNTHESES_DIR.exists():
        return "No syntheses found."

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    entries = []

    for f in sorted(SYNTHESES_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            # Parse timestamp from filename (hourly-2026-03-07T1803.json)
            ts_str = f.stem.split("-", 1)[1] if "-" in f.stem else ""
            entries.append({
                "file": f.name,
                "health_summary": data.get("health_summary", ""),
                "recommendations": data.get("recommendations", []),
                "goal_status": data.get("goal_status", []),
            })
        except (json.JSONDecodeError, KeyError):
            continue
        if len(entries) >= 10:
            break

    if not entries:
        return "No recent syntheses."

    lines = []
    for e in entries:
        lines.append(f"### {e['file']}")
        lines.append(f"Health: {e['health_summary']}")
        if e["recommendations"]:
            for r in e["recommendations"]:
                lines.append(f"  - [{r.get('priority', '?')}] {r.get('title', '?')}: {r.get('rationale', '')}")
        lines.append("")
    return "\n".join(lines)


def collect_recent_briefings(days=7):
    """Read co-founder briefing filenames and summaries from last N days."""
    if not BRIEFINGS_DIR.exists():
        return "No briefings found."

    entries = []
    for f in sorted(BRIEFINGS_DIR.glob("*.md"), reverse=True):
        if f.name.endswith("-latest.md"):
            continue
        try:
            content = f.read_text()
            # Take first 500 chars as summary
            entries.append(f"### {f.name}\n{content[:500]}...\n")
        except Exception:
            continue
        if len(entries) >= 8:
            break

    return "\n".join(entries) if entries else "No recent briefings."


def collect_action_outcomes(days=14):
    """Summarize co-founder actions: proposed vs approved vs completed."""
    if not ACTIONS_DIR.exists():
        return "No action history."

    total_proposed = 0
    total_actions = []

    for f in sorted(ACTIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            actions = data.get("actions", [])
            total_proposed += len(actions)
            for a in actions:
                total_actions.append({
                    "file": f.name,
                    "title": a.get("title", "?"),
                    "confidence": a.get("confidence", 0),
                    "effort": a.get("effort", "?"),
                    "category": a.get("category", "?"),
                })
        except (json.JSONDecodeError, KeyError):
            continue

    if not total_actions:
        return "No actions proposed."

    # Check which ones became issues/PRs
    code, out, _ = run_shell(
        'gh issue list --repo patrickkidd/theapp --label co-founder '
        '--state all --json title,state --limit 200',
        timeout=30,
    )
    approved = []
    if code == 0 and out:
        try:
            approved = json.loads(out)
        except json.JSONDecodeError:
            pass

    approved_count = len(approved)
    closed_count = sum(1 for i in approved if i.get("state") == "CLOSED")

    return (
        f"**Actions summary (last {days} days):**\n"
        f"- Proposed: {total_proposed}\n"
        f"- Approved (became issues): {approved_count}\n"
        f"- Completed (closed): {closed_count}\n"
        f"- Approval rate: {approved_count/max(total_proposed,1)*100:.0f}%\n\n"
        f"Recent actions:\n" +
        "\n".join(f"  - [{a['confidence']:.1f}] {a['title']} ({a['effort']}, {a['category']})"
                 for a in total_actions[:10])
    )


def collect_task_stats(days=7):
    """Summarize task daemon activity."""
    if not TASK_EVENTS.exists():
        return "No task events."

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events = []
    try:
        for line in TASK_EVENTS.read_text().splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
                events.append(e)
            except json.JSONDecodeError:
                continue
    except Exception:
        return "Failed to read task events."

    if not events:
        return "No task events recorded."

    # Count by event type
    counts = {}
    for e in events:
        evt = e.get("event", "unknown")
        counts[evt] = counts.get(evt, 0) + 1

    # Task registry
    registry_info = ""
    if TASK_REGISTRY.exists():
        try:
            reg = json.loads(TASK_REGISTRY.read_text())
            tasks = reg.get("tasks", []) if isinstance(reg, dict) else reg
            by_status = {}
            for t in tasks:
                s = t.get("status", "unknown") if isinstance(t, dict) else "unknown"
                by_status[s] = by_status.get(s, 0) + 1
            registry_info = f"Registry: {dict(by_status)}"
        except (json.JSONDecodeError, KeyError):
            pass

    lines = [f"**Task daemon (last {days} days):**"]
    for evt, cnt in sorted(counts.items()):
        lines.append(f"  - {evt}: {cnt}")
    if registry_info:
        lines.append(registry_info)
    return "\n".join(lines)


def collect_metrics_snapshot():
    """Get latest metrics from metrics-log.jsonl."""
    if not METRICS_LOG.exists():
        return "No metrics log."

    last_line = ""
    try:
        for line in METRICS_LOG.read_text().splitlines():
            if line.strip():
                last_line = line
    except Exception:
        return "Failed to read metrics."

    if not last_line:
        return "Empty metrics log."

    try:
        m = json.loads(last_line)
        return (
            f"**Latest metrics:**\n"
            f"- Velocity (7d): {m.get('velocity_7d', '?')} tasks/day\n"
            f"- Cycle time: {m.get('cycle_time_hours', '?')} hours\n"
            f"- Success rate (30d): {m.get('success_rate_30d', '?')}\n"
            f"- Queue length: {m.get('queue_length', '?')}\n"
            f"- Running tasks: {m.get('running_tasks', '?')}\n"
            f"- CI master: {m.get('ci_master', '?')}\n"
            f"- Direct master commits (7d): {m.get('direct_master_commits_7d', '?')}\n"
            f"- Master activity: {json.dumps(m.get('master_activity', {}))}\n"
        )
    except json.JSONDecodeError:
        return "Malformed metrics."


def fetch_master_activity(days=7):
    """Recent direct commit activity on master across product repos."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    activity = {}

    for repo in REPOS:
        code, out, _ = run_shell(
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
                first_line = msg.split("\n")[0] if msg else ""
                commits.append({
                    "sha": c.get("sha", "")[:8],
                    "message": first_line,
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

    if not activity:
        return "No direct master commits in the last 7 days."

    total = sum(r["commit_count"] for r in activity.values())
    lines = [f"**Direct master activity (last {days} days): {total} commits**\n"]
    for repo, data in activity.items():
        lines.append(f"**{repo}** ({data['commit_count']} commits, latest: {data.get('latest', '?')}):")
        for msg in data.get("recent_messages", [])[:8]:
            lines.append(f"  - {msg}")
        lines.append("")
    return "\n".join(lines)


def collect_service_health():
    """Check systemd service status."""
    services = ["openclaw-gateway", "openclaw-taskdaemon", "openclaw-teamlead"]
    lines = ["**Service health:**"]
    for svc in services:
        code, out, _ = run_shell(f"systemctl --user is-active {svc}")
        lines.append(f"  - {svc}: {out or 'unknown'}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Discord posting
# ---------------------------------------------------------------------------


def load_secrets():
    """Load all secrets from secrets.json."""
    if SECRETS_FILE.exists():
        try:
            return json.loads(SECRETS_FILE.read_text())
        except (json.JSONDecodeError, KeyError):
            pass
    return {}


def discord_post_digest(message, session_id="", digest_file=""):
    """Post digest to #chief-of-staff as a threaded message.

    Creates a thread on the first message so Patrick can reply to it.
    Registers the thread for reply monitoring by the task daemon.
    Returns the thread_id or None.
    """
    # Initialize discord_relay token
    _load_relay_token()

    now = datetime.now()
    thread_name = f"COS Digest {now.strftime('%b %d')}"

    # Split message: first chunk becomes the channel message, rest goes in thread
    chunks = []
    current = ""
    for line in message.split("\n"):
        if current and len(current) + len(line) + 1 > 1900:
            chunks.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)

    if not chunks:
        return None

    first_chunk = chunks[0]
    if len(first_chunk) > 2000:
        first_chunk = first_chunk[:1997] + "..."

    # Create thread on the first message
    thread_id, msg_id = create_channel_thread(
        DISCORD_PLANNING_CHANNEL_ID, first_chunk, thread_name
    )
    if not thread_id:
        log.error("Failed to create Discord thread for digest")
        return None

    # Post remaining chunks in the thread
    for chunk in chunks[1:]:
        if len(chunk) > 2000:
            chunk = chunk[:1997] + "..."
        _discord_api(
            "POST",
            f"https://discord.com/api/v10/channels/{thread_id}/messages",
            {"content": chunk},
        )
        time.sleep(0.5)

    # Post a footer inviting replies
    _discord_api(
        "POST",
        f"https://discord.com/api/v10/channels/{thread_id}/messages",
        {"content": "💬 Reply in this thread to discuss — I'll pick up your message and respond with full context."},
    )

    # Register for reply monitoring
    register_channel_thread(
        thread_id=thread_id,
        channel_type="cos",
        channel_id=DISCORD_PLANNING_CHANNEL_ID,
        session_id=session_id,
        context_file=digest_file,
        label=thread_name,
    )

    log.info(f"Posted digest as thread: {thread_id}")
    return thread_id


# ---------------------------------------------------------------------------
# Previous digest context (conversational continuity)
# ---------------------------------------------------------------------------


def load_previous_digest():
    """Load the most recent digest for conversational continuity."""
    if not DIGESTS_DIR.exists():
        return ""
    digest_files = sorted(DIGESTS_DIR.glob("digest-*.md"), reverse=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    for f in digest_files:
        if today_str not in f.name:
            try:
                content = f.read_text()
                if len(content) > 4000:
                    content = content[:4000] + "\n...(truncated)"
                return content
            except Exception:
                return ""
    return ""


# ---------------------------------------------------------------------------
# Knowledge base data collection
# ---------------------------------------------------------------------------


def collect_spawn_policy():
    """Read spawn policy for COS context."""
    if not SPAWN_POLICY_FILE.exists():
        return "No spawn policy configured yet."
    try:
        policy = json.loads(SPAWN_POLICY_FILE.read_text())
        lines = [f"**Spawn Policy** (updated: {policy.get('last_updated', '?')})"]
        for cat, data in policy.get("categories", {}).items():
            lines.append(
                f"  - {cat}: {data.get('autonomy', '?')} "
                f"(accuracy={data.get('accuracy', 0)*100:.0f}%, "
                f"n={data.get('total', 0)}, correct={data.get('correct', 0)})"
            )
        lines.append(f"  Default: {policy.get('default_autonomy', 'propose_only')}")
        return "\n".join(lines)
    except (json.JSONDecodeError, IOError):
        return "Spawn policy file unreadable."


def collect_kb_summary():
    """Summarize KB index and entry counts."""
    if not KNOWLEDGE_DIR.exists():
        return "Knowledge base not initialized."
    lines = ["**Knowledge Base Summary:**"]
    for subdir in ["domain", "market", "technical", "strategy", "self", "users"]:
        path = KNOWLEDGE_DIR / subdir
        if path.exists():
            files = list(path.glob("*.md")) + list(path.glob("*.json"))
            lines.append(f"  - {subdir}/: {len(files)} entries")
        else:
            lines.append(f"  - {subdir}/: (empty)")
    return "\n".join(lines)


def collect_telemetry_summary():
    """Summarize recent telemetry entries."""
    if not TELEMETRY_FILE.exists():
        return "No telemetry data yet."
    try:
        entries = []
        for line in TELEMETRY_FILE.read_text().splitlines()[-50:]:
            if line.strip():
                entries.append(json.loads(line))
    except (json.JSONDecodeError, IOError):
        return "Telemetry file unreadable."

    if not entries:
        return "Empty telemetry."

    by_type = {}
    for e in entries:
        t = e.get("type", "unknown")
        by_type.setdefault(t, []).append(e)

    lines = ["**Recent Telemetry:**"]
    for t, items in by_type.items():
        lines.append(f"  - {t}: {len(items)} entries")
        if t == "compute_roi" and items:
            latest = items[-1]
            lines.append(
                f"    ROI ratio: {latest.get('roi_ratio', '?')} "
                f"(merged: {latest.get('merged_minutes', 0):.0f}min, "
                f"discarded: {latest.get('discarded_minutes', 0):.0f}min)"
            )
        elif t == "master_topics" and items:
            latest = items[-1]
            topics = latest.get("topics", {})
            top = sorted(topics.items(), key=lambda x: -x[1])[:5]
            lines.append(f"    Top topics: {', '.join(f'{k}({v})' for k,v in top)}")
    return "\n".join(lines)


def collect_capability_gaps():
    """Read capability gaps from session learner."""
    if not CAPABILITY_GAPS.exists():
        return "No capability gap analysis yet."
    try:
        content = CAPABILITY_GAPS.read_text()
        if len(content) > 1500:
            content = content[:1500] + "\n...(truncated)"
        return content
    except IOError:
        return "Capability gaps file unreadable."


# ---------------------------------------------------------------------------
# Main: build prompt, run via Agent SDK, post digest
# ---------------------------------------------------------------------------


async def run_digest():
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage

    log.info("Chief of Staff: collecting system data...")

    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)

    # Collect all inputs
    syntheses = collect_recent_syntheses(days=4)
    briefings = collect_recent_briefings(days=7)
    action_outcomes = collect_action_outcomes(days=14)
    task_stats = collect_task_stats(days=7)
    metrics = collect_metrics_snapshot()
    master_activity = fetch_master_activity(days=7)
    service_health = collect_service_health()
    previous_digest = load_previous_digest()

    # New: KB + policy + telemetry context
    spawn_policy = collect_spawn_policy()
    kb_summary = collect_kb_summary()
    telemetry_summary = collect_telemetry_summary()
    capability_gaps = collect_capability_gaps()

    prompt = f"""You are the Chief of Staff for an AI agent system supporting Patrick's software development.

Your job is to evaluate the ENTIRE system — not just the project, but how well the agent infrastructure is serving Patrick — and produce a concise strategic digest.

## Your Role

You sit above team-lead (hourly synthesis) and co-founder (deep lens analysis). They generate raw intelligence. You CURATE it: what actually matters, what's noise, what's missing.

Patrick is a solo founder building a personal app MVP (familydiagram + btcopilot backend). He works interactively with Claude Code, pushing directly to master. The agent system (task daemon, team-lead, co-founder) supplements his work.

## System Data

{service_health}

{metrics}

{master_activity}

{task_stats}

{action_outcomes}

## Spawn Policy (per-category autonomy)

{spawn_policy}

## Knowledge Base

{kb_summary}

{telemetry_summary}

## Capability Gaps (from CC session analysis)

{capability_gaps}

## Team-Lead Syntheses (last 4 days)

{syntheses}

## Co-Founder Briefings (last 7 days)

{briefings}

## Previous Digest

{previous_digest if previous_digest else "No previous digest available (first run)."}

## Your Analysis

Reference your previous digest where relevant: note what changed since last time, what stalled, what was wrong. Track trends across digests rather than evaluating in isolation.

You have **{MAX_TURNS} turns**. Use them to investigate deeply:

1. **Turns 1-3: Investigate.** Read project files ({THEAPP}/TODO.md, {THEAPP}/CLAUDE.md, decision logs). Check git logs across repos. Look at what Patrick has actually been working on vs what the agents think he's working on.

2. **Turns 4-7: Evaluate the system.** Check team-lead synthesis quality, co-founder action relevance, task daemon success patterns. Look at the gap between agent outputs and reality.

3. **Turns 8+: Synthesize your digest.**

## Output Format

Produce a structured digest with these sections:

**SYSTEM HEALTH** (2-3 sentences)
How well is the agent infrastructure serving Patrick right now? Are the services stable, the outputs useful, the signal-to-noise ratio good?

**PROJECT MOMENTUM** (3-5 bullets)
What has Patrick actually accomplished this period? Use git evidence, not agent assumptions. Where is the real progress vs where do the agents think it is?

**AGENT EFFECTIVENESS** (3-5 bullets)
Evaluate each component:
- Team-lead: Are syntheses accurate? Useful? Or noise?
- Co-founder: Are briefings insightful? Are proposed actions worth Patrick's time?
- Task daemon: Is it being utilized? Success rate? Bottlenecks?
- Information gaps: What can't the agents see that they should?

**TOP 3 RECOMMENDATIONS** (numbered, specific)
One sentence each. Mix of product and system improvements. Only things that are actionable THIS WEEK.

**SYSTEM EVOLUTION** (2-3 bullets)
- Is the knowledge base growing? Are entries being updated (not just appended)?
- Are spawn policy categories graduating or stagnating?
- What should the system research next? (identify knowledge gaps)
- Any self-repair proposals? (infrastructure fixes the system should make autonomously)

**THE UNCOMFORTABLE QUESTION**
One question Patrick probably doesn't want to think about but should. Could be about product strategy, agent ROI, technical debt, market timing, or resource allocation.

## Rules

- Be HONEST about agent system ROI. If the system is producing more noise than signal, say so.
- Cite specific evidence: commit hashes, synthesis files, action approval rates.
- Don't repeat what team-lead or co-founder already said — add value above their analysis.
- If an agent component is consistently wrong or unhelpful, recommend turning it off.
- Keep the digest under 1500 words. Patrick's time is the scarcest resource.
- Do NOT use markdown # headers. Use **bold** for section labels.
- Do NOT propose actions or spawn tasks. This is strategic advice only.
"""

    log.info(f"Running Agent SDK (model={CLAUDE_MODEL}, max_turns={MAX_TURNS})...")

    gh_token = load_gh_token()
    sdk_env = {
        "PATH": "/usr/local/bin:" + str(HOME / ".local/bin") + ":" + os.environ.get("PATH", ""),
        "HOME": str(HOME),
        "CLAUDECODE": "",  # unset to allow nested session
    }
    if gh_token:
        sdk_env["GH_TOKEN"] = gh_token

    options = ClaudeAgentOptions(
        model=CLAUDE_MODEL,
        permission_mode="bypassPermissions",
        cwd=str(THEAPP),
        env=sdk_env,
        cli_path=str(CLAUDE_BIN),
        max_turns=MAX_TURNS,
        setting_sources=["project"],
    )

    cc_output = ""
    session_id = ""

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    cc_output = message.result or ""
                    session_id = getattr(message, 'session_id', '') or getattr(client, 'session_id', '') or ''
                    break
    except Exception as e:
        log.error(f"Agent SDK error: {e}")
        sys.exit(1)

    if not cc_output:
        log.error("Empty response from Agent SDK")
        sys.exit(1)

    log.info(f"SDK returned {len(cc_output)} chars")

    # Save digest
    now = datetime.now()
    digest_date = now.strftime("%Y-%m-%d")
    day_name = now.strftime("%A")
    digest_file = DIGESTS_DIR / f"digest-{digest_date}.md"
    digest_file.write_text(
        f"# Chief of Staff Digest\n"
        f"**Date:** {now.strftime('%Y-%m-%d %H:%M %Z')} ({day_name})\n"
        f"**Session:** {session_id or 'unknown'}\n"
        f"**Model:** {CLAUDE_MODEL}\n\n"
        f"---\n\n"
        f"{cc_output}\n"
    )
    log.info(f"Digest saved: {digest_file}")

    # Save session metadata for potential future resume
    session_meta = {
        "date": digest_date,
        "session_id": session_id,
        "model": CLAUDE_MODEL,
        "digest_file": str(digest_file),
    }
    (DIGESTS_DIR / "last-session.json").write_text(json.dumps(session_meta, indent=2))

    # Post to Discord as thread (enables replies)
    header = f"📋 **Chief of Staff Digest** | {now.strftime('%A %b %d, %Y')}"
    discord_message = f"{header}\n\n{cc_output}"
    thread_id = discord_post_digest(discord_message, session_id=session_id, digest_file=str(digest_file))
    if thread_id:
        session_meta["thread_id"] = thread_id
        (DIGESTS_DIR / "last-session.json").write_text(json.dumps(session_meta, indent=2))

    # Git commit
    openclaw_dir = str(HOME / ".openclaw")
    run_shell(f"git add chief-of-staff/digests/digest-{digest_date}.md", cwd=openclaw_dir)
    run_shell(
        f'git commit -m "chief-of-staff: digest {digest_date}" --no-gpg-sign',
        cwd=openclaw_dir,
    )
    rc, _, err = run_shell(
        'git -c "credential.helper=!gh auth git-credential" push',
        cwd=openclaw_dir,
    )
    if rc != 0:
        log.warning(f"git push failed: {err}")
    else:
        log.info("Committed and pushed digest")

    log.info("Done.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(run_digest())
