---
created: 2026-09-17T00:00:00.000Z
updated: 2026-09-17
title: F-E1's exact 2-element-array lv_content_type serialization case was not reproducible live in stress attempt 3
area: n8n-review
severity: info
kind: accepted
evidence: "Stage E live run (73-UAT.md § Attempt 3): no review candidate in the reset portal's queue carried a multi-value lv_content_type array (unknown or scalar everywhere, tied to the F-S2 web-research-fence defect); the multi-checkbox field itself DID land and verify on this run (F-E1 PASS on its field)"
files:
  - n8n/code/reviewApply.js
  - tests/n8n/reviewLoop.test.mjs
---

## Found during

Phase 73 plan 07 Task 3 (operator gate), Stage E of stress attempt 3, 2026-09-17/18.

## Why accepted (won't-fix as a live gap)

D-73-19 forbids engineering a test-only trigger to manufacture a live case the natural data
does not produce, and no review candidate in the reset portal happened to carry a genuine
multi-element `lv_content_type` value in this run (compounded by F-S2's web-research fence
defect leaving most researched companies' `lv_content_type` unknown rather than populated).

The underlying fix (F-E1: `reviewApply()`'s array-serialization join, exercised via the
`Apply Review` node) DID land and verify live for the single-value case, and the
multi-element-array semicolon-join path remains proven by
`tests/n8n/reviewLoop.test.mjs` offline. This is the same category as F-A6 (D-73-19): correct
by construction and by offline test, live-exercised only for the sub-case the reset data
happened to produce. No further action — offline coverage stands as the proof for this case.
