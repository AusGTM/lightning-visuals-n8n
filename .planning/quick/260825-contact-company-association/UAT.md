---
status: diagnosed
phase: quick-260825-contact-company-association
source: [commit ca954c9 (Lusha sandbox + contact research identity), commit b014b69 (ingest association), commit 472ac50 (company name fallback)]
started: 2026-08-25T00:55:00Z
updated: 2026-08-25T01:20:00Z
---

## Current Test

number: 2
name: Lusha contributes again on a contact with an email
expected: |
  Held — superseded by the gaps found in test 1. The write path is blocked for the
  operator (G-2), so further tests through the operator surface cannot reach a write.
awaiting: routing decision (v1.1 planning)

## Tests

### 1. A name-only contact comes back enriched
expected: enriching contact 347569451461 returns jobtitle + seniority + a phone, not an empty result; no HubSpot write occurs while disarmed
result: pass
reported: "enrichment ran (matched by ID, derived jobtitle=CEO, seniority=C-Suite, mobile/phone, persona), but the backend did not PATCH HubSpot because its write window isn't armed"
note: the fix under test is confirmed from the operator's own surface — the same record returned nothing before ca954c9

### 2. Lusha contributes again on a contact with an email
expected: enriching a contact that has an email returns data whose provenance names lusha; no item carries "Cannot access \"prototype\""
result: [pending]
note: partially evidenced by test 1 (the run produced provider data at all, which it could not before), but not isolated to Lusha from the operator surface

### 3. An existing company is matched, never duplicated
expected: enriching "Harness Racing New South Wales" at hrnsw.com.au reports the company as already existing (18756544347) rather than proposing to create it
result: [pending]

### 4. A contact with no resolvable company is held, not landed
expected: uploading a contact whose company is not in HubSpot reports that row held for review with a reason naming the company, and no contact is created
result: [pending]

## Summary

total: 4
passed: 1
issues: 0
pending: 3
skipped: 0

## Gaps

Found during test 1. None are defects in the code under test — all four are the
operator-path design the v1.1 milestone exists to fix, now with live evidence from a real
client-facing UAT rather than a reported impression.

### G-1 — three separate arming surfaces to reach one write (major)

Reaching a single contact write required, in order: (1) the client-side phrase "arm the
enrichment", per turn; (2) the backend `arm_dispatch` proposal plus an explicit yes; (3)
the `ALLOW_N8N_ARM` environment variable. Each was designed independently and each is
defensible alone; nobody had walked all three end to end from the operator's chair.

Operator's words: *"Multiple arming steps - this can be compressed into a single approval
set and there are far too many low level actions that need to be done to get from
enrichment to write into Hubspot."*

Feeds: GRANT-01, GRANT-02.

### G-2 — the write path is unreachable from the operator's surface at all (blocker)

`n8n_arming._arm_gate()` refuses unless `ALLOW_N8N_ARM=true` is set **in the environment
the session runs in**. An operator in Claude Desktop cannot set a shell environment
variable. So the documented operator path — enrich, then arm, then write — terminates in a
refusal that only an admin with terminal access can clear, and the plugin cannot say
otherwise. Every write this client has seen land was landed by an admin from a terminal.

This is not a bug in the gate; the gate is doing what it was built to do. It is a missing
operator-reachable authorization surface, and it makes "one grant at session start"
(v1.1's whole premise) impossible to build on the current mechanism without deciding who
may grant and how that grant is expressed.

Feeds: GRANT-01, GRANT-03, decision 1 (where the grant lives).

### G-3 — arming re-runs the waterfall, so an armed write costs the providers twice (major)

The first dispatch derived everything and returned `write_blocked`. The arm cycle then
**re-sends the same waterfall** for the same record so the derived fields can land. Two
full provider passes per record, one of which is thrown away by design. At one record it is
$0.07 and ~2 credits; at the client's scale it doubles the entire enrichment bill and the
execution count against a 2,500/month plan.

The derived payload already exists in the first execution's `Decide Action` output. A
grant that is opened *before* the run — rather than after a blocked one — removes the
second pass entirely.

Feeds: GRANT-02, RUN-03, RUN-05.

### G-4 — two provider balances read as unknown in the same preview (minor)

`Apollo: unrecognized_response_shape` (known, expected — no credit pool) and, new in this
run, `ZoomInfo: provider_error`. ZoomInfo read 9388 credits successfully 40 minutes
earlier, so this is likely transient. Worth a second look before a large batch: a preview
that cannot confirm headroom on two of three providers is thin cover for an unattended run
that spends against them.

Feeds: RUN-05.
