# Phase 67: An autonomy flag with sensible defaults - Research

**Researched:** 2026-09-07
**Domain:** Operator-plugin consent/settings architecture (Python, no external libraries)
**Confidence:** MEDIUM — the mechanics of every existing gate are HIGH confidence (read
directly, line-cited below); the exact shape of the NEW mechanism Phase 67 must add is a
genuine open design question the artifacts do not fully resolve, flagged explicitly below
rather than guessed at.

## Summary

Phase 67 adds no new library, no new service, and no new execution harness. Every piece of
"safety scaffolding" it needs already exists and is read-only reused: `write_grant.py`'s
tri-state ceiling/balance verdicts, `run_report.py`'s mandatory-report builder, and
`config_gate.py`'s capability/authority split. Phase 68 (shipped 2026-09-07, immediately
before this phase) already converted all four write/spend batch skills to an unconditional
"state, pause 5-10s, open a grant, proceed" default — with **no flag gating that behavior at
all**. That is the critical fact this research turned up: the friction Phase 67's brief
worried about removing (the per-round ask) is **already gone, for everyone, unconditionally**.
What is *not* yet built, and what Phase 67 must build, is narrower than "add an autonomy
switch" — it is: (1) name three settings keys so the already-shipped default is visible,
auditable and toggleable; (2) insert the fail-closed refusal on `CEILING_UNKNOWN` / unread
provider balance / missing allowance key that Phase 68's own decision record (D-68-10)
explicitly deferred to this phase, replacing today's "proceed with the blind spot disclosed"
at those three checks; (3) make `run_report.build_run_report` mandatory at the two batch
skills that don't call it today (`contact-upload`, `suggest-contacts`); (4) put the D-61-08
reversal to the operator as an explicit `checkpoint:decision`, recorded; (5) reconcile a real
textual conflict between `REQUIREMENTS.md`'s AUTO-02 and the locked `D-67-03` (below).

**Primary recommendation:** Do not build a new "unattended execution" harness. `scheduled_arm.py`
is pinned grant-free by a live test (`test_headless_grant_boundary.py`) and must stay that way
— genuinely headless (cron-fired, no Claude session) writes can *only* ever go through n8n's
own `ALLOW_N8N_ARM`-gated scheduled workflows, which this phase must not touch (D-67-02,
AUTO-05). "Autonomy" in this phase's actual scope is about an **interactive session that
proceeds without a human reacting to each round** — which is what Phase 68 already ships.
Phase 67's job is to name that behavior, make its unknown-state handling strict by default
(the opposite intuition from "autonomy = more permissive" — here autonomy ON means "nobody is
watching, so fail closed on anything unreadable"), and make the report the record of what an
absent watcher would otherwise have seen.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Autonomy settings keys (3 tiers) | Plugin config (`operator.local.json` + `config_gate.py`) | — | Same tier as `allow_write_grants` (D-67-02: default-setter, not authority) |
| Fail-closed refusal (CEILING_UNKNOWN / balance / allowance key) | Plugin script (`write_grant.py` or a thin new wrapper) | SKILL.md prose (call site) | Refusal lives in code per binding rule; SKILL.md states it |
| Mandatory end-of-run report | Plugin script (`run_report.py`, already built) | SKILL.md (new call sites) | Reuse; wire into `contact-upload`/`suggest-contacts` |
| Two authority gates (`allow_write_grants`, `ALLOW_N8N_ARM`) | Unchanged, out of scope | — | D-67-02 explicitly forbids touching either |
| Genuine decision points (held-row, review-triage, ambiguous match, backend-control mutations) | Unchanged, out of scope | — | D-68-09's test: a different answer changes the outcome and the system cannot pick |

## User Constraints

<user_constraints>

### Locked Decisions (from 67-CONTEXT.md, verbatim in substance)

- **D-67-01**: Three tiers — read-only / spend-no-write / write — all three autonomous by
  default. Naming the tiers is required even though today's default values agree.
- **D-67-02**: The flag is a DEFAULT-SETTER, not a third authority gate. Both
  `allow_write_grants` (interactive) and `ALLOW_N8N_ARM` (headless/cron) stay unchanged and
  required. A third self-authorising gate was considered and rejected (four reasons on
  record in CONTEXT.md). Reversibility: one-way in the direction NOT taken.
- **D-67-03**: Tier defaults apply ON UPDATE — an existing install moves to the new defaults
  rather than keeping current behaviour. The brief recommended the opposite; the operator was
  shown the trade-off and chose the new defaults. Reversibility: one-way.
- **D-67-04**: This phase formally opens D-61-08's unattended gate, handed here by Phase 68's
  D-68-04, and must be presented as a deliberate reversal of the 57-05 Task 4 option-a
  decision (small SUPERVISED batch, not the unattended one), never as a config convenience.
  Reversibility: one-way.
- **D-67-05**: Three fail-closed conditions, each a refusal in code: `CEILING_UNKNOWN`, an
  unread provider balance (D-57-02 tri-state), a missing allowance key. Absent is never
  permissive.
- **D-67-06**: The end-of-run report becomes MANDATORY when the flag is on.
- **D-67-07**: The per-run ceiling is sufficient containment for revocation — chunk-granular
  revocation is NOT built (same conclusion as D-59-06, same cost).
- **D-67-08**: RUN-05 (affordable-subset split) is still incomplete; the flag must account
  for it. Decide in planning: refuse loudly into the mandatory report, or make RUN-05 a
  dependency.

### Claude's Discretion

- The settings keys' names and nesting in `operator.local.json`.
- Whether the three tiers are three keys or one key with three values.
- How the changed-posture notice is surfaced on update (release notes, first-run banner, or
  both).
- Whether RUN-05 is a dependency or a documented limitation.

### Deferred Ideas (OUT OF SCOPE)

- Chunk-granular revocation (D-67-07, declined again).
- RUN-05's affordable-subset split — either a dependency or a documented limitation.
- A third self-authorising gate (rejected in D-67-02).
- Per-skill autonomy overrides finer than the three tiers — not asked for.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTO-01 | Autonomy expressed per tier, not one boolean | See "Tier design" and the skill-classification table below; `config_gate.CAPABILITY_KEYS`/`write_grants_enabled` give the established per-key pattern to extend |
| AUTO-02 | **CONFLICTS with locked D-67-03 — see "Critical conflict" below.** Text says every default preserves current behaviour; D-67-03 says defaults change on update. Not resolvable by research; flagged for the planner/operator. |
| AUTO-03 | Fail closed on `CEILING_UNKNOWN`, unread provider balance, missing allowance key | Exact code locations and current (non-fail-closed) behaviour cited in "The three fail-closed conditions" below — this is genuinely unbuilt, not merely undocumented |
| AUTO-04 | Put the D-61-08 reversal to the operator explicitly, as a reversal, and record the answer | A `checkpoint:decision` task, first in the plan, mirroring 68-01's Task 2 pattern (`prose-and-pin`: recorded in SKILL.md prose + pinned by a structural test) |
| AUTO-05 | Does not replace `ALLOW_N8N_ARM` for the headless/cron path | `test_headless_grant_boundary.py` already pins `scheduled_arm.py` grant-free; Phase 67 must not touch it — extend the SAME AST-walk test style if a new check is needed, never modify the pinned file |
| AUTO-06 | End-of-run report mandatory when autonomy is on | `run_report.build_run_report`/`record_audit` already exist; not called today by `contact-upload`, `suggest-contacts`, `review-triage`, `backend-control` — see call-site audit below |

</phase_requirements>

## Critical conflict: REQUIREMENTS.md AUTO-02 vs. locked D-67-03

This is the single most important finding in this research and must be resolved before or
during planning — it cannot be resolved by research alone.

- `.planning/REQUIREMENTS.md:77` (AUTO-02, unticked): *"Every default preserves CURRENT
  behaviour, so a plugin update never turns autonomy on for an existing install."*
- `.planning/phases/67-.../67-CONTEXT.md` D-67-03 (LOCKED, gathered 2026-09-05, one commit day
  after AUTO-02 was written on 2026-09-04 per `cb833db`): *"An existing install moves to the
  new defaults rather than keeping current behaviour. The brief recommended the opposite... the
  operator was shown that trade-off... and chose the new defaults."*

These say the opposite thing. Git history confirms the sequence: AUTO-02 was written into
`v1.2-REQUIREMENTS.md` on 2026-09-04 as part of defining the whole v1.2 milestone
(`plan(v1.2)` commit `cb833db`), *before* `/gsd-discuss-phase` ran for Phase 67 on 2026-09-05
and produced D-67-03 — which explicitly records the operator being shown AUTO-02's own
recommendation (worded identically to the brief's "sensible defaults... defaulting to the
CURRENT behaviour" line) and choosing to override it. AUTO-02's text is stale; nothing in the
repo updated it after the reversal was recorded. The task's own framing note ("D-67-01..D-67-08
are LOCKED") and the general GSD rule that CONTEXT.md decisions bind planning both point the
same way: **D-67-03 should govern, and AUTO-02's text needs to be corrected to match it before
or during this phase's planning** — either by the planner rewriting the requirement text, or by
surfacing it to the operator as an explicit confirmation before implementing. Do not silently
implement one and let the other stand unticked-and-wrong in the requirements ledger.

Practically, this conflict is easier to resolve in code than it looks (see next section):
`config_gate.write_grants_enabled` already establishes the pattern of "absent key reads a
specific way in code," and nothing in this repo's config-migration mechanism (`durable_paths.py`
step 5, `33-02`) copies new *default* values into an existing install's config on update — it
only copies an existing file's *existing* keys verbatim to a new install location. So "the
default changes on update" does not require writing anything into anyone's file; it is
satisfied for free by choosing the new tier keys' **code-level default** to be `True` when the
key is absent. This automatically satisfies D-67-03 (an existing install with no such key
present gets the new default) and is why AUTO-02's literal text is the one that is actually
wrong given the operator's own later decision, not an error of implementation.

## Architecture Patterns

### The two authority gates (read this before writing any code — do not touch either)

Both gates are unmodified by this phase, per D-67-02 and AUTO-05. They are cited here so the
plan can point at exact lines rather than re-derive them:

- **`allow_write_grants`** — `operator-claude-plugin/scripts/config_gate.py:104`
  (`WRITE_GRANT_SETTINGS_KEY = "allow_write_grants"`), checked by
  `write_grants_enabled(config)` at `config_gate.py:107-121`: `(config or {}).get(KEY) is True`
  — identity check, not truthiness, not `.lower() == "true"`. Absent key → `False`. This is
  the established pattern for "a JSON boolean is the ONE thing that means yes" in this repo,
  and it is the pattern the *authority* gates use — deliberately different from what the new
  *default-setter* tier keys should do (see below).
- **`ALLOW_N8N_ARM`** — `n8n_arming.py:178` (`ARM_ENV_VAR = "ALLOW_N8N_ARM"`), checked in
  `_arm_gate()` at `n8n_arming.py:213-263`. Two branches: WITH a grant (interactive,
  `write_grants_enabled`), WITHOUT a grant (headless, exact string `"true"` env var). These are
  the ONLY two branches that exist in code today. There is no third branch, and Phase 67 must
  not add one to `_arm_gate`.
- **`scheduled_arm.py` is pinned grant-free** by
  `operator-claude-plugin/tests/test_headless_grant_boundary.py` (3 tests, shipped 68-01): no
  `write_grant` import, no `write_grant` substring anywhere in its source, no `plan_grant()`/
  `open_grant()` call outside `write_grant.py` itself. **A genuinely headless, cron-fired write
  cannot go through `write_grant.py`'s mechanism at all** — this is a hard, tested boundary, not
  a convention. It rules out any design where Phase 67 builds a new unattended-write entrypoint
  reusing the grant machinery; that would either violate this pin or require rewriting it
  (out of scope, and D-67-02 forbids it).

### What Phase 68 already shipped, and what it explicitly left for Phase 67

Confirmed by reading `68-01/02/03-SUMMARY.md` and the four `SKILL.md` files directly (not
inferred from CONTEXT.md alone):

- All four write/spend batch skills — `enrich-before-ingest`, `enrich-records`,
  `contact-upload`, `suggest-contacts` — now price a grant, state the arithmetic (including any
  `CEILING_UNKNOWN`/unsampled-ceiling sentence), pause once via `watch.pre_spend_pause()`
  (`watch.py`, `PRE_SPEND_PAUSE_SECONDS = 7`), open the grant with the literal `"yes"`, and
  proceed — **unconditionally, with no settings key gating this behavior at all.** The old
  two-phase ask survives only as the path taken if the operator interrupts.
- `write_grant.plan_grant` (`write_grant.py:962-1120`) computes `ceiling = figures["ceiling"]`
  from `ceiling_verdict` (`write_grant.py:319-364`) and `allowance_headroom`
  (`write_grant.py:209-...`). Per D-57-02, **`CEILING_UNKNOWN` never refuses today** —
  `write_grant.py:1111-1120` states explicitly: *"A `CEILING_UNKNOWN` verdict proceeds with the
  blind spot disclosed... Only `CEILING_OVER` refuses."* This is unconditional, for every
  caller, interactive or otherwise — there is no parameter that changes it.
- Phase 68's own decision record makes the deferral explicit and load-bearing:
  **D-68-10** (`68-CONTEXT.md`, "Planning-time rulings... 2026-09-07"): *"An implicit open on
  `CEILING_UNKNOWN` PROCEEDS, with the blind spot disclosed. The implicit-open path inherits the
  explicit path's behaviour unchanged... No Phase-68-only fence; fail-closed on
  `CEILING_UNKNOWN` stays Phase 67's (D-68-04)."*
- `backend-control/SKILL.md:113-116` (added by 68-01) states this in the operator-facing prose
  itself: *"Implicit approval (D-68-01) is a posture of this conversation only. The scheduled
  and cron paths are unchanged by this phase and stay gated by `ALLOW_N8N_ARM` exactly as
  before; the unattended gate itself — the autonomy levels and their fail-closed conditions —
  is Phase 67's to open (D-68-04)."* This is the exact hook site Phase 67 must edit.

**Conclusion: the single, concrete, unambiguous code change this phase's AUTO-03 requires is a
refusal that does not exist anywhere in the codebase today** — a new gate, inserted at the same
call sites Phase 68 built, that intercepts `CEILING_UNKNOWN` (and the analogous unread-balance
and missing-allowance-key cases) and refuses instead of proceeding, when autonomy is what is
making the round proceed unsupervised. Since Phase 68 made "proceed unsupervised" the universal,
unconditional default, and D-67-01 sets autonomy ON by default for all three tiers, this refusal
is — under the tier defaults — the new UNCONDITIONAL behavior at those three checks, unless an
operator explicitly turns a tier's autonomy off (which then falls back to today's D-68-10
proceed-with-disclosure, i.e. "I am here, I accept the blind spot, don't block me").

**This reframing — autonomy ON tightens unknown-state handling, it doesn't loosen it — is the
one design recommendation in this research most worth a `checkpoint:decision` to confirm with
the operator early**, because it inverts the naive intuition that "autonomy" means "fewer
refusals." It is, however, exactly what D-67-05's own wording requires ("an autonomy default
must never treat an unreadable state as permission") and is the only reading that is coherent
with D-67-02 ("the flag decides only whether an already-authorised action proceeds without
asking" — i.e., it changes *whether you ask*, and the compensating control for not asking is
stricter handling of the unknown).

### Tier design and the settings-key shape (Claude's discretion, with a recommendation)

Recommended shape, following the established `_key_note` documentation pattern already used
throughout `operator.local.example.json`:

```json
{
  "autonomy": {
    "read_only": true,
    "spend_no_write": true,
    "write": true
  },
  "_autonomy_note": "Per-function-tier default: whether a batch proceeds without asking, once
    already authorised by allow_write_grants/ALLOW_N8N_ARM (D-67-02 — this key is a
    default-setter, never a third authority gate). Absent keys default to true (D-67-03: an
    update moves an existing install to the new defaults). Turning a tier's key to false
    reverts that tier's rounds to asking first, as they did before Phase 68/67."
}
```

**Vocabulary constraint (D-10b, binding):** `test_report_enrichment.py:635`
(`_FORBIDDEN_SUBSTRINGS = ("icp", "tier")`) and
`test_no_operator_facing_skill_body_mentions_icp_or_tier_not_even_a_placeholder`
(`test_report_enrichment.py:666-681`) case-insensitively substring-scan every
`skills/*/SKILL.md` body (one named exemption: `loss-reason-report/SKILL.md`) for the literal
substrings `"icp"` and `"tier"`. This is a **substring**, not a whole-word match, so it will
also catch any word containing "tier" (there is no plausible collision in this phase's
vocabulary, but do not introduce one). **Never write the word "tier" in any SKILL.md prose,
settings-key name, CHANGELOG entry that ships inside the plugin package, or code comment inside
a SKILL.md.** Phase 68-01 hit this exact collision and fixed it by using **"autonomy levels"**
instead of "autonomy tiers" — reuse that exact wording. The settings-key names above
(`read_only` / `spend_no_write` / `write`) avoid the word entirely and are safe. Python test
files and `.py` docstrings are NOT scanned by this guard (only `skills/*/SKILL.md` bodies and
the serialized report JSON) — internal code comments and STATE.md/ROADMAP.md prose may say
"tier" freely; only operator-facing SKILL.md text and rendered report output are gated.

**Two keys or three, or nesting — recommendation:** three keys nested under one `autonomy`
object (as above), matching `CAPABILITY_KEYS`' per-row structure rather than
`write_grants_enabled`'s single flat key, because D-67-01 explicitly requires the three tiers
be independently named and independently defaultable even when their values agree today — a
single boolean would not survive an operator later wanting `write` off while `spend_no_write`
stays on, which the phase's own "all functions" framing anticipates as a real, near-term need.

**Absence handling — do NOT reuse `write_grants_enabled`'s `is True` identity-on-absence
pattern for these keys.** That pattern is deliberately built for an AUTHORITY gate, where
absence must mean "no" (D-67-05's "absent is never permissive" — this principle governs the
THREE FAIL-CLOSED CONDITIONS and the two AUTHORITY gates, not the tier default itself). The new
tier keys are a DEFAULT-SETTER (D-67-02), not an authority — the action is already authorised
by the two unchanged gates before an autonomy key is ever consulted. So: read each tier key as
`cfg.get("autonomy", {}).get(tier_name, True)` — an explicit Python-level default of `True`,
distinct in kind from `is True`'s absent-means-off. Document this distinction explicitly in a
code comment at the read site, because a future reader who has internalized
`write_grants_enabled`'s pattern will otherwise "fix" this into the wrong shape.

### Skill-by-skill tier classification (evidence for AUTO-01, D-67-01)

Read directly from `operator-claude-plugin/tests/test_disclosure_audit.py`'s `AUDIT` dict
(lines ~59-70) and each skill's own genuine-decision-point literal
(`PRESERVED_LITERALS`, same file, lines ~72-79) — this table already exists as a *tested*
artifact for Phase 68's purposes; the tier column below is this research's addition, mapped
against D-67-01's own tier definitions.

| Skill | AUDIT verdict (test-pinned) | Tier (D-67-01) | Genuine decision point that STAYS a question under any autonomy setting |
|---|---|---|---|
| `backend-status` | swept-no-findings | read-only | none |
| `backend-sweep` | swept-no-findings | read-only | none |
| `loss-reason-report` | swept-no-findings | read-only | none (also the D-10b "tier" exemption skill) |
| `initialize` | swept-no-findings | read-only | its "never guess a value" config-gate stop is a hard STOP, not an ask — unaffected either way |
| `suggest-contacts` | converted + decision-point-preserved (split, step 3) | **spend-no-write** (match/propose) | role selection ("no default to state instead of asking it") — genuine, D-68-02 |
| `contact-upload` | converted (decision-point-preserved: per-header confirmation) | **write** (ingest) | one confirmation per header — a header like `Ph.` could be phone or photo |
| `enrich-before-ingest` | converted (decision-point-preserved: held-row review vocabulary) | **write** (ingest + enrich) | held/ambiguous row's end-of-run `approve`/`deny`/`pick`/`email:` vocabulary |
| `enrich-records` | converted (decision-point-preserved: company-domain confirmation) | **write** (enrich-and-write) | an undecided company-domain row stops the whole batch, never defaults |
| `review-triage` | decision-point-preserved (verified non-change) | **write** (review-decision apply) | its entire per-record ritual — unmodified by Phase 68, "unchanged by the grant" |
| `backend-control` | decision-point-preserved | **not one of the three tiers — see below** | every structural mutation (workflow on/off, schedule change, arm live writes, grant open/revoke) — explicit-yes confirm-and-wait, scoped OUT of D-68-01 by its own existing prose |

**Open classification question, not resolved by the artifacts — flag for the planner:**
`backend-control`'s mutations (arm/disarm, schedule change, deploy) do not fit cleanly into
"read-only / spend-no-write / write" as D-67-01 defines them (those three are about
*enrichment functions*, not infrastructure control). `backend-control`'s AUDIT verdict is
"decision-point-preserved" **unconditionally** — Phase 68 explicitly scoped its own implicit-
approval posture OUT of this skill ("D-68-01's implicit-approval posture is scoped to batch
spend, never to this skill's own mutations" — `test_disclosure_audit.py`'s own docstring
table). **Recommendation: leave `backend-control`'s confirm-and-wait rule untouched by Phase
67 entirely** — it is neither a tier nor a genuine per-record decision point in the same shape
as held-row review; it is closer to `ALLOW_N8N_ARM`/`allow_write_grants` in kind (an
infrastructure-level authority action), and the phase's own binding rule ("no guard rail
weakened") argues for leaving it exactly as-is unless a future phase asks specifically.

### The three fail-closed conditions — exact code, exact current (non-refusing) behaviour

All three cited from source read this session, with the current behaviour stated precisely so
the plan does not accidentally re-derive or contradict it:

1. **`CEILING_UNKNOWN`.** `write_grant.ceiling_verdict(figures, headroom)` —
   `write_grant.py:319-364`. Returns `CEILING_UNKNOWN` whenever `headroom["sampled"]` is
   `False` OR `figures["projected_executions"]` is `None`. `allowance_headroom(config, ...)`
   (`write_grant.py:209-...`) sets `sampled=False` when the executions listing could not be
   read, was truncated by the page budget, or (see #3 below) the allowance key itself is
   unconfigured. `plan_grant` (`write_grant.py:962-1120`) reads this verdict at line ~1111 and
   **only refuses on `CEILING_OVER`** — `CEILING_UNKNOWN` proceeds today, unconditionally, for
   every caller.
2. **Unread provider balance.** `cost_guard.fetch_balances(config, transport=None)`
   (`cost_guard.py:343-383`) returns `{provider: {credits, unreadable, reason}}` per provider,
   using **identity checks only** (`row.get("unreadable") is True or credits is None`) — never
   truthiness, so an unreadable balance is never collapsed into a zero-shaped one.
   `cost_guard.compare(estimate, balances)` (`cost_guard.py:392+`) turns this into the
   tri-state verdict `ok` / `insufficient` / `unknown` per provider. This account already reads
   `unknown` for one of three providers routinely (Apollo's non-master key → 403, per CLAUDE.md
   §14's cost note and `write_grant.py:1008`'s own comment: "two of three provider balances
   already read `unknown` on this account"). Today `unknown` does not refuse anywhere in the
   dispatch path — it is disclosed, not gated.
3. **A missing allowance key.** `allowance_headroom` (`write_grant.py:209-260`) checks
   `raw_allowance = (config or {}).get(n8n_read.EXECUTION_ALLOWANCE_KEY)` — the config key is
   `n8n_monthly_execution_allowance` (see `operator.local.example.json`'s
   `_n8n_monthly_execution_allowance_note`, which already warns "a missing, blank or
   non-positive value here means the sweep is NOT watching the execution budget at all"). If
   `raw_allowance` is not a positive `int`, `sampled` is forced `False` and the reason states
   "not configured (or is not a positive whole number)". **This is a different "missing key"
   than the new autonomy tier keys** — do not conflate the two in the plan. This specific key's
   absence already collapses into condition #1 (`CEILING_UNKNOWN`) mechanically, since
   `ceiling_verdict` reads `headroom["sampled"]` alone; a plan does not need a fourth, separate
   check for this — it needs to confirm condition #1's refusal also fires for this specific
   root cause (it does, by construction, since `allowance_headroom` already sets
   `sampled=False` for it).

**Design for the new refusal** (recommendation, to be confirmed via `checkpoint:decision`): a
small, pure wrapper — e.g. `autonomy_gate.refuses(ceiling_verdict, balance_verdicts, *,
autonomy_on)` — inserted into each of the four SKILL.md implicit-open sequences immediately
after `plan_grant`/`envelope` returns figures and before `pre_spend_pause()`/`open_grant()` are
called. It refuses (never proceeds-with-disclosure) when `autonomy_on` is `True` for the
relevant tier AND (`ceiling["verdict"] == CEILING_UNKNOWN` OR any consulted provider balance
verdict is `unknown`). When `autonomy_on` is `False` for that tier, it defers entirely to
today's (Phase 68) behavior — proceed with the blind spot disclosed. This function is new,
small, pure, and testable in isolation exactly like `ceiling_verdict` itself — it does not
require touching `plan_grant`'s own signature or its `CEILING_OVER`-only refusal logic, which
must stay unchanged (it is the one other caller of this exact figures dict, and Phase 68's own
tests pin its current shape).

### The mandatory end-of-run report (AUTO-06, D-67-06)

`run_report.record_audit` (`run_report.py:169-227`) and `run_report.build_run_report`
(`run_report.py:668-690`, delegating to `_build_run_report` at `:697+`) are fully built —
"never raises," degrades any missing input to a named `gaps` entry, joins five durable stores
plus the audit record. **Confirmed by direct grep of every skill's `SKILL.md`, session-fresh:**

| Skill | Calls `record_audit` | Calls `build_run_report` |
|---|---|---|
| `enrich-before-ingest` | yes (`SKILL.md:474,510,825,861`) | yes (`SKILL.md:1038`) |
| `enrich-records` | yes (`SKILL.md:461,494`) | yes (`SKILL.md:597`) |
| `contact-upload` | **no** | **no** |
| `suggest-contacts` | **no** | **no** |
| `review-triage` | **no** | **no** |
| `backend-control` | **no** | **no** |

**Recommendation:** wire `build_run_report`/`record_audit` into `contact-upload` and
`suggest-contacts` — both are batch, spend-or-write-capable skills whose autonomous rounds
under this phase need the same "only account of what happened" the two enrich skills already
get. `review-triage` and `backend-control` are per-record/per-action skills without a "run" of
their own in the `run_manifest`/`run_state` sense (no batch scope object exists for them today)
— extending the report machinery to them is a larger, more speculative change; recommend
**documenting this as an explicit scope decision** (report is mandatory for the two remaining
batch skills; `review-triage`/`backend-control` are out of scope for this phase's AUTO-06,
named explicitly rather than silently skipped) rather than building new run-scope machinery for
two skills that don't currently have one.

### Where the first-run notice belongs (D-67-03's consequence)

No session-start hook exists in this plugin's architecture — every skill is invoked on-demand,
including `initialize`. The cheapest, most reliable surface, given that constraint:

1. **CHANGELOG.md entry, mandatory regardless** — `operator-claude-plugin/.claude-plugin/plugin.json`
   is currently `"0.40.0"` (unbumped since before Phase 68 shipped), and per
   `operator-claude-plugin/CHANGELOG.md`'s own release checklist, a version bump is required
   in the same commit as the CHANGELOG entry or the Update button in Claude Desktop/Code stays
   greyed out and the change is invisible regardless of what shipped (confirmed by memory note
   `plugin-release-requires-version-bump` and the file's own header).
2. **Edit the existing `backend-control/SKILL.md:113-116` paragraph in place** (added by 68-01,
   already states "the unattended gate itself... is Phase 67's to open") to instead state what
   Phase 67 actually did, since `backend-control` is a routinely-invoked skill (status/arm
   actions) an operator is likely to hit early after updating — no new mechanism required,
   just updating prose already at the right hook site.
3. Do not build a "last-seen version" tracking mechanism to gate a one-time banner — that is
   new persisted state for a one-time notice, and the phase brief's own "missing switch, not
   missing safety" framing argues against inventing new scaffolding here.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ceiling/balance tri-state verdicts | A new UNKNOWN/OK/OVER classifier | `write_grant.ceiling_verdict`, `cost_guard.compare` | Already produce the exact tri-state D-67-05 needs; reused unmodified |
| Refusal-before-start | A new pre-flight check | `write_grant.plan_grant`'s existing `CEILING_OVER` refusal path as the template | Same shape, same "refusal carries the batch's own figures" pattern |
| End-of-run report | A new report/summary builder | `run_report.build_run_report` / `record_audit` | Fully built, "never raises," already joins 5 durable stores |
| Settings-key documentation | Free-text README | `_key_note` sibling-key pattern already used 12+ times in `operator.local.example.json` | Established, consistent, self-documenting in the one file operators actually read |
| Pinning a structural absence (e.g. "no new key reaches `scheduled_arm.py`") | A prose claim in CONTEXT.md only | AST-walk symbol-absence test, same style as `test_headless_grant_boundary.py` | This repo's own established pattern for making a claim like AUTO-05 a checked fact, not an assertion |

**Key insight:** every mechanism this phase needs already exists in this codebase in a form one
call away from reuse. The actual work is: two or three new settings keys, one new small pure
refusal function, two new report call sites, one prose edit, and one `checkpoint:decision`
task — not new infrastructure.

## Common Pitfalls

### Pitfall 1: Assuming "autonomy on" answers genuine decision points

**What goes wrong:** a plan that reads D-67-01 ("all functions can be run autonomously") too
literally and tries to auto-resolve held rows, ambiguous matches, or review-triage's per-record
approve/reject when the write tier is on.
**Why it happens:** the phase's own goal language ("without per-step intervention") sounds
total.
**How to avoid:** `test_disclosure_audit.py`'s own docstring states the test precisely: "a
statement of fact the operator cannot act on differently is not a decision point... What stays
a genuine question: anything where a different answer changes what happens and the system
cannot pick." Every genuine decision point catalogued above (held-row vocabulary, per-header
confirmation, undecided company-domain row, review-triage's whole ritual, `suggest-contacts`'
role ask) stays a question under every autonomy setting. None of them is affected by this
phase.
**Warning signs:** any plan task that proposes a default value for an ambiguous match, or that
proposes review-triage auto-approving anything.

### Pitfall 2: Reading `write_grants_enabled`'s absent-key pattern as the template for the new tier keys

**What goes wrong:** copying `(config or {}).get(KEY) is True` (absent → `False`/off) for the
new autonomy keys, which would make D-67-03's "defaults apply on update" false in code even
while claiming to satisfy it, since an absent key would read as autonomy OFF.
**Why it happens:** it's the only precedent in the file, and it's explicitly praised in the
canonical refs as "the ONE definition" of the boolean-settings pattern.
**How to avoid:** that pattern is for AUTHORITY gates specifically (`allow_write_grants`,
implicitly `ALLOW_N8N_ARM`'s exact-string-match). The new tier keys are a DEFAULT-SETTER
(D-67-02) layered on top of authority that is already granted elsewhere — use
`cfg.get("autonomy", {}).get(tier, True)`, an explicit code-level default, not identity-on-
absence.
**Warning signs:** a test asserting an absent `autonomy` key behaves identically to
`{"write": false}` — that test itself would be the bug.

### Pitfall 3: Touching `scheduled_arm.py` or widening `_arm_gate`'s two branches

**What goes wrong:** any temptation to add a third `_arm_gate` branch, or to have
`scheduled_arm.py` read the new autonomy keys "for consistency."
**Why it happens:** the word "unattended" appears in both this phase's brief and in
`scheduled_arm.py`'s own docstring ("this runs unattended, ..."), inviting a false equivalence.
**How to avoid:** `scheduled_arm.py`'s "unattended" is n8n's own cron-fired SJ-3 poller,
completely separate machinery from this phase's "autonomy," gated ENTIRELY by `ALLOW_N8N_ARM`
and untouchable per D-67-02/AUTO-05. `test_headless_grant_boundary.py` will fail loudly (by
design) if `write_grant` is ever imported or named in that file.
**Warning signs:** a diff touching `scheduled_arm.py` at all, for any reason, in this phase.

### Pitfall 4: Forgetting the D-10b "tier" ban is a case-insensitive substring scan

**What goes wrong:** using "autonomy tier(s)" anywhere in a `SKILL.md` body, which fails
`test_no_operator_facing_skill_body_mentions_icp_or_tier_not_even_a_placeholder`
(`test_report_enrichment.py:666`).
**Why it happens:** the word is natural, it's used throughout `.planning/` docs and this
research, and Phase 68 already made this exact mistake once (caught before commit).
**How to avoid:** use "autonomy levels" (Phase 68's own fix) or "per-function default"
throughout every `SKILL.md` edit. `.planning/` markdown, `.py` docstrings, and non-skill
markdown are NOT scanned — only `skills/*/SKILL.md` bodies and rendered report JSON.
**Warning signs:** `grep -il tier operator-claude-plugin/skills/*/SKILL.md` returning anything
other than nothing (the exemption file `loss-reason-report` is not touched by this phase, so
even that one exemption should stay unaffected).

### Pitfall 5: Treating RUN-05's incompleteness as blocking

**What goes wrong:** deciding Phase 67 cannot ship until RUN-05's affordable-subset split is
built, when D-67-08 explicitly leaves this as a planning-time choice, not a hard dependency.
**Why it happens:** the brief and CONTEXT.md both flag it prominently.
**How to avoid:** `plan_grant`'s existing `CEILING_OVER` refusal (`write_grant.py:1120-1150`,
`split_for_allowance` at `write_grant.py:871+`) already carries a concrete "smaller batch"
offer in its refusal text — the mechanism already partially exists for a human to act on
manually. Under autonomy, the cheapest, lowest-risk path (recommended) is: the CEILING_OVER
refusal (unchanged, already correct) simply lands in the mandatory report as a named refusal
rather than being silently swallowed — no new split-execution logic required. Document this as
the chosen resolution rather than building RUN-05's split offer inside this phase.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python), `node --test` (n8n code, unaffected by this phase) |
| Config file | `operator-claude-plugin/tests/` (no separate pytest.ini found; run from `operator-claude-plugin/`) |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_headless_grant_boundary.py operator-claude-plugin/tests/test_implicit_approval_contract.py -q` |
| Full suite command | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (baseline: 2646 passed, 5 skipped, confirmed this session's read of 68-REVIEW-FIX.md) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTO-01 | Three tiers, separate keys, independently defaultable | unit | new `tests/test_autonomy_levels.py` (config read/default behavior) | ❌ Wave 0 |
| AUTO-02 | (conflict — see above; do not write a test until the text conflict is resolved) | — | — | blocked on decision |
| AUTO-03 | `CEILING_UNKNOWN`/unread balance/missing allowance key refuse under autonomy | unit | new test(s) for the new refusal wrapper, parametrized over the three conditions | ❌ Wave 0 |
| AUTO-04 | D-61-08 reversal recorded, prose + pin | unit | extend `test_headless_grant_boundary.py`-style AST/literal pin at whichever SKILL.md carries the record (likely `backend-control/SKILL.md`) | ❌ Wave 0 (extends existing file/pattern) |
| AUTO-05 | `ALLOW_N8N_ARM` untouched, `scheduled_arm.py` stays grant-free | unit | `operator-claude-plugin/tests/test_headless_grant_boundary.py` | ✅ exists, re-run only |
| AUTO-06 | Mandatory report at `contact-upload`/`suggest-contacts` | unit | extend `test_implicit_approval_contract.py`-style call-order pin, or a new `test_mandatory_report_call_sites.py` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the relevant subset above (quick run command)
- **Per wave merge:** full suite (`operator-claude-plugin/tests/ -q`) + `node --test tests/n8n/*.test.mjs` (940 pass baseline, unaffected — confirm no n8n files touched, matching every Phase 68 plan's own verify step: `git status --porcelain -- n8n/ scripts/build_cloud_workflows.py` empty)
- **Phase gate:** full suite green before `/gsd-verify-work`, plus `git diff --name-only <pre-phase-commit> -- operator-claude-plugin/scripts/` reviewed by hand to confirm `scheduled_arm.py`, `n8n_arming.py` are absent from the diff (mirrors every Phase 68 plan's own self-check pattern)

### Wave 0 Gaps
- [ ] `operator-claude-plugin/tests/test_autonomy_levels.py` — the three tier keys, their
      default-True-when-absent behavior, and their nesting under `autonomy`
- [ ] A new refusal test file (or an addition to `test_write_grant.py`) covering the three
      fail-closed conditions under autonomy
- [ ] An extension to `test_implicit_approval_contract.py`'s `TARGETS`-style table, or a new
      file, for the mandatory-report call sites at `contact-upload`/`suggest-contacts`
- [ ] Framework install: none — pytest and the whole harness already present, no gap

## Environment Availability

Skipped — this phase is a pure code/config/prose change inside an already-configured
repository. No new external dependency, service, or CLI tool is introduced. The existing
`n8n_url`/`webhook_secret`/`n8n_api_key`/`n8n_monthly_execution_allowance` config surface is
read, never newly required.

## Package Legitimacy Audit

Skipped — this phase installs no external package. Every module it touches or reuses
(`write_grant`, `cost_guard`, `run_report`, `config_gate`, `n8n_arming`) is already part of
this repository's own `operator-claude-plugin/scripts/` tree.

## Project Constraints (from CLAUDE.md)

- Never hand-edit `n8n/wf_*.json` — this phase should touch no `n8n/` file at all; if any diff
  appears there, it is out of scope and should be reverted.
- No `while` / `import time` / `sleep()` in any plugin script except `watch.py` — the new
  refusal-wrapper function must stay pure (no loop, no sleep); `watch.pre_spend_pause` already
  exists and is reused unmodified, never duplicated.
- Nothing armed, no live HubSpot writes — this phase changes settings-key defaults and refusal
  logic; it authorizes nothing live by itself (the two existing gates still require an admin's
  separate action).
- `.env` is permission-blocked — not relevant; this phase's config surface is
  `operator.local.json`, a plain JSON file, not `.env`.

## Sources

### Primary (HIGH confidence — all read directly this session)
- `operator-claude-plugin/scripts/write_grant.py` — module header (lines 1-33), `CEILING_*`
  constants (195-197), `allowance_headroom` (209-315), `ceiling_verdict` (319-364), `envelope`
  (415+), `plan_grant` (962-1150), `close_grant` (1248+)
- `operator-claude-plugin/scripts/config_gate.py` — full file (215 lines): `CAPABILITY_KEYS`
  (57-73), `WRITE_GRANT_SETTINGS_KEY` (104), `write_grants_enabled` (107-121)
- `operator-claude-plugin/scripts/n8n_arming.py` — module header, `ARM_ENV_VAR`/`DISPATCH_FLAGS`/
  `REVIEW_FLAGS` (178-199), `_arm_gate` (213-263)
- `operator-claude-plugin/scripts/durable_paths.py` — module header, migration mechanism (1-90)
- `operator-claude-plugin/scripts/cost_guard.py` — `fetch_balances` (343-383), `compare` (392+)
- `operator-claude-plugin/scripts/run_report.py` — module header, `record_audit` (169-227),
  `build_run_report` (668-690)
- `operator-claude-plugin/scripts/run_manifest.py`, `run_state.py`, `held_queue.py`,
  `confidence.py` — module headers (first ~40 lines each)
- `operator-claude-plugin/scripts/sweep_entry.py`, `sweep_shim.py` — module headers
- `operator-claude-plugin/tests/test_disclosure_audit.py` — full `AUDIT` dict, `PRESERVED_LITERALS`,
  module docstring (1-100)
- `operator-claude-plugin/tests/test_headless_grant_boundary.py` — full file
- `operator-claude-plugin/tests/test_report_enrichment.py` — `_FORBIDDEN_SUBSTRINGS` and the
  banned-word test (635-681)
- `operator-claude-plugin/skills/backend-control/SKILL.md:95-120`
- `operator-claude-plugin/skills/initialize/SKILL.md:1-45`
- `operator-claude-plugin/config/operator.local.example.json` — full file
- `operator-claude-plugin/CHANGELOG.md`, `.claude-plugin/plugin.json` — version/release process
- Grep confirmation of `record_audit`/`build_run_report` call sites across all 6 write-capable
  `SKILL.md` files (session-fresh, this research)
- `.planning/phases/67-.../67-CONTEXT.md`, `.planning/phases/68-.../68-CONTEXT.md`,
  `68-01/02/03-SUMMARY.md`, `68-REVIEW-FIX.md` — full text
- `.planning/REQUIREMENTS.md` (AUTO section, lines 73-86), `.planning/ROADMAP.md` (Phase 67/68
  entries, Standing facts), `.planning/todos/pending/2026-09-04-autonomy-flag-with-sensible-defaults.md`
- `git log`/`git show` on `.planning/REQUIREMENTS.md` — dating AUTO-02 to commit `cb833db`
  (2026-09-04), before D-67-03's context-gathering (2026-09-05)

### Secondary / Tertiary
None used — this research required no external documentation lookup (no new library, no new
service); every claim above is sourced from a file read directly in this repository this
session.

## Metadata

**Confidence breakdown:**
- Existing mechanisms (ceiling/balance tri-state, report builder, authority gates): HIGH — read
  directly, line-cited
- The exact shape of the new refusal wrapper and settings-key defaulting: MEDIUM — a coherent,
  evidence-grounded recommendation, but genuinely a design choice the artifacts leave open;
  flagged for a `checkpoint:decision`
- The REQUIREMENTS.md AUTO-02 vs. D-67-03 conflict: HIGH confidence the conflict exists and is
  real (dated by git history); the resolution itself is a decision for the planner/operator, not
  research
- `backend-control`'s tier classification: MEDIUM — a reasoned recommendation (leave untouched),
  not settled by any locked decision

**Research date:** 2026-09-07
**Valid until:** This phase should be planned promptly — it directly follows Phase 68
(completed same day) and both operate on the same `SKILL.md` prose surface. A significant delay
risks drift in `write_grant.py`'s figures or in Phase 69 (held rows), which lands next and
touches related surfaces per its own CONTEXT.md.
