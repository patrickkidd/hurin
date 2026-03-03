# Co-Founder Briefing: wild-ideas
**Date:** 2026-03-02 23:06 AKST
**Session:** 8550eb98-381d-4048-be16-96954debca2e
**Turns:** 10 max

---

Now I have everything I need. Let me synthesize this into a brainstorming briefing.

---

**Feature Moonshots**

- **1. Pattern Intelligence Engine — "Your family has a pattern"**

  The killer feature nobody else has. After extraction, run a second LLM pass over the completed PDP that does cross-generational pattern analysis. The data model already captures exactly what you need: events with SARF variables (symptom, anxiety, relationship, functioning) tagged to specific people across 3+ generations. The matching logic in `f1_metrics.py` already does fuzzy entity resolution. Imagine: "We notice that anxiety increased for both your mother and grandmother around age 35, both during periods of marital distance. Your current anxiety spike at 33 follows a similar pattern." 

  **Prototype path:** Add a `generate_insights()` function alongside `extract_full()` in `pdp.py`. Takes the committed PDP, sends it to an LLM with a "pattern analyst" prompt. Returns 2-3 natural language insights. Display in a new "Insights" tab in LearnView. Weekend project — the hard part (extraction) is already done.

  **What makes this unlike anything else:** Every therapy app gives you coping tools. Every genealogy app gives you family trees. Nobody connects the two. Nobody says "here is the mathematical structure of your family's emotional patterns." This is Bowen theory made tangible.

- **2. Emotional Seismograph — temporal SARF visualization**

  LearnView already has `sarfGraphModel`, WCAG AA colors for each SARF variable (`symptomColor: "#e05555"`, `anxietyColor: "#40a060"`, etc.), and cluster/timeline infrastructure. But right now events are dots on a timeline. What if instead you rendered a multi-layer area chart — a landscape where you can literally see waves of anxiety propagate through the family system over decades? X-axis is time. Y-axis is intensity. Layers are family members, colored by SARF variable. When Mom's anxiety goes up in 1985 and Dad's functioning goes down in 1986 and the kid develops symptoms in 1987, you'd SEE the wave.

  **Prototype path:** The data is already in events with SARF variable shifts + dates. The cluster detection already groups events temporally. You'd need a Canvas element in QML (or use the existing graph infrastructure in LearnView's mini-graph) to render a stacked area chart. Each committed event with a SARF variable contributes a data point. The scene system's layer architecture could literally overlay this — one layer per family member's emotional trajectory.

  **Build on:** `LearnView.qml` graph properties (lines 37-100), `sarfGraphModel.events`, the existing cluster detection system.

- **3. Multiplayer Family Diagram — "Your family, their perspective"**

  The existing layer/view system in the scene (`emotionalunit.py`, the layer system in `scene.py`) already separates different perspectives on the same data. What if different family members each contributed their own version of events? Mom says the divorce was about Dad's drinking. Dad says it was about Mom's controlling behavior. The kid says they didn't notice anything. Each person gets a discussion, each discussion produces a PDP, and the diagram shows convergent data in bold and divergent data with conflict markers.

  **Prototype path:** The personal app already supports multiple discussions per diagram. Each discussion already produces a separate PDP. The `commit_pdp_items()` function in `schema.py` already handles dedup via ID mapping. You'd need: (a) a way to tag which discussion/person contributed each committed item, (b) a "conflict" visualization when two people describe the same event differently. The fuzzy matching in `f1_metrics.py` could identify "same event, different interpretation." This is F1 scoring, but between family members instead of AI vs GT.

  **Build on:** Multiple discussions per diagram, `f1_metrics.py` matching logic, the layer/view system.

---

**Business Model Experiments**

- **Give the software away. Sell the intelligence.**

  The personal app could be completely free — chat, extract, view your diagram. The monetization is the pattern analysis. "Your family diagram is free. Understanding what it means costs $9.99/month." This is the Spotify model: the music (data) is free, the algorithmic playlists (insights) are premium. You already have the AI infrastructure. The marginal cost of a second LLM call for insights is pennies.

- **Certification as a Service**

  The IRR study infrastructure (`f1_metrics.py`, the feedback/approval system, Cohen's/Fleiss' Kappa) is literally a clinical assessment platform. What if therapists paid $200/year to get "Bowen Theory Certified" through your platform? They code 5 synthetic discussions, the system measures their Kappa against expert GT, and they get a certificate. Revenue from therapist certification, not software licenses. The training app is 90% built for this — it already has synthetic discussions, per-statement coding, auditor feedback, and multi-coder comparison.

- **B2B licensing to therapy platforms**

  BetterHelp, Talkspace, etc. have millions of therapy transcripts and zero structured clinical data. Your extraction pipeline (`extract_full()` → SARF-coded PDP) could be an API they pay per-call for. They send a transcript, you return structured clinical data. The IP isn't the software — it's the SARF model, the extraction prompts (the ones in fdserver), and the validation pipeline. This is pure margin because your fixed costs are already paid.

- **Research data marketplace**

  The GT coding you're doing is the first structured Bowen theory dataset in existence. Academic researchers would pay for de-identified, IRR-validated family systems data. Not the software, not the AI — the data itself. Even 50 coded discussions would be a first-of-its-kind resource.

---

**Technology Wildcards**

- **Voice-first personal app**

  Skip the chat typing entirely. User opens app, talks about their family for 10 minutes, hits "Build my diagram." Whisper/Deepgram transcribes, `extract_full()` processes the transcript. The conversation flow prompt becomes unnecessary for the personal app — you're just extracting from a monologue. This dramatically lowers the barrier to entry. Talking about your family is natural. Typing about your family in a chat interface is weird. The entire `ask()` pipeline in `chat.py` could be bypassed for a voice-first mode that goes straight to `extract_full()` on transcribed text — you already have `import_text()` that does exactly this.

- **Fine-tune on your GT data**

  You have 4 coded discussions (target 5-8). That's a small but legitimate fine-tuning dataset for structured extraction. Instead of prompt engineering (which you're spending massive effort on), fine-tune a small model specifically for SARF extraction. The infrastructure is perfectly set up: `f1_metrics.py` gives you evaluation, `cumulative()` gives you training pairs (input: conversation, output: PDP). The `edited_extraction` field in Feedback is literally labeled training data. This is the endgame that makes the prompt engineering investment pay off exponentially.

- **What FamilyDiagram looks like built on an LLM from scratch**

  You wouldn't build a diagram editor. You'd build a conversational interface where the AI is the diagram. "Show me Mom's anxiety over time" → renders a chart. "What happened between Dad and Uncle Jim?" → narrative + relationship timeline. "What if Grandma hadn't cut off her sister?" → counterfactual simulation using the family system model. The structured data (PDP) would exist underneath, but the user would never see JSON or even a traditional UI. Just conversation and responsive visualizations. The `extract_full()` + pattern analysis + natural language generation pipeline is the seed of this.

- **10x compute, zero latency fantasy**

  Real-time extraction during speech. As you talk about your family, the diagram builds itself in front of you — people appear, relationship lines form, events stack on the timeline. When you mention "my parents got divorced when I was 7," a divorce event slides in, the pair bond splits, and anxiety indicators light up around the children. This would require streaming structured output from the LLM (Gemini's API supports streaming, but not structured streaming yet). The `_extract_and_validate` retry loop would need to become a streaming accumulator.

---

**The "What If We..." Section**

- **What if we abandoned the Pro app entirely and went all-in on Personal?**

  The Pro app is a Qt/QML desktop application — a complex, mature codebase with a scene system, views, layers, emotional units, property system, undo/redo. It serves clinicians who manually construct diagrams. The Personal app is a mobile-first chat interface where AI builds the diagram for you.

  These serve fundamentally different users with fundamentally different workflows. The Pro app needs manual control. The Personal app needs AI automation. Maintaining both means every architectural decision (like the PDP commit flow, the PairBond lifecycle, the diagram data format) has to satisfy two masters. Goal 3 on the MVP dashboard ("Open Personal-app-generated diagrams in the Pro app with correct layout") is a 2-3 week auto-arrange algorithm just to bridge the gap.

  **First week:** Fork the `schema.py` data model into "personal-schema" (simplified, AI-first) and "pro-schema" (full, editor-optimized). Strip SARF variables from the personal extraction prompt. Ship a web-based personal app (no Qt dependency) using the existing Flask API + a React frontend. The entire backend is already JSON-API ready — `discussions.py` returns JSON.

- **What if the product is the synthetic discussion generator, not the diagram tool?**

  The synthetic pipeline (`synthetic.py`) generates realistic family therapy conversations with configurable personas (attachment styles, traits like evasive/oversharing, specific presenting problems). This is a training simulator for therapists. There are ~600K licensed therapists in the US. How many of them have access to realistic practice conversations? Zero. BetterHelp charges $100/session for real clients. A practice conversation costs you cents.

  **First week:** Expose the synthetic generation pipeline as a standalone web app. Therapist logs in, selects a persona profile ("anxious parent with dismissive attachment, presenting problem: child's school refusal"), chats with the simulated client, gets scored on their Bowen theory application. The infrastructure exists: `ConversationSimulator`, persona generation, quality evaluation, coverage tracking. You'd need a frontend and a scoring rubric.

- **What if we open-sourced everything, including fdserver's prompts?**

  The decision log shows fdserver holds the "confidential IP" — the real extraction prompts. But the actual moat isn't the prompts (anyone can prompt-engineer). The moat is: (a) the SARF data model definition, (b) the GT coding methodology and data, (c) the evaluation infrastructure, and (d) domain expertise embedded in the persona system. Open-sourcing the prompts would attract academic collaborators, generate community prompt improvements, and establish FamilyDiagram as the standard platform for computational family systems. The Bowen theory community is small enough that being the open standard IS the business model.

  **First week:** Move fdserver prompts to btcopilot. Publish the SARF data model specification as a paper/blog post. Create a "contribute your family systems prompt" workflow. Set up a public F1 leaderboard — anyone can submit an extraction prompt and see how it scores against the GT benchmark.

---

**Cross-Pollination**

- **If Duolingo designed FamilyDiagram:** Gamified family knowledge. "You've identified 3 out of 5 triangles in your family — keep going!" Daily streaks for adding family events. Difficulty levels: Level 1 (immediate family), Level 2 (extended family), Level 3 (multigenerational patterns). Achievement badges: "Triangle Detective", "Three Generations Deep", "Pattern Breaker." The `DataPoint` categories in `synthetic.py` already define what "complete coverage" looks like — turn that checklist into a progress bar.

- **If Figma designed FamilyDiagram:** Multiplayer. Real-time collaboration. Your sister sees the same diagram and adds events from her perspective. Annotations and comments on specific people or events. "Hey, Dad wasn't actually that anxious in the 90s — you were too young to remember." Version history showing how the family narrative evolved. The existing layer/view system is literally a primitive version of Figma's pages.

- **If a game studio designed FamilyDiagram:** The family system as a simulation. Change one variable and watch the system respond. "What if your mother had maintained contact with her sister?" → simulate the cascade. Move the cutoff event to "distance" instead → watch how anxiety redistributes across the triangle. This would make Bowen theory visceral and experiential instead of academic. The SARF variable model (symptom/anxiety/relationship/functioning with up/down/same) is already a discrete simulation state space.

- **If Spotify designed FamilyDiagram:** "Your Family Wrapped." Year-end summary of family patterns. "Your most anxious month was March. Your strongest relationship was with Mom. You identified 12 family events this year, up from 0 last year." Weekly "relationship radar" — a push notification with one insight about your family system.

- **If fintech designed FamilyDiagram:** Emotional portfolio theory. Each relationship is an asset with a risk/return profile. Diversification = maintaining multiple non-triangulated relationships. Your "emotional balance sheet" shows where you're over-invested (fusion) and under-invested (cutoff). Rebalancing recommendations. This sounds absurd but it maps surprisingly well to Bowen theory's concept of differentiation.

---

**One Uncomfortable Question**

Patrick — I dug into the personal app's `PDPEventCard.qml` and found that it displays full SARF variables to consumers: "Symptom: Up", "Anxiety: Down", "Relationship: Conflict", "Functioning: Down" with clinical color coding. Meanwhile, the extraction pipeline asks Gemini to extract all of this simultaneously — people, events, pair bonds, AND four SARF variables per event — in a single prompt call, and Events F1 sits at 0.29.

The training app code is ~36K lines (22K Python + 14K templates). The personal app backend is ~5.7K lines. The training app's purpose is to validate the very SARF extraction that consumers see.

Here's the question: **Does a person chatting about their family on a phone need to see "Symptom: Up" and "Functioning: Down" on their events?** Clinical SARF coding is the heart of the Pro app and the training system — it's the research contribution, the certification basis, the entire academic moat. But for the personal app user, wouldn't "Here are the stressful events in your family, and here's who was affected" be enough? If you stripped SARF variables from the personal extraction prompt and told Gemini to focus only on people, events (kind + date + description), and pair bonds, your Events F1 would almost certainly jump — the model wouldn't be splitting its attention budget across 8 additional enum fields per event. You could ship a consumer product that works well at the simpler task while continuing to invest in SARF accuracy for the clinical platform. The two audiences have fundamentally different needs, but right now they're sharing a single extraction prompt that tries to serve both.

```proposed-actions
{
  "actions": [
    {
      "id": "wild-ideas-2026-03-02-1",
      "title": "Add pattern intelligence second-pass after extraction",
      "category": "ux",
      "effort": "small",
      "confidence": 0.80,
      "repo": "btcopilot",
      "plan": "1. Create btcopilot/personal/insights.py with generate_insights(pdp, conversation_history) function. 2. After extract_full() returns PDP, call generate_insights() with the committed + staged PDP. 3. Use gemini_text_sync() to send the full PDP as context with a pattern-analyst prompt asking for 2-3 cross-generational observations. 4. Return insights as a list of strings. 5. Add insights to the extract endpoint response JSON. 6. Display insights in a new section in LearnView.qml below the timeline.",
      "spawn_prompt": "Create a 'Pattern Intelligence' feature that generates natural-language insights about cross-generational family patterns after extraction.\n\n**Context:** The personal app extracts family data (people, events, pair_bonds with SARF variables) via `pdp.extract_full()` in `btcopilot/pdp.py`. After extraction, we want a second LLM pass that analyzes the extracted PDP for cross-generational patterns.\n\n**Step 1: Create `btcopilot/personal/insights.py`**\n```python\nasync def generate_insights(pdp: PDP, conversation_history: str) -> list[str]:\n```\n- Takes the complete PDP (people, events, pair_bonds) and the conversation text\n- Builds a prompt like: 'You are a family systems analyst trained in Bowen theory. Given this family data, identify 2-3 cross-generational patterns. Focus on: anxiety transmission across generations, relationship pattern repetition (triangles, cutoffs, fusion), and functioning shifts that correlate across family members. Be specific — name the people and events involved. Write in plain language a non-clinician would understand.'\n- Includes the PDP as structured context (use `asdict()` from schema)\n- Calls `gemini_text_sync()` (same as chat.py uses) with temperature 0.3\n- Parses response into a list of insight strings (split on numbered list or double newline)\n- Returns empty list on error (never block extraction)\n\n**Step 2: Add to extract endpoint**\nIn `btcopilot/personal/routes/discussions.py`, find the POST extract endpoint.\nAfter `extract_full()` succeeds, call `generate_insights()` with the resulting PDP.\nAdd `\"insights\": [...]` to the response JSON alongside existing PDP data.\n\n**Step 3: Wire into personal app**\nIn `familydiagram/pkdiagram/resources/qml/Personal/LearnView.qml`, add an 'Insights' section.\nThis can be a simple ColumnLayout with Text elements for each insight string, displayed below the timeline graph area. Use a Repeater over the insights array. Style with cardColor background, 14px font, 12px padding.\n\nThe PersonalApp Python bridge (look for the class that exposes data to QML) needs to store and expose the insights list from the extract response.\n\n**Acceptance criteria:**\n1. `uv run pytest btcopilot/tests/personal/ -k insights` passes (write a basic test)\n2. Extract endpoint returns `insights` field in response\n3. Insights are 2-3 sentences each, reference specific family members by name\n4. If insight generation fails, extraction still succeeds (insights = empty list)\n5. No changes to existing extraction logic or prompts",
      "success_metric": "Users see 2-3 natural language insights about their family patterns after each extraction"
    },
    {
      "id": "wild-ideas-2026-03-02-2",
      "title": "Create simplified personal-only extraction prompt experiment",
      "category": "velocity",
      "effort": "small",
      "confidence": 0.70,
      "repo": "btcopilot",
      "plan": "1. In btcopilot/personal/prompts.py, create DATA_EXTRACTION_PROMPT_SIMPLE that removes all SARF variable instructions (symptom, anxiety, relationship, functioning, relationshipTargets, relationshipTriangles). 2. Keep people, events (kind + date + description only), and pair_bonds. 3. Add a flag to extract_full() to use simplified prompt. 4. Run F1 comparison on disc 48: full prompt vs simplified prompt. 5. Document results. Do NOT change production behavior — this is an experiment.",
      "spawn_prompt": "Create an experimental simplified extraction prompt for the personal app that strips SARF clinical variables to test whether extraction accuracy improves when the LLM focuses on fewer fields.\n\n**Hypothesis:** The current extraction prompt asks Gemini to extract people, events (with 4 SARF variables + relationship targets + triangles per event), and pair bonds simultaneously. Events F1 is 0.29. If we remove SARF variables from the extraction task, the model can focus attention on correctly identifying events, dates, and person references — potentially boosting Events F1 above 0.4.\n\n**Step 1: Create simplified prompt**\nIn `btcopilot/personal/prompts.py`, add a new constant `DATA_EXTRACTION_PROMPT_SIMPLE` that is a copy of `DATA_EXTRACTION_PROMPT` with these removals:\n- All mentions of symptom, anxiety, relationship, functioning variable shifts\n- All mentions of relationshipTargets and relationshipTriangles\n- All SARF-related extraction rules and examples\n- Keep: people (id, name, gender, parents), events (id, kind, person, spouse, child, description, dateTime, dateCertainty, notes), pair_bonds (id, person_a, person_b)\n\nAlso create `DATA_EXTRACTION_EXAMPLES_SIMPLE` — same examples but with SARF fields removed from the JSON output examples.\n\n**Step 2: Add experiment flag to extract_full()**\nIn `btcopilot/pdp.py`, add an optional `simplified: bool = False` parameter to `extract_full()`. When True, use the simplified prompt and examples. When False, use existing behavior (no change to production).\n\n**Step 3: Create experiment script**\nCreate `btcopilot/experiments/test_simplified_extraction.py`:\n```python\n# Run extract_full() on discussion 48 with both prompts\n# Compare F1 scores using calculate_cumulative_f1()\n# Print side-by-side results\n```\n\n**Step 4: Update PDPDeltas schema handling**\nWhen `simplified=True`, the response schema should still use the same PDPDeltas dataclass, but SARF fields will come back as None/default. No schema change needed — just ensure validation doesn't reject events with null SARF fields.\n\n**IMPORTANT:** This is an experiment branch. Do NOT change the default extraction behavior. The `simplified` flag must default to False.\n\n**Acceptance criteria:**\n1. `DATA_EXTRACTION_PROMPT_SIMPLE` exists and contains zero mentions of symptom/anxiety/relationship/functioning\n2. `extract_full(simplified=True)` uses the simplified prompt\n3. `extract_full(simplified=False)` is identical to current behavior\n4. Experiment script can be run manually to compare F1\n5. No existing tests break",
      "success_metric": "Comparison data showing whether simplified extraction improves People/Events/PairBond F1 scores"
    }
  ]
}
```
