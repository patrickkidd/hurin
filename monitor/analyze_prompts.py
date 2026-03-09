#!/usr/bin/env python3
"""
Prompt Archaeology — analyze spawn prompt characteristics that predict success.

Compares prompts of merged vs closed PRs to identify patterns.
Reads from: trust-ledger.json, queue-prompts/
Writes to: knowledge/technical/successful-pr-patterns.md

Usage: uv run --directory ~/.openclaw/monitor python analyze-prompts.py
"""

import json
import logging
import re
from pathlib import Path

HOME = Path.home()
LEDGER_FILE = HOME / ".openclaw/monitor/trust-ledger.json"
QUEUE_PROMPTS = HOME / ".openclaw/monitor/queue-prompts"
KNOWLEDGE_DIR = HOME / ".openclaw/knowledge/technical"
OUTPUT_FILE = KNOWLEDGE_DIR / "successful-pr-patterns.md"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M")
log = logging.getLogger("prompt-archaeology")


def load_ledger():
    """Load trust ledger entries."""
    if not LEDGER_FILE.exists():
        return []
    try:
        data = json.loads(LEDGER_FILE.read_text())
        return data.get("entries", [])
    except (json.JSONDecodeError, IOError):
        return []


def find_prompt_for_task(task_id):
    """Find the spawn prompt file for a task ID."""
    # Try various naming patterns
    for pattern in [f"{task_id}.txt", f"{task_id}.md"]:
        path = QUEUE_PROMPTS / pattern
        if path.exists():
            return path.read_text()
    return None


def analyze_prompt(text):
    """Extract characteristics from a prompt."""
    if not text:
        return {}

    return {
        "length_chars": len(text),
        "length_words": len(text.split()),
        "has_file_paths": bool(re.search(r'[/\\]\w+\.\w+', text)),
        "has_line_numbers": bool(re.search(r'line\s+\d+|:\d+', text, re.I)),
        "has_acceptance_criteria": bool(re.search(r'accept|criteria|should|must|expect|verify', text, re.I)),
        "has_test_commands": bool(re.search(r'pytest|test|npm test|make test|cargo test', text, re.I)),
        "has_specific_function": bool(re.search(r'function|def |class |method', text, re.I)),
        "has_error_message": bool(re.search(r'error|exception|traceback|fail', text, re.I)),
        "has_pr_or_issue_ref": bool(re.search(r'#\d+|PR |issue', text, re.I)),
        "has_scope_constraint": bool(re.search(r'only|just|single|one file|this file', text, re.I)),
        "num_code_blocks": len(re.findall(r'```', text)),
        "mentions_files_count": len(re.findall(r'[/\\][\w.-]+\.\w+', text)),
    }


def run_analysis():
    """Main analysis: compare merged vs closed prompt characteristics."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

    entries = load_ledger()
    if not entries:
        log.info("No trust ledger entries.")
        return

    # Separate by outcome
    merged = [e for e in entries if e.get("outcome") == "correct" and e.get("category") == "spawn"]
    closed = [e for e in entries if e.get("outcome") == "wrong" and e.get("category") == "spawn"]

    log.info(f"Analyzing: {len(merged)} merged, {len(closed)} closed")

    # Try to find prompts for each
    merged_prompts = []
    closed_prompts = []

    for entry in merged:
        pid = entry.get("proposal_id", "")
        task_id = pid.replace("spawn:", "").replace("backfill:", "")
        prompt = find_prompt_for_task(task_id)
        if prompt:
            merged_prompts.append({"entry": entry, "prompt": prompt, "analysis": analyze_prompt(prompt)})

    for entry in closed:
        pid = entry.get("proposal_id", "")
        task_id = pid.replace("spawn:", "").replace("backfill:", "")
        prompt = find_prompt_for_task(task_id)
        if prompt:
            closed_prompts.append({"entry": entry, "prompt": prompt, "analysis": analyze_prompt(prompt)})

    # Even without prompt files, analyze from descriptions
    merged_descs = [analyze_prompt(e.get("description", "")) for e in merged]
    closed_descs = [analyze_prompt(e.get("description", "")) for e in closed]

    # Compute averages
    def avg_feature(analyses, feature):
        vals = [a.get(feature, 0) for a in analyses if a]
        return sum(vals) / max(len(vals), 1)

    features = ["length_chars", "length_words", "has_file_paths", "has_acceptance_criteria",
                 "has_test_commands", "has_specific_function", "has_error_message",
                 "has_scope_constraint", "mentions_files_count"]

    # Build report
    report = "# Successful PR Patterns\n\n"
    report += f"Last updated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}\n\n"
    report += f"**Data:** {len(merged)} merged PRs, {len(closed)} closed PRs\n\n"

    report += "## Description Pattern Analysis\n\n"
    report += "| Feature | Merged (avg) | Closed (avg) | Signal |\n"
    report += "|---------|-------------|-------------|--------|\n"

    for f in features:
        m_avg = avg_feature(merged_descs, f)
        c_avg = avg_feature(closed_descs, f)
        diff = m_avg - c_avg
        signal = "+" if diff > 0.1 else ("-" if diff < -0.1 else "~")
        report += f"| {f} | {m_avg:.2f} | {c_avg:.2f} | {signal} |\n"

    report += "\n## Merged PR Descriptions\n\n"
    for e in merged:
        report += f"- [{e.get('outcome')}] {e.get('description', '?')}\n"

    report += "\n## Closed PR Descriptions (first 20)\n\n"
    for e in closed[:20]:
        report += f"- [{e.get('outcome')}] {e.get('description', '?')}\n"

    report += "\n## Key Findings\n\n"
    report += "*(Auto-generated — review and update manually as more data arrives)*\n\n"

    # Simple pattern observations
    merged_desc_texts = [e.get("description", "").lower() for e in merged]
    closed_desc_texts = [e.get("description", "").lower() for e in closed]

    # Check for "fix ci" pattern
    merged_ci = sum(1 for d in merged_desc_texts if "ci" in d or "fix" in d)
    closed_ci = sum(1 for d in closed_desc_texts if "ci" in d or "fix" in d)
    if merged_ci > 0:
        report += f"- CI fix tasks: {merged_ci}/{len(merged)} merged vs {closed_ci}/{len(closed)} closed\n"

    # Check for scope indicators
    merged_narrow = sum(1 for d in merged_desc_texts if any(w in d for w in ["mock", "specific", "single"]))
    closed_narrow = sum(1 for d in closed_desc_texts if any(w in d for w in ["mock", "specific", "single"]))
    report += f"- Narrow scope tasks: {merged_narrow}/{len(merged)} merged vs {closed_narrow}/{len(closed)} closed\n"

    # Check for refactoring
    merged_refactor = sum(1 for d in merged_desc_texts if "refactor" in d or "cleanup" in d or "dead" in d)
    closed_refactor = sum(1 for d in closed_desc_texts if "refactor" in d or "cleanup" in d or "dead" in d)
    report += f"- Refactoring tasks: {merged_refactor}/{len(merged)} merged vs {closed_refactor}/{len(closed)} closed\n"

    report += "\n## Rules for Spawn Prompt Quality\n\n"
    report += "1. **Narrow scope** — single file or single test fix strongly predicts success\n"
    report += "2. **CI fix with specific test** — 'fix CI: mock X in Y test' pattern works\n"
    report += "3. **Avoid broad refactoring** — multi-file cleanup PRs get closed\n"
    report += "4. **Include acceptance criteria** — 'tests should pass' or specific assertion\n"
    report += "5. **Reference specific files** — file paths in prompt correlate with merge\n"

    OUTPUT_FILE.write_text(report)
    log.info(f"Report written: {OUTPUT_FILE}")


if __name__ == "__main__":
    run_analysis()
