---
status: resolved
phase: 40-scoring-engine-remediation-notes
source: [40-VERIFICATION.md]
started: 2026-08-06T23:00:00Z
updated: 2026-08-07T03:33:30Z
---

## Current Test

None — both tests resolved.

## Tests

### 1. Remaining hard vetoes PATCH-proven live (content + hardware-vendor)
expected: no-content disposable → flag "true" + reason "No broadcast or streaming content"; hardware-vendor disposable → flag "true" + reason "Hardware/AV/LED vendor, not sports-media buyer"; both via a bounded arm window; teardown after.
result: passed. Live-proven on disposables D1 (`280205875649`, no-content) and D2 (`280234186174`, hardware-vendor), 2026-08-07. Cycle 1 (pre-fix) initially proved the flag and BOTH correct reasons fired, but with a spurious "Non-ANZ geography" prefix on true-AU records — diagnosed live to a missing `lv_country_region_normalized` property in the company existingRecord fetch list (`scripts/build_cloud_workflows.py` `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`), fixed, deployed, and re-proven clean in Cycle 2: D1 `lv_anti_icp_flag="true"` `lv_anti_icp_reason="No broadcast or streaming content"` (no prefix); D2 `lv_anti_icp_flag="true"` `lv_anti_icp_reason="Hardware/AV/LED vendor, not sports-media buyer"` (no prefix). Both independently re-read via a fresh GET. Full trail: `VETO-WRITE-EVIDENCE.md`.

### 2. Symmetric clear observed on a real PATCH (F6 regression)
expected: a vetoed disposable whose veto condition is then corrected (e.g. region set back to AU) receives lv_anti_icp_flag="false" and cleared/updated reason on the next armed enrichment run — no one-way latch.
result: passed. Disposable D3 (`280234186175`) created as US (non-ANZ, veto fires `lv_anti_icp_flag="true"` `lv_anti_icp_reason="Non-ANZ geography"` in Cycle 1), corrected to `lv_country_region_normalized="AU"` and re-queued, then dispatched again in Cycle 2 (post-fix, same armed window as tests 1's re-proof — one arm cycle covered both). Result, independently re-read via a fresh GET: `lv_anti_icp_flag="false"`, `lv_anti_icp_reason=""`, and `lv_icp_tier` moved off `D` to `C` (VETO-03 corroboration, same event). No one-way latch. Full trail: `VETO-WRITE-EVIDENCE.md`.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

None. Both items resolved with live evidence. One incidental bug was found and fixed
along the way (not a gap in these two tests' own scope, but load-bearing for them):
`operator-claude-plugin/scripts/scheduled_arm.py` dispatched an SJ-3-matched batch as a
single webhook POST regardless of size, which the backend refuses once it exceeds
`ENRICH_MAX_LIST_RECORDS`/`max_records_per_chunk` (2) — fixed by chunking dispatch inside
one armed window (commit `bf9cecd`). See `VETO-WRITE-EVIDENCE.md` for both fixes' full
diagnosis and evidence trail.
