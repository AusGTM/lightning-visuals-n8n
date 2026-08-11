# Phase 47: Veto Remediation - Context

**Gathered:** 2026-08-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Clear the false non-ANZ veto on 17 companies **and** enrich the scoring inputs those same
records are missing, in a **single deliberately-armed write window**, so each record is touched
once rather than twice. Verifiable from HubSpot alone with no script.

**Scope widened three times during discussion, deliberately** (D-01, D-05, D-11). ROADMAP.md
scoped this phase to clearing 17 vetoes. Scouting established that **all 17 false-veto records
are also blank-`lv_org_type` records** — a strict subset of Phase 48's 18-company set, not a
partial overlap. ROADMAP.md's own instruction ("check whether any of the 17 also fall inside
Phase 48's set; an overlapping record should get both fixes in one armed touch") therefore
applies to *every* record in this phase. The operator confirmed the widened boundary explicitly.

Phase 47 now delivers, for the 17: `lv_org_type`, `lv_produces_content` and
`lv_country_region_normalized` enrichment; the veto clear; and a single settled recompute.

**Excluded by construction** — the 3 companies verified correct on 2026-08-11, which carry
genuine non-ANZ regions and must not be swept up: Entain (`10024564084`), Gravity Media
(`15860277364`), Ironman (`17317184159`). The pinned-ID list (D-09) excludes them structurally,
not by filter.

**Not in this phase:** the 1 remaining blank-`lv_org_type` record outside the 17 (Phase 48);
the full-population re-score (Phase 49); any rubric weight change (settled in Phase 46).

</domain>

<decisions>
## Implementation Decisions

### Phase boundary and requirement mapping

- **D-01:** **Phases 47 and 48 merge for the 17 overlapping records.** Phase 47 enriches
  `lv_org_type` AND clears the veto in one armed window; Phase 48 shrinks to the 1
  non-overlapping record plus any coverage work not about these rows. Rationale: two separate
  windows would touch the same 17 records twice — the exact "re-score twice" cost Phase 46 was
  built to avoid, reappearing one phase later.
  — **Reversibility:** costly — undo means re-opening a second write window against records
  already touched, and re-amending ROADMAP.md and REQUIREMENTS.md in both phases.

- **D-02:** **COVER-01 and COVER-02 map to BOTH Phase 47 and Phase 48.** Phase 47 satisfies them
  for its 17; Phase 48 for the remainder. Neither phase may close claiming full coverage alone.
  Follows Phase 46's precedent of broadening existing requirement wording rather than minting
  new IDs, preserving traceability.

- **D-03:** **COVER-02's cost discipline applies in Phase 47**: estimate the execution and
  provider cost before the run, report actuals after, and **refuse rather than truncate** a run
  that would exceed the 2,500/month n8n allowance or the Lusha balance.

- **D-04:** **Order within the single touch: enrich first, then one recompute.** Populate
  `lv_org_type` / `lv_produces_content` / region, then trigger a single recompute so the veto
  clears and the record lands on its tier in one settle. Avoids two derived-field cycles.

- **D-05:** **Enrichment widened to all scoring inputs**, not `lv_org_type` alone. A club only
  reaches a real tier if it also carries content output and a region; enriching org type alone
  leaves records at `Unscored`. Operator confirmed the widening explicitly after it was flagged
  as the third scope increase in the discussion.
  — **Reversibility:** reversible — narrowing back to org-type-only is a scope edit, not a
  data migration; the extra properties would simply go unwritten.

### Recompute mechanism

- **D-06:** **Direct batch PATCH, reusing `scripts/backfill_seed_company_scores.py`'s
  `compute_components()` + `batch_update_companies()` path.** Costs ~0 n8n executions against the
  2,500/month allowance. 17 records fit inside its existing `HARD_CEILING_RECORDS = 25` in one
  chunk. Rejected: flipping `lv_enrichment_requested` and waiting for the SJ-3 poller — that
  trigger is **daily** (up to 24h latency) and fans out per record against the n8n allowance.

- **D-07:** **`lv_anti_icp_flag` / `lv_anti_icp_reason` are never written directly.**
  `scripts/backfill_seed_company_scores.py:19-20` states this explicitly and a **T-40-22 offline
  guard asserts it**: those fields, plus `lv_icp_fit_score` and `lv_icp_tier`, are derived by the
  HubSpot calculated property, WF1, and the n8n flow. "Clearing the veto" means changing inputs
  and letting the derived chain settle. Any plan that patches these fields directly violates a
  standing guard.

- **D-08:** **`lv_org_type` (and the other inputs) come from Claude web research**, not the
  provider waterfall. No provider credits, no Lusha balance drawn down; Anthropic cost only
  (~$0.0686/record measured in the Phase 20 canary). Providers classify org type poorly compared
  to a website read. **Rejected outright: setting the values manually as "they are all clubs"** —
  see D-13, that premise is false and would have written wrong data.

- **D-09:** **Full source metadata stamped on all 17**, despite `config/field_policy.yaml` only
  compelling an evidence URL for `governing_body_league` / `content_producer` /
  `hardware_vendor` / `gambling_operator`. Write `lv_org_type_source`, `_confidence`,
  `_evidence_url`, `_evidence_summary`, `_verified_at`, `_verified_by_model`,
  `_validation_status`. Note per D-13 that this set **will** produce policy-compelled values, so
  evidence is mandatory for several of the 17 regardless of this decision.

- **D-10:** **Settle proven per record, not assumed.** Reuse the existing
  `_settle(id, "lv_icp_tier")` helper (`scripts/backfill_seed_company_scores.py:247`): after the
  PATCH, poll each record until the derived fields reflect the new inputs, and **fail loudly** on
  any record that never settles. A fixed-interval single sweep was rejected — a slow-settling
  record would read as a failure when it was only late.

### Write-window shape (VETO-02)

- **D-11:** **The batch-PATCH script itself carries the operator-only arming gate**, not n8n.
  `scripts/june_run_arm.py` arms the n8n workflow, but the chosen write path is a direct CRM
  batch PATCH that bypasses n8n entirely — arming n8n would satisfy VETO-02's letter while arming
  a surface the write never touches. Follow the established `ALLOW_N8N_ARM` /
  `ALLOW_HUBSPOT_FLOW_WRITE` pattern: operator-only, per-shell, never set by Claude, and **disarm
  must not be gated on the arm variable** so an operator can always shut the window
  (`june_run_arm.py:20`).
  — **Reversibility:** costly — this is a new safety gate other phases will inherit and depend on;
  changing its shape later means re-auditing every caller.

- **D-12:** **Volume capped by the existing `HARD_CEILING_RECORDS = 25`; identity capped
  separately by an explicit pinned `--ids` list of the 17.** The cap bounds how much can be
  written; the pinned list bounds *which* records — the script refuses any ID not on the list.
  This is what structurally excludes Entain / Gravity Media / Ironman. The cap alone was
  rejected as insufficient: 25 would not catch the row set drifting up to 25.

- **D-13:** **Mandatory disarmed dry-run printing the exact PATCH payloads** before arming,
  matching the repo's `DRY_RUN=true` default and the dry-run PATCH-payload pattern used since the
  local MVP. Disarm and read back the disarmed state afterward, per VETO-02.

### Data-honesty rules

- **D-14:** **Never write `lv_produces_content = false` on absent evidence.** `false` is a
  **hard veto** — it sets `lv_anti_icp_flag` and forces Tier D. `config/field_policy.yaml`
  requires an evidence URL for this field and the web-research contract says "prefer unknown over
  guessing". Writing `false` because research found nothing converts a data gap into a hard veto,
  manufacturing exactly the false-veto class this phase exists to clear. Leave unknown; record
  per-record why it could not be established, so COVER-01's bar is met (an unresolved company
  must be distinguishable from one never attempted).

- **D-15:** **`lv_anti_icp_flag` goes false and `lv_anti_icp_reason` empties** for a cleared
  record — regardless of whether it reaches a real tier. This is what makes VETO-03's HubSpot
  search return zero. Subject to D-07: these are derived, so the plan changes inputs and verifies
  the derived result, it does not write these fields.

- **D-16:** **Some of the 17 will legitimately remain Tier D after remediation.** Clearing a
  *false* non-ANZ veto may reveal a *genuine* veto underneath (see D-17 — at least one record is
  likely a hardware vendor, which is a hard veto). That is a correct outcome, not a failure, and
  the phase's success criteria must not assume every cleared record becomes targetable.

### The row set is not what it looked like

- **D-17:** **The 17 are NOT all racing clubs.** Enumerated from
  `46-SIMULATION-REPORT.md`, the set includes at least five records that are plainly not clubs:
  **Simtech LED** (`18047161864`) — almost certainly `hardware_vendor`, a **hard veto**;
  **Jam TV** (`17317850381`) and **Editix** (`17317381378`) — broadcaster / content producer;
  **The Rumble / Pacific Action Sports** (`20943964946`) — content producer; plus venue-shaped
  records (**Thoroughbred Park** `10152138518`, **Wyong** `10215097384`, **Pinjarra Park**
  `17696004613`) whose classification is not obvious from the name.

  Three consequences the planner must carry:
  1. Any "they are all clubs, set it manually" shortcut writes **wrong data** — including
     scoring a likely LED hardware vendor as a club at +15. This is why D-08 chose research.
  2. `hardware_vendor`, `content_producer` and `broadcaster` **all require an evidence URL**
     under `config/field_policy.yaml`. Evidence is policy-compelled for part of this set, not
     merely good practice.
  3. **Waikato Racing Club Inc** (`20538284384`) is **NZ**, not AU. Inside ANZ so no veto, but it
     proves the region field must be genuinely researched rather than defaulted to `AU`.

### Claude's Discretion

- The exact chunking within the 17 (one chunk of 17 is permitted by the cap; smaller is allowed).
- The dry-run output format, beyond the requirement that it print the exact PATCH payloads.
- Whether the per-record "could not establish" note lives in a property, the run report, or both.
- The polling interval and timeout for `_settle`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The record set and what Phase 46 established
- `.planning/phases/46-rubric-decision-simulation-engine-parity/46-SIMULATION-REPORT.md` — the
  live 66-row table carrying the `false_veto` / `blank_org_type` flags. **The 17 pinned IDs are
  enumerated from here** (rows flagged `blank_org_type, false_veto`). Also the before/after
  scores these records will move from.
- `.planning/phases/46-rubric-decision-simulation-engine-parity/46-DECISION.md` — the settled
  rubric this re-score runs against, and the parity red-window section explaining why the
  standing sweep is red during this phase.
- `.planning/phases/46-rubric-decision-simulation-engine-parity/46-ENGINE-INVENTORY.md` — two
  scoring engines, not three; what is and is not a scoring surface.

### The write path
- `scripts/backfill_seed_company_scores.py` — **the pattern to reuse**. `compute_components()`
  (line ~93), `batch_update_companies()` (line ~237), `HARD_CEILING_RECORDS = 25` (line 85),
  `_settle()` (line ~247). Lines 19-20 and 70 state which fields it must never write (D-07).
- `scripts/june_run_arm.py` — the arming ceremony to mirror: operator-only per-shell env gate,
  `--ids` list, and disarm deliberately ungated (lines 12, 20, 25-27).
- `src/hubspot_client.py` — `batch_update_companies`, `search_records`, `get_record`.

### Policy and scoring rules
- `config/field_policy.yaml` — `lv_produces_content` requires an evidence URL (D-14);
  `lv_org_type` requires one for `governing_body_league` / `content_producer` /
  `hardware_vendor` / `gambling_operator` (D-17 consequence 2).
- `config/icp_scoring.yaml` — the rubric of record, post-Phase-46. Hard vetoes: non-ANZ, no
  content, hardware vendor.
- `src/icp_scoring.py` — `compute_icp_score`, including the `cfg=None` override added in
  Phase 46.
- `docs/WEB-RESEARCH-SPEC.md` — the web-research contract; "prefer unknown over guessing" and
  the evidence-URL obligations underpinning D-14.
- `src/web_research.py` — the existing Claude web-research adapter (native `web_search` tool,
  `USE_MOCK_WEB_RESEARCH` switch, `REQUIRED_FIELDS`).

### Milestone framing
- `.planning/REQUIREMENTS.md` — VETO-01/02/03, COVER-01/02 (the latter now mapping to this phase
  too, per D-02), and the no-new-properties constraint.
- `.planning/ROADMAP.md` §Phase 47 — success criteria, the 3 excluded IDs, and the overlap
  instruction this discussion acted on.

### Operational gotchas
- `.planning/milestones/v0.7-phases/**/PORTAL-FACTS.md` — HubSpot API constraints discovered
  live. **Read, never edit.**
- `CLAUDE.md` §4.0 — the `lv_`-prefix delta; §19.1 — the enrichment trigger contract
  (`lv_enrichment_requested = true` AND `lv_enrichment_status != running`) and the daily SJ-3
  cadence that D-06 rejected.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/backfill_seed_company_scores.py`** — near-exactly the write this phase needs:
  computes components in Python, batch-PATCHes via the CRM API, caps records, and polls for
  settle. Extend or mirror rather than build fresh.
- **`scripts/june_run_arm.py`** — the arming/disarming ceremony, including the correct
  asymmetry (arm gated, disarm ungated).
- **`src/web_research.py`** — the Claude web-research adapter already returns the
  `ProviderResult` shape with `evidence_urls` and `evidence_summary`, which is exactly what D-09
  needs to stamp.
- **Phase 46's `scripts/simulate_rubric_weights.py`** — read-only scoring of a live record under
  a given config. Useful for predicting what each of the 17 will land on *before* arming.

### Established Patterns
- **Derived fields are never written directly** — inputs change, the calculated property + WF1 +
  n8n derive the rest, and a guard asserts it (D-07).
- **Dry-run first, then arm, then disarm and read back** — the repo's standing write ceremony.
- **Pin identity as well as volume** — a cap bounds damage, an explicit ID list bounds blast
  target.
- **Rule 1 fallout is expected** — Phases 40, 43 and 46 each found stale test assertions when
  scoring behaviour changed. Budget for fixture updates.

### Integration Points
- Component score properties → HubSpot calculated property `lv_icp_fit_score` → WF1 → the n8n
  flow → `lv_icp_tier` / `lv_anti_icp_flag` / `lv_anti_icp_reason`. This chain is what the phase
  drives; it does not write its endpoints.
- The standing `scripts/run_scoring_parity.py` sweep samples real companies and is **red by
  design** from Phase 46's commit `caae5d6` until Phase 49 re-scores. Expect it to fire during
  this phase; it is not a new defect.

</code_context>

<specifics>
## Specific Ideas

- The operator's framing throughout: touch a record **once**, not twice. That principle drove
  the Phase 46 rubric-first sequencing and it drove the 47/48 merge here.
- VETO-03's bar is deliberately script-free: a RevOps person must be able to run one HubSpot
  search — non-ANZ veto reason with blank `lv_country_region_normalized` — and see zero results.
  Whatever the implementation does, that search is the acceptance test.
- The phase should predict, before arming, what each of the 17 will land on. Phase 46 built the
  tooling to do exactly that read-only; use it rather than discovering the outcome after a write.

</specifics>

<deferred>
## Deferred Ideas

- **The 1 remaining blank-`lv_org_type` record** outside the 17 — Phase 48.
- **Full-population re-score** — Phase 49 (RESCORE-01/02/03), which also closes the parity red
  window.
- **A `lv_icp_scoring_version` property** — would make rubric-version segmentation possible and
  avoid whole-population re-scores. Rejected under the standing no-new-properties constraint;
  noted again here because this is the second phase to pay its cost.
- **A needs-review queue for un-enrichable records** — raised as an option for D-14's
  evidence-less case and not taken; the phase records the reason on the record instead. If a
  review queue is ever built, these records are its first population.

### Reviewed Todos (not folded)
Three pending todos keyword-matched Phase 47 via `todo.match-phase`; none is in scope for a
record-write phase, and all three matched on generic keywords ("operator", "two", "phase")
rather than substance. Identical to the Phase 46 outcome:
- **Sweep crontab pins a versioned plugin path** (score 0.60, `operator-claude-plugin`) — admin
  and install concern, unrelated to record writes.
- **UAT 2.2 names two header aliases the column mapping does not support** (score 0.60) — contact
  ingestion, not company scoring.
- **Enrichment throughput — 82% of every full run is two sequential Anthropic calls** (score
  0.40, `n8n`) — runtime-cost concern for the n8n enrichment path, which D-06 explicitly does not
  use.

</deferred>

---

*Phase: 47-veto-remediation*
*Context gathered: 2026-08-11*
