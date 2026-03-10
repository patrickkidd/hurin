# Successful PR Patterns

Last updated: 2026-03-10

**Data:** 10 merged PRs, 39 closed PRs

## Description Pattern Analysis

| Feature | Merged (avg) | Closed (avg) | Signal |
|---------|-------------|-------------|--------|
| length_chars | 46.40 | 56.87 | - |
| length_words | 7.70 | 8.59 | - |
| has_file_paths | 0.00 | 0.00 | ~ |
| has_acceptance_criteria | 0.00 | 0.00 | ~ |
| has_test_commands | 0.20 | 0.15 | ~ |
| has_specific_function | 0.00 | 0.00 | ~ |
| has_error_message | 0.00 | 0.03 | ~ |
| has_scope_constraint | 0.00 | 0.00 | ~ |
| mentions_files_count | 0.00 | 0.00 | ~ |

## Merged PR Descriptions

- [correct] PR #98: Fix CI: mock gemini_structured in extraction tests
- [correct] PR #89: Add per-entity-type F1 breakdown to eval harness
- [correct] PR #76: Add missing test coverage for personal app endpoints
- [correct] PR #70: Fix birth event self-reference bug (T7-10)
- [correct] PR #65: Raise PairBond F1 from 0.37 to 0.52
- [correct] PR #51: T7-7: Add cumulative F1 validation script for T7-5 discussio
- [correct] Fix co-founder approval rate metric
- [correct] Triage and consolidate PR backlog
- [correct] Auto-fix master CI for btcopilot
- [correct] Respond to @mention on PR #52

## Closed PR Descriptions (first 20)

- [wrong] PR #107: Fix CI: defer litreview FileNotFoundError to runtime
- [wrong] PR #105: Fix CI: graceful degradation for missing fdserver prompts
- [wrong] PR #101: Fix CI: batch_llm_calls tests match updated batch size
- [wrong] PR #97: Fix CI: mock gemini_structured for Pass 3 review
- [wrong] PR #96: Improve PairBond extraction F1 via completeness check prompt
- [wrong] PR #95: Improve Events extraction F1 > 0.4
- [wrong] PR #93: Add integration tests for sync-prod-db.sh
- [wrong] PR #90: Add production database sync script
- [wrong] PR #88: Add deterministic extraction dedup against committed items (
- [wrong] PR #87: Fix T7-10: birth event self-reference bug
- [wrong] PR #86: Add extraction F1 baseline report (2026-03-04)
- [wrong] PR #84: Batch dead-code cleanup (#44, #47, #48, #49)
- [wrong] PR #83: Add per-entity-type F1 breakdown to eval harness
- [wrong] PR #82: Add deterministic extraction dedup against committed items (
- [wrong] PR #81: Fix birth event self-reference bug (T7-10)
- [wrong] PR #75: Add per-entity-type F1 breakdown to eval harness
- [wrong] PR #73: T7-9: Idempotency regression tests for extraction pipeline
- [wrong] PR #72: T7-11: Deterministic extraction dedup against committed item
- [wrong] PR #66: Add idempotent re-extraction tests
- [wrong] PR #64: Fix Events F1: reduce over-extraction + committed-ID resolut

## Key Findings

*(Auto-generated — review and update manually as more data arrives)*

- CI fix tasks: 4/10 merged vs 9/39 closed
- Narrow scope tasks: 1/10 merged vs 1/39 closed
- Refactoring tasks: 0/10 merged vs 3/39 closed

## Rules for Spawn Prompt Quality

1. **Narrow scope** — single file or single test fix strongly predicts success
2. **CI fix with specific test** — 'fix CI: mock X in Y test' pattern works
3. **Avoid broad refactoring** — multi-file cleanup PRs get closed
4. **Include acceptance criteria** — 'tests should pass' or specific assertion
5. **Reference specific files** — file paths in prompt correlate with merge
