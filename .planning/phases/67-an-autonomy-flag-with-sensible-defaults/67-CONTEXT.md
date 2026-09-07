# Phase 67: An autonomy flag with sensible defaults - Context

**Gathered:** 2026-09-05
**Status:** Ready for planning

<domain>
## Phase Boundary

The operator can let functions run without per-step intervention, deliberately and per tier.
The safety scaffolding already exists — Phase 57 built per-run ceilings, refusal-before-start
and post-run proof; Phase 61 built run scope, resume and held rows. **This is the missing
switch, not missing safety.**

**In scope:** the per-tier autonomy setting, its defaults, its fail-closed conditions, the
formal opening of D-61-08's unattended gate (handed here by Phase 68's D-68-04), and making
the end-of-run report mandatory under autonomy.

**Out of scope:** building any new guard rail (they exist), chunk-granular revocation
(D-67-07), and the disclosure audit itself (Phase 68).

</domain>

<decisions>
## The tiers

- **D-67-01: Three tiers, all three autonomous by default.** "All functions" is not one
  decision — the functions differ in kind:
  - **read-only** — `backend-status`, review-queue reads, `loss-reason-report`. Trivially
    safe; arguably should never have prompted.
  - **spend-no-write** — the match and propose lanes. Bounded by provider credit, reversible
    in effect.
  - **write** — ingest, enrich-and-write, review-decision apply. Irreversible against the CRM.
  The operator chose autonomy on for all three. Naming the tiers is still required — they get
  separate settings keys and separate fail-closed behaviour even when their default values
  agree today.

- **D-67-02: The flag is a DEFAULT-SETTER, not a third authority gate.** Both existing gates
  remain required and unchanged:
  - `allow_write_grants` (JSON boolean in `operator.local.json`) authorises the INTERACTIVE
    path only. It is the repo's deliberate first exception to "authority gates are environment
    variables", because an operator in Claude Desktop cannot set a shell variable.
  - `ALLOW_N8N_ARM` (environment variable, exact string `"true"`) remains the SOLE authority
    for the headless and cron paths. Operator-only, per-shell, **never set by Claude.**
  The flag decides only whether an already-authorised action proceeds without asking.
  **Considered and rejected: a third self-authorising gate.** The reasons, on the record:
  1. It would move unattended write authority into a JSON file the assistant can write.
     `write_grant.py`'s own header states the split is "three-way on purpose" and that the
     probe, deploy and headless arm gates stay environment-gated; `ALLOW_N8N_ARM` being
     unsettable from inside a session is the property that would be lost.
  2. Persistence asymmetry — an env var dies with the shell; a settings key survives reboots,
     machine copies, backups and plugin installs, so autonomy would persist into contexts
     never intended.
  3. It would collapse two blast radii into one: interactive (operator present, can interrupt
     — the whole containment Phase 68 rests on) and headless (nobody present).
  4. It cuts against the pinned `DISPATCH_FLAGS` / `REVIEW_FLAGS` separation in
     `n8n_arming.py`, where arming one deliberately never grants the other.
  What a third gate would have bought was one shell line of setup, once — the recurring
  friction was per-round asking, which Phase 68 already removed.
  — **Reversibility:** one-way in the direction NOT taken — had the third gate shipped,
  reinstating the env-var-only headless authority would mean revoking a capability operators
  had come to rely on.

## Defaults and upgrade

- **D-67-03: The tier defaults apply on update.** An existing install moves to the new
  defaults rather than keeping current behaviour. The brief recommended the opposite (default
  to current behaviour so an update never silently turns autonomy on); the operator was shown
  that trade-off — fewest steps for them, a silent write-posture change for any other operator
  taking the update — and chose the new defaults.
  **The plan must handle the consequence, not just the setting:** the update's release notes
  and the plugin's first-run output must state the changed posture plainly, because the
  setting file will not be the thing that tells anyone.
  — **Reversibility:** one-way — an update that changes write posture on other operators'
  installs cannot be un-shipped.

- **D-67-04: This phase formally opens D-61-08's unattended gate.** Handed here by Phase
  68's D-68-04. It must be presented and implemented as **a deliberate reversal of a recorded
  decision**, never as a config convenience that happens to imply one. The record: at Phase
  57-05's Task 4 gate the operator selected option-a — a small, operator-SUPERVISED first live
  batch — with option B (authorising the unattended credit-spending batch) on the table and
  not taken. The standing fact today is that nothing is armed and the first live unattended
  credit-spending batch has never run.
  — **Reversibility:** one-way — it crosses a line the project has deliberately not crossed.

## Fails closed on

- **D-67-05: Three conditions, each a refusal, in code.** An autonomy default must never treat
  an unreadable state as permission:
  1. **`CEILING_UNKNOWN`** — a hard precondition already on the record: authorising the first
     unattended credit-spending batch is forbidden while the ceiling sample is unsampleable.
     An unreadable ceiling is not headroom.
  2. **An unread provider balance** — D-57-02's tri-state honesty requirement: unreadable is
     `unknown`, never headroom.
  3. **A missing allowance key** — Phase 57 found an absent allowance key silently disabled
     two guards. Absent is not permissive.

- **D-67-06: The end-of-run report becomes MANDATORY when the flag is on.** Under autonomy it
  is the only account of what happened. Conventional today; required here.

- **D-67-07: The per-run ceiling is sufficient containment for revocation.** Revoking refuses
  the NEXT send while a dispatch already running finishes its remaining chunks (D-59-06). With
  nobody watching, that window is unobserved; the operator accepted the ceiling as the bound.
  Chunk-granular revocation is NOT built — the same conclusion D-59-06 reached with its cost
  stated. Named plainly so a later reader does not mistake it for an oversight.

- **D-67-08: RUN-05 is still incomplete and the flag must account for it.** 57-03's
  affordable-subset split offer was never built, so a batch exceeding the ceiling can today
  only be refused whole, never trimmed to fit. Under supervision that is a conversation;
  unattended it is a silent no-op unless the flag handles it. Decide in planning whether the
  autonomous path refuses loudly into the mandatory report (D-67-06) or whether RUN-05 must
  land first.

## Planning-time rulings (operator, 2026-09-07, put by plan-phase after 67-RESEARCH.md)

- **D-67-09: REVERSES D-67-05 and AUTO-03. Autonomy ON discloses an unknown state and
  PROCEEDS.** On `CEILING_UNKNOWN` (the n8n monthly execution allowance could not be
  sampled), an unread provider balance, or a missing `n8n_monthly_execution_allowance` key,
  an autonomous spend/write round states the unknown in the pre-spend line and continues —
  identical to Phase 68's attended path (D-68-10, D-57-02). It does NOT refuse. The bounds
  that remain are `CEILING_OVER` (refuses only when sampled) and `CapRefused`. Reason, on
  the record: two of three provider balances already read `unknown` on this account
  (`write_grant.py` ~1006), so refuse-on-unknown would block essentially every autonomous
  round. Offered and not taken: restore D-67-05 (refuse on all three); a split (refuse only
  on the missing key). Operator reaffirmed after the reversal was named explicitly.
  — **Reversibility:** one-way in effect — credits an unattended round spends under an
  unsampled ceiling are not recoverable. Reinstating a refusal later is a one-line code change.

- **D-67-10: D-67-03 governs; REQUIREMENTS.md AUTO-02 is rewritten to match.** Defaults
  apply on update; an absent autonomy key reads as ON. AUTO-02 becomes "a plugin update that
  changes write posture states it plainly (release notes + first-round notice); it never
  changes it silently". AUTO-02's 2026-09-04 text predated the 2026-09-05 discuss-phase.

- **D-67-11: The mandatory end-of-run report (D-67-06) covers the four batch skills.**
  `contact-upload` and `suggest-contacts` gain `run_report.build_run_report`/`record_audit`;
  `enrich-before-ingest` and `enrich-records` already call it. `review-triage` keeps its
  per-record ritual (no batch report); `backend-control` is out of scope.

- **D-67-12 (orchestrator, from CONTEXT's discretion note): `backend-control` is in no
  tier.** Its arm/deploy/structural mutations stay confirm-and-wait regardless of any
  autonomy key — they are D-68-09 genuine decision points and are not in D-67-01's write list.

- **D-67-13 (orchestrator, from CONTEXT's discretion note): RUN-05 is a documented
  limitation, not a dependency.** A `CEILING_OVER` batch is still refused whole; under
  autonomy that refusal lands loudly in the mandatory end-of-run report (D-67-06), never a
  silent no-op. The affordable-subset split stays unbuilt.

- **Vocabulary (binding, from Phase 68-01):** the substring "tier" is banned in every
  operator-facing SKILL.md body (`test_report_enrichment.py` D-10b). Say "autonomy levels";
  key names `read_only` / `spend_no_write` / `write` carry no banned substring.

### Claude's Discretion

- The settings keys' names and nesting in `operator.local.json`.
- Whether the three tiers are three keys or one key with three values.
- How the changed-posture notice is surfaced on update (release notes, first-run banner, or
  both — D-67-03).
- Whether RUN-05 is a dependency or a documented limitation (D-67-08).

### Folded Todos

- **`2026-09-04-autonomy-flag-with-sensible-defaults.md`** — this phase in full.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The brief
- `.planning/todos/pending/2026-09-04-autonomy-flag-with-sensible-defaults.md` — read "What
  this flag would REVERSE", the two authority gates, the D-59-06 section, and "'All functions'
  is not one decision".
- `.planning/ROADMAP.md` § "Phase 67", § "Binding on all six", and § Standing facts.
- `.planning/milestones/v1.2-REQUIREMENTS.md` — `AUTO-04`.

### The decision being reversed
- D-61-08 and the 57-05 Task 4 gate (operator chose option-a, supervised, not unattended).
  `.planning/STATE.md` § Decisions; the v1.1 Phase 57 and 61 records. **Read before
  implementing D-67-04.**

### The two gates that must NOT be collapsed
- `operator-claude-plugin/scripts/write_grant.py` — the module header states the three-way
  split and why `allow_write_grants` became a settings key (Claude Desktop cannot set a shell
  variable; G-2, live client UAT 2026-08-25). Also `plan_grant`, `allowance_headroom`,
  `ceiling_verdict`, `record_audit`, `build_run_report`, `close_grant`.
- `operator-claude-plugin/scripts/n8n_arming.py` — `ARM_ENV_VAR = "ALLOW_N8N_ARM"`,
  `DISPATCH_FLAGS` / `REVIEW_FLAGS` (separate on purpose, pinned by
  `test_control_arming.py::test_review_writes_is_not_touched_by_a_dispatch_disarm`),
  `armed_window`, and the deliberately-ungated disarm.
- `operator-claude-plugin/scripts/scheduled_arm.py` — still gated on `ALLOW_N8N_ARM`; the cron
  path this phase must not loosen.
- `operator-claude-plugin/scripts/config_gate.py` — `WRITE_GRANT_SETTINGS_KEY`,
  `CAPABILITY_KEYS`, and the capability-versus-authorisation distinction D-53-01 keeps.

### The scaffolding that already exists
- `run_manifest.py`, `run_state.py`, `held_queue.py`, `confidence.py` — run scope, resume,
  held rows, confidence verdicts.
- Phase 57's ceilings, refusal-before-start and post-run proof.

### Cross-phase
- `.planning/phases/68-.../68-CONTEXT.md` — D-68-04 hands the formal gate-opening here;
  D-68-01/-05 already made approval implicit with a 5–10s pre-spend pause. **Phase 68 lands
  first**; this phase inherits its posture rather than re-deciding it.
- `.planning/phases/69-.../69-CONTEXT.md` — a drained `send` is a normal send and clears the
  same gates. Autonomy does not exempt it.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `write_grant.allowance_headroom` / `ceiling_verdict` — already produce the OK/OVER/UNKNOWN
  tri-state D-67-05 fails closed on. No new verdict logic.
- `write_grant.plan_grant` — already refuses a CEILING_OVER batch before anything is armed,
  carrying the refusal arithmetic and an override path.
- `write_grant.record_audit` / `build_run_report` — already the end-of-run report joining five
  durable stores. D-67-06 makes it mandatory; it does not build it.
- `config_gate.py` — already the settings-file reader with a capability/authority split. The
  autonomy keys belong on the capability side, not with `WRITE_GRANT_SETTINGS_KEY`.

### Established Patterns
- **Authority gates are environment variables compared against the exact string `"true"`**
  (D-34, D-53-01), with `allow_write_grants` as the ONE documented exception and its reason
  recorded. D-67-02 adds no second exception.
- **Absent is never permissive.** Phase 57's missing-allowance-key finding; D-57-02's
  tri-state honesty. Both are D-67-05.
- **A refusal lives in code, not prose** — v1.2's binding rule.
- **Arming one authority never grants another** — `DISPATCH_FLAGS` / `REVIEW_FLAGS`, pinned.
- **Plugin scripts are pure and contain no `while` loop.**

### Integration Points
- `skills/*/SKILL.md` — every skill's ask-or-proceed behaviour reads the tier setting. This
  is the same prose surface Phase 68's audit rewrites, which is why **67 runs after 68**.
- `scheduled_arm.py` / the cron path — inherits the write tier's default but keeps
  `ALLOW_N8N_ARM` as its authority (D-67-02).
- The mandatory end-of-run report (D-67-06) is the observability that replaces a watching
  operator.

</code_context>

<specifics>
## Specific Ideas

- The operator's request, verbatim (2026-09-04): *"Separately it was suggested to set an
  autonomy flag with sensible defaults, so all functions can be run autonomously without human
  intervention to make enrichment frictionless."*
- The brief's own framing, adopted: this is the missing switch, not missing safety. Phase 57
  and Phase 61 already built what an unattended run needs to be defensible.
- The third-gate question was raised by the operator directly ("wouldn't that be easier to
  manage and more frictionless?") and answered on evidence: the recurring friction was
  per-round asking, removed by Phase 68; the gates are one-time setup. D-67-02 records both
  the question and the four risks that decided it.

</specifics>

<deferred>
## Deferred Ideas

- **Chunk-granular revocation** — D-67-07. Declined again, same reasoning and cost as D-59-06.
- **RUN-05's affordable-subset split offer** — D-67-08. Either a dependency or a documented
  limitation; planning decides.
- **A third self-authorising gate** — rejected in D-67-02 with reasons. Revisit only if the
  Claude-can't-write property is deliberately given up, which is its own decision.
- **Per-skill autonomy overrides** (finer than the three tiers) — not asked for; the tiers are
  the stated granularity.

### Reviewed Todos (not folded)
- `2026-09-04-phone-is-never-chased-only-accepted.md` — Phase 66. Same frictionless goal on
  the data-completeness axis; no shared files.
- `2026-09-04-state-the-price-and-keep-moving.md` — Phase 68, which lands first.

</deferred>

---

*Phase: 67-an-autonomy-flag-with-sensible-defaults*
*Context gathered: 2026-09-05*
