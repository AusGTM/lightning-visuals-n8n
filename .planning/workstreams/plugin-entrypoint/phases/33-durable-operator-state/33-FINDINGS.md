# 33-FINDINGS — durable operator state, real-migration observation (plan 33-04, RB-10)

**Status: PENDING OBSERVATION.** This file records what the phase knows going in and what
question RB-10 exists to answer. It does not yet contain a live result — the migration this
gate observes happens on the operator's own machine, against the operator's own installed
plugin and live `webhook_secret`/`n8n_api_key`, and the executor that wrote 33-04 does not
perform it. Replace this section with the observed outcome once RB-10 is walked; do not delete
the question below when that happens.

---

## The open question, verbatim (33-RESEARCH.md, Open Questions #1)

> **Does the Bash-tool "sensitive location" permission prompt (Pitfall 1) actually fire for
> this plugin's migration write, on this operator's Claude Code version?**
> - What we know: A GitHub issue reports it does, for writes into
>   `~/.claude/plugins/data/<id>/`, closed as "not planned" by the upstream project.
> - What's unclear: Whether it reproduces here, whether it blocks (hangs pending
>   confirmation) or is skippable, and whether it differs between an interactive session and
>   any other invocation path this plugin uses.
> - Recommendation: Add a live-check step to this phase's own execution/verification —
>   consistent with this project's established pattern of resolving Claude-Code-host
>   uncertainties via a runbook-style observed check (RB-1 through RB-9) rather than further
>   research. Not a blocker for planning or building the code — the degrade-never-refuse
>   design already required by CONTEXT.md's discretion clause is the correct response
>   regardless of the answer.

**Upstream reference:** anthropics/claude-code#41156, closed as not-planned. **Confidence as
recorded by research: MEDIUM. Not reproduced during 33-RESEARCH.md's session.** This phase's
own objective states plainly why that is not good enough to ship on: "It cannot be settled by
more research; it is settled by looking."

## What is already true regardless of the answer

The code does not wait on this observation to be correct — `33-CONTEXT.md`'s
degrade-never-refuse discretion clause was already the design constraint before this question
was raised, and 33-01/33-02/33-03 built to it:

- A prompt that blocks does not corrupt anything. `_migrate_once` (`durable_paths.py`) copies,
  verifies byte-for-byte, and **only then** deletes the source — there is no window where a
  half-completed migration leaves the operator with neither copy.
- `LV_OPERATOR_CONFIG` is the already-built escape hatch (`durable_paths.py` resolution step
  2, ahead of the durable home) if the chosen storage location turns out to need a prompt every
  time. It exists for exactly this contingency, not as a hypothetical.
- The unattended sweep never triggers this write path at all — `allow_migration=False` by
  construction (33-02), so a scheduled fire meeting a fresh install cannot hit the prompt
  either, blocking or not.

What RB-10 settles is narrower than "is the code correct": it is whether the *first live use*
of that correct code, on a real operator's real Claude Code install, is interrupted by a
confirmation dialog neither this plugin nor its operator can suppress through a supported path.

## The absolute constraint this observation must not violate

Restated here because it is the one thing that would invalidate the gate, not just the
finding: **if a permission prompt fires during RB-10, that IS the finding.** No task and no
line of RB-10 may change a permission setting, edit `settings.json`, or add a hook to suppress
it. `LV_OPERATOR_CONFIG` is the recorded mitigation if the answer is "yes, it fires" — a
decision about the chosen storage location, made with the observation in hand, never a
workaround around the guard.

## Where the real observation goes

`.planning/workstreams/plugin-entrypoint/OPERATOR-RUNBOOK.md`, §RB-10, has the exact five
steps (before-state backup, clone refresh, update, trigger one resolution, read the outcome,
confirm the dashboard pointer). When RB-10 is walked, record here, verbatim:

- Whether a permission-confirmation dialog appeared at Step 3, its exact wording if so, and
  whether it blocked `/operator-claude-plugin:initialize` from completing.
- The migrated file's mode (`ls -l`) and whether its contents matched the Step 0 backup
  byte-for-byte.
- Whether the previous install directory's copy was removed, and whether the current install
  directory held no config of its own beforehand.
- Whether the dashboard Artifact URL matched across a brand-new conversation (STATUS-05).
- A clean run with nothing to report is still a valid, complete answer — do not withhold
  writing this section because the result was unremarkable.

## Readiness of the plans this gate releases

| Plan | Released? | Basis |
|---|---|---|
| 33-04 (this plan) | Code-complete, gate open | Tasks 1–2 shipped and committed (`25e26ec`, `24c2f16`); Task 3 is RB-10, walked by the operator, not this executor |
| Phase 33 close | Pending RB-10 | The phase's own `must_haves.truths` requires "One real migration has been performed and observed on this host" — not yet true until RB-10 is walked and this file is updated with the result |
