# Deferred Items — Phase 58

Out-of-scope discoveries logged during plan execution (not fixed, per the executor's scope
boundary — only issues directly caused by the current task's changes are auto-fixed).

## 58-05: `tests/test_merge_policy.py` full-suite-order flake (pre-existing, not caused by this plan)

**Found during:** Task 2, full-suite pytest run.

**Symptom:** `tests/test_merge_policy.py::test_sc3_e2e_promote_forced_still_protects_manual`,
`test_sc4_full_source_attribution`, `test_sc4b_cache_key_not_stamped_unless_promoted`, and
`test_integ_wires_icp_scorer` fail with `AttributeError: 'ThinkingBlock' object has no
attribute 'text'` (inside `pydantic/main.py`) when the FULL `.venv/bin/python -m pytest -q`
suite runs, but all four pass when `tests/test_merge_policy.py` runs in isolation.

**Confirmed pre-existing:** reproduced identically with this plan's entire diff `git stash`ed
(clean state at commit `f6327f1`, the end of 58-05 Task 1) — same 4 failures, same full-suite
count (3186 passed / 4 failed either way). Not introduced by 58-05.

**Likely cause (not investigated further — out of scope):** these tests make live Anthropic
API calls (`src/validator_sonnet.py`); the SDK's response occasionally includes a
`ThinkingBlock` content type that this repo's pydantic-based parsing does not handle,
apparently only reachable under some ordering/timing condition present in the full suite but
not in isolated runs.

**Action:** none taken. Logged per the scope boundary — fixing this is unrelated to
58-05's `country`/`city`/`numberofemployees` wiring.
