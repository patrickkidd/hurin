#!/usr/bin/env python3
"""
Board Reconciliation — Weekly audit of GitHub Project #4 ("Family Diagram").

Checks every board item against actual GitHub state and fixes mismatches:
- Closed issues still marked "In Progress" or "Todo" → move to "Done"
- Merged PRs not marked "Done" → move to "Done"
- Closed PRs still marked "In Progress" → move back to "Todo"
- Duplicate items (same issue/PR listed twice)
- Orphaned items (no linked issue/PR)
- Stale labels (cf-pr-open on merged/closed PRs)

Runs via cron (weekly Monday 9:30 AM AKST) or manually.
Posts summary to #planning Discord channel.
"""

import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

MONITOR_DIR = Path(__file__).parent
SCRIPTS_DIR = Path.home() / ".openclaw" / "workspace-hurin" / "scripts"
GH_SYNC_SCRIPT = SCRIPTS_DIR / "gh-project-sync.sh"

PROJECT_ID = "PVT_kwHOABjmWc4BP0PU"
REPOS = ["patrickkidd/familydiagram", "patrickkidd/btcopilot", "patrickkidd/fdserver"]

# Discord
sys.path.insert(0, str(MONITOR_DIR))
from discord_relay import discord_api as _discord_api, load_discord_token, set_discord_token

DISCORD_PLANNING_CHANNEL = "1475607956698562690"

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("board-reconcile")


def run(cmd, cwd=None):
    """Run a shell command, return (returncode, stdout, stderr)."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=60)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def fetch_all_board_items():
    """Fetch all items from the project board, handling pagination."""
    items = []
    cursor = None

    while True:
        after_clause = f', after: "{cursor}"' if cursor else ""
        query = f'''{{
  node(id: "{PROJECT_ID}") {{
    ... on ProjectV2 {{
      items(first: 50{after_clause}) {{
        pageInfo {{ hasNextPage endCursor }}
        nodes {{
          id
          fieldValues(first: 10) {{
            nodes {{
              ... on ProjectV2ItemFieldSingleSelectValue {{
                name
                field {{ ... on ProjectV2SingleSelectField {{ name }} }}
              }}
            }}
          }}
          content {{
            ... on Issue {{
              number
              title
              state
              labels(first: 10) {{ nodes {{ name }} }}
              repository {{ nameWithOwner }}
            }}
            ... on PullRequest {{
              number
              title
              state
              merged
              labels(first: 10) {{ nodes {{ name }} }}
              repository {{ nameWithOwner }}
            }}
            ... on DraftIssue {{
              title
            }}
          }}
        }}
      }}
    }}
  }}
}}'''
        rc, out, err = run(f"gh api graphql -f query='{query}'")
        if rc != 0:
            log.error(f"GraphQL query failed: {err}")
            break

        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            log.error(f"Failed to parse GraphQL response: {out[:200]}")
            break

        page = data.get("data", {}).get("node", {}).get("items", {})
        nodes = page.get("nodes", [])
        items.extend(nodes)

        page_info = page.get("pageInfo", {})
        if page_info.get("hasNextPage"):
            cursor = page_info["endCursor"]
        else:
            break

    return items


def parse_item(item):
    """Extract useful fields from a board item."""
    content = item.get("content", {})
    if not content:
        return None

    # Extract field values (Status, Owner, Priority, Component)
    fields = {}
    for fv in item.get("fieldValues", {}).get("nodes", []):
        field_info = fv.get("field", {})
        if field_info:
            fields[field_info.get("name", "")] = fv.get("name", "")

    repo = content.get("repository", {}).get("nameWithOwner", "")
    labels = [l["name"] for l in content.get("labels", {}).get("nodes", [])]

    return {
        "item_id": item["id"],
        "number": content.get("number"),
        "title": content.get("title", ""),
        "repo": repo,
        "state": content.get("state", ""),
        "merged": content.get("merged", False),
        "labels": labels,
        "is_pr": "merged" in content,  # PRs have merged field
        "is_draft": "title" in content and "number" not in content,
        "board_status": fields.get("Status", ""),
        "board_owner": fields.get("Owner", ""),
        "board_priority": fields.get("Priority", ""),
    }


def sync_board_status(item_id, status):
    """Update a board item's status."""
    if not GH_SYNC_SCRIPT.exists():
        log.warning(f"Sync script not found: {GH_SYNC_SCRIPT}")
        return False
    rc, out, err = run(f'bash {GH_SYNC_SCRIPT} {item_id} --status "{status}"')
    return rc == 0


def fix_stale_labels(repo, number, add=None, remove=None):
    """Fix labels on an issue/PR."""
    if add:
        run(f"gh issue edit {number} --repo {repo} --add-label {add} 2>/dev/null")
    if remove:
        run(f"gh issue edit {number} --repo {repo} --remove-label {remove} 2>/dev/null")


def reconcile():
    """Main reconciliation logic. Returns summary dict."""
    log.info("Fetching all board items...")
    raw_items = fetch_all_board_items()
    log.info(f"Found {len(raw_items)} board items")

    items = []
    for raw in raw_items:
        parsed = parse_item(raw)
        if parsed:
            items.append(parsed)

    # Track fixes
    fixes = []
    warnings = []

    # --- Check 1: Status mismatches ---
    for item in items:
        if item["is_draft"]:
            continue

        repo = item["repo"]
        num = item["number"]
        board_status = item["board_status"]
        state = item["state"]
        merged = item["merged"]

        # Merged PR not marked Done
        if item["is_pr"] and merged and board_status != "Done":
            log.info(f"  FIX: {repo}#{num} merged PR, board={board_status} → Done")
            if sync_board_status(item["item_id"], "Done"):
                fixes.append(f"✅ {repo}#{num}: merged PR was '{board_status}' → Done")
            fix_stale_labels(repo, num, add="cf-done", remove="cf-pr-open")

        # Closed PR (not merged) still "In Progress"
        elif item["is_pr"] and state == "CLOSED" and not merged and board_status == "In Progress":
            log.info(f"  FIX: {repo}#{num} closed PR, board=In Progress → Todo")
            if sync_board_status(item["item_id"], "Todo"):
                fixes.append(f"🔄 {repo}#{num}: closed PR was 'In Progress' → Todo")
            fix_stale_labels(repo, num, remove="cf-pr-open")

        # Closed issue still "In Progress" or "Todo" with work labels
        elif not item["is_pr"] and state == "CLOSED" and board_status in ("In Progress", "Todo"):
            log.info(f"  FIX: {repo}#{num} closed issue, board={board_status} → Done")
            if sync_board_status(item["item_id"], "Done"):
                fixes.append(f"✅ {repo}#{num}: closed issue was '{board_status}' → Done")

        # Open issue/PR marked "Done" (reopened?)
        elif state == "OPEN" and board_status == "Done":
            warnings.append(f"⚠️ {repo}#{num}: open but board says 'Done' — check manually")

    # --- Check 2: Duplicates ---
    seen = defaultdict(list)
    for item in items:
        if item["is_draft"]:
            continue
        key = f"{item['repo']}#{item['number']}"
        seen[key].append(item)

    for key, dupes in seen.items():
        if len(dupes) > 1:
            warnings.append(f"🔁 Duplicate: {key} appears {len(dupes)} times on board")

    # --- Check 3: Stale label cleanup ---
    for item in items:
        if item["is_draft"]:
            continue
        labels = item["labels"]
        state = item["state"]
        merged = item["merged"]

        # cf-pr-open on merged/closed items
        if "cf-pr-open" in labels and (merged or state == "CLOSED"):
            fix_stale_labels(item["repo"], item["number"], remove="cf-pr-open")
            if merged:
                fix_stale_labels(item["repo"], item["number"], add="cf-done")
            fixes.append(f"🏷️ {item['repo']}#{item['number']}: removed stale cf-pr-open label")

    # --- Check 4: Draft issues (no linked content) ---
    draft_count = sum(1 for raw in raw_items if not parse_item(raw))
    if draft_count:
        warnings.append(f"📋 {draft_count} draft/orphaned items with no linked issue/PR")

    return {
        "total_items": len(raw_items),
        "parsed_items": len(items),
        "fixes": fixes,
        "warnings": warnings,
    }


def format_summary(result):
    """Format reconciliation result for Discord."""
    lines = [f"**Board Reconciliation** — {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    lines.append(f"Scanned {result['total_items']} items ({result['parsed_items']} with linked content)")
    lines.append("")

    if result["fixes"]:
        lines.append(f"**{len(result['fixes'])} fixes applied:**")
        for f in result["fixes"]:
            lines.append(f"  {f}")
        lines.append("")

    if result["warnings"]:
        lines.append(f"**{len(result['warnings'])} warnings:**")
        for w in result["warnings"]:
            lines.append(f"  {w}")
        lines.append("")

    if not result["fixes"] and not result["warnings"]:
        lines.append("Board is in sync. No issues found.")

    return "\n".join(lines)


def post_to_discord(message):
    """Post reconciliation summary to #planning."""
    token = load_discord_token()
    if not token:
        log.warning("No Discord token, skipping post")
        return
    set_discord_token(token)
    try:
        _discord_api(
            "POST",
            f"https://discord.com/api/v10/channels/{DISCORD_PLANNING_CHANNEL}/messages",
            {"content": message[:2000]},
        )
    except Exception as e:
        log.error(f"Discord post failed: {e}")


def main():
    dry_run = "--dry-run" in sys.argv
    quiet = "--quiet" in sys.argv

    if dry_run:
        log.info("DRY RUN — no changes will be made")
        # Monkey-patch sync to no-op
        global sync_board_status, fix_stale_labels
        orig_sync = sync_board_status
        orig_labels = fix_stale_labels
        sync_board_status = lambda *a, **k: True
        fix_stale_labels = lambda *a, **k: None

    result = reconcile()
    summary = format_summary(result)

    print(summary)

    if not quiet and not dry_run:
        post_to_discord(summary)

    if dry_run:
        sync_board_status = orig_sync
        fix_stale_labels = orig_labels


if __name__ == "__main__":
    main()
