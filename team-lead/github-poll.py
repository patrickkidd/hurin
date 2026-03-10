#!/usr/bin/env python3
"""
GitHub Poll — standalone cron-callable script.

Collects GitHub data, computes metrics, detects anomalies, posts high-severity
alerts to Discord, and runs telemetry. Replaces the GitHub polling loop from
the team-lead daemon.

Run via cron every 15 minutes during business hours.
"""

import sys
from pathlib import Path

# Ensure team-lead and monitor dirs are on path
sys.path.insert(0, str(Path.home() / ".openclaw/team-lead"))
sys.path.insert(0, str(Path.home() / ".openclaw/monitor"))

from team_lead import (
    load_tokens,
    collect_github_data,
    compute_metrics,
    log_metrics,
    detect_anomalies,
    read_recent_events,
    post_to_teamlead,
    log,
)


def main():
    load_tokens()

    try:
        github_data = collect_github_data()
    except Exception as e:
        log.error(f"GitHub data collection failed: {e}")
        sys.exit(1)

    metrics = compute_metrics(github_data)
    log_metrics(metrics)

    events = read_recent_events()
    anomalies = detect_anomalies(github_data, metrics, events)

    if anomalies:
        log.info(f"{len(anomalies)} anomaly(ies) detected")
        for a in anomalies:
            log.info(f"  [{a['severity']}] {a['message']}")
            if a["severity"] == "high":
                post_to_teamlead(f"**[{a['severity'].upper()}]** {a['message']}")

    # Telemetry (piggyback, non-critical)
    try:
        from telemetry import collect_all as _collect_telemetry
        _collect_telemetry()
    except Exception as e:
        log.debug(f"Telemetry collection error: {e}")

    log.info("GitHub poll complete")


if __name__ == "__main__":
    main()
