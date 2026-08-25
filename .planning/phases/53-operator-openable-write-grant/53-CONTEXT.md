# Phase 53: Operator-openable write grant - Context

**Gathered:** 2026-08-25
**Status:** Ready for planning

<domain>
## Phase Boundary

An operator working in Claude Desktop can authorize HubSpot writes without anyone touching a
terminal, and that authorization is bounded, expiring and revocable. This phase delivers the
**grant** — its authority, its shape, its lifetime, and how it replaces the per-send arming
phrase. It does NOT deliver single-pass dispatch (Phase 54), async runs (55), the unattended
pair pipeline (56), or the ceiling enforcement and post-run proof (57).

The defect it exists to remove — G-2, found in a live client UAT on 2026-08-25:
`n8n_arming._arm_gate()` requires `ALLOW_N8N_ARM=true` **in the shell environment the session
runs in**, and an operator in Claude Desktop cannot set a shell variable. The documented
operator path therefore ends in a refusal only an admin with terminal access can clear. Every
HubSpot write this client has seen land was landed by an admin from a terminal.

</domain>

<decisions>
## Implementation Decisions

### D-53-01 — Authority: an admin-set settings key, with the env var kept for headless

- The interactive path's authority becomes an admin-set key in the operator settings file
  (`operator.local.json` — the file an admin already edits at install, outside the versioned
  plugin directory). Working name `allow_write_grants: true`; the planner may rename it, but
  it is a **settings key, not a capability row**: `CAPABILITY_KEYS` today means "these keys are
  present", not "an admin authorized this", and overloading it would blur a distinction the
  refusal wording depends on.
- `ALLOW_N8N_ARM` is **retained, unchanged, as the sole authority for headless/cron paths**
  (`scheduled_arm.py`). Those have no operator to confirm anything, so an env kill switch is
  the right shape there. Nothing about the sweep or the SJ-3 companion changes in this phase.
- **The arm/probe parity pin must be decoupled deliberately.**
  `test_control_arming.py::test_the_probe_and_the_arm_gate_use_the_same_comparison` currently
  couples the arm gate to `ALLOW_N8N_PROBE`'s comparison. The probe and deploy gates stay
  env-gated; the interactive arm no longer is. That test is re-pointed with the reason recorded
  in the test itself — never deleted, and never quietly weakened. Same for
  `test_with_the_gate_unset_the_arm_refuses_and_makes_no_call_at_all`: it keeps binding on the
  headless path.
- **`test_the_disarm_is_NOT_gated_on_the_kill_switch` is untouched.** Disarm must never require
  authority of any kind. If this phase makes disarm harder in any way, it is wrong.

### D-53-02 — Grant shape: the computed worst case IS the ceiling

- The operator names the batch. The system computes worst-case spend (provider credits,
  Anthropic dollars, projected n8n executions) and shows it before the yes; that figure becomes
  the grant's binding ceiling.
- **Accepted consequence, recorded rather than discovered later:** a ceiling derived from the
  batch cannot block anything the batch already implies. Its job here is **disclosure, not
  constraint**. The protective load therefore falls entirely on Phase 57's
  refuse-before-starting check against the remaining monthly execution allowance — that check
  is not optional tail-end work, it is the only thing standing between a large batch and the
  execution budget. The planner must not treat D-53-02 as if it delivered spend protection.
- An unbounded grant stays inexpressible: the batch must resolve to a concrete record set
  before the ceiling can be computed at all, which is the property that keeps the allowlist
  record-scoped.

### D-53-03 — Lifetime: client-held, for the session only

- The grant lives in the client for the conversation. No expiry written into the deployed
  workflow, no watchdog job. This is today's `armed_window` guarantee, extended in duration.
- **Accepted risk, stated plainly:** that guarantee depends on the Python process surviving. A
  crashed session, a closed laptop or a killed terminal leaves the backend armed with a live
  record-scoped allowlist and nothing watching it. The operator accepted this on 2026-08-25
  after the alternative (an expiry inside the shared write-safety gate) was offered and
  declined.
- **PROPOSED GUARDRAIL — the planner must surface this as a task, not assume it:** a
  session-start read of the live write-safety state that **refuses to open a grant when it
  finds writes already armed**, names what it found, and offers to disarm. This does not change
  D-53-03; it turns the accepted risk from silent into loud, and it is the only cheap defence
  available under a client-held design. Also: disarm on any unhandled exception and on session
  end, exactly as `armed_window.__exit__` does today.

### D-53-04 — Consolidation: the grant subsumes the per-send phrase

- While a grant is open, dispatches run under it. The per-turn "arm the enrichment" / "arm the
  upload" phrase is not asked again — that repetition is G-1, and removing it is the point of
  the phase.
- With no grant open, today's per-send behaviour is unchanged. The grant is an addition, not a
  replacement of the existing careful path.
- **A failed disarm fails that send only; the session continues.** Chosen deliberately so a
  transient blip does not abort a long run.
- **Accepted risk:** the run continues while the previous window's disarm state is unknown.
- **PROPOSED GUARDRAIL — surface as a task, do not assume:** bound the unknown. Two consecutive
  `disarm_failed` results, or a pre-flight read showing writes still live at the start of the
  next send, ends the session grant and blocks further sends. This keeps the operator's "one
  failure does not abort the run" while stopping an unbounded march of writes over an unknown
  backend state.

### D-53-05 — One grant spans both lanes of `enrich-before-ingest` (operator, 2026-08-25)

Raised by the planner as risk #2 and **accepted by the operator explicitly, for speed.**

- A single grant covers the enrich lane and the ingest lane of `enrich-before-ingest`. The
  operator is not asked a second time between them.
- **What this collapses, stated so nobody rediscovers it as a surprise:**
  `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` currently forbids
  a combined arming phrase and pins the enriched-preview heading as strictly preceding the
  ingest-arm heading. Its recorded reason (37-CONTEXT §6.3) is that a combined authorization is
  necessarily given **before the enriched preview exists** — so the HubSpot write is approved
  before the operator can see what they are approving. The enriched preview is the only place
  held rows and merge conflicts (source value kept over a differing provider value) become
  visible ahead of a write. Under D-53-05 those rows are authorized unseen.
- **What still holds:** the allowlist remains record-scoped to that batch, so the collapse
  widens *when* the approval is given, never *what* it covers. The enriched preview is still
  rendered, and revocation (GRANT-05) still works — the default flips from ask-again to
  proceed-unless-stopped, rather than removing the operator's ability to stop it.
- **Implementation discipline, same as the parity pin (D-53-01):** that contract test is
  changed by ONE deliberate edit that records this decision, its date, and who took it, inside
  the test file. It is never deleted and never weakened by a sweep. A future reader must be
  able to find out that the ordering protection was removed on purpose and by whom.
- Declined alternative, buildable and now deferred: one grant whose ingest half stays withheld
  until the enriched preview lands. Keeps both properties; it is a different design and its own
  phase.

### Claude's Discretion

- The settings key's exact name and where it sits in the file.
- How the grant object is represented in the client (dataclass vs dict) and which module owns
  it — `n8n_arming`, `control_actions`, or a new one.
- Refusal wording, provided it names what is missing and who can fix it, per the existing
  `config_gate` convention.

</decisions>

<specifics>
## Specific Ideas

- The operator's own words, from the UAT that produced this phase: *"Multiple arming steps -
  this can be compressed into a single approval set and there are far too many low level
  actions that need to be done to get from enrichment to write into Hubspot."*
- The consequence sentence `control_actions.plan_action` already produces for `arm_dispatch` is
  the right register for a grant's consequence: what turns on, bounded to what, what turns it
  off, and what happens if turning it off fails. Extend that shape rather than inventing a new
  one.

</specifics>

<canonical_refs>
## Canonical References

### The milestone
- `.planning/milestones/v1.1-REQUIREMENTS.md` — GRANT-01..06 are this phase's requirements;
  the "What must NOT be lost" section lists the five properties a grant may not regress.
- `.planning/milestones/v1.1-ROADMAP.md` — Phase 53's goal and its relationship to 54–57.
- `.planning/quick/260825-contact-company-association/UAT.md` — G-1..G-4, the live evidence.

### The arming stack this phase changes
- `operator-claude-plugin/scripts/n8n_arming.py` — `ARM_ENV_VAR`, `_arm_gate()`,
  `arm_for_dispatch()`, `armed_window`, `set_write_safety()`, and the allowlist charset rule
  (`_ALLOWLIST_VALUE_RE`, enforced because the re-scan's regex terminates at the first `;`).
- `operator-claude-plugin/scripts/control_actions.py` — `plan_action`'s `arm_dispatch` branch
  and `execute_action`'s one-cycle arm → dispatch → disarm.
- `operator-claude-plugin/scripts/n8n_control.py` — `apply_mutation`'s
  fetch → mutate → refuse-if-out-of-allowlist → deactivate → PUT → restore-prior-active
  sequence. The reactivation is what forces the running instance to reload (D-18).
- `operator-claude-plugin/scripts/config_gate.py` — `CAPABILITY_KEYS` and the refusal wording
  convention.
- `operator-claude-plugin/scripts/scheduled_arm.py` — prior art for an unattended armed window
  and the path that KEEPS the env gate.

### Tests that pin what must not move
- `operator-claude-plugin/tests/test_control_arming.py` — the three gate tests named in D-53-01.
- `operator-claude-plugin/tests/test_control_flag_parity.py` — declaration counts per workflow
  (they moved on 2026-08-25 when the association gate was added; they will move again if this
  phase touches the declaring set).
- `operator-claude-plugin/tests/test_scheduled_arm.py` — the headless path's own guarantees.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `armed_window` (context manager): already gives arm → run → guaranteed disarm with a
  `DisarmFailed` state of its own. A session grant is this, held open longer, with a different
  authority check at the front.
- `control_actions.plan_action` / `execute_action`: the shown-consequence-then-explicit-yes
  shape, already carrying the bounded-to-this-batch sentence the grant needs.
- `n8n_control.apply_mutation`: the only allowlisted PUT path, with the deactivate/reactivate
  bounce built in. A grant must arm through it, never around it.
- `config_gate.require_capability`: the refusal that names the missing key, the file, and who
  holds the value.

### Established Patterns
- **Empty allowlist denies everything.** `_writeSafetyAllows` returns false when both lists are
  empty; `arm_for_dispatch` refuses to arm an empty allowlist rather than reporting a successful
  arming that grants nothing. A grant inherits both properties.
- **Arming is a mutation, so it is planned, shown, confirmed, and verified by re-read** — a 200
  from n8n is never success.
- **Authority gates in this repo are env vars with exact-`true` comparison** (`ALLOW_N8N_PROBE`,
  `ALLOW_N8N_DEPLOY`, `ALLOW_N8N_ARM`, D-34). This phase creates the first deliberate exception
  and must say so where a reader will find it.

### Integration Points
- The three lane skills (`enrich-records`, `contact-upload`, `enrich-before-ingest`) each ask
  for their own arming phrase today; all three change when a grant is open (D-53-04).
- `backend-control`'s "one action, one confirmation" framing already describes an arm cycle —
  the grant extends that surface rather than adding a parallel one.

</code_context>

<deferred>
## Deferred Ideas

- **Expiry inside the shared write-safety gate** (offered as the recommendation for D-53-03,
  declined). If the client-held design proves lossy in practice — a real session dies armed —
  this is the structural fix, and it belongs in its own phase because it changes the gate every
  workflow embeds.
- **A scheduled watchdog that disarms anything armed longer than N minutes** — the cheaper half
  of the same idea, also declined. Note it spends executions from the budget it protects.
- **Admin-set maximum ceilings the operator may only narrow** (offered for D-53-02, declined in
  favour of computed worst case). Revisit if Phase 57's allowance check proves to be carrying
  too much alone.
- **A session token minted by an admin** (offered for D-53-01, declined) — would put a secret in
  a chat surface, which this plugin forbids elsewhere.

</deferred>

---

*Phase: 53-operator-openable-write-grant*
*Context gathered: 2026-08-25*
