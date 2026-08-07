# Phase 42: Scoring Artifact Cleanup & Reconciliation - Research

**Researched:** 2026-08-07
**Domain:** HubSpot CRM v3 Properties API / Automation v4 Flows API schema hygiene, repo-vs-portal reconciliation
**Confidence:** MEDIUM-HIGH (property/flow API mechanics are live-verified in this exact portal by prior phases; the D-04 property-existence question is the one load-bearing item this research could NOT close from repo evidence alone and must be closed by Phase 42's own live GET)

## Summary

This phase has two independent halves — archival (a portal mutation, gated) and reconciliation
(read-only, no portal mutation) — and the repo already contains live-verified precedent for
every mechanic both halves need. The archive semantics question (D-07, the highest-stakes
factual question per the task brief) is **answered with live evidence, not assumption**:
`scripts/probe_org_type_migration.py`'s 9-step ladder was armed against portal 22617666 on
2026-07-30, and its verbatim operator-pasted VERDICT block
(`.planning/workstreams/milestone/phases/21-transport-schema-hygiene/21-03-SUMMARY.md:86-98`)
confirms `DELETE /crm/v3/properties/{objectType}/{name}` archives (HTTP 200/204, not a hard
delete) and that the archived name is **immediately reusable** by a fresh `POST`. This matches
Phase 15's `[CITED, MEDIUM confidence]` documentation research
(`.planning/milestones/v0.3-phases/15-hubspot-property-migration/RESEARCH.md:110-118`): HubSpot's
own docs describe the delete call as moving a property "to the trash," values retained for a
90-day window, restorable via the portal UI or the same recreate-by-name mechanism the probe
exercised — there is no documented dedicated REST restore endpoint.

The bigger risk in this phase is not archival mechanics — it is the reconciliation half's D-04
property list. Direct inspection of `config/hubspot_properties.yaml` confirms the CONTEXT.md
premise exactly (22 company + 17 contact properties, zero `lv_org_type`/`lv_icp_fit_score`/etc.
entries). But five of the ten names D-04 lists as "currently missing from the yaml" —
`lv_icp_confidence`, `lv_recommended_motion`, `lv_icp_scored_at`, `lv_icp_scoring_version`,
`lv_named_account_priority` — trace back exclusively to CLAUDE.md's superseded local-MVP design
(§5.2/§12) and have **no live-creation evidence anywhere in the repo**. One of them
(`lv_icp_scored_at`) is explicitly documented as a live 404 as of 2026-08-06
(`HANDOVER-2026-08-06-icp-scoring.md:443-445`). D-05 says "live wins, yaml catches up" — you
cannot catch the yaml up to a property that was never created. Phase 42 must live-verify each
of these five before writing yaml entries for them; anything still absent belongs in the
drift/discrepancy report, not fabricated into the manifest.

A second concrete risk: expanding the yaml under D-04 collides with the yaml's *own* offline
test suite, which was written under the assumption that the file is a **create-only manifest**
(what to create, not a full mirror) — a premise D-04 explicitly inverts. Three tests in
`tests/test_hubspot_properties_config.py` will fail or actively contradict the expansion unless
updated as an explicit task (§ "What consumes the yaml" below).

**Primary recommendation:** Treat the D-04 yaml expansion as two sub-tasks, not one: (1) a live
D-02 enumeration that settles, per property, "does this exist live and with what enum/type
shape" — including the five design-only names — before any yaml line is written; (2) a
companion update to `tests/test_hubspot_properties_config.py`'s prefix/type-pair/count/"not
listed for creation" assertions, since the file's own oracle tests currently assert the
opposite of what D-04 wants. Archival (D-07/D-08) is separately safe to execute directly per
the live-verified soft-archive mechanics above, gated only by the do-not-archive set staying
intact.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Property/flow archival (portal mutation) | HubSpot (CRM v3 Properties API, Automation v4 Flows API) | Repo (`config/hubspot_flows/` archive dir, `scripts/snapshot_hubspot_schema.py`) | Archival is a live portal write; the repo side is purely the before/after evidence trail per the existing convention. |
| Schema drift detection (read-only) | Repo (`scripts/`, new drift-check script) | HubSpot (source of truth read via GET) | D-05 forbids portal mutation here — this is a pure diff/report layer sitting on top of two GETs. |
| `config/hubspot_properties.yaml` (desired-state manifest) | Repo (config file) | `scripts/sync_hubspot_properties.py` (create-only consumer) | The manifest itself lives in the repo; its only portal-mutating consumer already treats "exists live" as a no-op, which is what makes D-04's expansion safe. |
| Test-suite invariants over the manifest | Repo (`tests/`) | — | These are the second-order surface most likely to break silently when D-04 expands the file; no portal interaction. |

## Package Legitimacy Audit

Not applicable — this phase installs no new external packages/dependencies. All work uses the
existing `requests`/`PyYAML`/`pytest` stack already vendored via `requirements.txt` and the
already-live HubSpot Properties/Automation APIs.

## User Constraints (from CONTEXT.md)

<user_constraints>

### Locked Decisions (verbatim from 42-CONTEXT.md)

- **D-01:** ROADMAP SC1's archive list is reinterpreted, and the reinterpretation is recorded.
  Phase 42 archives only what is actually orphaned under fix-in-place; the five live
  component-score properties, the calculated `lv_icp_fit_score`, and the four repaired flows
  are explicitly NOT archived. CONTEXT.md carries the supersession rationale so the divergence
  from the roadmap text is traceable rather than silent. ROADMAP.md itself is not edited as a
  prerequisite. Reversibility: reversible.
- **D-02:** The orphan list is derived from a live-portal diff: enumerate live company
  properties and automation flows via API, cross-reference against what the repaired engine
  and the n8n pipeline actually read/write plus `config/hubspot_flows/*.after.json`. Anything
  referenced by nothing is a candidate. Repo-only derivation is rejected.
- **D-03:** Approval gate: archive uncontested, ask on doubt. Clear-cut orphans (zero
  references, obvious provenance) are archived without pausing; ambiguous items are surfaced
  to the operator with evidence before any action.
- **D-04:** "Reconciles clean / zero drift" scope = full mirror of every `lv_*` and scoring
  property the system depends on. The yaml grows to cover the currently-missing set
  (`lv_org_type`, `lv_produces_content`, `lv_icp_fit_score`, `lv_icp_tier`, `lv_anti_icp_flag`,
  `lv_icp_confidence`, `lv_recommended_motion`, `lv_icp_scored_at`, `lv_icp_scoring_version`,
  `lv_named_account_priority`, `org_type_score`, `geography_score`, `annual_revenue_score`,
  `produces_content_score`, `gambling_score`). HubSpot-native fields stay out of scope.
- **D-05:** Drift direction: live wins, yaml catches up. Reconciliation performs no portal
  mutation; it updates the config file to match. Reversible.
- **D-06:** Reconciliation depth: existence + enum option values. Property presence and exact
  enum `value` lists must match. Labels/`displayOrder`/descriptions are cosmetic — reported,
  not treated as failures.
- **D-07:** HubSpot properties archive via HubSpot's soft-archive (`DELETE
  /crm/v3/properties/{objectType}/{name}`, archives rather than destroys). Snapshot the
  property definition to the repo before the call. Reversibility: costly.
- **D-08:** Orphaned flows: fetch JSON to repo, then deactivate — `GET
  /automation/v4/flows/{id}` archived under a dated archive dir, then disabled. Not deleted.
- **D-09:** Locations: `scripts/snapshot_hubspot_schema.py`'s destination/naming unchanged.
  Archived flow/property definitions land in a dated archive directory under
  `config/hubspot_flows/`, consistent with the `{id}-{name}.before.json`/`.after.json`
  convention.
- **D-10:** Form: a standing drift-check script under `scripts/` — read-only, compares yaml vs
  live for the D-04 set at D-06 depth, emits a JSON report and a meaningful exit code. New
  script, not a `--reconcile` bolt-on to the snapshot tool.
- **D-11:** Execution convention: Claude executes directly, snapshot-first — same envelope as
  Phase 40 D-08. `scripts/snapshot_hubspot_schema.py` runs before any mutation; archival calls
  run in-session. No operator arming gate for this phase's mutations.
- **D-12:** Cadence: on-demand and pre/post schema change, same tier as the parity full run.
  NOT added to the unattended sweep.

### Claude's Discretion (verbatim)

- Exact archive directory name/date format under `config/hubspot_flows/`.
- Drift-report JSON shape and exit-code semantics.
- Reference-detection method for D-02 (how "referenced by nothing" is computed across flow
  JSON, n8n code, Python source, and config).
- Which cosmetic drift classes appear in the report body vs a summary line.
- Ordering of archive operations within the gated pass.

### Deferred Ideas (OUT OF SCOPE, verbatim)

- Sweep re-notify / crontab-pins-versioned-path / UAT header-alias / enrichment-throughput
  todos — all reviewed and explicitly not folded into this phase.
- Adding the drift checker to the unattended sweep — declined per D-12; revisit only if schema
  churn increases.

</user_constraints>

## Project Constraints (from CLAUDE.md)

CLAUDE.md's §5–§8/§12 field-provenance-and-property design (per-field `_source`/`_confidence`/
`_evidence_url`/`_verified_at`/`_verified_by_model`/`_validation_status` suffix families, and
the ICP output properties `lv_icp_confidence`, `lv_recommended_motion`, `lv_icp_scored_at`,
`lv_icp_scoring_version`, `lv_named_account_priority`) is the **local-MVP design that was never
carried into the live cloud build**. Live evidence (below) shows the actually-implemented
system uses a single `lv_enrichment_provenance` blob per record
(`config/hubspot_properties.yaml:192-197`, `lv_contact_enrichment_provenance` at
`config/hubspot_properties.yaml:355-360`) and never created the five ICP-metadata properties
named above. **Where CLAUDE.md and live evidence conflict, live evidence wins** — this
research treats CLAUDE.md §5–§8/§12's per-field provenance and the five ICP-metadata property
names as design documentation, not a live-schema oracle, per the task's explicit framing.

CLAUDE.md §21 "Safety Gates" / §11.2 dry-run-by-default conventions ARE still load-bearing and
are honored throughout this repo's live scripts (`DRY_RUN=true` default, two-key write gates)
— this convention should be followed by any new drift-check/archive script Phase 42 adds.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLEAN-01 | Superseded scoring artifacts are archived, not deleted (`scripts/snapshot_hubspot_schema.py` run first), and `config/hubspot_properties.yaml` reconciles clean against the live portal. | §"Live Engine Inventory" confirms what must NOT be archived; §"Orphan Candidate Inventory" gives the actual (likely near-empty) candidate list; §"Archive Semantics" gives live-verified DELETE/PUT mechanics; §"Reconciliation Gap" + §"Consumers of the yaml" give the exact expansion shape and its second-order test-suite conflicts. |

</phase_requirements>

## Live Engine Inventory (what must NOT be archived — reinforces D-01, does not relitigate it)

Confirmed by direct `Read` of the repo's own evidence, not inference:

- `lv_icp_fit_score` — live, `calculated: true`, `fieldType: "calculation_equation"`,
  `calculationFormula: "org_type_score + geography_score + annual_revenue_score +
  produces_content_score + gambling_score"`, `groupName: "companyinformation"`.
  [VERIFIED: config/hubspot_flows/lv_icp_fit_score-property.after.json:1-29]
- `lv_icp_tier` — live, `fieldType: "select"`, `groupName: "companyinformation"`, options
  verbatim: `A`, `B`, `C`, `D`, `Unscored` (five values, `displayOrder` 0-4).
  [VERIFIED: config/hubspot_flows/lv_icp_tier-property.after.json:22-58]
- Four company scoring flows, all `isEnabled: true` as of the last live listing: `4626124224`
  (Update Score Based on Org Type), `4626722240` (Geography Score), `4626722237` (Annual
  Revenue Score), `4625147345` (WF1 Set ICP Tier). [VERIFIED:
  .planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md:6-19]
- Two new company scoring flows created in Phase 40, both `isEnabled: true`:
  `4634822079` (Update Produces Content Score), `4634822085` (Update Gambling Score).
  [VERIFIED: config/hubspot_flows/produces-content-score.after.json (id/name/isEnabled fields),
  config/hubspot_flows/gambling-score.after.json (same)]
- The five `*_score` properties (`org_type_score`, `geography_score`, `annual_revenue_score`,
  `produces_content_score`, `gambling_score`) are asserted-live-written-only by a permanent
  conformance test (`tests/test_flow_rubric_conformance.py:159,189,264-265,303,355-359`) and
  consumed by `scripts/backfill_seed_company_scores.py:73-77,112-116` and
  `tests/test_scoring_parity.py:567-568`. These are the reachable, load-bearing surface — not
  orphans under any reading. [VERIFIED: file:line above]

## Landmine: 39-DECISION.md's own text contradicts 42-CONTEXT.md's D-01 correction

`39-DECISION.md` is listed as a canonical ref the planner MUST read. Its own "Phase 42" section
says, verbatim: *"the retirement set is whatever the lead-scoring-tool path would have produced
had it been chosen: none... Phase 42's cleanup scope is therefore the pre-existing
superseded-artifact list from `REQ-retire-calc-placeholder` (the `1 + 1` calculated-property
placeholder and its `*_score` orphans)"* [file:
`.planning/phases/39-path-decision-fit-score-verification/39-DECISION.md:107-112`]. Read
literally, this sentence points an executor straight back at ROADMAP SC1's superseded list —
the exact mistake `42-CONTEXT.md` D-01 was written to correct. `REQ-retire-calc-placeholder`
was HANDOVER's *original*, pre-39-DECISION wording
(`HANDOVER-2026-08-06-icp-scoring.md:312-325`), written before the fix-in-place path was
chosen; it does not appear anywhere in the current `.planning/REQUIREMENTS.md`. There is also
no live evidence of a separate "1 + 1 placeholder" property ever existing side-by-side with the
real `lv_icp_fit_score` — the formula was edited **in place** on the same property record
(`createdAt: 2026-07-17`, `updatedAt: 2026-08-06` on the *same* `lv_icp_fit_score` object,
[VERIFIED: config/hubspot_flows/lv_icp_fit_score-property.after.json:5,27]) — so there is
nothing named "the placeholder" left to archive as a distinct artifact.
**Recommendation for the planner:** cite `42-CONTEXT.md` D-01 as authoritative and flag
`39-DECISION.md:107-112` explicitly as stale/superseded prose in the plan, so an executor
skimming the canonical refs doesn't silently follow the older, wrong sentence.

## Orphan Candidate Inventory (D-02/D-03) — what repo evidence suggests, pending live re-check

D-02 requires a **live** portal diff; nothing in this section substitutes for that. What repo
evidence establishes is a strong prior that the candidate list is small or empty:

- **Company scoring automation flows:** `GET /automation/v4/flows` returned exactly 8 flows
  portal-wide as of 2026-08-06, with only the four company-object scoring flows above matching
  `objectTypeId == "0-2"` and `isEnabled == true`; explicitly noted "no fifth company scoring
  flow exists." [VERIFIED: .planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md:6-19]
  The other four flows are non-company (deal-pipeline defaults, a contact form-submission flow)
  and are out of CLEAN-01's scope regardless. Since this snapshot, Phase 40 created exactly two
  *new* flows via `POST` (never a duplicate/throwaway flow object — its own D-07 protocol
  edits the *same* flow id through disable→edit→enable, never creates a copy). Prior:
  **likely zero orphaned company-scoring flows**, but this is now >24h stale and D-02
  explicitly forbids relying on a cached fact — Phase 42 must re-run the live `GET
  /automation/v4/flows` enumeration itself.
- **`ZZ-SCORING-TEST-DELETE-ME-*` disposable companies:** every Phase 40 plan tore these down
  in the same run (`finally`-block deletes, 204 responses) and 40-07's close explicitly
  confirms a portal-wide sweep found zero survivors.
  [VERIFIED: .planning/phases/40-scoring-engine-remediation-notes/40-07-SUMMARY.md (search
  "No `ZZ-SCORING-TEST-DELETE-ME-*` company survived any validation")] These are company
  *records*, not schema artifacts, and are not CLEAN-01's target — noted only because the
  research brief asked whether any survived; the answer is no, as of Phase 40's close.
- **Phase 39 probe leftovers, org_type probe (`lv__phase21_org_type_probe`):** the 9-step
  ladder's own cleanup step (Step 9) archived the disposable property and the operator's
  verbatim residual-state line reads "Clean — nothing left behind in the portal."
  [VERIFIED: .planning/workstreams/milestone/phases/21-transport-schema-hygiene/21-03-SUMMARY.md:96-97]
- **`scripts/snapshot_hubspot_schema.py`'s own probe property**
  (`lv__phase15_unknown_property_probe`, defined at
  scripts/snapshot_hubspot_schema.py:50): no `SUMMARY.md` or evidence file in the repo records
  this probe ever being armed (`DRY_RUN=false` + `--probe` + a valid `TEST_COMPANY_IDS`
  entry). **UNVERIFIED** — Phase 42's live enumeration should explicitly check for this exact
  property name; if present, it is uncontested-orphan-shaped (obvious provenance, a
  double-underscored probe name, zero references anywhere in `n8n/` or `src/`).
- **`config/hubspot_flows/*.before.json` files:** these are Phase 40's own archived
  pre-remediation flow/property JSON, already living in git under the exact convention D-09
  extends. They are *repo* artifacts, not live portal objects — nothing to archive live; they
  are already the archive.

**Net assessment:** the honest, evidence-backed expectation is that D-02's live diff will find
few or zero genuinely orphaned properties/flows beyond, at most, one unconfirmed probe property
name. The planner should build the archival task to **accept and report a "nothing found"
outcome** as a valid, fully-satisfying result for SC1 — not structure the plan so that finding
zero orphans looks like task failure.

## Live-Portal Enumeration Mechanics (D-02)

- **Properties:** `GET /crm/v3/properties/{objectType}` (no query params needed; the response
  includes `name`, `label`, `type`, `fieldType`, `groupName`, `options`, `hubspotDefined`,
  `calculated`, `calculationFormula` where applicable, `archived`). Already implemented,
  read-only, and destination-fixed by `scripts/snapshot_hubspot_schema.py:61-96` — `_get_properties_raw()`
  fetches, `_write_snapshot()` writes verbatim to
  `config/hubspot_migration/baseline/portal-schema-{object_type}-{label or UTC timestamp}.json`.
  [VERIFIED: scripts/snapshot_hubspot_schema.py:61-96] D-09 keeps this destination/naming
  unchanged — Phase 42 should invoke this script (with a phase-specific `--label`, e.g.
  `phase42-pre`) rather than hand-rolling a new GET. This portal returned all ~270 properties
  in a single unpaginated call at last observation (no `after`/cursor handling anywhere in the
  script or its callers) — treat as **[CITED, not exhaustively documented]**: the CRM v3
  Properties list endpoint is not known to paginate the way the Objects Search endpoint does;
  this repo's own tooling has never needed to handle a cursor here.
- **Groups:** `GET /crm/v3/properties/{objectType}/groups`, used by
  `scripts/sync_hubspot_properties.py:109-114` (`_get_live_groups`). Same auth, same portal
  guard pattern.
- **Automation flows list:** `GET /automation/v4/flows` — used live in Phase 40 and returned 8
  total flows portal-wide in one unpaginated call.
  [VERIFIED: .planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md:6-8] No
  wrapper script exists yet for this call generically (Phase 40 hand-rolled it); Phase 42's new
  drift/archive tooling needs to add this, mirroring `_get_properties_raw`'s idiom
  (`requests.get`, `hs_headers()`, `BASE_URL` from `src/hubspot_client.py`).
- **Automation flow detail:** `GET /automation/v4/flows/{id}` — proven live repeatedly across
  Phase 40 (D-05's fetch/PUT round-trip). [VERIFIED:
  .planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md — every flow section]
- **Auth scope:** the private-app token already carries the `automation` scope (granted
  2026-08-06, used throughout Phase 40) plus the pre-existing `crm.objects.companies.read/write`,
  `crm.objects.contacts.read/write`, and (implicitly, since property CRUD succeeded throughout
  Phase 15/21/40) property-schema read/write scopes. No new scope grant is needed for Phase 42's
  read enumeration or its archival calls. [VERIFIED: CONTEXT.md "Established Patterns" +
  PORTAL-FACTS.md header]
- **Portal identity guard:** every existing schema-mutating script asserts
  `HUBSPOT_PORTAL_ID == "22617666"` before any call and refuses otherwise
  (`scripts/snapshot_hubspot_schema.py:39,147-151`; identical pattern in
  `sync_hubspot_properties.py:47,224-227` and `rollback_property_migration.py`). Any new script
  Phase 42 adds should copy this guard verbatim — it is the established idiom, not optional.

## Reference Detection (D-02's "referenced by nothing")

**Surfaces to scan**, derived from where a live property/flow name can legitimately appear as an
executable reference in this repo:

1. `config/hubspot_flows/*.json` (both `.before.json` and `.after.json`) — flow branch filters
   (`MULTISTRING`/`IS_EQUAL_TO` etc.) and, distinctly, the `calculationFormula` string field on
   calculated properties (see trap 3 below — this is a plain string, not a structured JSON key).
2. `n8n/code/*.js` — the Code-node source (`mergeCompanies.js`, `enrichmentGate.js`, etc.)
   compiled into the deployed workflow JSON by `scripts/build_cloud_workflows.py`.
3. `n8n/wf_*.json` — the actual deployed/exportable workflow definitions (the *build output*,
   not the source). A property can appear in the built JSON without appearing verbatim in
   `build_cloud_workflows.py` if it's assembled from a CSV constant (see trap 2).
4. `scripts/build_cloud_workflows.py` — the workflow generator; this is where most property
   fetch/candidate lists actually live as Python string constants.
5. `src/*.py`, `scripts/*.py` — the offline oracle (`src/icp_scoring.py`), backfill tooling
   (`scripts/backfill_seed_company_scores.py`), and any CLI script.
6. `config/*.yaml` — `config/hubspot_properties.yaml` (declaration) and `config/icp_scoring.yaml`
   (rubric — property *values*, not names, mostly, but `tier_rules`/`recommended_motion` keys
   double as `lv_icp_tier` enum values).
7. `tests/*.py` — a property referenced only by a test assertion (not by production code) is a
   distinct, weaker signal than a production reference; the detector should distinguish these,
   since a test-only reference doesn't prove the property does anything live.
8. `n8n/code/*.generated.js` (e.g. `hubspotEnums.generated.js`, `taxonomy.generated.js`) — build
   artifacts generated from the YAML/taxonomy sources; a name can appear here even if the
   *source* file uses a different literal (e.g. an enum key vs. a full property name).

**False-positive / false-negative traps found by direct inspection, not assumption:**

- **Existing prefix regex silently excludes the `*_score` family.** The one existing
  reference-detector in this repo, `tests/test_hubspot_schema_coverage.py:33`, uses
  `PROPERTY_RE = re.compile(r"\b(lv_[a-z0-9_]+|enrichment_[a-z0-9_]+)\b")`. This pattern
  **cannot match** `org_type_score`, `geography_score`, `annual_revenue_score`,
  `produces_content_score`, or `gambling_score` — none carry the `lv_` or `enrichment_` prefix.
  A reference detector built by copying this regex would report all five component-score
  properties as "referenced by nothing" and mark them uncontested-orphans — which would
  directly violate D-01's do-not-archive set. [VERIFIED: tests/test_hubspot_schema_coverage.py:33]
  Any new detector must use a broader match set (or explicitly whitelist the five score names)
  before computing "referenced by nothing."
- **Two parallel company-search property-list constants, feeding different templates.**
  `scripts/build_cloud_workflows.py:1769-1778` (`HS_CO_SEARCH_BODY_EXPR`, feeds the "local-live
  variant" template, used at line 3080) and `scripts/build_cloud_workflows.py:3996`
  (`ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`, feeds the Cloud template) are **two separate property
  lists**. As of the last read, `HS_CO_SEARCH_BODY_EXPR`'s literal list (line 1769-1778) does
  **not** include `lv_country_region_normalized`, while `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`
  was patched to include it in commit `00f6f2b` (`fix(40): add lv_country_region_normalized to
  the company existingRecord fetch list`, `scripts/build_cloud_workflows.py` diff,
  `n8n/wf_enrichment_cloud.json` diff). A grep for a property name that stops at the first hit
  would report "referenced" without checking whether the reference is in the template that's
  actually deployed/live-relevant. A reference detector must enumerate **both** constants
  (and confirm which built `n8n/wf_*.json` file is the one actually consumed by a live/enabled
  workflow) rather than treating any single grep hit as sufficient.
- **Sticky notes are documentation, not references — and this repo has already been burned by
  this exact trap.** `HANDOVER-2026-08-06-icp-scoring.md:443-445` documents that
  `lv_icp_scored_at` "appears in `wf_scheduled_maintenance_cloud.json` but does not exist in
  HubSpot (404)... it is only named in a sticky note stating SJ predicates never reference it."
  `tests/test_hubspot_schema_coverage.py:35-39,127-129` already excludes
  `n8n-nodes-base.stickyNote` nodes from its reference scan for exactly this reason. Any new
  D-02 detector must apply the same exclusion, or it will conclude `lv_icp_scored_at` is
  "referenced" by the very sticky note that says the opposite.
- **Prose in superseded planning docs is not a reference.** `39-DECISION.md:107-112`'s mention
  of "`*_score` orphans" (see landmine above) is exactly this trap in the other direction — a
  planning-doc string match that looks like it endorses archiving properties that must not be
  archived. Reference detection for D-02 should scope its search to *executable* surfaces
  (flow JSON, Code-node JS, Python source, YAML config) and treat `.planning/`/`*.md` hits as
  context only, never as "referenced by nothing" evidence.
- **A calculated property's formula is a plain string field, not a structured reference.**
  `lv_icp_fit_score`'s `calculationFormula` (`config/hubspot_flows/lv_icp_fit_score-property.after.json:4`)
  is the string `"org_type_score + geography_score + annual_revenue_score +
  produces_content_score + gambling_score"`. A JSON-structural comparator that only walks
  named keys (e.g. diffing `options`/`type`/`fieldType`) will not see this as a reference at
  all — it must be treated as free text and substring-searched. This is also the concrete
  mechanism behind the archival safety risk noted below: archiving any of the five terms this
  formula sums, while the formula still references them, is exactly the scenario D-01's
  do-not-archive set exists to prevent.

## Archive Semantics (D-07) — live-verified, not assumed

- **DELETE is a soft archive, confirmed live in this portal.** The 9-step probe ladder's
  Step 8 archived a disposable company property (`DELETE
  /crm/v3/properties/companies/{name}`), then immediately re-created a property under the
  **same name** with a different type — the create succeeded (HTTP 201).
  `name_immediately_reusable: yes`. [VERIFIED:
  .planning/workstreams/milestone/phases/21-transport-schema-hygiene/21-03-SUMMARY.md:87-98]
  This directly demonstrates the DELETE call does not permanently reserve or destroy the name —
  consistent with an archive, not a hard delete.
- **90-day retention, values retained, restore path.** [CITED, MEDIUM confidence — not
  re-verified live this session, carried from Phase 15's documentation research]: HubSpot's own
  reference describes the delete operation as moving the property "to the trash"; archived
  properties and their **values are retained for 90 days**; within that window an admin can
  restore via the portal UI, or — per community-reported behavior, not an official documented
  guarantee — by re-creating a property with the identical internal `name`, which restores
  previously-assigned values. After 90 days, archived properties are permanently deleted and
  cannot be restored. There is **no documented dedicated REST `restore` endpoint** — restoration
  is a UI action or the recreate-by-name side effect.
  [CITED: .planning/milestones/v0.3-phases/15-hubspot-property-migration/RESEARCH.md:110-118,126]
- **What happens to record values on archive:** the live probe's own step 4 (read the value
  back after conversion) was invalidated by an unrelated test-data bug (a stale, non-existent
  `TEST_COMPANY_IDS=789`), so this specific repo does **not** contain a clean live observation
  of "archive a *populated* property, recreate it, confirm the value returns." Treat the
  "values retained/restored" claim as `[CITED, MEDIUM confidence]` per Phase 15's own tagging,
  not `[VERIFIED]`. [file:
  .planning/workstreams/milestone/phases/21-transport-schema-hygiene/21-03-SUMMARY.md:104-114]
  This is low-risk for CLEAN-01 specifically because the do-not-archive set (D-01) already
  excludes every property that carries real data on real companies; anything genuinely a
  candidate for archival under D-02/D-03 is expected to be data-sparse (a probe property, an
  unused property) — but the planner should not claim this is empirically proven for
  data-bearing properties, because it isn't, in this repo.
- **Calculated-property-in-formula risk — UNVERIFIED, and this is the reason D-01 is
  load-bearing, not decorative.** No repo evidence answers "can HubSpot's API archive a
  property that is currently referenced inside another property's live `calculationFormula`
  string?" This was never tested (nothing in this repo has ever tried to archive a term of a
  live formula — every archival probe used a disposable, formula-unreferenced property). What
  *is* independently confirmed is the blast radius if it goes wrong: Phase 40 found that
  `lv_icp_fit_score`'s formula "blanks entirely when one referenced term is null, not treats it
  as 0" (`.planning/STATE.md` Phase 40-04 decision entry). If archiving `org_type_score` (say)
  either (a) succeeds and the term becomes permanently null/undefined, or (b) HubSpot rejects
  the DELETE outright because the property is formula-referenced — either outcome is currently
  **unknown** and untested in this portal. **Recommendation:** this is exactly why D-01's
  do-not-archive set must be enforced as a hard pre-flight check in the archival tooling (assert
  the candidate name is not a substring of any live `calculationFormula` before calling
  DELETE), not merely documented as a decision on paper — the failure mode if the check is
  skipped is silent, portfolio-wide score corruption, not a clean API rejection.
- **Reusable code:** `scripts/rollback_property_migration.py:120-134` already has
  `_get_property_live(object_type, name)` (existence probe, returns `None` on 404) and
  `_archive_property_live(object_type, name) -> status_code` (the DELETE call itself) — both
  directly reusable building blocks for D-07's archive tooling, already following the same
  `hs_headers()`/`BASE_URL` idiom as every other script in this repo.
  `_archive_group_live(object_type, name)` at :137-141 is the equivalent for property groups
  (not expected to be needed here, since D-09 doesn't call for group archival, but present if
  needed).

## Flow Deactivation (D-08) — live-verified, same PUT shape as content edits

- **`isEnabled` is a top-level boolean field on the flow's JSON body**, confirmed live:
  `"isEnabled": true` at `config/hubspot_flows/4626124224-org-type-score.after.json:251`.
- **Disable via PUT is proven live, in this exact portal, in Phase 40**, using the identical
  fetch→edit→PUT round trip already proven for `STATIC_BRANCH`/`LIST_BRANCH` action-content
  edits (D-05's mechanism): *"Disable — PUT the archived `.before.json` body with `isEnabled:
  false`. Accepted (200); re-GET confirmed `isEnabled: false`."* ...*"Confirmed enabled — final
  re-GET: `isEnabled: true`."* [VERIFIED:
  .planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md:80-81,93] This is not a
  new API shape Phase 42 needs to discover — it is the *same* `PUT /automation/v4/flows/{id}`
  endpoint Phase 40 already round-tripped six times (four repaired flows + two new ones), just
  flipping a different top-level field.
- **No new endpoint or fallback needed.** D-08's "fetch JSON to repo, then deactivate" is
  therefore: `GET /automation/v4/flows/{id}` → write to
  `config/hubspot_flows/<dated-archive-dir>/{id}-{name}.archived.json` (D-09's naming, extended
  with a dated subdirectory per Claude's discretion) → `PUT
  /automation/v4/flows/{id}` with the fetched body, `isEnabled` set to `false`, all other
  fields byte-identical to the GET.
- **One live-discovered PUT gotcha to carry forward:** a flow's PUT rejects reintroducing any
  `actionId` that existed in an earlier revision of that same flow but is absent from the
  current PUT body — even with no duplicate/orphan actionIds in the current payload
  (`.planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md`, "Plan 05 section").
  Not relevant to a pure `isEnabled` toggle (the action list is unchanged), but worth keeping in
  mind if D-08's archival PUT accidentally strips or reorders action ids while re-serializing
  the fetched JSON — send the GET body back verbatim with only `isEnabled` changed.

## Reconciliation Gap (D-04) — exact current state, confirmed by direct Read

`config/hubspot_properties.yaml` is 500 lines: companies section spans lines 1-337 (1 group,
`lv_enrichment`; 22 properties), contacts section spans lines 338-500 (1 group,
`lv_enrichment_contacts`; 17 properties). [VERIFIED: config/hubspot_properties.yaml — full file
read] Confirmed absent from the companies list: `lv_org_type`, `lv_produces_content`,
`lv_icp_fit_score`, `lv_icp_tier`, `lv_anti_icp_flag`, `lv_icp_confidence`,
`lv_recommended_motion`, `lv_icp_scored_at`, `lv_icp_scoring_version`,
`lv_named_account_priority`, and all five `*_score` properties — matches CONTEXT.md's D-04
premise exactly.

**Yaml schema shape** (per-property, exact keys an expansion must match):
```yaml
- name: <property_name>
  label: <Display Label>
  type: <bool|string|number|datetime|enumeration>
  fieldType: <booleancheckbox|text|textarea|number|date|select|checkbox|calculation_equation>
  groupName: <group_name>
  options: []   # or a list of {label, value, displayOrder, hidden}
```
[VERIFIED: config/hubspot_properties.yaml:6-35 for the enumeration shape,
:150-163 for the bool shape, :192-197 for the string/no-options shape]

**Live groupName for the ICP output properties is `companyinformation`, not `lv_enrichment`.**
Both `lv_icp_fit_score` and `lv_icp_tier` live under HubSpot's native `companyinformation`
group. [VERIFIED: config/hubspot_flows/lv_icp_fit_score-property.after.json:13,
config/hubspot_flows/lv_icp_tier-property.after.json:12] The yaml's `groups:` list currently
declares only `lv_enrichment` (companies) / `lv_enrichment_contacts` (contacts)
[VERIFIED: config/hubspot_properties.yaml:2-4,339-341]. New entries for `lv_icp_fit_score`,
`lv_icp_tier`, and any other property that actually lives in `companyinformation` must set
`groupName: companyinformation` — a HubSpot-native, `hubspotDefined` group that must **not** be
declared in the yaml's own `groups:` list (that list is only for groups this project's own
sync tooling would need to create).

**`lv_icp_tier`'s live enum is exactly `A`/`B`/`C`/`D`/`Unscored` — five values, not six.**
Verbatim from the live property definition: `{"label": "A", "value": "A"}`, `{"label": "B",
"value": "B"}`, `{"label": "C", "value": "C"}`, `{"label": "D", "value": "D"}`, `{"label":
"Unscored", "value": "Unscored"}`. [VERIFIED:
config/hubspot_flows/lv_icp_tier-property.after.json:22-58] **Correction to the task brief's
framing:** the research priorities describe D-06's target as confirming the enum "must accept
`Unscored` and `Needs Review`, not just A-D." Live evidence shows only `Unscored` was added
(Phase 40, F8/ENGINE-07); `Needs Review` was **deliberately deferred**
(`.planning/phases/40-scoring-engine-remediation-notes/40-06-SUMMARY.md`: *"no `Needs Review`
option added (deferred, per REQUIREMENTS.md)"*) and is a **documented, accepted** PARITY-01
divergence, not an open defect: *"1 documented `Needs Review` divergence... only the tier label
diverges because HubSpot's live `lv_icp_tier` enum has no `Needs Review` value"*
(`.planning/STATE.md`, Phase 40-07 decision entry). Since D-05 mandates "live wins, yaml
catches up" and reconciliation performs no portal mutation, the correct yaml entry for
`lv_icp_tier` is the **five-value live enum**, and if the comparator is later run against
`config/icp_scoring.yaml`'s `recommended_motion` map (which does list a `Needs Review` key,
`config/icp_scoring.yaml:83`), that mismatch should be **reported as a known, already-accepted
divergence**, not treated as a reconciliation failure to fix — fixing it would require a
portal-side enum-option addition, which is outside D-05's no-mutation reconciliation and outside
D-07/D-08's archival-only mutation authorization.

**Five of the ten D-04 names have no live-creation evidence anywhere in the repo — the
single biggest open risk in this phase.** `lv_icp_confidence`, `lv_recommended_motion`,
`lv_icp_scored_at`, `lv_icp_scoring_version`, `lv_named_account_priority` all trace back
exclusively to CLAUDE.md's local-MVP design (§5.2/§12, e.g. `src/merge_policy.py:348-350`'s own
comment listing them as fields the *local* oracle "still computes... for in-pipeline [use]" but
never writes to HubSpot). None of six pre-Phase-40 live portal-schema snapshots under
`config/hubspot_migration/baseline/` contain any of these five names
[VERIFIED: direct query against all 6
`config/hubspot_migration/baseline/portal-schema-companies-*.json` files — see method below].
One is explicitly documented as a live 404 as of 2026-08-06: *"`lv_icp_scored_at` appears in
`wf_scheduled_maintenance_cloud.json` but **does not exist** in HubSpot (404). Harmless — it is
only named in a sticky note..."* [VERIFIED: HANDOVER-2026-08-06-icp-scoring.md:443-445]. A
company-search property list explicitly documents itself as requesting only "the 5 lv_* props
that ACTUALLY exist in portal 22617666" [VERIFIED: scripts/build_cloud_workflows.py:1763-1764],
and `lv_named_account_priority` is separately flagged in an older phase's RESEARCH.md as one of
the CLAUDE.md-specified properties that "do NOT all exist as real custom properties in portal
22617666" [VERIFIED: .planning/milestones/v0.3-phases/16.4-fetch-by-objectid/16.4-RESEARCH.md:256].
`test_cloud_companies_branch.py:87-100` further documents `lv_recommended_motion` as a name the
pipeline is **forbidden** to write (on the theory HubSpot derives it) — but no code anywhere
creates or writes it either. **Recommendation:** Phase 42's live D-02 enumeration must
individually GET (or check against the fresh full-portal snapshot) each of these five names.
Whichever are still absent belong in the reconciliation output as a **documented gap**
("declared in the superseded local-MVP design, never implemented live — out of scope for this
phase's no-portal-mutation reconciliation"), not as new yaml entries. Fabricating yaml entries
for non-existent live properties would itself be a drift the very next `--reconcile` run
reports.

*Method for the "not in any baseline snapshot" claim above:* each of the six files under
`config/hubspot_migration/baseline/portal-schema-companies-*.json` was parsed and its
`results[].name` set checked for membership of the five names plus `lv_icp_needs_review` (present
only from `-post-canary.json` onward) and the five already-confirmed-live names (`lv_icp_fit_score`,
`lv_icp_tier`, `lv_anti_icp_flag`, `lv_org_type`, `lv_produces_content` — present in all six). All
six snapshots pre-date Phase 40 (most recent: probe-related, 2026-07-30-ish); none reflect the
`*_score` properties either, since those were created after every one of these snapshots was
taken. This is why D-11 requires re-running `snapshot_hubspot_schema.py` fresh, not relying on
these committed files — they are stale for exactly the objects this phase cares about.

## What Consumes the yaml (D-05's no-mutation guarantee)

**Only one consumer writes to the portal:** `scripts/sync_hubspot_properties.py:44`
(`CONFIG_PATH`). It is a **create-only** tool: `compute_property_diff` (:72-93) computes
`desired - actual` by property `name`; if `actual is not None` (the property already exists
live, regardless of shape match), the property is **never** proposed for creation — a
shape mismatch is appended to a `drift` list that is explicitly "report only, never
auto-fixed" (:74,157-158). The live write path itself is additionally two-key gated
(`DRY_RUN=false` AND `ALLOW_HUBSPOT_PROPERTY_WRITES=true`, :58-61) and defaults to a dry-run
report. **Consequence for D-04:** since every property D-04 wants added to the yaml (other than
the five unconfirmed design-only names above) already exists live under the exact same name,
`sync_hubspot_properties.py` would treat all of them as already-satisfied and propose **zero**
creates for them — expanding the yaml under D-04 does not, by this tool's own logic, risk a
portal write. The only latent risk is the group-creation path (`compute_group_diff`, :96-98):
if a new yaml entry declared a `groupName` not already present in the yaml's own `groups:` list
*and* not already live, a future sync run would try to create that group. Since the correct
`groupName` for the ICP-output properties is `companyinformation` (a native, already-existing
group — see above), and D-04's other new entries (the five `*_score` properties) most likely
also live outside the `lv_enrichment` group (unverified — Phase 42's live GET must confirm each
`groupName`), this risk is avoidable as long as the yaml's `groups:` list is **not** edited to
declare `companyinformation` (native groups should never be declared there) and each new
property's `groupName` field is set from the live GET, not guessed.

**Read-only / non-mutating consumers, confirmed by grep + spot-read, no write path in any:**
- `scripts/canary_record_snapshot.py:48,75` — derives the yaml's declared property names for
  a record-snapshot utility. Read-only.
- `tests/test_hubspot_properties_config.py` (whole file) — offline structural validation of the
  yaml itself. Read-only, but **will need direct edits as part of this phase's own work**
  (below).
- `tests/test_backend_status_wiring.py:21,90-102` — derives expected portal-declared property
  types from the yaml at test time. Read-only.
- `n8n/code/reviewDecision.js:59`, `scripts/build_cloud_workflows.py:6100`, `n8n/README.md:325`,
  `docs/architecture/ENRICHMENT-WORKFLOW-PLAN.md:124` — prose comments referencing the yaml as
  the source of truth for the `lv_`-prefixed review family. Not executable references to
  specific property names; no mutation.

**Second-order test-suite conflict — the concrete, load-bearing risk for D-04's execution, not
just a design question.** `tests/test_hubspot_properties_config.py` encodes the yaml's *old*
contract (a create-only manifest of what's missing), and three of its tests directly
contradict D-04's new contract (a full mirror):
1. `test_every_property_name_is_lv_prefixed` (:45-51) — asserts every property name starts
   with `lv_` except two named Lusha exemptions. The five `*_score` properties do not start
   with `lv_` and will fail this test the moment they're added, unless the exemption set
   `_PN1_EXEMPT_NAMES` (:42) is extended to cover them (or the test's rule is otherwise
   relaxed for this phase's additions).
2. `test_every_type_fieldtype_pair_is_valid` (:54-58) — `VALID_TYPE_FIELDTYPE_PAIRS` (:13-23)
   does not include `("number", "calculation_equation")`, which is `lv_icp_fit_score`'s live
   `fieldType`. Adding `lv_icp_fit_score` to the yaml with its real live shape will fail this
   test unless the valid-pairs set is extended.
3. `test_lv_org_type_and_lv_produces_content_not_listed_for_creation` (:94-101) — asserts, by
   name, that `lv_org_type` and `lv_produces_content` are **absent** from the companies
   properties list, with the docstring explicitly stating "the plan explicitly omits them."
   D-04 explicitly wants both of these **added**. This test's premise is the exact thing D-04
   overturns — it cannot simply be "fixed," it needs to be deleted or rewritten to match the
   new full-mirror contract, and that rewrite should be called out as a deliberate,
   documented supersession in the plan (mirroring how `42-CONTEXT.md` documents D-01's
   supersession of ROADMAP SC1), not a silent test edit.

Additionally, `test_exact_counts_guard_against_manifest_drift` (:87-91) hardcodes
`len(companies_properties) == 22`, `len(contacts_properties) == 17`,
`len(companies_groups) == len(contacts_groups) == 1` — this test exists specifically as a
manifest-drift tripwire and is *expected* to need its numbers bumped as part of this phase's
own work, not a defect to route around.

## Enum-Value Comparison (D-06)

Both the yaml and the live API represent enum options as a list of dicts with a `value` key
(yaml: `{label, value, displayOrder, hidden}` — [VERIFIED: config/hubspot_properties.yaml:12-35];
live API: `{description, displayOrder, hidden, label, value}` — [VERIFIED:
config/hubspot_flows/lv_icp_tier-property.after.json:23-57]). The API includes an extra
`description` key the yaml's shape doesn't carry; per D-06 this is cosmetic and excluded from
the existence+enum-value comparison depth. `scripts/sync_hubspot_properties.py:68-69`
(`_options_values`) already implements exactly the comparison D-06 wants —
`{str(o.get("value")) for o in (options or [])}` — and is directly reusable (or trivially
portable) into the new D-10 drift-check script rather than reinvented. The one concrete case to
encode as a named assertion in that script, per the live evidence above: `lv_icp_tier`'s live
value set is `{"A", "B", "C", "D", "Unscored"}` — five values — and the drift script should
assert against this live-read set, not against `config/icp_scoring.yaml`'s `tier_rules` keys
(which also include `Unscored` but never enumerated `Needs Review` as a `tier_rules` entry
either — only `recommended_motion` mentions it, `config/icp_scoring.yaml:83`) or against any
assumption carried over from pre-Phase-40 documentation.

## Timing Constraint / n8n Independence

Phase 42's mutating work is entirely HubSpot-side: CRM v3 Properties `DELETE` (D-07),
Automation v4 Flows `GET`/`PUT` for `isEnabled` (D-08), and a new read-only drift script (D-10).
None of it touches `n8n/wf_*.json`, `scripts/build_cloud_workflows.py`'s generation path, or
`scripts/deploy_n8n_workflows.py` — the tooling that bakes `ALLOW_HUBSPOT_RECORD_WRITES` and
other write-safety constants into a deployed n8n workflow
(`.planning/STATE.md`'s Phase 40-03 blocker entry names this exact baking mechanism). Since
Phase 42 never rebuilds or redeploys n8n workflow content, it cannot rebake those constants and
is **independent of whatever arm-window state Phase 41's live import run leaves behind** —
Phase 42 can run regardless of whether Phase 41's `scheduled_arm.py`/write-gate window is open
or closed at the time. The one soft interaction worth naming in the plan: if Phase 41's import
run is actively writing/enrolling companies at the exact moment Phase 42 runs its D-02 live
enumeration, the property/flow **schema** it reads is still unaffected (Phase 41 writes property
*values* on company records, not property/flow *definitions*), so even concurrent execution
poses no schema-read hazard. The archival gate (D-01's do-not-archive set) is unaffected by
either phase's concurrent state.

## Common Pitfalls

### Pitfall 1: Treating "reconciled" as "written," when the yaml's oracle test suite still
encodes the old create-only contract
**What goes wrong:** the plan adds ten-plus new yaml entries and calls SC2 satisfied, but
`tests/test_hubspot_properties_config.py`'s pre-existing assertions (prefix rule, valid
type/fieldType pairs, "not listed for creation," exact counts) fail or actively contradict the
new entries, and CI/local test runs surface this as unrelated breakage.
**Why it happens:** the yaml's original design intent (create-only manifest) and D-04's new
intent (full mirror) are genuinely incompatible without an explicit test-suite update.
**How to avoid:** treat the `tests/test_hubspot_properties_config.py` update as an explicit
task in the plan, not a side effect — see the three specific tests named above.
**Warning signs:** `pytest tests/test_hubspot_properties_config.py` red immediately after the
yaml edit.

### Pitfall 2: Fabricating yaml entries for properties that were designed but never created live
**What goes wrong:** `lv_icp_confidence`/`lv_recommended_motion`/`lv_icp_scored_at`/
`lv_icp_scoring_version`/`lv_named_account_priority` get added to the yaml on the strength of
CONTEXT.md's D-04 list, without a live existence check; the very next drift-check run reports
these as "declared but archived/missing" drift, since D-05 forbids creating them.
**Why it happens:** D-04's list was written from the design intent (CLAUDE.md/HANDOVER), not
from a live GET, and this phase's own research (this file) could not close the existence
question for these five without Phase 42's own live call.
**How to avoid:** run the live D-02 enumeration and individually confirm existence for each of
the five before writing any yaml line for them; anything absent goes in a documented-gap report
section, not the yaml.
**Warning signs:** a `--reconcile`/drift-check run immediately after the yaml expansion reports
drift on properties that were *just* added.

### Pitfall 3: Archiving a component score property while `lv_icp_fit_score`'s formula still
references it
**What goes wrong:** an "uncontested orphan" judgment call (D-03) misses that a property name
is referenced only inside a `calculationFormula` string (a plain-text field, not a structured
JSON reference), archives it, and the live ICP score for every scored company either blanks or
the formula errors.
**Why it happens:** the reference-detection surfaces listed above (flow JSON, Code-node JS,
Python, YAML) don't include "is this a substring of any live property's `calculationFormula`"
by default — it's a distinct check.
**How to avoid:** the archival pre-flight for every candidate must explicitly check it's not a
substring of any live `calculationFormula` (start with `lv_icp_fit_score`'s formula string,
verbatim quoted above) in addition to the D-01 do-not-archive name list.
**Warning signs:** none live-observed in this repo — this is precisely why it's flagged as
UNVERIFIED risk rather than a known-safe/known-broken fact.

### Pitfall 4: Reusing the existing `PROPERTY_RE` regex verbatim for D-02's reference detector
**What goes wrong:** the five `*_score` properties are reported as unreferenced (they don't
match `lv_`/`enrichment_` prefixes) and become uncontested-archive candidates.
**Why it happens:** `tests/test_hubspot_schema_coverage.py:33`'s regex was written for a
different, narrower purpose (this project's own `lv_`/`enrichment_`-namespaced properties) and
predates the `*_score` family's existence.
**How to avoid:** build D-02's detector with an explicit name-list match (the D-04 property set
plus the flow-write targets from `tests/test_flow_rubric_conformance.py:355-359`), not a prefix
regex.
**Warning signs:** a "referenced by nothing" report that includes any of the five `*_score`
names.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | HubSpot's CRM v3 Properties list endpoint (`GET /crm/v3/properties/{objectType}`) does not paginate at this portal's scale (~270 properties) and returns all results in one call. | Live-Portal Enumeration Mechanics | Low — if wrong, the new enumeration script silently under-reports properties; easily caught by comparing the returned count against the ~270 figure already observed in this repo's committed snapshots. |
| A2 | Archived-property values are retained for 90 days and restorable by UI or recreate-by-name (no dedicated REST restore endpoint). | Archive Semantics | Low for this phase specifically (D-01 excludes all data-bearing properties from archival), but would matter if the archival scope is later broadened; carried forward as `[CITED, MEDIUM confidence]` from Phase 15's own research, not independently re-verified this session. |
| A3 | Archiving a property that is currently referenced inside another property's live `calculationFormula` is untested and its outcome (rejected vs. silently accepted with a broken formula) is unknown. | Archive Semantics (calculated-property-in-formula risk) | High if this phase's archival tooling skips the pre-flight substring check — could silently zero out `lv_icp_fit_score` portfolio-wide. Mitigated by keeping D-01's do-not-archive set intact and adding the pre-flight check as a hard gate, not by resolving the underlying API question (which this research could not do without a live, risky test). |
| A4 | `lv_icp_confidence`, `lv_recommended_motion`, `lv_icp_scored_at`, `lv_icp_scoring_version`, `lv_named_account_priority` do not exist live in portal 22617666 as of this research session (2026-08-07). | Reconciliation Gap | Medium — based on absence from six pre-Phase-40 snapshots plus explicit 404 documentation for one of the five; none of the five have any live-creation code path in this repo. Could theoretically have been created out-of-band (portal UI) since the last committed evidence; Phase 42's own live GET is the actual authority and must re-confirm before the yaml is written. |

**If this table is empty:** not applicable — see above.

## Open Questions

1. **Does the `scripts/snapshot_hubspot_schema.py --probe` property
   (`lv__phase15_unknown_property_probe`) still exist live?**
   - What we know: the script exists, is two-key-gated, and no `SUMMARY.md` in the repo
     documents it ever being armed.
   - What's unclear: whether an operator ran it out-of-band without a committed record.
   - Recommendation: Phase 42's own live property enumeration will surface this automatically
     if it's present (it will show up as a company property with zero references anywhere in
     `n8n/`/`src/`/`scripts/` other than the probe script's own module constant) — no separate
     investigation needed, just don't assume it's absent going in.

2. **What are the live `groupName`, `type`, and `fieldType` values for the five `*_score`
   properties?**
   - What we know: they exist live (confirmed via multiple test files and
     `scripts/backfill_seed_company_scores.py`), and are `number`-typed by every code path that
     writes to them (e.g. `tests/test_backfill_seed_company_scores.py:26,39,47-48` PATCHes them
     as bare integers).
   - What's unclear: their exact live `groupName` (likely `companyinformation`, matching
     `lv_icp_fit_score`/`lv_icp_tier`, since they were all created in the same Phase 40 session
     via direct API calls rather than through `sync_hubspot_properties.py`'s
     `lv_enrichment`-grouped manifest — but this repo contains no committed post-Phase-40
     property snapshot to confirm) and whether they carry a `numberDisplayHint` or other cosmetic
     field the yaml schema should record.
   - Recommendation: this is precisely what Phase 42's D-11 fresh `snapshot_hubspot_schema.py`
     run settles — do not guess `groupName` for these five; read it from the fresh snapshot.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `HUBSPOT_PRIVATE_APP_TOKEN` (env, `.env`-sourced) | Every live GET/DELETE/PUT this phase performs | Presumed ✓ (used successfully throughout Phase 40/41, 2026-08-06/07) | — | None — `.env` is permission-blocked to Read/Bash per repo convention; hand the operator a `!`-prefixed shell command if a value is ever needed interactively, but the token itself should already be exported in the execution shell per established pattern. |
| `automation` OAuth scope on the private app | `GET/PUT /automation/v4/flows*` | ✓ (granted 2026-08-06, used throughout Phase 40) | — | — |
| `HUBSPOT_PORTAL_ID=22617666` | Portal-identity guard in every script | Presumed ✓ | — | Every script refuses (exit 1) rather than proceeding against a mismatched portal — safe-by-default. |
| `pytest`, `PyYAML`, `requests` | Offline tests, yaml parsing, live HTTP calls | ✓ (already vendored, used throughout the repo's existing scripts/tests) | per `requirements.txt` | — |

**Missing dependencies with no fallback:** none identified — this phase reuses the exact
credential/scope surface already exercised successfully by Phase 40/41.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (already the project standard; `.venv/bin/python -m pytest`) |
| Config file | none dedicated — repo-root `pytest.ini`/`pyproject.toml` convention already governs `tests/` |
| Quick run command | `.venv/bin/python -m pytest tests/test_hubspot_properties_config.py tests/test_hubspot_schema_coverage.py -x` |
| Full suite command | `.venv/bin/python -m pytest` (offline tier); live-gated tests (e.g. anything hitting `HUBSPOT_PRIVATE_APP_TOKEN`) already opt-in via env, consistent with the rest of the repo |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLEAN-01 (yaml full-mirror expansion) | `config/hubspot_properties.yaml` gains the D-04 property set with correct shape | unit (offline) | `.venv/bin/python -m pytest tests/test_hubspot_properties_config.py -x` | ✅ exists, needs edits (see Pitfall 1) |
| CLEAN-01 (yaml full-mirror expansion, live confirmation) | yaml matches live per D-06 depth | new script + smoke | `python scripts/<new-drift-check-script>.py` (D-10) | ❌ Wave 0 — this is the phase's own new deliverable |
| CLEAN-01 (archival, do-not-archive set preserved) | the five `*_score` properties, `lv_icp_fit_score`, `lv_icp_tier`, and the six flows remain live and unarchived after this phase | unit (offline, existing) | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -x` | ✅ exists (Phase 40 conformance guard — already asserts these flows never write outside their rubric-correct property; extend or add a sibling assertion that they remain `isEnabled: true` post-Phase-42 if a fresh snapshot is captured) |
| CLEAN-01 (archival, snapshot-first) | `scripts/snapshot_hubspot_schema.py` runs and produces a fresh baseline before any DELETE/PUT | smoke (live, credential-gated) | `python scripts/snapshot_hubspot_schema.py --label phase42-pre` | ✅ exists |

### Sampling Rate
- **Per task commit:** the quick offline pytest command above.
- **Per wave merge:** full offline suite (`pytest tests/`), plus a live, read-only run of the
  new D-10 drift-check script (no mutation risk).
- **Phase gate:** full offline suite green, D-10 drift-check report committed (even if it shows
  documented, accepted divergences like the `lv_icp_tier` "Needs Review" gap above), and a
  fresh post-archival `snapshot_hubspot_schema.py --label phase42-post` confirming the
  do-not-archive set is still present and enabled.

### Wave 0 Gaps
- [ ] `scripts/<new-drift-check-script>.py` (D-10) — does not exist yet; this phase's own
      primary deliverable.
- [ ] `tests/test_hubspot_properties_config.py` updates for the D-04 expansion (prefix
      exemption, valid type/fieldType pair, exact-count bump, and either deletion or rewrite of
      `test_lv_org_type_and_lv_produces_content_not_listed_for_creation`) — file exists, needs
      targeted edits as an explicit task.
- [ ] A committed post-Phase-42 property snapshot (via `snapshot_hubspot_schema.py`) is the
      only way Open Question 2 (live `groupName`/shape for the five `*_score` properties) gets
      answered — no offline substitute.

## Security Domain

`security_enforcement` is absent from `.planning/config.json` — treated as enabled per the
governing instruction, though this phase's actual attack surface is minimal (a schema-hygiene
phase with no new user input, no new auth surface, no new external package).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No new auth surface; reuses the existing private-app token pattern. |
| V3 Session Management | No | N/A |
| V4 Access Control | Yes (narrow) | The two-key write gate (`DRY_RUN=false` + a dedicated `ALLOW_*` flag) is the established access-control pattern for every schema-mutating script in this repo (`sync_hubspot_properties.py:58-61`, `snapshot_hubspot_schema.py --probe`'s two-key gate) — any new archive/PUT tooling this phase adds should follow the same pattern rather than a single `DRY_RUN` flag alone, consistent with D-11's "Claude executes directly" convention still being scoped to reversible, snapshot-protected actions only. |
| V5 Input Validation | Yes | The D-01 do-not-archive substring/name check (Pitfall 3) is itself an input-validation control on the archival tool's own candidate list — it must run before every `DELETE`/`PUT`, not be a documentation-only decision. |
| V6 Cryptography | No | No secrets are created, rotated, or stored by this phase; the existing `_assert_no_secrets()` guard in `snapshot_hubspot_schema.py:78-83` already covers the one place this phase writes portal data to disk. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Archiving a live, data-bearing, or formula-referenced property by mistake (D-03's "ask on doubt" gate exists precisely for this) | Tampering / Denial of Service (of the scoring engine itself) | D-01's explicit do-not-archive name list, enforced as code (not just documentation) per Pitfall 3; D-03's ambiguous-item escalation to the operator before any DELETE. |
| A drift-check script that reports false "in sync" because its reference/enum comparator misses a namespace (Pitfall 4) | Tampering (silent) | Build the D-10 comparator against an explicit name list derived from D-04, not a regex reused from an unrelated, narrower-scoped test. |
| Credential/token leakage into a committed snapshot file | Information Disclosure | Already mitigated by the existing `_assert_no_secrets()` pattern (`snapshot_hubspot_schema.py:78-83`) — reuse verbatim in any new script that writes portal responses to disk. |

## Sources

### Primary (HIGH confidence — live-verified in this exact portal by prior phases, read directly this session)
- `.planning/workstreams/milestone/phases/21-transport-schema-hygiene/21-03-SUMMARY.md` —
  verbatim armed-probe VERDICT block (archive/recreate semantics, 2026-07-30).
- `.planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md` — live flow
  disable/enable PUT round-trips, live flow-list enumeration (8 total, 4 company-scoring).
- `config/hubspot_flows/lv_icp_fit_score-property.after.json`,
  `config/hubspot_flows/lv_icp_tier-property.after.json` — live property definitions read
  directly this session.
- `config/hubspot_properties.yaml` — read in full this session (500 lines).
- `HANDOVER-2026-08-06-icp-scoring.md:443-445` — live 404 confirmation for `lv_icp_scored_at`.
- `scripts/rollback_property_migration.py:120-141`,
  `scripts/sync_hubspot_properties.py:44-114,68-93` — reusable code, read directly.

### Secondary (MEDIUM confidence — documentation-derived, cited in the repo's own prior research with explicit confidence tagging)
- `.planning/milestones/v0.3-phases/15-hubspot-property-migration/RESEARCH.md:110-118,126` —
  HubSpot's official docs on archive-vs-delete semantics and the 90-day retention window,
  tagged `[CITED, MEDIUM confidence]` in the original research and carried forward unchanged
  here (not independently re-verified this session).

### Tertiary (LOW confidence — repo-internal prose/planning docs, used for context and landmine-flagging only, never as a reference-detection oracle)
- `.planning/phases/39-path-decision-fit-score-verification/39-DECISION.md:107-112` — stale
  cleanup-scope language, explicitly flagged above as superseded by `42-CONTEXT.md` D-01.
- CLAUDE.md §5-§8/§12 — superseded local-MVP design; used only to identify which D-04 property
  names lack live-creation evidence.

## Metadata

**Confidence breakdown:**
- Archive/flow-toggle mechanics: HIGH — live-verified in this exact portal by prior phases,
  read directly this session.
- Orphan candidate inventory: MEDIUM — strong repo-evidence prior (likely near-zero), but D-02
  explicitly requires Phase 42's own fresh live diff; nothing here substitutes for that.
- D-04 property-existence for the five design-only names: MEDIUM — absence is well-evidenced
  across six independent stale snapshots plus one explicit 404, but not re-confirmed live this
  session; Phase 42 must re-check.
- Reference-detection false-positive/negative traps: HIGH — each trap is demonstrated with a
  specific file:line, not inferred.

**Research date:** 2026-08-07
**Valid until:** ~2026-08-14 (7 days) — this research depends on live portal state that Phase 41
and any operator-run migration could change at any time; the property/flow existence claims in
particular should be treated as needing re-confirmation if this research is consumed more than
a few days after 2026-08-07.
