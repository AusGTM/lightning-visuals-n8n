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

## Gaps

<!-- none yet — no test has been run -->
