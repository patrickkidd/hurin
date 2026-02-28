# Co-Founder Briefing: architecture
**Date:** 2026-02-27 23:07 AKST
**Session:** a2dec2be-83f6-4794-9e18-dc2ad3a425fe
**Turns:** 10 max

---

Good — I now have comprehensive evidence across all dimensions. Let me also confirm `async_utils.py` is actually used (it's imported from `llmutil.py`).

Now I have everything I need. Let me synthesize.

---

**Architecture Review Briefing — 2026-02-27**

---

**Tech Debt Inventory**

The codebase is 127,535 lines of Python across 479 files, plus 45,722 lines of QML across 131 files. For an MVP-stage product built mostly by one person, this is a *lot* of code. The debt is concentrated in a few areas:

- **`scene.py` is a god object (3,012 lines, 161+ methods).** `familydiagram/pkdiagram/scene/scene.py` inherits from both `QGraphicsScene` and `Item`, and handles: item management, undo/redo, clipboard, rendering, file I/O, layer management, event property CRUD, and temporal navigation. Every feature change in the diagram touches this file. It churned 2x in the last month. This is the single highest-risk file in the codebase for introducing regressions. However — this is a Qt scene graph. God-object scenes are *normal* in Qt applications. The cost of decomposing it is high and the benefit to MVP velocity is low. **Don't refactor this now.** Just be aware it's fragile.

- **Training route files are doing business logic.** `btcopilot/btcopilot/training/routes/discussions.py` (1,762 lines, 21 endpoints) has a 254-line `_create_import()` function and a 290-line `filter_event_fields()` nested inside a route handler. `admin.py` (1,355 lines) has a 178-line `approve()` function. Database session management (`db.session.add/flush/commit`) is scattered across route handlers rather than service layers. This makes the training app harder to test and reason about. But — the training app is internal tooling for GT coding. The debt is real but doesn't directly block MVP.

- **Missing database indexes on `access_rights`.** `btcopilot/btcopilot/pro/models/etc.py:46-47` — `diagram_id` and `user_id` columns in the `access_rights` table have no indexes. Every `check_write_access()` and `check_read_access()` call in `diagram.py:123-143` does a full table scan. With a small user base this is invisible; with 100+ diagrams it becomes noticeable. This is a 2-line fix with a migration.

- **Dead code confirmed.** `btcopilot/btcopilot/arrange.py` (59 lines) — zero imports anywhere in the codebase. Abandoned layout dataclasses. `btcopilot/btcopilot/pro/copilot/engine.py` has 24 lines of commented-out old RAG code. Both are safe to remove.

- **`async_utils.py` is NOT dead code** — it's imported by `llmutil.py:220` and `llmutil.py:261` for the `gemini_structured_sync()` and `gemini_text_sync()` wrappers. It's small (31 lines) and functional, though the pattern of creating event loops is fragile in contexts where an event loop already exists (Flask async routes, Celery tasks).

- **Deprecated dependencies.** `six==1.14.0` is imported in `familydiagram/pkdiagram/main.py:52` for sysroot compatibility — it's a build/packaging artifact, not active code. `xlsxwriter==0.9.8` (released 2016, current version 3.x) is used in `documentcontroller.py:1269` for Excel export. `sortedcontainers==2.2.2` (released 2019) is pinned but still functional. These are not urgent but `xlsxwriter` in particular is 10 years behind.

- **38 TODO markers across 411 source files.** Most are architectural notes, not bugs. Notable: `scene.py:2283` about layer model notification, `person.py:1592` about bounding rect calculation, `diagram.py:17` about removing a version compat shim. Zero HACK/XXX/WORKAROUND markers — the codebase is honest about its debts.

**Impact on MVP velocity:** Low. The real debt is in the training routes, but that's internal tooling. The `scene.py` god object is the kind of debt that accumulates slowly — each change is 5% harder than it should be, compounding over months. None of these items are blocking.

---

**Architecture Assessment**

The three-package structure (btcopilot, familydiagram, fdserver) is **well-designed** for the project's needs:

- **Unidirectional dependency graph.** familydiagram depends on btcopilot. btcopilot depends on nothing upstream. Zero reverse imports confirmed. This is clean and correct.

- **`btcopilot/schema.py` is the shared contract** — 138 imports across both packages. It defines the Bowen theory domain model (`Person`, `Event`, `PairBond`, `PDP`, `DiagramData`) as pure Python dataclasses with no ORM coupling. This is the right design: the schema can be used by the client (familydiagram), the server (btcopilot), and the training app without any of them needing to know about each other.

- **The PDP staging workflow is elegant.** Negative IDs for LLM-extracted staging, positive IDs for committed items, `commit_pdp_items()` with transitive closure for inference — this is genuinely well-thought-out domain modeling. `pdp.py` (785 lines) is the most-churned file (10 commits last month) but it's focused, well-structured, and has good error handling. The churn is feature work, not thrashing.

- **`server_types.py` is the right bridge.** 614 lines handling client-server communication with pickle serialization and optimistic locking. It isolates the network layer cleanly. familydiagram never touches SQLAlchemy directly.

- **The extension system (`extensions/__init__.py`, 601 lines) is standard Flask.** Global singletons for db, mail, chroma, celery — initialized via `init_app()` pattern. Datadog JSON logging, Stripe integration, Bugsnag error tracking. This is boilerplate but correct.

- **Circular imports are minimal.** Only 2 `TYPE_CHECKING` blocks in all of familydiagram (Event ↔ Marriage, Triangle ↔ Event/Layer/Person). Zero in btcopilot. For a 127K LOC Python codebase, this is unusually clean.

**Missing abstractions:** The training route files need a service layer. `discussions.py` and `admin.py` have business logic (PDP delta construction, CSV parsing, approval workflows) embedded in Flask route handlers. Extracting these into service classes would make the training app testable without HTTP.

**Unnecessary abstractions:** None found. The codebase is lean for its size. If anything, it errs on the side of *too few* abstractions rather than too many — which is correct for a pre-MVP project.

---

**Dependency Health**

- **Python 3.11.6 exact pin** in root `pyproject.toml`. This is appropriate for reproducibility but will need updating eventually. Python 3.11 has security support through October 2027 — no rush.

- **Qt/PyQt pinned precisely** (`pyqt5==5.15.11`, `sip==6.8.6`). This is necessary — Qt version mismatches cause silent crashes. Correct decision.

- **`numpy<2` upper bound.** NumPy 2.0 broke many downstream packages. This constraint is protective and appropriate.

- **Flask ecosystem entirely unpinned.** Flask, Flask-SQLAlchemy, Flask-Mail, Flask-WTF — all at whatever `uv` resolves. This is risky for production but fine for development. The lock file (`uv.lock`) provides reproducibility. Keep the lock file current.

- **AI/LLM dependencies are a sprawl.** The project uses: `openai` (Pro copilot), `google-genai` (Personal extraction), `pydantic_ai` (listed twice), `mistralai`, `assemblyai`, `langchain-chroma`, `langchain-core`, `langchain-openai`, `langchain-text-splitters`, `chromadb`. That's 5 different AI vendor SDKs plus LangChain plus ChromaDB. For an MVP, this is a lot of surface area to maintain. The actual *used* code paths are narrower — `llmutil.py` only calls Gemini — but the dependency graph pulls in all of these.

- **`xlsxwriter==0.9.8`** — 10 years old. Used for Excel export in the Pro app. Not blocking, but if you ever need to touch that export code, you'll need to update.

- **`six==1.14.0`** — Python 2/3 compatibility shim, deprecated. Only imported in `main.py:52` as a sysroot artifact. If the sysroot build system no longer needs it, remove it.

- **`celery==5.5.3` exact pin.** Celery has historically been fragile with version bumps. Pinning is correct.

---

**Code Quality Metrics**

- **Test ratio:** 1,627 test functions across the codebase. familydiagram has excellent coverage (1,053 tests). btcopilot's coverage is uneven.

- **Critical coverage gap: `btcopilot/pro/routes.py`** — 1,037 lines, 32 route functions, **zero tests.** This is the Pro app API that handles diagrams, licensing, and user management for paying customers. Every endpoint is untested. This is the single highest-risk coverage gap.

- **`btcopilot/pro/tasks.py`** — 15 background task functions, zero tests. Async failures in production would be invisible.

- **`btcopilot/personal/chat.py`** — Core conversation logic, zero dedicated test file. This is MVP-critical.

- **All 6 Pro models** (diagram, user, license, session, etc, policy) have zero individual test files. They're tested indirectly through route tests — except there are no route tests.

- **Training app is well-tested** by comparison: `f1_metrics.py` has 55 tests, `clusters.py` has 12, `analysis_utils.py` has 10.

- **Largest files (complexity risk):**
  - `scene.py` — 3,012 lines (Qt scene, expected to be large)
  - `random_names.py` — 2,861 lines (data file, not complexity)
  - `test_audio_upload.py` — 2,608 lines (test file, acceptable)
  - `discussions.py` — 1,762 lines (needs service extraction)
  - `mainwindow.py` — 2,047 lines (Qt main window, expected)

- **Most-churned files (stability risk):**
  - `btcopilot/pdp.py` — 10 commits last month (core extraction, actively developed)
  - `btcopilot/tests/schema/test_validation.py` — 8 commits (tests evolving with schema)
  - `familydiagram/personalappcontroller.py` — 8 commits (personal app UI)

- **Type suppression is minimal.** 8 `# type: ignore` directives total, all in familydiagram for PyQt5 edge cases. Zero `noqa`. Zero `pragma: no cover`. This is unusually clean.

- **Warning suppression is strategic.** Only 2 locations: Pydantic deprecation from chromadb, and ResourceWarning from Stripe in debug builds. No `ignore all` patterns.

---

**Performance & Scalability**

- **Missing FK indexes are the biggest issue.** `access_rights.diagram_id` and `access_rights.user_id` at `etc.py:46-47` — no `index=True`. The `check_write_access()` and `check_read_access()` methods at `diagram.py:123-143` loop through `AccessRight.query.filter_by()` results per diagram. With N diagrams and M access rights, this is O(N*M) table scans instead of O(N) indexed lookups.

- **Other missing FK indexes:** `diagrams.user_id`, `discussions.user_id`, `discussions.diagram_id`, `statements.discussion_id`, `statements.speaker_id`, `speakers.discussion_id`. Standard practice is to index all FK columns.

- **N+1 in statement iteration.** `personal/chat.py` and `training/routes/discussions.py` iterate through `discussion.statements` and access `s.speaker_id` or `s.speaker`. The speaker relationship is lazy-loaded, triggering a query per statement. The training app's audit view has the correct pattern at `discussions.py:686-689` (`subqueryload`/`joinedload`), but it's not applied elsewhere.

- **Redundant session operations.** `pro/models/user.py:151-154` calls `db.session.add(diagram)` then `db.session.merge(diagram)` twice. The merge calls are redundant — the diagram is already in the session after `add()`.

- **No LLM rate limiting or retry logic.** `llmutil.py` calls Gemini directly with no retry on transient failures, no token counting, no cost tracking. The 120-second timeout (`GEMINI_TIMEOUT_MS`) is the only protection. For MVP this is fine; for production with real users, one Gemini outage will cascade.

- **Pickle serialization for diagram data.** `server_types.py` uses pickle for client-server data transfer. Pickle is fast but creates tight version coupling — if `DiagramData` fields change, old pickled data may fail to deserialize. The `test_compat.py` (1,080 lines) test file suggests this has already been a pain point.

- **No query result caching** beyond F1 metrics and the Gemini client singleton. Every page load queries the database fresh. Acceptable at current scale.

---

**One Uncomfortable Question**

Patrick — `llmutil.py` is 264 lines. It hardcodes `EXTRACTION_MODEL = "gemini-2.5-flash"` and `RESPONSE_MODEL = "gemini-3-flash-preview"` at lines 14-16. It uses a single Gemini client. It has no retry logic, no fallback, no token tracking, no cost guardrails.

Meanwhile, your `pyproject.toml` lists **10 AI-related dependencies**: openai, google-genai, pydantic_ai (twice), mistralai, assemblyai, langchain-chroma, langchain-core, langchain-openai, langchain-text-splitters, chromadb. That's 5 vendor SDKs, LangChain's full chain-of-abstraction stack, and a vector database.

**How much of this dependency surface is actually used?**

The extraction pipeline calls `gemini_structured()`. The chat calls `gemini_text()`. The Pro copilot uses OpenAI. That's... three API calls. LangChain is presumably used for RAG in the Pro copilot's `engine.py`, and ChromaDB stores embeddings. AssemblyAI is for transcription. MistralAI — is it used anywhere in active code paths?

Each of these dependencies is a maintenance liability: version conflicts, API changes, security patches, import time overhead. LangChain in particular changes its API aggressively between versions. You're carrying 10 packages to make ~5 API calls. For an MVP where speed matters, **is the abstraction helping you or slowing you down?** The 264-line `llmutil.py` that does the actual work suggests you've already bypassed most of these abstractions. The question is whether the rest can be pruned before they rot into the kind of dependency debt that makes `pip install` a prayer.

```proposed-actions
{
  "actions": [
    {
      "id": "architecture-2026-02-27-1",
      "title": "Add missing FK indexes on access_rights table",
      "category": "infrastructure",
      "effort": "trivial",
      "confidence": 0.95,
      "repo": "btcopilot",
      "plan": "1. Add index=True to diagram_id and user_id columns in etc.py AccessRight model\n2. Generate alembic migration\n3. Verify migration runs clean",
      "spawn_prompt": "In /Users/hurin/Projects/theapp/btcopilot, add missing database indexes:\n\n1. Edit btcopilot/btcopilot/pro/models/etc.py line 46-47: Add `index=True` to both `diagram_id` and `user_id` columns in the AccessRight model. Current code:\n```python\ndiagram_id = Column(Integer, ForeignKey(\"diagrams.id\"), nullable=False)\nuser_id = Column(Integer, ForeignKey(\"users.id\"), nullable=False)\n```\nChange to:\n```python\ndiagram_id = Column(Integer, ForeignKey(\"diagrams.id\"), nullable=False, index=True)\nuser_id = Column(Integer, ForeignKey(\"users.id\"), nullable=False, index=True)\n```\n\n2. Generate an alembic migration: `cd /Users/hurin/Projects/theapp/btcopilot && uv run alembic revision --autogenerate -m 'add_indexes_to_access_rights'`\n\n3. Verify the generated migration file looks correct (should add two CreateIndex operations).\n\nAcceptance criteria: AccessRight model has indexed FK columns, alembic migration generated successfully.",
      "success_metric": "AccessRight FK columns have index=True, alembic migration file exists and is correct"
    },
    {
      "id": "architecture-2026-02-27-2",
      "title": "Remove dead arrange.py module",
      "category": "velocity",
      "effort": "trivial",
      "confidence": 0.98,
      "repo": "btcopilot",
      "plan": "1. Verify arrange.py has zero imports (confirmed)\n2. Delete btcopilot/btcopilot/arrange.py\n3. Run tests to confirm nothing breaks",
      "spawn_prompt": "In /Users/hurin/Projects/theapp/btcopilot:\n\n1. First verify that arrange.py is not imported anywhere: `grep -rn 'arrange' btcopilot/ --include='*.py' | grep -v __pycache__` — should return zero results for import statements.\n\n2. Delete the file: btcopilot/btcopilot/arrange.py (59 lines, contains unused dataclasses: Point, Size, Rect, Person, PersonDelta, Diagram, DiagramDelta)\n\n3. Run `uv run pytest btcopilot/btcopilot/tests/ -x -q --timeout=30` to verify nothing breaks.\n\nAcceptance criteria: arrange.py deleted, tests pass.",
      "success_metric": "File deleted, test suite passes with no import errors"
    }
  ]
}
```
