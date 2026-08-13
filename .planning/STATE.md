---
gsd_state_version: 1.0
milestone: v0.9
milestone_name: ICP Rubric Calibration & Veto Remediation
current_phase: 50
current_phase_name: Derived Tier Property
status: executing
stopped_at: Completed 50-03-PLAN.md (D-07 gate FAIL, D-19 census DEFECT)
last_updated: "2026-08-13T22:07:32.061Z"
last_activity: 2026-08-13
last_activity_desc: Phase 50 execution started
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 34
  completed_plans: 31
  percent: 83
---

# Project State

## ✅ PHASE 48 — ALL 7 PLANS COMPLETE, NOTHING ARMED (2026-08-13)

**Verification passed 5/5 must-haves.** The one declared armed window is spent and closed;
independent post-hoc live read confirms `TEST_RECORD_IDS = ""`, 111 nodes, `active: True`.

**Coverage outcome — all 5 blank-`lv_org_type` records resolved** (population re-derived live
2026-08-12 and again at execution; the ROADMAP's "18" was stale — Phase 47 resolved 13 of its 17):

| id | company | written | tier | score |
|---|---|---|---|---|
| `15008671672` | Racing NSW | `governing_body_league` | B → **A** | 40 → 80 |
| `20538284384` | Waikato Racing Club | `individual_club_team` | C → B | 30 → 45 |
| `20943964946` | The Rumble | `content_producer` | B → B | 40 → 60 |
| `17317850381` | Jam TV | `broadcaster` | D → D | 20 → 40 |
| `17317381378` | Editix | `unknown` + reason (D-03) | Unscored | 0 |

Jam TV's geographic veto (`Non-ANZ geography`) survived its `broadcaster` write, as predicted —
org-type has no path to clear a geography veto.

**Costs vs the approved ex-ante estimate:** 1 Anthropic research call, 6 n8n executions
(`11865` disarmed proof + `11866`–`11870` armed), 0 provider credits. Matched the projection.
The Anthropic *dollar* actual was never captured — `claude_web_research()` does not log
`msg.usage` — so the run report carries the $0.0686 **floor**, explicitly not a measurement.

**D-06 window accounting honoured exactly:** 1 deploy+bounce, 1 armed window, cap 5. One deploy
attempt printed `skipped (no n8n creds)` and made no PUT — disclosed, did not count.

**Two mid-phase deviations, both disclosed:**

1. **Plan 48-07 inserted mid-execution.** The paid research classified Racing NSW as `regulator`;
   the operator rejected it. Root cause: the prompts listed the 9 enum values but never *defined*
   them, so the model keyed on statutory origin — useless, since QRIC and Racing NSW are both
   statutory bodies. The real discriminator is **commercial control of the sport**. Fixed offline
   at zero spend: definitions now live once in `config/taxonomy.yaml` and render into both
   prompts, a coherence guard flags (never auto-flips) an incoherent `regulator`, and the
   `WEB-RESEARCH-SPEC` §9 golden case is now an executable test. Vindicated empirically — Racing
   NSW landed Tier A (80); `regulator` would have scored 20 (Tier C). 48-07 also fixed a live
   blocker that would have made 48-05 raise.

2. **Waiver `D-48-01`** (operator, 2026-08-13, `375e919`) delegated the deploy+bounce and both
   arming surfaces to Claude **for Phase 48 only**. It does not revive the expired `D-47.5-01`
   and expires with this phase.

**Known-unproven, stated rather than papered over:** the D-04 gate's live *firing* on a real
Anthropic error. Proven instead: structural presence in the RUNNING instance (execution `11865`'s
own embedded node list) plus an offline expression test. No Phase 48 execution traverses the
research branch and a 400 cannot be induced on demand.

**Carried forward:** COVER-01/COVER-02 are NOT closed by Phase 48 alone (D-02 split — Phase 47
covers 17 records, Phase 48 the rest). Code review left 2 WARNINGs (bare `assert` for the D-07
guard; partial audit-trail loss if an unexpected exception hits the armed loop) — latent
robustness gaps for future re-invocation, neither affecting this run.

## ✅ PHASE 47.5 — ALL 6 PLANS COMPLETE, NOTHING ARMED (2026-08-12)

**Both declared armed windows are spent and closed. The phase declared TWO up front and used
exactly two** — the correction to Phase 47, which needed five for one plan.

**47.5-06 outcome (armed window #2 of 2).** One arm, one disarm, three records touched once
each. Executions 11859/11860/11861 (plus disarmed rehearsal 11858).

| id | write | before | after |
|---|---|---|---|
| 17317184159 Ironman | region `Other` -> `ANZ` | 70 / D / `Non-ANZ geography` | **80 / A / no veto** |
| 15860277364 GRAVITY MEDIA | region `Other` -> `ANZ` | 50 / D / `Non-ANZ geography` | **60 / B / no veto** |
| 18047161864 Simtech LED | **NONE — recompute only** | 40 / B / no veto | **40 / D / `Hardware/AV/LED vendor…`** |

**Simtech is the load-bearing row:** a COMPLETE record the gate calls `skip`, zero input change,
moved solely because the new OR predicate ran on the recompute lane. Retroactivity executed, not
asserted — and the one outcome no input edit could have produced.

Every hard assertion (flag + reason) proven by independent read-back. Score and tier all six
matched the pre-arm oracle predictions but **stay reported as predictions** — Phase 49 owns
oracle-vs-live parity. D-07 held absolutely: only `lv_country_region_normalized` was ever
PATCHed, twice. Disarm `observed` all-false with both allowlists empty, plus a fourth
independent read of the workflow literals; `active: true`. Cost: 4 n8n executions, **0** provider
credits, **0** Anthropic calls.

**Portal-wide non-ANZ veto census: 4 -> 2.** The two remaining are the two never in the
allowlist — Entain `10024564084` (held by its second veto, `lv_produces_content=false`) and
**Jam TV `17317850381`, still vetoed as D-23 requires**. Both untouched, `hs_lastmodifieddate`
predating the window. VETO-03 bar still 0.

**Completed:** 47.5-01 (lane offline) · 47.5-02 (deployed+bounced, execs 11852/11853) ·
47.5-03 (acceptance test GREEN, window #1) · 47.5-04 (registry-grade D-V6 evidence) ·
47.5-05 (OR predicate in both engines, one commit) · 47.5-06 (window #2, 3 records written).
**RECOMP-01/02/03/04 all Complete.**

**Next action: seal phase 47.5, then Phase 48 (COVER-01/COVER-02).** Do NOT pass `--ws` to
`phase.complete` — v0.8 phases live in root `.planning/` and the workstream guard misfires.

## Current Position

Phase: 50 (Derived Tier Property) — EXECUTING
Plan: 3 of 5
Status: Ready to execute
  deployed and live, the acceptance test red since Phase 40-07 is GREEN with all four
  assertions byte-identical, the D-V6 flips are written, and the hardware veto's retroactivity
  has executed on a real record. **Nothing is armed** — windows #1 and #2 were each opened
  once and closed once, and both disarms were independently re-read.

**47.5-03 outcome (armed window #1 of 2).**
`tests/test_scoring_parity.py::test_veto_clear_after_correction` passed live in 23.34s,
exit 0. `git diff HEAD -- tests/test_scoring_parity.py | grep -cE '^[-+][[:space:]]*assert '`
reads **0** — no assertion was weakened, deleted, reworded or added; the "exactly one
search match" enforcement is `pytest.fail`, not `assert`. The test was made HARDER: it
stamps both `lv_*_verified_at` before leg 2, so exec **11857**'s `Company Gate` verdict is
`skip` ("all required fields present, fresh and valid") mapped to `enrich` by the recompute
intent — the frozen-COMPLETE case, proven on the acceptance test itself and not only by
inheritance from Simtech LED. `HubSpot Company Update` returned 200 in both legs
(11856 flag `"true"`/`"Non-ANZ geography"`; 11857 flag `"false"`/`""`), 21 nodes each, zero
provider/research/judge/merge nodes. Disarm `observed` all-false with both allowlists empty,
confirmed by a fourth independent re-read showing `active: true`; domain search `MATCHES: 0`
before and after; no disposables survive. **Not proven: a live D -> non-D tier transition** —
the tier assert passed but the legs are 5s apart and the disarmed rehearsal read
`lv_icp_tier: "Unscored"` pre-veto, so the flag->tier flow likely never wrote D. Phase 49
scope. Full record: 47.5-A-LIVE-PROOF.md § "Armed window #1".

**47.5-02 outcome.** The lane is LIVE in the running instance, proven by execution 11852's
own node list (not a stored read-back). Assumption A1 discharged: n8n did not fan out.
RECOMP-02 met live by execution 11853.

**47.5-01 outcome.** A complete company can now be routed straight from `Company Gate`
into `Decide Company Action` by a request-level `recompute` flag on the D-18 POST — one
edge, zero provider/research/Anthropic calls, `Decide` still the sole veto writer. A
recompute that resolves to no company is REFUSED (`recompute_refused`), never created. A
skipped company now terminates observably at `Build Response` with its gate reason instead
of a bare 200 (RECOMP-02), which also closes the latent paired-index defect by construction.
Two operator helpers landed for plan 03: `post_webhook_event(..., recompute=True)` with a
300s default read timeout, and `june_run_arm.py --domains`. 664 node tests + 2600 pytest
green; zero live reads, zero writes, zero arming. See 47.5-01-SUMMARY.md — one live-found
deviation (`ENRICH_CO_GATE` is shared by two workflows that have no `Parse HubSpot Event`
node, so the `$()` read is try/catch-guarded, fail-closed).

**Phase 47 outcome (closed).** 16 false non-ANZ vetoes cleared; Jam TV (17317850381) correctly RETAINED its
veto per D-23 with region=Other. VETO-03 operator-confirmed 2026-08-12 ("no Non-ANZ
geography companies with Unknown region") — that bar went 17 -> 0. Tiers after: B×9, C×5,
Unscored×2, D×1. n8n executions 18 (11834-11851). Provider credits 0. Tests green.

**Two disclosed misses.** must_have #1 ("ONE armed window") NOT met — five arm/disarm
cycles, two records touched twice. Two named checks relaxed (D-20 re-stamp; oracle-tier
assertion). Both recorded in 47-RUN-REPORT.md § "Window accounting" and 47-04-SUMMARY.md,
not softened. settle_veto stayed hard throughout.

**All three workstreams are now closed.** Both armed windows are spent. 47.5 carried
THREE workstreams:

- **A — fix the recompute path.** ~~A record with COMPLETE inputs cannot have its veto
  recomputed by any on-demand trigger.~~ **DONE — built in 47.5-01, proven live in 47.5-02,
  and the acceptance bar met in 47.5-03 (RECOMP-01 Complete).**
  Per project memory `n8n-stored-vs-running-content.md`, a stored read-back proves nothing:
  the lane is in the built JSON only until plan 02 deploys, bounces and reads back one live
  execution whose `runData` contains `Decide Company Action`.

- **B — D-V6 re-examination of the four remaining non-ANZ vetoes.** **DONE** — registry-grade
  evidence in 47.5-04 (RECOMP-03), written live in 47.5-06. Ironman is Tier A and Gravity Media
  Tier B; Entain and Jam TV correctly retained. Gravity Media's `ANZ` rests on **Australian
  operating presence alone** — its NZ leg is UNPROVEN and must not be read as two-country
  evidence.

- **C — decide the hardware veto's trigger field.** **DONE** — `or-retroactive` decided
  (47.5-C-DECISION.md), landed in both engines in one commit `f817ec5`, deployed, bounced, read
  back out of the RUNNING instance, and its retroactive consequence executed live on Simtech LED
  (RECOMP-04).

Scope doc amended accordingly, including its out-of-scope list (which previously forbade
exactly what B and C now do): .planning/phases/47.5-veto-recompute-path/47.5-CONTEXT.md

**Standing order:** COVER-01/COVER-02 stay open for Phase 48 (four records ended with no
lv_org_type: Editix, Jam TV, Waikato, The Rumble). Not a 47.5 workstream.

Previous status: Executing — Anthropic credit restored, Plan 03 completed
Last activity: 2026-08-13 — Phase 50 execution started
  the live property-existence guard (found 19 missing D-09 metadata properties, resolved
  via operator-confirmed D-21 narrowing), one live research pass over all 17 pinned
  companies (47-RESEARCH-RESULTS.json), two live-discovered data-quality fixes
  (lv_org_type enum gate, lv_is_gambling_operator never derives org_type), and the
  mandatory disarmed dry-run (47-DRYRUN.md/47-RUN-REPORT.md). Zero live writes. The
  Anthropic billing outage recorded in 47-BLOCKED.md is resolved -- credit confirmed
  restored before Plan 03 resumed and completed. Plan 04 (armed run, autonomous: true
  per D-22) is next.

Progress: [█████████░] 91% (v0.9 phase 47.5 of 46-49)

## Session

**Last session:** 2026-08-13T22:07:23.133Z
**Stopped at:** Completed 50-03-PLAN.md (D-07 gate FAIL, D-19 census DEFECT)
**Resume file:** None

## Performance Metrics

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 39 P01 | 25min | 3 tasks | 3 files |
| Phase 39 P02 | 12min | 3 tasks | 8 files |
| Phase 39 P03 | 8min | 3 tasks | 3 files |
| Phase 39 P04 | 15min | 1 tasks | 4 files |
| Phase 40 P01 | 27min | 2 tasks | 9 files |
| Phase 40 P02 | 22min | 3 tasks | 3 files |
| Phase 40 P03 | 66min | 3 tasks | 9 files |
| Phase 40 P04 | 25min | 3 tasks | 6 files |
| Phase 40 P05 | 75min | 3 tasks | 4 files |
| Phase 40 P06 | 55min | 3 tasks | 5 files |
| Phase 40 P07 | ~60min | 3 tasks | 6 files |
| Phase 41 P02 | 45m | 3 tasks | 7 files |
| Phase 41 P01 | ~55min | 3 tasks | 10 files |
| Phase 43 P01 | 25min | 3 tasks | 13 files |
| Phase 42 P02 | 12min | 3 tasks | 3 files |
| Phase 42 P03 | 20min | 3 tasks | 6 files |
| Phase 43 P04 | 45min | 3 tasks | 3 files |
| Phase 44 P01 | 35m | 3 tasks | 14 files |
| Phase 44 P02 | ~20min | 3 tasks | 8 files |
| Phase 44 P03 | ~50min | 3 tasks | 2 files |
| Phase 45 P01 | ~30min | 3 tasks | 9 files |
| Phase 45 P02 | ~55min | 3 tasks | 7 files |
| Phase 45 P03 | ~20min | 3 tasks | 4 files |
| Phase 46 P01 | ~40min | 3 tasks | 6 files |
| Phase 46 P02 | ~35min | 2 tasks | 4 files |
| Phase 46 P03 | ~20min | 2 tasks | 1 files |
| Phase 46 P04 | 35min | 2 tasks | 11 files |
| Phase 46 P05 | ~15min | 2 tasks | 7 files |
| Phase 47 P01 | 20min | 3 tasks | 3 files |
| Phase 47 P02 | 35m | 3 tasks | 4 files |
| Phase 47 P03 | 5h | 3 tasks | 9 files |
| Phase 47 P04 | ~3h | 4 tasks | 8 files |
| Phase 47.5 P01 | 50min | 3 tasks | 9 files |
| Phase 47.5 P04 | 35 min | 3 tasks | 2 files |
| Phase 47.5 P02 | 25min | 3 tasks | 3 files |
| Phase 47.5 P03 | 45min | 3 tasks | 3 files |
| Phase 47.5 P05 | 40min | 3 tasks | 7 files |
| Phase 47.5 P06 | 35min | 3 tasks | 4 files |
| Phase 48 P01 | 25min | 3 tasks | 3 files |
| Phase 48 P02 | ~20min | 3 tasks | 4 files |
| Phase 48 P03 | 35min | 3 tasks | 4 files |
| Phase 48 P07 | 35min | 3 tasks | 9 files |
| Phase 48 P04 | 15min | 3 tasks | 1 files |
| Phase 48 P05 | 35min | 3 tasks | 5 files |
| Phase 48 P06 | ~20min | 3 tasks | 3 files |
| Phase 49 P01 | 32min | 3 tasks | 4 files |
| Phase 49 P02 | 22min | 2 tasks | 3 files |
| Phase 49 P03 | 9min | 3 tasks | 12 files |
| Phase 49 P04 | 8min | 3 tasks | 4 files |
| Phase 49 P05 | 45min | 3 tasks | 6 files |
| Phase 49 P06 | ~30min | 3 tasks | 4 files |
| Phase 49 P07 | 12min | 3 tasks | 1 files |
| Phase 50 P01 | ~35min | 4 tasks | 10 files |
| Phase 50 P03 | 50min | 3 tasks | 6 files |

## Decisions

- [Phase ?]: D-03 -> D-04: live probe found a null term inside an UNTAKEN calculation_equation branch still blanks the whole result; coalesce(lv_icp_fit_score, -1) forced into lv_icp_tier_derived's formula
- [Phase ?]: lv_icp_tier_derived created live; all 4 stuck records (9605273630, 9604738976, 17696004613, 19100977027) confirmed reading B with zero writes; live search confirms 646 never-enriched companies now read Unscored
- [Phase ?]: Live discovery: HubSpot's Properties API canonicalizes stored calculationFormula text on create (= -> equals, double -> single quotes, inserted line breaks) -- not byte-identical to the submitted literal though functionally equivalent; future formula-pin tests must compare against the live-read text, not the pre-creation literal
- [Phase ?]: D-07's gate FAILS live: veto guard on lv_icp_tier_derived never fires for any of 6 real anti_icp_flag=true records (a defect never verified before this run); D-06/D-08 stay blocked
- [Phase ?]: TIER-01 left NOT complete (ladder not verified against real records per its own text); TIER-02 marked complete (null semantics settled and disclosed independent of the veto bug)

### Roadmap Evolution

- **Phase 50 added 2026-08-13: Derived Tier Property.** Added during `/gsd-discuss-phase 50`, which
  found no roadmap entry (`init.phase-op 50` → `phase_found: false`). Operator directed adding it
  and **extending v0.9** rather than opening v1.0, because it closes v0.9's own disclosed debt —
  the 4 stuck-tier records logged as unmet truth by Phase 49 (`WINDOWS.md` ids 9–12). v0.9 is now
  Phases 46–50 and its close is no longer imminent. Requirements TIER-01/02/03 added. Roadmap and
  requirements committed as `4173da0`; context and discussion log as `4a8f896`.

- **Scope lift 2026-08-13:** v0.9's "no new HubSpot properties of any kind" decision (operator,
  2026-08-11) is lifted for **exactly one** derived-tier string property (`lv_icp_tier_derived`)
  and nothing else. Forced, not preferred — `lv_icp_tier` is `type: enumeration,
  calculated: false`, zero of 264 portal properties are calculated enumerations, and HubSpot does
  not support enumeration outputs for calculation properties. `lv_icp_scoring_version` and the
  three CLAUDE.md §5.3 fields remain excluded. Amendment lives in `.planning/REQUIREMENTS.md`
  § Out of Scope; rationale in `50-CONTEXT.md` D-01.

### Phase decisions

- [Decision 2026-08-12]: `venue` org type LOCKED at weight 5 (no hard veto, motion work_via_league); on entity collision individual_club_team wins; three-layer org-type normalization (generation-time enum, deterministic alias table, Haiku fallback) LOCKED. Implement in Phase 48, score in Phase 49. Phase 47's window unaffected. Full record: .planning/decisions/2026-08-12-org-type-venue-and-normalization.md

- [Phase 40-01]: D-05 round-trip verdict PROVEN — `PUT /automation/v4/flows/{id}` accepts STATIC_BRANCH action-content edits live; no portal-UI fallback needed for this edit shape. IS_BETWEEN edits (40-05) remain unverified.
- [Phase 40-01]: Corrected D-07's literal step order — validate-on-disposable must run while the flow is enabled, not disabled (a disabled flow never fires). Documented in PORTAL-FACTS.md for 40-04/40-05/40-06 to follow.
- [Phase 40-01]: ENGINE-06 fully closed; ENGINE-05 only half-closed (org-type branch no longer double-deducts gambling, but the real lv_is_gambling_operator-driven -20 component is still 40-04's work — do not mark ENGINE-05 complete until then).
- [Phase ?]: Task 1 checkpoint resolved: merge-then-cut (operator, 2026-08-06) — feat/v0.6-plugin-entrypoint merged into master via --ff-only, feat/v0.7-scoring-remediation cut from master (D-09).
- [Phase ?]: git push origin master skipped this session (sandbox denied it) — local master is ahead of origin/master; push deferred to operator/orchestrator.
- [Phase ?]: 39-03: FLIP_PROPERTY_NAME chosen as lv_org_type (taxonomy-controlled, matches 39-04's example criterion) since the plan left the concrete flip property unspecified.
- [Phase ?]: 39-03: DECIDE-01 left unmarked in REQUIREMENTS.md — spans all 4 plans, completes only when 39-DECISION.md lands in 39-04.
- [Phase 39-02]: Availability verdict AVAILABLE (company fit-score confirmed on Sales Hub Pro, portal 22617666) — but operator overrode CONTEXT.md D-05's lead-scoring-tool preference mid-plan, locking the path to fix-the-four-workflow-chain-in-place on an lv_icp_fit_score architecture-reuse requirement the lead-scoring tool cannot satisfy. Full decision record still lands in 39-04's 39-DECISION.md.
- [Phase 39-02]: Task 2's in-portal walkthrough was performed by the orchestrator driving the operator's own logged-in Chrome session, at the operator's live delegation — deviation from D-01's "operator drives it," recorded in VERIFICATION-NOTE.md's header; portal state/screenshots are authentic.
- [Phase ?]: [Phase 39-04]: Path verdict recorded: fix-the-four-workflow-chain-in-place (39-DECISION.md), decided on operator hard requirement to reuse lv_icp_fit_score/lv_icp_tier — availability gate resolved AVAILABLE but was not the deciding factor.
- [Phase ?]: [Phase 39-04]: Tasks 1 (armed recalc-latency probe) and 2 (band-c checkpoint) skipped as moot per operator override — D-04 gate applies only to the lead-scoring-tool path, which is not chosen. Documented as deviations in 39-DECISION.md's Process note.
- [Phase ?]: [Phase 40-02]: Live parity harness landed (PARITY-01/PARITY-02) — tests/scoring_fixtures.py + tests/test_scoring_parity.py + scripts/run_scoring_parity.py. All named -k selectors ready for 40-03..40-06; live tests intentionally RED until owning plans land.
- [Phase 40-03]: lv_anti_icp_flag/lv_anti_icp_reason ported into ENRICH_DECIDE_CO_CLOUD (D-01), byte-identical to src/icp_scoring.py's hard-veto block; DEFAULT_COMPANY_POLICY's veto entries hardened to min_confidence:80 (D-04/P2 closed). Operator armed the deploy and bounced the affected workflows — confirmed live.
- [Phase 40-03]: **BLOCKER (pre-existing, not caused by this plan) — ALLOW_HUBSPOT_RECORD_WRITES is baked "false" in every build** (scripts/build_cloud_workflows.py's WRITE_SAFETY_DEFAULTS). No enrichment run can PATCH a real HubSpot record until this is flipped, rebuilt, and redeployed — a deliberate rollout-gate decision, not something 40-03 should flip unilaterally. 40-05 must NOT delete the Geography flow's veto branch until this is resolved and a live write is confirmed landing, or the portal will have zero working veto writers (T-40-11's DoS scenario). See WINDOWS.md id 2, 40-03-SUMMARY.md's Live Validation Findings.
- [Phase 40-03]: **BLOCKER (pre-existing) — SJ-3's dispatch to "LV Enrichment (Cloud template)" errors "Missing node to start execution"** (live executions 1891/1893) because that workflow's only entry point is a Webhook Trigger, not an Execute Workflow Trigger. The 15-min lv_enrichment_requested poller (D-02's documented refresh path) never reaches enrichment. Blocks SJ-1/SJ-2/SJ-3 broadly, not just the veto. See WINDOWS.md id 3.
- [Phase 40-03]: VETO-01/VETO-02 left unmarked in REQUIREMENTS.md — code is fully verified (offline+live-webhook-execution) but the plan's own bar (a live PATCH landing on a real record) could not be met due to the two blockers above.
- [Phase 40-04]: The other three `*_score` components' default-0-on-creation stamp is not reproducible via the CRM v3 Properties API (`defaultValue` silently dropped on POST and PATCH, `numberDisplayHint` PATCH also had no effect) — live-probed three ways before concluding this. Live-confirmed via a reversible formula spike that this matters: `lv_icp_fit_score`'s `calculation_equation` formula blanks entirely when one referenced term is null, not treats it as 0. Fixed by giving `produces_content_score`/`gambling_score`'s new mapper flows a second enrollment branch on `createdate` known, feeding the existing default branch — stays inside the API-only D-05/D-08 path, no portal-UI needed. Does not retroactively affect any of the 712 pre-existing companies (per 40-01's enrollment-requires-a-future-event finding).
- [Phase 40-04]: `lv_icp_fit_score` extended from 3 to 5 terms (`+ produces_content_score + gambling_score`) via a single clean PATCH (no 400, no portal-UI fallback). ENGINE-02 and ENGINE-05 closed. The remaining gap to ENGINE-01's 80/A total is exactly 40-05's geography/revenue retarget, unchanged by this plan.
- [Phase 40-05]: **Blocker resolved before this plan started** — `VETO-WRITE-EVIDENCE.md` (2026-08-06/07) live-proves both WINDOWS.md #2 (ALLOW_HUBSPOT_RECORD_WRITES) and #3 (SJ-3 dispatch) are fixed: a real HubSpot PATCH landed `lv_anti_icp_flag="true"` via the scheduled-arm companion, independently re-verified, window disarmed after. This satisfied the precondition the old blocker below (now cleared) was guarding.
- [Phase 40-05]: Both Geography (4626722240) and Annual Revenue (4626722237) flows retargeted to their canonical trigger properties (`lv_country_region_normalized`, `lv_revenue_band`) and the Geography flow's veto branch deleted — D-01 complete, n8n pipeline is now the sole writer of `lv_anti_icp_flag`/`lv_anti_icp_reason`, guarded by a permanent conformance test scanning every archived flow. ENGINE-03/ENGINE-04 closed.
- [Phase 40-05]: Live-discovered two HubSpot Automation v4 API limits not previously documented: (1) converting an action's `type` from `LIST_BRANCH` to `STATIC_BRANCH` via PUT 400s — worked around by keeping `LIST_BRANCH` and editing its `MULTISTRING IS_EQUAL_TO` filter content instead, staying on the API-only path with no portal-UI fallback needed; (2) a flow's PUT rejects reintroducing any `actionId` that existed in an earlier revision of that same flow but is absent from the current PUT body, even with no orphans and unique targets — resolved by using ids never before used by that flow. See `PORTAL-FACTS.md`'s Plan 05 section for full detail.
- [Phase 40-05]: Task 3's blocking checkpoint auto-resolved per operator pre-approval (2026-08-07), citing `VETO-WRITE-EVIDENCE.md`. Read-only measurement performed instead of the checkpoint's real-record-refresh step: stale `lv_anti_icp_flag=true` population is **zero** across all 711 companies (not "unknown" as originally framed) — no company in this portal has ever had the flag written by any source, consistent with `ALLOW_HUBSPOT_RECORD_WRITES` having been false for the whole phase until the one now-deleted disposable exception.
- [Phase 40-05]: `tests/test_scoring_parity.py::test_f4_au_string_is_not_vetoed` corrected (Rule 1) to assert `lv_anti_icp_flag != "true"` rather than `== "false"` — a direct, in-scope consequence of D-01's completion (HubSpot no longer writes the flag at all, so a bare disposable patch leaves it `None`, not `"false"`). Matches this plan's own Task 1 acceptance bar verbatim.
- [Phase 40-06]: `lv_icp_tier` enum given a fifth option, `Unscored` (`config/hubspot_flows/lv_icp_tier-property.{before,after}.json`), live-validated on a disposable before WF1 was touched — A/B/C/D preserved verbatim, no `Needs Review` option added (deferred, per REQUIREMENTS.md).
- [Phase 40-06]: WF1 (4625147345) retargeted and rebranched — below-15 branch writes `Unscored` instead of `D` (F8/ENGINE-07 closed: `D` is now reachable only through the veto-guarded branch); enrollment criteria extended with `lv_anti_icp_flag` known as a second trigger (F7/VETO-03 closed: a flag flip alone moves the tier, live-validated both directions on a fixed B-band total with the score held constant); veto branch filter corrected from `BOOL true` to `STRING "true"` (D-04) after live-discovering `lv_anti_icp_flag` is a `booleancheckbox` property with string-valued options. Live parity: 70/69/40/39/15/14/-20 all graded to the correct tier, `-20` landing `Unscored` not `D`.
- [Phase 40-06]: `tests/test_scoring_parity.py::test_gambling_deducts_20_without_veto` corrected (Rule 1) to assert `lv_anti_icp_flag != "true"` rather than `== "false"` — the same stale-assertion class 40-05 already fixed once in this file, surfaced by this plan's own `<verification>` selector.
- [Phase 40-07]: **Phase 40 CLOSED.** ENGINE-01 live-proven end to end — a disposable with `lv_org_type=governing_body_league`, `lv_produces_content=true`, `lv_country_region_normalized=AU`, `lv_revenue_band=50-500M` reads `org_type_score=40`, `produces_content_score=20`, `geography_score=10`, `annual_revenue_score=10`, `gambling_score=0`, summing to `lv_icp_fit_score=80`, `lv_icp_tier=A` — entirely inside HubSpot, off canonical inputs only, closing the phase's headline requirement.
- [Phase 40-07]: D-10's backfill mechanism built (`scripts/backfill_seed_company_scores.py`, `batch_update_companies` in `src/hubspot_client.py`) and proven on the real-record sample. Portfolio-wide measurement found exactly **one** company anywhere in the portal (711 total) carries any canonical `lv_*` scoring input — Melbourne Racing Club, id `9604614548` — confirming the 712-population backfill is genuinely Phase 41's job, not deferred prematurely. Armed run seeded its five components; settled live to `lv_icp_fit_score=15`, `lv_icp_tier=C` in ~11s.
- [Phase 40-07]: PARITY-01 verdict committed (`.planning/phases/40-scoring-engine-remediation-notes/parity-report-final.json`): `assertions_executed=1`, `PASS` with 1 documented `Needs Review` divergence (40-02's flagged assumption — score and veto state agree with the oracle exactly; only the tier label diverges because HubSpot's live `lv_icp_tier` enum has no `Needs Review` value) and 0 real findings. `scripts/run_scoring_parity.py`'s flag comparison corrected (Rule 1, third instance of the same defect class 40-05/40-06 each fixed once in the pytest live tier) to boolean-equivalence instead of raw string equality — a never-enriched real record reads `lv_anti_icp_flag=None`, not `"false"`.
- [Phase 40-07]: **VETO-01/VETO-02 confirmed still open, empirically, not fixed by this plan.** Full live fixture tier: 56/56 non-veto-arming tests passed. The 5 excluded cases (`test_veto_set_all_three_hard_vetoes` ×3, `test_veto_set_multiple_reasons_join`, `test_veto_clear_after_correction`) fail because setting veto-input properties alone never dispatches the n8n pipeline under this portal's actually-configured webhook subscriptions — VETO-WRITE-EVIDENCE.md's own proof required the SJ-3 poller plus a bounded `scheduled_arm.py` write-gate arm, an operational/security action outside this plan's `<action>` text and explicit scope per 40-03/40-05/40-06 precedent. Also fixed WINDOWS.md #4 (Rule 1, pre-existing open bug): `test_veto_clear_after_correction` patched `enrichment_requested` instead of the real SJ-3 poller-search property `lv_enrichment_requested` — corrected, though the test still fails at its earlier veto-setting assertion for the same structural reason as the other four. New WINDOWS.md entry (id 5, open) records this gate for Phase 41/future-phase visibility.
- [Phase ?]: 41-02: domain-first D-09 re-match derives a candidate domain from the June row's per-field evidence URLs (urlparse netloc, www.-stripped) since the June source snapshot carries no explicit domain field
- [Phase ?]: 41-02: PARITY_REQUIRE_PROVENANCE=true is additive to real_findings (a shallow-copied record with classification=provenance_missing), never overwriting a pre-existing score/tier/flag mismatch classification on the same record
- [Phase ?]: 41-02: june_run_arm.py imports operator-claude-plugin/scripts modules directly via sys.path insert -- PLUGIN-04's import guard only forbids plugin-to-backend imports, backend-to-plugin was never scanned
- [Phase 41-01]: F1/F2 resolved as planned (native firmographic band derivation; D-04 as a synthetic needs_review decision, not a CONFLICT_WATCH extension — CONFLICT_WATCH has zero live consumers for org_type/produces_content). Exception-list judgement: Big Screen Video, Racing.com, and The Creek Agency deliberately left on the deterministic org_type mapping — docs/business/icp-scoring.md section 4 does not name any of the three, so none were added to scripts/build_june_candidates.py's EXCEPTIONS dict. Two pre-existing guard tests (test_architecture_guard.py's AR-2 host allowlist, test_companies_factory_frozen.py's byte-identity fixture) required scoped, non-weakening extensions/re-baselines as a direct consequence of embedding the real 66-company dataset into the Merge Company node — both documented in 41-01-SUMMARY.md. DATA-01 intentionally left unmarked in REQUIREMENTS.md: this plan covers only the offline half; full closure needs 41-03's zero-spend proof and 41-04's live parity verdict.

- [Phase 43-01]: PIPE-01's boolean-writer sweep (D-07) fixed exactly the 5 BROKEN inventory rows named in 43-01-PLAN.md — `reviewApply.js` clearPatch (rows 1-2, single shared fix site for both HubSpot PATCH consumers), `ENRICH_DECIDE_CO_CLOUD`'s needs-review branch (row 3), and a boolean-coercion branch added to the pre-existing BUG-27 array-join loop in both `ENRICH_DECIDE_CO_CLOUD` and `ENRICH_DECIDE_CLOUD` (rows 4-5) — covering `lv_produces_content`/`lv_sponsorship_reliant`/`lv_is_hardware_vendor`/`lv_is_gambling_operator` with no per-field list. Rows 6-8 (already fixed in Phase 40/36-07) verified unchanged with a new regression test guarding them.
- [Phase 43-01]: PIPE-02's `min_confidence` was confirmed already 80 (Phase 40 D-04) and left untouched, per C1/43-RESEARCH.md Pitfall 1 — only coercion was added to `mergeCompanies.js`'s promote branch (D-09/D-10), proven statically with zero calls to `mergeCompanies()` in the new test, and applies to every promoted boolean candidate (not just the dead veto path) since it shares the one promote-branch assignment.
- [Phase 43-01]: Rule 1 fallout — 4 node-test fixtures (reviewLoop, reviewDecisionEndpoint, mergeCompanies, sponsorshipReliantCopyLoop) and `tests/fixtures/companies_jscode_frozen.json` needed updating/re-baselining to match the corrected boolean-string shape; all documented in 43-01-SUMMARY.md's Deviations section, not scope creep.
- [Phase 42-02]: `config/hubspot_properties.yaml` expanded from a 22-property create-only company manifest to a 32-property full D-04 mirror; every new value copied verbatim from the committed live snapshot (never CLAUDE.md). The 5 design-only names (`lv_icp_confidence`, `lv_recommended_motion`, `lv_icp_scored_at`, `lv_icp_scoring_version`, `lv_named_account_priority`) stayed absent from the yaml, confirmed absent live by this plan's own re-run (documented_gap, not fabricated).
- [Phase 42-02]: The 4 offline guards D-04 broke were amended in place (exemption set, valid-pair set, native-group frozenset, count bump), each with a comment restating its protective intent; a 5th test whose absence-assertion premise D-04 overturns was renamed and its body replaced with a presence-plus-live-shape assertion. 15/15 tests pass, no guard weakened or deleted.
- [Phase 42-02]: Live proof completed in-session (dotenv-loaded operator commands, `.env` never read directly): `drift-report-phase42-reconciled.json` exit_code=0, do_not_archive.ok=true; `sync_hubspot_properties.py` dry-run shows 0 property creates / 0 group creates for both companies and contacts — the expansion cannot cause a portal write.
- [Phase 43-01]: **Deploy deliberately NOT performed.** The regenerated `n8n/*.json` files carry undeployed Phase 43 changes. 43-05 must confirm Phase 41's arm window is disarmed before running `scripts/deploy_n8n_workflows.py` against them — deploying now would push these unproven changes live for the first time AND close whatever Phase 41 arm state remains open, as a side effect of the same PUT.
- [Phase ?]: [Phase 42-03]: Live orphan derivation found zero uncontested_orphan and zero ambiguous candidates -- all 32 non-hubspotDefined company properties classify protected (11 do-not-archive + 21 already declared in 42-02's full-mirror yaml); 6/10 live flows protected, remaining 4 out_of_scope (non-company objectTypeId). Archival command never attempted, config/hubspot_flows/archive-2026-08-07/ never created -- nothing to archive. Post-mutation drift-report-phase42-post.json confirms exit_code=0, do_not_archive.ok=true. Phase 42 (CLEAN-01) fully closed.
- [Phase 43-04]: Deviated from the plan's literal Task 2 operator command (`PARITY_SAMPLE_IDS=9604614548`, a protected canary) per this session's explicit constraint against writing to any of the 5 canary records; substituted a disposable company driven through the live n8n scoring pipeline instead, proving the breakdown-write claim against pipeline-computed truth (total 80 == live lv_icp_fit_score 80) rather than the portal's one already-scored record.
- [Phase 43-04]: PIPE-01 severity framing softened per a measured, disconfirming live result: HubSpot silently coerces a bare-JSON-boolean PATCH to `lv_enrichment_needs_review` (a booleancheckbox property) into the string `'true'` — not the "records become invisible to the queue" framing the plan assumed for this property. The fix's value is closing the class before it reaches a non-coercing property, still a real and worthwhile fix.
- [Phase 43-04]: Discovered (not fixed, out of this plan's file scope) that `tests/test_review_flag_eq_filter.py`'s second live test flakes on first run — it PATCHes a brand-new company then searches immediately, with no wait for HubSpot's ~20s search-index lag on new records. Direct reproduction with a poll confirms the EQ filter itself matches correctly. Logged to WINDOWS.md id 6 (open) for the test's owner (43-01) to add a poll.
- [Phase 43-04]: PIPE-04 both `lv_closed_lost_reason` (custom) and `closed_lost_reason` (native) confirmed to exist live on Deals, both 0% filled across 59 examined closed-lost deals — expected first-run outcome per D-04. Open Question 2 (join reliability via `hs_primary_associated_company`) is recorded as genuinely untested: the join step only runs for a deal that already carries a reason, and none did this session.
- [Phase 43-04]: Portal-wide finding, flagged for the operator and not investigated further (out of scope): exactly 1 of 712 companies carries a live ICP score (the canary, Melbourne Racing Club) — its score has drifted from Phase 40's recorded 80/A to 25/C sometime between then and now.
- [Phase 43-04]: Plugin marketplace clone refresh (C5) deferred to merge — session remains on `feat/v0.7-scoring-remediation`; the clone tracks `master` and a refresh now would fetch nothing new.
- [Phase ?]: 44-01: ALLOW_SJ3_DRAIN_WRITES defaults true (D-05 approved) — first enabled-at-rest write authority; bound recorded in code; excluded from overlay/arm system per ALLOW_JUDGE_ESCALATION precedent
- [Phase ?]: 44-01: write-gate coverage guarantee amended deliberately — SJ-3 Drain Clear Flag exempt by name (walker inversion recorded), replaced by sole-feeder + D-06 negative-grep + key+value patch allowlist assertions
- [Phase 44-02]: idle_floor_max_share set to 0.25 in config/execution_budget.yaml — current schedule idles at ~95/month (~4%); one hourly trigger (720/month = 29%) already fails CAP-03, so any sub-daily re-timing is caught
- [Phase 44-02]: invalid opts.cap fails CLOSED in sj3Gate (behaves as 0: defer everything permitted) — deferral preserves work and stays visible via outcome=capped_partial; build also asserts SJ3_DISPATCH_CAP >= 1 since a sub-daily cadence derives the cap to <= 0
- [Phase 44-03]: Phase 44 SEALED live — deploy (operator-run, five 200s, disarmed) + agent bounce (8/8 verified) + execution 11820: gate-closed tick costs 1 execution / 0 sub-executions (research A1 discharged as observation), verbatim gate_closed outcome with cap 40, drain read-back requested=false/status=skipped on disposable 280176525780 (deleted, 0 leaked). verify_live_write_safety.py: disarmed PASS + drain PASS.
- [Phase 44-03]: The observed tick was mode=manual (operator-fired from SJ-3 Trigger in the UI) — no API run-now exists for schedule triggers (405) and the natural daily tick was ~21h out; the schedule's own firing is separately proven by prior tick history. Recorded honestly in 44-LIVE-EVIDENCE.md.
- [Phase ?]: [Phase 45-01]: Tracer feedback gate waived — autonomous:true frontmatter + already-green tracer verify + orchestrator's execute-completely directive outweighed the auto_chain/auto_advance=false literal reading (advisor-reviewed); execution continued through Tasks 2/3 without a human-verify checkpoint.
- [Phase ?]: [Phase 45-01]: executions_in_window's pagination uses a bounded for/else, never a while loop, to stay inside test_report_sufficiency.py's repo-wide D-07 no-poll-loop guard.
- [Phase ?]: [Phase 45-01]: list_workflows stays the second GET in sweep_read.gather (after the executions window, before the summary loop) rather than first, preserving every pre-existing test helper's first-GET-is-executions assumption while still satisfying LOOK-01's backfill ordering requirement.
- [Phase ?]: [Phase 45-02]: fake_config gained permissive budget-floor config keys (share 1.0, not the real 0.25) so pre-existing set_cadence/plan_action plumbing tests keep original semantics; the floor's own strict-refusal arithmetic lives in test_cadence_budget_floor.py's dedicated configs (advisor-reviewed).
- [Phase ?]: [Phase 45-02]: schedule_month_cost fails closed when the target workflow_id+node_name pair is absent from workflow_items, not just when the list is unreadable -- a collection that doesn't contain the workflow being edited cannot answer the cost question either (T-45-08).
- [Phase ?]: [Phase 45-03]: Task 3 was pointer-writing not status-flipping — all six requirement rows were already Complete with ticked checkboxes from 45-01/45-02's own commits; this plan added the concrete test-name pointer each row lacked.
- [Phase ?]: [Phase 45-03]: Plan's literal collected-test-count acceptance criteria (2562/1291+) predate 45-01/45-02's own test additions and no longer match (2481+121/1326+5 actual); the binding zero-failures contract holds on all three suites, recorded per 45-02's precedent for the same stale-literal class.
- [Phase ?]: [Phase 46-01]: Engine count settled at TWO (Python oracle + HubSpot flow 4626124224), not three -- n8n leg carries no org-type weight table (Approach C, Phase 15). ROADMAP success criterion 4 recorded not-triggered.
- [Phase ?]: [Phase 46-01]: Deviated from 46-PATTERNS.md's gambling-block-deletion instruction -- guarded the .get-chained deduction lookup one wave earlier instead of deleting the block, so config and code are never simultaneously green/red across the phase's waves.
- [Phase ?]: [Phase 46-01]: Tracer feedback gate waived (advisor-reviewed) between Task 2 and Task 3, matching Phase 45-01's precedent -- autonomous:true + already-green tracer verify + execute-completely directive outweigh the literal auto_chain/auto_advance=false reading.
- [Phase ?]: [Phase 46-02]: D-02 confirmed as a direct base_score.org_type weight (-20), not a new graduated_deductions key -- build_proposed_cfg's graduated_deductions dict is empty ({}) after all three overrides apply, proven by test.
- [Phase ?]: [Phase 46-02]: Live simulation (66 rows, exact match against 41-final-population.json) found QRIC and both gambling-flagged records already carry genuine hard vetoes independent of this phase's weight changes -- D-02/D-03's score effects are real but do not move those records' tiers, differing from CONTEXT.md's June-snapshot-derived '~1 record moves' estimate. Movement is 14/66 rows, all individual_club_team C->B.
- [Phase ?]: [Phase 46-03]: Operator accepted all three rubric levers as recommended (individual_club_team=15, regulator=-20, gambling deduction removed), no substitutions -- shown the D-07 tiebreaker tension on D-02/D-03 (zero live tier movement) and the parity red-window cost (option a, closed by Phase 49) before deciding.
- [Phase ?]: [Phase 46-03]: D-09's shareable-artifact publish deferred to the orchestrator session -- this CLI executor has no artifact-publishing capability; recorded as a deviation, not an unmet requirement.
- [Phase ?]: Landed signed-off rubric weights (club=15, regulator=-20, gambling deduction removed) in config/icp_scoring.yaml and both live HubSpot flows, with a running-content read-back; RUBRIC-03 complete.
- [Phase ?]: Discovered mid-execution: config/taxonomy.yaml mirrors icp_scoring.yaml's org-type scores and needed the same two edits (not named by 46-RESEARCH.md/46-ENGINE-INVENTORY.md) -- confirmed it never reaches the generated n8n JS.
- [Phase ?]: 46-05: docs/business/icp-scoring.md's anti-ICP direction markers ('club –') fixed to '+' beyond the plan's explicit list, to avoid contradicting the newly-added GTM override text in the same document
- [Phase ?]: 46-05: WEB-RESEARCH-SPEC.md's FanDuel worked-example row was the one site beyond D-13's table the grep sweep found (D-13's own line-159 citation is now stale in a different way -- that text describes revenue-band conflicts, not gambling)
- [Phase ?]: 46-05: .planning/intel/requirements.md edited beyond the single read_first-cited line (REQ-icp-scoring-model, REQ-graduated-deductions also updated) since both print superseded literal weight values covered by the plan's numeric-agreement truth
- [Phase ?]: Phase 47-01: skipped requirements mark-complete for VETO-01/02/COVER-01/02 -- gsd-tools requirements ready-ids confirmed all 4 are blocked pending sibling plans 47-02/03/04's SUMMARY.md
- [Phase ?]: Phase 47-01: added evidence_by_field to the shared claude_web_research_company.json mock fixture (Rule 2) -- it predated the Phase 13/OC-1 addition and was stale against its own RESEARCH_SYSTEM contract
- [Phase ?]: COVER-01/COVER-02 mapped to Phase 47 + 48 (D-02); neither phase closes them alone
- [Phase ?]: 47-COST-ESTIMATE.md written ex-ante, sourced from live estimate_cost() call: 17 web-research calls, ~4 redundant, ~$1.17 Anthropic floor, 0 provider credits
- [Phase ?]: D-21: narrowed D-09 metadata stamps to the 2 that exist live (lv_org_type_verified_at, lv_produces_content_verified_at); full trail moves to 47-RESEARCH-RESULTS.json/47-RUN-REPORT.md
- [Phase ?]: Live-discovered fix: lv_org_type gated to a strict CRM enum allowlist -- the research prompt returns free text, never guessed via keyword mapping
- [Phase ?]: Live-discovered fix: lv_is_gambling_operator boolean never derives lv_org_type -- proven unreliable (8/17 racing clubs false-flagged) unlike lv_is_hardware_vendor
- [Phase ?]: [47.5-01] The recompute intent is a strict boolean row property normalized AFTER the ...event spread, never a `mode` value — isReturnOnly() treats every non-"write" mode as return-only, so a mode-borne intent would report success and write nothing.
- [Phase ?]: [47.5-01] Live-found deviation: ENRICH_CO_GATE is shared by wf_enrichment_cloud, wf_enrichment_local_live and wf_scheduled_maintenance_cloud (SJ-2 Company Gate); only the first has a Parse HubSpot Event node, so the request-level $() read is wrapped in the repo's nodeAll try/catch idiom and fails to false. The plan's literal form would have thrown on every row of the SJ-2 daily sweep.
- [Phase ?]: [47.5-01] The single-veto-writer count gate is DOT-ANCHORED (`.lv_anti_icp_flag =`) — a naive scan reads 2 in Decide Company Action alone, because its 2026-08-10 blank-region debug comment quotes lv_anti_icp_flag="true" in prose. Measured before the assertion was written.
- [47.5-04]: 47.5-B: Ironman 17317184159 -> ANZ and GRAVITY MEDIA 15860277364 -> ANZ (region only); Entain and Jam TV get no write
- [47.5-04]: D-V6 AU-vs-ANZ resolved: ANZ absorbs the multinational-with-local-operations case; Gravity Media's NZ leg recorded UNPROVEN
- [Phase ?]: [47.5-03] RECOMP-01 MET: test_veto_clear_after_correction is green LIVE with all four assertions byte-identical (assert-diff gate = 0). Armed window #1 of 2, opened once and closed once.
- [Phase ?]: [47.5-03] The frozen-COMPLETE case is proven on the acceptance test itself: exec 11857's Company Gate verdict is 'skip' with both lv_*_verified_at stamps present, mapped to 'enrich' by the recompute intent; HubSpot Company Update returned 200 with flag 'false'.
- [Phase ?]: [47.5-03] NOT proven: a live D -> non-D tier transition. The tier assert passed but the legs are 5s apart and the rehearsal read tier 'Unscored' pre-veto — the flag->tier flow likely never wrote D. Phase 49 scope.
- [Phase ?]: [47.5-03] python-dotenv's bare load_dotenv() resolves relative to the CALLING FILE, not the cwd; with no conftest.py, live pytest must be driven through a wrapper passing an absolute .env path, or every HubSpot read 401s.
- [Phase ?]: 47.5-C: hardware veto fires on lv_is_hardware_vendor === true OR lv_org_type == 'hardware_vendor' (or-retroactive); additive so no record loses a veto, boolean survives as manual override
- [Phase ?]: 47.5-C: lv_is_gambling_operator answered with no work — zero divergent records, graduated deduction already empty (Phase 46 D-03)
- [Phase ?]: Phase 48 Plan 01: live population re-derivation matched CONTEXT.md's 2026-08-12 snapshot exactly (5 ids, drift: false); this plan builds coverage_writes_allowed() as a tested gate only, no armed write leg -- zero HubSpot writes/n8n executions by construction
- [Phase ?]: Phase 48 Plan 02: D-04 IF Research Errored gate + Build Research Failure Response landed in scripts/build_cloud_workflows.py (CLOUD build site only), rebuilt into n8n/wf_enrichment_cloud.json (byte-reproducible), offline-tested in tests/n8n/researchErrorGateFlow.test.mjs against the live-observed error shape, a healthy shape, and a degenerate shape. Not deployed -- plan 48-04 owns the operator deploy+bounce.
- [Phase ?]: Operator approved approve-as-estimated at plan 48-03's checkpoint; Racing NSW resolved to 'regulator' (evidenced), not the flagged-likely 'governing_body_league'
- [Phase ?]: Phase 48 Plan 07: Racing NSW ORG_TYPE_DECISIONS entry overridden from returned 'regulator' to 'governing_body_league' per 2026-08-13 operator review; commercial control of the sport (not statutory origin) is the discriminator; the override is recorded as data (override_of/override_rationale) over the byte-identical captured artifact.
- [Phase ?]: Phase 48 Plan 07: config/taxonomy.yaml gained a definition: key on all 9 org_types entries, rendered into both Python research prompts via src.taxonomy.org_type_definitions_block() -- one source, two call sites, no rebuild needed since gen_taxonomy_js.render() doesn't read the new key.
- [Phase ?]: Phase 48 Plan 07: added org_type_coherence_flags() -- flags a regulator classification alongside evidenced content/sponsorship as incoherent, refuses to promote, never auto-flips to another value. Deviation: tests/n8n/parity.test.mjs strips the new Python-only coherence_flags key with a tripwire assertion, since the JS port cannot be touched in this offline plan.
- [Phase ?]: D-48-01 waiver: operator delegated Phase 48's one deploy+bounce and both arming surfaces to Claude, scoped to this phase only; Task 2 performed by Claude accordingly
- [Phase ?]: Execution 11865 (embedded workflowData.nodes, 111 nodes incl. both D-04 gate nodes) proves the RUNNING n8n instance carries the D-04 gate; the Trap-6 duration heuristic did not apply as literally stated and was corrected against the Phase 47.5 recompute-lane precedent instead
- [Phase ?]: 48-05: D-48-01 delegated both arming surfaces to Claude for Phase 48 only; arm and window ran as two separate per-shell Bash invocations so a failed window start still has an explicit disarm path
- [Phase ?]: 48-05: assert_allowlist_exact widened beyond the plan's literal Trap-4 wording to also require ALLOW_HUBSPOT_RECORD_WRITES==true and an empty TEST_RECORD_DOMAINS, closing execution 11858's silent-denial shape
- [Phase ?]: Phase 48 run report: 4/5 cost rows matched estimate exactly; Anthropic-dollar spend disclosed as an unmeasured floor, not a measured actual
- [Phase ?]: D-06 window accounting: exactly 1 deploy+bounce and 1 armed write window spent, matching the declaration -- no excess to disclose
- [Phase ?]: Venue decision file (2026-08-12-org-type-venue-and-normalization.md) closed with a dated additive block confirming D-02's deferral was examined; lv_org_type live-reconfirmed at 9 options
- [Phase ?]: COVER-01/COVER-02 traceability updated to Phase 48's share complete, without claiming joint closure with Phase 47's 17 records
- [Phase ?]: Raised HARD_CEILING_RECORDS 25->100 as a strengthening (paired with a new exact-set gate), not a relaxation
- [Phase ?]: rescore_population.py is a new thin wrapper importing compute_components/build_updates/_chunked/enforce_sample_cap/enforce_exact_population unchanged, never a fork
- [Phase ?]: Population is re-derived TWICE (derive, then re-confirm) immediately before every write leg, refusing on any drift between the two reads
- [Phase ?]: Captured --plan live against portal 22617666 through the absolute-path dotenv wrapper rather than reusing a fixture, so the runbook's numbers trace to a live capture (D-07).
- [Phase ?]: Guard test pins config/icp_scoring.yaml's scoring surface as a key-by-key dict comparison (not a digest) so the D-09 failure message can name exactly which keys moved.
- [Phase ?]: n8n research prompt now renders lv_org_type definitions (not just bare keys); frozen jsCode fixture re-baselined as an explicit reviewed act; contacts-target prompt confirmed to not enumerate org types and left unchanged
- [Phase ?]: Deployed and bounced Phase 49's one declared n8n change (org-type-definitions research prompt fix), proven live via execution 11871's own embedded jsCode executed and its returned prompt string inspected (not just structural substring presence).
- [Phase ?]: Closed the folded todo (2026-08-13-n8n-research-prompt-lacks-org-type-definitions) in .planning/todos/completed/ with a dated RESOLVED block naming plans 49-03/49-04, execution 11871, and the regression test.
- [Phase ?]: Operator resolved the W1 4-record tier-staleness finding as ACCEPT AND DISCLOSE: logged as unmet-truth entries (WINDOWS.md ids 9-12), fix deferred to a future phase (lv_icp_tier as calculation_equation, per TIER-DERIVATION-SPIKE-2026-08-13.md)
- [Phase ?]: Parity verdict committed genuinely RED (4/66 real findings) rather than edited to pass; scripts/run_scoring_parity.py confirmed unedited via git diff
- [Phase ?]: 49-06: W2 opened -- Entain's veto cleared live, D->non-D tier transition proven as a causal chain (t0=D, t1=Unscored), closing the gap 47.5-A left open.
- [Phase ?]: 49-06: Domain-based arming fails for existing records whose stored domain carries a prefix n8n's search normalization strips -- use --ids + a bare event (fetch-by-id lane) instead.
- [Phase ?]: Phase 49 Plan 07: D-11 Artifact deferral resolved -- orchestrator published https://claude.ai/code/artifact/2ac2d25f-586c-4123-9c23-2e6cc7634d2b, operator approved 2026-08-13; Phase 46-03's carried-forward D-09 discharged through the same publish event, not re-deferred

### Blockers

open (VETO-01/VETO-02 remain open requirements, not blockers — Phase 40 met its own scope; see WINDOWS.md id 5 and Decisions above).

- Phase 49 Plan 05 Task 3 (W1 write window): 4 of 66 scored companies (9605273630 Port Macquarie Race Club, 9604738976 Bunbury Turf Club, 17696004613 Pinjarra Park, 19100977027 Newcastle Harness Racing Club) already carried correct new-weight components before W1 opened, so the component-only write was a genuine no-op for them and their lv_icp_tier stayed stale at C (oracle expects B, score 45). Parity sweep FAILs with these 4 real findings. No in-scope W1 mechanism can force WF1 to re-grade them (tier PATCH forbidden, n8n allowlist out of scope for W1). Awaiting operator decision at the checkpoint returned by Plan 05's continuation.
- D-06 (retire lv_icp_tier) / D-08 (switch off WF1) blocked: lv_icp_tier_derived's veto guard never fires live for any of 6 real anti_icp_flag=true records (WINDOWS.md id 13) -- Plan 04's checkpoint must decide fix-vs-defer before retirement

## Deferred Items

Items acknowledged and deferred at the v0.8 milestone close on 2026-08-11. All three predate
this milestone (planted 2026-08-04, v0.6 era) and are not v0.8 gaps.

| Category | Item | Severity | Area | Status |
|----------|------|----------|------|--------|
| pending todo | Enrichment throughput — 82% of every full run is two sequential Anthropic calls | major | n8n | deferred |
| pending todo | Sweep crontab pins a versioned plugin path, so an update silently stops the unattended sweep | major | operator-claude-plugin | deferred |
| pending todo | UAT 2.2 names two header aliases the column mapping does not support | major | n8n + operator-claude-plugin | deferred |

Note on the second item: it is the same failure class as the known plugin-install trap where a
version bump breaks a pinned path. Deferring it leaves the unattended sweep quietly fragile
across the next plugin update — it fails silently, which is the dangerous direction.

## Operator Next Steps

- Run /gsd-plan-phase 50 to plan Derived Tier Property (context gathered 2026-08-13,
  `.planning/phases/50-derived-tier-property/50-CONTEXT.md`)
