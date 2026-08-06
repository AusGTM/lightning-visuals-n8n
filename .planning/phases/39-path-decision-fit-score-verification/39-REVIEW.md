---
phase: 39-path-decision-fit-score-verification
reviewed: 2026-08-06T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - scripts/probe_scoring_tool_availability.py
  - scripts/probe_scoring_recalc_latency.py
  - src/hubspot_client.py
  - tests/test_scoring_probe_helpers.py
findings:
  critical: 1
  warning: 3
  info: 3
  total: 7
status: issues
fixed_at: 2026-08-06T00:00:00Z
fix_status: partial
fixed_findings: [CR-01, WR-01, WR-02, WR-03]
remaining_findings: [IN-01, IN-02, IN-03]
---

# Phase 39: Code Review Report

**Reviewed:** 2026-08-06
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the disarmed-by-default HubSpot scoring-tool availability probe, the
two-key-gated disposable-company recalc-latency probe, the new `delete_record()`
CRUD wrapper, and their unit tests. The stated safety invariants (zero writes
unless two-key armed, portal guard, no token logging, disposable-company prefix as
a module constant, dry-run-default `delete_record()`) all hold under inspection and
are backed by passing unit tests for the disarmed paths.

However, `scripts/probe_scoring_recalc_latency.py`'s core measurement loop has a
logic bug that breaks the probe's actual purpose: it patches the flip property to
the same target value on every one of the three samples instead of alternating it,
so only the first of three samples ever represents a genuine property change. When
this script is eventually run live (per 39-04), it will very likely burn a ~65-minute
timeout on sample 2, report `band=c` (no-fire), and falsely conclude the lead-scoring
tool doesn't recalculate on API writes — even when it does. This directly undermines
the D-03/D-04 decision this whole phase exists to make, so it is filed as a Critical
finding despite the script not having been run live yet ("shipped code still gets
reviewed" per this review's scope).

A few secondary robustness/quality issues are noted as warnings and info items.

## Fix Summary (2026-08-06)

Critical + Warning findings (CR-01, WR-01, WR-02, WR-03) fixed and committed atomically.
Info findings (IN-01, IN-02, IN-03) are out of scope per fix run instructions and remain
open below, unchanged.

| Finding | Outcome | Commit |
| --- | --- | --- |
| CR-01 | fixed | `c24fda5` |
| WR-01 | fixed | `a61172f` |
| WR-02 | fixed | `f7e541c` |
| WR-03 | fixed | `cb7ee0f` |
| IN-01 | not fixed (out of scope) | — |
| IN-02 | not fixed (out of scope) | — |
| IN-03 | not fixed (out of scope) | — |

Full test suite (`.venv/bin/python -m pytest`) green after all four fixes: 2202 passed, 6
skipped.

## Critical Issues

### CR-01: Recalc-latency probe re-writes the same value on samples 2 and 3, silently degrading a real measurement into a guaranteed timeout

**Outcome: fixed** (commit `c24fda5`)

**File:** `scripts/probe_scoring_recalc_latency.py:154-172` (`_run_one_sample`) and `216-227` (the sample loop inside `main`)

**Issue:** The disposable company is created with `FLIP_PROPERTY_NAME = FLIP_INITIAL_VALUE` (line 208). `_run_one_sample` always patches `FLIP_PROPERTY_NAME` to the same constant, `FLIP_TARGET_VALUE` (line 163), on every call — there is no alternation back to `FLIP_INITIAL_VALUE` between rounds. The `SAMPLE_COUNT = 3` loop in `main()` (lines 216-227) calls `_run_one_sample` three times with no varying target:

- Sample 0 (`i=0`): flip property goes `FLIP_INITIAL_VALUE -> FLIP_TARGET_VALUE`. This is a genuine change, so if the lead-scoring tool actually recalculates on API writes, the score changes and a real latency is captured.
- Sample 1 (`i=1`): flip property is already `FLIP_TARGET_VALUE` from sample 0. Patching it to `FLIP_TARGET_VALUE` again is a no-op write. Since the score is a function of the (unchanged) scoring inputs, the score cannot change — `current != pre_flip_value` (line 169) will never become true, regardless of whether HubSpot's recalculation engine actually fires. The loop will spin for the full `POLL_TIMEOUT_SECONDS = 3900.0` (65 minutes) and return `None`.
- Because `elapsed is None` triggers an early `break` (lines 223-226), sample 2 never even runs.

`main()` then computes `median_seconds = None if any(s is None for s in samples) else ...` (line 229) — since `samples = [real_elapsed, None]`, this is unconditionally `None`, so `classify_latency_band(None) == "c"` (line 230/103-104). The probe reports `band=c` ("manual-only / does not fire on API writes... pause for operator review") even in the scenario where the real answer is band `a` or `b`. This is the exact outcome D-04 uses to decide whether to proceed with the lead-scoring tool at all — a false `c` verdict here would misdirect the whole Phase 39 decision, and the live run would also waste ~65 minutes and a disposable-company create/delete cycle to produce it.

No unit test exercises this loop's write-alternation behavior (only the pure `median_latency`/`classify_latency_band`/`find_score_property_name` functions and `delete_record` are tested — see WR-03), so nothing caught this before it shipped.

**Fix:** Alternate the value written each round instead of hard-coding `FLIP_TARGET_VALUE` in `_run_one_sample`:

```python
def _run_one_sample(record_id: str, score_property_name: str, pre_flip_value, flip_value):
    t0 = time.monotonic()
    patch_record("companies", record_id, {FLIP_PROPERTY_NAME: flip_value}, dry_run=False)
    while time.monotonic() - t0 < POLL_TIMEOUT_SECONDS:
        time.sleep(POLL_INTERVAL_SECONDS)
        record = get_record("companies", record_id, [score_property_name])
        current = record.get("properties", {}).get(score_property_name)
        if current != pre_flip_value:
            return time.monotonic() - t0
    return None
```

```python
for i in range(SAMPLE_COUNT):
    record = get_record("companies", record_id, [score_property_name])
    pre_flip_value = record.get("properties", {}).get(score_property_name)
    flip_value = FLIP_TARGET_VALUE if i % 2 == 0 else FLIP_INITIAL_VALUE
    elapsed = _run_one_sample(record_id, score_property_name, pre_flip_value, flip_value)
    ...
```

## Warnings

### WR-01: Portal guard is overridable via an environment variable, weakening a stated hard invariant

**Outcome: fixed** (commit `a61172f`)

**File:** `scripts/probe_scoring_tool_availability.py:33`, `scripts/probe_scoring_recalc_latency.py:46`

**Issue:** Both scripts define `EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")`. The stated safety invariant is "Portal guard: refuses unless portal 22617666," but as written this is only the *default* — any process environment that happens to export `HUBSPOT_EXPECTED_PORTAL_ID` (e.g. a stale `.env`, a CI secret, a copy-pasted shell export from another project) silently redefines what portal the guard accepts, without any code change. This mirrors an existing pattern from `rollback_canary_proof.py` per the plan notes, so it isn't newly invented here, but it is present in both files under review and undercuts the "hard-coded 22617666 refusal" guarantee the phase's safety invariants describe.

**Fix:** Hard-code `EXPECTED_PORTAL_ID = "22617666"` (no env override), matching the treatment already given to `COMPANY_NAME_PREFIX` and `FLIP_PROPERTY_NAME` ("module constant, no CLI/env override").

### WR-02: Teardown is best-effort with no retry; a raising `delete_record` call masks the triggering exception

**Outcome: fixed** (commit `f7e541c`)

**File:** `scripts/probe_scoring_recalc_latency.py:214-276`

**Issue:** The `finally` block calls `delete_record("companies", record_id, dry_run=False)` exactly once with no retry/backoff. `delete_record` (in `src/hubspot_client.py:80-81`) calls `r.raise_for_status()`, so a transient 429/5xx, or a 404 if the company was already removed by another process, raises an exception out of the `finally` block. Two consequences:

1. If the code inside `try` also raised (e.g. a network error mid-poll), Python replaces that original exception with the one raised inside `finally` — the operator sees only the delete failure, not the root cause of the probe's actual failure.
2. If the delete genuinely fails (transient error), the disposable `ZZ-SCORING-TEST-DELETE-ME-*` company is left live with no retry attempt, contradicting "guaranteed teardown... even on failure paths." The `record_id` is printed earlier (line 212) so it's recoverable, but only by a human reading stdout/logs after the fact.

**Fix:** Wrap the `finally` delete in its own try/except that logs (rather than raises) on failure, and/or add one retry with backoff before giving up:

```python
finally:
    try:
        response = delete_record("companies", record_id, dry_run=False)
        deleted_ok = getattr(response, "status_code", None) == 204
    except Exception as exc:
        deleted_ok = False
        print(f"teardown FAILED for {record_id}: {exc} — company may still exist live, "
              f"delete it manually.")
```

### WR-03: No test coverage for the live sample loop's write-alternation behavior

**Outcome: fixed** (commit `cb7ee0f`)

**File:** `scripts/probe_scoring_recalc_latency.py` (`_run_one_sample`, `main`'s sample loop), `tests/test_scoring_probe_helpers.py`

**Issue:** `tests/test_scoring_probe_helpers.py` covers `delete_record` and the three pure helpers (`median_latency`, `classify_latency_band`, `find_score_property_name`) but has no test that mocks `patch_record`/`get_record` to assert what value gets written on each of the three sample rounds. A test asserting "the value written to `FLIP_PROPERTY_NAME` differs from the previous round's value" would have caught CR-01 before it shipped.

**Fix:** Add a unit test that monkeypatches `patch_record`/`get_record` and drives `main()`'s loop (or a refactored-out sample-loop function) through 3 iterations, asserting the written flip value alternates and is never equal to the immediately-preceding write.

## Info

### IN-01: Score-property filtering logic is duplicated across two files

**File:** `scripts/probe_scoring_tool_availability.py:53-55` (`find_score_properties`), `scripts/probe_scoring_recalc_latency.py:114-121` (`find_score_property_name`)

**Issue:** Both functions filter on `entry.get("fieldType") == "calculation_score"`, one returning a list of matches, the other the first match's name. If HubSpot's `fieldType` string for score properties ever changes, both call sites need updating and it's easy to miss one.

**Fix:** Not urgent for two small tracer/probe scripts — flagging for awareness rather than requesting a shared-helper refactor.

### IN-02: `FLIP_TARGET_VALUE` computed at import time can raise `IndexError` if `taxonomy.ORG_TYPES` ever shrinks to one entry

**File:** `scripts/probe_scoring_recalc_latency.py:79`

**Issue:** `FLIP_TARGET_VALUE = sorted(k for k in taxonomy.ORG_TYPES if k != taxonomy.DEFAULT_ORG_TYPE)[0]` runs at module import. If `taxonomy.ORG_TYPES` were ever reduced to a single value equal to `DEFAULT_ORG_TYPE`, this raises `IndexError` on import — which would also break `tests/test_scoring_probe_helpers.py` (it imports this module at collection time), failing the whole test file rather than just this feature.

**Fix:** Low priority given current taxonomy size; a defensive `next(iter(...), None)` plus an explicit check would fail more legibly if it ever happens.

### IN-03: `find_score_property_name` picks an arbitrary property if multiple `calculation_score` properties exist

**File:** `scripts/probe_scoring_recalc_latency.py:114-121`

**Issue:** Returns the first matching property in API response order with no disambiguation, warning, or determinism guarantee if the portal ever has more than one `calculation_score`-typed property on companies.

**Fix:** Acceptable for a single-criterion MVP probe; worth a comment or an explicit "exactly one expected" check if the portal's scoring setup grows.

---

_Reviewed: 2026-08-06_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
