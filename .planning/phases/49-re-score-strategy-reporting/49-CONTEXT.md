# Phase 49: Re-score Strategy & Reporting - Context

**Gathered:** 2026-08-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Three things, in this order:

1. **A defined, budget-bounded re-score procedure the operator can trust *before* invoking it**
   (RESCORE-01/RESCORE-02) — which records, in what chunk size, under which write window, at what
   stated cost, for *both* classes of rubric change.
2. **Execute it.** Phase 46 **did** change three weights (`individual_club_team` 5→15,
   `regulator` 0→−20, `graduated_deductions.gambling_operator` removed; commit `caae5d6`,
   2026-08-11), so the ROADMAP's "if Phase 46 changed a weight" branch is **live** — the
   full-population re-score is owed, not merely proven.
3. **Narrate v0.9's net effect on the target list in plain language** (RESCORE-03), covering the
   milestone as a whole: veto clear (47), veto recompute + D-V6 flips (47.5), coverage
   enrichment (48), and this phase's weight-driven re-score.

Plus one folded todo (the production n8n research prompt's missing org-type definitions) and
three carried-forward items three prior phases assigned to Phase 49 by name.

**Acceptance anchor:** `scripts/run_scoring_parity.py`'s live population sweep exits **green**.
That sweep has been **red by design** since `caae5d6` — it compares each record's old-weight live
score against the new-weight oracle — and closing that deliberately-opened window is this phase's
headline proof. Do not "fix" the sweep; make it true.

**Not this phase:** implementing the `venue` enum option (deferred by Phase 48 D-02 and its
2026-08-13 CLOSURE block — the LOCKED file's "Scores in: Phase 49's full-population re-score"
line is **moot**, and the planner must not resurrect it); exercising the veto branch of the
re-score procedure live; `docs/SYSTEM-CONTRACT.md`'s stale boundary section; enrichment
throughput/latency work; the v0.9 milestone close itself.

</domain>

<population>
## The population — 66, and it is NOT a choice

`HAS_PROPERTY(lv_icp_fit_score)` = **66** companies (portal holds 712; only these 66 have ever
carried a score). This is **forced, not a decision**, and the planner must not re-open it:

- It is the *same* selection `scripts/run_scoring_parity.py::_select_sample_ids` and
  `scripts/simulate_rubric_weights.py::_select_row_ids` deliberately share — the latter's docstring
  says so explicitly: *"no second definition of the scored population"*.
- Any scored record left out of the re-score keeps surfacing as a `real_finding` on the parity
  sweep, so the red window **never closes** and the phase cannot meet its own acceptance bar.
- **Includes the vetoed records.** 46-02's live simulation found the gambling-flagged and
  `regulator` rows' *scores* move under D-02/D-03 even though their *tiers* do not.
- **Includes Editix `17317381378`** (`lv_org_type = "unknown"`, score 0 — still satisfies
  `HAS_PROPERTY`). Five zero components is a harmless uniform write.

**Re-derive it live and stamp the date anyway.** A committed snapshot is evidence, not a
guarantee — the house rule that caught COVER-01's stale "18" (13 records out of date) and the
ROADMAP's stale Phase 48 census.

**v0.9 entry distribution (the report's point 1):** `A:7 B:18 C:17 D:24` across the 66
(PROJECT.md; corroborated by `46-simulation-20260811.json`'s live column, 2026-08-11 — the only
dated full-66 snapshot predating every v0.9 write). PROJECT.md also records a **prediction**:
*"a correct post-remediation shape is roughly A:7 B:18 C:17+ D:7."*

**Expected movement from the weight change** (46-02's live simulation, exact match against
`41-final-population.json`): **14 of 66** rows move, all `individual_club_team` **C→B**. QRIC and
both gambling-flagged records carry genuine hard vetoes independent of the weight change, so
their scores move but their tiers do not.

</population>

<decisions>
## Implementation Decisions

### The re-score mechanism (pre-decided by Phase 46 — do not re-litigate)

- **D-01:** **Component backfill, not the n8n pipeline.** Reuse
  `scripts/backfill_seed_company_scores.py::compute_components()`, which computes all five
  component scores in Python from each record's own current canonical inputs via
  `src/icp_scoring.compute_icp_score()` (reading `config/icp_scoring.yaml` directly — never a
  second hand-copied table), then batch-PATCHes `org_type_score` / `geography_score` /
  `annual_revenue_score` / `produces_content_score` / `gambling_score` via
  `src.hubspot_client.batch_update_companies()`. Writing **all five** (never a subset — a missing
  term blanks the calculated sum) makes `lv_icp_fit_score` recompute and WF1 fire, with **no
  reliance on unverified same-value re-enrollment**.

  Cost: **~0 n8n executions, 0 Anthropic calls, 0 provider credits.** `BATCH_CHUNK_SIZE = 100`,
  so 66 records is **one** batch call. Verified: `grep -c org_type_score` over
  `scripts/build_cloud_workflows.py` and `n8n/wf_enrichment_cloud.json` returns **0** — the n8n
  leg writes no component score at all, which is why the pipeline is not the tool here.

  **Rejected:** the SJ-3 `lv_enrichment_requested` poller path — a full waterfall including two
  sequential Anthropic calls per record, for inputs that already exist live on all 66. Source:
  `46-DECISION.md` § "What Phase 49 owes and what it costs".
  — **Reversibility:** reversible — components are recomputable from any config; re-running with
  the prior `icp_scoring.yaml` restores the old values exactly.

- **D-02:** **Veto fields need no recomputation for *this* change.** None of Phase 46's three
  weight changes touches hard-veto category membership (non-ANZ / no-content / hardware-vendor);
  veto derivation lives entirely in n8n's `ENRICH_DECIDE_CO_CLOUD`. **This is not true of rubric
  changes in general** — see D-06's decision rule.

### Getting past the Phase 40 sample cap

- **D-03:** **Raise `HARD_CEILING_RECORDS` from 25 to 100, and replace the blunt count cap with a
  pinned exact-set gate.** The sample must equal the live-derived
  `HAS_PROPERTY(lv_icp_fit_score)` id set **exactly**, or the driver refuses non-zero.

  This is **strictly stronger** than what it replaces, and the planner should say so in the diff:
  a count cap of 25 permits *any* 25 records; an exact-set gate permits only the intended ones.
  Precedent: `scripts/remediate_veto_companies.py`'s `PINNED_COMPANY_ID_ORDER` gate (Phase 47).

  `DEFAULT_MAX_RECORDS = 10` stays — the ceiling is the safety bound, not the default.
  `enforce_sample_cap`'s refuse-rather-than-truncate behaviour is preserved verbatim; only its
  predicate changes.

  **Rejected:** three ≤25-record chunks with distinct `--company-id` sets (46-DECISION's option
  (a)) — three invocations is three times the surface for the window-count failure Phase 47 hit
  (five arm/disarm cycles against a must_have of one). **Also rejected:** a new dedicated driver
  — it would be a second producer of the same five component writes.
  — **Reversibility:** costly — the constant is a Phase 40 safety bound with its own tests; the
  swap from count-cap to exact-set gate changes the refusal contract every caller relies on, so
  undoing it means re-deriving what "too many" meant.

- **D-04:** **Canary one record first, inside the one window.** `46-DECISION.md` flagged exactly
  one edge unresolved and assigned it to *"Phase 49's own research"*: whether overwriting an
  already-`PROPERTY_DEFAULT_VALUE`-stamped component behaves identically to writing a never-set
  one. HubSpot's stamp mechanism is **API-inaccessible for reads** (`PORTAL-FACTS.md`), so it
  cannot be settled by inspection.

  Procedure: inside W1, PATCH a **single** record whose components definitely change under the
  new weights (any `individual_club_team`, `org_type_score` 5→15), settle, read back
  `lv_icp_fit_score` + `lv_icp_tier`, confirm the write landed — **then** release the remaining
  65 in the **same** window. Zero extra arm/disarm cycles. Phase 40-07's own pattern (prove the
  mechanism on a sample before the population), and it means a stamp-related failure surfaces on
  1 record rather than 66.

### Windows, deploys, and arming authority

- **D-05:** **Declared up front, D-06-style: exactly 1 deploy+bounce, W1, and a conditional W2.**

  | # | What | Surface armed | Cost |
  |---|---|---|---|
  | deploy | the folded research-prompt todo | `DRY_RUN=false` + `ALLOW_N8N_DEPLOY=true` in one invocation, **plus a bounce** | 1 deploy, 1 bounce, ≥1 proof execution |
  | **W1** | the 66-record re-score | backfill's **own** two-key gate: `DRY_RUN=false` + `ALLOW_SCORE_BACKFILL=true` | **0 n8n executions**, 0 Anthropic, 0 credits, 1 batch PATCH |
  | **W2** | **CONDITIONAL** — Entain only, opens only if its research clears the bar | `ALLOW_HUBSPOT_RECORD_WRITES` **and** `scripts/june_run_arm.py`'s n8n allowlist | 1 record, ~1–2 n8n executions |

  **W1 arms a surface n8n knows nothing about.** `ALLOW_SCORE_BACKFILL` is a Python-side env gate
  on a direct CRM v3 batch call; no n8n allowlist is armed and no execution is spent. Do **not**
  copy Phase 48's "both arming surfaces must be armed together" rule into W1 — there it served
  one write; here the two surfaces serve two unrelated writes, and arming n8n record-writes for
  W1 would widen the blast radius for nothing.

  W2 is declared **conditional** because its trigger is a research outcome nobody knows yet.
  Exceeding this declaration is a **disclosure obligation in the run report**, not a silent event.

- **D-06 (waiver):** **`D-49-01` — a NEW, separately-granted, Phase-49-only delegation of the
  deploy+bounce and both arming surfaces to Claude.** `D-48-01` **expired with Phase 48** and
  `D-47.5-01` before it; neither is revived and neither may be cited. Terms, all binding and
  copied from the version that has now worked twice:

  - **Expires with Phase 49.** The "arming is operator-only" / "deploys are operator-only" rules
    resume full force the moment this phase seals.
  - Arming vars are set **per-shell only** — never `.env`, never a profile, never exported into a
    shell that outlives the window.
  - **Disarm is ungated** and runs even when the write leg fails or raises. Closing the window
    always wins.
  - After disarming, **independently re-read** every armed surface and quote the read-back
    verbatim. A re-read of the stored PUT body is not evidence (Trap 3).
  - Arm and window run as **separate shell invocations** so a failed window start still has an
    explicit disarm path (48-05's precedent).
  - **The window declaration in D-05 is unchanged.** Delegation changes who types the command,
    not how many times it may be typed.
  - **Project-level D-07 is unaffected** (see `<constraints>`).

### The reusable procedure (RESCORE-01)

- **D-07:** **A runbook doc *and* a `--plan` mode — the numbers produced by code, not prose.**
  `docs/OPERATOR-RESCORE.md` is what the operator reads before deciding (plain language, the
  `docs/OPERATOR-VETO-REFRESH.md` precedent); it **cites** a `--plan` / dry-run mode on the
  re-score driver that emits the live re-derived id set, its count, the chunking, the window
  shape and the cost. House rule this follows: `47-COST-ESTIMATE.md`'s figures were read from a
  live `estimate_cost()` call **so the doc and the function cannot silently drift**. A
  prose-only runbook is the mechanism that let a stale 18-record census survive two phases.
  — **Reversibility:** reversible.

- **D-08:** **The runbook covers BOTH branches, with the decision rule first.** Step 1 is a
  classifier, not a procedure:

  ```
  Did the change touch a VETO predicate?  (non-ANZ / no-content / hardware-vendor)

    NO  → weight branch:  component backfill only
                          0 n8n exec | 0 Anthropic | 0 provider credits
    YES → veto branch:    backfill + one recompute POST per record
                          ~66 n8n exec (2.6% of the 2,500/month allowance)
                          0 Anthropic | 0 provider credits
  ```

  The veto branch's cost is **measured, not estimated**: Phase 47.5 clocked the recompute lane at
  1 n8n execution per POST, 0 provider credits, 0 Anthropic calls (executions `11858`–`11861`).
  The branch is **documented, not exercised** this phase — see `<deferred>`.

- **D-09:** **A guard test that fails on an unaccompanied weight change.** Pin
  `config/icp_scoring.yaml`'s `base_score` table (digest or literal) in a pytest whose failure
  message names `docs/OPERATOR-RESCORE.md` and the re-score obligation, so the next weight change
  cannot land without a deliberate, reviewed re-baseline. Established idiom three times over:
  `tests/test_n8n_org_type_absence.py` (permanent absence guard),
  `tests/test_flow_rubric_conformance.py`, and `tests/test_companies_factory_frozen.py`, whose own
  header insists its fixture is re-baselined *"ONLY by an explicit, reviewed act — never as a
  routine 'make the test pass' step."* Write that same sentence into the new guard.

  **Rejected:** relying on the parity sweep as the detector. It detects *after* the divergence
  exists — the red window is the very state this phase closes — and v0.8 shipped the sweep
  **inert**: PROJECT.md records the cron/launchd schedule was never installed and `crontab -l`
  is empty, so nothing is running it on a cadence today.
  — **Reversibility:** reversible.

### The report (RESCORE-03)

- **D-10:** **Three points, two free live reads.**

  | Point | Source | Captures |
  |---|---|---|
  | P1 — v0.9 entry | `46-simulation-20260811.json`'s **live** column | `A:7 B:18 C:17 D:24`; predates every v0.9 write |
  | P2 — pre-re-score | fresh live read **before W1 opens** | what 47 + 47.5 + 48 already did |
  | P3 — post-re-score | fresh live read **after W1 settles** | the three weight changes on all 66 |

  Per-phase attribution then falls out for free, and live reads cost nothing — no executions, no
  credits. **Rejected:** a two-point entry→after series (satisfies the letter of RESCORE-03 but
  lumps three different levers into one undifferentiated delta — Phase 46 spent a whole plan
  building a *three*-column report precisely to avoid that misattribution). **Also rejected:**
  reconstructing the series from committed AFTER snapshots only — they are per-cohort (17, 3 and
  5 records), not full-population, and the cohorts overlap (Simtech LED and Jam TV each appear
  in two).

- **D-11:** **Committed markdown *plus* a published Artifact.** `49-RESCORE-REPORT.md` in the
  phase directory is the durable, git-reproducible record citing every source. A published
  Artifact is the readable, forwardable surface — **private by default**, link handed to the
  operator, who decides whether it is ever shared. Content is internal company names, tiers and
  scores; no personal data. This also **discharges 46-03's deferred D-09 shareable-artifact
  publish**, which was deferred only because that CLI executor had no artifact capability.

  Markdown-only was rejected on reachability grounds: PROJECT.md's operator is non-technical,
  works in Claude Desktop and never opens the repo — v0.6's premise is that *"an instruction to
  run a command is a requirement failure, not a fallback."*

- **D-12:** **Counts + GTM consequences + a named-caveats block.** Tier counts at all three
  points; every material movement stated as a consequence for how the account gets worked, with
  records **named** (e.g. "14 racing clubs moved C→B: worked directly now, not via a governing
  body"; "Racing NSW `15008671672` B→A"; "Simtech LED `18047161864` B→D, suppressed as a hardware
  vendor"; "16 false vetoes returned to the list"). Then an explicit **"what this does not say"**
  block carrying what the milestone knows it did not prove:

  - the score is a fit heuristic derived from 92 closed deals, **not a forecast**;
  - Gravity Media `15860277364`'s `ANZ` rests on **Australian operating presence alone** — its NZ
    leg is **UNPROVEN** and `ANZ` denotes the multinational-with-local-operations pattern per
    D-V6, not a count of countries;
  - Editix `17317381378` is **`Unscored`, not Tier D**, and that distinction is deliberate
    (Phase 48 D-03: blank = never attempted, `unknown` = attempted, evidence insufficient);
  - v0.9's Anthropic **dollar** figures are **floors, never measurements** —
    `claude_web_research()` does not log `msg.usage`.

### Carried-forward items (assigned to Phase 49 by name)

- **D-13:** **Entain `10024564084` — re-examine BOTH veto inputs**, region *and*
  `lv_produces_content`. The LOCKED venue decision calls the three-record re-examination
  *"a mandatory, explicit re-examination in Phase 49 — not an incidental consequence of the
  re-score"*; Phase 47.5 discharged Ironman and Gravity Media, Entain is the residue.

  Region-only was rejected for a measured reason: a region flip **provably cannot move Entain**,
  because `lv_produces_content = false` fires a second, independent hard veto — so region-only
  spends a write for zero effect on the target list. And the M3 tri-state rule sets
  `lv_produces_content = false` **only on positive evidence of absence**, which was never
  recorded for Entain. Re-examining both is the only path that could make it targetable.

  The research uses the D-V6 bright line — **"does it have substantive ANZ operating presence?"**,
  not "where is it headquartered?" — and must return **evidence URLs**, not assertion.
  Route it through `src/web_research.py` (whose prompts Phase 48-07 already fixed with
  `config/taxonomy.yaml` definitions), **not** the n8n lane.
  — **Reversibility:** costly — clearing a hard veto returns a record a human deliberately
  excluded to the target list; undoing it means re-establishing the exclusion and explaining the
  round trip.

- **D-14:** **Sign-off: config bar only, no human gate — an explicit, dated OVERRIDE.**
  The operator was shown the conflict and chose this. Recorded as an override rather than by
  rewriting the gate, per RUBRIC-01's house pattern (*"where a decision overrides the evidence,
  the override and its reasoning are recorded and the underlying evidence is left intact"*).

  **What is being overridden, stated plainly and left intact in its source:**
  - `CLAUDE.md` §21.3 — human review required when a hard veto is possible but uncertain, and
    when there is no evidence URL for content output;
  - `CLAUDE.md` §15.1 — `anti_icp_flag_would_change` and `lv_produces_content_conflict` are both
    named Sonnet-5 escalation triggers;
  - the LOCKED venue decision's own stated risk: *"the risk being managed is that a re-score
    silently un-vetoes a record a human deliberately excluded."*

  **What still binds, and is not negotiable:** the driver **hard-refuses** below
  `field_policy.yaml`'s `lv_produces_content` bar — `min_confidence: 85` **and**
  `require_evidence_url: true` — and every piece of evidence (URLs, confidence, summary) is
  written into the run report so the decision is reviewable after the fact. A refusal is a
  refusal, never a warning, and never a truncation.

- **D-15:** **The live `D` → non-`D` tier TRANSITION is proven on Entain if it flips, and
  re-deferred *with the reason recorded* if it does not.** 47.5-03 could not close it: its two
  reads were ~5s apart and the disarmed rehearsal read `lv_icp_tier: "Unscored"` pre-veto, so the
  flag→tier flow likely never wrote `D` at all. Instrument W2 to capture it *as* a transition:

  ```
  read  lv_icp_tier          → D            (t0, independent read)
  write region + lv_produces_content
  poll  until lv_anti_icp_flag settles
  read  lv_icp_tier          → non-D        (t1, independent read)
  record t1 − t0
  ```

  **Assert `≠ D`, never a specific tier.** The landing tier depends on Entain's
  `lv_revenue_band`, which must be read in pre-flight rather than assumed: Entain plc is a
  1.2B+-revenue company, and if that band is populated the rubric's **−50** deduction applies —
  `produces_content +20`, `geography ANZ +10`, `org_type gambling_operator 0`, `revenue −50`
  = **−20**, which grades `Unscored`. That is non-`D` and satisfies the transition proof, but it
  is neither `B` nor `C`. A hard-coded `B or C` assertion is exactly the stale-literal class
  Phases 45 and 47 each had to disclose after the fact — cheaper to prevent in the contract than
  to relax in the run report.

  If Entain does not clear the bar, **no vehicle exists this phase** — the weight re-score moves
  `C→B` only — so re-defer it with that reason stated. It has now been deferred by 47.5, 48 and
  potentially 49 in a row, which is how a permanent gap gets built one reasonable deferral at a
  time; say so rather than letting it roll silently into a fifth phase.

- **D-16:** **Jam TV `17317850381` retains its veto (D-23) — asserted by a plain read** in the
  run report, unconditionally, whatever else happens. Its veto is **geographic** (region
  `Other`, reason `Non-ANZ geography`) and Phase 48's `broadcaster` write could not and did not
  clear it. The portal-wide non-ANZ veto census stands at **2** (Entain + Jam TV) and the VETO-03
  bar (non-ANZ veto **and** blank region) reads **0 rows**; re-confirm both.

### Claude's Discretion

- **Engines-first ordering in the runbook.** Phase 46's parity rule means a weight change must
  land in **both** engines in one commit — `config/icp_scoring.yaml` (Python oracle) **and**
  HubSpot flow `4626124224` ("Update Score Based on Org Type"). Because the backfill computes
  components from the *Python* oracle, a lagging flow will silently overwrite correct backfilled
  components with old-weight ones the next time any input changes on that record. The runbook
  needs an explicit engines-first-then-re-score sequence. **No work is owed this phase** —
  Phase 46 Plan 04 already landed both with a running-content read-back — it is a runbook
  sequencing item.
- The report notes the **712-company portal denominator** (only 66 have ever carried a score) and
  **scores the outcome against PROJECT.md's own prediction** (`A:7 B:18 C:17+ D:7`) rather than
  quietly dropping the prediction.
- Deploy ordering relative to W1 — the folded todo's deploy touches the research prompt, which
  the re-score never traverses, so they are independent and may run in either order.
- The settle timeout and poll interval for the calculated-property chain (Phase 40-07 measured
  ~11s to settle `lv_icp_fit_score` → `lv_icp_tier`).
- Whether the exact-set gate re-derives the population at arm time or asserts against a pre-arm
  snapshot (prefer arm-time re-derivation; both are defensible).
- Whether the re-score also settles `lv_icp_score_breakdown` — `run_scoring_parity.py` has an
  opt-in `--write-breakdown` path that patches exactly that one property.
- Plan/wave decomposition, and whether the `--plan` mode lives on `backfill_seed_company_scores.py`
  or on a thin re-score wrapper over it.

### Folded Todos

- **`.planning/todos/pending/2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md`**
  (score 0.6, severity **major**, discovered in Phase 48). Operator chose to fold it.

  **The problem:** Phase 48-07 fixed the root cause of Racing NSW's misclassification by adding a
  `definition:` key to every `org_types` entry in `config/taxonomy.yaml` and rendering
  `src.taxonomy.org_type_definitions_block()` into both **Python** prompts. **The production n8n
  prompt was not fixed.** `COMPANIES_TARGET.research_system_prompt_fn_js` in
  `scripts/build_cloud_workflows.py` (function `researchSystemPrompt()`, ~line 2039) still builds
  its `allowed_org_types` line as `"allowed_org_types: " + JSON.stringify(ORG_TYPES) + "."` —
  bare keys from `n8n/code/taxonomy.generated.js`, no definitions. The live lane and its
  local-live twin can therefore still reproduce the statutory-origin misclassification for any
  org whose statutory history reads like QRIC's or Racing NSW's.

  **The fix, per the todo:** teach `scripts/gen_taxonomy_js.py::render()` to also emit an
  `ORG_TYPE_DEFINITIONS` object mirroring `src.taxonomy.ORG_TYPE_DEFINITIONS`; build the
  `allowed_org_types` line from it (and the contacts-target twin, if applicable); re-baseline
  `tests/fixtures/companies_jscode_frozen.json` **as the explicit, reviewed act its own test
  insists on**; rebuild, deploy, bounce, and prove the running instance changed with a live
  execution's own node list. Add a `node --test` assertion that the emitted `jsCode` contains
  each org type's **definition text**, not just its bare key — mirroring
  `tests/test_taxonomy_conformance.py::test_tx10_every_org_type_has_a_definition_and_both_prompts_render_them`.

  **How it fits:** it consumes exactly the one deploy+bounce D-05 declares, and it is the reason
  this phase has a deploy at all. It is otherwise **independent** of the re-score — the component
  backfill never traverses the research branch.
  — **Reversibility:** costly — it changes the sealed enrichment lane's emitted prompt and
  re-baselines a byte-frozen fixture; undoing needs another rebuild + deploy + bounce.

</decisions>

<constraints>
## Hard rules that bind this phase — downstream agents MUST honour these

| Rule | Detail |
|---|---|
| **Project-level D-07** | **Never PATCH `lv_anti_icp_flag`, `lv_anti_icp_reason`, `lv_icp_fit_score`, `lv_icp_tier`.** Write inputs (the five `*_score` components, region, `lv_produces_content`), let the derived chain settle, read it back. Held absolutely through Phase 47.5's two windows and Phase 48's one. `lv_icp_fit_score` is a `calculation_equation` property and `readOnlyValue: true` — it cannot be written even by mistake |
| **`Decide Company Action` is the single veto writer** | Do not add a second. It is also the *only* writer of `lv_anti_icp_flag`/`lv_anti_icp_reason` |
| **The population is 66 and is not a decision** | See `<population>`. Re-derive live, stamp the date, and refuse if the set differs from what was armed |
| **Write all five components, never a subset** | `lv_icp_fit_score`'s formula **blanks entirely** when any one referenced term is null — it does not treat it as 0 (live-proven by Phase 40-04's reversible spike) |
| **No new HubSpot properties** | Standing v0.9 constraint. There is no `lv_icp_scoring_version` and there will not be — which is exactly why RESCORE-02 re-scores wholesale |
| **`run_scoring_parity.py`'s population sweep is the acceptance gate** | Red by design since `caae5d6`. Make it green by re-scoring; **do not edit the script to pass**. Phase 48 verified it untouched (`git log` last touch Phase 41, `986c37f`) and Phase 49 should preserve that property except where a genuine Rule-1 defect is found |
| **Deploys** | `DRY_RUN=false` **and** `ALLOW_N8N_DEPLOY=true` in **one** invocation, plus a **bounce** (deactivate → reactivate). Prove the running instance changed with a live execution's own node list, never a stored read-back |
| **Never hand-edit `n8n/wf_*.json`** | Edit `scripts/build_cloud_workflows.py` / `n8n/code/*.js` / `scripts/gen_taxonomy_js.py`, rebuild, deploy, bounce |
| **Parity rule (Phase 46)** | Any *scoring-predicate* change lands in every engine holding it, in one commit. The folded todo's prompt change is not a predicate — but if planning touches one, the rule binds |
| **Two engines carry org-type weights, not three** | `config/icp_scoring.yaml` and HubSpot flow `4626124224`. The n8n leg carries **no** org-type-keyed numeric table, guarded permanently by `tests/test_n8n_org_type_absence.py` (`46-ENGINE-INVENTORY.md`) |
| **`.env` is Read/Bash permission-blocked** | Drive live work through the dotenv form with an **absolute** path: `.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv('/abs/path/.env'); …"`. Bare `load_dotenv()` resolves relative to the **calling file**; with no `conftest.py`, live pytest needs a wrapper passing an absolute path or every HubSpot read 401s |
| **Tests** | `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` — **glob form**; the directory form is broken on node 24 |
| **Portal assertion before any network call** | `HUBSPOT_PORTAL_ID == 22617666` (ap1), the discipline every live script in this repo already follows |
| **`venue` is NOT implemented this phase** | Phase 48 D-02 + the 2026-08-13 CLOSURE block. The LOCKED file's "Scores in: Phase 49" line is moot. Adding an enum option is portal schema work with its own arming decision |

### Traps that already cost real time — do not re-pay them

1. **Stored ≠ running.** A bare `PUT /api/v1/workflows/{id}` does not reload a running workflow.
   Bounce, then prove it with an **independent** GET or a live execution's own node list.
2. **An EMPTY allowlist denies every write and still reports `armed`.** Assert the allowlist is
   non-empty **and** exactly the intended id set, in the driver, at arm time. Phase 48-05 widened
   this to also require `ALLOW_HUBSPOT_RECORD_WRITES == true` and an empty `TEST_RECORD_DOMAINS`,
   closing execution `11858`'s silent-denial shape.
3. **n8n `status: "success"` lies.** A node can receive a 400 and pass the error object downstream
   **as data**, `executionStatus: "success"`, zero node-level errors. Judge a run by node-level
   `runData`. (Phase 48 D-04's gate now catches the research-error shape — its live *firing* is
   still unproven.)
4. **A client POST timeout is not a failure.** n8n completes server-side.
   `post_webhook_event` defaults to a 300s read timeout. Never retry on timeout without reading
   the execution back — that is how a record gets touched twice.
5. **`isReturnOnly()` treats any non-`"write"` mode as return-only.** Anything carried as a `mode`
   value on a write path reports success and writes nothing. Use request-level row properties.
6. **`ENRICH_CO_GATE` is shared by three workflows**, only one of which has a
   `Parse HubSpot Event` node. Any `$()` read of a request-level property must use the repo's
   `nodeAll` try/catch idiom and **fail closed**.
7. **HubSpot's search index lags ~20s on brand-new records** (Phase 43-04). Poll, don't assume.
8. **Duration is a cheap tell.** A healthy company recompute is 20 nodes disarmed, 21 armed (the
   extra is `HubSpot Company Update`). 2.4s against a normal 10–37s means the chain died early.

</constraints>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Read first — this phase's mechanism was largely pre-decided
- `.planning/phases/46-rubric-decision-simulation-engine-parity/46-DECISION.md` §§ "Parity red
  window" and **"What Phase 49 owes and what it costs"** — **the load-bearing document.** Names
  the recommended mechanism (D-01), the `HARD_CEILING_RECORDS` gate (D-03), the veto-branch
  caveat (D-02/D-08), and the one unresolved stamped-component edge (D-04)
- `.planning/phases/48-enrichment-coverage/48-HANDOVER.md` § 6 "Open items Phase 48 should know
  about but does not own" — Entain, the Jam TV confirmation, and the D→non-D transition, all
  assigned to Phase 49 by name
- `.planning/phases/48-enrichment-coverage/48-CONTEXT.md` — D-01…D-09, the `<constraints>` table
  this one extends, and `D-48-01` (**EXPIRED** — cited only so nobody re-cites it as live)

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — RESCORE-01/02/03 text; the `lv_icp_scoring_version` **Out of
  Scope** entry that forces wholesale re-scoring; the COVER-01/02 split note
- `.planning/ROADMAP.md` § "Phase 49" — four success criteria, and the "if Phase 46 changed a
  weight" branch determination
- `.planning/PROJECT.md` — the `A:7 B:18 C:17 D:24` entry distribution, the
  `A:7 B:18 C:17+ D:7` **prediction**, the 2,500/month allowance, the disarmed-at-rest premise,
  and the non-technical-operator constraint that decides D-11
- `.planning/STATE.md` — current position and the full decisions log

### The re-score mechanism
- `scripts/backfill_seed_company_scores.py` — `compute_components()`, `build_updates()`,
  `_chunked()`, `enforce_sample_cap()`, `_resolved_max_records()`,
  `HARD_CEILING_RECORDS`/`DEFAULT_MAX_RECORDS`/`BATCH_CHUNK_SIZE`, the two-key arm
  (`DRY_RUN=false` + `ALLOW_SCORE_BACKFILL=true`), and its docstring's own account of why
  writing all five components avoids the re-enrollment assumption
- `src/icp_scoring.py` — the Python oracle; `:82` blank-region → `unknown` (not `non_anz`),
  `:125` the hardware-veto OR predicate
- `config/icp_scoring.yaml` — the rubric of record; `base_score.org_type` is what D-09 pins
- `src/hubspot_client.py` — `batch_update_companies`, `patch_record`, `search_records`,
  `get_record`

### The population, the parity gate, and the simulation
- `scripts/run_scoring_parity.py` — `_select_sample_ids()` (**the** definition of the scored
  population), `build_report()`, `_flag_matches()`, `_classify_mismatch()`, the
  `assertions_executed == 0` false-green guard, and the opt-in `--write-breakdown` path
- `scripts/simulate_rubric_weights.py` — `_select_row_ids()` (mirrors the above by design),
  `build_simulation()`, `render_markdown()`, and the three-column report pattern D-10 follows
- `tests/scoring_fixtures.py` — `fetch_for_parity`, `expected_for`, `FIT_SCORE_PROPS`
- `.planning/phases/46-rubric-decision-simulation-engine-parity/46-SIMULATION-REPORT.md` and
  `46-simulation-20260811.json` — **the report's point 1**, and the 14-row C→B movement forecast
- `.planning/phases/46-rubric-decision-simulation-engine-parity/46-ENGINE-INVENTORY.md` — the
  two-engines-not-three evidence

### Windows, arming, and proof standards
- `.planning/phases/47.5-veto-recompute-path/47.5-RUN-REPORT.md` — the run-report shape D-05's
  accounting should take; the measured recompute cost (executions `11858`–`11861`) that D-08 cites
- `.planning/phases/48-enrichment-coverage/48-RUN-REPORT.md` — § "Cost actuals", § "Window
  accounting"; the estimate-vs-actual table this phase mirrors
- `.planning/phases/48-enrichment-coverage/48-ARM-RECORD.md` and `48-DEPLOY-PROOF.md` — the
  arm/disarm and deploy-proof ceremonies, including the 109-vs-111 node-count baseline
- `scripts/june_run_arm.py` — `--domains`, the record-scoped n8n allowlist arming helper (W2)
- `scripts/deploy_n8n_workflows.py` — the deploy path; `_has_n8n()`, `_base_url()`,
  `_n8n_headers()`, `_get_live_workflows()`
- `scripts/verify_live_write_safety.py` — the disarmed/drain verification pass
- `scripts/remediate_veto_companies.py` — `estimate_cost()` (**estimates must come from code**),
  `post_webhook_event(..., recompute=True)` with its 300s default read timeout,
  `PINNED_COMPANY_ID_ORDER`, and the strict `lv_org_type` enum allowlist at `:142`

### Entain, the veto, and the D-V6 bright line
- `.planning/decisions/2026-08-12-org-type-venue-and-normalization.md` — D-V1…D-V6, the dated
  FACTUAL CORRECTION block, the DEFERRAL block, the 2026-08-13 CLOSURE block, **and
  § "Phase 49 must RE-EXAMINE the three excluded records"** (D-13's mandate). Its
  "Scores in: Phase 49" header line is **moot** per the CLOSURE block
- `.planning/phases/47.5-veto-recompute-path/47.5-B-EVIDENCE.md` — the registry-grade D-V6
  evidence standard D-13 must match; Ironman and Gravity Media discharged
- `.planning/phases/47.5-veto-recompute-path/47.5-C-DECISION.md` — the hardware-veto OR predicate
  and its deploy record
- `docs/OPERATOR-VETO-REFRESH.md` — amended 2026-08-12; the runbook-voice precedent for D-07
- `CLAUDE.md` §13.0 (the recompute lane as-built), §10.3.1 (the hardware OR predicate),
  §15.1 (Sonnet escalation triggers — **overridden by D-14, text left intact**),
  §21.2/§21.3 (high-risk and human-review gates — **§21.3 overridden by D-14**),
  §19.0/§19.1 (as-built cadences; the poller is **not** a veto-refresh path), §4.0 (the
  `lv_`-prefix delta)
- `config/field_policy.yaml` — `lv_produces_content`: `min_confidence: 85`,
  `require_evidence_url: true`, `allow_sonnet_escalation: true` — **the bar D-14 keeps**
- `config/escalation_policy.yaml` — the documented cascade D-14 departs from

### The folded todo
- `.planning/todos/pending/2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md` — the
  full statement, the three blockers that kept it out of 48-07, and the suggested fix
- `scripts/gen_taxonomy_js.py` — `render()`; must learn to emit `ORG_TYPE_DEFINITIONS`
- `src/taxonomy.py` — `ORG_TYPE_DEFINITIONS`, `org_type_definitions_block()`
- `config/taxonomy.yaml` — the `definition:` key on all 9 `org_types` entries (48-07)
- `scripts/build_cloud_workflows.py` — `COMPANIES_TARGET.research_system_prompt_fn_js`,
  `researchSystemPrompt()` (~line 2039). **The only editable source for the lane**
- `tests/test_companies_factory_frozen.py` + `tests/fixtures/companies_jscode_frozen.json` — the
  byte-frozen `jsCode` fixture and its explicit-reviewed-act re-baseline rule
- `tests/test_taxonomy_conformance.py::test_tx10_every_org_type_has_a_definition_and_both_prompts_render_them`
  — the Python-side assertion the new `node --test` one mirrors
- `docs/WEB-RESEARCH-SPEC.md` §2 — the dated TX-10 amendment recording the knowing divergence
- `src/web_research.py` — `RESEARCH_SYSTEM`, `RACING_NSW_ORG_TYPE_SYSTEM`,
  `claude_web_research()`. **D-13's research routes through here, not the n8n lane**

### Known-stale, deliberately not cited as truth
- `docs/SYSTEM-CONTRACT.md` § "Boundary of responsibility" — still says computing scores/tiers/
  vetoes is out of scope; false since Phase 40-05. Needs an operator decision, not a sweep edit
- `CLAUDE.md` §12.7 `compute_icp_score` — the local-MVP prototype, not the live rule; its
  `graduated_deductions["gambling_operator"]` lookup would now `KeyError`
- `CLAUDE.md` §4/§5 property tables — target design, not an inventory (see §4.0)
- `.planning/workstreams/milestone/STATE.md` — v0.5-era, superseded by root `STATE.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/backfill_seed_company_scores.py` (275 lines) — the re-score engine, already
  written.** `compute_components()` reads points through `src/icp_scoring.py`'s loaded config so
  there is no second point table; `build_updates()` and `_chunked()` shape the batch;
  `batch_update_companies()` does one call per 100. Phase 49 changes **two** things: the ceiling
  constant and the cap predicate (D-03). Everything else is reuse.
- **`scripts/run_scoring_parity.py` (465 lines)** — both the population definition and the
  acceptance gate. Its `assertions_executed == 0` false-green guard means an empty or
  credential-less run **fails loudly** instead of looking clean.
- **`scripts/simulate_rubric_weights.py` (520 lines)** — `render_markdown()` and
  `build_simulation()` already produce a per-company three-column before/after report with
  `Counter`-based tier distributions and D-10-style row annotations. The report in D-10/D-12
  should extend this shape rather than invent one.
- **`scripts/remediate_veto_companies.py` (1044 lines)** — `estimate_cost()` for the ex-ante
  figure, `post_webhook_event(..., recompute=True)` for W2's settle, `PINNED_COMPANY_ID_ORDER`
  as the exact-set-gate precedent.
- **`scripts/enrichment_cost_ledger.py` (831 lines)** — `report`/`credits`/`diff`/`estimates`
  subcommands for the cost actuals table.
- **`scripts/enrich_coverage_companies.py` (901 lines)** — Phase 48's driver; the closest
  structural model for a phase driver with a declared window and a run report.
- **`scripts/june_run_arm.py`, `scripts/verify_live_write_safety.py`** — arming and
  disarm-verification helpers.

### Established Patterns
- **Estimate produced by code, not prose** — `47-COST-ESTIMATE.md`'s figures came from a live
  `estimate_cost()` call so doc and function cannot drift. D-07 extends this to the whole runbook.
- **Two engines, one commit** — any predicate carried by both `src/icp_scoring.py` and the
  `Decide Company Action` node built by `scripts/build_cloud_workflows.py` lands in a single
  commit (Phase 46 parity rule; Phase 47.5's `f817ec5` is the worked example).
- **Dated amendment blocks** — the house style for correcting a stale doc or a LOCKED decision,
  rather than rewriting it. D-14's override follows it.
- **Permanent guard tests over prose** — `test_n8n_org_type_absence.py`,
  `test_flow_rubric_conformance.py`, `test_companies_factory_frozen.py`. D-09 adds the fourth.
- **Declare windows up front, disclose any excess** — Phase 47 spent five against a must_have of
  one; 47.5 declared two and spent two; 48 declared one and spent one. D-05 continues it.
- **`nodeAll` try/catch, fail closed** — for any `$()` read of a request-level property in a
  shared code node.

### Integration Points
- The five component properties (`org_type_score`, `geography_score`, `annual_revenue_score`,
  `produces_content_score`, `gambling_score`) are the **only** things W1 writes. They feed
  `lv_icp_fit_score` (a `calculation_equation` property, 5 terms since Phase 40-04), which
  triggers **WF1** (`4625147345`) to grade `lv_icp_tier`, whose veto branch reads
  `lv_anti_icp_flag` as the **string** `"true"`.
- HubSpot flow `4626124224` ("Update Score Based on Org Type") is the *other* writer of
  `org_type_score`, firing on `lv_org_type` change. It already carries the new weights
  (Phase 46 Plan 04, running-content read-back) — which is why the backfill and the flow agree.
- W2's recompute POST enters at the D-18 webhook and routes `Company Gate` →
  `IF Company Recompute` → `Decide Company Action`, bypassing providers/research/judge/merge.
- The folded todo's change lands in `n8n/code/taxonomy.generated.js` (via
  `scripts/gen_taxonomy_js.py`) and in the `jsCode` emitted for the companies research nodes
  (via `scripts/build_cloud_workflows.py`), then into `n8n/wf_enrichment_cloud.json` and
  `n8n/wf_enrichment_local_live.json` by rebuild.

</code_context>

<specifics>
## Specific Ideas

- **The exact-set gate is a strengthening, not a loosening — write the diff so a reviewer sees
  that.** Raising a safety ceiling from 25 to 100 reads like a relaxation in isolation. It is not:
  a count cap of 25 permits *any* 25 records, while the exact-set gate permits *only* the
  live-derived scored population and refuses everything else, including a 24-record subset. The
  commit message and the code comment should both say this, or the next reader will
  reasonably assume the bound was weakened for convenience.

- **The stamped-component edge cannot be resolved by reading anything.** HubSpot's
  `PROPERTY_DEFAULT_VALUE` / default-value-generation stamp is API-inaccessible for reads, and
  `defaultValue` is silently dropped on POST and PATCH (Phase 40-04 probed it three ways). D-04's
  canary is the *only* way to learn the answer, and the answer is worth writing into
  `PORTAL-FACTS.md` whichever way it goes — it is a portal fact nobody in this repo has ever
  established.

- **Entain is the whole reason W2 exists, and it may never open.** Its `lv_produces_content =
  false` was never backed by positive evidence of absence, which the M3 tri-state rule requires;
  meanwhile Ladbrokes and Neds are Entain brands with obvious Australian operations. So the
  research could plausibly clear **both** vetoes — or neither. Plan for both outcomes, and treat
  "W2 never opened" as a successful outcome to report, not a gap.

- **The report's most useful single line may be about the denominator, not the tiers.** 66 of 712
  companies have ever carried a score. Every tier count in this report describes 9% of the
  portal. Say so once, plainly, near the top.

- **Simtech LED `18047161864` is the milestone's best story and belongs in the narrative.** A
  record with *complete* inputs that the gate calls `skip`, zero input change, moved B→D purely
  because a new OR predicate ran on the recompute lane. It is the one outcome no input edit could
  have produced, and it is what "retroactive" means in practice.

</specifics>

<deferred>
## Deferred Ideas

- **`venue` as a 10th `lv_org_type` enum option** — deferred by Phase 48 D-02 and confirmed spent
  by the 2026-08-13 CLOSURE block. Revisit when a record's evidence actually demands it; it needs
  a portal enum-option PATCH with its own arming decision. **The LOCKED file's "Scores in:
  Phase 49" line does not create an obligation here.**
- **Exercising the veto branch of the re-score procedure live** (66 recompute POSTs, ~2.6% of the
  monthly allowance). Documented with measured costs per D-08, not spent — by Phase 47.5's own
  census it would most likely confirm a no-op, since only Simtech LED ever diverged on the
  hardware predicate.
- **`docs/SYSTEM-CONTRACT.md` § "Boundary of responsibility"** — false since Phase 40-05. Needs an
  operator decision, not a sweep edit.
- **Installing the sweep cron/launchd schedule** — carried from v0.8, where the burn-rate alarm
  and the standing parity sweep both shipped **inert**. An admin action on the operator's machine;
  explicitly out of v0.9 scope. Worth noting because it means "the parity sweep will catch it"
  is not currently a live safety net (which is why D-09 is a test, not a reliance on the sweep).
- **The `lv_produces_content` evidence-of-absence audit beyond Entain** — the M3 rule says `false`
  is set only on positive evidence of absence. Entain is being checked because it blocks a named
  carried-forward item; whether any *other* record carries an unevidenced `false` is unexamined.

### Reviewed Todos (not folded)

- **`2026-08-04-enrichment-throughput-ceiling.md`** (score 0.6, major) — 82% of a full enrichment
  run is two sequential Anthropic calls. Real and measured, but this phase's re-score leg spends
  **zero** Anthropic calls, and its remedies are architecture decisions touching the sealed lane.
  Its own phase.
- **`2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md`** (score 0.6, major) — an update
  silently stops the unattended sweep. Unrelated to re-scoring; related to the inert-cron item
  above.
- **`2026-08-04-uat-22-names-aliases-the-mapping-lacks.md`** (score 0.4, major) — CSV header
  aliases in contact upload. Unrelated.

</deferred>

---

*Phase: 49-re-score-strategy-reporting*
*Context gathered: 2026-08-13*
