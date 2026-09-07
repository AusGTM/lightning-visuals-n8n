# Phase 68: State the price and keep moving - Context

**Gathered:** 2026-09-05
**Status:** Ready for planning

<domain>
## Phase Boundary

A round stops halting on statements the operator cannot act on differently. Approval becomes
implicit — the round states what it will do and proceeds unless interrupted — and every other
disclosure that has drifted into a blocking question is converted back into a statement.

**In scope:** the no-grant branch's ask, the pre-spend pause that makes an interrupt real,
frictionless grant opening, and a sweep of every disclosure across the operator skills.

**Out of scope:** the ceilings themselves (Phase 57's, unchanged and still refusals in code),
the autonomy tier switch and its fail-closed conditions (Phase 67 — see D-68-04), and every
`min_confidence` / `fill_blank_only` / drop path (SAFE-01..05).

</domain>

<decisions>
## Approval

- **D-68-01: The BROAD reading. Approval is implicit on the no-grant branch too.** State what
  the round will do, then proceed unless interrupted. The brief offered a narrow reading
  (keep the ask, make grants easy) and recommended it; the operator chose broad, having been
  shown that the no-grant ask is consent for provider spend and CRM writes rather than a
  price confirmation.
  — **Reversibility:** one-way — this is a consent posture on a live, credit-spending, CRM-
  writing system. Reinstating the ask later is easy in code; the spend that happened without
  one is not recoverable.

- **D-68-02: Consent and the cap default are BOTH statements.** Operator ruling: "I consider
  consent and cap default as statements that an operator is likely to not act on differently,
  but they can interrupt if they wish." Neither is a question in the default path.

- **D-68-03: Proceeding IMPLICITLY OPENS a grant, and the round states it.** Not a
  grant-less run. Mechanically required, not stylistic: `suggest_contacts.agreed_cap` raises
  `CapRefused` — "never clamps, never defaults" — when the grant's figures never priced a
  suggestion allowance, so on a grant-less branch there is no `priced_cap` for a stated cap
  default to be a default OF. Opening the grant mints the envelope, so `priced_cap` exists,
  `agreed_cap` works unchanged, and the line the operator reads is a real ceiling their
  interrupt lands against. Rejected: a separate config ceiling — a second ceiling source
  `agreed_cap` does not know about.

- **D-68-04: This phase STATES the unattended intent; Phase 67 opens D-61-08 formally.**
  The operator chose "same behaviour everywhere" — implicit approval regardless of session
  type — which reverses D-61-08, whose unattended gate the v1.2 roadmap binds to an explicit
  ask. That choice is recorded here as made. The gate-opening itself — the tiers, and the
  fail-closed conditions on `CEILING_UNKNOWN`, an unread provider balance and a missing
  allowance key — lands in Phase 67, which exists for exactly that. **Until 67 ships,
  unattended keeps today's path**; there is no gap and no silent widening.
  Named honestly: in an unattended run the D-68-05 pause protects nothing, because nobody is
  there to interrupt. Containment there is the ceiling and the refusals alone — which is
  precisely what Phase 57 built.
  — **Reversibility:** one-way — reverses a recorded operator decision (57-05 Task 4 gate,
  D-61-08).

## What makes an interrupt real

- **D-68-05: The disclosure precedes the first credit-spending call by a real pause of 5–10
  seconds, once per round.** A fixed constant, pinned by test — not a question, not a prompt.
  This answers the brief's D-59-06 question directly: an interrupt refuses the NEXT send while
  a running dispatch finishes its chunks, so under implicit approval the window between the
  operator reading the line and reacting is a window in which spend could already have
  started. The pause makes that window exist. Rejected: the ceiling alone as containment
  (a fast round can complete before the operator reacts), and a config-tunable interval
  (a constant is one fewer thing to get wrong).

- **D-68-06: "Proceed unless interrupted" NEVER becomes "proceed past a refusal."** The
  brief's hard constraint, kept verbatim. `CapRefused` (a cap above the grant's priced cap)
  and the per-run ceiling refusal stay in code, not prose. An interrupt is a courtesy; a
  refusal is a fence.

## Grant ergonomics

- **D-68-07: Grant opening is offered inline AND invocable directly.** Inline at the first
  point of a batch so it is discoverable by an operator who did not know they wanted one;
  a direct command for an operator who does. The live friction this fixes: the Brisbane Roar
  round was invoked as `285507657175 - grant approved for session` and the session correctly
  reported no machine grant open — a phrase in an argument string is not a grant — so the
  operator intended a session grant, did not get one, and hit the per-round ask a grant
  exists to avoid. `allow_write_grants` is already `true` in this operator's config and the
  envelope already carries `figures["suggestion_allowance"]`; the machinery exists, the
  ergonomics do not.

- **D-68-08: One consent point per BATCH.** Every round inside an open grant takes the
  already-silent branch, which is what `suggest-contacts/SKILL.md` step 4's granted branch
  already specifies.

## The audit

- **D-68-09: Sweep every operator skill for disclosures that halt but should not.** The test:
  a statement of fact the operator cannot act on differently is not a decision point, and
  each one costs a round trip. Converted to statements: price/ceiling lines on a granted
  round, "backend is disarmed" status statements, provenance and source summaries, post-run
  reports — plus, per D-68-02, consent and the cap default. What stays a genuine question:
  anything where a different answer changes what happens and the system cannot pick — an
  ambiguous match, a conflict the judge could not adjudicate, a destructive or irreversible
  action.

## Planning-time rulings (operator, 2026-09-07, put by plan-phase after 68-RESEARCH.md)

- **D-68-10: An implicit open on `CEILING_UNKNOWN` PROCEEDS, with the blind spot disclosed.**
  The implicit-open path inherits the explicit path's behaviour unchanged (`plan_grant`
  refuses only `CEILING_OVER`; `CEILING_UNKNOWN` proceeds with the blind spot disclosed,
  D-57-02, `write_grant.py` ~1117). The pre-spend line MUST state the unsampled ceiling in
  words. No Phase-68-only fence; fail-closed on `CEILING_UNKNOWN` stays Phase 67's (D-68-04).
  Option B (fall back to the old ask on unknown) was offered and not taken.

- **D-68-11: The pre-spend pause fires ONCE per SKILL.md invocation.** One pause, immediately
  before the first credit-spending call of the whole batch, consistent across every skill
  touched. Per-company / per-record pauses were offered and not taken.

### Claude's Discretion

- The exact pause constant inside 5–10s, and where it lives.
- The stated line's wording and how the implicitly-opened grant's size is chosen from the
  batch (companies × cap × priced per-company figure is the obvious derivation).
- The direct grant command's name.
- Whether the audit's inventory ships as a doc, a test, or both.

### Folded Todos

- **`2026-09-04-state-the-price-and-keep-moving.md`** — this phase in full, including its
  "Audit to run either way" list. Its recommended narrow reading was put to the operator and
  the broad reading was chosen (D-68-01).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The brief
- `.planning/todos/pending/2026-09-04-state-the-price-and-keep-moving.md` — read "There are
  TWO stops in that flow", the two readings, the two properties that must survive under
  reading (2), and the audit list.
- `.planning/ROADMAP.md` § "Phase 68" and § "Binding on all six" (SAFE-01..05).
- `.planning/milestones/v1.2-REQUIREMENTS.md`

### The decision this phase reverses
- D-61-08's unattended gate, and the 57-05 Task 4 gate where the operator chose a small
  SUPERVISED first live batch, explicitly not the unattended one. `.planning/STATE.md`
  § Decisions and the v1.1 phase 57 / 61 records. **Read before implementing D-68-04.**
- `.planning/ROADMAP.md` § Standing facts — "the first live unattended, credit-spending batch
  has NOT run, and nothing is armed."

### The code this phase changes
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` step 4 — the two-branch ask. The
  granted branch already specifies disclosure-without-stop; the no-grant branch is what moves.
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` step 5 — the two-phase ask
  quoted verbatim by the others. Change it here and the quotes must move with it.
- `operator-claude-plugin/skills/enrich-records/SKILL.md`
- `operator-claude-plugin/scripts/write_grant.py` — `envelope()` and its
  `figures["suggestion_allowance"]["line"]` / `["priced_cap"]`. D-68-03's implicit open.
- `operator-claude-plugin/scripts/suggest_contacts.py` — `agreed_cap` and `CapRefused`
  (unchanged in behaviour; D-68-03 exists so it keeps working).

### Fences that must survive
- Phase 57's per-run ceilings, refusal-before-start and post-run proof.
- D-59-06 — an interrupt refuses the NEXT send; a running dispatch finishes its chunks.
  D-68-05 is the direct answer to the question this raises.
- `operator-claude-plugin/scripts/n8n_arming.py` and `ALLOW_N8N_ARM` — unchanged for the
  headless path (this is 67's, per D-68-04).

### Cross-phase
- `.planning/todos/pending/2026-09-04-autonomy-flag-with-sensible-defaults.md` — Phase 67.
  D-68-04 hands it the formal gate-opening plus the fail-closed conditions.
- `.planning/phases/69-.../69-CONTEXT.md` — the end-of-run batch report is a report, and
  D-68-09's rule applies to it: it states, it does not halt. The drain's own actions ARE
  decision points and stay questions.
- `.planning/phases/66-.../66-CONTEXT.md` — D-66-06's completeness line is a statement too.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `write_grant.envelope()` — already carries `figures["suggestion_allowance"]` with both a
  human `line` and a machine `priced_cap`. D-68-03 opens one; it does not invent a figure.
- `suggest_contacts.agreed_cap` / `CapRefused` — already the promoted-to-code version of a
  prose cap rule (D-62-11/-12), and already refuses rather than clamping. D-68-06 keeps it.
- `suggest-contacts/SKILL.md` step 4's GRANTED branch — the requested behaviour is already the
  spec there. The phase extends an existing pattern rather than inventing one.
- `allow_write_grants: true` already set in this operator's config.

### Established Patterns
- **Two-phase ask, quoted verbatim across skills.** `enrich-before-ingest/SKILL.md` step 5 is
  the source; the others quote it. A change lands once and propagates by quotation — check
  every quoting site in the same commit.
- **A refusal is terminal and lives in code.** D-5sd-04's fence principle, `CapRefused`,
  `eligible_after_ladder`. Prose never overrides one.
- **Ceilings are refusals in code, never prose** (v1.2 binding rule).
- **Plugin scripts are pure and contain no `while` loop**
  (`tests/test_report_sufficiency.py::_has_while_loop`).

### Integration Points
- Every operator skill's disclosure surface is in scope for the audit — this is the phase with
  the widest `SKILL.md` blast radius, which is why 68 runs before 67 (whose
  `skills/*/SKILL.md` changes would otherwise rewrite the same prose twice) and after 64/65
  (which change `suggest-contacts/SKILL.md`'s round mechanics).
- Phase 69's batch report and Phase 66's completeness line both land under D-68-09's rule.

</code_context>

<specifics>
## Specific Ideas

- The operator's request, verbatim (2026-09-04, after the Roma round halted at its price
  line): *"I also want to stop Claude from stopping and requiring approval when disclosing
  price. Just state and keep moving (set this to default behaviour even without autonomy
  flag), approval is default, the operator can interrupt if they wish."*
- And on the audit's boundary: *"I consider consent and cap default as statements that an
  operator is likely to not act on differently, but they can interrupt if they wish."*
- The live friction: `285507657175 - grant approved for session` in an argument string
  produced no machine grant, correctly. The operator's intent and the system's state diverged
  silently, and the cost was a per-round ask.

</specifics>

<deferred>
## Deferred Ideas

- **The autonomy tiers and their fail-closed conditions** — Phase 67, per D-68-04.
- **Whether the pre-spend pause should scale with the round's priced ceiling** — a bigger
  spend arguably deserves a longer window. Not decided; the constant ships first.
- **Retiring the explicit ask entirely from the codebase** — D-68-01 makes it non-default, not
  absent. Removal is a separate decision.

### Reviewed Todos (not folded)
- `2026-09-04-autonomy-flag-with-sensible-defaults.md` — Phase 67.
- `2026-09-04-skill-step8-routes-holds-into-a-queue-that-refuses-them.md` — Phase 69.

</deferred>

---

*Phase: 68-state-the-price-and-keep-moving*
*Context gathered: 2026-09-05*
