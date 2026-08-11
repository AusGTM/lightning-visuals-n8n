# Phase 46: Rubric Decision, Simulation & Engine Parity - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-11
**Phase:** 46-rubric-decision-simulation-engine-parity
**Areas discussed:** Club weight decision, Simulation deliverable, Known-bad inputs in the 66

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Club weight decision | Candidate values + what evidence settles it | ✓ |
| Simulation deliverable | Where the operator sees the re-tier; one weight or a sweep | ✓ |
| Known-bad inputs in the 66 | How to treat the 17 false vetoes and 18 blank org types | ✓ |
| Pending todos | 3 keyword-matched todos from `todo.match-phase` | |

**Notes:** Two candidate gray areas were dropped before presentation as already-decided —
simulation data source (ROADMAP.md fixes it to current live `lv_*` inputs) and the
unchanged-weight branch (success criteria 3/4 already specify trivial-pass and conditional
deploy).

---

## Club weight decision

### Q1 — Candidate weights to simulate

| Option | Description | Selected |
|--------|-------------|----------|
| 5 / 0 / −10 sweep | Status quo, neutral, mild deduction | |
| 5 vs 0 only | Binary, cheapest simulation | |
| You decide | Claude picks the candidate set from evidence | ✓ |

**User's choice:** You decide.
**Notes:** Superseded later in the discussion — the operator supplied explicit GTM direction that
moved the weight *up*, not down, so the candidate set became 15 (primary) with 10/20 as
sensitivity columns.

### Q2 — Decision authority

| Option | Description | Selected |
|--------|-------------|----------|
| Claude proposes, you sign off | `46-DECISION.md` + blocking checkpoint; 39-DECISION.md precedent | ✓ |
| Claude decides outright | Faster; no business owner in the loop | |
| You decide now, sim confirms | Weight stated up front, sim shows consequences only | |

**User's choice:** Claude proposes, operator signs off.

### Q3 — Tiebreaker when evidence and movement disagree

| Option | Description | Selected |
|--------|-------------|----------|
| Keep 5 — no movement, no change | A cosmetic edit still costs deploy + bounce + 66-record re-score | ✓ |
| Change anyway — rubric must be honest | Rubric is a business artifact people read | |
| Depends on how much movement | Threshold in the decision record | |

**User's choice:** Keep 5 — no movement, no change.
**Notes:** Recorded as standing policy (D-07), but it did **not** govern this phase's decision —
the operator's GTM direction overrode it explicitly. Preserved for future weight questions.

### Q4 — Operational reality (asked after clarification)

**Free-text from operator:** *"The sales teams consider individual racing/turf clubs a prime
target, below perhaps leagues, but definitely not in lower tiers. How should we adjust the rubric
using the existing levers and properties, without dramatically affecting other companies'
scores?"*

**Claude's response:** Presented `base_score.org_type.individual_club_team` as the only surgical
lever (per-org-type; geography/content/revenue all move every company), with the tier math for
weights 5/10/15/20/30, and flagged that raising it directly contradicts `icp-scoring.md`'s
strongest finding (club 19% over n=36 vs 34% baseline — and those 36 deals *are* the single-venue
racing clubs).

### Q5 — Club weight value

| Option | Description | Selected |
|--------|-------------|----------|
| Weight 15 — solid B (45) | Headroom above the B floor; larger turf clubs reach 55 | ✓ |
| Weight 10 — B at the boundary (40) | Fragile; any soft signal drops back to C | |
| Weight 20 — ties broadcaster (50) | Most direct contradiction of the 19%-vs-40% ordering | |
| Weight 30 — larger clubs reach A (70) | Clubs outrank producers; largest inversion | |

**User's choice:** Weight 15.
**Notes:** Presented alongside the measured blast radius — `individual_club_team` is **37 of 66**
records (56% of the scored population), so the lever is surgical across org types but sweeping
across records.

### Q6 — Regulator scope

| Option | Description | Selected |
|--------|-------------|----------|
| No — out of v0.9 scope | Roadmap scopes the phase to `individual_club_team` only | |
| Yes — include it | Decide both org-type weights sitting at 5 | |

**User's choice (free-text):** *"regulator can sit in the same weight as gambling_operator
currently does for org_type with −20 deduction, while gambling_operator can have the −20
deduction removed."*

**Claude's response:** Flagged three mechanical facts — (1) the gambling −20 is keyed on the
`lv_is_gambling_operator` **boolean**, not org type, so removing it reaches beyond the 2
`gambling_operator` records; (2) a regulator −20 is **new engine logic**, not a config edit, since
`graduated_deductions` has one boolean-driven key today; (3) a **third engine** exists that the
roadmap does not name — HubSpot flow `4626124224-org-type-score` — which any org-type weight
change must also reach.

### Q7 — Fold or defer the regulator/gambling changes

| Option | Description | Selected |
|--------|-------------|----------|
| Fold in — all three, one pass | Decided and re-scored once; larger parity surface | ✓ |
| Club only — defer the rest | Phase stays as roadmapped | |
| Club + gambling, defer regulator | Only the regulator needs new code | |

**User's choice:** Fold in — all three, one pass.

### Q8 — Gambling deduction removal scope

| Option | Description | Selected |
|--------|-------------|----------|
| All flagged — remove outright | Any company with the boolean stops losing 20 | ✓ |
| Only org_type=gambling_operator | Scoped; needs a code change, not a config delete | |
| Defer with regulator | Leave as-is this milestone | |

**User's choice:** All flagged — remove outright.
**Follow-up question from operator:** *"Should we create a new boolean property
`lv_is_regulator`?"*

### Q9 — `lv_is_regulator` (three rounds)

**Round 1 — Claude recommended no**, on three grounds: it's explicitly out of scope
(`REQUIREMENTS.md` no-new-properties, operator decision 2026-08-11); it would sit blank on all 712
records and fire on nobody until Phase-48-scale enrichment populated it; and boolean semantics are
wrong because regulation overlaps governance in AU racing.

**Round 2 — operator granted a narrow exception**, reasoning that QRIC is already scored and *is*
a regulator. Claude corrected one fact: QRIC (`16047156820`) is **already** captured as
`lv_org_type=regulator`, so the org-type lever hits it today with no new property; the boolean's
only additional reach is the overlap case.

**Round 3 — operator asked for research**: *"do regulators overlap with governing bodies? I
suspect they may do."*

**Research finding (from portal data):** Yes, and jurisdiction-dependent.

| Record | Classified | Regulatory role |
|---|---|---|
| Racing and Wagering WA (`9605284722`) | `governing_body_league` | Fused — controlling authority **and** regulator. **A won deal**, named in `icp-scoring.md` §4's primary win list. |
| Racing NSW (`15008671672`) | `governing_body_league` | Statutory integrity/stewarding functions. |
| Racing Queensland (`9648957286`) + QRIC (`16047156820`) | `governing_body_league` + `regulator` | Split — separate legal entities. |

A boolean would flag RWWA and cost −20 on an already-won account inside the 83%-win segment.

| Option | Description | Selected |
|--------|-------------|----------|
| `lv_org_type=regulator` only | Catches QRIC, leaves RWWA/Racing NSW untouched; zero portal write | ✓ |
| Create `lv_is_regulator` anyway | Narrow exception; accepts the RWWA over-penalty | |
| Property exists, org_type triggers | Schema write for no behavioural change | |
| Researcher settles it | Defer the decision to planning | |

**User's choice:** `lv_org_type=regulator` only.
**Notes:** No-new-properties constraint survives the milestone unbroken. Statutory detail flagged
as a low-priority researcher confirmation; the split-vs-fused pattern is visible in portal data
independent of it.

---

## Simulation deliverable

| Option | Description | Selected |
|--------|-------------|----------|
| Markdown report in `.planning/` | Greppable, diffable, lives with phase artifacts | |
| Published artifact (shareable link) | Better for the business sign-off audience | |
| CSV | Best for pivoting, worst for narrative | |
| Markdown + artifact | Commit the markdown, publish the same content | ✓ |

**User's choice:** Markdown + artifact.
**Notes:** Output should be written so Phase 49's RESCORE-03 before/after reporting can reuse it
directly rather than regenerating.

---

## Known-bad inputs in the 66

| Option | Description | Selected |
|--------|-------------|----------|
| As-is + annotated | Faithful current state, affected rows flagged | ✓ |
| As-is + projected column | Adds post-Phase-47/48 projection; speculative for the 18 | |
| As-is only | Simplest; 17 records read as genuine D and distort the judgement | |

**User's choice:** As-is + annotated.

---

## Post-discussion addendum — documentation sync folded in

**Operator, after the summary:** *"Fold in docs update into this phase to reflect the decisions
we've made."*

No options presented — a direct scope instruction, actioned. Claude inventoried the live doc
sites carrying superseded values (11 locations across `docs/business/icp-scoring.md`, `CLAUDE.md`
§10, `.planning/intel/*`, `docs/WEB-RESEARCH-SPEC.md`), recorded them as **D-13**, and added
**D-14** guarding the business doc's evidentiary voice — the 19%/n=36 finding stays on the page
with the override recorded beside it, rather than the evidence being rewritten to agree.

Archived artifacts under `.planning/milestones/` (~12 files quoting the old org-type map) were
deliberately excluded — historical record, load-bearing for audit.

In the same pass, `ROADMAP.md` Phase 46 and `REQUIREMENTS.md` RUBRIC-01/RUBRIC-03 were amended to
match the widened scope, so `gsd-verifier`'s goal-backward check does not read the regulator,
gambling, third-engine, and docs work as unrequested. Commit `8c210f8`.

## Claude's Discretion

- Candidate weight set for the simulation (operator answered "you decide", then directed the club
  value) — Claude locks 15 as primary, may add 10/20 sensitivity columns.
- Annotation format and threshold for the flagged rows in the simulation report.
- Whether the regulator −20 is expressed as a new `graduated_deductions` key or as a negative
  value in the existing org-type map — whichever ports most cleanly across all three engines.

## Deferred Ideas

- `lv_is_regulator` boolean property — investigated and rejected; revisit only if the
  no-new-properties constraint is lifted, and only with an answer for fused-role jurisdictions.
- Association-aware club scoring ("a club linked to an already-won governing body is worth working
  directly") — the rubric has no association signal; own phase.
- `lv_sponsorship_reliant` as a scoring component — populated but unscored; `icp-scoring.md` §3
  found it drives deal *value*, not conversion.
- Revenue-band deduction calibration — already deferred to v1.0 as EVID-02.
- Re-examining the `governing_body_league` bucket's internal mix (§4 warns it is "slightly mixed").

## Pending todos reviewed, not folded

Three matched via `todo.match-phase 46` on keywords only; none in scope for a zero-write rubric
phase: enrichment throughput (0.90), sweep crontab pinned path (0.60), UAT 2.2 header aliases
(0.60).
