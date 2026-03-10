#!/usr/bin/env python3
"""
Run Synthesis — standalone cron-callable script.

Collects fresh GitHub data, computes metrics, reads recent events, detects
anomalies, runs Agent SDK synthesis (Opus), posts results to Discord, executes
auto-spawn pipeline, and runs post-synthesis learning. Replaces the synthesis
portion of the team-lead daemon.

Run via cron weekly (Monday 9 AM AKST) or on-demand via /teamlead skill.
"""

import asyncio
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
    run_synthesis,
    process_synthesis,
    log,
)


async def main():
    load_tokens()

    log.info("Collecting GitHub data for synthesis...")
    try:
        github_data = collect_github_data()
    except Exception as e:
        log.error(f"GitHub data collection failed: {e}")
        sys.exit(1)

    metrics = compute_metrics(github_data)
    log_metrics(metrics)

    events = read_recent_events()
    anomalies = detect_anomalies(github_data, metrics, events)

    log.info("Starting synthesis...")
    try:
        synthesis, session_id = await run_synthesis(
            metrics, events, github_data, anomalies,
        )
        if synthesis:
            process_synthesis(synthesis, github_data, session_id=session_id)
            log.info("Synthesis complete and posted to Discord")
        else:
            log.error("Synthesis returned no results")
    except Exception as e:
        log.error(f"Synthesis error: {e}")
        sys.exit(1)

    # Post-synthesis learning (non-critical)
    try:
        from session_learner import run_learner as _run_session_learner
        _run_session_learner()
        log.info("Session learner completed")
    except Exception as e:
        log.debug(f"Session learner error: {e}")

    try:
        from analyze_prompts import run_analysis as _run_prompt_analysis
        _run_prompt_analysis()
        log.info("Prompt archaeology completed")
    except Exception as e:
        log.debug(f"Prompt archaeology error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
