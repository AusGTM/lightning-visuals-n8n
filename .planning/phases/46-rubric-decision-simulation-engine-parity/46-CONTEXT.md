# Phase 46: Rubric Decision, Simulation & Engine Parity - Context

**Gathered:** 2026-08-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Decide the `individual_club_team` weight (and, folded in during discussion, the `regulator`
weight and the `gambling_operator` deduction) with a recorded, evidence-traceable rationale;
simulate how the 66 currently-scored companies re-tier under the proposed weights **writing
nothing to any HubSpot record**; and prove the change lands identically in every scoring engine
before Phase 47 (veto remediation) or Phase 48 (coverage enrichment) touch a record.

**Scope grew during discussion, deliberately — twice.** ROADMAP.md scoped this to
`individual_club_team` alone. The operator folded in two more org-type levers (D-02, D-03) so
all rubric changes are decided once and the population re-scores once rather than three times,
then folded in **documentation sync** (D-13) so no doc still prints the superseded rubric after
the change ships. RUBRIC-01/02/03 still frame the work; ROADMAP.md and REQUIREMENTS.md were
amended on 2026-08-11 to match the widened scope.

**Not in this phase:** clearing the 17 false vetoes (Phase 47), enriching the 18 blank
`lv_org_type` records (Phase 48), executing the full-population re-score (Phase 49).

</domain>

<decisions>
## Implementation Decisions

### Rubric weights (the decision itself)

- **D-01:** `base_score.org_type.individual_club_team` moves **5 → 15**. An AU club producing
  content scores 15 + 20 (content) + 10 (geo) = **45 → Tier B**; a larger turf club with
  revenue 5–500M reaches 55. Rationale is **operator GTM direction, explicitly overriding the
  closed-deal evidence**: sales treats individual racing/turf clubs as a prime target ranking
  just below leagues, not a nurture tier. `docs/business/icp-scoring.md` §3/§4 reads the other
  way — Club/Team wins **19% over n=36** against a 34% baseline, and §4 names them anti-ICP
  ("reach them via their governing body, not directly"). RUBRIC-01 requires the decision be
  *evidenced and recorded*, not that it follow the evidence; the decision record must state the
  override and its reasoning plainly. 15 was chosen over 10 (40 = fragile B floor, any soft
  signal drops back to C), over 20 (ties broadcaster/producer, hardest contradiction of the
  19%-vs-40% ordering), and over 30 (clubs outrank producers and reach Tier A).
  — **Reversibility:** costly — undo means re-scoring the whole 66-company population again
  (RESCORE-02: no `lv_icp_scoring_version` exists, so segmentation is impossible), plus reverting
  three separate engines.

- **D-02:** `base_score.org_type.regulator` moves **5 → 0**, and a **new org-type-driven −20
  graduated deduction** fires when `lv_org_type = regulator`. Net: an AU regulator producing
  content goes 35 (C) → 10 (**Unscored**). Rationale: `icp-scoring.md` §4 flags the
  governing-body bucket as mixed — "QRIC is a regulator, not a content buyer" — and a regulator
  is not a sports-media buyer. Affects 1 record today (QRIC, `16047156820`).
  — **Reversibility:** costly — this is new engine logic (see D-06), not a config value, in three
  engines.

- **D-03:** The **gambling −20 deduction is removed outright**, for all companies carrying
  `lv_is_gambling_operator = true` regardless of org type. An AU gambling operator producing
  content goes 10 (Unscored) → 30 (**Tier C**). Contradicts `icp-scoring.md` §4, which
  deliberately made gambling a graduated deduction rather than a veto so operators stay
  "targetable proactively where other fit signals are strong" — record the override. Affects 2
  records; one (Entain `10024564084`) stays Tier D on a genuine non-ANZ veto, so ~1 record
  actually moves.
  — **Reversibility:** reversible — deleting/restoring one config key plus its port sites.

- **D-04:** **No new HubSpot properties.** `lv_is_regulator` was proposed and rejected after
  investigation. The `REQUIREMENTS.md` no-new-properties constraint holds unbroken.

  The decisive argument is data, not policy: regulation in AU racing is **jurisdiction-dependent**
  and overlaps governance. Queensland *splits* it — Racing Queensland (`9648957286`,
  `governing_body_league`) and QRIC (`16047156820`, `regulator`) are separate legal entities, which
  is why QRIC exists as its own record. Western Australia *fuses* it — **Racing and Wagering WA**
  (`9605284722`) is classified `governing_body_league` and is **a won deal** named in
  `icp-scoring.md` §4's primary win list. Racing NSW (`15008671672`) carries statutory integrity
  functions under the same classification.

  A boolean asks "does it regulate?" and answers **yes** for RWWA — landing −20 on an account
  already won, inside the 83%-win segment. `lv_org_type` is single-valued, so it asks "what is
  this org *primarily*?" — catching QRIC and leaving RWWA and Racing NSW untouched. The
  single-valued classification is the *safer* lever, not merely the cheaper one. A new boolean
  would also sit blank on all 712 companies (inert until enrichment is extended and a run touches
  every record — Phase 48-scale spend against an 18-record scope).

  Researcher may confirm the statutory detail; the QLD-split-vs-WA-fused pattern is visible in
  the portal data independent of the legal specifics, so this decision does not block on it.

### Authority and decision record

- **D-05:** **Claude proposes, operator signs off.** Claude writes `46-DECISION.md` carrying the
  evidence, the simulation output, and a recommendation; the phase does not close until the
  operator accepts or overrides. Follows the `39-DECISION.md` precedent. The planner should
  place a **blocking checkpoint** before the phase seals.

- **D-06:** The regulator −20 is **new engine logic, not a weight edit**. `graduated_deductions`
  in `config/icp_scoring.yaml` holds exactly one key today (`gambling_operator`), and
  `src/icp_scoring.py:89` fires it on the `lv_is_gambling_operator` **boolean**, independent of
  `lv_org_type`. An org-type-driven deduction needs a new branch written into the Python oracle
  *and* hand-ported into the JS. This is the split-brain shape v0.7 already paid for once —
  the parity harness must cover it, not inspection.

- **D-07:** Default rule for future weight decisions, recorded before the operator's GTM
  direction arrived and **kept as policy even though it did not govern this one**: *if evidence
  argues a weight down but the simulation shows near-zero tier movement, keep the current
  weight* — a change with no tier consequence still costs a deploy, a bounce, and a full 66-record
  re-score (~66 executions against the 2,500/month allowance). D-01/D-02/D-03 were directed on
  explicit GTM grounds, not derived from simulation movement, so this rule was not the deciding
  factor here. Record it in `46-DECISION.md` as the standing tiebreaker.

### Simulation

- **D-08:** Simulation reads **current live `lv_*` inputs** and **writes nothing to any HubSpot
  record**. Fixed by ROADMAP.md. `config/june_candidates.json` is a **June snapshot**, not
  "current" — it may be used to cross-check, never as the source of truth (see Open Questions).

- **D-09:** Deliverable is **markdown committed under `.planning/` *and* the same content
  published as an artifact** (shareable link for the sales/business sign-off conversation).
  Per-company before/after score and tier, plus a tier-distribution summary. This output feeds
  RESCORE-03's plain-language before/after directly — write it so Phase 49 can reuse it.

- **D-10:** The 17 false-veto records and 18 blank-`lv_org_type` records sit inside the 66 and are
  simulated **as-is, with annotation**. Faithful to current live state — no projected or
  speculative column — but every affected row is flagged so the 17 are not misread as genuine
  Tier D and the 18 are not misread as genuine unknowns. Without the annotation, 17 records read
  as D for reasons unrelated to the weight change and distort the judgement.

### Engine parity

- **D-11:** **There are three engines, not two.** RUBRIC-03 names only `config/icp_scoring.yaml`
  (Python oracle) and the JS port compiled into `n8n/wf_enrichment_cloud.json`. A third exists:
  the HubSpot workflow `config/hubspot_flows/4626124224-org-type-score.*.json`, which maps
  `lv_org_type` → points natively and feeds `lv_icp_fit_score`. **Every org-type weight change in
  this phase must land there too**, via the Automation v4 API, or HubSpot's own score diverges
  from the pipeline's. `tests/test_flow_rubric_conformance.py` guards this surface.
  Phase 40's `PORTAL-FACTS.md` records the hard-won API constraints for editing these flows.
  This applies to D-01 regardless of what else is decided.

- **D-12:** If a weight reaches the live workflow, it does so **only** via
  `scripts/build_cloud_workflows.py` → deploy → bounce, with a **read-back of the running (not
  merely stored) workflow** confirming the new value is what actually executes. A bare PUT never
  reloads a running workflow.

### Documentation sync (folded in 2026-08-11)

- **D-13:** **Every doc that prints the superseded rubric is updated in this phase**, in the same
  pass as the config change — not left to drift. A weight table that disagrees with the engine is
  the same split-brain failure class as an unported JS value, just with humans as the consumer.
  The `46-DECISION.md` task owns this.

  **Live sites carrying values these decisions supersede** (verified 2026-08-11):

  | File | What goes stale |
  |---|---|
  | `docs/business/icp-scoring.md` §5 scoring model table | `Org: individual club \| +5` → 15 |
  | `docs/business/icp-scoring.md` §5 graduated-deductions table | `Gambling Operator \| −20` row is removed; a `regulator \| −20` row is added |
  | `docs/business/icp-scoring.md` §5 property-map table | "gambling and $500M+ revenue are graduated deductions" — gambling is no longer a deduction at all |
  | `docs/business/icp-scoring.md` §5 tier illustration | "**C** = individual club, AU, content → nurture via league" — becomes **B** |
  | `docs/business/icp-scoring.md` §4 anti-ICP bullets | Clubs listed as anti-ICP "suppress/disqualify"; gambling described as "graduated deduction, targetable" |
  | `CLAUDE.md` §10.1 (lines ~786, ~787, ~817) | Inline copy of `config/icp_scoring.yaml`: `individual_club_team: 5`, `regulator: 5`, `graduated_deductions.gambling_operator: -20` |
  | `CLAUDE.md` §10.3 | "Graduated deductions include: gambling_operator" |
  | `.planning/intel/constraints.md:46` | Machine-readable rubric mirror — full org-type map + deductions |
  | `.planning/intel/requirements.md:24` | "Gambling operators … are graduated deductions and must never set the anti-ICP flag" |
  | `docs/WEB-RESEARCH-SPEC.md:159` | Gambling "only drives graduated deductions, never a veto" |
  | `docs/WEB-RESEARCH-SPEC.md:483` | Australian Turf Club → "`individual_club_team` — low-score path" |

  **Do NOT edit:** anything under `.planning/milestones/` (v0.7 phase artifacts, `40-VERIFICATION.md`,
  `PORTAL-FACTS.md`, prior PLAN/SUMMARY files). Those are the historical record of what was true
  at the time and are load-bearing for audit. Roughly a dozen archive files quote the old org-type
  map; all stay verbatim.

  **`.planning/PROJECT.md` (lines 60, 239, 348) is also left as-is** — it frames `individual_club_team=5`
  as an *open question*, which remains accurate until this phase executes. It updates at milestone
  close, not here.

- **D-14:** `icp-scoring.md` is a **business sign-off document**, not a config mirror. The edit
  must preserve its evidentiary voice: the 19%/n=36 finding stays on the page, with the override
  and its GTM reasoning recorded next to it. Do not silently rewrite the evidence to agree with
  the new weight — that would destroy the record RUBRIC-01 depends on and mislead the next
  recalibration.

### Claude's Discretion

- Candidate weight set for the simulation. Operator answered "you decide", then directed the club
  value to 15. Claude locks **15 as the primary scenario** and may include **10 and 20 as
  sensitivity columns** so the operator sees how close the B boundary sits before signing off.
- The threshold/format of the annotation in D-10.
- Whether the regulator −20 is expressed as a new `graduated_deductions` key or a distinct
  org-type deduction map — whichever ports most cleanly across all three engines.

### Reviewed Todos (not folded)
None folded. See Deferred.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The evidence behind the decision
- `docs/business/icp-scoring.md` — the 92-closed-deal ICP validation. §3 assumption scorecard,
  §4 best-fit/anti-ICP (club 19% n=36, gambling as graduated deduction, "QRIC is a regulator"),
  §5 proposed scoring model and tier definitions. **This is the document RUBRIC-01 requires the
  decision to be traceable to** — including where the decision overrides it.

### The three scoring engines (D-11)
- `config/icp_scoring.yaml` — Python oracle weight table; `base_score.org_type` line 10 is
  `individual_club_team: 5`, line 11 `regulator: 5`; `graduated_deductions` holds only
  `gambling_operator`.
- `src/icp_scoring.py` — the oracle implementation; line ~89 is the boolean-driven gambling
  deduction, the site D-06's new branch sits beside.
- `n8n/wf_enrichment_cloud.json` — the deployed JS port (the *live* producer of scores).
- `scripts/build_cloud_workflows.py` — the only sanctioned path from config to the live
  workflow (D-12).
- `config/hubspot_flows/4626124224-org-type-score.after.json` — the **third** engine, HubSpot's
  native org-type→points mapper.
- `config/hubspot_flows/lv_icp_fit_score-property.after.json` — the calculated property summing
  the component scores.

### Parity harness
- `tests/test_scoring_parity.py` — two-tier parity suite (offline + live).
- `tests/scoring_fixtures.py` — shared fixtures.
- `scripts/run_scoring_parity.py` — the live parity runner producing the verdict artifact.
- `tests/test_flow_rubric_conformance.py` — guards the HubSpot flow surface against the rubric.

### Milestone framing and constraints
- `.planning/REQUIREMENTS.md` — RUBRIC-01/02/03; **Out of Scope** section carries the
  no-new-properties constraint that D-04 upholds and the `lv_icp_scoring_version` exclusion that
  forces whole-population re-scores.
- `.planning/ROADMAP.md` §Phase 46 — success criteria 1–4, and the Phase 47/48/49 dependencies
  this phase gates.
- `.planning/PROJECT.md` — current tier distribution (A:7 B:18 C:17 D:24 across 66, 17 of the D
  being false vetoes) and the v0.9 goal statement.

### Docs that must be updated in this phase (D-13)
- `docs/business/icp-scoring.md` §4, §5 — business sign-off doc; scoring model table, graduated
  deductions table, property-map table, tier illustration. Preserve the evidence, record the
  override (D-14).
- `CLAUDE.md` §10.1, §10.3 — inline `icp_scoring.yaml` copy and the graduated-deductions prose.
- `.planning/intel/constraints.md`, `.planning/intel/requirements.md` — machine-readable rubric
  mirrors read by other agents.
- `docs/WEB-RESEARCH-SPEC.md` — gambling-deduction semantics and the ATC worked example.

### Operational gotchas that constrain how the change ships
- `.planning/milestones/v0.7-phases/` — `PORTAL-FACTS.md` (HubSpot Automation v4 PUT limits
  discovered live in Phase 40) and the `39-DECISION.md` precedent D-05 follows.
- `config/june_candidates.json` — the June 66-company snapshot. **Reference only, not the
  simulation source** (D-08).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/run_scoring_parity.py`** — already reads live records and compares against the
  oracle. The simulation is close to a read-only variant of this; extend or mirror rather than
  build fresh.
- **`tests/scoring_fixtures.py` + `tests/test_scoring_parity.py`** — the parity bar RUBRIC-03
  demands. Named `-k` selectors already exist per Phase 40's convention.
- **`src/icp_scoring.py::compute_icp_score`** — pure function over a record + candidate patch.
  A simulation can call it directly with a mutated config, no HubSpot write path involved.
- **`config/june_candidates.json`** — 66 rows with `_name`, `lv_org_type`,
  `lv_country_region_normalized`, `lv_produces_content`, `_evidence` URLs. Useful for
  cross-checking the live pull and for naming companies in the report.

### Established Patterns
- **Config → build → deploy → bounce → read-back running content.** A bare PUT never reloads a
  running n8n workflow (D-12). Phase 44's live evidence and the memory note on stored-vs-running
  content both apply.
- **Weight tables are per-value.** Changing one `org_type` key moves only records carrying that
  value — no cross-contamination between org types. This is why D-01/D-02 are surgical *by org
  type* even though D-01 moves the majority of records.
- **Rule 1 fallout is expected.** Phases 40/43 each found stale test assertions when scoring
  behaviour changed. Budget for fixture/assertion updates in all three engines' test surfaces.

### Integration Points
- `base_score.org_type` in `config/icp_scoring.yaml` → the JS port's org-type map in
  `wf_enrichment_cloud.json` → HubSpot flow `4626124224`. All three must move together or the
  portal's native score diverges from the pipeline's.
- `graduated_deductions` → `src/icp_scoring.py:89` branch → the JS port's equivalent → the
  HubSpot `gambling-score` flow (`config/hubspot_flows/gambling-score.after.json`). D-03's
  removal and D-02's addition both touch this chain.

### Blast radius (measured, June snapshot n=66)
```
individual_club_team   37   (56% of the scored population)  → D-01 moves these
broadcaster            12
governing_body_league  10
gambling_operator       2   → D-03 moves ~1 (Entain stays D on a genuine non-ANZ veto)
hardware_vendor         2
other                   2
regulator               1   → D-02 moves this one
```
D-01 alone re-tiers more than half the scored list. That is the real blast radius — surgical
across org types, sweeping across records — and it is why the simulation must run before sign-off.

</code_context>

<specifics>
## Specific Ideas

- Operator's framing, verbatim in substance: *"sales teams consider individual racing/turf clubs
  a prime target, below perhaps leagues, but definitely not in lower tiers"* — and the ask was
  explicitly to achieve this **using existing levers and properties, without dramatically
  affecting other companies' scores**. The org-type weight table satisfies that constraint
  exactly: no other org type moves a point.
- Tier A is unreachable for a typical single-venue club at any defensible weight — A needs 70,
  and a small club lacks the revenue-band points. "Below leagues, above nurture" lands at **B**,
  which is what D-01 delivers (45).
- The hard vetoes still filter regardless of these changes: a club with no broadcast content
  still vetoes to D, and non-AU still vetoes.
- Current weights already rank-order with win rate (league 40 / 83%, broadcaster 20 / 40%,
  club 5 / 19%). D-01 compresses that ordering but does not invert it — clubs at 15 still sit
  below broadcaster/producer at 20.

</specifics>

<deferred>
## Deferred Ideas

- **`lv_is_regulator` boolean property** — investigated and rejected this phase (D-04). If the
  no-new-properties constraint is ever lifted, the open question is how to handle fused-role
  jurisdictions like RWWA without penalising won accounts.
- **Association-aware club scoring** — "a club linked to an already-won governing body is worth
  working directly; a standalone single-venue club is not." Raised during discussion as a real
  GTM distinction. The current rubric has no association-aware signal and cannot express it.
  Own phase.
- **`lv_sponsorship_reliant` as a scoring component** — the property exists and is populated, but
  is not a scoring input today. `icp-scoring.md` §3 found it drives deal *value* ($27k vs $9k),
  not conversion — so it may belong in a value/priority signal rather than the fit score.
- **Revenue-band deduction calibration** (−5 at 500–750M, −50 at 1.2B+) — deferred to v1.0 as
  EVID-02; untouched here.
- **Re-examining the `governing_body_league` bucket's internal mix** — `icp-scoring.md` §4 warns
  the bucket is "slightly mixed" and shouldn't be treated as monolithic. Out of scope.

### Reviewed Todos (not folded)
Three pending todos keyword-matched Phase 46 via `todo.match-phase`; the operator did not select
them for discussion, and none is in scope for a phase that writes nothing to a record:
- **Enrichment throughput — 82% of every full run is two sequential Anthropic calls** (score 0.90,
  area `n8n`) — a runtime-cost concern for enrichment runs. Phase 48 territory at the earliest.
- **Sweep crontab pins a versioned plugin path** (score 0.60, `operator-claude-plugin`) — v0.8-era
  deferral, admin/install concern, unrelated to rubric weights.
- **UAT 2.2 names two header aliases the column mapping does not support** (score 0.60) — contact
  ingestion, not company scoring.

</deferred>

<open_questions>
## Open Questions for the Researcher

1. **Enumerate "the 66" live.** `PROJECT.md` says 66 scored with distribution A:7 B:18 C:17 D:24,
   but Phase 43-04 recorded "exactly 1 of 712 companies carries a live ICP score". Phase 41's
   June run presumably backfilled the rest — **verify, do not assume**, and establish the
   authoritative live query the simulation pulls from.
2. **Reconcile blank `lv_org_type` counts.** `config/june_candidates.json` has **zero** blanks
   across its 66 rows, yet REQUIREMENTS.md COVER-01 says **18** scored companies have no
   `lv_org_type` live. Either the snapshot's org types were derived offline and never written,
   or the live set differs from the June set. This changes what D-10's annotation must cover.
3. **Locate the JS port's org-type weight table** in `n8n/wf_enrichment_cloud.json` /
   `scripts/build_cloud_workflows.py` — is it generated from `config/icp_scoring.yaml` or
   hand-maintained? A generated table makes D-01/D-02 near-free; a hand-ported one is the
   split-brain risk RUBRIC-03 exists to catch.
4. **Confirm the HubSpot flow `4626124224` is live and authoritative** for org-type points, and
   whether `tests/test_flow_rubric_conformance.py` asserts the *values* or only the structure.
5. **Determine how a new org-type-driven deduction (D-02/D-06) ports** into the JS and into
   HubSpot's flow model — HubSpot's mapper flows are branch-per-value, so a −20 for `regulator`
   may be expressible as a weight of −20 in the existing org-type flow rather than a separate
   deduction component. If so, D-02 collapses from "new engine logic" to a weight edit; confirm
   before planning around the harder shape.
6. **Estimate Phase 49's cost consequence.** All three changes re-tier a large share of the 66,
   so a full-population re-score is owed. State the execution count against the 2,500/month
   allowance up front (RESCORE-02).
7. *(Low priority — decision already made, does not block)* Confirm the AU racing
   governance/integrity statutory split per jurisdiction, to firm up D-04's rationale in the
   decision record.

</open_questions>

---

*Phase: 46-rubric-decision-simulation-engine-parity*
*Context gathered: 2026-08-11*
