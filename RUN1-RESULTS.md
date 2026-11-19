# Run 1 results (19 November 2026)

Tool: commit 8df06ca. Repositories: the four public repositories of the author
that contain Python tests (falsify-dev/falsify, falsify-inspect, mlflow-falsify,
falsify-giskard), default branch, each first-parent commit against its first
parent, file contents read from git objects. No rule was changed after the run.
Each flag below was read against its diff by the AI coding assistant used to
build the tool (Claude); the author has not reviewed them by hand.

## Numbers

| repository | commits compared | commits touching tests | parse failures | flags | conditional skips listed |
|---|---|---|---|---|---|
| falsify | 411 | 110 | 0 | 18 | 8 |
| falsify-inspect | 58 | 10 | 0 | 0 | 0 |
| mlflow-falsify | 25 | 5 | 0 | 0 | 0 |
| falsify-giskard | 13 | 2 | 0 | 4 | 0 |
| **total** | **507** | **127** | **0** | **22** | **8** |

Flags by type: removed_test 19, fewer_assertions 3, new_unconditional_skip 0,
tolerance_loosened 0.

## Each flag, read against its diff

| commit | type | count | label | reading |
|---|---|---|---|---|
| 2bd9397 | fewer_assertions | 1 | legitimate, explained loosening | Test now accepts `falsify init` or `falsify.py init`; reason in a code comment (new console entry point). Two runtime checks became one static assert inside a loop. |
| fd45ae8 | fewer_assertions | 1 | legitimate, explained loosening | Checks phrases across the document instead of in a section that no longer exists; reason in a code comment. |
| c420021 | fewer_assertions | 1 | legitimate, explained loosening | Looks for TUTORIAL in the whole changelog instead of the [Unreleased] block, because releases move entries; reason in a code comment. |
| 3df7eb5 | removed_test | 6 | noise | pytest functions rewritten as unittest methods; four kept their names inside a class, two became dynamically attached per-vector methods that a static check cannot see. |
| 57d9f8c | removed_test | 6 | noise | Test file and tests renamed (sample renamed); same checks. |
| 74820a7 | removed_test | 1 | noise | Test renamed with the module it checks; same assertion. |
| b27c24e | removed_test | 1 | noise | JS-only parity test generalised to all targets under a new name; same assertions per target. |
| ced217a | removed_test | 1 | legitimate change | Renamed and narrowed to control-character vectors after structural reject vectors were added. |
| giskard 2d7ccb0 | removed_test | 2 | legitimate change | Schema migration; replaced by tests for the new schema. |
| giskard 12504a0 | removed_test | 2 | legitimate change | Behaviour changed (claim_id now a generated UUIDv7); replaced by tests for the new behaviour. |

Totals: real weakening 0 · legitimate change 8 (3 of them explained loosenings) · noise 14 (64%, all renames, moves or dynamically generated tests).

## Conditional skips listed separately

8, all in commit 3a3e91e: `tests/test_pyproject.py` gains
`@unittest.skipUnless(tomllib is not None, ...)` on its class (Python 3.11+).
Correctly separated from the flags.

## Against EXPECTED.md

- **b27c24e removes a conditional skip: not flagged for the skip.** As expected
  (it is flagged once, for a renamed test, see above).
- **eb734a4, f045511, 5ebfd41, d048e1a: expected under new_conditional_skip,
  not listed.** The expectation was wrong, not the tool: in all four commits the
  conditional skip arrives together with a new test file or a new test class,
  so no existing test gains a skip, and the definition only compares tests that
  exist in both versions. Tests born skipped are outside the definition.
- **Tolerance rule:** not exercised by the run (no tolerance argument changed in
  these histories); tested on fixtures only.

## What this says, and what it does not

- On the author's own history the check found no real weakening. Most flags
  (14 of 22) are renames and moves, which the definition counts as removals.
- The three fewer_assertions flags are the kind of change the check is meant
  to surface: tests that accept more than before. Here each came with a reason
  in the code.
- This is one author's repositories, built with heavy AI assistance, and
  mostly not research software. It says nothing about how often weakening
  happens in research software; the replay in the proposal is designed for that.

## Misses check (19 November 2026, added after the results above)

The complete search of the history for skip markers (no cut) found 10 commits in
falsify and 1 in mlflow-falsify. The six not covered above:

| commit | where the skip is | in an existing test? | reading |
|---|---|---|---|
| d42e5cf | new file tests/test_prml_vectors.py, `pytest.skip` in a module helper | no | born skipped; outside the definition |
| fa223f4 | new file tests/test_mcp.py, `skipIf` / `skipUnless` | no | born with conditional skips; outside the definition |
| 032543b | new file tests/test_mcp_server.py, `skipUnless` | no | same |
| 3df7eb5 | conditional skip moved from a module helper (`pytest.skip` when vectors are missing) to `setUpClass` (`raise unittest.SkipTest`) | existed before and after | not a weakening; but both places are invisible to the check |
| mlflow 1a1a631 | `self.skipTest` inside `except` in a new test class | no | outside the definition |

No existing test gained an unconditional skip that the check missed.

Two blind spots shown by this check, recorded as limitations (no rule revised):
- Skips raised in helpers, `setUp`, `setUpClass` or at module level are invisible:
  the check reads decorators and test bodies only.
- A skip call inside `except` (or any branch other than `if`) is classified as
  unconditional, although in effect it is conditional. Not triggered in this run.
