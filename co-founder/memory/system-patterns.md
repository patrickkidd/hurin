# System Patterns

## Task Success Patterns
- Claude Code (Opus) handles most implementation
- Hurin routes trivial queries directly
- Ralph Loop recovers from ~60% of failures

## Known Gaps (as of 2026-03-02)
- No DAG-based decomposition
- No event-sourced state persistence
- Secrets still partly plaintext
- No per-task risk scoring (addded today)
