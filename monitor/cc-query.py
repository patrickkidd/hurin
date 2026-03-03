#!/usr/bin/env python3
"""
cc-query.py — Agent SDK wrapper for hurin's sync Claude Code calls.

Replaces `claude -p --model opus --dangerously-skip-permissions` with a
structured SDK call that also streams progress to a Discord thread.

Usage:
    uv run --directory ~/.openclaw/monitor python cc-query.py \
        --description "Investigating auth bug" \
        [--cwd /path/to/repo] \
        [--max-turns 10] \
        <<'PROMPT'
    Read the codebase and investigate why auth is broken...
    PROMPT

Behavior:
    1. Reads prompt from stdin
    2. Creates Discord thread in #tasks: "🔄 query · <description>"
    3. Runs Agent SDK query() with streaming
    4. Streams formatted output to Discord thread (shared DiscordThreadRelay)
    5. On completion: updates thread status (✅/❌), prints result to stdout
    6. Exits 0 on success, 1 on error
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[cc-query] %(message)s",
    stream=sys.stderr,
)

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage, AssistantMessage
from claude_agent_sdk.types import TextBlock

from discord_relay import (
    DiscordThreadRelay,
    discord_api,
    load_discord_token,
    get_bot_user_id,
    poll_discord_thread,
    DISCORD_TASKS_CHANNEL_ID,
)

HOME = Path.home()
DEFAULT_CWD = str(HOME / ".openclaw/workspace-hurin/theapp")
CLI_PATH = str(HOME / ".local/bin/claude")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Agent SDK wrapper for sync CC calls with Discord streaming"
    )
    parser.add_argument(
        "--description",
        required=True,
        help="Short description for the Discord thread name",
    )
    parser.add_argument(
        "--cwd",
        default=DEFAULT_CWD,
        help=f"Working directory for CC (default: {DEFAULT_CWD})",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="Max agentic turns (default: SDK default)",
    )
    parser.add_argument(
        "--source-url",
        default=None,
        help="Discord message URL that triggered this query (shown in thread header)",
    )
    return parser.parse_args()


async def run_query(prompt: str, args) -> int:
    """Run the SDK query with Discord streaming and live steering. Returns exit code."""

    # Load Discord token for thread relay
    token = load_discord_token()
    log = logging.getLogger("cc-query")
    if token:
        log.info(f"Discord token loaded (len={len(token)})")
    else:
        log.warning("No Discord token — threads will be skipped")

    # Generate a short thread name for Discord
    desc_short = args.description[:60]
    thread_label = f"query · {desc_short}"

    # Set up Discord thread relay
    relay = DiscordThreadRelay(
        task_id=thread_label,
        description=args.description,
        repo=Path(args.cwd).name,
    )
    thread_id = relay.create_thread(header_prefix="🔍")
    if thread_id:
        log.info(f"Discord thread created: {thread_id}")
        relay.set_status("running")
        # Post source message backlink in thread
        if args.source_url:
            relay._post(f"📩 Triggered by: {args.source_url}")
    else:
        log.warning("Failed to create Discord thread")

    # Build SDK options
    env = {
        "PATH": "/opt/homebrew/bin:"
        + str(HOME / ".local/bin")
        + ":"
        + os.environ.get("PATH", ""),
    }

    options = ClaudeAgentOptions(
        model="claude-opus-4-6",
        permission_mode="bypassPermissions",
        cwd=args.cwd,
        env=env,
        cli_path=CLI_PATH,
        setting_sources=["project"],  # Loads CLAUDE.md from cwd
    )

    if args.max_turns:
        options.max_turns = args.max_turns

    # --- Steering setup ---
    steer_queue = asyncio.Queue()
    poller_task = None
    bot_user_id = get_bot_user_id() if token else None

    # Run the query with ClaudeSDKClient for bidirectional steering
    session_id = ""
    is_error = False
    result_text = ""

    try:
        async with ClaudeSDKClient(options=options) as client:
            # Start the Discord thread poller for steering
            if thread_id and bot_user_id:
                poller_task = asyncio.create_task(
                    poll_discord_thread(
                        thread_id, steer_queue,
                        bot_user_id=bot_user_id,
                    )
                )

            # Send initial prompt
            await client.query(prompt)

            while True:
                steered = False

                async for message in client.receive_response():
                    # Forward to Discord thread
                    relay.on_message(message)

                    # Capture result
                    if isinstance(message, ResultMessage):
                        session_id = message.session_id
                        is_error = message.is_error
                        result_text = message.result or ""
                        break

                    # Stream assistant text to stdout
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock) and block.text.strip():
                                print(block.text.strip(), flush=True)

                    # Non-blocking steer check
                    try:
                        steer = steer_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        steer = None

                    if steer:
                        await client.interrupt()
                        log.info(f"Steering: {steer[:80]}")
                        relay._post(f"📩 **Steering received:**\n> {steer}")
                        relay._post("🔄 Interrupting and redirecting...")
                        relay.set_status("steering")
                        await client.query(f"[STEERING from human operator]: {steer}")
                        relay.set_status("running")
                        steered = True
                        break  # Restart receive_response loop

                if steered:
                    continue  # Re-enter receive_response loop

                # Response complete — wait briefly for follow-up steering
                try:
                    steer = await asyncio.wait_for(steer_queue.get(), timeout=5.0)
                    log.info(f"Post-completion follow-up: {steer[:80]}")
                    relay._post(f"📩 **Follow-up:**\n> {steer}")
                    relay.set_status("steering")
                    await client.query(steer)
                    relay.set_status("running")
                    session_id = ""  # Reset so we re-enter the loop
                    continue
                except asyncio.TimeoutError:
                    break  # No follow-up — done

    except Exception as e:
        is_error = True
        error_msg = f"SDK error ({type(e).__name__}): {e}"
        print(error_msg, file=sys.stderr)

        # Post error to Discord thread
        if relay.thread_id:
            relay._post(f"## ❌ Error\n```\n{error_msg}\n```")

    finally:
        if poller_task:
            poller_task.cancel()
            try:
                await poller_task
            except asyncio.CancelledError:
                pass
        relay.close()
        if relay.thread_id:
            relay.set_status("done" if not is_error else "failed")

    # Append thread link so hurin can include it in the relay
    if relay.thread_url:
        print(f"\n📋 Session thread: {relay.thread_url}", flush=True)

    return 1 if is_error else 0


def main():
    args = parse_args()

    # Read prompt from stdin
    if sys.stdin.isatty():
        print("Error: prompt must be provided via stdin", file=sys.stderr)
        print(
            "Usage: echo 'your prompt' | python cc-query.py --description '...'",
            file=sys.stderr,
        )
        sys.exit(1)

    prompt = sys.stdin.read().strip()
    if not prompt:
        print("Error: empty prompt", file=sys.stderr)
        sys.exit(1)

    exit_code = asyncio.run(run_query(prompt, args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
