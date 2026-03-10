#!/usr/bin/env python3
"""
Weekly Cross-Correlation — emergent insight extraction.

Reads all three agents' latest outputs + signal bus + episodes.
Asks Opus to find patterns that span multiple agents' data.
Writes to knowledge/shared/weekly-insights.md and posts to Discord.

Usage: uv run --directory ~/.openclaw/monitor python ~/.openclaw/scripts/weekly-insight.py
Cron:  0 10 * * 1   (1hr after Monday synthesis)

Part of the Collective Intelligence system (ADR-0009).
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
sys.path.insert(0, str(HOME / ".openclaw/monitor"))

from shared_memory import (
    read_signals,
    read_recent_episodes,
    read_recent_calibrations,
    read_state,
    get_latest_file,
    extract_and_emit_signals,
    append_signal,
    SYNTHESES_DIR,
    DIGESTS_DIR,
    BRIEFINGS_DIR,
)

# Force Max plan — never use API key. "Credit balance is too low" = API key leak.
os.environ.pop("ANTHROPIC_API_KEY", None)

INSIGHTS_FILE = HOME / ".openclaw/knowledge/shared/weekly-insights.md"


async def main():
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

    # Gather all context
    synthesis = get_latest_file(SYNTHESES_DIR, "*.json", max_chars=10000)
    if synthesis:
        try:
            data = json.loads(synthesis)
            synthesis = data.get("synthesis", synthesis)
        except json.JSONDecodeError:
            pass
    else:
        synthesis = "No synthesis available."

    digest = get_latest_file(DIGESTS_DIR, "*.md", max_chars=3000) or "No digest available."
    briefing = get_latest_file(BRIEFINGS_DIR, "*.md", max_chars=3000) or "No briefing available."

    # Read all signals without marking consumed (read-only)
    signals = read_signals("all", mark_consumed=False)
    episodes = read_recent_episodes(limit=10)
    calibrations = read_recent_calibrations(limit=5)
    state = read_state()

    signals_text = "\n".join(
        f"- [{s['type']}] {s['from']}→{s['to']}: {s['signal']}" for s in signals[-20:]
    ) or "No signals yet."

    episodes_text = "\n".join(
        f"- {ep['task_id']} ({ep['outcome']}): {'; '.join(ep.get('lessons', [])[:2])}" for ep in episodes
    ) or "No episodes yet."

    cal_text = "\n".join(
        f"- {c['challenger']} vs {c['challenged']}: {c['topic']} → {c['patrick_decided']}" for c in calibrations
    ) or "No calibrations yet."

    prompt = f"""You are analyzing a 3-agent AI system (Huor=operations, Tuor=strategy, Beren=meta-evaluation).

## Latest Huor Synthesis (operations)
{str(synthesis)[:2000]}

## Latest Tuor Briefing (strategy)
{briefing[:2000]}

## Latest Beren Digest (meta-evaluation)
{digest[:2000]}

## Signal Bus (recent cross-agent signals)
{signals_text}

## Recent Task Outcomes (episodic memory)
{episodes_text}

## Calibration History (adversarial outcomes)
{cal_text}

## Current Sprint Focus
{state.get('sprint_focus', 'Not set')}

## Your Task
Identify the 1-3 most important insights that SPAN MULTIPLE agents' data — patterns that no individual agent stated but that emerge from combining their perspectives.

For each insight:
1. Which agents' data does it combine?
2. What is the insight?
3. What action does it suggest?
4. How confident are you? (0.0-1.0)

If there are no genuine cross-agent insights this week, say so honestly. Do not fabricate.

After your insights, emit signals on a SEPARATE line:
SIGNALS_JSON: [{{"to": "huor", "type": "cross_correlation", "signal": "...", "confidence": 0.8}}, ...]
"""

    client = ClaudeSDKClient()
    options = ClaudeAgentOptions(model="claude-opus-4-6", max_turns=3)
    result = await client.query(prompt, options=options)

    output_text = result.text if hasattr(result, 'text') else str(result)

    # Write insight
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    header = f"\n\n---\n## Week of {date}\n\n"
    INSIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing = INSIGHTS_FILE.read_text() if INSIGHTS_FILE.exists() else "# Weekly Cross-Correlation Insights\n"
    INSIGHTS_FILE.write_text(existing + header + output_text + "\n")

    # Extract and emit signals from the output
    emitted = extract_and_emit_signals(output_text, from_agent="system", source_artifact=f"weekly-insight-{date}")
    print(f"Insight written to {INSIGHTS_FILE}")
    print(f"Emitted {len(emitted)} cross-agent signals")

    # Post to Discord if relay available
    try:
        from discord_relay import post_to_channel
        await post_to_channel(
            "chief-of-staff",
            f"**Weekly Cross-Correlation Insight ({date})**\n\n{output_text[:1900]}",
        )
        print("Posted to Discord #chief-of-staff")
    except ImportError:
        print("Discord relay not available, skipped posting")
    except Exception as e:
        print(f"Discord post failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
