#!/bin/bash
# Run GitHub poll + anomaly detection + telemetry.
# Called by cron every 15 minutes.
exec /home/hurin/.local/bin/uv run --directory /home/hurin/.openclaw/monitor \
    python /home/hurin/.openclaw/team-lead/github-poll.py
