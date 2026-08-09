# Phase 44: SJ-3 Dispatch Gate, Drain & Cap - Context

**Gathered:** 2026-08-10
**Status:** Ready for planning

<domain>
## Phase Boundary

SJ-3 — the `lv_enrichment_requested` poller inside "LV Scheduled Maintenance (Cloud)" —
cannot spend the monthly n8n execution allowance on work it is structurally unable to
complete. Three behaviours, one build → deploy → bounce cycle:

1. **Gate** — dispatch only what the write-safety allowlist will actually permit.
2. **Drain** — clear the trigger flag on what it declined, so the queue cannot re-form.
3. **Cap** — bound how many records one tick may dispatch, derived from the plan allowance.

Requirements: GATE-01/02/03, DRAIN-01/02/03, CAP-01/02/03.

**Not in this phase:** the burn-rate alarm (Phase 45), installing any cron, bounding the
webhook or operator-initiated dispatch paths, and any change to the write-safety invariant
itself beyond the one new authority named in D-05.

</domain>

<decisions>
## Implementation Decisions

### Gate granularity

- **D-01:** The gate filters **per record**, not all-or-nothing. A tick dispatches exactly
  the records `_writeSafetyAllows` permits and skips the rest; its cost is
  `1 + permitted_count`. All-or-nothing was rejected on evidence: every real armed window
  scopes `TEST_RECORD_IDS` to one batch (`scheduled_arm.py`), so an all-or-nothing check
  would make legitimately armed windows dispatch **nothing**.

- **D-02:** The check **reuses `WRITE_SAFETY_GATE_JS` verbatim** in a new SJ-3 Code node —
  the same embedding pattern `ENRICH_DECIDE_CLOUD` and every spliced write gate already
  use. One definition of "permitted", so the poller and the enrichment lane cannot drift
  apart. A second, narrower predicate was rejected for exactly that drift risk.

- **D-03:** The downstream per-record refusal inside the enrichment lane **stays**. The
  webhook and operator-initiated paths reach enrichment without passing SJ-3 at all, so
  removing it would open a hole this phase's fix does not cover. Defence in depth is
  deliberate, not redundant.

- **D-04:** A record that **was** dispatched and whose run then fails **stays flagged**.
  That is retryable work, not stuck-queue debris. The drain touches only records the gate
  **declined** — never a record that got its chance and failed. Existing failed-run
  handling is unchanged by this phase.

### Drain authority

- **D-05:** The drain gets a **new write authority of its own, defaulting `true`** —
  unreachable from `ALLOW_HUBSPOT_RECORD_WRITES` and `ALLOW_HUBSPOT_REVIEW_WRITES` in
  either direction, following the precedent those two already set for each other.
  — **Reversibility:** costly — this is the **first write in the system that is enabled at
  rest**, and `WRITE_SAFETY_DEFAULTS` is load-bearing across `build_cloud_workflows.py`'s
  `ENABLE_BAKED_FLAGS` overlay, the plugin's arm/verify/disarm cycle, and
  `scripts/verify_live_write_safety.py`. A prior spike that flipped an existing flag broke
  64 tests across two packages and was reverted (WINDOWS.md #2). Undoing this means
  re-deploying workflow content and re-baking every write-safety assertion that learns
  about the new constant.
  **Rationale that must be written into the code, not just here:** it may only ever set
  `lv_enrichment_requested` to `"false"` — it removes queued work, it cannot create or
  alter data. This is not precedent for defaulting any other write on. A `false`-defaulting
  drain was explicitly considered and rejected: it would run only inside an armed window,
  which is precisely when the queue is not stuck, leaving the runaway free to re-form
  every time the system rests disarmed.

- **D-06:** The drain does **not** consult the `TEST_RECORD_*` allowlist. The allowlist
  scopes *data* writes to test records; the stuck queue is overwhelmingly non-allowlisted
  records — that is the failure mode itself — so an allowlisted drain would clear only the
  records that were never stuck.

- **D-07:** Blast radius is bounded **structurally**: the drain may write only
  `lv_enrichment_requested`, only the literal `"false"`, only to record ids the gate
  declined **in the same tick**, and it stamps provenance. A test asserts the emitted patch
  has exactly one key.

- **D-08:** Drain provenance reuses the existing **`lv_enrichment_status`** property rather
  than adding a new one. It is already in SJ-3's own search filter (`NEQ "running"`) and
  already part of the control-property model, so it is readable by the same searches and
  needs no property migration — this phase otherwise ships no schema change. A drained
  record is therefore distinguishable from an enriched one and from a hand-cleared one
  (DRAIN-03).

### Cap policy + overflow

- **D-09:** A record that passes the gate but exceeds the tick's cap **stays flagged** and
  is picked up by the next tick. Overflow is *deferred* work, not *declined* work — the
  drain must never touch it. Draining overflow was rejected as exactly the silent
  truncation CAP-02 forbids.

- **D-10:** The cap is derived as `allowance × cadence × share`, with **share configurable,
  defaulting to ~50%** (~1,250 dispatches/month → ~40/tick at daily cadence). The remaining
  headroom is reserved for webhook and operator-initiated enrichment, which do not pass
  SJ-3 and are therefore not covered by the cap.

- **D-11:** The plan allowance lives in **`config/` YAML**, alongside the existing config
  files the builder already reads. One source, read by both the builder (to derive the cap)
  and the CAP-03 test — and by Phase 45's alarm for ALARM-03, so there is one allowance
  rather than two that drift. Env var was rejected (`.env` is permission-blocked to tooling
  here, and a committed test cannot read it); a builder constant was rejected because
  Phase 45 would then import from a build script or duplicate the number.

- **D-12:** **Known limit, accepted and stated:** the cap bounds the SJ-3 lane only.
  Webhook and operator-initiated dispatch bypass it entirely. That is acceptable for this
  phase — SJ-3 is the unattended path, the one that ran away, and operator-initiated
  dispatch is human-triggered behind the plugin's existing cost guard. Extending the cap to
  every path would touch the enrichment lane and the plugin, beyond this phase's boundary.

### Gate-closed visibility

- **D-13:** The gate-closed outcome is observable in **two places**: a structured outcome in
  the tick's execution data (found N, permitted M, declined N−M, capped K), and the drained
  records' `lv_enrichment_status`. Execution data alone was rejected — n8n prunes at 2,500
  rows (~10 hours at real rates), so that evidence evaporates; the HubSpot side survives.

- **D-14:** A gate-closed tick is **quiet and recorded, not loud**. Disarmed is the normal
  resting state, so a tick declining 61 records while disarmed is correct behaviour, not an
  incident — alarming on it would train the operator to ignore alarms. Phase 45's burn-rate
  alarm is the thing that should be loud.

### Claude's Discretion

None — every question in this discussion was answered with an explicit choice. The exact
`lv_enrichment_status` value written by the drain, the precise cap-rounding rule, and the
shape of the structured outcome object are left to planning within the decisions above.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` — Phase 44 goal and its 5 success criteria
- `.planning/REQUIREMENTS.md` — GATE-01/02/03, DRAIN-01/02/03, CAP-01/02/03 verbatim
- `.planning/PROJECT.md` — v0.8 milestone context and the measured runaway numbers

### The code this phase changes
- `scripts/build_cloud_workflows.py` — **the only way n8n JSON is produced; never hand-edit
  `n8n/*.json`.** Key sites: `WRITE_SAFETY_DEFAULTS` (~line 908), `WRITE_SAFETY_GATE_JS` +
  `_writeSafetyAllows` (~line 926), `_write_gate_js` / `splice_write_gates` (~line 5747),
  `_schedule_trigger` (~line 5530, carries the per-interval monthly cost arithmetic),
  `build_scheduled_maintenance_cloud` SJ-3 cluster (~line 5809: trigger → search →
  `SJ-3 Extract Rows` → `SJ-3 Build Dispatch Event` → `SJ-3 Dispatch To Enrichment`),
  `_hs_update_set_property` as used by `SJ-1 Set Requested` (~line 5862) — the existing
  precedent for a maintenance-lane HubSpot write
- `scripts/verify_live_write_safety.py` — the live disarmed-state verifier; it enumerates
  every declaring node and must learn about any new write-safety constant
- `scripts/deploy_n8n_workflows.py` — two-key gated deploy (`DRY_RUN=false` **and**
  `ALLOW_N8N_DEPLOY=true`)

### Prior decisions that constrain this phase
- `.planning/WINDOWS.md` #2 — why `WRITE_SAFETY_DEFAULTS` is not a simple flag flip: a spike
  that flipped it broke 64 tests across two packages and was reverted. Read before touching
  D-05.
- `.planning/milestones/v0.7-phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md` —
  live portal facts, including the calculated-property and flow-enrollment gotchas
- `operator-claude-plugin/scripts/scheduled_arm.py` — the arm/dispatch/disarm companion that
  scopes `TEST_RECORD_IDS` to one batch; the reason D-01 is per-record
- `CLAUDE.md` §21 — the safety-gate pattern (exact-string `true`, gate is the caller's job)

### Tests that must stay green
- `.venv/bin/python -m pytest -q` — 2427 passing
- `node --test tests/n8n/*.test.mjs` — 636 passing (glob form; dir form fails on node ≥21)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`WRITE_SAFETY_GATE_JS` / `_writeSafetyAllows(action, hsObjectId, domain)`** — the exact
  predicate D-01/D-02 need, already embedded verbatim into multiple Code nodes. Note it is
  a *filter*, not a boolean: it requires `ALLOW_HUBSPOT_RECORD_WRITES=true` **and** the
  record on `TEST_RECORD_IDS` / `TEST_RECORD_DOMAINS`, with an empty allowlist denying all.
- **`splice_write_gates(nodes, conns, gated)`** — inserts a gate Code node in front of a
  named write node and re-points every inbound connection. The drain write can be gated
  through this machinery if planning wants the same shape.
- **`_hs_update_set_property(name, "company", x, y, prop, value)`** — exactly the
  single-property write the drain needs; `SJ-1 Set Requested` is the working precedent in
  the same workflow.
- **`ENRICH_EXTRACT_SEARCH_ROWS`** — the shared search-row extractor SJ-1/SJ-2/SJ-3 all use;
  the gate node slots in after it.

### Established Patterns
- **Builder-only n8n changes.** `n8n/*.json` is generated output. Every change goes through
  `build_cloud_workflows.py`, then deploy, then a **deactivate → activate bounce** — a bare
  PUT does not reload a running workflow (proven live 2026-08-03).
- **A content deploy rebakes write-safety to disarmed.** Never deploy while a write window
  is open.
- **Write authorities are deliberately non-transitive.** `ALLOW_HUBSPOT_REVIEW_WRITES` and
  `ALLOW_HUBSPOT_RECORD_WRITES` each grant nothing on the other's path. D-05's new authority
  must follow that shape.
- **Exact-string `true` for every gate** (CLAUDE.md §21).

### Integration Points
- New gate Code node between `SJ-3 Extract Rows` and `SJ-3 Build Dispatch Event`.
- New drain write node (plus its provenance stamp) on the declined branch — the first
  HubSpot write ever added to the SJ-3 lane.
- New `config/` YAML key for the plan allowance, consumed by the builder, the CAP-03 test,
  and later by Phase 45's ALARM-03.
- `scripts/verify_live_write_safety.py` must recognise the new authority so its disarmed
  verdict stays meaningful.

</code_context>

<specifics>
## Specific Ideas

- The measured failure this phase prevents: **253 executions/hour, flat, for at least 10
  hours** — 61 records × 4 ticks/hour, against a 2,500/month allowance. Reproduced from the
  live execution log on 2026-08-09/10, not inferred.
- The drain's justification sentence should live in the code as a comment, in the same
  register as the existing write-safety commentary: it may only remove queued work, never
  create or alter data — and it is not precedent for defaulting other writes on.
- A capped tick must log **found vs dispatched**, in the spirit of the repo's existing
  "no silent caps" rule (`backfill_seed_company_scores.py`'s 25-record typo-guard logs what
  it dropped).

</specifics>

<deferred>
## Deferred Ideas

- **Bounding webhook / operator-initiated dispatch** — D-12 accepts SJ-3-only scope for this
  phase. A cap covering every dispatch path touches the enrichment lane and the plugin.
- **Surfacing the gate-closed outcome through `backend-status`** — reaches the
  non-technical operator in Claude, but edits the plugin package, which is Phase 45's
  territory.
- **Warning above a declined-count threshold** — rejected for this phase (D-14) as
  overlapping Phase 45's alarm and risking routine noise from the normal disarmed state.

### Reviewed Todos (not folded)
- *Sweep re-notifies a fixed failure until 100 executions displace it* — already tagged
  `resolves_phase: 45`; it is the sweep's lookback window, not SJ-3's.
- *Enrichment throughput — 82% of every full run is two sequential Anthropic calls* —
  matched on generic keywords only; per-run latency, not execution count.
- *The sweep's crontab entry pins a versioned plugin path* — cron installation is explicitly
  out of scope for this milestone.

</deferred>

---

*Phase: 44-SJ-3 Dispatch Gate, Drain & Cap*
*Context gathered: 2026-08-10*
