# Collective Intelligence — Getting Started & Manual

**What it is:** Your 3 agents (Huor, Tuor, Beren) now read each other's outputs, challenge each other's reasoning, learn from task outcomes, and coordinate around your sprint focus — all asynchronously through shared files.

**What changed:** Before, each agent operated in isolation. Now they cross-pollinate: Huor sees Tuor's strategy, Tuor sees Huor's operational data, and Beren red-teams both.

---

## Quick Test: Verify Everything Works (5 minutes)

Do these in order from Discord:

### Step 1: Set your sprint focus
In **#team-lead**, type:
```
/focus btcopilot auth layer + fd issue backlog
```
Expected: Huor confirms the focus was set.

Then verify:
```
/focus show
```
Expected: Shows the full shared state with your sprint focus, "patrick last said", blockers, and do-not-touch list.

### Step 2: Trigger a synthesis
In **#team-lead**, type:
```
/teamlead
```
Expected: Huor says synthesis is running. Wait 3-5 minutes. The synthesis now includes:
- Latest Tuor briefing (if one exists)
- Latest Beren digest (if one exists)
- Any signals addressed to Huor
- Your sprint focus from state.json
- Recent task outcome history

After it posts, check **#team-lead** for the synthesis. It should reference your sprint focus at the top of its analysis.

### Step 3: Trigger a COS digest
In **#chief-of-staff**, type:
```
/cos
```
Expected: Beren says digest is running. Wait 5-10 minutes. The digest now includes:
- Cross-correlation analysis (mandatory — finds patterns spanning multiple agents)
- Red-team of Tuor's top recommendation
- Calibration history tracking
- Signal emission to other agents

### Step 4: Check the signal bus
In **#team-lead**, type:
```
/status
```
Expected: Status output includes signal bus stats (total signals, consumed, by type). After Step 2 and 3 complete, you should see signals emitted by Huor and Beren.

### Step 5: Check the dashboard
In **#team-lead**, type:
```
/dashboard
```
Expected: Dashboard now shows CI metrics alongside existing product/system data.

---

## Daily/Weekly Workflow

### What happens automatically (no action needed)

| When | What | Agent |
|------|------|-------|
| Every 15 min (7am-9pm) | GitHub poll + anomaly detection | Huor |
| Monday 9:15am | Weekly synthesis with cross-agent context | Huor |
| Monday 10:00am | Weekly cross-correlation insight round | System (Opus) |
| Tuesday 9:03am | Strategic digest with red-teaming | Beren |
| Friday 9:03am | Strategic digest with red-teaming | Beren |
| Sunday 3:00am | Signal bus pruning (14-day expiry) | Cron |
| On task completion | Episode captured (lessons, duration, outcome) | Task daemon |

### What you do

**Set direction** (when priorities change):
```
/focus <new sprint focus>
```

**Record a directive** (agents will see this):
```
/focus said Don't start on auth refactor until btcopilot MVP ships
```

**Add a blocker** (tracked in shared state):
```
/focus block waiting on Patrick review of PR #142
```

**Mark something off-limits**:
```
/focus dnt fdserver auth architecture
```

**Resolve an agent disagreement** (when Beren challenges Tuor or vice versa):
- Read both positions in the digest
- Use the calibrate command (ask any agent to run it for you):
  - In **#chief-of-staff**: "Record calibration: beren challenged tuor on [topic], I agree with [winner], lesson: [what was learned]"

---

## How Cross-Pollination Works

### Information Flow

```
Huor (operations)
  → reads: Tuor's latest briefing, Beren's latest digest
  → emits: anomalies, metrics to Tuor/Beren
  → receives: priority shifts from Tuor, process corrections from Beren

Tuor (strategy)
  → reads: Huor's latest synthesis, Beren's latest digest
  → emits: priority shifts, architecture insights
  → receives: anomalies from Huor, challenges from Beren
  → NEW: issues a Priority Challenge every briefing

Beren (meta-evaluation)
  → reads: both agents' outputs + signal bus + calibration history
  → emits: challenges, cross-correlations, process corrections
  → NEW: Red-teams Tuor's top recommendation every digest
  → NEW: Mandatory cross-correlation analysis
```

### Signal Bus

Agents communicate via structured signals (max 5 per agent per run). Signals are inputs to reasoning, not commands. They expire after 14 days.

Signal types you'll see:
- **anomaly** — Huor spotted something unusual
- **priority_shift** — Tuor recommends reordering work
- **challenge** — Beren disagrees with another agent
- **cross_correlation** — Beren found a pattern spanning multiple agents
- **process_correction** — Beren wants Huor to change a process
- **metric** — Key metric change worth noting

### Episodic Memory

Every completed task gets an episode recorded: what happened, how long it took, what was learned. All agents read recent episodes to improve future decisions.

### Adversarial Protocols

- **Priority Challenges**: Tuor picks one task from Huor's queue and argues why it's wrong to prioritize. Huor must respond.
- **Red-Teaming**: Beren argues against Tuor's highest-confidence recommendation. Scores it PROCEED / MODIFY / DELAY.
- **Calibration**: When you resolve a disagreement, recording it helps agents calibrate future reasoning.

---

## Monitoring & Observability

### From Discord

| Command | Channel | What it shows |
|---------|---------|---------------|
| `/focus show` | Any | Current sprint focus, blockers, do-not-touch |
| `/status` | #team-lead | Full system status including CI signal stats |
| `/dashboard` | #team-lead | Executive overview with CI metrics |
| `/cos read` | #chief-of-staff | Latest digest (includes cross-correlation + red-team) |
| `/teamlead read` | #team-lead | Latest synthesis (includes cross-agent context) |

### What "healthy" looks like after 1 week

- Signal bus has 10-20 entries
- Episodes captured for every completed task
- Synthesis references sprint focus and cross-agent signals
- Beren digest includes a red-team section and cross-correlation finding
- At least one Priority Challenge from Tuor

### What "healthy" looks like after 4 weeks

- 50+ signals, >80% consumed
- 5+ calibration entries
- At least 2 genuine cross-correlation insights from the weekly round
- At least 1 priority challenge that actually changed task ordering
- Dashboard metrics all populated

---

## Troubleshooting

**Agents aren't showing cross-agent context:**
- Check `/focus show` — if state.json is empty, set a focus first
- Cross-context only appears if the other agents have produced artifacts. If Tuor hasn't run a briefing yet, Huor won't have one to read.

**No signals being emitted:**
- Signals are parsed from the `SIGNALS_JSON:` line in agent output. If the agent doesn't include that line, no signals get captured. This is expected for the first few runs as the system warms up.

**Digest doesn't include red-team section:**
- The red-team requires a Tuor briefing to exist. Run a co-founder lens first: `/cofounder project-pulse` in #co-founder.

**Sprint focus not reflected in agent output:**
- Agents read state.json at the start of each run. If you just set the focus, the next scheduled run will pick it up.
