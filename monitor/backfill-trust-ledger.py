#!/usr/bin/env python3
"""
Backfill trust ledger from GitHub PR history.

Scans all repos for PRs created by patrickkidd-hurin (bot account),
records outcomes based on current PR state:
- Merged → correct
- Closed (not merged) → wrong
- Open → pending (recorded as proposal, no outcome yet)

Run once to bootstrap the trust ledger with historical data.
"""

import json
import subprocess
import sys
from pathlib import Path

MONITOR_DIR = Path(__file__).parent
sys.path.insert(0, str(MONITOR_DIR))
from trust_ledger import record_proposal, record_outcome, get_summary

REPOS = ["patrickkidd/btcopilot", "patrickkidd/familydiagram", "patrickkidd/fdserver"]
BOT_AUTHOR = "patrickkidd-hurin"


def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def fetch_prs(repo, state="all"):
    """Fetch PRs by bot account from a repo."""
    cmd = (
        f"gh pr list --repo {repo} --author {BOT_AUTHOR} --state {state} "
        f"--json number,title,state,mergedAt,closedAt,createdAt,headRefName --limit 100"
    )
    rc, out, err = run(cmd)
    if rc != 0:
        print(f"  Error fetching PRs from {repo}: {err}")
        return []
    try:
        return json.loads(out) if out else []
    except json.JSONDecodeError:
        return []


def main():
    dry_run = "--dry-run" in sys.argv
    print("Backfilling trust ledger from PR history...")
    if dry_run:
        print("(DRY RUN — no changes)")

    stats = {"correct": 0, "wrong": 0, "pending": 0, "skipped": 0}

    for repo in REPOS:
        print(f"\n--- {repo} ---")
        prs = fetch_prs(repo)
        if not prs:
            print("  No PRs found")
            continue

        for pr in prs:
            num = pr["number"]
            title = pr.get("title", "")[:60]
            state = pr.get("state", "").upper()
            branch = pr.get("headRefName", "")

            # Generate a proposal ID from the branch name or PR number
            proposal_id = f"backfill:{repo.split('/')[1]}:pr{num}"
            desc = f"PR #{num}: {title}"

            if dry_run:
                outcome = "merged" if state == "MERGED" else ("closed" if state == "CLOSED" else "open")
                print(f"  #{num} [{outcome}] {title}")
                if state == "MERGED":
                    stats["correct"] += 1
                elif state == "CLOSED":
                    stats["wrong"] += 1
                else:
                    stats["pending"] += 1
                continue

            # Record the proposal (category, proposal_id, description)
            record_proposal("spawn", proposal_id, desc)

            if state == "MERGED":
                record_outcome(proposal_id, "correct", detail=f"PR #{num} merged in {repo}")
                stats["correct"] += 1
                print(f"  ✅ #{num} merged: {title}")
            elif state == "CLOSED":
                record_outcome(proposal_id, "wrong", detail=f"PR #{num} closed without merge in {repo}")
                stats["wrong"] += 1
                print(f"  ❌ #{num} closed: {title}")
            else:
                # Open — just record as pending proposal
                stats["pending"] += 1
                print(f"  ⏳ #{num} open: {title}")

    print(f"\n--- Summary ---")
    print(f"Correct (merged): {stats['correct']}")
    print(f"Wrong (closed):   {stats['wrong']}")
    print(f"Pending (open):   {stats['pending']}")

    if not dry_run:
        print("\nUpdated trust ledger:")
        summary = get_summary()
        for cat, d in summary.items():
            if d["total"] > 0:
                print(f"  {cat}: {d['accuracy']*100:.0f}% accuracy ({d['correct']}/{d['total']} correct, {d['pending']} pending)")
            else:
                print(f"  {cat}: no resolved data yet ({d['pending']} pending)")


if __name__ == "__main__":
    main()
