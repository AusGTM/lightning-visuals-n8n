---
created: 2026-09-17T00:00:00.000Z
updated: 2026-09-17
title: verify_decision reports a successful review approve as failed when a booleancheckbox field is approved to false
area: operator-plugin
severity: medium
kind: defect
evidence: "Stage E live run (73-UAT.md § Attempt 3, run_id 05f8c46e9aca4e289d23365b969a701b): approving Melbourne Racing Club 9604614548 landed every business field correctly (industry, lv_org_type, lv_content_type, lv_country_region_normalized all verified), but verify_decision flagged lv_is_hardware_vendor and lv_is_gambling_operator as 'did not take the approved value' because HubSpot returns an unchecked booleancheckbox as empty string on re-read, not the literal string 'false'"
files:
  - operator-claude-plugin/scripts/review_decision.py
---

## Found during

Phase 73 plan 07 Task 3 (operator gate), Stage E of stress attempt 3, 2026-09-17/18.

## What happened

`verify_decision` (`operator-claude-plugin/scripts/review_decision.py:366`) compares the
intended approved value against a re-read of the record. For a `booleancheckbox` HubSpot
property, an approved value of `false` is stored by HubSpot as an EMPTY string on read-back,
not the literal string `"false"` — this is a HubSpot API quirk already documented elsewhere in
this repo (`hubspot-property-api-gotchas` memory: "bools need true/false options; ... both
only fail live"). `verify_decision` does not currently normalize an empty re-read against an
intended `false` as equal, so it reports the field — and by extension the whole approve — as
`failed`, even though the write was correct and no data was lost.

This is a verify-only false negative (false-vs-empty), not a real write failure. The practical
risk is operator trust: a genuinely successful approve reads as `failed` in the run report, and
an operator who trusts that report may re-attempt or distrust a clean write.

## Fix (not designed here)

In `verify_decision`'s comparison for `booleancheckbox`-typed fields (or more generally,
wherever it treats a re-read of empty-string as a mismatch), treat an intended `false` against
a re-read empty string as a match. Needs a regression test pinning the MRC-shaped case:
approve `lv_is_hardware_vendor=false` / `lv_is_gambling_operator=false`, re-read returns `""`
for both, and `verify_decision` reports the overall decision as verified/applied, not failed.
