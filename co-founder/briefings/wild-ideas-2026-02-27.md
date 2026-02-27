# Co-Founder Briefing: wild-ideas
**Date:** 2026-02-27 10:14 AKST
**Session:** 777316e4-3471-4b17-9880-93dde8d83336
**Turns:** 10 max

---

Now I have a thorough understanding of the entire system. Let me synthesize the wild ideas briefing.

---

Alright Patrick. I spent six turns reading through the codebase — prompts, schema, extraction pipeline, cluster detection, the SARF graph, the Pro app copilot, the conversation flow system, the training app, and your decision log. Here's what I found and where my brain went.

---

**Feature Moonshots**

**1. "Family System Simulator" — What-If Time Travel for Emotional Process**

You already have the SARF cumulative graph model (`sarfgraphmodel.py`), event clusters with narrative arcs, and a conversation flow prompt that understands Bowen theory deeply. What if users could ask: *"What would have happened if my parents hadn't divorced in 1995?"*

The system would: remove the divorce event and all downstream events tagged with that cluster → re-run cluster detection on remaining events → use the LLM to generate *hypothetical* SARF trajectories based on the family system's pre-divorce dynamics → render a "ghost" cumulative SARF graph overlay showing the alternate timeline alongside the real one.

**To prototype:** You already have `detect_clusters()` in `clusters.py` and the SARF graph in `LearnView.qml` with its cumulative sum logic. Add a new Gemini call: given the family system state at time T, the event being removed, and Bowen theory principles, generate hypothetical SARF shifts for the next N years. Render as a dashed-line overlay on the existing Canvas graph. The `SARFGraphModel` already computes cumulative sums — add a parallel `hypotheticalEvents` list. **Weekend-doable** for a hardcoded single-event removal. Full interactive version: 2-3 weeks.

This doesn't exist in any family therapy tool. It makes Bowen theory *visceral* — you can see the counterfactual your client has been carrying in their head.

**2. "Family Genome" — Cross-Generation Pattern DNA**

You have 12 relationship types in `emotions.py` (Conflict, Distance, Fusion, Cutoff, Projection, etc.), multigenerational data in the schema (grandparents via `Person.parents`), and the triangle detection system. What if the system could compute a "family pattern fingerprint" — a visual signature showing which emotional processes recur across generations?

The insight: your `ClusterPattern` enum already identifies patterns like `anxiety_cascade` and `triangle_activation`. Run cluster detection independently on each generation's events, then use an LLM to identify cross-generational echoes: "Your grandmother's cutoff pattern with her sister mirrors your mother's distance from her brother, which echoes your current distance from your spouse."

**To prototype:** You have `DiagramData.people` with `parents` links. Walk the generational tree, group events by generation, run `detect_clusters()` per generation, then add a new Gemini call comparing cluster patterns across generations. Return a `FamilyGenome` dataclass with `RecurringPattern` entries. Render in `PlanView.qml` (currently a placeholder). The infrastructure is all there — it's a new prompt + a new dataclass + filling in that empty PlanView.

**3. "Live Differentiation Score" — Real-Time Functioning Feedback During Conversation**

The conversation flow prompt (`CONVERSATION_FLOW_PROMPT`) already tracks 7 phases and has a "required data checklist." The SARF model's `F (Functioning)` is defined as "differentiation of self — ability to balance emotion and intellect." What if, during the conversation itself, the system computed a *live differentiation score* based on how the user talks about their family?

Indicators: Does the user use "I" statements vs. blame language? Do they describe their own position or only others'? Can they describe family patterns without getting emotionally flooded? Do they track factual details (dates, sequences) or speak in vague generalizations?

**To prototype:** Add a small secondary Gemini call after each `chat.ask()` in `chat.py`. Input: the last 3-5 turns. Output: a structured `DifferentiationSignal` with scores for self-reference, emotional reactivity, factual precision, and pattern awareness. Show as a subtle meter in `DiscussView.qml` (or just log it for now). This is a publishable innovation — no existing tool measures differentiation in real-time conversation.

---

**Business Model Experiments**

**What if the software were free?**

The training app at `training/routes/` already has an auditing workflow, GT coding, IRR study infrastructure, and F1 metrics. The *real* product might not be the Personal app — it might be the **training and certification platform**. Give away the Personal app (it's the data collection flywheel), charge for:
- **SARF Certification courses** using the synthetic client system (`SyntheticPersona` model, discussion generation) — students practice on AI clients, get scored on F1 against GT
- **Continuing Education credits** — the IRR study infrastructure (`training/irr/`) becomes a formal assessment platform
- **Institutional licenses** for training programs — Bowen Center, Georgetown, family therapy graduate programs

The conversational flow evals (decision log 2025-12-09) already plan to measure therapist skill using the same rubric as AI. This is a B2B SaaS for clinical education, not a consumer therapy app.

**The Bowen Theory API**

You have the only structured, machine-readable encoding of Bowen theory constructs — 12 relationship types, 4 SARF variables, 6 cluster patterns, triangle detection, multigenerational linking. No one else has this. What if you licensed the *data model and extraction pipeline* to other therapy platforms? EHR systems, other therapy apps, research institutions.

The extraction pipeline (`pdp.py:extract_full()`) is prompt-driven and model-agnostic (you already switched from delta-by-delta to single-prompt; the LLM is a swappable component). The schema (`schema.py`) is a clean dataclass hierarchy. Package it as an API: send transcript text, get structured SARF-annotated family system data back.

**Unconventional monetization: "Family System Report" one-time purchase**

After a user completes a conversation in the Personal app, generate a beautiful PDF report: genogram visualization, SARF timeline, cluster narrative summaries, cross-generational patterns, and a plain-language "what your family system looks like" explanation. Charge $29 per report. The content is 100% AI-generated from data you already have. No subscription needed. The cluster `summary` and `pattern` fields in `clusters.py` are already generating narrative text. Add a report-generation prompt and a PDF renderer.

---

**Technology Wildcards**

**FamilyDiagram built on an LLM from scratch**

If you started fresh with an LLM as the *primary interface*, you wouldn't have a diagram canvas at all. You'd have:
- A conversational interface (you already have this — `DiscussView`)
- An AI that *constructs* the diagram programmatically (you already have this — `extract_full()` + `commit_pdp_items()`)
- A *narrated* diagram — the AI walks you through the genogram, highlighting patterns as it speaks, like a guided tour of your family system

The key insight: the Pro app's manual diagram drawing (`scene.py`, `person.py`, `emotions.py` — thousands of lines of QPainterPath code) is legacy from a pre-LLM world. The Personal app is already the future architecture. The Pro app could eventually become a *read-only viewer* with the LLM as the authoring tool.

**Voice-first family interviews**

The Personal app already has text-to-speech (`test_tts.py`). What if it had speech-to-text? A voice conversation with the AI coach, hands-free, feels like an actual therapy session. The conversation flow prompt is already written for natural dialogue. Whisper API → transcript → `chat.ask()` → TTS response. The extraction happens on "Build my diagram" as designed. This transforms the app from a chat interface to an *experience*.

**10x compute, zero latency**

You'd run extraction *continuously* — every turn updates the diagram in real-time (you actually tried this with delta-by-delta and it failed at 0.09 Events F1 — but with faster, cheaper models and the full conversation context, it could work). You'd render the genogram animated in real-time as the conversation progresses — people appearing, relationship lines drawing themselves, events lighting up on the timeline. It would feel like watching your family system *come alive*.

---

**The "What If We..." Section**

**What if we made it multiplayer?**

FamilyDiagram currently treats the family system from one person's perspective. What if two family members — say, two siblings — could each do their own conversation in the Personal app, and the system *merged* their two PDPs into one diagram, showing where they agree and disagree about family events?

`DiagramData.pdp` uses negative IDs for staging. Each user's extraction could use a different negative-ID range. The matching logic in `f1_metrics.py` (fuzzy name matching, structural event matching) could be repurposed to detect overlapping entities across users. Conflicts get flagged: "Your sister remembers your parents' divorce in 1998; you said 1997."

**First week:** (1) Add a `perspective_id` field to PDP items, (2) run F1 matching between two users' PDPs to identify overlaps, (3) build a "merge view" that shows shared entities as solid, conflicting entities as dashed, (4) generate an LLM summary of the discrepancies. The technical primitives already exist — it's new plumbing.

**What if we pivoted to research infrastructure?**

The training app's GT coding workflow, F1 metrics, IRR kappa computation, synthetic client generation, and SARF annotation pipeline is — accidentally — a complete *research infrastructure* for computational family therapy. No academic lab has this.

**First week:** (1) Write a landing page targeting family therapy researchers, (2) package the SARF coding workflow as a standalone research tool, (3) create a "demo dataset" from the synthetic discussions with GT annotations, (4) submit to a family therapy journal or conference as a methods paper. Patrick, you already have 4 coded discussions, a published-quality SARF data model, and IRR study infrastructure. The paper practically writes itself.

**What if the AI coached the clinician in real-time during a real session?**

The Pro app's BT Copilot (`engine.py`) already does RAG over Bowen Theory literature with timeline data. What if it ran *during* a live therapy session? The clinician records the session (with consent), the transcript feeds into `extract_full()` in real-time, and the BT Copilot suggests: "The client just described a triangle activation. Consider asking about the third person's position."

**First week:** (1) Hook Whisper API to a "session mode" in the Pro app, (2) run `extract_full()` every 5 minutes on the growing transcript, (3) feed the latest PDP + transcript into the BT Copilot with a "coaching suggestions" prompt, (4) display suggestions in the Copilot sidebar. The scary part: this could be more useful than the consumer app.

---

**Cross-Pollination**

**If Notion designed FamilyDiagram:** The diagram would be a *database* with views. People table, Events table, Relationships table — with linked records. The genogram would be one "view" of the data, the timeline another, clusters another. Users could create custom views, filters, and formulas. Your `DiagramData` is already structured this way (lists of people/events/pair_bonds). The Pro app's `Scene` is just one rendering of that data.

**If Figma designed it:** Real-time collaboration. Multiple clinicians annotating the same diagram simultaneously, with cursors visible. Comments pinned to specific events or relationships. A "history" slider showing how the diagram evolved over time (your Layer system in `layer.py` already supports alternate visual states — extend it to temporal snapshots). Version control for diagrams.

**If a game studio designed it:** The SARF graph becomes a *heartbeat monitor* with dramatic visual feedback. When anxiety cascades, the screen subtly pulses red. Cluster arcs have sound design — tension builds, peaks, resolves. The "Family Genome" cross-generational patterns render as an interactive skill tree. Users *level up* their differentiation score. Achievements: "Identified your first triangle." "Connected a symptom to a nodal event." Sounds absurd — but gamification of self-awareness is literally what meditation apps did.

**If fintech designed it:** "Family System Risk Score" — like a credit score but for emotional process. The SARF cumulative graph already computes running sums. Normalize them. Show a single number: how much unresolved anxiety is in the system right now? Track it over time. People understand dashboards and scores. Insurance companies would *love* an objective family therapy outcome metric.

---

**One Uncomfortable Question**

Patrick — I read `clusters.py`. The entire cluster detection system sends your family's private events (descriptions, dates, SARF annotations) to Google Gemini's API. The extraction system in `pdp.py` sends full conversation transcripts — intimate family histories — to Gemini. The chat in `chat.py` sends every message to Gemini. The Pro copilot sends to OpenAI.

Your `prompts.py` has `FDSERVER_PROMPTS_PATH` to protect your *prompts* as IP. But the actual sensitive data — the family stories, the relationship dynamics, the symptoms, the triangle patterns — all flows through third-party APIs with no local processing option.

**Have you thought about what happens when a therapist asks "where does my patient's data go?" and the honest answer is "Google and OpenAI"?**

The SARF data model is *clinical* data. Therapists have HIPAA obligations. The training app stores `Feedback.edited_extraction` — expert-coded clinical assessments — in a database that routes through Gemini for F1 analysis. The certification and training platform ideas above require handling student clinical data.

The uncomfortable version of this question: **Is FamilyDiagram's real competitive moat the Bowen theory data model and extraction pipeline — or is it the clinical data that flows through it?** Because if it's the data, you have a privacy problem that no terms-of-service checkbox can fix. And if it's the model, you should be able to run it locally.

The weekend project that might matter most: swap Gemini for a local model (Llama 3.3 on your M4 Mac Mini, or Ollama) for extraction, even at lower quality. Not because it's better — because "your data never leaves your device" is the one sentence that gets a therapist to trust software with their patients' stories. And you have 16GB of RAM and an M4 — you're literally sitting on the hardware.

---

```proposed-actions
{
  "actions": [
    {
      "id": "wild-ideas-2026-02-27-1",
      "title": "Populate PlanView with cross-generational pattern summary",
      "category": "ux",
      "effort": "small",
      "confidence": 0.7,
      "repo": "btcopilot",
      "plan": "1. Add a new endpoint POST /personal/diagrams/{id}/patterns that takes committed people+events, groups by generation using Person.parents links, and calls Gemini with a prompt asking for cross-generational SARF pattern echoes. 2. Return a PatternSummary dataclass with recurring_patterns list. 3. In familydiagram, add a PatternModel that calls this endpoint. 4. Replace PlanView.qml placeholder with a simple list of pattern cards. This fills the empty 'Plan' tab with genuinely useful clinical content.",
      "spawn_prompt": "Add a cross-generational pattern detection feature to fill the empty PlanView tab.\n\nBackend (btcopilot):\n1. Create btcopilot/btcopilot/personal/patterns.py with:\n   - A PATTERN_PROMPT that asks Gemini to identify recurring SARF patterns across generations\n   - A PatternSummary dataclass with fields: patterns: list[Pattern] where Pattern has title, description, generation_1_events: list[int], generation_2_events: list[int], sarf_variable: str\n   - A detect_patterns(diagram_data: DiagramData) function that groups events by generation using Person.parents links, calls gemini_structured_sync with the prompt\n2. Add endpoint POST /personal/diagrams/<int:diagram_id>/patterns in btcopilot/btcopilot/personal/routes/diagrams.py\n\nFrontend (familydiagram):\n3. Create familydiagram/pkdiagram/personal/patternmodel.py - QObject that calls the patterns endpoint, stores results\n4. Update PlanView.qml to show pattern cards instead of placeholder text\n5. Wire patternModel into PersonalAppController\n\nKey files to read first:\n- btcopilot/btcopilot/personal/clusters.py (pattern for Gemini structured calls)\n- btcopilot/btcopilot/schema.py (DiagramData, Person.parents)\n- familydiagram/pkdiagram/resources/qml/Personal/PlanView.qml (currently placeholder)\n- familydiagram/pkdiagram/personal/clustermodel.py (pattern for frontend model)\n\nSuccess criteria: PlanView tab shows AI-generated cross-generational pattern insights when user has committed events across 2+ generations. Falls back to helpful message when insufficient data.",
      "success_metric": "PlanView shows cross-generational pattern cards from Gemini analysis"
    }
  ]
}
```
