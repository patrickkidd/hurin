"""
Trust Ledger — tracks system proposal accuracy across categories.

Categories:
  - merge: "should this PR be merged?" proposals
  - spawn: auto-spawn task quality (PR merged as-is = good, closed = bad)
  - recommendation: were recommendations acted on?

Each entry records a proposal and its outcome. Accuracy is computed
per-category as: correct / total over a rolling window.

Used by:
  - task-daemon: records PR outcomes automatically
  - team-lead synthesis: reads accuracy scores for context
  - decisions log: threshold checks for unlocking autonomy
"""

import json
import time
from pathlib import Path

LEDGER_FILE = Path.home() / ".openclaw/monitor/trust-ledger.json"

# Minimum proposals before accuracy is meaningful
MIN_PROPOSALS = 5

# Rolling window for accuracy calculation
ROLLING_WINDOW_DAYS = 90


def _load():
    if not LEDGER_FILE.exists():
        return {"entries": []}
    try:
        return json.loads(LEDGER_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {"entries": []}


def _save(data):
    LEDGER_FILE.write_text(json.dumps(data, indent=2))


def record_proposal(category, proposal_id, description, metadata=None):
    """Record a new proposal (before outcome is known)."""
    data = _load()
    # Avoid duplicate proposals
    if any(e["proposal_id"] == proposal_id for e in data["entries"]):
        return
    data["entries"].append({
        "category": category,
        "proposal_id": proposal_id,
        "description": description,
        "proposed_at": time.time(),
        "proposed_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "outcome": None,  # pending
        "outcome_at": None,
        "metadata": metadata or {},
    })
    _save(data)


def record_outcome(proposal_id, outcome, detail=""):
    """Record the outcome of a proposal.

    Outcomes:
      - "correct": proposal was right (PR merged as-is, recommendation acted on)
      - "partial": partially right (PR merged with modifications)
      - "wrong": proposal was wrong (PR closed, recommendation ignored/harmful)
      - "failed": execution failed (no PR created, task errored)
    """
    data = _load()
    for entry in data["entries"]:
        if entry["proposal_id"] == proposal_id and entry["outcome"] is None:
            entry["outcome"] = outcome
            entry["outcome_at"] = time.time()
            entry["outcome_detail"] = detail
            break
    _save(data)


def get_accuracy(category, window_days=ROLLING_WINDOW_DAYS):
    """Get accuracy stats for a category.

    Returns dict with: total, correct, partial, wrong, failed, accuracy, has_enough_data
    """
    data = _load()
    cutoff = time.time() - (window_days * 86400)

    entries = [
        e for e in data["entries"]
        if e["category"] == category
        and e.get("outcome") is not None
        and e.get("proposed_at", 0) > cutoff
    ]

    total = len(entries)
    correct = sum(1 for e in entries if e["outcome"] == "correct")
    partial = sum(1 for e in entries if e["outcome"] == "partial")
    wrong = sum(1 for e in entries if e["outcome"] == "wrong")
    failed = sum(1 for e in entries if e["outcome"] == "failed")

    accuracy = (correct + 0.5 * partial) / total if total > 0 else 0.0

    return {
        "total": total,
        "correct": correct,
        "partial": partial,
        "wrong": wrong,
        "failed": failed,
        "accuracy": round(accuracy, 3),
        "has_enough_data": total >= MIN_PROPOSALS,
        "pending": sum(
            1 for e in data["entries"]
            if e["category"] == category and e.get("outcome") is None
        ),
    }


def get_summary():
    """Get accuracy summary across all categories."""
    categories = ["merge", "spawn", "recommendation"]
    return {cat: get_accuracy(cat) for cat in categories}


def get_pending(category=None):
    """Get proposals awaiting outcomes."""
    data = _load()
    entries = [
        e for e in data["entries"]
        if e.get("outcome") is None
        and (category is None or e["category"] == category)
    ]
    return entries
