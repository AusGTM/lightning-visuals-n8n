# Phase 68: State the Price and Keep Moving - Research

**Researched:** 2026-09-07
**Domain:** Prose/consent-flow engineering in a Claude Code plugin (`operator-claude-plugin`) — no new library, no new package, no new runtime dependency. The domain is: existing Python modules (`write_grant.py`, `suggest_contacts.py`, `watch.py`), existing `SKILL.md` prose contracts, and the pytest suite that pins both.
**Confidence:** HIGH — every claim below is either a direct `Read` of the source-of-truth file this session (quoted, with line numbers) or a `grep`/`git log` run this session. No web research was needed; this phase touches no external API, library, or framework.

## Summary

Phase 68 is a **pure in-repo prose-and-code edit**, not a research-a-new-technology phase. Every question the phase brief poses is answerable by reading five files: `write_grant.py`, `suggest_contacts.py`, `watch.py`, `test_report_sufficiency.py`, and `scheduled_arm.py`, plus the ten `skills/*/SKILL.md` files that make up the audit surface. This document answers the three required questions with file:line evidence, maps the audit (FLOW-04/D-68-09) skill-by-skill, and lays out the mechanical shape of D-68-01/03/07 changes against code that already does 90% of what the decisions ask for.

**Primary recommendation:** Implement D-68-01's implicit-approval branch as a **fourth arming path** parallel to the three that already exist (`authorize_send`, `authorize_ungranted_send`, and the review-triage per-record arm) — never as a change to any of those three. Thread the pre-spend pause through `watch.py` (the one file the test suite already exempts from the no-sleep/no-while rule) as a dependency-injected function mirroring `poll_until_settled`'s existing `now=`/`sleep=` pattern, invoked via a `python3 scripts/watch.py ...` subprocess call from the SKILL.md step — never as a literal `sleep N` Bash instruction, and never as `time.sleep()` inlined in any other `scripts/*.py` file. Open D-68-03's implicit grant with `write_grant.plan_grant(..., suggestion_companies=..., suggestion_cap=None)` — the exact call `enrich-records/SKILL.md` step 5 already makes for the *explicit* grant path — so `agreed_cap`/`CapRefused` need zero code changes. Leave `plan_grant`'s `CEILING_UNKNOWN` behavior (proceed, disclosed) untouched per D-57-02/D-68-04, and make the implicit-open disclosure state that blind spot explicitly in the stated line.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Implicit-approval branch (no-grant → state-and-proceed) | SKILL.md prose (per-skill step) | `write_grant.py` (new arming helper) | The *decision* to skip the ask is a conversational-flow choice made in the skill's own step; the *authorization mechanics* (record-scoped allowlist, disarm-on-exit) must reuse `authorize_ungranted_send`'s existing single-use-grant shape, never a new mechanism |
| Implicitly-opened batch grant sizing (D-68-03) | `write_grant.plan_grant`/`envelope()` | SKILL.md (supplies `suggestion_companies`) | Pricing arithmetic already lives in `envelope()`; the skill's only job is passing the batch's own company count, exactly as `enrich-records/SKILL.md` step 5 already does |
| Pre-spend pause (D-68-05) | `watch.py` (new DI'd function) | SKILL.md (invokes it as a subprocess) | `watch.py` is the one file `test_report_sufficiency.py` exempts from the no-sleep/no-while/no-time-import rule; a real wall-clock delay run any other way either fails that test (inline in a script) or is refused by the harness (a literal Bash `sleep`) |
| Direct grant command (D-68-07) | `backend-control/SKILL.md` + `control_actions.py`/`write_grant.py` | Other skills' inline offer | The command already exists (`backend-control`'s "Opening a write grant" action, `write_grant.plan_grant`/`open_grant`); the gap is discoverability, not machinery — the fix is an inline offer at the point a batch begins, not new grant-opening code |
| Sweep of halting disclosures (D-68-09/FLOW-04) | SKILL.md prose, all 10 skills | `test_skill_sequence_coverage.py` (ratchet) | Every halt this phase converts to a statement is a prose edit; any edit that changes a documented `module.function(...)` call sequence inside a `python` fence must be registered in that test's `COVERED`/`NOT_A_PIPELINE` maps (`MAX_GRANDFATHERED = 0` — no free pass) |
| Review-triage per-record approve/reject arm | SKILL.md prose (unchanged) | — | Explicitly exempted by its own text: "This per-record ritual is unchanged by the grant" (`review-triage/SKILL.md:218`) — the decision itself (which record, which direction) is substantive, not a spend confirmation, and D-68-01's implicit-approval posture does not reach it |

## The Three Required Questions — Answered With File:Line Evidence

### Question 1 — the 5-10s pre-spend pause: which mechanism survives BOTH constraints?

**Constraint A** — `test_report_sufficiency.py::test_no_plugin_script_polls_sleeps_or_loops_on_execution_status` (`operator-claude-plugin/tests/test_report_sufficiency.py:225-242`), verified `[VERIFIED: operator-claude-plugin/tests/test_report_sufficiency.py:196-242]`:

```
193: _POLL_LOOP_ALLOWED = {"watch.py"}
196: def _plugin_source_files():
197:     return sorted(p for p in SCRIPTS_DIR.glob("*.py") if p.name not in _POLL_LOOP_ALLOWED)
200: def _imports_forbidden_module(tree, name):   # matches `import time`/`import sched`
       # and any `from time import ...` / `from time.x import ...` (submodule-prefix match)
211: def _calls_sleep(tree):                      # matches ANY ast.Call whose func name
       # (bare id OR attribute .attr) is literally "sleep" — origin-agnostic
221: def _has_while_loop(tree):                   # any ast.While anywhere in the file
225: def test_no_plugin_script_polls_sleeps_or_loops_on_execution_status():
```

`SCRIPTS_DIR.glob("*.py")` (line 197) is **non-recursive** (no `**`) and scans every top-level `.py` file directly under `operator-claude-plugin/scripts/` **except** `watch.py`. The three checks are purely syntactic (AST-walk, no import resolution), so:
- Any `import time`/`import sched` in any other script fails Constraint A regardless of whether it is used for a pause vs. a poll.
- Any function call literally named `sleep` — `time.sleep(7)`, a locally defined `def sleep(): ...` called as `sleep()`, or `foo.sleep()` — fails Constraint A in any other script.
- Any `while` loop anywhere in any other script fails Constraint A.

So a `time.sleep(7)` **cannot exist in any `scripts/*.py` file except `watch.py`.**

**Constraint B** — the harness's own Bash tool restricts a literal foreground `sleep N` shell command (documented in this session's own tool instructions: "Long leading sleep commands are blocked... Do not chain shorter sleeps to work around the block"). A SKILL.md instruction telling the executing Claude to run `sleep 7` as a bare Bash command is therefore at risk of refusal in exactly the kind of Claude Code harness this plugin is designed to run under. `[ASSUMED: this specific harness behavior generalizes to the operator's own Claude Code session]` — the operator-claude-plugin ships no evidence either way (no existing SKILL.md instructs a literal `sleep` Bash command; confirmed by `grep -rn "sleep\b" operator-claude-plugin/skills/*/SKILL.md` returning zero hits this session), so this is inferred from this coding session's environment, not observed inside the plugin's own runtime.

**The one existing pattern that satisfies both, found by reading the sole exempted file** `[VERIFIED: operator-claude-plugin/scripts/watch.py:39,292-359]`:

```
39:  import time
292: def poll_until_settled(read_once, bound_seconds, run_handle, *, now, sleep,
296:     """... `now` and `sleep` are both injected so a test drives the bound boundary
298:     from either side without a real clock ever running — production supplies
299:     `time.monotonic`/`time.sleep`, a test supplies a fake ..."""
343: def watch(config, run_handle, *, ..., now=None, sleep=None):
356:     return poll_until_settled(..., now=now or time.monotonic, sleep=sleep or time.sleep, ...)
```

`watch.py` is the one file the ratchet exempts, and it already carries the exact DI-injected-clock pattern D-68-05 needs: `now`/`sleep` as keyword-only parameters defaulting to the real `time` functions in production, overridable to a deterministic fake in a test. **Recommendation for the planner:** add a new function to `watch.py` (e.g. `pre_spend_pause(seconds=PRE_SPEND_PAUSE_SECONDS, *, sleep=None)`, `sleep=sleep or time.sleep`), with `PRE_SPEND_PAUSE_SECONDS` a module-level constant in the 5-10 range, pinned by a plain `assert 5 <= watch.PRE_SPEND_PAUSE_SECONDS <= 10` test — that test never has to actually wait, since it asserts the constant, not the sleep. The SKILL.md step then runs `python3 scripts/watch.py --pre-spend-pause` (or calls the function from a small script entrypoint already following the plugin's `python3 scripts/...` convention) as a **Bash tool invocation of a Python subprocess that happens to take 5-10 wall-clock seconds** — not a literal `sleep` shell command — which is the same shape every other bounded-wait call in this plugin already takes (e.g. `watch.recover_async_dispatch`). This is the only candidate home found that satisfies Constraint A (lives in the one exempted file, tested via DI without a real wait) and does not trip Constraint B (it is a subprocess call, not a shell `sleep`).

**If no clean answer had existed**, the honest fallback would have been: ship the constant only (declared, tested, not yet wired to a real wait) and flag the wiring itself as an open question for the operator — but a clean answer exists (`watch.py`'s existing exemption plus its existing DI pattern), so the plan should use it rather than defer.

### Question 2 — what does `write_grant.plan_grant` do TODAY on `CEILING_UNKNOWN`?

Confirmed by reading `plan_grant`'s own docstring and body `[VERIFIED: operator-claude-plugin/scripts/write_grant.py:1003-1010,1103-1118]`:

```
1003: `ceiling` (Phase 57): the `ceiling_verdict` computed against `allowance_headroom`'s
1004: live sample, attached to every returned proposal AND every refusal so an operator is
1005: never shown a batch's cost without also being shown how much of the month it would
1006: spend. `CEILING_UNKNOWN` — an unconfigured or unsampleable allowance — does NOT
1007: refuse (D-57-02: a guard that always fires is indistinguishable from a feature that
1008: is off; two of three provider balances already read `unknown` on this account, and
1009: refusing on unknown would block essentially every run today, which makes the guard
1010: indistinguishable from the feature being switched off. Only `CEILING_OVER` refuses,
              (continues:) and only when `override` is falsey.
...
1117:     ceiling = figures["ceiling"]
1118:     if ceiling["verdict"] == CEILING_OVER and not override:
              (only this branch refuses; CEILING_UNKNOWN and CEILING_OK both fall through
               to guardrail A and, absent a block there, to a returned/opened grant)
```

**`plan_grant` PROCEEDS on `CEILING_UNKNOWN` today**, exactly as the brief suspected — only `CEILING_OVER` (both figures known, and the projection strictly exceeds the sampled remainder) refuses. This is `D-57-02`'s deliberate, documented posture, not a bug: two of three provider balances already read `unknown` on this account (per the same docstring), so a refuse-on-unknown rule would block nearly every run.

**What this means for D-68-03/D-68-04 (laid out, not decided, per the brief's instruction):**

- **Option A — keep disclosure-and-proceed, make the disclosure explicit.** The implicit-open path calls `plan_grant` exactly as `enrich-records/SKILL.md` step 5 already does; on `CEILING_UNKNOWN` it opens the grant and proceeds (unchanged code path), but the **stated line** the round shows before proceeding must name the blind spot plainly — e.g. "the monthly execution ceiling could not be sampled this run, so this batch is not bounded by it; proceeding anyway, per how this backend already operates." This satisfies D-68-06 ("never proceed past a refusal" — `CEILING_UNKNOWN` was never a refusal) and is consistent with D-68-04's framing that Phase 68 states the unattended intent while Phase 67 does the formal gate-opening — the CEILING_UNKNOWN behavior itself is `write_grant.py`'s existing, already-shipped contract, not something Phase 68 is choosing to loosen.
- **Option B — Phase-68-only fence: refuse to implicitly open on `CEILING_UNKNOWN`.** Add a **skill-level** check (never inside `write_grant.py`, which D-68-04 explicitly reserves for Phase 67) that declines the *implicit* open specifically — falling back to the old two-phase ask — when `ceiling["verdict"] == CEILING_UNKNOWN`, while leaving the *explicit* grant path (the one `enrich-records`/`enrich-before-ingest` already use, where the operator sees the figures and says yes) completely unchanged. This is more conservative and narrower than Option A but adds a special-case branch that the explicit-grant path does not have, which is itself a new asymmetry a future reader has to understand.

The research does not adjudicate between A and B — D-68-04 hands `CEILING_UNKNOWN`'s *formal* gate-opening semantics to Phase 67, and both options above are consistent readings of "Phase 68 states the unattended intent" against that boundary. The planner/discuss-phase should put this choice to the operator as an open question, framed exactly as above, because it changes user-visible behavior (A: implicit grants open under an unsampled ceiling with disclosure; B: they silently fall back to the old ask under that one condition).

### Question 3 — is the implicit-open path unreachable from the headless/cron lane?

Confirmed by reading the actual import list `[VERIFIED: operator-claude-plugin/scripts/scheduled_arm.py:74-82]`:

```
74: import requests
76: import chunking
77: import config_gate
78: import enrichment
79: import executions_client
80: import n8n_arming
81: from report import _node_output_items, _run_data
82: from sweep_read import MAINTENANCE_WORKFLOW_NAME
```

**`scheduled_arm.py` imports no `write_grant` and no module that reads a grant envelope.** Cross-checked with a repo-wide grep `[VERIFIED: grep -rln "write_grant" operator-claude-plugin/scripts/*.py]`, which lists 12 files (`chunking.py`, `config_gate.py`, `init_check.py`, `measure_dispatch.py`, `n8n_arming.py`, `n8n_read.py`, `remainder_queue.py`, `review_decision.py`, `run_report.py`, `run_state.py`, `suggest_contacts.py`, `write_grant.py` itself) — `scheduled_arm.py` is not among them. The dependency direction is also one-way: `write_grant.py` imports `chunking` (confirmed among the same 12), never the reverse, so there is no transitive path either.

**No existing test pins this boundary specifically for `scheduled_arm.py`.** `grep`-checked this session: no `test_*.py` asserts "`scheduled_arm.py` never imports `write_grant`" or "the headless lane cannot open a grant." `test_scheduled_arm.py` exists (25.7K) but its content was not found to reference `write_grant` in this pass. **Recommendation:** the plan should add exactly this — a small structural test (AST-walk `scheduled_arm.py`'s own imports, or a plain `import ast; assert "write_grant" not in {name for the module's own import names}`) mirroring the style `test_report_sufficiency.py` already uses for its own import-boundary checks — so D-68-04's "until 67 ships, unattended keeps today's path" is pinned by code, not only true by absence.

## Grant Sizing (D-68-03) — the Exact Existing Call to Reuse

`agreed_cap`/`CapRefused` require nothing new (`[VERIFIED: operator-claude-plugin/scripts/suggest_contacts.py:420-464]`, quoted): `agreed_cap` reads `grant_figures["suggestion_allowance"]["priced_cap"]` and raises `CapRefused` when that key is missing/non-positive, when `chosen_cap` is not a positive int, or when `chosen_cap > priced_cap`. It never touches `write_grant` and needs no import of it (confirmed by its own docstring: "this module gains no `write_grant` import to compute it").

`write_grant.envelope()`/`plan_grant()` already have the exact keyword arguments the implicit-open path needs (`[VERIFIED: operator-claude-plugin/scripts/write_grant.py:415-447,500-523,962-965,1096-1101]`):

```
415: def envelope(config, *, object_type, record_ids, record_domains, providers,
     ...      transport=None, today=None, headroom=None,
     ...      suggestion_companies=None, suggestion_cap=None):
438: """`suggestion_companies=None` (default, D-62-11): the whole suggestion-allowance
439: branch is skipped ... A non-negative int prices a suggestion round's worst-case
     ...  ceiling (`cost_guard.suggestion_line`) at `suggestion_cap` (or `PRICED_CAP`
443: when omitted — the sitting has not chosen a cap yet at grant-open) ..."""
```

`enrich-records/SKILL.md` step 5 (`[VERIFIED: operator-claude-plugin/skills/enrich-records/SKILL.md:197-209]`) already threads this for its *explicit* grant path: `write_grant.plan_grant(config, lanes=[...], object_type="companies", ...)` "also carries `suggestion_companies=<this batch's own company count>`, leaving `suggestion_cap` unset so the envelope prices the suggestion round's worst-case allowance at `PRICED_CAP` (3 ...)". The implicit-open path Phase 68 introduces should call `plan_grant` **the identical way**, with `suggestion_companies` set from the batch's own company count wherever `suggest-contacts`/`enrich-records`/`enrich-before-ingest` open a grant implicitly — this is a copy-the-existing-call situation, not new arithmetic. `PRICED_CAP = 3` (`operator-claude-plugin/scripts/write_grant.py:154`) is the top of D-62-12's 2-to-3 band, already the default used everywhere else.

## The Direct Grant Command (D-68-07)

The command **already exists** — `backend-control/SKILL.md`'s "Opening a write grant" action (`[VERIFIED: operator-claude-plugin/skills/backend-control/SKILL.md:95-109]`, quoted):

```
95: **Opening a write grant** — the same shape one step larger: one action, one confirmation,
96: for a whole named batch instead of one send. `write_grant.plan_grant(...)` composes the
97: proposal and `write_grant.open_grant(proposal, "yes", config)` opens it; only the exact
98: string `yes` proceeds, exactly as `execute_action` does. Show the operator the envelope as
99: arithmetic before the yes — the record count, worst-case provider credits per provider,
...
```

So D-68-07's "direct command" is `backend-control`'s existing action, invocable today as `/operator-claude-plugin:backend-control` (or by conversational request). **The live Brisbane Roar friction was not a parsing bug in this command** — it was invoked in a *different* skill's argument string (`enrich-records`, per the phase description: `285507657175 - grant approved for session`). `enrich-records/SKILL.md`'s steps do not scan the free-text arguments of its own invocation for a grant-opening phrase; they only recognize an explicit "yes" answering their own structured ask (step 6), or an *already-open* `grant` object the conversation is tracking. There is no code that parses invocation-argument strings for intent — confirmed by grepping all skills for "grant approved" and finding zero hits outside the phase's own context/brief documents. **The gap is discoverability/ergonomics, not a broken parser**, matching the phase description's framing exactly. D-68-07's fix is: (a) offer grant-opening **inline**, at the first point a batch begins (e.g. `enrich-records` step 5, `enrich-before-ingest` step 1/5, `suggest-contacts` step 4's no-grant branch) — pointing at the same `write_grant.plan_grant`/`open_grant` call `backend-control` already uses — and (b) name that inline offer's own invocable phrase clearly enough that an operator who already knows what they want (as in Brisbane Roar) can trigger it without stumbling into the free-text-argument dead end. This needs no new script, no new function — only new SKILL.md prose plus (per Claude's Discretion) a name for the direct command, which could simply be documenting `backend-control`'s existing action more prominently at each batch skill's entry point.

## D-59-06 / FLOW-05 — Where the Revoke Semantics Are Stated Today

Four sites currently state "revoking a grant refuses the next send, not a dispatch already running" — three are near-identical restatements (not literal quotes of one another) and one is `backend-control`'s own version:

- `[VERIFIED: operator-claude-plugin/skills/contact-upload/SKILL.md:266-268]` — "Revoking a grant **refuses the next SEND** — it **does not stop a dispatch already running**, so a revoke arriving mid-dispatch still lets that send finish."
- `[VERIFIED: operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:328-330]` — "revoking the grant... **refuses the next send** — it **does not stop a dispatch already running**, so a revoke arriving mid-dispatch still lets every remaining chunk of that send go out."
- `[VERIFIED: operator-claude-plugin/skills/enrich-records/SKILL.md:234-236]` — same wording as enrich-before-ingest's, "every remaining chunk of that send go out."
- `[VERIFIED: operator-claude-plugin/skills/backend-control/SKILL.md:112-115]` — "Say plainly when it bites: it **refuses the next SEND**, and it **does not stop a dispatch already running**. At the two-record chunk ceiling a forty-record send is twenty chunks, and all twenty go out after a revoke."

None of these four is the literal string `"arms this run and nothing else"` and none is currently pinned by a shared test the way `ENRICHMENT_CONSENT`/`INGEST_CONSENT` are (see next section) — each is restated independently per skill. **FLOW-05's re-statement (once implicit consent ships) needs to touch all four sites**, sharpening each to name the concrete gap D-68-05's pause exists to shrink: the window between the round's stated line and the operator's interrupt is now a window in which spend can already have started (this is the same fact all four already state about revoke; what changes is that under implicit approval the *arming* itself, not just a later revoke, needs the same honesty).

## The Verbatim-Quote Propagation Sites (D-68-06 anchor)

`grep -rn "arms this run and nothing else\|arms this write and nothing else"` finds three sites `[VERIFIED: three grep hits, quoted above]`:

- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:290` — "arms this run and nothing else" (the enrichment-lane ask, step 5)
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:659` — "arms this write and nothing else" (the ingest-lane ask, step 7)
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md:92` — "arms this run and nothing else" — this line is itself a **cross-reference**, not a repetition: step 4 says "follow `enrich-before-ingest/SKILL.md` step 5's two-phase ask **verbatim**" and then restates its consequence, so `enrich-before-ingest`'s step 5 is the *source of truth* and `suggest-contacts` step 4 is a *pointer plus paraphrase-of-consequence*.

**These two exact phrases are pinned by a test** `[VERIFIED: operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py:53-54]`:

```python
53: ENRICHMENT_CONSENT = "arms this run and nothing else"
54: INGEST_CONSENT = "arms this write and nothing else"
```

`contact-upload/SKILL.md:246` and `enrich-records/SKILL.md:214-215` carry their **own** independent phrasing ("arms this send and nothing else") — not literal quotes of `enrich-before-ingest`, so they are not caught by this same test, but they follow the identical VOCAB-05 shape. **If D-68-01's implicit-approval branch removes or restructures the no-grant ask in `enrich-before-ingest/SKILL.md` step 5**, this changes the source-of-truth text `suggest-contacts` step 4 points at — the fix must land in `enrich-before-ingest/SKILL.md` first, then `suggest-contacts/SKILL.md`'s cross-reference, then `test_enrich_before_ingest_skill_contract.py`'s two pinned constants, **in the same commit** (this is exactly what CONTEXT.md's "Established Patterns" section already calls out).

## Test That Will Break or Need Extension When the Ask Moves

`test_enrich_before_ingest_skill_contract.py` (`[VERIFIED: read this session, lines 1-120]`) pins two structural facts that are explicitly **not** wording assertions: (1) a character-offset comparison that the enriched-preview heading (`"6. **The enriched preview"`) must precede the ingest-ask heading (`'7. **Ask for the HubSpot write,'`), and (2) that the two consents (`ENRICHMENT_CONSENT`, `INGEST_CONSENT`) never share a step number. The module's own docstring already documents that these pins were rewritten once before (VOCAB-05, 2026-08-25) when the literal arming phrases changed — the same update discipline applies again here: **if D-68-01 removes the ask from the no-grant branch, `ENRICHMENT_CONSENT`/`INGEST_CONSENT` as *pinned constants* may need to move from "the exact consent phrase" to "the exact statement phrase that replaces it," and the docstring must record why, the same way it already records D-53-05's and D-59-07/D-59-09's edits.** `test_skill_sequence_coverage.py` (`[VERIFIED: read this session, lines 1-60, 187, 411, 421-428]`) is the second, broader ratchet: it extracts every documented `module.function(...)` call sequence from every fenced ```python block in every `skills/*/SKILL.md`, and fails a NEW sequence that is neither `COVERED` (a named composition test) nor `NOT_A_PIPELINE`/`GRANDFATHERED_UNCOVERED` (a reasoned exclusion) — and **`MAX_GRANDFATHERED = 0`** (`test_skill_sequence_coverage.py:428`), so there is no free pass for a new uncovered sequence today. Any Phase 68 edit that adds or changes a `python` fence block's call chain (e.g. wiring `write_grant.plan_grant(...)` into a new implicit-open branch, or adding a `watch.pre_spend_pause(...)` call into a dispatch sequence) must be registered in one of `COVERED`/`NOT_A_PIPELINE` in the same commit, or the suite fails outright.

## Skill-by-Skill Audit (FLOW-04 / D-68-09) — Halting Disclosures Inventory

D-68-09's test, applied per line: **a statement of fact the operator cannot act on differently is not a decision point.** Genuine decision points stay: an ambiguous match, a conflict the judge could not adjudicate, a destructive/irreversible action the system cannot pick for the operator.

### `enrich-before-ingest/SKILL.md` (1001 lines) — the primary change site
| Line(s) | Text (paraphrased pointer) | Classification |
|---|---|---|
| 48-56 | "With no write grant open... this flow will ask for permission **twice**" | Statement (disclosure of what will happen) — stays as a statement either way |
| 277-296 | No-grant branch: "disarmed is the default... ask for this run... An affirmative... arms this run and nothing else" | **THE HALT D-68-01 CONVERTS.** Currently a genuine stop-and-wait; becomes state-and-proceed under D-68-01, still gated by D-68-06's refusal fence |
| 655-665 | Step 7, same shape for the ingest write: "disarmed is the default here too... ask for this write" | **Second instance of the same halt** — the two-phase ask names TWO stops (enrichment spend, then HubSpot write); both convert together under D-68-01's broad reading, since both are consent for spend/write, not a price confirmation of something already decided |
| 617-621 | "A row this table cannot confirm is HELD... shown ONCE, in the end-of-run review pass" | Report — already non-halting |
| 623-629 | End-of-run review's `approve`/`deny`/`pick`/`email:` vocabulary | **Genuine decision point** — a held row is an ambiguous or low-confidence case the system cannot resolve; stays |
| 954-1001 | Step 9's end-of-run report | Report — already non-halting (explicitly framed as "what the operator reads INSTEAD of watching the run") |

### `suggest-contacts/SKILL.md` (555 lines)
| Line(s) | Text | Classification |
|---|---|---|
| 29-51 | Step 1's "what this will and will not do" disclosure | Statement — already non-halting |
| 83-92 | Step 4: granted branch shows the price and does NOT stop; no-grant branch quotes `enrich-before-ingest` step 5 | Granted branch already correct per D-68-01/spec; no-grant branch is the same halt as above, converts together |
| 61-81 | Step 3: roles + cap, `CapRefused` refusal | **Genuine decision points, explicitly named in CONTEXT.md as staying** (D-68-02: "consent and the cap default are BOTH statements... but they can interrupt if they wish" — the cap/role *choice itself* is still an ask, only the *arming* consequence attached to it changes tone) |
| 517-555 | Step 9's report (cause table, held-row groups) | Report — already non-halting |

### `enrich-records/SKILL.md` (565 lines)
| Line(s) | Text | Classification |
|---|---|---|
| 42-44 | Step 1: "dispatch is currently disarmed for this conversation" | Statement — already non-halting ("Say this even if the operator only asked a question") |
| 98-131 | Step 2: company-domain confirmation table | **Genuine decision point** — an ambiguous/unresearched domain proposal the system cannot confidently resolve on its own; explicitly names three operator moves (accept/correct/decline) |
| 184-236 | Steps 5-6: grant-vs-no-grant ask, same two-phase shape as `enrich-before-ingest` | Same halt, converts under D-68-01 |
| 555-565 | Step 10's unconditional suggestion-round offer | **Borderline — kept as a genuine offer**, not a blocking gate: it is phrased as an offer the operator can decline in the same turn, not a required stop; D-68-09's audit should confirm this reads as "here's what's available" rather than "may I proceed" |

### `contact-upload/SKILL.md` (515 lines)
| Line(s) | Text | Classification |
|---|---|---|
| 34-47 | Step 1: "dispatch is currently disarmed"; `can_send: false` branch | Statement — already non-halting; explicitly instructs "do not ask for this send at all" when blocked |
| 124-131 | Step 2b: header-mapping "one confirmation per header" | **Genuine decision point** — an ambiguous header (e.g. `Ph.` = phone or photo) the system cannot resolve without the operator seeing sample values |
| 230-... | Step 4/5: grant-vs-no-grant ask, same shape | Same halt, converts under D-68-01 |
| 399-469 | Step 7's report, held-row manual-override offer | Report + genuine optional offer (not a required halt) |
| 471-479, 481-505 | Steps 8-9: "re-check only when asked," retry | Already non-halting/on-demand |

### `review-triage/SKILL.md` (300 lines)
| Line(s) | Text | Classification |
|---|---|---|
| 41-46 | Step 1's "accurate two-part position" | Statement — already non-halting |
| 167-181 | Step 5: "ask for a reason every time," but "if they decline... accept the decision anyway" | **Genuine decision point for the reason itself is soft** — a decline does not block; the *approve/reject* decision is what stays hard |
| 212-231 | Step 7: **"This per-record ritual is unchanged by the grant"** — explicit exemption in the skill's own text | **Genuine decision point, explicitly out of scope for D-68-01.** Quoted: "what changed underneath it is only the authority, never the act." This is the one skill where the phase brief's own architecture (grant removes spend-consent, never decision-consent) is already stated in prose — Phase 68 should not touch it, and the audit should record it as a confirmed non-change, not an oversight |

### `backend-control/SKILL.md` (146 lines)
| Line(s) | Text | Classification |
|---|---|---|
| 26-29 | "Confirm. Ask, and wait. Only an explicit yes proceeds." | **Genuine decision point** — every action here is a *structural* backend change (workflow on/off, schedule change, live-write enable), each irreversible or operationally significant in a way a batch-round price disclosure is not; D-68-01's posture is scoped to enrichment/contacts/review lane spend, not to this skill's mutations |
| 95-109 | Opening a write grant: "Then ask once." | **Genuine decision point** — this is itself the consent point D-68-01's implicit-approval design is meant to make people use MORE (via D-68-07's ergonomics), not remove |

### `backend-status/SKILL.md`, `backend-sweep/SKILL.md`, `initialize/SKILL.md`, `loss-reason-report/SKILL.md`
All four are **read-only skills with no write/spend path.** Full read this session found no halting disclosure beyond a genuine config-gate `STOP` (a terminal state when a required key is missing, not a question awaiting an answer) and `initialize/SKILL.md`'s own explicit "never guess a value" refusal. **No audit findings — no change needed.** `backend-status/SKILL.md:149-152` already states the exact posture Phase 68 wants elsewhere: "Re-check only when the operator asks... This skill does not watch the backend; it answers a question when asked."

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Record-scoped single-use authorization for an implicitly-approved send | A new "auto-armed" dispatch path | `write_grant.authorize_ungranted_send` (already builds a single-use grant scoped to exactly the send's records, discards it after) | This function already IS "arm without a standing grant, narrowly, once" — the only thing D-68-01 changes is who calls it and under what disclosure, never its own logic |
| Grant sizing for an implicit suggestion round | A second cost estimator | `write_grant.envelope(..., suggestion_companies=N)` / `cost_guard.suggestion_line` | Already measured, already dated, already tri-state about readability (`operator-claude-plugin/scripts/write_grant.py:438-446`) |
| A real wall-clock pause | `time.sleep()` inlined anywhere convenient | `watch.py`'s existing DI'd `now=`/`sleep=` pattern, extended with a new function in the one exempted file | The only path that survives both the pytest ratchet and the harness's Bash-sleep restriction |
| A direct "open a grant" command | New CLI/skill | `backend-control/SKILL.md`'s existing "Opening a write grant" action + `write_grant.plan_grant`/`open_grant` | Already built, already tested (`test_write_grant.py`, `test_control_arming.py`); the gap is prose discoverability, not code |

**Key insight:** every mechanism D-68-01/03/05/07 needs already exists in code, in a form nearly identical to what's needed — the only genuinely new artifact this phase should produce in `scripts/` is the pre-spend-pause function in `watch.py`. Everything else is: reuse an existing function under a new SKILL.md branch, and register the new call sequences with `test_skill_sequence_coverage.py`.

## Common Pitfalls

### Pitfall 1: Conflating the two stops in `suggest-contacts` step 4 (already named in the brief, restated here as a planning hazard)
**What goes wrong:** treating the no-grant branch's ask as "just a price confirmation" and removing it wholesale removes consent for provider spend and CRM writes, not a redundant disclosure.
**Why it happens:** the two branches read similarly in the SKILL.md's surface prose (both show a price).
**How to avoid:** D-68-01 already resolves this correctly (implicit approval on BOTH branches, with the interrupt window protected by D-68-05's pause) — the plan must still keep D-68-06's refusal fence (`CapRefused`, ceiling refusal) completely untouched, since "proceed unless interrupted" is explicitly never "proceed past a refusal."
**Warning signs:** any diff that touches `CapRefused`'s raise conditions, or `plan_grant`'s `CEILING_OVER` refusal branch, is out of scope for this phase and should be rejected in review.

### Pitfall 2: Registering a changed `python` fence sequence late
**What goes wrong:** editing a SKILL.md's documented call sequence (adding `write_grant.plan_grant(...)` to a previously grant-less branch, or adding `watch.pre_spend_pause(...)`) without updating `test_skill_sequence_coverage.py`'s `COVERED`/`NOT_A_PIPELINE` maps fails the suite outright, with `MAX_GRANDFATHERED = 0` giving no slack.
**Why it happens:** the ratchet is a separate file from the SKILL.md being edited, easy to forget mid-edit.
**How to avoid:** treat every task that edits a `python` fence block inside a `skills/*/SKILL.md` as requiring a paired edit to `test_skill_sequence_coverage.py` in the same task/commit.
**Warning signs:** `pytest operator-claude-plugin/tests/test_skill_sequence_coverage.py -q` failing with a message naming the skill, block line number, and call sequence.

### Pitfall 3: Wiring the pause as a literal SKILL.md-instructed Bash `sleep`
**What goes wrong:** the executing Claude either has the command refused by its own harness (silent no-op, the pause never actually happens) or, if not refused, produces a shell command indistinguishable from an idle busy-wait to anyone reading the transcript.
**Why it happens:** it looks like the simplest possible instruction to write in prose.
**How to avoid:** invoke the pause as a bounded Python subprocess call (`python3 scripts/watch.py --pre-spend-pause` or similar), per Question 1's answer above.
**Warning signs:** a SKILL.md line containing the literal string `sleep ` followed by a number, outside a fenced Python block.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The Claude Code harness restriction on foreground Bash `sleep` (observed in THIS research session's own tool instructions) generalizes to the operator's own Claude Code session running the operator-claude-plugin | Question 1 | If the operator's harness does NOT block a literal `sleep N`, a simpler SKILL.md-instructed Bash sleep becomes viable and the `watch.py` subprocess route is extra engineering, not a necessity — still the safer choice since it's also the only route that satisfies Constraint A (the pytest ratchet), which is independent of any harness behavior |
| A2 | `contact-upload/SKILL.md` and `enrich-records/SKILL.md`'s own "arms this send and nothing else" phrasing (not literally quoted from `enrich-before-ingest`) should also be brought into the D-68-01 conversion, alongside the two literally-quoted sites | Verbatim-Quote Propagation Sites | If the operator intends D-68-01 to apply ONLY to the skills explicitly named in CONTEXT.md's canonical_refs (`suggest-contacts`, `enrich-before-ingest`, `enrich-records`), this is correct as scoped; if `contact-upload`'s standalone upload flow was meant to be excluded, converting it would be an over-reach — CONTEXT.md's canonical_refs list does not name `contact-upload/SKILL.md` explicitly, so treat its independent ask as in-scope-by-analogy, not confirmed in-scope |

**If this table is empty:** N/A — see above.

## Open Questions

1. **`CEILING_UNKNOWN` at implicit-open time — Option A (proceed with explicit disclosure) vs. Option B (fall back to the old ask specifically on unknown)?**
   - What we know: `plan_grant` proceeds on `CEILING_UNKNOWN` today for the *explicit* grant path (D-57-02, unconditionally); D-68-04 reserves the *formal* fail-closed conditions for Phase 67.
   - What's unclear: whether Phase 68's *implicit*-open path should inherit that exact behavior unchanged (Option A) or add a narrower, skill-level fallback specifically for the implicit case (Option B).
   - Recommendation: put both options to the operator at discuss-phase, framed with the file:line evidence in this document; Option A is the smaller diff and the more consistent one (no new asymmetry between explicit and implicit paths), Option B is more conservative but adds a special case.

2. **Should the pre-spend pause apply per-round or per-batch when a round contains multiple companies/records?**
   - What we know: D-68-05 says "once per round." `suggest-contacts` operates over a whole batch of companies in one round; `enrich-records`/`enrich-before-ingest` likewise dispatch a whole batch under one arm.
   - What's unclear: whether "round" in D-68-05's sense means "once per SKILL.md invocation" (i.e., once total, before the FIRST credit-spending call of the whole batch) — this reading matches the brief's own wording ("precedes the first credit-spending call... once per round") and is almost certainly correct, but the planner should confirm no skill's batch spans what the operator would consider multiple separate "rounds."
   - Recommendation: treat "round" as "one SKILL.md invocation's worth of spend," i.e., the pause fires once, immediately before the first `dispatch_plan`/`dispatch.dispatch`/waterfall call in a given round — consistent across all skills touched.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python), `node --test` (n8n JS harness, unaffected by this phase) |
| Config file | none dedicated — `operator-claude-plugin/tests/conftest.py` provides fixtures (`no_durable_writes` autouse fixture, path setup) |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_suggest_contacts.py operator-claude-plugin/tests/test_skill_sequence_coverage.py operator-claude-plugin/tests/test_report_sufficiency.py operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py -q` |
| Full suite command | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (2565 passed / 5 skipped as of phase brief) plus `node --test tests/n8n/*.test.mjs` (glob form only — directory form is broken on node 24, per project memory) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FLOW-01 | A disclosure the operator cannot act on differently does not halt | unit (SKILL.md text assertions) | new test extending `test_enrich_before_ingest_skill_contract.py`'s `_normalized()` idiom | ❌ Wave 0 — extend existing file |
| FLOW-02 | No-grant two-phase ask is not silently removed; either stays or is an explicit operator-chosen implicit-consent path, recorded | unit | `test_enrich_before_ingest_skill_contract.py`'s existing structural pins (heading-order, same-step exclusion), extended for the new branch | ✅ file exists, ❌ new assertions needed |
| FLOW-03 | Opening a grant is easy enough a round doesn't fall to the per-round ask | unit + composition | `test_write_grant.py`/`test_write_grant_surface.py` (grant-open mechanics unchanged) + a new SKILL.md-prose test confirming the inline offer text exists at the right step | ✅/❌ mixed |
| FLOW-04 | Every skill swept, genuine decision points preserved | doc/audit (this RESEARCH.md's table) + `test_skill_sequence_coverage.py` (structural ratchet for any call-sequence change) | manual audit ships as this document; whether it ALSO ships as a test is Claude's Discretion per CONTEXT.md | this doc = ✅, code ratchet = ✅ already exists |
| FLOW-05 | D-59-06 revoke-refuses-next-send re-stated against implicit consent | unit (text assertion across the four sites identified above) | new test grepping all four SKILL.md files for the updated wording | ❌ Wave 0 — new small test |

### Sampling Rate
- **Per task commit:** the quick run command above (five targeted test files covering grant mechanics, suggestion caps, the no-sleep ratchet, and the SKILL.md-sequence ratchet)
- **Per wave merge:** full suite green (`.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` + `node --test tests/n8n/*.test.mjs`)
- **Phase gate:** full suite green before `/gsd-verify-work`, plus a manual read-through confirming every skill named in the audit table above reads as intended (this phase is prose-heavy; automated tests cannot catch every tone/register regression)

### Wave 0 Gaps
- [ ] A new test in `watch.py`'s own test file (or a new `test_watch.py` if none exists — check `operator-claude-plugin/tests/` for an existing `test_watch*.py` before creating one) asserting `PRE_SPEND_PAUSE_SECONDS` is in `[5, 10]` and that `pre_spend_pause(sleep=fake)` calls the injected `sleep` exactly once with that value — never a real wait in CI.
- [ ] A new structural test asserting `scheduled_arm.py` imports no `write_grant` (Question 3's recommendation) — mirrors `test_report_sufficiency.py`'s own AST-walk style.
- [ ] Extend `test_enrich_before_ingest_skill_contract.py`'s pinned constants/headings once the no-grant branch's wording changes (FLOW-01/02), in the same commit as the SKILL.md edit — per the module's own established discipline (VOCAB-05, D-59-07/09 precedent).
- [ ] Register any new/changed `python` fence call sequence in `test_skill_sequence_coverage.py`'s `COVERED`/`NOT_A_PIPELINE` maps in the same commit as the SKILL.md edit that introduces it — `MAX_GRANDFATHERED = 0` gives no slack.

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | This phase touches no auth mechanism — `webhook_secret`/`n8n_api_key` handling is unchanged |
| V3 Session Management | yes (loosely) | The "grant" IS the session-scoped authorization object (`write_grant.py:20`: "the grant is held in the conversation, for the session"). D-68-01 changes WHEN a grant is opened (implicitly vs. on explicit ask), never HOW it is scoped, disarmed, or revoked — `authorize_send`/`authorize_ungranted_send`/`armed_window` are unchanged |
| V4 Access Control | yes | `write_grant.covers()`'s record-scoped allowlist and `n8n_arming.armed_window`'s per-send narrowing are the access-control mechanism; explicitly unchanged by this phase (CONTEXT.md: "What stays exactly as it is... the per-send armed window") |
| V5 Input Validation | no new surface | No new user input is parsed by this phase beyond what already exists (an operator's yes/no, a chosen cap, a chosen role list) |
| V6 Cryptography | no | Not touched |

### Known Threat Patterns for This Domain
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A round proceeds past what the operator would have refused, because the interrupt window was too short or nonexistent | Elevation of Privilege (unauthorized spend/write) | D-68-05's real pause (5-10s) before the first credit-spending call; D-68-06's hard fence that "proceed unless interrupted" never overrides `CapRefused`/ceiling refusal |
| A pause implemented via a shell `sleep` gets silently skipped/refused by the harness, producing a round that reads as having a safety window but does not | Tampering (silent safety-control bypass) | Question 1's `watch.py`-subprocess mechanism, tested via DI so the CI suite proves the constant exists and the injected sleep is called — this doesn't prove the LIVE harness executes it, but it proves the code path is real and testable, which a bare prose instruction cannot |
| An implicitly-opened grant is sized wrong (too small — round refuses legitimate work; too large — round could spend beyond what the operator would have agreed to had they seen the number) | Tampering / Repudiation | Reuse the exact `envelope(..., suggestion_companies=N, suggestion_cap=None)` arithmetic already used by the explicit-grant path — no new pricing logic, no new place for a sizing bug to hide |
| A revoke arrives during an implicitly-approved round and the operator believes it stopped an in-flight spend | Repudiation (operator's understanding of what "interrupt" bought them is wrong) | FLOW-05's re-statement of D-59-06 at all four sites, made explicit for the implicit-consent case specifically |

## Sources

### Primary (HIGH confidence — direct `Read`/`grep` of source-of-truth files this session)
- `.planning/phases/68-state-the-price-and-keep-moving/68-CONTEXT.md` — locked decisions D-68-01..09
- `.planning/todos/pending/2026-09-04-state-the-price-and-keep-moving.md` — the brief
- `.planning/REQUIREMENTS.md` § FLOW — FLOW-01..05
- `operator-claude-plugin/scripts/write_grant.py` — `envelope`, `plan_grant`, `ceiling_verdict`, `allowance_headroom`, `CEILING_*` constants, `PRICED_CAP`
- `operator-claude-plugin/scripts/suggest_contacts.py` — `agreed_cap`, `CapRefused`
- `operator-claude-plugin/scripts/watch.py` — `poll_until_settled`, `watch`, the `_POLL_LOOP_ALLOWED` exemption target
- `operator-claude-plugin/scripts/scheduled_arm.py` — import list
- `operator-claude-plugin/scripts/cost_guard.py` — `suggestion_line`
- `operator-claude-plugin/tests/test_report_sufficiency.py` — the no-sleep/no-while/no-time-import ratchet
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` — the SKILL.md call-sequence ratchet
- `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` — `ENRICHMENT_CONSENT`/`INGEST_CONSENT` pins
- All 10 `operator-claude-plugin/skills/*/SKILL.md` files, read in full this session

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` — decision history (D-61-08, D-59-06, D-62-11/12) cross-referenced against CONTEXT.md's own citations
- `.planning/ROADMAP.md` § Standing facts — "the first live unattended, credit-spending batch has NOT run"

### Tertiary (LOW confidence / assumed)
- The Claude Code harness's Bash-`sleep` restriction generalizing to the operator's own session (A1 in Assumptions Log)

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — no new library/package; this phase is a prose+existing-code composition exercise
- Architecture: HIGH — every mechanism cited was read directly this session with line numbers
- Pitfalls: HIGH for the two code-ratchet pitfalls (directly observed test behavior); MEDIUM for the harness-Bash-sleep pitfall (partially assumed, A1)

**Research date:** 2026-09-07
**Valid until:** This is an in-repo-only research pass with no external dependency; valid until the next commit touches any of the primary source files listed above (check `git log` on those paths before reusing this document for a re-plan).
