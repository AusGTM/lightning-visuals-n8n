---
status: complete
phase: 60-review-lane-authority
source: [60-VERIFICATION.md "Human Verification Required" items 1-2, 60-VALIDATION.md § Manual-Only Verifications]
started: 2026-09-03T08:20:00Z
updated: 2026-09-03T11:08:41Z
---

## Current Test

[testing complete]

## Tests

### 1. An end-to-end review approve under a real grant actually writes to HubSpot
expected: |
  Open a write grant scoped to ONE real flagged HubSpot record, approve it through the
  review-triage skill, and confirm via an INDEPENDENT re-read
  (`review_decision.verify_decision`'s post-PATCH refetch) that the approved fields hold on
  the live record. The record's fields must match the previewed `would_write` patch —
  confirmed by re-fetching from HubSpot, never by trusting the POST response.
result: pass
resolved_on: second run, 2026-09-03, after the G-60-1 fix shipped
evidence: |
  **Re-run 2026-09-03 after commit `2d1c881`, on a second real record — `verified`.**

  The Alice Springs Turf Club, `9604787229`, run_id `8ce8dde4b82a477caea16b691d29c305`,
  operator-authorized grant (`lanes=["review"]`, one record id, `allow_create=false`,
  `providers=[]`), operator reason "UAT Alice Springs Turf Club is target company, but not
  named account". Deliberately the same shape as the first walk — one review reason, one
  business field — so the only meaningful variable was the fixed code.

  Predicted before the run, in writing: `verified`. Actual:

      [8] VERDICT status=verified
          message: Confirmed: the record was re-read after the write and all 8 field(s)
                   hold the approved values.

  All 8 keys, including the two that produced the false `failed` this morning. Three
  independent confirmations again, none of them the POST status code: the companies review
  queue dropped 18 → 17 with the record absent, a fresh `preview_decision` now answers
  `not_flagged`, and the backend's post-PATCH refetch shows `lv_produces_content="true"`.

  This discharges the residual recorded under "Gap closure" below: a real approve has now
  been observed reporting `verified` under the fixed code. The n8n side was byte-unchanged
  between the two walks (`git diff --stat` over `n8n/` and `scripts/build_cloud_workflows.py`
  across every commit since the first walk is empty), so the fixed client is the only
  difference between `failed` and `verified`.

  **What this re-run did NOT exercise, stated so it is not mistaken for proven:**
    - `lv_enrichment_reviewed_by`, the fourth unpinnable key. The operator declined to stamp
      a name, so preview and submit both carried `"operator (unnamed)"` and the key matched
      on both sides. It is excluded by the fix and unit-tested, but no live approve has yet
      had preview and submit disagree on it.
    - **G-60-2's fix.** The in-window armed verification in this walk re-used the ORIGINAL
      invocation (no `--armed-workflow`), so it reported `armed FAIL` exactly as it did on
      the first walk — the pre-fix behaviour, not a regression. The new scoped expectation
      shipped in `408ccf5` was not run live. It is unit-tested and the verifier read the
      shipped logic directly, but proving it live needs an arm-only window (no decision
      submitted, so no HubSpot write) and was not done.

first_run_result: issue
first_run_reported: |
  The write LANDED and is independently confirmed — but the phase's own prescribed
  verification call reported `failed` on it, so the test's stated expectation ("the
  record's fields match the previewed `would_write` patch") is literally not met.

  Walk executed 2026-09-03, run_id `56b827c6574b42b4be3beb6ba08e884e`, operator-authorized
  grant (`lanes=["review"]`, `record_ids=["9604738976"]`, `allow_create=false`,
  `providers=[]`), operator reason "UAT Bunbury is target company, but not named account".

  What landed (three independent confirmations, none of them the POST status code):
    - backend post-PATCH refetch (`verified_properties`): `lv_produces_content="true"`,
      `lv_enrichment_needs_review="false"`, review reason and candidate JSON cleared
    - endpoint outcome `applied`, message "applied 1 field(s) as a human decision:
      lv_produces_content"
    - **separate later requests on a fresh connection**: the companies review queue dropped
      19 → 18 rows with `9604738976` absent, and a fresh `preview_decision` on that id now
      answers `not_flagged` (it answered `applied` with an 8-key patch before the walk)

  What failed: `verify_decision(preview["would_write"], response)` → `status: failed`,
  "The backend reported `applied`, but re-reading the record shows 2 field(s) did not take
  the approved value: lv_enrichment_provenance, lv_enrichment_reviewed_at."
first_run_severity: major

### 2. No stuck-open review authorization survives the run
expected: |
  After the armed batch above, `scripts/verify_live_write_safety.py --expectation disarmed`
  against the deployed review workflow reports `disarmed PASS` — no stuck-open
  `ALLOW_HUBSPOT_REVIEW_WRITES` survives.
result: pass
evidence: |
  Two independent observations agree.

  1. The context manager's own `window.disarm_result` on block exit:
     `{"outcome": "disarmed", "workflow_id": "WBJwoZOo63wzeP69",
       "workflow_name": "LV Review Decision (Cloud)",
       "observed": {"ALLOW_HUBSPOT_REVIEW_WRITES": "false",
                    "ALLOW_HUBSPOT_RECORD_WRITES": "false", "ALLOW_HUBSPOT_CREATE": "false",
                    "TEST_RECORD_IDS": "", "TEST_RECORD_DOMAINS": ""}}`

  2. A separate process re-reading the live instance afterwards:
     `verify_live_write_safety.py --expectation disarmed` → `VERDICT: disarmed PASS`,
     5 workflows / 15 declaring nodes, all three `LV Review Decision (Cloud)` gate nodes
     reading `ALLOW_HUBSPOT_REVIEW_WRITES='false'` with both allowlists empty.

  Note the walk deliberately ran arm → submit → verify → disarm inside ONE process. The
  `armed_review_window` disarm guarantee only holds within a single process, so splitting
  the walk across conversation turns would have risked creating exactly the stuck-open
  state this test detects.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Session note — why the FIRST session prepped rather than ran

> **Superseded 2026-09-03 by the second session, which ran the walk.** The paragraphs below
> describe the session that OPENED this file; its closing statement ("nothing was armed") is
> true of that session only. The walk was executed in a later session — see the test results
> and the run account above.

This UAT was opened 2026-09-03 in a session already ~93% through its context window. The
walk was deliberately NOT started, and the reason is test 2 itself.

Test 1 requires opening a real armed write window against production portal 22617666. The
repo's standing discipline is that an armed window is opened, used, and DISARMED inside one
session, with the disarm independently re-read. A session that exhausts its context
mid-window cannot complete that disarm — which would leave a stuck-open
`ALLOW_HUBSPOT_REVIEW_WRITES` on a live portal. That is precisely the failure state test 2
exists to detect. Running out of room mid-walk would not just fail the test; it would CREATE
the condition under test.

Nothing was armed. No HubSpot write, no n8n deploy, no provider call was made by this
session — the same statement all four phase-60 plan summaries make.

## Preconditions for the armed walk (all read-only, do these first)

1. Baseline the gate BEFORE arming, not only after:
   `scripts/verify_live_write_safety.py --expectation disarmed` should already report
   `disarmed PASS`. If it does not, the portal is in an unexpected state and the walk must
   not start — investigate the stuck flag first.
2. Identify ONE real flagged record (`lv_enrichment_needs_review = true`) and pin its id.
   Scope the grant to exactly that id; assert the allowlist is non-empty and is exactly that
   id before trusting the armed state (the 49-W2 lesson).
3. Capture the previewed `would_write` patch BEFORE approving — test 1 compares against it.
4. Confirm the committed n8n JSON matches the deployed instance. Standing caveat from
   CLAUDE.md §13.0.2: Phase 62 regenerated six workflows and committed them WITHOUT
   deploying, so committed JSON may be ahead of what is running.

## Precondition results (discharged 2026-09-03, read-only — nothing armed)

1. **Baseline gate state — PASS.** `scripts/verify_live_write_safety.py --expectation
   disarmed` (creds injected in-process from `operator.local.json`, never through a shell
   arg): `coverage: 5 workflow(s) fetched, 15 declaring node(s) found` →
   `VERDICT: disarmed PASS`. All three `Review*` nodes in `LV Review Decision (Cloud)` read
   `ALLOW_HUBSPOT_REVIEW_WRITES='false'`, `TEST_RECORD_IDS=''`, `TEST_RECORD_DOMAINS=''`.
   `ALLOW_SJ3_DRAIN_WRITES='true'` across 14 nodes, as D-05 requires.

2. **Record pinned.** `review_queue.fetch_queue` — companies `available=true, total=19`;
   contacts `available=true, total=0`. Contacts hold nothing, so the walk is necessarily a
   company (which is what test 1 wants: a contacts approve hits `no_candidate` and promotes
   nothing). Candidate proposed to the operator: **Bunbury Turf Club, `9604738976`,
   `bunburyturfclub.com.au`** — one review reason (`lv_produces_content: Best confidence 65
   below threshold 85.`), so the patch is small enough to read in full.

3. **`would_write` captured BEFORE any arming.** `review_decision.preview_decision(...,
   "approve")` returned `available=true, outcome=applied` with an 8-key patch. Preview is a
   dry run and is deliberately ungated; nothing was written.

   ```
   lv_produces_content                 = true          ← the only business-data field
   lv_enrichment_needs_review          = false
   lv_enrichment_review_approved       = false
   lv_enrichment_review_reason         = ""
   lv_enrichment_review_candidate_json = ""
   lv_enrichment_reviewed_at           = 2026-09-03T09:55:50.209Z
   lv_enrichment_reviewed_by           = "operator (unnamed)"
   lv_enrichment_provenance            = {…887 chars — the audit-trail entry}
   ```

   Test 1's field-match assertion is against this captured patch, re-read from the live
   record after the write.

4. **Deployed vs committed — PASS, no drift on this lane.** Fetched `LV Review Decision
   (Cloud)` live and hashed every node's `jsCode`/`jsonBody` against
   `n8n/wf_review_decision_cloud.json`: **26 nodes each side, zero differing bodies.** This
   matters because phase 60 itself changed that file (`9d514a7 fix(60-04): correct the
   review-decision not_allowlisted refusal message`) and phase 62 changed it again
   (`050b8a3`) — the §13.0.2 caveat predicted the running instance might be behind both.
   Empirically it is not: the deployed artifact is the one this phase built, so the walk
   tests the right thing.

## Gaps

- gap_id: G-60-1
  truth: "An approved review decision's landed fields match the previewed `would_write` patch, confirmed by an independent re-read"
  status: resolved
  resolved_by: 60-05-PLAN.md
  resolved_at: 2026-09-03
  reason: |
    User reported: the write landed, but `verify_decision` returned `failed` on it.
    `review_decision.verify_decision(intended, response)` compares the PREVIEW's
    `would_write` map key-for-key against the post-PATCH refetch. Two of the eight keys are
    minted by the backend AT SUBMIT TIME and therefore can never match a map captured at
    preview time:
      - `lv_enrichment_reviewed_at` — preview `2026-09-03T09:55:50.209Z`,
        submit `2026-09-03T10:00:07.118Z`
      - `lv_enrichment_provenance` — the same submit timestamp is embedded inside the blob
        (`"lv_produces_content":{...,"verified_at":"2026-09-03T10:00:07.118Z"}`)
    The response's OWN `would_write` (submit-time) does match `verified_properties`
    exactly; only the preview-vs-refetch comparison the skill prescribes diverges.
  severity: major
  test: 1
  root_cause: |
    `verify_decision`'s contract (its docstring, `operator-claude-plugin/scripts/review_decision.py:346-366`)
    defines `intended` as "the `would_write` map the operator approved" — i.e. the preview's
    — and compares every approved key against the refetch with no allowance for
    backend-minted, time-varying fields. review-triage SKILL.md step 8 prescribes exactly
    `verify_decision(preview["would_write"], response)`, and step 8 further instructs the
    agent to tell the operator a `failed` means the change is "not confirmed" and to "never
    soften a `failed` into 'probably fine'". So the documented happy path produces a
    false alarm on EVERY successful approve, and the skill's own wording forbids explaining
    it away. This was unreachable before today: no live review approve had ever run (all
    four phase-60 summaries state nothing was armed and nothing was written), so only a
    live walk could surface it.
  artifacts:
    - path: "operator-claude-plugin/scripts/review_decision.py"
      issue: "verify_decision compares preview-time `intended` against submit-time refetch; no exclusion for backend-minted time-varying keys (`lv_enrichment_reviewed_at`, and the timestamp embedded in `lv_enrichment_provenance`)"
    - path: "operator-claude-plugin/skills/review-triage/SKILL.md"
      issue: "step 8 prescribes `verify_decision(preview[\"would_write\"], response)` and forbids softening the resulting false `failed`"
  missing:
    - "Decide the intended semantics: compare against the RESPONSE's `would_write` (what the backend actually set) rather than the preview's, or exclude backend-minted time-varying keys from the comparison — the operator-facing promise is that the approved BUSINESS fields landed, not that a timestamp was predicted in advance"
    - "Whichever is chosen, the comparison must still fail loudly if a business field (e.g. `lv_produces_content`) diverges — the fix must not weaken the check into a status-code trust"
    - "A regression test that walks preview -> submit -> verify with DIFFERENT preview and submit timestamps; today's stub-transport tests evidently reuse one timestamp and so cannot catch this"
  debug_session: ""

- gap_id: G-60-2
  truth: "An operator can independently confirm, while a review batch window is open, that the live allowlist contains exactly the granted record id (the 49-W2 lesson: a count check is not a membership check)"
  status: resolved
  resolved_by: 60-05-PLAN.md
  resolved_at: 2026-09-03
  reason: |
    User reported: no working tool exists for this on a per-lane window.
    `verify_live_write_safety.py --expectation armed --allowlist 9604738976 --expect-armed
    ALLOW_HUBSPOT_REVIEW_WRITES`, run from inside a genuinely-open and genuinely-working
    review batch window, returned `VERDICT: armed FAIL`.
  severity: minor
  test: 1
  root_cause: |
    The `armed` expectation is global by construction. Its own docstring: "the named flags
    must read enabled WHEREVER THEY ARE DECLARED". `ALLOW_HUBSPOT_REVIEW_WRITES` is
    declared by 12 nodes across 4 workflows, but `armed_review_window` arms exactly ONE
    workflow (`LV Review Decision (Cloud)`, `WBJwoZOo63wzeP69`) — which is the correct,
    tightly-scoped behaviour. So every declaring node in the other three workflows reads
    `false` and each one is reported as a FAIL. The failure is the verifier's model of what
    "armed" means, not the arming.
    Note the DISARMED direction is unaffected and worked correctly in both directions
    today — the global model is right for "nothing is armed anywhere" and wrong for
    "exactly this workflow is armed". Deliberately no workflow-selection argument exists
    (27-04 D-07: an operator who can narrow the scan can blind it), so the fix is not
    simply adding a `--workflow` flag.
  artifacts:
    - path: "scripts/verify_live_write_safety.py"
      issue: "`--expectation armed` requires the named flags true on every declaring node instance across all workflows; cannot express a correctly-scoped single-workflow batch window"
  missing:
    - "An armed expectation that takes the ARMED WORKFLOW as the assertion (this workflow's declaring nodes must read the named flags true with the allowlist exactly equal to VALUE) while keeping the global part of the check intact (every OTHER workflow must still read fully disarmed) — so scoping the assertion cannot blind the scan, which is what D-07 was protecting"
    - "Wire it into review-triage SKILL.md step 4 so an operator arming a sitting can pin the allowlist membership before the first decision"
  debug_session: ""

## Run account (D-60-08) — what this walk actually wrote

run_id: `56b827c6574b42b4be3beb6ba08e884e`
`written_records.load(path=written_records_path(run_id))` — this run's own artifact, not the
path-less load that would fold in every previous run:

```json
[{"chunk_index": 0, "object_type": "companies", "action": "review_approve",
  "hs_object_id": "9604738976", "outcome": "write_attempted",
  "reason": null, "row_id": null, "association": null}]
```

One record, one review approve. No provider call, no record creation, no contact touched.

Cost, measured against the projection the grant disclosed: projected 2 n8n executions;
the sitting's own traffic was 1 preview + 1 submit on the review endpoint plus the
read-only queue and safety reads. Provider credits 0, as projected for a review lane.

## Verification-tooling notes carried out of this walk

Neither of these blocks the phase; both are recorded because the walk is the only thing
that could have found them.

- **`--expectation armed` is unusable for a per-lane window.** See gap G-60-2. The
  `disarmed` direction — the one test 2 depends on and the one that matters for a
  stuck-open gate — worked correctly in both directions today.
- **An `armed_review_window` cannot span conversation turns.** Its disarm guarantee is a
  Python context manager, so the whole arm → submit → verify → disarm sequence has to run
  inside one process. The operator's consent therefore has to be taken BEFORE the sequence
  starts, on a `would_write` captured by an ungated preview — which is exactly what the
  design supports, but it means the skill's step 4-8 loop ("offer the next record — still
  inside the same batch window") is only reachable by an agent that can hold one process
  open across several operator answers. A one-record sitting, like this one, is unaffected.

## Gap closure (2026-09-03)

Both gaps closed by `60-05-PLAN.md` (`/gsd-plan-phase 60 --gaps --chain` →
`/gsd-execute-phase 60 --gaps-only`). Commits `2d1c881` (G-60-1), `408ccf5` (G-60-2),
`020148b` (skill + release 0.38.0), `5c5f270` (summary).

**G-60-1 — the RED was observed, not claimed.** Before the fix, the two mandated tests failed
with `AssertionError: assert 'failed' == 'verified'` — the live walk's bug reproduced in a
unit test, which is the thing that had never existed. The fix is a two-leg comparison: leg 1
proves intent stability (the preview's map against the backend's own submit-time `would_write`,
over the UNION of both key sets so a key the backend added at submit time cannot hide), leg 2
proves landing (unchanged in key count and in authority — the post-PATCH refetch remains the
sole judge of whether the write landed).

**The exclusion set is four keys, not the two this walk exposed.** `lv_enrichment_reviewed_at`
and `lv_enrichment_provenance` are what failed here. Planning found two more that would have
re-broken the fix on a later sitting: `lv_contact_enrichment_provenance` (contacts select a
different provenance property, `n8n/code/reviewDecision.js:87`) and `lv_enrichment_reviewed_by`
(`preview_decision` accepts no reviewed-by argument, so a preview always carries
`"operator (unnamed)"` while a submit carries the operator's real label — this walk used the
default, which is exactly why it stayed invisible). The concept is therefore "keys a
preview-time capture cannot pin", not "backend-minted": three are clock-derived, one is an
API-shape gap.

**Zero n8n changes, verified rather than assumed** — both diverging values are minted
per-request inside the backend (`reviewApply.js:124`, `reviewDecision.js:150-156`, `:271`), so
two timestamps across two requests is the backend behaving correctly and the client was the
only place the comparison could be fixed. Nothing armed, nothing deployed, no HubSpot request,
no provider credit.

Regression after the fix: 867 node tests, 1727 root pytest (149 skipped), 2283 plugin tests
(5 skipped) — all passing.

### Residual — one cheap live confirmation, deliberately NOT claimed here

Nobody has yet watched a REAL approve report `verified` under the fixed code. The fix is proven
against a unit test built from this walk's exact observed shape (different preview and submit
timestamps, different reviewed-by label), which is strong evidence — but it is not the same as
a live observation, and this repo's standing rule is that live behaviour earns live proof.

This does not need its own armed walk. 18 companies remain in the review queue, so the next
ordinary triage sitting confirms it at zero extra cost: the operator should see `verified`
where this walk saw `failed`. Recording it so the distinction is not lost, not to gate anything.

## Second run account — the re-test that closed test 1

run_id: `8ce8dde4b82a477caea16b691d29c305`

```json
[{"chunk_index": 0, "object_type": "companies", "action": "review_approve",
  "hs_object_id": "9604787229", "outcome": "write_attempted",
  "reason": null, "row_id": null, "association": null}]
```

Test 2 was re-confirmed on this run too: `window.disarm_result` reported `disarmed` with all
three review flags false and both allowlists empty, and a separate process afterwards returned
`VERDICT: disarmed PASS`. Two armed windows have now been opened and closed on this portal in
one day with no residue after either.

Two real records were approved across the two walks — `9604738976` (Bunbury Turf Club) and
`9604787229` (The Alice Springs Turf Club). Both were genuine review decisions the queue was
holding, not throwaway data; both promoted `lv_produces_content = true` with the operator's
reason recorded in the provenance blob. Review queue: 19 → 17.
