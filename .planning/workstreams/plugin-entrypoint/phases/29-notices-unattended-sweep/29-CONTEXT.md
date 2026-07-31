# Phase 29: Notices & Unattended Sweep - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 29 makes the backend speak up. Two mechanisms, one purpose — the operator learns something
needs them without having to think to ask:

1. **In-session watch** — after a dispatch, keep watching until the run settles and report back
   unprompted with per-record outcomes and the cost actually incurred.
2. **Unattended sweep** — with no session open, notice when something needs a human and push a
   notification.

The sweep is **read-only by construction**: it burns no provider credits, enables no writes, and
dispatches nothing. That is a structural property of what it is allowed to call, not a policy it
promises to follow.

Not in scope: acting on what the sweep finds. Notices point at controls Phase 28 already exposes.

</domain>

<decisions>
## Implementation Decisions

### Sweep host
- **D-01:** The unattended sweep is a **Claude scheduled routine that reuses the plugin's existing
  read paths** — Phase 27's status surface on a cadence, pushing a notification when something
  needs a human.
- **D-02:** This makes **NOTICE-05 structural rather than promised**: the sweep calls only read
  endpoints, so it *cannot* burn credits, enable writes, or dispatch. The plan must keep it that
  way — the sweep must have no code path to a mutation or a dispatch, not merely avoid calling one.
  — *Qualified by D-13 and D-19:* "read endpoints" includes exactly one bodyless POST (the n8n
  status webhook, allowlisted by name), and the no-credit half is mediated by that endpoint's
  behaviour rather than being structural on the client. The no-write half **is** structural.
- **D-03:** The notice lands **where the operator already is**, rather than in a separate channel
  they would have to watch. — **Reversibility:** costly — moving to an n8n-side or cron-hosted
  sweep later means rebuilding both the scheduling and the delivery path.
- **D-04:** **Dependency the plan must verify early:** this assumes scheduled Claude agents are
  available on the operator's account. If they are not, the sweep has no host and the phase needs
  a different mechanism — verify before building, do not discover mid-implementation.

### In-session watch bound
- **D-05:** The watch bound is an **admin-config value with a sane default**. The default is tuned
  to observed run times; an admin can raise it for a slow backend.
- **D-06:** The bound must be **empirical, not guessed**. Enrichment runs the full provider + Haiku
  + Sonnet chain per record, and 25-RESEARCH.md established that **no batch-timing data exists in
  this repo yet**. Deriving the default therefore needs a measurement task, shared with Phase 25's
  chunk-size measurement (25-CONTEXT D-11a) rather than duplicated.
- **D-07:** At the bound the run is reported as **still running, with how to re-check** — reusing
  Phase 26's run handle (26-CONTEXT D-06). The watch **never simply goes quiet** (NOTICE-02).

### What the sweep reports
- **D-08:** The sweep is **silent when the backend is healthy** (NOTICE-04). Only these conditions
  produce a notice: a failed scheduled run, a credential or auth failure, an exhausted quota, a
  stuck lock, or a review backlog past its configured threshold.
- **D-09:** Every notice states **whether the operator or an admin can act on it** (NOTICE-04),
  using the same attribution discipline as Phase 27 D-04/D-05 — including its guardrail that an
  unrecognized cause defaults to admin attribution rather than telling the operator they can fix
  something the table does not recognize.
- **D-10:** A **stuck-armed backend** is one of the conditions the sweep watches for. Phase 28 D-03
  names this sweep as the backstop for the crash window between arm and disarm.

### Corrections and confirmations from 29-RESEARCH.md
- **D-01a (D-04's availability risk is CLOSED for this machine):** Scheduled Claude routines are
  real and enabled here — `claude_desktop_config.json` carries `coworkScheduledTasksEnabled: true`
  and `ccdScheduledTasksEnabled: true`, and a working example already runs at
  `~/Documents/Claude/Scheduled/weekday-morning-brief/SKILL.md`, firing on a cadence and driving
  real MCP tool calls. **Still unverified:** whether a scheduled routine can invoke *this plugin's
  own* skill rather than a generic connector. That is the plan's **first task**, not an assumption.
- **D-01b:** Anthropic's lower-level scheduled mechanism (Managed Agents `deployments`, cron +
  webhook delivery) is **not** the right fit — its notification path needs a developer-operated
  webhook receiver, which contradicts the milestone's "operator never runs infrastructure" rule.
  Retained only as D-04's named fallback.
- **D-05a (NOTICE-01 is this phase's highest-risk claim):** Research observed the unprompted
  background-notification behaviour NOTICE-01 describes working in the **CLI** runtime, but could
  **not** confirm it in Claude Desktop — which is the actual target (Phase 23 D-14a). Therefore:
  build **D-07's bounded "still running, here's how to re-check" path as the real NOTICE-01/02
  mechanism**, and treat true unprompted mid-conversation follow-up as a **bonus if verified, never
  a dependency**. A phase that depends on an unconfirmed platform primitive fails silently.
- **D-06a (the watch bound is computable from data already fetched):** `/api/v1/executions` returns
  both `startedAt` and `stoppedAt`. `scripts/enrichment_cost_ledger.py` already reads that list but
  never computes a duration. No new endpoint is needed — just the computation, shared with Phase 25
  D-11a's chunk-sizing measurement.
- **D-08a (the five conditions are unevenly detectable):** stuck-lock, review-backlog, and partially
  failed-scheduled-run reuse Phase 27's read surface unmodified. **Credential-failure and
  exhausted-quota need new threshold/classification logic** over Phase 27's existing credit-probe
  data — new logic, not new reads.
- **D-08b (new instance of a known bug pattern):** `wf_scheduled_maintenance_cloud.json`'s own
  HubSpot-Search nodes are `onError: continueRegularOutput`, so **the maintenance job silently
  swallows the same failure class** Phase 27 found in the enrichment workflow (27-CONTEXT D-04a).
  The sweep must not treat "the maintenance job reported success" as evidence of health.
- **D-02a (NOTICE-05 becomes enforceable rather than promised):** implement the sweep as a
  dedicated module plus an **AST / import-graph test asserting zero reachable mutation calls** —
  mirroring `scripts/enrichment_cost_ledger.py`'s no-write guarantee, but enforced by CI instead of
  a comment. This is the concrete mechanism D-02 asked for.

### Planning judgments recorded
- **D-09 (tracer is not first):** the tracer is plan 3, not plan 1. The platform probe (29-01) and
  the fixtures + measured watch bound (29-02) must precede it — the probe is the first question the
  research demands answered, and the tracer needs something to verify against.
- **D-10 (NOTICE-05's guard is an ALLOWLIST, not a denylist):** the import-graph guard enumerates
  what the sweep may reach rather than what it may not. It therefore **fails closed on imports
  Phases 28 and 30 have not written yet**, instead of silently permitting them. The same allowlist
  is extended to the shipped skill body — a clean module graph invoked by a wide skill would pass a
  module-only guard while still violating the requirement.
- **D-11 (an accepted, unmitigated gap — T-29-19):** **a sweep that stops *firing* is
  indistinguishable from a healthy backend.** *(Scoped by D-15: a sweep that fires and cannot do its
  job is a different, observable problem, and it is mitigated rather than accepted. Do not merge the
  two.)* Silence means healthy (D-08), so a dead sweep and a
  well backend produce identical operator experience. D-08 locks the notice list to exactly five
  conditions, so a sixth (a heartbeat or dead-man's switch) was **not** smuggled in during
  planning. It is recorded as an accepted threat for a future requirement. **This is a real hole in
  the milestone's monitoring story and should be raised as a v0.7 candidate**, not left implicit.
- **D-12 (the live gate is safe by construction):** the end-to-end gate fires a condition by
  **lowering the review-backlog threshold** — never by breaking a credential or arming the backend
  — plus a step verifying no write and no credit consumption occurred. That verification is the
  observable counterpart to the static import guard.

### Corrections from the 2026-07-31 plan check (D-13 … D-21)

**These are decisions, not notes.** Each was found by checking a plan's instruction against the
actual tree, and each was wrong in a way an executor would have had to resolve on their own — which
is how a safety property gets quietly weakened. They are recorded here rather than only in the plans
so they are not re-litigated. **Numbering continues from D-12; nothing above is renumbered**, since
every plan cites these IDs.

- **D-13 (the read-only guard allowlists exactly ONE non-GET call, by name).** 29-03 originally
  required that no module in the sweep's import closure reference a non-GET HTTP verb. That cannot
  pass: **Phase 27's read surface is half POST.** `backend_status.py:33` is
  `def fetch_backend_status(config, transport=requests.post)` ("One POST"), `status.py:186-187` is
  `full_report(..., post_transport=requests.post, ...)`, `status.py:19` imports `backend_status`, and
  `render_text.py:28` imports `status`. 29-05 **requires** what that POST returns — provider balances
  and review-backlog counts — so `requests.post` is necessarily in the closure. The executor's only
  exits would have been to weaken the assertion (silently degrading the phase's headline safety
  property) or hand-roll a second reader (which 29-03 forbids). **Decision:** the assertion
  allowlists `backend_status.fetch_backend_status`'s POST to `webhook/hubspot/backend-status` **by
  name** and fails on every other non-GET verb. A POST is a read here because the endpoint is an n8n
  webhook (webhooks answer on POST), the request carries nothing — `backend_status.py:46` sends
  `json={}` — and its chain has no write node, proven by
  `tests/test_backend_status_wiring.py::test_endpoint_chain_contains_no_write_node`. **This follows a
  precedent already set in this repo:** `tests/test_retry_reuses_dispatch.py` allowlists the same
  function in `_EXPECTED_SEND_SHAPED` and keeps it honest with two compensating tests — no
  `files=`/`data=`, and the `json=` body must remain the empty dict literal, asserted by AST. Mirror
  that shape, do not invent a second convention, and remove the exemption rather than widening it if
  that POST ever gains a body.

- **D-14 (`is_stuck()` does not exist; use the shipped tri-state).** Four places in 29-03 named
  "Phase 27's `is_stuck()`" and instructed verbatim reuse, including a precondition telling the
  executor to **halt** if it were absent — which would have fired wrongly against a tree that is in
  fact ready. Phase 27 shipped instead: `n8n_read.py:107` `stuck_threshold_minutes(config)` (config
  key `stuck_execution_minutes`, already in `config/operator.local.example.json`), and `stuck`
  computed inline at `n8n_read.py:150-169`, surfaced through `last_execution` and
  `status.describe_workflow` as `last_run["stuck"]` / `last_run["stuck_threshold_minutes"]`. The
  tri-state is good news, not an obstacle: 29-03's condition contract already asked for a
  "boolean-or-unknown outcome". **Decision:** consume the shipped verdict, preserve all three states,
  and never flatten `None` to `False` — per Phase 27 D-07b(i) `None` means *in flight with an
  unreadable start time*, which fires its own "age unreadable" notice.

- **D-15 (a sweep that cannot run must say so; silence is reserved for health).**
  `status.py:189` and `:206` call `config_gate.require_capability(config, "status")`, which **raises
  `ConfigError` before any transport is constructed**. No Phase 29 plan said what `sweep_entry` does
  with that. In a scheduled routine with nobody watching, a raised exception produces **nothing** —
  and D-08 defines nothing as healthy. A misconfigured sweep would therefore be indistinguishable
  from a well backend: a live hole in exactly the NOTICE-03/04 pair. **Two decisions:**
  (i) **`sweep` gets its own `CAPABILITY_KEYS` row**, requiring `n8n_url`, `n8n_api_key` **and**
  `webhook_secret`. `config_gate.py:26-30` records that `control` was split from `status` on
  precisely this reasoning (Phase 28 D-29) — a config that may read is not thereby one that may
  mutate, and withholding a row is how "read-only plugin" stays expressible. The sweep earns one for
  the mirror-image reason: it is the only capability that runs **unattended**, so an admin must be
  able to decline it without disabling the operator's interactive status check. It needs all three
  keys because, unlike `status` (which degrades to the half it can read), a sweep that reads only
  half the conditions stays silent about the other half.
  (ii) **`sweep_entry` catches `ConfigError` and emits an admin-attributed notice** naming the
  missing keys — it never raises and never returns silence. The same rule applies one layer down: a
  gather in which every read came back unavailable is also not silence. Zero fired conditions counts
  as healthy only when the reads that would have fired them succeeded.
  **This is NOT T-29-19.** T-29-19 is a sweep that stops *firing*, unobservable from inside and
  correctly deferred to v0.7. This is a sweep that *does* fire and cannot do its job, which it can
  observe and report. Do not merge them: doing so either promotes deferred scope or excuses a live
  hole. Tracked as T-29-24, disposition **mitigate**. Note this adds no heartbeat — the notice fires
  only on failure, so silence-when-healthy is untouched.

- **D-16 (write-safety is a PAIR of flags, and `disagreement` is the signal, not noise).** 29-05
  described the stuck-armed condition as reading "the write-safety flag", singular.
  `status.py:23` `WRITE_SAFETY_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE")` is a
  pair declared over **different node subsets** (8 and 9), and `n8n_read.read_write_safety(body,
  flag)` takes one flag at a time and returns `{value, nodes, disagreement}`. **Decision:** check
  both flags, and treat a truthy `disagreement` as **firing** rather than as unknown. A partially
  armed workflow is precisely the residue a crash between arm and disarm leaves — the case this
  backstop exists for (Phase 28 D-03) — so swallowing it as "unknown, therefore quiet" would blind
  the backstop to its own headline scenario.

- **D-17 (detecting a swallowed maintenance failure needs `runData`, which costs an extra GET).**
  D-08b's blind spot cannot be detected from the collection read: `recent_executions()` /
  `last_execution()` objects carry `id`, `status`, `startedAt`, `stoppedAt` and **no run data**, so a
  check written against them could never fire. **Decision:** use `n8n_read.get_execution` (which
  fetches with `includeData=true`) plus `execution_errors.harvest_errors(execution)`
  (`execution_errors.py:81`, already used this way at `:148`), which returns
  `{available, reason, findings}` with every message already translated and attributed. The extra
  per-execution GET is I/O, so it lives in `sweep_read.py`'s gather — widen that gather's documented
  scope rather than reaching for a client from a condition module — and stays gated per
  `get_execution`'s own T-27-18 rule: the maintenance workflow's most recent execution(s) only, never
  every execution in a page. Unbounded, it would turn a cheap sweep into an expensive one on a
  cadence.

- **D-18 (the attribution helper exists; name it, do not hedge).** 29-03 and 29-05 both said to
  "reuse Phase 27's attribution helper **if it exposes one**" and otherwise mirror its rules. It
  exposes one: `error_table.translate(text)` → `{matched, cause, sentence, who_can_fix,
  is_interpretation, raw}`. It imports only `re`, and D-05's guardrail lives **inside** it — an
  unmatched cause attributes to `admin` unconditionally, so a caller that forgets the rule cannot
  produce a wrong "you can fix this". **Decision:** import it. The hedge invited a second attribution
  convention, and the failure mode of two conventions is the operator being told two different things
  about the same error on two different surfaces. The cheapest guarantee that two surfaces agree is
  that they call the same function.

- **D-19 (the sweep's no-credit property is backend-mediated, not structural — say so in the
  cadence).** Every sweep fire POSTs `hubspot/backend-status`, whose docstring records that it
  "probes all three providers unconditionally" — it takes no request body, so it cannot know which
  providers a caller cares about. These are **balance** endpoints, not match or enrich ones, so no
  enrichment credits are consumed and D-02 holds. But it holds because of *what the backend endpoint
  does*, not structurally on the client the way the import-graph guard is. **Decision:** 29-06's
  cadence note states this rather than implying the sweep is free at any frequency, and the default
  cadence is expressed in hours, not minutes. If a provider ever meters balance checks, cadence is
  the only dial that limits the cost.

- **D-20 (the timing measurement runs through the dotenv wrapper, verbatim).** A bare
  `python scripts/...` from a fresh shell **silently sees no credentials** (HANDOFF §6) — it does not
  error, it returns an empty result indistinguishable from "no executions to measure". The
  consequence is a *provisional* bound recorded when a measured one was available, and D-06 forbids
  guessing. **Decision:** 29-02 Task 3 carries the wrapper verbatim
  (`.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/enrichment_cost_ledger.py', run_name='__main__')" durations`), and "no credentials"
  is a finding only once observed *through* it.

- **D-21 (the maintenance search-node names, verbatim).** 29-RESEARCH.md abbreviates them, and the
  abbreviations match no key in `runData`. The five, as they appear in the deployed JSON:
  `SJ-1 Search (input-gap scan)`, `SJ-2 Search (stale refresh)`, `SJ-3 Search (requested poller)`,
  `Dedupe Search (candidate contacts)`, `Review Search (approved=true)`. All five carry
  `onError: continueRegularOutput`, so **Pitfall 1's substance is unchanged** — only the spelling was
  wrong. Fixtures keyed on the abbreviations would pass while the live code found nothing.

- **D-22 (the three provider states, as the deployed endpoint actually emits them).** Folded in by
  29-02 after reading the artifacts. 29-RESEARCH Pitfall 5 says "Phase 27's endpoint already returns
  `{configured: bool, credits: int|None, ...}` per provider" — **it does not**, and a fixture built
  to that sentence would carry a `configured: false` balances row production never emits. What
  `Build Credit Status` really emits (`scripts/build_cloud_workflows.py:4453-4471`) is one row per
  **requested** provider, `{provider, configured, credits, unreadable, error, status}`, with
  `configured` **hardcoded `true`** and `unreadable === (credits === null)`. So the three states are:
  1. **numeric** — `credits` a number, `unreadable: false`;
  2. **unknown** — `credits: null`, `unreadable: true`, plus a `credential_health` entry
     `state: "refused"` (Apollo's 403-by-design). Never "exhausted", never "healthy";
  3. **never probed** — **absent from `balances` entirely**, present in `credential_health` as
     `{state: "unknown", reason: "not_configured"}` — `deriveSourceHealth`'s real `configured: false`
     output (`n8n/code/backendStatus.js:37`).

  Pitfall 5's substance is unchanged (unknown must never fire the exhausted notice); only the shape
  was wrong. **29-05's `is_quota_exhausted` must therefore read `balances` for states 1 and 2 and
  `credential_health` for state 3** — a provider missing from `balances` is not zero-credit, and
  reading only `balances` would make state 3 invisible. Note also that the rendered plugin-side view
  (`status.py::render_backend_status`) keeps only `{provider, credits}` from each balances row, so
  the sweep must consume `fetch_backend_status()`'s raw `data`, not the rendered mapping.

- **D-23 (the executions collection carries no `workflowData` on this tenant).** Found live by 29-02
  Task 3. Every item in `/api/v1/executions` has `workflowData: undefined`, so a per-workflow filter
  reading `workflowData.name` matches **nothing** and prints an empty table — indistinguishable from
  "no executions to measure", the exact D-20 failure in a second guise. `enrichment_cost_ledger.py`'s
  `list` mode already knew this and falls back to a `workflowId → name` map from the workflow
  collection; `collect_durations()` now does the same, with a regression test. Any later code
  filtering executions by workflow name must resolve through the workflow collection.

### Claude's Discretion
- Sweep cadence default and whether it is admin-configurable — bounded by D-19: state the
  all-three-providers probe per fire, and prefer hours over minutes.
- Notification wording and grouping when several conditions fire at once.
- Review-backlog threshold default.
- Backoff schedule within the in-session watch.
- Whether the watch reports incrementally as chunks settle or only once at the end.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions (locked)
- `.planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-CONTEXT.md` — the
  read surface the sweep runs on. D-08 (unknown is never zero) and D-04/D-05 (error translation and
  its guardrail) both apply directly to notice text.
- `.planning/workstreams/plugin-entrypoint/phases/28-control-actions/28-CONTEXT.md` — D-03 names
  this sweep as the backstop for the arm/disarm crash window. Notices point at the controls Phase
  28 exposes.
- `.planning/workstreams/plugin-entrypoint/phases/26-outcome-reporting-safe-retry/26-CONTEXT.md` —
  D-06's run handle is what "how to re-check" refers to. D-07 there deliberately deferred the poll
  loop to this phase, so the watch is built here **once**.
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-CONTEXT.md` —
  D-11a's missing batch-timing data is the same gap D-06 here depends on; measure once, use twice.

### Research already completed
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-RESEARCH.md` —
  the ~100s n8n Cloud webhook response ceiling and the absence of a `Split In Batches` node, which
  together determine how long a run realistically takes and therefore what the watch bound must be.
- `.planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-RESEARCH.md` — the
  stuck-lock / queued / review-backlog filter definitions the sweep re-uses verbatim.

### Milestone scope and requirements
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` — NOTICE-01..05. §"Future Requirements"
  is binding here: **unattended *ingestion* is explicitly deferred** — the sweep watches and
  reports but never dispatches a batch on its own. Sending stays operator-initiated by design.
- `.planning/workstreams/plugin-entrypoint/ROADMAP.md` §"Phase 29" — goal and five success criteria.

### Repo conventions
- `CLAUDE.md` §19 — the existing scheduled-job semantics (stuck-lock cleanup, needs-review queue,
  stale refresh). The sweep reports on these; it does not replace them.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 27's entire read surface — the sweep is that surface on a timer plus a notification.
- Phase 26's run handle and outcome renderer — the in-session watch reports through the same
  renderer rather than a second one.
- The repo's existing scheduled jobs (CLAUDE.md §19) already define what a stuck lock and a review
  backlog are; the sweep does not invent new definitions.

### Established Patterns
- **Read-only by construction.** The repo's disarmed-by-default posture generalized: the safest
  component is one with no code path to a write.
- **Honest attribution.** Inherited from Phase 27 D-05 — an unrecognized cause names an admin
  rather than guessing the operator can fix it.
- **Silence means healthy.** Notices are exceptions, not a heartbeat.

### Integration Points
- Reads: Phase 27's status surface and the n8n read API. Nothing else.
- Writes: none. Structurally none (D-02).
- Delivery: a push notification into the operator's Claude surface.

</code_context>

<specifics>
## Specific Ideas

- "It never simply stops talking" is the real requirement in NOTICE-02. A watch that hits its bound
  and says nothing is worse than no watch, because the operator believes it is still watching.
- The sweep's value is proportional to how rarely it speaks. A noisy sweep gets ignored, and an
  ignored sweep is the same as no sweep.

</specifics>

<deferred>
## Deferred Ideas

- **Unattended ingestion** — permanently deferred by REQUIREMENTS.md §"Future Requirements". The
  sweep never dispatches.
- **Acting on findings automatically** — out of scope. Notices point at Phase 28's controls; a
  human decides.
- **Alternative sweep hosts (n8n-side, OS cron)** — considered and rejected (D-01). Revisit only if
  D-04's availability check fails.
- **Per-condition notification channels** — all notices use one delivery path in this phase.

</deferred>

---

*Phase: 29-notices-unattended-sweep*
*Context gathered: 2026-07-30*
