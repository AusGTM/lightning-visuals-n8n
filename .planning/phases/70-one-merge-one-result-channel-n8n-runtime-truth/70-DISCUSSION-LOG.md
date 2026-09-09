# Phase 70: One merge, one result channel — n8n runtime truth - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-09
**Phase:** 70-one-merge-one-result-channel-n8n-runtime-truth
**Areas discussed:** Convergence mechanism, Result channel, Write-gate contract, Harness depth + UAT shape

---

## Todo fold (pre-discussion)

Eleven pending todos matched by keyword; four offered, all four folded: the structural brief,
the create-row write_blocked precheck, written_records labelling propose legs failed (F8), and
the preview SEND vs confidence hold. Seven reviewed and not folded (listed in CONTEXT.md
`<deferred>`).

---

## Convergence mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit Merge node | One Merge (append, N inputs) at each convergence point; nodeRunRecovery.js retired | ✓ |
| Per-item pairedItem lineage | Readers use $('X').item; HTTP nodes break lineage; .item ambiguous across runs | |
| Keep nodeRunRecovery.js as the idiom | Fence with a builder lint; does not retire the idiom | |

**User's choice:** Explicit Merge node (recommended).

| Option | Description | Selected |
|--------|-------------|----------|
| Flip to v1 via the builder | Builder sets executionOrder v1 on every generated workflow | |
| Stay on v0, design around it | Merge made robust to a never-firing lane under legacy order | |
| Researcher decides after doc check | Flip only if n8n docs confirm Merge needs v1 for the empty-lane case | ✓ |

**User's choice:** Researcher decides after doc check.

| Option | Description | Selected |
|--------|-------------|----------|
| Retire bare .all() on converged nodes; lint the rest | By-name reads allowed only where the builder proves one inbound edge | |
| Retire every by-name read | No $('X') anywhere; every value carried on the row | ✓ |
| Retire only the seven listed instances | Smallest diff; idiom survives elsewhere | |

**User's choice:** Retire every by-name read (chosen over the recommended narrower option).

| Option | Description | Selected |
|--------|-------------|----------|
| Researcher picks carry; builder asserts zero $('X') | Locked rule is the build-time assertion; researcher evaluates carry mechanisms | ✓ |
| Merge combine-by-position after every HTTP hop | n8n-native; ~15–20 new nodes per workflow | |
| HTTP calls inside Code nodes | this.helpers.httpRequest; credential reachability on Cloud unverified | |

**User's choice:** Researcher picks carry; builder asserts zero $('X') (recommended).

---

## Result channel

| Option | Description | Selected |
|--------|-------------|----------|
| Execution runData by run_id, always | Client reads the settled execution for every mode incl. propose; sync body becomes a receipt | ✓ |
| Sync body, made complete by the Merge | Respond fires once with all rows; async keeps runData; two channels | |
| Sync body for propose, runData for writes | Split by mode | |

**User's choice:** Execution runData by run_id, always (recommended).

| Option | Description | Selected |
|--------|-------------|----------|
| Build Response reads the write node's actual output | action reflects HubSpot's response or the gate's refusal item; F12 precheck removed | ✓ |
| Keep the Decide-side precheck as the source | F12 pattern extended to create rows | |
| Both: precheck for routing, write output for the report | Two verdicts kept in parity by test | |

**User's choice:** Build Response reads the write node's actual output (recommended).

| Option | Description | Selected |
|--------|-------------|----------|
| Always an ack; async_ack flag retired | Respond fires once with {run_id, accepted, row_ids}; flag ignored if passed | ✓ |
| Ack by default, full body on request | Inverted flag returns the merged body for probes | |
| Keep the flag as-is | Sync default returns the merged body; client ignores it | |

**User's choice:** Always an ack; async_ack flag retired (recommended).

| Option | Description | Selected |
|--------|-------------|----------|
| Enrichment + ingest lanes only | Review queue/decision and backend-status stay body-responding queries | ✓ |
| Enrichment + ingest for the plugin; scripts keep a body | Request-level flag for repo scripts | |
| Every webhook goes ack-only | Turns three read-only queries into two-step polls | |

**User's choice:** Enrichment + ingest lanes only (recommended). Question was first sent back
for clarification; the operator asked for a commit-and-push of the consolidated fixes before
continuing (done, `5c11d43`), then answered.

| Option | Description | Selected |
|--------|-------------|----------|
| Do not record no-write legs | dispatch_plan appends to written_records only when the leg's mode can write | ✓ |
| Record as NO_ACTION with reason | Every leg appended; ledger widens to dispatches | |
| Backend stamps action on every row | Build Response guarantees an action; classify_item maps to NO_ACTION | |

**User's choice:** Do not record no-write legs (recommended).

| Option | Description | Selected |
|--------|-------------|----------|
| Refuse before start when key absent | n8n_api_key missing = Phase-57-style refusal; never time-proximity fallback | ✓ |
| Dispatch, then report 'unread' outcomes | Spend happens with no readable result | |
| Fall back to time-proximity match | D-12 guess; listed for completeness | |

**User's choice:** Refuse before start when key absent (recommended).

| Option | Description | Selected |
|--------|-------------|----------|
| confidence.assess is the only verdict | Preview shows HELD code/reason or SEND; send_count equals SENDABLE by construction | ✓ |
| Preview shows both columns | Email-found SEND plus the confidence verdict | |
| Drop the preview's send/hold column | Verdict appears once, at dispatch time | |

**User's choice:** confidence.assess is the only verdict (recommended).

---

## Write-gate contract

| Option | Description | Selected |
|--------|-------------|----------|
| One canonical write-request shape, no fallbacks | write_request {action, hs_object_id, domain, email}; builder asserts emitters | ✓ |
| Keep the tolerant gate, extend fallbacks | Contract stays implicit | |
| Canonical shape, gate keeps legacy fallbacks one phase | Two shapes for a while | |

**User's choice:** One canonical write-request shape, no fallbacks (recommended).

| Option | Description | Selected |
|--------|-------------|----------|
| Gate emits a refusal item on a second output | Refused rows carry write_blocked + reason to the Merge; no dead end | ✓ |
| Gate passes every row, write node skips refused | allowed flag; write node runs conditionally | |
| Keep drop; precheck in every Decide | Two implementations of one predicate | |

**User's choice:** Gate emits a refusal item on a second output (recommended).

| Option | Description | Selected |
|--------|-------------|----------|
| All three lanes, one shape; review keeps its id-only rule | Review emitter sets domain: null so 30-02 survives as data | ✓ |
| Enrichment + ingest only | Review-decision gate untouched | |
| All three, and review gains the domain path | Reverses 30-02 | |

**User's choice:** All three lanes, one shape; review keeps its id-only rule (recommended).

| Option | Description | Selected |
|--------|-------------|----------|
| One gate verdict covers update + associate | One write_request, one allowlist verdict; association still not_attempted when no company resolved | ✓ |
| Separate gates, separate verdicts | Association can refuse independently | |

**User's choice:** One gate verdict covers update + associate (recommended). Wording tightened
after advisor review so it does not contradict §13.0.1 (an update is never held for lack of a
company).

---

## Harness depth + UAT shape

| Option | Description | Selected |
|--------|-------------|----------|
| Graph walker over the committed JSON | Executes from connections per executionOrder; models Merge, one Respond, responseData, $runIndex | ✓ |
| Shared per-node run-history helper only | Promote makeDollar; hand-wired run counts | |
| Hybrid: walker for the two lanes, helper elsewhere | Two harness layers | |

**User's choice:** Graph walker over the committed JSON (recommended).

| Option | Description | Selected |
|--------|-------------|----------|
| One RED-first test per instance, against the pre-fix JSON | Seven tests shown RED at historical commits | |
| One mixed-batch test per lane | 2 lanes × 2 actions per lane; every row returns once from the write | ✓ |
| Walker plus live differential proof | RED-first tests AND a disarmed live batch | |

**User's choice:** One mixed-batch test per lane (chosen over the recommended option).

| Option | Description | Selected |
|--------|-------------|----------|
| Run both against the pre-Phase-70 JSON once, record RED | Historical RED committed as evidence | |
| GREEN on the refactored JSON is enough | Walker's detection asserted by its own unit tests | ✓ |

**User's choice:** GREEN on the refactored JSON is enough (chosen over the recommended option).

| Option | Description | Selected |
|--------|-------------|----------|
| Disarmed live mixed batch, runData matches walker | Shape-equal verdict JSON; zero writes, zero arming | ✓ |
| Offline GREEN closes it; live proof is the next UAT | Live behaviour unproven at close | |
| Disarmed live batch plus one armed supervised row | Spends one write | |

**User's choice:** Disarmed live mixed batch, runData matches walker (recommended).

---

## Claude's Discretion

Merge parameters and layout; walker API and fixture format; ack field names beyond the three
named; poll bounds for former sync callers; migration order and script delete-vs-migrate;
node-count and declaration-count pin updates; shaping of former sync-body refusal reasons as
runData rows.

## Deferred Ideas

None raised — discussion stayed within phase scope. Seven matched todos reviewed and not
folded (see CONTEXT.md).
