# lv-n8n-poc

## What This Is

A local-first Python MVP that proves Lightning Visuals' HubSpot → n8n waterfall
enrichment + ICP scoring system before any production wiring. It scores companies
against a governing-body-first ICP rubric using mock ZoomInfo/Apollo/Lusha adapters,
mock Claude web research, a Haiku→Sonnet LLM cascade, and a non-clobber merge policy —
emitting dry-run HubSpot PATCH payloads. It is internal RevOps tooling for LV's sales
team, not a customer-facing product.

## Current State

**Shipped: v0.4 — Reachability & Verification Debt (2026-07-29).** No new capability by design —
the milestone cleared every debt the v0.3 close deferred: BUG 23 (`contact:create` structurally
unreachable) fixed with dual live canary; a numeric provider industry code can no longer win the
waterfall or survive normalization; `lv_sponsorship_reliant` and `lv_persona_group` wired AND given
live producers; the six-item verification ledger discharged **6/6** (surfacing and same-day
resolving BUG 26 deployment drift, and closing the last armed-write residual with a passed
`company:update` canary). Live deployment is current with git, active, and disarmed at rest.

**Previously shipped: v0.3 — Company Enrichment & ICP Research (2026-07-29).**

The description above is the project's origin, not its present shape. Three milestones in, this is
no longer a local-first mock MVP:

- **v0.1** — ICP scoring engine, hard vetoes, tiering, non-clobber merge, dry-run PATCH payloads,
  proven locally against fixtures.
- **v0.2** — contact ingestion, dedupe and enrichment ported into n8n; local Docker n8n replica.
- **v0.3** — companies enrich through a live provider waterfall (Lusha + Apollo + ZoomInfo) with
  native web retrieval for the two ICP fields no provider supplies, and **the pipeline now writes to
  HubSpot**. Three workflows run in n8n Cloud (LV Contact Ingest, LV Enrichment, LV Scheduled
  Maintenance). The non-clobber guarantee is live-proven, not asserted: a provider candidate that
  cleared the confidence threshold was refused on ownership class alone, and an un-allowlisted
  company was refused with `write_blocked`.

**Deployment posture:** all three workflows are active and **disarmed** — write gates off by
default, armed only inside a deliberate, audited window against allowlisted test records.

**Scope fence that still holds:** the pipeline writes ICP *inputs* and their provenance. The
derived outputs (`lv_icp_fit_score`, `lv_icp_tier`, `lv_anti_icp_flag`, `lv_anti_icp_reason`,
`lv_recommended_motion`) are HubSpot-side. A partial HubSpot-side implementation exists (four
workflows + calculated property, built 2026-08-04) but carries ten validated defects — see
`HANDOVER-2026-08-06-icp-scoring.md` §10. Remediating it is milestone v0.7. Supersedes CLAUDE.md §29.

## Current Milestone: v0.7 HubSpot Scoring Engine Remediation

**Goal:** The ICP rubric executes correctly inside HubSpot (the scoring engine stays
HubSpot-resident) — a textbook Tier-A record (governing body + content + ANZ + mid-market)
scores 80 and grades A; the ten validated defects (F1–F10, HANDOVER-2026-08-06-icp-scoring.md
§10) are remediated; vetoes set AND clear with reason strings; and a parity guard asserts
HubSpot's live scores against `src/icp_scoring.py`.

**Target features:**
- Decision phase first: verify company fit-score availability on Sales Hub Pro, then commit to
  fix-the-workflow-chain-in-place vs lead-scoring-tool rebuild (requirements path-neutral until then)
- Scoring engine remediation per chosen path: content term (+20), input rewiring to canonical
  `lv_*` properties, symmetric veto with `lv_anti_icp_reason`, revenue boundary fixes,
  gambling deduction on `lv_is_gambling_operator`, regulator points, missing hard vetoes
- Import the 66 web-researched companies (49 high-confidence) from the ICP validation analysis
  as scoreable validation population — zero provider spend
- Parity/regression harness: `src/icp_scoring.py` as oracle; worked examples + F4/F7/F9/F10
  scratch scenarios as fixtures
- Retire/reconcile orphan scoring artifacts per the path decision

**Key context:** full-712 backfill trigger deferred beyond v0.7. Phase numbering continues at 39
(global sequence). The `milestone` workstream's v0.5 Phase 22 armed canary remains pending and is
a dependency, not part of this milestone. HubSpot portal 22617666 (ap1); `automation` scope now
granted to the private app.

## Parallel Milestone (in-flight workstream): v0.5 Lusha v3 & Armed Enrichment

**Goal:** Migrate Lusha to v3 before the 2026-11-18 sunset with selective-reveal cost control, and prove the full enrichment pipeline (providers + Haiku research + Sonnet judge) live with writes armed.

**Target features:**
- Lusha v2→v3 migration: live contract probe → POST `/v3/*/search-and-enrich` ×2 lanes → `reveal[]` driven by gate `missingFields` (field policy becomes the cost control) → `lusha_contact_id`/`lusha_company_id` staging properties (free re-enrichment via `canReveal.credits=0`) → parser/tests/fixtures → disarmed redeploy
- Armed full-enrichment canary: providers + Haiku research + Sonnet judge end-to-end on allowlisted records, writes armed deliberately
- Dedupe Search transport swap: retire the last native-node search (BUG-23 family)
- Schema hygiene: `lv_org_type` text→enumeration one-way door + `lv_country_region_normalized` field-policy entry

**Key context:** Lusha balance ~3.9k credits vs ~12.6k measured v2 full-sweep cost (~4.65 credits/reveal, phone bundling) — v3 selective reveal is a cost fix, not just deadline compliance. Research lane live on `claude-haiku-4-5` since 2026-07-30 (judge `claude-sonnet-5` armed, cap 50). Deferred to **v0.7** (not v0.6, which is the operator client): HubSpot-side ICP formula (the `1 + 1` placeholder) + JTBD 2 weighted-rubric sign-off (REQ-signoff-gate) — downstream-owner decisions needing a business owner, not client work.

## Parallel Milestone: v0.6 Claude Plugin Entrypoint

Runs concurrently with v0.5 in its own workstream (`.planning/workstreams/plugin-entrypoint/`,
branch `worktree-claude-plugin-entrypoint`). v0.5 owns the backend; v0.6 owns the surface over it.

**Goal:** Make Claude the operator's only interface to the n8n backend — both the ingestion front
door and the control plane. The operator is non-technical, works in Claude Desktop, and never opens
n8n, so anything n8n would surface in its own UI (failed runs, dead credentials, exhausted quotas,
stuck locks, review queues) has to arrive in the conversation instead. An instruction to run a
command is a requirement failure, not a fallback.

**Target features:**
- Ingestion front door (phases 23–26): spreadsheet → preview → approve → dispatch; then prose,
  foreign JSON, public URLs and web-page screenshots with per-row provenance; enrichment lane on
  existing records with a credit/token cost guard; per-record outcome reporting and safe retry
- Control plane (phases 27–30): n8n-side health endpoint + plain-language status (text or dashboard
  artifact); run/stop/reschedule and conversation-scoped live-write permission via allowlisted
  mutations, confirmed then read-back verified; in-session run watch plus a read-only unattended
  sweep; conversational review-queue triage with gated writeback stamped as a human decision

**Key context:** 49 requirements, 8 phases, coverage 49/49. Client code is confined to
`operator-claude-plugin/` and is documented as a *suggested default thin client* — n8n is a
standalone backend over plain HTTP, so other front ends can be built against the same contract.
Two constraints absorbed rather than designed around: arming is a workflow write (`ALLOW_*` gates
are compiled into Code nodes by `ENABLE_BAKED_FLAGS`, cadence lives in Schedule Trigger params), and
the client holds no provider credentials, so credit figures must return through a new n8n-side
status endpoint. Unverified: whether scheduled/unattended agents exist in the operator's Claude
Desktop environment (NOTICE-03 depends on it).

## Shipped Milestone: v0.4 Reachability & Verification Debt (archived)

**Goal:** Make every structurally dead or silently inert path in the deployed pipeline reachable
and proven live, and clear the verification backlog carried out of v0.3.

**Progress:** ALL THREE PHASES COMPLETE 2026-07-29 — milestone execution done. Phase 17 (BUG 23 —
contact:create reachable, live-canaried), Phase 18 (numeric industry code neutralized; both
copy-loop fields wired AND given live producers, verified 5/5), Phase 19 (six-item verification
ledger discharged: 3 passed, 3 honest human_needed — `19-LEDGER.md`, verified 6/6). Phase 19
surfaced **BUG 26**: the live n8n Cloud `LV Enrichment` deployment predated Phase 18's rebuild —
**RESOLVED same day** by the operator's runbook Step-0 disarmed redeploy (read-back confirmed
Phase-18 markers live; brief in `.planning/debug/resolved/`). The operator then executed the full
16.9 armed `company:update` canary (execution 108: write proven on allowlisted `9604614548`,
neighbor unchanged, disarm read back). **Ledger 6/6 passed — v0.4 fully discharged, live
deployment current with git and disarmed.**

**Target features:**
- **BUG 23 fix** — enrichment `contact:create` reachable: transport swap on `HubSpot Search` +
  `HubSpot Fetch By Id` to the credential-bound httpRequest envelope (the mechanism proven by
  BUG 10 and BUG 22), byte-identical-pin override with documented rationale, live canary of BOTH
  cases (contact 201 must still match and enrich; a nonexistent email must reach `Decide Action`
  as `create`, write-gated), and the harness gap closed (`bareEventChainFlow` mocks model the
  native node's 0-item behavior, or the lane asserts no native search nodes remain).
- **ZoomInfo numeric industry** — normalization gap: a numeric industry code (`"71"`) must not win
  the waterfall over provider text and pass through normalization unchanged.
- **Copy-loop gaps** — `lv_sponsorship_reliant` (companies, ENRICH_MERGE_CO researchData loop) and
  `persona_group`/`lv_persona_group` (contacts, ENRICH_MERGE winners loop) wired from candidate
  source into the merge call; both properties are currently permanently empty.
- **Verification debt** — six `/gsd-verify-work` re-runs carried from the v0.3 goal ledger.

**Key context:** the BUG 23 fix churns `HubSpot Search` — the single most live-proven node in the
system (the whole 16.7 non-clobber canary chain runs through it), pinned byte-identical by design
in `tests/test_bug10_company_search_transport.py`. The plan must carry before/after live-canary
discipline, not a drive-by migration. Phase numbering continues from 16.10 (next: phase 17).

## Core Value

The ICP scoring engine turns firmographic + enrichment signals into trustworthy,
auditable A/B/C/D prioritization (with hard vetoes) and never clobbers HubSpot data —
proven entirely in dry-run locally, before touching a single production record.

## Business Context

- **Customer**: Lightning Visuals RevOps / sales team (sports-media / broadcast graphics vendor).
- **Revenue model**: Internal GTM tooling — prioritizes a finite best-fit TAM (~100–150 ANZ orgs) rather than high-volume prospecting.
- **Success metric**: Plausible tier distribution, zero false clobbering, and a config-driven rubric ready for JTBD 2 sign-off.
- **Strategy notes**: Governing-body-first targeting derived from 92 closed HubSpot deals (see icp-scoring.md); primary competitor LIGR.live already runs the "buy-once-deploy-league-wide" play.

## Requirements

Full detail and traceability live in `.planning/REQUIREMENTS.md`.

### Validated

(None yet — ship Milestone 1 to validate.)

### Active (Milestone v0.4 — Reachability & Verification Debt)

- [ ] Enrichment `contact:create` reachable — transport swap + pin override + dual live canary + harness gap (BUG 23)
- [ ] Numeric provider industry codes never survive normalization or win the waterfall over text (ZoomInfo `"71"`)
- [ ] `lv_sponsorship_reliant` + `persona_group` copy-loops wired; properties stop being permanently empty
- [ ] Six `/gsd-verify-work` re-runs from the v0.3 goal ledger closed

### Shipped (Milestone 3 — Company Enrichment & ICP Research, 2026-07-29)

- [x] Company enrichment as a sibling n8n branch, live provider waterfall (REQ-company-branch, REQ-company-merge, REQ-provider-contracts, REQ-conflict-withhold)
- [x] Taxonomy single-source so org/content types extend without drift (REQ-taxonomy-single-source, REQ-enum-normalization)
- [x] Web-research retrieval for the two provider-unresolvable ICP fields (REQ-web-retrieval, REQ-evidence-by-field, REQ-tristate-content)
- [x] Evidence-before-judgement escalation (REQ-evidence-before-judgement)
- [x] HubSpot metadata property migration tooling, checkpointed (REQ-property-migration; live runbook pending)
- [x] Inputs-only writeback + tiered adjudication (REQ-inputs-only-writeback, REQ-tiered-adjudication)

### Shipped (Milestone 1 — Local-First MVP)

- [ ] Config-driven ICP scoring: score, tier (A/B/C/D), anti-ICP vetoes, graduated deductions (REQ-icp-scoring-model, REQ-anti-icp-vetoes, REQ-graduated-deductions, REQ-tiering)
- [ ] Governing-body-first targeting encoded in the rubric and demonstrated by tests (REQ-org-type-targeting)
- [ ] Mock enrichment pipeline: provider waterfall + Claude research + Haiku classifier + Sonnet stub (REQ-enrichment-plan)
- [ ] HubSpot ICP property contract exercised through non-clobber merge (REQ-hubspot-icp-properties)
- [ ] MVP foundation, non-clobber merge, source attribution, and dry-run PATCH output (MVP-01…MVP-04)

### Out of Scope (deferred to future milestones)

- **n8n Cloud workflows** (webhook receiver, schedules, subworkflows) — Milestone 1 is local Python only; production orchestration is a later milestone.
- **Live provider APIs** (real ZoomInfo/Apollo/Lusha) — mock adapters only in Milestone 1; live integration is CLAUDE.md Phase 3.
- **HubSpot writeback / property creation / private app** — dry-run PATCH only; test-record writeback is CLAUDE.md Phase 1 (next milestone).
- **Canonical firmographic promotion** — MVP stages firmographics; only `lv_icp_*` outputs are written canonically (SPEC §29 scope cut).
- **Pixel intent scoring** (REQ-intent-scoring) — defined in the PRD but absent from the SPEC's `icp_scoring.yaml`; HubSpot-pixel dependent, deferred.
- **Closed-lost capture** (REQ-closed-lost-capture) — HubSpot-property dependent, deferred to a writeback milestone.
- **Finite-list named-account motion** (REQ-finite-list-motion) — requires real CRM + live enrichment, deferred.

## Context

- **Two source docs, complementary not competing.** `CLAUDE.md` (SPEC) is the authoritative implementation contract; `icp-scoring.md` (PRD) is the validated business rationale. Scoring numbers agree field-by-field across both (INGEST-CONFLICTS.md, 0 blockers / 0 warnings / 3 INFO).
- **Finite best-fit TAM** (~100–150 ANZ orgs; racing core ~25–28) motivates enrich-and-score over programmatic prospecting.
- **Data-quality caveats:** findings measure engaged-deal conversion, not the whole market; small cells (n ≥ 3) are hypotheses, not certainties; pre-HubSpot wins are undercounted; HubSpot native industry tags are unreliable (e.g. Australian Turf Club tagged "Gambling/Casinos") — lead with enriched signals.
- **Competition:** LIGR.live (AU cloud pay-per-use, holds Football Australia gatekeeper deal) is the #1 threat; LV sits between Vizrt (premium) and LIGR (budget). Differentiate on automation/data/price/outbound, not "cloud."

## Constraints

- **Tech stack (Milestone 1)**: Python 3, local-only. anthropic, requests, pydantic, PyYAML, phonenumbers, email-validator, pytest.
- **Platform**: Sales Hub Professional-compatible — no HubSpot workflow "Send webhook", custom-code actions, Data Hub formatting, or native waterfall enrichment. All orchestration lives outside HubSpot.
- **Orchestration (production)**: n8n Cloud (paid, hosted — not self-hosted). Out of scope for Milestone 1.
- **LLM cascade**: deterministic rules → Haiku → Sonnet 5 → human review. Sonnet only on conflict / hard-veto-possible / anti-ICP-flip / canonical-overwrite / low-confidence.
- **Non-clobber merge**: field-ownership governance (manual_protected, system_owned, fill_blank_only, stale_refreshable, review_required, append_only, score_output, veto_output). Manual values authoritative unless blank/stale/system-owned/low-confidence.
- **Source attribution**: every enriched field carries source / confidence / evidence URL+summary / verified_at / verified_by_model / validation_status.
- **Safety**: kill-switch env flags + per-run caps; dry-run prints exact PATCH; MVP canonical writes limited to `lv_icp_*` outputs.
- **Provider adapter contract**: every adapter emits the normalized `{provider, object_type, matched, confidence, data, evidence, cost, model_trace}` schema.

## Key Decisions

<!-- SPEC-level architectural commitments recorded as project decisions (no ADRs in ingest set). -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| HubSpot Sales Hub Pro as CRM + control plane (custom properties, not native automation) | Avoid Data Hub / programmable-automation dependency; keep logic portable | — Pending |
| n8n Cloud as production orchestration layer | Hosted, avoids self-hosting ops; owns webhook/schedule/waterfall/retry | — Pending |
| LLM cascade Haiku → Sonnet 5 → human | Cheap classification by default; escalate only high-risk/conflict decisions to control cost | — Pending |
| Non-clobber merge with field-ownership classes | Protect manually-maintained CRM data; stage before promoting | — Pending |
| Per-field source/evidence attribution | Auditable enrichment; supports human review and rollback | — Pending |
| Safety gates + MVP canonical writes limited to `lv_icp_*` | Prove scoring with zero clobbering risk before enabling firmographic promotion | — Pending |
| Config-driven rubric with illustrative weights (`icp_scoring.yaml` v lv-icp-v0.1) | Weights change after JTBD 2 sign-off without code changes | ⚠️ Revisit (pending sign-off) |
| **(M2)** File upload is a merge *source*, not a new engine — reuse Milestone 1 non-clobber merge | The field-level "don't clobber" is already solved; a CSV row is just another candidate source | — Pending |
| **(M2)** Identity match: auto only on email/LinkedIn; no-email never auto-creates; ambiguous → review | Matching is the real risk; conservative default prevents duplicate-contact explosion in HubSpot | — Pending |
| **(M2)** Net-new + valid email → auto-create, gated (`ALLOW_CONTACT_CREATE`, dry-run first, re-check-by-email guard) | User-chosen; safe because create is flag-gated, dry-run-default, and dedupe-guarded | — Pending |
| **(M2)** Weekly n8n scheduler sweep flags duplicate/mangled contacts as needs_review | Catches dupes and bad data that slipped past ingestion; matches CLAUDE.md §13.4 Workflow D | — Pending |
| **(M3)** Companies is a SIBLING branch, not nested under contacts | ICP fields are per-domain and expensive; nesting re-pays for every contact at the same company, and the two gates have different REQUIRED sets, TTLs and triggers | ✅ Shipped 2026-07-20 |
| **(M3)** No entity-resolution / corporate-hierarchy modelling | Wrong granularity only corrupts SIZE signals — org_type, produces_content, hardware/gambling and geography are brand-level and inherit down. Cross-provider size disagreement already detects it, free | ✅ Shipped 2026-07-20 |
| **(M3)** Name-mismatch detection rejected | Blind to the identical-name case that actually costs (ZoomInfo returns "Harvey Norman" for a store); its only true positive is already caught by the conflict detector | ✅ Evaluated + rejected |
| **(M3)** Resolution order: deterministic → retrieval → judgement | An LLM judging from parametric recall is least reliable exactly where the ICP lives — it knows Harvey Norman and FanDuel (already vetoed) and confabulates on obscure ANZ clubs (where it matters) | — Pending |
| **(M3)** `lv_produces_content` tri-state; `false` only on positive evidence of absence | `false` fires a hard veto and permanently disqualifies. A failed search is not evidence of absence, and thin-web-presence ANZ clubs are the ICP core. No blanket human gate — the queue self-targets by score | — Pending |
| **(M3)** Approach C — HubSpot owns the derived ICP outputs; the pipeline writes only the inputs | Score and tier are computed in HubSpot programmatically. Both properties are placeholders today (`calculationFormula` is `1 + 1`). Keeping the pipeline to inputs-only means score, tier, veto flag and motion have exactly one definition and cannot contradict each other on a record. Supersedes CLAUDE.md §29 | ✅ Decided 2026-07-20 |
| **(M3)** Authoring the HubSpot-side calculation is downstream, out of Milestone 3 scope | The rubric must be re-expressed in HubSpot calculation syntax against the `lv_*` inputs. Sequencing it after the inputs are trustworthy avoids encoding a formula against fields the pipeline cannot yet populate | — Deferred |
| **(M3)** All custom properties this workflow creates are prefixed `lv_` | Ownership signalling — marks the property as created by LV's team, and separates ours from HubSpot-native fields and third-party integration properties already in the portal. Native properties are never renamed. Zero migration cost: the 5 existing custom properties already comply and the ~40 others do not exist yet | ✅ Decided 2026-07-20 |
| **(M3)** `config/taxonomy.yaml` as single source; node literals generated at build time | n8n Code nodes cannot read files, so values must be literals — but generated ones. Hand-editing a node yields a silent 0-score and a HubSpot 400 | — Pending |

## Risks & Open Items

- **Point weights are illustrative pending JTBD 2 sign-off** (REQ-signoff-gate). Alex must approve best-fit (governing-bodies-first) and anti-ICP (clubs-direct / non-AU / no-content) before the weighted production rubric is built. The MVP is deliberately config-driven so this can happen without code changes.
- **Pixel intent scoring** (REQ-intent-scoring) is in the PRD but not in the SPEC's `icp_scoring.yaml` — carry as an open item for the JTBD 2 rubric build, not a Milestone-1 deliverable.
- **HubSpot is on Starter ($35) today; Pro tier is required** for production scoring/workflows. Blocks the writeback and n8n milestones, not Milestone 1.
- **(M3) `lv_icp_fit_score` is a HubSpot calculated property** (`readOnlyValue: true`) — the pipeline cannot write it, contradicting CLAUDE.md §29. Product decision needed: is the HubSpot formula the source of truth, or does the property convert (destroying the formula)?
- **(M3) `lv_icp_tier` accepts only `A,B,C,D`** but the scorer also emits `Unscored` / `Needs Review` — those writes fail today.
- **(M3) Research caching is blocked** until metadata properties exist; every run currently re-researches every company.
- **Enrich-first reality**: org type verified for only 66 of 712 CRM companies; `closed_lost_reason` is 0% filled. Anti-ICP is currently inferred from firmographics; discovery calls now supply real reasons (price #1, cloud-fear #2).

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-29 after v0.4 milestone (Reachability & Verification Debt shipped and archived; ledger 6/6, zero operator debt)*
