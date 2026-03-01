# Co-Founder Briefing: market-research
**Date:** 2026-02-28 19:05 AKST
**Session:** 9d743d33-f96b-412d-8f51-d21785b9e765
**Turns:** 10 max

---

Now I have enough data to synthesize a comprehensive market intelligence briefing. Let me compile everything.

---

**Market Intelligence Briefing — FamilyDiagram**
*2026-02-28 | Co-Founder: Market Research*

---

**Competitive Landscape**

The genogram software market is fragmented, underfunded, and stagnant. Here's who you're up against:

- **GenoPro** ($2/mo for GenoProX, legacy desktop) — The incumbent. Windows-only for the original, GenoProX now cross-platform. Rich symbol library, report generation, error checking. But: no clinical data model beyond genealogy, no AI, no cloud collaboration (until GenoProX), and an interface that looks like it was designed in 2005. Wikipedia notes it was originally released in 1998. It occupies the space through sheer inertia — it's what everyone learned in grad school. [Source](https://genopro.com/)

- **Genogram Analytics** (~$50-100 range, Mac+PC) — Closest to a clinical tool. Has heritage/ethnicity inheritance, timeline snapshots, triangle relationships, and predefined clinical attributes (medical, psychological). Added cloud collaboration in 2025. Used by LCSWs, MFTs, psychologists. Weakness: still manual data entry, no AI, no theoretical framework beyond standard genogram symbols. [Source](http://www.genogramanalytics.com/)

- **Qwoach/EasyGenogram** ($29/mo, web) — Coaching-first platform with genogram as a feature. ClarityTrack system claims to "uncover toxic patterns" from genograms. 60+ relationship types, drag-and-drop, collaborative editing. It's a coaching practice management tool (scheduling, billing, contracts) that happens to have genograms. Genogram is a feature, not the product. [Source](https://qwoach.com/tools/genogram)

- **GenoConnect** (pricing unclear, web/API) — The interesting new entrant. Data-driven genograms from structured data, works as a plug-in to other apps. Emotional/functional layers, dynamic redraw, GEDCOM support. Positioned for organizations rather than individual practitioners. More infrastructure than product. [Source](https://genogramtools.com/)

- **General diagramming tools** (Creately, Miro, Lucidchart) — Offer genogram templates as one of 500 template types. No clinical intelligence. These compete on "good enough" convenience for students and one-off use.

- **Practice management platforms** (SimplePractice $49-99/mo, Ensora/TheraNest) — Own the therapist's daily workflow: scheduling, billing, notes, telehealth. Their genogram capabilities are basic drag-and-drop at best. They compete by being "one more tab you don't need to open." [Source](https://www.simplepractice.com/pricing/compare-plans/)

**Where FamilyDiagram sits:** You are categorically different from everything above. None of these tools have: (a) a clinical data model grounded in a specific theoretical framework, (b) AI extraction from natural language, (c) a validation pipeline with F1 metrics, or (d) a timeline that tracks variable shifts over time. The competition is drawing boxes and lines. You are building a clinical assessment system. This is both your advantage and your risk — you're in a category of one, which means you either *create* the category or you struggle to explain what you are.

**Tech stack comparison:** You are over-built relative to the competition and under-built relative to your ambition. GenoPro is a C++ desktop app. Genogram Analytics is a Java app. Qwoach is a Rails/React SaaS. You have Flask + PostgreSQL + Celery + Redis + ChromaDB + PyQt5 + QML + Gemini + Stripe — a stack built for a VC-backed team of 10, being run by one person with an agent swarm. The architecture is *correct* — it's what you'll need at scale — but the gap between what you've built and what the competition has is also the gap between your costs and theirs.

---

**AI + Therapy Trends**

The AI-in-therapy space is heating up fast, but it's concentrated in one area: **documentation**.

- **AI note-taking is the beachhead.** Upheal (free-$39/mo), SimplePractice AI Note Taker ($35/mo add-on), Mentalyc, SupaNote — the entire first wave of AI therapy tools is about turning session recordings into progress notes. 83% of clinicians who use SimplePractice's Note Taker report saving ~5 hours/week. This is where the money is flowing because the ROI is immediate and the risk is low (notes aren't patient-facing). [Source](https://www.upheal.io/)

- **Therapist adoption is inflecting.** In 2025, only 44% of psychologists reported *never* using AI — down from 71% the year before. But daily use is still just 8%. The adoption curve is early-majority. Top perceived benefits: operational efficiency (42%), research summaries (27%), patient education (18%). [Source](https://bhbusiness.com/2025/12/10/proliferation-of-ai-tools-brings-increased-adoption-skepticism-among-psychologists/)

- **Resistance is real but specific.** Two-thirds of therapists are concerned about data breaches, biased outputs, and hallucinations. The resistance pattern: "AI for admin = fine, AI for clinical judgment = dangerous." Psychotherapists show a "psychological defense mechanism" against AI that mimics clinical reasoning. Context matters: low-risk clients + admin tasks = acceptable, complex cases = wariness. [Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC12220637/)

- **APA published ethical guidance in June 2025.** This is a legitimizing signal — the profession's governing body is now *guiding* AI adoption rather than *blocking* it. The framing is "how to use AI responsibly" not "don't use AI." [Source](https://www.apaservices.org/practice/news/artificial-intelligence-psychologists-work)

- **AFTA's 2025 conference theme was literally "Systemic Therapy in the Age of Technology and AI."** The family therapy establishment is actively engaging with AI as a topic. This is your entry point for conference presentations and visibility. [Source](https://www.afta.org/annual-conference)

**Where FamilyDiagram sits:** You're NOT competing in the documentation/notes space (good — it's crowded). You're doing something no one else is attempting: AI extraction of structured clinical data from conversation. The risk is that therapists will bucket you with "AI doing clinical work" (scary) rather than "AI doing data entry" (safe). Your positioning needs to make the "data entry" frame obvious: the AI isn't making clinical judgments — it's transcribing what the client already said into a structured format, and the therapist reviews every item. The PDP accept/reject workflow is your regulatory shield.

---

**HIPAA and Regulatory Landscape**

- **BAA requirement is non-negotiable.** Any tool processing PHI needs a Business Associate Agreement. Google Cloud (your Gemini provider) offers BAAs for HIPAA-covered entities. You'll need to verify that your Gemini usage is under a BAA-covered account. [Source](https://www.sprypt.com/blog/hipaa-compliance-ai-in-2025-critical-security-requirements)

- **HHS proposed new HIPAA Security Rule in January 2025** that explicitly covers AI training data and prediction models as ePHI. This means if you train models on patient conversations, the training data itself is HIPAA-regulated. Your current architecture (Gemini API calls with conversation text, no fine-tuning) likely sidesteps this, but it constrains your future roadmap. [Source](https://www.jimersonfirm.com/blog/2026/02/healthcare-ai-regulation-2025-new-compliance-requirements-every-provider-must-know/)

- **Penalties are material:** $141-$70,000 per violation, up to $2.1M annually. For a solo founder, a single HIPAA complaint could be existential.

- **State-level AI healthcare laws are proliferating.** Disclosure, transparency, and data protection requirements vary by state. This is the kind of regulatory surface area that favors larger companies with legal teams — or small companies that get compliance right from day one and market it as a differentiator.

**Bottom line:** HIPAA compliance is a moat if you get it right and a landmine if you don't. Your competitors (GenoPro, Genogram Analytics) are all local/offline tools — they sidestep HIPAA by never touching the network. The moment you put patient conversation data through a cloud AI, you're in a different regulatory category. This needs to be solved pre-beta, not post.

---

**Market Size and Opportunity**

- **~120,000 licensed MFTs in the US.** AAMFT represents 72,000 of them (about 60% market coverage for the association). All 50 states license MFTs. [Source](https://www.aamft.org/AAMFT/About_AAMFT/About_Marriage_and_Family_Therapists.aspx)

- **But the real addressable market is wider.** Genograms are used by LCSWs, psychologists, counselors, psychiatric nurses, and social workers — not just MFTs. The broader mental health provider market is ~600,000+ licensed professionals in the US. Any clinician who works with families (child psychologists, school counselors, substance abuse counselors) is a potential user.

- **Current spending:** SimplePractice ($49-99/mo) and similar platforms show therapists will pay $600-1,200/year for practice tools. Specialized clinical tools command premiums — Upheal's paid tier is $39/mo, and SimplePractice's AI Note Taker is a $35/mo add-on. [Source](https://www.simplepractice.com/pricing/compare-plans/)

- **Your pricing ($19.99/mo or $199.99/yr for Professional)** is at the low end of what therapists pay for tools. Given what you're building, this seems underpriced — you're offering more clinical intelligence than tools charging 2-3x more. But the right price depends on the market segment you target (see Positioning below).

- **The training program market is distinct and lucrative.** There are 140+ COAMFTE-accredited MFT programs in the US, plus dedicated Bowen theory programs (The Bowen Center, Kansas City Family Systems Center, Center for Family Consultation in Evanston, ISSFI international). These programs need teaching tools — a genogram tool that teaches Bowen theory concepts as students use it is a different product than a clinical tool for practitioners. [Source](https://www.thebowencenter.org/continuing-studies)

- **Institutional vs. individual:** University programs buy site licenses. Training programs buy cohort access. Individual therapists buy monthly subscriptions. The highest-value contracts are institutional, but the fastest sales are individual. Your current Stripe integration supports individual subscriptions. Institutional licensing (annual invoices, bulk discounts, SSO) would require additional work.

---

**Distribution Channels**

- **Conferences are the primary discovery channel for clinical tools.** AAMFT's Systemic Family Therapy Conference (virtual, October 2025), AFTA Annual Conference (May 2025, online), and the Medical Family Therapy Intensive are where practitioners discover new tools. Presenting at these conferences — even a poster session — would put FamilyDiagram in front of your exact audience. [Source](https://www.aamft.org/AAMFT/Shared_Content/Events/Event_display.aspx?EventKey=SFTC2025)

- **Bowen theory training programs are a direct pipeline.** The Bowen Center (Georgetown), Kansas City Family Systems Center, Center for Family Consultation (Evanston), ISSFI (international) — these are small, tight-knit communities. A demo to one program director could reach an entire cohort. Patrick's clinical background gives you credibility here that no competing software team has.

- **AAMFT's 72,000 members = a mailing list you can't buy.** Sponsoring an AAMFT event, writing for the Family Therapy Magazine, or being listed in their resource directory would be worth more than any Google Ad. AAMFT's 2025 conference theme on AI+therapy suggests they're actively looking for "responsible AI" tools to showcase.

- **Word of mouth in clinical communities is powerful and slow.** Therapists trust peer recommendations. Getting 5-10 clinicians to genuinely use and recommend FamilyDiagram would compound over 12-18 months. This is the long game but the only game that sticks.

- **University MFT programs** (140+ COAMFTE-accredited) adopt tools when professors recommend them. One professor teaching with FamilyDiagram means 20-30 new users per cohort, every year. This is the most leveraged distribution channel for a learning-focused tool.

---

**Positioning Recommendation**

You have three viable positioning options. They're not mutually exclusive long-term, but for MVP launch, you need to pick one:

**Option A: "The Bowen Theory Assessment Tool" (Clinical)**
- Target: Practicing MFTs who use Bowen theory
- Pitch: *"FamilyDiagram turns your client conversations into evidence-based family system assessments using the SARF clinical coding scheme."*
- Advantage: Deep moat (no competitor has SARF), high willingness to pay, clinical credibility
- Risk: Small niche (~5-10% of MFTs actively use Bowen theory), long sales cycle, HIPAA-critical, "AI doing clinical work" resistance

**Option B: "The AI Genogram Builder" (Convenience)**
- Target: Any therapist who uses genograms
- Pitch: *"Talk with your client. FamilyDiagram listens and builds the genogram automatically."*
- Advantage: Broad market (any therapist who draws genograms), easy to explain, "AI as data entry" framing avoids resistance
- Risk: Commoditizable (big players could add this), Bowen theory depth becomes invisible

**Option C: "The Family Systems Teaching Lab" (Education)**
- Target: MFT training programs and Bowen theory institutes
- Pitch: *"Your students practice clinical interviews with AI personas, and the system scores their assessment skills automatically."*
- Advantage: Institutional contracts, recurring cohort revenue, training app already exists, no HIPAA (synthetic personas), aligns with AFTA's AI+education theme
- Risk: Smaller total market, longer contract cycles, product isn't fully built for this yet

**My recommendation: Lead with Option C for MVP launch, build toward Option A.**

Here's why:
1. The Training App already exists and works. You have synthetic persona generation, F1 scoring, and an auditing pipeline.
2. No HIPAA burden — students practice on synthetic personas, not real patients. This removes the single biggest regulatory blocker.
3. Institutional sales = fewer customers, higher contract value, more predictable revenue.
4. Every student who trains on FamilyDiagram in school becomes a future Professional subscriber when they enter practice. This is the "free trial" that lasts 2 years and costs you nothing.
5. AFTA's 2025 conference theme ("Systemic Therapy, Research, and Education in the Age of Technology and AI") is *literally* your pitch. Submit a presentation.
6. The Bowen Center, Kansas City Center, Center for Family Consultation, and ISSFI are 4 organizations that could each represent 20-50 students/year. Getting 2 of those 4 gives you a real user base for the training product.

Then, once you have clinical validation data from the training pipeline (F1 scores, IRR studies), you launch the Personal app (Option A) with published evidence that your extraction actually works. Clinical credibility earned through education is the best go-to-market for a clinical tool.

---

**The One-Sentence Pitch**

For training programs: *"FamilyDiagram is the first tool that lets family therapy students practice clinical interviews with AI personas and receive objective, scored feedback on their Bowen theory assessment skills."*

For practitioners (post-MVP): *"FamilyDiagram listens to your client conversations and builds evidence-based family system assessments automatically — you just review and approve."*

---

**One Uncomfortable Question**

Patrick — your decision log shows you've been iterating on extraction quality for months. People F1 is at 0.72, Events at 0.29, PairBonds at 0.33. You're the sole GT coder at 60 minutes per discussion. You have 4 discussions coded out of a target 5-8.

**Have you talked to a single potential customer who isn't you?**

The decision log has 15 entries. All of them are technical or architectural. None say "talked to [therapist/professor/training director], learned [X]." The IRR study with Guillermo and Kathy was deferred. There's no mention of a waitlist, a landing page, a beta signup form, a conference submission, or even an email to a Bowen theory training program.

Your extraction pipeline may be the most sophisticated AI clinical tool ever built for family therapy. But F1 scores don't pay rent. The market signal you're missing is: does a single person outside your household want this badly enough to pay for it? The fastest way to answer that isn't another point of F1 — it's one demo to one training program director. If they lean forward and ask "when can my students use this?", you have a business. If they say "interesting," you have a hobby.

The agent swarm, the GT coding, the prompt tuning — all of it assumes the market exists. That's the one assumption you haven't tested, and it's the only one that matters.

---

Sources:
- [GenoPro](https://genopro.com/)
- [Genogram Analytics](http://www.genogramanalytics.com/)
- [Qwoach EasyGenogram](https://qwoach.com/tools/genogram)
- [Creately Best Genogram Software 2026](https://creately.com/guides/best-genogram-software/)
- [GenogramTools.com Comparison Guide 2025](https://genogramtools.com/)
- [SimplePractice Pricing](https://www.simplepractice.com/pricing/compare-plans/)
- [Upheal AI Notes](https://www.upheal.io/)
- [Talkspace AI Tools for Therapists](https://www.talkspace.com/blog/ai-tools-for-therapists/)
- [SimplePractice 2026 Therapy Trends](https://www.simplepractice.com/blog/trends-shaping-therapy-2026/)
- [APA on AI in Psychology](https://www.apaservices.org/practice/news/artificial-intelligence-psychologists-work)
- [Psychotherapists' Attitudes Toward AI (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12220637/)
- [AI Adoption Among Psychologists (BHB)](https://bhbusiness.com/2025/12/10/proliferation-of-ai-tools-brings-increased-adoption-skepticism-among-psychologists/)
- [AAMFT About MFTs](https://www.aamft.org/AAMFT/About_AAMFT/About_Marriage_and_Family_Therapists.aspx)
- [MFT Demographics (Zippia)](https://www.zippia.com/marriage-and-family-therapist-jobs/demographics/)
- [BLS MFT Outlook](https://www.bls.gov/ooh/community-and-social-service/marriage-and-family-therapists.htm)
- [The Bowen Center Continuing Studies](https://www.thebowencenter.org/continuing-studies)
- [COAMFTE Accredited Programs](https://www.campusexplorer.com/colleges/accredited-schools/coamfte-accredited-programs/)
- [AFTA 2025 Annual Conference](https://www.afta.org/annual-conference)
- [AAMFT 2025 SFTC Conference](https://www.aamft.org/AAMFT/Shared_Content/Events/Event_display.aspx?EventKey=SFTC2025)
- [HIPAA AI Compliance 2025](https://www.sprypt.com/blog/hipaa-compliance-ai-in-2025-critical-security-requirements)
- [Healthcare AI Regulation 2025](https://www.jimersonfirm.com/blog/2026/02/healthcare-ai-regulation-2025-new-compliance-requirements-every-provider-must-know/)

```proposed-actions
{
  "actions": [
    {
      "id": "market-research-2026-02-28-1",
      "title": "Draft AFTA 2026 conference abstract submission",
      "category": "content",
      "effort": "small",
      "confidence": 0.85,
      "repo": "none",
      "plan": "1. Research AFTA 2026 call for proposals timeline and format requirements\n2. Draft a 250-word abstract positioning FamilyDiagram's training app as 'AI-assisted assessment skill development for family therapy students'\n3. Frame around SARF coding scheme + F1 metrics as objective skill measurement\n4. Save to btcopilot/doc/marketing/afta-2026-abstract.md for Patrick's review and editing",
      "spawn_prompt": "Research the AFTA (American Family Therapy Academy) conference abstract submission process. Their 2025 theme was 'Systemic Therapy, Research, and Education in the Age of Technology and AI' — check if 2026 call for proposals is open yet.\n\nThen draft a conference abstract (250-word max) for FamilyDiagram's training application. Key points to include:\n- Family therapy students practice clinical interviews with AI-generated personas based on synthetic family system scenarios\n- The SARF clinical coding scheme (Symptom, Anxiety, Relationship, Functioning) provides structured assessment of student extraction quality\n- F1 metrics compare student extractions to expert-coded ground truth, providing objective skill measurement\n- Preliminary results: People extraction F1=0.72, Events F1=0.29 (AI baseline), showing the metric discriminates between extraction quality levels\n- Implications for standardized clinical assessment training\n\nWrite the abstract in academic conference style. Save to /Users/hurin/Projects/theapp/btcopilot/doc/marketing/afta-2026-abstract.md (create the marketing directory if needed).\n\nAlso draft a short list of 3-4 Bowen theory training programs to contact for beta testing, with rationale for each:\n- The Bowen Center (Georgetown)\n- Kansas City Family Systems Center\n- Center for Family Consultation (Evanston, IL)\n- ISSFI (international)\n\nSave contact research to /Users/hurin/Projects/theapp/btcopilot/doc/marketing/training-program-outreach.md.\n\nAcceptance criteria: Two markdown files created with polished, ready-to-edit content.",
      "success_metric": "Abstract draft and outreach list ready for Patrick's review"
    },
    {
      "id": "market-research-2026-02-28-2",
      "title": "Create competitive comparison matrix document",
      "category": "content",
      "effort": "small",
      "confidence": 0.90,
      "repo": "none",
      "plan": "1. Create a detailed feature comparison matrix: FamilyDiagram vs GenoPro vs Genogram Analytics vs Qwoach vs Creately\n2. Include: clinical data model, AI features, collaboration, platforms, pricing, HIPAA, Bowen theory support\n3. Save to btcopilot/doc/marketing/competitive-matrix.md",
      "spawn_prompt": "Create a competitive comparison matrix for FamilyDiagram vs its competitors. Save to /Users/hurin/Projects/theapp/btcopilot/doc/marketing/competitive-matrix.md (create marketing directory if needed).\n\nCompare these products across these dimensions:\n\n**Products:**\n1. FamilyDiagram (our product)\n2. GenoPro / GenoProX\n3. Genogram Analytics\n4. Qwoach / EasyGenogram\n5. Creately (genogram templates)\n6. SimplePractice (practice management with basic genogram)\n\n**Dimensions (create a markdown table):**\n- Clinical data model (none / basic genogram / SARF-level)\n- AI extraction from conversation (yes/no)\n- Bowen theory framework (none / symbols only / full SARF coding)\n- Timeline visualization (none / basic / event+variable tracking)\n- Ground truth validation pipeline (yes/no)\n- Platform (Windows / Mac / Web / Mobile)\n- Real-time collaboration (yes/no)\n- HIPAA compliance (stated / BAA available / N/A)\n- Pricing (monthly/annual)\n- Primary target user\n- Key strength\n- Key weakness\n\nFor FamilyDiagram, reference the actual codebase features:\n- SARF clinical coding (Symptom, Anxiety, Relationship, Functioning variables)\n- AI single-prompt extraction with PDP accept/reject workflow\n- F1 metric validation against expert ground truth\n- Desktop (PyQt5) + Mobile (QML) + Training Web App\n- Professional plan: $19.99/mo or $199.99/yr\n- Stripe subscription management\n\nAlso add a 'Positioning Summary' section below the table explaining why FamilyDiagram is in a category of one (clinical assessment system vs diagramming tool).\n\nAcceptance criteria: Clean markdown table with accurate competitive data, suitable for internal strategy use.",
      "success_metric": "Competitive matrix document created with accurate feature comparisons"
    }
  ]
}
```
