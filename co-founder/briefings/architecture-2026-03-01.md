# Co-Founder Briefing: architecture
**Date:** 2026-03-01 23:06 AKST
**Session:** b11dc480-155a-43dc-b0ce-997ebe16a8fd
**Turns:** 10 max

---

Now I have comprehensive data. Let me compile the architecture review briefing.

---

**Architecture Review Briefing — March 1, 2026**

Building on my previous journal entries from Feb 28. This week I went deep into the actual code rather than just process metrics. Here's what I found.

---

**Tech Debt Inventory**

**1. CI is now at 2 failing tests on master — and one was just introduced.**

The latest CI run (PR #35 merge) shows 550 passed, 25 skipped, **2 failed**:

- `test_pickle_contains_json_serializable_dicts` — The test expects `set_diagram_data()` to produce a dict with keys `{people, events, pdp, lastItemId}`, but the actual output includes a top-level `pair_bonds: []` key that the expected dict doesn't have. This is a real regression introduced when `set_diagram_data` started writing `pair_bonds` to the pickle blob. The fix is either to update the test's expected dict to include `pair_bonds`, or to fix `set_diagram_data` if writing `pair_bonds` was unintended. File: `btcopilot/btcopilot/tests/pro/test_diagram_pickle_format.py:83`.

- `test_update` in `training/test_pdp.py` — `KeyError: 'GOOGLE_GEMINI_API_KEY'`. This test calls the real extraction pipeline which requires a Gemini API key that doesn't exist in CI. This test should either be gated behind `@pytest.mark.e2e` or should mock the LLM call. **This is a pre-existing issue** — it's been failing in CI for weeks.

This is a significant improvement from last week's 60% failure rate, but both failures have clear, mechanical fixes.

**2. `test_ask_content.py` — entire module skipped since creation.**

`btcopilot/btcopilot/tests/training/test_ask_content.py:10` has `pytest.skip("not done yet", allow_module_level=True)`. The file references `DataPoint`, `StatementOrigin`, `ResponseDirection`, `Anxiety.detect()`, `Triangle.detect()` — none of which exist in the current codebase. This is a spec file from an earlier architecture that was never implemented. It's 128 lines of dead code counting toward your "test file count" while testing nothing. It should either be deleted or rewritten for the current chat flow.

**3. `pdp.py` validate_pdp_deltas() — 225 lines, 6 nesting levels, highest churn file.**

This function (`btcopilot/btcopilot/pdp.py:163-395`) was modified 8 times in 2 weeks. It has 37 if-statements and 30 for-loops doing validation across three entity types (people, events, pair_bonds). The pattern is identical for each: iterate entities, check FK references exist, collect errors. This is a prime candidate for a validation-per-entity-type decomposition, but given it's the hottest file in the codebase during active MVP work, I'd leave it until the validation rules stabilize after GT coding (T7-5).

**4. `schema.py` DiagramData — god dataclass, 26 fields, 280+ lines, mixed concerns.**

`btcopilot/btcopilot/schema.py` DiagramData mixes: scene data (people, events, pair_bonds), UI display state (hideNames, hideToolBars, scaleFactor), metadata (id, uuid, name, version), PDP staging (pdp, clusters), and authentication (password). The `commit_pdp_items()` method alone is 100+ lines and `_create_inferred_birth_items()` is 140+ lines with 3 major case branches. This is the core data structure for the entire app — every serialization, extraction, and scene mutation flows through it. Not a fire right now, but every new field added increases the blast radius.

**5. Known circular import: `pdp.py` line 459.**

`from btcopilot.training.models import Feedback` inside `cumulative()` to avoid circular import with `training.routes`. Documented and intentional. Not blocking anything, but indicates the extraction pipeline and training feedback are coupled in a way that will get worse as features grow.

---

**Architecture Assessment**

**The good:**

- **Schema layer is clean and intentionally isolated.** `schema.py` imports only Python stdlib + PyQt5.QtCore (for QDate/QDateTime legacy compat). No SQLAlchemy, no Flask. This is a solid design choice — the data model is portable between the desktop app and the backend.

- **Fixture hierarchy in tests is well-designed.** `btcopilot/btcopilot/tests/conftest.py` (250 lines) has clean separation: session-scoped extension mocking, function-scoped test users, parametric LLM mocking (`chat_flow`). Personal and pro test suites each have focused conftest files. This is good engineering.

- **The personal/pro/training package split maps to real product boundaries.** Each has its own models, routes, and test directories. The separation is clean enough that you could deploy the training app independently of the personal app.

**The concerning:**

- **`scene.py` — 3,012 lines, 161 methods, 2 classes.** This is the largest file in the entire codebase. The `Scene` class has 147 public methods and only 14 private ones. It manages item CRUD, querying, property binding, persistence, layout, undo/redo, and event management in a single flat namespace. It's also the Qt/QML scene graph root, so refactoring it means touching the entire UI. This is legacy debt that was well-managed in the past (the CLAUDE.md documents the two-phase loading pattern), but at 3,012 lines, it's at the upper bound of what a single developer can hold in working memory.

- **`discussions.py` route file — 1,762 lines, 48 functions, `audit()` is 460 lines.** This single Flask route handler manages GET, POST, PATCH, DELETE, and PUT in one function with 7 major if/elif chains. All business logic (validation, DB ops, response formatting) lives inline. There's no service layer. For MVP this is fine — it works and it ships. But any agent working on the training app will struggle with a 460-line function that does everything.

- **`extensions/__init__.py` — 601 lines of initialization spaghetti.** Logging, Stripe, Bugsnag, Celery, ChromaDB, and mail initialization all in one file. Eight `init_*` functions called in sequence from `init_app()`. Each mutates global state. The Stripe sync logic (lines 524-601) is 80 lines of nested loops doing subscription reconciliation during Flask app init.

- **No service layer between routes and models.** Both `discussions.py` and `pro/routes.py` query the DB directly, transform data, and return responses all in route handlers. This means business logic can't be reused (e.g., by Celery tasks) without importing the route module.

---

**Dependency Health**

**Pinned dependency versions from `pyproject.toml`:**

| Dependency | Pin | Concern |
|-----------|-----|---------|
| `numpy<2` | Hard ceiling | NumPy 2.0 has been out since June 2024. The `<2` pin suggests an incompatibility that was never investigated. This blocks all packages that require NumPy 2.x. |
| `celery==5.5.3` | Exact pin | Reasonable for stability, but check if security patches have been released. |
| `sip==6.8.6`, `pyqt5==5.15.11` | Exact pins | Qt 5 is in maintenance mode. Not a problem today but the desktop app will eventually need Qt 6. |
| `six==1.14.0` | Exact pin | Python 2/3 compatibility layer. Python 2 has been EOL since 2020. `familydiagram/sysroot/lib/six.py` (980 lines) ships as vendored code. If nothing actually uses six's Py2 features, this is dead weight. |

**LLM framework split**: btcopilot uses three AI frameworks simultaneously:
- `openai` — for the pro copilot
- `pydantic_ai` — for personal chat
- `google-genai` — for personal extraction (Gemini)
- `mistralai` — listed in deps but unclear usage
- `langchain-*` (chroma, core, openai, text-splitters) — for RAG/embeddings

Five AI frameworks is a lot. Each has its own auth, error handling, retry logic, and response format. The `btcopilot/btcopilot/llmutil.py` file centralizes some of this, which is good. But new contributors (or agents) will need to know which framework handles which product surface.

**`chromadb` is listed twice** in `pyproject.toml` — once at the top level and once in the training section. No harm, but sloppy.

---

**Code Quality Metrics**

| Metric | familydiagram | btcopilot | Total |
|--------|--------------|-----------|-------|
| Python files | 296 | 183 | 479 |
| Total lines | 84,843 | 42,692 | 127,535 |
| Test files | ~134 | ~93 | 227 |
| Source files (excl tests) | ~162 | ~90 | 252 |
| Test : source ratio | 0.83:1 | 1.03:1 | — |
| Files > 1000 lines | 11 | 6 | 17 |
| CI pass rate (last 10) | 80% (8/10) | ~80% (8/10) | — |
| Skipped tests | unknown | 25 | — |

**Largest files (complexity risk):**
1. `familydiagram/pkdiagram/scene/scene.py` — 3,012 lines
2. `familydiagram/pkdiagram/scene/random_names.py` — 2,861 lines (data, not logic)
3. `btcopilot/btcopilot/tests/training/routes/test_audio_upload.py` — 2,608 lines (mostly inline JSON fixture data)
4. `familydiagram/pkdiagram/mainwindow/mainwindow.py` — 2,047 lines
5. `familydiagram/pkdiagram/util.py` — 1,996 lines
6. `btcopilot/btcopilot/training/routes/discussions.py` — 1,762 lines

**Highest-churn files (last 2 weeks):**
1. `btcopilot/btcopilot/pdp.py` — 8 modifications
2. `btcopilot/btcopilot/tests/schema/test_validation.py` — 6 modifications
3. `btcopilot/btcopilot/tests/personal/synthetic.py` — 5 modifications
4. `btcopilot/btcopilot/training/routes/discussions.py` — 4 modifications
5. `btcopilot/btcopilot/schema.py` — 4 modifications

All of these are in the extraction/PDP pipeline, confirming that's where active development is concentrated.

**Coverage gaps (untested routes):**
- `btcopilot/btcopilot/training/routes/irr.py` — no test file
- `btcopilot/btcopilot/training/routes/synthetic.py` — no test file

**Dead/abandoned test modules:**
- `btcopilot/btcopilot/tests/training/test_ask_content.py` — module-level skip, references nonexistent classes
- `btcopilot/btcopilot/tests/pro/test_diagrams.py` — test(s) with skip reason "Can't remember why this is skipped"

---

**Performance & Scalability**

**1. `Session.account_editor_dict()` is an N+1 query bomb.**

`btcopilot/btcopilot/pro/models/session.py:38-95` — This method is called on every login/session load. It:
- Queries ALL active users (`User.query.filter_by(active=True)`) — line 47
- For each user, lazy-loads licenses, then for each license, lazy-loads activations and machines — lines 56-64
- Loads the free_diagram with nested discussions, statements, and speakers — lines 68-79

With 100 users and 3 licenses each, that's 1 + 100 + 300 queries minimum. This will be slow in production. It needs `joinedload()` on `User.licenses`, `License.activations`, `License.policy`.

**2. `AccessRight` table has no indexes on FK columns.**

`btcopilot/btcopilot/pro/models/etc.py:46-47` — `diagram_id` and `user_id` are both foreign keys used in `check_read_access()` and `check_write_access()` queries (`btcopilot/btcopilot/pro/models/diagram.py:123-142`). Every diagram access check does a table scan. I see PR #35 just merged with a migration to add these indexes — good, that one's already addressed. **But the CI is now failing on the merge commit**, so the fix isn't fully landed until CI is green.

**3. No database connection pool tuning.**

The Flask app doesn't set `SQLALCHEMY_ENGINE_OPTIONS`. SQLAlchemy defaults to pool_size=5, max_overflow=10, no connection recycling, no pre-ping. For MVP with a few users this is fine. But Celery workers running `generate_synthetic_discussion()` (which can run for minutes) will hold connections from this pool. With 5 connections and a couple concurrent tasks + web requests, you'll hit pool exhaustion.

**4. Pickle serialization for diagram data.**

`Diagram.data` stores diagram state as a pickle blob in PostgreSQL. The `test_pickle_contains_json_serializable_dicts` test suggests you're aware of the brittleness here — pickle format changes when you add fields to DiagramData. The current failing test is evidence of exactly this problem: a new `pair_bonds` top-level key appeared in the pickle output and the test wasn't updated. Pickle is not forward-compatible. Every schema change to DiagramData is a potential data corruption event for existing diagrams.

---

**One Uncomfortable Question**

Patrick — `_create_inferred_birth_items()` at `btcopilot/btcopilot/schema.py:688` is 140+ lines of procedural inference logic that creates parents, spouses, and pair bonds when a Birth/Adopted event is committed. It has 3 major case branches, each mutating `self.pdp.people`, `self.pdp.pair_bonds`, and `self.pdp.events` in place through sequential calls to `_next_pdp_id()`.

This function creates **new family members that the user never mentioned.** If someone says "Sarah was born in 1985," this function infers a mother, a father, and a pair bond between them — all with auto-generated names and auto-assigned IDs. It also searches both PDP (uncommitted) and committed pair bonds to find existing spouses before creating new ones.

**Is this what a family therapist would expect?** In Bowen theory, you typically want the client to identify their own family members. Auto-creating "Sarah's mother" and "Sarah's father" as placeholder people could be useful scaffolding — or it could create data that feels wrong to the clinician reviewing it. The three cases (child-only, person-no-spouse, person-spouse-no-child) each make different assumptions about what should be inferred.

More practically: this function is 140 lines of imperative list mutation inside a dataclass method. It modifies `self.pdp` in place, generates sequential negative IDs by scanning the current PDP state on each call, and updates event references by searching for indexes. A bug here doesn't just create wrong data — it creates structurally inconsistent data (dangling ID references, orphaned people) that manifests as crashes downstream in the scene layer. You've already fixed at least one such crash (commit `5b8506a` — "birth event child resolution crash in accept-all").

The question: **should this inference logic be in `DiagramData.commit_pdp_items()` at all, or should it be a separate pre-commit transform** that the user can review before accepting? If a clinician commits a birth event and suddenly 3 new entities appear that they didn't request, that's a UX surprise. And if the inference is wrong (wrong parent gender, wrong pair bond structure), there's no undo path short of manually deleting the inferred items.

---

**Changes Since Last Review**

Tracking against my Feb 28 baselines:

| Metric | Feb 28 | Mar 1 | Trend |
|--------|--------|-------|-------|
| CI pass rate (btcopilot) | 40% | ~80% | Improving |
| Open PRs (btcopilot) | 3 | 6 | Growing — 3 new PRs from agent index work |
| Failing tests on master | many | 2 | Much better — 550 pass |
| PR #32 (T7-12) | Open, 6835 lines | Still open | Stale |
| Agent autonomous commits | 3 | 3 (same) | Flat |

The CI situation has improved dramatically. Going from 40% to ~80% pass rate in one week is good. The remaining 2 failures have clear fixes.

The PR count is growing though — PRs #34, #35, #36 are all variations on the same AccessRight index fix. PR #35 merged but #34 and #36 are still open. PR #32 (T7-12, +6835 lines) is now 5 days old and still unmerged.

---

```proposed-actions
{
  "actions": [
    {
      "id": "architecture-2026-03-01-1",
      "title": "Fix test_pickle_contains_json_serializable_dicts CI failure",
      "category": "velocity",
      "effort": "trivial",
      "confidence": 0.95,
      "repo": "btcopilot",
      "plan": "1. Read btcopilot/btcopilot/tests/pro/test_diagram_pickle_format.py. 2. The expected dict at line 35 is missing the top-level 'pair_bonds' key that set_diagram_data now writes. 3. Add 'pair_bonds': [] to the expected dict. 4. Run the test to confirm it passes.",
      "spawn_prompt": "Fix the failing test in btcopilot/btcopilot/tests/pro/test_diagram_pickle_format.py::test_pickle_contains_json_serializable_dicts. The test creates a DiagramData with people, events, pdp, and lastItemId, calls diagram.set_diagram_data(), then asserts the pickled output matches an expected dict. The test fails because the actual pickle now includes a top-level 'pair_bonds': [] key that the expected dict at line 35 doesn't have. Fix: add 'pair_bonds': [] to the expected dict at the appropriate position (after 'events'). Run `uv run pytest btcopilot/btcopilot/tests/pro/test_diagram_pickle_format.py -v` to verify. Acceptance criteria: test passes locally.",
      "success_metric": "test_pickle_contains_json_serializable_dicts passes in CI"
    },
    {
      "id": "architecture-2026-03-01-2",
      "title": "Gate test_update behind @pytest.mark.e2e",
      "category": "velocity",
      "effort": "trivial",
      "confidence": 0.95,
      "repo": "btcopilot",
      "plan": "1. Read btcopilot/btcopilot/tests/training/test_pdp.py, find test_update. 2. It fails in CI with KeyError: 'GOOGLE_GEMINI_API_KEY' because it calls the real extraction pipeline. 3. Add @pytest.mark.e2e decorator to test_update so it only runs when --e2e flag is passed. 4. Verify with `uv run pytest btcopilot/btcopilot/tests/training/test_pdp.py -v` (without --e2e) that it gets skipped.",
      "spawn_prompt": "Fix the CI failure in btcopilot/btcopilot/tests/training/test_pdp.py::test_update. This test fails in CI with `KeyError: 'GOOGLE_GEMINI_API_KEY'` because it calls the real Gemini extraction pipeline which requires API credentials not available in CI. Add the `@pytest.mark.e2e` decorator to the `test_update` function (and any other functions in the same file that call real LLM APIs). The e2e marker is already registered in conftest.py and causes tests to be skipped unless `--e2e` is passed. Import pytest at the top if not already imported. Run `uv run pytest btcopilot/btcopilot/tests/training/test_pdp.py -v` (without --e2e) to verify the test is properly skipped. Acceptance criteria: test is skipped in normal runs, CI passes.",
      "success_metric": "btcopilot CI run shows 0 failures (552 passed, 26+ skipped)"
    },
    {
      "id": "architecture-2026-03-01-3",
      "title": "Delete dead test_ask_content.py module",
      "category": "velocity",
      "effort": "trivial",
      "confidence": 0.90,
      "repo": "btcopilot",
      "plan": "1. Verify test_ask_content.py references nonexistent classes (DataPoint, StatementOrigin, ResponseDirection, Anxiety.detect, Triangle.detect). 2. Confirm none of these exist anywhere in the codebase. 3. Delete the file. 4. Run tests to confirm nothing breaks.",
      "spawn_prompt": "Delete the dead test file btcopilot/btcopilot/tests/training/test_ask_content.py. This file has `pytest.skip('not done yet', allow_module_level=True)` at line 10 and references classes that don't exist in the codebase: DataPoint, StatementOrigin, ResponseDirection, Anxiety.detect(), Triangle.detect(). First verify these don't exist: `grep -r 'class DataPoint' btcopilot/` and `grep -r 'class StatementOrigin' btcopilot/` and `grep -r 'class ResponseDirection' btcopilot/` — all should return empty. Then delete the file: `rm btcopilot/btcopilot/tests/training/test_ask_content.py`. Run `uv run pytest btcopilot/btcopilot/tests/training/ -v --co` to confirm no import errors. Acceptance criteria: file deleted, test collection still works.",
      "success_metric": "Dead test file removed, 25 skipped tests drops to 24"
    },
    {
      "id": "architecture-2026-03-01-4",
      "title": "Close stale PRs #34 and #36 (superseded by merged #35)",
      "category": "velocity",
      "effort": "trivial",
      "confidence": 0.95,
      "repo": "btcopilot",
      "plan": "1. PR #35 (Add indexes to AccessRight foreign key columns) was already merged. 2. PRs #34 and #36 are earlier/later attempts at the same fix and are now stale. 3. Close both with a comment explaining they were superseded by #35.",
      "spawn_prompt": "Close stale GitHub PRs in the btcopilot repo. PR #35 ('Add indexes to AccessRight foreign key columns') has already been merged. PRs #34 and #36 are earlier/later attempts at the same change and are now stale. Run: `cd btcopilot && gh pr close 34 --comment 'Superseded by #35 which has been merged.' && gh pr close 36 --comment 'Superseded by #35 which has been merged.'`. Acceptance criteria: both PRs show as closed on GitHub.",
      "success_metric": "PRs #34 and #36 closed, open PR count reduced from 6 to 4"
    },
    {
      "id": "architecture-2026-03-01-5",
      "title": "Remove duplicate chromadb in pyproject.toml",
      "category": "velocity",
      "effort": "trivial",
      "confidence": 0.98,
      "repo": "btcopilot",
      "plan": "1. Read btcopilot/pyproject.toml. 2. 'chromadb' appears twice in [project.optional-dependencies] app section — once at line ~18 and once in the training section around line ~46. 3. Remove the first occurrence (keep the one in the training section where it's semantically grouped). 4. Run `uv lock` to verify no changes to lockfile.",
      "spawn_prompt": "Remove the duplicate 'chromadb' entry in btcopilot/pyproject.toml. Under [project.optional-dependencies] app, 'chromadb' appears twice: once near the top of the list (around line 18, between 'celery' and 'click') and once in the training section (around line 46, before 'langchain-chroma'). Remove the FIRST occurrence only — keep the one grouped with the other training/langchain dependencies. Then run `cd /Users/hurin/.openclaw/workspace-hurin/theapp && uv lock --check` to verify the lockfile is still valid. Acceptance criteria: 'chromadb' appears exactly once in pyproject.toml, uv lock still valid.",
      "success_metric": "Clean pyproject.toml, no functional change"
    },
    {
      "id": "architecture-2026-03-01-6",
      "title": "Add eager loading to Session.account_editor_dict()",
      "category": "bugfix",
      "effort": "small",
      "confidence": 0.80,
      "repo": "btcopilot",
      "plan": "1. Read btcopilot/btcopilot/pro/models/session.py. 2. account_editor_dict() at line 38 lazy-loads User.licenses, License.activations, License.policy in nested list comprehensions. 3. Replace User.query.filter_by(active=True) with User.query.options(joinedload(User.licenses).joinedload(License.activations), joinedload(User.licenses).joinedload(License.policy)).filter_by(active=True). 4. Also add joinedload for self.user.licenses. 5. Run existing pro tests to verify.",
      "spawn_prompt": "Add eager loading to btcopilot/btcopilot/pro/models/session.py to eliminate N+1 queries. In `account_editor_dict()` (line 38): 1. Add `from sqlalchemy.orm import joinedload` at the top of the file. 2. Change line 47 from `User.query.filter_by(active=True)` to `User.query.options(joinedload(User.licenses).joinedload(License.activations).joinedload(Activation.machine), joinedload(User.licenses).joinedload(License.policy)).filter_by(active=True)`. You'll need to import User, License, Activation, Policy from btcopilot.pro.models. 3. Run `uv run pytest btcopilot/btcopilot/tests/pro/ -v` to verify all pro tests still pass. Acceptance criteria: all pro tests pass, account_editor_dict issues fewer queries (verifiable by enabling SQLAlchemy echo).",
      "success_metric": "Pro test suite passes, login endpoint issues O(1) queries instead of O(N*M)"
    }
  ]
}
```
