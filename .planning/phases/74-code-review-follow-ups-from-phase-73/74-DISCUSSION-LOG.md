# Phase 74: Code-review follow-ups from phase 73 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-19
**Phase:** 74-code-review-follow-ups-from-phase-73
**Areas discussed:** Create-error lane convergence (CR-01, WR-07), Error-item shape proof (CR-02), Fixture redaction guard (CR-04), Warning triage + end-of-phase gate

---

## Todo cross-reference

10 keyword matches presented; 2 offered for folding, both folded by the operator:
`2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md` and
`2026-09-17-stage-d-match-chunk-unchecked-rate.md`. The other 8 were reviewed and left pending.

---

## Create-error lane convergence (CR-01, WR-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Real sentinel producer | Code node on the error edge emits one marker per run unconditionally | ✓ |
| Keep drain-only, document | Correct the comment, add the §13.0.3 row, rely on the v1 drain | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Gated sentinel | `_add_starved_lane_sentinel` keyed on zero create-routed rows | ✓ |
| Document the drain | State that Ingest Merge Response is the terminal convergence | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Freeze 12522 + rule + row | Frozen fixture, walker pads index 0 only, fidelity test, §13.0.3 row | ✓ |
| Rule + row only | No new fixture | |
| You decide | | |

**User's choice:** all three recommended options. **Notes:** none.

---

## Error-item shape proof (CR-02, CR-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Stamp only, stay [documented] | `_create_error: true` on the error edge; zero armed executions | ✓ |
| Stamp + one armed duplicate-email create | Freeze the real shape, rebuild the stub | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| All three shapes | Parametrise the stub over the three candidate shapes | |
| Keep one stub, tag UNOBSERVED | Single stub, UNOBSERVED comment, rely on the stamp | ✓ |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Reason names the sub-case | `create_outcome_reason` passes through verbatim | ✓ |
| One generic reason | Single string for both sub-cases | |
| You decide | | |

**User's choice:** stamp only; single stub tagged UNOBSERVED; reason names the sub-case.
**Notes:** the operator chose the smaller test change over the recommended three-shape stub.

---

## Fixture redaction guard (CR-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Re-redact in place | Rewrite the 7 matching fixtures with the widened scrubber | ✓ |
| Exempt by path | Allowlist the 7 legacy files | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Wholesale key replacement | Replace headers/error/request/options/config at any depth, per run | ✓ |
| Whitelist scalars inside error | Keep message/description/httpCode | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Secrets + JWT + bearer | pat-na, Bearer, x-enrichment-secret value, eyJ… bodies | ✓ |
| Review's three only | Authorization, x-enrichment-secret, pat-na | |
| You decide | | |

**User's choice:** all three recommended options. **Notes:** pre-discussion scan found 5 Phase-70
fixtures (3 hits each), `exec_12434` (37) and `exec_12449` (19) matching; 4 frozen workflow bodies
hit only on the header name inside node code.

---

## Warning triage + end-of-phase gate

| Option | Description | Selected |
|--------|-------------|----------|
| Fix all seven | WR-03/04/08/09/10/11/12 each fixed with a test | ✓ |
| Fix operator-truth ones only | WR-04/09/11/12 fixed; WR-03/08/10 accepted | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| In-phase disarmed proof | Deploy `--only wf_contact_ingest_cloud.json`, bounce, one all-update send, freeze | ✓ |
| Stop at regen + suites | D-73-18 precedent, operator deploys later | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Answer MN-01 from frozen runData | Search 12522/12434/12449 for a Merge with two pending runs | ✓ |
| Keep open, reference only | | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Investigate the Stage D bound offline | Parametrise/raise the recovery bound, add a test, surface unchecked_count | ✓ |
| Keep open, trigger unchanged | | |
| You decide | | |

**User's choice:** all four recommended options. **Notes:** none.

---

## Claude's Discretion

- One Code node or two for the D-74-01 producer and the D-74-04 stamp.
- Wording of the UNOBSERVED tag and the §13.0.3 rows.
- Plan/wave grouping around the roadmap's fix order.

## Deferred Ideas

- Armed duplicate-email create to observe the real error-item shape (trigger stays "a real race").
- Deploying any cloud workflow other than the ingest lane.
