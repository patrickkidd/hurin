# HEARTBEAT.md

# Periodic tasks for Beren (Chief of Staff)

## Tasks

### 1. Research Synthesis (Weekly)
- **When:** Every Friday at 10 AM AKST
- **Action:** Run CC (chief-of-staff.py) with focus on:
  - Collective intelligence literature → agent team architecture
  - Bowen theory → organizational/agentic team dynamics
- **Output:** Save to `knowledge/strategy/agent-architecture-research.md`
- **Why:** Build a research foundation for the next digest recommendation

### 2. System Health Check (Daily)
- **When:** Every day at 9 AM AKST
- **Action:** Check:
  - Gateway status (`openclaw gateway status`)
  - Recent errors in `~/.openclaw/chief-of-staff/cron.log`
  - Task daemon health (`~/.openclaw/monitor/task-events.jsonl` last 24h)
- **Output:** Brief status note to #chief-of-staff if issues found
- **Why:** Catch problems before they compound

### 3. Digest Freshness (Daily)
- **When:** Every day at 8 AM AKST  
- **Action:** Check if latest digest is >3 days old
- **Output:** If stale, remind Patrick to run `/cos`
- **Why:** Keep strategic guidance current

### 4. Cross-Agent Context Pull (Weekly)
- **When:** Every Monday at 9 AM AKST
- **Action:** Read recent syntheses from Huor and briefings from Tuor
- **Output:** Brief summary note if there are cross-agent themes
- **Why:** Surface connections before they become obvious
