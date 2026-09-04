---
phase: 66-rich-enrichment-not-minimum-enrichment
verified: 2026-09-04T08:55:15Z
status: passed
score: 17/17 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 66: Rich Enrichment, Not Minimum Enrichment — Verification Report

**Phase Goal:** make the enrichment waterfall CHASE the fields the merge policy can already
promote — rather than accepting whichever of them a provider happens to volunteer — with every
non-clobber guarantee intact; derive the gate lists from an explicit producer/consumer matrix
rather than intuition; and make phone-and-email completeness visible in the operator's report
without holding anything.

**Verified:** 2026-09-04T08:55:15Z
**Status:** passed
**Re-verification:** No — initial verification

## Verification Method

This phase went through code review post-execution: `66-REVIEW.md` found 1 critical (CR-01) and
3 warnings (WR-01/WR-02/WR-03), all fixed in `66-REVIEW-FIX.md` (commits `a637fe6`, `6b3edf2`,
`c42d3b5`). Per the harness instructions, a green suite was NOT accepted as evidence on its own
— every fix claim below was independently re-derived against the working tree (regenerated
JSON, live `node -e`/`python -c` probes, direct reads of generated `jsCode`), not read off the
review/fix documents.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D-66-01/RICH-01: a blank-landline contact's Lusha body carries the phone reveal value | ✓ VERIFIED | `lushaReveal(['phone','mobilephone'])` → `["phones"]` (one element, deduped); `LUSHA_REVEAL_BY_FIELD` keys = `email,mobilephone,phone` |
| 2 | D-66-01/RICH-01: an all-blank CREATE row also carries the phone reveal value | ✓ VERIFIED | `decideAction({},['email','phone'],{},now).missingFields` → `["email","phone"]` (both, not empty) |
| 3 | D-66-02/RICH-03: Apollo LinkedIn URL produces a candidate reaching `mergeContacts` under `lv_linkedin_url` | ✓ VERIFIED | `toCandidates('apollo',{person:{linkedin_url:'https://www.linkedin.com/in/example/'}},'contacts')` → field `linkedin_url`; `linkedinProducer.test.mjs` (h)-(l) prove the full seam end to end incl. compiled node bodies |
| 4 | D-66-03: a stored `lv_linkedin_url` is READ and protects against overwrite | ✓ VERIFIED | `linkedinProducer.test.mjs` (k): `mergeContacts` stages-only against an existing different LinkedIn URL |
| 5 | D-66-08 (66-01): `config/field_policy.yaml` zero-line diff | ✓ VERIFIED | `git diff 3493a01..c42d3b5 -- config/field_policy.yaml` exits 0 (checked against phase-66's actual commit set, not the interleaved branch range) |
| 6 | D-66-09 (66-01): contacts `POLICY` map still exactly 2 keys (`jobtitle`, `mobilephone`), no TTL added to `phone` | ✓ VERIFIED | Read `Enrichment Gate` node's generated `jsCode`: `const POLICY = { jobtitle: {...}, mobilephone: {...} }` |
| 7 | D-66-07/RICH-02/RICH-05: matrix exists for every policy-promotable field, both lanes, naming producer/class/fetch/chase | ✓ VERIFIED | `66-COVERAGE.md` has 33 `|`-delimited table lines covering all 12 contacts + 17 companies keys; `fieldProducerMatrix.test.mjs` derives inputs from `config/field_policy.yaml` at runtime (confirmed no hardcoded key lists) |
| 8 | D-66-07: a producer-less field is caught by a test, by name | ✓ VERIFIED | `fieldProducerMatrix.test.mjs` allow-list explicitly names `domain` (companies, no producer) and ZoomInfo-LinkedIn (pending-probe) with reasons; both tests pass |
| 9 | D-66-01 companies half/RICH-02: `ENRICH_CO_GATE.REQUIRED` derived from matrix, exclusions reasoned | ✓ VERIFIED | Cloud `Company Gate` REQUIRED = 13 fields, excludes `domain` (no producer), `annualrevenue` (not promotable), veto-output fields — matches `66-COVERAGE.md`'s stated exclusion rule |
| 10 | D-66-04: `CONFLICT_WATCH`/`MATERIAL_CONFLICT_GROUPS` byte-unchanged | ✓ VERIFIED | `materialConflictNoVetoFlip.test.mjs`: 3 snapshot-equality assertions pass (`Merge Company`'s `CONFLICT_WATCH`, `Judge Gate`'s and `Merge Company`'s `MATERIAL_CONFLICT_GROUPS`) |
| 11 | D-66-08 (66-02): zero-line diff on policy/mergeContacts/mergeCompanies/resolveIdentity/providerConflict | ✓ VERIFIED | `git diff 3493a01..c42d3b5` on each named file, restricted to phase-66's own commits (confirmed no phase-66 commit touches any of them via `git show --stat`) |
| 12 | CLAUDE.md §29.1: `numberofemployees` exception not widened by chasing it | ✓ VERIFIED | `n8n/code/normalizeProviders.js`'s companies branches (58-05 Task 2 code) untouched by any phase-66 commit except the unrelated contacts-branch LinkedIn addition; `mergeCompanies.js`'s policy table unchanged |
| 13 | D-66-06/RICH-01: a contacts row ending the run with phone+email is distinguishable from email-only in the report | ✓ VERIFIED | `_contactability(row)` in `Build Response` stamps `complete`/`email_only`/`none`; `outcomeContractFlow.test.mjs` 4 D-66-06 assertions pass; `report_enrichment.py` surfaces it per-row and as a batch tally |
| 14 | D-66-05: phone-less row is FLAGGED, never held — no gate/hold/refusal/write reads the signal | ✓ VERIFIED | Grepped every consumer of `contactability` in `scripts/build_cloud_workflows.py`/`n8n/code/`: only computed and assigned into the response object, never read in a conditional; `report_enrichment.py`'s docstring and code confirm report-only, count-only usage |
| 15 | D-66-05: signal reflects post-run state (existing + this-run promotion), not raw provider return | ✓ VERIFIED | `_postRunFieldValue` reads `canonicalPatch` first, falls back to `existingRecord`; `outcomeContractFlow.test.mjs`: "a blank email promoted THIS run reads as complete" passes |
| 16 | Outcome contract version NOT bumped | ✓ VERIFIED | `Build Response` jsCode contains `OUTCOME_CONTRACT_VERSION = 2` (unchanged); `preingest.py`'s known-version set untouched (`git diff` on that file exits 0 for phase-66 commits) |
| 17 | D-66-08 (66-03): zero-line diff, `config/field_policy.yaml` | ✓ VERIFIED | Same file-level check as #5/#11 |

**Score:** 17/17 truths verified (0 present-but-behavior-unverified)

### Post-Review Defect Re-Verification (do not trust the fix report — re-derived independently)

| Defect | Claimed fix | Independent re-verification |
|--------|-------------|------------------------------|
| CR-01 (critical): `_contactability_for_row` raises `TypeError` on a dict/list value | `isinstance(value, str)` guard added | Reproduced the review's exact repro commands against current tree: dict value → `None` returned, no raise; list value through `build_sync_report` → succeeds, no raise. Confirmed by direct execution, not by reading the diff. |
| WR-01: `HS_SEARCH_BODY_EXPR`/`HS_CO_SEARCH_BODY_EXPR` (local-live lane) narrower than widened `REQUIRED`, computing a wrong preview | Both constants widened to match | Read the regenerated `n8n/wf_enrichment_local_live.json` search node bodies directly: all 7 previously-missing contacts fields (`city`,`state`,`country`,`hs_state_code`,`hs_country_region_code`,`lv_linkedin_url`,`lv_persona_group`) and all 6 previously-missing companies fields (`lv_revenue_band`,`lv_employee_band`,`lv_country_region_normalized`,`country`,`city`,`lv_sponsorship_reliant`) are now present in the respective `jsonBody` strings. |
| WR-02 (the headline one): `wf_scheduled_maintenance_cloud.json`'s `SJ-2 Company Gate` reused the widened 13-field `ENRICH_CO_GATE`, but `SJ-2 Search`'s fetch stayed at 6 properties — false-triggering `lv_enrichment_requested=true` on nearly every fresh company | Split off `SJ2_CO_GATE` with the original narrow 2-field `REQUIRED`, `SJ-2 Search` untouched | **Independently confirmed against the regenerated JSON** (not the fix report): `SJ-2 Company Gate`'s `REQUIRED` = exactly `["lv_org_type", "lv_produces_content"]`, and this is the ONLY gate node in that file. Cloud `Company Gate` (the reused-elsewhere shared constant) = 13 fields, confirming the two are now genuinely different constants. `SJ-2 Search (stale refresh)`'s fetch list (`hs_object_id,domain,lv_org_type,lv_produces_content,lv_org_type_verified_at,lv_produces_content_verified_at`) is a superset of SJ-2's own 2-field REQUIRED. Regression test `sjPredicates.test.mjs` pins this with a snapshot assertion, run and passing (28/28 in the targeted node-test run). |
| WR-03: matrix test's fetch-gate assertion only checked `wf_enrichment_cloud.json`, missing the other three gate-embedding files | Generic assertion added, enumerating every `n8n/wf_*.json`, walking the connection graph to find each gate's real upstream fetch node | Ran `fieldProducerMatrix.test.mjs` directly: the generic "fetch gate (WR-03)" assertion is present and passes, alongside the original single-lane assertion (kept, not removed). |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `n8n/code/lushaRequest.js` | landline reveal-map entry, deduped `lushaReveal` | ✓ VERIFIED | 3-key reveal map confirmed live; dedup confirmed by direct call |
| `n8n/code/enrichmentGate.js` | `decideAction` create-branch fix | ✓ VERIFIED | CREATE-row `missingFields` now non-empty, confirmed live |
| `n8n/code/normalizeProviders.js` | Apollo LinkedIn producer + host guard | ✓ VERIFIED | Producer confirmed; host guard rejects lookalikes, accepts subdomains |
| `scripts/build_cloud_workflows.py` | `ENRICH_GATE`/`ENRICH_CO_GATE` widened REQUIRED, `SJ2_CO_GATE` split, widened search CSVs and local-live expressions | ✓ VERIFIED | All confirmed by reading regenerated JSON directly |
| `.planning/phases/66-rich-enrichment-not-minimum-enrichment/66-COVERAGE.md` | producer/consumer matrix, both lanes | ✓ VERIFIED | Exists, 33 table rows, names both known gaps with reasons |
| `tests/n8n/fieldProducerMatrix.test.mjs` | 4 derived assertions + WR-03 generic fetch-gate assertion | ✓ VERIFIED | Exists, reads YAML at runtime, all assertions pass |
| `tests/n8n/linkedinProducer.test.mjs` | producer/guard/seam/gate-widening tests | ✓ VERIFIED | 14/14 pass |
| `operator-claude-plugin/scripts/report_enrichment.py` | per-row + batch-level contactability | ✓ VERIFIED | Confirmed shared through `_build_row_report`, used by both `build_sync_report` and `build_enrichment_report` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| gate `REQUIRED` (contacts) | Lusha request body | `missingFields` → `lushaReveal` | ✓ WIRED | Traced live: widened gate feeds `missingFields`, which the 3-key reveal map converts to a deduped reveal array |
| `_push` under `linkedin_url` | `mergeContacts` under `lv_linkedin_url` | `scoreCandidates` → `ENRICH_MERGE`'s `canonicalizeLinkedin(winners.linkedin_url)` rename | ✓ WIRED | `linkedinProducer.test.mjs` (h)/(i)/(l) prove every hop, including against the real compiled node bodies |
| `ENRICH_CONTACT_SEARCH_PROPERTIES_CSV`/`ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` | `existingRecord` | HubSpot Search node fetch | ✓ WIRED | Confirmed superset of REQUIRED in cloud lane (matrix test) and now also local-live lane (WR-01 fix, independently re-checked) |
| `ENRICH_BUILD_RESPONSE` | operator report | `contactability` key → `report_enrichment._build_row_report` → rendered report | ✓ WIRED | Confirmed additive key present in `Build Response` jsCode and read defensively in the Python renderer |
| `ENRICH_CO_GATE`/`SJ2_CO_GATE` | respective search fetch lists | `REQUIRED` array | ✓ WIRED (post-fix) | Cloud `Company Gate` (13 fields) matched against widened `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`; SJ-2's narrower `SJ2_CO_GATE` (2 fields) matched against SJ-2's own unwidened 6-field fetch — both confirmed supersets by direct read, not by trusting the WR-03 test alone |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| RICH-01 | 66-01, 66-03 | phone chased, not merely accepted; phone-and-email completeness visible | ✓ SATISFIED | Landline/CREATE-row chase confirmed live; contactability marker confirmed live and rendered |
| RICH-02 | 66-02 | producer/consumer matrix for all 12 contact fields; gate `REQUIRED` derived from it | ✓ SATISFIED | `66-COVERAGE.md` + `fieldProducerMatrix.test.mjs` confirmed derived, not hardcoded |
| RICH-03 | 66-01 | `lv_linkedin_url` acquires a producer | ✓ SATISFIED | Apollo producer confirmed live, full seam proven |
| RICH-05 | 66-02 | same audit run for companies | ✓ SATISFIED | `66-COVERAGE.md` companies table (17 rows) + companies-lane matrix assertions pass |
| RICH-06 | 66-01 | provider cost confirmed, not assumed | ✓ SATISFIED | Lusha flat-billing/ZoomInfo-already-paid/Apollo-no-per-field-ask comments present at the reveal-map mirror site, citing `docs/LUSHA-V3-CONTRACT.md` §6 |

No orphaned requirements: `REQUIREMENTS.md`'s RICH section lists RICH-01/02/03/05/06 for Phase 66, all five `[x]`-marked and all five present in at least one plan's `requirements:` frontmatter. RICH-04 was legitimately re-routed to Phase 65 by a recorded 2026-09-04 operator ruling (`merge_enriched` lives in `suggest_contacts.py`, outside this phase's domain) — this is documented in `REQUIREMENTS.md`, `ROADMAP.md`, and `66-01-PLAN.md`'s `<upstream_corrections>` item 8, and is not a gap.

### Anti-Patterns Found

None blocking. No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers found in the phase's own commits' changed files. The one genuine bug found by code review (CR-01) was fixed and independently re-verified above, not merely trusted.

### Test Suite Reproduction (run directly, not read off SUMMARY/REVIEW-FIX claims)

| Suite | Command | Result |
|-------|---------|--------|
| n8n/node | `node --test tests/n8n/*.test.mjs` | 940 pass / 0 fail |
| Python (repo root) | `.venv/bin/python -m pytest -q` | 4250 passed / 154 skipped |
| Python (plugin) | `cd operator-claude-plugin && ../.venv/bin/python -m pytest -q` | 2492 passed / 5 skipped |
| Regeneration idempotency | `.venv/bin/python scripts/build_cloud_workflows.py` then `git status --porcelain n8n/` | 8 "wrote n8n/..." lines, zero diff against committed tree |

All three counts match the numbers claimed in `66-REVIEW-FIX.md`, reproduced independently rather than trusted.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Landline chased for existing row | `lushaReveal(['phone','mobilephone'])` | `["phones"]` | ✓ PASS |
| CREATE-row reveal no longer empty | `decideAction({},['email','phone'],{},now).missingFields` | `["email","phone"]` | ✓ PASS |
| LinkedIn producer fires on nested Apollo shape | `toCandidates('apollo',{person:{linkedin_url:...}},'contacts')` | `linkedin_url` field present | ✓ PASS |
| LinkedIn host guard rejects lookalikes | `toCandidates` with `evil-linkedin.com.attacker.io` / `notlinkedin.com` | no candidate for either | ✓ PASS |
| LinkedIn host guard accepts subdomains | `toCandidates` with `au.linkedin.com` | candidate produced | ✓ PASS |
| CR-01 fix: dict/list `contactability` value | `_build_row_report`/`build_sync_report` with dict/list value | returns `None`, no raise | ✓ PASS |
| SJ-2 gate narrowed correctly | read `SJ-2 Company Gate` REQUIRED from regenerated JSON | `["lv_org_type","lv_produces_content"]` | ✓ PASS |
| Cloud Company Gate widened correctly | read `Company Gate` REQUIRED from regenerated JSON | 13 fields | ✓ PASS |
| POLICY maps unchanged (D-66-09), both lanes | read `POLICY` object literal from both gate nodes | 2 keys each, unchanged | ✓ PASS |
| Local-live search bodies widened (WR-01) | read `HubSpot Search`/`HubSpot Company Search` `jsonBody` | all previously-missing fields present | ✓ PASS |

### Human Verification Required

None. This phase produces no runtime-observable UI, and nothing is deployed or armed — the standing project fact (CLAUDE.md §13.0.2/§13.0.3) that "nothing is armed, no unattended credit-spending batch has run" is unchanged by this phase and is not a gap for this phase's own goal, which is entirely about the generator's static output (chased-field lists, reveal maps, report shape) and does not require a live n8n execution to verify. Every truth above was checked by direct execution against generated artifacts or unit-level code, with no UI/visual/timing-dependent behavior in scope.

### Gaps Summary

None. All 17 must-haves across the three plans verified directly against the current working
tree (not trusted from SUMMARY.md or the review/fix documents). The one critical defect (CR-01)
and three warnings (WR-01/WR-02/WR-03) found by the post-execution code review were each
independently re-reproduced against the current tree and confirmed fixed — including the
headline WR-02 regression (SJ-2's scheduled stale-refresh gate silently over-triggering because
it reused the widened companies `REQUIRED`), which is now provably split into its own narrow,
snapshot-pinned `SJ2_CO_GATE` matching exactly what `SJ-2 Search` fetches.

---

_Verified: 2026-09-04T08:55:15Z_
_Verifier: Claude (gsd-verifier)_
