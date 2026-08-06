---
status: testing
phase: 40-scoring-engine-remediation-notes
source: [40-VERIFICATION.md]
started: 2026-08-06T23:00:00Z
updated: 2026-08-06T23:00:00Z
---

## Current Test

number: 1
name: Remaining hard vetoes PATCH-proven live (content + hardware-vendor)
expected: |
  Disposable companies exercising the no-content veto and the hardware-vendor veto
  each receive lv_anti_icp_flag="true" (string) with the rubric-correct
  lv_anti_icp_reason via one bounded scheduled_arm.py window.
awaiting: user response

## Tests

### 1. Remaining hard vetoes PATCH-proven live (content + hardware-vendor)
expected: no-content disposable → flag "true" + reason "No broadcast or streaming content"; hardware-vendor disposable → flag "true" + reason "Hardware/AV/LED vendor, not sports-media buyer"; both via a bounded arm window; teardown after.
result: [pending]

### 2. Symmetric clear observed on a real PATCH (F6 regression)
expected: a vetoed disposable whose veto condition is then corrected (e.g. region set back to AU) receives lv_anti_icp_flag="false" and cleared/updated reason on the next armed enrichment run — no one-way latch.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
