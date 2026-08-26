# Phase 54: Single-pass armed dispatch - Research

**Researched:** 2026-08-26
**Domain:** n8n Cloud arm/dispatch lifecycle, cost/execution measurement, HubSpot review-flag clearing
**Confidence:** HIGH (code read directly this session; two claims flagged LOW where live instrumentation doesn't exist)

## Summary

**The headline finding, and it is load-bearing for planning: G-3's accidental mechanism is
already fixed, shipped, and live-verified — one day before this research, inside Phase 53's
own close-out.** `write_grant.authorize_ungranted_send()` (added as fix "F2",
`operator-claude-plugin/scripts/write_grant.py:740-779`, plugin 0.18.0) makes every interactive
send — grant or no grant — open an `n8n_arming.armed_window` **before** `chunking.dispatch_plan`
runs, so the deployed workflow's write-safety flags are already `true` when the one and only
full-waterfall pass executes. `.planning/debug/resolved/walk-write-path-defects.md` documents
this as root-caused and fixed against live executions (`11934/11935/11937` reproduced the bug
pre-fix; the fix itself was structurally tested, not yet live-write-verified at F2's own
close). `.planning/STATE.md`'s Phase-53-complete entry (`git show b24d7b2`) then records that
the operator walk on 2026-08-26 **did** land a real write this way — "John Tsatsimas
347569451461 fully written (title/phones/email/city/country)" — which is the live proof F2's
own summary said was still missing. `operator-claude-plugin/CHANGELOG.md`'s `[0.18.0]` entry
independently confirms the same mechanism under the same name.

**What this means for scope:** Phase 54 is not "build the fix" — it already exists for the
common case (record ids, exact email/LinkedIn identity, domain-identified companies, and every
standing-grant send). What remains is (1) **measuring** the already-shipped saving with real
numbers instead of the projected formula `write_grant.envelope()` currently ships
(`WINDOWS.md` id 26 names this explicitly as Phase 54's job), (2) **naming honestly** the two
distinct cases that still cost two full passes by either design or structural necessity —
propose-mode rehearsal and ambiguous-identity confirm-then-resend — neither of which is the G-3
bug, and (3) the operator-added scope: closing the contact review-flag lane, which is a small,
well-scoped n8n change, not a plugin change.

**Primary recommendation:** Do not re-implement arm-before-dispatch. Spend the phase on: a live
before/after execution count for one record (via `executions_client`, already used by
`scheduled_arm.py`); updating `envelope()`'s `projected_executions` label and
`REQUIREMENTS.md`/`ROADMAP.md`'s G-3 language to match what's actually shipped; adding the
"this will cost a second pass" disclosure to propose-mode and ambiguous-match flows; and a
scoped `reviewDecision.js` change (`n8n/code/reviewDecision.js:229-234`) that lets a contact
review decision clear its flag without inventing a contacts apply-engine.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Consent / arming decision | Client (Python plugin) | — | `write_grant.py`/`n8n_arming.py` own the plan→show→yes→arm sequence; no server-side consent state exists |
| Write-safety gate (the actual block) | Backend (n8n workflow, `Decide Company/Contact Action` node) | — | `_writeSafetyAllows()`, baked into the deployed workflow's Code nodes; only a bounced deploy changes it |
| Full waterfall (providers, Haiku, Sonnet) | Backend (n8n workflow) | — | Runs unconditionally inside the SAME execution as the write-safety check, before the check — this is why an unarmed pass is not cheap |
| Execution / cost measurement | Client (Python, via n8n API reads) | n8n Cloud (source of truth) | `executions_client.py` already reads execution history; no new endpoint needed |
| Review-flag clear for contacts | Backend (n8n workflow, `n8n/code/reviewDecision.js`) | Client (review-triage skill prose) | The decision logic and the property write both live in the n8n-authored Code node; the skill only relays what the endpoint returns |

## Standard Stack

Not applicable — this phase adds no new library or service dependency. Every capability needed
(arming, execution reads, review decisioning) already exists in this repo. No `npm install` /
`pip install` line is expected in this phase's plan.

## Package Legitimacy Audit

Not applicable — no external package is proposed by this research.

## 1. Where the two passes actually happen (and where they no longer do)

### The mechanism, traced end to end

1. **Client builds and sends a chunk.** `operator-claude-plugin/scripts/chunking.py:253-301`
   (`dispatch_plan`) calls `enrichment.build_envelope` then
   `enrichment.dispatch_enrichment(envelope, armed, config, ...)` once per chunk. `armed` here
   is a plain bool the caller passes — it does **not**, by itself, touch the backend's
   write-safety flags. It only gates the client's willingness to POST at all
   (`dispatch.py:31-36`, `NotArmedError`).
2. **The backend runs the full pipeline regardless of the write-safety flags.** Inside the
   deployed enrichment workflow (built by `scripts/build_cloud_workflows.py`), the sequence is:
   fetch → gate → provider waterfall (ZoomInfo/Apollo/Lusha) → normalize/score → Haiku → Sonnet
   (if conflict) → **`Decide Contact/Company Action`** → respond. Every one of those upstream
   nodes runs unconditionally; the write-safety check is the LAST thing evaluated, deep inside
   `Decide Contact Action`:
   ```js
   // scripts/build_cloud_workflows.py:1625-1628
   if ((action === "create" || action === "enrich") &&
       !_writeSafetyAllows(action, hs_object_id, domain)) {
     action = "write_blocked";
   }
   ```
   `_writeSafetyAllows` itself (`scripts/build_cloud_workflows.py:1171-1188`) requires
   `ALLOW_HUBSPOT_RECORD_WRITES === "true"` AND a non-empty allowlist match (id or domain). By
   the time this line runs, every provider credit, every Haiku call, and every Sonnet call for
   that record has already been spent — `write_blocked` throws away a fully-derived result, not
   an unstarted one.
3. **Before F2 (fixed 2026-08-25), the interactive path could never supply an armed backend on
   the first try.** `.planning/debug/resolved/walk-write-path-defects.md`'s "F2" section quotes
   the deployed `Decide Action` node's compiled defaults —
   `const ALLOW_HUBSPOT_RECORD_WRITES = "false"; const TEST_RECORD_IDS = "";` — and proves via
   live executions `11934/11935/11937` that a correctly-matched record still returned
   `write_blocked` because "only the GRANT path calls `n8n_arming.armed_window`; the ungranted
   path's `armed=True` authorizes the client POST only." That is the exact two-pass defect
   G-3 names: one full-cost pass that could only ever return `write_blocked`, then a second
   full-cost pass after a human manually re-armed and re-sent.
4. **F2 closed that gap by moving the arm to before the dispatch, for both the granted and the
   ungranted case.** `write_grant.py:740-779` (`authorize_ungranted_send`) composes the existing
   `plan_grant()` + `open_grant()` into a single-lane, single-use grant scoped to exactly one
   send's records, gated on the same `allow_write_grants` key a standing grant uses. Every lane
   skill's dispatch step (`enrich-records/SKILL.md:225-274`,
   `contact-upload/SKILL.md` step 6, both `enrich-before-ingest` lanes) now does:
   ```python
   decision = (write_grant.authorize_send(grant, ...) if grant is not None
               else write_grant.authorize_ungranted_send(cfg, ...))
   if not decision["armed"]:
       ...  # STOP, no HTTP call at all
   with n8n_arming.armed_window(decision["workflow_id"], <ids>, <domains>,
                                <allow_create>, cfg, grant=decision["grant"]):
       outcome = chunking.dispatch_plan(plan, providers, True, cfg)
   ```
   `armed_window.__enter__` (`n8n_arming.py:496-501`) calls `arm_for_dispatch`, which flips
   `ALLOW_HUBSPOT_RECORD_WRITES`/`TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS` on the live workflow and
   verifies the rewrite by independent re-read (`n8n_arming.py:299-420`) **before** returning
   control to the `with` block that then calls `dispatch_plan`. The single dispatch inside that
   block is therefore the only pass; the backend is already armed when the provider waterfall
   runs, so `_writeSafetyAllows` returns `true` on the same execution that derived the values.
5. **`.planning/STATE.md` (commit `b24d7b2`) records this live-verified**, not merely
   structurally tested: "John Tsatsimas 347569451461 fully written (title/phones/email/city/
   country)" during the Phase 53 close-out walk, 2026-08-26. `operator-claude-plugin/
   CHANGELOG.md`'s `[0.18.0]` entry documents the same fix under the same name (F2), independent
   confirmation of the mechanism (both files read this session).

### What is NOT fixed by F2 — the headless (scheduled) path

`operator-claude-plugin/scripts/scheduled_arm.py` (SJ-3 poller companion) is architecturally a
**separate** two-pass by design, not touched by F2 and not mentioned in the v1.1 milestone as
in scope: SJ-3's own in-n8n dispatch (`SJ-3 Dispatch To Enrichment`, an Execute-Workflow node
inside `LV Scheduled Maintenance (Cloud)`) always runs unarmed and always returns
`write_blocked` (module docstring, `scheduled_arm.py:44-54`: "this companion cannot literally
straddle SJ-3's Execute-Workflow call... it does not touch SJ-3's own in-n8n dispatch, which
keeps running on its own schedule and will keep reporting `write_blocked`"). `scheduled_arm.py`
then externally re-runs the SAME matched batch, armed, through the identical
`n8n_arming.armed_window` + `chunking.dispatch_plan` sequence (`scheduled_arm.py:218-227`) —
this is a genuine, permanent, by-design double full-waterfall pass for every record SJ-3
matches, and it is **out of milestone scope** per D-1.1-01 ("`ALLOW_N8N_ARM` is retained,
unchanged, as the sole authority for headless/cron paths... Nothing about the sweep or the SJ-3
companion changes in this phase" — `53-CONTEXT.md:34-36`). Flagging this for the planner as an
**open question, not an assumption**: the roadmap's Phase 54 goal text ("a record is enriched
once") reads as if it covers every path, but the milestone's own decisions scope headless paths
out. Recommend the plan state explicitly whether `scheduled_arm.py`'s double pass is in or out
of Phase 54 — right now nothing forces it in, and nothing has decided it's out either.

## 2. What "arm first" changes structurally — the ordering constraint

The constraint is real but already solved by construction, not something Phase 54 needs to
design: **the allowlist an armed window needs must be resolvable from information the client
already has before the dispatch, or the window cannot be built at all.**

- **Record-id specs, exact-identity people specs (email/LinkedIn), and domain-anchored company
  specs**: the id or domain is known from the operator's own input before any HTTP call, so
  `authorize_send`/`authorize_ungranted_send` can compute the allowlist and arm before dispatch
  with no gap. This is the common case and is what F2 fixed.
- **Ambiguous-identity people specs** (matched by surname + company only, "medium" tier): the
  `hs_object_id` genuinely does not exist client-side until the backend's name-search runs
  inside the SAME enrichment-workflow execution that also runs the full provider waterfall
  (`scripts/build_cloud_workflows.py:1617-1624` — the `needs_match_review` reassignment happens
  in `Decide Contact Action`, AFTER `Normalize + Score` has already produced `row.merge`). So a
  medium-tier match's full waterfall cost is already spent by the time the operator is even
  shown a candidate to confirm — there is no way to arm ahead of that first pass, because the
  id an armed window would need is one of this pass's own outputs. Confirming the candidate and
  re-sending is a **second**, unavoidable full-cost pass. This is not a bug F2 left behind; it
  is a structural consequence of resolving identity ambiguity inside the same workflow that does
  enrichment. `.planning/debug/resolved/walk-write-path-defects.md`'s "F1" section documents the
  match-fallback logic this created (`matchProposal.js`'s `mediumCandidates`).
- **`mode: "propose"` (deliberate rehearsal, Phase 58)**: `enrichment.py:266-399` sets
  `envelope["mode"] = "propose"` only when the caller opts in (`spec.get("propose")`). Inside
  the workflow this forces `action = "proposed"` **before** `_writeSafetyAllows` is even
  consulted (`scripts/build_cloud_workflows.py:1609-1616`, "set BEFORE `_writeSafetyAllows`,
  unconditionally on the mode predicate alone — no `ALLOW_*` constant is read on this branch").
  This is a full-cost pass with no write attempted at all, by the operator's own choice, and a
  second full-cost pass is required if they later decide to commit. This is also not the G-3
  bug — it is Phase 58's proven-live propose feature (execution `11972`) — but its cost has to
  be disclosed the same way.

**No allowlist-derivation change is needed in code.** What changes structurally is only
`enrich-records`/`contact-upload`/`enrich-before-ingest`'s already-shipped ordering: authorize
→ arm → dispatch, one dispatch per authorized decision. The two remaining "two full passes"
shapes above are not something Phase 54 fixes; they are something Phase 54 must **name
correctly** so the plan doesn't try to eliminate a structural necessity or misreport a Phase 58
feature as a residual G-3 bug.

## 3. The ungranted/rehearsal path's honesty

Two distinct disclosures are currently either absent or only partially present:

- **Propose mode.** Nothing in `enrich-records/SKILL.md` currently tells the operator, at the
  point they ask for a propose/preview, that committing afterward will re-run the full waterfall
  and re-spend provider credits and Anthropic dollars. The skill needs one sentence, attached to
  the propose result, in VOCAB-01..03's register: not "mode=propose skips the write gate" but
  "this looked but didn't save anything — if you want it saved, I'll need to check it again,
  which costs the same as this check did."
- **Ambiguous-match confirm-then-resend.** `enrich-records/SKILL.md` (§2, "People, named the way
  you would name them") already tells the operator a same-surname/same-company match is "held
  for the operator to confirm, never written over" — but does not currently say that confirming
  and sending again re-runs the full waterfall a second time. The `build_sync_report`
  outcome for this case renders as `unknown` today (a documented, un-fixed gap:
  `.planning/debug/resolved/walk-write-path-defects.md`'s handover item 3 — `report_enrichment.
  _ACTION_TO_OUTCOME` has no `needs_match_review` entry), so there is no existing "this will
  cost again" sentence to extend; one has to be added.
- **What is NOT a live gap:** an accidental `write_blocked` from a genuinely-refused send (grant
  doesn't cover this record, admin hasn't enabled write grants, backend already dirty per
  Guardrail A) never reaches the backend at all — `authorize_send`/`authorize_ungranted_send`
  both return `armed: False` and the skill stops before any HTTP call
  (`write_grant.py:717-737`). There is no live "write_blocked-then-manually-rearm" ceremony left
  in the documented interactive flow for the common case; framing Phase 54's job as "keep that
  path reachable" would be describing a shape that no longer exists after F2, except in the two
  cases above.

## 4. Measuring the saving live and cheaply

**What's already measurable, cheaply, today:**
- **n8n executions**: `operator-claude-plugin/scripts/executions_client.py` (used by
  `scheduled_arm.py:145-172` and `find_latest_sj3_batch`) already lists and reads executions by
  workflow id. A before/after count for one record — one ordinary send under the current (F2)
  code, one deliberately-forced two-pass send (e.g., propose then commit) — is a few
  `list_executions` calls against the enrichment workflow's id, filtered by time window. This is
  the cheapest, most honest way to replace `write_grant.envelope()`'s `projected_executions`
  figure (`write_grant.py:210-224`, formula `executions = chunk_count + record_count`, labelled
  `PROJECTED` in `figures["basis"]`) with a MEASURED one. `WINDOWS.md` id 26 names this
  explicitly: *"envelope()'s projected_executions... is PROJECTED, never measured — nobody has
  counted executions for a multi-chunk grant end to end... measure in Phase 54."*
- **Provider credits**: `cost_guard.fetch_balances`/`compare` already reads live balances before
  and can be re-read after a single-record send to diff the delta — the existing `hubspot/
  backend-status` read this plugin already makes for every preview.
- **What is NOT measurable without new instrumentation, and should be stated as a floor, not a
  measurement:** the Anthropic dollar figure. `cost_guard.estimate_batch`
  (`operator-claude-plugin/scripts/cost_guard.py:115-156`) computes `anthropic_usd` as a static
  rate (from the dated `config/cost_rates.json`, measured 2026-07-30 per project memory) times
  record count — there is no code path anywhere in this repo that reads back Anthropic's actual
  token usage or dollar spend (`src/web_research.py`'s `claude_web_research()` does not capture
  `msg.usage`, per project memory `n8n-execution-budget`/CLAUDE.md context and confirmed by this
  session's read of `cost_guard.py` finding no usage-read anywhere). The roadmap's "~$0.07 →
  ~$0.035" projection is two multiplications of that same static per-record rate, not two
  independent measurements. **Recommendation:** either (a) report the saving in executions and
  provider credits as genuinely measured, and keep the Anthropic figure explicitly labelled
  "projected from the dated rate table, not measured" (cheapest, matches existing `basis`
  labelling conventions already in `envelope()`), or (b) if a real dollar figure is required,
  scope a small Anthropic-usage-read as its own task — this would be new instrumentation, not a
  measurement of what already exists, and should not be assumed free.

**Execution-budget accounting for the measurement itself:** the plan's monthly allowance is
2,500 (`operator.local.example.json:6`, `n8n_monthly_execution_allowance`); `max_records_per_chunk`
is 2 (`operator.local.example.json:24`, pinned to the live-measured 37.44s single-record
waterfall time, `B4` probe). A single-record before/after measurement costs at most
`chunk_count + record_count` = 2 executions per pass (per `envelope()`'s own formula) — budget
**at most ~4-6 executions total** for a one-record before/after comparison (one ordinary
single-pass send, one deliberately-forced two-pass rehearsal via propose-then-commit), which is
a rounding error against the 2,500/month allowance and does not need `n8n_cadence`'s burn-rate
alarm consulted.

## 5. Tests pinning the current behavior

No test in this repo pins the OLD two-pass-by-design behavior as a requirement — there is
nothing to "deliberately re-point" for the core fix, because F2 already replaced it and its own
tests are in place (`test_write_grant.py`'s `authorize_ungranted_send` coverage,
7 new tests per `walk-write-path-defects.md`'s F2 entry). What DOES exist and must be **read,
not rewritten**, because it still describes a real, reachable outcome:

- `operator-claude-plugin/tests/test_report_enrichment.py::test_write_blocked_row_renders_as_blocked_with_a_reason_never_enriched`
  and `::test_build_sync_report_relays_write_blocked_and_the_no_hit_match_reason` — these pin
  correct REPORTING of a `write_blocked` body when the backend genuinely refuses (allowlist
  mismatch, admin disabled the flag mid-session, etc.). `write_blocked` is still a real,
  reachable outcome after F2 — these tests are correct as-is and must not be weakened or
  interpreted as "write_blocked can no longer happen."
- `operator-claude-plugin/tests/test_report_sufficiency.py::test_build_contact_report_never_labels_the_write_blocked_row_created` —
  same category, keep as-is.
- **The one known, documented, un-fixed gap** (not a pin to touch, but load-bearing context):
  `report_enrichment._ACTION_TO_OUTCOME` has no entry for `needs_match_review`, so that outcome
  renders as `unknown` rather than something more specific — flagged in
  `walk-write-path-defects.md` handover item 3, explicitly deferred there to avoid touching
  `test_build_enrichment_report_counts_and_total_sum_correctly`'s exact-dict-equality pin. If
  Phase 54 adds the "confirming this will cost a second pass" disclosure for ambiguous matches
  (§3 above), extending `_ACTION_TO_OUTCOME` for `needs_match_review` is the natural place to do
  it, and that pin is the one the planner should expect to touch deliberately, with the reason
  recorded in place — matching this repo's established discipline (D-53-01/D-53-05 precedent).

## 6. The contact review-flag lane

**Root cause, precisely located.** `n8n/code/reviewDecision.js:229-234`:
```js
if (inp.objectType === "contacts") {
  return nothingToApply(
    "this record holds no review candidate to approve — contact records are flagged for "
    + "review (dedupe, ICP) but no contact enrichment candidate is ever staged in this "
    + "deployment, so there is nothing to promote. Reject with a reason, or edit the "
    + "record in HubSpot.");
}
```
Every contacts `approve` call resolves to `no_candidate` and writes nothing (module-header
comment, lines 44-54, confirms this is intentional, not a stub). Separately, `reject` **never**
clears a review flag for **either** object type by design (D-10/REVIEW-05, lines 27-32: "a
rejection RECORDS THE REASON AND NOTHING ELSE... The record stays in the queue WITH a recorded
decision."). So today there is no code path, for any decision value, that clears
`lv_enrichment_needs_review` on a contact — companies clear it only via `approve`, which calls
`reviewApply()` and its `clearPatch` (`n8n/code/reviewApply.js:93-99`).

**Why contacts differ semantically, and why that's the fix's shape.** The permissive contact
enrichment lane (quick 260826-20w) already **writes the value directly** when it flags a contact
for review — it does not hold a candidate for later promotion the way companies do. Confirmed at
`scripts/build_cloud_workflows.py:1576-1579`: "Deliberately does NOT write
`lv_enrichment_review_candidate_json`... this module has already WRITTEN the value... staging it
as a candidate too would make the review-apply lane try to re-apply a value that is already
live." So a contact's "review" flag means "already applied, please double-check" — not
"withheld, awaiting your promotion." Clearing it does not need `reviewApply`'s compare-and-set
promotion machinery at all; it needs a clear-only patch, analogous to `reviewApply`'s
`clearPatch` constant but without a candidate to consume:
```js
{ lv_enrichment_needs_review: "false", lv_enrichment_review_reason: "",
  lv_enrichment_reviewed_at: <timestamp> }
```
(no `lv_enrichment_review_candidate_json` to clear — never set for contacts; no
`lv_icp_needs_review` — company-only property, confirmed via `config/icp_scoring.yaml` and
CLAUDE.md §5.2, ICP scoring is companies-only).

**Where the write path already exists, unmodified.** `build_review_decision_cloud()`
(`scripts/build_cloud_workflows.py:3310-3343`, docstring lines 3315-3325) already wires a
`Review Contact Decision Update` node, gated by the SAME `_writeSafetyAllows("review", ...)`
check every review write uses (`ALLOW_HUBSPOT_REVIEW_WRITES` + the shared `TEST_RECORD_*`
allowlist — line 7226 and `splice_write_gates` call at line 7631-7632). **This means the smallest
honest closure is a change to `reviewDecision.js`'s contacts-`approve` branch ONLY** — replacing
`nothingToApply(...)` with a clear-only patch when `objectType === "contacts"` — with **no
change** to the node graph, the write gate, or the verify-fetch, all of which are already
object-type-agnostic and already deployed.

**Cost and classification of this change:**
- **This is a `build_cloud_workflows.py` / `n8n/code/` change, not plugin-only.** The logic
  lives in `n8n/code/reviewDecision.js`, inlined into the built workflow JSON by
  `build_review_decision_cloud()`. Per this repo's hard constraint (CLAUDE.md and every phase
  summary read this session), `n8n/wf_review_decision_cloud.json` must never be hand-edited —
  the fix is: edit `reviewDecision.js` → `python3 scripts/build_cloud_workflows.py` → diff →
  disarmed deploy → bounce (deactivate/reactivate, the D-18 reload requirement) → independent
  re-read. Live node tests already exist and will need extending, not building from scratch:
  `tests/n8n/reviewDecisionEndpoint.test.mjs` has a named test at line 225,
  `"approve on a contact writes nothing: no contacts candidate producer exists in this repo"`,
  and a second at line 654, `"(g4) a contacts APPROVE writes nothing and says why — no contact
  candidate is ever produced"`. **Both assert the CURRENT (to-be-changed) behavior by name and
  will need deliberate re-pointing** with the reason recorded in place — the same discipline
  D-53-01/D-53-05 already established in this repo (rewrite, do not delete, record the decision
  and its date in the test itself).
- **Deploy cost**: one disarmed deploy + bounce of `wf_review_decision_cloud.json` only (this
  workflow is separate from the enrichment and ingest workflows — no cross-workflow blast
  radius). Zero provider credits, zero Anthropic calls — this is a pure Code-node/property-write
  change with no waterfall involvement.
- **Plugin-side change, small**: `operator-claude-plugin/skills/review-triage/SKILL.md`
  currently tells the operator, in step 5, "Every contact is in this position [no_candidate],
  and so is every record flagged as a possible duplicate. There is a reason to record, but
  nothing to approve." (lines 120-122, read this session). This sentence becomes false for the
  contacts case once the fix lands and needs rewriting — but the duplicate-record case (a
  genuinely different flagging reason, still `no_candidate` for companies too) is unaffected and
  that half of the sentence should stay.
- **Naming risk to flag for the planner, not resolve unilaterally:** reusing the verb `approve`
  for "acknowledge and clear, nothing to promote" is a semantic stretch from what `approve`
  means for companies ("promote a held candidate"). This is buildable either way (reuse
  `approve` with contacts-specific behavior, documented and tested; or introduce a third
  decision value, e.g., `acknowledge`, scoped to contacts only) — the operator should decide
  which vocabulary is honest before the plan locks it in, per this repo's VOCAB-01..03
  discipline.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Arm-before-dispatch for interactive sends | A new "single-pass" wrapper or a second grant-like object | `write_grant.authorize_send`/`authorize_ungranted_send` (already shipped, F2) | Duplicating this is literally rebuilding what shipped 2026-08-25; a second implementation is exactly the drift risk `authorize_ungranted_send`'s own docstring (`write_grant.py:758-771`) was written to avoid |
| Counting n8n executions for the measurement | A new n8n-execution-reading module | `executions_client.list_executions`/`get_execution` (already used by `scheduled_arm.py`) | Same reads, same auth, same pagination handling already tested |
| A contacts "apply engine" to promote candidate values | `DEFAULT_CONTACT_POLICY` + a contacts `reviewApply` clone | A clear-only patch (no candidate involved) inside `reviewDecision.js`'s existing contacts branch | The permissive contact lane already writes values directly; there is nothing held to promote, so a promotion engine would solve a problem that doesn't exist here |
| A new cost model for the Anthropic dollar figure | A bespoke usage-estimation module | State the existing static-rate figure's basis honestly (`projected`, per `cost_guard.py`'s existing tri-state labelling) | The repo already has a `measured`/`projected`/`unconfigured` basis convention (`write_grant.py:250-257`) — extend it, don't invent a parallel one |

## Common Pitfalls

### Pitfall 1: Re-implementing F2
**What goes wrong:** A plan that treats "arm before dispatch" as unbuilt work re-derives
`authorize_send`/`authorize_ungranted_send` under a new name, creating two implementations of
the same scope check (`write_grant.covers`) that can drift.
**Why it happens:** The ROADMAP and REQUIREMENTS.md text for Phase 54/G-3 was written
2026-08-25, before F2 landed later that same day and before the live walk confirmed it
2026-08-26 — the documents describing the phase predate the fix.
**How to avoid:** Read `write_grant.py:740-779` and `walk-write-path-defects.md`'s F2 section
before writing any task that touches the arm/dispatch ordering. If a task's action text says
"wire the armed window before dispatch," check whether it already is (it is, for every
documented lane) before writing it.
**Warning signs:** A task whose acceptance criterion is "the enrichment workflow is armed
before the waterfall runs" with no reference to `authorize_ungranted_send` — that criterion is
already met by existing code.

### Pitfall 2: Conflating a feature with the bug it superficially resembles
**What goes wrong:** Treating propose-mode's deliberate two-pass, or an ambiguous-match
confirm-then-resend, as more instances of G-3 and trying to "fix" them by suppressing the
preview or auto-resolving the ambiguity.
**Why it happens:** Both produce the same visible shape (two full waterfall passes for one
outcome) as the original bug.
**How to avoid:** Propose mode is Phase 58's shipped feature (live-proven execution `11972`) and
the ambiguous-match hold is a deliberate non-clobber protection (`enrich-records/SKILL.md`
§2's "held for the operator to confirm, never written over"). Neither should be removed or
short-circuited; both need a cost disclosure, not a redesign.
**Warning signs:** A task that removes `mode: "propose"` support or auto-picks a medium-tier
candidate to avoid a second pass — either would regress a decision this repo's history shows was
made deliberately, for safety reasons unrelated to cost.

### Pitfall 3: Reporting a projected Anthropic dollar figure as measured
**What goes wrong:** The phase's stated goal ("Measure the actual saving live... ~$0.07 →
~$0.035 Anthropic") gets satisfied by computing the static rate twice and calling both numbers
"measured."
**Why it happens:** No code path in this repo captures real Anthropic usage
(`cost_guard.estimate_batch` is a pure rate-table multiplication; `claude_web_research()` never
reads `msg.usage`, per this session's read of `cost_guard.py` and project memory).
**How to avoid:** Report executions and provider credits as measured (both are readable via
existing API clients); report the Anthropic figure explicitly as projected from the dated rate
table unless the plan explicitly adds new usage-capture instrumentation as its own task.
**Warning signs:** A verification step that says "Anthropic $ actual: $0.035" with no citation
of where that number was read from an API — it wasn't; it was computed.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Ungranted send dispatches unarmed, always returns `write_blocked`; operator must manually re-arm and re-send to actually write | `authorize_ungranted_send` opens a single-use, single-lane grant and arms `armed_window` before the one dispatch | 2026-08-25 (F2), plugin 0.18.0; live-verified 2026-08-26 | The G-3 bug's accidental mechanism is closed for the documented interactive lanes; two full-cost passes → one, for the common case |
| `envelope()`'s execution count is a formula, never checked against a real count | Unchanged as of this research — still `PROJECTED` (`write_grant.py:216`, `WINDOWS.md` id 26) | Open, assigned to Phase 54 | The number an operator reads before granting a batch has never been checked against reality |
| Contact review flags can never be cleared by any decision | Unchanged as of this research — `reviewDecision.js:229-234` still returns `no_candidate` unconditionally for contacts | Open, operator-added scope for Phase 54 | Every contact ever flagged for review stays flagged forever, regardless of operator decision |

**Deprecated/outdated:** the ROADMAP's phrase "the write_blocked-then-arm path stays reachable
for the ungranted case" (Phase 54 goal text, written 2026-08-25) no longer describes the
documented interactive flow after F2 — that specific ceremony (dispatch unarmed, observe
`write_blocked`, manually re-arm, re-dispatch) is not reachable through
`enrich-records`/`contact-upload`/`enrich-before-ingest` as currently written. What remains
reachable and needs the same honest-cost framing is propose-mode and ambiguous-match
confirm-then-resend (see §2-3 above) — the planner should update this language rather than plan
against the stale description.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `scheduled_arm.py`'s SJ-3 double-pass is out of Phase 54's scope (per D-1.1-01's headless carve-out) | §1, "What is NOT fixed by F2" | If the operator actually wants this in scope, the phase's cost/measurement claims would need to cover a structurally different, always-on double-pass with no per-session grant to avoid it — a much bigger phase |
| A2 | `approve` is an acceptable verb to reuse for a contacts "acknowledge and clear" decision, vs. introducing a new decision value | §6 | If the operator prefers a distinct verb, the `reviewDecision.js` branch structure and `review-triage` skill wording both need the new name threaded through, and `n8n/code`'s `decision !== "approve" && decision !== "reject"` guard (line 185) needs a third case |

**Both flagged assumptions are scoping questions for the operator/planner, not technical
uncertainties** — the code paths involved are fully read and cited above.

## Open Questions

1. **Is `scheduled_arm.py`'s SJ-3 double-pass in scope for Phase 54?**
   - What we know: it is architecturally the same "full pass, always write_blocked, then a
     second full pass to actually write" shape G-3 describes, and it is NOT fixed by F2 (F2
     only touches the interactive lane skills).
   - What's unclear: the v1.1 milestone's own decisions (D-1.1-01) explicitly carve headless
     paths out of the grant redesign, but Phase 54's own goal text ("a record is enriched once")
     doesn't name an exception the way D-1.1-01 does.
   - Recommendation: the planner should ask the operator directly and record the answer as a
     decision, rather than silently including or excluding it.

2. **Does the contacts review-flag fix need a new decision verb, or does `approve` do?**
   - What we know: the write path, the gate, and the node graph are unchanged either way; only
     `reviewDecision.js`'s contacts branch and two named test assertions change.
   - What's unclear: whether reusing `approve` for a semantically different action (acknowledge
     vs. promote) will confuse an operator reading the review-triage skill's wording later.
   - Recommendation: surface both options to the operator with the one-sentence tradeoff above;
     either is a small, well-bounded change.

## Environment Availability

Not applicable in the usual sense — this phase adds no new external dependency. Every tool it
needs (n8n Cloud API access, HubSpot API access via the deployed workflow, Anthropic API via the
existing enrichment nodes) is already configured and already used by the code this research
cites. No new credential, service, or CLI is required.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (Python) | pytest (repo-root `.venv/bin/python -m pytest`) |
| Framework (n8n node logic) | node's built-in `node --test` |
| Config file | none dedicated — `pytest.ini`/config absent; conftest-based fixtures (`operator-claude-plugin/tests/conftest.py`) |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_report_enrichment.py -q` |
| Full suite command | `.venv/bin/python -m pytest -q` (repo root) `&&` `node --test tests/n8n/*.test.mjs` (glob form — the directory form is broken on node 24, per project memory) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| G-3 (verify already-shipped) | An ordinary armed send runs the waterfall exactly once and writes | unit + live | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k authorize_ungranted_send -q` (existing); live count via `executions_client` (new, small script) | ✅ unit / ❌ live-measurement script, Wave 0 |
| (measurement) | `envelope()`'s `projected_executions` matches a real count for a 1-record and a multi-chunk send | unit + live | new `test_write_grant.py` case comparing `envelope()`'s figure against a scripted `executions_client` count; live confirmation once | ❌ Wave 0 |
| (review-flag contacts) | A contacts `approve` decision clears `lv_enrichment_needs_review` and writes no promoted fields | unit (node) | `node --test tests/n8n/reviewDecisionEndpoint.test.mjs` (existing file, tests to be re-pointed, not created) | ✅ file exists, assertions need editing |
| (rehearsal honesty) | Propose-then-commit and ambiguous-match confirm-then-resend both state the second-pass cost before it is incurred | unit (skill contract) | `test_enrich_skill_contract.py` (existing file, new assertions) | ✅ file exists, assertions to add |

### Sampling Rate
- **Per task commit:** the quick run command above, scoped to the module touched.
- **Per wave merge:** full suite (`pytest -q` + `node --test tests/n8n/*.test.mjs`).
- **Phase gate:** full suite green, plus the one live execution-count measurement and the one
  live contacts-review-clear proof (both are `checkpoint:human-verify`-shaped, mirroring this
  repo's established pattern for anything touching a real n8n execution or a real HubSpot
  write).

### Wave 0 Gaps
- [ ] A small script (or extension of `scheduled_arm.py`'s pattern) that counts n8n executions
      for a workflow id within a time window — covers the measurement requirement.
- [ ] `reviewDecisionEndpoint.test.mjs` lines 225 and 654 (and their surrounding assertions) —
      need deliberate re-pointing once the contacts-`approve` behavior changes, with the
      decision and date recorded in the test file per this repo's established discipline.
- [ ] `test_enrich_skill_contract.py` — new assertions for the propose-mode and ambiguous-match
      cost disclosures.

*(No framework install needed — both suites already run in this repo.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V4 Access Control | yes | Record-scoped allowlist (`_writeSafetyAllows`, `write_grant.covers`) — already the dominant control in this codebase; this phase must not widen it (see Pitfall 1: a re-implementation risks a second, divergent scope check) |
| V5 Input Validation | yes | `_ALLOWLIST_VALUE_RE` charset enforcement on allowlist values (`n8n_arming.py:71`) — unaffected by this phase, cited for completeness since the allowlist is central to §2 |
| V7 Error Handling / Logging | yes | `ArmingRefused`/`DisarmFailed` are never downgraded to a return value (`n8n_arming.py:74-78, 193-200`) — any new measurement code must preserve this: a failed execution-count read must raise or clearly flag "unmeasured," never silently report zero |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A measurement script accidentally arms a live workflow to count executions | Elevation of Privilege | Use only read-only `executions_client`/`n8n_read` calls for the measurement; never call `armed_window` outside a deliberate, disclosed test send |
| A contacts review-clear change accidentally reuses the companies allowlist/gate path incorrectly, clearing a flag without the write actually being allowlisted | Tampering | Reuse the existing `_writeSafetyAllows("review", ...)` check verbatim (already shared, already correct) — do not add a parallel gate for contacts |

## Sources

### Primary (HIGH confidence — read directly this session)
- `operator-claude-plugin/scripts/write_grant.py` — `authorize_send`, `authorize_ungranted_send`,
  `envelope`, `covers`, close-reason constants
- `operator-claude-plugin/scripts/n8n_arming.py` — `arm_for_dispatch`, `armed_window`, `disarm`
- `operator-claude-plugin/scripts/chunking.py` — `dispatch_plan`, `plan_chunks`, `chunk_ceiling`
- `operator-claude-plugin/scripts/dispatch.py` — `dispatch`
- `operator-claude-plugin/scripts/scheduled_arm.py` — `run_scheduled_arm_cycle`
- `scripts/build_cloud_workflows.py` — `WRITE_SAFETY_GATE_JS`, `_writeSafetyAllows`,
  `ENRICH_DECIDE_...` action-assignment code, `build_review_decision_cloud`
- `n8n/code/reviewDecision.js`, `n8n/code/reviewApply.js`
- `operator-claude-plugin/skills/enrich-records/SKILL.md`,
  `operator-claude-plugin/skills/review-triage/SKILL.md`
- `.planning/debug/resolved/walk-write-path-defects.md` (F1/F2/F3 root-cause and fix record)
- `.planning/milestones/v1.1-REQUIREMENTS.md`, `.planning/milestones/v1.1-ROADMAP.md`
- `.planning/phases/53-operator-openable-write-grant/53-CONTEXT.md`, `53-02-SUMMARY.md`,
  `53-04-SUMMARY.md`
- `.planning/STATE.md` (current + `git show b24d7b2`)
- `.planning/WINDOWS.md` (stub ids 25, 26)
- `operator-claude-plugin/CHANGELOG.md` (`[0.18.0]`)
- `operator-claude-plugin/config/operator.local.example.json`
- `operator-claude-plugin/tests/test_report_enrichment.py`,
  `tests/n8n/reviewDecisionEndpoint.test.mjs`

### Secondary (MEDIUM confidence)
- None used beyond primary sources — this research was entirely code-and-docs based, no web
  search was needed for a phase this internally scoped.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — no new stack
- Architecture (two-pass mechanism, F2 fix, ordering constraint): HIGH — every claim traced to
  a specific file:line read this session
- Contact review-flag lane: HIGH — root cause and fix shape both traced to specific lines;
  MEDIUM only on the verb-naming question, which is explicitly a scoping decision, not a
  technical unknown
- Cost measurement feasibility: HIGH on executions/credits (existing read paths cited), LOW on
  Anthropic-dollar "measurement" being achievable without new instrumentation (stated as a
  finding, not softened)

**Research date:** 2026-08-26
**Valid until:** short — this phase sits directly on top of Phase 53's last-24-hours fixes
(F1/F2/F3) and Phase 58's close (2026-08-26); re-verify against `git log` before planning if more
than a few days pass, since this repo's own pattern is same-day fixes discovered mid-walk.
