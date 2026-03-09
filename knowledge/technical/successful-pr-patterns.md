# Successful PR Patterns

Last updated: 2026-03-09

**Data:** 3 merged PRs, 26 closed PRs

## Description Pattern Analysis

| Feature | Merged (avg) | Closed (avg) | Signal |
|---------|-------------|-------------|--------|
| length_chars | 56.33 | 58.23 | - |
| length_words | 9.67 | 8.62 | + |
| has_file_paths | 0.00 | 0.00 | ~ |
| has_acceptance_criteria | 0.00 | 0.00 | ~ |
| has_test_commands | 0.33 | 0.19 | + |
| has_specific_function | 0.00 | 0.00 | ~ |
| has_error_message | 0.00 | 0.04 | ~ |
| has_scope_constraint | 0.00 | 0.00 | ~ |
| mentions_files_count | 0.00 | 0.00 | ~ |

## Merged PR Descriptions

- [correct] PR #98: Fix CI: mock gemini_structured in extraction tests
- [correct] PR #65: Raise PairBond F1 from 0.37 to 0.52
- [correct] PR #51: T7-7: Add cumulative F1 validation script for T7-5 discussio

## Closed PR Descriptions (first 20)

- [wrong] PR #107: Fix CI: defer litreview FileNotFoundError to runtime
- [wrong] PR #105: Fix CI: graceful degradation for missing fdserver prompts
- [wrong] PR #101: Fix CI: batch_llm_calls tests match updated batch size
- [wrong] PR #96: Improve PairBond extraction F1 via completeness check prompt
- [wrong] PR #95: Improve Events extraction F1 > 0.4
- [wrong] PR #93: Add integration tests for sync-prod-db.sh
- [wrong] PR #90: Add production database sync script
- [wrong] PR #87: Fix T7-10: birth event self-reference bug
- [wrong] PR #84: Batch dead-code cleanup (#44, #47, #48, #49)
- [wrong] PR #83: Add per-entity-type F1 breakdown to eval harness
- [wrong] PR #82: Add deterministic extraction dedup against committed items (
- [wrong] PR #81: Fix birth event self-reference bug (T7-10)
- [wrong] PR #72: T7-11: Deterministic extraction dedup against committed item
- [wrong] PR #66: Add idempotent re-extraction tests
- [wrong] PR #64: Fix Events F1: reduce over-extraction + committed-ID resolut
- [wrong] PR #61: T7-20: Baseline F1 with gemini-3.1-flash-lite-preview
- [wrong] PR #57: Upgrade extraction model to gemini-3.1-flash-lite-preview
- [wrong] PR #56: Upgrade extraction model to gemini-3.1-flash-lite-preview
- [wrong] PR #55: Smoke test: relay reads README (579 lines)
- [wrong] PR #53: Experiment: simplified extraction prompt (strip SARF variabl

## Key Findings

*(Auto-generated — review and update manually as more data arrives)*

- CI fix tasks: 1/3 merged vs 6/26 closed
- Narrow scope tasks: 1/3 merged vs 0/26 closed
- Refactoring tasks: 0/3 merged vs 3/26 closed

## Rules for Spawn Prompt Quality

1. **Narrow scope** — single file or single test fix strongly predicts success
2. **CI fix with specific test** — 'fix CI: mock X in Y test' pattern works
3. **Avoid broad refactoring** — multi-file cleanup PRs get closed
4. **Include acceptance criteria** — 'tests should pass' or specific assertion
5. **Reference specific files** — file paths in prompt correlate with merge
