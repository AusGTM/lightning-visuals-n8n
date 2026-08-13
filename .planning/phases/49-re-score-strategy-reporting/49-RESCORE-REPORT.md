# v0.9 Re-score Report — What Changed on the Target List, and What Didn't

Plain-language summary for the operator. Every number below comes from a committed file, not
from memory or a hand-typed estimate — see the "Source" line under each section. This report
covers the whole v0.9 milestone's effect on the scored target list, not only this final phase.

---

## 1. The denominator — read this line first

**Only 66 of the 712 companies in the portal have ever carried a score.** That is under 9% of
the portal. Every tier count in this report — every "A", "B", "C", "D", "Unscored" — describes
that 66-company fraction, not the other 646 companies, which have no score at all and are not
part of any distribution below.

*Source: `HAS_PROPERTY(lv_icp_fit_score)` live count, re-derived 2026-08-13
(`49-P2-SNAPSHOT.json` / `49-P3-SNAPSHOT.json`, `population_count: 66`); portal total from
`CLAUDE.md`'s live property census.*

**One line up front: this milestone's own acceptance check does not pass cleanly — it is
honestly red on 4 of the 66 companies, not forced green. See §9 for what, why, and the
scheduled fix.**

---

## 2. Three points, three tier distributions

| Point | When | What it captures | A | B | C | D | Unscored |
|---|---|---|---|---|---|---|---|
| **P1 — entry** | 2026-08-11, before any v0.9 write | The rubric as it stood before this milestone touched anything | 7 | 18 | 17 | 24 | 0 |
| **P2 — pre-re-score** | 2026-08-13, before this phase's write window opened | P1 **plus** the veto clear (phase 47), the veto recompute (phase 47.5), and the coverage enrichment (phase 48) | 9 | 27 | 21 | 7 | 2 |
| **P3 — post-re-score** | 2026-08-13, after this phase's write window settled | P2 **plus** this phase's weight re-score (the `individual_club_team`, `regulator`, and gambling-deduction changes) | 9 | 41 | 7 | 7 | 2 |

*Source: `.planning/phases/46-rubric-decision-simulation-engine-parity/46-simulation-20260811.json`
(P1, its live column), `49-P2-SNAPSHOT.json` (P2), `49-P3-SNAPSHOT.json` (P3) — all three
re-derived live and dated, none hand-typed. Rendered by `scripts/build_rescore_report.py`.*

Each pair of points isolates a different lever, deliberately, so no single number blends two
different causes together:

- **P1 → P2** is everything that happened *before* this phase's write window: clearing false
  vetoes that a stale bug had fired against companies with no region on file, recomputing two
  veto records under a corrected rule, and filling in blank company-type data for five records
  that had never been researched. **None of this movement was caused by the weight change** —
  the weight change had not run yet.
- **P2 → P3** is *only* this phase's weight change — three rubric weights (racing clubs raised,
  regulators lowered, the gambling deduction removed) applied to every one of the 66 scored
  companies in one write window. **Nothing else happened between these two reads** — no veto
  work, no new research — so every movement in this pair is the weight change, and only the
  weight change.

---

## 3. What each movement means for how the account gets worked

Every row below is `scripts/build_rescore_report.py`'s own rendered output against the three
committed snapshots — reproduced verbatim, not retyped, so no name, id, or number here can drift
from the source data.

### P1 → P2 (18 companies changed tier)

| Name | HubSpot ID | P1 Tier | P2 Tier | P1 Score | P2 Score | Delta |
|---|---|---|---|---|---|---|
| Rockhampton Jockey Club | 9604732795 | D | B | 10 | 55 | +45 |
| Tweed Valley Jockey Club | 9604732797 | D | B | 0 | 45 | +45 |
| Bunbury Turf Club | 9604738976 | D | C | 0 | 45 | +45 |
| The Alice Springs Turf Club | 9604787229 | D | B | 10 | 55 | +45 |
| Sapphire Coast Turf Club (Bega Valley) | 9604794661 | D | B | 0 | 45 | +45 |
| Port Macquarie Race Club | 9605273630 | D | C | 0 | 45 | +45 |
| Thoroughbred Park | 10152138518 | D | B | 10 | 55 | +45 |
| Wyong | 10215097384 | D | B | 10 | 55 | +45 |
| Coffs Harbour Racing Club | 14752488879 | D | Unscored | 0 | 25 | +25 |
| Racing NSW | 15008671672 | B | A | 40 | 80 | +40 |
| GRAVITY MEDIA | 15860277364 | D | B | 50 | 60 | +10 |
| Ironman | 17317184159 | D | A | 70 | 80 | +10 |
| Editix | 17317381378 | D | Unscored | 0 | 0 | +0 |
| Pinjarra Park | 17696004613 | D | C | 0 | 45 | +45 |
| The Kalgoorlie-Boulder Racing Club | 18796602894 | D | B | 10 | 55 | +45 |
| Newcastle Harness Racing Club | 19100977027 | D | C | 0 | 45 | +45 |
| Waikato Racing Club Inc | 20538284384 | D | B | 0 | 45 | +45 |
| The Rumble / Pacific Action Sports | 20943964946 | D | B | 10 | 60 | +50 |

**Twelve clubs** (Rockhampton Jockey Club `9604732795`, Tweed Valley Jockey Club `9604732797`,
Bunbury Turf Club `9604738976`, The Alice Springs Turf Club `9604787229`, Sapphire Coast Turf
Club `9604794661`, Port Macquarie Race Club `9605273630`, Thoroughbred Park `10152138518`,
Wyong `10215097384`, Coffs Harbour Racing Club `14752488879`, Pinjarra Park `17696004613`, The
Kalgoorlie-Boulder Racing Club `18796602894`, and Newcastle Harness Racing Club `19100977027`)
were reading **Tier D for the wrong reason**: a data bug was treating "we never recorded this
company's region" as if it meant "this company is not in Australia or New Zealand," which fired
a hard exclusion (a "veto") that should never have fired. Once that bug was fixed and the flag
cleared, eleven of the twelve landed in **B or C** and are **back on the target list**, not new
additions. The twelfth, **Coffs Harbour Racing Club `14752488879`**, landed at **`Unscored`**,
not a tier — see Editix below and §7 for why that distinction matters.

Two companies had the same region bug but needed a second, deliberate write window to
re-examine and clear (rather than an automatic bulk fix), because clearing a hard exclusion on a
specific record needs a human look, not a blanket rule. **Ironman `17317184159`** moved D → A
and is now a **direct-outreach priority**. **GRAVITY MEDIA `15860277364`** moved D → **B**, not
A — worked directly, but not at the same priority as a governing body.

Four companies got a company-type on file for the first time: **Racing NSW `15008671672`**
(governing body, on an operator-reviewed correction — the first research pass mis-typed it),
**Waikato Racing Club Inc `20538284384`**, and **The Rumble / Pacific Action Sports
`20943964946`** all moved up, and **Editix `17317381378`** was researched and found to have no
identifiable web presence at all. Racing NSW landed at **Tier A** — the single largest jump in
this report (score 40 → 80) — meaning it should be worked as a top-priority direct account, the
same tier as a governing body like Racing Queensland or Tasracing. Editix is correctly recorded
as **`Unscored`**, not Tier D — like Coffs Harbour above, see §7 for why that distinction
matters.

### P2 → P3 (14 companies changed tier — exactly the weight change's own advance forecast)

| Name | HubSpot ID | P2 Tier | P3 Tier | P2 Score | P3 Score | Delta |
|---|---|---|---|---|---|---|
| Tamworth Jockey Club | 9604738975 | C | B | 35 | 45 | +10 |
| South Australian Jockey Club | 9604753960 | C | B | 35 | 45 | +10 |
| Geraldton Turf Club | 9605284721 | C | B | 35 | 45 | +10 |
| Redcliffe Harness RC | 9680908136 | C | B | 35 | 45 | +10 |
| The Creek Agency | 9681041418 | C | B | 35 | 45 | +10 |
| Cairns Jockey Club | 10021900550 | C | B | 35 | 45 | +10 |
| Harness Racing ACT | 10152245364 | C | B | 35 | 45 | +10 |
| Scone Race Club | 14748141740 | C | B | 35 | 45 | +10 |
| Albury Racing Club | 14752422181 | C | B | 35 | 45 | +10 |
| Bunbury Trotting Club | 15388186399 | C | B | 35 | 45 | +10 |
| Shepparton Harness Racing Club | 18973591368 | C | B | 35 | 45 | +10 |
| Bathurst Harness Racing Club | 19099896622 | C | B | 35 | 45 | +10 |
| Bendigo Harness Racing Club | 19154355339 | C | B | 35 | 45 | +10 |
| RACE (Racing at Awapuni and Trentham Combined Enterprise Incorporated) | 20538599475 | C | B | 35 | 45 | +10 |

All 14 are **individual racing/harness clubs** whose company-type weight was raised under the
recalibrated rubric. Every one moved **C → B**. This confirms the rubric recalibration's stated
purpose: individual clubs were under-weighted relative to governing bodies, and this correction
now scores clubs closer to where their real deal history says they should sit. In practice: these
14 clubs should be worked **directly by the sales team**, not treated as lower-priority accounts
to be reached only through a governing body relationship.

*Source: `scripts/build_rescore_report.py`, run against `46-simulation-20260811.json` (P1),
`49-P2-SNAPSHOT.json` (P2), and `49-P3-SNAPSHOT.json` (P3). The 14-row P2→P3 count and shape
match `49-05-SUMMARY.md`'s independently-recorded observation and `46-SIMULATION-REPORT.md`'s
pre-registered forecast exactly.*

---

## 4. The milestone's best story: a record that moved with zero input change

**Simtech LED `18047161864`** is the one outcome in this whole milestone that no input edit
could have produced. As of 2026-08-12, it held **complete, correct data** — a hardware-vendor
company type, Australian region, a score of 40, and **Tier B**. HubSpot's own gate looked at
that record and said "nothing to do here, all fields present, fresh and valid" — it would not
even have been touched by an ordinary refresh. But a rule fix landed that phase (closing a gap
where a hardware-vendor exclusion could be missed if only one of two possible signals was set),
and when that fix's write window ran, it re-evaluated Simtech LED's *existing* data under the
*corrected* rule — with no field on the record changed at all — and correctly moved it from
**Tier B to Tier D**: suppressed as a hardware/AV vendor, not a sports-media buyer. That is what
"the rule changed, not the record" looks like in practice, and it is the reason a hard veto's
correctness matters independently of any research or data-entry work.

*Source: `.planning/phases/47.5-veto-recompute-path/47.5-RUN-REPORT.md` §2.2 (score 40 → 40
unchanged, tier B → D, no input PATCH sent).*

---

## 5. Score-only changes — the score moved, the tier did not

Some companies' underlying score number moved under the weight recalibration or the earlier veto
work, but their tier was the same at both endpoints of the pair being compared. Reporting these
as "tier movements" would be wrong — nothing changed about how the account should be worked —
but omitting them would understate what these changes actually did to the numbers behind the
tiers.

**P1 → P2 (2 companies, same tier — Tier D — at both endpoints):**

| Name | HubSpot ID | P1 Tier | P2 Tier | P1 Score | P2 Score | Delta |
|---|---|---|---|---|---|---|
| Jam TV | 17317850381 | D | D | 0 | 40 | +40 |
| Simtech LED | 18047161864 | D | D | 10 | 40 | +30 |

**Jam TV `17317850381`**: company-type filled in (broadcaster) by the coverage pass, but its
veto is **geographic** (it is an Italian broadcaster, not an ANZ one) and a company-type write
cannot clear a region-based exclusion. Still correctly vetoed.

**Simtech LED `18047161864`**: this P1→P2 row shows only its endpoints, D and D, and hides an
intermediate hop — between these two reads it briefly held **Tier B** (correct, complete data),
before the hardware-vendor rule fix described in §4 moved it back to D with no input change at
all. The full three-step story (D → B → D) is told in §4, not repeated as a simple score delta
here.

**P2 → P3 (13 companies, tier held throughout):**

| Name | HubSpot ID | P2 Tier | P3 Tier | P2 Score | P3 Score | Delta |
|---|---|---|---|---|---|---|
| Melbourne Racing Club | 9604614548 | C | C | 25 | 35 | +10 |
| Toowoomba Turf Club | 9605244179 | B | B | 45 | 55 | +10 |
| Brisbane Racing Club (BRC) | 9605284723 | B | B | 45 | 55 | +10 |
| Australian Turf Club | 9605284724 | B | B | 45 | 55 | +10 |
| Victoria Racing Club | 9605291627 | B | B | 45 | 55 | +10 |
| Auckland Thoroughbred Racing | 9680571285 | B | B | 45 | 55 | +10 |
| Sunshine Coast Turf Club | 9680907342 | B | B | 45 | 55 | +10 |
| Entain | 10024564084 | D | D | -70 | -50 | +20 |
| Gloucester Park | 15387953738 | B | B | 45 | 55 | +10 |
| Queensland Racing Integrity Commission | 16047156820 | D | D | 25 | 0 | -25 |
| Sportsbet | 17861423879 | D | D | 0 | 20 | +20 |
| Southside Racing | 18756544344 | B | B | 45 | 55 | +10 |
| Addington | 18756544407 | B | B | 45 | 55 | +10 |

Nine Tier-B individual clubs (Toowoomba Turf Club, Brisbane Racing Club, Australian Turf Club,
Victoria Racing Club, Auckland Thoroughbred Racing, Sunshine Coast Turf Club, Gloucester Park,
Southside Racing, Addington) and one Tier-C company (Melbourne Racing Club) gained +10 points
each as the weight recalibration applied — they were already correctly tiered, so the extra
points did not move them further. The remaining three are all Tier D and hard-excluded on their
own, unrelated grounds: **Queensland Racing Integrity Commission `16047156820`** dropped from 25
to 0 (the regulator weight fell from a small positive number to a firm negative one), still
excluded for having no broadcast/streaming content regardless of the weight change. **Sportsbet
`17861423879`** rose from 0 to 20 (the gambling deduction was removed entirely), still excluded
on the same no-content grounds. **Entain `10024564084`** rose from −70 to −50 under the weight
change alone; its own veto clearing is a separate, later event — see §8 below, it is not part of
this pair.

*Source: `scripts/build_rescore_report.py`'s score-only sections, computed from
`49-P2-SNAPSHOT.json` / `49-P3-SNAPSHOT.json`, and the P1 comparison from
`46-simulation-20260811.json`.*

---

## 6. The outcome against the prediction

Before this milestone's weight change was even decided, `PROJECT.md` recorded a prediction for
what the shape *should* look like once the false-veto remediation alone was done:

> **Predicted:** A:7 B:18 C:17+ D:7

**Actual (P3):** A:9 B:41 C:7 D:7 Unscored:2

**Verdict: partially held.** The **D count landed exactly on the predicted 7** — the false-veto
remediation did what it was expected to do, cleanly. But **B and C diverged well beyond the
prediction**: B came in more than double the forecast (41 vs. 18) and C came in well under it (7
vs. "17+"). The reason is not a miss — it is that the prediction was written *before* two levers
this milestone went on to use were decided: the coverage enrichment (filling in blank
company-type data, which the prediction could not have accounted for) and the weight
recalibration itself (the 14-club C→B move in §3, decided in a later phase). The prediction is
reported here rather than quietly dropped, and the gap is attributed to those two levers landing
after the prediction was written, not to any error in the remediation work itself.

*Source: `PROJECT.md` ("a correct post-remediation shape is roughly A:7 B:18 C:17+ D:7"),
compared against `49-P3-SNAPSHOT.json`.*

---

## 7. What this does not say

Four things this milestone's evidence does not establish, stated plainly rather than smoothed
over:

- **The score is a fit heuristic, derived from 92 closed deals — it is not a forecast.** A high
  score means "this company's profile resembles the ones that have historically won," not "this
  company will close."

- **Gravity Media `15860277364`'s ANZ classification rests on Australian operating presence
  alone.** Its New Zealand leg is **unproven**. The "ANZ" label here denotes a
  multinational-with-local-operations pattern, not a confirmed count of countries the company
  operates in.

- **Editix `17317381378` reads `Unscored`, and that is deliberately not the same thing as Tier
  D.** A blank means the company was never researched at all; `Unscored` means research was
  attempted and returned nothing usable (in Editix's case, no identifiable web presence matched
  the company name and domain). Treating the two as equivalent would erase a distinction a prior
  phase built specifically so a "nobody has looked yet" record is never confused with a "looked,
  and there was nothing to find" record.

- **Every Anthropic dollar figure anywhere in this milestone is a floor, never a measurement.**
  The web-research code path this milestone uses does not log token usage, so no dollar amount
  from any research call in v0.9 — including the Entain research below — can be reported as an
  actual spend. Every dollar figure carried forward from earlier phases (the $0.0686/record
  figure cited in this run's cost table) is a lower bound only.

---

## 8. Entain's outcome and Jam TV's retained veto

**Jam TV `17317850381` retains its exclusion, unconditionally, and correctly.** It is an Italian
broadcaster (`jamtv.it`); its exclusion is geographic (non-ANZ), and no company-type write can
or should clear it. A live, dated check on 2026-08-13 confirms it is still excluded for exactly
this reason.

**Entain `10024564084` is now `Unscored` — it is not a re-added prospect, and it is not Tier
D.** This milestone re-examined both of Entain's two exclusion reasons (region, and "does this
company produce broadcast/streaming content") against registry-grade evidence — a federal court
filing and industry press coverage of its Australian racing-media brands — and both cleared the
evidence bar required to reconsider a hard exclusion. Once cleared, Entain's revenue band (over
$1.2 billion) triggers a large negative deduction under the current rubric, which places it below
every graded tier. **The correct, honest way to read this: Entain is no longer hard-excluded, but
it also does not currently qualify for a workable tier under this rubric.** It should not be
treated as returned to the active target list, and it should not be treated as suppressed either
— it sits in a third state the rubric is designed to produce for exactly this situation.

**One note on timing:** this Entain outcome happened in a separate write window *after* the P3
snapshot above was captured. P3's Tier-D count of 7 still includes Entain as it stood before that
window — this section reports its true, current state, on top of P3, not folded into P3's own
numbers. Accounting for it, the milestone's final position across all three levers plus this
last window is **A:9 B:41 C:7 D:6 Unscored:3**.

*Source: `49-W2-RECORD.md` §§7, 10-11 (the transition proof and the census); `49-ENTAIN-EVIDENCE.json`
(the evidence and the bar it cleared); `49-06-SUMMARY.md`.*

---

## 9. The acceptance sweep — honestly red, not forced green

This milestone's own acceptance check (`scripts/run_scoring_parity.py`, which compares every
scored company's live tier against what the rubric says it should be) does **not** pass cleanly.
**4 of the 66 companies show the correct score but a stale tier**, and this is stated here
plainly rather than buried:

| Company | ID |
|---|---|
| Port Macquarie Race Club | `9605273630` |
| Bunbury Turf Club | `9604738976` |
| Pinjarra Park | `17696004613` |
| Newcastle Harness Racing Club | `19100977027` |

**Cause:** all four already held the correct new-weight score *before* this phase's write window
ran (an earlier, unrelated update had already set them correctly). When this phase's write sent
the same, already-correct values back to HubSpot, HubSpot recognised nothing had changed and
fired no update event — so the automation that re-grades a company's tier from its score never
ran for these four. Their score is right; their tier display is one step behind it.

**Fix, scheduled, not done here:** a proven design exists (`TIER-DERIVATION-SPIKE-2026-08-13.md`)
to make the tier calculate directly from the score, the same way the score itself already
calculates directly from its inputs — removing this class of gap entirely. It requires adding
one new field to the CRM, which this milestone's scope explicitly excludes, so it is scheduled
for the next phase of work rather than done here. These four records are logged
(`.planning/WINDOWS.md`, entries 9–12) so they are not forgotten before that fix lands.

*Source: `49-PARITY-VERDICT.json` (the genuine, unedited sweep result); `49-W1-ARM-RECORD.md`;
`.planning/WINDOWS.md` ids 9–12.*
