# Phase 50: Derived Tier Property - Context

**Gathered:** 2026-08-13
**Status:** Ready for planning

<domain>
## Phase Boundary

`lv_icp_tier` stops depending on a HubSpot property-change event to be correct.

Today the tier is a plain `enumeration` written **only** by workflow WF1 (`4625147345`,
`type: EVENT_BASED`), which enrols on property-change events for `lv_anti_icp_flag` and
`lv_icp_fit_score`. A value-identical PATCH fires no event, so WF1 never re-enrols and the tier
goes stale against a score that is already correct. Observed live in Phase 49 W1 on 4 companies
(`9605273630` Port Macquarie Race Club, `9604738976` Bunbury Turf Club, `17696004613` Pinjarra
Park, `19100977027` Newcastle Harness Racing Club), which still read `C` while their score sits
at `45` — tier `B`. `shouldReEnroll: true` does not help; re-enrolment still needs an event to
re-enrol *on*.

This phase creates a calculated string property that derives the tier from the score the way
`lv_icp_fit_score` already derives itself, proves it against the live population, migrates the
portal dependents, and — as the last gated step — retires the old enum and switches WF1 off.

**Not in this phase:** formula grammar exploration (settled by the spike, 7/7), rubric weight
changes, `lv_icp_scoring_version`, the three CLAUDE.md §5.3 fields, or any change to how
`lv_icp_fit_score` itself is computed.

</domain>

<decisions>
## Implementation Decisions

### Scope lift (gate, resolved before the discussion proper)

- **D-01:** v0.9's "no new HubSpot properties of any kind" decision (operator, 2026-08-11) is
  lifted for **exactly one** derived-tier string property and nothing else.
  `lv_icp_scoring_version` remains out of scope; the three §5.3 fields remain deferred to v1.0.
  The lift is forced rather than preferred: `lv_icp_tier` is `type: enumeration,
  calculated: false`, zero of 264 portal properties are calculated enumerations, and HubSpot does
  not support enumeration outputs for calculation properties — so this is a new property plus a
  migration, not a formula edit. Amendment written into `.planning/REQUIREMENTS.md` § Out of Scope
  (dated, additive, in the COVER-01/COVER-02 amendment style) and committed as `4173da0`.
  — **Reversibility:** costly — the amendment is a text revert, but a created HubSpot property
  cannot be un-created, only archived, and archived internal names are generally not reusable.

- **D-02:** Phase 50 extends **v0.9** rather than opening v1.0. It closes v0.9's own disclosed
  debt (`WINDOWS.md` ids 9–12), so the milestone does not ship with a known unmet truth.

### Null semantics

- **D-03:** **Preferred variant is uncoalesced** — `lv_icp_fit_score` referenced bare, so
  never-scored companies keep today's blank tier. Zero operator-visible change beyond the 4 stuck
  records. WF1's branches all carry `includeObjectsWithNoValueSet: false`, so blank is already the
  status quo for never-scored records.

- **D-04:** **Forced fallback if uncoalesced proves impossible** — if the live test shows HubSpot
  blanks the whole property when a referenced term is null even in an *untaken* branch (Phase 41
  proved this for a bare sum; whether it extends into conditionals is the open question), ship
  `coalesce(lv_icp_fit_score, -1)` and accept roughly 646 never-enriched companies flipping blank
  → `"Unscored"`. Report the flip to the operator as a disclosed deliberate consequence, in the
  Phase 49 unmet-truth style — do **not** stop for a checkpoint, and do **not** abandon derivation.
  — **Reversibility:** costly — undoing the flip means changing the formula back, which is cheap,
  but ~646 records will have been visibly re-labelled to the operator in the interim.

- **D-05:** The live null test is run by a **fresh two-key-gated script kept in `scripts/`** —
  the repo's paired `DRY_RUN=false` key plus its own allow-key. This deliberately supersedes the
  spike's posture: `spike_tier_formula*.py` were gated on `ALLOW_SPIKE_PROPERTY_WRITE` alone and
  were therefore *not* kept (Phase 49 code review CR-01). Teardown discipline carries over
  verbatim — disposable property archived in a `finally` block and verified gone by re-read
  (404). No company record is read or written by this test.

### Migration shape

- **D-06:** **Retire `lv_icp_tier` within Phase 50**, but only as the **last gated step** — ship
  the derived property, prove it, migrate dependents, *then* archive. If the gate fails, the phase
  closes with the derived property live and the old enum still present; that is a coherent partial
  state, not a failure to clean up.
  — **Reversibility:** one-way — archiving a HubSpot property cannot be undone by re-creating it
  under the same internal name, and every portal dependent still pointed at it breaks at that
  moment. This is the phase's single irreversible act and must sit behind D-07's gate.

- **D-07:** **The gate for both retirement and WF1 shutdown:** the derived property matches WF1's
  `lv_icp_tier` on **all 66 scored companies with zero mismatches** — except the 4 known stuck
  records, where the derived value **must differ** (`B`, not the stale `C`). A mismatch anywhere
  else is a defect, not a rounding difference. Provable from HubSpot alone, matching the
  Phase 47–49 evidence bar.

- **D-08:** **WF1 (`4625147345`) is switched off but its definition kept.** Full cleanup is
  deferred until the new property passes D-07's evaluation (operator's words: *"defer full cleanup
  until new property passes evaluation"*). `config/hubspot_flows/4625147345-wf1-set-icp-tier.*.json`
  already archives before/after states, so an off-but-present workflow is a one-action rollback.
  Do not delete it, and do not leave it running alongside the derived property — two writers
  disagreeing is worse than either alone.

- **D-09:** **The derived ladder mirrors WF1's 5 values exactly** — `lv_anti_icp_flag` → `D`,
  `>= 70` → `A`, `40..69` → `B`, `15..39` → `C`, else `Unscored`. The 6th label
  `Needs Review` that `config/icp_scoring.yaml`'s `recommended_motion` map names is **not** added,
  even though a string property makes it structurally free. PARITY-01 stays a documented accepted
  divergence (deferred since Phase 40, `40-06-SUMMARY.md` F8/ENGINE-07). Rationale: any tier
  change this phase produces must be attributable to the derivation mechanism, not to a rubric
  change smuggled in alongside it.

- **D-10:** **The 4 stuck records are fixed as a pure side effect — no record write.** Their score
  is already correct at `45`, so a derived tier lands them on `B` the moment the property exists:
  no event, no enrolment, no PATCH. Verify by reading them back, never by writing them.

- **D-11:** **If a portal dependent cannot be migrated, stop and bring it to the operator** — a
  checkpoint on the real case, not a rule decided in advance. Do not force the retirement through,
  and do not silently keep the old property alive without saying so.

### Portal dependents

- **D-12:** Operator knows of two dependent classes today: **sales lists / saved views filtered by
  tier**, and **reports or dashboards grouping by tier**. Neither is visible from the repo. Treat
  these as confirmed-to-exist, not as the complete list.

- **D-13:** **Enumeration is a read-only API sweep committed as a phase artifact** — scripted
  across lists, workflows, views and reports for references to `lv_icp_tier`, in the evidence
  posture of `47.5-B-EVIDENCE.md` / `49-P2-SNAPSHOT.json`. It must be **re-runnable**, so it can
  be run again immediately before cutover to catch anything added in the interim.

- **D-14:** **The new property is created as `lv_icp_tier_derived`.** Operator's choice, made after
  being shown that `lv_icp_tier_calc` reads better as a permanent survivor.

- **D-15:** **Intent is to rename to `lv_icp_tier` after retirement — but this is flagged as
  unproven and must be researched, not assumed.** HubSpot property *internal names* are not
  editable after creation, and archived names are generally not reusable, so neither the rename
  route nor the archive-then-recreate route may be reachable. The spike never probed this.
  **If it proves impossible: keep `lv_icp_tier_derived` permanently** (operator's chosen fallback)
  — do not keep the old property alive merely to hold the canonical name, and do not treat the
  awkward survivor name as a reason to reopen D-06. Changing the *label* to "ICP Tier" remains
  available and costs nothing.
  — **Reversibility:** one-way — if a rename is attempted and the name is consumed or the property
  archived, there is no path back to the original naming.

### Proof bar

- **D-16:** **Zero company write windows are declared.** A calculated property computes itself and
  D-10 needs no PATCH, so no company record write is required anywhere in this phase. Property
  schema operations (create, archive) and the WF1 toggle are portal-schema actions, not record
  writes. Any company write that appears during execution is a **deviation requiring
  justification**, not a budgeted allowance. Context: Phase 47 declared 1 window and spent 5,
  disclosed.

- **D-17:** **Four pieces of regression protection**, all four required:
  1. A test pinning the live calculation formula against `config/icp_scoring.yaml`'s `tier_rules`,
     in the shape of Phase 49's `test_rubric_change_guard.py` (key-by-key, so the failure message
     names exactly what moved).
  2. `scripts/check_schema_drift.py` updated — it currently pins `lv_icp_tier`'s five-value enum
     (line ~119) and carries `PARITY-01-tier-label` as an accepted divergence; both go stale the
     moment the property is archived.
  3. `config/hubspot_properties.yaml` (declaration at line ~408) and
     `config/hubspot_flows/lv_icp_tier-property.*.json` updated to reflect the new property and
     WF1's off state.
  4. The derived-vs-WF1 comparison across all 66 committed as an **evidence artifact** (not a
     test), so D-07's gate decision is auditable after the fact.

- **D-18:** **Rollback is re-enabling WF1 *plus* a forced re-enrolment trigger.** Re-enabling alone
  is insufficient and this is the crux of the whole phase: value-identical records fire no event,
  so a re-enabled WF1 re-grades nothing. The forced-enrolment mechanism must be named and proven
  *before* WF1 is switched off — Phase 47.5's request-level `recompute: true` POST already solves
  the equivalent problem for the veto lane and is the obvious precedent. Do not accept "re-enable
  and let it converge naturally."

- **D-19:** **Operator-facing result is a before/after tier census in Phase 49's format** — reuse
  the three-point distribution report built in `49-07`. Expected result is stark and pre-registered:
  **identical distribution except 4 records moving C→B**. Anything else is a defect signal. No
  separate published Artifact required for this phase.

### Amendment 2026-08-14 (operator-directed, mid-execution) — D-20 … D-22

Two live findings during Plan 03/execution invalidated assumptions D-04 and the veto guard rested
on. Both were proven with disposable properties + a disposable company in portal `22617666`
(zero population records touched). Recorded here as amendments rather than edits, so the original
reasoning and the correction both stay visible.

**The finding that forced this:** `calculation_equation` reads **only numeric properties**.
A `booleancheckbox` reads as null even when set (`coalesce(lv_anti_icp_flag, -99)` discriminated
to `NULL` on a company whose flag was genuinely `true`), and enumerations are rejected outright at
property-create ("Sub-expression output type: String is not compatible with input type:
BigDecimal") — as are string and boolean literal comparisons. So every input the veto is built
from (`lv_anti_icp_flag`, `lv_produces_content`, `lv_is_hardware_vendor`, `lv_org_type`,
`lv_country_region_normalized`) is unreadable, and `lv_anti_icp_flag → D` was silently never
firing. The spike's "booleans arrive as BigDecimal" was correct about the declared *type* and
silent about the *value*.

- **D-20:** **A second new property is authorised — `lv_anti_icp_flag_num`** (numeric 0/1),
  extending D-01's one-property lift. Required, not preferred: with bools and enums unreadable,
  a numeric mirror is the only way the veto branch can be expressed at all.
  — Operator raised the right objection ("shouldn't it be derived from the original, so it
  references one boss number instead of being written twice?"). It **cannot** be derived: there is
  no numeric upstream for a formula to read. But it is **not** a second derivation — the veto is
  computed once, in `Decide Company Action` / `src/icp_scoring.py`, and the mirror is a second
  *serialization* of that same computed value emitted in the same write. This is the **existing**
  architecture, not a workaround: `lv_icp_fit_score` is itself a `calculation_equation` summing
  five pipeline-written numeric properties, one of which (`produces_content_score`) is already a
  boolean pre-translated to a number for exactly this reason.
  — **Drift control is mandatory**, since the objection is legitimate: a test in BOTH engines
  asserting the boolean and its mirror always agree, and a population-level agreement check.
  — **Reversibility:** costly — a created property cannot be un-created, only archived, and
  archived internal names are not reusable (proven: the API DELETE is a soft archive).

- **D-21:** **D-04 is REVERSED — ship the uncoalesced formula D-03 preferred.** D-04 fired on a
  race, not a finding: calculated properties backfill ~70–130s after create, and Plan 01's probe
  read back immediately, recording "not computed yet" as `null_propagates`. Re-tested with
  polling, a bare reference to a null `lv_icp_fit_score` fell through to its else branch normally
  — **null does not propagate**. The ~646 never-enriched companies flipped blank → `"Unscored"`
  must be flipped back. `50-NULL-PROBE.json` stays committed unaltered as historical evidence of
  what was believed at the time; this amendment is the correction of record.

- **D-22:** **Any probe of a calculated property MUST poll to a populated value** (or a fixed
  ≥3 min ceiling) before concluding anything. A single immediate read-back is no evidence. This
  is the process defect behind D-21 and applies to every future formula probe in this repo.

### Amendment 2026-08-14 (operator-directed) — D-23

- **D-23:** **D-07's accepted-divergence class is extended from 4 records to 5**, adding Coffs
  Harbour Racing Club `14752488879` (`WINDOWS.md` id 14) alongside ids 9–12.
  — **Why it is legitimate:** it is the same WF1-staleness bug class the phase exists to retire —
  a value-identical PATCH fires no property-change event, so WF1 never re-enrolled. Its `lv_icp_tier`
  reads `Unscored` while `lv_icp_fit_score` is `25`, which `config/icp_scoring.yaml`'s `tier_rules`
  grade as `C`. So `lv_icp_tier_derived` reads `C` and is **correct**; the stale enum is wrong. It
  diverges in the *opposite* direction from ids 9–12 (`Unscored`→`C` rather than `C`→`B`), which is
  the only reason it fell outside the original hardcoded list.
  — **Why it is nonetheless recorded as an amendment, not a fix:** D-07 was pre-registered
  specifically so a red result could not be explained away, and widening an exception list after
  seeing the result is the exact move that pre-registration guards against. The operator was shown
  that framing and chose to extend deliberately. Without this amendment the gate stays RED and
  retirement stays blocked — on evidence that the new property is *better* than the old one.
  — Encoded in `scripts/check_tier_derived_parity.py`'s `KNOWN_STUCK_IDS` / `KNOWN_STUCK_WINDOWS_IDS`
  with the id tagged `D-23`, so the evidence artifact names the ledger entry rather than saying
  "known exceptions" generically.
  — **Reversibility:** cheap — narrowing the set back is a one-line edit and a re-run.

### Claude's Discretion

None. Every question in this discussion was answered with an explicit choice — no "you decide"
option was taken. Where judgement remains it is bounded by a named fallback (D-04, D-15) rather
than left open. D-20 and D-21 were likewise explicit operator choices, made mid-execution when
live evidence contradicted the original decisions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary evidence for this phase
- `.planning/TIER-DERIVATION-SPIKE-2026-08-13.md` — **the researcher's primary source.** Verdict
  CONCLUSIVE POSITIVE on grammar. Contains: the two-syntax trap (Properties API
  `calculationFormula` uses a statement-form grammar, *not* the `if(cond, a, b)` bracket-ref
  grammar in HubSpot's published docs — do not port syntax between them); the finding that HubSpot
  *booleans* arrive in formula-land as **BigDecimal**, so `lv_anti_icp_flag` cannot sit bare in a
  condition and `coalesce`'s second argument must be numeric (`0`, not `false`); the full
  authoritative token list captured from a 400 body; the accepted ladder; and the three things
  explicitly NOT established (runtime null propagation, in-place conversion, portal dependents).
- `.planning/WINDOWS.md` ids 9–12 — the 4 stuck records, logged as unmet truth by Phase 49.

### Requirements and scope
- `.planning/REQUIREMENTS.md` § Tier Derivation (TIER) — TIER-01/02/03, added 2026-08-13.
- `.planning/REQUIREMENTS.md` § Out of Scope — the no-new-properties bullet and its dated
  scope-lift amendment (D-01).
- `.planning/ROADMAP.md` § Phase 50 — goal, scope amendment, 5 success criteria.

### Precedent to follow
- `.planning/phases/47.5-veto-recompute-path/` — the forced-recompute mechanism D-18 depends on
  (request-level `recompute: true` on the D-18 webhook POST; note the naming collision — that
  phase's decision id is unrelated to this phase's D-18).
- `.planning/phases/49-re-score-strategy-reporting/` — the three-point distribution report format
  (D-19), the arm/disarm and read-back-after-disarm evidence bar, and `test_rubric_change_guard.py`
  as the shape for D-17's formula pin.
- `docs/OPERATOR-RESCORE.md` — the runbook conventions this phase's operator-facing output should
  match.

### Portal facts and schema
- `PORTAL-FACTS.md` — live portal facts; re-confirm anything it asserts about `lv_icp_tier`.
- `config/hubspot_properties.yaml` (~line 408) — the declared `lv_icp_tier` enumeration.
- `scripts/check_schema_drift.py` (~line 119) — the five-value enum pin and the
  `PARITY-01-tier-label` accepted divergence.
- `config/hubspot_flows/4625147345-wf1-set-icp-tier.{before,after}.json` — WF1's archived
  definition; the rollback anchor for D-08.
- `config/hubspot_flows/lv_icp_tier-property.{before,after}.json` — the property's archived state.
- `CLAUDE.md` §5.2 and §10.2 — what the tier means operationally (A/B/C/D → recommended motion).
- `.planning/HANDOFF-2026-08-08-formula-spike.md` — the Phase 41 formula spike, source of the
  "HubSpot blanks a calculated property when a referenced term is null" finding that D-04 hinges on.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 49's `test_rubric_change_guard.py`** — key-by-key dict comparison so the failure names
  exactly which key moved. Direct template for D-17's formula pin.
- **Phase 49's three-point distribution report builder (`49-07`)** — reusable as-is for D-19.
- **Phase 47.5's `recompute: true` webhook path** and
  `scripts/remediate_veto_companies.py::post_webhook_event(..., recompute=True)` — the existing
  forced-enrolment precedent D-18 requires.
- **The spike's teardown pattern** — create disposable, PATCH per candidate, archive in `finally`,
  verify gone by 404 re-read. Carry it into D-05's permanent script.
- **`config/hubspot_migration/baseline/portal-schema-companies-*.json`** — an established
  before/after portal-schema snapshot convention for property changes.

### Established Patterns
- **No repo code writes `lv_icp_tier`.** All ~35 references are reads, forbidden-list guards or
  tests; project D-07 already treats the tier as HubSpot-derived, and
  `scripts/remediate_veto_companies.py:17` says so explicitly. WF1 is the sole writer, so retiring
  it orphans nothing in code — the blast radius is smaller than it looks.
- **Calculated properties carry `readOnlyValue: true`** — the derived tier becomes unclobberable,
  which is a benefit *and* a constraint: nothing can PATCH it, including a corrective script.
- **Armed, capped write windows with disarm-and-read-back verification** (Phases 47–49) — the
  discipline this phase inherits even though D-16 declares zero company windows.
- **Deploy-and-bounce for n8n** — a bare PUT never reloads a running workflow. Relevant only if
  any n8n-side change turns out to be needed; none is currently anticipated.

### Integration Points
- **HubSpot Properties API** — property create (new calculated string), archive (retirement), and
  the `calculationFormula` field. Note the two-syntax trap in the spike.
- **HubSpot Workflows/Flows API** — WF1's on/off toggle and the dependent-workflow half of D-13's
  sweep. Lists, views and saved filters are the parts that may resist API enumeration.
- **`scripts/check_schema_drift.py`** — the comparator that must learn about the new property or
  start reporting noise the moment the old one is archived.

</code_context>

<specifics>
## Specific Ideas

- Expected end-state distribution is **pre-registered**: identical to the current census in every
  bucket *except* 4 records moving C→B. Stating it up front makes the report a test rather than a
  narrative — a distribution that differs anywhere else is a defect signal.
- The name `lv_icp_tier_derived` was chosen by the operator over the suggested `lv_icp_tier_calc`
  after being shown the survivor-name argument. Do not silently substitute the other name.
- Operator's phrasing on WF1, recorded verbatim: *"Switch off, keep definition, defer full cleanup
  until new property passes evaluation."*

</specifics>

<deferred>
## Deferred Ideas

- **PARITY-01 / the 6th `Needs Review` tier label** — structurally free once the tier is a string
  property (the enum-option addition that blocked it in Phase 40 no longer applies), but
  deliberately not taken here per D-09 to avoid confounding a mechanism change with a rubric
  change. Genuinely cheap for a future phase.
- **`lv_icp_scoring_version`** — remains out of scope; D-01's lift is one property only.
- **The three CLAUDE.md §5.3 fields** (`lv_qualitative_fit_summary`, `lv_budget_timeline_signal`,
  `lv_loss_reason_detail`) — remain deferred to v1.0 alongside EVID-01..03.

### Reviewed Todos (not folded)
All three pending todos matched Phase 50 at score 0.6 but on stopwords only (`claude`, `operator`,
`run`, `records`) — none touches tiering. All are v0.8-era deferrals, reviewed and **not folded**:

- `2026-08-04-enrichment-throughput-ceiling.md` — 82% of every full run is two sequential Anthropic
  calls. Unrelated: this phase makes zero Anthropic calls.
- `2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md` — operator-plugin packaging fragility.
- `2026-08-04-uat-22-names-aliases-the-mapping-lacks.md` — contact-upload column mapping.

</deferred>

---

*Phase: 50-derived-tier-property*
*Context gathered: 2026-08-13*
