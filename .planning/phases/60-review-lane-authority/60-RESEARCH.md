# Phase 60: Review-lane authority - Research

**Researched:** 2026-09-01
**Domain:** Internal authorization plumbing (Python plugin client + n8n Cloud workflow write-safety gate) — no new external dependency, no UI, no HubSpot schema change.
**Confidence:** HIGH

## Summary

This phase is pure composition of machinery that already exists and is already proven live: `write_grant.py`'s grant/lane model, `n8n_arming.py`'s bidirectional overlay-and-verify setter, and the review workflow's own write-safety gate. Every one of the five specific unknowns the phase brief asked this research to close was resolved by reading the actual files, not by inference — and the answer to all five is the same shape: **the review lane already declares its write-safety constants in the identical form the dispatch lanes do, using the identical shared gate function, so D-60-05's dynamic arm can be built by extending the *client-side* Python (`write_grant.LANES`, a new `n8n_arming.REVIEW_FLAGS`-style constant, a new arm/disarm pair or parameterization) with ZERO changes to `n8n/wf_review_decision_cloud.json` and ZERO changes to `scripts/build_cloud_workflows.py`'s generated JS.**

The one thing this research found that CONTEXT.md's own analysis did not name: **Guardrail A (the dirty-backend refusal `write_grant.guardrail_a` runs before opening any grant) is currently blind to a stuck-open `ALLOW_HUBSPOT_REVIEW_WRITES`, on every lane, including the review lane itself, once it exists.** Two module-level constants — `write_grant.py`'s own local `WRITE_ENABLING_FLAGS` tuple (line 1556, DELIBERATELY 2 items, dispatch-only) and `read_live_write_state`'s per-lane read loop (line 1599, iterates `n8n_arming.DISPATCH_FLAGS`, 4 items) — never read or report `ALLOW_HUBSPOT_REVIEW_WRITES` at all. Today this is inert because review has no `workflow_ids` entry for Guardrail A to iterate over. The moment `"review"` joins `LANES`, Guardrail A will read the review workflow's dispatch flags (harmlessly — the review workflow also declares them, unused) but will **never notice a previous crashed session left `ALLOW_HUBSPOT_REVIEW_WRITES=true` armed on it.** This is exactly the failure category D-53-03 built Guardrail A to catch, and closing it is now in scope by consequence of D-60-01/D-60-05 even though CONTEXT.md's decisions do not name it directly. See Common Pitfalls.

**Primary recommendation:** Do the arm/disarm split by **parameterizing**, not duplicating: `n8n_arming.arm_for_dispatch`/`disarm`/`armed_window` are 90% generic (`n8n_control.apply_mutation` + `set_write_safety` + `n8n_read.read_write_safety` already take a `targets`/`flags` argument or can trivially be threaded one). Add `REVIEW_FLAGS = ("ALLOW_HUBSPOT_REVIEW_WRITES", "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")` next to `DISPATCH_FLAGS`, and either (a) give `arm_for_dispatch`/`disarm` a `flags=DISPATCH_FLAGS` keyword the review path overrides, or (b) add a thin `arm_for_review`/`disarm_review` pair that composes the same primitives with `REVIEW_FLAGS` and a `{"ALLOW_HUBSPOT_REVIEW_WRITES": True, ...}` target (no `allow_create` concept on this lane at all). Widen `write_grant.py`'s own dirty-backend detection (`WRITE_ENABLING_FLAGS` local tuple + `read_live_write_state`'s flag loop) to also read `ALLOW_HUBSPOT_REVIEW_WRITES`, and update the two hard-coded test fixtures this will touch (see Common Pitfalls and Validation Architecture).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-60-01:** Review-lane approval authority reverses Phase 30-01's deliberate separation
  (D-02/D-08e) between dispatch grants and review writeback. Chosen over (a) an admin
  config key that keeps the two authorities separate, and (c) accepting the current
  two-round-trip flow as correct for occasional triage. — **Reversibility:** costly —
  undoing this means re-excluding `ALLOW_HUBSPOT_REVIEW_WRITES` from whatever grantable-lane
  set this phase builds, and re-standing-up `ALLOW_REVIEW_SUBMIT` as review's sole
  independent gate (D-60-04 retires it).
- **D-60-02:** A single grant covers all three lanes together (enrichment, contacts,
  review) — opening one grant authorizes all three, not a separate deliberate "yes" per
  lane. This mirrors D-53-05's existing precedent (one grant already spans enrichment +
  contacts) rather than inventing a new per-lane consent model. — **Reversibility:**
  costly — separating review back into its own deliberately-opened grant would need
  re-adding a lane-selection step to whatever grant-opening flow this phase builds.
- **D-60-03:** The grant's existing record-scoping (ids/domains named when it is opened)
  bounds which flagged records can be approved via review, exactly the same "narrower than
  the grant, never wider" rule dispatch sends already follow (`write_grant.authorize_send`).
  A grant opened over records A/B/C cannot approve a review decision on record D. This is
  what keeps D-60-02's combined-lane choice from being a blank check on every flagged record
  in the system — only records already named in the grant get review authority too.
  — **Reversibility:** reversible.
- **D-60-04:** The client-side `ALLOW_REVIEW_SUBMIT` shell-env kill switch
  (`review_decision.py:SUBMIT_ENV_VAR`) is retired. Grant-authorization
  (`write_grant.authorize_send` / `authorize_ungranted_send`) becomes the gate
  `submit_decision()` checks instead — the same authorization call enrichment already uses,
  not a second copy of the check. — **Reversibility:** reversible.

- **D-60-05:** This phase also wires `ALLOW_HUBSPOT_REVIEW_WRITES` into the same dynamic
  arm-window mechanism (`n8n_arming.py`) dispatch already uses, so a grant's review decision
  needs zero manual admin deploy. Without this, D-60-01/D-60-02 would remove the friction
  that mattered least (a client-side env var) while leaving the friction that mattered most
  (a human running a deploy) untouched. — **Reversibility:** reversible — additive; the
  existing deploy-time-baked path (`deploy_n8n_workflows.py::enable_baked_flags`) is not
  removed, only bypassed when a grant arms dynamically instead.
- **Load-bearing implementation note (Claude's discretion on the mechanism, not asked as a
  question):** `ALLOW_HUBSPOT_REVIEW_WRITES` already shares the SAME `TEST_RECORD_IDS` /
  `TEST_RECORD_DOMAINS` allowlist as the dispatch flags in the deployed workflow node — it
  is one of `n8n_arming.OVERLAYABLE_FLAGS`'s five names, just never included in
  `DISPATCH_FLAGS`. A review arm window must set `ALLOW_HUBSPOT_REVIEW_WRITES=true` on the
  allowlisted records **without** setting `ALLOW_HUBSPOT_RECORD_WRITES=true` for them —
  arming review on a record must never incidentally open dispatch-write eligibility for
  that same record. The separate `WRITE_ENABLING_FLAGS` booleans already make this safe by
  construction (the shared allowlist alone authorizes nothing without its own boolean); the
  planner should add a `REVIEW_FLAGS` (or similarly named) constant analogous to
  `DISPATCH_FLAGS`, not extend `DISPATCH_FLAGS` itself.
- **`write_grant.LANES` currently maps 2 lane names → 2 workflow names**
  (`{"enrichment": ..., "contacts": ...}`, `write_grant.py:83-86`). Add `"review"` →
  `"LV Review Decision (Cloud)"` (the workflow's actual `name` field, confirmed live from
  `n8n/wf_review_decision_cloud.json`; no existing Python constant names it yet — the
  planner should add one, e.g. `REVIEW_WORKFLOW_NAME`, mirroring
  `ENRICHMENT_WORKFLOW_NAME` / `CONTACT_INGEST_WORKFLOW_NAME`'s placement pattern).
- **Recorded-edit discipline required, matching D-53-05's own precedent (the roadmap
  explicitly calls this out):** `write_grant.py:64-82`'s comment block documents WHY the
  review lane is currently excluded from `LANES` (30-01 D-02/D-08e). This phase reverses
  that decision — the comment must be AMENDED with a dated addendum explaining the reversal
  and why (mirroring the D-59-07 amendment already sitting a few lines below it in the same
  file), never silently deleted or rewritten as if the old design never existed.

- **D-60-06:** One arm window covers a whole batch of review decisions in a session,
  rather than opening and disarming a fresh window for every single decision. Chosen over
  per-decision arm/disarm (which would exactly mirror how each enrichment SEND already
  opens its own window under `authorize_send`) because triaging several flagged records in
  one sitting shouldn't cost an arm/disarm round trip to n8n per record.
  — **Reversibility:** costly — a batch-scoped window's lifecycle (open once, handle a
  disarm-on-crash mid-batch, handle what happens if one decision in the batch fails) is
  more involved to build than per-decision arm/disarm; reversing to per-decision later means
  re-deriving that lifecycle from scratch rather than trimming an existing one.
- **Note for planner:** D-60-03's record-scoping still applies per decision inside the
  batch — the batch arm's allowlist is fixed to the grant's own record list at open time
  (per D-60-02/D-60-03), it does not grow as the operator triages records one by one.

### Claude's Discretion

- The exact mechanism for a `REVIEW_FLAGS`-style constant and where the review-specific
  arm/disarm wrapper function lives (new function in `n8n_arming.py`, or a `write_grant.py`
  call site composing the existing generic overlay primitives directly) — both are
  consistent with the existing architecture; pick whichever produces the smaller diff.
- Whether the batch arm's disarm-on-crash path reuses `n8n_arming.armed_window`'s existing
  context-manager guarantee (arm → run caller's decisions → disarm, including on the
  exception path) as-is, or needs a review-specific variant — the existing
  `armed_window.__exit__`'s "never swallow the body's exception, still disarm" guarantee
  should carry over unchanged; only the flags set at arm/disarm time differ from dispatch.

### Deferred Ideas (OUT OF SCOPE)

None raised during this discussion — no scope creep occurred; all three areas stayed within
the phase's authorization-plumbing boundary. One reviewed-but-not-folded todo:
`2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md` (unrelated subject, left in the
backlog).

</user_constraints>

<phase_requirements>
## Phase Requirements

None mapped. `milestones/v1.1-REQUIREMENTS.md` carries no review-lane requirement ID
[VERIFIED: .planning/milestones/v1.1-REQUIREMENTS.md — grepped for "review", no G-/REQ-ID
governs this lane]. This phase is driven entirely by `59-CONTEXT.md` § D-59-03 and
`60-CONTEXT.md`'s D-60-01..06, reproduced verbatim above.
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Grant authority / lane resolution | Plugin client (Python, operator's machine) | — | `write_grant.py` never touches HubSpot directly; it authorizes and arms |
| Dynamic write-safety overlay (arm/disarm) | Plugin client → n8n Cloud API (PUT workflow) | — | `n8n_arming.py` rewrites deployed JS `const` literals via the n8n management API, never the webhook path |
| Write-safety gate evaluation | n8n Cloud (deployed workflow) | — | `_writeSafetyAllows()`, baked into every write-gate Code node, evaluated at request time inside n8n — this phase does not touch it |
| Review decision computation (`buildReviewDecision`) | n8n Cloud (deployed workflow) | — | `n8n/code/reviewDecision.js`, inlined via `scripts/build_cloud_workflows.py`; unaffected by this phase |
| Operator consent / conversation UX | Plugin skill (`review-triage/SKILL.md`) | Plugin client (`review_decision.py`) | The skill decides what to say and when to call `submit_decision`; the module decides whether the call is gated |

## Standard Stack

No new library, package, or service is introduced by this phase. It composes existing
in-repo Python modules (`write_grant.py`, `n8n_arming.py`, `review_decision.py`,
`n8n_read.py`, `n8n_control.py`) and touches zero external dependencies.

**Installation:** none.

## Package Legitimacy Audit

Not applicable — this phase installs no external package.

## Architecture Patterns

### System Architecture Diagram — current (two independent gates) vs. this phase's target

```
CURRENT (two disconnected authorities):

  Operator "approve record X"
        |
        v
  review-triage skill --yes--> review_decision.submit_decision()
        |                              |
        | checks (client-side)         | checks
        v                              v
  ALLOW_REVIEW_SUBMIT (shell env,   review_armed (per-decision,
  admin-only, machine-local)        conversation-scoped)
        |                              |
        +------------------+-----------+
                           v
              POST hubspot/review/decision
                           |
                           v
          n8n: Build Review Decision node
          computes _writeSafetyAllows("review", id, domain)
                           |
                           v
          ALLOW_HUBSPOT_REVIEW_WRITES (baked constant,
          only settable by an ADMIN-RUN DEPLOY today)
          + shared TEST_RECORD_IDS / TEST_RECORD_DOMAINS


TARGET (D-60-01..06 — review folded into the grant, dynamically armed):

  Operator "yes" to plan_grant() proposal, lanes=[enrichment, contacts, review]
        |
        v
  write_grant.open_grant()  -->  grant{lanes:[...,"review"], record_ids, record_domains,
                                        workflow_ids:{..., "review": <id>}}
        |
        | one batch, D-60-06
        v
  n8n_arming.armed_review_window(review_workflow_id, grant.record_ids,
                                  grant.record_domains, config, grant=grant)
        |  arms ONLY: ALLOW_HUBSPOT_REVIEW_WRITES=true, TEST_RECORD_IDS/DOMAINS
        |  (never touches ALLOW_HUBSPOT_RECORD_WRITES / ALLOW_HUBSPOT_CREATE)
        v
  for each record the operator triages in this batch:
        review-triage skill --yes(per-record, unchanged UX)--> submit_decision(
            ..., authorized_by=write_grant.authorize_send(grant, lane="review", ...))
        |
        v
  POST hubspot/review/decision  -- same endpoint, same gate, unchanged n8n JSON --
        |
        v
  disarm on batch end / crash (armed_window.__exit__, unchanged guarantee)
```

The n8n-side boxes at the bottom of both diagrams are byte-identical — this phase changes
nothing below the webhook. Everything new is above it.

### Pattern 1: Parameterize the arm/disarm pair rather than duplicate it
**What:** `n8n_arming.arm_for_dispatch` / `disarm` / `armed_window` already delegate all
their actual mutation and verification work to lane-agnostic primitives:
`set_write_safety(workflow, targets)` (rewrites any subset of the 5 `OVERLAYABLE_FLAGS`),
`n8n_control.apply_mutation(workflow_id, mutate_fn, allowed_node_names, config,
verify_fn=..., transport=...)` (generic fetch→mutate→PUT→verify cycle), and
`n8n_read.read_write_safety` (generic reader, discovers declaring nodes dynamically — never
a hardcoded list). The only lane-specific things `arm_for_dispatch` hardcodes are (a) which
flags to target (`DISPATCH_FLAGS`) and (b) the `targets` dict it builds
(`ALLOW_HUBSPOT_RECORD_WRITES` + optional `ALLOW_HUBSPOT_CREATE` + the two allowlist
flags).
**When to use:** Exactly this phase's situation — a second lane needing the identical
arm→verify→disarm lifecycle against a different flag.
**Example (verified read of the real function, not paraphrased):**
```python
# Source: operator-claude-plugin/scripts/n8n_arming.py:299-420 (arm_for_dispatch, abridged)
targets = {
    "ALLOW_HUBSPOT_RECORD_WRITES": True,
    "TEST_RECORD_IDS": ",".join(ids),
    "TEST_RECORD_DOMAINS": ",".join(domains),
}
if allow_create:
    targets["ALLOW_HUBSPOT_CREATE"] = True
...
result = n8n_control.apply_mutation(
    workflow_id, _mutate, _declaring_nodes(original), config,
    verify_fn=_verify, transport=transport,
    action=f"arm live writes on {workflow_id} for {len(ids)} id(s) and "
           f"{len(domains)} domain(s)")
```
The review analog needs only a different `targets` dict
(`{"ALLOW_HUBSPOT_REVIEW_WRITES": True, "TEST_RECORD_IDS": ..., "TEST_RECORD_DOMAINS": ...}`,
never `ALLOW_HUBSPOT_RECORD_WRITES`/`ALLOW_HUBSPOT_CREATE`) and a different flag list fed to
`_declaring_nodes`/`_verify`/`disarmed_targets`. `n8n_arming.OVERLAY_DISABLED_LITERALS`
already has the disarmed literal for `ALLOW_HUBSPOT_REVIEW_WRITES` (`n8n_arming.py:49`), so
`disarmed_targets("ALLOW_HUBSPOT_REVIEW_WRITES", "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")`
already works with zero changes to `disarmed_targets` itself.

### Pattern 2: The shared allowlist is the safety property, and it already generalizes
**What:** `set_write_safety` and the whole verify-then-refuse mechanism operate on
whatever flag names appear in `targets`; they never assume DISPATCH_FLAGS. The empty-
allowlist refusal in `arm_for_dispatch` ("the deployed `_writeSafetyAllows()` returns
false when both allowlists are empty...") is a general truth about the shared gate, true
for `action === "review"` exactly as for `action === "create"`/`"enrich"`
[VERIFIED: scripts/build_cloud_workflows.py:1177-1194 — the single `_writeSafetyAllows`
body baked into every gate node, quoted below].
**When to use:** Reuse this refusal verbatim in a review-specific arm function; do not
re-derive it.

### Anti-Patterns to Avoid
- **Do not touch `n8n/wf_review_decision_cloud.json` by hand, or add a node to it via
  `scripts/build_cloud_workflows.py`.** Nothing in this phase requires it — the JSON
  already declares `ALLOW_HUBSPOT_REVIEW_WRITES` in the exact rewritable form
  `n8n_arming.set_write_safety`'s regex targets (verified below). Regenerating the
  workflow when no generator change is needed just adds diff noise and deploy risk.
- **Do not extend `DISPATCH_FLAGS` to include `ALLOW_HUBSPOT_REVIEW_WRITES`.** CONTEXT.md's
  load-bearing note is explicit and the live JS gate (quoted below) proves why: arming
  `ALLOW_HUBSPOT_REVIEW_WRITES=true` must never make `_writeSafetyAllows("create"/"enrich",
  ...)` return `true` for the same allowlisted record, and vice versa. Keep the two
  boolean flags on two separate constant tuples so a caller can never blend them by
  accident (`test_write_grant.py::test_the_review_lane_is_not_grantable` half-pins exactly
  this — see Common Pitfalls for the half that needs rewriting).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rewriting a deployed workflow's `const` literal safely | A second regex / string-replace | `n8n_arming.set_write_safety` (bidirectional, fail-closed re-scan via the shipped `n8n_read.read_write_safety`) | Already handles multi-node declaration desync, already tested, already the writer half of the reader every status surface uses |
| Fetch→mutate→verify→restore-active-state cycle against the n8n API | A bespoke PUT+GET pair | `n8n_control.apply_mutation` | Already restores the workflow's prior active/inactive state, already refuses on out-of-allowlist diffs (T-28-06), already used by both `arm_for_dispatch` and `disarm` |
| Deciding whether a send is inside a grant's scope | A second scope-check function | `write_grant.covers` | "the ONE implementation of the scope question" per its own docstring — a review-specific reimplementation would immediately diverge in wording from the dispatch refusal |
| Resolving a workflow name to an id | A hand-rolled n8n API list-and-filter | `executions_client.resolve_workflow_id(config, transport, workflow_name=...)` | Generic over `workflow_name`, already process-cached, already used by both existing lanes — needs zero code change for a third lane, only a new name constant |

**Key insight:** every primitive this phase needs already exists and is already lane-generic
except two module-level constants that were deliberately scoped to 2 lanes before review
existed (`n8n_arming.DISPATCH_FLAGS`, `write_grant.WRITE_ENABLING_FLAGS`). The work is almost
entirely "add a third value/branch to an existing generic mechanism," not "build a new
mechanism."

## Common Pitfalls

### Pitfall 1: Guardrail A cannot see a stuck-open review authorization
**What goes wrong:** `write_grant.guardrail_a` (the "refuse to open a grant over a backend
where writes are already live" check, D-53-03) reads live write state via
`read_live_write_state`, which loops `for flag in n8n_arming.DISPATCH_FLAGS:`
[VERIFIED: operator-claude-plugin/scripts/write_grant.py:1599 — `for flag in
n8n_arming.DISPATCH_FLAGS:`] — 4 flags, never `ALLOW_HUBSPOT_REVIEW_WRITES`. Separately,
`write_grant.py` defines its OWN local `WRITE_ENABLING_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES",
"ALLOW_HUBSPOT_CREATE")` [VERIFIED: operator-claude-plugin/scripts/write_grant.py:1556] —
a 2-item tuple, distinct from and shadowing the name of `n8n_arming.WRITE_ENABLING_FLAGS`
(a 3-item frozenset that DOES include the review flag, at `n8n_arming.py:54-56`). Once
`"review"` is added to `LANES` and a grant's `workflow_ids` dict gets a `"review"` entry,
Guardrail A will read the review workflow's dispatch flags (harmless, since the review
workflow declares all 5 and the dispatch ones are unused there) but will structurally
never notice `ALLOW_HUBSPOT_REVIEW_WRITES=true` left armed by a crashed prior session — the
exact scenario Guardrail A exists to catch (D-53-03's own words: "found a state IT DID NOT
CREATE").
**Why it happens:** Both constants were written correctly for a 2-lane world (D-02/D-08e
deliberately kept review's authority off Guardrail A's radar, because review had no
`workflow_ids` entry to iterate). D-60-01 changes that premise without either constant
being touched.
**How to avoid:** Widen `read_live_write_state`'s per-lane flag loop and `write_grant.py`'s
local `WRITE_ENABLING_FLAGS` to also read/report `ALLOW_HUBSPOT_REVIEW_WRITES`. The
cheapest correct fix is almost certainly to swap the read loop's `n8n_arming.DISPATCH_FLAGS`
for `n8n_arming.OVERLAYABLE_FLAGS` (all 5) unconditionally per lane — every currently
deployed cloud workflow already declares all 5 via the single shared `WRITE_SAFETY_GATE_JS`
block [VERIFIED: ran `n8n/wf_enrichment_cloud.json` and `n8n/wf_contact_ingest_cloud.json`
through a declaration scan this session — both declare `ALLOW_HUBSPOT_REVIEW_WRITES` on
their own write-gate nodes (`Decide Company Action`/`Decide Action`,
`HubSpot Update Write Gate`/`HubSpot Associate Company Write Gate`/`HubSpot Create Write
Gate`) even though those workflows never branch on it] — so this is not overreach, it
matches deployed reality on lanes that exist today too.
**Warning signs:** `guardrail_a` returning `None` (proceed) on a grant that includes the
review lane even though a previous session's review batch crashed mid-window — silent,
because nothing surfaces an absence of a check.

### Pitfall 2: Widening the guardrail's flag set will break existing test fixtures, on purpose
**What goes wrong:** `operator-claude-plugin/tests/test_write_grant_guardrails.py`'s
`_gate()` helper builds a mock workflow's `jsCode` declaring exactly 4 constants
(`ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`, `TEST_RECORD_IDS`,
`TEST_RECORD_DOMAINS`) [VERIFIED: operator-claude-plugin/tests/test_write_grant_guardrails.py:37-42
— `def _gate(record_writes='"false"', create='"false"', ids='""', domains='""'):` followed
by exactly those 4 `const` lines]. `n8n_read.read_write_safety` returns `{"value": None,
"nodes": [], "disagreement": None}` for a flag with zero declaring nodes
[VERIFIED: operator-claude-plugin/scripts/n8n_read.py:452-453 — `if not distinct: return
{"value": None, "nodes": [], "disagreement": None}`]. If Pitfall 1's fix widens the read
loop to check `ALLOW_HUBSPOT_REVIEW_WRITES` unconditionally, every existing guardrail test
using `_gate()`/`_workflow()` will suddenly read `flags["ALLOW_HUBSPOT_REVIEW_WRITES"] =
None` → `readable = False` (since the widened `WRITE_ENABLING_FLAGS` would require it
non-`None`) → **every currently-passing "disarmed backend proceeds" test starts refusing.**
**Why it happens:** The test fixtures were written to match a 2-lane world's real declared
shape and never needed to change, until this phase widens what "real declared shape" means.
**How to avoid:** Update `_gate()` in the same commit that widens the guardrail's flag set,
adding the review constant with its disarmed literal (`'"false"'`) as a fifth line — a
one-line fixture change, not a redesign. `test_write_gate_coverage.py` (referenced in
`scripts/build_cloud_workflows.py:8165`'s comment) is a separate test that walks the real
committed JSON and is unaffected either way, since this phase changes no JSON.
**Warning signs:** A wave of guardrail-A tests failing with "its write-safety state could
not be read at all" immediately after widening the flag list — that message is
`_live_write_faults`'s literal wording for `readable=False`
[VERIFIED: operator-claude-plugin/scripts/write_grant.py:1618-1622].

### Pitfall 3: Two tests currently assert the design this phase reverses — by name
**What goes wrong:** `operator-claude-plugin/tests/test_write_grant.py` has:
```python
# Source: operator-claude-plugin/tests/test_write_grant.py:602-617 (verbatim)
def test_plan_grant_refuses_an_unknown_lane_by_name(granting_config,
                                                    stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())

    result = _proposal(granting_config, transport, lanes=("review",))

    assert result["outcome"] == write_grant.REFUSED
    assert "review" in result["detail"]
    assert transport.calls == []


def test_the_review_lane_is_not_grantable(granting_config, stub_module_transport_factory):
    """30-01's D-02/D-08e: review writeback is a SEPARATE authority. A dispatch grant must
    not reach it."""
    assert "review" not in write_grant.LANES
    assert "ALLOW_HUBSPOT_REVIEW_WRITES" not in n8n_arming.DISPATCH_FLAGS
```
Once `"review"` joins `LANES`, `test_plan_grant_refuses_an_unknown_lane_by_name`'s
`lanes=("review",)` call stops refusing and the test fails outright — it must be
repurposed onto a genuinely-unknown lane name (e.g. `lanes=("bogus",)`) rather than
deleted, so the "unknown lane refuses by name" behavior stays pinned.
`test_the_review_lane_is_not_grantable`'s FIRST assertion (`"review" not in
write_grant.LANES`) becomes false and must be inverted with the recorded-edit discipline
D-60-05 already calls for; its SECOND assertion (`"ALLOW_HUBSPOT_REVIEW_WRITES" not in
n8n_arming.DISPATCH_FLAGS`) stays TRUE after this phase (the load-bearing note is explicit
that `DISPATCH_FLAGS` must never gain this flag) and should be preserved, ideally in a
renamed test asserting the SEPARATION survives even though the lane is now grantable.
**Why it happens:** These tests were written to pin exactly the design D-60-01 reverses;
CONTEXT.md's own recorded-edit-discipline instruction (for the `write_grant.py:64-82`
comment) applies with equal force to these two tests.
**How to avoid:** Rewrite both in the same commit that adds `"review"` to `LANES`, with a
docstring/comment naming this phase and dated, mirroring the D-59-07 amendment style
already present in `write_grant.py`. Do not silently delete
`test_the_review_lane_is_not_grantable` — repurpose it to assert the surviving half of the
separation (arming review grants nothing on dispatch, and vice versa), which is exactly
what `tests/n8n/reviewWriteFlagSeparation.test.mjs` already independently proves at the JS
level (see Validation Architecture).

### Pitfall 4: `submit_decision`'s two other gates must not silently vanish
**What goes wrong:** D-60-04 retires the `ALLOW_REVIEW_SUBMIT` env check specifically. It
says nothing about the session arm (`review_armed`) or the `is_undoing`/`reject` carve-out.
A literal reading of "grant-authorization becomes THE gate" could tempt an implementation
that also drops the per-decision `review_armed` confirmation the skill still asks for in
Step 6 of `review-triage/SKILL.md` — but nothing in D-60-01..06 authorizes removing the
per-record "read the exact write back and get an explicit yes" ritual, and the skill's own
Step 6 language ("A yes here authorizes this record's write and nothing else") is
unaffected by which authority sits underneath it.
**Why it happens:** `submit_decision`'s current code checks THREE things in sequence
(`is_undoing(decision) or submit_enabled()`, then `review_armed`, then does the POST)
[VERIFIED: operator-claude-plugin/scripts/review_decision.py:243-249 — `if not
is_undoing(decision) and not submit_enabled(): return _unavailable(...)` then `if not
review_armed: return _unavailable(...)`]. Swapping gate 1 for a grant-authorization call is
a one-line-shaped change that is easy to over-apply to gate 2 by accident.
**How to avoid:** Keep `review_armed` as a separate, still-required argument;
`submit_decision`'s new first check becomes something shaped like `write_grant.check_before_send`
or the `armed`/`refusal` fields `authorize_send` already returns, composed BEFORE the
existing `review_armed` check, not replacing it. `is_undoing("reject")`'s bypass of gate 1
(`review_decision.py:100-103`, `UNDOING_DECISIONS = ("reject",)`) needs an explicit design
decision under grant-authorization: does a reject still bypass the grant check the way it
bypassed the env var? The rationale for the original carve-out ("a closed kill switch must
not be able to strand a record mid-decision") arguably still applies to "no grant is open" —
this is an Open Question below, not resolved by CONTEXT.md.

### Pitfall 5: `n8n/code/reviewDecision.js`'s own message is now stale text, not stale code
**What goes wrong:** The `not_allowlisted` refusal message says: *"an administrator adds
records to that allowlist at deploy time"* [VERIFIED: n8n/code/reviewDecision.js:226-228 —
`message: "this record is not on the backend's TEST_RECORD_* allowlist, so nothing was "
+ "sent to HubSpot and the record is unchanged — an administrator adds records to " +
"that allowlist at deploy time"`]. After this phase ships, that will often be false — the
allowlist can also be set dynamically by a grant's arm window, with no admin and no deploy.
**Why it happens:** This string was accurate in the pre-D-60-05 world; it is
operator-facing text baked into the deployed workflow JSON.
**How to avoid:** This is a `scripts/build_cloud_workflows.py` string edit (regenerating
`wf_review_decision_cloud.json`) — the ONE part of this phase that legitimately does touch
the generated JSON, and only the message text, not the gate logic. `test_review_outcome_parity.py`
does not pin message text (only outcome literals), so this edit is low-risk, but must still
go through `scripts/build_cloud_workflows.py`, never a hand-edit of the JSON (project rule).

## Code Examples

### The shared write-safety gate the review lane already uses (unchanged by this phase)
```javascript
// Source: scripts/build_cloud_workflows.py:1177-1194 (WRITE_SAFETY_GATE_JS, verbatim) —
// baked into "Build Review Decision", "Review Decision Update Write Gate" and
// "Review Contact Decision Update Write Gate" in the committed
// n8n/wf_review_decision_cloud.json (confirmed via live read of that file this session)
function _writeSafetyAllows(action, hsObjectId, domain) {
  if (action === "review") {
    if (String(ALLOW_HUBSPOT_REVIEW_WRITES).toLowerCase() !== "true") return false;
  } else {
    if (String(ALLOW_HUBSPOT_RECORD_WRITES).toLowerCase() !== "true") return false;
    if (action === "create" && String(ALLOW_HUBSPOT_CREATE).toLowerCase() !== "true") return false;
  }
  const allowedDomains = String(TEST_RECORD_DOMAINS).split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  const allowedIds = String(TEST_RECORD_IDS).split(",").map((s) => s.trim()).filter(Boolean);
  if (!allowedDomains.length && !allowedIds.length) return false;
  if (hsObjectId && allowedIds.indexOf(String(hsObjectId)) !== -1) return true;
  if (domain && allowedDomains.indexOf(String(domain).toLowerCase()) !== -1) return true;
  return false;
}
```
The declared constants immediately above this function in the committed workflow, read
directly this session:
```javascript
// Source: n8n/wf_review_decision_cloud.json, node "Build Review Decision" (also
// "Review Decision Update Write Gate" and "Review Contact Decision Update Write Gate"),
// verified by scanning the committed JSON this session
const ALLOW_HUBSPOT_REVIEW_WRITES = "false";
const ALLOW_HUBSPOT_RECORD_WRITES = "false";
const ALLOW_HUBSPOT_CREATE = "false";
const TEST_RECORD_IDS = "";
const TEST_RECORD_DOMAINS = "";
```
This is the EXACT `const NAME = <literal>;` shape `n8n_arming.set_write_safety`'s regex
targets (`rf"const\s+{re.escape(flag)}\s*=\s*[^;]+;"`,
`operator-claude-plugin/scripts/n8n_arming.py:136`) — no drift, no adaptation needed.

### The lane table this phase extends
```python
# Source: operator-claude-plugin/scripts/write_grant.py:83-86 (verbatim, current state)
LANES = {
    "enrichment": scheduled_arm.ENRICHMENT_WORKFLOW_NAME,
    "contacts": executions_client.CONTACT_INGEST_WORKFLOW_NAME,
}
```
```python
# Source: n8n/wf_review_decision_cloud.json (verified live this session)
# wf.get("name") == "LV Review Decision (Cloud)"
```

### The overlay flag table review already belongs to
```python
# Source: operator-claude-plugin/scripts/n8n_arming.py:46-57 (verbatim, current state)
OVERLAY_DISABLED_LITERALS = {
    "ALLOW_HUBSPOT_RECORD_WRITES": '"false"',
    "ALLOW_HUBSPOT_CREATE": '"false"',
    "ALLOW_HUBSPOT_REVIEW_WRITES": '"false"',
    "TEST_RECORD_IDS": '""',
    "TEST_RECORD_DOMAINS": '""',
}
OVERLAYABLE_FLAGS = frozenset(OVERLAY_DISABLED_LITERALS)
WRITE_ENABLING_FLAGS = frozenset({
    "ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE", "ALLOW_HUBSPOT_REVIEW_WRITES",
})
ALLOWLIST_FLAGS = frozenset({"TEST_RECORD_IDS", "TEST_RECORD_DOMAINS"})

DISPATCH_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE",
                  "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")
```
`ALLOW_HUBSPOT_REVIEW_WRITES` is already `[OVERLAYABLE]` (line 49) and already counted in
`n8n_arming.WRITE_ENABLING_FLAGS` (lines 54-56) — this phase needs a `REVIEW_FLAGS` tuple
analogous to `DISPATCH_FLAGS`, e.g. `("ALLOW_HUBSPOT_REVIEW_WRITES", "TEST_RECORD_IDS",
"TEST_RECORD_DOMAINS")`, never a change to `OVERLAY_DISABLED_LITERALS` or
`OVERLAYABLE_FLAGS` (both already correct) and never a change to `DISPATCH_FLAGS` itself.

### The build-time generator (confirms no JSON hand-edit is needed)
```python
# Source: scripts/build_cloud_workflows.py:8167-8168 (verbatim) — the ONE call site that
# wires the review lane's write nodes to the shared gate
splice_write_gates(nodes, conns, {"Review Decision Update": "review",
                                  "Review Contact Decision Update": "review"})
```
`build_review_decision_cloud()` (the function containing this call, at
`scripts/build_cloud_workflows.py:7841`) is the sole generator of
`n8n/wf_review_decision_cloud.json`. This phase's client-side change requires no edit here.

## Runtime State Inventory

Not applicable — this is not a rename/refactor/migration phase. No stored data, live
service config, OS-registered state, secret/env-var name, or build artifact carries a
string this phase renames.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The smallest-diff design for the arm/disarm split is to parameterize `arm_for_dispatch`/`disarm` with a `flags=` argument rather than write a fully separate `arm_for_review`/`disarm_review` pair. | Architecture Patterns, Pattern 1 | If the planner instead duplicates the ~120-line `arm_for_dispatch` body, the two copies drift over time (e.g. a future fix to the fail-closed re-scan lands in one but not the other). Low risk to correctness today, real risk to maintainability later. Recorded as [ASSUMED] because CONTEXT.md explicitly left this to Claude's Discretion ("pick whichever produces the smaller diff") and only a planner with the full diff in hand can measure that. |
| A2 | Widening `read_live_write_state`'s flag loop to `n8n_arming.OVERLAYABLE_FLAGS` (all 5, unconditionally per lane) is the right fix for Pitfall 1, rather than a lane-keyed flag map (dispatch flags for enrichment/contacts, review flag only for review). | Common Pitfalls, Pitfall 1 | The uniform-5-flags approach is simpler and matches deployed reality (verified: all cloud workflows using the shared gate already declare all 5), but it does mean Guardrail A will report `ALLOW_HUBSPOT_CREATE`/`ALLOW_HUBSPOT_RECORD_WRITES` state on the review workflow too (harmless, since those flags are functionally inert there) and `ALLOW_HUBSPOT_REVIEW_WRITES` state on the enrichment/contacts workflows too (also harmless for the same reason). If a future workflow is added that does NOT use the shared `WRITE_SAFETY_GATE_JS` block, this assumption would need re-checking. |
| A3 | `submit_decision`'s `is_undoing("reject")` env-var bypass should also bypass whatever replaces `submit_enabled()` under grant-authorization (i.e. a reject still needs no open grant). | Common Pitfalls, Pitfall 4 | Not stated by D-60-04. If wrong, a reject would start requiring an open grant, which would strand a rejection exactly the way the original carve-out was designed to prevent — this is an Open Question, not a decision, and the planner should surface it for confirmation rather than assume either answer. |

## Open Questions

1. **Does a `reject` decision need an open grant at all, under D-60-04?**
   - What we know: today, `is_undoing("reject")` bypasses `ALLOW_REVIEW_SUBMIT` specifically
     (`review_decision.py:100-103`, `SUBMIT_ENV_VAR` check only) but NOT the session arm
     (`review_armed` is still required for both approve and reject).
   - What's unclear: D-60-04 says grant-authorization "becomes the gate `submit_decision()`
     checks instead" of the env var — it does not say whether a reject should also be able
     to proceed with NO grant open at all (the way it could proceed today with the env var
     unset, since the env-var-bypass existed specifically so a closed kill switch could
     never strand a record).
   - Recommendation: surface this explicitly to the operator during planning/discuss rather
     than assume either direction — the original rationale ("a rejection records a reason
     and leaves the record in the queue... blocking that would strand a record") reads as
     applying to "no grant open" symmetrically with "env var unset," but CONTEXT.md never
     says so.

2. **Should the review lane's writes appear in the D-59-07/D-59-09 `written_records-<run_id>.json` artifact?**
   - What we know: the dispatch lanes (enrichment, contacts) now write a durable
     per-run record of what actually landed in HubSpot, specifically so a partial or
     revoked run's writes are still visible (D-59-07/D-59-09, `written_records.py`).
     Review decisions also write to HubSpot (an approve promotes a candidate; a reject
     writes a reason) but go through `review_decision.submit_decision`, never through
     `chunking.dispatch_plan`, so they are NOT captured by that artifact today.
   - What's unclear: 60-CONTEXT.md's decisions do not mention this at all — it may be
     intentionally out of scope (review already has its own audit trail via
     `lv_enrichment_provenance` and `lv_enrichment_reviewed_by`/`_at`, stamped by
     `reviewApply` on the record itself, which arguably makes a separate written-records
     entry redundant for this lane).
   - Recommendation: treat as explicitly out of scope for this phase (CONTEXT.md's phase
     boundary paragraph says the phase "does not change what a reviewer sees before
     approving" and never proposes a new artifact) unless the operator raises it in
     discuss-phase.

3. **Where should `REVIEW_WORKFLOW_NAME` live?**
   - What we know: `ENRICHMENT_WORKFLOW_NAME` lives in `scheduled_arm.py` (which also uses
     it for the scheduled-maintenance poller, independent of `write_grant.LANES`);
     `CONTACT_INGEST_WORKFLOW_NAME` lives in `executions_client.py` (the module that
     defines `resolve_workflow_id`, whose default parameter it is, and is also read by
     `report.py`-family consumers). Verified: grepping the whole plugin `scripts/` tree,
     the review lane has NO other consumer today besides `write_grant.LANES` — no
     scheduled poller, no report reader references a "review" workflow name.
   - What's unclear: there is no natural "owner" module for this constant the way the
     other two have one, since review has no scheduled-arm analog and no executions-report
     consumer.
   - Recommendation: place it directly in `write_grant.py` beside `LANES` (smallest diff,
     matches its single actual consumer today) rather than manufacturing a new module or
     forcing it into `executions_client.py` where it would be an orphaned constant with no
     use besides being a default nobody defaults to.

## Environment Availability

Not applicable — this phase adds no new external dependency, tool, or service. It uses the
n8n Cloud API and HubSpot credentials this plugin already requires and already probes via
`config_gate.load_config()`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python plugin/backend) + Node's built-in `node:test` (n8n JS logic) |
| Config file | none dedicated — `operator-claude-plugin/tests/conftest.py` provides fixtures/autouse guards; `tests/conftest.py` provides the root suite's |
| Quick run command (plugin) | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` |
| Quick run command (root) | `.venv/bin/python -m pytest -q` |
| n8n JS logic | `node --test tests/n8n/*.test.mjs` — GLOB form; the directory form is broken on node 24 (repo-documented gotcha, do not use `tests/n8n/`) |

### Phase Requirements → Test Map
No REQ-IDs are mapped to this phase (see Phase Requirements above). The behaviors below are
derived directly from D-60-01..06 and must each have a passing/updated test before this
phase can be called done.

| Behavior (from decision) | Test Type | Automated Command | File Exists? |
|---|---|---|---|
| `"review"` is a valid, grantable lane (D-60-01/D-60-02) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k lane -x` | ❌ needs new/rewritten test — see Pitfall 3 |
| Review decisions cannot exceed the grant's record scope (D-60-03) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k covers -x` | ✅ `write_grant.covers` already generically scope-checked; a review-specific case should be added alongside the existing ones |
| `submit_decision` no longer reads `ALLOW_REVIEW_SUBMIT`; grant-authorization gates it instead (D-60-04) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_decision.py -x` | ✅ file exists, ~15 tests currently pin the env-var gate and need rewriting (see Pitfall 4/Common Pitfalls) |
| Arming review sets `ALLOW_HUBSPOT_REVIEW_WRITES` dynamically, never touching `ALLOW_HUBSPOT_RECORD_WRITES`/`ALLOW_HUBSPOT_CREATE` (D-60-05, load-bearing note) | unit + n8n JS | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_flag_parity.py -x` (parity unaffected, should already be green) AND `node --test tests/n8n/reviewWriteFlagSeparation.test.mjs` (already pins the separation direction from the JS side; must stay green unmodified) | ✅ both exist; the JS test needs NO change (proves the JSON-side invariant this phase must not violate); a new Python-side test proving `arm_for_review` never sets `ALLOW_HUBSPOT_RECORD_WRITES` should be added |
| Guardrail A detects a dirty `ALLOW_HUBSPOT_REVIEW_WRITES` state before opening a grant (consequence of D-60-01, this research's own finding, Pitfall 1) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant_guardrails.py -x` | ❌ needs a new test case; existing `_gate()` fixture needs the one-line update from Pitfall 2 |
| One arm window covers a whole batch of decisions (D-60-06) | unit | new test module or additions to `test_write_grant.py`/`test_write_grant_guardrails.py` exercising the batch-scoped arm/disarm lifecycle | ❌ needs new test — no existing test exercises a multi-decision single-window lifecycle for ANY lane today (dispatch's `authorize_send` is per-send, not batch-scoped, so this is genuinely new coverage, not a copy of an existing pattern) |
| `write_grant.py:64-82`'s exclusion comment is amended, not deleted (recorded-edit discipline) | manual/code-review | `git diff` review of the comment block | N/A — a documentation/process check, not a runnable test |
| `n8n/code/reviewDecision.js`'s stale `not_allowlisted` message text (Pitfall 5) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_outcome_parity.py -x` (outcome vocabulary parity, unaffected by a message-text edit) | ✅ exists, should stay green through the text edit since it only pins outcome literals, not message strings |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest operator-claude-plugin/tests -q` (fast,
  no network — `conftest.py`'s autouse `no_network` guard blocks any real transport)
- **Per wave merge:** the full three-part suite — `.venv/bin/python -m pytest -q`,
  `.venv/bin/python -m pytest operator-claude-plugin/tests -q`, and
  `node --test tests/n8n/*.test.mjs`
- **Phase gate:** all three suites green before `/gsd-verify-work`; this phase performs
  no live HubSpot or n8n writes (READ-ONLY research; the plan itself should stage a
  disarmed-by-default implementation and treat any live arm/disarm proof as a separate,
  explicitly-approved verification step, mirroring how Phase 53/59's own live walks were
  gated)

### Wave 0 Gaps
- [ ] A new unit test module (or additions to `test_write_grant_guardrails.py`) covering
      the batch-scoped review arm/disarm lifecycle (D-60-06) — no existing fixture covers
      a multi-decision single window for any lane.
- [ ] `test_write_grant.py::test_the_review_lane_is_not_grantable` and
      `test_plan_grant_refuses_an_unknown_lane_by_name` need rewriting in the same commit
      that adds `"review"` to `LANES` (Pitfall 3).
- [ ] `test_write_grant_guardrails.py`'s `_gate()`/`_workflow()` fixtures need a fifth
      declared constant (`ALLOW_HUBSPOT_REVIEW_WRITES`) if Guardrail A's flag-read is
      widened (Pitfall 2).
- [ ] No test framework install needed — pytest and node:test are both already the
      project's standing tools.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V4 Access Control | yes | This IS the phase's subject: which authority (env var vs. session arm vs. grant) may enable a write, and to which records. Reuse `write_grant.covers`'s "narrower than the grant, never wider" scope check rather than inventing a parallel one for review. |
| V2 Authentication | no | Unaffected — `X-Enrichment-Secret` header auth on the webhook, `X-N8N-API-KEY` on the management API, both unchanged |
| V5 Input Validation | no (unchanged) | `review_decision.py::_request_body` already sends only 6 fixed keys; this phase changes which gate evaluates the request, not the request shape |
| V6 Cryptography | n/a | No cryptographic material touched |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Authority collapse — arming one lane accidentally grants another (dispatch write vs. review write) | Elevation of Privilege | Keep `REVIEW_FLAGS` and `DISPATCH_FLAGS` on two separate constant tuples/target dicts (never merge); `tests/n8n/reviewWriteFlagSeparation.test.mjs` already proves the JSON-side gate keeps them separate — this phase's Python-side change must not undermine that by, e.g., a shared `targets` dict built from a union of both flag sets |
| Stuck-open authorization surviving a crashed session (Guardrail A blind spot, Pitfall 1) | Tampering / Repudiation | Widen Guardrail A's flag-read to include `ALLOW_HUBSPOT_REVIEW_WRITES`, per this research's central finding |
| Scope widening — a grant opened over records A/B approving a review decision on record D | Elevation of Privilege | `write_grant.covers`'s existing symmetric ids/domains check (D-60-03), reused unchanged for the review lane |

## Sources

### Primary (HIGH confidence — read directly this session)
- `operator-claude-plugin/scripts/write_grant.py` (full read, both halves — lines 1-1073 and 1074-1752)
- `operator-claude-plugin/scripts/n8n_arming.py` (full read)
- `operator-claude-plugin/scripts/review_decision.py` (full read)
- `operator-claude-plugin/scripts/executions_client.py` (partial read, resolver + constant)
- `n8n/wf_review_decision_cloud.json` (read via `json.load` + targeted regex scans this session — name field, declaring nodes, gate function bodies)
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_contact_ingest_cloud.json` (targeted declaration scans this session, confirming shared-gate reality)
- `n8n/code/reviewDecision.js` (partial read, `buildReviewDecision` + message text)
- `scripts/build_cloud_workflows.py` (targeted reads: `WRITE_SAFETY_GATE_JS`, `build_review_decision_cloud`, `REVIEW_BUILD_DECISION`)
- `operator-claude-plugin/scripts/n8n_read.py::read_write_safety` (full function read)
- `operator-claude-plugin/scripts/n8n_control.py::apply_mutation` (signature + docstring read)
- `operator-claude-plugin/tests/test_write_grant.py`, `test_write_grant_guardrails.py`, `test_review_decision.py` (grep + targeted reads), `test_control_flag_parity.py` (full read), `test_review_outcome_parity.py` (full read)
- `tests/n8n/reviewWriteFlagSeparation.test.mjs`, `reviewAllowlistRefusal.test.mjs` (partial reads)
- `operator-claude-plugin/skills/review-triage/SKILL.md` (full read)
- `.planning/phases/60-review-lane-authority/60-CONTEXT.md`, `.planning/phases/59-frictionless-write-path/59-CONTEXT.md`, `.planning/ROADMAP.md` (Phase 60 entry), `.planning/STATE.md`, `.planning/milestones/v1.1-REQUIREMENTS.md` (grep)

### Secondary (MEDIUM confidence)
- None — every claim above a `[VERIFIED]` tag was checked directly against source this session; no web search or documentation lookup was needed for this internal-plumbing phase.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — no new dependency
- Architecture: HIGH — every mechanism cited was read directly, not inferred, including the exact JS gate function and the exact Python constants this phase must add/extend
- Pitfalls: HIGH — Pitfalls 1-3 were discovered by executing the actual read/scan against the actual files this session, not by pattern-matching the phase description; Pitfall 4/5 are direct readings of the modules named in CONTEXT.md's canonical refs

**Research date:** 2026-09-01
**Valid until:** This research is tied to the current state of `n8n/wf_review_decision_cloud.json`, `write_grant.py`, and `n8n_arming.py` as committed on 2026-09-01. It should be re-verified if any of those three files change materially before this phase is planned/executed (e.g. if a concurrent phase touches Guardrail A or the review workflow first).
