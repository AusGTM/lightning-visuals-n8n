---
phase: 40-scoring-engine-remediation-notes
reviewed: 2026-08-06T22:55:23Z
depth: standard
files_reviewed: 25
files_reviewed_list:
  - config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json
  - config/hubspot_flows/4626124224-org-type-score.after.json
  - config/hubspot_flows/4626722237-annual-revenue-score.after.json
  - config/hubspot_flows/4626722240-geography-score.after.json
  - config/hubspot_flows/gambling-score.after.json
  - config/hubspot_flows/lv_icp_fit_score-property.after.json
  - config/hubspot_flows/lv_icp_tier-property.after.json
  - config/hubspot_flows/produces-content-score.after.json
  - docs/OPERATOR-VETO-REFRESH.md
  - n8n/code/mergeCompanies.js
  - operator-claude-plugin/scripts/config_gate.py
  - operator-claude-plugin/scripts/scheduled_arm.py
  - operator-claude-plugin/tests/test_scheduled_arm.py
  - operator-claude-plugin/tests/test_status_unknown.py
  - scripts/backfill_seed_company_scores.py
  - scripts/build_cloud_workflows.py (ENRICH_DECIDE_CO_CLOUD, WRITE_SAFETY_GATE_JS, SJ-3/Execute Workflow Trigger wiring)
  - scripts/fetch_hubspot_flow.py
  - scripts/put_hubspot_flow.py
  - scripts/run_scoring_parity.py
  - src/hubspot_client.py
  - tests/fixtures/companies_jscode_frozen.json (not read — exceeds 256KB size limit; see note)
  - tests/scoring_fixtures.py
  - tests/test_backfill_seed_company_scores.py
  - tests/test_cloud_companies_branch.py
  - tests/test_enrichment_list_branch.py
  - tests/test_flow_rubric_conformance.py
  - tests/test_scoring_parity.py
findings:
  critical: 0
  warning: 4
  info: 1
  total: 5
status: issues_found
---

# Phase 40: Code Review Report

**Reviewed:** 2026-08-06T22:55:23Z
**Depth:** standard
**Files Reviewed:** 25 (24 read in full; `tests/fixtures/companies_jscode_frozen.json` exceeds the 256KB single-read limit and was not opened — it is a generated fixture snapshot, not hand-authored logic, so this is noted as a coverage gap rather than worked around)
**Status:** issues_found

## Summary

This phase remediates the four live HubSpot ICP-scoring flows (org-type/geography/
revenue/gambling/produces-content mapper flows + WF1's tier ladder), moves
`lv_anti_icp_flag`/`lv_anti_icp_reason` ownership from HubSpot-native workflows to the
n8n pipeline (`mergeCompanies.js` + `ENRICH_DECIDE_CO_CLOUD` in
`scripts/build_cloud_workflows.py`), adds flow fetch/PUT tooling, a scheduled-arm
write-window companion, a component-seeding backfill script, and a parity harness.

The core scoring logic is unusually well guarded: every mapper flow's branch-value point
table is asserted against `config/icp_scoring.yaml` by
`tests/test_flow_rubric_conformance.py` (parametrized off the live `.after.json`
archives, not a hand-copied table), the veto-derivation JS is checked character-for-
character against the oracle's reason strings, and both the backfill script and the
parity script enforce fail-closed defaults (dry-run-first, hard sample caps, a documented
"zero assertions must never look like success" guard). I did not find a defect in the
scoring arithmetic itself, the veto derivation, or the two-key write-safety gating.

What I did find: one concrete tooling gap (two live flows this phase created are
untracked by the phase's own archival script), one structural inconsistency in WF1 that
is untested for a specific race, one reporting-accuracy bug in the parity script's
human-readable verdict, and a design inconsistency across the mapper flows' enrollment
triggers. None of these cause incorrect canonical data to be written; they degrade
operational visibility and future-maintainability.

## Warnings

### WR-01: `fetch_hubspot_flow.py`'s `FLOW_SLUGS` map omits the two flows 40-04 itself created

**File:** `scripts/fetch_hubspot_flow.py:44-49`
**Issue:** `FLOW_SLUGS` hard-codes exactly four flow ids (org-type, geography,
annual-revenue, WF1). Plan 40-04 subsequently created and enabled two more live
Automation v4 flows — `4634822079` "Update Produces Content Score" and `4634822085`
"Update Gambling Score" (confirmed via `.planning/phases/40-scoring-engine-
remediation-notes/40-04-SUMMARY.md:15-16` and `PORTAL-FACTS.md:212-213`) — but neither
id was ever added to this map. `main()`'s default (`args.flow_id or
list(FLOW_SLUGS.keys())`) is what every documented invocation in this repo uses (the
module's own docstring example enumerates only the original four ids), so a future
re-archive of "every scoring flow" via this tool's default path silently skips both
new flows every time.

This is not speculative: `config/hubspot_flows/gambling-score.after.json` and
`config/hubspot_flows/produces-content-score.after.json` don't even follow this
script's own `{flow_id}-{slug}.{label}.json` naming convention (`archive_flow()`
always prefixes the flow id) — their filenames prove they were captured through some
other, non-reproducible path, not this tool. There is also no corresponding
`.before.json` for either, unlike all four original flows, so there is no pre-edit
snapshot to diff a future change against.

**Fix:**
```python
FLOW_SLUGS = {
    "4626124224": "org-type-score",
    "4626722240": "geography-score",
    "4626722237": "annual-revenue-score",
    "4625147345": "wf1-set-icp-tier",
    "4634822079": "produces-content-score",
    "4634822085": "gambling-score",
}
```
And re-run `fetch_hubspot_flow.py` once (label `after`, or `before` if a fresh pre-edit
baseline is wanted) so both flows get a properly-named, reproducibly-generated archive.

### WR-02: WF1's score-ladder branch (action `"3"`) has no `defaultBranch`, unlike every sibling branch action in this phase, and the blank-score race it implies is untested

**File:** `config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json:43-170`
**Issue:** Action `"2"` (the veto check) has a `defaultBranch` (→ action `"3"`).
Action `"1"` in `4626124224-org-type-score.after.json`, action `"1"` in
`4626722240-geography-score.after.json`, and action `"1"` in
`4626722237-annual-revenue-score.after.json` all have a `defaultBranch` that scores 0
for the unmatched/blank case. Action `"3"` here — the four-way score ladder
(`>=70`/`[40,69]`/`[15,39]`/`<15`) — is the only `LIST_BRANCH` action across all six
reviewed flows with **no** `defaultBranch`.

Numerically the four branches cover every *known* real number, so the gap only bites
when `lv_icp_fit_score` is genuinely unset. That is a real, reachable state: WF1's own
enrollment criteria fire on **either** `lv_anti_icp_flag` **or** `lv_icp_fit_score`
becoming known (`test_wf1_enrollment_includes_score_and_veto_flag`), and the n8n
pipeline writes `lv_anti_icp_flag`/`lv_anti_icp_reason` in the *same* PATCH as the
canonical inputs while the five component-score mapper flows (which the calculated
`lv_icp_fit_score` formula depends on, and which blank the whole sum if any one term is
null — confirmed by `scripts/backfill_seed_company_scores.py`'s own docstring) fire as
*separate*, asynchronously-triggered workflows. If WF1 evaluates on the flag-known
trigger before all five mapper flows have finished (plausible on a company's first-ever
enrichment, or immediately post-backfill), it falls through action `2`'s default into
action `3` with a blank score, matches none of the four branches, and — with no
`defaultBranch` — writes nothing this pass. The state is very likely eventually correct
once the score itself becomes known and re-fires WF1, so this is not a wrong-answer
defect, but it is untested: no offline (`tests/test_flow_rubric_conformance.py`) or live
(`tests/test_scoring_parity.py`) test exercises a blank `lv_icp_fit_score` reaching
action `3`, so this behavior is currently assumed benign rather than proven.

**Fix:** Either add a `defaultBranch` on action `3` that leaves `lv_icp_tier` untouched
by routing to a no-op terminal (documenting the intent explicitly instead of relying on
HubSpot's fall-through-with-no-branch behavior), or add a regression test that drives a
disposable company through exactly this ordering (write the veto flag before any
component score exists) and asserts `lv_icp_tier` is not left in a stale/incorrect
state once the components do land.

### WR-03: `run_scoring_parity.py`'s verdict string understates the sample size when a read fails alongside successes

**File:** `scripts/run_scoring_parity.py:120-201`
**Issue:** In `build_report()`, a company whose `fetch_fn` raises is appended to
`mismatches` and `real_findings` but **not** to `comparisons` (the `continue` at line
134 skips the `comparisons.append(record)` at line 165, which only runs for the
success path). `assertions_executed = len(comparisons)` (line 167) therefore excludes
every exception row. When at least one company in the sample raises and at least one
succeeds, the verdict message at line 176-180 —
`f"FAIL: {len(real_findings)} of {assertions_executed} sampled companies diverge..."`
— reports a denominator that has already excluded the very row contributing to the
numerator. E.g. sample of 3, 1 fetch raises, 2 match perfectly: `real_findings=1`,
`assertions_executed=2`, verdict reads "FAIL: 1 of 2 sampled companies diverge", when
the true picture is "1 of 3 sampled companies could not even be checked; the other 2
matched." The `exit_code` is still correctly non-zero (this is a reporting-accuracy bug,
not a false-green), but an operator scanning this cron-produced verdict string would
undercount how many companies were actually in the attempted sample.

**Fix:**
```python
verdict = (
    f"FAIL: {len(real_findings)} of {len(sample_ids)} sampled companies "
    "diverge from the oracle or could not be checked (not the documented Needs "
    "Review divergence)."
)
```
(replace `assertions_executed` with `len(sample_ids)` in this one message, or state
both numbers explicitly — "assertions_executed=2 (1 of 3 sampled companies failed to
fetch)").

### WR-04: Two of the five component mapper flows enroll on `createdate`, three do not — an unexplained, untested inconsistency

**File:** `config/hubspot_flows/gambling-score.after.json:54-116`,
`config/hubspot_flows/produces-content-score.after.json:54-116` vs.
`config/hubspot_flows/4626124224-org-type-score.after.json:214-248`,
`config/hubspot_flows/4626722240-geography-score.after.json:77-111`,
`config/hubspot_flows/4626722237-annual-revenue-score.after.json:435-469`
**Issue:** `Update Gambling Score` and `Update Produces Content Score` both enroll on
`createdate IS_KNOWN` **in addition to** their own property change (so every newly
created company gets `gambling_score`/`produces_content_score` stamped to 0
immediately). `Update Score Based on Org Type`, `Geography Score`, and `Annual Revenue
Score` enroll **only** on their own `lv_*` property changing — a brand-new company gets
no `org_type_score`/`geography_score`/`annual_revenue_score` until enrichment actually
sets those inputs. Since the calculated `lv_icp_fit_score` formula blanks entirely if
*any* referenced component term is null, this asymmetry is currently harmless (the
overall score stays blank regardless of which 2 of the 5 terms are pre-seeded), but
it's an unexplained inconsistency in a phase that otherwise treats every mapper flow as
a byte-identical sibling (see `test_flow_rubric_conformance.py`'s shared extractors).
If a future change ever makes the formula tolerant of a subset of blank terms (e.g.
`SUM` instead of an implicit-null-propagating expression), this asymmetry would start
mattering silently.

## Info

### IN-01: `tests/fixtures/companies_jscode_frozen.json` was not read directly (314.8KB, exceeds single-read limit) — verified via `git diff` instead

**File:** `tests/fixtures/companies_jscode_frozen.json`
**Issue:** This fixture is a frozen snapshot of several built jsCode node bodies (used to catch accidental drift in the built workflow's Code nodes) and could not be opened in one call under this review's tooling limits. As a substitute, `git diff 0b8d6a0^..HEAD -- tests/fixtures/companies_jscode_frozen.json` was run: exactly 10 of the fixture's JSON string values changed (whole-blob replacements, since each value is one long jsCode string and any change anywhere in it diffs as a full replacement), consistent with `mergeCompanies.js`'s reviewed 12-line diff propagating into every jsCode blob that inlines it via `inline()`. No content in the diff was inconsistent with the reviewed `mergeCompanies.js` change. This is a lighter-weight check than a byte-for-byte read, not a substitute for one.
**Fix:** Not applicable — flagging the gap for the record; re-run this review with an offset/limit read on this file if stronger assurance than the `git diff` spot-check is needed.

---

_Reviewed: 2026-08-06T22:55:23Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
