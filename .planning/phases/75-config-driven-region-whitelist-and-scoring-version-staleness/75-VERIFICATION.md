---
phase: 75-config-driven-region-whitelist-and-scoring-version-staleness
verified: 2026-09-20T13:20:00Z
status: passed
score: 20/20 decisions verified (D-75-01..D-75-20); 22/22 prohibitions verified
covered_files: [".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-01-PLAN.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-01-SUMMARY.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-02-PLAN.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-02-SUMMARY.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-03-PLAN.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-03-SUMMARY.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-04-PLAN.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-04-SUMMARY.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-05-PLAN.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-05-SUMMARY.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-06-PLAN.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-06-SUMMARY.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-CONTEXT.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-DEPLOY-RECORD.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-SCHEMA-RECORD.md", ".planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-UAT.md", ".planning/todos/pending/2026-09-20-other-stamped-records-cannot-be-rescued-by-recompute.md", ".planning/todos/pending/2026-09-20-sj2-version-stale-backstop-is-armed-only.md", "CLAUDE.md", "config/execution_budget.yaml", "config/hubspot_flows/4626722240-geography-score.after.json", "config/hubspot_flows/4626722240-geography-score.post75.json", "config/hubspot_flows/4626722240-geography-score.pre75.json", "config/hubspot_migration/baseline/portal-schema-companies-phase75.json", "config/hubspot_migration/undo-manifest-7ee513f4-644d-4788-8b1f-fcda558fb767.json", "config/hubspot_properties.yaml", "config/icp_scoring.yaml", "docs/OPERATOR-RESCORE.md", "n8n/code/hubspotEnums.generated.js", "n8n/code/icpScoring.generated.js", "n8n/code/normalizeProviders.js", "n8n/wf_contact_ingest_cloud.json", "n8n/wf_enrichment_cloud.json", "n8n/wf_enrichment_local.json", "n8n/wf_enrichment_local_live.json", "n8n/wf_review_decision_cloud.json", "n8n/wf_scheduled_maintenance_cloud.json", "operator-claude-plugin/scripts/n8n_arming.py", "scripts/bounce_n8n_workflows.py", "scripts/build_cloud_workflows.py", "scripts/check_schema_drift.py", "scripts/deploy_n8n_workflows.py", "scripts/gen_geography_flow.py", "scripts/gen_hubspot_enums_js.py", "scripts/gen_icp_scoring_js.py", "scripts/remediate_veto_companies.py", "scripts/sync_hubspot_properties.py", "scripts/zoominfo_company_client.py", "src/icp_scoring.py", "src/normalizer.py", "tests/n8n/antiIcpFlagMirror.test.mjs", "tests/n8n/companyRecomputeLaneFlow.test.mjs", "tests/n8n/companyVersionStaleRecompute.test.mjs", "tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs", "tests/n8n/fixtures/frozen/exec_12682.runData.json", "tests/n8n/fixtures/frozen/exec_12683.runData.json", "tests/n8n/materialConflictNoVetoFlip.test.mjs", "tests/n8n/regionAliasParity.test.mjs", "tests/n8n/reviewQueueEndpoint.test.mjs", "tests/n8n/sj2VersionStaleGate.test.mjs", "tests/test_check_schema_drift.py", "tests/test_geography_flow_conformance.py", "tests/test_hubspot_properties_config.py", "tests/test_icp_scoring.py", "tests/test_icp_scoring_generated_currency.py", "tests/test_normalizer.py", "tests/test_recompute_flag_isolation.py", "tests/test_rubric_change_guard.py", "tests/test_sync_hubspot_properties.py", "tests/test_zoominfo_company_client.py"]
covered_digest: "v1:sha256:1f104ff8eb47d3c477bc26cdb68678fd56ffc371e9d6569018bd0abc62519dc0"
behavior_unverified: 0
overrides_applied: 0
---

# Phase 75: Config-driven region whitelist and scoring-version staleness Verification Report

**Phase Goal:** move the ANZ-only geography rule out of code into `config/icp_scoring.yaml` as
a whitelist, generate `n8n/code/icpScoring.generated.js`, make both scoring engines and all
three region normalisers read the generated/loaded constants, stamp `lv_icp_scoring_version` on
every scored record, define staleness, and reach the record through the zero-cost recompute
lane — with a disarmed deploy + bounce and one recompute proof each for a whitelisted and a
non-whitelisted company.

**Verified:** 2026-09-20
**Status:** passed
**Re-verification:** No — initial verification

## Method

This phase maps no REQUIREMENTS.md ids; coverage is keyed on the 20 locked decisions in
`75-CONTEXT.md` (D-75-01..D-75-20), each treated as a requirement and cross-checked against (a)
the six plans' `must_haves` frontmatter (truths, artifacts, key_links, prohibitions), (b) the
actual committed source (`config/icp_scoring.yaml`, `n8n/code/icpScoring.generated.js`,
`scripts/build_cloud_workflows.py`, `src/icp_scoring.py`, the three normalisers, the
arming/deploy/bounce tooling, the SJ-2 gate), (c) the offline test suites, and (d) the live
evidence — not by re-running any live HubSpot/n8n call (none was made by this verifier, per the
task instruction), but by opening the raw artifact files the SUMMARY/UAT prose describes
(the two frozen `runData` JSON files, the portal schema snapshot JSON, the post-PUT geography
flow JSON) and confirming their content directly rather than trusting the narrative.

## Goal Achievement

### Observable Truths (by decision id)

| # | Decision | Truth | Status | Evidence |
| --- | --- | --- | --- | --- |
| 1 | D-75-01 | Veto reason renamed to `"Outside target regions"`, byte-identical from both engines | ✓ VERIFIED | `config/icp_scoring.yaml:98`; `n8n/code/icpScoring.generated.js` `HARD_VETO_REASONS.outside_home_regions`; raw `runData` grep of `exec_12683.runData.json`: `"lv_anti_icp_reason": "Outside target regions"` |
| 2 | D-75-02 | All three hard-veto reason strings read from yaml; zero hand-typed reason literals in `Decide Company Action` | ✓ VERIFIED | grep of `scripts/build_cloud_workflows.py` for the three reason strings finds only 3 historical-incident comment occurrences (documented, exempted in 75-01-SUMMARY), zero functional literals; `HARD_VETO_REASONS.*` read at push sites (L5292-5294) |
| 3 | D-75-03 | `config.version` bumped, `Decide Company Action` stamps `lv_icp_scoring_version` on every company it decides, unconditionally | ✓ VERIFIED | `config/icp_scoring.yaml:3` `version: "lv-icp-v0.2"`; `build_cloud_workflows.py:5321` `properties.lv_icp_scoring_version = VERSION;` (unconditional, outside any `if`); raw `runData` grep of both fixtures: `"lv_icp_scoring_version": "lv-icp-v0.2"` |
| 4 | D-75-04 | Every file under `tests/n8n/fixtures/frozen/` and `tests/stress-tests/` byte-identical to pre-plan content; only new fixtures added | ✓ VERIFIED | `git diff dfef89d9 --stat -- tests/n8n/fixtures/frozen/ tests/stress-tests/` shows 2 files, both insertions-only (`exec_12682`, `exec_12683`), zero existing-file modifications |
| 5 | D-75-05 | `regions.home` = `[AU, NZ, ANZ, US, GB, IE, CA, ZA, HK, SG, AE, IN]` with rationale comment | ✓ VERIFIED | `config/icp_scoring.yaml:9-21` + comment `:22-27`; mirrored in generated JS |
| 6 | D-75-06 | All three normalisers: known-mapped country → alias code, unmapped known country → `Other`, blank/absent → lane's own sentinel unchanged | ✓ VERIFIED | `normalizeProviders.js:152-156` (`null` sentinel, `REGION_ALIASES[v] \|\| "Other"`); `src/normalizer.py:81-89` (`"Unknown"` sentinel); `scripts/zoominfo_company_client.py:108-123` (`None` sentinel) — all three read the one `region_aliases()`/`REGION_ALIASES` source |
| 7 | D-75-07 | 8 new enum options + `UK` hidden (not deleted) + `lv_icp_scoring_version` property declared | ✓ VERIFIED | `config/hubspot_properties.yaml` GB/IE/CA/ZA/HK/SG/AE/IN options + `UK` `hidden: true` comment (D-75-07) + `lv_icp_scoring_version` property block; parsed `portal-schema-companies-phase75.json` directly: 16 options incl. `UK True` (hidden), no option removed, `lv_icp_scoring_version` present (`type=string, fieldType=text, group=lv_enrichment`) |
| 8 | D-75-08 | `regions.aliases` is the single source; `_COUNTRY_ISO2` deleted; superset pinned by parity test | ✓ VERIFIED | `grep _COUNTRY_ISO2 n8n/code/normalizeProviders.js` → zero hits; `tests/n8n/regionAliasParity.test.mjs` present and green (part of 1350-pass node run) |
| 9 | D-75-09 | Geography flow body regenerated from `regions.home`, never hand-edited; `Decide` writes no `geography_score` | ✓ VERIFIED | `scripts/gen_geography_flow.py` present; `gen_geography_flow.py && git diff --quiet -- config/hubspot_flows/` → clean (regen is a no-op); parsed `4626722240-geography-score.post75.json` directly: branch filter `values` = `['AU','NZ','ANZ','US','GB','IE','CA','ZA','HK','SG','AE','IN']` exactly; `grep -n geography_score scripts/build_cloud_workflows.py` → zero hits (confirms no write site in `Decide Company Action`) |
| 10 | D-75-10 | Live schema writes + flow PUT run in-plan with the stated fallback | ✓ VERIFIED | `75-SCHEMA-RECORD.md`: operator ran every write from the interactive shell at the plan-05 `checkpoint:decision`, per the documented fallback pattern |
| 11 | D-75-11 | Offline test pins committed flow body == `regions.home`; live drift check exits 0/1 (not archived) | ✓ VERIFIED | `tests/test_geography_flow_conformance.py` present and green; `75-SCHEMA-RECORD.md`: `check_schema_drift.py` post-fix run → `geography_flow_drift = in_sync`, `do_not_archive.ok = True`, exit 0 |
| 12 | D-75-12 | Version-stale `skip` reroutes into `Decide` via the *existing* `IF Company Recompute` lane (gate-derived marker, zero new nodes); a fresh `skip` is unaffected | ✓ VERIFIED | `build_cloud_workflows.py` sets `row.recompute`/`row.recompute_reason = "version_stale"` at the gate; enrichment body node count independently counted by this verifier: 289 (committed) == 289 (`git show dfef89d9:n8n/wf_enrichment_cloud.json`, pre-phase) — zero nodes added; `tests/n8n/companyVersionStaleRecompute.test.mjs` directly opened: `test("a version-stale skip reroutes: recompute=true, recompute_reason=version_stale, action=enrich, reaches Decide")` asserts `r.gate.action === "enrich"`, `r.gate.recompute_reason === "version_stale"`, `r.decided.action !== "create"` — the transition itself is exercised offline, not merely presence-checked. Live proofs (D-75-12 note) used the explicit `recompute` request flag rather than a real version mismatch — `[documented]` for that specific path per the phase's own tagging |
| 13 | D-75-13 | SJ-2 search selects version-stale-but-fresh company; `SJ2_CO_GATE` treats mismatch as not-skip | ✓ VERIFIED | `build_cloud_workflows.py:11273-11295` (NOT_HAS_PROPERTY/NEQ filter groups + gate fetch); `tests/n8n/sj2VersionStaleGate.test.mjs` present and green — code-level only, no live SJ-2 tick this phase (monthly cadence; next tick is the trigger of the pending todo below) |
| 14 | D-75-14 | Operator one-shot bump sweep documented as a runbook procedure | ✓ VERIFIED | `docs/OPERATOR-RESCORE.md` § "AS-BUILT AMENDMENT — 2026-09-20 (Phase 75)" §(a) names the chunked `post_webhook_event(recompute=True)` pattern and bounded-window rules |
| 15 | D-75-15 | SJ-2 version-stale filter ANDed with `HAS_PROPERTY lv_org_type`; never-enriched company excluded | ✓ VERIFIED | `build_cloud_workflows.py:11282-11289` filter-group structure (OR'd unset/NEQ groups each ANDed with the input-presence conjunct) |
| 16 | D-75-16 | `ALLOW_HUBSPOT_RECOMPUTE_WRITES` grants a `recompute`-classified write alone, no allowlist; unreachable from the other 3 flags | ✓ VERIFIED | `build_cloud_workflows.py:2575` default, `:2598` gate — `if (action === "recompute") return ...;` ordered first, returns rather than falling through |
| 17 | D-75-17 | Ships `"false"`; flip documented as a post-phase, post-review operator step, not part of exit gate | ✓ VERIFIED | `WRITE_SAFETY_DEFAULTS["ALLOW_HUBSPOT_RECOMPUTE_WRITES"] = "false"`; independent grep of all 4 deployed `n8n/wf_*.json` bodies: `ALLOW_HUBSPOT_RECOMPUTE_WRITES = \"false\"` at every site (4+4+3+5 = 16 occurrences, zero `"true"`); `docs/OPERATOR-RESCORE.md` §(b) documents the flip as a separate later step; `75-UAT.md` confirms "D-75-17 flip not performed" |
| 18 | D-75-18 | (a) excluded from arming/overlay sets, (b) bounce compares live vs committed rather than hardcoding false, (c) execution_budget.yaml unchanged | ✓ VERIFIED | (a) zero `RECOMPUTE` hits in `operator-claude-plugin/scripts/n8n_arming.py`; `deploy_n8n_workflows.py:223` names the exclusion; (b) `bounce_n8n_workflows.py:36-44` `COMMITTED_TRUTH_FLAGS = ("ALLOW_HUBSPOT_RECOMPUTE_WRITES",)`; (c) `git diff dfef89d9 -- config/execution_budget.yaml` empty |
| 19 | D-75-19 | Disarmed non-recompute enrich dispatch still reaches `Decide` and is `write_blocked`; version stamp lands only on recompute-classified/armed-enrich runs | ✓ VERIFIED | `tests/n8n/companyVersionStaleRecompute.test.mjs` directly opened: asserts `action === "write_blocked"` / `write_blocked_reason` matches `/recompute/i` for the disarmed recompute path; logically entailed for the non-recompute path by the `_writeSafetyAllows` structure verified under D-75-16 (an `enrich` action falls through to the pre-existing `ALLOW_HUBSPOT_RECORD_WRITES` gate, unchanged by this phase and independently tested elsewhere) |
| 20 | D-75-20 | Rubric-change guard re-baselined to `home/other/unknown`; message names `lv_icp_scoring_version` | ✓ VERIFIED | `tests/test_rubric_change_guard.py:50` `"geography": {"home": 10, "other": 0, "unknown": 0}`; `:109` message names `lv_icp_scoring_version` as the segmentation mechanism |
| — | Three-state rule | Blank/absent region → `"unknown"`, 0 points, no veto in both engines (2026-08-10 rule, unchanged) | ✓ VERIFIED | `build_cloud_workflows.py:5273-5275` `_regionKey`: `undefined/null/"" → "unknown"`, else `home`/`other`; `src/icp_scoring.py:138-144` mirrors; veto block only checks `region === "other"` (L5292), never `"unknown"` |

**Score:** 20/20 decisions verified (plus the carried-forward three-state rule), 0 present-but-behavior-unverified, 0 overrides.

### Prohibitions (must-NOT checks, all 6 plans, ~22 items)

Every plan's `must_haves.prohibitions` is `verification: judgment`-tier by construction (no
plan declared `verification: test`). Each is resolved to a disposition below — none silently
absorbed into the passing verdict.

| # | Plan | Prohibition | Disposition | Evidence |
| --- | --- | --- | --- | --- |
| 1 | 01 | Blank/unknown region never sets `lv_anti_icp_flag` in either engine | ✓ held | veto block checks `region === "other"` only (both engines), never `"unknown"` — see three-state row above |
| 2 | 01 | Empty/missing `regions.home` never silently degrades; generator raises | ✓ held | `scripts/gen_icp_scoring_js.py:32-48` raises `AssertionError`-style on empty/non-string `regions.home` members and empty veto reasons |
| 3 | 01 | No frozen fixture rewritten by plan 01 | ✓ held | `git diff dfef89d9 --stat -- tests/n8n/fixtures/frozen/` — insertions-only, both new files land in plan 06, not plan 01 |
| 4 | 01 | No hand-edit of `n8n/wf_*.json` | ✓ held | `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/` → clean (regen is a no-op) |
| 5 | 02 | No normaliser changes its blank sentinel | ✓ held | confirmed per-lane in D-75-06 row (`null`/`"Unknown"`/`None` unchanged) |
| 6 | 02 | No second YAML parser introduced | ✓ held | `src/normalizer.py:11` and `scripts/zoominfo_company_client.py:31` both `import region_aliases` from `src.icp_scoring` — one loader |
| 7 | 02 | No enum option deleted from `config/hubspot_properties.yaml` | ✓ held | `UK` option present with `hidden: true` comment, never removed; declared options are additive only |
| 8 | 02 | No hand-edit of `n8n/wf_*.json` | ✓ held | same regen-no-op check as #4 |
| 9 | 03 | No new IF/Merge node spliced onto the company branch | ✓ held | node count independently counted: 289 == 289 (pre/post) — see D-75-12 row |
| 10 | 03 | A version-stale `create` verdict is never rerouted | ✓ held | `companyVersionStaleRecompute.test.mjs` opened directly: `test("a create verdict is never rerouted by version staleness — no junk company is seeded")` asserts `r.gate.action === "create"` (untouched) |
| 11 | 03 | `ALLOW_HUBSPOT_RECOMPUTE_WRITES` never `"true"` in any committed JSON | ✓ held | independent grep of all 4 bodies: 16/16 occurrences `"false"`, zero `"true"` |
| 12 | 03 | No executor task arms/deploys/bounces anything | ✓ held | plan 03 scope is code-only per its own SUMMARY; deploy/bounce happens only in plan 06 under an explicit operator checkpoint |
| 13 | 03 | No hand-edit of `n8n/wf_*.json` | ✓ held | same regen-no-op check |
| 14 | 04 | `sync_hubspot_properties.py` gains no option-delete path; absent-from-desired is refused, never dropped | ✓ held | `scripts/sync_hubspot_properties.py:122-123`: a live option value absent from desired is routed to `drift` (report-only), never removed from the update payload |
| 15 | 04 | `ALLOW_HUBSPOT_RECOMPUTE_WRITES` never added to any arming/overlay/disarm set | ✓ held | zero `RECOMPUTE` hits in `n8n_arming.py`; `deploy_n8n_workflows.py:223` names the deliberate exclusion |
| 16 | 04 | `config/execution_budget.yaml` not modified | ✓ held | `git diff dfef89d9 -- config/execution_budget.yaml` empty |
| 17 | 04 | No live HubSpot/n8n write/deploy/bounce/arm in plan 04 | ✓ held | plan 04 is tooling-only per its own SUMMARY; live writes are plan 05 (schema/flow) and plan 06 (deploy/bounce) |
| 18 | 04 | No hand-edit of `4626722240-geography-score.after.json` | ✓ held | `gen_geography_flow.py && git diff --quiet -- config/hubspot_flows/` → clean |
| 19 | 05 | No enum option deleted from the live portal | ✓ held | independently parsed `portal-schema-companies-phase75.json`: 16 options present, `UK` hidden not removed |
| 20 | 05 | No n8n workflow deployed/bounced/armed by plan 05 | ✓ held | `75-SCHEMA-RECORD.md` scope is HubSpot schema + flow only; deploy/bounce is `75-DEPLOY-RECORD.md` (plan 06) |
| 21 | 05/06 | No `ALLOW_HUBSPOT_*` flag flipped; nothing armed | ✓ held | independent grep confirms `ALLOW_HUBSPOT_RECOMPUTE_WRITES` false in all 4 live-deployed bodies; `75-DEPLOY-RECORD.md` bounce read-back: all four `ALLOW_HUBSPOT_*` flags false on every workflow |
| 22 | 06 | No HubSpot record written; both proofs return `write_blocked`; no provider credit spent; D-75-17 flip not performed; no frozen fixture regenerated (only additive) | ✓ held | raw `runData` grep of both fixtures: `action: write_blocked`, zero provider/research/judge node mentions (`ZoomInfo Mint\|Apollo Org\|Lusha Company\|Claude Web Research\|Judge Call` → 0 hits each); `75-UAT.md` post-send record re-read: byte-equal `hs_lastmodifieddate`; frozen-dir diff is insertions-only (#3 above) |

**Prohibitions score:** 22/22 held, 0 violated.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `scripts/gen_icp_scoring_js.py` | generator, `gen_escalation_js.py` precedent | ✓ VERIFIED | exists, renders `VERSION`/`REGIONS_HOME`/`REGION_ALIASES`/`HARD_VETO_REASONS`/`GEOGRAPHY_POINTS`, raises on malformed input |
| `n8n/code/icpScoring.generated.js` | generated artifact, checked in | ✓ VERIFIED | content matches `config/icp_scoring.yaml` exactly (manually diffed) |
| `tests/test_icp_scoring_generated_currency.py` | currency test | ✓ VERIFIED | present, green in full run |
| `scripts/gen_geography_flow.py` | flow body generator | ✓ VERIFIED | present; regen-no-op confirmed directly by this verifier |
| `tests/test_geography_flow_conformance.py` | offline yaml-vs-flow assertion | ✓ VERIFIED | present, green |
| `tests/test_recompute_flag_isolation.py` | arming-exclusion pin | ✓ VERIFIED | present, green |
| `tests/n8n/companyVersionStaleRecompute.test.mjs` | reroute + write_blocked + create-untouched behavior | ✓ VERIFIED | present, green, opened directly — exercises the state transitions for D-75-12/13(create-guard)/19 |
| `tests/n8n/sj2VersionStaleGate.test.mjs` | SJ-2 gate behavior | ✓ VERIFIED | present, green |
| `.planning/todos/pending/2026-09-20-other-stamped-records-cannot-be-rescued-by-recompute.md` | sized population + design decision | ✓ VERIFIED | present, well-formed (`kind: design`, `decision_needed`, `owner`), matches todo-triage rules |
| `75-UAT.md` / `75-DEPLOY-RECORD.md` / `75-SCHEMA-RECORD.md` | exit evidence | ✓ VERIFIED | all present, internally consistent, cross-referenced against the raw frozen `runData` and schema/flow JSON files, not merely their own prose |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `config/icp_scoring.yaml` | `n8n/code/icpScoring.generated.js` | `gen_icp_scoring_js.py::render()` | ✓ WIRED | generated content matches yaml byte-for-byte on inspection |
| `n8n/code/icpScoring.generated.js` | `ENRICH_DECIDE_CO_CLOUD` | inline at build time | ✓ WIRED | `REGIONS_HOME`/`HARD_VETO_REASONS`/`VERSION` referenced directly in the veto block |
| `src/icp_scoring.py` | `ENRICH_DECIDE_CO_CLOUD` (Phase 46 parity) | same `regions.home`/`hard_vetoes` source, one commit | ✓ WIRED | identical `region_key`/reason logic in both files, same commit range |
| `config/icp_scoring.yaml regions.aliases` | all 3 normalisers | `REGION_ALIASES`/`region_aliases()` | ✓ WIRED | JS/Python/ZoomInfo lanes all import from the one source, zero second parser |
| `ENRICH_CO_GATE` recompute marker | `IF Company Recompute` → `Decide Company Action` | existing lane, D-75-12 | ✓ WIRED | raw `runData` of both proof executions confirms this exact path ran (71 nodes each, no provider/research/judge node); the version-mismatch-specific trigger of the marker is pinned offline (test opened directly), not separately exercised live this phase |
| `Decide Company Action` write gate | `_writeSafetyAllows('recompute', ...)` | `ALLOW_HUBSPOT_RECOMPUTE_WRITES` | ✓ WIRED | raw `runData` of both proofs shows `action: write_blocked` under the false flag |
| `SJ-2 Search` filter groups | `SJ2_CO_GATE` version comparison | `lv_icp_scoring_version` fetch | ✓ WIRED (code-level) | not live-exercised this phase (SJ-2 is monthly; next natural tick is the trigger named in the pending todo) |
| committed `n8n/wf_*.json` | live n8n Cloud | `deploy_n8n_workflows.py` → `bounce_n8n_workflows.py` | ✓ WIRED | 4 bodies PUT 200, bounce exit 0, node counts match, `v1`, all flags false (`75-DEPLOY-RECORD.md`); the `wf_scheduled_maintenance_cloud` body was deployed and bounced but no execution ran on it this phase — deploy/bounce correctness confirmed, its recompute/SJ-2 code paths were not live-exercised |

### Behavioral Spot-Checks / Probe Execution

Not applicable in the conventional sense — the phase's own exit gate IS a pair of live n8n
executions, already run by the operator. This verifier did not re-run any live call (per the
task's explicit instruction) but opened the raw evidence artifacts directly rather than
trusting UAT.md's prose:

| Behavior | Evidence (raw file, verifier-run grep) | Result | Status |
| --- | --- | --- | --- |
| Whitelisted company (`AU`) recompute derives no geography veto, stamps version, writes nothing | `tests/n8n/fixtures/frozen/exec_12682.runData.json` | `"lv_anti_icp_reason": ""`, `"lv_icp_scoring_version": "lv-icp-v0.2"`, `"action": "write_blocked"`, 0 hits for `ZoomInfo Mint\|Apollo Org\|Lusha Company\|Claude Web Research\|Judge Call` | ✓ PASS (verifier-confirmed from raw file) |
| Non-whitelisted company (`Other`, native Italy) recompute derives the renamed veto reason, stamps version, writes nothing | `tests/n8n/fixtures/frozen/exec_12683.runData.json` | `"lv_anti_icp_reason": "Outside target regions"`, `"lv_icp_scoring_version": "lv-icp-v0.2"`, `"action": "write_blocked"`, 0 provider/research/judge hits | ✓ PASS (verifier-confirmed from raw file) |
| Exactly 2 new executions, 0 credits, no burst | `75-UAT.md` post-send watch (not independently re-observable offline) | baseline `12677`→`12683` enrichment, maintenance unchanged at `12681` before/after | ✓ PASS (`[observed live]`, cited from operator's own record) |
| Post-send record re-read confirms nothing written | `75-UAT.md` (not independently re-observable offline) | both companies byte-equal pre/post, `hs_lastmodifieddate` unchanged | ✓ PASS (`[observed live]`, cited) |
| Live portal schema after the PUT: 16 options, `UK` hidden, `lv_icp_scoring_version` present | `config/hubspot_migration/baseline/portal-schema-companies-phase75.json` | parsed directly: `AU..IN` present, `UK True` (hidden), `lv_icp_scoring_version` string/text/lv_enrichment | ✓ PASS (verifier-confirmed from raw file) |
| Live geography flow branch after the PUT equals `regions.home` | `config/hubspot_flows/4626722240-geography-score.post75.json` | parsed directly: filter `values` == the 12 home codes exactly | ✓ PASS (verifier-confirmed from raw file) |

Offline evidence re-run by this verifier (not merely cited from the SUMMARY):

| Check | Command | Result | Status |
| --- | --- | --- | --- |
| Python suite | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` | `5210 passed, 160 skipped, 1 warning` | ✓ PASS |
| Node suite | `node --test tests/n8n/*.test.mjs` | `pass 1350, fail 0` | ✓ PASS |
| Regeneration is a no-op | `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/` | clean | ✓ PASS |
| Todo triage | `.venv/bin/python scripts/todo_triage.py` | exit 0, all pending todos classified | ✓ PASS |
| `ALLOW_HUBSPOT_RECOMPUTE_WRITES` literal across all 4 committed bodies | `grep -o 'ALLOW_HUBSPOT_RECOMPUTE_WRITES = \"[a-z]*\"' n8n/wf_*.json` | 16 hits, all `\"false\"`, zero `\"true\"` | ✓ PASS |
| Enrichment node count unchanged | `python3` node-count of committed vs `git show dfef89d9:...` | 289 == 289 | ✓ PASS |
| `geography_score` never written by Decide | `grep -n geography_score scripts/build_cloud_workflows.py` | zero hits | ✓ PASS |
| Debt-marker scan on phase-changed files | `grep -E "TBD\|FIXME\|XXX"` over `git diff dfef89d9 --name-only` (excl. frozen/stress) | only false positives (Phase 72's own "Requirements: TBD" boilerplate at ROADMAP.md:423, unrelated to Phase 75; a `"0XXXXXXXXX"` phone-format placeholder comment) | ✓ PASS — no unresolved debt marker |
| Frozen/stress-test byte-identity | `git diff dfef89d9 --stat -- tests/n8n/fixtures/frozen/ tests/stress-tests/` | 2 files, insertions-only | ✓ PASS |

### Requirements Coverage

No REQUIREMENTS.md ids map to this phase (confirmed: no "Phase 75" section exists in
`.planning/REQUIREMENTS.md`; the phase task explicitly states coverage is keyed on decision ids
instead). All 20 decisions (D-75-01..D-75-20) traced above; zero orphaned decisions.

### Anti-Patterns Found

None blocking. Two `grep` hits for `TBD`/`XXX` in phase-changed files are both false positives:
`.planning/ROADMAP.md:423` is Phase 72's own "Requirements: TBD — coverage is by DECISION ID"
line (confirmed by reading the surrounding section, which cites `D-72-01..D-72-21`), not Phase
75's — unrelated boilerplate, not a Phase 75 debt marker. The other hit is a phone-format
placeholder comment (`"0XXXXXXXXX"`) containing the substring `XXX` incidentally. No `FIXME`, no
unreferenced debt marker, no stub pattern in any changed implementation file.

### Human Verification Required

None. Every must-have across all six plans (truths, artifacts, key_links, and all 22
prohibitions) resolved to VERIFIED/held against either static code evidence, a green offline
test opened and read directly, or a raw live-evidence artifact file opened and parsed directly
by this verifier. Two items remain `[documented]`-only per the phase's own honest tagging, and
neither is a phase must-have that asserts live observation:

1. **D-75-12's reroute on a *real* version-stale record.** Both live proofs used the explicit
   `recompute` request flag rather than triggering the version-mismatch path at the gate. The
   version-mismatch transition itself is exercised and passes offline
   (`companyVersionStaleRecompute.test.mjs`, opened directly). The first real version-stale
   record will only exist after the scheduled maintenance workflow's poller or the operator's
   bump sweep runs post-phase.
2. **D-75-13's SJ-2 monthly gate and the `wf_scheduled_maintenance_cloud` deploy generally.**
   The body was deployed and bounced correctly (`75-DEPLOY-RECORD.md`), but no execution ran on
   it during this phase's proof window (baseline and post-watch execution ids both `12681`) —
   its recompute-adjacent code paths are code-verified and offline-tested but not
   live-exercised. This is the trigger named in
   `.planning/todos/pending/2026-09-20-sj2-version-stale-backstop-is-armed-only.md`.

### Gaps Summary

None found. All 6 plans' must_haves (truths, artifacts, key_links, and all prohibitions) are
satisfied by codebase evidence opened directly, all offline suites are green at their expected
counts (5210/1350), regeneration is a no-op, no debt markers, no frozen-fixture rewrites (only
two new, additive), the live deploy/bounce/schema/flow writes are independently read back from
their raw artifact files and match the yaml/config source exactly, and the phase's own two
required recompute proofs are frozen, redacted, and confirmed directly from the raw `runData`
(not merely cited from prose). Nothing is armed
(`ALLOW_HUBSPOT_RECOMPUTE_WRITES` reads `"false"` in all 16 occurrences across the 4 live
bodies; the D-75-17 flip is explicitly deferred and undone).

---

_Verified: 2026-09-20_
_Verifier: Claude (gsd-verifier)_
