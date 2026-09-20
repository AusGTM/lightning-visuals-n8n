# Phase 75: Config-driven region whitelist and scoring-version staleness - Context

**Gathered:** 2026-09-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Move the geography rule out of code into `config/icp_scoring.yaml` as a whitelist
(`regions.home`, `regions.aliases`, `hard_vetoes.outside_home_regions`, `base_score.geography`
as `home`/`other`/`unknown`), generate `n8n/code/icpScoring.generated.js` from it via a new
`scripts/gen_icp_scoring_js.py`, and make both scoring engines and all three region normalisers
read the generated/loaded constants (Phase 46 parity rule, one commit). Stamp
`lv_icp_scoring_version` on every scored record, define stale as
`lv_icp_scoring_version != config.version`, and make version-stale records reach
`Decide Company Action` through the zero-cost recompute lane. The hard veto STAYS: a KNOWN
region outside the whitelist vetoes; blank/unknown never vetoes (2026-08-10 three-state rule).
Exit per ROADMAP: JSON regenerated, both suites green, disarmed deploy + bounce of the
enrichment and scheduled-maintenance workflows, one recompute proof each for a whitelisted and a
non-whitelisted company (0 credits, 2 executions).

Carried forward, not re-asked: three-state region rule; Phase 46 parity rule; generator
precedent `scripts/gen_escalation_js.py`; version is an opaque bumped string (no semver, no
timestamp); `Decide Company Action` remains the single writer of the veto fields and computes
no score/tier (Approach C).

</domain>

<decisions>
## Implementation Decisions

### Veto reason string
- **D-75-01:** Rename the geography veto reason now, region-agnostic. Default string
  `"Outside target regions"` (Claude's discretion on exact wording; no region suffix — tests
  assert byte-equality on one constant). — **Reversibility:** costly — ~15 asserting test sites
  (`tests/test_scoring_parity.py`, `tests/test_icp_scoring.py`,
  `tests/test_veto_remediation_report.py`, `tests/test_simulate_rubric_weights.py`,
  `tests/test_remediate_veto_companies.py`, `tests/test_backfill_dry_run.py`,
  `tests/n8n/antiIcpFlagMirror.test.mjs`, `tests/n8n/companyRecomputeLaneFlow.test.mjs`,
  `tests/n8n/materialConflictNoVetoFlip.test.mjs`, `tests/n8n/reviewQueueEndpoint.test.mjs`,
  `tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs`) change with it, and
  `lv_anti_icp_reason` churns once on every vetoed record at its next recompute.
- **D-75-02:** ALL THREE hard-veto reason strings come from `config/icp_scoring.yaml`
  (`hard_vetoes.<key>.reason`) via the generated JS (`HARD_VETO_REASONS` or equivalent).
  `Decide Company Action` (`scripts/build_cloud_workflows.py`, the three hard-coded
  `vetoReasons.push(...)` literals) stops hand-typing any of them. `src/icp_scoring.py` already
  reads them from yaml. Content and hardware strings keep their current VALUES.
- **D-75-03:** Records already carrying `"Non-ANZ geography"` are refreshed by the
  `config.version` bump + stale sweep only. No dedicated armed remediation script for the
  string.
- **D-75-04:** Frozen runData fixtures (`tests/n8n/fixtures/frozen/*`) and stress logs
  (`tests/stress-tests/*`) stay byte-identical — they are recordings, refresh policy none
  (README). Only tests that ASSERT the string change. Optional, additive only: freeze the
  phase-exit proof executions as a new fixture showing the new string.

### Whitelist + enum contents
- **D-75-05:** `regions.home` from day one = `AU, NZ, ANZ, US, GB, IE, CA, ZA, HK, SG, AE, IN`.
  Selection criteria (record in the yaml comment): English-speaking or native-English-audience
  market with a strong sports-broadcasting ecosystem. Considered and NOT included: `NG`, `KE`,
  `JM`, `PH`. — **Reversibility:** reversible — one-line yaml edit + version bump; but note
  every currently-vetoed company whose region resolves into this set flips at the first armed
  sweep, and the flip COUNT is unknown offline (researcher: size it before the first armed
  sweep).
- **D-75-06:** The normalisers emit the alias region code for any KNOWN mapped country
  (`US`, `GB`, `IE`, `CA`, `ZA`, `HK`, `SG`, `AE`, `IN`, plus `AU`/`NZ`); an unmapped known
  country still emits `Other`; blank/absent still emits the lane's blank sentinel (JS `null`,
  Python `"Unknown"`, ZoomInfo `None` — the existing per-lane contract is unchanged). Today
  everything non-AU/NZ collapses to `Other`, which is why a whitelist edit alone cannot rescue
  an already-stamped record (see Open items).
- **D-75-07:** Region token for the United Kingdom is `GB` (ISO2, matches the existing phone
  map). The existing `UK` enum option on `lv_country_region_normalized` is HIDDEN
  (`hidden: true`), never deleted. New enum options `GB, IE, CA, ZA, HK, SG, AE, IN` are added in
  `config/hubspot_properties.yaml`; `n8n/code/hubspotEnums.generated.js` is regenerated
  (`scripts/gen_hubspot_enums_js.py`). `EU` option: leave as-is (no alias emits it; Claude's
  discretion). — **Reversibility:** costly — HubSpot enum option delete is destructive; hide is
  the only undo.
- **D-75-08:** `regions.aliases` in `config/icp_scoring.yaml` is the SINGLE source for
  country-name/ISO2 → region code. `scripts/gen_icp_scoring_js.py` emits `REGION_ALIASES`, and
  that generated constant REPLACES the hand-typed `_COUNTRY_ISO2` map in
  `n8n/code/normalizeProviders.js` (phone normalisation reads the generated constant). The
  aliases table MUST be a superset of `_COUNTRY_ISO2`'s existing keys (`canada`, `ireland`,
  `india`, `singapore`, `great britain`, `england`, `united states of america`, …) or phone
  normalisation regresses to the AU heuristic for those — pin with the yaml-vs-JS parity test.

### HubSpot geography_score flow
- **D-75-09:** HubSpot flow `4626722240 Geography Score` REMAINS the `geography_score` writer.
  Its body (`config/hubspot_flows/4626722240-geography-score.after.json`, the `IN [AU,NZ,ANZ]`
  branch values) is REGENERATED from `regions.home` by the generator, never hand-edited, and
  pushed with `scripts/put_hubspot_flow.py`. `Decide Company Action` does NOT start writing
  `geography_score` (Approach C unchanged). Formulas cannot read enums (D-20), so no formula
  path exists.
- **D-75-10:** The flow PUT AND the schema writes (`lv_icp_scoring_version` property create,
  the new enum options, the `UK` hide, via `scripts/sync_hubspot_properties.py`) are run by the
  EXECUTOR in-plan, not deferred to the operator's exit UAT. The plan MUST state the fallback:
  if the permission classifier blocks the armed HubSpot write from a subagent, the executor
  stops at a checkpoint and the operator runs the identical command. Undo manifests as usual.
  — **Reversibility:** costly — a live HubSpot automation edit; the `.before.json` is the
  rollback body.
- **D-75-11:** yaml-vs-flow agreement is enforced twice: (a) an offline test asserting the
  committed `after.json` branch values == `regions.home`; (b) `scripts/check_schema_drift.py`
  gains a live compare of the fetched flow's branch values vs yaml (ordinary drift, exit 1 —
  the flow's presence/enabled state stays in the exit-2 do-not-archive set).
- Planner note: after the PUT, HubSpot re-evaluates the flow only when
  `lv_country_region_normalized` CHANGES (`shouldReEnroll: true`, event-based on that property).
  Existing records are not re-scored by the PUT itself; a record gains its new `geography_score`
  when its region is (re)written.

### Stale-version sweep path
- **D-75-12:** Route: inside `wf_enrichment_cloud`, the company branch's skip path
  (`IF Company Skip`) additionally tests `lv_icp_scoring_version != <generated VERSION>`; a
  mismatch reroutes the gate's `skip` into `Decide Company Action` (recompute), so EVERY path
  through the workflow ends in Decide. The webhook `recompute: true` lane (§13.0) is unchanged.
  `Company Gate`'s fetch list must include `lv_icp_scoring_version`.
- **D-75-13:** SJ-2 (monthly) carries the version-stale filter as the BACKSTOP, per ROADMAP.
  Verified blocker the planner must solve: `SJ-2 Company Gate` (`SJ2_CO_GATE`, REQUIRED
  `lv_org_type`/`lv_produces_content`, 180d TTL, `RECOMPUTE_REQUESTED = false` constant) runs
  BEFORE `SJ-2 Set Requested`; a version-stale but fresh record gets `skip` there and never has
  `lv_enrichment_requested` set — the search filter alone is inert. `SJ-2 Search`'s fetch list
  must add `lv_icp_scoring_version` and `SJ2_CO_GATE` must treat version mismatch as not-skip.
- **D-75-14:** A `config.version` bump is followed by an OPERATOR one-shot sweep: a
  `scripts/remediate_veto_companies.py::post_webhook_event`-style chunked POST with
  `recompute: true`, under bounded windows. The scheduled path is only the backstop.
- **D-75-15:** Version-stale scope = `lv_icp_scoring_version != current` AND the record carries
  scoring inputs (`HAS_PROPERTY lv_org_type` or `lv_produces_content`). Never-enriched companies
  are excluded. Researcher question: HubSpot search `NEQ` vs an UNSET property — on day one no
  record carries the property; likely shape is OR'd groups (`NOT_HAS_PROPERTY` + `NEQ`), each
  ANDed with the inputs `HAS_PROPERTY`; verify against HubSpot's documented operator semantics
  before building the filter.
- **D-75-16 (operator ruling 2026-09-20, supersedes Phase 57 / D-61-08 for THIS lane only):**
  STANDING arming for recompute writes. New builder constant `ALLOW_HUBSPOT_RECOMPUTE_WRITES`;
  `_writeSafetyAllows` gains a branch for a distinct recompute classification that checks this
  flag ALONE — no `TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS` allowlist. The existing three
  `ALLOW_HUBSPOT_*` flags are untouched and stay `"false"`. Planner-verified facts that shape
  the wiring: (a) today the recompute path REWRITES `action` from `skip` to `"enrich"` in
  Decide, and every write gate calls `_writeSafetyAllows("enrich", ...)` — there is NO
  `"recompute"` action today, so the new branch needs its own signal (a new action value or
  `row.recompute === true` / the D-75-12 reroute marker carried to the gate); (b) Decide's PATCH
  on that path is NOT just the veto triple — it also writes `lv_enrichment_status`
  (`complete`/`needs_review`), `lv_enrichment_needs_review`, and on needs-review
  `lv_enrichment_review_reason`/`lv_enrichment_review_candidate_json`; the flag's blast-radius
  statement in the plan must enumerate the ACTUAL property set (veto triple + version stamp +
  those status props) and the planner decides whether the status props ride the recompute PATCH
  or are dropped on that path. — **Reversibility:** one-way-adjacent — undo is an operator
  ruling re-instating Phase 57 for this lane, not a code revert; the flag itself is one
  literal.
- **D-75-17:** Ship `ALLOW_HUBSPOT_RECOMPUTE_WRITES = "false"`. The operator flips it `"true"`
  (deploy + bounce) only after the FIRST supervised bump sweep (D-75-14) is reviewed. The flip is
  a documented one-line deploy step in the phase's UAT/runbook, not part of the exit gate.
- **D-75-18:** Tooling consequences of a fourth, deliberately-true literal: (a)
  `operator-claude-plugin/scripts/n8n_arming.py`'s `OVERLAY_DISABLED_LITERALS`/
  `OVERLAYABLE_FLAGS`/`WRITE_ENABLING_FLAGS` must NOT include the new flag, so `disarm()` and
  `arm_for_dispatch()` never rewrite it; (b) every deploy/bounce/UAT read-back that asserts "all
  `ALLOW_*` literals read `false`" (`scripts/bounce_n8n_workflows.py` exits 1 while armed;
  `scripts/deploy_n8n_workflows.py`; UAT scripts) must enumerate `ALLOW_HUBSPOT_RECOMPUTE_WRITES`
  as allowed-true; (c) `config/execution_budget.yaml` is unchanged — the recompute lane rides
  the existing SJ-3 dispatch cap.
- **D-75-19:** Under the standing flag with `ALLOW_HUBSPOT_RECORD_WRITES = "false"`, a
  disarmed SJ-1/SJ-3 ENRICH dispatch still reaches Decide with a non-recompute action and is
  `write_blocked` — the version stamp lands only on recompute-classified runs and on armed
  enrich runs. State this plainly in the plan; nobody may assume every Decide run stamps.

### Rubric change guard
- **D-75-20:** `tests/test_rubric_change_guard.py` pins `base_score.geography`'s keys
  (`ANZ/AU/NZ/non_anz/unknown`); the rename to `home/other/unknown` turns it RED and its message
  demands the RUNBOOK re-score procedure before re-baselining. THIS phase's version bump +
  stale sweep IS that procedure: the executor re-baselines `PINNED_BASE_SCORE` in the same plan
  that adds the version stamp and sweep, never as a standalone edit, and the guard's message is
  updated to name `lv_icp_scoring_version` as the segmentation mechanism it said did not exist.

### Claude's Discretion
- Geography points: flat `home: 10`, `other: 0`, `unknown: 0` (ROADMAP default; no tiering).
- Exact rename string (default `"Outside target regions"`).
- Generated-JS module layout (`icpScoring.generated.js` exporting `VERSION`, `REGIONS_HOME`,
  `REGION_ALIASES`, `HARD_VETO_REASONS`, `GEOGRAPHY_POINTS`) and how
  `scripts/zoominfo_company_client.py::zoominfo_country_region` loads the yaml (import from
  `src/icp_scoring.py`'s loaded config, no second parser).
- Whether `sync_hubspot_properties.py` already supports `hidden: true` on an existing option
  (verify; add if not).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase spec and standing rules
- `.planning/ROADMAP.md` § Phase 75 — the goal text, exit criteria, and the three rulings this
  context resolves.
- `CLAUDE.md` §4.0 — live-portal naming (`lv_` prefix); §5.2 — `lv_icp_scoring_version`
  documented but never created; §10.3.1 — hardware veto OR predicate and the Phase 46 parity
  rule (both engines, one commit, never hand-edit `n8n/wf_enrichment_cloud.json`); §10.3.2 —
  named-account floor lives in the HubSpot formula + Python only, not n8n; §13.0 — the
  recompute lane, `IF Company Recompute`/`IF Company Skip`, arming still required to PATCH;
  §13.0.3 — n8n platform facts table (v1 execution order, Merge/sentinel rules) for any node
  splice; §19.0–19.1 — as-built cadences (SJ-2 monthly, SJ-3 daily) and why the poller cannot
  recompute; §21.1 — global kill switches.
- `.planning/phases/57-*/` (Phase 57 ruling on unattended writes) and `D-61-08` — the ruling
  D-75-16 supersedes for the recompute lane only.

### Scoring config, engines, normalisers
- `config/icp_scoring.yaml` — the file being extended (`regions.*`, renamed keys).
- `src/icp_scoring.py` — Python engine; already reads `hard_vetoes.<key>.reason` from yaml.
- `scripts/build_cloud_workflows.py` — `ENRICH_DECIDE_CO_CLOUD` (`_regionKey`, the three
  hard-coded reason literals, the PATCH shape), `_writeSafetyAllows`, `SJ2_CO_GATE`,
  `ENRICH_SJ3_BUILD_DISPATCH_EVENT`, `assert_no_self_dispatch`.
- `n8n/code/normalizeProviders.js` — `normalizeCountryRegion` (line ~146) and `_COUNTRY_ISO2`
  (line ~21).
- `src/normalizer.py::normalize_country_region`;
  `scripts/zoominfo_company_client.py::zoominfo_country_region` (docstring explains the
  per-lane blank sentinel contract).
- `scripts/gen_escalation_js.py` — generator precedent (json.dumps literals, `render()` called
  by the builder, currency test in `tests/test_judge_spec.py`).
- `scripts/gen_hubspot_enums_js.py`, `n8n/code/hubspotEnums.generated.js`,
  `config/hubspot_properties.yaml` (`lv_country_region_normalized` options, lines ~112–150).
- `tests/test_rubric_change_guard.py` — the pin D-75-20 re-baselines.
- `tests/test_scoring_parity.py` — parity suite; `test_veto_clear_after_correction` (`@live`).

### HubSpot geography flow and schema
- `config/hubspot_flows/4626722240-geography-score.after.json` / `.before.json` — the flow body
  regenerated in D-75-09; `scripts/put_hubspot_flow.py`, `scripts/fetch_hubspot_flow.py`.
- `scripts/check_schema_drift.py` — do-not-archive invariant (exit 2) and where D-75-11(b) lands.
- `scripts/sync_hubspot_properties.py` and `config/hubspot_migration/` — property create /
  enum option / undo-manifest mechanism.
- `config/hubspot_flows/lv_icp_fit_score-property.after.json` — the calculated formula that
  sums `geography_score`.

### Arming, grant, budget
- `operator-claude-plugin/scripts/n8n_arming.py` — `OVERLAY_DISABLED_LITERALS`,
  `WRITE_ENABLING_FLAGS`, `arm_for_dispatch`, `disarm` (D-75-18a).
- `operator-claude-plugin/scripts/write_grant.py` — the session-grant model D-75-16 departs from.
- `operator-claude-plugin/scripts/scheduled_arm.py` — the SJ-3 external arm companion.
- `scripts/bounce_n8n_workflows.py`, `scripts/deploy_n8n_workflows.py` — read-backs that must
  learn the fourth flag (D-75-18b).
- `config/execution_budget.yaml` — SJ-3 dispatch cap; unchanged.
- `scripts/remediate_veto_companies.py` — `post_webhook_event(..., recompute=True)` precedent
  for the D-75-14 bump sweep.

### Fixtures
- `tests/n8n/fixtures/frozen/README.md` — refresh policy: none (D-75-04).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/gen_escalation_js.py` → template for `scripts/gen_icp_scoring_js.py` (json.dumps
  literals, builder calls `render()` before inlining, currency test).
- `n8n/code/normalizeProviders.js::_COUNTRY_ISO2` + `_iso2()` — existing name→ISO2 map to be
  superseded by `REGION_ALIASES` (D-75-08); its keys are the minimum alias set.
- `scripts/put_hubspot_flow.py` / `fetch_hubspot_flow.py` — flow body PUT/GET with before/after
  JSON records.
- `scripts/remediate_veto_companies.py::post_webhook_event` — recompute POST helper with 300s
  read timeout, pinned-id-set pattern.
- `scripts/backfill_seed_company_scores.py::compute_components` — reads geography points from
  `src/icp_scoring.py`'s loaded config, never a second table; unchanged by this phase if the
  breakdown `signal: "geography"` component name is preserved.

### Established Patterns
- Phase 46 parity: any predicate change lands in `src/icp_scoring.py` AND `Decide Company
  Action` in one commit; JSON is always regenerated, never hand-edited.
- Config→generated-JS: yaml is the source, `n8n/code/*.generated.js` is the artifact, a test
  asserts the checked-in artifact is current (`test_judge_spec.py` precedent).
- Write safety: every HubSpot write passes `_writeSafetyAllows(action, id, domain)`; flags are
  string literals `"false"` in the deployed body overlaid by `n8n_arming.set_write_safety`;
  bounce after every PUT (stored ≠ running).
- Three-state region: `unknown` (blank) contributes 0 points and never vetoes — the
  2026-08-10 blank-region incident (17 AU racing clubs falsely vetoed) must not recur;
  `tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs` pins it.
- v1 execution order: a node on an empty branch never runs; any new IF/Merge splice on the
  company branch follows the sentinel/Merge rules in §13.0.3.

### Integration Points
- `IF Company Skip` (company branch of `wf_enrichment_cloud`) — D-75-12 reroute point; its
  false edge today goes to `Build Response Merge` (via stage Merges).
- `SJ-2 Search (stale refresh)` filter groups + `SJ2_CO_GATE` + `SJ-2 Set Requested` — D-75-13.
- `_writeSafetyAllows` — D-75-16 new branch; the `enrich`/`create`/`review` call sites at
  builder lines ~1913, ~2363, ~9793, ~10224, ~11566 stay as they are.
- HubSpot flow `4626722240` branch filter values — regenerated from `regions.home`.
- `lv_country_region_normalized` enum — new options + `UK` hidden.

</code_context>

<specifics>
## Specific Ideas

- Whitelist rationale to record in the yaml comment: "English-speaking or native-English
  audience + strong sports-broadcasting ecosystem"; excluded candidates `NG`, `KE`, `JM`, `PH`.
- The operator wants veto/version recompute to happen REGULARLY as data changes, not only inside
  operator sessions — that is the reason for D-75-16, and why the skip→recompute reroute
  (D-75-12) was preferred over flag plumbing on SJ-3.

## Open items for research/planning (not user decisions)
- Records vetoed today with `lv_country_region_normalized = Other` but a native `country` in the
  new home set cannot be rescued by the whitelist alone (region on record reads `Other`). Two
  options for the planner: re-enrich, or have the recompute path re-derive region from native
  `country` via `REGION_ALIASES` when the stored region is `Other`. Size the population first.
- HubSpot `NEQ` semantics for an unset property (D-75-15).
- Flip count at first armed sweep (D-75-05).
- Whether `sync_hubspot_properties.py` supports hiding an existing option.

</specifics>

<deferred>
## Deferred Ideas

- **Event-driven recompute:** subscribe `company.propertyChange` on the veto inputs
  (`lv_org_type`, `lv_produces_content`, `lv_country_region_normalized`,
  `lv_is_hardware_vendor`) so a human portal edit dispatches a recompute immediately instead of
  waiting for a scheduled dispatch. New capability (webhook subscriptions, §20.2 "later
  subscriptions"); its own phase.
- Wave-2 regions were folded into `regions.home` on day one (D-75-05); no separate wave remains.

### Reviewed Todos (not folded)
All 10 `todo.match-phase` hits were keyword noise and none touch geography or version stamping:
`2026-08-04-enrichment-throughput-ceiling`, `2026-09-04-company-domain-has-no-candidate-source`,
`2026-09-11-merge-multi-run-drain-and-grouping-unobserved`,
`2026-09-12-enrichment-lane-and-companies-branch-have-no-property-history-hop`,
`2026-09-12-rows-to-resume-current-outcomes-never-wired-fingerprint-branch-dead`,
`2026-09-17-csv-only-ingest-withholds-mobile-and-linkedin-into-blank-fields`,
`2026-09-17-stage-d-match-chunk-unchecked-rate`,
`2026-09-18-racing-clubs-researched-produces-content-false` (different veto — content, not
geography), `2026-09-18-suggest-contacts-stage2-block-not-promoted-to-a-script`,
`2026-09-18-zoominfo-mint-invalidates-prior-token-enrich-lane-cache-risk`.

</deferred>

---

*Phase: 75-config-driven-region-whitelist-and-scoring-version-staleness*
*Context gathered: 2026-09-20*
