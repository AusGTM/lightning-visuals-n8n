---
phase: 72-enrichment-extras-land-in-hubspot
verified: 2026-09-12T22:38:10Z
status: passed
score: 22/22 decisions verified (3 human items resolved by operator ruling D-72-24..26, 2026-09-13)
covered_files: [".planning/WINDOWS.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-01-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-01-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-02-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-02-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-03-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-03-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-04-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-04-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-05-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-05-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-06-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-06-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-07-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-07-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-08-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-08-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-09-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-09-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-10-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-10-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-11-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-11-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-12-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-12-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-CONTEXT.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-PORTAL-PROBE.json", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-REVIEW.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-UAT.md", ".planning/todos/completed/2026-09-12-ingest-lane-drops-paid-for-enrichment-extras-map-them-instead.md", ".planning/todos/pending/2026-09-12-enrichment-lane-and-companies-branch-have-no-property-history-hop.md", "CLAUDE.md", "config/column_mapping.yaml", "config/field_policy.yaml", "config/hubspot_migration/undo-manifest-481a5c99-ec62-4f59-940a-7387f5e2a7ad.json", "config/hubspot_properties.yaml", "docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md", "n8n/code/columnMap.js", "n8n/code/mergeCompanies.js", "n8n/code/mergeContacts.js", "n8n/code/normalizeProviders.js", "n8n/wf_contact_ingest_cloud.json", "n8n/wf_contact_ingest_local.json", "n8n/wf_enrichment_cloud.json", "n8n/wf_enrichment_local.json", "n8n/wf_enrichment_local_live.json", "n8n/wf_review_decision_cloud.json", "n8n/wf_scheduled_maintenance_cloud.json", "operator-claude-plugin/.claude-plugin/plugin.json", "operator-claude-plugin/CHANGELOG.md", "operator-claude-plugin/config/column_mapping.yaml", "operator-claude-plugin/config/field_policy.yaml", "operator-claude-plugin/scripts/held_queue.py", "operator-claude-plugin/scripts/preingest.py", "operator-claude-plugin/scripts/suggestion_declines.py", "operator-claude-plugin/skills/contact-upload/extraction.md", "operator-claude-plugin/skills/enrich-before-ingest/SKILL.md", "operator-claude-plugin/skills/review-triage/SKILL.md", "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py", "operator-claude-plugin/tests/test_extraction_handoff.py", "operator-claude-plugin/tests/test_held_queue.py", "operator-claude-plugin/tests/test_preingest_merge.py", "operator-claude-plugin/tests/test_preview_rendering.py", "operator-claude-plugin/tests/test_skill_sequence_coverage.py", "scripts/build_cloud_workflows.py", "scripts/deploy_n8n_workflows.py", "src/merge_policy.py", "tests/fixtures/companies_jscode_frozen.json", "tests/n8n/contactHistoryFlow.test.mjs", "tests/n8n/enrichment.test.mjs", "tests/n8n/fieldProducerMatrix.test.mjs", "tests/n8n/ingestCarryMerge.test.mjs", "tests/n8n/ingestMixedBatch.test.mjs", "tests/n8n/ingestTracerFlow.test.mjs", "tests/n8n/ingestWidenedFieldsFlow.test.mjs", "tests/n8n/mergeCompanies.test.mjs", "tests/n8n/mergeInputContract.test.mjs", "tests/n8n/mergeRecencyGate.test.mjs", "tests/n8n/normalizeProviders.test.mjs", "tests/n8n/overflowSlots.test.mjs", "tests/n8n/parity.test.mjs", "tests/n8n/widenedKeyParity.test.mjs", "tests/n8n/writeGateShape.test.mjs", "tests/test_fetch_by_id_topology.py", "tests/test_merge_helpers.py", "tests/test_merge_policy.py"]
covered_digest: "v1:sha256:1f306cd887a26f8b5388ad8b6dac6164d6896868858aa403f2e48fa920d7d260"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 19/22
  gaps_closed:
    - "D-72-04/D-72-17: LinkedIn dual-write on CREATE (lv_linkedin_url + hs_linkedin_url) — closed by CANDIDATE_ALIASES (plan 72-09, commit 0f7c8c08) and live-proven (contact 352522004980, execution 12414, plan 72-12)."
    - "D-72-01/D-72-06 (CR-01): local-live enrichment lane's non-clobber fetch gap for lv_phone_2/lv_mobilephone_2/state/hs_state_code/phone — closed by widening HS_SEARCH_BODY_EXPR / HS_CO_SEARCH_BODY_EXPR (plan 72-10, commit 455b0173), proven offline (wf_enrichment_local_live.json is not part of deploy_n8n_workflows.py's cloud glob, so no live redeploy applies to this lane)."
    - "D-72-09 (WR-02): overflow-dedup case-sensitivity parity drift between the two JS merge engines and the Python oracle — closed by folding case in both JS engines (plan 72-11, commit e2ea2653), confirmed Python oracle already conformant."
  gaps_remaining: []
  regressions: []
behavior_unverified_items_resolved:  # D-72-24: closed offline by tests/n8n/overflowSlots.test.mjs (commit 0a15398e)
  - truth: "D-72-10: a second email found by the waterfall for the same person is recorded in lv_contact_enrichment_provenance only, never written to hs_additional_emails (confirmed enumeration-typed, not string, by the live portal probe)."
    test: "Run the ingest/enrichment lane against a real (or realistically-shaped) waterfall response that returns two distinct emails for one person."
    expected: "The second email lands in lv_contact_enrichment_provenance's evidence/history, and no write is attempted against hs_additional_emails."
    why_human: "No test anywhere in the repo exercises this path — confirmed by direct search: `/usr/bin/grep -rln \"hs_additional_emails\" tests/ operator-claude-plugin/tests/ n8n/ scripts/ src/` returns zero files, and `/usr/bin/grep -rniE \"second.?email|additional.?email\"` across the same tree also returns zero. The enumeration-type guard's existence is confirmed by code read, but the fallback behavior itself has never been exercised by any test, offline or live. This was never scored as a gap (no plan's must-haves asserts specific runtime behavior here) and is unchanged by this gap-closure round — presence-only, correctly excluded from the verified score."
human_verification_resolved:  # all three resolved by operator ruling 2026-09-13 — see body §Post-verification rulings
  - test: "D-72-10: exercise the hs_additional_emails second-email path with a real waterfall response returning two distinct emails for the same person."
    expected: "A second email is recorded in lv_contact_enrichment_provenance only (never written to hs_additional_emails, which the live portal probe found typed enumeration, not string) — confirming the documented fallback actually engages against real dual-email data, not just against the code's own type guard."
    why_human: "72-UAT.md Test 3 records this explicitly as NOT OBSERVED a second time — the gap-closure live gate's one row also returned only one email from the waterfall. Code-level trace confirms the enumeration-type guard exists; that is a different claim from the fallback actually engaging correctly on real dual-email data. Unchanged since the prior verification; no gap-closure plan targeted it (it was never a gap)."
  - test: "F72-3 item 1: is it acceptable that mobilephone can be filled with the exact same number already present in phone on the same contact (observed live on Telfer 1251 — both fields now read +61 409 390 022)?"
    expected: "An explicit operator ruling: either this duplication is acceptable (fill_blank_only correctly filled a blank field; the duplicate value is a data-quality curiosity, not a merge-policy defect) or a cross-field equality check should suppress the fill when the candidate value already equals a sibling field's value."
    why_human: "Unchanged since the prior verification. 72-12-SUMMARY.md explicitly records F72-3 as 'left exactly as Task 2 recorded them' — this gap-closure round's scope was G1/G2/G3 only. No plan's must_haves asserts a specific behavior here, so it cannot be scored FAILED, but it remains an open decision the phase has not resolved."
  - test: "F72-3 item 2: is it acceptable that a matched UPDATE row's CSV-supplied firstname/lastname/company corrections are never applied, now that the ingest lane merges against real existingRecord values (Plan 01's new prerequisite)?"
    expected: "An explicit operator ruling on whether identity-field corrections on an UPDATE row should ever apply, and if so, through what mechanism (the current merge intentionally treats these as CREATE-only per D-72-05's IDENTITY_FIELDS carve-out)."
    why_human: "Unchanged since the prior verification, for the same reason as F72-3 item 1 — this gap-closure round did not address it, and no plan's must_haves takes a position on it."
---

# Phase 72: Enrichment extras land in HubSpot — Verification Report (Re-verification)

**Phase Goal:** every field the waterfall finds and the operator paid for reaches the HubSpot
contact it was found for — mobile, LinkedIn, seniority, persona, city/state/country — instead of
being dropped.

**Verified:** 2026-09-12T22:38:10Z
**Status:** passed (after operator rulings D-72-24..26, 2026-09-13)
**Re-verification:** Yes — after gap closure (plans 72-09, 72-10, 72-11, 72-12; commits `52705d00`
through `8b6610dd`)

## Method

Re-verified against the prior `72-VERIFICATION.md` (commit `4e3921cc`, `status: gaps_found`,
score 19/22, 3 gaps). Each of the 3 gaps was re-checked against the current codebase at HEAD by:
direct code read of the fix (not the SUMMARY's narration), the specific regression test(s) each
gap-closure plan added, the full node + python suites, a from-scratch regeneration of every n8n
workflow JSON (zero diff against committed), and — for gap 1 only, since it is the one gap the
phase's own discipline required a live gate for — `72-UAT.md` Test 3's transcribed live read-back.
No REQUIREMENTS.md rows map to Phase 72 (confirmed: `/usr/bin/grep -n "Phase 72" .planning/REQUIREMENTS.md`
returns nothing, exit 1) — traceability is by decision ID D-72-01..23 in `72-CONTEXT.md`, per the
task's explicit instruction; this is by design, not an omission.

## Gap-by-Gap Re-verification

### Gap 1 — D-72-04/D-72-17: LinkedIn dual-write incomplete on CREATE

**Status: CLOSED (VERIFIED, live-proven).**

- **Code fix confirmed by direct read:** `scripts/build_cloud_workflows.py:480`,
  `CANDIDATE_ALIASES = { linkedin_url: ["lv_linkedin_url", "hs_linkedin_url"] }`, read by both the
  `confidenceByField`/`sourceByField` derivation loop (line ~495) and the candidate-builder block
  (line ~514) inside `MERGE_CONTACTS` — the exact fix `72-REVIEW.md` WR-01 and the prior
  verification's `missing:` item specified, undoing `preingest.py`'s `PROVIDER_KEY_ALIASES` rename
  at the one place both consumers read it.
- **Regression fixture re-seeded with the real pre-alias key:** `tests/n8n/ingestWidenedFieldsFlow.test.mjs`
  now seeds `source_by_field: { linkedin_url: "apollo" }` (confirmed by direct re-run:
  `/usr/bin/grep -c 'linkedin_url: "apollo"' tests/n8n/ingestWidenedFieldsFlow.test.mjs` returns
  `2`) — the exact vocabulary `preingest.provider_sourced_fields()` actually emits, replacing the
  already-aliased fixture that let the suite stay green through the original live defect. Both
  named tests pass:
  `D-72-04: a linkedin_url header value produces a Create body carrying BOTH lv_linkedin_url and
  hs_linkedin_url` and `D-72-04: hs_linkedin_url is withheld from an update whose contact already
  holds a different non-blank value`.
  ```
  ✔ D-72-04: a linkedin_url header value produces a Create body carrying BOTH lv_linkedin_url and hs_linkedin_url
  ✔ D-72-04: hs_linkedin_url is withheld from an update whose contact already holds a different non-blank value
  ```
- **Regenerated and zero-diffed:** `wf_contact_ingest_cloud.json` / `wf_contact_ingest_local.json`
  regenerate with zero git diff against committed (confirmed by re-running
  `scripts/build_cloud_workflows.py` from the current tree).
- **Live-proven (plan 72-12, `72-UAT.md` Test 3):** contact `352522004980`, n8n execution `12414`
  (the create). Read-back: `lv_linkedin_url` = `http://www.linkedin.com/in/jimmybusteed`,
  `hs_linkedin_url` = identical full URL, both non-null, provenance source `waterfall`/confidence
  85 (not `csv`, the pre-fix fallback). Deploy+bounce table shows all 5 cloud workflows active,
  node counts unchanged from the prior live gate (78/287/55/43/30), `executionOrder: v1`, all
  `ALLOW_*` write flags `false` both before and after the armed window. F72-5 value-shape check
  (CREATE-path URL shape vs the original UPDATE-path URL shape) explicitly compared, no
  regression. This is the phase's own required live gate for this decision (D-72-17), and it now
  passes where it previously failed.

### Gap 2 — D-72-01/D-72-06 (CR-01): local-live enrichment lane non-clobber hole

**Status: CLOSED (VERIFIED, offline; lane is not part of the cloud deploy surface).**

- **Code fix confirmed by direct read:** `scripts/build_cloud_workflows.py`'s `HS_SEARCH_BODY_EXPR`
  (contacts, ~line 2894) now ends its `properties` array with `"lv_phone_2","lv_mobilephone_2"`;
  `HS_CO_SEARCH_BODY_EXPR` (companies, ~line 3047) now includes
  `"lv_phone_2","state","hs_state_code","phone"` — mirroring their cloud-lane siblings
  (`ENRICH_CONTACT_SEARCH_PROPERTIES_CSV`/`ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`) exactly, closing
  the fetch gap CR-01 identified.
  ```
  ✔ non-clobber fetch gate (CR-01): every protect_if_current_present field is fetched, on every overflow-capable shared merge lane
  ```
- **A new derived (not hardcoded) regression assertion** in `tests/n8n/fieldProducerMatrix.test.mjs`
  checks every `protect_if_current_present: true` field is fetched on every overflow-capable merge
  lane across every generated `n8n/wf_*.json` — this is the CR-01 defect class, not just the two
  fields CR-01 happened to find. Confirmed RED-then-GREEN in `72-10-SUMMARY.md`; confirmed
  currently passing.
- **Regenerated and confirmed scoped:** only `wf_enrichment_local_live.json` changed; node count
  unchanged (82).
- **Not deployed live, and this is correctly not counted as a live gap:** confirmed by direct
  read, `scripts/deploy_n8n_workflows.py:280`, `paths = sorted(N8N_DIR.glob("wf_*_cloud.json"))` —
  `wf_enrichment_local_live.json` does not match that glob and is never pushed to n8n Cloud by that
  tool, by design (also stated in `72-10-SUMMARY.md` and `72-12-SUMMARY.md`, now independently
  confirmed here rather than taken on their word). Note the ORIGINAL (pre-gap-closure) verification
  described this file as producing "the real, deployed/credential-bound `wf_enrichment_local_live.json`"
  — that referred to the workflow's runtime *credentials* (a live n8n Docker-replica instance it
  can run against), not to `deploy_n8n_workflows.py`'s cloud-push surface; the two statements are
  compatible, not contradictory: this lane is real and can run, but is never touched by the cloud
  deploy tool this phase's live gates use. There is no live surface this fix needs to be
  redeployed onto for this phase's purposes; the offline fix plus the derived regression guard is
  the complete closure for this gap.

### Gap 3 — D-72-09 (WR-02): overflow-dedup case-sensitivity parity drift

**Status: CLOSED (VERIFIED, offline — deployed to all 7 inlining cloud/local workflows per `72-UAT.md` Test 3 Step 1, but not itself exercised by that live gate's one CREATE row, which never produced a mixed-case overflow candidate).**

- **Code fix confirmed by direct read:** `n8n/code/mergeContacts.js:356-357` and
  `n8n/code/mergeCompanies.js` (byte-identical dedup loop) now fold case:
  `String(c.normalizedValue != null ? c.normalizedValue : c.value).toLowerCase()` compared against
  the same transform on each existing deduped entry — matching `src/merge_policy.py`'s
  `route_overflow` (`str(c.normalized_value).lower()`, confirmed unchanged and already conformant)
  and each engine's own pre-existing `has_conflict()` convention.
  ```
  ✔ mergeContacts overflow: mixed-case agreeing candidates on phone do not manufacture lv_phone_2 (WR-02)
  ✔ mergeCompanies overflow: mixed-case agreeing candidates on phone do not manufacture lv_phone_2 (WR-02)
  ```
- **Mixed-case agreeing-candidates test added to both JS suites and the Python suite**
  (`tests/n8n/overflowSlots.test.mjs`, `tests/test_merge_policy.py`) — pinning the parity so a
  recurrence would be caught, not just restored.
- **Frozen fixture re-baselined as a reviewed act:** `tests/fixtures/companies_jscode_frozen.json`
  diffed old vs new before acceptance, confirming the only change was the `Merge Company` node's
  dedup-loop lines and comment (`72-11-SUMMARY.md`).
- **Seven workflows regenerated** (every workflow inlining either JS merge module), node counts
  unchanged across all seven; `wf_backend_status_cloud.json` (inlines neither module) correctly
  untouched.

## Regression Check

- **Full node suite:** `node --test tests/n8n/*.test.mjs` — **1170 passed, 0 failed** (up from the
  prior verification's 1167 baseline — 3 new tests from the gap-closure plans, consistent with the
  SUMMARYs' own counts).
- **Full python suite:** `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/
  operator-claude-plugin/tests/` — **4948 passed, 154 skipped, 0 failed** (up from 4947 — 1 new
  parity-pin test from plan 72-11).
- **Zero-diff regeneration:** `.venv/bin/python scripts/build_cloud_workflows.py` from the current
  tree followed by `git status --porcelain n8n/ config/` — empty output. Committed, generated, and
  (per `72-UAT.md` Test 3's Step 1 deploy table) live are level for all changed cloud workflows.
- **`scripts/todo_triage.py --check`** exits 0 (2 question, 2 design, 2 minor-defect todos, all
  pre-existing and correctly triaged — none newly introduced by the gap-closure plans, none
  untriaged).
- **No regressions found.** Nothing that passed in the prior verification now fails; no new debt
  markers (`TBD`/`FIXME`/`XXX`) introduced in any file touched by the gap-closure plans.

## Goal Achievement — Updated Decision Table (deltas only; all other 16 decisions from the prior
report are unchanged and re-confirmed by the full green suite + zero-diff regen above)

| # | Decision | Prior Status | Current Status | Evidence |
|---|---|---|---|---|
| D-72-01 | Widen ingest lane; plugin stops stripping enrichment extras | ⚠️ PARTIAL (CR-01) | ✓ VERIFIED | Gap 2 closed — see above. |
| D-72-04 | LinkedIn lands in BOTH `lv_linkedin_url` and `hs_linkedin_url` | ✗ FAILED (CREATE) | ✓ VERIFIED | Gap 1 closed, live-proven — see above. |
| D-72-06 | UPDATE recency/SAFE-01 non-clobber | ⚠️ PARTIAL (CR-01) | ✓ VERIFIED | Gap 2 closed — see above. |
| D-72-09 | Recency + system-correctable + overflow-dedup parity (Phase 46, 3 engines) | ✗ FAILED (overflow-dedup only) | ✓ VERIFIED | Gap 3 closed — see above. |
| D-72-17 | End-of-phase live gate: create + update, all mapped fields land | ✗ FAILED (same root cause as D-72-04) | ✓ VERIFIED | Live-proven, `72-UAT.md` Test 3 — see above. |
| D-72-10 | Second email → `hs_additional_emails` if writable, else provenance-only fallback | ⚠️ human_verification (not a gap) | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Design evidenced (enumeration-type guard confirmed by code read), but no test anywhere — offline or live — exercises the provenance-only fallback itself; `72-UAT.md` Test 3 confirms NOT OBSERVED live a second time, and a repo-wide search finds no offline test either. Excluded from the verified score, routed to human verification, not scored as a gap (no plan's must-haves asserts specific runtime behavior here). |

All other 16 decisions (D-72-02, 03, 05, 07, 08, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23) are
unaffected by the gap-closure plans and remain ✓ VERIFIED exactly as the prior report found them —
re-confirmed here by the fact that the full regression suite (which exercises all of them) stays
green and the zero-diff regeneration shows no unintended drift. D-72-18 remains N/A (superseded by
D-72-21, not separately scored).

**Score:** 21/22 scorable decisions fully verified (up from 19/22). 0 FAILED (down from 3). 1
routed to human verification as a genuinely unexercised-but-well-evidenced behavior (D-72-10,
unchanged — this was never a gap and none of the gap-closure plans targeted it).

### Roadmap Goal Assessment

The goal names five field categories by name: "mobile, LinkedIn, seniority, persona,
city/state/country." All five now land on a CREATED contact via the cloud ingest lane, live-proven
in the phase's own gate: mobile (`mobilephone`), LinkedIn (both `lv_linkedin_url` and
`hs_linkedin_url`, closed by this gap-closure round), seniority, persona (`lv_persona_group`), and
city/state/country (plus ISO codes where a provider supplied one). SAFE-01 non-clobber is proven
live on the cloud lane's UPDATE row and is now also structurally sound on the local-live lane
(closed offline, no live surface applies). The overflow-dedup parity contract (Phase 46's "one
predicate, three engines" rule) is restored. **The phase goal, as stated in ROADMAP.md, is now
achieved as shipped at HEAD** for every category the goal names. Two matters remain open, but
neither is a goal-achievement failure: D-72-10's fallback path is well-evidenced but genuinely
unexercised against real dual-email data (a data-availability limit of the UAT session, not a code
defect), and two F72-3 findings are open operator-ruling questions the phase deliberately left
unresolved (no plan's must-haves takes a position on either).

### Required Artifacts

All artifacts named across the 8 original plans' `must_haves.artifacts` blocks, plus the 4
gap-closure plans' artifacts (`CANDIDATE_ALIASES` in `scripts/build_cloud_workflows.py`, the
widened `HS_SEARCH_BODY_EXPR`/`HS_CO_SEARCH_BODY_EXPR`, the case-folded dedup loops in both JS
merge engines), exist at HEAD and are substantive (verified by direct file/line read, not SUMMARY
narration).

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `preingest.merge_enriched`'s `PROVIDER_KEY_ALIASES` | `MERGE_CONTACTS`'s `CANDIDATE_ALIASES` | Both sides now share the same rename vocabulary; regression fixture uses the real pre-alias key | ✓ WIRED (was ⚠️ PARTIAL) |
| `HS_SEARCH_BODY_EXPR`/`HS_CO_SEARCH_BODY_EXPR` (local-live) | `ENRICH_MERGE`'s `existingRecord` | Fetch lists now widened to match cloud siblings | ✓ WIRED (was ✗ NOT WIRED) |
| `config/source_registry.yaml` trust_rank | slot routing (`_2` overflow) in all 3 merge engines | Case-folding now identical across JS pair and Python oracle | ✓ WIRED (was ⚠️ PARTIAL) |
| `scripts/build_cloud_workflows.py` | all 8 `n8n/wf_*.json` | Re-ran generator from clean tree — zero git diff | ✓ WIRED (unchanged) |

### Behavioral Spot-Checks

Full pytest suite: **4948 passed, 154 skipped, 0 failed.** Full node suite: **1170 passed, 0
failed.** Both exceed the prior baseline by exactly the number of new regression tests the
gap-closure plans added (1 python, 3 node), with zero failures anywhere in either suite. All three
gap-specific named tests re-run individually above and pass. `scripts/build_cloud_workflows.py`
re-run from a clean checkout produced zero diff against all 8 committed workflow JSONs.
`scripts/todo_triage.py --check` exits 0.

### Probe Execution

No `scripts/*/tests/probe-*.sh` convention used by this phase. `72-UAT.md` Test 3 is the phase's
live-check mechanism for gap 1 (the only gap requiring a live proof); reviewed above as primary
live evidence, not re-run (re-running would require a second live HubSpot/n8n write, which the
phase's own "exactly one record" gate discipline reserves for the operator, not the verifier).

### Requirements Coverage

No REQUIREMENTS.md rows map to Phase 72, by design (confirmed by direct grep, exit 1 / no match).
All 23 D-72-NN decisions (22 scorable, D-72-18 superseded) are accounted for above.

### Anti-Patterns Found

No new `TBD`/`FIXME`/`XXX` debt markers introduced by the gap-closure plans in any modified file.
No stub patterns in the fixed code (`CANDIDATE_ALIASES`, the widened fetch constants, the
case-folded dedup loops are all substantive, tested implementations). `scripts/todo_triage.py
--check` confirms all standing todos (2 question, 2 design, 2 minor-defect) are pre-existing,
correctly triaged, and none newly introduced by this gap-closure round.

### Human Verification Required

1. **D-72-10 second-email path** — still genuinely unexercised against real dual-email data (see
   frontmatter). Unchanged since the prior verification; not a gap, not newly introduced.
2. **F72-3 item 1** — is `mobilephone` duplicating an existing `phone` value acceptable? Unchanged
   since the prior verification; this gap-closure round's scope did not include it.
3. **F72-3 item 2** — should a matched UPDATE row's CSV identity corrections ever apply? Unchanged
   since the prior verification; same reason as item 2 above.

These three items are why this re-verification's status is `human_needed` rather than `passed`:
per the decision tree, a non-empty human-verification section routes to `human_needed` regardless
of how many must-haves are cleanly verified. All three items were already present and already
routed to human verification in the prior `gaps_found` report — none is new, and none blocks the
roadmap goal's field-landing claim, which is now fully met. They are standing open questions the
phase has always carried, now the only thing left between this phase and a clean `passed`.

## Gaps Summary

**Zero gaps remaining.** All three gaps from the prior verification are closed:

1. **D-72-04/D-72-17 (LinkedIn dual-write on CREATE)** — closed by `CANDIDATE_ALIASES`
   (`scripts/build_cloud_workflows.py`), live-proven on contact `352522004980` / execution `12414`.
2. **D-72-01/D-72-06 (CR-01 — local-live non-clobber hole)** — closed by widening
   `HS_SEARCH_BODY_EXPR`/`HS_CO_SEARCH_BODY_EXPR`; no live surface applies to this lane.
3. **D-72-09 (WR-02 — overflow-dedup case parity)** — closed by folding case in both JS merge
   engines to match the already-conformant Python oracle.

No regressions were introduced by the fixes (full suite green, +4 new regression tests, zero-diff
regeneration). The roadmap goal — every one of the five named field categories reaching a created
HubSpot contact — is now fully achieved as shipped at HEAD. The only reason this report is not
`passed` is three pre-existing, unchanged human-verification items (one genuinely-unexercised
design decision, two open operator-ruling questions) that were already flagged in the prior report
and that this gap-closure round correctly left untouched, since none was in its scope.

---

_Verified: 2026-09-12T22:38:10Z_
_Verifier: Claude (gsd-verifier)_


## Post-verification operator rulings (2026-09-13)

The three items routed to human verification above were resolved by the operator in the
execute-phase session, recorded as D-72-24..26 in `72-CONTEXT.md` (commit `ba3cdeff`):

| Item | Ruling | Evidence |
| --- | --- | --- |
| D-72-10 second-email fallback (behavior_unverified) | **D-72-24** — closed by an OFFLINE test, no live dual-email run | `tests/n8n/overflowSlots.test.mjs` "hs_additional_emails is never written (D-72-10)": two distinct emails → winner to `email`, runner-up in `provenance.email.overflow_tail` only, `canonicalPatch.hs_additional_emails === undefined`; commit `0a15398e`, 9/9 pass |
| F72-3 item 1 — mobile duplicating `phone` (Telfer `1251`) | **D-72-25** — acceptable; `fill_blank_only` behaved; data-quality note, not a merge defect | no code change |
| F72-3 item 2 — identity corrections never apply on UPDATE | **D-72-26** — acceptable; identity fields are CRM-owned, D-72-05's CREATE-only carve-out stands | no code change |

With these resolved the human-verification section is empty and the status is `passed`.
