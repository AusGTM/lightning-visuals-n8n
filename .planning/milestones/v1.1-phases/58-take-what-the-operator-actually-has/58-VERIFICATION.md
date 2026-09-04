---
phase: 58-take-what-the-operator-actually-has
verified: 2026-08-26T12:07:21Z
status: passed
score: 31/31 must-haves verified (INPUT-02 carries one operator-accepted residual, documented below, not counted as a gap)
behavior_unverified: 0
overrides_applied: 0
deferred:
  - truth: "INPUT-02: the backend research node is extended to seek a company's own website when Claude cannot propose one and the operator cannot supply one."
    addressed_in: "a later, not-yet-numbered phase (explicitly 'carried forward' per 58-SPIKE-VERDICT.md and v1.1-REQUIREMENTS.md)"
    evidence: "58-SPIKE-VERDICT.md: operator decision 'defer-residual', 2026-08-26 — 'ship the client (plugin) path this phase; do not extend the backend research node to seek a domain.' v1.1-REQUIREMENTS.md leaves INPUT-02 unchecked with the identical residual restated. This is a phase-scoped, in-writing operator ruling, not a silently discovered gap — the roadmap's own INPUT-02 wording ('closing this gap is a future phase's job') and 58-04's written disposition both anticipate it."
---

# Phase 58: Take What the Operator Actually Has — Verification Report

**Phase Goal:** Every input an operator holds resolves to something the backend can act on —
screenshot, paste, URL, bare name resolve to a company; missing domains researched then
confirmed before write; never silently invent a domain (a profile URL is dropped, not passed
through); refusal is the last resort and always names what would make it work. Closes
INPUT-01..04. Research cost priced in the envelope and declinable.

**Verified:** 2026-08-26T12:07:21Z
**Status:** passed
**Re-verification:** No — initial verification

## Method

No previous VERIFICATION.md existed for this phase (initial mode). Six plans (58-01..58-06)
were each checked against: (1) their own `must_haves.truths`/`artifacts`/`key_links`/
`prohibitions` frontmatter, (2) the phase's roadmap goal, (3) the milestone requirements file
(`INPUT-01..04`), and (4) the code review + fix report. Every claim below was re-run against
the current working tree — not read off SUMMARY.md prose. Commands actually executed:
`.venv/bin/python -m pytest` (full suite, once), `node --test tests/n8n/*.test.mjs` (full
glob, once), targeted single-file/`-k` reruns for named tests, `git log`/`git show` to confirm
every commit hash cited in the six SUMMARYs and the REVIEW-FIX report exists and touches the
claimed files, and a full `scripts/build_cloud_workflows.py` + `scripts/gen_escalation_js.py`
regeneration to confirm the checked-in `n8n/wf_*.json` and `escalation.generated.js` are
byte-identical to generator output (no hand-edit drift).

## Goal Achievement

### Observable Truths (by plan)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | A company named only by its name (no domain, no URL) survives extraction and reaches a companies envelope event (58-01, D-58-11, INPUT-01) | VERIFIED | `operator-claude-plugin/tests/test_company_extraction.py::test_bare_company_name_reaches_a_companies_envelope_event` passes; `company_column_mapping.yaml`'s `required_identity.any_of: [[name]]` confirmed on disk |
| 2 | One paste/screenshot holding both people and companies produces both record types in a single pass, companies first (58-01, D-58-13) | VERIFIED | `test_mixed_artifact_validates_both_lanes_in_one_pass_companies_first`, `test_every_accepted_entry_carries_a_record_type` pass |
| 3 | All six company source kinds (pasted text, foreign JSON, public URL, screenshot, bare-name list, search-results screenshot) documented and structurally pinned (58-01, D-58-14, INPUT-01) | VERIFIED | `test_all_six_company_adapter_headings_are_present`, `test_company_canonical_props_section_matches_the_config_file_exactly` pass; `extraction.md` contains all six `### Company adapter:` headings |
| 4 | A nameless company row is rejected naming what's missing, never naming contact fields (58-01, INPUT-04) | VERIFIED | `test_nameless_company_record_is_rejected_without_naming_contact_fields` passes |
| 5 | A field the source doesn't supply is absent, never invented (58-01, D-58-12) | VERIFIED | Structural: no default/fill logic exists in `extraction.py`'s `canonical_props()`; pinned by config-vs-prose parity tests |
| 6 | A malformed `record_type` is rejected by name, not silently coerced to contacts (code-review WR-02) | VERIFIED | `test_unrecognized_record_type_is_rejected_by_name_not_silently_coerced` passes; commit `5e22393` confirmed in `git log` |
| 7 | A mixed-batch artifact-supplied ambiguity survives companies-first reassembly without landing on the wrong row (code-review CR-01, critical) | VERIFIED | `test_mixed_batch_ambiguity_on_a_contact_survives_companies_first_reassembly` + inverse-order sibling pass; `_raw_index`/`raw_to_final` remap present in `extraction.py`; commit `5e22393` confirmed |
| 8 | A request-level `mode` key survives `Parse HubSpot Event` to `Decide Company Action`'s `isReturnOnly`, forcing a non-writing `proposed` action (58-02, INPUT-03) | VERIFIED (live) | 58-SPIKE-VERDICT.md: live execution `11972`, `action: "proposed"`, `mode_visible_on_parsed_row: "propose"`, 0 writes — read from the execution's own runData, not a stored read-back |
| 9 | Spike spends ≤3 executions, 0 provider credits, 0 Anthropic calls | VERIFIED | 1 execution, 0/0 actuals recorded in 58-SPIKE-VERDICT.md |
| 10 | Operator decision on backend research-node scope recorded in writing, not assumed (58-02, INPUT-02) | VERIFIED | `58-SPIKE-VERDICT.md` — decider "operator", date, reason, and the residual all present |
| 11 | An undecided proposed domain cannot reach a companies envelope event — the spec build refuses and names the row (58-03, INPUT-03, VOCAB-05) | VERIFIED | `test_to_envelope_spec_raises_on_undecided_row` and siblings in `test_company_domain_confirm.py` pass |
| 12 | A denied proposal falls to name-only lookup, disclosed, never dropped (58-03, D-58-06, INPUT-04) | VERIFIED | decline-survives-to-spec tests pass; `DECLINE_DOMAIN` sentinel confirmed in `company_domain.py` |
| 13 | An operator-typed domain is accepted on the operator's word with no research pass, still refused for profile/freemail hosts (58-03, D-58-07) | VERIFIED | `company_domain.py` imports and calls `enrichment._clean_domain` (grep-confirmed) rather than re-implementing the guard; tests pass |
| 14 | A confirmed proposal writes with no second model pass (58-03, D-58-02) | VERIFIED | `apply_domain_decisions` → `to_envelope_spec` path has no model call (code-inspection + passing tests) |
| 15 | A decision set with one bad entry applies none of its entries (58-03, atomicity) | VERIFIED | `test_all_or_nothing_a_bad_last_entry_applies_none_of_the_earlier_good_ones` passes |
| 16 | Operator live-walked the confirm table and approved it, no wording flagged, silence-means-nothing-sends understood (58-03 Task 4) | VERIFIED (operator-recorded) | Verbatim walk transcript in 58-03-SUMMARY.md, plugin 0.19.0, verdict APPROVED, 2026-08-26 — treated as evidence per this verification's instructions |
| 17 | Backend domain research appears as its own priced envelope line, naming affected rows (58-04, D-58-08, INPUT-02) | VERIFIED | `test_an_unmeasured_rate_renders_no_dollar_figure_and_no_zero`, `test_zero_rows_says_no_research_needed_even_with_a_measured_rate`, and 3 siblings in `test_company_research_envelope.py` pass |
| 18 | Default-on, declinable — one batch yes covers it unless struck (58-04, D-58-09) | VERIFIED | `test_striking_the_line_moves_exactly_the_needs_research_rows_to_name_only_and_nothing_else` passes |
| 19 | An unmeasured rate is disclosed as unmeasured, never rendered as zero or fabricated | VERIFIED | `cost_rates.json`'s `company_domain_research` entry is `value: null`; rate-shape parity test passes |
| 20 | Striking the research line converges on the same name-only fallback as a denied proposal — one degradation path (58-04, D-58-10) | VERIFIED | `test_a_declined_research_row_and_a_declined_proposal_row_are_the_same_shape` passes — both route through `DECLINE_DOMAIN` |
| 21 | INPUT-02's residual is named in writing (decider, date, reason, what would close it), not left implied (58-04) | VERIFIED — accepted residual, not a gap | `58-04-SUMMARY.md`'s "INPUT-02 Disposition" section; `git diff --stat scripts/build_cloud_workflows.py src/web_research.py` empty for this plan's own commits, confirming zero backend code touched under the defer branch |
| 22 | Native `country` written blank-fill-only from provider data, not left blank while `lv_*` mirror is populated (58-05, INPUT-01) | VERIFIED (live) | `tests/n8n/companyNativeFields.test.mjs` (19/19 pass, re-run); live execution `11980`'s own runData carries `country: "Australia"` in the derived (unwritten, disarmed) patch |
| 23 | Native `city`/`numberofemployees` written when supplied, absent when not (D-58-12 no-invention, 58-05) | VERIFIED (live) | Same test file + execution `11980`: `city: "Brunswick"`, `numberofemployees: 13` (a real number, not a range string); ZoomInfo's structural city-absence pinned and confirmed by 4-execution live sample |
| 24 | Native `industry` untouched — Phase 31 enum guard still refuses unmapped strings (58-05 prohibition) | VERIFIED (live) | Execution `11980`: `industry` absent from top-level patch despite a candidate existing, `validation_status: "rejected"`; `git diff --stat n8n/code/hubspotEnums.js` empty |
| 25 | Native properties actually exist live and are writable (not just assumed) | VERIFIED (live) | `tests/test_company_native_properties.py` — 4/4 passed against the **live** HubSpot portal (not skipped; `HUBSPOT_PRIVATE_APP_TOKEN` present), confirming `country`/`city`/`numberofemployees` exist, correct type, not read-only |
| 26 | Series Futsal Victoria retro-fix determined from live gate state, not assumed (58-05) | VERIFIED (live) | Live gate replay + confirming execution `11980`; and disclosed honestly that the operator's own intervening dispatch (`11983`) landed the fields via a different path and introduced a regression, cleared by an authorized corrective window (`11b17c0`), independently read back |
| 27 | A material cross-provider conflict on any of 5 decision-driving field groups is withheld from the patch and flags the record, unless a judge verdict adjudicated it (58-06, INPUT-01) | VERIFIED | `tests/n8n/materialConflictNoVetoFlip.test.mjs` (4/4 pass, built from execution `11983`'s own captured payloads): no-verdict withholds+flags+no-flip; AU-verdict promotes+no-flip; non-ANZ-verdict promotes+DOES-flip (suppression is conditional, not a ban); agreeing multi-source still promotes |
| 28 | A material conflict is observable — reaches `needsReview`, writes `lv_enrichment_needs_review`/status/reason (58-06) | VERIFIED | Same test file; `tests/n8n/providerConflict.test.mjs` (9/9) proves the shared predicate in isolation |
| 29 | RO-2 still holds — no model call triggered by a size disagreement alone; size conflicts gain a flag, nothing else (58-06 prohibition) | VERIFIED | `tests/test_judge_spec.py::test_ro2_judge_gate_cannot_see_size_conflicts` passes (9/9 in file); `tests/n8n/judge.test.mjs`'s built-jsCode grep for size-field names passes |
| 30 | The hard-veto predicate (`src/icp_scoring.py`) is byte-equivalent in meaning, untouched by this phase | VERIFIED | `git log --oneline -- src/icp_scoring.py` shows no phase-58 commit; `tests/test_scoring_parity.py` — 53 passed, 34 skipped |
| 31 | Every claim about the running n8n instance rests on one live execution's own runData, never a stored read-back (58-05 and 58-06 prohibition) | VERIFIED | Executions `11980` and `11987` both read via `includeData=true`/`workflowData.nodes` directly off the execution object, per the SUMMARYs' own methodology, cross-checked against `git status --porcelain n8n/wf_*.json` (clean) and a full local regeneration (byte-identical) |

**Score:** 31/31 truths verified. One requirement (INPUT-02) carries a deliberate, in-writing
operator-accepted residual — see Deferred Items below, not counted as a failure per this
phase's explicit scope.

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | INPUT-02: extend the backend `Claude Web Research` node's prompt/schema to seek a company's own website (for rows Claude cannot propose and the operator cannot supply), plus the company-shaped `match`/`candidates` response contract 58-02 flagged as also needed | A later, not-yet-numbered phase | `58-SPIKE-VERDICT.md` (operator decision `defer-residual`, 2026-08-26); `58-04-SUMMARY.md`'s "INPUT-02 Disposition" names exactly what would close it; `v1.1-REQUIREMENTS.md` leaves INPUT-02 unchecked with the identical residual restated |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|---|---|---|---|---|
| INPUT-01 | 58-01, 58-05, 58-06 | A company can be named by anything the operator holds; a landing record shows what the backend found; a provider disagreement can no longer resolve to a confident wrong answer | SATISFIED | Truths 1–7, 22–31 above; ticked `[x]` in `v1.1-REQUIREMENTS.md` |
| INPUT-02 | 58-02, 58-04 | When input carries no usable domain, the system finds one rather than asking the operator | PARTIALLY SATISFIED, residual accepted | Truths 8–10, 17–21 above; the client-side propose/confirm/price/decline lane is fully built and tested; the backend research-node extension is deliberately deferred by written operator decision. Correctly left unticked `[ ]` in `v1.1-REQUIREMENTS.md` with the residual documented |
| INPUT-03 | 58-02, 58-03 | A researched domain is confirmed before it is written | SATISFIED | Truths 8, 9, 11, 14, 15, 16 above; ticked `[x]` in `v1.1-REQUIREMENTS.md` |
| INPUT-04 | 58-01, 58-03, 58-04 | A refusal is a last resort and always names what would make it work | SATISFIED | Truths 4, 6, 12, 13, 20 above; ticked `[x]` in `v1.1-REQUIREMENTS.md` |

**Orphan check:** `v1.1-REQUIREMENTS.md`'s INPUT section lists exactly INPUT-01..04. The union
of every plan's `requirements:` frontmatter across 58-01..58-06 is `{INPUT-01, INPUT-02,
INPUT-03, INPUT-04}` — an exact match. No requirement declared in a plan is missing from the
milestone file, and no milestone-file requirement in this phase's closes-list is unclaimed by
any plan. No orphans.

### Anti-Patterns Found

Scanned every file touched across the six plans plus the two REVIEW-FIX commits
(`operator-claude-plugin/scripts/{extraction,company_domain,enrichment,cost_guard}.py`,
`n8n/code/{normalizeProviders,mergeCompanies,providerConflict,judge}.js`,
`scripts/{build_cloud_workflows,fix_sfv_region,probe_company_propose_mode}.py`,
`src/judge.py`, `config/{field_policy,escalation_policy}.yaml`) for `TBD|FIXME|XXX|TODO|HACK|
PLACEHOLDER`, `return null|{}|[]`, and empty-arrow patterns. **None found.**

### Test Suites (run fresh, not read from SUMMARY prose)

| Suite | Command | Result |
|---|---|---|
| Node (full glob) | `node --test tests/n8n/*.test.mjs` | 772/772 pass, 0 fail |
| Python (full suite) | `.venv/bin/python -m pytest -q` | 3203 passed, 154 skipped, 4 failed — all 4 the pre-existing, disclosed `tests/test_merge_policy.py` `ThinkingBlock`/pydantic-SDK failures (reproduced against the pre-phase-58 diff per `deferred-items.md`), no other failures |
| Live property check | `.venv/bin/python -m pytest tests/test_company_native_properties.py -q` | 4/4 pass against the **live** HubSpot portal (not skipped) |
| n8n generator drift check | `python scripts/build_cloud_workflows.py` + `python scripts/gen_escalation_js.py` | Zero diff against checked-in `n8n/wf_*.json` and `n8n/code/escalation.generated.js` — no hand-edit drift |
| Targeted RO-2 / veto-predicate pins | `pytest tests/test_judge_spec.py`, `pytest tests/test_scoring_parity.py` | 9/9 and 53 passed/34 skipped respectively; `git log` confirms `src/icp_scoring.py` carries no phase-58 commit |
| Code-review fix regression | `-k "mixed_batch_ambiguity or unrecognized_record_type"` | 3/3 pass; commits `5e22393`/`d9b7510` confirmed in `git log` |

### Human Verification Required

None outstanding. The phase's human-gated checkpoints (58-02 Task 3's scope decision, 58-03
Task 4's live confirm-table walk, 58-05 Task 4's corrective-window authorization, 58-06 Task
4's two policy rulings) were each already resolved by a recorded, dated operator decision
during phase execution — treated here as evidence per this verification's own instructions,
not re-opened as pending items.

### Gaps Summary

No gaps found. INPUT-01, INPUT-03, and INPUT-04 are fully closed with live-execution evidence,
passing automated tests at every layer (Python unit, n8n node, live n8n execution, live
HubSpot property read), and a code review whose 3 findings (1 critical, 2 warning) were all
fixed and re-verified. INPUT-02 is intentionally left partially open by an explicit,
dated, written operator decision (`defer-residual`) rather than a discovered or silent
shortfall — the milestone requirements file itself reflects this correctly (`[x]` for
INPUT-01/03/04, `[ ]` for INPUT-02 with the residual restated verbatim). Two mid-phase
incidents (a git-reset that discarded and required re-committing one 58-04 commit; an
operator's own out-of-band armed dispatch that landed 58-05's goal via a different path and
introduced a false-veto regression) were both disclosed in full in their SUMMARYs and are
resolved on disk — re-verified directly rather than taken on faith.

---

_Verified: 2026-08-26T12:07:21Z_
_Verifier: Claude (gsd-verifier)_
