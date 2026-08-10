# Phase 45: Burn-Rate Alarm - Context

**Gathered:** 2026-08-10
**Status:** Ready for planning

<domain>
## Phase Boundary

The sweep reports an unsustainable n8n execution rate before a human notices it on the
billing page (ALARM-01..04), and — folded in by operator decision — the plugin's runtime
cadence action gains a budget floor so a schedule change cannot silently bust the plan, and
the sweep's execution lookback becomes time-windowed instead of a fixed 100-row page. Pure
Python inside `operator-claude-plugin/scripts/` plus one repo-side drift test; **no n8n
deploy, no bounce, no HubSpot write**.

**Folded todos (now in scope):**
- `2026-08-10-runtime-cadence-has-no-budget-floor.md` — prevention half of the budget domain
- `2026-08-03-sweep-lookback-has-no-time-window.md` — the alarm needs time-windowed
  execution reads anyway; the same plumbing fixes the re-notify-for-days defect

**Not in this phase:** installing any cron/launchd schedule (admin action, milestone-level
out of scope — the alarm ships inert until scheduled); the crontab versioned-path todo
(deferred, install-side); automatic cadence throttling in response to an alarm (deferred at
milestone scoping); per-lane execution attribution (deferred).

</domain>

<decisions>
## Implementation Decisions

### Rate sample + projection

- **D-01:** The rate targets the **last 24 hours** but is computed over the **actually
  observed span** (oldest retained execution → now), and the notice states that span.
  n8n prunes at 2,500 rows (~10h at runaway rates), so during the exact incident this alarm
  exists for, the window shrinks — the rate must never pretend to a window it did not see.
  A shrunken window is itself a symptom worth naming in the notice.

- **D-02:** Projection is **anchor-free**: `rate × 30 days` compared against the monthly
  allowance. n8n exposes no billing-cycle day, and inventing one violates the same honesty
  rule as ALARM-02's no-fabricated-total. **ALARM-01's wording ("for the current billing
  period") is to be amended** to match: "projects to exhaust the monthly allowance at the
  sampled rate". A config `billing_anchor_day` was considered and rejected — one more key
  to keep correct, and a wrong anchor silently mis-projects.

- **D-03:** **Every execution counts** — all workflows, all modes (manual, webhook,
  scheduled, sub-executions). That is what n8n bills; the 2026-08-09 runaway was
  sub-executions, and an excluded path is a blind spot.

### Allowance plumbing

- **D-04:** The allowance reaches the sweep via a **new plugin config key**
  (`n8n_monthly_execution_allowance`), admin-set like every other key, with a **repo-side
  drift test** asserting the plugin's example/config value equals
  `config/execution_budget.yaml`'s `monthly_execution_allowance` so the two sources cannot
  drift unnoticed. Reading the repo YAML directly at sweep runtime was rejected: the
  unattended sweep would gain a backend-checkout filesystem dependency, and a moved
  checkout would silently turn the alarm off.

- **D-05:** A missing/unreadable allowance produces a **condition-level notice** — the
  burn-rate condition alone emits "not configured — not watching the budget", **naming the
  key** (ALARM-03) — while the sweep's other conditions keep running. Adding the key to
  `config_gate`'s `sweep` capability row was rejected: a stuck lock must not go unreported
  because a budget key is absent.

### Threshold + repeat policy

- **D-06:** Fire threshold is **configurable, defaulting 1.0×**: fire when
  `rate × 30d > allowance × threshold`. The idle floor is ~95/month (~4% of plan), so any
  real anomaly clears the default by an order of magnitude; the key exists for tightening
  later, not because 1.0 is marginal.

- **D-07:** **The alarm re-notifies on every sweep while the burn persists.** This is the
  one condition where repetition is the discipline: an active burn costs money hourly, and
  this repo's history says a missed signal costs 73× the plan. It is self-clearing — the
  time-windowed rate (D-01, plus the lookback fold) drops when the burn stops — which is
  what distinguishes it from the fixed-100-page lookback defect, where *stale history*
  re-notified about the past. NOTICE-04's noise discipline is honoured by the condition
  being rate-based and current, not by suppression.

### Sweep lookback (folded todo)

- **D-08:** `recent_executions`' fixed `EXECUTIONS_PAGE_LIMIT = 100` page becomes a
  **time-windowed read** — the same windowed execution query the burn-rate condition needs
  (D-01). Applied to the existing failure conditions too, so a fixed failure stops
  re-notifying for days after its cause is resolved. The todo's secondary finding (notices
  name "an unnamed workflow" — `workflowId` → name is one `list_workflows` read away) is in
  scope as part of the same touch.

### Cadence floor (folded todo)

- **D-09:** The floor bounds **every trigger, every request** — any cadence action on any
  of the five schedule triggers gets the budget arithmetic. Sub-daily-only was rejected:
  "hourly on all five" passes individually while summing to 3,600/month. The check computes
  the requested interval's monthly fire count and refuses when the schedule's total cost
  busts the configured share, in `n8n_cadence`'s established refusal style (D-09/D-10 of
  that module: plain words, no expression syntax, a way forward, numbers named — "every 15
  minutes is 2,880 fires a month against a 2,500 plan").

- **D-10:** **A conversational override exists, by operator decision** (selected against
  the no-override recommendation — recorded as their call). Shape, as agreed:
  1. The refusal always states the arithmetic FIRST — the override is never offered before
     the numbers are on the table.
  2. A deliberate, specific phrase (e.g. "override the budget floor") lets that one change
     through, with the consequence restated at the moment of override.
  3. The override is **single-shot** — it applies to exactly that one schedule change and
     never persists to later changes or later sessions.
  — **Reversibility:** reversible, but note the precedent: this is the first budget gate in
  the repo that yields to conversation. The implementation must not generalise the pattern
  (no shared "override" helper other gates could adopt).

### Claude's Discretion

Left to planning within the decisions above: the exact notice wording, the new time-window
constant and its config key name (if configurable), the threshold key name, the override
phrase's exact string, and how the drift test locates the plugin's example config.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` — Phase 45 goal + 4 success criteria (note the ships-inert
  verification note: direct invocation + fixtures, no live scheduled fire)
- `.planning/REQUIREMENTS.md` — ALARM-01..04 verbatim (ALARM-01 wording to be amended per
  D-02); the folded todos add scope beyond these four — the planner should add requirement
  rows (e.g. FLOOR-01, LOOK-01) so traceability stays 100%
- `.planning/todos/pending/2026-08-10-runtime-cadence-has-no-budget-floor.md` — full gap
  mechanism, worst-case arithmetic, fix shape
- `.planning/todos/pending/2026-08-03-sweep-lookback-has-no-time-window.md` — the lookback
  defect, observed live (RB-8), plus the unnamed-workflow secondary

### The code this phase changes
- `operator-claude-plugin/scripts/sweep_conditions.py` — existing conditions (STUCK,
  STUCK_ARMED, QUOTA_EXHAUSTED, CREDENTIAL_FAILURE, FAILED_RUN, REVIEW_BACKLOG,
  SWALLOWED_MAINTENANCE_FAILURE); the burn-rate condition joins this set
- `operator-claude-plugin/scripts/sweep_read.py` — gather layer; already talks to the
  executions API
- `operator-claude-plugin/scripts/n8n_read.py:47` — `EXECUTIONS_PAGE_LIMIT = 100`, the
  fixed page D-08 replaces
- `operator-claude-plugin/scripts/sweep_entry.py` — D-15 rule (a sweep that cannot run must
  say so); the condition-level not-configured notice (D-05) follows its existing pattern
- `operator-claude-plugin/scripts/n8n_cadence.py:199` (`parse_cadence`) and `:439`
  (`set_cadence`) — where the floor (D-09/D-10) lands; the module's own D-09/D-10 refusal
  rules are binding
- `operator-claude-plugin/scripts/config_gate.py` — capability rows; the allowance key is
  deliberately NOT added to the `sweep` row (D-05)
- `config/execution_budget.yaml` — the repo-side allowance the drift test (D-04) pins
  against

### Constraints and history
- `.planning/PROJECT.md` — v0.8 milestone context, measured runaway numbers
- Sweep design rules: silence means healthy (D-15); NOTICE-04 (a sweep that speaks when
  healthy is one the operator learns to ignore); notices carry who-can-fix
- Phase 44's `44-CONTEXT.md` D-11 — why one allowance source; the drift test is how D-04
  honours it without a runtime filesystem dependency

### Tests that must stay green
- `.venv/bin/python -m pytest -q` — 2438 passing
- `node --test tests/n8n/*.test.mjs` — 656 passing
- `operator-claude-plugin` suite — 1286 passing (`tests/test_sweep_read_only.py`'s
  filesystem-write guard binds the sweep; the new condition must stay read-only)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **The sweep condition framework** — `sweep_conditions.evaluate(gathered)` returns fired
  condition dicts; `sweep_notify.render` handles silence/single/grouped. A new condition is
  additive; no orchestration change.
- **`executions_client.py`** — the executions API client the windowed read extends.
- **`n8n_cadence.CadenceRefused`** — carries reason + worked examples; the floor's refusal
  reuses it.
- **`config_gate` condition-level degradation pattern** — `status` already degrades to the
  half it can read; D-05's condition-level notice follows the same philosophy.

### Established Patterns
- Sweep is READ-ONLY, enforced by test (`test_sweep_read_only.py`).
- Notices: one delivery per sweep, grouped, most-actionable-first, capped with a stated
  count of anything past the cap.
- Exact-string config semantics; refusals name keys, never values.
- The plugin ships behind a version bump (`plugin.json` 0.12.0 → bump with CHANGELOG entry;
  same-version reinstall traps documented in project memory).

### Integration Points
- New condition in `sweep_conditions.py` + its gather support in `sweep_read.py`.
- Time-windowed replacement for `n8n_read.recent_executions` consumers.
- Floor check inside `parse_cadence`/`set_cadence` path, before any PUT is composed.
- New plugin config key + example-config entry + repo-side drift test against
  `config/execution_budget.yaml`.
- `operator-claude-plugin/USAGE.md` — the guide's budget note and admin table were written
  pre-floor ("nothing else stands between a too-fast cadence and the budget"); this phase
  makes that sentence false and must update it.

</code_context>

<specifics>
## Specific Ideas

- The refusal/notice register follows the repo's existing voice: numbers first, then the
  way forward ("every 15 minutes is 2,880 fires a month against a 2,500/month plan").
- The alarm's notice should include: sampled rate, actual observed span (and that it was
  truncated by pruning, when it was), projection, allowance, and who-can-fix.
- Verification is by direct invocation + fixture/synthetic execution histories (roadmap
  note) — including a fixture reproducing the 2026-08-09 runaway shape (flat 253/hour) and
  one reproducing a pruning-truncated window.

</specifics>

<deferred>
## Deferred Ideas

- Crontab versioned-path todo (`2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md`)
  — install-side; cron installation is out of milestone scope.
- Escalation delivery (email/Slack) for a burn that would exhaust the plan within hours —
  milestone-level future requirement.
- Per-lane execution attribution — future requirement.
- Automatic cadence throttling on alarm — deliberately deferred at milestone scoping.

### Reviewed Todos (not folded)
- *Enrichment throughput — two sequential Anthropic calls* — per-run latency, not
  execution count; matched on keywords only.
- *UAT 2.2 header aliases* — column mapping; unrelated.

</deferred>

---

*Phase: 45-Burn-Rate Alarm*
*Context gathered: 2026-08-10*
