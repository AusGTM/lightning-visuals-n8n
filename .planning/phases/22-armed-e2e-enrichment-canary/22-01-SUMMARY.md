---
phase: 22-armed-e2e-enrichment-canary
plan: 01
subsystem: infra
tags: [hubspot, n8n, anthropic, read-only-tooling, canary, cost-ledger]

requires:
  - phase: 21-transport-schema-hygiene
    provides: "current n8n Cloud deployment (v3 Lusha URLs, no native search nodes), the taxonomy module's EVIDENCE_GATED_ORG_TYPES vocabulary"
provides:
  - "scripts/canary_record_snapshot.py — read-only HubSpot snapshot/compare tool + research-gate prediction, reused by Plan 04 as the armed run's neighbour-untouched verifier"
  - "scripts/enrichment_cost_ledger.py (token half) — n8n executions API token-usage extraction, proven against a real execution"
  - "A committed live pre-canary snapshot of company 9604614548 + neighbour contact 201, with research_gate_will_fire=true recorded"
  - "A committed redacted fixture of a real n8n execution's Anthropic runData, settling Assumption A1"
affects: [22-02, 22-03, 22-04]

tech-stack:
  added: []
  patterns:
    - "Snapshot/compare over a recorded property list (never a freshly recomputed one) so a config change between snapshot and compare can't silently widen or narrow what's compared"
    - "Extraction functions defensive-by-construction: any malformed payload shape yields an explicit unavailable reason, never a raised exception (same contract as check_provider_credits.py's extractors)"
    - "Fixture redaction is allow-list only, never deny-list — copy known-safe keys out, never delete known-bad ones"

key-files:
  created:
    - scripts/canary_record_snapshot.py
    - scripts/enrichment_cost_ledger.py
    - tests/test_canary_record_snapshot.py
    - tests/test_enrichment_cost_ledger.py
    - tests/fixtures/n8n/execution_rundata_usage.json
    - .planning/phases/22-armed-e2e-enrichment-canary/snapshots/pre-canary-20260730T082110Z.json
  modified: []

key-decisions:
  - "Company property set for snapshot/compare = config/hubspot_properties.yaml's declared companies properties UNION scripts/snapshot_hubspot_schema.py's KNOWN_COMPANY_CUSTOM_PROPS (lv_org_type, lv_produces_content, lv_anti_icp_flag, lv_icp_fit_score, lv_icp_tier) — those five predate the yaml-driven property config and are reused, never re-typed, since the research-gate prediction needs them"
  - "Modification-timestamp property is never assumed: both hs_lastmodifieddate and lastmodifieddate are requested per record, and whichever the portal actually returns is recorded — live data confirmed companies return only hs_lastmodifieddate and contacts return only lastmodifieddate on this portal"
  - "compare mode's exit code is driven only by neighbors_changed; a changed target is the expected outcome of an armed run and never fails the comparator"
  - "A node key genuinely absent from n8n's runData (or present with an empty run list) is treated as a normal not-run state; a node key present with a non-list value is treated as a malformed/truncated payload and fails the whole token extraction closed rather than returning a partial result"
  - "Default neighbours are exactly the Phase 19 runbook's standing fixtures: no neighbour companies, one neighbour contact (201) — the only neighbour named in that precedent"

patterns-established:
  - "Read-only live-script idiom reused a third time: _has_credentials()/_has_n8n() skip-to-exit-0, portal/instance guard refusing before any call, argparse mode dispatch, 'a finding exits non-zero, it never crashes'"

requirements-completed: [REQ-armed-e2e-canary, REQ-canary-cost-ledger]

coverage:
  - id: D1
    description: "Read-only HubSpot snapshot/compare tool with a research-gate prediction mirroring the live Research Trigger Gate node's needsResearch() predicate"
    requirement: "REQ-armed-e2e-canary"
    verification:
      - kind: unit
        ref: "tests/test_canary_record_snapshot.py -q (16 tests, all behaviour-table cases including the evidence-gated-org-type case)"
        status: pass
      - kind: integration
        ref: "live snapshot + immediate compare run against company 9604614548 / contact 201 (documented below): neighbors_changed: 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "Live pre-canary read of company 9604614548 settling whether the armed canary will exercise the research+judge lanes (Assumption A2)"
    requirement: "REQ-armed-e2e-canary"
    verification:
      - kind: e2e
        ref: "python scripts/canary_record_snapshot.py (live) -> research_gate_will_fire: true"
        status: pass
    human_judgment: false
  - id: D3
    description: "n8n executions API token-usage extraction (token half of the cost ledger), pure and defensive against malformed runData shapes"
    requirement: "REQ-canary-cost-ledger"
    verification:
      - kind: unit
        ref: "tests/test_enrichment_cost_ledger.py -q (12 tests, all behaviour-table cases including not-run-vs-zero-tokens and the truncated-payload cases)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Live proof that this n8n Cloud instance's executions API returns per-node runData with Anthropic usage counters intact (Assumption A1), captured as a redacted committed fixture"
    requirement: "REQ-canary-cost-ledger"
    verification:
      - kind: e2e
        ref: "python scripts/enrichment_cost_ledger.py extract --execution-id 18 (live) -> full usage counters on Claude Web Research + Judge Call"
        status: pass
      - kind: unit
        ref: "tests/test_enrichment_cost_ledger.py -q -k redact (2 tests, including the committed-fixture credential-marker check)"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-07-30
status: complete
---

# Phase 22 Plan 1: Read-Only Canary Pre-Flight Tooling Summary

**Read-only HubSpot snapshot/compare tool with a research-gate prediction, plus an n8n executions-API token-usage extractor — both proven live, settling Assumption A2 (research WILL fire) and Assumption A1 (usage counters DO survive execution replay) before any write is armed.**

## Performance

- **Duration:** ~45 min
- **Completed:** 2026-07-30
- **Tasks:** 2/2
- **Files modified:** 6 created (2 scripts, 2 test files, 1 fixture, 1 snapshot artifact)

## Accomplishments

- Built `scripts/canary_record_snapshot.py` — read-only (GET-only) snapshot/compare tool over `src/hubspot_client.get_record`. Snapshot mode captures the target + neighbour records and prints a `research_gate_will_fire` prediction that mirrors the live `Research Trigger Gate` node's `needsResearch()` predicate verbatim, importing `EVIDENCE_GATED_ORG_TYPES` from `src/taxonomy.py` rather than re-typing it. Compare mode re-diffs against the snapshot's own recorded property list and exits non-zero only on a changed neighbour.
- Ran the tool live against company `9604614548` (target) and contact `201` (neighbour, per the Phase 19 runbook precedent). **Prediction: `research_gate_will_fire: true`** — `lv_org_type` is still `None`/unresolved on this record, so the armed canary in Plan 04 will actually exercise the Haiku-research-then-Sonnet-judge chain, not skip past it. Immediate compare against the just-written snapshot confirmed `neighbors_changed: 0`.
- Built the token-usage half of `scripts/enrichment_cost_ledger.py` — `list`/`extract`/`capture` subcommands over the n8n Public API's executions endpoint, reusing `_base_url()`/`_n8n_headers()`/`_get_live_workflows()` from `scripts/deploy_n8n_workflows.py`. `extract_token_usage()` is pure and defensive: a not-run node and a ran-but-usage-unavailable node are reported distinctly, and any malformed `runData` shape fails the whole extraction closed rather than raising or guessing at a partial result.
- Ran the tool live: `list` surfaced execution `18` (2026-07-29, company lane) as the most recent execution where `Research Trigger Gate` fired `research_needed: true`. `extract` against it showed **both `Claude Web Research` and `Judge Call` ran with full token counters present** (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` all populated, non-null). `capture` wrote the redacted fixture.
- Pinned the four Anthropic node names (`Claude Web Research`, `Judge Call`, `Contact Web Research`, `Contact Judge Call`) as a module constant with a test asserting all four exist in the committed `n8n/wf_enrichment_cloud.json`, so a node rename can't leave the ledger silently reading nothing.

## Assumption Verdicts (the whole point of this plan)

**A2 — will the canary exercise research+judge?** Settled: YES. Live read of company `9604614548`:
```
research_gate_will_fire: true
lv_org_type=None lv_produces_content=None
reason: lv_org_type is unresolved (None)
```
`lv_org_type` and `lv_produces_content` are both still blank on this record as of 2026-07-30 — no prior canary or scheduled run has populated them (Phase 21's enum migration has not landed yet, per the research doc's Pitfall 3 — the field is still free-text and empty, which is itself sufficient to fire the gate regardless of the enum question). Plan 04's armed run will genuinely exercise the full waterfall + Haiku research + Sonnet judge chain.

**A1 — does the executions API return per-node token usage?** Settled: YES. `GET /api/v1/executions/18?includeData=true` returned `data.resultData.runData` with both Anthropic `httpRequest` nodes' raw output intact:
```
node='Claude Web Research' status=ran model='claude-sonnet-5' input_tokens=20247 output_tokens=915 cache_creation_input_tokens=0 cache_read_input_tokens=0
node='Judge Call' status=ran model='claude-sonnet-5' input_tokens=1318 output_tokens=559 cache_creation_input_tokens=0 cache_read_input_tokens=0
node='Contact Web Research' status=not_run
node='Contact Judge Call' status=not_run
```
No truncation, no pruning observed on this instance. The Plan 03 cost ledger can be built against this observed shape with confidence, and Plan 04's runbook does NOT need an Anthropic-response-header fallback for token capture.

(Note: execution `18` predates the 2026-07-30 Haiku research-model swap — its research call used `claude-sonnet-5`, not the now-default `claude-haiku-4-5`. This doesn't affect the A1 verdict, which is about whether `usage` survives execution replay at all, not which model was called. Every execution against the *current* live deployment since that swap — ids `68` through `111` — had `ALLOW_WEB_RESEARCH` baked `true` but happened to land on records whose org-type/content were already resolved, so `research_needed` evaluated `false` and neither Anthropic node ran; execution `18` remains the most recent one that actually exercised both nodes.)

## Task Commits

1. **Task 1: Read-only record snapshot/compare tool + the live pre-canary read** - `89ce972` (feat)
2. **Task 2: Probe a real n8n execution read-only; extract Anthropic token usage; capture a redacted fixture** - `57808db` (feat)

_No TDD RED/GREEN split — tests and implementation were written together per task, matching this repo's established `type="auto" tdd="true"` convention of test+impl in one commit._

## Files Created/Modified

- `scripts/canary_record_snapshot.py` - read-only snapshot/compare tool + research-gate prediction (also the armed run's neighbour-untouched verifier)
- `scripts/enrichment_cost_ledger.py` - token-usage half of the cost ledger (list/extract/capture over n8n executions)
- `tests/test_canary_record_snapshot.py` - 16 tests, offline/hermetic
- `tests/test_enrichment_cost_ledger.py` - 12 tests, offline/hermetic
- `tests/fixtures/n8n/execution_rundata_usage.json` - redacted real execution payload (execution 18)
- `.planning/phases/22-armed-e2e-enrichment-canary/snapshots/pre-canary-20260730T082110Z.json` - live pre-canary snapshot artifact

## Decisions Made

See `key-decisions` in frontmatter. The most consequential one for Plan 04: the company property set merges `config/hubspot_properties.yaml`'s declared properties with `snapshot_hubspot_schema.py`'s `KNOWN_COMPANY_CUSTOM_PROPS` constant, because `lv_org_type`/`lv_produces_content` (needed for the prediction) predate the yaml-driven property config and live outside it.

## Deviations from Plan

None - plan executed exactly as written. The plan's own read_first list anticipated the property-set ambiguity (pointing at both `config/hubspot_properties.yaml` and, implicitly via the taxonomy/gate read_first items, the pre-existing ICP fields) and the timestamp-property ambiguity; both were resolved by reusing existing repo constants/idioms rather than inventing new ones.

## Issues Encountered

- The first live probe of recent "LV Enrichment (Cloud template)" executions (ids `108`, `111`, and everything in between) all showed `Research Trigger Gate` firing `research_needed: false` with skip reason `ALLOW_WEB_RESEARCH=false` — these executions predated the 2026-07-30 quick-task redeploy that baked `ALLOW_WEB_RESEARCH=true`. Confirmed the *live* deployment is current (the node body was read back directly and shows `true`), but no fresh webhook had fired against it since. Resolved by searching further back through the execution history for the most recent execution where the gate genuinely fired (`18`) — its usage data is still valid evidence for the A1 question the task asked, which is about the execution-data shape, not about which build produced it.

## User Setup Required

None - no external service configuration required. All calls made were read-only GETs against already-live, already-authenticated services.

## Next Phase Readiness

Plan 02/03/04 can now build with observation rather than assumption:
- Plan 03's cost ledger can extend `enrichment_cost_ledger.py` with provider-credit diffing, confident the token half's shape assumption is real.
- Plan 04's armed-canary runbook can proceed with confidence that company `9604614548` will genuinely exercise the research+judge chain, and can reuse `canary_record_snapshot.py` directly as its neighbour-untouched verifier (compare mode against a snapshot taken immediately before arming).
- No blockers. The Phase 21 org-type enum migration (referenced in 22-RESEARCH.md Pitfall 3) remains a separate, not-yet-closed dependency for the "writes succeed against the migrated schema" half of ROADMAP's Phase 22 criterion 2 — out of scope for this plan, unaffected by anything built here.

---
*Phase: 22-armed-e2e-enrichment-canary*
*Completed: 2026-07-30*

## Self-Check: PASSED

All 6 created files verified present on disk; both task commits (`89ce972`, `57808db`) verified present in `git log --oneline --all`.
