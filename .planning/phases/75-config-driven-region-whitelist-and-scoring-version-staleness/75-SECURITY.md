---
phase: "75"
slug: "config-driven-region-whitelist-and-scoring-version-staleness"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-21"
---

# Phase 75 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register authored at plan time (all six PLANs carry a `<threat_model>` block, T-75-01..29).
> No SUMMARY carried a `## Threat Flags` section — no unregistered attack surface reported by
> any executor. ASVS L1: each `mitigate` disposition verified by grep-level presence in the
> cited file on 2026-09-21; the `[observed live]` rows cite the phase's own recorded evidence.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| `config/icp_scoring.yaml` → both scoring engines | a repo-controlled config value decides whether a company is vetoed; codegen (`scripts/gen_icp_scoring_js.py`) is the only path into n8n | region whitelist, alias table, veto reason strings, `version` |
| generated JS → n8n Code node body | `icpScoring.generated.js` literals concatenated verbatim into Code nodes via `json.dumps` | region codes, points, reason strings — no secrets |
| provider/native country string → region code | untrusted provider text crosses into a scoring decision | Apollo names, Lusha ISO2, ZoomInfo text |
| `config/hubspot_properties.yaml` → live HubSpot schema (portal 22617666) | manifest becomes a live, destructive-capable schema change via `sync_hubspot_properties.py` | enum options, new property |
| n8n Code node → HubSpot PATCH | every write crosses `_writeSafetyAllows`; Phase 75 adds a FOURTH authority that bypasses the record allowlist | `lv_anti_icp_flag`, `lv_anti_icp_flag_num`, `lv_anti_icp_reason`, `lv_icp_scoring_version` |
| scheduled trigger → HubSpot search → dispatch | SJ-2 selects a population unattended | company ids; provider credits downstream |
| committed workflow JSON → live n8n Cloud | a deploy replaces running bodies; an armed literal is armed on landing | `ALLOW_HUBSPOT_*` literals |
| operator shell → live HubSpot / n8n | schema writes, flow PUT, deploy, bounce, proof sends — all operator-run from `.env` | `HUBSPOT_PRIVATE_APP_TOKEN`, `N8N_API_KEY`, webhook secret |
| n8n runData → frozen fixture in git | `Webhook Trigger` runData embeds the shared secret and caller IP | headers (redacted before commit) |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-75-01 | Denial of Service | `scripts/gen_icp_scoring_js.py::render()` | high | mitigate | refuse empty/malformed `regions.home` or blank reason | closed — `gen_icp_scoring_js.py:43` non-empty-list assert, `:54-55` reason assert naming the key; `tests/test_icp_scoring_generated_currency.py:46,53,60` three `pytest.raises` |
| T-75-02 | Tampering | `config/icp_scoring.yaml` scoring surface | medium | mitigate | rubric change guard pins `base_score`, names the bump + sweep | closed — `tests/test_rubric_change_guard.py:51` `home/other/unknown` pin, `:26,86` names `docs/OPERATOR-RESCORE.md` |
| T-75-03 | Information Disclosure | `n8n/code/icpScoring.generated.js` | low | accept | committed by design; region codes/points/reasons only | closed — accepted risk R-75-01 |
| T-75-04 | Tampering | `n8n/wf_*.json` | medium | mitigate | builder is the sole producer; no hand-edits; Decide jsCode read from the regenerated body | closed — `n8n/README.md:52` rule; plan-01 Task 1 verify reads regenerated Decide jsCode; `tests/test_committed_bodies_ship_disarmed.py` pins committed bodies |
| T-75-05 | Tampering | `regions.aliases` as the single table | medium | mitigate | parity test pins a HARD-CODED historical key list | closed — `tests/n8n/regionAliasParity.test.mjs:47-48` `HISTORICAL_ALIASES` hard-coded; `_COUNTRY_ISO2` 0 hits in `normalizeProviders.js` |
| T-75-06 | Spoofing | region alias values | medium | mitigate | every alias value ∈ `REGIONS_HOME` ∪ `{"Other"}` | closed — `regionAliasParity.test.mjs:19-20` assertion (c) |
| T-75-07 | Denial of Service | `hubspotEnums.js` refusing the eight new codes until plan 05 | low | accept | fail-closed inert window, recorded | closed — accepted risk R-75-02; window closed by plan 05 Task 2 (snapshot repointed, `hubspotEnums.generated.js` regenerated) |
| T-75-08 | Denial of Service | `UK` enum option | high | mitigate | `hidden: true`, never deleted; no delete path in the tool | closed — `config/hubspot_properties.yaml:136-138` `UK` retained + hidden; `sync_hubspot_properties.py` has no DELETE call |
| T-75-09 | Elevation of Privilege | `ALLOW_HUBSPOT_RECOMPUTE_WRITES` | high | mitigate | ships `"false"`; checked only on `action === "recompute"`; PATCH pinned to exactly four keys; flip is deploy+bounce | closed — `build_cloud_workflows.py:2575` default `"false"`, `:2597-2598` recompute-only gate; `companyVersionStaleRecompute.test.mjs:344-354` sorted 4-key equality; live `false` on all four bodies (`75-DEPLOY-RECORD.md:35-38`) |
| T-75-10 | Elevation of Privilege | standing flag creeping onto SJ-2 | high | mitigate | SJ-2 dispatch keeps `"enrich"` classification (allowlist-gated) | closed — `sj2VersionStaleGate.test.mjs`; pending todo `2026-09-20-sj2-version-stale-backstop-is-armed-only.md` names the operator owner |
| T-75-11 | Denial of Service | SJ-2 filter scope | high | mitigate | version groups ANDed with `HAS_PROPERTY lv_org_type` | closed — `sj2VersionStaleGate.test.mjs:74-93` asserts the anchor conjunct in every version group |
| T-75-12 | Denial of Service | new IF/Merge splice on the company branch | high | mitigate | zero nodes added; existing `IF Company Recompute` routes the marker | closed — `wf_enrichment_cloud.json` 289 nodes (pre == post); `companyVersionStaleRecompute.test.mjs:133-160` drives the existing lane; plan-03 Task 2 verify asserts no new version IF |
| T-75-13 | Tampering | `lv_icp_scoring_version` reading `undefined` | medium | mitigate | property in every fetch list | closed — grep hits: `wf_enrichment_cloud.json` 5, `wf_enrichment_local_live.json` 2, `wf_scheduled_maintenance_cloud.json` 2 |
| T-75-14 | Repudiation | version-stale recompute masquerading as an operator request | low | mitigate | `recompute_reason` `"requested"` vs `"version_stale"` | closed — `build_cloud_workflows.py:4032`; `tests/n8n/phase75RecomputeProofRecordings.test.mjs` pins `"requested"` on both proofs |
| T-75-15 | Elevation of Privilege | flag left `true` indefinitely | high | mitigate | bounce prints the flag vs committed body every run | closed — `bounce_n8n_workflows.py:44` `COMMITTED_TRUTH_FLAGS`, `:73,124` `_row_ok(committed_body=…)`; `75-DEPLOY-RECORD.md:35-38` per-row output |
| T-75-16 | Denial of Service | `_update_property_options_live` dropping a live option | high | mitigate | desired set omitting a live option → `drift`, never `update` | closed — `sync_hubspot_properties.py:86-107` drift bucket; `tests/test_sync_hubspot_properties.py:91` refusal test |
| T-75-17 | Tampering | HubSpot flow `4626722240` body | medium | mitigate | generated from `regions.home`; conformance test; live drift check on the single-flow body | closed — `scripts/gen_geography_flow.py:64` ambiguity refusal; `tests/test_geography_flow_conformance.py`; `check_schema_drift.py:450` `_get_live_flow` (fixed `0221804a`), live `in_sync` |
| T-75-18 | Spoofing | a green bounce that never read the flag | medium | mitigate | `_row_ok` rejects live `true` vs committed `false` | closed — `tests/test_recompute_flag_isolation.py:150,163` |
| T-75-19 | Information Disclosure | HubSpot token in a PATCH error object | medium | mitigate | `(status_code, body)` return; never echoes request/headers | closed — `sync_hubspot_properties.py:167+` docstring + `return r.status_code, body` |
| T-75-20 | Denial of Service | live `lv_country_region_normalized` options | high | mitigate | independent read-back: no pre-write option absent after | closed — `75-SCHEMA-RECORD.md` 8→16 options, `UK` hidden; `portal-schema-companies-phase75.json` read-back |
| T-75-21 | Tampering | writing to the wrong portal | high | mitigate | `EXPECTED_PORTAL_ID` assert pre-call | closed — `scripts/snapshot_hubspot_schema.py:41,60,152`; `test_sync_hubspot_properties.py:169` portal-mismatch refusal |
| T-75-22 | Information Disclosure | token in command output or the schema record | high | mitigate | inline gate var; bodies only; grep before commit | closed — `pat-na1`/`Bearer`/`Authorization` 0 hits in `75-SCHEMA-RECORD.md`, `75-DEPLOY-RECORD.md`, `75-UAT.md`; 0 `eyJ`/`pat-na1` in the two frozen fixtures |
| T-75-23 | Elevation of Privilege | `ALLOW_HUBSPOT_PROPERTY_WRITES` left set | medium | mitigate | inline on one command; post-write `--dry-run` without it | closed — `75-SCHEMA-RECORD.md:32,63` |
| T-75-24 | Tampering | a stale pinned snapshot | medium | mitigate | fresh snapshot required; old baseline retained | closed — `gen_hubspot_enums_js.py:28` repointed to `portal-schema-companies-phase75.json`; prior baselines retained in `config/hubspot_migration/baseline/` |
| T-75-25 | Elevation of Privilege | an armed literal reaching the live instance | high | mitigate | pre-deploy literal check; bounce exits 1 while armed; post-bounce read-back `false` ×4 | closed — `75-DEPLOY-RECORD.md:10-11` (`"false"` at every site), `:30-38` `bounce_exit=0`, all four flags `false`; `tests/test_committed_bodies_ship_disarmed.py` 37 cases |
| T-75-26 | Information Disclosure | `x-enrichment-secret` + caller IP in a frozen fixture | high | mitigate | Phase 74 freezer scrub; headers redacted; no existing fixture regenerated | closed — `exec_12682`/`exec_12683` `Webhook Trigger` headers are the redaction placeholder string; frozen dir diff = 2 files added, 0 modified; `phase75RecomputeProofRecordings.test.mjs` pins it |
| T-75-27 | Denial of Service | execution burst after the proof POSTs | high | mitigate | 130 s post-send watch; exactly two executions | closed — `75-UAT.md:99-100` (enrichment max `12683`, maintenance `12681`, no burst) |
| T-75-28 | Repudiation | expectation written after the result | medium | mitigate | expectations written before send; divergence → FINDING id | closed — `75-UAT.md:31,45` "written before sending", `:73,84,96` MATCH, `:141` no finding raised |
| T-75-29 | Information Disclosure | HubSpot record data in the sizing output | low | accept | counts and filter bodies only | closed — accepted risk R-75-03 |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

Standing residuals (not threats of this phase, recorded for the next audit): the D-75-17 flip
to `"true"` has NOT been performed — T-75-09/T-75-15 describe the controls that bound it once
it is; behaviour under an ARMED flag is `[documented]` only. Five records still carry the
legacy `Non-ANZ geography` reason until the operator's bump sweep runs.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-75-01 | T-75-03 | `icpScoring.generated.js` carries only region codes, point values and veto reason strings — no secret, credential or PII; committing it is the design (mirrors `escalation.generated.js`) | planner (plan 01), operator via `--chain` | 2026-09-20 |
| R-75-02 | T-75-07 | between plan 02 and plan 05 an unrecognised region candidate was REFUSED at merge (record unchanged, scores `unknown`, no veto) — fail-closed inert window, closed by plan 05 Task 2 the same day; recorded in `75-02-SUMMARY.md:131-146` | planner (plan 02), operator via `--chain` | 2026-09-20 |
| R-75-03 | T-75-29 | sizing searches record counts and filter bodies, not record contents; company firmographics are not PII | planner (plan 06), operator at the blocking-human checkpoint (`proceed`) | 2026-09-20 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-21 | 29 | 29 | 0 | `/gsd-secure-phase 75` (orchestrator L1 grep verification; auditor not spawned — short-circuit rule: threats_open 0, plan-time register, ASVS 1) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-21
