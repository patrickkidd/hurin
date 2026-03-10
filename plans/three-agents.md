# Plan: Three-Agent Architecture — Huor, Tuor, Beren

## Naming

- **Húrin** — the platform. Linux user, VPS, repo `patrickkidd/hurin`. Not an agent.
- **Huor** — Team Lead. Renamed from existing `hurin` Discord bot.
- **Tuor** — Co-Founder. New Discord bot.
- **Beren** — Chief of Staff. New Discord bot.

## Context

Restructuring from one agent (`hurin`) + slash commands to three autonomous agents with clearly defined scope. Each agent is a specialist — the key advantage of LLM teams is that narrow scope produces better outputs. All agents run on MiniMax M2.5 and retain the two-tier architecture: MiniMax routes, Claude Code (Opus 4.6) does heavy lifting via Agent SDK.

## Architecture

### Agent → Channel Mapping

| Agent | Discord Bot | Channel(s) | Scope |
|-------|------------|-----------|-------|
| Huor | `huor` (renamed hurin bot) | #planning, #tasks, #quick-wins, #team-lead | Task execution, GitHub monitoring, hourly synthesis, task spawning |
| Tuor | `tuor` (new bot) | #co-founder | Strategic briefings (9 lenses), product vision, market research, KB-aware analysis |
| Beren | `beren` (new bot) | #chief-of-staff | Meta-orchestration, strategic digests, system evaluation, recommendations |

### Two-Tier Intelligence (unchanged per agent)

Every agent is MiniMax M2.5 — fast, cheap, good at routing. Complex work is offloaded to Claude Code / Opus 4.6 via the existing Agent SDK scripts:
- **cc-query.py** — sync queries (blocks turn, Discord thread relay, live steering)
- **task spawn** — async background tasks (worktree, PR output, respawn with session resume)
- **co-founder-sdk.py** — strategic lens analysis
- **chief-of-staff.py** — meta-analysis digests

Agents NEVER call `claude -p` directly. Always Agent SDK.

### What Changes

| Before | After |
|--------|-------|
| 1 agent (`hurin`) + slash commands | 3 agents, each conversational in their channels |
| `/cos followup`, `/cofounder followup`, `/teamlead followup` | Reply in the thread — daemon auto-resumes session |
| Single SOUL.md / memory | Per-agent SOUL.md, AGENTS.md, memory (QMD) |
| `hurin` = agent identity | `hurin` = platform; agents are huor/tuor/beren |

### What Stays the Same

- **Task daemon** — unchanged, executes all CC work via Agent SDK
- **Cron jobs** — co-founder-sdk.py, chief-of-staff.py, team-lead.py stay as standalone scripts
- **Thread follow-ups** — daemon's `check_channel_thread_replies()` handles conversational follow-up
- **Model** — all three agents on MiniMax M2.5
- **Gateway** — single process hosting all three agents
- **Co-founder lens slash commands** — retained (e.g. `/cofounder architecture`, `/cofounder project-pulse`)
- **Agent-to-agent communication** — enabled via `sessions_send` (config: `agentToAgent.enabled: true`)

## Implementation Steps

### Step 1: Create Discord bot applications (PATRICK — IN PROGRESS)

**Already done:** Renamed existing `hurin` bot → `Huor` in Discord Developer Portal.

**Still needed:** Create 2 new bot applications:
- **Tuor** bot
- **Beren** bot

For each new bot in Developer Portal:

**Intents** (Bot tab → Privileged Gateway Intents):
- Message Content Intent — ON (required)
- Server Members Intent — ON (needed for user allowlists)

**OAuth2 invite URL** (OAuth2 → URL Generator):
- Scopes: `bot`, `applications.commands`
- Bot Permissions: View Channels, Send Messages, Read Message History, Embed Links, Attach Files, Add Reactions

Do NOT grant Administrator.

Invite both bots to the Alaska Family Systems guild.

Add tokens to `~/.openclaw/secrets.json`:
```json
{
  "huor-discord-bot-token": "<existing hurin token>",
  "tuor-discord-bot-token": "<new token>",
  "beren-discord-bot-token": "<new token>"
}
```

### Step 2: Create agent workspaces (new, clean folders)

```
~/.openclaw/workspace-huor/
  SOUL.md        — Team lead scope: task execution, GitHub monitoring, synthesis, spawning
  AGENTS.md      — Lifecycle rules, Discord formatting, memory capture
  USER.md        — Patrick info (shared content across agents)
  TOOLS.md       — exec, task spawn, cc-query.py, sessions_send
  IDENTITY.md    — huor identity
  memory/        — QMD-indexed per-agent memory

~/.openclaw/workspace-tuor/
  SOUL.md        — Co-founder scope: 9 lenses, strategic briefings, product vision, market research
  AGENTS.md      — Lifecycle rules, Discord formatting, memory capture
  USER.md        — Patrick info (shared)
  TOOLS.md       — exec, co-founder-sdk.py, sessions_send
  IDENTITY.md    — tuor identity
  memory/        — QMD-indexed per-agent memory

~/.openclaw/workspace-beren/
  SOUL.md        — Chief of staff scope: meta-orchestration, digests, system evaluation
  AGENTS.md      — Lifecycle rules, Discord formatting, memory capture
  USER.md        — Patrick info (shared)
  TOOLS.md       — exec, chief-of-staff.py, sessions_send
  IDENTITY.md    — beren identity
  memory/        — QMD-indexed per-agent memory
```

SOUL.md content comes from existing feature definitions:
- **Huor** ← team-lead.py, config.py, ADR-0006, skills/teamlead/SKILL.md
- **Tuor** ← co-founder-sdk.py, co-founder/README.md, ADR-0004, skills/cofounder/SKILL.md
- **Beren** ← chief-of-staff.py, skills/cos/SKILL.md

Focus on **scope boundaries** — what each agent owns, what it delegates, what it never touches.

Old `workspace-hurin/` stays as-is. Fix any references that break.

### Step 3: Create agent state directories

```bash
openclaw agents add huor
openclaw agents add tuor
openclaw agents add beren
```

Or manually:
```
~/.openclaw/agents/huor/agent/   — auth-profiles.json, models.json
~/.openclaw/agents/huor/sessions/
~/.openclaw/agents/huor/qmd/

~/.openclaw/agents/tuor/agent/
~/.openclaw/agents/tuor/sessions/
~/.openclaw/agents/tuor/qmd/

~/.openclaw/agents/beren/agent/
~/.openclaw/agents/beren/sessions/
~/.openclaw/agents/beren/qmd/
```

### Step 4: Update openclaw.json

**agents.list** — replace single hurin agent with three:

```json
{
  "id": "huor",
  "name": "huor",
  "workspace": "/home/hurin/.openclaw/workspace-huor",
  "agentDir": "/home/hurin/.openclaw/agents/huor/agent",
  "model": "minimax/MiniMax-M2.5",
  "tools": {
    "allow": ["exec", "sessions_list", "sessions_history", "session_status", "sessions_send"]
  }
},
{
  "id": "tuor",
  "name": "tuor",
  "workspace": "/home/hurin/.openclaw/workspace-tuor",
  "agentDir": "/home/hurin/.openclaw/agents/tuor/agent",
  "model": "minimax/MiniMax-M2.5",
  "tools": {
    "allow": ["exec", "sessions_list", "sessions_history", "session_status", "sessions_send"]
  }
},
{
  "id": "beren",
  "name": "beren",
  "workspace": "/home/hurin/.openclaw/workspace-beren",
  "agentDir": "/home/hurin/.openclaw/agents/beren/agent",
  "model": "minimax/MiniMax-M2.5",
  "tools": {
    "allow": ["exec", "sessions_list", "sessions_history", "session_status", "sessions_send"]
  }
}
```

**channels.discord.accounts** — three accounts:

```json
"huor": {
  "enabled": true,
  "allowBots": true,
  "groupPolicy": "allowlist",
  "historyLimit": 50,
  "streaming": "off",
  "guilds": {
    "1474833522710548490": {
      "requireMention": false,
      "users": ["1237951508742672431"],
      "channels": {
        "1475607956698562690": { "allow": true },
        "1476635425777914007": { "allow": true },
        "1476950473893482587": { "allow": true },
        "1478507314427334950": { "allow": true }
      }
    }
  },
  "token": "${HUOR_DISCORD_BOT_TOKEN}"
},
"tuor": {
  "enabled": true,
  "groupPolicy": "allowlist",
  "historyLimit": 50,
  "streaming": "off",
  "guilds": {
    "1474833522710548490": {
      "requireMention": false,
      "users": ["1237951508742672431"],
      "channels": {
        "1476739270663213197": { "allow": true }
      }
    }
  },
  "token": "${TUOR_DISCORD_BOT_TOKEN}"
},
"beren": {
  "enabled": true,
  "groupPolicy": "allowlist",
  "historyLimit": 50,
  "streaming": "off",
  "guilds": {
    "1474833522710548490": {
      "requireMention": false,
      "users": ["1237951508742672431"],
      "channels": {
        "1479984919353626674": { "allow": true }
      }
    }
  },
  "token": "${BEREN_DISCORD_BOT_TOKEN}"
}
```

**bindings** — route channels to agents:

```json
{ "agentId": "huor", "match": { "channel": "discord", "accountId": "huor", "peer": { "kind": "channel", "id": "1475607956698562690" } } },
{ "agentId": "huor", "match": { "channel": "discord", "accountId": "huor", "peer": { "kind": "channel", "id": "1476635425777914007" } } },
{ "agentId": "huor", "match": { "channel": "discord", "accountId": "huor", "peer": { "kind": "channel", "id": "1476950473893482587" } } },
{ "agentId": "huor", "match": { "channel": "discord", "accountId": "huor", "peer": { "kind": "channel", "id": "1478507314427334950" } } },
{ "agentId": "tuor", "match": { "channel": "discord", "accountId": "tuor", "peer": { "kind": "channel", "id": "1476739270663213197" } } },
{ "agentId": "beren", "match": { "channel": "discord", "accountId": "beren", "peer": { "kind": "channel", "id": "1479984919353626674" } } }
```

### Step 5: Update gateway-wrapper.sh

Add env vars for all three bot tokens:

```bash
export HUOR_DISCORD_BOT_TOKEN=$(python3 -c "import json; print(json.load(open('$SECRETS_FILE'))['huor-discord-bot-token'])")
export TUOR_DISCORD_BOT_TOKEN=$(python3 -c "import json; print(json.load(open('$SECRETS_FILE'))['tuor-discord-bot-token'])")
export BEREN_DISCORD_BOT_TOKEN=$(python3 -c "import json; print(json.load(open('$SECRETS_FILE'))['beren-discord-bot-token'])")
```

Remove the old `DISCORD_BOT_TOKEN` export.

### Step 6: Simplify skills

**Remove /followup modes** from cos, cofounder, teamlead skills — thread replies handle this natively.

**Retain co-founder lens commands** — `/cofounder <lens>`, `/cofounder read`, `/cofounder approve`, etc.

**Move skills to per-agent workspaces:**
- `skills/cofounder/` → `workspace-tuor/skills/cofounder/`
- `skills/cos/` → `workspace-beren/skills/cos/`
- `skills/teamlead/` → `workspace-huor/skills/teamlead/`
- `task`, `dashboard`, `trust`, `research` → stay in `~/.openclaw/skills/` (shared)

### Step 7: Write SOUL.md for each agent

Derive from existing implementations. Each SOUL.md defines:
- **Scope** — what this agent owns exclusively
- **Delegates** — what gets offloaded to CC (Agent SDK, never CLI)
- **Never touches** — other agents' domains
- **Tools** — which scripts it calls and how
- **Personality** — brief, only if it helps the agent make better decisions

### Step 8: Update cron scripts (minimal)

Cron jobs stay as standalone scripts. They already post to the right Discord channels. Agents pick up conversational context when Patrick replies in threads.

### Step 9: Update CLAUDE.md and documentation

- Update agent architecture section (hurin = platform, huor/tuor/beren = agents)
- Update channel mapping
- Add new agent paths
- Record decision in `decisions/log.md`
- Write ADR for the 1-agent → 3-agent transition
- Update QUICKSTART.md
- Fix any broken `workspace-hurin` references

## Memory Pressure Estimate

Current baseline:
- Gateway: ~158MB
- Task daemon: ~108MB
- Team lead service: ~49MB
- Total: ~315MB on 2GB box

Adding 2 more agent identities to the gateway adds session state + QMD indexing but NOT additional processes. Gateway hosts all agents in one process. Estimated overhead: ~50-100MB.

Expected total: ~365-415MB — well within 2GB.

## Files to Create/Modify

| File | Change |
|------|--------|
| `~/.openclaw/openclaw.json` | Replace hurin agent with huor/tuor/beren; new accounts + bindings |
| `~/.openclaw/gateway-wrapper.sh` | Add HUOR/TUOR/BEREN discord token env vars |
| `~/.openclaw/secrets.json` | Add 3 discord bot tokens (Patrick) |
| `~/.openclaw/workspace-huor/SOUL.md` | New: team lead scope |
| `~/.openclaw/workspace-huor/AGENTS.md` | New: lifecycle rules |
| `~/.openclaw/workspace-huor/USER.md` | New: Patrick info |
| `~/.openclaw/workspace-huor/TOOLS.md` | New: available tools + two-tier pattern |
| `~/.openclaw/workspace-huor/IDENTITY.md` | New: huor identity |
| `~/.openclaw/workspace-tuor/SOUL.md` | New: co-founder scope |
| `~/.openclaw/workspace-tuor/AGENTS.md` | New: lifecycle rules |
| `~/.openclaw/workspace-tuor/USER.md` | New: Patrick info |
| `~/.openclaw/workspace-tuor/TOOLS.md` | New: available tools + two-tier pattern |
| `~/.openclaw/workspace-tuor/IDENTITY.md` | New: tuor identity |
| `~/.openclaw/workspace-beren/SOUL.md` | New: chief of staff scope |
| `~/.openclaw/workspace-beren/AGENTS.md` | New: lifecycle rules |
| `~/.openclaw/workspace-beren/USER.md` | New: Patrick info |
| `~/.openclaw/workspace-beren/TOOLS.md` | New: available tools + two-tier pattern |
| `~/.openclaw/workspace-beren/IDENTITY.md` | New: beren identity |
| `~/.openclaw/skills/cos/SKILL.md` | Remove followup mode, move to beren workspace |
| `~/.openclaw/skills/cofounder/SKILL.md` | Remove followup mode, move to tuor workspace |
| `~/.openclaw/skills/teamlead/SKILL.md` | Remove followup mode, move to huor workspace |
| `~/CLAUDE.md` | Update architecture section |

## Verification

1. `openclaw agents list --bindings` — verify 3 agents with correct channel bindings
2. `openclaw channels status --probe` — verify all 3 Discord bots connected
3. Post in #co-founder → Tuor responds (not Huor or Beren)
4. Post in #chief-of-staff → Beren responds
5. Post in #team-lead → Huor responds
6. `/cofounder project-pulse` in #co-founder → Tuor triggers lens
7. Reply in a COS digest thread → daemon resumes session
8. Reply in a TL synthesis thread → daemon resumes session
9. Gateway memory stays under 500MB after 1hr

## Blocked On

- **Step 1** — Patrick creating Tuor and Beren bot applications in Discord Developer Portal and adding tokens to secrets.json
- Everything else can be prepared in advance
