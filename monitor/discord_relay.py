"""
Shared Discord relay module for streaming Claude Code sessions to Discord threads.

Used by both task-daemon.py (background tasks) and cc-query.py (sync queries).
Provides low-level Discord API helper and the DiscordThreadRelay class for
styled, batched message streaming.
"""

import asyncio
import json
import logging
import re
import time
import urllib.request
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ResultMessage
from claude_agent_sdk.types import TextBlock, ToolUseBlock

# ---------------------------------------------------------------------------
# Secret scrubbing — never leak credentials to Discord
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    re.compile(r'AIza[A-Za-z0-9_-]{35}'),                          # Google API keys
    re.compile(r'sk-[A-Za-z0-9]{32,}'),                             # OpenAI keys
    re.compile(r'gh[ps]_[A-Za-z0-9]{36,}'),                         # GitHub tokens
    re.compile(r'xox[bpas]-[A-Za-z0-9\-]{10,}'),                    # Slack tokens
    re.compile(r'(?i)(api[_-]?key|api[_-]?secret|token|password|secret[_-]?key)\s*[=:]\s*["\']?([A-Za-z0-9_/+=\-]{20,})'),  # Generic KEY=value
    re.compile(r'Bearer\s+[A-Za-z0-9_\-/.]{20,}'),                  # Bearer tokens
    re.compile(r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----'),         # Private keys
]


def scrub_secrets(text):
    """Replace detected secrets with [REDACTED]."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub('[REDACTED]', text)
    return text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HOME = Path.home()
MONITOR_DIR = HOME / ".openclaw/monitor"

DISCORD_TOKEN_FILE = MONITOR_DIR / "discord-bot-token"
BOT_TOKEN_FILE = MONITOR_DIR / "hurin-bot-token"

DISCORD_GUILD_ID = "1474833522710548490"
DISCORD_QUICKWINS_CHANNEL_ID = "1476950473893482587"
DISCORD_TASKS_CHANNEL_ID = "1476635425777914007"

log = logging.getLogger("discord-relay")

# ---------------------------------------------------------------------------
# Token loading
# ---------------------------------------------------------------------------

_discord_bot_token = ""


def load_discord_token():
    """Load Discord bot token from secrets.json (preferred) or legacy file."""
    global _discord_bot_token
    secrets_file = HOME / ".openclaw/secrets.json"
    if secrets_file.exists():
        try:
            import json
            secrets = json.loads(secrets_file.read_text())
            token = secrets.get("discord-bot-token", "")
            if token:
                _discord_bot_token = token
                return _discord_bot_token
        except (json.JSONDecodeError, IOError):
            pass
    if DISCORD_TOKEN_FILE.exists():
        _discord_bot_token = DISCORD_TOKEN_FILE.read_text().strip()
    return _discord_bot_token


def get_discord_token():
    """Get the current Discord bot token (call load_discord_token first)."""
    return _discord_bot_token


def set_discord_token(token):
    """Set the Discord bot token directly (for callers that manage their own loading)."""
    global _discord_bot_token
    _discord_bot_token = token


# ---------------------------------------------------------------------------
# Low-level Discord API
# ---------------------------------------------------------------------------


def discord_api(method, url, payload=None):
    """Low-level Discord API call. Returns parsed JSON or None."""
    if not _discord_bot_token:
        return None
    try:
        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bot {_discord_bot_token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "TaskDaemon (https://openclaw.ai, 2.0)")
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.warning(f"  Discord API error: {e}")
        return None


# ---------------------------------------------------------------------------
# Bot user ID (cached)
# ---------------------------------------------------------------------------

_bot_user_id = ""


def get_bot_user_id():
    """GET /users/@me and cache the bot's own user ID."""
    global _bot_user_id
    if _bot_user_id:
        return _bot_user_id
    result = discord_api("GET", "https://discord.com/api/v10/users/@me")
    if result and "id" in result:
        _bot_user_id = result["id"]
        log.info(f"  Bot user ID cached: {_bot_user_id}")
    return _bot_user_id


# ---------------------------------------------------------------------------
# Discord Thread Poller (for steering)
# ---------------------------------------------------------------------------


async def poll_discord_thread(thread_id, steer_queue, poll_interval=3.0,
                              bot_user_id=None, last_seen_id="0"):
    """Long-running async task that polls a Discord thread for new user messages.

    Pushes each non-bot message's content into steer_queue (asyncio.Queue).
    Runs until cancelled. Never crashes — logs errors and backs off.
    """
    if not bot_user_id:
        bot_user_id = get_bot_user_id()

    backoff = poll_interval
    loop = asyncio.get_event_loop()

    while True:
        try:
            await asyncio.sleep(backoff)

            url = (
                f"https://discord.com/api/v10/channels/{thread_id}"
                f"/messages?after={last_seen_id}&limit=100"
            )
            result = await loop.run_in_executor(
                None, lambda: discord_api("GET", url)
            )

            if result is None:
                # API error — already logged by discord_api
                backoff = min(backoff * 2, 30.0)
                continue

            backoff = poll_interval  # reset on success

            if not isinstance(result, list) or not result:
                continue

            # Discord returns newest-first; reverse for chronological order
            result.sort(key=lambda m: m["id"])

            for msg in result:
                author = msg.get("author", {})
                # Skip bot's own messages and any bot messages
                if author.get("id") == bot_user_id or author.get("bot"):
                    continue

                content = msg.get("content", "").strip()
                if content:
                    await steer_queue.put(content)
                    log.info(f"  Steer message queued: {content[:80]}")

                last_seen_id = msg["id"]

        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning(f"  Thread poller error: {e}")
            backoff = min(backoff * 2, 30.0)


# ---------------------------------------------------------------------------
# Discord Thread Relay
# ---------------------------------------------------------------------------


class DiscordThreadRelay:
    """Streams task/query progress to a Discord thread in #tasks.

    Styled to approximate the Claude Code VS Code extension:
    - Claude's thinking/text → blockquote with 💭
    - Tool calls → emoji + bold tool name + details in code block
    - Tool groups (consecutive tools) batched into one message
    - Result → final summary bar

    Rules-based filtering — no LLM tokens. Batches messages to respect
    Discord rate limits (max 1 post per BATCH_INTERVAL seconds).
    """

    BATCH_INTERVAL = 12  # seconds between Discord posts
    BATCH_MAX_CHARS = 1800  # flush before hitting Discord's 2000 limit

    # Tool emoji mapping (matches CC extension iconography)
    TOOL_EMOJI = {
        "Bash": "⚡",
        "Read": "📄",
        "Edit": "✏️",
        "Write": "📝",
        "Grep": "🔍",
        "Glob": "🔍",
        "Agent": "🤖",
        "WebSearch": "🌐",
        "WebFetch": "🌐",
        "Skill": "⚙️",
    }

    def __init__(self, task_id, description, repo="theapp"):
        self.task_id = task_id
        self.description = description
        self.repo = repo
        self.thread_id = None
        self._buffer = []  # list of formatted strings
        self._buffer_chars = 0
        self._last_flush = time.time()
        self._tool_count = 0
        self._text_count = 0

    def create_thread(self, header_prefix="🚀"):
        """Create a thread in #tasks. Returns thread_id or None."""
        result = discord_api(
            "POST",
            f"https://discord.com/api/v10/channels/{DISCORD_TASKS_CHANNEL_ID}/threads",
            {
                "name": f"{self.task_id}",
                "type": 11,  # PUBLIC_THREAD
                "auto_archive_duration": 1440,  # 24 hours
            },
        )
        if result and "id" in result:
            self.thread_id = result["id"]
            # Header — styled like CC session start
            self._post(
                f"## {header_prefix} `{self.task_id}`\n"
                f"**{self.description}**\n"
                f"repo: `{self.repo}` · model: `opus-4.6` · mode: `bypass`"
            )
            log.info(f"  Discord thread created: {self.thread_id}")
            return self.thread_id
        return None

    def _post(self, content):
        """Post a message to the thread. Scrubs secrets before sending."""
        if not self.thread_id:
            return
        content = scrub_secrets(content)[:1990]
        discord_api(
            "POST",
            f"https://discord.com/api/v10/channels/{self.thread_id}/messages",
            {"content": content},
        )

    def on_message(self, message):
        """Process an SDK message. Filters and batches for Discord."""
        if not self.thread_id:
            return

        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text.strip()
                    if not text:
                        continue
                    self._text_count += 1
                    # Claude's text → blockquote (like CC's chat bubbles)
                    quoted = "\n".join(f"> {line}" for line in text.split("\n"))
                    self._append(quoted)

                elif isinstance(block, ToolUseBlock):
                    self._tool_count += 1
                    formatted = self._format_tool_use(block)
                    if formatted:
                        self._append(formatted)

        elif isinstance(message, ResultMessage):
            # Flush, then post final result bar + result text
            self._flush()
            mins = message.duration_ms / 60000
            turns = message.num_turns
            stats = (
                f"`{mins:.1f}min` · `{turns} turns` · "
                f"`{self._tool_count} tool calls`\n"
                f"session: `{message.session_id}`"
            )
            if message.is_error:
                self._post(f"## ❌ Task failed\n{stats}")
            else:
                self._post(f"## ✅ Task complete\n{stats}")

            # Post the full result text (CC's final summary)
            result = (message.result or "").strip()
            if result:
                # Split into Discord-sized chunks
                while result:
                    chunk = result[:1990]
                    if len(result) > 1990:
                        # Try to split on a newline
                        split_at = chunk.rfind("\n")
                        if split_at > 200:
                            chunk = result[:split_at]
                    self._post(chunk)
                    result = result[len(chunk):].lstrip("\n")
            return

        # Auto-flush on interval or size
        now = time.time()
        if (self._buffer_chars >= self.BATCH_MAX_CHARS or
                (self._buffer and now - self._last_flush >= self.BATCH_INTERVAL)):
            self._flush()

    def _format_tool_use(self, block):
        """Format a tool use block to look like CC extension tool panels."""
        name = block.name
        inp = block.input or {}
        emoji = self.TOOL_EMOJI.get(name, "🔧")

        if name == "Bash":
            cmd = inp.get("command", "")
            desc = inp.get("description", "")
            # Show description if available, command in code block
            if len(cmd) > 300:
                cmd = cmd[:297] + "…"
            header = f"{emoji} **Bash**"
            if desc:
                header += f" · {desc}"
            return f"{header}\n```\n$ {cmd}\n```"

        elif name == "Read":
            path = self._short_path(inp.get("file_path", ""))
            return f"{emoji} **Read** `{path}`"

        elif name == "Edit":
            path = self._short_path(inp.get("file_path", ""))
            old = inp.get("old_string", "")
            # Show a hint of what changed
            if old:
                preview = old.split("\n")[0][:60]
                return f"{emoji} **Edit** `{path}` · `{preview}…`"
            return f"{emoji} **Edit** `{path}`"

        elif name == "Write":
            path = self._short_path(inp.get("file_path", ""))
            return f"{emoji} **Write** `{path}`"

        elif name == "Grep":
            pattern = inp.get("pattern", "")
            path = inp.get("path", "")
            suffix = f" in `{self._short_path(path)}`" if path else ""
            return f"{emoji} **Grep** `{pattern}`{suffix}"

        elif name == "Glob":
            pattern = inp.get("pattern", "")
            return f"{emoji} **Glob** `{pattern}`"

        elif name == "Agent":
            desc = inp.get("description", "")
            agent_type = inp.get("subagent_type", "")
            return f"{emoji} **Agent** ({agent_type}) · {desc}"

        elif name == "WebSearch":
            query = inp.get("query", "")
            return f"{emoji} **Search** `{query}`"

        else:
            return f"🔧 **{name}**"

    def _short_path(self, path):
        """Shorten paths for readability — strip worktree prefix."""
        if not path:
            return ""
        # Strip common long prefixes
        for prefix in [
            str(HOME / ".openclaw/workspace-hurin/btcopilot-worktrees/"),
            str(HOME / ".openclaw/workspace-hurin/familydiagram-worktrees/"),
            str(HOME / ".openclaw/workspace-hurin/theapp/"),
            str(HOME) + "/",
        ]:
            if path.startswith(prefix):
                # Also strip the task-id directory
                remainder = path[len(prefix):]
                parts = remainder.split("/", 1)
                if len(parts) > 1:
                    return parts[1]  # skip task-id dir
                return remainder
        return path

    def _append(self, text):
        """Add formatted text to the buffer."""
        self._buffer.append(text)
        self._buffer_chars += len(text) + 1  # +1 for newline

    def _flush(self):
        """Flush buffered lines to Discord as a single message."""
        if not self._buffer or not self.thread_id:
            return
        content = "\n".join(self._buffer)
        # Split on Discord's 2000 char limit
        while content:
            # Try to split on a newline boundary
            if len(content) <= 1990:
                self._post(content)
                break
            split_at = content.rfind("\n", 0, 1990)
            if split_at == -1:
                split_at = 1990
            self._post(content[:split_at])
            content = content[split_at:].lstrip("\n")
        self._buffer.clear()
        self._buffer_chars = 0
        self._last_flush = time.time()

    def post_prompt(self, full_prompt, label="System Prompt"):
        """Post the full prompt sent to the Agent SDK into the thread."""
        if not self.thread_id:
            return
        header = f"## 📋 {label}\n"
        # Wrap in a code block for readability; split if needed
        body = full_prompt.strip()
        # Discord limit is 2000 chars per message; header + fences ~30 chars
        max_body = 1990 - len(header) - 10  # leave room for fences + newlines
        chunks = []
        while body:
            chunk = body[:max_body]
            if len(body) > max_body:
                # Try to split on a newline
                split_at = chunk.rfind("\n")
                if split_at > 200:
                    chunk = body[:split_at]
            chunks.append(chunk)
            body = body[len(chunk):].lstrip("\n")

        for i, chunk in enumerate(chunks):
            prefix = header if i == 0 else ""
            self._post(f"{prefix}```\n{chunk}\n```")

    def post_pr(self, pr_url, risk):
        """Post PR notification to the thread."""
        if not self.thread_id:
            return
        risk_emoji = {"high": "🔴 HIGH RISK", "medium": "🟡 MEDIUM", "low": "🟢 LOW RISK"}.get(risk, "")
        self._post(
            f"## 🔗 PR Created\n"
            f"{risk_emoji}\n"
            f"<{pr_url}>"
        )

    def set_status(self, status):
        """Update the thread name with a status emoji prefix.

        This makes #tasks a visual dashboard — sidebar shows:
          🔄 cf-task-id  → running
          ✅ cf-task-id  → done (PR ready)
          ❌ cf-task-id  → failed
          🔁 cf-task-id  → respawning
          💀 cf-task-id  → killed
          ⏳ cf-task-id  → waiting (CI/review)
        """
        if not self.thread_id:
            return
        emoji_map = {
            "running": "🔄",
            "done": "✅",
            "failed": "❌",
            "respawn": "🔁",
            "killed": "💀",
            "pr_open": "⏳",
            "steering": "📡",
        }
        emoji = emoji_map.get(status, "❓")
        new_name = f"{emoji} {self.task_id}"
        discord_api(
            "PATCH",
            f"https://discord.com/api/v10/channels/{self.thread_id}",
            {"name": new_name},
        )

    @property
    def thread_url(self):
        """Discord URL for the thread, or None if no thread."""
        if not self.thread_id:
            return None
        return f"https://discord.com/channels/{DISCORD_GUILD_ID}/{self.thread_id}"

    def close(self):
        """Flush any remaining buffer."""
        self._flush()


# ---------------------------------------------------------------------------
# Channel Thread Registry — shared across all components
# ---------------------------------------------------------------------------

CHANNEL_THREADS_FILE = MONITOR_DIR / "channel-threads.json"

# Max age for monitoring channel threads (7 days)
CHANNEL_THREAD_MAX_AGE = 7 * 24 * 3600


def load_channel_threads():
    """Load the channel thread registry."""
    if not CHANNEL_THREADS_FILE.exists():
        return {"threads": []}
    try:
        return json.loads(CHANNEL_THREADS_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {"threads": []}


def save_channel_threads(data):
    """Save the channel thread registry."""
    CHANNEL_THREADS_FILE.write_text(json.dumps(data, indent=2))


def register_channel_thread(thread_id, channel_type, channel_id,
                             session_id="", context_file="", label=""):
    """Register a thread for reply monitoring.

    Args:
        thread_id: Discord thread ID
        channel_type: "cos", "teamlead", or "cofounder"
        channel_id: Discord channel ID the thread belongs to
        session_id: Claude SDK session ID for resume
        context_file: Path to the context file (digest, synthesis, briefing)
        label: Human-readable label for the thread
    """
    data = load_channel_threads()
    # Prune expired threads
    now = time.time()
    data["threads"] = [
        t for t in data["threads"]
        if now - t.get("created_at_ts", 0) < CHANNEL_THREAD_MAX_AGE
    ]
    # Avoid duplicate registration
    data["threads"] = [
        t for t in data["threads"]
        if t.get("thread_id") != thread_id
    ]
    data["threads"].append({
        "thread_id": thread_id,
        "channel_type": channel_type,
        "channel_id": channel_id,
        "session_id": session_id,
        "context_file": context_file,
        "label": label,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "created_at_ts": now,
        "last_checked_message_id": "0",
    })
    save_channel_threads(data)
    log.info(f"Registered {channel_type} thread: {thread_id} ({label})")


def create_channel_thread(channel_id, first_message, thread_name):
    """Post a message to a channel, then create a thread on it. Returns (thread_id, message_id) or (None, None)."""
    # Post the first message
    msg_result = discord_api(
        "POST",
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        {"content": first_message[:2000]},
    )
    if not msg_result or "id" not in msg_result:
        return None, None

    message_id = msg_result["id"]

    # Create thread on that message
    thread_result = discord_api(
        "POST",
        f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/threads",
        {
            "name": thread_name[:100],
            "auto_archive_duration": 1440,
        },
    )
    if not thread_result or "id" not in thread_result:
        return None, None

    thread_id = thread_result["id"]
    return thread_id, message_id


def post_to_channel_thread(thread_id, content):
    """Post a message (or chunked messages) to an existing thread."""
    chunks = []
    current = ""
    for line in content.split("\n"):
        if current and len(current) + len(line) + 1 > 1900:
            chunks.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)

    for chunk in chunks:
        if len(chunk) > 2000:
            chunk = chunk[:1997] + "..."
        discord_api(
            "POST",
            f"https://discord.com/api/v10/channels/{thread_id}/messages",
            {"content": chunk},
        )
        time.sleep(0.5)
