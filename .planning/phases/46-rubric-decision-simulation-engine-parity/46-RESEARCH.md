# Phase 46: Rubric Decision, Simulation & Engine Parity - Research

**Researched:** 2026-08-11
**Domain:** ICP scoring rubric change management, cross-engine parity (Python oracle +
HubSpot Automation v4), read-only simulation over live CRM data
**Confidence:** HIGH for engine-mechanics findings (all verified by reading source this
session and running code locally); MEDIUM for the "66 currently scored" live count (best
available evidence is a 3-day-old committed snapshot, not a live read this session —
credentials/`.env` are permission-blocked in this sandbox); LOW/deferred for the AU
racing statutory detail (non-blocking per CONTEXT.md).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

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
  engines. *(This research's Open Question 5 finding: the net arithmetic is identical to setting
  `base_score.org_type.regulator: -20` directly — see below. The "new engine logic" framing does
  not survive contact with the code; recommend the direct-weight-edit shape.)*

- **D-03:** The **gambling −20 deduction is removed outright**, for all companies carrying
  `lv_is_gambling_operator = true` regardless of org type. An AU gambling operator producing
  content goes 10 (Unscored) → 30 (**Tier C**). Contradicts `icp-scoring.md` §4, which
  deliberately made gambling a graduated deduction rather than a veto so operators stay
  "targetable proactively where other fit signals are strong" — record the override. Affects 2
  records; one (Entain `10024564084`) stays Tier D on a genuine non-ANZ veto, so ~1 record
  actually moves.
  — **Reversibility:** reversible — deleting/restoring one config key plus its port sites.

- **D-04:** **No new HubSpot properties.** `lv_is_regulator` was proposed and rejected after
  investigation. The `REQUIREMENTS.md` no-new-properties constraint holds unbroken. The decisive
  argument is data, not policy: regulation in AU racing is jurisdiction-dependent and overlaps
  governance — Queensland *splits* it (Racing Queensland `governing_body_league` vs. QRIC
  `regulator`, separate legal entities), Western Australia *fuses* it (Racing and Wagering WA
  `9605284722` is `governing_body_league` and **a won deal**). A boolean would flag RWWA and cost
  −20 on an already-won account inside the 83%-win segment; `lv_org_type` is single-valued and
  catches QRIC without touching RWWA/Racing NSW.

- **D-05:** **Claude proposes, operator signs off.** Claude writes `46-DECISION.md` carrying the
  evidence, the simulation output, and a recommendation; the phase does not close until the
  operator accepts or overrides. Follows the `39-DECISION.md` precedent. The planner should
  place a **blocking checkpoint** before the phase seals.

- **D-06:** The regulator −20 is **new engine logic, not a weight edit** *(per CONTEXT.md — this
  research's Open Question 5 finding disputes the premise; see the Open Questions section
  below for the direct-execution proof that it collapses to a weight edit)*.

- **D-07:** Default rule for future weight decisions, recorded before the operator's GTM
  direction arrived and **kept as policy even though it did not govern this one**: *if evidence
  argues a weight down but the simulation shows near-zero tier movement, keep the current
  weight* — a change with no tier consequence still costs a deploy, a bounce, and a full 66-record
  re-score. D-01/D-02/D-03 were directed on explicit GTM grounds, not derived from simulation
  movement, so this rule was not the deciding factor here. Record it in `46-DECISION.md` as the
  standing tiebreaker.

- **D-08:** Simulation reads **current live `lv_*` inputs** and **writes nothing to any HubSpot
  record**. `config/june_candidates.json` is a **June snapshot**, not "current" — it may be used
  to cross-check, never as the source of truth.

- **D-09:** Deliverable is **markdown committed under `.planning/` *and* the same content
  published as an artifact** (shareable link). Per-company before/after score and tier, plus a
  tier-distribution summary. Feeds RESCORE-03's before/after directly.

- **D-10:** The 17 false-veto records and 18 blank-`lv_org_type` records sit inside the 66 and are
  simulated **as-is, with annotation**. No projected/speculative column — every affected row is
  flagged so the 17 are not misread as genuine Tier D and the 18 are not misread as genuine
  unknowns.

- **D-11:** **There are three engines, not two** *(per CONTEXT.md — this research's Open
  Question 3 finding disputes this for org-type weight purposes specifically: the "JS port"
  carries no weight table at all; see below)*. `tests/test_flow_rubric_conformance.py` guards
  the HubSpot flow surface against the rubric. This applies to D-01 regardless of what else is
  decided.

- **D-12:** If a weight reaches the live workflow, it does so **only** via
  `scripts/build_cloud_workflows.py` → deploy → bounce, with a **read-back of the running (not
  merely stored) workflow** confirming the new value is what actually executes. *(This
  research's finding: none of D-01/D-02/D-03 trigger this pipeline at all, since the n8n side
  carries no org-type weight table — see Open Question 3.)*

- **D-13:** **Every doc that prints the superseded rubric is updated in this phase**, in the same
  pass as the config change. Live sites: `docs/business/icp-scoring.md` §5 (scoring model table,
  graduated-deductions table, property-map table, tier illustration) and §4 (anti-ICP bullets),
  `CLAUDE.md` §10.1/§10.3, `.planning/intel/constraints.md`, `.planning/intel/requirements.md`,
  `docs/WEB-RESEARCH-SPEC.md` (lines 159, 483). **Do NOT edit** anything under
  `.planning/milestones/` (historical record) or `.planning/PROJECT.md` (updates at milestone
  close, not here).

- **D-14:** `icp-scoring.md` is a **business sign-off document**, not a config mirror. The 19%/
  n=36 finding stays on the page, with the override and its GTM reasoning recorded next to it —
  never silently rewrite the evidence to agree with the new weight.

### Claude's Discretion

- Candidate weight set for the simulation. Claude locks **15 as the primary scenario** and may
  include **10 and 20 as sensitivity columns**.
- The threshold/format of the annotation in D-10.
- Whether the regulator −20 is expressed as a new `graduated_deductions` key or a distinct
  org-type deduction map — whichever ports most cleanly across all three engines. *(This
  research's recommendation: a direct `base_score.org_type.regulator: -20` value — see Open
  Question 5.)*

### Deferred Ideas (OUT OF SCOPE)

- **`lv_is_regulator` boolean property** — investigated and rejected this phase (D-04).
- **Association-aware club scoring** — "a club linked to an already-won governing body is worth
  working directly; a standalone single-venue club is not." No association-aware signal exists
  today. Own phase.
- **`lv_sponsorship_reliant` as a scoring component** — populated but not a scoring input;
  drives deal *value* ($27k vs $9k), not conversion.
- **Revenue-band deduction calibration** (−5 at 500–750M, −50 at 1.2B+) — deferred to v1.0 as
  EVID-02.
- **Re-examining the `governing_body_league` bucket's internal mix** — out of scope.
- Three pending todos (enrichment throughput, sweep crontab pinned path, UAT 2.2 header
  aliases) — keyword-matched but not selected for this phase; none in scope for a zero-write
  rubric phase.
</user_constraints>

## Summary

This phase's plan should center on one corrected fact that changes its shape materially:
**there are two computation engines for org-type point values, not three**
`[VERIFIED: n8n/code/mergeCompanies.js:56-59, scripts/build_cloud_workflows.py:2746-2749 —
exhaustive grep of both files for any org-type-keyed numeric table, zero matches]`. The
Python oracle (`config/icp_scoring.yaml` + `src/icp_scoring.py`) and HubSpot's native flow
`4626124224-org-type-score` both encode `base_score.org_type` as a value-keyed points
table. The n8n JS "port" (`n8n/wf_enrichment_cloud.json`, built by
`scripts/build_cloud_workflows.py`) does not — `mergeCompanies.js`'s own header comment
names this "Approach C (Phase 15): HubSpot owns these derived outputs," and grepping the
378K-line build script and the deployed workflow JSON for any org-type-keyed numeric
table returns nothing. n8n's only org-type-adjacent logic is the *categorical* hard-veto
derivation in `ENRICH_DECIDE_CO_CLOUD` (region/content/hardware booleans →
`lv_anti_icp_flag`), which none of D-01/D-02/D-03 touch. This means: (a) D-02's regulator
change collapses from "new engine logic" to a one-line weight edit — verified by direct
execution, see Open Question 5 below; (b) D-12's n8n build→deploy→bounce pipeline is not
triggered by any of this phase's three weight decisions; (c) the parity bar RUBRIC-03
sets is satisfiable by editing exactly two files (`config/icp_scoring.yaml` and the
archived-then-live-PUT HubSpot flow JSON) plus one already-proven PUT protocol, not a
three-way port.

Second load-bearing finding: `scripts/backfill_seed_company_scores.py` already computes
score components in Python from live canonical inputs and batch-PATCHes them directly via
the HubSpot CRM v3 API — bypassing both HubSpot's own Automation v4 flows *and* n8n
entirely for the write. Reusing this mechanism for Phase 49's re-score costs **zero n8n
executions** (a plain CRM API batch write, capped at 100/call), a materially different
and cheaper answer than CONTEXT.md's D-07 "~66 executions against the 2,500/month
allowance" framing, which appears to assume the n8n SJ-3 poller path. This phase should
record the cheaper path in `46-DECISION.md` so Phase 49 doesn't over-provision.

Third: a real, live artifact answers Open Questions 1 and 2 outright.
`.planning/milestones/v0.7-phases/41-validation-data-import-end-to-end-proof/41-final-population.json`
(a 66-company live snapshot, `hs_lastmodifieddate` 2026-08-08) reproduces PROJECT.md's
tier distribution (A:7 B:18 C:17 D:24) and REQUIREMENTS.md COVER-01's "18 blank
`lv_org_type`" **exactly**, byte-for-byte. This is almost certainly the source PROJECT.md
was written from. It is 3 days stale relative to CONTEXT.md's 2026-08-11 date, so it
should be used as a cross-check reference, not blindly as ground truth — but it gives the
planner a concrete, already-committed 66-ID list and the exact HAS_PROPERTY search
(`scripts/run_scoring_parity.py::_select_sample_ids()`) to re-verify live before the
simulation locks its row set.

**Primary recommendation:** Treat this as a config-and-flow-edit phase, not a
three-engine-port phase. Extend `compute_icp_score` with an optional `cfg` override
parameter (small, additive, backward-compatible) so a new simulation script can score the
same live record twice — once under the current rubric, once under the proposed one —
without touching the file on disk. Reuse `tests/scoring_fixtures.py::fetch_for_parity`
for the live reads. Follow the already-proven disable→edit→PUT→enable→validate→confirm
protocol (`scripts/fetch_hubspot_flow.py` / `scripts/put_hubspot_flow.py`,
`PORTAL-FACTS.md`) for the HubSpot flow edits. Budget for two confirmed test breakages
(enumerated below) plus a `KeyError` in `src/icp_scoring.py:89-92` that D-03 makes
unconditional-crash-on-any-gambling-record unless that block is edited, not just the
config key deleted.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Org-type/geography/revenue/content point weights | HubSpot native Automation v4 flows (5 flows, `config/hubspot_flows/*.json`) | Python oracle (`config/icp_scoring.yaml` + `src/icp_scoring.py`) | HubSpot flows are the *live* score producer (write `org_type_score` etc., summed by a `calculation_equation` property); the Python oracle is the offline mirror used for tests/parity/simulation. Both must agree — this is RUBRIC-03's real two-party parity bar. |
| Hard-veto derivation (`lv_anti_icp_flag`/`reason`) | n8n Cloud (`ENRICH_DECIDE_CO_CLOUD` in `n8n/wf_enrichment_cloud.json`) | Python oracle (same file, hard-veto block) | Sole writer since Phase 40 D-01 (40-05); HubSpot workflows are permanently guarded (`test_no_archived_flow_writes_veto_properties`) against ever writing these again. Not touched by D-01/D-02/D-03 — none of the three decisions change hard-veto category membership. |
| Categorical input values (`lv_org_type`, `lv_produces_content`, `lv_is_gambling_operator`) | n8n Cloud (`mergeCompanies.js` via `ENRICH_DECIDE_CO_CLOUD`) | HubSpot CRM (record storage) | n8n's non-clobber merge decides *whether* to promote a candidate value; it never computes or stores a point value for that candidate. |
| Simulation compute | Python (new/extended script, local process) | — | Zero-write by construction (D-08) — a local process reading live records read-only and scoring them twice is the correct tier; no HubSpot or n8n write path is appropriate here at all. |
| Decision record / doc sync | Filesystem (`.planning/`, `docs/`, `CLAUDE.md`) | — | Pure content authoring, no runtime tier. |

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RUBRIC-01 | Evidenced decision per org-type weight, override recorded not evidence rewritten | `39-DECISION.md` precedent structure captured below for `46-DECISION.md`; live verification confirms D-01/D-02 math exactly as CONTEXT.md states (see Open Question 5) |
| RUBRIC-02 | Zero-write simulation of the 66 under proposed weights | `compute_icp_score` cfg-override extension + `fetch_for_parity` reuse plan below; D-08's "current live inputs" constraint resolved via the same HAS_PROPERTY query the parity harness already uses |
| RUBRIC-03 | All engines carry the weights identically, proven not inspected | **Corrected to two real engines** (Python oracle + HubSpot flow `4626124224`) for org-type weights — see the load-bearing finding below; `test_flow_rubric_conformance.py::test_org_type_flow_matches_rubric` already asserts VALUES, self-updating from config, needs zero test-code changes for D-01/D-02. The literal "all three engines" text in RUBRIC-03 is satisfied for the n8n leg by an **absence-proof guard test** (Pitfall 2 below), not a port — the planner should add that guard explicitly so a goal-backward check does not read the n8n leg as uncovered. |
</phase_requirements>

## Answers to the Researcher's Open Questions

### Open Question 1 — Enumerate "the 66" live

**Verified, with one important caveat.**
`[VERIFIED: .planning/milestones/v0.7-phases/41-validation-data-import-end-to-end-proof/41-final-population.json,
read and counted in full this session — 66 top-level keys, tier
Counter({'D': 24, 'B': 18, 'C': 17, 'A': 7})]`. This file
is a 66-record live snapshot (`hs_object_id`-keyed, `hs_lastmodifieddate` values clustered
around `2026-08-08T12:40:25Z`) that reproduces PROJECT.md's claimed distribution
**exactly**: matches "A:7 B:18 C:17 D:24" verbatim.
`lv_anti_icp_flag=='true'` count is 24, consistent with "17 of the D are false vetoes"
plus a handful of genuine vetoes.

**The caveat that must be closed live before the simulation locks its row set:**
Phase 41's own `41-RUN-REPORT.md` (same date, 2026-08-08, but written *before* this
snapshot — it self-labels "INCOMPLETE... the full 66-record run never happened... DATA-01
and DATA-02 remain open") shows only 2 of 66 records actually processed at that point in
time; `scripts/release_remaining.py` and `scripts/finish_canary.py` exist in the same
phase directory, meaning the population landing completed *later that same day*, after
the interim run report was written. That reconciles the apparent contradiction with STATE.md's
Phase 43-04 note ("exactly 1 of 712 companies carries a live ICP score... its score has
drifted from Phase 40's recorded 80/A to 25/C") — that note references "Phase 40's
recorded" state and is very likely a measurement taken *before* Phase 41's population
landing completed, given STATE.md's Decisions log interleaves 41-01/41-02 entries before
43-01/43-04 in a way that does not track true chronological execution order (parallel
workstream artifact). **Neither document alone is authoritative for "today."** Three days
(2026-08-08 → 2026-08-11) and four phases (42-45, none scoring-related in their stated
scope) sit between this snapshot and the phase this research is for.

**The authoritative live query** (already built, already trusted by the parity harness —
reuse verbatim, do not invent a second definition of "the scored population"):

```python
# scripts/run_scoring_parity.py:157-165, _select_sample_ids()
from src.hubspot_client import search_records
result = search_records(
    "companies",
    [{"propertyName": "lv_icp_fit_score", "operator": "HAS_PROPERTY"}],
    ["lv_icp_fit_score"],
    limit=100,
)
ids = [r["id"] for r in result.get("results", [])]
```

**Recommendation for the planner:** Task 1 (or a pre-flight step before the simulation
script runs) must execute this exact query live and diff the returned ID set against
`41-final-population.json`'s 66 IDs. If they match, the snapshot is confirmed current and
can be cited directly in `46-DECISION.md` with today's date. If they diverge, that
divergence is itself a finding to record (not silently resolved), since it changes both
which companies the simulation covers and whether D-10's 17/18 annotation sets still
apply verbatim.

### Open Question 2 — Reconcile blank `lv_org_type` counts

**Resolved for the 2026-08-08 snapshot; needs the same live re-check as Q1.**
`config/june_candidates.json` (the *researched*, pre-write dataset) has 0 blanks across
66 rows by construction — it is Perplexity research output, not a HubSpot read.
`41-final-population.json` (the *post-write, live-read* dataset) has **exactly 18** blank
`lv_org_type` values, counted this session by reading the file:
`['10152138518', '10215097384', '14752488879', '15008671672', '17317381378',
'17317850381', '17696004613', '18047161864', '18796602894', '19100977027',
'20538284384', '20943964946', '9604732795', '9604732797', '9604738976',
'9604787229', '9604794661', '9605273630']` — matching REQUIREMENTS.md COVER-01's "18"
exactly. The gap between "0 blank in the June research" and "18 blank live" is the
**promotion gate**, not a data problem: `41-RUN-REPORT.md`'s own canary table shows this
mechanism directly — Racing NSW (`15008671672`, one of the 18) promoted
`lv_produces_content=true` but **not** `lv_org_type`, because `lv_org_type` is
evidence-gated at `min_confidence: 80` with `require_evidence_url_for` a subset of org
types (`mergeCompanies.js` `DEFAULT_COMPANY_POLICY`, `n8n/code/mergeCompanies.js:44-46`) —
some of the 66 researched candidates evidently did not clear that gate on the actual live
promotion pass, even though they carried a value in the June research file.

**What this means for D-10's annotation:** the 18 blank-org_type IDs are a *specific,
enumerable* set (listed above, pending live re-confirmation), not a fuzzy count. The
simulation report should be able to look each row up against this exact ID list rather
than re-deriving "blank" from a live NOT_HAS_PROPERTY search alone (do both — the live
search is authoritative, this list is the fast cross-check).

### Open Question 3 — Is the JS org-type weight table generated or hand-maintained?

**Neither — it does not exist.** This is the single most important correction this
research surfaces. Verified by:
- Exhaustive grep of `scripts/build_cloud_workflows.py` (6,394+ lines) for
  `individual_club_team`, `governing_body_league`, `org_type_score`, `ORG_TYPE_SCORE` —
  zero matches for any of the four.
- Exhaustive grep of the deployed `n8n/wf_enrichment_cloud.json` for the same terms —
  the only 13 matches are enum *membership* strings inside `taxonomy.generated.js`
  (which org types exist and are evidence-gated, not what they score) and a frozen
  `JUNE_CANDIDATES` fixture blob.
- `n8n/code/mergeCompanies.js:56-59` (read this session): *"`lv_icp_fit_score` /
  `lv_icp_tier`: Approach C (Phase 15 criterion 4) — HubSpot owns these derived outputs.
  Removed from policy so either falls to the default non-promoting policy
  (fill_blank_only) if it ever appears in a candidate, never 'score_output'."*
- `scripts/build_cloud_workflows.py:2746-2749` (read this session): *"Approach C
  (Phase 15 criterion 4): canonicalPatch never carries `lv_icp_fit_score`/
  `lv_icp_tier`/`lv_anti_icp_flag`/`lv_recommended_motion` — `mergeCompanies.js`'s
  `DEFAULT_COMPANY_POLICY` has no score_output/veto_output entries for those (they were
  removed in Phase 15), so this node cannot emit them even if it tried."*
- Grepping the whole repo for the five component-score property names
  (`org_type_score`, `produces_content_score`, `geography_score`,
  `annual_revenue_score`, `gambling_score`) shows every write site is under
  `config/hubspot_flows/*.json` — none in `n8n/` or `src/` (other than the Python
  oracle itself, whose consumer `scripts/backfill_seed_company_scores.py` also just
  delegates to `src/icp_scoring.py`, never hand-copying a table).

**Practical consequence:** there is nothing to generate and nothing to hand-port for
D-01/D-02/D-03. Neither risk framing in the open question ("generated = near-free" /
"hand-ported = split-brain risk") applies — the third case, "doesn't exist," is what's
actually true. The n8n build→deploy→bounce pipeline (D-12) is not triggered by this
phase's weight edits at all.

### Open Question 4 — Is the HubSpot flow live/authoritative, and does the conformance test assert values or structure?

**Confirmed live and authoritative; confirmed the test asserts VALUES.**
`PORTAL-FACTS.md` (Phase 40, live-read against portal 22617666) lists flow `4626124224`
("Update Score Based on Org Type") as `isEnabled: true`, `objectTypeId: 0-2`
(companies) — one of exactly 4 enabled company-scoring flows in the portal (later
6 after 40-04 adds two more). `39-DECISION.md` records the operator's binding
architecture decision: HubSpot's native workflow chain, not a rebuilt lead-scoring tool,
is where the score lives — this flow is that chain's org-type stage.

`tests/test_flow_rubric_conformance.py::test_org_type_flow_matches_rubric`
(lines 111-135, read this session) asserts **exact point values**, not structure:

```python
rubric_org_type = load_rubric()["base_score"]["org_type"]
flow_scores = extract_org_type_branch_scores(flow)   # walks STATIC_BRANCH -> staticValue
for branch_value, points in flow_scores.items():
    assert points == rubric_org_type[branch_value]
```

Ran this extractor live against the committed `.after.json` this session:
`{'governing_body_league': 40, 'content_producer': 20, 'broadcaster': 20,
'individual_club_team': 5, 'regulator': 5, 'gambling_operator': 0, 'hardware_vendor': 0,
'other': 0, 'unknown': 0}` — exactly matches `config/icp_scoring.yaml` today, confirming
zero pre-existing drift as a baseline. **Caveat:** this test is offline (reads the
committed `.after.json`, never GETs the live portal), so it proves config↔archive
parity, not archive↔live-portal parity — D-12's own "read-back the running content"
requirement is the step that closes that second gap, and there is no repo-committed
automated test for it (it is a documented manual verification step per
`PORTAL-FACTS.md`'s protocol).

### Open Question 5 — Does the regulator −20 collapse to a weight edit?

**Yes — `[VERIFIED: reproduced by direct local execution this session, not just static
reasoning]`.**
D-02's own worked example ("an AU regulator producing content goes 35 (C) → 10
(Unscored)") is arithmetically identical whether expressed as (a) `org_type.regulator:
0` plus a new `-20` graduated deduction, or (b) `org_type.regulator: -20` directly —
`0 + (-20) == -20` either way, and `src/icp_scoring.py`'s `.get(org_type, 0)` lookup has
no floor/clamp that would make negative org-type weights behave differently. Verified
live this session by monkeypatching a copy of the config in-process and calling
`compute_icp_score` directly (no file on disk touched):

```
regulator AU+content (org_type.regulator = -20, no revenue band): score=10, tier=Unscored
```

— exactly D-02's stated 10/Unscored outcome. This means:
- **No new engine logic anywhere.** `src/icp_scoring.py` needs zero new branches for
  D-02 (the existing `org_points = cfg["base_score"]["org_type"].get(org_type, 0)` line
  already handles it).
- **The HubSpot side is the same edit shape already proven live.** `PORTAL-FACTS.md`'s
  "D-05 round-trip verdict" section documents a prior Phase 40 edit to this *exact* flow
  (`4626124224`) that mutated the `regulator` branch's `staticValue` from `"0"` to
  `"5"` and the `gambling_operator` branch from `"-20"` to `"0"` — the mechanical
  precedent for D-01/D-02 is not hypothetical, it already happened once for these same
  two branches in this same flow.
- **`test_org_type_flow_matches_rubric` needs zero code changes** to cover D-02 — it is
  parametrized off `config/icp_scoring.yaml`, so a `-20` there is asserted automatically
  against whatever the flow's `regulator` branch reads.

This resolves CONTEXT.md's "Claude's Discretion" bullet: *express the regulator −20 as a
direct negative value in the existing `base_score.org_type` map, not as a new
`graduated_deductions` key.* It is the strictly cheaper, zero-new-code, already-tested
shape, and it produces the exact number D-02 specifies.

**D-03 (gambling removal) is genuinely different and does need a code edit** — not
because it is org-type-driven (it isn't; `lv_is_gambling_operator` is an independent
boolean, unaffected by which org type a company carries), but because
`src/icp_scoring.py:89-92` unconditionally does
`cfg["graduated_deductions"]["gambling_operator"]`:

```python
# src/icp_scoring.py:89-92 (read this session, verbatim)
    if is_gambling_operator:
        deduction = cfg["graduated_deductions"]["gambling_operator"]
        score += deduction
        breakdown["graduated_deductions"].append({"signal": "gambling_operator", "points": deduction})
```

Deleting the `graduated_deductions.gambling_operator` key from
`config/icp_scoring.yaml` without touching this code produces a live `KeyError` for
**every** company with `lv_is_gambling_operator=true`
`[VERIFIED: src/icp_scoring.py:89-92, reproduced by direct local execution this session
— monkeypatched config with the key deleted, called compute_icp_score with
lv_is_gambling_operator=True, raised KeyError('gambling_operator')]`. This block must
be removed (or the whole `if is_gambling_operator:` branch deleted) in the same commit as
the config-key deletion. On the HubSpot side, the separate flow `4634822085` ("Update
Gambling Score," `isEnabled: true`, no paired `.before.json` archived yet — only
`config/hubspot_flows/gambling-score.after.json` exists) must have both its `true` and
default `STATIC_BRANCH` targets edited to `0` (recommended over disabling the flow
outright, since `lv_icp_fit_score`'s formula already `coalesce(gambling_score, 0)`s a
null term — an explicit-0-write flow keeps the property populated and auditable rather
than relying on the null-coalesce path for every future write).

### Open Question 6 — Phase 49's n8n execution-count cost

**The cheap path already exists in the repo and costs ~0 n8n executions.**
`scripts/backfill_seed_company_scores.py` (built Phase 40 D-09/D-10, read in full this
session) computes all five component scores in Python — via
`compute_components()` → `src/icp_scoring.compute_icp_score()`, reading
`config/icp_scoring.yaml` directly, never a second table — from a record's *own current*
canonical inputs (`lv_org_type`, `lv_produces_content`,
`lv_country_region_normalized`, `lv_revenue_band`, `lv_is_gambling_operator`), then
batch-PATCHes `org_type_score`/`geography_score`/`annual_revenue_score`/
`produces_content_score`/`gambling_score` directly via
`src/hubspot_client.batch_update_companies()` — a **plain HubSpot CRM v3 batch API
call**, capped at 100 updates/call (`src/hubspot_client.py`, read this session:
`if len(updates) > 100: raise ValueError(...)`). This path touches neither an n8n
workflow nor a HubSpot Automation v4 flow — HubSpot's own `lv_icp_fit_score` calculated
property and WF1 (tier assignment) still fire automatically off the component-property
writes (both HubSpot-side, not n8n-side), exactly as Phase 40's proof-of-mechanism run
demonstrated on Melbourne Racing Club (`0 → 15 → 25` component/score progression settling
in seconds).

For a 66-record re-score, **this path costs 0 n8n executions** (2,500/month allowance
untouched) — a materially different answer than D-07's "~66 executions against the
2,500/month allowance," which implies routing through n8n's SJ-3
`lv_enrichment_requested` poller (the expensive path: full waterfall including "two
sequential Anthropic calls" per the enrichment-throughput todo, entirely unnecessary
since every input this rubric change needs already exists live on these records — no new
enrichment, only recomputed weights).

**What Phase 46 owes Phase 49, concretely (record in `46-DECISION.md`):**
1. State the recommended mechanism: reuse `backfill_seed_company_scores.py`'s
   `compute_components()` shape (not the SJ-3 poller) for the re-score.
2. Flag the one gate that currently blocks reuse at n=66: `HARD_CEILING_RECORDS = 25`
   (module constant, `scripts/backfill_seed_company_scores.py:85`) — D-09 deliberately
   scoped Phase 40's version of this script to a small proving sample. Phase 49 must
   either call it 3× in ≤25-record chunks with distinct `--company-id` sets, or raise the
   ceiling with a recorded justification (the "chunk size" RESCORE-01 already asks for).
3. Note the veto fields (`lv_anti_icp_flag`/`lv_anti_icp_reason`) do **not** need
   recomputation for this rubric change — none of D-01/D-02/D-03 touch hard-veto
   category membership — so Phase 49's re-score can skip n8n's pipeline (and its
   Anthropic cost) entirely for this specific change, which is not true in general for
   every future rubric change.
4. Note the untested edge in this reuse: does a PATCH of a component property that was
   *already* enrolled once via a HubSpot flow (vs. this script's direct-write) produce
   identical downstream calculated-property behavior for all 66, or could pre-existing
   `PROPERTY_DEFAULT_VALUE`-stamped components (the three original components on records
   created before 40-04) interact differently? `PORTAL-FACTS.md`'s "Default-value-
   generation finding" documents that the stamp mechanism is API-inaccessible but says
   nothing about whether *overwriting* an already-stamped value behaves differently from
   writing a never-set one — flag as an open item for Phase 49's own research, not
   resolved here.

### Open Question 7 — AU racing governance/integrity statutory split (low priority)

**Confirmed via web search, non-blocking as CONTEXT.md states.** Queensland: the
*Racing Integrity Act 2016* established the Queensland Racing Integrity Commission
(QRIC) as an independent statutory body separating integrity/welfare regulation from the
commercial/administrative racing-code function, which stayed with Racing Queensland —
directly matching D-04's "QLD splits it" framing (Racing Queensland =
`governing_body_league`, QRIC = `regulator`, separate legal entities). This corroborates,
without additionally proving, D-04's WA-fused/QLD-split contrast; the portal-data
evidence D-04 already cites (RWWA classified `governing_body_league`, a won deal) remains
the operative, already-verified basis for the decision regardless of this statutory
detail.

Sources: [Queensland Racing Integrity Commission — About us](https://qric.qld.gov.au/about-us/),
[QRIC — Functions & powers](https://qric.qld.gov.au/about-us/functions-powers/),
[What You Need to Know About the QLD Racing Integrity Commission](https://hannaylawyers.com.au/what-you-need-to-know-about-the-queensland-racing-integrity-commission/).

## The Parity Harness — Exact Shape

`tests/test_scoring_parity.py` (read in full this session, 1034+ lines) is two tiers in
one module:
- **Offline tier** (zero network, always runs): parametrized directly off
  `ORG_TYPE_POINTS = CFG["base_score"]["org_type"]` (loaded from
  `config/icp_scoring.yaml` at import time) — `test_engine_06_org_type_sweep_offline`
  and its live twin `test_org_type_sweep` (line 361-368) are **self-updating**: a config
  edit changes what they assert against with zero test-code changes.
- **Live tier** (`RUN_LIVE_PARITY=true`, creates/exercises/deletes
  `ZZ-SCORING-TEST-DELETE-ME-*` disposables): named `-k` selectors exist per requirement
  (`test_engine_01_...`, `test_f8_...`, `test_f9_gambling_conflation`, etc.) — this
  convention should be followed for any new named case this phase adds.

`tests/scoring_fixtures.py::fetch_for_parity(company_id)` / `expected_for(props)` are the
two shared functions both `tests/test_scoring_parity.py` and
`scripts/run_scoring_parity.py` import — the single source of "what does the oracle say
about this live record."

`scripts/run_scoring_parity.py::build_report()` is a **pass/fail comparison** shaped
function (oracle vs. live HubSpot triple, classifies mismatches, returns a verdict
string and exit code) — it is not a before/after diff report, and retrofitting a second
mode into it would complicate its one existing job (the standing unattended drift sweep,
D-12/D-13's false-green guard). **Recommendation: write a separate script**, e.g.
`scripts/simulate_rubric_weights.py`, importing `fetch_for_parity` from
`tests/scoring_fixtures.py` (for the live read) and an **extended**
`compute_icp_score(record, candidate_patch, cfg=None)` from `src/icp_scoring.py` (small,
additive parameter — `cfg = cfg or load_yaml("config/icp_scoring.yaml")` at the top of
the function; every existing call site with 2 positional args is untouched). The
simulation calls `compute_icp_score` twice per company — once with `cfg=None` (current),
once with a proposed-weights dict built in-process (never written to disk) — and emits
the before/after table D-09 wants. This is the "close to a read-only variant" CONTEXT.md
flags, but the actual reuse is at the fixture-function level (`fetch_for_parity`), not at
the `run_scoring_parity.py` script level.

## Rule 1 Fallout — Test Sites That Will Go Red

`[VERIFIED: reproduced by direct local execution this session]` — every row below was
confirmed by running the actual scenario against a monkeypatched in-process copy of
`config/icp_scoring.yaml` (file on disk never touched) and calling
`src.icp_scoring.compute_icp_score` directly, not by static inference from reading the
test source alone:

| Site | Current behavior | Under D-01/D-02/D-03 | Fix needed |
|------|-------------------|----------------------|------------|
| `tests/test_icp_scoring.py:48-59` `test_case_3_au_individual_club_tier_c` | Hardcodes `individual_club_team`+`1-5M` revenue → asserts `score == 35`, `tier == "C"` | Score becomes **45**, tier becomes **"B"** (verified by direct call) | Update the two literal asserts; rename the test (`_tier_c` → `_tier_b`) or add a sibling case — planner's call |
| `tests/test_scoring_parity.py:553-575` `test_run_scoring_parity_classifies_needs_review_as_documented_divergence` | Live-record stub with `lv_org_type: individual_club_team`, no `produces_content`, region `AU` → oracle score computed as 15, live stub says `"15"`/`"C"`, classified as documented divergence | Oracle score becomes **25** (still "Needs Review" internally, still live-enum "C" since 15-39 stays band C) — but the **literal stub `"15"` no longer matches**, so `score_match` fails and the row becomes a `real_finding`, breaking `assert report["real_findings"] == []` | Update the stub's literal `"lv_icp_fit_score": "15"` to `"25"` |
| `src/icp_scoring.py:89-92` | `cfg["graduated_deductions"]["gambling_operator"]` — direct key lookup | **`KeyError`** the moment the key is deleted from config, for any company with `lv_is_gambling_operator=true` (confirmed by direct execution) | Not a test — a **required code change**, in the same commit as the config-key deletion, or this ships broken |
| `tests/test_scoring_parity.py:134-144` `test_gambling_deducts_20_without_veto_offline` | `deduction = CFG["graduated_deductions"]["gambling_operator"]` then asserts it's in the breakdown | `KeyError` at collection/run time once the key is removed | Rewrite to assert gambling contributes 0 (or delete, if the concept is retired) |
| `tests/test_icp_scoring.py:93` | `assert {"signal": "gambling_operator", "points": -20} in r.breakdown["graduated_deductions"]` | Literal `-20` and the whole `graduated_deductions` list entry disappear | Update/remove |
| `tests/test_scoring_parity.py:341-358` `test_gambling_deducts_20_without_veto` (live) + its alias `test_f9_gambling_conflation` (line 511-514) | `assert props.get("gambling_score") == "-20"` | Must become `"0"` once flow `4634822085` is edited | Update literal |
| `tests/test_flow_rubric_conformance.py:165-190` `test_gambling_flow_matches_rubric` | `rubric_deduction = load_rubric()["graduated_deductions"]["gambling_operator"]` | `KeyError` once config key removed | Rewrite to assert both branches score 0 directly (no longer reads from a removed config key) |
| `tests/test_backfill_seed_company_scores.py:151-152,163` | `compute_components(...)["gambling_score"] == -20` (true case), `== 0` (false case) | True case must become `== 0` | Update literal |

**Safe / no fallout, verified this session (do not budget work here):**
- `test_org_type_sweep_offline_matches_config`, `test_engine_06_org_type_sweep_offline`,
  `test_org_type_sweep` (live) — fixture-driven off `ORG_TYPE_POINTS`, self-update.
- `tests/test_scoring_parity.py:191-213`
  `test_blank_region_is_not_vetoed_offline` — asserts `tier == "C"`; under D-01
  (`individual_club_team: 5→15`) the recomputed score is 15+20+0+0=35, still inside the
  C band (15-39) — verified this stays "C", no change needed.
- `tests/test_scoring_parity.py:231-241`
  `test_blank_region_boundary_neighbor_empty_string_offline` — only asserts
  `anti_icp_flag is False`, no score/tier literal.
- `tests/scoring_fixtures.py`, `tests/test_hubspot_properties_config.py`,
  `tests/test_check_schema_drift.py` reference `gambling_score` as a **property name**
  for schema/list purposes only, not a value literal — safe as long as D-03 keeps the
  property (writing 0) rather than deleting it, which this research recommends.

**Baseline confirmed green this session** before any change: `.venv/bin/python -m
pytest` → `2498 passed, 121 skipped` (whole repo); the scoring-specific offline subset
(`tests/test_icp_scoring.py tests/test_scoring_parity.py -k "not live"`) → `70 passed,
33 skipped, 1 deselected`.

## Package Legitimacy Audit

**N/A — this phase installs no new packages.** Every change is an edit to existing
Python source, an existing YAML config, existing committed HubSpot flow JSON, and
existing markdown documentation. No `pip install` / `npm install` occurs anywhere in
this phase's scope.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Compare oracle score to live HubSpot state | A new fetch/compare loop | `tests/scoring_fixtures.py::fetch_for_parity` + the existing `EXPECTED_PORTAL_ID`/credentials guards | Already handles the portal-id assertion, the property list, and the `.env`-blocked-session skip pattern every other script in this repo follows |
| Publish the simulation as a shareable artifact (D-09) | Custom publish tooling/CI step | The ambient Claude Artifacts feature (this environment already has `artifact-design`/`artifact-capabilities` skills available) | No prior art for "publish" exists anywhere in this repo (searched `.planning/` exhaustively) — this is a conversational/manual deliverable, not a coded one; scope it as a `checkpoint:human` task, not a script |
| Edit a HubSpot Automation v4 flow's branch value | A new PUT wrapper | `scripts/fetch_hubspot_flow.py` (archive) + `scripts/put_hubspot_flow.py` (two-key-gated PUT) following the disable→edit→PUT→enable→validate→confirm protocol in `PORTAL-FACTS.md` | This exact edit shape (mutating a `STATIC_BRANCH` target's `staticValue`, including on `regulator`'s branch specifically) is already live-proven once in Phase 40 |

**Key insight:** every mechanical piece this phase needs (fetch, compare, edit-a-flow,
recompute-a-component) was already built in Phase 40/41 for the identical purpose. The
work here is almost entirely config/data edits plus a small, additive code extension
(the `cfg` override) — resist the temptation to build new scaffolding around any of it.

## Common Pitfalls

### Pitfall 1: Assuming a config edit alone re-scores existing records
**What goes wrong:** Editing `4626124224`'s `regulator` branch value does not
retroactively recompute `org_type_score` for the 66 already-enrolled companies.
**Why it happens:** `PORTAL-FACTS.md`'s live-probed finding: "Enrollment requires a
genuine property-change event, not a value present at row creation" — the same principle
extends to a flow *definition* edit: existing enrollments already computed their branch
result under the old table and do not silently re-fire because the table changed later.
**How to avoid:** Phase 49 (or a deliberate re-touch step) must issue a genuine
property-change PATCH (or the direct component-write path from Open Question 6) per
company to force recomputation.
**Warning signs:** A simulation or spot-check that reads `org_type_score` immediately
after a flow edit and finds it unchanged for a pre-existing record — this is expected,
not a bug.

### Pitfall 2: Treating the n8n build→deploy→bounce pipeline as required for this phase
**What goes wrong:** Budgeting a full `build_cloud_workflows.py` regenerate + deploy +
bounce + read-back cycle (D-12) for D-01/D-02/D-03, when none of the three weight changes
touch anything n8n encodes.
**Why it happens:** D-11/D-12 in CONTEXT.md were written assuming a "JS port" carries
org-type weights; Open Question 3's answer shows it does not.
**How to avoid:** Reserve the n8n deploy pipeline for changes that touch categorical
promotion logic (taxonomy membership, evidence-gating, merge policy) — not pure weight
edits. If the planner wants a permanent guard proving this absence (satisfying RUBRIC-03's
"proven not inspected" spirit for the n8n leg specifically), add one cheap static assertion
(e.g., grep `n8n/wf_enrichment_cloud.json` for any of the 9 org-type enum values followed
by a colon-and-number pattern) rather than a deploy cycle.

### Pitfall 3: Deleting the gambling config key without editing the code that reads it
**What goes wrong:** `src/icp_scoring.py:89-92`'s unconditional
`cfg["graduated_deductions"]["gambling_operator"]` lookup raises `KeyError` for any
company with the boolean set true, the moment the key disappears from
`config/icp_scoring.yaml` — confirmed by direct execution this session, not a theoretical
risk.
**How to avoid:** Remove the `if is_gambling_operator:` block (or guard it with `.get()`
returning 0/skip) in the *same* commit/task as the config-key deletion — never split
across two tasks in a way that leaves the config green and the code red even transiently.

### Pitfall 4a: The standing unattended parity sweep goes RED between the flow PUT and Phase 49's re-score
**What goes wrong:** The moment the live HubSpot flow PUT lands (D-01 alone re-tiers 37+ of the
66), `scripts/run_scoring_parity.py`'s standing unattended sweep — which samples **real**
companies via the same `HAS_PROPERTY(lv_icp_fit_score)` search named in Open Question 1, not
disposables — starts comparing each one's **old-weight live score** against the **new-weight
oracle** (`config/icp_scoring.yaml` already carries the new value the instant it's committed).
Every re-tiered record becomes a `real_finding`; the sweep's own false-green guard (D-13, "a
sweep that checked nothing must never report success") means this is a loud, correct FAIL, not
a silent one — but it will fire on every scheduled run from the moment of deploy until Phase 49
executes the re-score, however long that gap is `[VERIFIED: scripts/run_scoring_parity.py:149-165,
_select_sample_ids() reads real companies via HAS_PROPERTY, not disposables]`.
**Why it happens:** This is Pitfall 1's finding one step further — a flow edit doesn't
retroactively re-score existing records, but the *parity harness itself* has no notion of "a
weight changed but the population hasn't caught up yet" — it only knows oracle-vs-live match/
mismatch.
**How to avoid:** The planner must explicitly sequence this, not treat it as an afterthought.
Two options, either acceptable, but the choice must be a stated decision, not a default: (a)
document the red window explicitly (bounded, with an end condition tied to Phase 49's
completion) and accept the scheduled sweep will alert during it; or (b) coordinate the live
flow PUT itself with Phase 49's re-score so the gap is as short as possible (e.g., run the
component-write re-score from Open Question 6 immediately after the PUT, in the same
operator session). Either way, `46-DECISION.md` should record which was chosen and why —
this changes task ordering across Phase 46/49, not just Phase 46's own scope.
**Warning signs:** A scheduled `run_scoring_parity.py` run reporting `real_findings` for
records whose `lv_org_type` is `individual_club_team`/`regulator`/anything
gambling-flagged, immediately after this phase's deploy — this is the expected, self-inflicted
signal, not evidence of a new bug.

### Pitfall 4: Confusing the archived `.after.json` conformance test with live-portal proof
**What goes wrong:** Treating `test_flow_rubric_conformance.py`'s green result as proof
the *live, running* HubSpot flow carries the new weight.
**Why it happens:** The test reads the committed JSON file, never GETs the portal — it
proves config↔archive agreement, which is necessary but not sufficient.
**How to avoid:** Follow D-12 literally for the two flows this phase touches
(`4626124224`, `4634822085`): re-fetch and archive as `.after.json` only *after* a live
PUT, and treat that fresh archive (not the pre-PUT one) as the thing the conformance test
should pass against going forward.

## Runtime State Inventory

**Not applicable — this is not a rename/refactor/migration phase.** No string, ID, or
key is being renamed anywhere; this phase edits point *values* under fixed keys, not key
names. Skipped per the trigger condition in the verification protocol.

## The `39-DECISION.md` Precedent — Structure for `46-DECISION.md`

Read `39-DECISION.md` in full this session. Its section structure, directly reusable:

1. **Verdict** — one or two sentences, the decided value(s), decision date, portal id.
2. **How the verdict was reached** — gate-by-gate (for 46: per-weight, evidence vs.
   override).
3. **Rationale** — cites the evidence document (`icp-scoring.md`) without re-deriving it,
   states explicitly where the decision overrides the evidence and why (D-14's
   requirement).
4. **Rejected alternatives** — the weight values *not* chosen (10/20/30 for the club
   weight; the graduated-deductions-key shape for regulator, per Open Question 5's
   finding) and why.
5. **What this shapes downstream** — explicit forward pointers to Phase 47/48/49, mirroring
   39-DECISION.md's own "Phase 40/41/42" section.
6. **Assumptions carried into the verdict** — this phase's equivalent of 39's A-BOUNDARY/
   A-PRECISION list; should include this research's Open-Question-1/2 live-recheck
   caveat explicitly, since the decision record is dated and the underlying snapshot is
   not.
7. **Re-check procedure** — how a future phase re-verifies this decision if the rubric is
   revisited (mirrors 39-DECISION.md's numbered re-check steps).
8. **Process note** — any deviation from the plan's literal task order, recorded honestly
   (39-DECISION.md's precedent for this: it documented two skipped tasks rather than
   silently omitting them).
9. **Evidence index** — table of every supporting artifact, including (for 46) the
   simulation's committed markdown output and the parity-report JSON.

`39-DECISION.md` also models the tone D-14 requires for `46-DECISION.md`: it states its
override plainly ("Not availability-driven — it would have been the same verdict had the
availability gate failed") without editing the superseded evidence out of the record.

## Documentation Sync (D-13) — Confirmed Target List

CONTEXT.md's table of live doc sites is accurate and load-bearing; this research adds no
new sites but confirms the mechanism is pure content editing (no template/generator
regenerates any of these — they are hand-maintained prose/tables) and flags one ordering
constraint: the `docs/business/icp-scoring.md` §5 tables should be edited **after**
`46-DECISION.md` is signed off, not speculatively ahead of it, since D-05 makes the
operator's sign-off the actual locking event — editing the business doc before sign-off
risks documenting a value that gets overridden in review.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `41-final-population.json` is current as of today (2026-08-11), not stale relative to Phases 42-45 | Open Question 1/2 | If a later phase silently touched scores/org-type (none of 42-45's stated scope suggests this, but not exhaustively verified), the simulation's row set or D-10 annotation could be built on stale data — mitigated by the recommended live re-check task |
| A2 | Editing `gambling-score` flow's both branches to `0` is preferable to disabling the flow outright | Open Question 5 / Pitfall 3 | Low risk either way (formula already coalesces null to 0) — recorded as a judgment call, not a verified requirement |
| A3 | No later phase (Phase 42-45) altered `src/icp_scoring.py`'s gambling-deduction block or `graduated_deductions` shape since Phase 40 | Rule 1 Fallout table | Verified by reading the current file this session (line 89-92 matches Phase 40's description exactly) — low risk, direct read not inference |

**If this table is short:** most claims in this research are `[VERIFIED]` by direct file
reads and local code execution this session, not `[ASSUMED]` — the exceptions above are
the ones genuinely resting on inference across a multi-day, multi-phase gap this sandbox
cannot re-verify live (no HubSpot credentials reachable this session; `.env` is
permission-blocked per repo memory, and no live API call was attempted or claimed).

## Open Questions Remaining

1. **Live re-verification of the 66-company set and the 18-blank-org_type list**
   (Open Questions 1/2 above) — must be run with credentials before the simulation
   locks its row set. Query is fully specified above; this is a data-freshness gap, not
   a design gap.
2. **Whether overwriting an already-`PROPERTY_DEFAULT_VALUE`-stamped component behaves
   identically to writing a never-set one** (Open Question 6, item 4) — genuinely
   untested in this repo's history; low risk (batch PATCH is a normal write either way)
   but worth a one-record spot-check before Phase 49's full run, not blocking Phase 46.
3. **Whether HubSpot Automation v4 has its own execution-count limit** separate from the
   n8n 2,500/month allowance RESCORE-02 names — not investigated (out of scope per
   REQUIREMENTS.md, which names only the n8n allowance and Lusha balance), flagged in
   case Phase 49's planner wants to check the portal's own workflow-execution ceiling
   before running 66-198 HubSpot flow enrollments in one sitting.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 |
| Config file | none dedicated — repo-root `tests/` package |
| Quick run command | `.venv/bin/python -m pytest tests/test_icp_scoring.py tests/test_scoring_parity.py -k "not live" -q` |
| Full suite command | `.venv/bin/python -m pytest -q` (whole repo, offline; `RUN_LIVE_PARITY=true` adds the live tier) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RUBRIC-01 | Decision recorded with evidence | manual (decision doc, not code) | n/a | n/a |
| RUBRIC-02 | Simulation writes nothing to HubSpot | unit (new) | new test asserting the simulation script's HTTP layer is GET-only / no `patch_record`/`batch_update_companies` import reachable | ❌ Wave 0 |
| RUBRIC-03 | Org-type/gambling weights match across Python oracle + HubSpot flow | offline | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -q` (self-updating, needs only the gambling test's rewrite from Pitfall/Fallout table) | ✅ exists, needs edit |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_icp_scoring.py tests/test_scoring_parity.py tests/test_flow_rubric_conformance.py -k "not live" -q`
- **Per wave merge:** `.venv/bin/python -m pytest -q` (full offline suite, baseline 2498 passed / 121 skipped)
- **Phase gate:** offline suite green before `/gsd-verify-work`; live tier
  (`RUN_LIVE_PARITY=true`) run manually if the operator's credentials are available in
  that session, since this sandbox could not run it

### Wave 0 Gaps
- [ ] A no-write assertion for the new simulation script (RUBRIC-02's zero-write bar
      needs a positive test, not just a docstring claim)
- [ ] `src/icp_scoring.py` needs a `cfg=None` parameter added to `compute_icp_score`
      before any simulation code can call it twice with different weight tables

## Security Domain

No new external attack surface. This phase edits configuration values and internal
scoring logic; no new authentication, input-validation, or cryptography surface is
introduced. The one write-adjacent risk is D-08's "simulation writes nothing" contract —
recommend the Wave 0 gap above (a static/no-write test) as the concrete control, rather
than relying on code review alone to keep the simulation script read-only over time.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | Marginal | The simulation script must reject/refuse on a portal-id mismatch, same pattern every other script in this repo already follows (`EXPECTED_PORTAL_ID` assert-before-any-call) |
| V6 Cryptography | No | No secrets/crypto touched |
| Others | No | Not applicable to a config-edit + read-only-report phase |

## Sources

### Primary (HIGH confidence — read/executed this session)
- `config/icp_scoring.yaml`, `src/icp_scoring.py` — full read, plus local execution
  reproducing D-01/D-02/D-03's exact stated outcomes and the D-03 `KeyError`.
- `scripts/build_cloud_workflows.py`, `n8n/wf_enrichment_cloud.json`,
  `n8n/code/mergeCompanies.js` — grepped exhaustively for org-type weight tables (none
  found); Approach C comments read verbatim.
- `tests/test_flow_rubric_conformance.py`, `tests/test_scoring_parity.py`,
  `tests/scoring_fixtures.py` — read in full; extractor run live against the committed
  flow archive this session.
- `scripts/backfill_seed_company_scores.py`, `src/hubspot_client.py` — read in full for
  the Open Question 6 cost-mechanism finding.
- `scripts/fetch_hubspot_flow.py`, `scripts/put_hubspot_flow.py`,
  `.planning/milestones/v0.7-phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md`
  (557 lines, read substantially) — the D-05/D-12 PUT protocol and prior live edit of
  this exact flow's `regulator`/`gambling_operator` branches.
- `.planning/milestones/v0.7-phases/41-validation-data-import-end-to-end-proof/41-final-population.json`,
  `41-RUN-REPORT.md`, `41-VALIDATION.md` — read/parsed for Open Questions 1/2.
- `.planning/milestones/v0.7-phases/39-path-decision-fit-score-verification/39-DECISION.md`
  — full read for the decision-record precedent.
- `config/hubspot_flows/4626124224-org-type-score.after.json`,
  `config/hubspot_flows/gambling-score.after.json` — read for flow ids and shape.
- `.venv/bin/python -m pytest` baseline runs this session (2498 passed/121 skipped whole
  repo; 70 passed/33 skipped scoring subset).

### Secondary (MEDIUM confidence)
- `.planning/PROJECT.md` — tier-distribution and blank-org_type prose, cross-checked
  against `41-final-population.json` and found to match exactly, but PROJECT.md itself
  does not cite its own source/date for that claim.

### Tertiary (LOW confidence, non-blocking per CONTEXT.md)
- QRIC/Racing Queensland statutory split — WebSearch only, not cross-checked against a
  primary legislative source; consistent with, but does not add proof beyond, D-04's
  already-decided portal-data rationale.

## Metadata

**Confidence breakdown:**
- Engine-parity mechanics (2 engines not 3, D-02 collapse, gambling KeyError, rescore
  cost): HIGH — verified by direct source reads and local code execution this session.
- 66-company population / blank-org_type reconciliation: MEDIUM — strong committed
  evidence, but 3 days stale relative to the phase's date; live re-check recommended as
  a first task.
- Test-breakage enumeration: HIGH — each cited breakage reproduced by direct execution
  this session, not static inference.
- AU racing statutory detail: LOW, explicitly non-blocking.

**Research date:** 2026-08-11
**Valid until:** Re-verify the live-population claims (Open Questions 1/2) before
execution if more than ~2-3 days pass from this research date, since the underlying
snapshot is already 3 days old at time of writing. Engine-mechanics findings (source
code structure) are stable until the next scoring-engine-touching phase.
