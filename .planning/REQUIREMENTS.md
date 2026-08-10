# Requirements — Milestone v0.8: Execution Budget Safety

Defined 2026-08-10. Source evidence: the live n8n execution log read on 2026-08-09/10 (flat
253 executions/hour over 10 hours, ~182,000/month run rate against a **2,500/month plan**),
the 61 companies stuck at `lv_enrichment_requested=true`, and the API probe showing n8n
exposes no usage/quota endpoint to an API key. Prior milestone: v0.7 HubSpot Scoring Engine
Remediation (shipped 2026-08-08, 16/16).

**The defect this milestone exists to make impossible:** SJ-3 dispatched one sub-execution per
flagged record every tick. The step that clears the trigger flag is a HubSpot write, the write
gate was closed (its correct resting state), so the flag never cleared and the same 61 records
re-dispatched forever. The system spent its entire monthly allowance ~73 times over on work it
was structurally incapable of completing, and nobody found out until a human read the billing
page at 80%.

## v0.8 Requirements

### Gate Check — do not start work that cannot finish

- [x] **GATE-01**: When the enrichment write gate is closed, an SJ-3 tick dispatches **zero**
  records. The tick costs 1 execution, not 1 + N.

- [x] **GATE-02**: A gate-closed tick reports a named, non-error outcome that an operator can
  distinguish from "found nothing to do". Disarmed is the normal resting state, so this path
  must not be modelled as a failure.

- [x] **GATE-03**: When the gate is open, dispatch behaviour is unchanged — a test fails if the
  gate check swallows or reorders dispatches inside a legitimately armed window.

### Queue Drain — a stuck flag cannot survive

- [x] **DRAIN-01**: On a gate-closed tick, SJ-3 clears `lv_enrichment_requested` on every record
  it declined to dispatch, so the following tick finds none. The queue drains instead of
  accumulating.

- [x] **DRAIN-02**: The drain write path is narrow by construction — its patch may contain
  only the keys `lv_enrichment_requested` and `lv_enrichment_status`, with only the values
  `"false"` and `"skipped"` respectively, on records it just declined. Clearing a trigger flag
  is not a data write, but it must not become a hole in the data write gate.
  <!-- AMENDED 2026-08-10, operator decision. Originally read "exactly
  `lv_enrichment_requested=\"false\"` and nothing else", which Phase 44 research proved
  incompatible with DRAIN-03/D-08: the same write is what stamps the provenance that makes a
  drained record distinguishable. Narrowness is now enforced by an explicit key+value
  ALLOWLIST rather than a key count of one — same intent, and DRAIN-03 becomes achievable.
  `skipped` is an existing option on the closed `lv_enrichment_status` enumeration
  (config/hubspot_properties.yaml:308-337) and is written by nothing else in the pipeline, so
  no property migration is needed. -->

- [x] **DRAIN-03**: A record whose flag is cleared by the drain is distinguishable afterwards
  from one that was enriched — a drained record was never processed, and nothing downstream may
  read the cleared flag as evidence that it was.

### Dispatch Cap — one tick cannot spend the month

- [x] **CAP-01**: A single tick dispatches at most a cap **derived from the plan allowance and
  the tick cadence**, not a hardcoded constant, so the bound cannot silently drift out of
  budget when a trigger is re-timed.

- [x] **CAP-02**: When a tick caps, it logs how many records it found and how many it
  dispatched. Silent truncation reads as "processed everything" and is forbidden.

- [x] **CAP-03**: A test fails if the shipped schedule's computed monthly execution floor
  exceeds a configured share of the plan allowance. The v0.7 schedule was 2.6x over the entire
  allowance while doing no work, and nothing in the repo said so.

### Burn-Rate Alarm — the system reports it, not the billing page

- [ ] **ALARM-01**: The sweep fires a notice when the sampled execution rate projects to exhaust
  the plan allowance for the current billing period.

- [ ] **ALARM-02**: The alarm samples a **rate over a bounded recent window** and never claims a
  monthly total. n8n prunes executions (2,500 rows / ~10 hours observed here) and exposes no
  usage endpoint to an API key, so a total is unknowable by construction — reporting one would
  be a fabrication.

- [ ] **ALARM-03**: The plan allowance is configuration, not a literal. A missing or unreadable
  allowance produces a notice naming the missing key — never silence, and never a guessed
  default.

- [ ] **ALARM-04**: An alarm that cannot read execution history says so. This inherits the
  sweep's existing rule (D-15): silence means healthy, so a check that failed to run must never
  be indistinguishable from a check that found nothing wrong.

## Future Requirements (deferred beyond v0.8)

- Alarm delivery beyond the existing notification path (email/Slack escalation for a burn rate
  that would exhaust the plan within hours rather than days).

- Per-lane execution attribution — which workflow/lane spent the month, not just the total rate.
  Useful for tuning; not needed to prevent the failure.

- Automatic cadence throttling in response to a burn-rate alarm. Deliberately deferred: a system
  that re-times its own triggers unattended is a larger blast radius than the problem.

## Out of Scope

| Item | Reason |
| --- | --- |
| Installing the sweep cron / launchd schedule | Admin action on the operator's machine, not code. The alarm ships inert until it is scheduled — stated plainly, not papered over. |
| Upgrading the n8n Cloud plan | Commercial decision. This milestone makes the system fit the plan it has. |
| Re-enabling sub-daily cadences | Already corrected to daily (2026-08-10). CAP-03 is what keeps it corrected; changing it back is a budget decision, not milestone work. |
| Reducing per-record execution count (sub-workflow → inline) | An architecture change to the enrichment lane with its own risk surface; the budget problem is solved by not dispatching work that cannot complete. |
| HubSpot-side write-gate redesign | The gate's disarmed-at-rest default is a v0.6 safety invariant, load-bearing across three packages. This milestone works with it, not around it. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| GATE-01 | Phase 44 | Complete — live: 44-LIVE-EVIDENCE.md (execution 11820, 0 enrichment sub-executions) |
| GATE-02 | Phase 44 | Complete — live: 44-LIVE-EVIDENCE.md (verbatim `gate_closed` tick outcome item) |
| GATE-03 | Phase 44 | Complete — test: tests/n8n/sj3DispatchGate.test.mjs gate-open order/mutation pin + tests/n8n/sjPredicates.test.mjs wiring |
| DRAIN-01 | Phase 44 | Complete — live: 44-LIVE-EVIDENCE.md (HubSpot read-back of 280176525780: requested="false", status="skipped") |
| DRAIN-02 | Phase 44 | Complete — test: tests/test_write_gate_coverage.py::test_drain_write_patch_is_exactly_the_two_pair_allowlist |
| DRAIN-03 | Phase 44 | Complete — test: tests/test_write_gate_coverage.py drain provenance assertions; live corroboration in 44-LIVE-EVIDENCE.md |
| CAP-01 | Phase 44 | Complete — test: cap derivation in tests/n8n/sj3DispatchGate.test.mjs + builder assert; live `cap: 40` in 44-LIVE-EVIDENCE.md |
| CAP-02 | Phase 44 | Complete — test: overflow-defers + found-vs-dispatched tests in tests/n8n/sj3DispatchGate.test.mjs |
| CAP-03 | Phase 44 | Complete — test: tests/test_execution_budget.py idle-floor guard over committed scheduleTriggers |
| ALARM-01 | Phase 45 | Pending |
| ALARM-02 | Phase 45 | Pending |
| ALARM-03 | Phase 45 | Pending |
| ALARM-04 | Phase 45 | Pending |

Coverage: 13/13 v0.8 requirements mapped. 100% coverage, no orphans.
