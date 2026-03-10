#!/bin/bash
# Run a team-lead synthesis on demand.
# Called by the /teamlead skill and openclaw cron.
exec /home/hurin/.local/bin/uv run --directory /home/hurin/.openclaw/monitor \
    python /home/hurin/.openclaw/team-lead/run-synthesis.py
