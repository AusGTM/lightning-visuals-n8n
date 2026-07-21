---
gsd_state_version: 1.0
milestone: v0.3
milestone_name: Company Enrichment & ICP Research
current_phase: 16
current_phase_name: Scheduled Workflows & Review Surface
status: awaiting plan
stopped_at: "Phase 15 executed (9 tasks, 8 commits + this docs commit), all offline-proven, zero live HubSpot calls made. Provenance = single JSON blob per object shipped in both Python (src/merge_policy.py) and JS (mergeCompanies.js/mergeContacts.js), byte-identical (parity + 2 deliberate-break proofs, incl. a manual ensure_ascii=False break-and-restore against real source). ICP write paths retired (Approach C). PN-1 contact rename (linkedin_url/persona_group -> lv_) landed. 33-property/2-group manifest + sync/rollback/canary scripts built and offline-tested; the live property creation, baseline snapshot, and canary proof are OPERATOR RUNBOOK steps (15-01-SUMMARY.md) not yet run. Next: run the operator runbook, then /gsd-plan-phase 16."
last_updated: "2026-07-22T00:00:00.000Z"
last_activity: 2026-07-22
last_activity_desc: "Phase 15 executed (9 tasks, 8 commits): scripts/snapshot_hubspot_schema.py (read-only baseline + unknown-property probe) and scripts/sync_hubspot_properties.py (two-key-gated dry-run diff + undo manifest, per-property creates not batch/create) built and offline-proven; config/hubspot_properties.yaml manifests 19 company + 14 contact = 33 properties + 2 groups under the provenance model (supersedes RESEARCH's 121-145 flat-suffix design); ICP write-path retirement (src/merge_policy.py, main.py, field_policy.yaml, mergeCompanies.js) with 3 flipped assertions now asserting ABSENCE; the atomic provenance-stamper rewrite (Task 5) replaced flat per-field metadata/staging with ONE JSON blob per object (lv_enrichment_provenance/lv_contact_enrichment_provenance) + 4 carve-out _verified_at cache keys in both Python (serialize_provenance, json.dumps sort_keys=True/ensure_ascii=False) and JS (stableStringify, recursive sorted-key stringify) — byte-parity proven incl. a non-ASCII fixture row (macron) and TWO deliberate-breaks (value-change; a genuine ensure_ascii=False removal-and-restore against the real source file, captured in the SUMMARY); enrichmentGate.js staleness now reads the real cache-key property, never the blob; PN-1 renamed linkedin_url/persona_group -> lv_linkedin_url/lv_persona_group everywhere they round-trip to a HubSpot property (decoupled from the raw read-side upload/scored-winner field name, which stays unprefixed) with a new architecture guard (14 parametrized cases); rollback_property_migration.py (manifest+baseline required, reverse-order archive, hubspotDefined belt-and-braces, DELIBERATE-BREAK proof) and rollback_canary_proof.py (create->archive->assert-archived on a throwaway property) shipped. 199 pytest passed / 77 node tests passed (baseline 148/74 + new, 0 regressions). PORTAL UNTOUCHED — zero live HubSpot calls made by the executor; every live script's no-credentials skip path is what ran. Discovered-not-fixed (carried forward, out of scope per plan): the 2 latent copy-loop bugs (lv_sponsorship_reliant, persona_group never reach the production merge candidate loop); icp_scoring.py:116 precedence bug + lv_icp_tier A/B/C/D enum bug, now dead-bound since Approach C retires the write path; lv_country_region_normalized has no explicit field_policy.yaml entry (falls to default fill_blank_only); lv_org_type text->enumeration one-way door deferred (C3, not scheduled). See 15-01-SUMMARY.md."
progress:
  total_phases: 16
  completed_phases: 15
  total_plans: 15
  completed_plans: 15
  percent: 94
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-07)

**Core value:** The ICP scoring engine turns firmographic + enrichment signals into trustworthy, auditable A/B/C/D prioritization (with hard vetoes) and never clobbers HubSpot data — proven in dry-run locally.
**Current focus:** Milestone 3 — company enrichment via live provider waterfall, plus the web-research retrieval layer that resolves the two ICP fields providers cannot supply. Phases 11–15.

## Current Position

Phase: 16 of 16 (Scheduled Workflows & Review Surface) — NOT PLANNED YET
Plan: none yet — run `/gsd-plan-phase 16`
Status: Milestone 3 in progress — Phase 15 executed + offline-verified (operator runbook pending); Phase 16 awaiting plan
Last activity: 2026-07-22 — Phase 15 executed: HubSpot property migration tooling (see last_activity_desc above)

Progress: [███████████░] 94% (15/16 phases)

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 4 | 1 | ~10m | ~10m |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase phase-5 P01 | 5m | 4 tasks | 8 files |
| Phase 9 P01 | ~15m | 3 tasks | 6 files |
| Phase 10 P01 | ~35m | 3 tasks | 6 files |
| Phase 12 P01 | ~30m | 4 tasks | 12 files |
| Phase 13 P01 | ~23m | 4 tasks | 8 files |
| Phase 14 P01 | ~55m | 5 tasks | 13 files |
| Phase 15 P01 | ~95m | 9 tasks | 34 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. SPEC-level architectural commitments captured at init:

- Config-driven rubric (`icp_scoring.yaml` v lv-icp-v0.1) with illustrative weights — changeable after JTBD 2 sign-off without code changes (⚠️ pending sign-off).
- MVP canonical writes limited to `lv_icp_*`; firmographics staged, manual fields never touched.
- LLM cascade Haiku → Sonnet 5 → human; non-clobber merge with field-ownership classes.
- [Phase ?]: Phase 9: dedupe_sweep compares NORMALIZED keys (normalize-before-compare); SweepReport findings are plain JSON dicts for Phase-10 transport
- Phase 11: companies is a SIBLING branch, not nested under contacts (ICP fields are per-domain; nesting re-pays per contact). `mergeCompanies.js` kept separate from `mergeContacts.js` for zero regression risk. NO entity-resolution/hierarchy modelling — granularity only corrupts SIZE signals; provider disagreement already detects it. Name-mismatch detection evaluated and REJECTED (blind to the identical-name case). Resolution order is deterministic → retrieval → judgement; a judge without retrieval is least reliable exactly where the ICP lives.
- Phase 10: n8n replica uses a THIN FastAPI wrapper (no JS logic dup); dry_run hard-True + stubbed HubSpot + allow_create off = structurally no live write. `n8n execute --id` (v2.4.4) rejects schedule-only workflows (needs a manual/execute-workflow start node) and needs a non-colliding task-broker port (5699) when run inside the container.
- Phase 12: taxonomy vocabulary is generated-data / hand-written-logic split (spec D2) — `n8n/code/taxonomy.generated.js` carries only vocabulary (regenerated by `scripts/gen_taxonomy_js.py`, called at the top of `build_cloud_workflows.py` before any `inline()`), `n8n/code/taxonomy.js` carries the ~30 lines of normalizer logic and builds its own canonical+synonym lookup at require-time (mirrors `src/taxonomy.py`'s `_build_synonym_map`). `icp_scoring.yaml`/`field_policy.yaml` stay hand-written, drift-guarded by the pre-existing TX-1/2/3 tests rather than generated — codegen is reserved for the one consumer that physically cannot read a file at runtime (n8n Code nodes, spec AR-4).
- Phase 13: tri-state coercion (TS-1/2/3) is keyed ONLY on `evidence_by_field` presence, never a confidence threshold — `lv_produces_content=false` without a per-field evidence URL coerces to `null` before it can fire the hard veto. Research retrieval is a prompted free-text JSON turn (D3), not a forced `tool_use` schema — mixing a client tool with the `web_search` server tool defers the search to a second round trip, incompatible with the single-HTTP-call n8n pattern. Research wiring lands ONLY in `wf_enrichment_local_live.json` (D4) — `build_enrichment_cloud()` has no companies branch yet (Phase 16 scope). `mergeCompanies.js` stays byte-identical; the research candidate folds in as a SECOND `mergeCompanies()` call in the `ENRICH_MERGE_CO` wrapper (D6), shallow-merged with the firmographic result (no key collision). Research-failure skip-not-retry (CLAUDE.md §26.2) proven offline via `researchCandidateFromHttpItem`, which never throws regardless of HTTP-node failure shape.
- Phase 14: the judge chain is wired STRUCTURALLY UPSTREAM of Merge Company (D1) — deliberately diverging from RESEARCH.md's after-Merge placement — so RO-2 (size conflicts never trigger a model call alone) is a topology fact, proven by a graph-ancestry BFS test plus a jsCode-absence check, not a comment. `escalation_policy.yaml` gets the same generated-data/hand-written-logic split as Phase 12's taxonomy (D3): `escalation.generated.js` carries only thresholds/vocabulary, `judge.js` carries all trigger/verdict logic by hand. Only `is_citation_sufficient` (JG-4) gets a Python twin + parity test (D4) — the judge's HTTP glue has no Python counterpart. `mergeCompanies.js` stays byte-identical for the third phase running (D2); the vendor-flag whitelist widening lives in the `ENRICH_MERGE_CO` n8n wrapper. JG-5's hardware-vendor veto is proven offline against the unchanged `src/icp_scoring.py` (Approach C) — no veto computation added to production JS. **Discovered (not fixed):** `icp_scoring.py`'s confidence-downgrade block overrides an already-fired hard-veto `tier` label whenever `lv_produces_content is None`, regardless of `anti_icp_flag` — the veto SIGNAL is independent as JG-5 requires, the `tier` LABEL is not, in that one branch. Out of Phase 14's scope (Do-Not list forbade touching `icp_scoring.py`); flagged for a future decision.
- Phase 15: provenance model (coordinator decision, supersedes RESEARCH's 121-145 flat-suffix design) — per-field enrichment metadata rides in ONE JSON text property per object (`lv_enrichment_provenance`/`lv_contact_enrichment_provenance`), not ~63 flat `lv_<field>_source/_confidence/...` properties; the 4 `_verified_at` cache-key datetimes are the sole carve-out that stays top-level/queryable (RT-5/SJ-2). Staging folds into the same blob (the `value` key per entry) — no `lv_waterfall_*`/`lv_claude_web_*` properties exist; `source_registry.yaml` stays documentation-only. Byte-identical serialization is load-bearing: Python `json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False)` vs JS `stableStringify()` (recursive sorted-key stringify) — proven with a non-ASCII fixture row and two deliberate-breaks, one of which (`ensure_ascii=False` removal) was performed once against the real source file and restored via file copy. ICP write paths retired (Approach C, criterion 4): `src/merge_policy.py`/`main.py`/`field_policy.yaml`/`mergeCompanies.js` no longer write `lv_icp_fit_score`/`lv_icp_tier`; the scoring engine still computes them internally for routing. PN-1 renamed `linkedin_url`/`persona_group` → `lv_linkedin_url`/`lv_persona_group` everywhere they round-trip to a HubSpot property, decoupled from the raw upload/scored-winner READ-side field name (which stays unprefixed — it is not itself a property). Sync/rollback/canary tooling chose per-property individual creates over HubSpot's `batch/create` endpoint (its partial-failure semantics are undocumented; the undo manifest's correctness is safety-critical). **Portal untouched this phase** — every live script's no-credentials skip path is what ran; the live property creation, baseline snapshot, and canary proof are OPERATOR RUNBOOK steps (15-01-SUMMARY.md).

### Pending Todos

- **RESOLVED 2026-07-20 (Phase 12)**: TX-4 red retired. `mergeCompanies.js` now `require()`s `EVIDENCE_GATED_ORG_TYPES` from the generated taxonomy module instead of hand-typing the array; `test_tx4_mergecompanies_has_no_handmaintained_enum` passes.
- **RESOLVED 2026-07-21 (Phase 13)**: The 7 `xfail(strict=True)` acceptance tests in `tests/test_web_research_spec.py` flipped to passing; markers removed. `REQ-web-retrieval`, `REQ-evidence-by-field`, `REQ-tristate-content` all satisfied.

### Blockers/Concerns

- **EXECUTED 2026-07-22 (Phase 15 Task 4): both ICP write-path retirement decisions below are now LIVE IN CODE**, not just decided. `src/merge_policy.py`, `main.py`, `config/field_policy.yaml`, `n8n/code/mergeCompanies.js` no longer write `lv_icp_fit_score`/`lv_icp_tier`; 3 test assertions flipped to assert absence. Engine still computes both internally for routing/audit.
- **RESOLVED 2026-07-20 (user decision): `lv_icp_fit_score` is HubSpot-calculated and MUST NOT be written by this workflow.** Calculation happens in HubSpot programmatically. Supersedes CLAUDE.md §29, which lists it as a permitted canonical write. Write paths to remove: `src/merge_policy.py:303`, `main.py:60`, `config/field_policy.yaml:86` (promote_to_canonical -> false), `n8n/code/mergeCompanies.js:35` (class score_output -> non-promoting), plus inverted assertions in `tests/test_merge_policy.py:196` and `tests/test_main.py:60`. The company SEARCH property list (`build_cloud_workflows.py:1183`) is a READ and stays.
- **RESOLVED 2026-07-20 (user decision): Approach C — HubSpot owns the DERIVED outputs; the pipeline writes only the INPUTS.** `lv_icp_fit_score` and `lv_icp_tier` are placeholders (the formula is literally `1 + 1`, so every company currently scores 2). Authoring the real HubSpot-side calculation is **downstream work, explicitly out of scope for Milestone 3**. This retires the tier/score divergence risk entirely, because the pipeline writes neither.
  - **Pipeline WRITES (inputs):** `lv_org_type`, `lv_produces_content`, `lv_content_type`, `lv_revenue_band`, `lv_employee_band`, `lv_country_region_normalized`, `lv_is_hardware_vendor`, `lv_is_gambling_operator`, `lv_sponsorship_reliant` + their `_source` / `_confidence` / `_evidence_url` / `_verified_at` metadata.
  - **HubSpot DERIVES (downstream, not now):** `lv_icp_fit_score`, `lv_icp_tier`, `lv_anti_icp_flag`, `lv_anti_icp_reason`, `lv_recommended_motion`.
  - `src/icp_scoring.py` still computes score/tier INTERNALLY — it drives in-pipeline routing (`needs_review`, `Unscored`) and the audit breakdown. It is no longer a write path. Keep the engine and its tests; gate the writes.
  - Write paths to retire when the write gate is next touched: `src/merge_policy.py:303`, `main.py:60`, `config/field_policy.yaml:86`, `n8n/code/mergeCompanies.js:35`, plus inverted assertions in `tests/test_merge_policy.py:196` and `tests/test_main.py:60`. Supersedes CLAUDE.md §29. **Deferred — not Phase 12 scope.**
- **SCORING PRECEDENCE RULE — a hard veto's tier label MUST survive a confidence downgrade.** `src/icp_scoring.py:116` overwrites `tier` (and `recommended_motion`) to Needs Review / Unscored whenever `org_type == "unknown" or produces_content is None`, *without* checking whether an independent hard veto already set `tier="D"`. Live-reproduced 2026-07-21 on Supertech Electronics: hardware-vendor veto fires (`anti_icp_flag=True`) but tier reads `"Unscored"`, not `"D"`. The veto SIGNAL is independent; the tier LABEL is not.
  - **One-line fix:** `if (org_type == "unknown" or produces_content is None) and not anti_icp_flag:`
  - **Blast radius: zero** — verified 2026-07-21; no existing test combines a fired veto with `produces_content is None`.
  - **Exposure today:** NOT n8n production (Python never runs there, AR-3; no tier computed in any node body — verified). It DOES reach HubSpot via the Python harness: `src/merge_policy.py:302-313` writes `lv_icp_tier`/`lv_anti_icp_flag` into `canonical_patch` and `main.py:57-71` promotes them when `ALLOW_ICP_SCORE_WRITES` (defaults **true** in `.env.example`) with `DRY_RUN=false`. Phase 15 retires those write paths, closing this exposure.
  - **Why it still matters after Phase 15:** Phase 15 keeps the engine and gates only the writes, so line 116 survives. `icp_scoring.py` is the spec-by-example for the HubSpot-side tier formula, which is still the `1+1` placeholder. Whoever authors that formula inherits this precedence bug unless it is fixed or explicitly encoded: **hard veto label wins over confidence downgrade.**
- **`lv_icp_tier` options are `A,B,C,D` only**, but the scorer also emits `Unscored` and `Needs Review` — writing those fails today. Live bug, predates Milestone 3.
- **`lv_org_type` is `string/text`, not an enumeration** — no CRM-level guard; the normalizer is the only barrier against a hallucinated value.
- **RT-5 tooling built, live creation still pending (Phase 15).** `config/hubspot_properties.yaml` + `scripts/sync_hubspot_properties.py` are built and offline-proven; the 4 cache-key datetimes (`lv_org_type_verified_at`, `lv_produces_content_verified_at`, `lv_jobtitle_verified_at`, `lv_mobilephone_verified_at`) do not yet exist in the live portal — the operator runbook (15-01-SUMMARY.md) is the remaining step. Until it runs, every run still re-researches every company.
- **12 days of untracked work (2026-07-08 → 2026-07-20)** happened outside GSD. Phase 11 reconciles it; not retrofitted as synthetic phases.
- **NEW 2026-07-21 (Phase 14, discovered not fixed): `icp_scoring.py`'s confidence-downgrade block outranks an already-fired hard veto's `tier` label.** `compute_icp_score` sets `tier="D"` when `anti_icp_flag` fires (e.g. `lv_is_hardware_vendor=True`), but a later, unconditional block (`if org_type == "unknown" or produces_content is None: ... tier = "Needs Review"/"Unscored"`) overwrites that tier whenever `lv_produces_content is None` — without checking `anti_icp_flag` first. Confirmed live: Supertech Electronics with `lv_is_hardware_vendor=True` + `lv_produces_content=None` yields `tier="Unscored", anti_icp_flag=True` — the veto SIGNAL fires correctly, the tier LABEL does not reflect it. No existing test combined these two conditions before Phase 14's JG-5 test probed it. Not fixed: Task 1's Do-Not list forbade touching `icp_scoring.py`/`icp_scoring.yaml`/any score number in Phase 14, and the plan's own contingency ("if it passes in only one branch, stop and report") was followed instead of a silent patch. Recommended one-line fix (skip the confidence-downgrade tier override when `anti_icp_flag` is already `True`) checked against all 16 `tests/test_icp_scoring.py` cases + TS-1/TS-4 — none currently combine a fired veto with `produces_content is None`, so blast radius appears zero, but this was NOT verified by applying the fix. Not blocking (pipeline does not write `lv_icp_tier` to HubSpot per Approach C) — needs an explicit decision before any future phase relies on this internal routing signal in that exact combination. See `14-01-SUMMARY.md` Deviations.

- **NEW 2026-07-22 (Phase 15, carried forward, explicitly out of scope): two latent copy-loop bugs.** `lv_sponsorship_reliant` (companies, `build_cloud_workflows.py` ENRICH_MERGE_CO researchData loop) and `persona_group`/`lv_persona_group` (contacts, ENRICH_MERGE winners loop) are declared in policy and now have HubSpot properties created for them (Phase 15 manifest), but the production merge wrapper never actually copies either from its candidate source into the merge call — both properties will stay permanently empty until a future phase's one-line wrapper fix. Not fixed here: it is a `build_cloud_workflows.py` logic change, not a schema migration.
- **NEW 2026-07-22 (Phase 15, explicitly out of scope): `lv_country_region_normalized` has no explicit `field_policy.yaml` entry** — falls to the default `fill_blank_only` policy at merge time. Property created; the policy question is flagged, not resolved.
- **NEW 2026-07-22 (Phase 15, one-way door, explicitly NOT scheduled): `lv_org_type` text→enumeration type change deferred (criterion 3).** HubSpot's own guidance: a field-type change can invalidate existing values with no documented API-level undo beyond restoring a pre-change export. Not performed, not gated as a disabled step — "not performed" is stronger than "gated."
- **REQ-signoff-gate**: point weights are illustrative pending Alex's JTBD 2 sign-off. Does not block Milestone 1 (config-driven), but gates the production weighted rubric.
- **HubSpot on Starter** ($35); Pro tier required before any writeback/n8n milestone.
- **Enrich-first reality**: org type verified for only 66/712 companies; `closed_lost_reason` 0% filled.

## Deferred Items

Items carried forward to later milestones:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Enrichment | REQ-finite-list-motion (named-list motion) | Deferred | 2026-07-07 |
| Scoring | REQ-intent-scoring (pixel intent) | Deferred | 2026-07-07 |
| Hygiene | REQ-closed-lost-capture | Deferred | 2026-07-07 |
| Process | REQ-signoff-gate (JTBD 2 weighted rubric) | Deferred | 2026-07-07 |

## Session Continuity

Last session: 2026-07-22T00:00:00.000Z
Stopped at: Phase 15 (HubSpot Property Migration) executed and committed — 9 tasks, 8 commits (6c65f79, cba5b0e, 6d64da7, 305b10e, e8c9369, f00c7b5, 584302f, f27eb0a), SUMMARY written. Tree clean at commit time (pending this docs commit). Portal 22617666 untouched — the live property creation, baseline snapshot, and canary proof are OPERATOR RUNBOOK steps, not yet run.
Resume file: None
Next command: run the operator runbook in 15-01-SUMMARY.md, then `/gsd-plan-phase 16`
