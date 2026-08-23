---
phase: 260823-ono-metro-peak-body-override-rule-tier-atc-m
reviewed: 2026-08-23T13:50:10Z
depth: quick
files_reviewed: 13
files_reviewed_list:
  - scripts/check_schema_drift.py
  - scripts/check_tier_derived_parity.py
  - scripts/probe_enum_in_formula.py
  - scripts/probe_number_floor_in_formula.py
  - scripts/set_named_account_score_floor.py
  - src/icp_scoring.py
  - tests/scoring_fixtures.py
  - tests/test_flow_rubric_conformance.py
  - tests/test_hubspot_properties_config.py
  - tests/test_icp_named_account_floor.py
  - tests/test_tier_derived_tools.py
  - config/hubspot_properties.yaml
  - config/hubspot_flows/lv_icp_fit_score-property.after.json
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 260823-ono: Code Review Report

**Reviewed:** 2026-08-23T13:50:10Z
**Depth:** quick (targeted read of all 13 files, diffed against 6f9bed9..HEAD)
**Files Reviewed:** 13
**Status:** issues_found

## Summary

This diff retargets the metro peak-body named-account override from an unreadable
enumeration (`lv_named_account_priority=core_racing`) to a plain number property
(`lv_named_account_score_floor=60`), adds two brand-new live-write scripts
(`set_named_account_score_floor.py`, `probe_number_floor_in_formula.py`) plus one new
probe (`probe_enum_in_formula.py`), and extends `src/icp_scoring.py`'s oracle with the
floor logic. `260823-ono-PREDICTIONS.json` shows the write already executed live and
verified (all 5 targets at floor=60/tier B) before this review ran.

Write-gate discipline is strong and consistent across every script: portal-id guard before
credentials guard before the two-key `DRY_RUN=false AND ALLOW_<X>=true` gate, single-key
payload-scope asserts, independent post-write re-reads (never trusting the PATCH response
body), and careful try/finally teardown for both probes (calculated property archived
before its dependent number property, clearing loop wrapped so a mid-teardown exception
never skips the rest). `check_schema_drift.py` and `check_tier_derived_parity.py` remain
strictly read-only (no `requests.{post,patch,delete}` anywhere in either module — confirmed
by inspection). The oracle's floor semantics (string/None/zero-safe parsing, no cap,
Needs-Review guard scoped to `floor_active` rather than "did it actually raise the score")
are correctly implemented and are exercised by 8 well-targeted offline tests in
`tests/test_icp_named_account_floor.py`, including the zero-floor-is-inert and
blank-string-is-byte-identical-to-no-floor cases the task explicitly asked about.

No blockers found. Four warnings: a float-truncation divergence between the Python oracle
and the live HubSpot formula for a floor that is ever non-integer; `--execute` performing
no drift/precondition check of its own; an unhandled exception mid-`--execute`-loop; and —
the most consequential — the script's own advertised "standing tool, add a 6th named
account" workflow is provably inoperable as written (WR-04). None of these leak a write:
every failure mode found fails closed (refuses or crashes before any PATCH), which is why
none is rated a blocker, but WR-04 means the documented forward-maintenance path does not
work at all today.

## Warnings

### WR-01: `int(floor)` truncates where the live HubSpot formula does not

**File:** `src/icp_scoring.py:165`
**Issue:** `_parse_named_account_score_floor` correctly parses `lv_named_account_score_floor`
as a `float` (so "60", 60, and 60.5 all parse without raising), but the floor is then
applied as `floored_score = max(score, int(floor))` — `int()` truncates toward zero. The
live HubSpot formula this is meant to mirror
(`config/hubspot_flows/lv_icp_fit_score-property.after.json`) does not truncate at all: it
uses `max(<coalesced base>, coalesce(lv_named_account_score_floor, 0))` directly on the raw
number. For the current fixed use (`FLOOR_VALUE = 60`, an int, hardcoded in
`scripts/set_named_account_score_floor.py`) this never fires. But `lv_named_account_score_floor`
is a plain HubSpot `number` property — nothing stops an operator from entering a
non-integer value directly in the HubSpot UI (the docstring explicitly frames this property
as "the operator's standing tool ... going forward"), and doing so would make the Python
oracle (used by `tests/scoring_fixtures.py`'s parity harness and any future simulation) and
the live-deployed formula compute two different scores for the same record.
**Fix:** Drop the truncation — HubSpot returns numbers as strings but they're still exact
decimal representations; `max(score, floor)` (comparing `int` to `float` is fine in Python)
mirrors the live formula's behavior exactly:
```python
if floor_active:
    floored_score = max(score, floor)
    breakdown["components"].append({
        "signal": "named_account_score_floor", "value": floor,
        "points": floored_score - score,
    })
    score = floored_score
```
(If `score` must stay an `int` type downstream, round rather than truncate, and add a test
pinning a non-integer floor.)

### WR-02: `--execute` has no drift/precondition check of its own

**File:** `scripts/set_named_account_score_floor.py:279-300`
**Issue:** `run_plan()` re-reads the 5 targets and 2 controls live and refuses (exit 1) if
either set has drifted from `260823-ono-PREDICTIONS.json`'s baseline — this is the tool's
one substantive safety check before arming a write. `run_execute()`, however, calls
`build_payloads()` and PATCHes directly; it never calls `check_drift()` itself. Since
`--plan` and `--execute` are documented as two **separate** process invocations (per the
module docstring's "operator invocations" — a fresh `.venv/bin/python -c ...` each time),
there is a window between the operator confirming "no drift" via `--plan` and the operator
later running `--execute` in which live state could change (another script writes to one
of the 5 targets or 2 controls, a scheduled job runs, etc.) with nothing in `--execute`
itself to catch it. Every other write path in this diff (the two probes) re-verifies its
own preconditions inside the same guarded call; this is the one write path that delegates
its safety check entirely to a separate, earlier invocation. See WR-04 below — naively
adding `check_drift()` to `--execute` makes the standing-tool contract worse, not better,
until the precondition model itself is fixed.
**Fix:** Call a drift/precondition check inside `run_execute()` too (after the
portal/credentials/writes-allowed gates, before the PATCH loop), and refuse on drift there
exactly as `run_plan()` does — but see WR-04 first, since `check_drift()` as it exists today
cannot simply be reused for this without also fixing the frozen-baseline problem.

### WR-03: unhandled exception mid-`--execute`-loop aborts the remaining PATCHes silently

**File:** `scripts/set_named_account_score_floor.py:292-300`
**Issue:** `run_execute()`'s loop calls `_patch_and_verify(cid, payload)` for each of the 5
named accounts with no `try`/`except`. `_patch_and_verify` calls `patch_record(...)`, which
(per the repo's documented idiom) raises on a non-2xx response. A transient failure on, say,
the 3rd record (429, timeout, 5xx) propagates uncaught and kills the whole function —
records 4 and 5 are never attempted, and the run ends in a bare traceback rather than a
clear "3 of 5 succeeded, 2 not attempted" summary the rest of this script's `print`-based
reporting style otherwise provides.
**Fix:** Wrap the per-record call in `try`/`except`, record failures alongside successes,
and print a final summary of exactly which ids succeeded/failed/were-not-attempted:
```python
for cid, payload in payloads.items():
    print(f"\n{cid} ({NAMED_ACCOUNTS[cid]}):")
    try:
        ok = _patch_and_verify(cid, payload)
    except Exception as exc:
        print(f"  {cid}: PATCH raised {exc!r} -- not verified")
        ok = False
    all_ok = all_ok and ok
```

### WR-04: the script's advertised "standing tool" workflow is inoperable, both for the original 5 and for any 6th account

**File:** `scripts/set_named_account_score_floor.py:6-7, 81-82, 154-168, 319-321`
**Issue:** The module docstring and the `NAMED_ACCOUNTS` comment both sell this script as
the permanent, re-runnable "add a 6th named account" surface: "edit NAMED_ACCOUNTS, run
`--plan`, arm `--execute`, poll `--verify`" (lines 6-7, 81-82). Two things make that
contract false today:
1. **`--plan` is now permanently refused for the original 5.** `check_drift()` (line
   142-194) compares live state against the ONE-TIME, frozen baseline recorded in
   `260823-ono-PREDICTIONS.json`'s `targets[].baseline`, where all 5 targets carry
   `lv_named_account_score_floor: null` (line 128 of the JSON). The write already executed
   live (`260823-ono-PREDICTIONS.json`'s `actuals` block confirms all 5 now read `"60"`).
   So `(live.get(FLOOR_PROP) or None) != baseline.get(FLOOR_PROP)` (line 164) now fires for
   every one of the 5 targets on every future run — `run_plan()` prints "REFUSED -- drift
   detected" and exits 1 permanently, even though the live state is exactly what it should
   be.
2. **A 6th (or any new) account crashes instead of refusing.** Both `check_drift()` (via
   `_target_prediction`, line 128-132) and `run_verify()` (line 319-321) do
   `for cid in NAMED_ACCOUNTS: pred = _target_prediction(predictions, cid)`, and
   `_target_prediction` raises a bare `KeyError` when `cid` is not present in
   `predictions["targets"]`. `260823-ono-PREDICTIONS.json` only ever has entries for the
   original 5 — it is never regenerated. Adding a 6th id to `NAMED_ACCOUNTS` exactly as the
   comment instructs makes `--plan` and `--verify` both crash with an uncaught `KeyError`
   instead of printing a clear "no baseline recorded for this id" refusal.
Both failure modes fail closed — no write is ever leaked, since `--execute` doesn't consult
`check_drift()` at all (WR-02) — but the tool cannot actually be used the way its own
docstring instructs, for either the accounts it already covers or any future one.
**Fix:** This needs a real precondition-model decision, not a patch: either (a) treat this
as a one-shot script scoped to exactly the 5 original ids, drop the "standing tool for a
6th account" framing from the docstring/comment, and have `--plan`/`--verify` explicitly
skip or note-not-fail on any `cid` not present in `PREDICTIONS.json`; or (b) make it a real
standing tool by deriving each account's drift baseline from a per-run live read (e.g. "is
`FLOOR_PROP` currently unset on this id, yes/no") rather than a frozen one-time JSON
snapshot, and handle a missing prediction entry for `--verify`'s target/expected-value
lookup as "nothing to compare against yet" rather than a raised `KeyError`. Whichever is
chosen should land before WR-02's fix (adding a drift check to `--execute`) is applied,
since applying WR-02's fix against today's `check_drift()` would only spread the permanent
refusal to `--execute` too.

## Info

### IN-01: stale "core_racing override" terminology in a comment added by this diff

**File:** `scripts/check_tier_derived_parity.py:106`
**Issue:** The new `KNOWN_STUCK_TRANSITIONS["9604794662"]` (Perth Racing) comment ends
with "Post-write, `lv_icp_tier_derived` correctly floors to `"B"` via the core_racing
override." `core_racing` was the abandoned enum value (`lv_named_account_priority=core_racing`)
from before CP1's halt-b; this same file's own module docstring (added five lines above, in
the same diff) correctly describes the retargeted mechanism as
`lv_named_account_score_floor=60`. This one comment wasn't updated to match, and could
mislead a future reader searching for "core_racing" into thinking that enum value is still
live somewhere.
**Fix:** Reword to "via the `lv_named_account_score_floor` override" (or simply "via the
named-account floor").

### IN-02: loosened formula assertion checks formula membership, not branch placement

**File:** `tests/test_flow_rubric_conformance.py:501-507`
**Issue:** `test_fit_score_formula_leaves_org_type_score_unguarded_as_the_sentinel`'s second
assertion was deliberately relaxed from "org_type_score is never coalesced anywhere" to
"if org_type_score is coalesced anywhere, `lv_named_account_score_floor` must also appear
in the formula somewhere" — a reasonable, well-documented relaxation to allow the new floor
branch's `coalesce(org_type_score, 0)`. But the check is a flat substring test on the whole
formula string, not a structural check that the coalesced occurrence is specifically inside
the `if coalesce(lv_named_account_score_floor, 0) > 0 then ...` branch. A future edit that
accidentally coalesces `org_type_score` in the `else` branch too (silently breaking the
"never-enriched companies stay at org_type_score 0 through a bare reference" sentinel this
test exists to protect) while the formula still happens to mention
`lv_named_account_score_floor` anywhere else would pass this test undetected.
**Fix:** Not blocking for a quick task — the actual shipped formula
(`config/hubspot_flows/lv_icp_fit_score-property.after.json`) was verified by-hand against
`scripts/probe_number_floor_in_formula.py`'s `formula_f_for()` and is correct today. If this
property's formula is touched again, consider splitting the formula on `else` first and
asserting `org_type_score` is bare in the tail half specifically, rather than searching the
whole string.

### IN-03: no offline test for a negative or non-numeric floor value

**File:** `tests/test_icp_named_account_floor.py`, `src/icp_scoring.py:34-44`
**Issue:** `_parse_named_account_score_floor` and `floor_active`'s `floor > 0` guard are
written to correctly treat a negative floor (e.g. `-10`) as inert (parses fine, just never
activates) and a garbage string (e.g. `"abc"`) as "no floor" (caught by the `except
(TypeError, ValueError)`). Both branches are correct by inspection but neither is exercised
by `tests/test_icp_named_account_floor.py`, which covers blank/zero/int/string-60 but not
negative or non-numeric input.
**Fix:** Optional at quick depth — two more one-line cases would close the gap:
```python
def test_negative_floor_is_inert():
    r = score({"lv_org_type": "individual_club_team", "lv_produces_content": True,
               "lv_revenue_band": "1-5M", "lv_named_account_score_floor": -10})
    assert r.score == 35
    assert named_account_component(r) is None

def test_garbage_string_floor_parses_to_no_floor():
    r = score({"lv_org_type": "individual_club_team", "lv_produces_content": True,
               "lv_revenue_band": "1-5M", "lv_named_account_score_floor": "not-a-number"})
    assert r.score == 35
    assert named_account_component(r) is None
```

---

_Reviewed: 2026-08-23T13:50:10Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
