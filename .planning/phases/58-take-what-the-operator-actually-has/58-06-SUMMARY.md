---
phase: 58-take-what-the-operator-actually-has
plan: 06
subsystem: enrichment-pipeline
tags: [n8n, hubspot, judge-escalation, non-clobber-merge, company-lane, veto]

requires:
  - phase: 58-05-native-fields-at-landing
    provides: "the 11983 incident (a false Non-ANZ veto from an unadjudicated region conflict) this plan traces and closes"
provides:
  - "n8n/code/providerConflict.js -- the shared, pure, parameterized cross-provider conflict predicate (detectConflicts/groupConflicts)"
  - "MATERIAL_CONFLICT_GROUPS (config/escalation_policy.yaml -> src/judge.py -> escalation.generated.js) -- the five decision-driving field groups"
  - "suppress-unless-adjudicated at Merge Company: a material/size conflict withholds every group member from canonicalPatch and flags the record, unless the judge already adjudicated a member field"
  - "region_conflict routed to the existing Sonnet judge (computeEscalation/applyUnadjudicated), and a provider-vs-provider conflict reason at the Judge Gate wrapper"
  - "one live execution (11987) proving the deployed lane carries the new predicate"
affects: []

actuals:
  tokens: 7400  # hand-authored diff only (chars/4); generated wf_enrichment_*.json + the
                # re-baselined frozen fixture add ~1.15M chars of MECHANICAL regeneration
                # on top, not hand-written content -- reported separately below, not folded
                # into this figure, since the estimate this pairs against was for authored work
  tasks: 4      # Task 4 (checkpoint) resolved by the operator 2026-08-26 -- see below
  commits: 2

tech-stack:
  added: []
  patterns:
    - "watched-field-list-as-parameter: n8n/code/providerConflict.js takes its watch list as an argument (never a module constant), which is what let the SAME module be inlined into both Merge Company (size+material) and Judge Gate (material only) without leaking the size list into RO-2-protected code"
    - "suppress-unless-adjudicated: a post-spread suppression block deletes conflicted group members from canonicalPatch unless row.judge_confidence_by_field already names one of the group's fields as adjudicated -- the group-level (not field-level) grant lets a resolved region also un-suppress its co-serialized native `country` sibling"

key-files:
  created:
    - n8n/code/providerConflict.js
    - tests/n8n/providerConflict.test.mjs
    - tests/n8n/materialConflictNoVetoFlip.test.mjs
  modified:
    - config/escalation_policy.yaml
    - src/judge.py
    - scripts/gen_escalation_js.py
    - n8n/code/escalation.generated.js
    - n8n/code/judge.js
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - tests/fixtures/companies_jscode_frozen.json
    - tests/n8n/judge.test.mjs
    - tests/n8n/researchScoring.test.mjs
    - tests/test_judge_spec.py
    - CLAUDE.md

key-decisions:
  - "The material-conflict field groups (5, modelled as GROUPS not bare fields) live once in config/escalation_policy.yaml, read by src/judge.py, emitted by scripts/gen_escalation_js.py into escalation.generated.js -- no second hand-typed list, mirroring the existing ESCALATION_CONFIDENCE_BAND/JUDGE_MIN_CONFIDENCE parity discipline."
  - "Group-level (not field-level) adjudication grant: when the judge adjudicates ANY member field of a group (e.g. lv_country_region_normalized), the WHOLE group is treated as resolved and no member is suppressed -- including native `country`, which the judge never adjudicates directly (it is not in _JUDGE_DATA_FIELDS). This is a deliberate reading of the plan's own acceptance criteria (the no-verdict test explicitly requires BOTH fields absent together) rather than a per-field grant, disclosed here since the plan text does not fully specify which reading it intends for the adjudicated cases."
  - "DEVIATION, disclosed for Task 4: tests/test_judge_spec.py's git diff is NOT empty, contra the plan's own top-level verification bullet. Task 2's own explicit instruction (\"Add the region to that list\" -- _JUDGE_DATA_FIELDS) is unimplementable without updating test_ta2_judge_eligible_and_deterministic_fields_are_disjoint's hardcoded field set, since that pre-existing test asserted the OLD boundary (region as deterministic-only) by name. The two SPECIFICALLY protected tests named in the plan's prohibitions -- test_ro2_judge_gate_cannot_see_size_conflicts and test_escalation_generated_js_is_current -- are unmodified and green. A sibling test in tests/n8n/researchScoring.test.mjs asserting the same old 5-field set was updated for the identical reason."
  - "Two pre-existing comments (judge.js's buildJudgeRequestBody docstring; build_cloud_workflows.py's judge_pass1_block_js) named size fields literally in prose. Once providerConflict.js was ALSO inlined into Judge Gate (Task 2), those comments' literal text leaked into Judge Gate's built jsCode and broke the RO-2 / no-size-field-name greps. Reworded both to be field-name-agnostic -- no behavior change, comment-only."

patterns-established:
  - "A shared conflict predicate parameterized by watch-list is the mechanism that lets one module serve two call sites with structurally different RO-2 obligations (Merge Company sees size; Judge Gate must never see it) without a second copy."

requirements-completed: [INPUT-01]

coverage:
  - id: D1
    description: "A cross-provider disagreement on the five decision-driving material fields (grouped so lv_country_region_normalized/country act as one disputed fact) is withheld from canonicalPatch and flags the record for review, unless the judge already adjudicated it -- pinned by tests built from execution 11983's own captured payloads"
    requirement: "INPUT-01"
    verification:
      - kind: unit
        ref: "tests/n8n/materialConflictNoVetoFlip.test.mjs (4 tests: no-verdict withholds+flags+no-flip, AU-verdict promotes+no-flip, non-ANZ-verdict promotes+DOES-flip, agreeing multi-source still promotes)"
        status: pass
      - kind: unit
        ref: "tests/n8n/providerConflict.test.mjs (9 tests: the shared predicate in isolation)"
        status: pass
    human_judgment: false
  - id: D2
    description: "A material provider conflict routes to the existing Sonnet judge; a size-only conflict never does (RO-2 preserved); every way the judge can fail to answer degrades to D1's outcome"
    requirement: "INPUT-01"
    verification:
      - kind: unit
        ref: "tests/n8n/judge.test.mjs (39 tests: region_conflict trigger matrix, applyUnadjudicated demotion, buildJudgeRequestBody payload fields, Judge-Gate-wrapper RO-2 grep, provider-conflict routing, 3 degradation paths, the deliberate non-addition)"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/test_judge_spec.py -q (9 tests, including test_ro2_judge_gate_cannot_see_size_conflicts and test_escalation_generated_js_is_current)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The deployed n8n lane carries the new material-conflict predicate, proven by one live execution's own runData (not a stored read-back)"
    requirement: "INPUT-01"
    verification:
      - kind: integration
        ref: "live execution 11987 (workflow 950HPb7a1GgSAIyZ), fetched via plain urllib with includeData=true -- see 'Live Proof' below"
        status: pass
    human_judgment: false
  - id: D4
    description: "Operator decides (a) whether size disagreements stay flag-only or should also be judge-checked (a structural change colliding with RO-2), and (b) what to do with the forensic's finding -- both disclosed at Task 4, ANSWERED 2026-08-26"
    verification: []
    human_judgment: true
    rationale: "Both questions are policy/architecture decisions the plan's own Task 4 explicitly reserves to the operator (gate=\"blocking\", autonomous: false per this plan's objective) -- automation cannot answer them. Operator ruling: (a) flag-only stays permanently, RO-2 untouched, no follow-up work opened; (b) forensic finding accepted as-is, the 70-vs-75 confidence rejection was correct behavior, no threshold change, no follow-up opened -- the material-conflict guard this plan built is the fix for the incident class."

duration: ~110min
completed: 2026-08-26
status: complete
---

# Phase 58 Plan 06: Material-Conflict Suppression (Judge Escalation for Property Conflicts) Summary

**A cross-provider disagreement on any of five decision-driving company fields — starting with the exact `lv_country_region_normalized`/`country` shape that fired a false Non-ANZ veto on Series Futsal Victoria in execution 11983 — can no longer promote unadjudicated and flip `lv_anti_icp_flag`; it is withheld, the record is flagged naming the disagreeing sources, and the existing Sonnet judge can resolve it (including a resolution that legitimately fires the veto). Tasks 1-3 complete and live-proven (execution 11987); Task 4 resolved by the operator 2026-08-26 -- plan complete.**

## Performance

- **Duration:** ~110min (Task 1 ~45min including the forensic; Task 2 ~45min; Task 3 ~20min; Task 4 checkpoint answered same day on resume)
- **Tasks:** 4 of 4 complete
- **Files modified:** 16 across 2 commits (3 created, 13 modified)

## Accomplishments

- **Forensic on execution 11983** (read via plain `urllib`, `includeData=true`, per project memory — `requests` fails against the n8n executions API in this environment): confirmed the exact defect shape from the record's own `scored.sourcesByField`/`best` — Lusha said `lv_country_region_normalized="AU"`, ZoomInfo said `"Other"` (a wrong-branch US match), no `agreedBy`, and `CONFLICT_WATCH` never watched this field, so ZoomInfo's trust-rank win (0.85 vs 0.80) promoted unadjudicated and fired the veto with `judge_reasons: []`. **Also answered the plan's open forensic question** (why the research candidate's own `"AU"` answer didn't override "Other" via last-spread-wins): the research candidate DID answer `"AU"`, but at confidence 70 — below `lv_country_region_normalized`'s 75 `min_confidence` threshold (`config/field_policy.yaml`) — so `mergeCompanies()` rejected it (`validation_status: "human_review_required"`) before last-spread-wins ever got a chance to apply it. **No second latent defect** — the mechanism is fully explained by the confidence gate, not a row-loss bug.
- **The structural guarantee (Task 1, tracer):** `n8n/code/providerConflict.js` — a pure, parameterized cross-provider conflict predicate (`detectConflicts`/`groupConflicts`) — replaces the inline `CONFLICT_WATCH` loop in `Merge Company` and is called with BOTH the size watch and the new `MATERIAL_CONFLICT_GROUPS` (5 decision-driving field groups from `config/escalation_policy.yaml`, emitted into `escalation.generated.js`). A post-spread suppression block deletes every group member from `canonicalPatch` (and any cache key) and pushes a synthetic `needs_review` decision naming the field and disagreeing sources — UNLESS `row.judge_confidence_by_field` already names an adjudicated member field, in which case the whole group is treated as resolved.
- **Judge routing (Task 2):** `computeEscalation` gains a `region_conflict` reason (research-vs-existing axis, mirroring `org_type_conflict` exactly); `applyUnadjudicated` demotes it the same way; `_JUDGE_DATA_FIELDS` gains the region so the judge payload can actually carry the disputed value; `buildJudgeRequestBody` adds `provider_conflicts` (the cross-provider `{source,value}` list). The Judge Gate WRAPPER (not `computeEscalation`) calls the same `providerConflict.js` predicate with material fields ONLY, keeping RO-2's 2-arg arity and the size-field-name absence intact by construction.
- **Deployed, bounced, and live-proven (Task 3):** all 5 cloud workflows deployed (200 each), the enrichment workflow bounced (deactivate→activate, independently re-read at each step, `updatedAt` unchanged across the bounce as expected), and one live execution (`11987`, against Racing And Sports `17861402663`, chosen by an offline `decideAction()` gate-state replay) proves the deployed `Judge Gate` node's OWN code (read from the execution's own `workflowData`, not a stored read-back) contains `detectConflicts`, `groupConflicts`, `MATERIAL_CONFLICT_GROUPS`, and `region_conflict`.

## Task Commits

1. **Task 1: The structural guarantee — one material field, suppressed unless adjudicated, and visibly flagged** — `169b35f` (feat)
2. **Task 2: Route material conflicts to the existing judge, and give size conflicts the flag they always needed** — `d5d08ae` (feat)
3. **Task 3: Deploy, bounce, and prove the deployed lane on one live execution** — no code commit (deploy/bounce/trigger only; the code deployed was already committed in Tasks 1-2). Evidence recorded in this SUMMARY.
4. **Task 4: Operator decides the two disclosed behaviour changes** — ANSWERED 2026-08-26, no code change required. See "Task 4 Resolution" below.

**Plan metadata:** (this commit, following the SUMMARY)

## Files Created/Modified

- `n8n/code/providerConflict.js` (new) — the shared conflict/group predicate
- `tests/n8n/providerConflict.test.mjs` (new) — the predicate in isolation
- `tests/n8n/materialConflictNoVetoFlip.test.mjs` (new) — the §21.2 pin, built from execution 11983's own captured payloads
- `config/escalation_policy.yaml` — `sonnet_5.material_conflict_field_groups` (5 groups) + `field_conflict: true`
- `src/judge.py` — `MATERIAL_CONFLICT_GROUPS` constant, read from the YAML
- `scripts/gen_escalation_js.py` — emits `MATERIAL_CONFLICT_GROUPS`
- `n8n/code/escalation.generated.js` — regenerated (byte-identical to generator output)
- `n8n/code/judge.js` — `region_conflict` reason in `computeEscalation`, matching demotion in `applyUnadjudicated`, region added to `_JUDGE_DATA_FIELDS`, `provider_conflicts`/`existing_lv_country_region_normalized` in `buildJudgeRequestBody`
- `scripts/build_cloud_workflows.py` — `ENRICH_MERGE_CO`'s conflict block replaced with the shared predicate + post-spread suppression; native `winners[f]` loop guarded; `COMPANIES_TARGET.judge_gate_inline_modules`/`judge_gate_header_comment_js`/`judge_pass1_block_js` updated
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json` — regenerated via `scripts/build_cloud_workflows.py`, never hand-edited
- `tests/fixtures/companies_jscode_frozen.json` — re-baselined twice (Merge Company changed in Task 1, Judge Gate changed in Task 2), each an explicit reviewed act per its own header
- `tests/n8n/judge.test.mjs` — 15 new tests (region_conflict, `buildJudgeRequestBody` fields, Judge Gate wrapper RO-2 grep, provider-conflict routing, 3 degradation paths, the deliberate non-addition)
- `tests/n8n/researchScoring.test.mjs` — 1 test updated (`_JUDGE_DATA_FIELDS` now 6 fields, not 5)
- `tests/test_judge_spec.py` — 1 test updated (`test_ta2_judge_eligible_and_deterministic_fields_are_disjoint`; see Deviations)
- `CLAUDE.md` §15.0 — new as-built delta documenting the materiality tiers, mechanism, and RO-2's preservation

## Execution 11983 Forensic

Pulled via plain `urllib` (project memory: `requests` fails against this n8n executions API) against workflow `950HPb7a1GgSAIyZ`, execution `11983` (2026-08-26T09:25:18Z, Series Futsal Victoria `283816805830`):

| Question | Answer, from the execution's own runData |
|---|---|
| What each provider returned for the country key | ZoomInfo `attributes.country = "United States"` (wrong-branch match); Apollo `organization.country = "Australia"`; Lusha `location.country = "Australia"`, `location.countryIso2 = "AU"` |
| What `Normalize + Score Company` scored | `scored.sourcesByField.lv_country_region_normalized = [{lusha, "AU"}, {zoominfo, "Other"}]` (Apollo emits no `lv_country_region_normalized` candidate at all — a structural asymmetry, not a bug: only ZoomInfo/Lusha's `normalizeProviders.js` branches derive that field). `best.lv_country_region_normalized` chose ZoomInfo, `agreedBy: []` — a genuine, correctly-detected-but-unwatched conflict. Separately, native `country`'s own `sourcesByField` showed 3 sources with Lusha/Apollo agreeing "australia" (2-of-3 majority, `agreedBy: ["apollo"]`) — `country` itself was NEVER in conflict; only its `lv_country_region_normalized` sibling was. |
| Why the research candidate's "AU" answer did not override "Other" via last-spread-wins | `research_candidate.data.lv_country_region_normalized = "AU"` at `confidence: 70`. `config/field_policy.yaml`'s `lv_country_region_normalized` policy is `system_owned, min_confidence: 75`. 70 < 75, so `mergeCompanies()`'s own deterministic gate rejected the research candidate (`merge.provenance.lv_country_region_normalized.validation_status = "human_review_required"`) — it never entered `researchMerged.canonicalPatch`, so the last-spread-wins mechanism had nothing to spread. **This fully explains the mechanism — no second latent defect.** |
| Whether `Judge Gate` produced any `judge_reasons` | `judge_reasons: []` at both `Judge Gate` and `Merge Company` on this row — confirmed, matching the incident report. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, found via advisor review] Two pre-existing comments leaked literal size-field names into Judge Gate's built jsCode once `providerConflict.js` was also inlined there.**
- **Found during:** Task 2, before rebuilding, while auditing for RO-2 compliance.
- **Issue:** `n8n/code/providerConflict.js`'s own header comment named "CONFLICT_WATCH" by identifier; `n8n/code/judge.js`'s `buildJudgeRequestBody` docstring named `annualrevenue`/`numberofemployees` literally, despite claiming to be "field-name-agnostic." Once `providerConflict.js` joined `judge_gate_inline_modules`, both leaked into `Judge Gate`'s built jsCode and would have broken `test_ro2_judge_gate_cannot_see_size_conflicts` and this plan's own "no size-field name" grep test.
- **Fix:** Reworded both comments to name-free prose ("the size watch-list", "no raw firmographic size figure"). No behavior change.
- **Files modified:** `n8n/code/providerConflict.js`, `n8n/code/judge.js`, `scripts/build_cloud_workflows.py` (one more instance of the same pattern in `judge_pass1_block_js`).
- **Verification:** `tests/test_judge_spec.py::test_ro2_judge_gate_cannot_see_size_conflicts` and `tests/n8n/judge.test.mjs`'s new grep test both pass.
- **Committed in:** `d5d08ae` (Task 2 commit).

**2. [Rule 4 - stated as a determination, not silently decided] `tests/test_judge_spec.py`'s TA-2 test hardcoded the OLD judge-eligible/deterministic-only boundary; Task 2's own explicit instruction to add the region to `_JUDGE_DATA_FIELDS` necessarily breaks it.**
- **Found during:** Task 2, first full pytest run after wiring the region into `_JUDGE_DATA_FIELDS`.
- **Issue:** The plan's top-level `<verification>` states `git diff --stat ... tests/test_judge_spec.py is empty`, but Task 2's `<action>` explicitly instructs "Add the region to that list" (`_JUDGE_DATA_FIELDS`), which is required for the judge to see/adjudicate the disputed region at all (without it, an AU-adjudication verdict is structurally impossible, and Task 1's own adjudicated-verdict acceptance tests would be untestable live). `test_ta2_judge_eligible_and_deterministic_fields_are_disjoint` hardcodes the pre-58-06 boundary by name and fails immediately once the region joins the judge-eligible set.
- **Resolution:** Consulted the advisor before proceeding; updated the test's hardcoded set to include the region in judge-eligible (removing it from deterministic-only), with a comment naming the operator ruling and date. The plan's own "Deliberately NOT produced" list scopes the protection to "no edit to `tests/test_judge_spec.py` **(RO-2 upheld)**" — i.e. RO-2 preservation is the stated intent, not a categorical file-level freeze. The two SPECIFICALLY named protected tests (`test_ro2_judge_gate_cannot_see_size_conflicts`, `test_escalation_generated_js_is_current`) are unmodified and pass. This is disclosed at Task 4 below, not decided unilaterally as "satisfied."
- **Files modified:** `tests/test_judge_spec.py`, `tests/n8n/researchScoring.test.mjs` (identical hardcoded-set issue, same fix).
- **Verification:** `.venv/bin/python -m pytest tests/test_judge_spec.py -q` — 9/9 pass, including both protected tests.
- **Committed in:** `d5d08ae` (Task 2 commit).

---

**Total deviations:** 2 auto-fixed (1 bug, 1 disclosed test-boundary update). **Impact on plan:** neither weakens RO-2 or the veto predicate; the second is a literal-verification-bullet miss that is fully disclosed to the operator rather than silently marked "passed."

## Live Proof (execution `11987`, disarmed)

**Deploy:** `DRY_RUN=false ALLOW_N8N_DEPLOY=true` (via a scratchpad dotenv-loading Python driver — direct `.env` access is Read/Bash-blocked to this agent, per project convention) updated all 5 live cloud workflows (200 each): `LV Backend Status (Cloud template)`, `LV Contact Ingest (Cloud template)`, `LV Enrichment (Cloud template)`, `LV Review Decision (Cloud)`, `LV Scheduled Maintenance (Cloud)`. `git status --porcelain n8n/wf_*.json` clean before and after (deploy pushes already-committed content).

**Bounce:** `POST /api/v1/workflows/950HPb7a1GgSAIyZ/deactivate` (200, `active: false`, independently re-confirmed by a fresh `GET`) then `POST .../activate` (200, `active: true`, independently re-confirmed by a fresh `GET`; `updatedAt: 2026-08-26T11:08:30.208Z` unchanged across the bounce, as expected — activation toggling never moves `updatedAt`/`versionId`).

**Gate-state pre-check (read-only, before spending any execution).** Chose the proof record by replaying `enrichmentGate.js::decideAction` offline against a candidate's last-known state (read from execution `11925`'s own runData, 2026-08-24, since this agent's HubSpot API credentials 401 against a direct live read — a real, disclosed limitation): Racing And Sports (`17861402663`), `REQUIRED = ["lv_org_type", "lv_produces_content"]`, both blank → predicted `action: "enrich"`, `reason: "missing: lv_org_type,lv_produces_content"`. Confirmed live: the actual execution reached the full waterfall/research/judge pipeline, not `skip`.

**Trigger:** one `POST /webhook/hubspot/enrichment/event` with `{"providers":["zoominfo","apollo","lusha"],"events":[{"objectId":"17861402663","objectType":"company"}]}` and the `X-Enrichment-Secret` header → **execution `11987`**, `success`, started `2026-08-26T11:14:12.247Z` — AFTER the deploy (`11:08:30`) and the bounce, so this execution ran the newly-deployed content.

**Read directly from execution 11987's own record** (both `resultData.runData` for the row trace and `workflowData.nodes` for the deployed node source — NOT a stored workflow read-back, since `workflowData` is embedded in this same execution GET):

- **The deployed `Judge Gate` node's own code contains the new predicate:** `detectConflicts`, `groupConflicts`, `MATERIAL_CONFLICT_GROUPS`, and `region_conflict` all present, read from `workflowData.nodes` inside this execution's response.
- **`judge_reasons: ["confidence_band"]`**, `needs_judge: true` — an EXISTING trigger fired (not the new material-conflict mechanism this time), and `material_conflicts: []` — **the negative that matters**: no material conflict fired on this record, because providers AGREED on region (`scored.sourcesByField.lv_country_region_normalized = [{lusha,"AU"},{zoominfo,"AU"}]`, `agreedBy` non-empty) and on `country` (2-of-3 majority, Apollo's outlier "hong kong" outvoted). This is the expected, healthy outcome for a record whose providers agree — it distinguishes "the guard did not fire" from "the guard is not there," which the guard-presence check above (reading the deployed Judge Gate's own source) independently confirms.
- **`Merge Company`'s `conflicts: []`** — consistent with the above; no group was suppressed.
- **`Decide Company Action`'s derived `properties`:** `lv_country_region_normalized: "AU"`, `lv_anti_icp_flag: "false"`, `lv_enrichment_needs_review: None` — a clean, correct enrich with no veto and no suppression, exactly as expected when no conflict exists.
- **A real judge call ran and genuinely degraded** (unplanned, live-observed): `Judge Call` fired (1 Anthropic judge call, at the declared cap of 1), but `judgeVerdictFromHttpItem` returned `{decision: "needs_review", confidence: 0, reason: "no usable judge response (execution error / missing content)"}` — a real production instance of the D5 fail-safe path, handled cleanly (`judge_confidence_by_field: {}`, no crash, no wrong promotion). Irrelevant to this record's outcome (no material conflict existed to adjudicate), but confirms the never-throws contract held in production, not only in tests.
- **No HubSpot write occurred:** response `action: "write_blocked"` and `ALLOW_HUBSPOT_RECORD_WRITES` stays baked `"false"` in the deployed workflow. **Disclosed limitation:** unlike 58-05's proof, this agent's HubSpot API credentials returned 401 on a direct read, so "no write occurred" rests on the disarmed baked flag and the response's own `write_blocked` action rather than an independent post-write HubSpot re-read.

**States plainly: the 11983 scenario itself is pinned OFFLINE** (`tests/n8n/materialConflictNoVetoFlip.test.mjs`, built from 11983's own captured payloads, run through the BUILT node code) — this live execution proves something different and equally necessary: the deployed lane carries the new modules, a normal enrich completes end to end with no regression, and judge-call spend is accounted for. It does not, and was not intended to, reproduce a natural three-source country disagreement live (per the plan's own instruction not to hunt for one).

**Execution actuals (cap 3, used 1):**
- 1 of 3 executions spent (`11987`).
- Judge calls: 1 of 1 cap used (`Judge Call` fired once, degraded per above).
- Lusha: `lv_lusha_company_id` newly cached for this record (was `null`); post-call balance 3899 credits (no pre-call balance captured for this specific run — a real, non-zero cost was incurred, unlike SFV's free cached re-enrich in 58-05).
- Apollo/ZoomInfo credit-check endpoints returned `null` in this sample — a pre-existing, unrelated issue (project memory: Apollo's credit-check key is not master).
- Anthropic calls: `Claude Web Research` + `Judge Call` — 2 calls total, bounded by the measured all-in `anthropic_usd_per_record = 0.068624 USD` figure per the declared budget; no per-call rate invented.
- No `ALLOW_HUBSPOT_*` or `ALLOW_N8N_ARM` flag was set at any point. Nothing was armed.

## Task 4 Resolution (operator, 2026-08-26)

**Type:** human-verify
**Gate:** blocking
**Status:** RESOLVED — both questions answered, plan proceeds to completion.

**What's built** (see the checkpoint task's own `<what-built>`/`<how-to-verify>` in `58-06-PLAN.md` for the full operator-facing text): the suppress-unless-adjudicated guarantee, judge routing for material conflicts, and one live execution proving the deployed lane carries it. Nothing has been written to any real record by this plan, and nothing was armed.

**Decision 1 — size (revenue/headcount) disagreements: flag-only stays, permanently.** The operator confirmed RO-2 stays untouched — no model call on a size disagreement alone. The review flag this plan added for size conflicts (where before there was silent, unflagged dropping) is the accepted end state, not an interim step toward judge-checking size. No follow-up work opened; RO-2's pinning test (`test_ro2_judge_gate_cannot_see_size_conflicts`) remains the standing guarantee.

**Decision 2 — the forensic's finding: accepted as-is.** The 70-vs-75 confidence rejection (the research candidate's correct "AU" answer, held below `lv_country_region_normalized`'s `min_confidence: 75` threshold) was correct behavior, not a defect. The operator ruled the threshold stays at 75 and opened no follow-up to revisit it — the new material-conflict guard this plan built (suppress-unless-adjudicated, routed to the judge) is the fix for the incident *class* execution 11983 represents, independent of where any single confidence threshold sits.

**Also acknowledged by the operator:** the disclosed `tests/test_judge_spec.py` diff (item 2 under "Deviations from Plan" above) is accepted as a disclosed deviation, not a plan miss requiring correction — it is a necessary consequence of Task 2's own explicit instruction to add the region to `_JUDGE_DATA_FIELDS`, and the two specifically-protected tests (`test_ro2_judge_gate_cannot_see_size_conflicts`, `test_escalation_generated_js_is_current`) remain unmodified and green.

**No code change resulted from Task 4.** Both rulings confirm the plan's existing behavior is the intended end state; nothing further to build.

## Re-verification (post-checkpoint, 2026-08-26)

Full plan-level `<verification>` re-run after Task 4's resolution, to confirm nothing drifted between the halt and this resume:

- `node --test tests/n8n/*.test.mjs` — **772/772 pass, 0 fail.**
- `.venv/bin/python -m pytest -q` — **3198 passed, 154 skipped, 4 failed** (all 4 failures pre-existing and unrelated: `tests/test_merge_policy.py::test_sc3_e2e_promote_forced_still_protects_manual`, `::test_sc4_full_source_attribution`, `::test_sc4b_cache_key_not_stamped_unless_promoted`, `::test_integ_wires_icp_scorer` — a `pydantic`/`anthropic` SDK version mismatch (`ThinkingBlock` has no `.text` attribute) unrelated to this plan's changes and known/deferred per project convention).
- `git diff --stat HEAD~3 HEAD -- src/icp_scoring.py tests/test_scoring_parity.py` — **empty**, confirming the veto predicate did not drift.
- `git diff --stat HEAD~3 HEAD -- tests/test_judge_spec.py` — **not empty** (the disclosed, operator-accepted deviation above); the two specifically-protected tests within it remain green and unmodified.
- `git status --porcelain n8n/wf_*.json scripts/` — **clean**, no uncommitted drift.

All plan-level acceptance criteria hold, modulo the one disclosed and now operator-accepted deviation.

## Known Stubs

None — every mechanism this plan adds (the shared predicate, the suppression, the judge routing) is wired end to end and live-proven on execution `11987`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

All 4 tasks complete, tested (39 + 9 + 4 new node tests, 772/772 node tests green overall, 3198/3202 Python tests green with 4 pre-existing unrelated failures), deployed, and live-proven. Task 4 answered by the operator 2026-08-26 (both disclosed behaviour changes accepted as-is, no follow-up work opened). This plan closes INPUT-01 (its final closing plan, alongside 58-01 and 58-05); the milestone checkbox lives in `.planning/milestones/v1.1-REQUIREMENTS.md`, not the root `REQUIREMENTS.md` (which lacks v1.1 IDs) — ticked as part of this completion. INPUT-03 and INPUT-04 are also ticked, since their own closing plans (58-01/58-02/58-03/58-04) are all independently complete. INPUT-02 stays open with its recorded defer-residual (`58-SPIKE-VERDICT.md`): the backend research node was deliberately not extended to seek a domain this phase, so rows where Claude cannot confidently propose one and the operator cannot supply one still fall to the accept-by-name path rather than a backend-researched domain.

Phase 58 as a whole: plans 01-06 all complete. Ready for phase seal / `/gsd-ship` review at the orchestrator's discretion — not performed by this execution, which was scoped to plan 58-06 only.

---
*Phase: 58-take-what-the-operator-actually-has*
*Completed: 2026-08-26 (all 4 tasks)*

## Self-Check: PASSED

- FOUND: `n8n/code/providerConflict.js`
- FOUND: `tests/n8n/providerConflict.test.mjs`
- FOUND: `tests/n8n/materialConflictNoVetoFlip.test.mjs`
- FOUND commit `169b35f` (Task 1)
- FOUND commit `d5d08ae` (Task 2)
- FOUND commit `37a95f4` (Tasks 1-3 SUMMARY, pre-checkpoint)
