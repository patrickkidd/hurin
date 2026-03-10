"""
Team Lead Daemon — Configuration
All paths, constants, thresholds, and field IDs in one place.
"""

from pathlib import Path
from zoneinfo import ZoneInfo

HOME = Path.home()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TEAM_LEAD_DIR = HOME / ".openclaw/team-lead"
MONITOR_DIR = HOME / ".openclaw/monitor"
DEV_REPO = HOME / ".openclaw/workspace-hurin/theapp"
REGISTRY = DEV_REPO / ".clawdbot/active-tasks.json"
QUEUE_FILE = MONITOR_DIR / "task-queue.json"
QUEUE_PROMPTS = MONITOR_DIR / "queue-prompts"
TASK_EVENTS = MONITOR_DIR / "task-events.jsonl"
TASK_LOGS = MONITOR_DIR / "task-logs"

METRICS_LOG = TEAM_LEAD_DIR / "metrics-log.jsonl"
METRICS_DAILY = TEAM_LEAD_DIR / "metrics-daily.jsonl"
SYNTHESES_DIR = TEAM_LEAD_DIR / "syntheses"
DEDUP_CACHE = TEAM_LEAD_DIR / "dedup-cache.json"
DAEMON_LOG = TEAM_LEAD_DIR / "daemon.log"

SCRIPTS_DIR = HOME / ".openclaw/workspace-hurin/scripts"
GH_FIND_SCRIPT = SCRIPTS_DIR / "gh-project-find-item.sh"
GH_SYNC_SCRIPT = SCRIPTS_DIR / "gh-project-sync.sh"

BOT_TOKEN_FILE = MONITOR_DIR / "hurin-bot-token"
DISCORD_TOKEN_FILE = MONITOR_DIR / "discord-bot-token"
CLAUDE_BIN = HOME / ".local/bin/claude"
GH_BIN = HOME / ".local/bin/gh"

# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

GITHUB_REPO = "patrickkidd/theapp"
PROJECT_NUMBER = 4
PROJECT_ID = "PVT_kwHOABjmWc4BP0PU"

# Project #4 field IDs (from GraphQL introspection)
STATUS_FIELD_ID = "PVTSSF_lAHOABjmWc4BP0PUzg-HbRs"
OWNER_FIELD_ID = "PVTSSF_lAHOABjmWc4BP0PUzg-HbS8"

# Status option IDs (from GraphQL introspection)
STATUS_OPTIONS = {
    "Todo": "ac7db2a9",
    "In Progress": "405c1d05",
    "Done": "9115f83f",
    "Goal 1": "c0a735ea",
    "Goal 2": "22459573",
    "Goal 3": "956a7662",
    "No Milestone": "256c5277",
}

OWNER_OPTIONS = {
    "Patrick": "2120b409",
    "Hurin": "4e27439a",
    "Beren": "fb745a0e",
    "Tuor": "e0b8b5b9",
}

# Goal names — the Status field values that represent goals
GOAL_STATUSES = {"Goal 1", "Goal 2", "Goal 3"}

# Workflow statuses (not goals)
WORKFLOW_STATUSES = {"Todo", "In Progress", "Done", "No Milestone"}

# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------

DISCORD_TEAMLEAD_CHANNEL_ID = "1478507314427334950"
DISCORD_GUILD_ID = "1474833522710548490"

# ---------------------------------------------------------------------------
# Business hours (AKST = America/Anchorage)
# ---------------------------------------------------------------------------

TZ = ZoneInfo("America/Anchorage")
BIZ_HOUR_START = 7   # 7:00 AM
BIZ_HOUR_END = 22    # 10:00 PM

# ---------------------------------------------------------------------------
# Autonomy
# ---------------------------------------------------------------------------

AUTONOMY_TIER = 0  # Auto-spawning paused per Patrick (2026-03-10) — too many low-quality tasks
MAX_CONCURRENT_SPAWNS = 2

# ---------------------------------------------------------------------------
# Knowledge Base
# ---------------------------------------------------------------------------

KNOWLEDGE_DIR = HOME / ".openclaw/knowledge"
SPAWN_POLICY_FILE = KNOWLEDGE_DIR / "self/spawn-policy.json"
PR_PATTERNS_FILE = KNOWLEDGE_DIR / "technical/successful-pr-patterns.md"

# ---------------------------------------------------------------------------
# Intervals
# ---------------------------------------------------------------------------

GITHUB_POLL_INTERVAL = 900     # 15 min
SYNTHESIS_INTERVAL = 7 * 24 * 3600  # Weekly synthesis
SYNTHESIS_DAY = 1              # Monday (0=Mon in weekday(), but we use isoweekday: 1=Mon)
SYNTHESIS_HOUR = 9             # 9 AM AKST
EVENT_POLL_INTERVAL = 5        # seconds

# ---------------------------------------------------------------------------
# Anomaly thresholds
# ---------------------------------------------------------------------------

STALE_PR_HOURS = 48
CI_DRIFT_HOURS = 2
STUCK_TASK_HOURS = 1
VELOCITY_STALL_DAYS = 3
QUEUE_BACKUP_ITEMS = 3
QUEUE_BACKUP_HOURS = 1
ANOMALY_COOLDOWN_SECS = 6 * 3600  # 6h per anomaly type

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

METRICS_MAX_LINES = 10_000

# Effort label weights
EFFORT_WEIGHTS = {"effort:large": 3, "effort:medium": 2, "effort:small": 1}
DEFAULT_EFFORT = 1

# Fuzzy completion weights by issue/PR state
COMPLETION_WEIGHTS = {
    "open_no_activity": 0.0,
    "open_active_commits": 0.2,
    "open_pr_draft": 0.3,
    "open_pr_review": 0.7,
    "closed": 1.0,
}

# Momentum: activity within this window gets favorable risk assessment
MOMENTUM_WINDOW_HOURS = 48

# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

SYNTHESIS_MAX_TURNS = 10  # Deep investigation like project-pulse (was 3 for hourly)
SYNTHESIS_MODEL = "claude-opus-4-6"  # Sonnet misjudges project state; Opus needed for quality

# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------

DEDUP_TTL_HOURS = 24
DEDUP_RECENT_SYNTHESES = 5  # Number of past syntheses to check for recommendation dedup
