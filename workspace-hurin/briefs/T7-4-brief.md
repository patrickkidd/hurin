# T7-4 Delegation Brief — "Build My Diagram" Button (familydiagram)

**Repo:** ~/Projects/theapp/familydiagram  
**Issue:** https://github.com/patrickkidd/btcopilot/issues (T7-4 is tracked in btcopilot issues)  
**PR title must start with:** `T7-4:`

## What to Build

Add a "Build my diagram" button to the Personal app's discussion view. When tapped, it calls the new backend endpoint, waits (~10-15 sec), and populates the PDP sheet with the result.

## Files to Change

1. `pkdiagram/personal/personalappcontroller.py`
   - Add `@pyqtSlot() def extractFullDiscussion(self)` method
   - Pattern: follow `_sendStatement()` — use `self.session.server().nonBlockingRequest("POST", f"/personal/discussions/{self._currentDiscussion.id}/extract", ...)`
   - On success: update `diagramData.pdp` from response JSON, call `self._diagram.setDiagramData(diagramData)`, emit `self.pdpChanged`
   - Add `extractionInProgress` bool property (pyqtProperty) — True while waiting, False on success/error
   - On error: call `self.onError(reply)`, reset `extractionInProgress`

2. `pkdiagram/resources/qml/Personal/DiscussView.qml`
   - Add button (below chat input, or in header — Patrick will review placement)
   - Calls `controller.extractFullDiscussion()`
   - Disabled + shows spinner/loading text while `controller.extractionInProgress` is True
   - Keep logic in QML minimal — no JS business logic (per CLAUDE.md)

## Endpoint (already exists after T7-2 merges)

```
POST /personal/discussions/<id>/extract
Response: { "pdp": { ... } }  (same PDP structure as sendStatement response)
```

## Key Constraints

- **Keep logic in Python, not QML JS** (CLAUDE.md rule)
- For UI constants (colors, spacing), reference `doc/UI_STYLE_SPEC.md` and `pkdiagram/util.py` / `QmlUtil.CONSTANTS`
- Button is simple enough to skip the full ui-planner prototyping process — single new button with loading state
- Run `uv run pytest -vv pkdiagram/tests/personal/` after changes; add a test for `extractFullDiscussion()` following patterns in `test_discussview.py`
- PR title: `T7-4: Add "Build my diagram" button in Personal app`

## Definition of Done

- [ ] `extractFullDiscussion()` slot implemented in Python
- [ ] `extractionInProgress` property exposed to QML
- [ ] Button visible in DiscussView, disabled during extraction
- [ ] On success: PDP drawer populates (pdpChanged signal fires)
- [ ] On error: graceful error message, button re-enabled
- [ ] Unit test added
- [ ] PR open against master with title starting `T7-4:`

## Notes

- T7-2 endpoint must be in master before this branch is testable — confirm before starting
- Patrick will review QML placement before merge
