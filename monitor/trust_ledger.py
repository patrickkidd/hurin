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


# ---------------------------------------------------------------------------
# Task classification + spawn policy engine
# ---------------------------------------------------------------------------

SPAWN_POLICY_FILE = Path.home() / ".openclaw/knowledge/self/spawn-policy.json"

# Keywords for classifying task descriptions into categories
_CATEGORY_KEYWORDS = {
    "ci_fix": ["ci", "ci:", "fix ci", "ci fail", "ci pass", "github actions"],
    "test_infra": ["mock", "fixture", "test infra", "pytest", "test setup"],
    "dead_code": ["dead code", "unused", "remove dead", "cleanup dead"],
    "refactoring": ["refactor", "cleanup", "reorganize", "rename", "move to"],
    "bugfix": ["fix bug", "bugfix", "crash", "error handling", "fix:", "hotfix"],
    "feature": ["add", "implement", "create", "new feature", "support for"],
    "infrastructure": ["deploy", "config", "infra", "systemd", "service", "openclaw"],
    "docs": ["doc", "readme", "comment", "docstring"],
}


def classify_task(description, files_changed=None):
    """Classify a task description into a spawn policy category.

    Returns category string. Uses keyword matching on description + file paths.
    """
    desc = description.lower()
    files_str = " ".join(files_changed or []).lower()
    combined = f"{desc} {files_str}"

    # Score each category
    scores = {}
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw in combined)

    best = max(scores, key=scores.get) if scores else "other"
    return best if scores.get(best, 0) > 0 else "other"


def _load_spawn_policy():
    """Load spawn policy JSON."""
    if not SPAWN_POLICY_FILE.exists():
        return None
    try:
        return json.loads(SPAWN_POLICY_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return None


def _save_spawn_policy(policy):
    """Save spawn policy JSON."""
    SPAWN_POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SPAWN_POLICY_FILE.write_text(json.dumps(policy, indent=2))


def get_spawn_autonomy(category):
    """Look up autonomy level for a category from spawn policy.

    Returns: "auto_spawn", "propose_only", or "blocked"
    """
    policy = _load_spawn_policy()
    if not policy:
        return "propose_only"  # safe default

    cat_data = policy.get("categories", {}).get(category)
    if not cat_data:
        return policy.get("default_autonomy", "propose_only")

    return cat_data.get("autonomy", "propose_only")


def update_spawn_policy():
    """Recalculate spawn policy from trust ledger data.

    Applies graduation rules:
      - >= 80% accuracy over 5+ proposals → auto_spawn
      - < 40% accuracy over 5+ proposals → blocked
      - Otherwise → propose_only

    Returns list of changes made (for logging/notification).
    """
    policy = _load_spawn_policy()
    if not policy:
        # Initialize from scratch
        policy = {
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "categories": {},
            "default_autonomy": "propose_only",
            "graduation_threshold": 0.80,
            "graduation_min_proposals": 5,
            "demotion_threshold": 0.40,
            "demotion_min_proposals": 5,
        }

    grad_threshold = policy.get("graduation_threshold", 0.80)
    grad_min = policy.get("graduation_min_proposals", 5)
    demote_threshold = policy.get("demotion_threshold", 0.40)
    demote_min = policy.get("demotion_min_proposals", 5)

    # Classify all resolved spawn entries by category
    data = _load()
    cat_stats = {}  # category -> {correct, partial, wrong, failed, total}

    for entry in data["entries"]:
        if entry["category"] != "spawn" or entry.get("outcome") is None:
            continue
        cat = classify_task(entry.get("description", ""))
        if cat not in cat_stats:
            cat_stats[cat] = {"correct": 0, "partial": 0, "wrong": 0, "failed": 0, "total": 0}
        cat_stats[cat]["total"] += 1
        outcome = entry["outcome"]
        if outcome in cat_stats[cat]:
            cat_stats[cat][outcome] += 1

    changes = []

    for cat, stats in cat_stats.items():
        total = stats["total"]
        accuracy = (stats["correct"] + 0.5 * stats["partial"]) / total if total > 0 else 0.0

        old_autonomy = policy.get("categories", {}).get(cat, {}).get("autonomy", "propose_only")

        # Apply graduation rules
        if total >= grad_min and accuracy >= grad_threshold:
            new_autonomy = "auto_spawn"
        elif total >= demote_min and accuracy < demote_threshold:
            new_autonomy = "blocked"
        else:
            new_autonomy = "propose_only"

        if old_autonomy != new_autonomy:
            changes.append({
                "category": cat,
                "old": old_autonomy,
                "new": new_autonomy,
                "accuracy": round(accuracy, 3),
                "total": total,
            })

        policy.setdefault("categories", {})[cat] = {
            "description": _CATEGORY_KEYWORDS.get(cat, [""])[0] if cat in _CATEGORY_KEYWORDS else cat,
            "autonomy": new_autonomy,
            "accuracy": round(accuracy, 3),
            "total": total,
            "correct": stats["correct"],
            "wrong": stats["wrong"],
            "graduation_rule": f">= {grad_threshold*100:.0f}% over {grad_min}+ proposals",
        }

    policy["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_spawn_policy(policy)

    return changes


def store_prompt_text(proposal_id, prompt_text):
    """Store the full prompt text in the trust ledger entry metadata.

    Used for prompt archaeology — correlating prompt characteristics with outcomes.
    """
    data = _load()
    for entry in data["entries"]:
        if entry["proposal_id"] == proposal_id:
            entry.setdefault("metadata", {})["prompt_text"] = prompt_text[:5000]  # cap size
            break
    _save(data)
