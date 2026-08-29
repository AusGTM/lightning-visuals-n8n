# Bare-assert safety-guard sweep (2026-08-29)

Closes the bare-`assert` safety-guard defect class across repo-root `scripts/`, following
commit `ac64353`'s WR-02 fix (`scripts/enrich_coverage_companies.py`'s
`build_coverage_patch`), which established the pattern: `assert` is stripped entirely by
CPython under `python -O` / `PYTHONOPTIMIZE=1` -- a safety guard written as a bare
`assert` does not weaken under that flag, it ceases to exist. Several of the guards in
this repo gate live PATCHes to a HubSpot portal with no rollback, or a bearer-token leak
into a committed artifact.

## Shared helper

New module: `src/guards.py` (chosen home -- every touched script already does
`from src.X import ...`). Four functions, all raising `ValueError` unconditionally
(matching `ac64353`'s precedent and the two independent `assert_payload_scope`
helpers already living in `scripts/backfill_anti_icp_flag_num.py` and
`scripts/rescore_population.py`, both of which already used `raise ValueError` --
strong precedent that this is the established convention, not a new one):

- `assert_disjoint(keys, forbidden, message)` -- payload must not contain any of a
  forbidden set. Covers Class 1.
- `assert_keys_equal(keys, expected, message)` -- payload's key set must be EXACTLY a
  given set. Covers the equality-shaped half of Class 3.
- `assert_keys_subset(keys, permitted, message)` -- payload's key set must be a subset
  of a permitted set. Covers the subset-shaped half of Class 3.
- `assert_no_secrets(text)` -- no Authorization header, bearer token value, or token
  env-var name in a serialized artifact. Covers Class 2.

**Decision: three payload-scope functions, not one.** `assert_disjoint` and
`assert_keys_equal`/`assert_keys_subset` are formally related (all three take a payload
and a reference set) but express genuinely different predicates: disjointness says "must
not contain any of these specific keys, otherwise anything goes"; equality says "must be
exactly this fixed shape, nothing more and nothing less"; subset says "must stay within
this known-safe universe, but may vary which of them it uses." Collapsing them into one
`require(mode=...)` function would trade a self-documenting call site
(`assert_disjoint(props, FORBIDDEN_PROPS, ...)`) for a mode flag a reader has to
cross-reference. Three small functions cost nothing extra and read correctly at every
call site.

Test coverage: `tests/test_guards.py` -- 19 tests, one pass/fail pair per predicate edge
case for all four functions, plus four `PYTHONOPTIMIZE=1` subprocess proofs (one per
function) reusing the pattern from `tests/test_enrich_coverage_companies.py`'s WR-02
test.

## Sites fixed

### Class 1 -- `FORBIDDEN_PROPS` disjointness guards on live-write payloads (6 sites, not 5)

All 5 given sites in `scripts/remediate_veto_companies.py`:
- `build_input_patch` (line ~368 pre-fix)
- `build_metadata_patch` (line ~433 pre-fix)
- `build_metadata_record` (line ~457 pre-fix)
- `build_component_patch` (line ~468 pre-fix)
- **Plus** the module-level `assert PINNED_COMPANY_IDS.isdisjoint(EXCLUDED_COMPANY_IDS)`
  (line 102) -- see "Borderline decision" below; this one WAS fixed, unlike the other
  borderline sites which were left alone.

**One additional site found beyond the given list, same shape, same file family:**
`scripts/fix_sfv_region.py:117`, `build_region_patch` -- `assert
FORBIDDEN_PROPS.isdisjoint(props), "build_region_patch produced a forbidden
derived-field key"`. This script imports `FORBIDDEN_PROPS` directly from
`remediate_veto_companies` and builds a live-write PATCH payload the exact same way the
5 given sites do. A full `grep -n "^\s*assert " scripts/*.py` (run before starting any
edits, to build a complete site inventory rather than trusting the given list alone)
surfaced it. Fixed identically to the other 5.

Total Class 1 sites fixed: **6** (5 given + 1 found).

### Class 2 -- `_assert_no_secrets` credential-leak guards (6 files, unchanged from spec)

All six copy-pasted-verbatim `_assert_no_secrets` bodies now delegate to
`src.guards.assert_no_secrets`, kept as thin named wrappers per the plan (so every
existing call site -- `_assert_no_secrets(text)` -- is unchanged):

- `scripts/check_schema_drift.py`
- `scripts/check_tier_null_propagation.py`
- `scripts/probe_enum_in_formula.py`
- `scripts/probe_number_floor_in_formula.py`
- `scripts/snapshot_hubspot_schema.py`
- `scripts/sweep_tier_dependents.py`

**Discovered during the sweep, not a seventh site:** `scripts/derive_orphan_candidates.py`
imports `_assert_no_secrets` directly from `check_schema_drift` (`from check_schema_drift
import (..., _assert_no_secrets, ...)`) rather than carrying its own copy. Fixing
`check_schema_drift.py`'s function fixes this import for free -- confirmed by
`import ast; ast.parse(...)` plus a live `import` smoke test of every touched module (see
"Verification" below); no separate edit was needed or made.

### Class 3 -- payload-scope guards bounding what gets written (3 sites, unchanged from spec)

- `scripts/set_named_account_score_floor.py:118` (`build_payloads`) -- now
  `assert_keys_equal`.
- `scripts/backfill_dry_run.py:769` (`build_dry_run_row`) -- now `assert_keys_subset`
  (this one is `<=`, not `==`, hence the different function).
- `scripts/probe_number_floor_in_formula.py:260` (`_patch_disposable_floor`) -- now
  `assert_keys_equal`. This file also carries a Class 2 site (its own
  `_assert_no_secrets`), fixed the same way as the other five.

## Borderline decisions

**`scripts/remediate_veto_companies.py:102` (module-level
`PINNED_COMPANY_IDS.isdisjoint(EXCLUDED_COMPANY_IDS)`): FIXED, folded into Class 1.**
Reasoning: `EXCLUDED_COMPANY_IDS` names three companies (Entain, Gravity Media, Ironman)
whose non-ANZ classification is verified correct and must never be touched by this
script's remediation. `resolve_pinned_ids` only checks `EXCLUDED_COMPANY_IDS` membership
in the branch where `company_id not in PINNED_COMPANY_IDS` -- if the two sets ever
overlapped, an excluded id sitting inside `PINNED_COMPANY_IDS` would short-circuit past
the exclusion check entirely and become write-eligible. That is the same consequence
class as WR-02 (a live, no-rollback HubSpot write reaching a record it must never touch),
just gated by a different invariant (id-set disjointness instead of key-set
disjointness). It is evaluated once, at import time, over two small literal tuples that
change rarely -- exactly the kind of check someone edits by hand and could silently break
under `-O`. Fixed via the same `assert_disjoint` helper (it is a generic two-set
disjointness check, not property-specific, so it fits without a second function).

**`scripts/check_schema_drift.py:363` (`assert len(results) >= 100`, in
`_get_live_properties`): LEFT AS `assert`.** This is a response-completeness sanity
floor on a READ (guards against a truncated/paginated GET reading as "zero drift" or
"zero properties"), not a payload-scope, forbidden-key, or secret-leak guard -- it
doesn't build an outbound PATCH body and doesn't touch credentials. It is reused
indirectly by `remediate_veto_companies.py`'s pre-write property-existence guard, so
stripping it under `-O` is not entirely free of consequence, but the failure mode if it's
silently missing is asymmetric in the SAFE direction in the realistic case: if this GET
ever did paginate/truncate to a small result set, `missing_property_names` would report
most or all checked names as "missing" and the caller REFUSES the write -- fail-closed,
not fail-open. The narrower fail-open scenario (a truncated response that happens to
still contain every name the current payload checks) requires a specific coincidence on
top of an endpoint the code's own comment says "has never been observed to paginate."
Given the task's explicit framing ("if not live-write or secret guards, leave them"),
this doesn't fit either of the two named guard shapes cleanly enough to fold in, so it
was left alone.

**`scripts/probe_org_type_migration.py:406` (`assert _property_name_ok(
_resolved_property_name())`): LEFT AS `assert`.** Traced both functions:
`_resolved_property_name()` unconditionally returns the module constant
`PROBE_PROPERTY_NAME`, and `_property_name_ok(name)` checks `name ==
PROBE_PROPERTY_NAME`. Given the current code (this script's `main()` explicitly "accepts
no arguments at all" and there is no override path anywhere), this assertion is
tautologically true on every call -- there is no live code path that can make it False
today. It is defensive scaffolding against a future refactor introducing an override,
not a guard reacting to real input. It also isn't a forbidden-key, payload-scope, or
secret-leak check. Left alone; if a future change adds a real override path, this should
be revisited.

## Explicitly out of scope -- verified, not just trusted

- `scripts/build_cloud_workflows.py` (4 sites: lines 1093, 1116, 1161, 6201) -- read the
  surrounding code. All four are dev-time, build-script config/constant-name lookups
  inside a static n8n-workflow-JSON generator (`_flag_const`, `_env_secret_expr`,
  `_write_safety_const`, and a derived-cap sanity check). No live network call, no
  HubSpot payload, no secret value ever touches these lines -- confirmed, not assumed.
- `scripts/sync_hubspot_properties.py:209,211` -- read the surrounding code. Both run
  strictly AFTER the write, re-GETting live state to confirm a just-created
  property/group actually landed. Verification, not prevention -- confirmed.

## Verification

- `.venv/bin/python -c "import ast; ast.parse(...)"` on all 10 edited scripts +
  `src/guards.py` -- no syntax errors.
- Live `import` of all 10 edited script modules (`import scripts.X`) -- all succeed,
  including the two files with module-level side effects at import time
  (`remediate_veto_companies.py`'s now-fixed disjointness check runs cleanly at import).
- Root suite: **3365 passed, 154 skipped** (baseline before this change: 3334 passed, 154
  skipped -- the +31 is exactly the new tests added: 19 in `tests/test_guards.py`, 2 in
  `tests/test_remediate_veto_companies.py`, 1 in `tests/test_fix_sfv_region.py`, 2 in
  `tests/test_set_named_account_score_floor.py` (new file), 1 in
  `tests/test_backfill_dry_run.py`, 3 in `tests/test_check_schema_drift.py`, 3 in
  `tests/test_probe_number_floor_in_formula.py` (new file)). No regressions, no skip-count
  drift.
- Plugin suite: **1725 passed, 5 skipped** -- unchanged from baseline.
- Zero live n8n/HubSpot/Anthropic/provider calls anywhere in this work: every new test is
  offline (pure functions, monkeypatched stubs, or a `python -c` subprocess with
  `PYTHONOPTIMIZE=1`). Nothing was armed; no armed script was invoked.

## Falsifiability check (required evidence)

Saved a patch of exactly the 10 edited `scripts/*.py` files
(`git diff -- <10 files> > /tmp/guard-fix.patch`), then `git checkout --` those 10 files
back to their pre-fix (HEAD) state -- reintroducing every bare `assert` this task closes
-- while leaving the new/edited test files and `src/guards.py` in place. Ran the six new
tests that exercise a REAL call site (not just the shared helper in isolation) against
that reverted state:

```
tests/test_remediate_veto_companies.py::test_forbidden_props_guard_survives_pythonoptimize_at_the_real_call_site
tests/test_fix_sfv_region.py::test_build_region_patch_guard_survives_pythonoptimize
tests/test_backfill_dry_run.py::test_build_dry_run_row_scope_guard_survives_pythonoptimize
tests/test_check_schema_drift.py::test_assert_no_secrets_wrapper_passes_clean_text
tests/test_check_schema_drift.py::test_assert_no_secrets_wrapper_raises_on_leaked_token_env_var_name
tests/test_check_schema_drift.py::test_assert_no_secrets_wrapper_survives_pythonoptimize
```

Result: **5 of 6 failed** (the 6th, `test_assert_no_secrets_wrapper_passes_clean_text`,
is a clean-input test with no defect to surface -- correctly still green). Observed
failure text, verbatim:

```
FAILED tests/test_remediate_veto_companies.py::test_forbidden_props_guard_survives_pythonoptimize_at_the_real_call_site
    AssertionError: GUARD DID NOT FIRE
    assert 'GUARD FIRED' in 'GUARD DID NOT FIRE\n'

FAILED tests/test_fix_sfv_region.py::test_build_region_patch_guard_survives_pythonoptimize
    AssertionError: GUARD DID NOT FIRE
    assert 'GUARD FIRED' in 'GUARD DID NOT FIRE\n'

FAILED tests/test_backfill_dry_run.py::test_build_dry_run_row_scope_guard_survives_pythonoptimize
    AssertionError: GUARD DID NOT FIRE
    assert 'GUARD FIRED' in 'GUARD DID NOT FIRE\n'

FAILED tests/test_check_schema_drift.py::test_assert_no_secrets_wrapper_raises_on_leaked_token_env_var_name
    AssertionError: serializer leaked the token env var name
    (an uncaught AssertionError -- not the ValueError the test's `except ValueError`
    clause was written to catch, because the pre-fix code still raises the OLD
    exception type via a bare `assert`)

FAILED tests/test_check_schema_drift.py::test_assert_no_secrets_wrapper_survives_pythonoptimize
    AssertionError: GUARD DID NOT FIRE
    assert 'GUARD FIRED' in 'GUARD DID NOT FIRE\n'
```

This is exactly the expected symptom class: under `PYTHONOPTIMIZE=1` the reverted bare
`assert` is stripped and the guarded function returns normally instead of raising
("GUARD DID NOT FIRE"); under normal execution the reverted code still raises, but as the
old `AssertionError` rather than the new `ValueError` the fixed call sites and tests
expect. Both are the defect class this task closes.

Restored the fix with `git apply /tmp/guard-fix.patch`, then re-ran the full root and
plugin suites to confirm the green state reported above (3365/154 and 1725/5) — no
`git checkout .` or other blanket reset was used at any point; only the exact 10-file
patch was applied and reverted.

## Files changed

**New:**
- `src/guards.py`
- `tests/test_guards.py`
- `tests/test_set_named_account_score_floor.py`
- `tests/test_probe_number_floor_in_formula.py`

**Modified (guard construct only -- no semantic change to any condition or message):**
- `scripts/remediate_veto_companies.py`
- `scripts/fix_sfv_region.py`
- `scripts/set_named_account_score_floor.py`
- `scripts/backfill_dry_run.py`
- `scripts/probe_number_floor_in_formula.py`
- `scripts/check_schema_drift.py`
- `scripts/check_tier_null_propagation.py`
- `scripts/probe_enum_in_formula.py`
- `scripts/snapshot_hubspot_schema.py`
- `scripts/sweep_tier_dependents.py`

**Modified (regression tests added, no other change):**
- `tests/test_remediate_veto_companies.py`
- `tests/test_fix_sfv_region.py`
- `tests/test_backfill_dry_run.py`
- `tests/test_check_schema_drift.py`

## Left unchanged, deliberately

- `scripts/build_cloud_workflows.py` (4 sites) -- dev-time config-name checks, no
  live-write/secret consequence (verified).
- `scripts/sync_hubspot_properties.py:209,211` -- post-write confirmation, not
  prevention (verified).
- `scripts/check_schema_drift.py:363` -- read-completeness sanity floor, not a
  payload-scope/forbidden-key/secret guard (evaluated, reasoning above).
- `scripts/probe_org_type_migration.py:406` -- tautological invariant given current
  code, no live consequence today, not a payload-scope/forbidden-key/secret guard
  (evaluated, reasoning above).
