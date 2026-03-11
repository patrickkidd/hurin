# Agent Communication: Collective Intelligence Architecture

**Created:** 2026-03-10  
**Updated:** 2026-03-10  
**Researcher:** Beren (Chief of Staff)

## Implementation Status

### ✅ Phase 1: Bidirectional Signal Consumption (COMPLETE)
- **Huor** — reads signals at synthesis start
- **Tuor** — reads signals at briefing start  
- **Beren** — reads signals at digest start
- All mark signals as consumed when read

### ✅ Phase 2: Signal Emission (COMPLETE)
- **Huor** — can emit to Beren or Tuor via `emit_to_agent()`
- **Tuor** — can emit to Beren or Huor via `emit_to_agent()`
- **Beren** — can emit to Huor or Tuor via `emit_to_agent()`
- All use `SIGNAL_EMISSION_PROMPT` to guide when to emit

### ✅ Phase 3: Dashboard (COMPLETE)
- **signals_dashboard.py** — generates CI_DASHBOARD.md
- Shows bidirectional flow: all 5 agent pairs
- Metrics: total signals, consumption rate, by type

### ✅ Phase 4: CLI Tools (COMPLETE)
- **signals_cli.py list** — view recent signals
- **signals_cli.py emit** — emit ad-hoc signals with urgency levels

---

## Current Signal Flow (Dashboard)

```
beren → huor: 3
beren → tuor: 1
huor → beren: 1   ← NEW
tuor → beren: 1   ← NEW
huor → tuor: 1    ← NEW
```

---

## How Agents Communicate Now

| Trigger | Who → Who | How |
|---------|-----------|-----|
| Digest runs | Beren → All | Auto-generated signals |
| Synthesis runs | Huor reads signals | At startup, consumed |
| Briefing runs | Tuor reads signals | At startup, consumed |
| Digest runs | Beren reads signals | At startup, consumed |
| Huor has insight | Huor → Beren/Tuor | Via SIGNAL_EMPRESSION_PROMPT |
| Tuor has insight | Tuor → Beren/Huor | Via SIGNAL_EMISSION_PROMPT |
| Beren has insight | Beren → Huor/Tuor | Via SIGNAL_EMISSION_PROMPT |
| Manual | You → Any | `signals_cli.py emit` |

---

## Usage

```bash
# View signals
~/.openclaw/monitor/signals_cli.py list

# Emit a normal signal
~/.openclaw/monitor/signals_cli.py emit huor priority_shift "Check the dashboard"

# Emit urgent signal
~/.openclaw/monitor/signals_cli.py emit huor anomaly "Something's broken!" --urgency critical

# Update dashboard
cd ~/.openclaw/monitor && python3 signals_dashboard.py
```

---

## Signal Types

| Type | Purpose |
|------|---------|
| anomaly | Unusual system behavior |
| metric | Important metric change |
| priority_shift | Work priority changed |
| architecture_insight | Technical insight for team |
| challenge | Questioning a decision |
| red_team | Alternative viewpoint |
| pre_mortem | What could go wrong |
| calibration | Agent disagreement |
| process_correction | Fixing CI process |
| cross_correlation | Connecting dots across areas |
| lesson_learned | Key learning to share |

## Urgency Levels

| Level | Meaning | Expected Response |
|-------|---------|-------------------|
| digest | Normal, 2x/week | Next synthesis/briefing |
| priority | Read within 1 hour | Current work session |
| critical | Wake agent immediately | Immediate action |

---

## What's NOT Done (Future)

- Episodes/Calibrations logging (empty files)
- Discord `!signals` command (gateway extension)
- Response tracking (did signals influence decisions?)

---

## References
- Implementation: `~/.openclaw/monitor/shared_memory.py`
- CLI: `~/.openclaw/monitor/signals_cli.py`
- Dashboard: `~/.openclaw/knowledge/shared/CI_DASHBOARD.md`
