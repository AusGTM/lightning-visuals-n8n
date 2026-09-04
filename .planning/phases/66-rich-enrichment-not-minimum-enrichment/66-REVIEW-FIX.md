---
phase: 66-rich-enrichment-not-minimum-enrichment
fixed_at: 2026-09-04T08:44:20Z
review_path: .planning/phases/66-rich-enrichment-not-minimum-enrichment/66-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 66: Code Review Fix Report

**Fixed at:** 2026-09-04T08:44:20Z
**Source review:** `.planning/phases/66-rich-enrichment-not-minimum-enrichment/66-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (CR-01, WR-01, WR-02, WR-03)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: `_contactability_for_row` raised `TypeError` on a non-string/unhashable `contactability` value

**Files modified:** `operator-claude-plugin/scripts/report_enrichment.py`,
`operator-claude-plugin/tests/test_report_enrichment.py`
**Commit:** `a637fe6`
**Applied fix:** Added an `isinstance(value, str)` guard before the `value in
_CONTACTABILITY_STATES` set-membership test, matching `_match_info_for_row`'s existing
defensive style. A dict/list `contactability` value now returns `None` instead of raising,
restoring `build_sync_report`/`build_enrichment_report`'s documented never-raises contract.
Added 3 regression tests: `_build_row_report` with a dict value, with a list value, and
`build_sync_report` end-to-end with a list value.

### WR-01 / WR-02 / WR-03: the widened companies/contacts gate REQUIRED lists were reused by search nodes whose fetch lists were never widened to match, and the phase's own audit test only ever checked one of the (at least) four search-node configurations that embed the shared gate code

**Files modified:** `scripts/build_cloud_workflows.py`, `tests/n8n/fieldProducerMatrix.test.mjs`,
`tests/n8n/sjPredicates.test.mjs`, `n8n/wf_enrichment_cloud.json` (comment-only jsCode delta),
`n8n/wf_enrichment_local_live.json`, `n8n/wf_scheduled_maintenance_cloud.json`
**Commit:** `6b3edf2` (WR-01/WR-02/WR-03 fix) + a follow-up commit adding the SJ-2 REQUIRED
snapshot-pin test and the "why not derived" comments named below
**Commit status:** CR-01 = `fixed`. WR-01 = `fixed`. WR-03 = `fixed`. **WR-02 =
`fixed: requires human verification`** — WR-02's own Fix section offered two options
(widen SJ-2's fetch to match the 13-field gate, or give SJ-2 its own narrower REQUIRED);
this fix chose narrowing, a behavioral/design decision that diverges from the orchestrator's
initial lean toward "derive the fetch list from the widened gate." The reasoning is laid out
below — the operator should confirm SJ-2 staying a 2-field ICP-classification staleness gate
(rather than growing into a 13-field companies-completeness gate, same as the other two
lanes) is the intended scope for SJ-2's job before this ships to production.

These three findings are one root cause with two manifestations and one missing guard, fixed
together rather than as three separate patches, per the orchestrator's analysis.

**WR-03 fixed first (test coverage gap).** `fieldProducerMatrix.test.mjs`'s fetch-gate
assertion was hardcoded to `n8n/wf_enrichment_cloud.json` only. Added a second, fully
generic assertion (`"fetch gate (WR-03): ..."`) that:
- Enumerates every `n8n/wf_*.json` file via `fs.readdirSync`.
- Finds every "gate node" in each file as any node whose `jsCode` contains `const REQUIRED`
  (no hardcoded node names).
- Classifies each gate's lane (contacts/companies) by checking whether its `REQUIRED`
  array is a subset of `config/field_policy.yaml`'s contacts or companies key set (no
  hardcoded constant names).
- Walks backward through `wf.connections` from each gate node to find the nearest
  upstream `httpRequest`-type node(s) feeding it — the actual HubSpot search/fetch call
  — stopping recursion at the first one found on each path.
- Asserts every `REQUIRED` field appears in the concatenated `parameters` text of those
  upstream nodes.
- Separately asserts the exact, named list of gate nodes with NO upstream `httpRequest`
  node at all (a mock-fed lane) — currently exactly one:
  `wf_enrichment_local.json:Enrichment Gate` — so a future mock-lane-grows-a-real-search
  change, or a genuinely orphaned gate, fails loudly instead of silently passing.

Run against the pre-fix tree (verified by `git stash`-ing the WR-01/WR-02 source/JSON
changes and re-running just this test), the RED failure list was **exactly** the two
feeders WR-01/WR-02 already named, and nothing else — confirming full scope:
```
wf_enrichment_local_live.json:Enrichment Gate (contacts): REQUIRED but not fetched: city, country, hs_country_region_code, hs_state_code, lv_linkedin_url, lv_persona_group, state
wf_enrichment_local_live.json:Company Gate (companies): REQUIRED but not fetched: lv_revenue_band, lv_employee_band, lv_country_region_normalized, country, city, lv_sponsorship_reliant
wf_scheduled_maintenance_cloud.json:SJ-2 Company Gate (companies): REQUIRED but not fetched: industry, numberofemployees, lv_revenue_band, lv_employee_band, lv_country_region_normalized, country, city, lv_content_type, lv_sponsorship_reliant, lv_is_hardware_vendor, lv_is_gambling_operator
```
The contacts-side scheduled path was checked separately: `grep -n 'code_node(.*ENRICH_GATE'
scripts/build_cloud_workflows.py` finds only 2 call sites (`build_enrichment_local_live()`,
`build_enrichment_cloud()`) — no SJ-1-equivalent scheduled job reuses `ENRICH_GATE`, so no
contacts-side over-triggering write path exists.

**WR-01 fixed by widening the fetch (both lanes are genuine completeness-chase previews).**
`HS_SEARCH_BODY_EXPR` and `HS_CO_SEARCH_BODY_EXPR` (both `build_enrichment_local_live()`
only) were widened to request the same fields `ENRICH_CONTACT_SEARCH_PROPERTIES_CSV` /
`ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` already fetch for the CLOUD lane:
- Contacts (+7): `city`, `state`, `country`, `hs_state_code`, `hs_country_region_code`,
  `lv_linkedin_url`, `lv_persona_group`.
- Companies (+6): `lv_revenue_band`, `lv_employee_band`, `lv_country_region_normalized`,
  `country`, `city`, `lv_sponsorship_reliant`.

`wf_enrichment_local_live.json` has no HubSpot write node (confirmed again post-fix — the
review's own finding that this is a preview-only lane, not an active write path, still
holds), so this closes the wrong-preview exposure the review named without arming anything.

**WR-02 fixed by narrowing the gate, not widening the fetch (SJ-2's job is different in
kind from the other two lanes).** SJ-2's monthly stale-refresh job (CLAUDE.md §19.5) is
narrowly about `lv_org_type`/`lv_produces_content` staleness, not full-record completeness.
Widening `SJ-2 Search`'s fetch to the full 13-field companies list (mirroring WR-01's fix)
would only relocate the bug: SJ-2 would then gate on completeness of 11 fields unrelated to
its documented job, and a record missing one of those (e.g. a producer-less companies
signal, or one Claude web research simply hasn't reached yet) would re-trigger every month
forever — the same class of over-triggering this fix exists to remove, just via a different
missing field.

Instead, added a new `SJ2_CO_GATE` constant (same `inline(...)` shared modules as
`ENRICH_CO_GATE`, same wrapper shape including the request-level recompute-intent
try/catch for consistency, kept even though it is always a no-op on this scheduled lane)
carrying `REQUIRED = ["lv_org_type", "lv_produces_content"]` and the original 2-entry TTL
`POLICY` — exactly SJ-2's pre-66-02 shape. `SJ-2 Search (stale refresh)`'s existing
6-field fetch already covers this narrower `REQUIRED` in full, so no fetch-list change was
needed for SJ-2 itself. `SJ-2 Company Gate` now builds from `SJ2_CO_GATE` instead of the
shared, now-13-field `ENRICH_CO_GATE`. Comments referencing the old "reused, UNMODIFIED
Company Gate" framing (in the SJ-2 node-build code and in `ENRICH_CO_GATE`'s own
`RECOMPUTE_REQUESTED` comment, which used to name SJ-2 as a third consumer) were updated to
reflect the split. `SJ-2 Set Requested` — the one write path among these three findings
that is real today, per the review (`lv_enrichment_requested=true`, gated behind the
lane's own write-safety gate before any live PATCH) — is now gated correctly again.

**Follow-up hardening (post-advisor review, same iteration):**
- Neither `SJ2_CO_GATE`'s narrower `REQUIRED` nor the design choice to narrow rather than
  widen was itself pinned by a test — the generic WR-03 fetch-gate assertion only checks
  `REQUIRED ⊆ fetched`, which holds under either design (narrow SJ-2 gate, or SJ-2 reused
  at the wide `ENRICH_CO_GATE` with a correspondingly widened fetch). Added
  `tests/n8n/sjPredicates.test.mjs#"SJ-2 Company Gate's REQUIRED stays the 2-field
  staleness pair..."`, snapshot-pinning `SJ-2 Company Gate`'s `REQUIRED` to exactly
  `["lv_org_type", "lv_produces_content"]` — the same snapshot-pin pattern
  66-02-SUMMARY used for `CONFLICT_WATCH`/`MATERIAL_CONFLICT_GROUPS`. A future
  re-point of `SJ-2 Company Gate` at `ENRICH_CO_GATE` now fails this test loudly instead
  of passing silently.
- `HS_SEARCH_BODY_EXPR`/`HS_CO_SEARCH_BODY_EXPR` are hand-typed widened lists, not
  mechanically derived from `ENRICH_GATE`/`ENRICH_CO_GATE`'s `REQUIRED` — the orchestrator
  asked for derivation "or say why not, in a comment and in the SUMMARY." The honest
  reason (this line is that documentation): `REQUIRED` is a JS array literal embedded
  inside a Python `r"""..."""` string, not a Python-level list either constant's module
  could import without a real refactor (lifting `REQUIRED` into a shared Python constant
  both JS sites read from) — out of scope for a review fix. `fieldProducerMatrix.test.mjs`'s
  generic fetch-gate assertion (WR-03) is the drift guard in lieu of derivation: it fails
  loudly the next time these lists and their gate's `REQUIRED` go out of sync. Comments
  naming this reasoning were added at both `HS_SEARCH_BODY_EXPR` and `HS_CO_SEARCH_BODY_EXPR`.

**Regeneration and verification (ran in the main checkout — `workflow.use_worktrees=false`
in `.planning/config.json`, so no isolated worktree was created for this fix session; all
suite counts below are reproducible directly from this working tree):**
- Regenerated via `scripts/build_cloud_workflows.py` (never hand-edited); only
  `n8n/wf_enrichment_cloud.json` (a single comment-only jsCode line, from the
  `ENRICH_CO_GATE` `RECOMPUTE_REQUESTED` comment edit — content and behavior unchanged),
  `n8n/wf_enrichment_local_live.json`, and `n8n/wf_scheduled_maintenance_cloud.json`
  differ from the pre-fix tree. Node count on `n8n/wf_enrichment_cloud.json` unchanged at
  **123**. A second regeneration run produces no further diff (idempotent).
- `node --test tests/n8n/*.test.mjs`: **940 pass / 0 fail** (baseline 938 + 2 new
  top-level tests — the WR-03 fetch-gate assertion, plus the follow-up SJ-2 `REQUIRED`
  snapshot-pin in `sjPredicates.test.mjs`; the pre-existing single-lane fetch-gate
  assertion was kept, renamed for clarity, not removed).
- `.venv/bin/python -m pytest -q` (repo root): **4250 passed / 154 skipped** (baseline
  4247 + 3 new CR-01 regression tests; unchanged by the WR-01/WR-02/WR-03 fix, which has
  no Python-side `REQUIRED`-shaped constant to move — matches 66-02-SUMMARY's own D-66-10
  parity note).
- `operator-claude-plugin`: `.venv/bin/python -m pytest -q`: **2492 passed / 5 skipped**
  (baseline 2489 + 3 new CR-01 tests).

## Skipped Issues

None — all four in-scope findings were fixed.

---

_Fixed: 2026-09-04T08:44:20Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
