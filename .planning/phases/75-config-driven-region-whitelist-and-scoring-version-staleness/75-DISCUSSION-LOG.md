# Phase 75: Config-driven region whitelist and scoring-version staleness - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-20
**Phase:** 75-config-driven-region-whitelist-and-scoring-version-staleness
**Areas discussed:** Veto reason string, Whitelist + enum contents, HubSpot geography_score flow, Stale-version sweep path

---

## Todo cross-reference

| Option | Description | Selected |
|--------|-------------|----------|
| None — all noise | Record as reviewed-not-folded | ✓ |
| Racing clubs produces_content=false | Different veto (content); folding widens scope | |

**User's choice:** None — all noise.

---

## Veto reason string

| Option | Description | Selected |
|--------|-------------|----------|
| Rename now, region-agnostic | e.g. "Outside target regions"; one-time churn; ~20 sites in same commit | ✓ |
| Keep "Non-ANZ geography" this bump | Zero churn now; string becomes wrong once home != {AU,NZ} | |
| Rename, reason names the region | e.g. "Outside target regions (US)"; tests assert prefix | |

| Option | Description | Selected |
|--------|-------------|----------|
| All 3 reasons from yaml via generated JS | gen script emits HARD_VETO_REASONS; Decide stops hard-coding | ✓ |
| Only the geography reason moves | Smaller diff; two drift points remain | |

| Option | Description | Selected |
|--------|-------------|----------|
| Version bump + stale sweep only | No dedicated remediation script | ✓ |
| One-shot armed remediation | Extend remediate_veto_companies.py | |

| Option | Description | Selected |
|--------|-------------|----------|
| Leave frozen fixtures untouched | Recordings; only asserting tests change | ✓ |
| Rewrite everywhere | Global replace incl. recordings | |

**User's choice:** rename now; all three reasons from yaml; bump+sweep for old records; frozen fixtures untouched.
**Notes:** User asked what the frozen runData fixtures are for and whether to re-record. Explained: they are live-execution recordings (refresh policy none per README); only `test_run_report_enrich_account.py` reads the `run_6891d018` excerpt and it asserts counts, not the reason string; re-recording would need new live executions and would fabricate legacy-engine bodies. User locked "leave untouched", optional additive freeze of exit-proof executions.

---

## Whitelist + enum contents

**User's input:** target markets are English-speaking or native-English-audience with strong sports broadcasting ecosystems (e.g. US, ZA, UK); asked for a proposed list. Proposed wave 1 (US, GB, IE, CA, ZA) and wave 2 (HK, SG, AE, IN); excluded NG/KE/JM/PH. User accepted both waves.

| Option | Description | Selected |
|--------|-------------|----------|
| Documented candidates, not in home yet | regions.home = AU NZ US GB IE CA ZA; wave 2 as next edit | |
| In regions.home now too | All 9 + ANZ home from day one | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Emit alias code; unmapped known country -> Other | Region lands once; later whitelist edits need no re-enrichment | ✓ |
| Keep collapsing to Other | No enum changes; expansion can't rescue existing records | |

| Option | Description | Selected |
|--------|-------------|----------|
| GB; hide UK enum option | ISO2-correct; hide not delete | ✓ |
| UK; alias GB->UK | Keeps existing option; diverges from ISO2 | |

| Option | Description | Selected |
|--------|-------------|----------|
| Yaml single source; phone map generated from it | REGION_ALIASES replaces _COUNTRY_ISO2 | ✓ |
| Two tables + parity test | Phone map stays hand-typed | |

**User's choice:** all waves home now; emit alias codes; GB token with UK hidden; yaml single source. "Next area" at the continue check.

---

## HubSpot geography_score flow

| Option | Description | Selected |
|--------|-------------|----------|
| Keep HubSpot flow; regenerate body from yaml | after.json rendered from regions.home; put_hubspot_flow.py; drift test | ✓ |
| Retire flow; Decide writes geography_score | Pipeline owns component; Decide becomes score writer | |
| Both | Two writers of one property | |

| Option | Description | Selected |
|--------|-------------|----------|
| Operator step at phase-exit UAT | Repo ships after.json + RED-until-PUT test | |
| Executor runs it in-plan | Same session as JSON regen | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Offline test on after.json + check_schema_drift live read | Two enforcement points | ✓ |
| Offline test only | Live flow can silently diverge | |

| Option | Description | Selected |
|--------|-------------|----------|
| Executor in-plan (property create + enum options + UK hide) | Consistent with flow-PUT answer | ✓ |
| Operator at phase-exit UAT | Roadmap default | |

**User's choice:** keep flow, regenerate; executor runs flow PUT and schema sync in-plan; dual enforcement. "Next area".

---

## Stale-version sweep path

| Option | Description | Selected |
|--------|-------------|----------|
| Gate skip + version mismatch -> recompute | Inside wf_enrichment; every path ends in Decide | ✓ |
| SJ-3 stamps recompute:true on version-stale events | Risk: human-requested enrich becomes recompute-only | |
| New SJ-4 lane | Dedicated trigger + dispatch | |

| Option | Description | Selected |
|--------|-------------|----------|
| SJ-2 monthly + operator one-shot after a bump | Scheduled is backstop | ✓ |
| SJ-2 monthly only | Roadmap literal | |
| Daily (SJ-1 tier) | Competes for SJ-3 cap | |

| Option | Description | Selected |
|--------|-------------|----------|
| Only records with scoring inputs | version != current AND HAS_PROPERTY lv_org_type | ✓ |
| Every company with version != current | Includes never-scored | |

| Option | Description | Selected |
|--------|-------------|----------|
| Sweep is backstop; writes only inside operator windows | No standing arming | |
| Standing narrow arming for the recompute lane | Decide's writes allowed unattended | ✓ |

**Notes:** Assistant flagged that standing arming supersedes the Phase 57 ruling and offered a session-grant alternative (grant + record-scoped windows, `scheduled_arm.py` precedent; deployed `_writeSafetyAllows` denies on an empty allowlist so "standing" needs a new predicate branch). User asked whether the flip could be covered by the ordinary session-wide grant; assistant answered yes for bump sweeps and drains, no for unattended ticks. User reaffirmed: "No, I do want standing flag." User then asked whether recompute happens regularly as data is written; assistant split score (HubSpot-side, automatic) from veto/version (n8n Decide, only on dispatch, only when armed) and noted no property-change webhook exists — user asked to note event-driven recompute as deferred.

| Option | Description | Selected |
|--------|-------------|----------|
| New ALLOW_HUBSPOT_RECOMPUTE_WRITES; bypasses allowlist for recompute only | Existing 3 flags untouched; disarm never touches it | ✓ |
| Reuse ALLOW_HUBSPOT_RECORD_WRITES with wildcard allowlist | Arms every write path | |

| Option | Description | Selected |
|--------|-------------|----------|
| Ship false; operator flips true after first supervised sweep | Documented one-line deploy step | ✓ |
| Ship true from the disarmed deploy | Unattended writes from first tick | |

**User's choice:** standing flag `ALLOW_HUBSPOT_RECOMPUTE_WRITES`, shipped false, flipped after first supervised sweep. "I'm ready for context."

---

## Claude's Discretion

- Flat geography points (home 10 / other 0 / unknown 0).
- Exact rename string (default "Outside target regions").
- Generated-JS module layout; how the ZoomInfo client loads the yaml.
- `EU` enum option left as-is.
- `hidden: true` support in `sync_hubspot_properties.py`.

## Deferred Ideas

- Event-driven recompute via `company.propertyChange` webhook subscriptions on the veto inputs.
