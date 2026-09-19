# Phase 74: Code-review follow-ups from phase 73 - Context

**Gathered:** 2026-09-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the 16 findings in `73-REVIEW.md` (CR-01..04 blocker, WR-01..12 warning) that were
triaged 2026-09-18 as non-breaking and carried out of Phase 73. Fix order and the shape of
CR-01..04 and WR-01/02/05/06 come from the ROADMAP entry; this context settles what the roadmap
left open. Regenerate every changed cloud JSON once, suites green, then ONE in-phase disarmed
proof send on the contact ingest lane. Nothing is armed at any point. No new capability.

</domain>

<decisions>
## Implementation Decisions

### Create-error lane convergence (CR-01, WR-07)
- **D-74-01:** `Create Carry Merge` input 2 gets a REAL producer: a Code node on `HubSpot
  Create`'s error edge that emits exactly one marker item per run unconditionally (a marker when
  the error branch is empty, the error items when it is not), so the input always receives and
  the merge completes normally instead of via the v1 end-of-run drain. The
  `set_always_output_data(["HubSpot Create"])` mechanism and its comment block are retired —
  n8n pads output 0 only, `[observed live]` on execution `12522` (`HubSpot Create` outs
  `[21, 0]`, input 2 never delivered, association still landed via the drain).
  — **Reversibility:** costly — the producer sits inside the Phase 70 carry-merge idiom; removing
  it means re-splicing the create lane and re-running the walker suite.
- **D-74-02:** `Ingest Merge Response` input 5 (`Build Create Failure Row`) gets a gated
  starved-lane sentinel keyed on "the decided-row set contains zero create-routed rows". That is
  knowable before any write, so it is not a second producer in the dangerous (double-fire)
  sense. No all-update batch is left drain-only.
- **D-74-03:** Walker fidelity: `tests/n8n/lib/walkWorkflow.mjs` pads output index 0 only under
  `alwaysOutputData`; execution `12522`'s runData is frozen (through the CR-04-widened freezer)
  as `tests/n8n/fixtures/frozen/exec_12522.runData.json` and a fidelity test pins the rule
  against it; CLAUDE.md §13.0.3 gains the row (file+symbol `[documented]` plus `12522`
  `[observed live]`). WR-08's JSDoc is corrected in the same edit.

### Error-item shape (CR-02, CR-03)
- **D-74-04:** Classification becomes explicit, not structural: a one-line Code node on the
  error edge (it can be the same node as D-74-01's producer) stamps `_create_error: true`;
  `pairCreateOutcome` tests that flag FIRST, ahead of `_isCarriedRow`. No armed execution is
  spent to observe the real n8n error-item shape — the lane stays `[documented]` per D-73-19
  until a real race occurs.
- **D-74-05:** The single hand-written stub in `tests/n8n/ingestCreateErrorLane.test.mjs` is
  kept and tagged `UNOBSERVED` in the same register `walkWorkflow.mjs` uses for D-70-30 rule
  (c), naming the shape question. Correctness rests on the stamp, not the stub's shape.
- **D-74-06:** `create_outcome` `none` / `refused` are consumed in `BUILD_INGEST_RESPONSE` as
  `action: "create_unconfirmed"`, mapped to `FAILED` in `written_records.ACTION_TO_OUTCOME`
  (never `created_id_unknown`). The operator-facing `reason` passes `create_outcome_reason`
  through verbatim so the two sub-cases stay distinguishable ("no create response joined to this
  row" vs the ambiguity text).

### Fixture redaction guard (CR-04)
- **D-74-07:** `scripts/freeze_execution_rundata.py` replaces ANY `headers`, `error`, `request`,
  `options` or `config` key at any depth with the placeholder, applied per node run so
  `run.error` is covered — the same non-enumerating idiom the tool already argues for. Error
  fixtures lose their message text by design.
- **D-74-08:** The 7 committed runData fixtures that match a naive pattern today (5 Phase-70
  fixtures carrying the superseded `x-enrichment-secret`; `exec_12434` / `exec_12449` carrying
  JWT-shaped strings) are RE-REDACTED IN PLACE by the widened scrubber and the rewritten bytes
  committed. No path exemptions. (The secret was rotated 2026-09-11; the JWTs have a 24h
  lifetime; git history is not rewritten.)
- **D-74-09:** A guard test over `tests/n8n/fixtures/frozen/` refuses VALUE shapes:
  `pat-na\d-…`, `Bearer <token>`, `x-enrichment-secret` followed by a value, and JWT bodies
  `eyJ[A-Za-z0-9_-]{20,}`. The header NAME inside node jsCode (present in the 4 frozen workflow
  bodies) must not trip it.

### Warnings and the end-of-phase gate
- **D-74-10:** WR-03, WR-04, WR-08, WR-09, WR-10, WR-11, WR-12 are ALL fixed in code with a test
  each, using the fixes `73-REVIEW.md` supplies. No accept-with-reason rows this phase.
  WR-01/02/05/06 follow the roadmap's stated shape (lane-invariant `executions = 1` hoisted out
  of the `try`; per-lane `executions_projection_basis` and `providers` taken from the estimate;
  ledger keyed by `(lane, id)` with ambiguous ids skipped; `excluded_marker_count` returned and
  reported when non-zero).
- **D-74-11:** End-of-phase gate is IN-PHASE and disarmed: regenerate, deploy
  `--only wf_contact_ingest_cloud.json`, bounce, send ONE all-update batch (zero creates) and
  read runData: `Create Carry Merge` and `Ingest Merge Response` both complete normally with no
  `merge_fired_with_unfilled_input`; freeze the execution. One execution, nothing armed, every
  `ALLOW_*` flag read back `false`. The other five cloud workflows are not deployed.
  — **Reversibility:** reversible — a disarmed deploy of one workflow; the committed JSON stays
  the source of truth.

### Folded Todos
- `2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md` (MN-01 / NF-MJ-01, `kind:
  question`) — **D-74-12:** answer MN-01 from frozen runData: search `exec_12522` (once frozen),
  `exec_12434` and `exec_12449` for any Merge left with two partially-filled pending runs. If
  found, record the answer in §13.0.3 and close the todo with a dated RESOLVED block; if not,
  keep it open with its trigger and say so in the SUMMARY. Never close it on a `resolves_phase`
  match alone.
- `2026-09-17-stage-d-match-chunk-unchecked-rate.md` (`kind: question`) — **D-74-13:** read the
  recovery bound in `operator-claude-plugin/scripts/chunking.py` against stress attempt 3's
  timings, parametrise or raise it, add a test, and surface `unchecked_count` in the run report.
  No live Stage D run this phase; the todo's trigger ("next Stage D run") stays until one does.

### Claude's Discretion
- Whether D-74-01's producer and D-74-04's stamp are one Code node or two.
- Exact wording of the `UNOBSERVED` tag and of the §13.0.3 rows.
- Plan/wave grouping; the roadmap's fix order (CR-03, CR-02, CR-04, CR-01, then WR) is the
  default unless a shared file makes another order cheaper.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The findings and their prior decisions
- `.planning/phases/73-ga-fix-list-from-stress-attempt-2/73-REVIEW.md` — the 16 findings, each
  with file:line and a concrete fix; the source of truth for scope.
- `.planning/phases/73-ga-fix-list-from-stress-attempt-2/73-CONTEXT.md` — D-73-01 (error
  output, never `continueRegularOutput`), D-73-18 (one deploy), D-73-19 (lane proven offline
  only), D-73-22 (name-only rows).
- `.planning/ROADMAP.md` § Phase 74 — fix order and the roadmap-fixed shapes.

### Engine facts and idioms
- `CLAUDE.md` §13.0.1 (create-error lane as built, `alwaysOutputData` rationale to retire) and
  §13.0.3 (platform-facts table: tagging rule, v1 drain rows, "a node can execute with an item
  no connection delivered").
- `tests/n8n/lib/walkWorkflow.mjs` — the offline engine model; D-70-30 rule (c) register for
  UNOBSERVED tags.
- `.planning/phases/73-ga-fix-list-from-stress-attempt-2/73-UAT.md` — execution `12522` and
  stress attempt 3 (Stage D unchecked rows, timings for D-74-13).

### Folded todos
- `.planning/todos/pending/2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md`
- `.planning/todos/pending/2026-09-17-stage-d-match-chunk-unchecked-rate.md`

### Secret handling
- `scripts/freeze_execution_rundata.py` — the redactor being widened.
- `.planning/phases/73.1-provider-backed-contact-discovery-as-source-tier-2/73.1-SECURITY.md`
  § Unregistered Flags — names the 7 fixtures D-74-08 re-redacts.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_add_starved_lane_sentinel` in `scripts/build_cloud_workflows.py`: the Phase 70 gated
  sentinel; D-74-02 is one more call keyed on a pre-write predicate.
- `_createFailureReason` / `BUILD_CREATE_FAILURE_ROW_JS`: already read only named scalar fields
  off an error item — the model for what a fixture may keep.
- `written_records.ACTION_TO_OUTCOME` (`operator-claude-plugin/scripts/written_records.py:184`):
  `create_failed` entry is the template for `create_unconfirmed`.
- `tests/n8n/walkerEngineFidelityV1.test.mjs` / `v1RuntimeRecordings.test.mjs`: the pattern for
  pinning a walker rule against a frozen execution (D-74-03).
- `scripts/deploy_n8n_workflows.py --only <file>` + `scripts/bounce_n8n_workflows.py`: the scoped
  disarmed deploy used by 73.1; run in-process via dotenv (memory
  `n8n-deploy-permission-blocked`).

### Established Patterns
- Never hand-edit `n8n/wf_*.json`; regenerate and `git diff --quiet n8n/`.
- `[documented]` vs `[observed live]` tagging in §13.0.3; a walker rule cites its execution id.
- Full-suite gate: `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` and
  `node --test tests/n8n/*.test.mjs` (glob form).
- Plugin code changes bump `operator-claude-plugin/.claude-plugin/plugin.json` and add a
  CHANGELOG entry (0.51.2 is current).

### Integration Points
- `scripts/build_cloud_workflows.py` around lines 1956-2007 (create lane splice, `Ingest Merge
  Response` inputs) and 848-905 (`BUILD_INGEST_RESPONSE`).
- `n8n/code/pairCreateOutcome.js` classification block (lines 69-75, 94-143).
- `operator-claude-plugin/scripts/{write_grant,report_enrichment,chunking,csv_dedupe,preview,review_decision}.py`.

</code_context>

<specifics>
## Specific Ideas

- The CR-01 fix is chosen for shape-independence: "a real producer on that input, rather than an
  engine flag believed to synthesise one" (73-REVIEW.md, CR-01 fix option 2).
- The proof send is an ALL-UPDATE batch on purpose — it is the case where every silent producer
  is silent at once.

</specifics>

<deferred>
## Deferred Ideas

- Observing the real n8n error-item shape with an armed duplicate-email create — explicitly not
  this phase (D-74-04); the trigger stays "a real race occurs" (D-73-19).
- Deploying the other cloud workflows — only the ingest lane changes graph shape this phase.

### Reviewed Todos (not folded)
- The 8 other keyword matches (enrichment throughput ceiling, company-domain candidate source,
  property-history hop, `rows_to_resume` fingerprint branch, CSV-only ingest thresholds,
  racing-club `produces_content` veto, suggest-contacts stage-2 script, ZoomInfo enrich-lane
  token cache) — unrelated to the 16 findings; left pending with their own triggers.

</deferred>

---

*Phase: 74-code-review-follow-ups-from-phase-73*
*Context gathered: 2026-09-19*
