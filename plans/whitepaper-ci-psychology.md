# Whitepaper: Reducing Multi-Agent AI Failure Rates Through Systems-Theoretic Interaction Design

**Status:** Outline + research notes — ready for drafting in separate conversation
**Author:** Patrick Kidd
**Target audience:** Micron Technology leadership; AI/ML practitioners; anyone deploying multi-agent AI systems
**Self-contained:** This file has all context needed to draft the full paper independently.

---

## 0. Strategic Framing

### The Paper's Job

This paper must do four things, in this order:

1. **Define a concrete, costly business problem.** Multi-agent AI systems fail at high rates. 36.9% of failures come from interagent misalignment (Cemri et al., 2025). Current design approaches lack predictive models for *when* and *how* agent interactions degrade. These failures are expensive — wasted compute, bad decisions, unreliable automation.

2. **Present a solution that measurably reduces those failures.** Six design patterns, each with a specific metric. Implemented in a real system, measured over weeks. Before/after data. Not "we think this helps" — "here are the numbers."

3. **Reveal the theoretical depth that makes the solution robust.** The patterns aren't ad-hoc — they're grounded in 50+ years of research on small-group dynamics (Bowen Family Systems Theory) combined with 2024-2026 collective intelligence research. This theoretical backing means the patterns are *predictive*, not just descriptive. They tell you what will go wrong before it does.

4. **Establish unique expertise.** The author is a PhD psychologist, the leading Bowen theory technical expert in the world, and has spent 7 years at the intersection of psychological systems theory and collective intelligence. This isn't a framework anyone else at Micron (or most AI companies) could have built — the cross-domain synthesis requires deep expertise in both fields.

### What This Is NOT

- Not a theoretical exercise. Every claim must have data behind it.
- Not anthropomorphism. We're not saying "agents have feelings." We're saying small-group dynamics follow predictable patterns regardless of whether group members are humans or LLM agents.
- Not an academic paper optimizing for novelty. It's an engineering document that happens to have deep theoretical roots.

### Success Criteria for the Paper

The paper succeeds if a Micron VP reads it and thinks:
- "This solves a real problem we're about to have with our AI agent deployments"
- "The solution is specific enough that I could hand it to my team to implement"
- "The results are measurable and the metrics make sense"
- "This guy clearly knows something nobody else on our team knows"

---

## 1. The Business Problem

### Multi-Agent AI Systems Are the Next Scaling Paradigm

- Single-model scaling is plateauing. "Societies of models" — structured multi-agent systems — are the frontier (2025-2026 consensus).
- Micron and every large enterprise will deploy multi-agent AI systems within 2 years (manufacturing process control, supply chain optimization, R&D acceleration).
- The problem: **we don't know how to make agent teams reliable.**

### The Failure Landscape

- **36.9% of multi-agent failures** stem from interagent misalignment — agents operating on inconsistent shared state (Cemri et al., 2025, 1,600+ execution traces)
- Adversarial debate outperforms cooperative consensus (Mitsubishi Electric, 2026), but no framework tells you *when* to apply adversarial pressure vs. cooperation
- Sparse agent systems (< 5 agents) need different strategies than dense swarms (MIT, 2025), but most research focuses on large-N systems
- No existing framework provides **leading indicators** of system degradation. Current monitoring only catches failures after they've happened.

### The Cost

For an enterprise deploying multi-agent AI:
- Failed agent runs = wasted compute + wrong decisions propagated downstream
- Undetected misalignment = silent quality degradation (worse than a crash — you don't know it's happening)
- No interaction-level metrics = can't debug, can't improve, can't audit

### What's Missing

Current CS approaches tell you *what* structures to build (shared memory, adversarial debate, metacognitive governance). They do NOT tell you:
- How to calibrate the balance between agent autonomy and collaboration (too much of either degrades quality)
- How to detect system degradation *before* output quality drops
- How to prevent one agent's systematic bias from infecting others through shared memory
- How to manage cascade reactions when an anomaly triggers multiple agents simultaneously

**These are not novel problems.** They have been studied for 50+ years in small-group dynamics research. We just haven't applied that research to AI systems yet.

---

## 2. The Solution: Six Design Patterns with Measurable Outcomes

### Core Thesis

Psychological systems theory — specifically Bowen Family Systems Theory — provides a **predictive framework** for multi-agent AI failure modes. It prescribes six design patterns that each address a specific failure mode, with a specific metric to track improvement. The patterns work because the underlying dynamics (differentiation, reactivity, triangulation, projection) are properties of *any* interdependent system, not just human families.

### Why Bowen Theory Specifically

Bowen theory is unique among psychological frameworks in that it:
1. **Models systems, not individuals** — it describes how interconnected actors influence each other, which maps directly to multi-agent architectures
2. **Is empirically grounded** — 50+ years of clinical research with measurable scales (Differentiation of Self Inventory, Skowron & Friedlander 1998)
3. **Is predictive** — it tells you what will go wrong in a system based on structural properties, before the failure occurs
4. **Operates at the small-group scale** — optimized for 3-8 actors, exactly the range of most practical agent systems
5. **Has a mature vocabulary for interaction health** — concepts like differentiation, triangulation, cutoff, and reactivity have precise definitions that map to measurable agent behaviors

Other psychological frameworks considered and why Bowen is superior for this application:
- **Tuckman (forming-storming-norming-performing):** Descriptive, not predictive. Tells you stages exist, not how to optimize them.
- **Bion (group dynamics):** Focuses on unconscious processes. Less operationalizable for AI systems.
- **Argyris (double-loop learning):** Relevant for learning but doesn't address interaction topology or failure cascading.
- **Social Identity Theory:** Focuses on in-group/out-group dynamics. Less relevant for small, fixed-role systems.

---

## 3. The Mapping — Design Decisions with Measurable Impact

Each row must answer: **What design decision does this concept change, and how do we measure the improvement?**

### 3.1 Differentiation of Self → Agent Boundary Strength

**Bowen concept:** Differentiation is the ability to maintain your own position while remaining connected to others. Low differentiation = either fusing with others (groupthink) or cutting off entirely (isolation). High differentiation = staying connected while thinking independently.

**Design decision it changes:** How much weight should an agent give to cross-agent signals vs. its own analysis?

Without this concept, you'd either:
- (a) Have agents blindly consume all signals (fusion → groupthink → averaged-out quality), or
- (b) Have agents ignore signals (cutoff → isolation → no CI benefit)

**Implementation:** Each agent has a "differentiation parameter" — when a cross-agent signal conflicts with its own analysis, the agent must explicitly reason about the conflict rather than automatically deferring or ignoring. The prompt instructs: "If this signal contradicts your analysis, state both positions and explain why you maintain or change yours."

**Metric:** *Differentiation Score* = (decisions where agent explicitly addressed a conflicting signal and maintained its position with reasoning) / (total decisions with conflicting signals). Target: 40-70%. Below 40% = too deferential (fusion). Above 70% = not learning from others (cutoff).

**Comparison without Bowen:** Standard CI systems either implement hard override rules or soft weighting. Neither captures the dynamic: the right balance shifts depending on the agent's confidence and the signal's track record.

### 3.2 Triangulation → Structured Adversarial Routing

**Bowen concept:** When two people are in tension, they pull in a third to reduce anxiety. In families this is pathological (it stabilizes the dyad but damages the third person). In deliberate organizational design, it's a feature — that's what mediators, reviewers, and oversight boards are.

**Design decision it changes:** When Huor and Tuor disagree (operational priority vs. strategic priority), who resolves it and how?

Without this concept, you'd either:
- (a) Have them negotiate directly (unstable dyad, no resolution mechanism), or
- (b) Always escalate to Patrick (bottleneck, defeats autonomy goal)

**Implementation:** Beren is the *deliberate triangle vertex*. When Huor and Tuor have conflicting signals, Beren is explicitly prompted to evaluate both positions, red-team both, and produce a recommendation. Patrick is the *second-order triangle* — only invoked when Beren can't resolve it.

**Metric:** *Triangulation resolution rate* = conflicts resolved by Beren without Patrick escalation / total inter-agent conflicts. Target: > 60% over time. Also: *Triangulation accuracy* = Beren's resolution agreed with by Patrick when reviewed / total reviewed.

**Comparison without Bowen:** Standard multi-agent systems use either voting (degrades quality) or fixed hierarchy (rigid). The triangulation model is dynamic — Beren resolves what it can, escalates what it can't, and the system learns which conflict types need escalation.

### 3.3 Emotional Reactivity → Cascade Dampening

**Bowen concept:** In anxious systems, one member's reactivity triggers others, creating escalating cascades. A well-differentiated system absorbs anxiety rather than amplifying it.

**Design decision it changes:** What happens when an agent detects an anomaly?

Without this concept, you'd propagate anomalies as high-priority signals, potentially triggering all agents to react simultaneously — e.g., Huor detects CI failure → signals Beren → Beren escalates to Patrick → Tuor reprioritizes → multiple spawns — when the CI failure might be a flaky test.

**Implementation:** Confidence-gated signal propagation. Signals below 0.7 confidence are NOT broadcast. Anomalies require *triangulation* (corroboration from a second source) before triggering system-wide response. Beren's digest explicitly asks: "Is the system currently in a reactive state? If so, what would a non-reactive response look like?"

**Metric:** *Cascade rate* = multi-agent reactive responses to single anomalies / total anomalies detected. Target: < 20%. Also: *False positive cascade rate* = cascades triggered by anomalies that turned out to be non-issues.

**Comparison without Bowen:** Standard anomaly detection either has fixed thresholds (brittle) or uses ML-based anomaly scoring (complex, needs training data). The Bowen insight adds a *systemic* check: not "is this anomaly real?" but "is the system currently overreacting?"

### 3.4 Family Projection Process → Bias Propagation Detection

**Bowen concept:** A parent's anxiety gets "projected" onto a specific child, who absorbs it and develops symptoms. The parent feels better, the child gets worse. The projection is invisible to both parties.

**Design decision it changes:** How do you prevent one agent's systematic bias from infecting others through shared memory?

Without this concept, shared memory is treated as neutral ground. But if Huor systematically over-estimates task complexity (bias), and Tuor reads Huor's episodes to ground its strategy, Tuor inherits the bias without knowing it.

**Implementation:** The calibration system acts as a "bias detector." When Patrick records a calibration disagreement, the system checks: does this pattern repeat? Is the same agent consistently wrong in the same category? If so, tag that agent's outputs in that category with a bias warning that consuming agents can see.

**Metric:** *Projection detection rate* = systematic biases identified / total calibration entries. *Bias correction lag* = time from first signal of bias to corrective action.

**Comparison without Bowen:** Standard systems track accuracy but don't model the *propagation path* of errors. The projection concept specifically looks at how one agent's errors become another agent's assumptions.

### 3.5 Multigenerational Transmission → Episodic Memory with Calibrated Decay

**Bowen concept:** Patterns transmit across generations. Some are adaptive (cultural knowledge), some are maladaptive (trauma responses). The challenge is keeping the good while shedding the bad.

**Design decision it changes:** How long should episodic memory persist, and how should old lessons be weighted?

Without this concept, you'd either keep all episodes forever (stale lessons misguide future decisions) or expire them uniformly (losing valuable hard-won knowledge).

**Implementation:** Episodes have a "validation status" that decays over time. Recent episodes are weighted higher. Episodes that are *cited in successful tasks* get their validity reinforced. Episodes that are contradicted by newer outcomes get flagged for review. This creates differential decay: useful knowledge persists, outdated knowledge fades.

**Metric:** *Memory relevance score* = episodes cited in successful recent tasks / total episodes cited. *Stale lesson rate* = decisions informed by episodes > 30 days old that led to negative outcomes.

**Comparison without Bowen:** Standard RAG/memory systems use recency weighting or embedding similarity. The multigenerational concept adds outcome-based validation: a lesson's persistence should depend on whether it keeps being *right*, not just whether it keeps being *retrieved*.

### 3.6 Emotional Cutoff → Communication Health Monitoring

**Bowen concept:** When anxiety gets too high, people "cut off" — stop communicating with family members entirely. This reduces anxiety short-term but prevents resolution and stunts growth.

**Design decision it changes:** How do you detect when your CI system is degrading?

Without this concept, you'd only notice CI failure when output quality drops — a lagging indicator.

**Implementation:** Monitor signal consumption rate per agent. If an agent stops consuming signals (cutoff), that's a leading indicator of system degradation — before output quality drops. Dashboard alerts when any agent's consumption rate drops below 50%.

**Metric:** *Communication health score* = min(agent consumption rates). Alert threshold: < 50% for any agent.

**Comparison without Bowen:** Standard monitoring tracks output metrics. The cutoff concept specifically monitors *interaction health* as a leading indicator of output degradation.

---

## 4. Outline

```
Title: "Reducing Multi-Agent AI Failure Rates Through Systems-Theoretic
        Interaction Design: Six Patterns from Psychological Group Dynamics"

Alternative titles (pick during drafting):
- "Six Design Patterns That Cut Multi-Agent AI Failures by X%:
   Lessons from 50 Years of Group Dynamics Research"
- "Why Your AI Agents Keep Failing Each Other:
   A Systems-Theoretic Framework for Multi-Agent Reliability"

Abstract (300 words)
- Lead with: multi-agent AI failure rates, what they cost
- Then: 6 design patterns that reduce specific failure modes by measurable amounts
- Then: patterns grounded in psychological systems theory (Bowen, 50+ yr literature)
- Then: validated in production 3-agent system over N weeks
- Last: applicable to enterprise domains including semiconductor manufacturing

1. Introduction
   1.1 Multi-agent AI is the next scaling paradigm — enterprises are deploying now
   1.2 The failure landscape: 36.9% interagent misalignment, no leading indicators
   1.3 What's missing: predictive models for agent interaction health
   1.4 Our contribution: 6 measurable patterns from systems theory, with data

2. Background
   2.1 Collective Intelligence Research (2024-2026)
       - Woolley et al. (2010): collective intelligence factor in groups
       - Du et al. (2024): multi-agent debate improves factuality
       - Cemri et al. (2025): 36.9% failure rate from misalignment
       - Mitsubishi Electric (2026): adversarial > cooperative
       - MIT (2025): sparse systems benefit from strong per-agent memory
       - Hong et al. (2024): MetaGPT structured collaboration
       - Guo et al. (2024): multi-agent survey
   2.2 Bowen Family Systems Theory
       - Bowen (1978): eight interlocking concepts
       - Kerr & Bowen (1988): differentiation as core variable
       - Friedman (1991): chronic anxiety in systems
       - Guerin et al. (1996): triangulation dynamics
       - Gilbert (2004): practitioner's guide to eight concepts
   2.3 Prior work: Psychology × AI
       - Park et al. (2023): generative agents with personality
       - Shanahan et al. (2023): role-play with LLMs
       - Serapio-García et al. (2023): personality traits in LLMs
       - Gap: no systems-level framework for multi-agent CI

3. The Bowen-CI Framework
   3.1 Mapping table with design decisions and metrics (§3 above)
   3.2 Differentiation Score: measuring agent boundary health
   3.3 Structured Triangulation: adversarial routing via metacognitive agent
   3.4 Cascade Dampening: confidence-gated signal propagation
   3.5 Bias Propagation Detection: calibration as projection firewall
   3.6 Calibrated Memory Decay: multigenerational learning
   3.7 Communication Health: cutoff detection as leading indicator

4. Case Study: The Húrin System
   4.1 System architecture (3 agents, 2-tier, cron-scheduled)
       - Huor: Team Lead — task execution, GitHub monitoring, synthesis
       - Tuor: Co-Founder — strategic briefings, 9 lenses, KB-aware
       - Beren: Chief of Staff — meta-orchestrator, red-team, digests
       - Shared infrastructure: signal bus, episode memory, calibrations
   4.2 Baseline measurements (pre-CI)
       - Task spawn accuracy, duration, success rate
       - Decision quality (Patrick override rate)
       - Agent isolation (no cross-pollination)
   4.3 CI implementation
       - Cross-read injection into agent prompts
       - Signal bus with typed, confidence-scored signals
       - Adversarial protocols (priority challenges, red-teaming, pre-mortems)
       - Episodic memory with lesson extraction
   4.4 Post-CI measurements
       - Signal consumption rate, influence rate
       - Challenge accuracy, triangulation resolution rate
       - Decision quality delta (with vs without CI input)
       - Emergent cross-correlation insights
   4.5 Analysis: which Bowen concepts had the most impact?

5. Design Patterns for Practitioners
   5.1 The Differentiation Pattern
       - When to use: any multi-agent system where consensus is tempting
       - Implementation: conflicting-signal reasoning prompt
       - Anti-pattern: unanimous agreement = red flag
   5.2 The Structured Triangulation Pattern
       - When to use: 3+ agent systems with potential for conflict
       - Implementation: dedicated metacognitive agent as triangle vertex
       - Anti-pattern: all-to-all debate (O(n²) communication, no resolution)
   5.3 The Cascade Dampening Pattern
       - When to use: systems with anomaly detection that can trigger responses
       - Implementation: confidence gates + corroboration requirement
       - Anti-pattern: propagating every anomaly as urgent
   5.4 The Projection Firewall Pattern
       - When to use: systems with shared memory between agents
       - Implementation: calibration tracking + bias tagging on agent outputs
       - Anti-pattern: treating shared memory as neutral truth
   5.5 The Calibrated Decay Pattern
       - When to use: systems with episodic/procedural memory
       - Implementation: outcome-based validation + time decay
       - Anti-pattern: keep-everything or expire-uniformly

6. Enterprise Applications
   6.1 Why this matters for organizations building AI agent systems
   6.2 Semiconductor manufacturing: multi-agent process control
       - Agents monitoring different fab parameters
       - Cascade dampening prevents false alarm shutdowns
       - Triangulation for conflicting sensor readings
   6.3 Supply chain: multi-agent planning
       - Demand planning vs. supply planning agents
       - Differentiation prevents groupthink on forecasts
       - Calibrated memory prevents stale demand patterns
   6.4 R&D: multi-agent research assistance
       - Literature review + experiment design + analysis agents
       - Red-teaming research hypotheses
       - Bias detection in research directions
   6.5 Governance advantages: auditability of agent interactions
       - Signal bus = complete audit trail
       - Calibrations = decision quality tracking
       - Communication health = leading indicator dashboards

7. Limitations and Future Work
   7.1 Small N (3 agents) — need validation at larger scale
   7.2 Single operator — multi-stakeholder dynamics differ
   7.3 Controlled experiments needed (A/B on decision quality)
   7.4 Bowen theory's own limitations (developed for human families)
   7.5 Risk of over-fitting: not every Bowen concept transfers
   7.6 Need for longitudinal data (months, not weeks)

8. Conclusion
   - Lead with: here are the failure rate reductions and the cost savings
   - Then: the theoretical depth explains why this works and predicts what else will work
   - Then: this requires cross-domain expertise that is rare
   - Practitioners can adopt individual patterns without buying the whole framework
```

### Note on Paper Structure

The outline above follows the standard academic structure (background → framework → case study → patterns → applications). But when presenting at Micron, the EXECUTIVE ORDER should be:

1. **Problem + cost** (§1 of paper, but front-loaded in any presentation)
2. **Results** (§4.4-4.5 — before/after metrics, not theory)
3. **The patterns that produced those results** (§5 — practical, implementable)
4. **Enterprise applications** (§6 — "here's how Micron uses this")
5. **Why it works** (§3 — the Bowen-CI framework, presented as the depth behind the patterns)
6. **Why I'm the right person** (implied throughout, stated once in conclusion)

The paper itself can be structured more traditionally, but any presentation or executive summary must lead with value and trail with theory.

---

## 5. Citations

### Collective Intelligence

1. Woolley, A. W., Chabris, C. F., Pentland, A., Hashmi, N., & Malone, T. W. (2010). Evidence for a collective intelligence factor in the performance of human groups. *Science*, 330(6004), 686-688. https://doi.org/10.1126/science.1193147

2. Malone, T. W., & Bernstein, M. S. (Eds.). (2015). *Handbook of Collective Intelligence*. MIT Press.

3. Du, Y., Li, S., Torralba, A., Tenenbaum, J. B., & Mordatch, I. (2024). Improving factuality and reasoning in language models through multi-agent debate. *ICML 2024*. https://arxiv.org/abs/2305.14325

4. Hong, S., Zhuge, M., Chen, J., Zheng, X., Cheng, Y., Zhang, C., ... & Wu, Y. (2024). MetaGPT: Meta programming for a multi-agent collaborative framework. *ICLR 2024*. https://arxiv.org/abs/2308.00352

5. Guo, T., Chen, X., Wang, Y., Chang, R., Pei, S., Chawla, N. V., ... & Zhang, X. (2024). Large language model based multi-agents: A survey of progress and challenges. *arXiv:2402.01680*. https://arxiv.org/abs/2402.01680

6. Li, G., Hammoud, H. A. A. K., Itani, H., Khizbullin, D., & Ghanem, B. (2024). More agents is all you need. *arXiv:2402.05120*. https://arxiv.org/abs/2402.05120

7. Zhang, C., Yang, K., Ma, S., Guo, J., Zhang, J., Wang, J., & Liu, Y. (2024). Building cooperative embodied agents modularly with large language models. *ICLR 2024*. https://arxiv.org/abs/2307.02485

8. Cemri, M., et al. (2025). Failure modes in multi-agent LLM systems: A taxonomy from 1,600 traces.
   **STATUS: UNVERIFIED — CRITICAL CITATION.** The 36.9% figure anchors the entire problem statement.
   **RESEARCH TASK:** Search Google Scholar, arXiv, Semantic Scholar for: "multi-agent LLM failure modes" OR "interagent misalignment taxonomy" by Cemri. If not found, find the best alternative citation for multi-agent failure rates. Patrick may have the original source — ask if search fails.

9. Mitsubishi Electric Research Laboratories. (2026). Adversarial argumentation frameworks outperform cooperative consensus in multi-agent decision-making.
   **STATUS: UNVERIFIED — IMPORTANT CITATION.** Supports adversarial > cooperative claim.
   **RESEARCH TASK:** Search MERL publications (merl.com/publications), arXiv for "adversarial argumentation" + "multi-agent" from Mitsubishi Electric / MERL. If not found under this name, search for the underlying claim: papers showing adversarial multi-agent debate outperforms cooperative consensus (Du et al. 2024 partially covers this, but a 2025-2026 paper would be stronger).

10. Park, P., Goldstein, S., O'Gara, A., Chen, M., & Hendrycks, D. (2024). AI deception: A survey of examples, risks, and potential solutions. *Patterns*, 5(1). https://doi.org/10.1016/j.patter.2023.100988

### Bowen Family Systems Theory

11. Bowen, M. (1978). *Family Therapy in Clinical Practice*. Jason Aronson.

12. Kerr, M. E., & Bowen, M. (1988). *Family Evaluation: An Approach Based on Bowen Theory*. W. W. Norton.

13. Friedman, E. H. (1991). *Generation to Generation: Family Process in Church and Synagogue*. Guilford Press.

14. Guerin, P. J., Fogarty, T. F., Fay, L. F., & Kautto, J. G. (1996). *Working with Relationship Triangles: The One-Two-Three of Psychotherapy*. Guilford Press.

15. Gilbert, R. M. (2004). *The Eight Concepts of Bowen Theory*. Leading Systems Press.

16. Papero, D. V. (1990). *Bowen Family Systems Theory*. Allyn & Bacon.

17. Titelman, P. (Ed.). (2014). *Differentiation of Self: Bowen Family Systems Theory Perspectives*. Routledge.

18. Skowron, E. A., & Friedlander, M. L. (1998). The Differentiation of Self Inventory: Development and initial validation. *Journal of Counseling Psychology*, 45(3), 235-246.

19. Knauth, D. G., Skowron, E. A., & Escobar, M. (2006). Effect of differentiation of self on adolescent risk behavior. *Nursing Research*, 55(5), 336-345.

### Psychology × AI

20. Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. *UIST 2023*. https://arxiv.org/abs/2304.03442

21. Shanahan, M., McDonell, K., & Reynolds, L. (2023). Role-play with large language models. *Nature*, 623, 493-498. https://doi.org/10.1038/s41586-023-06647-8

22. Serapio-García, G., Safdari, M., Crepy, C., Sun, L., Fitz, S., Romero, P., ... & Matarić, M. J. (2023). Personality traits in large language models. *arXiv:2307.00184*. https://arxiv.org/abs/2307.00184

23. Kosinski, M. (2024). Evaluating large language models in Theory of Mind tasks. *arXiv:2302.02083*. https://arxiv.org/abs/2302.02083

### Organizational / Systems Theory (bridge citations)

24. Senge, P. M. (1990). *The Fifth Discipline: The Art and Practice of the Learning Organization*. Doubleday.

25. Stacey, R. D. (2001). *Complex Responsive Processes in Organizations: Learning and Knowledge Creation*. Routledge.

26. Pentland, A. (2014). *Social Physics: How Social Networks Can Make Us Smarter*. Penguin.

---

## 6. Research Tasks Required

Before drafting, these need to be done:

1. **Verify citations 8 and 9** — Cemri et al. (2025) and Mitsubishi Electric (2026). Find exact publication details, DOIs, or confirm they're technical reports/preprints. These are the two most critical CI citations.

2. **Literature gap check** — Search for 2025-2026 papers specifically on:
   - Multi-agent memory architectures
   - Adversarial vs. cooperative multi-agent decision-making
   - Metacognitive agents / governance agents
   - Any paper that connects psychology to multi-agent AI

3. **Baseline data snapshot** — Before CI implementation, capture:
   - Spawn accuracy (from trust ledger): currently ~40% overall
   - Task duration distribution (from task events)
   - Patrick override rate (estimate from synthesis→action pipeline)
   - Number of cross-agent interactions: currently 0

4. **Micron context** — Research:
   - Does Micron currently use multi-agent AI systems?
   - What are the key decision-making challenges in semiconductor manufacturing that multi-agent CI could address?
   - Any published Micron AI/ML papers or talks?

5. **Controlled experiment design** — Design A/B protocol:
   - Week A: CI protocols active (cross-reads, signals, adversarial)
   - Week B: CI protocols off (agents operate independently)
   - Measure: spawn accuracy, task duration, decision quality, emergent insights
   - Need minimum 4 weeks of each for statistical significance with this small N

---

## 7. The Húrin System — Technical Context for Case Study

### Architecture
- 3 agents on MiniMax M2.5 (fast/cheap router)
- All complex work delegated to Claude Code Opus 4.6 via Agent SDK ($0 on Max plan)
- Agents communicate asynchronously via file-based shared memory (signal bus)
- Cron-scheduled runs: Huor weekly synthesis, Tuor briefings (paused), Beren 2x/week digest
- Task daemon: background execution, worktree isolation, PR output, session resume

### Agents
- **Huor** (Team Lead): GitHub polling every 15min, metrics computation, weekly synthesis (Opus), anomaly detection, auto-spawn pipeline. Posts to #team-lead and #tasks.
- **Tuor** (Co-Founder): 9 strategic lenses (product-vision, architecture, market-research, etc.), KB-aware analysis, action proposals with confidence gating. Posts to #co-founder.
- **Beren** (Chief of Staff): Meta-orchestrator, evaluates entire system, strategic digest 2x/week, surfaces recommendations + "uncomfortable questions." Posts to #chief-of-staff.

### Shared Infrastructure

**Knowledge Base** (`~/.openclaw/knowledge/`): 6 domains — domain, market, technical, strategy, self, users. Structured markdown + JSON files, indexed by `knowledge/index.md`.

**Trust Ledger** (`~/.openclaw/monitor/trust-ledger.json`): Tracks accuracy of spawn proposals by category. Schema:
```json
{
  "entries": [
    {"ts": "...", "task_id": "...", "category": "ci_fix", "proposed_by": "huor",
     "outcome": "correct|wrong|pending", "notes": "..."}
  ],
  "global_stats": {"accuracy": 0.40, "correct": 8, "total": 20, "pending": 3}
}
```
"Spawn accuracy" = `global_stats.correct / global_stats.total`. Currently ~40%.

**Spawn Policy Engine** (`~/.openclaw/knowledge/self/spawn-policy.json`): Per-category autonomy computed from trust ledger. Categories with >= 80% accuracy over 5+ proposals auto-graduate to `auto_spawn`. Categories with < 40% accuracy are `blocked`. Currently no categories qualify for auto-spawn.

**Telemetry** (`~/.openclaw/knowledge/self/telemetry.jsonl`): JSONL with entry types:
- `pr_review_latency`: hours from PR creation to merge/close
- `master_topics`: weekly commit topic distribution
- `compute_roi`: ratio of compute spent on merged vs. discarded tasks
- `attention_signal`: Discord thread engagement proxy

**Signal Bus** (`~/.openclaw/knowledge/shared/signals.jsonl`): Cross-agent communication. Schema per line:
```json
{"ts": "2026-03-10T09:15:00Z", "from": "huor", "to": "tuor",
 "type": "anomaly", "signal": "fdserver PR cycle time 3x baseline",
 "confidence": 0.87, "consumed": false, "source_artifact": "synthesis-2026-03-10",
 "influenced_decision": null}
```
Valid types: `anomaly`, `metric`, `priority_shift`, `architecture_insight`, `challenge`, `red_team`, `pre_mortem`, `calibration`, `process_correction`, `cross_correlation`, `lesson_learned`. Max 5 signals/agent/run. 14-day expiry.

**Episodic Memory** (`~/.openclaw/knowledge/shared/episodes.jsonl`): Task outcomes with lessons. Schema per line:
```json
{"ts": "2026-03-10T14:30:00Z", "task_id": "fd-142", "repo": "familydiagram",
 "outcome": "merged", "duration_hrs": 3.2, "spawned_by": "huor",
 "lessons": ["QML property bindings need null checks", "Scene requires mock Timeline"],
 "tags": ["qml", "testing"], "cross_agent_signals_consumed": ["signal-tuor-2026-03-09"]}
```
Written by task daemon on completion. CC extracts lessons from session transcript.

**Calibrations** (`~/.openclaw/knowledge/shared/calibrations.jsonl`): Adversarial challenge outcomes. Schema per line:
```json
{"ts": "2026-03-12T10:00:00Z", "challenger": "beren", "challenged": "tuor",
 "topic": "fdserver microservices split",
 "beren_position": "Monolith velocity advantage outweighs architecture concerns",
 "tuor_position": "Separation of concerns critical for maintainability",
 "patrick_decided": "agree_with_beren",
 "lesson": "Tuor over-weights elegance vs delivery speed at current team size",
 "category": "architecture"}
```
**Calibration interface:** Patrick writes entries manually (JSON append to file) or via CLI helper (`~/.openclaw/scripts/calibrate.sh`). This is intentionally low-tech — Patrick reviews agent outputs in Discord, decides who was right, and records the calibration. Expected frequency: 1-3 per week.

**Coordination State** (`~/.openclaw/knowledge/shared/state.json`): Alignment anchor. Schema:
```json
{"last_updated": "2026-03-10T09:00:00Z", "updated_by": "patrick",
 "sprint_focus": "btcopilot auth layer + fd issue backlog",
 "active_decisions": [{"id": "dec-001", "decision": "...", "status": "pending", "assigned_to": "tuor"}],
 "blocked_on": ["Patrick review of PR #142"],
 "patrick_last_said": "Focus on btcopilot MVP.",
 "do_not_touch": ["fdserver auth architecture"]}
```
Patrick-controlled fields: `sprint_focus`, `patrick_last_said`, `do_not_touch`. All agents read before every run.

### Metrics Operationalization

How each paper metric maps to actual data:

| Paper Metric | Data Source | Computation |
|---|---|---|
| **Spawn accuracy** | `trust-ledger.json` → `global_stats.accuracy` | correct / total proposals |
| **Task duration** | `task-events.jsonl` → `task_started` to `task_completed` timestamps | delta in hours |
| **Patrick override rate** | Calibrations where `patrick_decided != agree_with_proposer` | overrides / total calibrations |
| **Signal consumption rate** | `signals.jsonl` → count `consumed: true` / total | percentage |
| **Signal influence rate** | `signals.jsonl` → count `influenced_decision != null` / consumed | percentage |
| **Challenge accuracy** | `calibrations.jsonl` → per-agent `agree_with_challenger` / total challenges | percentage |
| **Differentiation score** | Synthesis/briefing text analysis → count explicit conflict-and-reason passages / conflicting signals received | ratio |
| **Cascade rate** | Count multi-agent reactive responses to single anomalies / total anomalies | ratio (from signals.jsonl + task-events) |
| **Communication health** | Per-agent signal consumption rate → min across agents | percentage |
| **Episode capture rate** | `episodes.jsonl` count / completed tasks in `task-events.jsonl` | percentage |
| **Cross-agent interactions (baseline)** | Currently 0 — no signal bus exists pre-CI | count from signals.jsonl |

### CI Dashboard

Self-contained HTML generated by `ci-dashboard.py`:
- SVG agent topology with directional flow arrows showing signal types + volume
- 8 Chart.js visualizations: signal flow (horizontal bar), signal types (doughnut), agent activity balance (radar), calibration accuracy (bar), episode outcomes (doughnut), repo distribution (bar), velocity trend (line), PR review latency (bar)
- 3 data tables: recent signals (timestamp, from, to, type, content, confidence, status), recent episodes (date, task, repo, outcome, duration, lessons, CI flag), calibration history (date, challenger, challenged, topic, winner, lesson)
- 4 KPI cards with color-coded targets: signals total, consumption rate (target > 80%), episodes captured, adversarial challenges
- Sprint focus banner from `state.json`
- Dark theme, responsive CSS grid, empty states for pre-data period

---

## 8. Writing Timeline

| Phase | When | Deliverable |
|-------|------|-------------|
| Outline + concept mapping | Done | This document |
| Literature verification | Week 1 | Verified citations + gap-fill |
| Baseline data capture | Week 1 | Pre-CI metrics snapshot |
| CI implementation | Week 1-2 | Signal bus, cross-reads, adversarial protocols live |
| Draft sections 1-3 (theory) | Week 3 | Introduction, background, framework |
| Collect CI operating data | Weeks 2-6 | Dashboard metrics accumulate |
| Draft section 4 (case study) | Week 5 | Before/after analysis |
| Draft section 5 (patterns) | Week 5 | Practitioner-oriented design patterns |
| Draft section 6 (enterprise) | Week 6 | Micron-relevant applications |
| Draft section 7 (limitations) | Week 6 | Honest limitations |
| Review + polish | Week 7 | Complete draft |
| Internal presentation prep | Week 8 | Micron-ready deck |

---

## 9. Key Questions to Resolve During Drafting

1. **Is Bowen the right psychological framework, or should we survey broader?** Other candidates: group dynamics (Bion, Tuckman), organizational psychology (Argyris double-loop learning), social identity theory. Bowen has the advantage of being Patrick's deep expertise AND mapping cleanly to small-group agent dynamics. But the paper should acknowledge alternatives.

2. **How rigorous can the case study be with N=3 agents?** This isn't a controlled experiment with statistical power. Frame it as: "demonstration of framework applicability" not "proof of superiority." The design patterns section generalizes beyond the specific case.

3. **What's the right balance of Bowen depth vs. accessibility?** Micron audience likely doesn't know Bowen. Need to explain enough to be credible without becoming a family therapy textbook. The mapping table is the anchor — always connect back to design decisions and metrics.

4. **Should we include a "negative result" section?** If some Bowen concepts don't transfer well (e.g., sibling position maps weakly to agent role assignment), being honest about that strengthens the paper's credibility.

5. **Patent/IP considerations?** If the Bowen-CI mapping constitutes novel IP, should it be filed as a patent or published openly? Discuss with Patrick before publishing externally.
