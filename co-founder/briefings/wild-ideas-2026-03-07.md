# Co-Founder Briefing: wild-ideas
**Date:** 2026-03-07 22:01 UTC
**Session:** 9266c9c6-9c8e-4b3f-911f-76a67abed5cb
**Turns:** 10 max

---

All three agents are back. I have deep context on the AI pipeline, personal app UI, data model, business model, and codebase structure. Time to synthesize.

---

**WILD IDEAS BRIEFING — 2026-03-07**

---

**Feature Moonshots**

- **"Family Weather Report" — Predictive SARF Forecasting.** You already compute cumulative S/A/F values in `sarfgraphmodel.py:_calculateCumulative()` and detect clusters via `clustermodel.py:detect()`. The data structure is *begging* for time-series prediction. Train a lightweight model (or just use Gemini) on the user's own SARF trajectory to predict: "Based on patterns in your family, the next 6 months after a major move typically involve anxiety-up and relationship-distance. Here's what happened last time." This turns the Learn tab from a rearview mirror into a windshield. No one else in family therapy tooling does predictive pattern matching on multi-generational data. The cluster detection endpoint (`POST /personal/diagrams/{id}/clusters`) already sends event data to the server — you'd add a "forecast" mode that looks at temporal patterns across clusters. **Prototype path:** Add a `forecast` field to the cluster detection response in `btcopilot/personal/routes/diagrams.py`, have Gemini analyze the cluster sequence and output a natural-language prediction. Display it in the PlanView stub (currently 484 bytes at `PlanView.qml`).

- **"The Genogram That Talks Back" — Voice-First Family Mapping.** Your `CONVERSATION_FLOW_PROMPT` is already structured as a clinical interview (7 phases, story-driven questioning). Your TTS is wired up in `personalappcontroller.py` (`_initTtsVoice`, `sayAtIndex`). The `fdserver/doc/TODO.md` mentions audio transcription via AssemblyAI. Combine them: user *speaks* their family story while walking, driving, or cooking. Real-time speech-to-text feeds the chat, AI responds with voice, extraction happens in background. Family therapy is an oral tradition — making the tool conversational-audio-first would be transformative. The key technical piece missing is STT integration — AssemblyAI is already a dependency in `pyproject.toml`. **Prototype path:** Add a microphone button to `DiscussView.qml` that streams audio to an AssemblyAI websocket, feeds transcribed text to the existing `sendStatement()` flow. Weekend-doable if you use AssemblyAI's real-time API.

- **"Shadow Diagram" — What Your Family Looks Like Through Someone Else's Eyes.** Your extraction system takes a *conversation* and builds a diagram. What if you ran the same family data through different persona lenses? Your synthetic client system (`synthetic.py`) already generates realistic personas with attachment styles (Secure, AnxiousPreoccupied, DismissiveAvoidant, FearfulAvoidant). Flip it: given a completed diagram, generate what *each family member* would say about the family. Then extract *their* version of the diagram. Show the user side-by-side: "Here's your diagram. Here's what your mother's diagram might look like." The differences reveal projection, triangulation, and blind spots — core Bowen concepts. **Prototype path:** New endpoint that takes `diagram_data`, generates a synthetic narrative from Person X's perspective using a modified `CONVERSATION_FLOW_PROMPT`, runs `extract_full()` on it, returns the delta between the two diagrams.

---

**Business Model Experiments**

- **Give the software away. Sell the interpretation.** Your Pro license is $19.99/mo. But the real value isn't the diagram tool — it's what the diagram *means*. What if FamilyDiagram were free, and the AI coach session was the paid product? A "session" could be a single conversation → extraction → cluster analysis → forecast. Price it like therapy sessions ($25-50 per AI session), not like SaaS ($20/mo). The `extract_full()` endpoint is the monetization gate. This reframes FamilyDiagram from "diagramming software" to "AI family systems consultation." The Professional tier stays for clinicians who need unlimited sessions + SARF data export.

- **Certification as a Service.** Your IRR calibration system, SARF coding workflow, and F1 metrics infrastructure are literally the first systematic measurement tools for Bowen theory competence (decision log `2025-12-09`). Sell certification: "Bowen Theory Practitioner, Verified by AI." Students code practice cases in the training app, their SARF coding is compared against expert ground truth, they get a score. Kappa > 0.6 = certified. You already have the entire pipeline: synthetic discussions, SARF editor, F1 metrics, IRR comparison. The Bowen Center, Georgetown, and independent training programs have no objective certification standard. You'd be creating a market.

- **White-label the extraction engine.** `pdp.extract_full()` is domain-agnostic in architecture — it takes conversation text, extracts structured entities via schema-guided LLM. The SARF overlay is Bowen-specific, but the Person/Event/PairBond extraction could serve genealogy apps, social work case management, legal family law documentation, immigration family history (proving family relationships for visas). License the engine, keep the Bowen theory layer as your differentiator. The `btcopilot.schema` public boundary (`test_isolation.py`) already enforces clean separation.

---

**Technology Wildcards**

- **LLM-native FamilyDiagram from scratch.** If you rebuilt today: no pickle files, no Scene/QGraphicsItem/QUndoStack. The entire diagram would be a structured JSON document that LLMs read and write directly. The UI would be a rendering layer over `DiagramData` (which you already have in `schema.py`). Chat, extraction, and diagram manipulation would all be LLM tool calls against the same document. The 658-line TODO.md of Qt bugs disappears. The `_addCommittedItemsToScene()` two-phase creation dance in `personalappcontroller.py` (lines 800+) disappears. You'd ship a web app in weeks. The question is whether the Pro app's investment (years of PyQt5 work) justifies maintaining that codebase, or whether the Personal app's architecture *is* the future and the Pro app becomes a "legacy viewer."

- **Real-time multi-user family mapping.** Imagine a family therapy session where the therapist and 3 family members each have the app open. Each person tells their version. The AI builds *one* diagram from *multiple* perspectives, flagging disagreements in real-time ("Mom says the divorce was 1998, Dad says 1997. Child says 'I was in 3rd grade.'"). Technically: WebSocket connections to a shared `DiagramData`, each user's statements feed into a shared discussion, extraction resolves conflicts via confidence scores (you already have `confidence: float` on Person, Event, and PairBond).

- **10x compute, zero latency version.** Run extraction *continuously* during chat (not just on button press). Every statement triggers a background `extract_full()` on the full conversation so far. The PDP updates in real-time as the user talks. The diagram literally builds itself during the conversation. The current architecture almost supports this — `extract_full()` clears PDP before re-extracting for idempotency (decision log `2026-02-24`). The blocker is cost/latency of Gemini calls per statement, but with 10x compute you'd just do it.

---

**The "What If We..." Section**

- **What if we stopped building a diagramming tool and built a family intelligence platform?** The diagram is a visualization of structured data. The *data* is the product. What if you exposed the SARF-coded family data as an API? Therapists, researchers, training programs, and the user themselves could query: "Show me all families where anxiety-up preceded relationship-distance within 6 months" across anonymized datasets. Week 1: Define the API schema (you have `PDPDeltas` and `DiagramData`). Build a read-only `/research/query` endpoint. Create an opt-in anonymization layer. Ship a simple query UI. The IRR-validated ground truth dataset you're building becomes the seed corpus.

- **What if the Personal app replaced the Pro app entirely?** The Pro app is PyQt5 desktop (massive codebase, platform-specific builds, C++ extensions, CMake, sysroot, provisioning). The Personal app is QML (mobile-compatible, simpler, AI-native). The Pro app's unique features: manual diagram editing, layers, pencil strokes, presentation mode, file management. But if extraction quality hits F1 > 0.8 (People are already at 0.909), manual diagram editing becomes a correction tool, not the primary workflow. Week 1: Audit which Pro features clinicians actually use (instrument the Pro app with Mixpanel — you already have `analytics.py`). Map each to a Personal app equivalent. Identify the 3 features that would make clinicians switch. Build one.

- **What if the AI became a co-therapist, not just a data collector?** Right now the chat collects family stories and the AI extracts data. But the SARF data + cluster detection + triangle detection already give the AI enough to make clinical observations. "I notice that every time your mother's anxiety goes up, your father's functioning goes down within 3 months. That's a classic reciprocal pattern." This crosses from tool to intelligence. The `CONVERSATION_FLOW_PROMPT` explicitly avoids clinical interpretation — but what if it didn't? What if there were a "Insights Mode" that the user could toggle? Week 1: Add an `INSIGHTS_PROMPT` that takes `diagram_data` + conversation and generates 3 Bowen-theory observations. Wire it to the PlanView stub. Test on synthetic discussions. The uncomfortable part: you're giving clinical insights without a license.

---

**Cross-Pollination**

- **If designed by Notion:** The diagram, timeline, events, and notes would all be blocks in a single document. Users could embed a diagram view inside their journal. Events would be database entries with properties (SARF values as columns). Filters and views would replace the search system. The 293-line TODO about search (`v1.5.1` features in `doc/TODO.md`) would be solved by making everything a queryable database.

- **If designed by a game studio:** Family history would be an exploration game. You'd start at yourself, "unlock" family members by answering questions about them. Each person has a "completeness score." Discovering a triangle or pattern awards an achievement. The timeline would be a playable narrative — scrub through time and watch relationship symbols animate. Your `Triangle.startPhase2Animation()` (jump-animate emphasis, repeat 3x) in `scene/triangle.py` is already gamified visualization.

- **If designed by Strava:** Social comparison of family patterns. "Your family's anxiety resilience score is in the top 20% of families who experienced a parental divorce." Anonymous benchmarking against aggregated SARF data. Shareable "family health reports" (like Strava year-in-review). This requires scale — but the synthetic discussion pipeline could generate the benchmark dataset.

- **Stolen from fintech — "Family Balance Sheet":** Present SARF data like a financial dashboard. Symptom = liabilities, Functioning = assets, Anxiety = volatility, Relationship = cash flow. "Your family's emotional net worth increased 15% this quarter." Sounds absurd — but quantifying emotional patterns is literally what SARF does. Making the metaphor explicit might make it accessible to non-clinicians.

---

**One Uncomfortable Question**

Your `PlanView.qml` is 484 bytes — a stub that says "Guidance, action items go here." The Learn tab shows *what happened*. The Discuss tab collects *the story*. But the Plan tab — the thing that would make someone *come back* to the app — is empty. You have cluster detection, SARF trajectories, triangle identification, and a conversation flow that collects 3+ generations of family data. You have everything needed to generate actionable guidance: "Based on your family pattern, here are 3 things to watch for" or "When you notice anxiety rising, here's what your family data shows typically follows."

**The uncomfortable question: Are you building a tool that collects family data, or a tool that helps families change? Because right now, FamilyDiagram is the world's most sophisticated family history *recorder* — but it doesn't tell anyone what to *do* with what they've recorded. The Plan tab is where the product becomes valuable enough that people pay for it, and it's been a stub since the beginning. Is the reason it's empty that you're not sure what should go there — or that you're avoiding the clinical-liability question of an AI giving family systems guidance?**

---

```proposed-actions
{
  "actions": [
    {
      "id": "wild-ideas-2026-03-07-1",
      "title": "Populate PlanView with AI-generated family insights",
      "category": "ux",
      "effort": "small",
      "confidence": 0.75,
      "repo": "btcopilot",
      "plan": "1. Add new endpoint POST /personal/diagrams/{id}/insights that takes diagram_data (people, events, pair_bonds, clusters) and generates 3 Bowen-theory-grounded observations using Gemini. 2. Use existing cluster data + SARF cumulative values as context. 3. Return structured JSON with title, description, supporting_events for each insight. 4. Wire PlanView.qml to call this endpoint and display results as cards.",
      "spawn_prompt": "Add a family insights generation feature to btcopilot.\n\n1. Create a new route in `btcopilot/personal/routes/diagrams.py`:\n   - `POST /personal/diagrams/<int:diagram_id>/insights`\n   - Reads diagram_data from the diagram\n   - Calls a new function `generate_insights(diagram_data)` in a new file `btcopilot/personal/insights.py`\n   - Returns JSON: `{\"insights\": [{\"title\": str, \"description\": str, \"supporting_events\": [int]}]}`\n\n2. `generate_insights()` should:\n   - Extract all shift events with SARF values\n   - Build a summary of people, relationships, and SARF patterns\n   - Call `gemini_text_sync()` from `btcopilot/llmutil.py` with a prompt asking for 3 observations grounded in Bowen family systems theory\n   - Parse the response into structured insights\n   - Temperature 0.3\n\n3. The prompt should:\n   - Receive the list of people (names, relationships) and events (dates, descriptions, SARF values)\n   - Ask for patterns: reciprocal relationships, multigenerational transmission, triangle patterns, symptom-event correlations\n   - Each insight must reference specific events by ID\n   - Keep language accessible (not clinical jargon)\n   - Include disclaimer: 'These observations are AI-generated pattern summaries, not clinical advice'\n\n4. Add a test in `tests/personal/test_insights.py` that mocks the LLM call and verifies the endpoint returns valid JSON structure.\n\nAcceptance criteria:\n- Endpoint returns 200 with 3 insights for a diagram with events\n- Each insight has title, description, and supporting_events list\n- Empty diagram returns empty insights list\n- Test passes",
      "success_metric": "POST /personal/diagrams/{id}/insights returns structured insights for a diagram with SARF-coded events"
    },
    {
      "id": "wild-ideas-2026-03-07-2",
      "title": "Add microphone button to DiscussView for voice input",
      "category": "ux",
      "effort": "small",
      "confidence": 0.6,
      "repo": "familydiagram",
      "plan": "1. Add a microphone toggle button next to the send button in DiscussView.qml. 2. Use Qt Multimedia QAudioRecorder to capture audio. 3. On stop, send audio to AssemblyAI real-time transcription endpoint (already a dependency). 4. Feed transcribed text into the existing sendStatement() flow. 5. Show transcription in the text input field before sending.",
      "spawn_prompt": "Add a voice input button to the personal app chat interface.\n\nFiles to modify:\n- `familydiagram/pkdiagram/resources/qml/Personal/DiscussView.qml` — add microphone button next to send button\n- `familydiagram/pkdiagram/personal/personalappcontroller.py` — add voice recording and transcription methods\n\n1. In DiscussView.qml:\n   - Add a microphone icon button (use existing PK.Button pattern) next to the send button in the input area\n   - Toggle state: idle (mic icon) → recording (red pulsing mic icon) → transcribing (spinner)\n   - On recording complete, call `personalApp.transcribeAudio(filePath)`\n   - On transcription complete, populate the text input field with result\n\n2. In personalappcontroller.py:\n   - Add `startRecording()` method using QMediaRecorder (from PyQt5.QtMultimedia)\n   - Add `stopRecording()` method that saves to temp file\n   - Add `transcribeAudio(filePath)` that sends audio to AssemblyAI REST API\n   - Use QNetworkAccessManager for the HTTP call (consistent with existing patterns)\n   - Emit signal `transcriptionReady(text)` when done\n   - Store AssemblyAI API key from server config or environment\n\nAcceptance criteria:\n- Microphone button visible in chat input area\n- Tapping starts/stops recording\n- Audio is transcribed and placed in text field\n- User can edit before sending\n- Works on iOS (QMediaRecorder is cross-platform in Qt 5.15)",
      "success_metric": "User can tap mic, speak, see transcription in text field, and send as a chat statement"
    }
  ]
}
```
