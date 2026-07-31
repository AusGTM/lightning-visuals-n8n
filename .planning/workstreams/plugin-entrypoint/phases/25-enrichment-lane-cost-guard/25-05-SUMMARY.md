---
phase: 25-enrichment-lane-cost-guard
plan: 05
subsystem: operator-claude-plugin
tags: [cost-guard, preview, rate-table, credit-balance, tri-state, plugin]

requires:
  - phase: 25-02
    provides: "n8n/wf_backend_status_cloud.json — the credit-only hubspot/backend-status endpoint whose `{balances:[{provider, configured, credits, unreadable, error, status}], checked_at}` shape this plan's balance parser consumes"
  - phase: 23
    provides: "operator-claude-plugin/scripts/config_gate.py (plugin-root path resolution, capability refusal wording), tests/conftest.py (stub_post_transport_factory, autouse no_network guard)"
  - phase: 27
    provides: "operator-claude-plugin/scripts/backend_status.py — the plugin's ONLY status-endpoint client; reused rather than duplicated, which is what keeps this plan out of the send-shaped function allowlist"
provides:
  - "operator-claude-plugin/config/cost_rates.json — versioned, dated, cited plugin-local per-record rate table"
  - "cost_guard.load_rates() / rate_table_age_days() — rate provenance and displayable staleness (D-08)"
  - "cost_guard.estimate_batch() — per-provider credit figures + measured Anthropic USD, with unknown-rate and unknown-record-count both reported as unknown rather than computed"
  - "cost_guard.fetch_balances() — per-provider balance map, every failure path resolving to unreadable"
  - "cost_guard.compare() — tri-state ok / insufficient / unknown, branching on readability before magnitude"
affects: [25-06 (preview cost block), 25-07 (chunk plan + dispatch), 26 (retry preview)]

tech-stack:
  added: []
  patterns:
    - "the clock as a parameter, not an internal read — rate_table_age_days(table, reference_date) so staleness is testable and displayable without a wall-clock flake"
    - "an unreadable value asserted by an object that RAISES on every comparison/coercion operator, so a compute-then-relabel implementation cannot pass a verdict-string test"
    - "reuse the one existing send-shaped client instead of adding a second, keeping test_retry_reuses_dispatch.py's two-entry allowlist intact"

key-files:
  created:
    - operator-claude-plugin/config/cost_rates.json
    - operator-claude-plugin/scripts/cost_guard.py
    - operator-claude-plugin/tests/test_cost_guard.py
  modified:
    - .planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-CONTEXT.md

key-decisions:
  - "fetch_balances() delegates to backend_status.fetch_backend_status() rather than opening its own POST. A second transport would have made cost_guard.py a third send-shaped module and failed test_retry_reuses_dispatch.py's exactly-two-entry allowlist (D-33)."
  - "The estimator always prices Lusha at the FIRST-TIME contact rate, never the stored-id re-enrich rate (a measured 0). It therefore over-states rather than under-states — the safe direction for a guard whose job is preventing an over-spend."
  - "compare() sets remaining_credits to None on the unreadable branch rather than passing the raw value through, so an unreadable balance cannot leak into a rendered number downstream."
  - "Apollo's per-match rate is recorded unknown PERMANENTLY, not pending-a-better-key — see the D-10a correction below."

requirements-completed: [PREVIEW-02]

coverage:
  - id: D1
    description: "Every rate an estimate uses carries its own value, unit, citation and confidence, inside the plugin — no runtime read of any docs/ or planning path"
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "test_cost_guard.py::test_load_rates_returns_version_measurement_date_and_rates"
        status: pass
      - kind: command
        ref: "grep -c 'planning/\\|docs/LUSHA' operator-claude-plugin/scripts/*.py → 0 matches"
        status: pass
    human_judgment: false
  - id: D2
    description: "An unknown rate and a measured zero are structurally distinct in the table and in the estimate"
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "test_cost_guard.py::test_an_unknown_rate_and_a_measured_zero_are_not_the_same_value, ::test_an_apollo_estimate_is_unknown_rather_than_zero_and_does_not_raise"
        status: pass
    human_judgment: false
  - id: D3
    description: "Rate-table age is computable against a supplied reference date, so a stale table reads as stale"
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "test_cost_guard.py::test_rate_table_age_is_computed_against_a_supplied_reference_date"
        status: pass
    human_judgment: false
  - id: D4
    description: "Balances arrive only from the n8n-side status endpoint; every failure path yields unreadable for all three providers, never a zero"
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "test_cost_guard.py::test_an_unreachable_endpoint_yields_unreadable_for_all_three_providers, ::test_a_malformed_response_body_yields_unreadable_for_all_three_providers, ::test_a_provider_absent_from_the_response_is_unreadable_not_zero"
        status: pass
      - kind: command
        ref: "grep -v '^\\s*#' operator-claude-plugin/scripts/cost_guard.py | grep -c 'or 0\\||| 0' → 0"
        status: pass
    human_judgment: false
  - id: D5
    description: "A genuine zero balance and an unreadable balance yield DIFFERENT verdicts, and no arithmetic is performed on an unreadable balance"
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "test_cost_guard.py::test_a_genuine_zero_and_an_unreadable_balance_yield_different_verdicts, ::test_no_arithmetic_is_performed_on_an_unreadable_balance"
        status: pass
    human_judgment: false
  - id: D6
    description: "A backend-resolved record count yields a result that says so rather than an estimate from a fabricated count (D-02)"
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "test_cost_guard.py::test_a_backend_resolved_record_count_says_so_rather_than_inventing_a_number, ::test_a_backend_resolved_record_count_makes_every_verdict_unknown"
        status: pass
    human_judgment: false
  - id: D7
    description: "No returned reason echoes the configured shared secret (T-25-21)"
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "test_cost_guard.py::test_no_returned_reason_echoes_the_configured_secret"
        status: pass
    human_judgment: false

duration: 40min
completed: 2026-07-31
status: complete
---

# Phase 25 Plan 05: Client-side cost guard Summary

**A dated, plugin-local rate table plus the estimator, balance reader and tri-state comparison that turn it into a verdict — where an unreadable balance is `unknown` with a reason, a genuine zero is `insufficient`, and the unreadable branch is proven to perform no arithmetic at all.**

## Performance

- **Duration:** ~40 min
- **Tasks:** 2 completed (Task 2 run as a real RED/GREEN pair)
- **Files created:** 3 · **Files modified:** 1 (`25-CONTEXT.md`, corrections)

## Accomplishments

- **The rate table is a copy, not a pointer.** `operator-claude-plugin/config/cost_rates.json` carries
  `version`, `measured_on: 2026-07-30`, and ten entries each with `value` / `unit` / `citation` /
  `confidence`. Every number is a literal transcribed at implementation time from
  `scripts/enrichment_cost_ledger.py`'s `ESTIMATES`, the Phase 22 canary ledger and the Lusha v3
  contract. **No plugin module reads any `docs/` or `.planning/` path at runtime** (grep-verified, D-09).
- **Unknown and zero are different values, one layer before the verdict.** `apollo_per_match` is
  `null`; `lusha_contacts_stored_id_reuse` is `0`. Both are asserted present and distinct — the
  defect the tri-state exists to prevent is blocked at the data layer as well as the comparison layer.
- **The balance client is not a new client.** `fetch_balances()` delegates to the existing
  `backend_status.fetch_backend_status()` and only adds the per-provider parse. This was the
  load-bearing design choice: a second POST would have made `cost_guard.py` a third send-shaped
  module and broken `test_retry_reuses_dispatch.py`'s two-entry allowlist. It also means the
  finite timeout, the `X-Enrichment-Secret` header and the synthesized (never-relayed) error labels
  are inherited rather than re-implemented.
- **The comparison branches on readability before magnitude**, and this is proven structurally, not
  by string-matching a verdict: `test_no_arithmetic_is_performed_on_an_unreadable_balance` supplies a
  balance value that raises `AssertionError` on `__lt__`, `__gt__`, `__eq__`, `__sub__`, `__bool__`,
  `__float__` and `__int__`. An implementation that computed first and relabelled afterwards cannot
  pass it.
- **Two causes of "unknown estimate" are reported distinguishably** — a missing rate (Apollo) versus a
  backend-resolved record count (D-02) — so the operator can tell "we cannot price this provider"
  from "we cannot count this batch yet."

## Rate figures shipped, and their provenance

| Rate | Shipped value | Provenance | Confidence |
|---|---|---|---|
| Lusha, first-time contact enrich | **1 credit/contact** | Lusha v3 contract §7-8, live probe 2026-07-30 | measured |
| Lusha, company match | **2 credits/company** | Lusha v3 contract §5, live probe 2026-07-30 | measured |
| Lusha, stored-id re-enrich | **0 credits/contact** | Lusha v3 contract §8, 4/4 live calls billed 0 | measured — a real zero |
| ZoomInfo, per match | **1.08 credits/match** | Phase 22 research A3, v2-era measurement carried forward | inferred, pre-v3 |
| Apollo, per match | **null (unknown)** | no committed figure exists; see D-10a correction | unknown, permanently |
| Anthropic, all-in per record | **$0.068624 USD/record** | Phase 22 canary, executions 332 & 337, both 2026-07-30 | measured |
| Haiku research in/out | $1.00 / $5.00 per MTok | Phase 14 judge-wiring research | measured |
| Sonnet judge in/out | $2.00 / $10.00 per MTok | Phase 14 judge-wiring research | measured, **intro pricing expires 2026-08-31** |

**Agreement with the measured inputs supplied to this executor:** all four load-bearing figures match
exactly — Lusha 1cr/contact, 2cr/company, 0 for stored-id re-enrich, and $0.0686 Anthropic per record
(shipped at full precision, $0.068624). **The v2-era 4.65-credit Lusha field bundling is absent from
this table and is called out as superseded in the citation text**, so it cannot be carried forward by
a later reader. No plan figure had to be overridden.

## Task Commits

1. **Task 1: the dated rate table, copied in rather than pointed at** — `7a57cab` (feat)
2. **Task 2 RED: failing cost-guard spec** — `ab20917` (test)
3. **Task 2 GREEN: estimate, balance read, tri-state verdict** — `38e21a0` (feat)

## TDD Gate Compliance

Task 2 carried `tdd="true"` and was executed as a genuine RED/GREEN pair. RED (`ab20917`) was
verified failing (`ModuleNotFoundError: No module named 'cost_guard'`) before the implementation was
written; GREEN (`38e21a0`) took it to 27/27. No REFACTOR commit was needed — the implementation did
not require cleanup after passing. Gate sequence present in `git log`: `test(...)` → `feat(...)`.

## Test Results — with sibling attribution

Two siblings (25-03, 25-04) were committing into the same working tree during this run, so every
count below is attributed.

| Suite | Baseline at start | Final | Delta | Attribution |
|---|---|---|---|---|
| pytest (repo root) | 1370 passed, 1 skipped | **1423 passed, 1 skipped** | +53 | **+27 mine** (`test_cost_guard.py`), +26 sibling 25-04 (commits `9282b59`, `1f7efbd`) |
| plugin suite | 521 passed | **574 passed** | +53 | same split: +27 mine, +26 from 25-04 |
| node (`tests/n8n/*.test.mjs`, file form) | 474 passed, 0 fail | **474 passed, 0 fail** | 0 | untouched — this plan modified nothing under `n8n/` or `tests/n8n/` |

Baselines were measured by this executor before any edit, not taken on trust. No flake was observed;
the known 1 ms timestamp flake in `mergeContacts.test.mjs` did not fire in this run, and nothing here
reads a wall clock at assertion time (`rate_table_age_days` takes the date as a parameter precisely
so it cannot).

**Safety invariants re-verified after the last commit:**
`grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → **0 matches across all 8 files**. No live
network call was made by any verification in this plan; the plugin's autouse `no_network` guard was
in force for every test.

## Acceptance criteria

| Criterion | Result |
|---|---|
| rate table has `version`, `measured_on`, non-empty `rates` | pass |
| `measured_on` parses as an ISO date | pass |
| every rate entry has `citation`, `confidence`, `unit` | pass |
| an unknown rate AND a measured zero both exist, and differ | pass |
| `grep -c 'planning/\|docs/LUSHA' operator-claude-plugin/scripts/*.py` | **0 matches** |
| `grep -c 'backend-status' cost_guard.py` ≥ 1 | 1 |
| `grep -v '^\s*#' cost_guard.py \| grep -c 'or 0\|\|\| 0'` | **0** |
| zero-vs-unreadable different-verdict test present | pass |
| unreachable-endpoint all-three-unreadable test present | pass |
| `git diff --name-only` shows nothing outside `operator-claude-plugin/` from this plan's code commits | pass (the only non-plugin file touched is `25-CONTEXT.md`, in the docs commit, as instructed) |

## Corrections folded into 25-CONTEXT.md

**D-10a — Apollo is not a credit pool at all.** D-10 and `25-RESEARCH.md` describe Apollo's unknown
balance as a permissions accident (non-master key → 403 on the usage endpoint). That framing is
incomplete and would mislead anyone who "fixes" it by upgrading the key. Verified live 2026-07-31:
with a master key, `POST /api/v1/usage_stats/api_usage_stats` returns **HTTP 200 carrying
per-endpoint rate limits** — `limit` / `consumed` / `left_over` by day, hour and minute. That is
**throughput headroom, not a depleting credit balance**, and it is not comparable against a per-match
credit estimate the way Lusha's `credits.remaining` and ZoomInfo's balance are. Three consequences,
now recorded in CONTEXT and in the rate table's own citation text:
1. Apollo's per-match credit rate stays unknown **permanently** — a better key does not produce one.
2. Apollo's verdict is **structurally** unknown, making the unknown branch the common case for this
   account rather than an edge case. This is precisely why rendering it as zero would become a
   standing false alarm.
3. Nothing downstream may model Apollo as a depleting pool.

**D-11c — the chunk-timing measurement D-11a asked for already exists, and it is small.** D-11a states
"no batch-timing data exists in this repo yet, so the plan needs a measurement task before fixing the
default." That is now false: `29-TIMING.md` derived real per-record enrichment wall-clock **free from
n8n execution history** — **max 36.1 s/record, max single run 38.9 s**. Against D-11a's ~100 s
Cloudflare ceiling, a safe chunk is **2 records**, with 3 already inside the timeout's variance band.
Marked D-11a's measurement sentence superseded rather than deleting it, so the reasoning stays legible.

## Deviations from Plan

**None affecting behaviour.** One test was corrected during GREEN, before the implementation commit:
`test_an_unknown_estimate_against_a_readable_balance_is_still_unknown` originally asserted the reason
string contained "rate", but its fixture supplied a *known* rate with an unknown record count, so the
implementation correctly emitted the record-count reason. The test was widened to assert **both**
unknown-estimate causes with their own reasons rather than loosened to accept either — a stricter
test than the one it replaced. This is the RED spec being wrong about its own fixture, not the
implementation deviating from the plan.

## Known Stubs

None. Every function shipped is fully implemented and exercised; no placeholder values, no `TODO`
markers, no skipped tests introduced.

## Threat Flags

None. This plan adds no network surface — `fetch_balances()` reuses the single existing status POST
rather than opening a new one — no auth path, no file access beyond one plugin-local JSON read, and
no schema change at a trust boundary. The plan's own register (T-25-05, T-25-20/21/22/23) is
mitigated as designed: readability-first branching with a grep-forbidden numeric fallback (T-25-05);
a dated table with a displayable age (T-25-20); synthesized reasons with a secret-echo test
(T-25-21); unreachable-degrades-to-unreadable rather than raising (T-25-22); plugin-local table with
a grep for repo-doc path reads (T-25-23). Nothing was installed (T-25-SC).

## What 25-07 needs from this plan

1. **The three entry points to call, in order:** `load_rates()` → `estimate_batch(record_count,
   object_type, providers, rates)` → `fetch_balances(config)` → `compare(estimate, balances)`.
   `compare()` returns `{provider: {verdict, estimated_credits, remaining_credits, reason}}` where
   `verdict` is exactly one of `ok` / `insufficient` / `unknown`.
2. **Render all three verdicts distinctly.** D-17 requires the unknown-vs-zero distinction be asserted
   a third time at the rendered-text layer. Two of the three assertions now exist (n8n response
   assembly in 25-02; client comparison here). The preview text assertion is 25-06/25-07's, and an
   assertion of the form "unreadable is falsy" is banned — assert the two produce **different output**.
3. **Display the rate-table age.** `rate_table_age_days(table, date.today())` plus
   `estimate["rates_version"]` and `estimate["rates_measured_on"]` give the preview everything D-08
   needs without re-reading the file. Both are already carried on the estimate result.
4. **Expect `unknown` to be the normal Apollo answer** (D-10a). Preview copy that treats unknown as an
   exception state will read as broken on every single run of the default full waterfall.
5. **Chunk size is 2 records, not a round number** (D-11c). 36.1 s/record against a ~100 s ceiling.
   This also makes D-15's refuse-an-oversize-list rule bite far earlier than "500 members" suggests —
   a 20-member list is already 10 chunks.
6. **25-01's remaining live work is the lists-scope probe only.** Its chunk-timing half is answered by
   D-11c, so the operator gate is now smaller than the runbook implies.
7. **The estimator over-states Lusha deliberately** (first-time rate, never the stored-id 0). If the
   preview claims precision, it should say "at most" rather than "will cost".

## Files Created/Modified

- `operator-claude-plugin/config/cost_rates.json` — created; ten dated, cited rate entries
- `operator-claude-plugin/scripts/cost_guard.py` — created; loader, age helper, estimator, balance
  reader, tri-state comparison, JSON-printing main block
- `operator-claude-plugin/tests/test_cost_guard.py` — created; 27 tests
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-CONTEXT.md` —
  modified; D-10a and D-11c corrections added

**Not touched, deliberately:** `STATE.md`, `ROADMAP.md`, `plugin.json`, `test_plugin_manifest.py`,
`23-06-SUMMARY.md` (all held uncommitted by an operator mid-23-06); `operator.local.example.json`,
`enrichment.py`, `test_enrichment_envelope.py` (25-04's region); `build_cloud_workflows.py`,
`wf_enrichment_cloud.json`, `CHANGELOG.md`, `tests/n8n/`, `tests/test_enrichment_list_branch.py`
(25-03's region); all of `n8n/`.

## State files deliberately NOT updated

`STATE.md` was left untouched by explicit instruction — an operator holds it uncommitted mid-23-06,
and this workstream's `state.update-progress` is known to mangle it. `ROADMAP.md` likewise.
`REQUIREMENTS.md` was **not** marked complete for PREVIEW-02: this plan builds the arithmetic half
only, and the preview-text half (25-06/25-07) is where the operator actually sees the warning.
Marking it done here would be exactly the false-green this milestone keeps guarding against.

## Self-Check: PASSED

All four created/modified files verified present on disk; all three task commit hashes verified
present in `git log`. No claim in this summary is unbacked.

---
*Phase: 25-enrichment-lane-cost-guard*
*Completed: 2026-07-31*
