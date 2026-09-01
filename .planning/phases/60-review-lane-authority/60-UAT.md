---
status: testing
phase: 60-review-lane-authority
source: [60-VERIFICATION.md]
started: 2026-09-01T08:10:00Z
updated: 2026-09-01T08:10:00Z
---

## Current Test

number: 1
name: Open a grant-scoped review approval on one real flagged HubSpot record and confirm the write held
expected: |
  The record's fields match the previewed would_write patch after the write, confirmed by
  re-fetching from HubSpot (not by trusting the POST response).
awaiting: user response

## Tests

### 1. Open a grant-scoped review approval on one real flagged HubSpot record and confirm the write held
expected: Open a write grant scoped to one real flagged HubSpot record, approve it through the review-triage skill, and confirm via an independent re-read (verify_decision's post-PATCH refetch) that the approved fields hold on the live record. The record's fields match the previewed would_write patch after the write, confirmed by re-fetching from HubSpot, not by trusting the POST response.
why_human: Requires a live, armed n8n workflow, a real flagged record, and a real HubSpot write — outside an automated suite's authority. This phase's own arming gates are the subject under test, so they cannot self-certify (60-VALIDATION.md § Manual-Only Verifications).
result: [pending]

### 2. Confirm no stuck-open review flag survives an armed review batch
expected: After any armed review batch (the supervised walk above, or any other live review session), run `verify_live_write_safety.py --expectation disarmed` against the deployed review workflow. It reports "disarmed PASS" — no stuck-open `ALLOW_HUBSPOT_REVIEW_WRITES` survives the run.
why_human: Requires reading live deployed n8n workflow state after a real batch; cannot be simulated by the stub-transport test suite (60-VALIDATION.md § Manual-Only Verifications).
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
