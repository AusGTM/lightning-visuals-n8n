# Phase 60: Review-lane authority - Context

**Gathered:** 2026-09-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Give the review lane (approving or rejecting one flagged HubSpot record) the same
once-per-session grant authority the enrichment and contact-ingest lanes already have,
closing BOTH manual round trips a human currently has to do to approve a single flagged
record: (1) an admin setting `ALLOW_REVIEW_SUBMIT=true` as a shell env var on their own
machine, and (2) a separate admin-run deploy that bakes `ALLOW_HUBSPOT_REVIEW_WRITES` plus
the record's id into the deployed `LV Review Decision (Cloud)` n8n workflow.

This phase does NOT touch the ingest → enrich → write path itself, does not change
enrichment or contact-ingest behavior beyond adding "review" as a third grantable lane, and
does not change what a reviewer sees before approving (the dry-run exact-write preview via
`preview_decision` stays exactly as it is — deliberately ungated, unaffected by any of this).

</domain>

<decisions>
## Implementation Decisions

### Authority model

- **D-60-01:** Review-lane approval authority reverses Phase 30-01's deliberate separation
  (D-02/D-08e) between dispatch grants and review writeback. Chosen over (a) an admin
  config key that keeps the two authorities separate, and (c) accepting the current
  two-round-trip flow as correct for occasional triage. — **Reversibility:** costly —
  undoing this means re-excluding `ALLOW_HUBSPOT_REVIEW_WRITES` from whatever grantable-lane
  set this phase builds, and re-standing-up `ALLOW_REVIEW_SUBMIT` as review's sole
  independent gate (D-60-04 retires it).
- **D-60-02:** A single grant covers all three lanes together (enrichment, contacts,
  review) — opening one grant authorizes all three, not a separate deliberate "yes" per
  lane. This mirrors D-53-05's existing precedent (one grant already spans enrichment +
  contacts) rather than inventing a new per-lane consent model. — **Reversibility:**
  costly — separating review back into its own deliberately-opened grant would need
  re-adding a lane-selection step to whatever grant-opening flow this phase builds.
- **D-60-03:** The grant's existing record-scoping (ids/domains named when it is opened)
  bounds which flagged records can be approved via review, exactly the same "narrower than
  the grant, never wider" rule dispatch sends already follow (`write_grant.authorize_send`).
  A grant opened over records A/B/C cannot approve a review decision on record D. This is
  what keeps D-60-02's combined-lane choice from being a blank check on every flagged record
  in the system — only records already named in the grant get review authority too.
  — **Reversibility:** reversible.
- **D-60-04:** The client-side `ALLOW_REVIEW_SUBMIT` shell-env kill switch
  (`review_decision.py:SUBMIT_ENV_VAR`) is retired. Grant-authorization
  (`write_grant.authorize_send` / `authorize_ungranted_send`) becomes the gate
  `submit_decision()` checks instead — the same authorization call enrichment already uses,
  not a second copy of the check. — **Reversibility:** reversible.

### Round-trip closure — dynamic backend arm

- **D-60-05:** This phase also wires `ALLOW_HUBSPOT_REVIEW_WRITES` into the same dynamic
  arm-window mechanism (`n8n_arming.py`) dispatch already uses, so a grant's review decision
  needs zero manual admin deploy. Without this, D-60-01/D-60-02 would remove the friction
  that mattered least (a client-side env var) while leaving the friction that mattered most
  (a human running a deploy) untouched. — **Reversibility:** reversible — additive; the
  existing deploy-time-baked path (`deploy_n8n_workflows.py::enable_baked_flags`) is not
  removed, only bypassed when a grant arms dynamically instead.
- **Load-bearing implementation note (Claude's discretion on the mechanism, not asked as a
  question):** `ALLOW_HUBSPOT_REVIEW_WRITES` already shares the SAME `TEST_RECORD_IDS` /
  `TEST_RECORD_DOMAINS` allowlist as the dispatch flags in the deployed workflow node — it
  is one of `n8n_arming.OVERLAYABLE_FLAGS`'s five names, just never included in
  `DISPATCH_FLAGS`. A review arm window must set `ALLOW_HUBSPOT_REVIEW_WRITES=true` on the
  allowlisted records **without** setting `ALLOW_HUBSPOT_RECORD_WRITES=true` for them —
  arming review on a record must never incidentally open dispatch-write eligibility for
  that same record. The separate `WRITE_ENABLING_FLAGS` booleans already make this safe by
  construction (the shared allowlist alone authorizes nothing without its own boolean); the
  planner should add a `REVIEW_FLAGS` (or similarly named) constant analogous to
  `DISPATCH_FLAGS`, not extend `DISPATCH_FLAGS` itself.
- **`write_grant.LANES` currently maps 2 lane names → 2 workflow names**
  (`{"enrichment": ..., "contacts": ...}`, `write_grant.py:83-86`). Add `"review"` →
  `"LV Review Decision (Cloud)"` (the workflow's actual `name` field, confirmed live from
  `n8n/wf_review_decision_cloud.json`; no existing Python constant names it yet — the
  planner should add one, e.g. `REVIEW_WORKFLOW_NAME`, mirroring
  `ENRICHMENT_WORKFLOW_NAME` / `CONTACT_INGEST_WORKFLOW_NAME`'s placement pattern).
- **Recorded-edit discipline required, matching D-53-05's own precedent (the roadmap
  explicitly calls this out):** `write_grant.py:64-82`'s comment block documents WHY the
  review lane is currently excluded from `LANES` (30-01 D-02/D-08e). This phase reverses
  that decision — the comment must be AMENDED with a dated addendum explaining the reversal
  and why (mirroring the D-59-07 amendment already sitting a few lines below it in the same
  file), never silently deleted or rewritten as if the old design never existed.

### Arm granularity

- **D-60-06:** One arm window covers a whole batch of review decisions in a session,
  rather than opening and disarming a fresh window for every single decision. Chosen over
  per-decision arm/disarm (which would exactly mirror how each enrichment SEND already
  opens its own window under `authorize_send`) because triaging several flagged records in
  one sitting shouldn't cost an arm/disarm round trip to n8n per record.
  — **Reversibility:** costly — a batch-scoped window's lifecycle (open once, handle a
  disarm-on-crash mid-batch, handle what happens if one decision in the batch fails) is
  more involved to build than per-decision arm/disarm; reversing to per-decision later means
  re-deriving that lifecycle from scratch rather than trimming an existing one.
- **Note for planner:** D-60-03's record-scoping still applies per decision inside the
  batch — the batch arm's allowlist is fixed to the grant's own record list at open time
  (per D-60-02/D-60-03), it does not grow as the operator triages records one by one.

### Answered during planning (raised by 60-RESEARCH.md's open questions, 2026-09-01)

- **D-60-07:** A `reject` decision works with **no grant open**. This preserves, symmetrically,
  the exact property the retired `ALLOW_REVIEW_SUBMIT` carve-out existed for
  (`review_decision.py`'s `is_undoing`): a closed authority must never be able to strand a
  flagged record mid-decision. A reject promotes nothing — it records a reason and leaves the
  record in the queue — so it carries none of the risk the grant exists to gate. The session arm
  (`review_armed`) is unaffected and still required, exactly as it is today for both approve and
  reject. **The `is_undoing` carve-out therefore SURVIVES D-60-04's retirement of the env var —
  it is re-pointed at the grant check, not deleted.** — **Reversibility:** reversible.
- **D-60-08:** Review-lane writes **DO** appear in the per-run `written_records-<run_id>.json`
  artifact (D-59-07/D-59-09), against 60-RESEARCH.md's own recommendation to treat it as out of
  scope — operator's call, 2026-09-01. Rationale: one artifact should answer "what did this
  session write to HubSpot" across all three lanes now that all three are grantable.
  — **Reversibility:** costly — review decisions go through `review_decision.submit_decision`,
  never `chunking.dispatch_plan`, so this is new plumbing rather than a reused call site;
  removing it later means unpicking a second writer of that artifact.
  **Constraints the planner must carry over from the artifact's own decisions:** the run must be
  keyed by a `run_id` the same way a dispatch run is (D-59-09: one artifact per run, readers glob
  and union — never a shared append); and per D-59-10 a written-records failure must **never**
  stop or abort a review write, it is recorded in the outcome and surfaced loudly instead.

### Claude's Discretion

- The exact mechanism for a `REVIEW_FLAGS`-style constant and where the review-specific
  arm/disarm wrapper function lives (new function in `n8n_arming.py`, or a `write_grant.py`
  call site composing the existing generic overlay primitives directly) — both are
  consistent with the existing architecture; pick whichever produces the smaller diff.
- Whether the batch arm's disarm-on-crash path reuses `n8n_arming.armed_window`'s existing
  context-manager guarantee (arm → run caller's decisions → disarm, including on the
  exception path) as-is, or needs a review-specific variant — the existing
  `armed_window.__exit__`'s "never swallow the body's exception, still disarm" guarantee
  should carry over unchanged; only the flags set at arm/disarm time differ from dispatch.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Why this phase exists and what it must not re-litigate
- `.planning/phases/59-frictionless-write-path/59-CONTEXT.md` § D-59-03 — the operator
  decision that split this phase out, the three roadmap options, and why deleting
  `ALLOW_REVIEW_SUBMIT` with nothing behind it is explicitly not an option.
- `.planning/ROADMAP.md` (search "Phase 60: Review-lane authority") — the phase's
  roadmap entry, including the exact three options and the "not an option" constraint.

### Current review-lane authority code (all three gates, as they exist today)
- `operator-claude-plugin/scripts/review_decision.py` — the client-side module this phase
  changes. Full docstring documents all three current gates (`ALLOW_REVIEW_SUBMIT`, the
  session arm `review_armed`, backend `ALLOW_HUBSPOT_REVIEW_WRITES`) and D-01/D-04's
  requirement that the session arm never persist to disk or outlive the session — that
  constraint is unaffected by folding review into a grant, since grants themselves are
  also session-scoped, not persisted.
- `operator-claude-plugin/scripts/n8n_arming.py` — the dynamic arm/disarm overlay
  mechanism this phase extends to review. `OVERLAY_DISABLED_LITERALS` (5 flags, including
  `ALLOW_HUBSPOT_REVIEW_WRITES`), `DISPATCH_FLAGS` (the 4 dispatch already uses),
  `WRITE_ENABLING_FLAGS`, `ALLOWLIST_FLAGS`, and the `armed_window` context manager (arm,
  run caller's dispatch, guaranteed disarm including on the exception path).
- `operator-claude-plugin/scripts/write_grant.py` — the grant machinery this phase folds
  review into. `LANES` (lines 64-86, including the comment block D-60-01/D-60-05 requires
  amending), `authorize_send`/`authorize_ungranted_send` (the authorization calls
  `submit_decision` should route through per D-60-04), `plan_grant`/`open_grant`, the
  per-send record-scoping this phase's D-60-03 extends to review.
- `n8n/wf_review_decision_cloud.json` — the deployed workflow this phase's dynamic arm
  targets (`name: "LV Review Decision (Cloud)"`). Never hand-edit; regenerate via
  `scripts/build_cloud_workflows.py` per the project's standing rule.

### Skill-side entry point (likely touched during planning/execution)
- `operator-claude-plugin/skills/review-triage/` — the skill an operator invokes to
  triage flagged records; wherever it currently checks `ALLOW_REVIEW_SUBMIT`/session-arm
  and calls `submit_decision` is where the new grant-authorization call replaces the old
  env-var check.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `write_grant.authorize_send` / `authorize_ungranted_send` — already return the identical
  `{armed, workflow_id, grant, refusal, detail}` shape regardless of which authorized the
  send; the review lane's decision call can use the exact same pattern enrichment's dispatch
  already does (see `operator-claude-plugin/skills/enrich-records/SKILL.md` step 8's code
  block for the canonical shape).
- `n8n_arming.armed_window` — the context-manager arm/dispatch/disarm lifecycle, including
  the guaranteed-disarm-on-exception behavior this phase's batch arm needs.

### Established Patterns
- Per-send/per-decision record-scoping ("narrower than the grant, never wider") — D-60-03
  extends this exact rule to review rather than inventing a new one.
- Recorded-edit discipline (D-53-05's own precedent) for amending a comment that documents
  a now-reversed design decision, rather than deleting it — D-60-05 requires this for
  `write_grant.py:64-82`.

### Integration Points
- `write_grant.LANES` gains a third entry (`"review"`).
- `n8n_arming.py` gains a `REVIEW_FLAGS`-analog constant and (per Claude's discretion above)
  a review-specific arm wrapper.
- `review_decision.py::submit_decision` loses its `ALLOW_REVIEW_SUBMIT` check
  (`submit_enabled()`) and gains a grant-authorization check in its place.

</code_context>

<specifics>
## Specific Ideas

No UI/UX-level specifics were raised — this phase is authorization plumbing, not a
reviewer-facing workflow change. The exact-write preview (`preview_decision`) stays exactly
as it is today; nothing about what a reviewer sees before approving changes.

</specifics>

<deferred>
## Deferred Ideas

None raised during this discussion — no scope creep occurred; all three areas stayed within
the phase's authorization-plumbing boundary.

### Reviewed Todos (not folded)
- `2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md` — surfaced by todo matching at
  score 0.2 (below the 0.4 fold threshold); already noted as unrelated to this phase's
  subject in `59-CONTEXT.md`'s own deferred section. Left in the backlog.

</deferred>

---

*Phase: 60-review-lane-authority*
*Context gathered: 2026-09-01*
