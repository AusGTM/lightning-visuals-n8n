---
phase: 48-enrichment-coverage
reviewed: 2026-08-13T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - scripts/enrich_coverage_companies.py
  - scripts/build_cloud_workflows.py
  - src/taxonomy.py
  - src/web_research.py
  - config/taxonomy.yaml
  - tests/test_enrich_coverage_companies.py
  - tests/test_taxonomy_conformance.py
  - tests/test_web_research_spec.py
  - tests/test_remaining_credits_response.py
  - tests/n8n/researchErrorGateFlow.test.mjs
  - tests/n8n/parity.test.mjs
  - docs/WEB-RESEARCH-SPEC.md
  - n8n/wf_enrichment_cloud.json
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 48: Code Review Report

**Reviewed:** 2026-08-13T00:00:00Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Reviewed the Phase 48 (Enrichment Coverage) deliverables against the review priorities called
out in the brief: the live-write driver's arming/disarming/budget-refusal guards, the
coherence-flag guard's flag-not-rewrite discipline, taxonomy single-source-of-truth integrity,
test honesty in the two n8n regression suites, and enum safety on the write path.

**Every named priority checked out clean:**

- `assert_allowlist_exact()` fails closed on an empty allowlist (Trap 4), on a superset/subset
  mismatch (exact `frozenset` equality, not a subset check), on a populated `TEST_RECORD_DOMAINS`,
  and on `ALLOW_HUBSPOT_RECORD_WRITES != "true"` (execution 11858's exact silent-denial shape) —
  all four confirmed both by direct code trace and by dedicated tests
  (`tests/test_enrich_coverage_companies.py:392-425`).
- `refuse_if_over_budget()` raises `BudgetRefused` and returns `ids` unmodified in the
  within-budget case; there is no code path that truncates (`scripts/remediate_veto_companies.py:674-683`,
  exercised at `tests/test_enrich_coverage_companies.py:133-159`).
- The disarm in `run_coverage_window()` is a `finally` with no early return or `sys.exit` inside
  the `try` (`scripts/enrich_coverage_companies.py:754-809`) — unconditional, as designed. A live
  armed run against all 5 records (`.planning/phases/48-enrichment-coverage/48-ARM-RECORD.md`)
  independently confirms the window opened once and closed once.
- The client-timeout leg (`requests.exceptions.Timeout`) is caught and never retried — it falls
  straight through to reading the execution back by dispatch time, never re-POSTs
  (`scripts/enrich_coverage_companies.py:772-776`).
- `org_type_coherence_flags()` is a pure read-only function: it returns reason strings and never
  writes into `data`, confirmed by inspection and by
  `tests/test_web_research_spec.py:286-300` (`validate_research_output_incoherent_regulator_flags_but_does_not_rewrite`).
  The corrected Racing NSW value comes only from the operator-authored
  `ORG_TYPE_DECISIONS["15008671672"]["override_of"]` table entry, never from the guard.
- Org-type definitions live once in `config/taxonomy.yaml` and are rendered into both
  `src/web_research.py` prompts via `org_type_definitions_block()` — no duplicated prose; enforced
  by `tests/test_taxonomy_conformance.py::test_tx10_...` and `tests/test_web_research_spec.py`.
  (Production n8n's research prompt is honestly disclosed as NOT yet carrying these definitions —
  tracked in a pending todo and `docs/WEB-RESEARCH-SPEC.md`'s dated "Known divergence" note, not
  hidden.)
- `tests/n8n/researchErrorGateFlow.test.mjs` loads the real committed `n8n/wf_enrichment_cloud.json`
  and evaluates the gate's actual `leftValue` expression and the failure node's actual `jsCode` via
  `new Function` — it is not a hand-copied string assertion.
- `tests/n8n/parity.test.mjs`'s `coherence_flags` strip (lines 363-378) is scoped to exactly that
  one key via object destructuring (`{ coherence_flags, ...rest }`), with an explicit tripwire
  assertion in both directions (`pyRaw.every(...)` / `jsValidate.every(...)`) that fails the moment
  the JS side gains the key — any other divergence still fails the surrounding
  `assert.deepStrictEqual`.
- Enum safety on the write path: `build_coverage_patch()` raises `ValueError` before building a
  payload for any `org_type` not in `VALID_ORG_TYPES` (`scripts/enrich_coverage_companies.py:440-445`),
  so an out-of-vocabulary value never reaches a PATCH; `lv_icp_fit_score`/`lv_icp_tier`/
  `lv_anti_icp_flag`/`lv_anti_icp_reason` are asserted disjoint from every payload this module
  builds and are never written by this script (confirmed against the live payloads recorded in
  `48-ARM-RECORD.md`).

Two WARNING-level robustness/observability gaps remain, both in the highest-stakes file
(`scripts/enrich_coverage_companies.py`). Neither caused incorrect data to reach HubSpot in the
run that already executed (per `48-ARM-RECORD.md`, all 5 records completed with 0 timeouts, 0
retries), but both are latent risks for the next time this driver — or a driver copied from it —
is invoked with different ids or under real network flakiness.

## Warnings

### WR-01: `run_coverage_window`'s per-record armed loop discards the whole run's audit trail on any exception it doesn't explicitly catch

**File:** `scripts/enrich_coverage_companies.py:753-823`
**Issue:**

The loop only special-cases one failure mode — a client-side `requests.exceptions.Timeout` on
the webhook POST (lines 772-776). Every other exception raised anywhere in the loop body —
`decide_org_type()` raising `PendingResearch` or `ValueError` for a *later* id in the same call,
`patcher()` raising on a HubSpot 4xx/5xx, `poster()` raising a non-timeout `HTTPError` from
`response.raise_for_status()`, or `lister`/`finder`/`getter`/`_read_snapshot` raising a transport
error — propagates immediately out of the `for` loop. Because `results.append(record)` sits at
the *end* of each iteration, and the function's `return` statement sits *after* the loop, an
exception on iteration N discards:

1. the in-progress record for company N (whose org-type PATCH may have already been sent with
   `armed=True` — a real production write), and
2. every already-fully-processed record for companies 1..N-1 in the *same call*, including their
   real armed writes, execution ids, and settle results.

The `finally` block still disarms the n8n side unconditionally (correct — no window stays open),
but the caller gets nothing back except a bare traceback: no `results` list, no record of which
ids were written before the failure, no execution ids to cross-reference. For a driver whose own
docstring and this codebase's broader convention (`CLAUDE.md` §"Full Traceability" — "Log every
action... for auditability") treat the returned run report as the audit record of a live CRM
write, silently losing it on a mid-loop failure is a real gap.

A concrete, non-network trigger: if this driver is ever re-invoked with an id list that includes
a coverage id whose `ORG_TYPE_DECISIONS` entry hasn't been authored yet (`decide_org_type` raises
`PendingResearch`, `scripts/enrich_coverage_companies.py:403-407`), and that id is *not* first in
`ids`, every already-armed-and-written company ahead of it in the same call loses its returned
audit record the moment the loop reaches the unauthored id.

**Fix:** Wrap the per-iteration body (at minimum, everything from `patcher(...)` onward) in a
broad `try/except Exception`, record the error onto the `record` dict (e.g.
`record["error"] = repr(exc)`), `results.append(record)` regardless, and then either `break` or
re-raise a wrapping exception that still carries the partial `results` list (e.g. attach it via
`exc.partial_results = results` before re-raising, or return the partial report with a top-level
`"failed_at"` marker instead of letting the exception fully unwind). The `finally`-based disarm
does not need to change.

### WR-02: D-07's "never write derived scoring fields" guard in `build_coverage_patch` is a bare `assert`, which `python -O`/`PYTHONOPTIMIZE=1` strips

**File:** `scripts/enrich_coverage_companies.py:458-460`
**Issue:**

```python
assert FORBIDDEN_PROPS.isdisjoint(props), (
    f"{company_id!r}: build_coverage_patch produced a forbidden derived-field key"
)
```

This is the module's own stated enforcement mechanism for the project's D-07 rule ("Never PATCH
`lv_anti_icp_flag`, `lv_anti_icp_reason`, `lv_icp_fit_score`, `lv_icp_tier`" — a CRITICAL,
project-level constraint per this codebase's conventions). The module header explicitly cites
this assert as the guard: "FORBIDDEN_PROPS stays asserted disjoint from every payload
build_coverage_patch produces" (line 507-508). A bare `assert` is removed entirely when Python
runs with the `-O`/`-OO` flag or `PYTHONOPTIMIZE` set — an interpreter-level setting outside this
module's control, and one that produces no warning or error at call time; the check simply stops
existing.

Today the practical risk is low: the only field ever placed in `props` is `lv_org_type` (already
gated by a real `raise ValueError` against `VALID_ORG_TYPES` two lines above) plus the two
always-safe metadata keys, so no current code path can actually trip this assert. But it is the
sole runtime backstop against a *future* edit to `ORG_TYPE_DECISIONS`, `UNENRICHABLE_REASONS`, or
`build_coverage_patch` itself accidentally introducing one of the four forbidden keys — exactly
the class of change this codebase's own D-07 precedent (`Decide Company Action` as sole writer)
treats as the worst mistake this pipeline can make.

**Fix:** Replace the `assert` with an explicit, always-active guard:

```python
if not FORBIDDEN_PROPS.isdisjoint(props):
    raise ValueError(
        f"{company_id!r}: build_coverage_patch produced a forbidden derived-field key"
    )
```

---

_Reviewed: 2026-08-13T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
