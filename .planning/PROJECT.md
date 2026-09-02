# lv-n8n-poc

## What This Is

A local-first Python MVP that proves Lightning Visuals' HubSpot → n8n waterfall
enrichment + ICP scoring system before any production wiring. It scores companies
against a governing-body-first ICP rubric using mock ZoomInfo/Apollo/Lusha adapters,
mock Claude web research, a Haiku→Sonnet LLM cascade, and a non-clobber merge policy —
emitting dry-run HubSpot PATCH payloads. It is internal RevOps tooling for LV's sales
team, not a customer-facing product.

## Current State (as of 2026-09-02)

**In flight: v1.1 — Unattended Session Runs (phases 53–63).** Complete: 53, 54, 57, 58, 59, 61.
Absorbed into 61 by operator decision D-61-08: 55 (async run) and 56 (unattended pair pipeline).
Phase 57 ("Ceilings, refusal-before-start, and post-run proof") completed 2026-09-01. **Phase
62** ("Suggest the contacts nobody named") has executed — 6 plans, verification `human_needed`
at 13/13 must-haves, UAT partial (3 items blocked on a live attended sitting with real
`web_fetch` and real Lusha credit spend); closes SUGGEST-01/-02/-04/-05 and amends SUGGEST-03
per D-62-11's cost-envelope decision and the 62-06 cap-enforcement gap closure. **Phase 63** ("The
unattended lane actually runs unattended") was numbered 2026-09-02 and is not yet planned. Open:
**Phase 60** (review-lane authority) and Phase 63. Phase 61 closed 2026-08-30 with 6/6 plans and
12/12 verification; all five cloud workflows are deployed and bounced but were exercised by
**disarmed** runs only. **The first live unattended, credit-spending batch has NOT run** — Phase
57 shipped, so naming it as the pending gate is stale; the fact that no such batch has run yet
still stands.
Detail: `.planning/ROADMAP.md`, `.planning/milestones/v1.1-ROADMAP.md`.

**v1.0 Direct Backfill & Scoring Coverage is paused:** Phase 51 complete, **Phase 52 deferred
INDEFINITELY by the operator (2026-08-25)** — not merely in favour of v1.1. The v1.0 requirements
are the root `.planning/REQUIREMENTS.md`; v1.1's live in `.planning/milestones/v1.1-REQUIREMENTS.md`.

### Prior state (as of 2026-08-19), retained

**Shipped: v0.9 — ICP Rubric Calibration & Veto Remediation.** 6 phases, 35 plans, 18
requirements, all verified `passed`. Archived at `.planning/milestones/v0.9-ROADMAP.md`.

The ICP tier is no longer written by a workflow. `lv_icp_tier_derived` is a HubSpot calculated
property computed server-side from `lv_icp_fit_score` and `lv_anti_icp_flag_num`, both written
by the n8n pipeline as plain numerics. There is no property-change event anywhere in the path,
which is what retired the stale-tier bug class rather than its instances. The old `lv_icp_tier`
enum is archived and the workflow that wrote it (`4625147345`) is deleted.

Load-bearing constraint discovered this milestone, worth carrying forward: HubSpot's
`calculation_equation` reads **only numeric properties** — booleans evaluate as null even when
set, enumerations are rejected at create. Anything a formula needs must be written as a number
first. And calculated values backfill ~70–130s after their inputs change, so a read issued
immediately after a write returns null for a property that will compute correctly.

**Next milestone — v1.0 Direct Backfill & Scoring Coverage.** Backfill the ~646 never-scored
companies with ZoomInfo firmographics plus targeted research, in-session, writing the scoring
inputs and the six numeric properties HubSpot's calculation engine reads. No n8n executions — the
operator has no credits for it, and none are needed: HubSpot already derives score and tier from
those six numbers on its own. Decisions in `.planning/MILESTONE-CONTEXT.md`.


## Shipped Milestone: v0.9 ICP Rubric Calibration & Veto Remediation (2026-08-19)

*(Was headed "Current Milestone" — corrected 2026-08-30; v0.9 shipped, the current milestone is
v1.1. The goal/feature text below is the v0.9 record as written at the time.)*

**Goal:** The ICP rubric reflects who Lightning Visuals actually wins, and every scored company
carries a score derived from that rubric rather than from a stale or false one.

**Target features:**
- **Rubric recalibration** — resolve whether `individual_club_team: 5` inverts GTM priority.
  Racing clubs cap at tier C (35–45) while governing bodies reach tier A (80) on org_type alone.
  If clubs are the core market the weighting is backwards. This is the question that triggered
  the blank-region investigation and is still unanswered.
- **Veto remediation** — clear the 17 false non-ANZ vetoes. The code fix is deployed, bounced and
  live-proven; the records need a deliberate armed write window, because SJ-3 correctly declined
  to dispatch through a closed gate and self-drained their flags.
- **Enrichment coverage** — 18 of 66 scored companies have no `lv_org_type` at all. The rubric
  cannot outperform its inputs, so coverage is a scoring-quality ceiling, not a separate concern.
- **Weight validation against outcomes** — the revenue-band deductions (−5 at 500–750M, −50 at
  1.2B+) and the gambling −20 were set by judgement and have never been checked against won/lost
  deals.
- **Loss-reason capture** — start filling `lv_closed_lost_reason` (exists on Deals, 0% filled
  across 59 examined closed-lost deals). This is the evidence that makes future recalibration
  empirical rather than intuitive.
- **Re-score strategy** — with no `lv_icp_scoring_version`, any rubric change implies re-scoring
  the whole population. Plan that against the 2,500/month execution budget deliberately.

**Key context:**
- The pipeline is **disarmed at rest** — `ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`
  and `ALLOW_HUBSPOT_REVIEW_WRITES` are baked `"false"` in the deployed workflow. No re-score of
  any kind lands until a window is opened deliberately. Every write item in this milestone
  inherits that gate.
- **No new HubSpot properties** (operator decision 2026-08-11). Loss-reason capture fits inside
  this because `lv_closed_lost_reason` already exists; the supporting fields it was spec'd
  alongside (`lv_qualitative_fit_summary`, `lv_budget_timeline_signal`, `lv_loss_reason_detail`)
  do NOT exist and are deferred to v1.0 rather than created.
- Current distribution across the 66 scored: A:7 B:18 C:17 D:24 — 17 of the D are the false
  vetoes, so a correct post-remediation shape is roughly A:7 B:18 C:17+ D:7.
- Rubric weights are still `lv-icp-v0.1` and were always flagged as illustrative pending JTBD 2
  sign-off (REQ-signoff-gate). This milestone is where that sign-off either happens or is
  explicitly deferred again.
- SJ-3 runs daily and fans out per record against a 2,500/month allowance — a full-population
  re-score is a budget event, not a free operation.

## Shipped Milestone: v0.8 Execution Budget Safety (2026-08-11)

**Goal:** The backend cannot spend its monthly n8n execution allowance on work it is
structurally unable to complete, and it reports an unsustainable burn rate before a human
notices it.

**Target features:**
- **SJ-3 gate check** — the daily poller (`daysInterval: 1`, verified live 2026-08-10) refuses to dispatch when the HubSpot write
  gate is closed, rather than fanning out one sub-execution per record that can never complete
  or clear its own trigger flag
- **Self-healing flag clear** — `lv_enrichment_requested` cannot remain `true` indefinitely
  after a dispatch that could not finish, so the re-dispatch loop cannot re-form even if the
  gate check is bypassed
- **Per-tick dispatch cap** — a bound on how many records one tick may fan out, so no single
  tick can consume a large share of the monthly allowance whatever the cause
- **Burn-rate alarm** — a sweep condition that samples the recent execution rate and fires when
  it would exhaust the plan

**Key context:** the plan allowance (2,500/month) is a hard constraint, not a preference —
three sub-daily triggers alone exceeded it 2.6x while doing no work. n8n prunes executions at
2,500 rows (~10 hours of history here) and exposes no usage/quota endpoint to an API key
(`/api/v1/usage|license|quota` all 404; `/rest/*` needs a browser session), so the alarm must
sample a RATE — monthly totals are unavailable by construction. Write gates read `false` at
rest by design, so "gate closed" is the normal state and the gate check must not be written as
an error path. The sweep cron is not installed on this machine (`crontab -l` empty), so the
alarm ships inert until an admin schedules it — that limit is explicit, not a gap to paper over.

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

> **Section hygiene note (2026-08-11, v0.8 close).** This section had drifted: the "Active"
> heading still carried v0.4 items that MILESTONES.md records as shipped 2026-07-29, and the
> "Shipped (Milestone 1)" block below still has unchecked boxes. The v0.4 rows are corrected
> below against the ledger. The Milestone 1 / Milestone 3 blocks are left as-found — their
> checkbox state predates the current ledger and re-deriving it was out of scope at this close.

### Validated

- ✓ **Execution budget safety** — v0.8. SJ-3 cannot dispatch work it cannot finish (gate), a stuck
  `lv_enrichment_requested` flag drains instead of re-accumulating, one tick's fan-out is capped
  at a build-time value derived from the plan allowance and baked cadence, and the sweep reports
  an unsustainable burn rate before a human reads the billing page. Live-proven (execution 11820).
- ✓ **Scoring engine correct on the live path** — v0.7. All ten defects (F1–F10) closed in place on
  the HubSpot-resident path, guarded by a two-tier parity harness.
- ✓ Enrichment `contact:create` reachable — v0.4 (BUG 23: transport swap + pin override + dual live canary)
- ✓ Numeric provider industry codes never survive normalization or win the waterfall over text — v0.4 (ZoomInfo `"71"`)
- ✓ `lv_sponsorship_reliant` + `persona_group` copy-loops wired — v0.4 (both now have real producers)
- ✓ Six `/gsd-verify-work` re-runs from the v0.3 goal ledger closed — v0.4 (6/6 passed, zero residual operator debt)

### Active (v0.9 — not yet scoped)

> **Stale block, flagged 2026-08-30 rather than rewritten** (same treatment as the 2026-08-11
> hygiene note above). This lists v0.9 candidate scope; v0.9 shipped 2026-08-19 and the current
> milestone is v1.1, whose requirements live in `.planning/milestones/v1.1-REQUIREMENTS.md`.
> Re-deriving these checkboxes against the v0.9 archive was out of scope for this pass.

Requirements are defined by `/gsd-new-milestone`. The candidate scope carried out of v0.8 and the
2026-08-11 debug work:

- [ ] ICP rubric recalibrated against real-world fit — the `individual_club_team=5` weighting caps
      racing clubs at C/35–45 while governing bodies reach A/80 on org_type alone
- [ ] The 17 false non-ANZ vetoes cleared (needs a deliberate armed write window; the code fix is
      already deployed and live-proven)
- [ ] Enrichment coverage raised — 18 of 66 scored companies have no `lv_org_type` at all, so the
      rubric cannot outperform its inputs
- [ ] Revenue-band deductions and the gambling deduction validated against actual won/lost outcomes
- [ ] A feedback loop that lets the rubric be revised on evidence rather than intuition
      (`lv_closed_lost_reason` and siblings are spec'd in CLAUDE.md §5.3, never built)

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
| **(v0.8)** The per-tick dispatch cap is COMPUTED at build time from the plan allowance and the baked trigger cadence, never a literal | A hardcoded cap silently becomes wrong the moment a trigger is re-timed — which is exactly how the 2026-08-09 runaway happened. Deriving it from the same tuple that builds the trigger makes the two impossible to disagree | ✅ Shipped 2026-08-10 |
| **(v0.8)** "Gate closed" is a named non-error outcome, not a failure path | Write gates read `false` at rest by design, so disarmed is the normal resting state. Reporting it as an error trains the operator to ignore the channel that also carries real failures | ✅ Shipped 2026-08-10 |
| **(v0.8)** The burn-rate alarm samples a RATE, never a monthly total | n8n prunes executions at 2,500 rows (~10h of history here) and exposes no usage/quota endpoint to an API key (`/api/v1/usage\|license\|quota` all 404). A monthly total is unavailable by construction | ✅ Shipped 2026-08-10 |
| **(v0.8)** `ALLOW_SJ3_DRAIN_WRITES` defaults `true` — the first write authority enabled at rest | A drain that needs arming cannot drain a queue that only accumulates while disarmed. Bounded by a key+value patch allowlist to the single flag, and excluded from the overlay/arm system per the `ALLOW_JUDGE_ESCALATION` precedent | ✅ Shipped 2026-08-10 |
| **(2026-08-11)** No `lv_icp_scoring_version` property — the no-new-properties constraint holds | Operator decision at the v0.8 close. Consequence accepted: HubSpot cannot filter on JSON inside a text property, so identifying records scored under a superseded rubric requires re-scoring the population rather than segmenting a list | ⚠️ Revisit if rubric churn becomes frequent |
| **(2026-08-11)** Two property-naming lanes coexist deliberately: live/n8n uses `lv_`-prefixed, the local Python oracle uses bare | The bare names are pinned by the oracle's fixtures and its JS-parity relationship; renaming them breaks the oracle. Translation happens at the live-write boundary instead (`src/live_patch.py`) | ✅ Decided 2026-08-11 |

## Risks & Open Items

- **Point weights are illustrative pending JTBD 2 sign-off** (REQ-signoff-gate). Alex must approve best-fit (governing-bodies-first) and anti-ICP (clubs-direct / non-AU / no-content) before the weighted production rubric is built. The MVP is deliberately config-driven so this can happen without code changes.
- **Pixel intent scoring** (REQ-intent-scoring) is in the PRD but not in the SPEC's `icp_scoring.yaml` — carry as an open item for the JTBD 2 rubric build, not a Milestone-1 deliverable.
- **HubSpot is on Starter ($35) today; Pro tier is required** for production scoring/workflows. Blocks the writeback and n8n milestones, not Milestone 1.
- **(M3) `lv_icp_fit_score` is a HubSpot calculated property** (`readOnlyValue: true`) — the pipeline cannot write it, contradicting CLAUDE.md §29. Product decision needed: is the HubSpot formula the source of truth, or does the property convert (destroying the formula)?
- **(M3) `lv_icp_tier` accepts only `A,B,C,D`** but the scorer also emits `Unscored` / `Needs Review` — those writes fail today.
- **(M3) Research caching is blocked** until metadata properties exist; every run currently re-researches every company.
- **Enrich-first reality**: org type verified for only 66 of 712 CRM companies; `closed_lost_reason` is 0% filled. Anti-ICP is currently inferred from firmographics; discovery calls now supply real reasons (price #1, cloud-fear #2).
- **(2026-08-11) 17 companies carry false non-ANZ vetoes.** The code fix is deployed, bounced and
  live-proven, but the records did not re-score: SJ-3 found the write gate closed, marked them
  `lv_enrichment_status=skipped` and self-cleared their `lv_enrichment_requested` flags. Clearing
  them requires a deliberate armed write window — the drain behaved exactly as designed, which is
  why nothing happened.
- **(2026-08-11) The pipeline is disarmed at rest.** `ALLOW_HUBSPOT_RECORD_WRITES`,
  `ALLOW_HUBSPOT_CREATE` and `ALLOW_HUBSPOT_REVIEW_WRITES` are all baked `"false"` in the deployed
  workflow. No re-score of any kind can land until that window is opened deliberately.
- **(2026-08-11) The rubric has never been validated against outcomes.** Revenue-band deductions
  (−5 at 500–750M, −50 at 1.2B+) and the gambling −20 were set by judgement, not by won/lost
  evidence, and `lv_closed_lost_reason` (CLAUDE.md §5.3, the field that would supply that
  evidence) was never built. The rubric can currently only be revised on intuition.
- **(2026-08-11) `individual_club_team=5` may invert GTM priority.** It caps racing clubs at
  tier C (35–45) while governing bodies score 40 on org_type alone and reach tier A (80). If clubs
  are the core market, the weighting is backwards — this is a business-calibration decision, not a
  defect, and is the open question that triggered the blank-region investigation.
- **(2026-08-11) Ledger gaps.** v0.5 has no MILESTONES.md entry and no `milestones/v0.5-*` archive
  despite a `v0.5.0` git tag; v0.6 has a narrative entry but no archive. Both appear to have
  shipped without running `/gsd-complete-milestone`. Recorded in ROADMAP.md, not reconstructed.

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
*Last updated: 2026-09-02 — current-state refresh: Phase 57 complete (2026-09-01), Phase 62
executed but not complete (verification `human_needed`, UAT partial), Phase 63 numbered and
unplanned; v1.1 still in flight, first live unattended credit-spending batch still has not run.
Previously updated 2026-08-30 after Phase 61 closed. Before that, 2026-08-11 after the v0.8
milestone close (verified_closeout, 2 phases / 6 plans / 15 requirements).*
