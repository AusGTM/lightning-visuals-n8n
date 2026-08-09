---
phase: 41-validation-data-import-end-to-end-proof
plan: 01
subsystem: crm-automation
tags: [hubspot, n8n, merge-policy, icp-scoring, taxonomy, provenance]
status: complete

requires:
  - phase: 40-scoring-engine-remediation-notes
    provides: mergeCompanies.js's provenance-blob merge policy and cache-key discipline
      (Phase 16.3 stale-timestamp fix), and the remediated ICP scoring engine this
      phase's imported inputs will feed
provides:
  - config/june_candidates_source.json + config/june_candidates.json -- a reproducible,
    sha256-pinned, 66-row June-2026 candidate table (org_type/produces_content/
    country/sponsorship + confidence + evidence), consumed by scripts/build_cloud_workflows.py
    and by 41-02's resolve_june_ids.py
  - scripts/build_june_candidates.py -- the builder (deterministic enum table + D-02
    hand-curated exception list + D-03 confidence mapping)
  - a third "june_2026" mergeCompanies() candidate source in the "Merge Company" n8n
    Code node, with D-01 precedence (fresh research always wins outright), the D-04
    disagreement gate (org_type/produces_content conflicts suppress promotion + delete
    the cache-key stamp + push a synthetic needs_review decision), and a permanent
    "hubspot_native" firmographic-band fold (lv_revenue_band/lv_employee_band from the
    record's own annualrevenue/numberofemployees when the waterfall supplies neither)
affects: [41-03-deploy-and-canary, 41-04-full-run-and-parity-proof]

actuals:
  tokens: 635664
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Third mergeCompanies() candidate fold mirroring the existing two-call
      waterfall/claude_web shape (source=june_2026, source=hubspot_native), no new
      merge architecture"
    - "Precedence filter computed by building the LATER-winning candidate set first
      (researchData) and excluding its keys from the EARLIER-folded candidate set
      (juneData), while keeping the actual fold/spread order unchanged"
    - "Disagreement gate runs as a final pass AFTER every spread, deleting from
      canonicalPatch/cacheKeys and pushing a synthetic decision -- never re-orders the
      folds themselves"

key-files:
  created:
    - config/june_candidates_source.json
    - config/june_candidates.json
    - scripts/build_june_candidates.py
    - tests/test_june_candidates.py
    - tests/n8n/juneCandidateFold.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - tests/test_architecture_guard.py
    - tests/fixtures/companies_jscode_frozen.json

key-decisions:
  - "F1 resolved: lv_revenue_band/lv_employee_band derive from the record's own
    annualrevenue/numberofemployees natives (option a), not from extending the
    web-research prompt (option b, rejected as costing more per record for weaker data)"
  - "F2 resolved: D-04 routes through a synthetic needs_review decision + canonicalPatch/
    cacheKeys deletion, not through extending CONFLICT_WATCH (which has zero live
    consumers for org_type/produces_content on the cloud write path)"
  - "Big Screen Video, Racing.com, and The Creek Agency deliberately left on the
    deterministic org_type mapping -- docs/business/icp-scoring.md section 4 does not
    name any of the three, and the exception list exists to correct a documented
    misfit, not to encode a new claim"

patterns-established:
  - "Reproducible-from-repo dataset snapshot: verbatim sibling-repo copy + sha256 in a
    _meta header, so a downstream consumer never depends on an uncommitted directory"

requirements-completed: []

coverage:
  - id: D1
    description: "config/june_candidates.json: 66 taxonomy-legal rows with per-field
      evidence URLs and D-03 confidences, reproducible from the committed
      june_candidates_source.json snapshot"
    requirement: "DATA-01"
    verification:
      - kind: unit
        ref: "tests/test_june_candidates.py (15 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The built n8n/wf_enrichment_cloud.json Merge Company node folds
      JUNE_CANDIDATES as a third mergeCompanies() source behind fresh research"
    requirement: "DATA-01"
    verification:
      - kind: unit
        ref: "tests/n8n/juneCandidateFold.test.mjs (11 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "A June-vs-fresh-research disagreement on lv_org_type or
      lv_produces_content suppresses that field's promotion and emits a needs_review
      decision instead of silently overwriting"
    requirement: "DATA-01"
    verification:
      - kind: unit
        ref: "tests/n8n/juneCandidateFold.test.mjs#(e), #(f)"
        status: pass
    human_judgment: false
  - id: D4
    description: "lv_revenue_band and lv_employee_band derive from the record's own
      annualrevenue/numberofemployees natives when the waterfall supplies neither, and
      never override a waterfall-supplied band"
    requirement: "DATA-01"
    verification:
      - kind: unit
        ref: "tests/n8n/juneCandidateFold.test.mjs#(h), #(h2), #(i)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Whether the full 66-row exception-list judgement (which 3
      section-4-adjacent rows to leave on the deterministic mapping) reads correctly
      against the source analysis narrative"
    verification: []
    human_judgment: true
    rationale: "A qualitative read of docs/business/icp-scoring.md section 4 against
      three borderline companies (Big Screen Video, Racing.com, The Creek Agency) --
      no automated check can confirm the narrative genuinely does not name them versus
      a human re-reading section 4 directly."

duration: ~55min
completed: 2026-08-07
status: complete
---

# Phase 41 Plan 01: June-2026 Validation Dataset as a Third Merge Candidate Summary

**A 66-row, sha256-pinned June-2026 candidate table folds into the "Merge Company" n8n node as a third `mergeCompanies()` source, adjudicated against fresh research via a D-04 disagreement gate, with revenue/employee bands now derived from HubSpot-native firmographics.**

## Performance

- **Duration:** ~55 min
- **Tasks:** 3
- **Files created:** 5
- **Files modified:** 5 (2 as a direct consequence of the change, 3 as scoped
  deviation fixes to existing guard tests/fixtures)

## Accomplishments

- Built `config/june_candidates_source.json` (verbatim sibling-repo snapshot) and
  `config/june_candidates.json` (the mapped, sha256-pinned candidate table) via
  `scripts/build_june_candidates.py` — idempotent against its own committed snapshot.
- Wired the table into `scripts/build_cloud_workflows.py` as a `JUNE_CANDIDATES` JS
  constant, inlined into the "Merge Company" node as a third `mergeCompanies()` call
  (`source: "june_2026"`), proven end-to-end on a real company (Racing NSW,
  `15008671672`) as the plan's tracer.
- Completed the table with the D-02 hand-curated exception list: QRIC → `regulator`,
  Sportsbet/Entain → `gambling_operator` (+ veto-input flag), Supertech/Simtech →
  `hardware_vendor` (+ veto-input flag). Confidence distribution matches D-03 exactly
  (49 rows at 85, 16 at 65, 1 at 40); every `lv_org_type` value is asserted
  taxonomy-legal against `config/taxonomy.yaml` directly, not a hard-coded list.
- Added the D-01 precedence filter (fresh research wins outright on any field it
  answers), the D-04 disagreement gate (org_type/produces_content conflicts between
  June and fresh research suppress promotion, delete the stale-timestamp cache key,
  and push a synthetic `needs_review` decision), and the F1 native firmographic band
  fold (`lv_revenue_band`/`lv_employee_band` from the record's own
  `annualrevenue`/`numberofemployees` when the waterfall supplies neither).

## Task Commits

Each task was committed atomically:

1. **Task 1: One June company end-to-end (tracer)** — `49e792b` (feat)
2. **Task 2: Complete the 66-row table — exception list, veto-input flags,
   sponsorship** — `5a1a1f0` (feat)
3. **Task 3: Precedence, D-04 disagreement gate, native firmographic band fold** —
   `84aca89` (feat)

_Note: this plan's tasks were not TDD-typed at the sub-commit level, but every task
carried a `tdd="true"` attribute in the sense that its node/pytest tests were written
and run green before the task was declared done — no separate RED/GREEN commit split
was warranted since the tests and implementation landed together per task, matching
the plan's own `<verify>` blocks._

## Files Created/Modified

- `config/june_candidates_source.json` — verbatim snapshot of the sibling repo's
  `enriched_companies.json` (66 records), sha256-pinned by `config/june_candidates.json`'s `_meta`
- `config/june_candidates.json` — the mapped candidate table: `_meta` header + `rows`
  keyed by June HubSpot id (string)
- `scripts/build_june_candidates.py` — builder: sibling JSON → mapped table, with the
  D-02 `EXCEPTIONS` dict
- `tests/test_june_candidates.py` — 15 offline tests: mapping, boolean-string
  coercion, confidence mapping, `_meta` shape, idempotency, exception list, taxonomy
  legality, confidence distribution
- `tests/n8n/juneCandidateFold.test.mjs` — 11 node tests: the tracer promotion, the
  untabled-id no-op, D-04 agreement/disagreement, D-01 precedence, F1 band derivation
  (incl. the `Number("") === 0` landmine), D-07's firmographic-staged-only invariant
- `scripts/build_cloud_workflows.py` — module-scope `JUNE_CANDIDATES_JS` read/inline;
  `ENRICH_MERGE_CO`'s three-source fold, precedence filter, D-04 gate, native band fold
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json` — regenerated
  build artifacts (the "Merge Company" node's jsCode changed; `wf_scheduled_maintenance_cloud.json`
  was also regenerated but is byte-identical since it never references this node)
- `tests/test_architecture_guard.py` — AR-2 host-allowlist exemption derived from
  `config/june_candidates.json`'s own evidence URLs (deviation, see below)
- `tests/fixtures/companies_jscode_frozen.json` — re-baselined twice (Task 1, Task 3)
  against the deliberately-changed "Merge Company" jsCode (deviation, see below)

## Decisions Made

- **F1 resolved** (option a): `lv_revenue_band`/`lv_employee_band` derive from the
  record's own `annualrevenue`/`numberofemployees` natives, reproducing
  `src/normalizer.py`'s exact cut points in JS. Option b (widen the web-research
  prompt) was rejected per the plan's own cost/quality argument.
- **F2 resolved**: D-04's conflict routing is a synthetic `needs_review` decision plus
  `canonicalPatch`/`cacheKeys` deletion, not an extension of `CONFLICT_WATCH` —
  `CONFLICT_WATCH` feeds `row.conflicts`, which `ENRICH_DECIDE_CO_CLOUD` never reads.
  `CONFLICT_WATCH`'s grep mention count in `scripts/build_cloud_workflows.py` is
  unchanged before and after Task 3 (verified: **3**, not the plan's stated pre-task
  value of "2" — the plan's own count appears to have missed a pre-existing `ponytail`
  comment mentioning `CONFLICT_WATCH` by name, present since before this phase. The
  substantive invariant — Task 3 adds no new mention — holds regardless of which
  literal number is correct; confirmed against `git show <pre-Task-3-commit>` that all
  3 mentions predate this plan except the (also-updated) comment's wording, not its
  presence).
- **Exception-list judgement calls** (Task 2 action's three section-4-adjacent
  candidates): all three left on the deterministic mapping.
  - `17791151956` (Big Screen Video, bucketed `Other`) — its own June evidence text
    reads "hardware vendor to sport, not a content/broadcast producer," but
    `docs/business/icp-scoring.md` section 4 names only Supertech and Simtech as the
    AV/LED-hardware-vendor veto examples. Not added to the exception list.
  - `19363725157` (Racing.com Pty Ltd, bucketed `Broadcaster/Production` →
    `broadcaster`) — D-02 permits promoting a broadcaster row to `content_producer`,
    but section 4's producer list (Gravity Media, Panasonic Studio Productions, Jam
    TV, ABC) does not name Racing.com, and `broadcaster` and `content_producer` score
    identically (`+20` each in `config/icp_scoring.yaml`). Left as `broadcaster`.
  - `9681041418` (The Creek Agency, bucketed `Team/Club` → `individual_club_team`) —
    section 2's note that "The Creek Agency" is actually Albion Park Harness Racing
    Club is about HubSpot's *native industry tag* being unreliable, not about the
    `lv_org_type` mapping; `individual_club_team` is already the correct classification
    for a single racing venue. No exception needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug/scope-boundary] AR-2 architecture guard flagged ~60 static June
evidence-source hostnames as middleware-creep dependencies**
- **Found during:** Task 1, first full pytest run after wiring `JUNE_CANDIDATES` into
  the built workflow
- **Issue:** `tests/test_architecture_guard.py`'s AR-2 guard scans every node's
  `parameters` blob for `https?://` URLs and flags any host outside a small
  allowlist. Embedding June's `sources` evidence URLs (static provenance strings,
  never fetched at runtime) as part of the `JUNE_CANDIDATES` constant tripped this
  guard for every source domain across all 66 companies.
- **Fix:** Added a `_june_evidence_hosts()` helper that derives the exempt hostname
  set from `config/june_candidates.json` itself (mirroring the existing
  `linkedin.com`/`www.linkedin.com` "fixture data, never fetched" precedent), rather
  than hand-listing ~60 domains that would rot every time the table regenerates.
- **Files modified:** `tests/test_architecture_guard.py`
- **Verification:** `pytest tests/test_architecture_guard.py` — 52 passed
- **Committed in:** `49e792b` (Task 1 commit)

**2. [Rule 1 - Bug/scope-boundary] Frozen companies-jsCode fixture required deliberate
re-baseline (twice)**
- **Found during:** Task 1 and Task 3, each time after a deliberate change to the
  "Merge Company" node's jsCode
- **Issue:** `tests/test_companies_factory_frozen.py` is a byte-identity guard against
  `tests/fixtures/companies_jscode_frozen.json`, whose own docstring calls for
  re-baselining "only by an explicit, reviewed act" tied to a real change.
- **Fix:** Re-generated the fixture from `build_enrichment_cloud()`/
  `build_enrichment_local_live()` after each of Task 1's and Task 3's jsCode changes.
- **Files modified:** `tests/fixtures/companies_jscode_frozen.json`
- **Verification:** `pytest tests/test_companies_factory_frozen.py` — 4 passed after
  each re-baseline
- **Committed in:** `49e792b` (Task 1), `84aca89` (Task 3)

---

**Total deviations:** 2 auto-fixed (both Rule 1, both scope-boundary extensions of
existing guard tests rather than plan-listed files)
**Impact on plan:** Both were necessary consequences of embedding a real 66-company
dataset into a node whose byte-identity and host-allowlist are independently guarded
by pre-existing tests outside this plan's `<files>` lists. No scope creep beyond what
those two guards required to stay green and meaningful.

## Issues Encountered

- **Concurrent working tree with 41-02 (parallel wave-1 plan).** `41-02` committed its
  own files (`scripts/june_run_arm.py`, `tests/test_june_run_arm.py`,
  `.planning/.../41-02-SUMMARY.md`) into the same working tree and index while this
  plan was executing. Handled by using pathspec-limited commits
  (`git commit -F <msg> -- <exact files>`) for all three task commits, and checking
  `git status`/`git log` immediately before each commit — no cross-plan file ever
  entered a Task 1/2/3 commit.

## User Setup Required

None — no external service configuration required. This plan is fully offline; no
live HubSpot, n8n, or Anthropic call was made by any task.

## Next Phase Readiness

- `config/june_candidates.json` and the Merge Company node's three-source fold are
  ready for 41-02's pre-flight ID resolver and 41-03's live canary to consume.
- **DATA-01 stays "Pending" in `.planning/REQUIREMENTS.md`'s traceability table** —
  this plan covers only the offline half (inputs + provenance mechanism); the
  requirement closes only after 41-03's zero-spend structural proof and 41-04's live
  parity verdict over the landed population (per this plan's own
  `source_coverage_audit`, DATA-01 spans 41-01/41-02 T2/41-03 T1/41-04 T3). No
  `requirements.mark-complete` call was made for this reason.
- **Band-distribution measurement (for Plan 04's run report):** the offline plan has
  no live HubSpot access, so the revenue/employee band distribution across the 66 rows
  is reported here from F1's own planning-time measurement (`41-CONTEXT.md`, sourced
  from a June portal export of the same 66 companies), not re-verified this session:
  `annualrevenue` populated on 60/66 (32 land in `5-50M`/`50-500M` at +10 each, 24 in
  `1-5M`, 2 in `<1M`, 1 in `1B-1.2B` at −30, 1 in `1.2B+` at −50); 6 records have no
  `annualrevenue` at all. `numberofemployees` populated on 61/66; 5 records have none.
  These 6+5 no-derivable-band records are F1's documented option-c residue — no
  `lv_revenue_band`/`lv_employee_band` will land for them via this fold.

---
*Phase: 41-validation-data-import-end-to-end-proof*
*Completed: 2026-08-07*

## Self-Check: PASSED

All 10 created/modified files confirmed present on disk; all 3 task commit hashes
(`49e792b`, `5a1a1f0`, `84aca89`) confirmed present in `git log --all`.
