# Phase 46 Decision Record: Rubric Weights (RUBRIC-01)

## Verdict

Three `base_score.org_type` levers move, on operator GTM direction that in two of three cases
overrides the closed-deal evidence in `docs/business/icp-scoring.md`:

| Lever | Current | Proposed | Shape |
|---|---|---|---|
| D-01 `individual_club_team` | 5 | **15** | direct `base_score.org_type` weight |
| D-02 `regulator` | 5 | **-20** | direct `base_score.org_type` weight (not a new `graduated_deductions` key — see Rejected alternatives) |
| D-03 `graduated_deductions.gambling_operator` | -20 | **removed** | config key deleted, `src/icp_scoring.py`'s gambling-deduction block already `.get`-guarded (46-01) |

**Decision date:** 2026-08-11. **Portal:** 22617666. This verdict is Claude's proposal per D-05
("Claude proposes, operator signs off") — it is not yet authoritative. It becomes binding only
when the Operator Sign-off block at the end of this document is filled and committed (Task 2).
No weight has been committed to `config/icp_scoring.yaml` or any HubSpot flow as of this
document's writing — `git diff config/icp_scoring.yaml config/hubspot_flows/` is empty.

## How the verdict was reached

**RUBRIC-01's bar is that the decision is evidenced and recorded, not that it follows the
evidence.** All three levers below were tested against `docs/business/icp-scoring.md`'s 92
closed-deal analysis; two are direct overrides of what that analysis recommends. Per D-14, the
evidence is quoted intact, not rewritten to agree with the new weight.

### D-01 — `individual_club_team`: 5 → 15 (override)

**The evidence:** `icp-scoring.md` §3's assumption scorecard: *"Three org types (club / league /
broadcaster) — ⚠️ Reframed — League/Governing-Body 83% (n=12) ≫ Broadcaster 40% (n=15) ≫
Club/Team 19% (n=36)."* §4 names clubs anti-ICP outright: *"Individual clubs/teams as the direct
target — 19% win over 36 deals; high effort, low yield... Reach them via their governing body,
not directly."* §1's headline calls this the report's central finding: *"The most-pursued
segment is the weakest: individual clubs/teams are the single biggest group of deals (36) yet
convert at only 19% — we chase them hardest and close them least."*

**The override:** the operator directs `individual_club_team` to 15 anyway. Verbatim in
substance, from `46-CONTEXT.md`: *"sales teams consider individual racing/turf clubs a prime
target, below perhaps leagues, but definitely not in lower tiers."* This is a deliberate GTM
decision **against** the 19%/n=36 win-rate evidence, not a data disagreement — sales treats
individual racing/turf clubs as a prime target ranking just below leagues, not a nurture
segment, and the ask was explicit: achieve this using existing levers, without materially
moving any other org type's score. The weight table satisfies that constraint exactly — no
other org type's points change as a result of D-01.

### D-02 — `regulator`: 5 → -20 (override)

**The evidence:** `icp-scoring.md` §4 flags the governing-body bucket as internally mixed:
*"(Bucket is slightly mixed — e.g. QRIC is a regulator, not a content buyer — so JTBD 2
shouldn't treat 'governing body' as monolithic.)"* A regulator is not a sports-media buyer even
where it sits adjacent to a governing body that is.

**The override:** the operator directs `regulator` from 5 to **-20** (not merely to 0), pushing
regulator accounts below the neutral floor rather than just removing their small positive
contribution. Net effect on a worked example: an AU regulator producing content goes from
35/C to 10/Unscored. Affects one live record — Queensland Racing Integrity Commission (QRIC,
`16047156820`).

### D-03 — gambling deduction removed (override)

**The evidence:** `icp-scoring.md` §4 states the deliberate design choice being overridden:
*"Gambling operators (Sportsbet, Entain) = graduated deduction, not a veto — targetable
proactively where other fit signals are strong."* §5's scoring model carries the same −20 as a
graduated deduction, explicitly not a hard veto, precisely so gambling operators with strong
other fit signals remain reachable.

**The override:** the operator directs the −20 deduction removed entirely, for every company
carrying `lv_is_gambling_operator = true`, regardless of org type. This goes further than the
evidence's own framing (which kept a small penalty) — it removes the penalty altogether. Net
effect on a worked example: an AU gambling operator producing content goes from 10/Unscored to
30/Tier C.

### Post-change org-type rank ordering

```
governing_body_league   40
content_producer        20  ┐
broadcaster              20  ┘ (tied)
individual_club_team    15   <- D-01, was 5
gambling_operator         0  ┐
hardware_vendor           0  │ (tied, unchanged)
other                      0  │
unknown                    0  ┘
regulator                -20   <- D-02, was 5
```

`individual_club_team` at 15 remains **strictly below** `broadcaster`/`content_producer` at 20 —
the ordering against measured win rate is **compressed, not inverted**. Current weights already
rank-order with win rate (league 40/83%, broadcaster 20/40%, club 5/19%); D-01 narrows the gap
between the club tier and the mid tier without reversing it.

### Live simulation findings (Plan 02, run 2026-08-11 against portal 22617666)

The simulation (`46-SIMULATION-REPORT.md`) ran read-only against the live 66-company scored
population — no HubSpot record was written. Its row set matched
`41-final-population.json`'s 66-id snapshot **exactly** (live=66, cross-check=66, symmetric
difference=0), so the "66" figure this decision rests on is confirmed against live data, not
assumed.

**Movement.** 14 of 66 rows change tier under the primary scenario (club=15). All 14 are
`individual_club_team`, all move C → B. No other org type moves under any of D-01/D-02/D-03 on
this live population. Tier distribution moves from oracle-current (A:7 B:17 C:16 D:7
Unscored:17 NeedsReview:2) to oracle-proposed (A:7 B:31 C:2 D:7 Unscored:17 NeedsReview:2).

**Club-weight sensitivity is not a knife-edge.** The simulation ran club weight at 10, 15, and
20 as three full scenarios. All three produce **identical** tier distributions on this live
population — a content-producing AU club at 1–5M revenue scores 40 at club=10, 45 at club=15,
and 50 at club=20, and all three land in Tier B because the B floor is 40 and every affected
live record's total clears it even at the lowest sensitivity weight, without any crossing into
A even at the highest. This is worth stating plainly so the three matching sensitivity rows in
`46-SIMULATION-REPORT.md` are not misread as a bug — they are the expected result of this
specific population's totals sitting comfortably clear of the B floor. The practical
consequence: 15 is not a fragile choice on this population; the decision would be robust to
being off by ±5. This does not change the abstract rejection of 10 and 30 below, which stand on
their own reasoning independent of this particular population's insensitivity to them.

**D-02 and D-03 are score-only on live data, not tier-moving — a real divergence from the
pre-simulation estimate, reported plainly rather than reconciled away.** QRIC (`16047156820`,
regulator) already carries a genuine hard veto today (live score 25/D) — D-02's effect (25 → 0)
does not change its tier; it was D before and stays D after. Both live gambling-flagged records
— Entain (`10024564084`) and Sportsbet (`17861423879`) — also already carry genuine hard vetoes
independent of gambling status; D-03's effect is score-only (−70 → −50, 0 → 20 respectively),
neither moves tier. This **contradicts** `46-CONTEXT.md` D-03's June-snapshot-derived "~1 record
actually moves" estimate, which assumed a veto-free gambling record existed in the live
population. It did not. One honest note on the tension this creates: D-07's standing tiebreaker
("if evidence argues a weight down but simulation shows near-zero tier movement, keep the
current weight") would, taken on its own terms, argue for leaving D-02 and D-03 unchanged, since
neither moves a single live tier. It does not govern here — see the D-07 section below — but the
tension is real and is recorded rather than smoothed over.

## Rationale

The evidence document (`docs/business/icp-scoring.md`) is cited, not re-derived, per D-07's
"don't re-derive the evidence, cite it" convention this record inherits from `39-DECISION.md`'s
own §5-citation pattern. Where the decision follows the evidence (none of the three levers here
do, entirely — all three are overrides, in whole or in degree), no override language is used.
Where the decision overrides the evidence — **all three levers in this phase** — the override is
stated as an override above, with the underlying finding quoted intact and its percentage and
sample size preserved (Club/Team 19% over n=36), per D-14's binding constraint. The next
recalibration depends on this record surviving with the evidence unedited; a decision record
that quietly rewrites the evidence to agree with the new weight would destroy exactly the
artifact RUBRIC-01 exists to produce.

### D-04 — no new HubSpot property (`lv_is_regulator` rejected)

Folded into this record because it is the reason D-02 is expressed as an `lv_org_type` edit
rather than a new boolean, and because REQUIREMENTS.md's no-new-properties constraint is a hard
constraint this phase must not violate.

`lv_is_regulator` was proposed and investigated, then rejected. The decisive argument is data,
not policy: regulation in AU racing is **jurisdiction-dependent and overlaps governance**.
Queensland *splits* the roles into separate legal entities — Racing Queensland (`9648957286`,
`governing_body_league`) and QRIC (`16047156820`, `regulator`) are distinct records, which is
why QRIC exists as its own `regulator`-classified record at all. Western Australia *fuses* the
roles — Racing and Wagering Western Australia (`9605284722`) is classified
`governing_body_league` and is **a won deal**, named in `icp-scoring.md` §4's primary win list.
Racing NSW (`15008671672`) carries statutory integrity functions under the same
`governing_body_league`-adjacent classification (currently blank `lv_org_type` live, per
`46-SIMULATION-REPORT.md`'s flags, but not `regulator`).

A boolean property asks "does this org regulate?" and would answer **yes** for RWWA — landing a
−20 penalty on an account already won, inside the 83%-win primary segment. `lv_org_type` is
single-valued and asks "what is this org *primarily*?" — this catches QRIC (primarily a
regulator) while leaving RWWA and Racing NSW untouched (primarily governing bodies that also
carry integrity functions). The single-valued classification is the *safer* lever here, not
merely the cheaper one to implement. A new boolean would also sit blank on all ~712 companies
until a full enrichment pass reached every record — Phase 48-scale spend against what is
currently an 18-record `lv_org_type`-blank gap, for a signal that only ever matters for one
live record today.

## Rejected alternatives

### Club weight: 10 and 20 and 30 rejected in favor of 15

- **10** — rejected. 40 (governing-body-adjacent floor for a content-producing AU club) is a
  fragile Tier B floor: any soft signal (e.g. a slightly narrower revenue band or a borderline
  content classification) drops the record straight back to Tier C. `46-SIMULATION-REPORT.md`'s
  club_10 sensitivity column shows the live population still lands in B at this weight for the
  14 affected rows on this specific population, but the abstract risk (a population with
  slightly less favorable geo/content/revenue totals) remains.
- **20** — rejected. Ties `broadcaster` and `content_producer` exactly, which is the hardest
  possible contradiction of the underlying win-rate ordering: clubs convert at 19% against
  broadcaster's 40%, so scoring them identically inverts nothing numerically-visible in the
  tier bands (both still land B) but erases the signal that clubs are the weaker segment of the
  two, which the evidence supports keeping distinct.
- **30** — rejected. At 30, clubs would outrank `content_producer`/`broadcaster` (20 each) and,
  combined with content + geo + revenue points, could reach Tier A — inverting the win-rate
  ordering outright (19% club win rate outscoring 40% broadcaster win rate is the wrong
  direction for a rubric meant to prioritize by likelihood of conversion).
- **15 chosen** — sits strictly between the fragile-floor risk of 10 and the ordering-inversion
  risk of 20/30, delivers the operator's explicit ask ("below leagues, not in lower tiers")
  landing at Tier B (45 for a typical AU content-producing club, 55 for a larger turf club in
  the 5–500M revenue band), and — per the live sensitivity run above — is not a fragile choice
  on the actual live population either.

### Regulator deduction shape: `graduated_deductions` key rejected in favor of a direct `base_score.org_type` weight

`46-CONTEXT.md` D-06 originally framed the regulator −20 as **new engine logic, not a weight
edit** — a new org-type-driven entry in `graduated_deductions` (which today holds only
`gambling_operator`, fired independently on the `lv_is_gambling_operator` boolean). This framing
is **superseded**. `46-RESEARCH.md`'s Open Question 5 reproduced, by direct local execution
(not static reasoning alone), that `0 + (-20) == -20` regardless of whether the −20 is expressed
as `org_type.regulator: 0` plus a new deduction key, or as `org_type.regulator: -20` directly —
`src/icp_scoring.py`'s `.get(org_type, 0)` lookup has no floor or clamp that would make a
negative org-type weight behave differently from a positive one. The direct-weight shape needs
**zero new code** in `src/icp_scoring.py` (the existing lookup line already handles a negative
value correctly) and `tests/test_flow_rubric_conformance.py::test_org_type_flow_matches_rubric`
covers it with **zero test changes**, since that test is parametrized directly off
`config/icp_scoring.yaml`'s `base_score.org_type` map. `46-02-SUMMARY.md` confirms this
empirically: `build_proposed_cfg`'s `graduated_deductions` dict is proven empty (`{}`) after all
three overrides apply — no new key was added anywhere. This resolves `46-CONTEXT.md`'s own
"Claude's Discretion" bullet on the deduction's shape and supersedes D-06's "new engine logic"
framing outright.

## What this shapes downstream

### The engine-count correction

`46-CONTEXT.md` D-11 and `REQUIREMENTS.md` RUBRIC-03 both state "**three** engines" carry
org-type weights. `46-ENGINE-INVENTORY.md` (Phase 46 Plan 01, Task 1) settles this at
**two engines, not three**: the Python oracle (`config/icp_scoring.yaml` + `src/icp_scoring.py`)
and the HubSpot Automation v4 flow `4626124224` ("Update Score Based on Org Type") both encode
`base_score.org_type` as a value-to-points table. The n8n JS leg
(`n8n/wf_enrichment_cloud.json`, built by `scripts/build_cloud_workflows.py` from
`n8n/code/mergeCompanies.js`) carries **no** org-type-keyed numeric table anywhere — confirmed
by an exhaustive word-boundary-adjacent-to-number grep across all nine `base_score.org_type`
keys against every n8n-side artifact, zero matches. `mergeCompanies.js`'s own header comment
names this "Approach C (Phase 15) — HubSpot owns these derived outputs."

**Consequence for ROADMAP.md Phase 46 success criterion 4:** that criterion (build → deploy →
bounce + running-content read-back) is **NOT TRIGGERED** by this phase, not satisfied. No
org-type or gambling-deduction weight reaches the live n8n workflow at all, so there is nothing
for `scripts/build_cloud_workflows.py` to regenerate differently as a result of D-01/D-02/D-03,
and therefore no build to deploy and no running content to bounce or read back. This is a
conditional, not permanent, finding — it would re-activate if a future change touches
categorical promotion logic, taxonomy membership, evidence gating, or merge policy in the n8n
leg (`46-ENGINE-INVENTORY.md` names the four specific triggers). None of this phase's three
weight decisions touch any of them.

**Practical consequence:** Plan 04's D-01/D-02/D-03 weight edits touch exactly two files —
`config/icp_scoring.yaml` and the archived-then-live-PUT HubSpot flow JSON
(`config/hubspot_flows/4626124224-org-type-score.after.json` plus, for D-03,
`config/hubspot_flows/gambling-score.after.json` for flow `4634822085`) — no n8n
build/deploy/bounce step is part of Plan 04's or Plan 05's edit surface. RUBRIC-03's "all three
engines" parity bar is satisfiable by keeping exactly these two engines in sync; there is no
third engine to keep in sync with. Plan 05 records the corresponding amendment notes in
`REQUIREMENTS.md` and `ROADMAP.md` so the "three engines" / "criterion 4" text does not sit
stale after this decision lands.

### The D-07 standing tiebreaker

Recorded here as **policy for future weight decisions**, kept even though it did not govern this
one: *if evidence argues a weight down but the simulation shows near-zero tier movement, keep
the current weight* — a change with no tier consequence still costs a live flow deploy, a
bounce, and a full population re-score (Phase 49's ~66-record run), for zero visible operator
benefit. **D-01/D-02/D-03 were directed on explicit GTM grounds, not derived from simulation
movement, so this tiebreaker did not decide any of the three levers in this phase.** As noted
under Live simulation findings above, D-02 and D-03's near-zero tier movement on live data means
D-07's tiebreaker, read literally and in isolation, would argue against making those two
changes at all — they proceed anyway on GTM grounds (regulator is genuinely not a content buyer;
gambling operators should stay proactively targetable), and that one sentence of tension is
recorded rather than resolved silently.

**Confirming a weight unchanged is an equally valid evidenced outcome under RUBRIC-01.** Had the
operator applied D-07 literally to D-02/D-03 given the live movement numbers above, the
resulting decision — "regulator and gambling weights stay as they are, because the simulation
shows the closed-deal-evidenced deduction wasn't moving any real tier anyway" — would have been
just as fully evidenced a verdict as the override recorded here. What the operator would be
choosing in that path: accepting the status quo −20-gambling/+5-regulator weights as
sufficient, on the grounds that no live record's tier depends on changing them, while leaving
`icp-scoring.md`'s own stated design intent (gambling as a targetable graduated deduction,
regulators flagged as a mixed sub-bucket) formally unaddressed in the rubric.

### Parity red window (46-RESEARCH.md Pitfall 4a)

**This is a stated choice, not a default.** The window opens the moment
`config/icp_scoring.yaml` is committed (Plan 04), **not** at the flow PUT — because
`scripts/run_scoring_parity.py` samples real, live companies (via the same `HAS_PROPERTY`
search this simulation used) and compares their **old-weight live score** against the
**new-weight oracle**, and `config/icp_scoring.yaml` becomes the new-weight oracle's source the
instant it is edited on disk, independent of whether the HubSpot flow has been PUT yet. From
that moment until Phase 49's re-score lands, every re-tiered live record (all 14
`individual_club_team` rows under the primary scenario, plus any score-only-affected
`regulator`/gambling-flagged rows) becomes a `real_finding` on the standing unattended parity
sweep. The sweep's own false-green guard means this is a loud, correct FAIL on every scheduled
run during the window — not a silent one, and not evidence of a new bug.

**Option chosen: (a) — accept and document a bounded red window, ending when Phase 49 completes
the population re-score.** Option (b) — coordinating the config commit and flow PUT with Phase
49's re-score to minimize the gap — was considered and rejected for this phase's structure:
Plan 04 (the weight commit + flow PUT) is scoped to execute directly after this checkpoint,
inside Phase 46, while Phase 47 (false-veto remediation) and Phase 48 (coverage enrichment) are
scheduled to run *before* Phase 49's re-score per the milestone's own sequencing rationale
("rubric decided once (46) before the 17 false-veto records are touched (47), so they re-score
exactly once rather than twice"). Deferring the weight commit itself to coincide with Phase 49
would mean holding the operator's GTM decision unenacted through two more phases for no
corresponding benefit — Phase 47/48 do not depend on the org-type weight values, only on
`lv_org_type`/veto-input population, so there is no coupling that option (b) would actually
close early. **Phase 49 closes the window** by executing the re-score (see below); until then,
the parity sweep's `real_findings` for `individual_club_team`/`regulator`/gambling-flagged
records are expected and self-inflicted, not a new defect.

### What Phase 49 owes and what it costs

**Recommended mechanism:** reuse `scripts/backfill_seed_company_scores.py`'s
`compute_components()` direct-CRM-batch path, not the n8n SJ-3 `lv_enrichment_requested`
poller. `compute_components()` computes all five component scores in Python from a record's own
current canonical inputs via `src/icp_scoring.compute_icp_score()` (reading
`config/icp_scoring.yaml` directly, never a second hand-copied table), then batch-PATCHes
`org_type_score`/`geography_score`/`annual_revenue_score`/`produces_content_score`/
`gambling_score` directly via `src/hubspot_client.batch_update_companies()` — a plain HubSpot
CRM v3 batch API call. This costs **approximately zero n8n executions** against the 2,500/month
allowance, versus the SJ-3 poller path's full enrichment waterfall, which includes two
sequential Anthropic calls per record and would touch neither necessary input for this
particular rubric change (every input D-01/D-02/D-03 need already exists live on these
records).

**The gate:** `scripts/backfill_seed_company_scores.py`'s module constant
`HARD_CEILING_RECORDS = 25` currently caps this script's sample size, deliberately scoped in
Phase 40 to a small proving run. At n=66, Phase 49 must either (a) call the script three times
in ≤25-record chunks with distinct `--company-id` sets, or (b) raise the ceiling with a recorded
justification (this is exactly the "chunk size" question `RESCORE-01` already asks Phase 49 to
answer).

**Veto fields need no recomputation for this specific rubric change.** None of D-01/D-02/D-03
touch hard-veto category membership (non-AU, no-content, hardware-vendor) — the veto derivation
lives entirely in n8n's `ENRICH_DECIDE_CO_CLOUD` and is untouched by any weight this phase
decides. This lets Phase 49's re-score skip n8n's pipeline (and its Anthropic cost) entirely for
this change. **This is not true of rubric changes in general** — a future change that touches
veto category membership would need the n8n pipeline re-run, not just the component backfill.

**Untested edge, flagged not resolved:** whether overwriting an already-
`PROPERTY_DEFAULT_VALUE`-stamped component (the original three components on records created
before Phase 40's flow expansion) behaves identically to writing a never-set one. HubSpot's
default-value stamp mechanism is API-inaccessible for reads (`PORTAL-FACTS.md`'s
Default-value-generation finding), and nothing in this repo's history has tested whether
*overwriting* an already-stamped value diverges from writing a never-set one. Flagged for Phase
49's own research as an open item, not resolved here, and not blocking this phase.

## Assumptions carried into the verdict

- **Population freshness.** This decision record is dated 2026-08-11. `docs/business/
  icp-scoring.md`'s evidence base is 92 closed HubSpot deals (39 won / 53 lost) analyzed as of
  its own preparation date, not re-verified live in this phase. Plan 02's live re-check is what
  the verdict's simulated movement numbers actually rest on: the live 66-company scored
  population, queried live on 2026-08-11, matched `41-final-population.json`'s snapshot exactly
  (symmetric difference 0), confirming the population this decision simulates against is current
  as of decision time, not stale. If a materially longer gap opens between this document's date
  and the operator's sign-off, or between sign-off and Plan 04's commit, the row-set match should
  be re-verified before the flow PUT, not assumed to still hold.
- **The engine-count finding is stable at decision time.** `46-ENGINE-INVENTORY.md`'s two-engine
  verdict is a source-code fact, not a live-population fact — it does not carry the same
  freshness risk as the row-set match above, but would need re-verification if a future phase
  touches `mergeCompanies.js`'s categorical promotion policy or the taxonomy build pipeline
  before this decision is acted on.
- **D-02/D-03's score-only-not-tier-moving live result is this population's result, not a
  general property of the rubric.** A future company entering the scored population with
  `lv_org_type=regulator` and no independent hard veto, or a gambling-flagged company with no
  independent hard veto, would see its tier move under D-02/D-03 — the current live population
  simply happens not to contain such a record today.

## Re-check procedure

If this rubric decision is later revisited (e.g. a future GTM direction change, or a rubric
recalibration once `lv_closed_lost_reason` starts collecting real loss data per `icp-scoring.md`
§9):

1. Re-run the live population query (`scripts/run_scoring_parity.py::_select_sample_ids()`'s
   `HAS_PROPERTY(lv_icp_fit_score)` search) and diff against the ID set this decision cites, to
   confirm the population hasn't materially changed.
2. Re-run `scripts/simulate_rubric_weights.py` with the proposed new overrides against the
   re-verified population, producing a fresh `46-SIMULATION-REPORT.md`-shaped artifact — do not
   reuse this phase's report as if it still reflects the current population.
3. Re-check `46-ENGINE-INVENTORY.md`'s two-engine finding is still current by re-running its
   word-boundary-adjacent-to-number grep against the live `n8n/wf_enrichment_cloud.json` and
   `scripts/build_cloud_workflows.py` — if either now carries an org-type-keyed numeric table,
   the engine count and RUBRIC-03's parity bar both need re-deriving.
4. Follow the same disable → edit → PUT → enable → validate → confirm protocol documented in
   `PORTAL-FACTS.md`'s "D-05 round-trip verdict" section for any HubSpot flow edit, including a
   post-PUT re-fetch of the running (not merely stored) flow content before treating the change
   as live.
5. Write a new dated decision record rather than editing this one in place — this document's
   evidence-vs-override structure is itself the audit trail a future recalibration depends on.

## Process note

No task or step in this plan was skipped. Task 1 (this document) executed in full per the
plan's `<action>`. Task 2 (the operator sign-off checkpoint) is a `checkpoint:human-verify` gate
this document intentionally leaves unresolved below — the sign-off block is empty by design,
to be filled only after the operator has reviewed the published simulation artifact and this
record, per D-05/D-09.

## Evidence index

| Artifact | Path | Role |
|---|---|---|
| Closed-deal ICP validation | `docs/business/icp-scoring.md` | The evidence document RUBRIC-01 requires traceability to; §3 assumption scorecard, §4 best-fit/anti-ICP, §5 proposed scoring model — the source of every quoted finding this record cites and, in three places, overrides |
| Live simulation report | `.planning/phases/46-rubric-decision-simulation-engine-parity/46-SIMULATION-REPORT.md` | Per-company before/after re-tier of the live 66-company population under the proposed weights; primary evidence for the "14/66 rows move, all individual_club_team C→B" and "D-02/D-03 score-only" findings above |
| Simulation JSON twin | `.planning/phases/46-rubric-decision-simulation-engine-parity/46-simulation-20260811.json` | Machine-readable form of the same run |
| Engine-count reconciliation | `.planning/phases/46-rubric-decision-simulation-engine-parity/46-ENGINE-INVENTORY.md` | Settles "two engines, not three" with file:line evidence; source of the ROADMAP criterion-4 finding |
| Technical research | `.planning/phases/46-rubric-decision-simulation-engine-parity/46-RESEARCH.md` | Open Question 5 (regulator-deduction-shape proof), Open Question 6 (Phase 49 cost mechanism), Pitfall 4a (parity red window) |
| Phase 46 context / user decisions | `.planning/phases/46-rubric-decision-simulation-engine-parity/46-CONTEXT.md` | D-01 through D-14, the locked decisions this record documents and, where superseded (D-06), records the supersession of |
| Wave 1 summary | `.planning/phases/46-rubric-decision-simulation-engine-parity/46-01-SUMMARY.md` | `compute_icp_score`'s additive `cfg` override, the zero-write simulation core |
| Wave 2 summary | `.planning/phases/46-rubric-decision-simulation-engine-parity/46-02-SUMMARY.md` | Full simulation build, live run findings, the D-02/D-03 live-vs-June-snapshot divergence first surfaced |
| June research snapshot (cross-check only, never source of truth) | `.planning/milestones/v0.7-phases/41-validation-data-import-end-to-end-proof/41-final-population.json` | Row-set cross-check reference the live simulation matched exactly (symmetric difference 0) |
| HubSpot Automation v4 PUT protocol | `.planning/milestones/v0.7-phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md` §"D-05 round-trip verdict" | The disable → edit → PUT → enable → validate → confirm protocol Plan 04 must follow for the two flows this decision touches (`4626124224`, `4634822085`) |
| Decision-record precedent | `.planning/milestones/v0.7-phases/39-path-decision-fit-score-verification/39-DECISION.md` | The nine-section structure and evidentiary tone this document follows |
| Rescoring backfill mechanism | `scripts/backfill_seed_company_scores.py` | The recommended Phase 49 re-score path; `HARD_CEILING_RECORDS = 25` is the gate Phase 49 must chunk around or raise with justification |

---

## Operator Sign-off

**Decision:** Accepted — "Accept all three (Recommended)". All three values proceed exactly as
recorded in this document: `base_score.org_type.individual_club_team = 15`,
`base_score.org_type.regulator = -20`, `graduated_deductions.gambling_operator` removed.

**Date:** 2026-08-11

**Substituted values (if override):** None. No lever was overridden from the recommendation
above.

**Downstream impact (if override):** Not applicable — Plans 04 and 05 execute with the values
exactly as recorded in this document; no revision needed.

**What the operator was shown before deciding:** the decision record above in full, the live
simulation numbers (14/66 rows move, all `individual_club_team` C→B; club-weight sensitivity
insensitive across 10/15/20 on this population), the D-07 standing-tiebreaker tension on D-02
and D-03 (both are score-only on live data — QRIC, Entain, and Sportsbet already carry
independent hard vetoes, so neither move tracks a live tier), and the parity red-window cost
(option (a): accept a bounded window from Plan 04's commit until Phase 49's re-score closes it).
The operator accepted the recommendation with both of these explicitly surfaced, not despite
them being omitted.

**Provenance:** received via the `/gsd-execute-phase` coordinator relay on 2026-08-11 (this
executor has no direct channel to the operator). Recorded per D-05's "Claude proposes, operator
signs off" flow, through the orchestrator layer that manages the operator conversation.

**D-09 publish note:** the shareable-artifact publish (simulation content, published outside the
repo for the sales/business sign-off conversation) could not be performed from this CLI
executor session — no artifact-publishing capability is available here. Deferred to the
orchestrator session, which will publish it after the phase completes. This is recorded as a
deferred step, not an unmet requirement; see `46-03-SUMMARY.md`.
