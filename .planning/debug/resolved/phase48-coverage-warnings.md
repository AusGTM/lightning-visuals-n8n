---
status: resolved
trigger: "The two Phase 48 code-review WARNINGs left unfixed — WR-01 (run_coverage_window discards the run's partial audit trail on an unhandled exception) and WR-02 (D-07's never-write-derived-scoring-fields guard is a bare assert, stripped under python -O)"
created: 2026-08-29
updated: 2026-08-29
resolution: fixed (WR-01 + WR-02), class swept
---

# Debug: Phase 48 coverage-script warnings (WR-01, WR-02)

## Symptoms

Both are **latent robustness gaps in the same file**, `scripts/enrich_coverage_companies.py`
(repo root `scripts/`, NOT the plugin). Both were found by the Phase 48 code review, disclosed
rather than fixed, and carried forward. Neither has ever manifested in a real run.

### WR-02 — the D-07 guard is a bare `assert`

**Source:** `.planning/phases/48-enrichment-coverage/48-REVIEW.md:133`

D-07's "never write derived scoring fields" guard in `build_coverage_patch`
(`scripts/enrich_coverage_companies.py`, around lines 507-508) is a bare `assert`.

**Expected:** the guard is a hard, always-present safety check. D-07 is a live-write safety
constraint — it is what stops the coverage script from PATCHing derived scoring fields onto real
HubSpot company records.

**Actual:** `assert` statements are removed entirely by the CPython compiler under `python -O`
or `PYTHONOPTIMIZE=1`. Under either, the guard does not merely weaken — it ceases to exist, and
the script would be free to write exactly the fields D-07 forbids.

**Why it matters more than a normal assert-vs-raise nit:** the thing on the other side of this
guard is a live write to a HubSpot portal with ~700 reachable company records and no rollback.

### WR-01 — the armed loop discards the run's audit trail

**Source:** `.planning/phases/48-enrichment-coverage/48-REVIEW.md:93` and
`48-VERIFICATION.md:104`

`run_coverage_window`'s per-record loop (`scripts/enrich_coverage_companies.py:753-823`)
discards the whole run's partial audit trail on any exception it does not explicitly catch.
Only a client-side `Timeout` is special-cased.

**Expected:** a run that fails partway still leaves behind the audit trail for the records it
already processed. This is an ARMED loop — it makes real writes — so the record of what it
wrote before it died is exactly the thing you need most when it dies.

**Actual:** any unanticipated exception propagates and takes the whole run's partial audit trail
with it. You lose the record of writes that actually happened.

### Error messages

None. Neither has ever fired. WR-01 did not manifest in the Phase 48 run that executed
(`48-ARM-RECORD.md`: 0 exceptions, 0 timeouts, 0 retries across all 5 records). WR-02 requires
someone to run the script under `-O` / `PYTHONOPTIMIZE=1`, which nothing currently does.

### Timeline

Both introduced with the Phase 48 coverage script and identified by that phase's own code review
(2026-08-13). Explicitly disclosed and accepted at the time as "latent risk for a future
re-invocation with different ids, not a defect in this phase's delivered outcome"
(`48-VERIFICATION.md:104`). Never fixed.

### Reproduction

Neither reproduces in normal operation — that is the nature of both. Demonstrable instead:
- **WR-02:** compile/run the guard's module under `python -O` and observe the `assert` is gone
  (`python -O -c "assert False"` exits 0). Do this on a scratch reproduction, NOT by invoking
  the real coverage script.
- **WR-01:** inject an exception type the loop does not catch into a stubbed per-record call and
  observe the partial audit trail is lost. Stubbed only — never against live HubSpot.

## Current Focus

hypothesis: confirmed and fixed (see Resolution). Both warnings were exactly as
  48-REVIEW.md described; no drift found beyond the line-number note in Evidence below.
test: fixed both, added one regression test per warning, proved each test fails on the
  pre-fix code (git stash of the script fix only, tests rerun red, stash popped back) and
  passes on the fix; full root suite rerun for regressions.
expecting: n/a — investigation and fix are done; awaiting human confirmation before
  archiving.
next_action: awaiting operator confirmation (checkpoint below), including a disposition
  decision on the 5 sibling bare-assert guards found out of scope (see Evidence).

```yaml
reasoning_checkpoint:
  hypothesis: >
    WR-01: run_coverage_window's per-record loop only special-cases
    requests.exceptions.Timeout; any other exception (decide_org_type's PendingResearch
    for a later id, a HubSpot 4xx/5xx from patcher/poster, a transport error from
    lister/finder/getter/_read_snapshot) propagates past `results.append(record)` and the
    function's `return`, discarding every already-processed record's audit trail in the
    same call. WR-02: build_coverage_patch's D-07 forbidden-derived-field guard is a bare
    `assert`, which CPython strips entirely under python -O / PYTHONOPTIMIZE=1, so the
    guard would silently cease to exist under that interpreter flag.
  confirming_evidence:
    - "Direct read of scripts/enrich_coverage_companies.py:783-799 (pre-fix): `results.append(record)`
      sits at the end of the loop body and the `return` sits after the loop; nothing
      appends a partial record when an exception is raised before that line."
    - "Direct read of scripts/enrich_coverage_companies.py:458-460 (pre-fix): bare
      `assert FORBIDDEN_PROPS.isdisjoint(props), (...)`; `python -O -c \"assert False\"`
      exits 0, confirming assert-stripping behavior generically."
    - "48-REVIEW.md:93-168 (2026-08-13) independently found and described both, with the
      exact fix WR-02 uses and the general shape WR-01 uses."
  falsification_test: >
    Run the two new regression tests against the pre-fix code. If they pass unmodified,
    the warnings are not real / already mitigated.
  fix_rationale: >
    WR-02: replace `assert` with `if not ...: raise ValueError(...)` — same message,
    unconditionally active regardless of interpreter optimize level (matches
    48-REVIEW.md's own proposed fix verbatim). WR-01: wrap each iteration's full body in
    try/except Exception (not an enumerated list of types — an enumerated list reproduces
    the same bug with a longer list), tag the in-flight record with `error` and append it
    to `results` before re-raising a new `CoverageWindowFailed(exc, partial_results)`
    chained via `raise ... from exc` so the underlying exception is never swallowed. The
    outer `finally` (unconditional disarm, D-48-01) is untouched — the new try/except
    lives entirely inside the existing `try:` block above it.
  blind_spots: >
    Did not exercise either fix against a *live* HubSpot/n8n call (forbidden by this
    session's constraints) — verification is entirely via injected stub exceptions and a
    subprocess-level PYTHONOPTIMIZE=1 check. Did not fix the 5 sibling bare
    `assert FORBIDDEN_PROPS.isdisjoint(...)` guards found in
    scripts/remediate_veto_companies.py (lines 368, 433, 457, 468) and
    scripts/fix_sfv_region.py (line 117) — same defect class, explicitly out of this
    session's scope fence (ONLY scripts/enrich_coverage_companies.py). Flagged, not fixed.
  candidate_causes:
    - "code: WR-02's guard used the wrong Python construct (`assert` instead of an
      explicit `raise`) for an unconditional safety check — a code-category defect."
    - "code: WR-01's loop only special-cased one exception type instead of structuring the
      whole iteration to preserve partial state under an outer catch-all — also
      code-category, but a distinct root cause (control-flow shape, not construct choice)."
  and_gate: >
    No. WR-01 and WR-02 are two independent findings in the same file, each sufficient on
    its own to explain its own symptom; neither requires the other to be present. Fixed
    independently, verified independently.
```

## Evidence

- timestamp: 2026-08-29 (orchestrator, pre-session)
  finding: both warnings located and still present as described.
  `.planning/phases/48-enrichment-coverage/48-REVIEW.md:93` (WR-01, cites
  `scripts/enrich_coverage_companies.py:753-823`) and `:133` (WR-02, cites `build_coverage_patch`
  around 507-508). `48-VERIFICATION.md:104` records the accept-and-disclose decision.

- timestamp: 2026-08-29
  checked: `scripts/enrich_coverage_companies.py` lines 435-461 (`build_coverage_patch`)
    and 693-823 (`run_coverage_window`), plus `48-REVIEW.md` in full.
  found: both warnings confirmed present and accurately described, with one small
    line-number note — WR-02's bare `assert` itself sits at lines 458-460 (matching
    48-REVIEW.md's citation exactly); the debug file's "around lines 507-508" pointed at
    a *comment* referencing the assert (`# FORBIDDEN_PROPS stays asserted disjoint...`),
    not the assert statement itself. WR-01's loop matched 48-REVIEW.md's description
    exactly at 753-799 (only `requests.exceptions.Timeout` special-cased).
  implication: no drift since Phase 48 beyond that one comment/code line-number
    distinction; safe to fix both as described.

- timestamp: 2026-08-29
  checked: `grep -rn "assert FORBIDDEN_PROPS.isdisjoint" scripts/`
  found: 5 more bare-assert guards of the identical WR-02 shape exist outside this
    session's scope fence: `scripts/remediate_veto_companies.py:368` (`build_input_patch`),
    `:433` (`build_metadata_patch`), `:457` (`build_metadata_record`), `:468`
    (`build_component_patch`), and `scripts/fix_sfv_region.py:117` (`build_region_patch`).
    `FORBIDDEN_PROPS` itself is defined in `remediate_veto_companies.py:116` and imported
    into `enrich_coverage_companies.py`.
  implication: this is the same defect class guarding the same kind of live write
    (D-07/forbidden-derived-field safety) in 5 more places. Explicitly out of scope per
    this session's scope fence ("ONLY WR-01 and WR-02 in
    scripts/enrich_coverage_companies.py") — flagged for a separate session/decision, not
    fixed here.

- timestamp: 2026-08-29
  checked: whether `run_coverage_window` / `enrich_coverage_companies.py` is imported by
    `operator-claude-plugin/` (release-hygiene rule applicability check).
  found: `grep -rl "enrich_coverage_companies" operator-claude-plugin/` returns no matches.
  implication: this fix does not touch plugin surface; the plugin.json
    version-bump/CHANGELOG rule does not apply to this commit.

- timestamp: 2026-08-29
  checked: fix verification — applied both fixes, added
    `test_wr02_forbidden_props_guard_survives_pythonoptimize` (subprocess with
    `PYTHONOPTIMIZE=1`, forces the forbidden-prop branch by monkeypatching
    `FORBIDDEN_PROPS`, asserts `ValueError` fires) and
    `test_wr01_unanticipated_exception_preserves_partial_audit_trail` (injects a bare
    `RuntimeError` — not `Timeout` — into a stubbed `patcher` on the 2nd of 2 ids, asserts
    `CoverageWindowFailed.partial_results` holds a complete record for id 1 and an
    `error`-tagged record for id 2, and disarm still ran).
  found: both new tests pass against the fixed code (43/43 in
    `tests/test_enrich_coverage_companies.py`). Reverted the fix only (`git stash push --
    scripts/enrich_coverage_companies.py`, keeping the new tests) and reran with `-k "wr01
    or wr02"`: both failed exactly as expected — WR-02 printed "GUARD DID NOT FIRE" under
    `-O`, WR-01 raised `AttributeError: module ... has no attribute 'CoverageWindowFailed'`
    (bare RuntimeError would otherwise have propagated unwrapped). Popped the stash to
    restore the fix; reran full file (43/43) and full root suite (`3334 passed, 154
    skipped` vs. the stated baseline of `3332 passed / 154 skipped` — delta is exactly the
    2 new tests, no regressions).
  implication: both tests are proven to pin their respective fixes, not just pass
    coincidentally.

## Eliminated

(none yet)

## Resolution

root_cause: |
  WR-01: `run_coverage_window`'s per-record loop special-cased exactly one exception type
  (`requests.exceptions.Timeout`) and appended to `results` only at the very end of each
  iteration, after the return, so any other exception (a later id's `PendingResearch`, a
  HubSpot 4xx/5xx, a transport error from lister/finder/getter/_read_snapshot) propagated
  bare and discarded the whole call's audit trail, including already-completed records for
  ids ahead of the failure.
  WR-02: D-07's "never write derived scoring fields" check in `build_coverage_patch` was a
  bare `assert`, which CPython removes entirely under `python -O` / `PYTHONOPTIMIZE=1` --
  the guard would silently cease to exist under that interpreter flag with no warning.
fix: |
  WR-02: replaced the bare `assert FORBIDDEN_PROPS.isdisjoint(props), (...)` with an
  unconditional `if not FORBIDDEN_PROPS.isdisjoint(props): raise ValueError(...)` carrying
  the same message -- fires regardless of interpreter optimize level. Updated the stale
  header comment that described the old assert-based mechanism.
  WR-01: added a `CoverageWindowFailed(Exception)` class carrying `.original` (the real
  exception, also chained via `__cause__`) and `.partial_results` (every record fully
  processed before the failure, plus a best-effort `error`-tagged entry for the record in
  flight). Wrapped each loop iteration's full body (from `decide_org_type` through the
  armed post/settle/read block) in `try/except Exception` -- not an enumerated list of
  types -- that tags and appends the in-flight record's partial state before re-raising
  `CoverageWindowFailed`. The outer `finally` block (unconditional n8n-side disarm, D-48-01)
  is untouched; the new try/except lives entirely inside the pre-existing outer `try:`.
verification: |
  Added two regression tests to `tests/test_enrich_coverage_companies.py`:
  `test_wr02_forbidden_props_guard_survives_pythonoptimize` (subprocess run with
  `PYTHONOPTIMIZE=1`, forces the forbidden-prop branch, asserts `ValueError` fires) and
  `test_wr01_unanticipated_exception_preserves_partial_audit_trail` (injects an
  un-special-cased `RuntimeError` into a stubbed `patcher` mid-run, asserts
  `CoverageWindowFailed.partial_results` preserves the completed first record and tags the
  failed second record, and that disarm still ran unconditionally).
  Both tests were proven to fail on the pre-fix code (git-stashed the script change only,
  reran, both failed with the exact pre-fix symptom) and pass on the fixed code. Full file
  suite: 43/43 passed. Full root suite: 3334 passed, 154 skipped (baseline 3332/154 + the 2
  new tests, zero regressions). No live n8n/HubSpot/Anthropic calls made at any point --
  all verification via stubs, monkeypatches, and one subprocess invocation of the module in
  isolation.
files_changed:
  - scripts/enrich_coverage_companies.py
  - tests/test_enrich_coverage_companies.py


## OPERATOR RULING AND CLASS SWEEP — 2026-08-29 (checkpoint answered)

The checkpoint was answered "confirmed fixed", and the out-of-scope sibling finding was
escalated rather than deferred.

**The sibling class was wider than this session reported.** The session flagged 5 sibling
bare-`assert` guards. An orchestrator sweep of all of `scripts/` found ~35 bare asserts across
14 files in distinct stakes classes, including ~18 CREDENTIAL-LEAK guards
(`assert "Authorization" not in text`, `assert token not in text`,
`assert "HUBSPOT_PRIVATE_APP_TOKEN" not in text`) copy-pasted verbatim across 6 files — under
`-O` a serialized artifact could carry the live bearer token. That class is arguably higher
stakes than WR-02 itself.

**Operator ruling: fix all safety-critical classes now, via one shared helper.** Executed in
commits `196b989` (helper + Class 2 secrets), `2f897fc` (Class 1 disjointness), `c205503`
(Class 3 payload scope), `f531026` (record). New module `src/guards.py` carries four
unconditional `ValueError`-raising helpers. 14 sites fixed — 2 more than the brief listed, both
found by the executor's own grep sweep and folded in with reasoning.

Record: `.planning/debug/resolved/bare-assert-guard-sweep.md`.

**Verified by the orchestrator independently:** root suite 3365 passed / 154 skipped, plugin
suite 1725 / 5, and zero residual bare asserts remain in any of the three fixed classes
(`assert FORBIDDEN_PROPS`, `assert "Authorization"`, `assert set(payload`) anywhere in
`scripts/`.
