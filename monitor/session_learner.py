#!/usr/bin/env python3
"""
Session Learner — extracts learnings from Patrick's interactive CC sessions.

Scans ~/.claude/projects/ for JSONL transcripts, classifies interactive vs daemon,
and extracts problem categories + solution patterns from interactive sessions.

Output:
  - knowledge/self/cc-session-learnings.md — what types of tasks Patrick does manually
  - knowledge/self/capability-gaps.md — what hurin should learn to handle

Usage: uv run --directory ~/.openclaw/monitor python session-learner.py
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
KNOWLEDGE_DIR = HOME / ".openclaw/knowledge/self"
PROCESSED_FILE = HOME / ".openclaw/monitor/processed-sessions.json"

# Session transcript locations
SESSION_DIRS = [
    HOME / ".claude/projects/-home-hurin",
    HOME / ".claude/projects/-home-hurin--openclaw-workspace-hurin-theapp",
]

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M")
log = logging.getLogger("session-learner")


def load_processed():
    """Load set of already-processed session file paths."""
    if PROCESSED_FILE.exists():
        try:
            return set(json.loads(PROCESSED_FILE.read_text()))
        except (json.JSONDecodeError, IOError):
            pass
    return set()


def save_processed(processed):
    """Save processed session paths."""
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_FILE.write_text(json.dumps(sorted(processed), indent=2))


def read_session(path):
    """Read a JSONL session file and return list of message dicts."""
    messages = []
    try:
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except (IOError, UnicodeDecodeError):
        pass
    return messages


def classify_session(messages):
    """Classify a session as 'interactive' or 'daemon'.

    Returns (classification, first_user_message)
    """
    for msg in messages:
        msg_type = msg.get("type", "")
        if msg_type == "user" or (msg_type == "human" and msg.get("message")):
            text = ""
            # Handle different message formats
            if isinstance(msg.get("message"), str):
                text = msg["message"]
            elif isinstance(msg.get("message"), dict):
                content = msg["message"].get("content", "")
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    text = " ".join(
                        b.get("text", "") for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    )

            cwd = msg.get("cwd", "")

            # Classification
            is_worktree = "-worktrees/" in cwd
            is_long = len(text) >= 500

            if is_long or is_worktree:
                return "daemon", text
            else:
                return "interactive", text

    return "unknown", ""


def extract_session_summary(messages):
    """Extract a lightweight summary from an interactive session.

    Returns dict with: problem_description, files_involved, tools_used, duration_estimate
    """
    files_involved = set()
    tools_used = set()
    user_messages = []
    assistant_messages = []

    for msg in messages:
        msg_type = msg.get("type", "")

        if msg_type in ("user", "human"):
            text = ""
            if isinstance(msg.get("message"), str):
                text = msg["message"]
            elif isinstance(msg.get("message"), dict):
                content = msg["message"].get("content", "")
                if isinstance(content, str):
                    text = content
            if text and len(text) < 2000:
                user_messages.append(text)

        elif msg_type == "assistant":
            content = msg.get("message", {})
            if isinstance(content, dict):
                for block in content.get("content", []):
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text = block.get("text", "")
                            if text and len(text) < 2000:
                                assistant_messages.append(text[:500])
                        elif block.get("type") == "tool_use":
                            tools_used.add(block.get("name", "unknown"))
                            # Extract file paths from tool inputs
                            inp = block.get("input", {})
                            if isinstance(inp, dict):
                                for key in ("file_path", "path", "command"):
                                    val = inp.get(key, "")
                                    if isinstance(val, str) and "/" in val:
                                        # Extract path-like strings
                                        for word in val.split():
                                            if "/" in word and not word.startswith("http"):
                                                files_involved.add(word.strip("'\""))

    return {
        "user_messages": user_messages[:5],  # First 5 user messages
        "assistant_summary": assistant_messages[:3],  # First 3 assistant responses
        "files_involved": sorted(files_involved)[:20],
        "tools_used": sorted(tools_used),
        "num_turns": len(user_messages),
    }


def classify_problem_type(first_message, files_involved):
    """Classify the problem type from the first user message and files."""
    msg = first_message.lower()
    files_str = " ".join(files_involved).lower()

    if any(w in msg for w in ["fix", "error", "bug", "crash", "broken", "failing"]):
        return "debugging"
    if any(w in msg for w in ["config", "setup", "install", "deploy", "service", "systemd"]):
        return "infrastructure"
    if any(w in msg for w in ["openclaw", "gateway", "daemon", "monitor", "agent"]):
        return "agent_infra"
    if any(w in msg for w in ["add", "implement", "create", "build", "new"]):
        return "feature"
    if any(w in msg for w in ["refactor", "clean", "move", "rename", "reorganize"]):
        return "refactoring"
    if any(w in msg for w in ["test", "ci", "pytest", "mock"]):
        return "testing"
    if any(w in files_str for w in [".openclaw", "monitor", "team-lead", "co-founder"]):
        return "agent_infra"
    return "general"


def run_learner():
    """Main entry point: scan, classify, extract, write."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    processed = load_processed()

    new_sessions = []

    for session_dir in SESSION_DIRS:
        if not session_dir.exists():
            continue
        for f in session_dir.glob("*.jsonl"):
            fpath = str(f)
            if fpath in processed:
                continue

            messages = read_session(f)
            if len(messages) < 3:  # Skip trivially short sessions
                processed.add(fpath)
                continue

            classification, first_msg = classify_session(messages)

            if classification == "interactive":
                summary = extract_session_summary(messages)
                problem_type = classify_problem_type(first_msg, summary["files_involved"])

                new_sessions.append({
                    "file": f.name,
                    "classification": classification,
                    "first_message": first_msg[:200],
                    "problem_type": problem_type,
                    "files_involved": summary["files_involved"][:10],
                    "tools_used": summary["tools_used"],
                    "num_turns": summary["num_turns"],
                })

            processed.add(fpath)

    if not new_sessions:
        log.info("No new interactive sessions to process.")
        save_processed(processed)
        return

    log.info(f"Found {len(new_sessions)} new interactive sessions")

    # Update cc-session-learnings.md
    learnings_file = KNOWLEDGE_DIR / "cc-session-learnings.md"
    existing = learnings_file.read_text() if learnings_file.exists() else "# CC Session Learnings\n\nTasks Patrick handles manually via interactive Claude Code sessions.\n\n"

    new_content = f"\n## Batch: {datetime.now().strftime('%Y-%m-%d')}\n\n"

    # Group by problem type
    by_type = {}
    for s in new_sessions:
        by_type.setdefault(s["problem_type"], []).append(s)

    for ptype, sessions in sorted(by_type.items()):
        new_content += f"### {ptype} ({len(sessions)} sessions)\n"
        for s in sessions:
            new_content += f"- **{s['first_message'][:100]}**\n"
            if s["files_involved"]:
                new_content += f"  Files: {', '.join(s['files_involved'][:5])}\n"
            new_content += f"  Tools: {', '.join(s['tools_used'][:5])} | Turns: {s['num_turns']}\n"
        new_content += "\n"

    learnings_file.write_text(existing + new_content)
    log.info(f"Updated {learnings_file}")

    # Update capability-gaps.md
    gaps_file = KNOWLEDGE_DIR / "capability-gaps.md"
    existing_gaps = gaps_file.read_text() if gaps_file.exists() else "# Capability Gaps\n\nWhat hurin should learn to handle autonomously.\n\n"

    # Count problem types across all sessions
    type_counts = {}
    for s in new_sessions:
        type_counts[s["problem_type"]] = type_counts.get(s["problem_type"], 0) + 1

    gaps_update = f"\n## Gap Analysis: {datetime.now().strftime('%Y-%m-%d')}\n\n"
    gaps_update += "| Problem Type | Sessions | Capability Needed |\n"
    gaps_update += "|---|---|---|\n"

    gap_descriptions = {
        "debugging": "Auto-detect and fix common errors",
        "infrastructure": "Self-manage service configs and deployments",
        "agent_infra": "Self-repair agent system issues",
        "feature": "Autonomously implement small features",
        "refactoring": "Safe, scoped refactoring with tests",
        "testing": "Fix CI and test issues autonomously",
        "general": "Varied — needs manual triage",
    }

    for ptype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        gaps_update += f"| {ptype} | {count} | {gap_descriptions.get(ptype, 'TBD')} |\n"

    gaps_file.write_text(existing_gaps + gaps_update)
    log.info(f"Updated {gaps_file}")

    save_processed(processed)
    log.info("Session learner complete.")


if __name__ == "__main__":
    run_learner()
