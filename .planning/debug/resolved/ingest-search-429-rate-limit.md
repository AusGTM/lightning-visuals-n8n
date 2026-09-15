---
status: resolved
trigger: "F-A3/F-A4"
created: 2026-09-15T05:40:00Z
updated: 2026-09-15T06:40:00Z
resolved_by: "Phase 73 Plan 02, D-73-15"
resolved_at: 2026-09-15
---

## Closing note (Phase 73 Plan 02, D-73-15)

F-A3r — the residual 429 this file's F-A3 fix left at 250ms (1 hit on a 48-row send,
`tests/stress-tests/SESSION-2026-09-15.md` F-A3r row; the account-wide search cap is shared
with the scheduled jobs, so 4 req/s left no headroom — is resolved by widening
`_INGEST_SEARCH_BATCH_INTERVAL_MS` from 250 to **400ms** (2.5 req/s, 50% headroom under
HubSpot's 5 req/s cap; a 48-row send now takes ≈58s across the three search nodes).
`retryOnFail` was again rejected, per this file's own original constraint. Pinned by
`tests/n8n/ingestSearchThrottle.test.mjs`, the first test in this repo asserting a batching
interval — it derives the throttled node set from `n8n/wf_contact_ingest_cloud.json`
structurally, not from a hard-coded node-name list, so a future unthrottled fourth search
node fails it automatically. Archived here per this file's own "Archive it when D-73-15
lands" instruction (73-CONTEXT.md).

## Current Focus
<!-- OVERWRITE on each update - always reflects NOW -->

hypothesis: CONFIRMED. See Resolution.
test: done — see Resolution.verification
expecting: n/a — resolved offline; live re-run of the 48-row CSV is the operator's deploy+bounce step
next_action: awaiting operator deploy+bounce (disarmed) + a live re-run of the 48-row CSV to confirm the fix end to end; this session cannot deploy/bounce/arm anything (constraint)
bug_class: bohrbug
reasoning_checkpoint:
  hypothesis: "The contact ingest lane's three per-row HubSpot search HTTP nodes fire one request per item in a burst with no throttling; at 48 items this exceeds HubSpot's documented account-wide 5 req/s CRM Search cap, causing 429s that set the batch-wide `lookup_failed` flag, which in turn makes `Decide Action`'s reason string for a legitimately-net_new-shaped row (\"valid email, no existing match\") indistinguishable from a row whose search never actually ran."
  confirming_evidence:
    - "Execution 12429 runData: 33/48, 38/48, 42/48 items 429'd on the three search nodes, all `NodeApiError` 'You have reached your secondly limit.'"
    - "Builder inspection: `_http_node`/`_live_http` emitted `options: {timeout: 20000}` only — no `options.batching`, no retry — on all three search nodes, confirmed by reading the generated JSON before the fix"
    - "HubSpot's own changelog (developers.hubspot.com/changelog/crm-search-api-rate-limit-increase): CRM Search is capped at 5 req/s, account-wide — 48 requests in one burst on three separate nodes vastly exceeds this"
    - "Code trace: DECIDE_CLOUD's `reason: company_hold || id.reason || row.reject_reason` reads `id.reason` verbatim from `resolveIdentity`, which returns \"valid email, no existing match\" for a valid email with 0 search hits — indistinguishable from 0 hits because the search never ran"
  falsification_test: "If the three search nodes already throttled requests below 5 req/s, or if `Decide Action`'s reason already named lookup_failed distinctly, the hypothesis would be false. Confirmed false only for those two claims by direct inspection of the pre-fix generated JSON and jsCode."
  fix_rationale: "F-A3: throttle the three per-row search nodes via n8n's native `options.batching.batch.{batchSize,batchInterval}` (1 item / 250ms = 4 req/s, 20% headroom under the 5 req/s cap) — the mechanism the constraints named as a candidate, confirmed sufficient because the three nodes are wired sequentially (node-by-node) in the generated topology, not concurrently, so their intervals never overlap. Wall-time cost is 48 x 0.25 x 3 ~= 36s, and — CORRECTED after re-verifying the constraint's own ack-timing claim against this workflow's live `executionOrder: v1` and n8n's documented v1 branch-ordering rule (topmost-canvas-position-first, to completion) — this 36s lands BEFORE \"Build Ingest Ack\"/\"Respond to Webhook\" fires (the main pipeline branch is topmost of Set Config's three fan-out targets), so it counts against the ~100s Cloudflare webhook ceiling rather than being free post-ack time as originally assumed. Still safe at 48 rows. F-A4: override ONLY the `net_new` outcome (resolveIdentity's SOLE net_new return carries reason \"valid email, no existing match\" — matched on `id.outcome` rather than that literal string so a future reword of the text can't silently disable the override) — a real match/multi-match reason reflects a genuine positive hit a 429 cannot invent, and an emailless row's reason never touches this search at all, so both must and do survive unchanged (now proven directly, including a multi-match ambiguous control)."
  blind_spots: "Live proof is out of scope for this session (deploy/bounce/arm forbidden) — the throttled interval's real-world sufficiency against concurrent scheduled-job search traffic on the same HubSpot account is unverified; company-search failures unrelated to email search (companyLink.js's `searchResults()` swallowing an errored response as `[]` with no lookup_failed-equivalent flag) are a separate, pre-existing gap this fix does not touch (out of F-A4's scope per the debug file's own evidence, which ties the reported reason string specifically to the email-search path); a batch meaningfully larger than 48 rows has not been checked against the corrected pre-ack wall-time budget (36s at 48 rows leaves headroom, but the lane's OTHER per-row work — email verification batch, the matched-row Contact History hop — also runs inside the same topmost branch and was not measured here)."
  candidate_causes:
    - "code: no throttling on the per-row HTTP nodes (builder, `_http_node`/call sites)"
    - "environment: HubSpot's account-wide 5 req/s CRM Search rate limit, shared across all traffic on the HubID — a constraint neither the builder nor this fix controls, only respects"
  and_gate: "no — the burst-vs-limit mismatch alone fully explains the 429s (no second contributing condition needed: no auth issue, no malformed body, no concurrent-workflow confound observed in the runData); the reason-string issue (F-A4) is a separate, single-cause defect in the same jsCode, not an AND with F-A3."
tdd_checkpoint: null

## Symptoms
<!-- Written during gathering, then immutable -->

expected: A 48-row contact-upload batch (tests/stress-tests/uat-stress-mixed-batch-2026-09-13.csv, `tests/stress-tests/README.md` row map) sent with an armed record-scoped window should create the valid-email rows (25) and update the one existing contact (`1251`, ctelfer@australianturfclub.com.au), holding only the sparse/malformed rows for review.
actual: 0 created, 0 updated, 47 review, 1 skip. Every row carried `lookup_failed: true`. 31 rows reported reason "valid email, no existing match" — including contact `1251`, which exists. Arm/disarm verified clean (flags read back false); the send itself was accepted (ack `accepted: true`).
errors: n8n execution 12429 (and the earlier identical attempt 12426), workflow `LV Contact Ingest (Cloud template)` `AwbBeShdPgV48eiY`: node `HubSpot Search by Email` 33/48 items errored, `HubSpot Company Search by Domain` 38/48, `HubSpot Company Search by Name` 42/48 — every error item is NodeApiError `The service is receiving too many requests from you` / description `You have reached your secondly limit.` (HTTP 429). `Adapt Search Results` output: 48× `lookup_failed: true`. `Decide Action`: 23× ('review','valid email, no existing match', company_match None), 15× ('review','no email, insufficient identity'), 6× ('review','valid email, no existing match','manual'), 2× (...,'name'), 1 skip. Read via the plugin's `executions_client.get_execution` — Webhook Trigger runData was NOT inspected or copied (it embeds the webhook secret).
reproduction: POST the 48-row CSV to `hubspot/contact-upload` (the plugin's contact-upload skill, run `aa059535b5f644e6a9c39f695ff76bfb`). Any ingest batch large enough that per-row HubSpot searches exceed HubSpot's per-second search limit (prior UATs were ≤ 9 rows and passed — 9-row walk 2026-08-05, Phase 72 gates 1–2 rows).
started: First observed 2026-09-15 on the first ≥ 20-row ingest send this repo has ever made. Not a regression of a previously-passing size; a throughput ceiling never reached before.

## Constraints (project rules the fix must honour)

- Never hand-edit `n8n/wf_*.json` — change `scripts/build_cloud_workflows.py` and regenerate (`python3 scripts/build_cloud_workflows.py`; the committed JSON must equal the regenerated output).
- Never deploy, bounce or arm anything. Deploy + bounce disarmed is the operator's step (`scripts/deploy_n8n_workflows.py`, `scripts/bounce_n8n_workflows.py`), recorded in the stress session sheet `tests/stress-tests/SESSION-2026-09-15.md`.
- `retryOnFail` is NOT a fix: the builder's own `_live_http` note records that n8n ignores it when `onError` is a continue mode (RESEARCH Pitfall 3). Throttling (`options.batching`) or a batched search body are the candidate mechanisms; state the trade-off (per-execution wall time vs the ~100 s Cloudflare webhook ceiling — note the ingest lane answers its ack early via `Build Ingest Ack`/`Respond to Webhook`, so post-ack work is not bounded by that ceiling; verify this claim in the builder before relying on it).
- Do not widen scope to the enrichment lane's search nodes unless the same per-row burst pattern provably applies there (it chunks at 2 records per POST; propose mode up to 20 rows — decide on evidence, not assumption).
- Keep `lookup_failed → never create` fail-safe intact (D-72-05 / Phase 36 Finding B). F-A4 is about the REASON STRING only.
- Tests: `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/ operator-claude-plugin/tests/` and `node --test tests/n8n/*.test.mjs` must be green (4948 passed / 154 skipped, 1170 node at HEAD). Frozen fixtures under `tests/fixtures/` and `tests/n8n/fixtures/frozen/` may need a recorded, node-scoped re-baseline — follow the existing re-baseline discipline (see 72-11-SUMMARY.md) and never freeze runData containing a Webhook Trigger `headers` object.
- Shell `grep` is rtk-wrapped in this environment: use `/usr/bin/grep`.
- Commit with the session attribution trailers:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01X5oeJHf2gNeEHmCTyfzjao`.

## Eliminated
<!-- APPEND only - prevents re-investigating after /clear -->

- hypothesis: Arming never reached the running workflow (stored-vs-running drift), so writes were refused.
  evidence: `n8n_control.apply_mutation` deactivates → PUT → reactivates with an independent second read; arm verified, disarm verified; `Decide Action` chose `review` BEFORE any write gate (IF Update 0/48, IF Create 0/48), so gates were never consulted.
  timestamp: 2026-09-15T05:30:00Z
- hypothesis: Company resolution failed (org not in portal) and downgraded creates to review.
  evidence: Rows with a manual `company_id` (`company_match: manual`, e.g. `9605284724`) were also held with "valid email, no existing match"; the hold is driven by `lookup_failed`, not by company resolution.
  timestamp: 2026-09-15T05:32:00Z

## Evidence
<!-- APPEND only - facts discovered during investigation -->

- timestamp: 2026-09-15T05:28:00Z
  checked: runData of executions 12429 and 12426 (`LV Contact Ingest (Cloud template)`), node item counts and error payloads (Webhook Trigger excluded)
  found: 50 nodes ran, status success. `HubSpot Search by Email` 48 items, 33 errored 429 "You have reached your secondly limit."; `HubSpot Company Search by Domain` 38/48 errored; `HubSpot Company Search by Name` 42/48 errored. The successful search items returned `total: 0` for emails (fictitious) and the expected `total: 1` for a few company domains/names.
  implication: HubSpot per-second search rate limit is the trigger; the burst is one request per input item on three consecutive HTTP nodes.
- timestamp: 2026-09-15T05:29:00Z
  checked: `Adapt Search Results` and `Decide Action` outputs for the same executions
  found: 48/48 rows `lookup_failed: true`; `Decide Action` reasons "valid email, no existing match" (31) and "no email, insufficient identity" (16), 1 skip; `IF Update` and `IF Create` both routed 0 to the true branch.
  implication: the batch-wide `lookup_failed` fail-safe (builder ~line 1282: declared outside the per-row loop) held the whole batch as designed; the reason string does not surface that cause (F-A4).
- timestamp: 2026-09-15T05:34:00Z
  checked: generated `n8n/wf_contact_ingest_cloud.json` node parameters for the three search nodes; builder `_live_http`
  found: `n8n-nodes-base.httpRequest` typeVersion 4.2, `options: {"timeout": 20000}` only, `onError: continueRegularOutput`, no `retryOnFail`, no `options.batching`; `_live_http` docstring explains why retryOnFail is deliberately absent. No node in any generated workflow uses `batching` today.
  implication: the fix is a builder change to the per-row search nodes (throttle or batch the body); it must survive regeneration and be pinned by an offline structural test.
- timestamp: 2026-09-15T06:35:00Z
  checked: the constraint's own claim ("the ingest lane answers its ack early... post-ack work is not bounded by [the ~100s Cloudflare] ceiling") — verified per the constraint's own instruction, not assumed. Checked node positions in the generated JSON (`Set Config` [440,300], `Extract From File` [660,300], `Build Ingest Ack` [440,480], `Set Config Fields` [440,660]), the workflow's `settings.executionOrder` ("v1", confirmed generated AND confirmed live on all five cloud workflows as of the Phase 72 gate per CLAUDE.md), and n8n's own published v1 semantics (docs.n8n.io/build/flow-logic/understand-execution-order: "v1... executes each branch in turn, completing one branch before starting another... orders the branches based on their position on the canvas, from topmost to bottommost").
  found: topology alone (no data dependency from "Set Config" to "Build Ingest Ack") is NECESSARY but NOT SUFFICIENT — under v1's documented branch-ordering rule, "Set Config"'s THREE fanned-out branches run topmost-canvas-position-first, to completion, one at a time. "Extract From File" (the entire main pipeline, including all three now-throttled search nodes) sits at the SAME y as "Set Config" — topmost of the three branches — while "Build Ingest Ack" (y+180) and "Set Config Fields" (y+360) sit below it. The main pipeline branch therefore runs to completion FIRST; the ack does not fire until after it.
  implication: the constraint's original claim ("post-ack work is not bounded by the ~100s ceiling") is WRONG for this workflow's actual live configuration (v1). The added throttling wall time (48 rows x 250ms x 3 nodes ~= 36s) lands BEFORE "Respond to Webhook", counting against the Cloudflare ~100s ceiling — not after it. Still safe at 48 rows (36s is well under 100s even before adding the lane's other per-row work), but this bounds how much larger a future batch can grow under the same per-row-search design before approaching that ceiling; a materially larger batch would need this rechecked together with the lane's other latency (email verification batch, the matched-row Contact History hop).

- timestamp: 2026-09-15T06:40:00Z
  checked: node start times in execution 12429's runData (orchestrator, after the debugger's "correction" about ack ordering)
  found: `Set Config` 0.00s, `Extract From File` 0.01s, `Build Ingest Ack` 0.02s, `Respond to Webhook` 0.03s, then `HubSpot Search by Email` 0.57s, `Company Search by Domain` 2.97s, `Company Search by Name` 5.05s, `Decide Action` 7.18s. Total wall 7.4s.
  implication: the ack fires BEFORE the pipeline on the live v1 body — the debugger's static reading (pipeline topmost, ack after) is contradicted by the observed execution. Post-ack work is therefore not bounded by the plugin's 30s `dispatch.py` transport timeout or the ~100s webhook ceiling; the ~36s the throttle adds (48 rows × 250ms × 3 nodes) lands after the ack and only lengthens the recovery poll (bound 600s). The Constraints section's original claim stands.

## Resolution
<!-- OVERWRITE as understanding evolves -->

root_cause: |
  F-A3: the contact ingest lane's three per-row HubSpot search HTTP nodes
  ("HubSpot Search by Email", "HubSpot Company Search by Domain", "HubSpot Company
  Search by Name") fired one request per CSV row in a single burst, with no throttling
  (`_http_node` emitted `options: {timeout: 20000}` only). HubSpot's CRM Search API is
  capped at 5 req/s account-wide (developers.hubspot.com/changelog/crm-search-api-rate-
  limit-increase). A 48-row batch therefore fired 48 requests per node in a burst, and
  HubSpot answered 429 "You have reached your secondly limit." on most items (33/48,
  38/48, 42/48). `Adapt Search Results` correctly (by design, Phase 36 Finding B)
  stamped the whole batch `lookup_failed: true` on any errored search item.
  F-A4: `Decide Action`'s reason string read `id.reason` (from `resolveIdentity`)
  verbatim. For a row with a valid email whose search failed, `resolveIdentity` cannot
  distinguish "searched, zero hits" from "search never ran" and returns "valid email,
  no existing match" either way — so an EXISTING contact (Colin Telfer, `1251`) whose
  search 429'd was reported with the same reason a genuinely new contact gets, with no
  indication the true cause was a rate-limited/failed lookup.
fix: |
  F-A3: added an optional `batch_interval_ms` parameter to `_http_node`
  (scripts/build_cloud_workflows.py) that, when set, emits n8n's native
  `options.batching.batch.{batchSize: 1, batchInterval}` — the documented n8n
  throttling mechanism (batchSize/batchInterval pace one item per interval). Wired at
  250ms (4 req/s, 20% headroom under HubSpot's 5 req/s cap) on all three per-row
  search nodes. Default is `None` (omits `options.batching` entirely), so every other
  existing `_http_node` call site is byte-for-byte unchanged — confirmed by the
  regeneration diff touching only the three named nodes plus Decide Action. Wall-time
  cost documented at the call site: 48 rows x 250ms x 3 nodes ~= 36s, added BEFORE
  "Respond to Webhook" fires under this workflow's live `executionOrder: v1` (see the
  2026-09-15T06:35:00Z Evidence entry — the ack does not fire early), safely under the
  ~100s Cloudflare webhook ceiling at 48 rows.
  F-A4: in `DECIDE_CLOUD`'s jsCode, introduced `identity_reason` (copied from
  `id.reason`) and override it to "lookup failed (HubSpot search unavailable/rate-
  limited) — held, not matched" ONLY when `row.lookup_failed === true &&
  id.outcome === "net_new"` — matched on the outcome rather than a hardcoded copy of
  resolveIdentity's reason text (net_new's sole reason is that exact string, so the two
  conditions are equivalent, but outcome-matching survives a future reword). A real
  match/multi-match reflects an actual hit a 429 can't invent; an emailless row's own
  reason is computed without ever touching this search. The final `reason:` field now
  reads `company_hold || identity_reason || row.reject_reason || null` (was
  `id.reason`); `company_hold` can never be set in this same branch (a net_new row only
  reaches the company_hold check with `action === "create"`, and the lookup_failed
  guard immediately above it already downgraded `create` to `review` first), so the
  override is never shadowed.
  Regenerated `n8n/wf_contact_ingest_cloud.json` via
  `python3 scripts/build_cloud_workflows.py` — diff is scoped to exactly these three
  nodes' `options.batching` and Decide Action's `jsCode`; no other generated workflow
  changed; node ids unchanged (deterministic build).
verification: |
  - signal 1 (offline structural test, NEW): tests/test_ingest_search_contract.py::
    test_per_row_search_nodes_are_throttled — asserts all three search nodes carry
    `options.batching.batch` with batchSize=1 and batchInterval > 200ms (200ms IS the
    5 req/s cap, so the interval must be strictly slower to have headroom). [documented]
    only per CLAUDE.md's evidence-tagging convention — no batching option has ever run
    on this n8n Cloud instance; this proves the generated config, not live throttling
    behavior. PASS.
  - signal 2 (offline behavioral test, NEW): tests/test_ingest_search_contract.py::
    test_decide_action_names_lookup_failure_distinctly_from_a_genuine_miss — executes
    the COMPILED `Decide Action` jsCode (via `node -e`) against four rows: (1)
    execution 12429's exact shape for Colin Telfer (valid email, net_new,
    lookup_failed=true) -> asserts the new lookup-failed reason string; (2) same row
    with lookup_failed=false (control) -> asserts the ORIGINAL "valid email, no
    existing match" reason is untouched; (3) a genuinely emailless row with
    lookup_failed=true (control) -> asserts its "no email, insufficient identity"
    reason is untouched; (4) a valid email with MULTIPLE hits (ambiguous,
    lookup_failed=true, control) -> asserts "multiple email matches" is untouched
    (only the net_new outcome is overridden, not every email-bearing outcome under the
    batch-wide flag). PASS.
  - signal 3 (regression, full suites): `.venv/bin/python -m pytest -q --tb=short
    -p no:cacheprovider tests/ operator-claude-plugin/tests/` -> 4952 passed, 154
    skipped (baseline immediately before this session's edits, same checkout: 4950
    passed / 154 skipped — +2 is exactly this session's 2 new tests; no regressions).
    `node --test tests/n8n/*.test.mjs` -> 1170 passed, 0 failed (unchanged from
    baseline). No frozen fixture needed re-baselining (no runData/walker fixture
    touches these three nodes' `options` or Decide Action's reason field by exact
    string match).
  - NOT verified this session (explicit scope boundary, constraints + debug file's own
    `expecting`): a live re-run of the 48-row CSV against the deployed workflow. This
    session may not deploy, bounce, or arm anything. That live proof is the operator's
    step, tracked in tests/stress-tests/SESSION-2026-09-15.md — it should confirm 0
    errored items on the three search nodes, `lookup_failed: false` on every row, and
    contact `1251` resolving to `action: "update"` (not the pre-fix "no existing
    match").
  guardrail_verdict: accepted (all applicable offline signals pass; live-proof signal
    is explicitly out of this session's scope by the task's own constraints, not
    skipped by omission)
oracle_type: derived
  # derived from (a) HubSpot's own published CRM Search rate-limit contract (the 5
  # req/s ceiling that determines whether batchInterval is "throttled enough"), and
  # (b) the documented behavior contract of resolveIdentity/DECIDE_CLOUD (which reason
  # strings identity resolution is allowed to produce, and under what conditions a
  # failed search can or cannot manufacture one) — not merely a specified single
  # expected value, and not merely "doesn't crash".
files_changed:
  - scripts/build_cloud_workflows.py
  - n8n/wf_contact_ingest_cloud.json
  - tests/test_ingest_search_contract.py
