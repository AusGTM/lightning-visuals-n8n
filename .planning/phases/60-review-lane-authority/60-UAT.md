---
status: partial
phase: 60-review-lane-authority
source: [60-VERIFICATION.md "Human Verification Required" items 1-2, 60-VALIDATION.md § Manual-Only Verifications]
started: 2026-09-03T08:20:00Z
updated: 2026-09-03T08:20:00Z
---

## Current Test

[testing paused — 2 items outstanding, both requiring an armed live window not yet opened]

## Tests

### 1. An end-to-end review approve under a real grant actually writes to HubSpot
expected: |
  Open a write grant scoped to ONE real flagged HubSpot record, approve it through the
  review-triage skill, and confirm via an INDEPENDENT re-read
  (`review_decision.verify_decision`'s post-PATCH refetch) that the approved fields hold on
  the live record. The record's fields must match the previewed `would_write` patch —
  confirmed by re-fetching from HubSpot, never by trusting the POST response.
result: [pending]
blocked_by: armed-window-not-opened

### 2. No stuck-open review authorization survives the run
expected: |
  After the armed batch above, `scripts/verify_live_write_safety.py --expectation disarmed`
  against the deployed review workflow reports `disarmed PASS` — no stuck-open
  `ALLOW_HUBSPOT_REVIEW_WRITES` survives.
result: [pending]
blocked_by: depends-on-test-1

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Session note — why this session prepped rather than ran

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

<!-- none yet — no test has been run -->
