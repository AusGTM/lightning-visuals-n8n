# 48-RUN-REPORT.md — Phase 48 actuals, window accounting, and requirements status

Phase 48, plan 06. Closes COVER-02's "reported after" half against `48-COST-ESTIMATE.md`'s
"estimated before" half, discloses every ceremony actually spent against D-06's declaration, and
states Phase 48's share of COVER-01/COVER-02 without claiming closure that is jointly Phase 47's
to complete.

Every figure below is sourced from a committed artefact — `48-POPULATION.json`, `48-BEFORE.json`,
`48-AFTER.json`, `48-ARM-RECORD.md`, `48-DEPLOY-PROOF.md`, `48-COST-ESTIMATE.md` — not from
recollection.

---

## Population

`48-POPULATION.json` (plan 48-01, derived 2026-08-12) re-ran the exact `lv_icp_fit_score
HAS_PROPERTY AND lv_org_type NOT_HAS_PROPERTY` filter live and returned 5 ids:
`15008671672`, `17317381378`, `17317850381`, `20538284384`, `20943964946` — **count 5,
identical to `48-CONTEXT.md`'s 2026-08-12 snapshot (66 scored, 5 blank org type), drift: false.**

The population was re-derived a second time at write time, inside plan 48-05 Task 1 (recorded in
`48-ARM-RECORD.md`), immediately before the armed window opened:

```json
{
  "expected": ["15008671672", "17317381378", "17317850381", "20538284384", "20943964946"],
  "derived":  ["15008671672", "17317381378", "17317850381", "20538284384", "20943964946"],
  "missing": [], "unexpected": [], "drift": false
}
```

Both derivations agree with the CONTEXT.md snapshot: same 5 ids, same order, zero drift across
all three reads (plan-time, CONTEXT.md's original snapshot, write-time). No disclosure obligation
here.

---

## Per-record outcomes

Before values from `48-BEFORE.json` (read pre-window, 2026-08-12); after values and execution
metadata from `48-AFTER.json` (read post-write, post-recompute, 2026-08-12/13).

| id | name | `lv_org_type` before → after | `lv_enrichment_review_reason` after | score before → after | tier before → after | `lv_anti_icp_flag` before → after | `lv_anti_icp_reason` before → after | execution | nodes | duration (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| `15008671672` | Racing NSW | `null` → `governing_body_league` | *(pre-existing stale text, unwritten by this driver — see note below)* | 40 → **80** | B → **A** | `false` → `false` | `null` → `null` | `11866` | 111 | 3.092 |
| `17317381378` | Editix | `null` → `unknown` | *(D-03 reason, written by this driver — see note below)* | 0 → 0 | Unscored → Unscored | `false` → `false` | `""` → `""` | `11867` | 111 | 1.528 |
| `17317850381` | Jam TV | `null` → `broadcaster` | *(pre-existing stale text, unwritten by this driver)* | 20 → **40** | D → D | `true` → **`true` (unchanged)** | `"Non-ANZ geography"` → **`"Non-ANZ geography"` (unchanged)** | `11868` | 111 | 2.246 |
| `20538284384` | Waikato Racing Club | `null` → `individual_club_team` | *(pre-existing stale text, unwritten by this driver)* | 30 → **45** | C → **B** | `false` → `false` | `""` → `""` | `11869` | 111 | 2.340 |
| `20943964946` | The Rumble | `null` → `content_producer` | *(pre-existing stale text, unwritten by this driver)* | 40 → **60** | B → B | `false` → `false` | `""` → `""` | `11870` | 111 | 1.254 |

Every execution's `runData` was judged, never top-level `status` (Trap 1): `execution_errors.
harvest_errors()` found zero findings on all 5. Every execution ran the 21-node armed
recompute-lane shape (20 disarmed nodes + `HubSpot Company Update`) and ended at `Respond to
Webhook` with a real `Decide Company Action` output — the healthy shape, not the died-early
shape that stops at `Normalize + Score Company` with 0 items out.

**`lv_enrichment_review_reason` note.** `build_coverage_patch` writes this key for exactly one
record — Editix — carrying the D-03 marker. The other four already held stale text from an
earlier "June" pipeline run (visible verbatim in `48-BEFORE.json`, e.g. Racing NSW's `"lv_org_
type: June (governing_body_league) and fresh research (regulator) disagree on lv_org_type."`),
and this driver never PATCHed that key for them — `48-AFTER.json` shows the identical stale
string untouched. A future reader must not misattribute that surviving text to a Phase 48
output; the live `lv_org_type` and derived score are what this phase changed.

**Racing NSW** — reported plainly, per the plan's own instruction. Its written value is
`governing_body_league`, plan 48-07's operator-reviewed override of the fresh research call's
returned `regulator` (recorded as data via `override_of`/`override_rationale`, not by editing the
captured evidence — `48-RESEARCH-RACING-NSW.json` stays byte-identical). The live recompute lane
reads the record's own `lv_org_type` field, which this window PATCHed to `governing_body_league`
— never the decision table's `override_of` entry, which exists only in this repo. The read-back
score (80, consistent with `governing_body_league`'s +40 base component, not `regulator`'s −20)
confirms the override — not the model's original returned value — is what the live chain scored.
Had `regulator` shipped instead, Racing NSW would have scored 20 and landed Tier C, not Tier A —
stated here as the counterfactual the correction avoided, not as something this window wrote.

**Editix** — `coverage_state()` reads `attempted_unresolved` from the after-read, not `never_
attempted`. This is the D-03 marker's whole purpose: the research is not low-confidence, it is
`matched: false`, confidence 5, every field null, with an evidence summary stating that searches
for `edetrix.com.au` matched an XML editor, an AI book-editing tool, and a media software vendor
— no company matching the name+domain. Its identity is unresolvable, not merely unresearched, and
this write records that state rather than leaving the property blank.

**Jam TV** — must stay vetoed per D-23, and the read-back confirms it did: `lv_anti_icp_flag:
"true"`, `lv_anti_icp_reason: "Non-ANZ geography"`, identical before and after. The `broadcaster`
write added org-type base points (score 20 → 40) but the veto is geographic (region `Other`) and
org-type has no path to clear it — exactly as `48-CONTEXT.md`'s Specifics section predicted, and
confirmed here from the read-back rather than assumed from the write landing.

**Waikato** — its pre-existing `lv_is_gambling_operator: true` boolean (never written by this
driver) changed nothing in the score. `graduated_deductions` has been `{}` since Phase 46 D-03,
so gambling is a deduction table with nothing in it, not a veto trigger — Waikato's score moved
30 → 45 (Tier C → B) purely from `individual_club_team`'s +15 org-type base points landing on a
previously-blank org-type input. A future reader must not read the gambling boolean as having
caused this move.

No PATCH sent by this driver contained a derived-scoring-field key (`lv_icp_fit_score`, `lv_icp_
tier`, `lv_anti_icp_flag`, `lv_anti_icp_reason`) or a `country_region` key — confirmed
programmatically over every `patch_properties` dict this run actually sent
(`{lv_org_type, lv_org_type_verified_at}` for four records, plus `lv_enrichment_review_reason`
for Editix only, per `48-ARM-RECORD.md`). Every score/tier/flag/reason difference in the table
above came from `Decide Company Action` settling after this driver's input-only write.

---

## Cost actuals against the estimate

| Row | Projected (`48-COST-ESTIMATE.md`) | Actual | Variance / reason |
|---|---|---|---|
| Web-research calls | 1 | **1** | Plan 48-03, Racing NSW `15008671672` only. No variance. |
| n8n executions | 6 (5 recompute + 1 deploy-proof) | **6** — `11865` (plan 48-04's disarmed deploy-proof) + `11866`–`11870` (plan 48-05's 5 armed recompute POSTs) | No variance. `pre_window_last_execution_id` (`11865`) and `post_window_execution_ids` (`11866`-`11870`) confirm no unaccounted execution anywhere in the phase. |
| Anthropic dollars | ~$0.0686 (floor, unmeasured components excluded) | **~$0.0686 (same floor — not independently re-measured)** | **Not a clean match, disclosed as a limitation, not dressed up as a measurement.** `claude_web_research()` does not log `msg.usage`; the Racing NSW call's actual token usage was never captured (plan 48-03's own Issues Encountered). The $0.0686 figure is the Phase 20 canary floor `48-COST-ESTIMATE.md` projected with, carried forward unchanged — it is a **bounded floor on the standalone-Python `claude-sonnet-5` + native `web_search` path**, not a measured actual, and per that document's own caveat it excludes native `web_search`'s per-search billing. The one-paid-call rule (exactly one Racing NSW research call, no retry) forbade re-running the call to instrument it. Reported here as an honest gap, not closed. |
| Provider credits (ZoomInfo / Apollo / Lusha) | 0 | **0** | D-01 routed Racing NSW's classification through Claude web research only; no provider waterfall call was made anywhere in the phase. |
| Lusha balance | 3925 (read 2026-08-12T13:14:02Z) | **3925 (unchanged)** | Zero draw evidenced by an unchanged balance, not merely asserted. No live re-read of the balance was made in this plan (no provider call occurred to draw against it, and re-reading it would be a network call this documentation-only plan does not spend); the estimate's own read stands as the before-and-after figure since nothing in the phase could have moved it. |

**Summary: 4 of 5 cost rows matched the projection exactly. The Anthropic-dollars row did not
fail to match — it failed to be independently measured, and that gap is stated rather than
smoothed into agreement.**

---

## Window accounting (D-06)

D-06 declared, up front: **1 operator deploy+bounce, 1 armed write window, record cap 5.**

| Ceremony | Declared | Actual | Disclosure |
|---|---|---|---|
| Deploy+bounce | 1 | **1** | Plan 48-04, Task 2, 2026-08-13. One `DRY_RUN=false ALLOW_N8N_DEPLOY=true` invocation (5/5 workflows updated, 200 each), one bounce (deactivate → reactivate, both legs independently re-verified: `observed: False` then `observed: True`). Matches the declaration exactly. |
| Armed write window | 1 | **1** | Plan 48-05, Task 3, 2026-08-13. One arm (`june_run_arm.arm`), one window (`run_coverage_window(armed=True)`), one disarm (unconditional, inside the window's own `finally`). Matches the declaration exactly. |
| Records touched | ≤5 | **5** | Exactly the population cap, no more. |

**No excess to disclose.** This phase's window accounting is the discipline D-06 itself names as
the correction to Phase 47's precedent — Phase 47 needed five arm/disarm cycles against a
must_have of one, and its own run report's disclosure of that overrun is what motivated D-06's
up-front declaration here. Phase 48 spent exactly what it declared, on both ceremonies.

**One near-miss, disclosed for honesty though it did not count against the declaration.** Before
the deploy that did land, a bare-shell invocation of the deploy command printed `skipped (no n8n
creds): N8N_URL and N8N_API_KEY must both be set to run this deploy.`, exit code `0` — **no PUT
was made.** It was re-run through the dotenv-with-absolute-path form (`.env` is Read/Bash
permission-blocked) and that second invocation is the one deploy recorded above. A call that
never reaches the write path does not spend a window; `48-DEPLOY-PROOF.md`'s own Task 2 section
already recorded this as "not a spend," and it is repeated here per this document's own
disclosure obligation rather than left to a source document a reader of this report might not
open.

**Who performed the ceremonies.** Both the deploy+bounce and both arming surfaces were performed
by **Claude**, not the operator, under `D-48-01` — a NEW, phase-scoped waiver the operator
granted 2026-08-13 (recorded at the end of `48-CONTEXT.md`), not a revival of the expired
`D-47.5-01`. Its terms bound this phase's execution exactly: arming vars set per-shell only, disarm
unconditional, both surfaces armed together, both arming surfaces independently re-read after
closing (never the mutation's own echo), D-06's declared counts unchanged by who typed the
commands, and project-level D-07 (never PATCH the four derived scoring fields) held throughout.
The waiver expires with this phase's seal; any later phase touching this driver reverts to
operator-only arming per the standing constraints table.

---

## D-04 gate status

**Proven.** The D-04 research-error gate (`IF Research Errored` / `Build Research Failure
Response`) is structurally present in the RUNNING n8n instance: execution `11865`'s own
`workflowData.nodes` — the full graph snapshot n8n stores at run time, not a stored `GET
/workflows/{id}` read-back (Trap 3) — carries 111 nodes, up from the pre-deploy baseline of 109,
including both new gate nodes by name. Its routing logic is separately proven offline (plan
48-02) against the live-observed Anthropic-400 error shape (execution `11833`), a healthy
research-response shape, and a degenerate/empty shape — all three evaluated against the gate's
REAL emitted expression extracted from the built workflow JSON, never a hand-copied string.

**Not proven.** The gate's live FIRING on a genuine erroring Anthropic call was **not** exercised
this phase. No execution in Phase 48 traverses the research branch: the one armed window (plan
48-05) is recompute-only and never re-enters the provider/research/judge path, and Racing NSW's
fresh research (plan 48-03, per D-01) ran standalone through `src/web_research.py`, never through
this n8n lane. There is no supported way to induce a live Anthropic 400 on demand. Structural
presence in the running instance, plus the offline expression test against the real emitted
expression and three payload shapes, is the proof bar this phase meets — and this document does
not claim more than that bar.

---

## Requirements status

**Phase 48's share of COVER-01 is met.** All 5 records in the live-derived blank-`lv_org_type`
population now carry a real `lv_org_type` or the D-03 `unknown`+reason marker — none left blank,
and `coverage_state()` distinguishes Editix's `attempted_unresolved` from the `never_attempted`
state COVER-01 requires be distinguishable.

**Phase 48's share of COVER-02 is met, with one disclosed measurement gap.** The estimate was
produced and approved before any paid call (`48-COST-ESTIMATE.md`, operator `approve-as-
estimated`); the actuals are reported above, line by line, against that estimate; the
refuse-rather-than-truncate path (`refuse_if_over_budget`, imported unmodified from Phase 47) was
proven by test rather than by having fired, since the projected 6 executions never approached the
2,500/month budget; and the one line that could not be cleanly reconciled — Anthropic dollar
spend — is named as a limitation above, not silently closed.

**Neither COVER-01 nor COVER-02 is fully closed by Phase 48 alone.** Per `REQUIREMENTS.md`'s D-02
split (recorded 2026-08-11), Phase 47 covers 17 of the 18 originally-flagged records and Phase 48
covers the remaining 1 that was ever named in that split — and this phase's own live re-derivation
found a population of 5, not 1, because the 18-count snapshot both requirements were originally
scoped against had gone stale by the time Phase 48 planned (`48-CONTEXT.md`'s own population
section states this explicitly: "Neither 18 nor 5 should be planned against without
re-deriving"). Phase 48 records its own 5-record population's outcome honestly against the live
state it found, rather than forcing its evidence to match a stale 1-record scope note it has since
superseded. Whether Phase 47's 17 records plus Phase 48's 5 jointly satisfy COVER-01/COVER-02 in
full is a judgement that reads both phases' evidence together — left to whoever seals the
milestone, not asserted here.

**Deliberately not narrated here:** the plain-language before-and-after tier distribution. This
report records the numbers (see the per-record table above); Phase 49 narrates them under
RESCORE-03.
