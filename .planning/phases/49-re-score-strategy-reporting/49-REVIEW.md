---
phase: 49-re-score-strategy-reporting
reviewed: 2026-08-13T00:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - scripts/rescore_population.py
  - scripts/backfill_seed_company_scores.py
  - scripts/build_rescore_report.py
  - scripts/gen_taxonomy_js.py
  - scripts/build_cloud_workflows.py
  - src/taxonomy.py
  - scripts/spike_tier_formula.py
  - scripts/spike_tier_formula2.py
  - tests/n8n/orgTypeDefinitionsPrompt.test.mjs
  - tests/test_rescore_population.py
  - tests/test_build_rescore_report.py
  - tests/test_rubric_change_guard.py
  - tests/test_backfill_seed_company_scores.py
  - tests/test_taxonomy_conformance.py
  - n8n/code/taxonomy.generated.js
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local_live.json
  - n8n/wf_review_decision_cloud.json
  - n8n/wf_scheduled_maintenance_cloud.json
  - tests/fixtures/companies_jscode_frozen.json
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues
---

# Phase 49: Code Review Report

**Reviewed:** 2026-08-13
**Depth:** standard
**Files Reviewed:** 20 (hand-written source + generated-artifact drift check)
**Status:** issues

## Summary

Phase 49's core deliverables — `scripts/rescore_population.py`'s exact-set population gate,
`enforce_exact_population()`, `assert_payload_scope()`'s all-five-components enforcement, the
D-06/D-07 write-gate discipline, and the org-type-definitions prompt fix — are well-built and
match the phase's own stated decisions. The two-key arm (`DRY_RUN=false` + `ALLOW_*=true`),
the refuse-rather-than-truncate contract, the never-PATCH-derived-fields guard, and the
offline test suite (99 pytest cases in the phase's own test modules + 4 more in
`tests/test_companies_factory_frozen.py` + 3 node tests, all green, no vacuous assertions
found) all hold up under adversarial reading. Re-running `scripts/gen_taxonomy_js.py` and
`scripts/build_cloud_workflows.py` reproduced every generated artifact byte-for-byte
(`git status` clean after rebuild) — no hand-editing of `n8n/wf_*.json` or
`n8n/code/taxonomy.generated.js` detected, and `tests/test_companies_factory_frozen.py`
(4/4 pass) confirms `tests/fixtures/companies_jscode_frozen.json` matches the fresh build too.

The issues below cluster in three places: the two throwaway grammar-spike scripts
(`scripts/spike_tier_formula.py`, `scripts/spike_tier_formula2.py`), which the phase itself
flagged for scrutiny; one design gap in the `HARD_CEILING_RECORDS` raise that the phase's own
"strengthening, not a relaxation" framing does not fully cover; and one refuse-rather-than-
truncate gap in the population selector itself that the module's own docstring claims is
already closed but is not.

## Critical Issues

### CR-01: Spike scripts can perform a live schema write with `DRY_RUN` left at its safe default

**File:** `scripts/spike_tier_formula.py:83` and `scripts/spike_tier_formula2.py:65`

**Issue:** Every other live-write script in this repo (`scripts/rescore_population.py`'s
`_writes_allowed()`, `scripts/backfill_seed_company_scores.py`'s `_writes_allowed()`,
`scripts/probe_scoring_recalc_latency.py`) requires **both** `DRY_RUN=false` **and** an
`ALLOW_*=true` flag before touching the network — this is the repo's own stated write-gate
idiom, restated verbatim in this phase's `<constraints>` (D-06) and in this review's own
criteria. `spike_tier_formula.py` and `spike_tier_formula2.py` check only
`ALLOW_SPIKE_PROPERTY_WRITE == "true"`; neither script reads `DRY_RUN` at all.

Concretely: an operator following the repo's own documented invocation pattern —
`ALLOW_X=true DRY_RUN=false .venv/bin/python -c "load_dotenv(); ..."` — is safe everywhere
else in this repo, because `DRY_RUN` defaults to `true` in `.env` and every other script
honours it. For these two spike scripts, `DRY_RUN`'s value is irrelevant: if
`ALLOW_SPIKE_PROPERTY_WRITE=true` is set in the shell (e.g. left over from a prior spike
session, or exported in a profile by mistake), the script creates a live company property,
PATCHes up to eight candidate `calculationFormula` values against it, and deletes it —
regardless of `DRY_RUN`. This is exactly the gate shape (`ALLOW_*` alone, no paired
`DRY_RUN` check) the project's own write-gate-integrity rule exists to catch.

The blast radius is narrower than a record write (it mutates one disposable, uniquely-named
company **property definition**, not customer data, and the `finally:` block deletes it even
on exception), which is why this is scoped as the phase's one Critical rather than a
data-loss finding — but it is a real, provable deviation from the stated two-key discipline,
on a script that performs live HubSpot API POST/PATCH/DELETE calls against the production
portal.

**Fix:**
```python
def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_SPIKE_PROPERTY_WRITE") == "true"
    return (not dry_run) and allow

def main() -> int:
    if (rc := preflight()) != 0:
        return rc
    if not _writes_allowed():
        print("DRY RUN (set DRY_RUN=false and ALLOW_SPIKE_PROPERTY_WRITE=true to run the spike).")
        ...
```
Apply the same fix to both `spike_tier_formula.py` and `spike_tier_formula2.py`.

## Warnings

### WR-01: `HARD_CEILING_RECORDS` 25→100 widens `backfill_seed_company_scores.py`'s own standalone CLI with no compensating gate

**File:** `scripts/backfill_seed_company_scores.py:93` (constant), `:220-244` (`main()`)

**Issue:** D-03's raise is correctly framed as a strengthening *for `scripts/rescore_population.py`'s
callers*, because that driver additionally requires `enforce_exact_population()` to pass —
a count-cap-only check permits any ≤100-record subset, but the new exact-set gate narrows
that to exactly the live-derived 66. That framing does not extend to
`backfill_seed_company_scores.py`'s **own** `main()`, which is still directly invocable
(`--company-id` repeated, or the default `_select_default_sample_ids()` search for *any*
company with at least one canonical `lv_*` input populated — a materially larger set than
the 66 that have ever carried a score). That path calls only `enforce_sample_cap()`; it never
calls `enforce_exact_population()` at all. Raising the shared `HARD_CEILING_RECORDS` constant
therefore doubles the maximum blast radius of this script's own entry point (25 → 100
records) with no new compensating control on that path — a genuine relaxation, not a
strengthening, for this specific caller.

No test in `tests/test_backfill_seed_company_scores.py` exercises `main()` at the new
100-record ceiling via `--company-id`, and `docs/OPERATOR-RESCORE.md` does not mention this
script's own CLI at all — it documents `rescore_population.py` exclusively. The direct
`backfill_seed_company_scores.py` CLI is effectively an orphaned, undocumented, wider-radius
write surface after this change.

**Fix:** Either (a) have `backfill_seed_company_scores.py`'s `main()` also call
`enforce_exact_population()` against `_select_default_sample_ids()`-or-`--company-id` when no
explicit override is intended, closing the same gap `rescore_population.py` closes; or (b)
split the constant — keep a small `DEFAULT_MAX_RECORDS`/`HARD_CEILING_RECORDS` pair for the
module's own standalone CLI (unchanged at 25) and give `rescore_population.py` its own,
separately-named ceiling constant so the two callers' safety bounds are not coupled through
one shared name. Document whichever choice is made in the module docstring next to the
existing D-03 comment.

### WR-02: `select_scored_population()`'s own docstring claim ("does not silently truncate") is false — `limit=100` just moves the truncation point

**File:** `scripts/rescore_population.py:105-117`

**Issue:** The docstring says: *"limit=100 so the query does not silently truncate if the
scored population grows past the current 66."* That is incorrect — `limit=100` does not
prevent truncation, it only raises the silent-truncation threshold from 66 to 100.
`search_records()` (`src/hubspot_client.py:119-128`) issues one HubSpot search POST and
returns the raw JSON with no pagination and no check of the response's `total` field against
`len(results)`. `select_scored_population()` reads only `result.get("results", [])`.

Walk the failure this leaves open: if the live scored population ever exceeds 100 (currently
66, but nothing in the code enforces that ceiling stays true), the search returns exactly 100
of them. `enforce_sample_cap()` at the (now-100) resolved ceiling **passes** against that
truncated set. `_derive_and_confirm_population()`'s second read goes through the same
truncating query, so the two reads are likely to agree with each other on the same wrong
100-of-N set, and `enforce_exact_population()` passes too — the very drift-detection gate
this phase built (D-03) cannot see a truncation that is consistent across both of its own
reads. `--execute` would then silently write components to 100 of N companies while every
log line reports "exact population," and `--snapshot` would emit `population_count: 100` as
a clean, dated census — a wrong denominator silently feeding `build_rescore_report.py`'s P2/P3
points in any future phase that re-runs this report. This is precisely the refuse-rather-than-
truncate failure mode this review was asked to weight heavily (criterion 3), sitting
underneath, not caught by, the exact-set gate this phase added to guard exactly this class of
problem.

Latent today (population is 66, well under 100), which is why this is a Warning rather than a
Critical — but the docstring's own claim that it is already handled is false, and the same
query shape (also `limit=100`, also unchecked) is shared by `scripts/run_scoring_parity.py`'s
`_select_sample_ids()` — that file is untouched this phase and out of scope for a fix here,
but any fix to this shared population-selection shape should land in both by the phase's own
"single population definition" rule (49-CONTEXT.md `<population>`).

**Fix:**
```python
def select_scored_population() -> list:
    result = search_records(
        "companies",
        [{"propertyName": "lv_icp_fit_score", "operator": "HAS_PROPERTY"}],
        ["lv_icp_fit_score"],
        limit=100,
    )
    results = result.get("results", [])
    total = result.get("total", len(results))
    if total > len(results):
        raise RuntimeError(
            f"live scored population read returned {len(results)} of {total} total -- "
            "refusing a truncated read rather than acting on a partial population. "
            "Paginate or raise the search limit."
        )
    return sorted(r["id"] for r in results)
```
Correct the docstring's "does not silently truncate" claim to describe what is actually true
today (the 66-of-100 headroom), not what the code enforces.

### WR-03: Both spike scripts hardcode a personal machine path instead of `Path(__file__).resolve().parent.parent`

**File:** `scripts/spike_tier_formula.py:25`, `scripts/spike_tier_formula2.py:17`

**Issue:**
```python
ROOT = Path("/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc")
```
Every other script in this repo (including the two these spikes are modeled on —
`probe_scoring_recalc_latency.py`, `rescore_population.py`, `backfill_seed_company_scores.py`)
derives `ROOT` from `Path(__file__).resolve().parent.parent`. The hardcoded absolute path
means these two scripts will fail (`FileNotFoundError` on `load_dotenv(ROOT / ".env")`,
`ModuleNotFoundError` on `from src.hubspot_client import hs_headers`) for any other operator
or CI environment where the repo is not checked out at that exact path — a portability
regression, and it also bakes a specific username/directory-structure into a committed file.

**Fix:**
```python
ROOT = Path(__file__).resolve().parent.parent
```
in both files, matching the rest of the repo.

### WR-04: Throwaway grammar spikes committed permanently to `scripts/`, undocumented and untested

**File:** `scripts/spike_tier_formula.py`, `scripts/spike_tier_formula2.py`

**Issue:** Both files' own docstrings describe themselves as disposable, one-shot grammar
probes ("Grammar spike: can lv_icp_tier be a calculated (derived) property?" / "Grammar spike
round 2"). Their purpose was fully discharged once `TIER-DERIVATION-SPIKE-2026-08-13.md`
captured the findings (per 49-05-SUMMARY.md). Neither script has a test, neither is
referenced from `docs/OPERATOR-RESCORE.md` or any other runbook, and (per WR-03) neither is
even portable to another machine. Combined with CR-01/WR-03, this reads as exploratory work
that was never cleaned up before being committed to the permanent `scripts/` directory
alongside the repo's actual operational tooling — a candidate for deletion or relocation to
an explicitly-scratch location now that the grammar question they were built to answer is
answered and recorded.

**Fix:** Delete both files (the finding is already captured in
`TIER-DERIVATION-SPIKE-2026-08-13.md`), or move them under a clearly-labeled
`scripts/spikes/` (or similar) directory excluded from the "operational script" expectations
(portable `ROOT`, two-key gate, test coverage) the rest of `scripts/` is held to.

## Info

### IN-01: `run_canary()` fetches the full population just to pick one record

**File:** `scripts/rescore_population.py:288-294`

**Issue:** `run_canary()` calls `_fetch_records(ids, CANONICAL_INPUT_PROPS + COMPONENT_PROPS)`
for the entire live-derived population (66 individual `get_record` calls) purely to run
`select_canary()`'s rule over them and write one record. This is functionally correct and
explicitly out of this review's performance scope, but it is worth noting as an easy later
win (e.g. a single `search_records` call requesting `lv_org_type` plus the five component
props, mirroring `select_scored_population()`'s own search shape) if the 66-call pattern is
ever felt as latency in a future, larger population.

**Fix:** Not required this phase. If revisited, replace the per-id `get_record` loop with one
`search_records` call carrying the same property list.

### IN-02: `SNAPSHOT_RECORD_PROPS` comment miscounts against the list it labels

**File:** `scripts/rescore_population.py:360-365`

**Issue:** The comment reads "The seven per-record properties a census entry carries (id is
the record id itself, not a fetched property)" directly above a 6-item `SNAPSHOT_RECORD_PROPS`
list. The code and the (passing) test `test_snapshot_records_sorted_by_id_with_seven_keys`
are both correct — a snapshot record entry has 7 total keys once `id` is added — but the
comment's placement makes it read, on first pass, as though the list below it should have
seven entries. Not a functional defect; a one-line clarity fix.

**Fix:**
```python
# The six HubSpot properties fetched per record; the census entry additionally carries the
# record's own id (not a fetched property), for seven keys total per entry.
SNAPSHOT_RECORD_PROPS = [...]
```

---

_Reviewed: 2026-08-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
