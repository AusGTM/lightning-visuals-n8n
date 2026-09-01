---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Unattended Session Runs
current_phase: 62
current_phase_name: Suggest the contacts nobody named
status: complete
stopped_at: "Completed 62-02-PLAN.md (role vocabulary: portal jobtitle clustering, disclosed generic fallback, SUGGEST-03 amended not closed)"
last_updated: "2026-09-01T23:34:02.207Z"
last_activity: 2026-09-02
state_head: e9e33a0f9fee727ccefa0fa0588dfa224984bd45
progress:
  total_phases: 9
  completed_phases: 6
  total_plans: 49
  completed_plans: 48
  percent: 67
last_activity_desc: "**Phase 61 complete and verified (12/12)**; backend deployed and"
---

# Project State

## 🚧 CURRENT MILESTONE — v1.1 Unattended Session Runs (IN FLIGHT; Phase 61 complete 2026-08-30)

**Phases:** 53–61. Complete: 53, 54, 58, 59, **61**. Absorbed into 61 by operator decision
D-61-08: **55** (async run) and **56** (unattended pair pipeline) — neither is open work, do not
re-plan them. Open: **57 — the next phase** (ceilings, refusal-before-start, post-run proof) and
60 (review-lane authority, split out of 59). Phase 52 stays v1.0's and stays deferred.

**Phase 61 outcome (2026-08-30):** 6/6 plans, verification 12/12. All five cloud workflows
deployed and bounced (enrichment 114 → 118 nodes) and exercised by DISARMED runs only —
executions `12040`, and `12044`–`12047` for the substrate-3 fan-out. **Nothing was armed.
The first live UNATTENDED, credit-spending batch has NOT run and is gated on Phase 57
(D-61-08).** Requirements closed: INPUT-05, RUN-01, RUN-02, RUN-03, RUN-04, AFTER-02 — all in
`.planning/milestones/v1.1-REQUIREMENTS.md`, NOT the root `.planning/REQUIREMENTS.md` (which is
v1.0's). Suites at close: root python 3539 passed / 154 skipped; `node --test tests/n8n/*.test.mjs`
844 pass / 0 fail.

**Next action: plan Phase 57.**

### Original milestone-definition note (2026-08-25) — retained as history

Client UAT verdict: the flow is "incredibly halting" — one grant per send does not scale. One
session grant, then an unattended run through to HubSpot write. Requirements:
`.planning/milestones/v1.1-REQUIREMENTS.md`; MILESTONES.md carries the summary. Phases
planned 2026-08-25 as phases 53-57 (`.planning/milestones/v1.1-ROADMAP.md`); Phase 52 remains v1.0's. Client UAT of the operator write path recorded four gaps (`.planning/quick/260825-contact-company-association/UAT.md`) — G-2 is a blocker: `ALLOW_N8N_ARM` must be set in the session's shell environment, which an operator in Claude Desktop cannot do, so every write to date was landed by an admin from a terminal. Note the milestone's own framing: consent and throughput are two problems, and the
2-record request ceiling plus the 2,500/month execution budget mean auto-approval alone does
not deliver an unattended batch.

## ✅ PHASE 50 — ALL 6 PLANS COMPLETE, RETIREMENT DONE (D-24 override) (2026-08-14)

**Plan 05 closed the phase.** First live window (earlier 2026-08-14) switched WF1 off and hit
`CANNOT_DELETE_PROPERTY_IN_USE` archiving `lv_icp_tier` — HubSpot counts a disabled workflow's
action reference as "in use". The operator was presented three options and **selected deleting
WF1 outright, explicitly overriding D-08's "not deleted" prohibition (D-24)**. Second live
window, same date: WF1 deleted (204, independently re-read 404); `lv_icp_tier` archived on the
first retry (204, confirmed absent and present under `?archived=true`); `lv_icp_tier_derived`
relabelled to "ICP Tier" (D-15's fallback), verified by re-read and a two-point D-22 poll on 3
known records (B/D/C, byte-identical both reads). `scripts/check_schema_drift.py`'s
`RETIRED_FLOW_IDS` invariant flipped from "live-and-disabled" to "must be absent" (D-24
supersedes D-08's original semantics) — live post-retirement: `do_not_archive.ok=True,
exit_code=0`. D-07's gate re-run live post-archive still passes byte-identical
(`population=66 match=61 expected_mismatch=5 defect=0`) — an unexpected finding that an archived
property's per-record values remain readable when named explicitly in `properties=`, documented
as a live finding, not a standing guarantee. Rollback is now rebuild-from-JSON via `POST
/automation/v4/flows`, not a one-action re-enable — the proven manual-enrolment mechanism no
longer exists once WF1 is deleted (`docs/OPERATOR-TIER-ROLLBACK.md`'s 2026-08-14 amendment).
Reports/dashboards residual remains an accepted, disclosed, UNRESOLVED risk (no public API to
enumerate either) — not narrowed by this session. Second (and final, per D-16) authorised
company-record deviation spent: a 1-record armed recompute proof (Melbourne Racing Club
`9604614548`) confirmed the pipeline writes `lv_anti_icp_flag_num` onto a real record end-to-end
(the `"0"` branch directly observed; the `"1"` branch inferred from the shared derivation and
both-engine drift tests, not independently re-observed). Full record:
`.planning/phases/50-derived-tier-property/50-RETIREMENT-RECORD.md`.

**v0.9 milestone (ICP Rubric Calibration & Veto Remediation) plans all complete** — ready for
`/gsd-ship` review, not yet shipped by this session.

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

Phase: 62 (Suggest the contacts nobody named) — EXECUTING
**62-02 outcome (2026-09-02):** the role vocabulary — `scripts/role_vocabulary.py` (repo root,
  credential- and portal-guarded, mirrors `inventory_org_type_values.py`) sweeps live contact
  `jobtitle` values and clusters them with ONE cached Haiku call (gated behind
  `SPARSE_THRESHOLD`, never re-clustered per round), ranking the top `TOP_N_FAMILIES` (8) by
  recurrence. The committed `operator-claude-plugin/config/role_vocabulary.yaml` was seeded by
  actually executing the generic-fallback branch (`evidenced: false` at document AND every
  family level), so a sitting works before any operator runs the live inventory.
  `role_classify.py` gained `load_families()`/`offer_block()`/`chosen_families()`: the loader
  never separates the family list from its evidence status, `offer_block()`'s disclosure
  sentence for an un-evidenced vocabulary IS D-62-07's whole mitigation, and
  `chosen_families()` validates a round-level (never per-record) selection. SUGGEST-03 was
  AMENDED (not closed) in `v1.1-REQUIREMENTS.md` with an inline D-62-07 note; `ROADMAP.md`'s
  Phase 62 entry now distinguishes closed (SUGGEST-01/-02/-04/-05) from amended (SUGGEST-03) —
  the blanket `Closes SUGGEST-01..05` claim is gone. Full record:
  `.planning/phases/62-suggest-the-contacts-nobody-named/62-02-SUMMARY.md`.
Next: **62-05** (the operator-attended sitting: `skills/suggest-contacts/SKILL.md`, the
  unprompted post-batch offer, and the 0.36.0 release — wave 3, the last plan in this phase).
  Also open: **Phase 57** — ceilings, refusal-before-start, post-run proof. It gates the first
  live unattended, credit-spending batch (D-61-08), which has NOT run.
Armed state: nothing armed. 62-02 touched only local Python/YAML source, tests, and two
  planning docs — no network, no HubSpot credentials, no workflow JSON.
Suites at 62-02 close: operator-claude-plugin 2237 passed / 5 skipped; root
  `.venv/bin/python -m pytest -q` 3907 passed / 154 skipped; `node --test tests/n8n/*.test.mjs`
  862 pass / 0 fail (all >= wave 1 baselines).

### Retained — 62-01 outcome (2026-09-02)

the suggestion round's engine, tracer-led — `suggest_contacts.py`
  (`eligibility`, `discovery_plan`, `company_budget`, `next_candidates`, `no_candidates`,
  `select_people`, `synthesise_rows`, `round_artifact`, `partition_for_dispatch`) and
  `role_classify.py` (`classify_title`), pure orchestration with no HTTP client, no model
  call, no filesystem write. One company with zero associated contacts, discovered via the
  existing sitemap ladder (`url_fallback.py`, called never re-implemented), role-filtered,
  deduped against known contacts (D-62-18, pre-filter half), and synthesised into a row
  `extraction.validate()` accepts on identity group 2 — proved end to end in one offline
  tracer test. 24 new tests, 3 tasks each RED (failing test) then GREEN (implementation).
  Full record: `.planning/phases/62-suggest-the-contacts-nobody-named/62-01-SUMMARY.md`.

### Retained history — Phase 47.5 (v0.9, 2026-08-12)

*The remainder of this section is the v0.9 Phase 47.5 record, left in place unedited. It is
history, not current position.*

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

Last activity: 2026-09-02
  disarmed-proven. Next: Phase 57.

*Retained history — Phase 47 (v0.9). Previous status: Executing — Anthropic credit restored,
Plan 03 completed.*

  the live property-existence guard (found 19 missing D-09 metadata properties, resolved
  via operator-confirmed D-21 narrowing), one live research pass over all 17 pinned
  companies (47-RESEARCH-RESULTS.json), two live-discovered data-quality fixes
  (lv_org_type enum gate, lv_is_gambling_operator never derives org_type), and the
  mandatory disarmed dry-run (47-DRYRUN.md/47-RUN-REPORT.md). Zero live writes. The
  Anthropic billing outage recorded in 47-BLOCKED.md is resolved -- credit confirmed
  restored before Plan 03 resumed and completed. Plan 04 (armed run, autonomous: true
  per D-22) is next.

Progress: [███████░░░] 67% — v1.1: 53/54/58/59/61 complete; **57 in progress (Plan 01 done,
RUN-05 closed)**; 60 open; 55 and 56 absorbed into 61; 52 deferred (v1.0). (The old
`97% (v0.9 phase 47.5 of 46-49)` bar was a v0.9 figure and is superseded.)

## Session

**Last session:** 2026-09-01T23:34:01.864Z
**Stopped at:** Completed 62-02-PLAN.md (role vocabulary: portal jobtitle clustering, disclosed generic fallback, SUGGEST-03 amended not closed)
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
| Phase 50 P06 | ~110min | 5 tasks | 22 files |
| Phase 50 P02 | ~13min (across checkpoint pause) | 3 tasks | 3 files |
| Phase 50 P04 | 35min | 2 tasks | 3 files |
| Phase 50 P05 | 55min | 1 tasks | 7 files |
| Phase 50 P05 | 35min | 1 tasks | 9 files |
| Phase 51 P01 | ~15min | 3 tasks | 5 files |
| Phase 51 P02 | ~25min | 3 tasks | 5 files |
| Phase 51 P03 | ~15min | 2 tasks | 5 files |
| Phase 51 P03 | 4h | 3 tasks | 30 files |
| Phase 53 P01 | 4min | 3 tasks | 5 files |
| Phase 53 P02 | 35min | 3 tasks | 3 files |
| Phase 53 P03 | 12min | 3 tasks | 7 files |
| Phase 58 P01 | ~35min | 3 tasks | 6 files |
| Phase 58 P02 | ~10min | 3 tasks | 4 files |
| Phase 58 P03 | ~15min | 4 tasks | 9 files |
| Phase 58 P04 | 25min | 3 tasks | 5 files |
| Phase 58 P05 | ~75min | 4 tasks | 14 files |
| Phase 58 P06 | ~110min | 4 tasks | 16 files |
| Phase 54 P01 | ~35min | 3 tasks | 6 files |
| Phase 54 P02 | ~25min | 3 tasks | 7 files |
| Phase 54 P03 | ~35min | 3 tasks | 3 files |
| Phase 54 P04 | 40min | 3 tasks | 3 files |
| Phase 54 P05 | 25min | 3 tasks | 3 files |
| Phase 54 P06 | 25min | 3 tasks | 8 files |
| Phase 54 P07 | 8min | 1 tasks | 2 files |
| Phase 59 P01 | 35min | 3 tasks | 6 files |
| Phase 59 P02 | 12min | 2 tasks | 3 files |
| Phase 59 P03 | 45min | 3 tasks | 7 files |
| Phase 59 P04 | 20min | 2 tasks | 5 files |
| Phase 59 P05 | 50min | 3 tasks | 9 files |
| Phase 59 P06 | ~40min | 3 tasks | 10 files |
| Phase 59 P07 | 25min | 3 tasks | 7 files |
| Phase 59 P08 | ~35min | 3 tasks | 10 files |
| Phase 59 P09 | ~35min | 3 tasks | 10 files |
| Phase 61 P02 | ~90min | 3 tasks | 17 files |
| Phase 61 P03 | ~55min | 3 tasks | 16 files |
| Phase 61 P04 | ~2h | 4 tasks | 16 files |
| Phase 61 P01 | 45min | 1 tasks | 2 files |
| Phase 61 P05 | ~35min (T1-3) + recording pass | 4 tasks | 12 files |
| Phase 61 P06 | this session | 5 tasks | 18 files |
| Phase 57 P01 | 90min | 4 tasks | 18 files |
| Phase 57 P04 | unknown | 3 tasks | 5 files |
| Phase 57 P02 | 55min | 3 tasks | 9 files |
| Phase 57 P03 | 90min | 3 tasks | 11 files |
| Phase 60 P01 | ~40min | 3 tasks | 6 files |
| Phase 60 P02 | 14min | 2 tasks | 6 files |
| Phase 60 P03 | ~11min | 2 tasks | 4 files |
| Phase 60 P04 | ~15min | 3 tasks | 9 files |
| Phase 62 P01 | 35min | 3 tasks | 3 files |
| Phase 62 P04 | 55min | 2 tasks | 15 files |
| Phase 62 P03 | 25min | 3 tasks | 5 files |
| Phase 62 P02 | 22 min | 3 tasks | 6 files |

## Decisions

- [Phase ?]: D-03 -> D-04: live probe found a null term inside an UNTAKEN calculation_equation branch still blanks the whole result; coalesce(lv_icp_fit_score, -1) forced into lv_icp_tier_derived's formula
- [Phase ?]: lv_icp_tier_derived created live; all 4 stuck records (9605273630, 9604738976, 17696004613, 19100977027) confirmed reading B with zero writes; live search confirms 646 never-enriched companies now read Unscored
- [Phase ?]: Live discovery: HubSpot's Properties API canonicalizes stored calculationFormula text on create (= -> equals, double -> single quotes, inserted line breaks) -- not byte-identical to the submitted literal though functionally equivalent; future formula-pin tests must compare against the live-read text, not the pre-creation literal
- [Phase ?]: D-07's gate FAILS live: veto guard on lv_icp_tier_derived never fires for any of 6 real anti_icp_flag=true records (a defect never verified before this run); D-06/D-08 stay blocked
- [Phase ?]: TIER-01 left NOT complete (ladder not verified against real records per its own text); TIER-02 marked complete (null semantics settled and disclosed independent of the veto bug)
- [Phase ?]: D-16 spent exactly once (backfill-scoped): lv_anti_icp_flag_num=1 backfilled onto 6 checkpoint-authorised vetoed companies; D-21 reverses D-04 (uncoalesced formula ships, ~646-record Unscored flip undone); TIER-01 stays Blocked pending Plan 04/05's decision on the residual Coffs Harbour defect (WINDOWS.md id 14)
- [Phase ?]: [Phase 50-02]: Saved views recorded CHECKED and MIGRATED on operator's dated 2026-08-14 attestation (not itemised); reports/dashboards left an explicit UNCONFIRMED residual carried forward to Plan 05's one-way retirement gate.
- [Phase ?]: [Phase 50-02]: Post-migration re-run of scripts/sweep_tier_dependents.py (D-13) found no delta from the pre-migration scripted findings (0 lists / 10 flows / 5 WF1-only findings) -- expected, since the script cannot see saved views.
- [Phase ?]: D-18 rollback: portal-UI manual enrolment proven live against Melbourne Racing Club 9604614548 while WF1 was on; primary mechanism marked PROVEN in docs/OPERATOR-TIER-ROLLBACK.md
- [Phase ?]: Reports/dashboards half of D-13's dependent sweep remains UNCONFIRMED -- carried unresolved into Plan 05's one-way retirement decision
- [Phase ?]: Phase 50: WF1 switched off live (D-08 complete); lv_icp_tier archive blocked by HubSpot's property-in-use rejection (a disabled workflow's action still counts as usage) -- escalated per D-11 rather than forced through by deleting or editing WF1.
- [Phase ?]: D-24: operator overrode D-08, WF1 (4625147345) deleted outright (not merely disabled) after lv_icp_tier's archive was rejected live (CANNOT_DELETE_PROPERTY_IN_USE); archive then succeeded and lv_icp_tier_derived was relabelled 'ICP Tier'
- [Phase ?]: Second D-16 deviation spent: armed 1-record recompute proof (Melbourne Racing Club 9604614548) confirms the pipeline writes lv_anti_icp_flag_num onto a real record end-to-end (0->'0' branch directly observed; '1' branch inferred from shared derivation + drift tests, not independently re-observed)
- [Phase ?]: Phase 51 Plan 01: measured ZoomInfo companies/enrich per-match cost live (100 hundredths, vs the 108 documented floor) via --measure-cost, retiring research Assumption A1; credits_per_match_hundredths_used is max(measured, fallback)
- [Phase ?]: Sample size sized to 10 (not the research doc's default 12) after Task 2's live sizing read discovered MAX_WEB_RESEARCH_PER_RUN=10 in the live .env -- respected the operator's configured research budget rather than overriding it.
- [Phase ?]: select_never_scored_sample fixed to sort by numeric id (int(r['id'])) instead of lexicographic string order -- this portal mixes 10- and 11-digit HubSpot ids, and the old sort both misordered rows and could select a different sample slice.
- [Phase ?]: Phase 51 Plan 03: 51-BEFORE-SNAPSHOT.json committed (66 already-scored companies, ascending numeric id, 18 properties each) as the read-only baseline Phase 52's closing diff is taken against; scored(66)+never-scored(646)=712 live-reconfirmed
- [Phase ?]: Phase 51 Plan 03: COVERAGE.md and 51-VALIDATION.md reconciled against shipped code -- zero divergence, all 8 automated per-task rows green; Task 3 (operator approval, gate=blocking) returned unanswered, Phase 52 does not open until approved
- [Phase ?]: Phase 51 Plan 03 checkpoint round 1 (operator ruling): fixed HubSpot/ZoomInfo country-conflict guard first (HubSpot's own country wins on disagreement, conflict recorded visibly), then re-ran the dry-run sample diversified (industry-stratified, deterministic) -- tier B x2/D x6 observed, Gold Coast Turf Club confirmed fixed live (D->B). FILL-04's third disposition explicitly deferred to Phase 52 planning per operator ruling, recorded in ROADMAP.md
- [Phase ?]: Checkpoint round 2: Gold Coast attribution corrected (lv_produces_content flip caused the D->B move, not the country guard alone); field-policy gate shipped and empirically exonerated as the reproducibility root cause; majority-of-3 research vote shipped instead because claude-sonnet-5 rejects an explicit temperature; live before/after measurement shows both Run 2 Tier B rows rest on a minority draw and revert to Tier D under the majority answer -- no Tier A/B genuinely observed; regenerate-or-not put to the operator
- [Phase ?]: Checkpoint round 3: Sonnet judge escalation wired into the dry-run research lane (CLAUDE.md SS15.1, reusing src.validator_sonnet.validate_conflict_with_sonnet verbatim; fixed a shared temperature=0 bug that 400s on claude-sonnet-5); Run 3 predictions regenerated over the same 8 companies at zero additional ZoomInfo cost. Result: Gold Coast and Warwick both settle at Tier C (unresolved conflict left absent, clears no hard veto), not the Tier D expected -- reported as observed, not smoothed. No Tier A/B produced across three runs. 27 Anthropic calls this round (24 research + 3 judge), zero ZoomInfo credits
- [Phase ?]: Checkpoint round 4: unresolved lv_produces_content conflicts (Warwick, Gold Coast, Tasmanian) now flagged lv_icp_needs_review=true with a specific reason in the predicted payload, distinguishing them from genuinely-assessed Tier C/D. lv_icp_needs_review confirmed live (contra CLAUDE.md SS4.0's stale never-created claim); lv_enrichment_review_reason reused for the reason text. Zero additional API spend -- payload-shape change over Run 3's settled results. Run 3 pre-flag archived as *-run3-judge-escalation.json
- [Phase ?]: Checkpoint round 5: OPERATOR APPROVED the dry-run artifacts -- Phase 51 Plan 03 (and Phase 51) complete after five checkpoint rounds. n8n's matching country blind spot (normalizeProviders.js:420-422, same defect the dry-run's country guard fixes) recorded as tracked debt (WINDOWS.md id 19) rather than fixed -- explicit operator ruling not to touch n8n this phase (zero n8n changes/executions is v1.0's binding constraint). Final totals: 13 ZoomInfo credits, 103 Anthropic calls, zero HubSpot writes, zero n8n executions
- [Phase ?]: [Phase 53-01]: D-53-01 landed: the interactive arm's authority is config_gate.WRITE_GRANT_SETTINGS_KEY ('allow_write_grants') in operator.local.json, compared by identity against the JSON boolean true. ALLOW_N8N_ARM is unchanged and remains the sole authority for headless/cron (scheduled_arm.py, unedited).
- [Phase ?]: [Phase 53-01]: GRANT-03 is enforced inside n8n_arming.arm_for_dispatch's grant branch, before any transport is constructed, via the single write_grant.covers implementation -- not only at a helper a caller could bypass.
- [Phase ?]: [Phase 53-01]: The grant is a plain JSON-shaped dict held in the conversation only: no file, no env var, no default (GRANT-06/D-53-03). Per-send armed windows are retained, so the guaranteed disarm is untouched.
- [Phase ?]: [Phase 53-02]: D-53-02 landed as DISCLOSURE, and the block says so where the operator reads it: write_grant.envelope() computes the four GRANT-02 figures out of cost_guard + chunking (no second cost model), labels each measured/projected/unconfigured, and states plainly that the projection is against the CONFIGURED monthly allowance rather than what is left of it this month. Phase 57 still carries all the actual spend protection. SUPERSEDED by D-57-00, Phase 57 -- see [Phase 57-01] below: the ceiling now refuses before start, not just discloses.
- [Phase ?]: [Phase 57-01]: D-57-00 supersedes D-53-02 for every run this milestone covers. D-53-02 recorded that a grant's computed ceiling is disclosure, not constraint -- correct while a human watched every send. Phase 57 makes the execution allowance a conservative binding preflight refusal and a pre-send mid-run stop. The prior behaviour remains historical context, not current behaviour. Sampling limits and the retention caveat are disclosed rather than pretended away.
- [Phase ?]: [Phase 53-02]: GRANT_04_REASONS is exactly GRANT-04's five and is pinned BY NAME; guardrail B's two closes are their own constants in GUARDRAIL_B_REASONS. Folding "two consecutive disarm failures" into one of the five would misreport the close the operator most needs to read correctly. close_grant RAISES on free text.
- [Phase ?]: [Phase 53-02]: GRANT-05 bites at the next SEND, proven by driving a real 3-chunk dispatch_plan with a mid-run revoke and asserting every chunk STILL ran. The drafted two-hand-calls test was refused: it would have passed while GRANT-05 was entirely unimplemented.
- [Phase ?]: [Phase 53-02]: Both proposed guardrails are working code and neither is switchable (T-53-12). A is plan_grant's MANDATORY preflight and is offer-only (its transport log is pinned to reads only); B's two closes ATTEMPT a disarm through the ungated n8n_arming.disarm, carry the verdict, and CLOSE EVEN WHEN THAT DISARM FAILS.
- [Phase ?]: [Phase 58-01]: domain and website kept as two separate canonical company props (not merged) -- mirrors CLAUDE.md's HubSpot company fixture shape where both properties exist independently
- [Phase ?]: [Phase 58-01]: dedupe()/D-07 made record-type-aware by splitting the accepted list into per-type sublists and calling dedupe() once per sublist with explicit index remapping on reassembly, rather than adding a record_type parameter to dedupe() itself
- [Phase ?]: [Phase 58-02]: Live execution 11972 confirms mode='propose' rides the recompute lane to Decide Company Action, forcing action=proposed with no write -- the traced claim from 58-RESEARCH.md is CONFIRMED, not merely traced
- [Phase ?]: [Phase 58-02]: Operator (2026-08-26) selected defer-residual over extend-now -- backend research node not extended to seek domains this phase; residual named against INPUT-02 for 58-04 to read
- [Phase ?]: Phase 58-03: Task 4 walk verdict APPROVED (operator, 2026-08-26, plugin 0.19.0 marketplace 16b8641) -- no wording flagged; LinkedIn-URL-input and reject-a-row moves not exercised live, covered by Tasks 1-3 automated tests instead
- [Phase ?]: Phase 58-03: operator ruling on walk finding -- native industry/country/city/employee-count promotion gap folds into Phase 58 as orchestrator-planned gap-closure plan 58-05; CLAUDE.md Section29 numberofemployees never-write ban LIFTED for this lane only, scoped fill_blank_only provider-sourced
- [Phase ?]: 58-04: research-line pricing is default-on and declinable; a struck line converges on the existing DECLINE_DOMAIN sentinel (no new bucket). INPUT-02 residual (backend research node not extended to seek a domain) remains deferred per operator decision, 2026-08-26.
- [Phase ?]: Phase 58-05: Task 4 superseded by events -- operator's own walk dispatch (exec 11983) armed a full enrich before Task 4 resumed, landing the plan's native fields but also flipping a false Non-ANZ veto via an unwatched ZoomInfo region conflict (root cause scoped to gap-closure plan 58-06); Task 4 executed instead as a corrective window (scripts/fix_sfv_region.py, commit 11b17c0), clearing the veto without re-running the same wrong provider match
- [Phase ?]: Phase 58-06: Task 4 checkpoint resolved 2026-08-26 -- size disagreements stay flag-only permanently (RO-2 untouched, no follow-up); forensic's 70-vs-75 confidence rejection accepted as correct behavior, region min_confidence stays 75, no follow-up opened. Plan complete; INPUT-01/03/04 ticked in v1.1-REQUIREMENTS.md, INPUT-02 stays open per its recorded defer-residual.
- [Phase ?]: 54-01: envelope() single-record execution count DIFFERS from live measurement (measured 1, projected chunk_count+record_count=2) -- reported, not reconciled; multi-chunk case (WINDOWS id 26) still open
- [Phase ?]: 54-01: anthropic_usd basis relabelled PROJECTED (was falsely MEASURED) per OP-54-05; SJ-3 double pass recorded WINDOWS id 27 per OP-54-02, deliberately left unfixed
- [Phase ?]: 54-02: needs_match_review -> held, proposed -> previewed added to report_enrichment._ACTION_TO_OUTCOME, neither a success; both reasons state the second-pass cost
- [Phase ?]: 54-02: no operator-facing look-only surface exists today for the companies propose=True form (only the Phase 58 spike uses it) -- confirmed by grep, no wording invented for it
- [Phase ?]: 54-02: G-3 amended in place (not overwritten) in v1.1-REQUIREMENTS.md and v1.1-ROADMAP.md, pointing at 54-MEASUREMENT.md and naming the two legitimate two-pass shapes plus the SJ-3 residual (OP-54-02)
- [Phase ?]: [Phase 54-03]: Task 2 operator decision engine-only (robert.li@australiagtm.com, 2026-08-27) -- contacts approve now writes via a policy-injectable reviewApply engine + already-applied clear branch; no contacts candidate producer built (named residual for 54-04/54-05)
- [Phase ?]: 54-04 completed across two executor agents; the first was killed by the harness watchdog mid-Task-3 (600s idle) after correctly staging the SKILL.md edit -- an execution interruption, not a defect in the deployed artifact. Deploy record confirmed: contacts approve branch live, disarmed (write flag false, both allowlists empty), 0 executions consumed.
- [Phase ?]: 54-05: reported verify_decision's literal failed verdict rather than reinterpreting -- one mismatched key is a HubSpot text-property empty-string-vs-null round-trip, not a real write defect
- [Phase ?]: 54-06: Widened contacts review-decision baseline to all twelve field_policy.yaml keys with queue read kept narrow (WR-02); fixed four stale pre-54-03 comments including the deployed jsCode and operator-facing sticky note (WR-01); scoped reviewApply.js's enum guard to company-only with a pinned drift-guard reason (WR-03); fixed the same false-permanence defect in review-triage/SKILL.md (IN-02); deployed disarmed and proven by independent re-GET
- [Phase ?]: WR-04: Anthropic-spend sentence dropped both bound-words ('worst case' and 'a floor') for a single 'projection' framing matching cost_rates.json's own citation; pinning test rescoped to the single sentence line.
- [Phase ?]: 59-01: crash-survival test injects the process-kill RuntimeError via enrichment.dispatch_enrichment (not the transport's .post()), since dispatch_enrichment converts every transport exception into a caught-and-continued DispatchError
- [Phase ?]: 59-01: dispatch_plan gained only a keyword-only run_id, no path= plumbing; tests redirect written_records.written_records_path via monkeypatch to isolate the artifact
- [Phase ?]: D-59-04: root tests/conftest.py autouse fixture gates the credential strip on RUN_LIVE_PARITY (repo's existing env-var live-test convention) rather than a nonexistent pytest 'live' marker -- deviation recorded in the conftest docstring itself
- [Phase ?]: [Phase 59-03]: SKILL.md carried a third, unnamed mention of D-53-05's retired warning (step 1 preamble) beyond the plan's read_first scope; fixed in the same Task 2 commit after the re-pointed test caught it. Recorded-edit notes must paraphrase retired wording, never quote it verbatim, or the note trips its own negative pin (enrich-records F3 precedent followed).
- [Phase ?]: [Phase 59-04]: D-59-06 SessionStart hook shipped -- non-blocking session-start note discloses run-to-completion behaviour; dispatch_plan stays grant-unaware, revocation test untouched; content proven by subprocess contract test, host delivery recorded as unperformed manual check
- [Phase ?]: [Phase 59-05]: D-59-08 gate inventory decided 16 gates -- GATE-01 (extraction.py identity gate) converted this plan, GATE-02..06 named candidates for 59-06, 8 NOT-APPLICABLE with stated no-legitimate-resolution-source reasons, 2 ALREADY-CONVERTED (company_domain.py, preingest unmatched bucket)
- [Phase ?]: [Phase 59-05]: extraction.py identity gate converted refuse-and-stop to refuse-and-classify-resolvable, additive to rejected; RESOLUTION_SOURCES closed vocabulary (hubspot_lookup/operator_statement/provider_result/same_row_derivation) rejects any resolutions entry naming an outside source or a field the row lacks; test_no_invention_structural.py extended (4 new forbidden substrings) never relaxed
- [Phase ?]: [Phase 59-06]: RESOLUTION_SOURCES moved to a new dependency-free resolution_sources.py module -- a live test proved enrichment.py importing it directly from extraction.py is a real circular import (enrichment -> extraction -> preview -> preview_enrichment -> chunking -> enrichment); extraction.RESOLUTION_SOURCES is the same re-exported object
- [Phase ?]: [Phase 59-07 gap closure]: chunking.dispatch_plan's RecordSpecError handler now binds the exception and carries str(e)+resolvable onto ChunkResult, closing the severed integration link that kept GATE-02..GATE-05's D-59-08 payload from reaching the operator; 59-GATE-INVENTORY.md corrected to credit delivery to 59-07, not 59-06 alone
- [Phase ?]: [Phase 59-08]: D-59-09 implemented — written_records.written_records_path now keyed by run_id (written_records-<run_id>.json), append_chunk's run-id-mismatch replace branch deleted, load() globs written_records*.json and unions per-run entries stamped with run_id; no lock, no merged index (both operator-rejected).
- [Phase ?]: [Phase 59-08]: D-59-07 gap 4 closed — write_grant._consequence's written-records disclosure moved out of the len(lane_names) > 1 branch so it fires for every grant (one lane or two); plan_grant's authorization control untouched (git diff confined to _consequence + import).
- [Phase ?]: D-59-10 (operator, 2026-08-29): a written-records bookkeeping failure never stops a dispatch -- caught in dispatch_plan's loop like DispatchError already is, recorded in DispatchOutcome.written_records_failures (one guard for a raised WrittenRecordsError AND append_chunk's falsey OSError return), and the run keeps sending; incomplete-list surfaced on 4 surfaces (DispatchOutcome, scheduled_arm's outcome+run_id, non-zero exit code without renaming the outcome, both skills' relay).
- [Phase ?]: [61-02] linkedin match lane: dedicated 3-outcome summarizeMatch arm (0/1/>1 verified hits), never joined to the two-outcome fetch_by_id/email arm (REVIEW-C4)
- [Phase ?]: [61-02] search-variant set stored as a sibling row field (linkedin_url_variants), not inside identity_keys, to avoid perturbing an out-of-scope exact-shape test
- [Phase ?]: [61-02] Python oracle ORs lv_linkedin_url/hs_linkedin_url by two sequential hs_search calls, unioned by contact id; src/hubspot_client.py deliberately untouched (REVIEW-C6)
- [Phase ?]: [61-02] MATCH_LOOKUP_KEYS widened from 4 to 5 (added linkedin_url); operator-claude-plugin bumped 0.28.6 -> 0.29.0
- [Phase ?]: Phase 61 Plan 03: linkedin_url added as third required_identity group in both YAML copies + columnMap.js, pinned by a YAML-driven parity test; extraction.py's rejection message now composed from identity_groups() rather than hard-coded; enrich-before-ingest/SKILL.md documents a strong-key-only row proceeding without a company and a waterfall find routed through the existing D-59-08 resolutions/provider_result loop
- [Phase ?]: 61-04: run_manifest.load() kept byte-unchanged; load_scoped() added instead of widening it, since 61-05 (the stated consumer) doesn't yet exist to require the wider shape
- [Phase ?]: 61-04: held_queue.py is ONE global file (not per-run like written_records.py) -- D-61-07's 'one review queue, cleared in a single pass' is a durable backlog across runs
- [Phase ?]: Operator decided run-state store for async batch runs: HubSpot object (run handle + progress) plus run_manifest.py (per-row verdicts); all six previously-unresolved 61-01 premises (P-05,P-07,P-08,P-09,P-10,P-13) closed by n8n docs + a live disarmed probe, none deferred
- [Phase ?]: Substrate 1 (async_ack opt-in on Respond node) selected over substrate 3 (self-referencing Execute Workflow) at this plan's scale; substrate 3 stays the disclosed 61-06 scale-up path, narrowed by P-14 to publish-viable-but-runtime-unproven
- [Phase ?]: run_id minted client-side before submit and passed into dispatch_plan's existing run_id keyword (REVIEW-C14) — no new handle, no signature change
- [Phase ?]: Resume path keeps run_manifest.load()'s degrade-whole rule unchanged; report path independently classifies the manifest file (absent/parseable/anomalous/wrong-run) and discloses which in words (REVIEW-C15/08)
- [Phase ?]: Per-chunk manifest persistence is load-accumulated-document, merge, save-whole-document — bounding crash replay exposure to one chunk (REVIEW-C13)
- [Phase ?]: Task 4 deploy scope widened to all five cloud workflows with operator's informed consent, because the live instance was four plans behind 61-05 alone
- [Phase ?]: Task 4 checkpoint resolved: operator approved offline pipeline and authorized Task 5's disarmed deploy + runtime proof; Phase 57's gate on the first live unattended run is unchanged
- [Phase ?]: Task 5: substrate-3 self-referencing fan-out proven live (executions 12044-12047, disarmed) -- runs, terminates with no depth supplied, stays correlatable; a Rule 1 multi-item bug was found and fixed by the proof's own first attempt
- [Phase ?]: [Phase 57-01]: D-57-00 supersedes D-53-02 -- the grant's ceiling now refuses a CEILING_OVER batch before anything is armed and stops mid-run before the breaching chunk, rather than only disclosing the projection.
- [Phase ?]: [Phase 57-01]: Task 2 checkpoint (option-a) -- measured sampled:true live via listing_exhausted (allowance 2500, spent 134, remaining 2366) after Task 1's exhausted-listing fix landed; the first pre-fix reading of sampled:false was a config-gap artifact (n8n_monthly_execution_allowance absent from the live plugin config), not an account limitation, and is superseded by this measurement.
- [Phase ?]: [Phase 57-01]: CEILING_UNKNOWN never refuses (D-57-02 preserved) but is no longer double-off -- runbooks self-bound execution_ceiling to the batch's own projected_executions instead of None when the monthly allowance can't be sampled.
- [Phase ?]: Phase 57 Plan 04 Task 2 checkpoint: operator selected option-run; live ZoomInfo balance probe returned readable (9381 credits), closing G-4's ZoomInfo half by observation with no code fix
- [Phase ?]: 57-02 Task 1 (operator): option-b — split written vs write_attempted by what the id echoed back actually proves
- [Phase ?]: [Phase 57-03]: Task 1 checkpoint ruling (operator, this plan): option-a selected -- auto-split queues WORK ONLY, never AUTHORITY (D-57-05, GRANT-06). remainder_queue.py holds re-sendable chunking.failed_batch()-shaped specs; write_grant.split_for_allowance projects the grant scope FROM the split work (never a separately-ordered ids/domains sequence, REVIEW-57-H1). Each split run still opens its OWN grant -- the queue confers no authority and nothing picks it up automatically. 57-03 is the declared owner of this STATE.md record per M-2.
- [Phase ?]: D-60-01/D-60-02: review is now a third grantable lane; one grant can span enrichment, contacts and review — 60-01 tracer proved the full path arm/decision/disarm with no shell env var
- [Phase 60]: Guardrail A widened to sorted(OVERLAYABLE_FLAGS) (5 flags, was DISPATCH_FLAGS' 4) so a stuck-open ALLOW_HUBSPOT_REVIEW_WRITES refuses the next grant open by name; WRITE_ENABLING_FLAGS appended the review flag last (order load-bearing).
- [Phase 60]: write_grant.authorize_review_batch(grant) returns the grant's own record_ids/record_domains on purpose (D-60-06) -- the deliberate divergence from authorize_send, which refuses to return a record list so a per-send window cannot widen to the whole grant.
- [Phase 60]: preflight_before_send narrowed on the review lane only (MEDIUM-1): liveness excludes the review flag, derived from WRITE_ENABLING_FLAGS, so the batch window's own arm cannot trip its own pre-flight; a live dispatch flag on the review workflow still closes the grant.
- [Phase 60]: D-60-08: a review decision now lands in the run's written_records-<run_id>.json artifact via a new classify_review_item mapping the review endpoint's seven outcome words onto the existing eight-word vocabulary; the append is gated on result["available"] (not merely run_id is not None) so a raising/unreachable POST leaves no artifact entry, matching dispatch.py's raise-before-append and chunking.dispatch_plan's DispatchError-continue precedent — resolved via advisor consult after the plan's <action> and <behavior> text diverged on this point.
- [Phase ?]: Phase 60 sealed: the review lane is grantable end-to-end, operator-facing docs corrected, plugin released as v0.35.0 (push and marketplace-clone refresh still the operator's own action).
- [Phase 62]: select_people's dedupe pre-filter runs before the role filter; the D-62-18 already-associated check never even reaches role classification
- [Phase 62]: 62-04: sourceByField resolves into both the provenance entry's source and the decisions row's source_provider, mirroring confidenceByField's dual-write so the two can never disagree.
- [Phase 62]: 62-04: num_associated_contacts was added to both HS_CO_SEARCH_BODY_EXPR (local_live) and ENRICH_COMPANY_SEARCH_PROPERTIES_CSV (the cloud builder's actual property list) after tracing that the plan's read_first named only the former, which never reaches wf_enrichment_cloud.json.
- [Phase 62]: 62-04: preingest.py's OUTCOME_CONTRACT_VERSION allowlist was widened to {1, 2}, not moved to {2}, since this plan regenerates but does not deploy the n8n JSON -- the deployed backend still stamps 1 until an operator deploys it separately.
- [Phase 62]: D-62-11 locked via checkpoint: the suggestion round's cost folds into the SAME opening grant envelope (one-envelope), not a separate spend confirmation. — Human operator answer at a gate=blocking-human checkpoint; one disclosure, one yes for the whole session; over-budget suggestion rounds now refuse pre-start via Phase 57's existing CEILING_OVER split offer.
- [Phase 62]: D-62-07 implemented: role_vocabulary.py's committed seed is the generic-fallback branch's actual output (executed, not hand-typed), and role_classify.offer_block()'s disclosure sentence is what SUGGEST-03's amendment requires operators to see.

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
- lv_icp_tier archive blocked: HubSpot rejects DELETE with CANNOT_DELETE_PROPERTY_IN_USE while WF1's actions reference the property, even disabled. Resolution requires a fresh operator decision among 3 options documented in 50-RETIREMENT-RECORD.md.

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 260823-ono | Metro peak-body named-account floor: `lv_named_account_score_floor` (number) read by `lv_icp_fit_score` FORMULA-F; ATC/MRC/SSR/BRC/Perth at 60/B live; enum rejected (D-20 reconfirmed) | 2026-08-23 | f1105dd | Verified | [260823-ono-metro-peak-body-override-rule-tier-atc-m](./quick/260823-ono-metro-peak-body-override-rule-tier-atc-m/) |
| 260826-20w | Permissive contact enrichment: email reclassified `fill_blank_only`@80 (was `manual_protected`@95), promotes into a blank + flags `lv_enrichment_needs_review`; five HubSpot-native location properties (city/state/country/hs_state_code/hs_country_region_code) added to the waterfall; live proof execution 11958 | 2026-08-26 | a583c29 | Verified | [260826-20w-permissive-contact-enrichment-location-f](./quick/260826-20w-permissive-contact-enrichment-location-f/) |
| 260829-hjm | Sequence-inventory meta-test (`test_skill_sequence_coverage.py`): extracts every documented `module.function(...)` SKILL.md call sequence, fails when unclaimed by `COVERED`/`NOT_A_PIPELINE`/`GRANDFATHERED_UNCOVERED`; census 8 identities (2 covered, 1 not-a-pipeline, 5 grandfathered with named reasons); guard bite demonstrated live (fake block appended/reverted) and permanently (synthetic unit test); zero production-code changes; plugin 0.28.2 -> 0.28.3 | 2026-08-29 | 03bf28c | Verified | [260829-hjm-skill-sequence-composition-guard](./quick/260829-hjm-skill-sequence-composition-guard/) |
| 260829-lg3 | **P2 closed — all five grandfathered sequences now covered.** 4 new composition tests drive the joins the registry said nothing drove: `authorize_send`/`authorize_ungranted_send` -> `armed_window` -> `dispatch.dispatch` INSIDE the window (one shared test closing both the `contact-upload` and `enrich-before-ingest` identities); the `resolve_providers` -> `plan_chunks`/`chunk_ceiling` -> authorize -> `armed_window` -> `dispatch_plan` waterfall (+`merge_enriched` for enrich-before-ingest); and `chunk_ceiling(key='max_rows_per_match_request')`'s real return through `plan_chunks` -> `match_batch` -> `classify_matches`. `GRANDFATHERED_UNCOVERED = {}`, `MAX_GRANDFATHERED = 0` (shrink-only contract honoured). Every falsifiability check independently re-run by reviewer AND verifier, not merely re-read. Zero production-code changes, zero `SKILL.md` edits, zero live calls. Plugin 0.28.3 -> 0.28.6 | 2026-08-29 | d1a2881 | Verified | [260829-lg3-close-the-five-grandfathered-skill-md-co](./quick/260829-lg3-close-the-five-grandfathered-skill-md-co/) |

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

- Run `/gsd-plan-phase 57` — Ceilings, refusal-before-start and post-run proof. It is the last
  gate on the first live unattended, credit-spending batch (D-61-08) and is the missing producer
  for GRANT-04's `ceiling_breach` and requirements RUN-05 / AFTER-01 / AFTER-03.

- ~~Run /gsd-plan-phase 50 to plan Derived Tier Property (context gathered 2026-08-13,
  `.planning/phases/50-derived-tier-property/50-CONTEXT.md`)~~ — superseded; Phase 50 completed
  2026-08-14.

## Deferred Items

Items acknowledged and deferred at the v0.9 milestone close on 2026-08-19
(`closeout_type: override_closeout`). All six phases were `complete` + `verified passed`;
these are open *artifacts*, not unverified work.

| Category | Item | Status |
|----------|------|--------|
| todo | 2026-08-04-enrichment-throughput-ceiling | pending — v0.8-era; 82% of a full run is two sequential Anthropic calls. Reviewed during Phase 50 discussion and explicitly not folded (that phase made zero Anthropic calls). |
| todo | 2026-08-04-sweep-crontab-pins-a-versioned-plugin-path | pending — v0.8-era operator-plugin packaging fragility. Unrelated to v0.9's scope. |
| todo | 2026-08-04-uat-22-names-aliases-the-mapping-lacks | pending — v0.8-era contact-upload column mapping. Unrelated to v0.9's scope. |
| context-questions | Phase 46 CONTEXT open questions (3) | answered in-phase by 46-SIMULATION-REPORT.md and 46-DECISION.md; the CONTEXT block was never edited to mark them closed. Documentation lag, not open work. |

Also carried forward: `WINDOWS.md` has 11 open entries. Ids 9–12 and 14 are permanent by
nature (the archived `lv_icp_tier` values are frozen-wrong and never self-correct). Ids 17
and 18 are genuinely fixable and should be closed rather than waived before any `/gsd-ship`,
which blocks while `open_count > 0`.
