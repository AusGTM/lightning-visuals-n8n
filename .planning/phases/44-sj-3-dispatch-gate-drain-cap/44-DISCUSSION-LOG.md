# Phase 44: SJ-3 Dispatch Gate, Drain & Cap - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-10
**Phase:** 44-SJ-3 Dispatch Gate, Drain & Cap
**Areas discussed:** Gate granularity, Drain authority, Cap policy + overflow, Gate-closed visibility

---

## Gate granularity

**Q1 — When the window is partially armed (2 of 61 records allowlisted), what should a tick dispatch?**

| Option | Description | Selected |
|--------|-------------|----------|
| Per-record filter | Dispatch exactly the allowlisted records, skip the rest; cost 1 + allowlisted count | ✓ |
| All-or-nothing | Zero if the flag is false, everything if true; enrichment refuses downstream | |

**Notes:** Scouting found `_writeSafetyAllows` is a per-record filter requiring both the flag
AND the `TEST_RECORD_*` allowlist. Since `scheduled_arm.py` scopes the allowlist to one batch,
all-or-nothing would make real armed windows dispatch nothing.

**Q2 — How should the allowlist logic reach SJ-3?**

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `WRITE_SAFETY_GATE_JS` | Embed verbatim, as `ENRICH_DECIDE_CLOUD` and the spliced gates already do | ✓ |
| New SJ-3-specific check | Narrower predicate for the poller only | |
| You decide | Lock behaviour, leave mechanism to planning | |

**Notes:** One definition of "permitted" so poller and lane cannot drift.

**Q3 — Keep the downstream enrichment refusal as well?**

| Option | Description | Selected |
|--------|-------------|----------|
| Keep both | Defence in depth; webhook/manual paths bypass SJ-3 entirely | ✓ |
| SJ-3 only | Trust the poller's filter, drop the per-record refusal | |

**Q4 — Does an allowlisted record whose enrichment fails mid-run stay flagged?**

| Option | Description | Selected |
|--------|-------------|----------|
| Stays flagged | Retryable work; the drain targets only gate-DECLINED records | ✓ |
| Cleared on failure too | No accumulation from any cause, but drops retryable work | |
| You decide | Let research check existing failure paths first | |

---

## Drain authority

**Q1 — How does the flag-clear write get permission while the data gate is shut?**

| Option | Description | Selected |
|--------|-------------|----------|
| New authority, defaults true | Unreachable from the other two; first write enabled at rest | ✓ |
| New authority, defaults false | Keeps the invariant intact but the drain only runs when the queue isn't stuck | |
| No authority — structurally narrow | No flag to arm/disarm, but no kill switch either | |

**Notes:** Justified because it can only ever set `lv_enrichment_requested="false"` — it
removes work rather than creating it. Must not be cited later as precedent for defaulting
other writes on. WINDOWS.md #2 records that flipping an existing write-safety default broke
64 tests across two packages and was reverted.

**Q2 — Should the drain respect the `TEST_RECORD` allowlist?**

| Option | Description | Selected |
|--------|-------------|----------|
| No — drain all declined | The stuck queue is mostly non-allowlisted; that is the problem | ✓ |
| Yes — allowlist applies | Maximum consistency, but a no-op against the actual failure | |

**Q3 — What bounds a drain that is on by default?**

| Option | Description | Selected |
|--------|-------------|----------|
| Property + value + provenance | One property, one literal value, ids declined this tick, stamped why; test asserts a one-key patch | ✓ |
| Property + value only | Narrow patch, no provenance — but then DRAIN-03 fails | |
| You decide | Lock narrow-write, let planning choose provenance | |

**Q4 — Where should drain-vs-enriched distinguishability live?**

| Option | Description | Selected |
|--------|-------------|----------|
| Existing `lv_enrichment_status` | Already in SJ-3's own search filter; no property migration | ✓ |
| New dedicated property | Cleanest semantics, adds a schema migration to a phase with none | |
| n8n execution log only | Zero schema impact, but pruned within ~10 hours | |

---

## Cap policy + overflow

**Q1 — A record that passes the gate but exceeds the cap?**

| Option | Description | Selected |
|--------|-------------|----------|
| Stays flagged, next tick | Overflow is deferred work; the drain must not touch it | ✓ |
| Drained like a declined record | Bounded and simple, but silently discards permitted work | |

**Q2 — What share of the allowance should the cap reserve?**

| Option | Description | Selected |
|--------|-------------|----------|
| Configurable, ~50% default | ~1,250/month → ~40/tick daily; headroom for webhook/manual | ✓ |
| ~80% default | Higher throughput, little slack for on-demand enrichment | |
| You decide | Lock the derivation, let planning pick the share | |

**Q3 — Where does the plan allowance live?**

| Option | Description | Selected |
|--------|-------------|----------|
| `config/` YAML | One source for builder, CAP-03 test, and Phase 45's ALARM-03 | ✓ |
| Env var | Matches the ALLOW_* idiom, but a committed test cannot read `.env` | |
| Constant in the builder | Simplest today; Phase 45 would import from a build script | |

**Q4 — Accept that the cap bounds SJ-3 only?**

| Option | Description | Selected |
|--------|-------------|----------|
| Accept, state it | SJ-3 is the unattended path that ran away; manual dispatch has the plugin's cost guard | ✓ |
| Extend cap to all paths | Broader, but touches the enrichment lane and the plugin — beyond the phase boundary | |

---

## Gate-closed visibility

**Q1 — Where should the gate-closed outcome be observable?**

| Option | Description | Selected |
|--------|-------------|----------|
| Execution data + drain evidence | Structured outcome in the run, plus `lv_enrichment_status` that survives pruning | ✓ |
| Execution data only | Zero HubSpot coupling, evidence gone within ~10 hours | |
| Surface via `backend-status` | Best reach, but edits the plugin — Phase 45's package | |

**Q2 — Loud, or quiet and recorded?**

| Option | Description | Selected |
|--------|-------------|----------|
| Quiet, recorded | Disarmed is the normal state; alarming on it trains the operator to ignore alarms | ✓ |
| Warn above a threshold | Catches a large queue early, overlaps Phase 45's alarm | |
| You decide | Let planning judge once the outcome shape is designed | |

---

## Claude's Discretion

None. Every question was answered with an explicit choice. Left to planning within those
decisions: the exact `lv_enrichment_status` value the drain writes, the cap-rounding rule,
and the shape of the structured outcome object.

## Deferred Ideas

- Bounding webhook / operator-initiated dispatch (D-12 accepts SJ-3-only scope).
- Surfacing the gate-closed outcome through `backend-status` (plugin package, Phase 45).
- Warning above a declined-count threshold (overlaps Phase 45's alarm).

## Todos reviewed, not folded

- *Sweep re-notifies a fixed failure until 100 executions displace it* — tagged
  `resolves_phase: 45`; the sweep's lookback window, not SJ-3's.
- *Enrichment throughput — 82% of every run is two sequential Anthropic calls* — matched on
  generic keywords; per-run latency, not execution count.
- *The sweep's crontab entry pins a versioned plugin path* — cron installation is out of
  scope for this milestone.
