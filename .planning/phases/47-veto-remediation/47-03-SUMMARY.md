---
phase: 47-veto-remediation
plan: 03
subsystem: crm-scoring
tags: [hubspot, icp-scoring, python, pytest, web-research, anthropic, data-quality]

# Dependency graph
requires:
  - phase: 47-veto-remediation (Plan 01)
    provides: "scripts/remediate_veto_companies.py -- the disarmed-by-default script this plan extends with --research-only/--from-cache and the property-existence guard."
  - phase: 47-veto-remediation (Plan 02)
    provides: "47-COST-ESTIMATE.md -- the ex-ante budget this plan's live research spend was measured against."
provides:
  - "47-BEFORE.json -- the committed, read-only before-snapshot of all 17 pinned companies (VETO-01)."
  - "scripts/veto_remediation_report.py -- snapshot/predict/diff/classify plus the live property-existence guard (live_property_names/missing_property_names)."
  - "47-RESEARCH-RESULTS.json -- the one live web-research pass over all 17 records, cached so Plan 04 spends nothing researching a second time."
  - "D-21 (CONTEXT.md amendment): D-09's metadata-stamp layer narrowed to the 2 properties that exist live; the full 7-suffix trail moves to 47-RESEARCH-RESULTS.json / 47-RUN-REPORT.md."
  - "Two live-discovered data-quality fixes in build_input_patch: a strict lv_org_type enum allowlist, and a lv_is_gambling_operator boolean that must NEVER derive org_type (proven unreliable against 8/17 real records)."
  - "47-DRYRUN.md / 47-RUN-REPORT.md -- the mandatory disarmed dry-run (D-13) with exact PATCH payloads, webhook bodies, and the predicted per-record outcome."
affects: [47-04-veto-remediation]

actuals:
  tokens: 57716
  tasks: 3
  commits: 13

tech-stack:
  added: []
  patterns:
    - "Property-existence guard as a checked-set union (built payload keys + read-only OBSERVED_PROPS), delegating the HTTP call to an existing lister (scripts.check_schema_drift._get_live_properties) rather than issuing a second one -- refuses before any write branch, in both dry-run and armed mode."
    - "D-21 split: build_metadata_patch (narrowed, HubSpot-bound) vs build_metadata_record (full 7-suffix trail, repo-artifact-bound) -- same computation, two destinations, nothing dropped."
    - "Trust-boundary allowlist over keyword classifier: _classify_org_type only accepts an exact CRM enum match or a schema-conformant boolean (lv_is_hardware_vendor) that was independently validated correct against a real record -- never a keyword read of free text, which is exactly the 'they are all clubs' guessing D-17 forbids."
    - "Injectable research_fn seam on _process_one so --from-cache substitutes a cache lookup for a live research call without touching the function body -- mirrors the existing injectable reader/sleeper pattern from Plan 01's settle functions."

key-files:
  created:
    - scripts/veto_remediation_report.py
    - tests/test_veto_remediation_report.py
    - .planning/phases/47-veto-remediation/47-BEFORE.json
    - .planning/phases/47-veto-remediation/47-RESEARCH-RESULTS.json
    - .planning/phases/47-veto-remediation/47-DRYRUN.md
    - .planning/phases/47-veto-remediation/47-RUN-REPORT.md
  modified:
    - scripts/remediate_veto_companies.py
    - tests/test_remediate_veto_companies.py
    - .planning/phases/47-veto-remediation/47-CONTEXT.md (D-21/D-22 amendments, D-08/D-16/D-17's blocked/resolved trail)

key-decisions:
  - "D-21 (operator-confirmed at a Task 2 checkpoint): Task 2's live property-existence guard found 19 of 21 D-09 source-metadata property names absent from the portal -- only lv_org_type_verified_at and lv_produces_content_verified_at exist. Narrowed the HubSpot PATCH to those two; the full seven-suffix trail is recorded in 47-RESEARCH-RESULTS.json / 47-RUN-REPORT.md instead, never dropped. Re-verified live after narrowing: zero missing names, exit 0, zero writes."
  - "lv_org_type strict-enum gate (live-discovered, not anticipated by the plan): none of the 17 real research results returned a member of the CRM's lv_org_type enum -- src/web_research.py's RESEARCH_SYSTEM prompt does not constrain the model to it. build_input_patch now only accepts an exact enum match, or a derivation from the schema-conformant lv_is_hardware_vendor boolean (validated correct against Simtech LED). Not fixed at the prompt (shared/production, parity-tracked against the n8n mirror, out of files_modified) -- gated at this script's own trust boundary instead."
  - "lv_is_gambling_operator boolean is NEVER used to derive org_type, despite being the same schema shape as lv_is_hardware_vendor: it fired true for 8 of 17 records, every one a not-for-profit racing club whose own evidence_summary says the club merely hosts on-track TAB/bookmaker facilities (standard for every Australian racecourse), not that the club IS a gambling operator. Trusting it would have written 'gambling_operator' onto 8 racing clubs -- caught before the dry-run, not after."
  - "_normalize_region maps only unambiguous forms ('Australia', 'New South Wales, Australia' -> AU; 'New Zealand' -> NZ) and is NOT src/normalizer.py's normalize_country_region, whose else-branch defaults every unrecognized string to 'Other' -- that would manufacture a genuine non-ANZ veto from an ambiguous or entity-mismatched read. Jam TV's live research resolved to jamtv.it, an unrelated Italian company -- region 'Italy' correctly stays unresolved rather than becoming a veto."
  - "Skipped requirements mark-complete for VETO-01/COVER-01/COVER-02 -- Plan 01's precedent and this plan's own prohibitions: 47-04 owns the tick once the live armed run actually clears the vetoes."

patterns-established:
  - "Checkpoint-then-resume across two blocking gates in one plan run: a locked-decision conflict (D-09 unsatisfiable without creating properties) resolved via an operator decision recorded as a CONTEXT.md amendment (D-21) before code changed; then an external billing gate (Anthropic credits) resolved by the operator and confirmed live before resuming. Neither was silently worked around."
  - "Live data validated against the plan's own safety rules before being trusted: research output was checked for schema conformance (enum membership, boolean cross-consistency) rather than assumed correct because it parsed as JSON -- caught two real defects (org_type free text, gambling_operator over-broad boolean) that offline test fixtures (built by hand, already schema-correct) could never have caught."

requirements-completed: []

coverage:
  - id: D1
    description: "A committed before-snapshot records, for each of the 17 pinned ids, its live scoring-relevant properties, taken read-only with zero writes."
    requirement: "VETO-01"
    verification:
      - kind: unit
        ref: "tests/test_veto_remediation_report.py::test_snapshot_is_pure_read_and_completes_with_requests_post_raising"
        status: pass
      - kind: other
        ref: ".planning/phases/47-veto-remediation/47-BEFORE.json -- 17 rows, all lv_icp_tier=D, agreeing with 46-SIMULATION-REPORT.md's Live column for every row"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every property name in any built payload is confirmed to exist live before any arming happens; a missing name refuses the run rather than discovering a batch-wide 400 mid-window."
    requirement: "COVER-01"
    verification:
      - kind: unit
        ref: "tests/test_veto_remediation_report.py::test_remediate_main_with_fake_lister_missing_one_stamp_refuses_and_calls_no_write"
        status: pass
      - kind: other
        ref: "live read-only guard run against the portal -- zero missing names after D-21's narrowing (was 19 missing before)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Claude web research has run once against the live Anthropic web_search path for all 17 records; results are committed and demonstrably live, not the mock fixture."
    requirement: "VETO-01"
    verification:
      - kind: other
        ref: ".planning/phases/47-veto-remediation/47-RESEARCH-RESULTS.json -- 17 entries, zero evidence-URL intersection with tests/fixtures/claude_web_research_company.json"
        status: pass
    human_judgment: false
  - id: D4
    description: "The mandatory disarmed dry-run prints exact PATCH payloads and webhook POST bodies for all 17 records, making no HubSpot or n8n write."
    requirement: "VETO-01"
    verification:
      - kind: other
        ref: ".planning/phases/47-veto-remediation/47-DRYRUN.md -- 17 objectId (webhook bodies), 33 batch-update payload blocks, zero forbidden derived-field keys, zero token-shaped strings"
        status: pass
    human_judgment: false
  - id: D5
    description: "lv_produces_content is never written false on absent evidence, and every omitted field carries a stated per-record reason distinguishable from never-attempted."
    requirement: "VETO-01"
    verification:
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_produces_content_false_without_evidence_is_omitted_with_a_reason"
        status: pass
    human_judgment: false
  - id: D6
    description: "A predicted post-write score and tier exists per record before arming, via the same oracle (compute_icp_score) Phase 46 fixed and 47-CONTEXT.md's Specifics section asks this phase to reuse."
    requirement: "VETO-01"
    verification:
      - kind: other
        ref: ".planning/phases/47-veto-remediation/47-RUN-REPORT.md -- predicted_score/predicted_tier/outcome columns for all 17 records"
        status: pass
    human_judgment: false
  - id: D7
    description: "Live research output is validated against real CRM constraints (enum membership, boolean cross-consistency) rather than trusted because it parses as JSON -- two genuine data-quality defects caught before the dry-run."
    requirement: "VETO-01"
    verification:
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_out_of_enum_org_type_free_text_is_left_unresolved_not_guessed"
        status: pass
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_gambling_operator_boolean_never_derives_org_type_even_when_evidenced"
        status: pass
    human_judgment: false
  - id: D8
    description: "The cost/budget gate (COVER-02) runs and is printed before the paid research pass, and refuses rather than truncates if a run would exceed budget."
    requirement: "COVER-02"
    verification:
      - kind: other
        ref: "live run stdout: COST ESTIMATE printed (17 calls, ~$1.17) before RESEARCHED: lines, matching 47-COST-ESTIMATE.md's projection exactly"
        status: pass
    human_judgment: false
  - id: D9
    description: "Live production writes performed by this plan: none. The armed ceremony (VETO-02/VETO-03, the actual PATCH/webhook/settle sequence) is Plan 04's job."
    verification: []
    human_judgment: true
    rationale: "Genuinely outside this plan's scope -- confirmed by construction (DRY_RUN default true, ALLOW_VETO_REMEDIATION never set) and by the git-status check showing only artefact files touched, never a live-write confirmation."

duration: ~5h (including two blocking waits: an operator decision on D-21, and an Anthropic billing outage)
completed: 2026-08-12
status: complete
---

# Phase 47 Plan 03: Veto Remediation — Before-Snapshot, Property Guard, Live Research, Disarmed Dry-Run Summary

**Everything before the write window: a committed 17-record before-snapshot, a live property-existence guard that caught 19 non-existent D-09 metadata properties and triggered an operator-confirmed scope narrowing (D-21), one live Claude web-research pass over all 17 pinned companies that surfaced two real data-quality defects (a non-conformant org_type enum and an over-broad gambling_operator boolean) fixed before any payload was trusted, and the mandatory disarmed dry-run with every exact PATCH payload, webhook body, and predicted outcome on paper.**

## Performance

- **Duration:** ~5h wall-clock (~25min of active execution; the rest was two blocking waits for operator/external resolution)
- **Tasks:** 3 completed (Task 1, Task 2, Task 3 — each with additional live-discovered fixes beyond the original plan text)
- **Files modified:** 9 (6 created, 3 modified) plus the two externally-committed blocker artifacts (`47-BLOCKED.md`, the n8n-swallows-failures todo)
- **Commits:** 13 in this plan's own work (see Task Commits below)

## Accomplishments

- A read-only, committed before-snapshot of all 17 pinned companies (`47-BEFORE.json`) — all 17 read `lv_icp_tier=D`, agreeing exactly with `46-SIMULATION-REPORT.md`'s Live column.
- A live property-existence guard (`scripts/veto_remediation_report.py::live_property_names`/`missing_property_names`, wired into `remediate_veto_companies.main()`) that checks BOTH written and read-only property names before any write branch, in both dry-run and armed mode. It found 19 of 21 D-09 source-metadata properties absent from the live portal on its first real run — refusing loudly, spending $0, rather than 400ing an armed batch mid-window.
- **D-21 (operator-confirmed via a checkpoint):** D-09's metadata-stamp layer narrowed to the two properties that exist live (`lv_org_type_verified_at`, `lv_produces_content_verified_at`). The full seven-suffix evidence trail is not dropped — it's recorded in `47-RESEARCH-RESULTS.json` and the new `47-RUN-REPORT.md` instead, so the `config/field_policy.yaml` evidence-URL obligation is still met, just in a repo artifact rather than on the live record. Re-verified live after narrowing: zero missing names.
- One live Claude web-research pass (`claude-haiku-4-5` via the native `web_search` tool) over all 17 pinned companies, cached to `47-RESEARCH-RESULTS.json` so Plan 04 spends nothing researching a second time. Blocked once mid-session on an Anthropic billing outage (zero dollars charged — the call failed before any processing), resumed after the coordinator confirmed credits restored.
- **Two real data-quality defects caught in the live output, before any payload was trusted:**
  1. None of the 17 live results returned a member of HubSpot's `lv_org_type` enum (free text like `'private_company'`, `'Media company / Web television broadcaster'`) — `src/web_research.py`'s prompt doesn't constrain the model to it. Fixed with a strict allowlist in `build_input_patch` (never edited the shared prompt file). `lv_org_type` now resolves for exactly 1/17 (Simtech LED → `hardware_vendor`, evidenced) — an honest, evidence-only count, not a guessed one.
  2. `lv_is_gambling_operator` fired `true` for 8/17 records — every one a not-for-profit racing club whose own evidence text says it merely hosts on-track TAB/bookmaker facilities (standard for every Australian racecourse), not that the club IS a gambling operator. This boolean is now never used to derive `lv_org_type` (unlike `lv_is_hardware_vendor`, validated correct against Simtech LED in the same dataset).
- The mandatory disarmed dry-run (D-13): `47-DRYRUN.md` carries 17 webhook event bodies and 33 exact batch-update payload blocks (17×2 minus Editix, whose input+metadata patch is fully unresolved), all printed via the SAME `dry_run=True` code path the armed branch would use. Zero forbidden derived-field keys, zero token-shaped strings. `47-RUN-REPORT.md` carries the full D-09 evidence trail and the predicted score/tier/outcome for all 17 records.

## Task Commits

Each task was committed atomically (13 commits total for this plan):

1. **Task 1 (RED): failing tests for report + guard** — `276ac7c` (test)
2. **Task 1 (GREEN): per-ID before/after report script** — `e258cdd` (feat)
3. **Task 1 (artifact): live before-snapshot, 17 rows** — `d4827d3` (feat)
4. **Task 2 (GREEN): live property-existence guard** — `4f40eb7` (feat)
5. **docs: record D-21/D-22 CONTEXT.md amendments** — `351f42b` (docs)
6. **fix: narrow D-09 metadata stamps to the two that exist live (D-21)** — `024c112` (fix)
7. *(external, during the operator/billing wait)* docs: record Anthropic credit blocker and n8n silent-failure finding — `83a0ce2`
8. *(external)* chore: capture n8n silent-failure todo and mark phase blocked — `40312c3`
9. *(external)* chore: mark phase blocked in STATE.md — `1656c52`
10. **Task 3(a): capture live research results for all 17 pinned companies** — `c2bb7e5` (feat)
11. **fix: gate lv_org_type/region on a strict enum, never keyword-guess (D-14/D-17)** — `1a67814` (fix)
12. **fix: stop deriving lv_org_type from lv_is_gambling_operator (D-17)** — `d517600` (fix)
13. **Task 3(b): mandatory disarmed dry-run + D-21 full evidence trail (D-13)** — `29d03e2` (docs)

_Task 1 was `tdd="true"` — RED then GREEN commits shown. Task 2's RED commit (`276ac7c`) bundled both Task 1 and Task 2's failing tests in one file/commit, which briefly inverted per-task verify gating (Task 1's own `pytest -x` command couldn't pass in isolation until Task 2's functions existed too) — harmless in outcome, recorded here as a process deviation rather than letting the commit history imply strict per-task TDD it didn't quite follow. Task 3 was not `tdd="true"`; its fixes were committed as they were discovered, each with its own tests._

## Files Created/Modified

- `scripts/veto_remediation_report.py` — `snapshot`/`predict`/`diff`/`classify` (Task 1, the per-ID before/after cohort report), `live_property_names`/`missing_property_names` (Task 2, the property-existence guard). Read-only: imports only `get_record`/`search_records` from `src.hubspot_client`, no write helper anywhere.
- `scripts/remediate_veto_companies.py` — the property-existence guard wiring (`_run_property_existence_guard`, `_live_property_lister`), the D-21 split (`build_metadata_patch` narrowed vs `build_metadata_record` full), the two live-discovered data-quality gates (`_classify_org_type`, `_normalize_region`), the `--research-only`/`--from-cache`/`--out`/`--report-md` CLI flags, and `_render_run_report_md`.
- `tests/test_veto_remediation_report.py` — 17 offline tests: snapshot/predict/diff/classify, the property guard (including a fake-lister-driven `main()` refusal), and D-21's narrowed-set assertions.
- `tests/test_remediate_veto_companies.py` — 6 new tests for the two live-discovered fixes, plus the fake-lister patch to `_arm_credentials_and_env` (needed to keep Plan 01's suite green against the new guard — not in this plan's declared `files_modified`, added under Rule 3).
- `.planning/phases/47-veto-remediation/47-BEFORE.json`, `47-RESEARCH-RESULTS.json`, `47-DRYRUN.md`, `47-RUN-REPORT.md` — the four committed artifacts (three planned, `47-RUN-REPORT.md` added per the operator's D-21 instruction).
- `.planning/phases/47-veto-remediation/47-CONTEXT.md` — D-21 (metadata narrowing) and D-22 (Plan 04 arming waiver) amendments, both operator-authored/confirmed, not mine to originate.

## Decisions Made

See `key-decisions` in frontmatter for the full list. The two most consequential, both discovered live and not anticipated by the plan text:

1. **D-21's metadata narrowing** resolved a genuine conflict between a locked CONTEXT.md decision (D-09: full seven-suffix stamps) and the standing "no new HubSpot properties" constraint — escalated via checkpoint rather than silently narrowed, per the plan's own text ("a missing stamp is a scope question for the operator, never something to create").
2. **The org_type/gambling_operator gating fixes** were NOT escalated — they resolve under D-14's existing "prefer unknown over guessing" rule and D-17's explicit "the 17 are not all clubs, do not let research collapse toward a club default" warning, applied one level deeper than the plan text anticipated (to the research OUTPUT's schema conformance, not just to whether research ran at all). Auto-fixed per Rule 1/2, each with its own regression test.

## Deviations from Plan

1. **[Rule 4 — architectural, checkpointed] D-21: narrowed D-09's metadata-stamp scope.** Found during Task 2. 19 of 21 D-09 property names don't exist live. Fixed by operator-confirmed decision (see above), not unilaterally.
2. **[Rule 1/2 — auto-fixed, both in `build_input_patch`] `lv_org_type` free-text non-conformance and `lv_is_gambling_operator` boolean unreliability.** Found during Task 3(a) against the real live research output. Neither was anticipated by the plan text (which assumed the research prompt already produced enum-conformant values). Fixed with a strict allowlist and a boolean-signal restriction to only the one validated-correct case (`hardware_vendor`), each covered by a new regression test. Not fixed at the source prompt (`src/web_research.py`, shared/production, parity-tracked against the n8n JS mirror, out of this plan's `files_modified`) — flagged below as a follow-up.
3. **[Rule 3 — auto-fixed, blocking] `tests/test_remediate_veto_companies.py` needed a fake-lister patch** to keep Plan 01's suite green against the new property-existence guard. Not in this plan's declared `files_modified`.
4. **Two blocking checkpoints, both resolved by the coordinator/operator, not by me:** the D-21 scope conflict (decision checkpoint), and an Anthropic billing outage (human-action checkpoint, $0 spent, resumed after confirmed-live credit restoration).

None of these violate the plan's prohibitions: zero live HubSpot or n8n writes occurred anywhere in this plan; `DRY_RUN` stayed at its default; `ALLOW_VETO_REMEDIATION`/`ALLOW_N8N_ARM`/`ALLOW_HUBSPOT_RECORD_WRITES` were never set; Entain/Gravity Media/Ironman were never touched; no new HubSpot property was created; `lv_produces_content` was never written `false` on absent evidence; `scripts/run_scoring_parity.py`'s population sweep was not touched (stays red by design, Phase 49); no `PORTAL-FACTS.md` was edited.

## Known Stubs

None. Every unresolved field in the dry-run output carries an explicit, stated reason (visible in `47-RUN-REPORT.md`'s table and per-record trail) — never a silent blank.

## Findings For Plan 04 (and beyond)

- **Coverage is low but honest.** `lv_org_type` resolves for only 1/17 records under the strict gate — a large majority stay unresolved with a stated reason rather than a guess. This is the correct, safe output given the research prompt's non-conformance; it is NOT the ~4-unresolved figure D-17 estimated. Two remediation paths exist for a future pass, neither taken here (out of this plan's scope): (a) fix `src/web_research.py`'s `RESEARCH_SYSTEM` prompt to constrain the model to the enum and re-research (a paid re-run, the operator's cost call), or (b) add a cheap, narrowly-scoped classification pass over the already-captured evidence (no new web search needed). Recommend logging this as a phase-49-or-later follow-up.
- **Jam TV (`17317850381`) has an entity-resolution doubt worth a human look before Plan 04 processes it**, even though it correctly stays unresolved here: the live research matched `jamtv.it`, an unrelated Italian music web-TV company, not (evidently) the pinned HubSpot record's actual identity. A separate, already-classified "Jam TV Australia" (`40613322263`, broadcaster) exists in `46-SIMULATION-REPORT.md`. Worth operator attention before or during Plan 04, not blocking it.
- **All 17 records predict "clears veto" under the Python oracle** (`compute_icp_score`, via Phase 46's `region_raw` fix: an unresolved region reads as `unknown`, not a defaulted non-ANZ veto). This is a prediction against the oracle only, not proof against the deployed n8n `Decide Company Action` Code node. Plan 04's `settle_veto` read-back after the real webhook POST is the ground truth, not this table.
- **The coordinator's mid-session finding, carried forward verbatim for Plan 04:** the deployed n8n `Claude Web Research` node swallows Anthropic failures — during the billing outage, execution `11833` reported `status: success` with zero node errors while that node itself 400'd, passing the error object downstream as data. Full detail in `.planning/phases/47-veto-remediation/47-BLOCKED.md`; tracked as `.planning/todos/pending/2026-08-12-n8n-swallows-anthropic-credit-failure.md`. Not fixed in this plan (out of scope) — but it means Plan 04 must never treat n8n `status: success` as proof the veto cleared. `settle_veto`'s read-back of `lv_anti_icp_flag`/`lv_anti_icp_reason` is the only trustworthy evidence, which is exactly what it already does.
- **`47-04-PLAN.md` is now `autonomous: true` per D-22** (operator-delegated arming waiver, scoped to this run only) — recorded in `47-CONTEXT.md`, not acted on here; Plan 04's business.

## User Setup Required

None beyond what already happened during this plan's run (the operator resolved the D-21 scope question and the Anthropic billing outage). No further action needed to hand off to Plan 04.

## Next Phase Readiness

Plan 04 has everything it needs to run the actual armed ceremony: `47-BEFORE.json` (the before-state to diff against), `47-RESEARCH-RESULTS.json` (the cached research, consumable via `--from-cache` at zero additional research cost), `47-DRYRUN.md`/`47-RUN-REPORT.md` (the exact payloads and predicted outcomes an operator would review before arming), and a property-existence guard that has already been proven live at zero missing names. `requirements.mark-complete` was correctly skipped for VETO-01/COVER-01/COVER-02 — Plan 04 owns marking them once the live armed run actually clears the vetoes and VETO-03's HubSpot search returns zero.

---
*Phase: 47-veto-remediation*
*Completed: 2026-08-12*

## Self-Check: PASSED

- FOUND: `scripts/veto_remediation_report.py`
- FOUND: `tests/test_veto_remediation_report.py`
- FOUND: `.planning/phases/47-veto-remediation/47-BEFORE.json`
- FOUND: `.planning/phases/47-veto-remediation/47-RESEARCH-RESULTS.json`
- FOUND: `.planning/phases/47-veto-remediation/47-DRYRUN.md`
- FOUND: `.planning/phases/47-veto-remediation/47-RUN-REPORT.md`
- FOUND: `.planning/phases/47-veto-remediation/47-03-SUMMARY.md`
- FOUND commits: `276ac7c`, `e258cdd`, `d4827d3`, `4f40eb7`, `351f42b`, `024c112`, `c2bb7e5`, `1a67814`, `d517600`, `29d03e2`, `03736eb`
