#!/usr/bin/env python3
"""
Co-Founder System — SDK Refactor

Replaces co-founder.sh: uses Claude Agent SDK instead of `claude -p`.
Same lens system, journal, Discord posting, action extraction.

Usage: python co-founder-sdk.py <lens-name>
Example: uv run --directory ~/.openclaw/monitor python ~/.openclaw/co-founder/co-founder-sdk.py project-pulse
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths & constants (mirrors config.sh)
# ---------------------------------------------------------------------------

HOME = Path.home()
COFOUNDER_DIR = HOME / ".openclaw/co-founder"
LENSES_DIR = COFOUNDER_DIR / "lenses"
JOURNAL = COFOUNDER_DIR / "journal.md"
THEAPP = HOME / ".openclaw/workspace-hurin/theapp"
CLAUDE_BIN = HOME / ".local/bin/claude"
BRIEFINGS_DIR = COFOUNDER_DIR / "briefings"
SESSIONS_DIR = COFOUNDER_DIR / "sessions"
ACTIONS_DIR = COFOUNDER_DIR / "actions"
PROMPT_TMPFILE = Path("/tmp/co-founder-prompt.txt")

JOURNAL_MAX_LINES = 1000
JOURNAL_CONTEXT_LINES = 100
MAX_TURNS = 10
CLAUDE_MODEL = "claude-opus-4-6"

# Discord
SECRETS_FILE = HOME / ".openclaw/secrets.json"
DISCORD_CHANNEL_ID = "1476739270663213197"
BOT_TOKEN_FILE = HOME / ".openclaw/monitor/hurin-bot-token"

# Import shared channel thread registry
sys.path.insert(0, str(HOME / ".openclaw/monitor"))
from discord_relay import (
    load_discord_token as _load_relay_token,
    register_channel_thread,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M",
)
log = logging.getLogger("co-founder")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_discord_token():
    """Load Discord bot token from secrets.json, fallback to file."""
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
    """Load GitHub PAT for bot account."""
    if BOT_TOKEN_FILE.exists():
        return BOT_TOKEN_FILE.read_text().strip()
    return ""


def run_shell(cmd, cwd=None, timeout=60):
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            cwd=cwd, timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


def fetch_master_activity(days=7):
    """Check recent direct commit activity on master across product repos."""
    repos = ["patrickkidd/familydiagram", "patrickkidd/btcopilot", "patrickkidd/fdserver"]
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    activity = {}

    for repo in repos:
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


def extract_actions_json(text):
    """Extract proposed-actions JSON from CC output text.

    Handles nested ``` inside JSON strings via brace-depth tracking.
    """
    for marker in ['proposed-actions', 'json']:
        pattern = r'```' + marker + r'\s*\n'
        m = re.search(pattern, text)
        if m:
            rest = text[m.end():]
            brace_depth = 0
            in_string = False
            escape_next = False
            for i, ch in enumerate(rest):
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\' and in_string:
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '{':
                    brace_depth += 1
                elif ch == '}':
                    brace_depth -= 1
                    if brace_depth == 0:
                        candidate = rest[:i + 1]
                        try:
                            obj = json.loads(candidate)
                            if 'actions' in obj:
                                return obj
                        except json.JSONDecodeError:
                            pass
            break
    return None


def strip_actions_block(text):
    """Remove the proposed-actions JSON block from output for clean posting."""
    return re.sub(
        r'\n*```(?:proposed-actions|json)\s*\n\s*\{[^`]*"actions"[^`]*\}\s*\n```\s*',
        '', text, flags=re.DOTALL
    )


# ---------------------------------------------------------------------------
# Discord posting (mirrors discord-post.sh)
# ---------------------------------------------------------------------------

def discord_post(message, attachment_path=None):
    """Post to #co-founder channel with threading. Returns thread ID."""
    discord_token = load_discord_token()
    if not discord_token:
        log.warning("No Discord bot token — skipping Discord post")
        return ""

    # Use the existing bash script for message splitting and threading
    cmd = [str(COFOUNDER_DIR / "discord-post.sh"), message]
    if attachment_path:
        cmd.append(str(attachment_path))

    env = os.environ.copy()
    env["DISCORD_BOT_TOKEN"] = discord_token

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, env=env,
        )
        thread_id = result.stdout.strip().split('\n')[-1] if result.stdout.strip() else ""
        if result.returncode != 0:
            log.error(f"Discord post failed: {result.stderr}")
        return thread_id
    except subprocess.TimeoutExpired:
        log.error("Discord post timed out")
        return ""


# ---------------------------------------------------------------------------
# Action routing (calls existing action-router.sh)
# ---------------------------------------------------------------------------

def fetch_open_issue_titles():
    """Fetch titles of open co-founder issues to dedup against."""
    code, out, _ = run_shell(
        'gh issue list --repo patrickkidd/theapp --label co-founder '
        '--state open --json title --limit 200 --jq ".[].title"',
        timeout=30,
    )
    if code == 0 and out:
        return [t.strip().lower() for t in out.splitlines() if t.strip()]
    return []


def dedup_and_filter_actions(actions_json):
    """Remove low-confidence actions and deduplicate against open issues.

    Returns filtered actions dict (may have fewer actions than input).
    """
    if not actions_json or "actions" not in actions_json:
        return actions_json

    existing_titles = fetch_open_issue_titles()
    original_count = len(actions_json["actions"])
    filtered = []

    for action in actions_json["actions"]:
        title = action.get("title", "")
        confidence = float(action.get("confidence", 0))
        effort = action.get("effort", "small")

        # Filter: only surface high-confidence trivial/small actions
        if confidence < 0.9:
            log.info(f"  Filtered (low confidence {confidence}): {title}")
            continue

        # Dedup: check if similar issue already exists
        title_lower = title.lower()
        is_dup = False
        for existing in existing_titles:
            # Simple substring match — catches "[co-founder] Fix X" vs "Fix X"
            existing_clean = existing.replace("[co-founder] ", "")
            if (title_lower in existing_clean or existing_clean in title_lower
                    or _title_similarity(title_lower, existing_clean) > 0.7):
                log.info(f"  Filtered (duplicate of existing issue): {title}")
                is_dup = True
                break

        if not is_dup:
            filtered.append(action)

    if len(filtered) < original_count:
        log.info(f"  Actions filtered: {original_count} → {len(filtered)}")

    actions_json["actions"] = filtered
    return actions_json


def _title_similarity(a, b):
    """Simple word-overlap similarity between two titles."""
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return 0.0
    overlap = words_a & words_b
    return len(overlap) / max(len(words_a), len(words_b))


def route_actions(actions_json_file, thread_id=""):
    """Route actions via existing action-router.sh."""
    cmd = [str(COFOUNDER_DIR / "action-router.sh"), str(actions_json_file)]
    if thread_id:
        cmd.append(thread_id)

    env = os.environ.copy()
    env["GH_TOKEN"] = load_gh_token()

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, env=env,
        )
        if result.returncode != 0:
            log.error(f"Action router failed: {result.stderr}")
        else:
            log.info(f"Action router output: {result.stdout}")
    except subprocess.TimeoutExpired:
        log.error("Action router timed out")


# ---------------------------------------------------------------------------
# Git commit helpers
# ---------------------------------------------------------------------------

def git_commit_and_push(files, message):
    """Commit and push files in ~/.openclaw repo."""
    openclaw_dir = str(HOME / ".openclaw")
    for f in files:
        run_shell(f"git add {f}", cwd=openclaw_dir)
    run_shell(
        f'git commit -m "{message}" --no-gpg-sign',
        cwd=openclaw_dir,
    )
    rc, out, err = run_shell(
        'git -c "credential.helper=!gh auth git-credential" push',
        cwd=openclaw_dir,
    )
    if rc != 0:
        log.warning(f"git push failed: {err}")
    else:
        log.info(f"Committed and pushed: {message}")


# ---------------------------------------------------------------------------
# Main: run a co-founder lens via Agent SDK
# ---------------------------------------------------------------------------

async def run_lens(lens_name):
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage

    lens_file = LENSES_DIR / f"{lens_name}.md"
    if not lens_file.exists():
        available = [f.stem for f in LENSES_DIR.glob("*.md")]
        log.error(f"Lens not found: {lens_name}. Available: {available}")
        sys.exit(1)

    log.info(f"Running co-founder lens: {lens_name}")

    # Ensure directories
    BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    ACTIONS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Read lens prompt
    lens_prompt = lens_file.read_text()

    # 2. Read journal context
    journal_context = ""
    if JOURNAL.exists():
        lines = JOURNAL.read_text().splitlines()
        journal_context = "\n".join(lines[-JOURNAL_CONTEXT_LINES:])

    # 2b. Fetch recent master commit activity
    master_activity = fetch_master_activity(7)
    master_summary = ""
    if master_activity:
        total = sum(r["commit_count"] for r in master_activity.values())
        master_summary = f"Total: {total} direct master commits in the last 7 days.\n\n"
        for repo, data in master_activity.items():
            master_summary += f"**{repo}** ({data['commit_count']} commits, latest: {data.get('latest', '?')}):\n"
            for msg in data.get("recent_messages", [])[:10]:
                master_summary += f"  - {msg}\n"
            master_summary += "\n"
    else:
        master_summary = "No direct master commits in the last 7 days.\n"

    # 3. Assemble full prompt (same structure as co-founder.sh)
    prompt = f"""{lens_prompt}

---

## Your Previous Journal Entries (last {JOURNAL_CONTEXT_LINES} lines)

Use these to build continuity — reference your own past observations, track how things evolve, and avoid repeating yourself.

{journal_context}

---

## Recent Direct Work (IMPORTANT — read before proposing any actions)

Patrick works interactively with Claude Code, pushing directly to master (branch by abstraction).
This work does NOT go through the task daemon or create PRs.
Do NOT propose actions that duplicate or conflict with recently committed work.

{master_summary}

## Key Project Locations

Read these files for current project state:
- TODO/roadmap: {THEAPP}/TODO.md
- Project instructions: {THEAPP}/CLAUDE.md
- Decision log: {THEAPP}/btcopilot/decisions/log.md
- Agent architecture: {HOME}/.openclaw/adrs/ADR-0001-agent-swarm.md
- Architecture status: {HOME}/.openclaw/adrs/ADR-0001-status.md
- FamilyDiagram app: {THEAPP}/familydiagram/
- BTCoPilot backend: {THEAPP}/btcopilot/
- Pro app: {THEAPP}/btcopilot-sources/

## Analysis Approach

You have **{MAX_TURNS} turns** available. Use them. Do not rush to produce output on the first turn.

**Suggested workflow:**
1. **Turn 1-3: Gather data.** Read project files, run shell commands (git log, gh pr list, find, wc -l, grep, etc.), explore the codebase. Collect concrete evidence.
2. **Turn 4-6: Dig deeper.** Investigate specific areas that warrant attention. Read source files, check test coverage, analyze patterns. Follow threads that surprise you.
3. **Turn 7+: Synthesize.** Write your briefing with specific citations — file paths, line numbers, PR numbers, commit hashes, concrete metrics.

**Do NOT constrain your output length.** A 2000-word briefing with concrete evidence is better than a 500-word summary of vibes. Write as much as the analysis warrants. Be specific and cite your sources.

## Output Format

Format your response for readability:
- Use **bold** for section labels
- Use bullet points (- ) for items
- Do NOT use markdown # headers
- End with one uncomfortable question for Patrick

## Quick Wins

If your analysis surfaces anything that meets ALL of these criteria, propose it as an action:

1. **Claude Code can fully implement it end-to-end** — no human judgment calls, no design decisions, no ambiguous scope
2. **It delivers clear, concrete value** — fixes a real bug, removes dead code that causes confusion, adds a missing index that prevents a production issue, removes redundant operations, unblocks a stuck PR, or creates content that drives traffic/signups
3. **The effort is genuinely trivial/small** — a focused CC session can ship it in one PR
4. **You are highly confident it's correct** — you've read the relevant code and understand the change

**Be thorough.** Every concrete finding in your briefing that has a clear mechanical fix should become an action. If you describe a problem with a known solution (dead code, missing index, redundant call, deprecated dependency with a drop-in replacement), propose it. Propose every action that genuinely clears this bar — whether that's zero or ten.

**Not quick wins:** speculative improvements, large-scale refactors requiring design decisions, test additions without a concrete bug, things requiring Patrick's product judgment, anything where you're unsure about the approach, "nice to have" architectural changes.

If something genuinely qualifies, add a ```proposed-actions code block at the very end:

```
```proposed-actions
{{
  "actions": [
    {{
      "id": "{lens_name}-{datetime.now().strftime('%Y-%m-%d')}-<n>",
      "title": "Short imperative description",
      "category": "revenue|ux|velocity|bugfix|content|infrastructure",
      "effort": "trivial|small",
      "confidence": 0.0-1.0,
      "repo": "btcopilot|familydiagram|website|none",
      "plan": "Step-by-step implementation plan",
      "spawn_prompt": "Full self-contained prompt for Claude Code — include file paths, context, acceptance criteria",
      "success_metric": "How we know this worked"
    }}
  ]
}}
```
```

Every action requires Patrick's approval before spawning. There is no auto-spawn tier.

**spawn_prompt quality bar:** It must be a complete, self-contained prompt that another CC instance could execute cold — specific files, specific changes, specific acceptance criteria. If you can't write a crisp spawn_prompt, the action isn't ready.
"""

    # 4. Run via Agent SDK
    log.info(f"Calling Agent SDK (model={CLAUDE_MODEL}, max_turns={MAX_TURNS})...")

    sdk_env = {
        "GH_TOKEN": load_gh_token(),
        "PATH": "/usr/local/bin:" + str(HOME / ".local/bin") + ":" + os.environ.get("PATH", ""),
        "HOME": str(HOME),
    }

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

    # 5. Save session ID for follow-up
    if session_id:
        session_file = SESSIONS_DIR / f"{lens_name}-session.txt"
        session_file.write_text(session_id)
        log.info(f"Session saved: {session_id}")

    # 6. Save full briefing
    briefing_date = datetime.now().strftime("%Y-%m-%d")
    briefing_file = BRIEFINGS_DIR / f"{lens_name}-{briefing_date}.md"
    briefing_file.write_text(
        f"# Co-Founder Briefing: {lens_name}\n"
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}\n"
        f"**Session:** {session_id or 'unknown'}\n"
        f"**Turns:** {MAX_TURNS} max\n"
        f"**Model:** {CLAUDE_MODEL}\n\n"
        f"---\n\n"
        f"{cc_output}\n"
    )
    # Update latest symlink
    latest_link = BRIEFINGS_DIR / f"{lens_name}-latest.md"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(f"{lens_name}-{briefing_date}.md")
    log.info(f"Briefing saved: {briefing_file}")

    # 6b. Commit and push briefing
    git_commit_and_push(
        [f"co-founder/briefings/{lens_name}-{briefing_date}.md"],
        f"co-founder: {lens_name} briefing {briefing_date}",
    )

    # 7. Extract actions JSON and strip from output
    actions_json = extract_actions_json(cc_output)
    cc_output_clean = strip_actions_block(cc_output) if actions_json else cc_output

    actions_file = None
    has_actions = False

    if actions_json:
        raw_count = len(actions_json.get("actions", []))
        actions_json = dedup_and_filter_actions(actions_json)
        action_count = len(actions_json.get("actions", []))
        log.info(f"Actions: {raw_count} extracted, {action_count} after dedup/filter")

        if action_count > 0:
            actions_file = ACTIONS_DIR / f"{lens_name}-{briefing_date}.json"
            actions_file.write_text(json.dumps(actions_json, indent=2))
            has_actions = True

            git_commit_and_push(
                [f"co-founder/actions/{lens_name}-{briefing_date}.json"],
                f"co-founder: {lens_name} actions {briefing_date}",
            )
        else:
            log.info("All actions filtered out by dedup/confidence gate")
    else:
        log.info("No actions proposed (normal)")

    # 8. Append to journal (clean output)
    with open(JOURNAL, "a") as f:
        f.write(
            f"\n## [{lens_name}] {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}\n\n"
            f"{cc_output_clean}\n\n---\n"
        )

    # 9. Trim journal
    if JOURNAL.exists():
        lines = JOURNAL.read_text().splitlines()
        if len(lines) > JOURNAL_MAX_LINES:
            trim = len(lines) - JOURNAL_MAX_LINES
            JOURNAL.write_text("\n".join(lines[trim:]) + "\n")
            log.info(f"Trimmed journal by {trim} lines")

    # 10. Post to Discord
    now_str = datetime.now().strftime("%a %b %d, %H:%M %Z")
    discord_header = f"🧠 **Co-Founder — {lens_name}** | {now_str}"
    discord_footer = f"💬 Follow up: `/cofounder followup {lens_name} <your question>`"
    discord_message = f"{discord_header}\n\n{cc_output_clean}\n\n{discord_footer}"

    thread_id = discord_post(discord_message, briefing_file)
    if thread_id:
        log.info(f"Discord thread created: {thread_id}")
        # Register thread for reply monitoring
        _load_relay_token()
        register_channel_thread(
            thread_id=thread_id,
            channel_type="cofounder",
            channel_id=DISCORD_CHANNEL_ID,
            session_id=session_id,
            context_file=str(briefing_file),
            label=f"CF {lens_name}",
        )

    # 11. Route actions
    if has_actions and actions_file:
        route_actions(actions_file, thread_id)

    log.info(f"Done: {lens_name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <lens-name>", file=sys.stderr)
        print(f"Available: {[f.stem for f in LENSES_DIR.glob('*.md')]}", file=sys.stderr)
        sys.exit(1)

    lens = sys.argv[1]
    asyncio.run(run_lens(lens))
