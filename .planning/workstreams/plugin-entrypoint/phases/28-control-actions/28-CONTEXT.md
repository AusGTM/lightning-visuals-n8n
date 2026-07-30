# Phase 28: Control Actions - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 28 is **the only phase in this milestone that mutates the backend**. The operator can start a
run, turn a workflow on or off, re-time a scheduled job, and enable live writes — all from the
conversation, each mutation confirmed before it happens and verified by read-back after.

The mutation set is **allowlisted**: write-safety flag overlay, Schedule Trigger cadence, a Schedule
Trigger node's `disabled` boolean (added by D-25, 2026-07-31 — amendment #6), and workflow active
state. **Four items.** Any other workflow-JSON change is **refused rather than attempted**. Arbitrary
workflow deployment from the plugin is a permanent exclusion — editing nodes, credentials, or
workflow structure stays an admin task run from this repo.

Nothing may be flipped that Phase 27 cannot first read: every confirmation and every read-back
verification is built on that read surface.

</domain>

<decisions>
## Implementation Decisions

### Live-write arming — resolving the conversation-scope contradiction
- **D-01:** CONTROL-04 requires live-write permission to be conversation-scoped, but n8n's
  write-safety flag is **persistent backend state that outlives any conversation**. Resolution:
  the plugin **arms immediately before dispatch, dispatches, then disarms**, with **read-back
  verification in both directions**.
- **D-02:** This scopes the permission **tighter than the conversation** — to the span of a single
  operation. "Never inherited by a later session" therefore holds by construction rather than by
  promise, which is strictly stronger than CONTROL-04 asks for.
  — **Reversibility:** costly — the alternative (arm-for-the-session with a TTL sweep) makes the
  lapse depend on Phase 29's sweep actually running, and unwinding to it later means rebuilding the
  arming lifecycle and its verification points.
- **D-03:** **Known failure mode, must be handled explicitly:** a crash or interruption between
  dispatch and disarm leaves the backend armed. Mitigations required in the plan: (a) Phase 27's
  status readout reports the true flag state read from n8n, so a stuck-armed backend is visible;
  (b) Phase 29's sweep is the backstop that catches it unattended. The plugin must not pretend
  disarm always succeeds — a failed disarm is reported loudly, not swallowed.
- **D-04:** Every status readout states plainly whether live writes are currently on, read from the
  backend (Phase 27 D-03), never asserted from local config.

### Starting a run
- **D-05:** Runs are started by **the mechanism each already has**: an ingestion lane is started by
  its **existing webhook POST** — the same dispatch path with its preview, cost guard, and arming
  gate intact. A **scheduled scan** has no payload and no webhook, so it is started through the
  **n8n API**.
- **D-06:** Rationale worth preserving: starting an ingestion lane via the n8n API would bypass the
  preview, cost guard, and arming gate that Phases 23 and 25 built. The guards live on the dispatch
  path, so the dispatch path is the only way in for a lane.
- **D-07:** No new manual-trigger webhooks are added to workflows. Each would be another entry
  point to secure for no gain.
- **D-05a (AMENDS CONTROL-01 — off-cycle scheduled scans are dropped):** 28-RESEARCH.md found that
  **`POST /api/v1/workflows/{id}/execute` does not exist** — it is an open, unmerged upstream PR
  (#20304) requiring a `workflow:execute` scope. There is no endpoint to start a scheduled scan
  off-cycle today.
- **D-05b:** Resolution: **CONTROL-01 narrows to the two ingestion lanes**, which do have webhooks
  and work as D-05 describes. Scheduled scans are controlled instead through capabilities this
  phase already delivers — **enable/disable (CONTROL-02)** via
  `POST /api/v1/workflows/{id}/activate` / `/deactivate`, and **re-timing (CONTROL-03)** via the
  allowlisted Schedule Trigger cadence mutation. "Run this scan right now" is simply not an offered
  capability.
- **D-05c:** The rejected alternative and why: repurposing the Schedule Trigger cadence as a
  one-shot near-future fire would mutate a schedule in order to simulate a trigger, and a crash
  between "set to fire soon" and "restore prior cadence" leaves the backend on the wrong schedule —
  silently changing how often it burns provider credits. That is a new failure mode on the surface
  whose entire purpose is safe control. Not worth it for a capability the operator can reach
  another way. ROADMAP Phase 28 criterion 1 and REQUIREMENTS CONTROL-01 both need their
  "scheduled scan off-cycle" clause dropped before this phase seals.
  — **Reversibility:** reversible — if upstream PR #20304 lands, off-cycle execution becomes a
  small addition rather than a redesign.

### Cadence
- **D-08:** Cadence accepts **free-form natural language**, parsed to a schedule — but the parse is
  **interpreted back to the operator in plain language for confirmation before any conversion to
  cron**. The operator confirms "so: every weekday at 9am and 5pm" before anything is written.
- **D-09:** The confirmation step is what makes free-form safe. A misparse silently changing how
  often the backend burns provider credits is the failure this guards against, and the operator
  sees the interpretation, not the cron string. **Cron syntax never appears to the operator** in
  either direction (CONTROL-03).
- **D-10:** A parse the plugin cannot confidently interpret is **refused with examples**, not
  guessed at.

### Reversibility statement
- **D-11:** Before mutating, the plugin **captures the prior state and quotes it back** when the
  change lands: "it was hourly; to undo, I'll set it back to hourly." Exact even when the prior
  value was unusual.
- **D-12:** This costs nothing extra — the pre-read is already required for CONTROL-06's read-back
  verification, so the prior value is in hand either way.

### Confirmation and verification (from requirements, restated as binding)
- **D-13:** Every mutation states its consequence in plain language before it happens, shows what
  will change, and waits for **explicit confirmation** (CONTROL-05).
- **D-14:** After every mutation the plugin **re-reads the backend and reports verified or failed**.
  A `200` from n8n is **never** reported as success on its own (CONTROL-06).
- **D-15:** Any requested change outside the allowlist is **refused, not attempted** (CONTROL-05).

### Mutation mechanics — corrected by research
- **D-16:** The `PUT /api/v1/workflows/{id}` body is a **strict 4-key allowlist** — `name`, `nodes`,
  `connections`, `settings`. n8n rejects anything else with `"must NOT have additional properties"`.
  `scripts/deploy_n8n_workflows.py::_update_workflow_live()` already implements this filter
  correctly; **reuse it verbatim** rather than re-deriving it.
- **D-17 (this phase's central risk):** A bare `GET`-after-`PUT` proves the value was **persisted**,
  not that the running instance is **honoring** it. Community and upstream evidence indicates an
  already-active workflow does not reliably reload updated Code-node or Schedule-Trigger content
  until deactivated and reactivated. These are **different claims** and the plan must treat them
  separately — CONTROL-06's read-back must verify *effective*, not merely *written*.
- **D-18:** Therefore every mutating PUT is bracketed **deactivate → PUT → activate**, and the plan
  carries an **early live-fire verification task** (flip the flag, dispatch, inspect what was
  actually written) to convert this from inference to observed fact. This is a Wave-0 task, not an
  assumption baked into later tasks.
- **D-19:** D-15's structural allowlist enforcement is implemented as a **node-by-node diff between
  the fetched original and the outgoing body**, refusing the PUT if anything outside the allowlisted
  node(s)/fields differs. This makes an out-of-allowlist change *impossible* rather than merely
  unattempted, which is what CONTROL-05 asks for.
- **D-20:** A **no-op GET→PUT round-trip test** is the first live PUT this phase performs, to
  confirm `settings` and `connections` survive the round trip cleanly on this n8n Cloud version.

### Findings from planning — these change the phase's shape
- **D-21 (arming is a FOUR-constant overlay, not one flag — and the flag alone is a no-op):** the
  deployed `_writeSafetyAllows()` in every write gate begins
  `if (!allowedDomains.length && !allowedIds.length) return false;` — **an empty allowlist denies
  everything**. Setting `ALLOW_HUBSPOT_RECORD_WRITES = "true"` with empty `TEST_RECORD_IDS` /
  `TEST_RECORD_DOMAINS` therefore **grants nothing while reporting a successful arm**. The research
  assumed a single-flag flip. Arming must refuse an empty allowlist and **derive it from the
  batch** — which makes the grant **record-scoped as well as operation-scoped**, strictly stronger
  than D-02 claims.
- **D-22 (`enable_baked_flags()` cannot disarm):** its exact-literal replace searches for the
  *disabled* declaration, so it only widens disabled→enabled. **Disarm needs a bidirectional
  mirror** carrying the same fail-closed re-scan — and that re-scan is precisely what makes D-03's
  loud disarm-failure detectable.
- **D-23 (node counts reconciled — both planners were right):** verified directly against the
  committed JSON. `ALLOW_HUBSPOT_RECORD_WRITES` appears in **8** nodes (contact 2, enrichment 2,
  maintenance 4); `ALLOW_HUBSPOT_CREATE` appears in **9** (contact 3, enrichment 2, maintenance 4).
  The contact lane carries three `CREATE` but only two `RECORD_WRITES` because Phase 23 added the
  third at `Decide Action`. **The two flags are declared in different subsets**, so any fixed node
  list is wrong for at least one flag. Scan every node; report disagreement.
- **D-24 (the bracket must RESTORE, not blindly activate):** `deactivate → PUT → activate` must
  restore the **prior** active state. Blindly activating would silently turn on a workflow the
  operator had deliberately left off — a mutation nobody requested, arriving as a side effect of
  re-timing a schedule. The research's pattern does not say this.

- **D-25 (allowlist widened by exactly one field — operator decision, 2026-07-31):**
  `LV Scheduled Maintenance (Cloud)` carries **five Schedule Triggers in one workflow**, so
  workflow-level activate/deactivate cannot express CONTROL-03's "disable **a scheduled job**". The
  mutation allowlist is therefore **widened by one field**: a Schedule Trigger node's `disabled`
  boolean. Constraints that make this bounded rather than open-ended:
  - It is a **single boolean on a node type already in the allowlist**.
  - It carries the **same field-level diff enforcement** as every other mutation (D-19), so it
    cannot be used as a foothold to rewrite anything else in the node.
  - It carries the **same read-back verification** (D-14).
  This **amends the allowlist definition in REQUIREMENTS.md** — the milestone's sixth accepted
  amendment. The rejected alternatives: refusing per-job control would have amended CONTROL-03
  instead (narrowing "a scheduled job" to "a workflow"), and splitting the five triggers into
  separate workflows was a structural backend change far outside a control-surface phase.
  — **Reversibility:** reversible — removing the field from the allowlist is a one-line change plus
  the operator-facing wording.

### Corrections against the shipped Phase 27 code (folded in 2026-07-31 after a plan-checker run)

**Why these exist:** Phase 28's plans were written against Phase 27's RESEARCH document, before
Phase 27 had shipped. Phase 27 is now code-complete and the real modules differ from what the plans
assumed. `gsd-plan-checker` returned 5 blockers and 7 concerns; these decisions are the resolutions.
**A correction left only in a plan gets re-litigated — that is why they are here.**

- **D-26 (`read_write_safety` ALREADY EXISTS — do not write a second one):**
  `operator-claude-plugin/scripts/n8n_read.py::read_write_safety(workflow_body, flag_name)`
  (module line 229, shipped by 27-01) returns `{value, nodes, disagreement}`, already scans every
  node, and its declaration regex at line 247 is character-for-character
  `deploy_n8n_workflows.py::enable_baked_flags()`'s own fail-closed re-scan regex (deploy line 374).
  `n8n_arming.py` **imports and calls it**, looping it over the four `_OVERLAY_FLAG_SPEC` names, and
  defines no reader and no second declaration regex. `conftest.py` puts `scripts/` on `sys.path`
  flat, so two same-named readers would both be importable under bare names — and a duplicate cannot
  detect the desync it is itself the cause of. **`set_write_safety` is the only genuinely new
  function**; its fail-closed re-scan *calls* `n8n_read`'s regex rather than copying it.

- **D-27 (`fetch_workflow` is not to be written either — reuse `n8n_read.get_workflow`):**
  `n8n_read.get_workflow(config, workflow_id, transport)` (line 88) is the same GET against the same
  endpoint with the same `X-N8N-API-KEY` header, already config-based and already injectable. Its
  `None`-on-every-failure-mode contract feeds the `failed` verdict rule directly: an unreadable
  read-back is not a verified one. Note the argument order is `(config, workflow_id, ...)`.

- **D-28 (the transport seam — `transport=requests`, never `transport=requests.put`):**
  `operator-claude-plugin/tests/test_retry_reuses_dispatch.py` is a structural guard no earlier
  Phase 28 plan mentioned. It `rglob`s **every** `operator-claude-plugin/scripts/*.py`, including
  modules not yet written (line 110); flags any function whose `transport` parameter defaults to
  `requests.post`/`requests.put` (line 129) or that calls `requests.put(...)` directly (line 146);
  and allowlists exactly two functions in `_EXPECTED_SEND_SHAPED` (line 192) —
  `backend_status.py::fetch_backend_status` and `dispatch.py::dispatch`.
  **Binding rule for all four of this phase's new modules:** the `transport` parameter defaults to
  the **bare `requests` module**, and every call goes through `transport.put(...)` /
  `transport.post(...)`. That matches `n8n_read.py`'s injectable-READ seam, not `dispatch.py`'s SEND
  seam (`dispatch.py:26` is `transport=requests.post`). **Appending to `_EXPECTED_SEND_SHAPED` is a
  weakening and is forbidden** — that list is what stands between a retry path and the arming gate
  `dispatch()`'s no-default `armed` parameter enforces. `git diff --stat` on that test file must be
  empty when the phase closes.

- **D-29 (one credential source: `config_gate`, and control is its own capability):** the plugin has
  never read `N8N_URL` / `N8N_API_KEY` from the shell — those are the backend deploy script's
  variables. Everything plugin-side loads credentials with `config_gate.load_config()` from
  `config/operator.local.json`. Consequences, both binding:
  - **28-01 adds `"control": ("n8n_url", "n8n_api_key")` to `config_gate.CAPABILITY_KEYS`**, and
    28-05 calls `require_capability(cfg, "control")` at the surface entry point. Control is a
    separate capability from `"status"` because a config that may read the backend is not thereby
    one that may mutate it. This follows 27-03's explicit instruction: add a row, do not re-add a
    global gate.
  - **Any wrong-instance guard compares `config["n8n_url"]` against `N8N_EXPECTED_URL`** — the value
    the request actually authenticates with. A guard reading `os.getenv("N8N_URL")` while the
    request authenticates from config is a guard that cannot fire.
  - **The probe's enabling variable is named `ALLOW_N8N_PROBE`**, must read exactly `true`, and
    matches the repo's existing `ALLOW_N8N_DEPLOY` idiom. It was previously referred to only as "the
    probe's enabling environment variable", which a human checkpoint cannot be run against.
  - The deploy tenant is confirmed `https://alexherman.app.n8n.cloud` and `N8N_EXPECTED_URL` is now
    set to it in `.env`.

- **D-30 (there is ONE ingestion-lane dispatcher, not two — discover, never assume):**
  `dispatch.py::dispatch` (line 26) is contact-lane only: multipart CSV, `files={"data": ...}`,
  `X-Enrichment-Secret`. The **enrichment lane's dispatcher is Phase 25 work** (25-03/25-04), and
  both are blocked behind the **25-01 human checkpoint, which has not been written**. So
  `start_lane` fronts *whichever lane dispatchers exist at execution time*, resolved at call time,
  and refuses a lane with no dispatcher by name — never raising an ImportError and never silently
  routing an enrichment batch down the contact lane's CSV path. CONTROL-01's wording becomes "either
  ingestion lane **that is built**".

- **D-31 (the allowlist charset pin compares the character class, not the separator):** the deploy
  script's `_ALLOWLIST_VALUE_RE` (line 156) permits `|`, converted to a comma at line 440, **only**
  because `,` already separates entries inside the `ENABLE_BAKED_FLAGS` environment-variable
  envelope. The plugin has no such envelope, so **comma-direct is correct plugin-side**. Pin
  `[A-Za-z0-9._-]`; a test that pinned `|` would fail a correct implementation.

**Also corrected, mechanically:** every deploy-script line citation in the Phase 28 plans was stale
by 12–18 lines and has been refreshed against the current file — `_base_url`/`_n8n_headers`/
`_get_live_workflows` 182–201, `_has_n8n`/`_instance_ok`/`_writes_allowed` 159–179,
`_OVERLAY_FLAG_SPEC`…`_ALLOWLIST_VALUE_RE` 141–156, `enable_baked_flags` 310–388,
`_requested_overlay_flags`'s two fail-safes 455–472, `_create_workflow_live`/`_update_workflow_live`
474–488.

**Verified correct and NOT to be "fixed":** the 8 `RECORD_WRITES` / 9 `CREATE` node counts in
different subsets (D-23); the five Schedule Trigger names; `settings == {}` on the maintenance
workflow; the four-key `(name, nodes, connections, settings)` filter; `assert_only_allowlisted_change`
running **before** the deactivate; the prior-active-restoring bracket (D-24); and the `no_network`
guard's coverage of GET — it is **not** GET-blind, verified three separate times.

### Claude's Discretion
- Wording of consequence statements per action type.
- Confirmation phrasing and how the diff of "what will change" is displayed.
- How the natural-language cadence parse is performed and how its interpretation is rendered.
- Retry posture when a read-back verification is inconclusive.
- Whether arm/disarm and the dispatch are presented to the operator as one action or three.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions (locked)
- `.planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-CONTEXT.md` — the
  read surface every confirmation and verification here depends on. D-03 there (read state from
  n8n, never assert from config) is what D-04 here relies on.
- `.planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-CONTEXT.md`
  — D-11 there is the interim client-side arming this phase supersedes with the real n8n-side
  mechanism.
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-CONTEXT.md` —
  the cost guard and chunked dispatch that D-05/D-06 must not bypass.

### Research already completed (read before planning)
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-RESEARCH.md` —
  the enrichment envelope and the n8n Cloud webhook response ceiling (~100s), which bounds how long
  an arm→dispatch→disarm cycle can hold the flag open.
- `.planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-RESEARCH.md` — where
  the write-safety flag actually lives in the deployed workflow JSON and how a client reads it.
  **This phase writes the same flag it reads, so the two must agree exactly.**

### Milestone scope and requirements
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` — CONTROL-01..07. §"Endpoints (targets)"
  gives the mutation surface: `POST /api/v1/workflows/{id}/activate` and `/deactivate` need no JSON
  write; `PUT /api/v1/workflows/{id}` is **allowlisted mutations only**. §"Out of Scope" forbids
  arbitrary workflow deployment from the plugin.
- `.planning/workstreams/plugin-entrypoint/ROADMAP.md` §"Phase 28" — goal and five success criteria.
  Also §"Safety posture, inherited and non-negotiable" in the Overview, which names this phase's
  widening of plugin authority and states that the allowlist plus confirm-and-verify is what keeps
  it bounded.

### Repo conventions
- `scripts/deploy_n8n_workflows.py` and the build scripts — how the write-safety flag overlay is
  applied today by an admin. The plugin's arming must produce the **same** flag state, not a
  parallel convention.
- `CLAUDE.md` §21 — safety gates and the high-risk write list.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 27's read surface — workflow state, execution state, and the write-safety flag read. Every
  mutation here is bracketed by two of those reads. **Phase 27 has SHIPPED; these are real modules,
  not planned ones** — read `operator-claude-plugin/scripts/n8n_read.py`, `config_gate.py` and
  `status.py` on disk, and `27-01-SUMMARY.md`…`27-05-SUMMARY.md`, before writing anything. Every
  function named in D-26 through D-29 exists today. See also the "Interfaces 27-04 Inherits" section
  of `27-03-SUMMARY.md`, which is the authoritative signature list.
- The admin-side write-safety flag overlay in the deploy scripts — the canonical definition of what
  armed means in this repo.
- Phase 23's dispatch path, which D-05 reuses verbatim for lane starts.

### Established Patterns
- **Two-key write gate.** Phases 19–22 all follow it. This phase automates the operator's key while
  keeping the gate itself.
- **Confirm, then verify.** The repo's armed operations already read back rather than trusting a
  success status. D-14 is that discipline applied to control actions.
- **Allowlist over generality.** Consistent with the milestone's refusal to become a deploy
  pipeline.

### Integration Points
- `POST /api/v1/workflows/{id}/activate` / `/deactivate` — no JSON write, lowest-risk mutation.
- `PUT /api/v1/workflows/{id}` — allowlisted only: write-safety flag overlay, Schedule Trigger
  cadence, and a Schedule Trigger's `disabled` boolean (D-25). Everything else refused.
- Existing webhooks — lane starts (D-05). **One dispatcher exists today**, contact lane only; see
  D-30.
- Phase 27's status endpoint and n8n read API — pre-read and read-back for every mutation.

</code_context>

<specifics>
## Specific Ideas

- The arm→dispatch→disarm cycle is the heart of this phase. It converts a persistent backend flag
  into an operation-scoped grant, which is the only honest way to satisfy "conversation-scoped"
  against state that has no concept of a conversation.
- Confirming the *interpretation* of a cadence rather than the cron string is the same principle as
  showing a preview before dispatch: the operator confirms meaning, never syntax.

</specifics>

<deferred>
## Deferred Ideas

- **Unattended detection of a stuck-armed backend** — Phase 29 / NOTICE-03. D-03 names this as the
  backstop for the arm/disarm crash window.
- **Arbitrary workflow deployment or node editing from the plugin** — permanent exclusion, not
  deferred.
- **Review-queue writeback gating** — Phase 30 / REVIEW-03, which has its own session-scoped
  confirmation separate from dispatch arming.
- **FURTHER widening of the mutation allowlist** — out of scope; any addition is a new requirement,
  not a planning decision. **This no longer covers the Schedule Trigger `disabled` field**: that
  widening was surfaced as a requirement, accepted by the operator on 2026-07-31, and recorded as
  D-25 and as the milestone's sixth accepted amendment. The allowlist is now **four** items. This
  bullet's earlier absolute wording is what let a planner reopen D-25 as a live decision checkpoint;
  it reads as a boundary on *future* additions only.

</deferred>

---

*Phase: 28-control-actions*
*Context gathered: 2026-07-30*
*Corrections D-26…D-31 folded in 2026-07-31 from a `gsd-plan-checker` run (5 blockers, 7 concerns),
after Phase 27 shipped. D-25's status as a settled amendment was reasserted at the same time.*

### D-32 — the repair's own drift, caught by the re-check (2026-07-31)

A second checker run over the repaired plans found the repair had **orphaned a reference in the one
file it did not edit**. `28-06` still described the mutation allowlist as *"the three allowlisted
mutations … plus per-job schedule enablement **if 28-04's decision permitted it**"* — the deleted
checkpoint's conditional voice. Since D-25 settled that decision, an allowlist documented as three
conditional items would have contradicted the code, this file, and the REQUIREMENTS/ROADMAP text
28-05 Task 3 writes. **The allowlist is four items, unconditionally**, the fourth being a Schedule
Trigger node's `disabled` boolean. Corrected in `28-06`.

Also corrected there: `28-06`'s precondition named `N8N_URL`/`N8N_API_KEY` as shell variables, which
the B4 repair had already established the plugin never reads — it loads credentials only from
`operator.local.json` via `config_gate.load_config()`. The precondition now names the operator
config and `N8N_EXPECTED_URL`, with the deploy-script steps called out as the genuine exception,
since `deploy_n8n_workflows.py` is a repo script and does read the shell environment.

**Lesson for future repairs: a fix that edits N of M plans must re-scan the other M−N for references
to what it changed.** The re-check is what caught this; the repair pass did not.

### D-34 — gating is uniform: every dangerous operation carries an env kill switch (2026-07-31)

**Operator decision.** The re-check noted an asymmetry: 28-02's *read-only* diagnostic probe is gated
behind `ALLOW_N8N_PROBE`, while `n8n_arming` — the only module in the milestone that writes a
write-safety constant's **enabled** literal to a live workflow — had no env gate at all, relying
solely on the human checkpoint and `execute_action`'s no-default confirmation.

That inverts this repo's established convention. Nine `ALLOW_*` gates already exist
(`ALLOW_N8N_DEPLOY`, `ALLOW_HUBSPOT_CREATE`, `ALLOW_HUBSPOT_RECORD_WRITES`,
`ALLOW_HUBSPOT_PROPERTY_WRITES`, `ALLOW_WEB_RESEARCH`, `ALLOW_JUDGE_ESCALATION`,
`ALLOW_LUSHA_PROBE`, `ALLOW_CANONICAL_WRITES`, and now `ALLOW_N8N_PROBE`). The rule is now explicit:
**gating behaviour is the same everywhere — one `ALLOW_*` variable per dangerous capability, value
must read exactly `true`, checked before any transport is constructed, refusing in plain language
that names the variable and says an admin sets it.**

`ALLOW_N8N_ARM` is added to `n8n_arming` in 28-03 accordingly. Three properties are load-bearing:

1. **It gates arming only, never disarming.** A kill switch that blocked a disarm would strand an
   armed backend — the exact failure this phase's ceremony exists to prevent.
2. **Its semantics must match `ALLOW_N8N_PROBE`'s exactly.** Two gates in one phase that disagree on
   what counts as "on" is worse than one gate, because the operator learns a rule that is false half
   the time. Near-miss values (`1`, `yes`, `TRUE`) refuse in both.
3. **It is defence in depth, not a replacement.** The human checkpoint and the no-default
   confirmation both stay. It is the gate that still holds when an agent, a test harness, or a
   scheduled routine reaches the module by a path nobody anticipated.

### D-33 — the transport object shape is a real seam change, and no fixture matches it yet

D-27's `transport=requests` rule (bare module, called as `transport.put(...)`) correctly keeps
Phase 28 out of `test_retry_reuses_dispatch.py`'s `_SEND_CALL_ATTRS = {"post","put"}` guard — but it
is a **different object shape** from everything shipped. Verified 2026-07-31:
`tests/conftest.py`'s `_StubTransport` (:114) and `_StubGetTransport` (:174) are **callables**, not
module-shaped objects carrying `.get`/`.post`/`.put`; and `n8n_read.get_workflow(config, id,
transport=requests.get)` (:88) passes `transport` straight to `_get_json`, which **calls** it (:58).

So every "recording transport" acceptance criterion in this phase is unsatisfiable with the shipped
fixtures, and a module-shaped transport must be handed down to `n8n_read` as `transport.get`, not as
`transport`. The executor of 28-01 adds a module-shaped recorder fixture whose `.get`/`.post`/`.put`
share one `calls` list. Not a safety defect — the first test run fails loudly — but it is real work
that no plan costed.
