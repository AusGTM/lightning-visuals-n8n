---
created: 2026-09-17T00:00:00.000Z
updated: 2026-09-17
title: A no-provider (CSV-only) ingest never promotes mobilephone / lv_linkedin_url / hs_linkedin_url even into a blank field, because csv-sourced confidence (80) sits below their fill_blank_only threshold (85)
area: field-policy
severity: low
kind: design
decision_needed: "whether a CSV-sourced value written into a currently-BLANK contact field should be allowed to clear the field's fill_blank_only confidence threshold (i.e. blank-field promotion should not require the same confidence bar as an overwrite), or whether the RUNBOOK's Stage-A 'Mobile + LinkedIn land' expectation should instead be corrected to require a provider pass"
files:
  - config/field_policy.yaml
  - tests/stress-tests/RUNBOOK.md
---

## Found during

Phase 73 plan 07 Task 3 (operator gate), Stage A of stress attempt 3, 2026-09-17/18.

## What happened

On a pure CSV ingest with no provider waterfall run (Stage A, `contact-upload` with no
enrichment), every field arrives with `source=csv, confidence=80`. `mobilephone` and
`lv_linkedin_url`/`hs_linkedin_url` are `fill_blank_only` at `min_confidence: 85` in
`config/field_policy.yaml`. 80 < 85, so both fields are held for review rather than promoted
— even when the target field is currently blank and there is no existing value at risk of
being clobbered. This is long-standing `field_policy` behaviour, not a Phase 73 regression:
the Phase 72 live proof of these fields used a provider-sourced value at confidence 85, never
a bare CSV value.

`tests/stress-tests/RUNBOOK.md`'s Stage A spot-check currently implies "Mobile + LinkedIn
land" is a first-pass CSV-only result; live behaviour on a no-provider run is that they are
held for review, not promoted, until a provider pass (Stage D) runs.

## Options

1. Lower or special-case the confidence bar for a `fill_blank_only` promotion into a
   currently-blank field specifically for `source=csv` (the risk of overwriting a
   higher-confidence value doesn't exist when the field starts blank).
2. Leave `field_policy` unchanged and correct the RUNBOOK's Stage A expectation to say these
   two fields land only after a provider/enrichment pass (Stage D), not on the raw CSV ingest.

Not decided here — needs an operator ruling before either the policy or the RUNBOOK text
changes.
