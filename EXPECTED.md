# Expected results, written before the first run (19 November 2026)

This file is committed before the check is written or run. It fixes the flag
definitions and the answers the first run should give on cases already known.
It will not be edited after the run; any change gets a new dated section below.

## Scope of this prototype

- Python test files only (pytest and unittest styles), compared between a commit
  and its first parent, file contents read from git objects (no checkout).
- Only the "tests got weaker" flag. The acceptance-file flag, R/testthat, a GitHub
  Action and packaging are out of scope.

## Flag definitions

A test is a function or method named `test*` in a file named `test_*.py` or
`*_test.py`, identified by file path + class + function name.

FLAGGED (weaker):
1. `removed_test`: a test present in the parent is absent in the commit.
   Known false positive: a renamed or moved test shows as removed. It is counted,
   not matched.
2. `new_unconditional_skip`: a test gains an unconditional skip or expected failure
   (`@pytest.mark.skip`, `@pytest.mark.xfail` without a condition, `@unittest.skip`,
   `@unittest.expectedFailure`, or a `pytest.skip(...)` / `self.skipTest(...)` call
   not inside an `if`).
3. `fewer_assertions`: a test that exists in both versions has fewer assertions
   (bare `assert` statements plus calls to `self.assert*`, `assert*` functions such
   as `np.testing.assert_allclose`, and `pytest.raises` / `self.assertRaises`).
4. `tolerance_loosened`: in a test present in both versions, a numeric tolerance
   argument (`rtol`, `atol`, `rel`, `abs`, `delta`, `places`, `decimal`) changes
   so that the test accepts more: a larger value for `rtol/atol/rel/abs/delta`,
   a smaller value for `places/decimal`.

LISTED SEPARATELY (not flagged):
5. `new_conditional_skip`: a test gains a skip that depends on a condition
   (`@pytest.mark.skipif`, `@pytest.mark.xfail(condition, ...)`,
   `@unittest.skipIf`, `@unittest.skipUnless`, or a skip call inside an `if`).

NOT FLAGGED: a skip removed, a test added, more assertions, a tolerance tightened.

## Known answers (from a search of the history on 19 November 2026)

In the repository `falsify-dev/falsify` (default branch, first-parent history):
- eb734a4, f045511, 5ebfd41 add conditional skips (optional extra, candidate
  vector file, Node.js present). Expected: listed under `new_conditional_skip`,
  not flagged.
- d048e1a (merge of the v0.3.11 branch, first parent) brings in a conditional
  skip (Node.js present). Expected: `new_conditional_skip`, not flagged.
- b27c24e removes a conditional skip. Expected: not flagged.

## What the result must say

- How many commits were scanned and how many files failed to parse.
- Flags by type, each read against its diff and labelled: real weakening,
  legitimate change, or noise (moved/renamed test counted as noise).
- The tolerance rule: tested on fixtures; the four repositories contain only a
  handful of tolerance arguments, so the run may not exercise it.
- No rule is tuned to the first run. At most one revision, logged here with the
  numbers before and after.
