# Co-Founder Briefing: product-vision
**Date:** 2026-03-08 00:25 UTC
**Session:** a586737b-5094-4409-b7ec-d84db6ae71a2
**Turns:** 10 max

---

**PRODUCT VISION BRIEFING — 2026-03-08**

---

**User Experience Check: A Therapist's First 5 Minutes**

Login → AccountDialog.qml (shared with Pro app, includes license/purchase flows a personal user doesn't need). Auto-creates a diagram + discussion. Lands on Discuss tab with "What's on your mind?" (`util.py:574`). No onboarding, no explanation of what the app does or what the three tabs mean. The conversation prompt (`prompts.py:13-58`) is excellent — warm, story-driven, avoids therapist clichés. But the user has zero context that chatting will eventually become a diagram. The extract button (top-right, `PersonalContainer.qml:231-276`) is a cryptic down-arrow icon with no label or tooltip. A therapist would chat, enjoy the conversation, and never discover extraction exists. The PDP sheet (`PDPSheet.qml`) uses accept/reject semantics that assume you understand what "pending diagram proposals" means. **The core loop — chat → extract → review → learn — is invisible to first-time users.**

**Feature Prioritization**

MVP Dashboard (`MVP_DASHBOARD.md`) is correctly focused: Goal 1 (extraction quality) → Goal 2 (human beta) → Goal 3 (Pro viewing). But Goal 2 has only 2 tasks (T3-7 and T8-1), and T8-1 is literally "beta test with 1 human." There's no onboarding task anywhere. The Learn tab is sophisticated — SARF graph, cluster detection, zoom/pan, event editing (`LearnView.qml`, 800+ lines) — but a new user with 0 events sees... nothing. The Plan tab is a 25-line stub (`PlanView.qml`). **Cut Plan from MVP entirely** — showing a dead tab is worse than not showing it. Three tabs with one empty creates the impression of incomplete software.

- Must-have for MVP: onboarding hint on Discuss tab explaining the flow, label on extract button, empty-state on Learn tab explaining what will appear
- Cut: Plan tab (hide it), voice settings (PR #118 is premature), Pattern Intelligence UI (PR #88)
- The one killer feature: **the extraction itself.** "Tell your family story, get a diagram" — that's the pitch. Everything else is secondary to making that loop feel magical

**Product-Market Fit Signals**

The conversation prompt assumes users will talk for 25+ statements before extracting — enough for a full 3-generation genogram. But therapists are time-constrained. The decision log (`2026-02-24`) shows single-prompt extraction was chosen because delta-by-delta had terrible F1 (0.099 events). What if a therapist only has 5 minutes? There's no "quick start" mode. The app assumes long-form storytelling but hasn't validated whether therapists will actually do that on a phone. **Validate this with T8-1 — specifically track: how many statements before the user gets bored or confused, and whether they find the extract button.**

**Competitive Angle**

Paper genograms take hours. GenoPro is desktop-only, manual entry, no AI. FamilyDiagram's advantage is conversation-to-diagram — genuinely novel. But the differentiation only works if extraction quality is good enough that the diagram feels like magic, not like a homework assignment of correcting AI mistakes. People F1 at 0.72, Events at 0.29 (`decisions/log.md:64-72`) — people extraction feels magical, event extraction still requires heavy correction. **Ship with people-only extraction visible and events collapsed/hidden until F1 > 0.5.**

**One Uncomfortable Question**

The Help view is listed as broken in TODO.md (line 15: "Help view is broken"). The Settings drawer has "Help & Support" (`PersonalContainer.qml:806`) that opens a `SettingsPage` — but it's a generic shell with no actual help content. You're about to hand this to a beta tester (T8-1) with no working help, no onboarding, a cryptic extract button, and an empty Plan tab. **Are you building for the therapist who will use this in 5 minutes, or for yourself who already understands every concept? Because right now, the app is optimized for someone who already knows what extraction, PDP, SARF, and clusters mean — and that's approximately 1 person.**

```proposed-actions
{
  "actions": [
    {
      "id": "product-vision-2026-03-08-1",
      "title": "Hide Plan tab until it has content",
      "category": "ux",
      "effort": "trivial",
      "confidence": 0.95,
      "repo": "familydiagram",
      "plan": "1. In PersonalContainer.qml, remove 'Plan' from the tab bar Repeater model. 2. Remove the PlanView from the StackLayout. 3. Keep PlanView.qml file intact for future use. 4. Adjust tab bar width calculation (now /2 instead of /3).",
      "spawn_prompt": "Hide the Plan tab from the personal app UI — it's a stub that shows 'Guidance, action items go here' and makes the app feel unfinished.\n\nFile: `familydiagram/pkdiagram/resources/qml/Personal/PersonalContainer.qml`\n\nChanges:\n1. In the StackLayout (id: stack, ~line 305), remove the `Personal.PlanView` block (lines ~327-331)\n2. In the tab bar Repeater (~line 357), change the model from `[\"Discuss\", \"Learn\", \"Plan\"]` to `[\"Discuss\", \"Learn\"]`\n3. In the tab bar item width calculation (~line 360), change `root.width / 3` to `root.width / 2`\n4. Remove the static 'Plan' title text in the header (~line 195-202, the block with `visible: tabBar.currentIndex === 2`)\n5. Remove `property var planView: planView` from the root properties (~line 23)\n\nDo NOT delete PlanView.qml — just disconnect it from the UI.\n\nAcceptance criteria:\n- App shows only Discuss and Learn tabs, evenly split\n- No references to planView cause runtime errors (search for planView usage in other QML files)\n- Header shows correct title for each tab",
      "success_metric": "Personal app shows 2 tabs (Discuss, Learn) with no empty stub visible"
    },
    {
      "id": "product-vision-2026-03-08-2",
      "title": "Add label to extract button for discoverability",
      "category": "ux",
      "effort": "trivial",
      "confidence": 0.9,
      "repo": "familydiagram",
      "plan": "1. In PersonalContainer.qml, replace the extract button's canvas-drawn icon with a text label 'Build Diagram' inside a rounded rectangle. 2. Keep the same position (top-right of header on Discuss tab). 3. Widen the button to fit the text.",
      "spawn_prompt": "Replace the cryptic extract button icon with a text label for better discoverability.\n\nFile: `familydiagram/pkdiagram/resources/qml/Personal/PersonalContainer.qml`\n\nThe extract button is at ~line 231-276 (id: extractButton). It's a 28x28 circle with a Canvas-drawn down-arrow icon. New users have no idea what it does.\n\nChanges:\n1. Replace the extractButton Rectangle (~lines 231-276) with a wider pill-shaped button:\n   - width: auto-sized to text + padding (use `extractLabel.implicitWidth + 20`)\n   - height: 32\n   - radius: 16\n   - Same color: `util.IS_UI_DARK_MODE ? \"#4495F7\" : \"#007AFF\"`\n   - Remove the Canvas element entirely\n   - Add a Text element (id: extractLabel) with text: \"Build Diagram\", color: \"white\", font.pixelSize: 13, font.weight: Font.Medium\n   - Keep the same anchors (right side of header, verticalCenter)\n   - Keep the same MouseArea + onClicked: personalApp.extractFull()\n   - Keep the same visible: tabBar.currentIndex === 0\n   - Keep objectName: \"extractButton\"\n\n2. Adjust pdpBadge anchoring — it anchors to `extractButton.left`, so it should still work with the wider button\n\nAcceptance criteria:\n- 'Build Diagram' text button visible on Discuss tab header, right side\n- Tapping it calls personalApp.extractFull() (same as before)\n- PDP badge still appears correctly to the left of the button\n- Button is readable on both light and dark mode",
      "success_metric": "Extract button shows 'Build Diagram' text instead of cryptic icon"
    }
  ]
}
```
