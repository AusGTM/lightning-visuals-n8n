# 33-FINDINGS — durable operator state, real-migration observation (plan 33-04, RB-10)

**Status: OBSERVED 2026-08-04 — see the RB-10 result appended at the end of this file.** The original pre-walk text is kept below unchanged, per this file's own instruction not to delete the question.

**Superseded header (pre-walk):** This file records what the phase knows going in and what
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


---

# RB-10 RESULT — walked 2026-08-04, operator + orchestrator, real machine

**Plugin under test:** `0.7.1`. RB-10 was written for `0.7.0`; the `0.7.1` empty-input fix shipped
before the walk, so the operator updated once, straight past `0.7.0`.

## Open Question 1 — ANSWERED: no prompt

**No permission-confirmation dialog appeared.** Operator, verbatim:

> "When runing initialize no permission confirmation dialogue appeared"

The migration wrote, verified, and deleted its source uninterrupted. **No permission setting,
`settings.json` edit, or hook was used to achieve that** — the absence is genuine, not manufactured.
The mitigation built for the other outcome (`LV_OPERATOR_CONFIG` plus the untouched legacy fallback)
was never needed and remains available. Open Question 1 is closed; the storage location stands.

## The migration — worked exactly as designed

Before (Step 0): installs `0.1.0`, `0.6.1`, `0.6.2`, all holding an identical config (sha
`db2674a2…`); no durable home. Backup outside `~/.claude/` at `~/rb10-config-backup-20260804.json`.

| Check | Result |
|---|---|
| Durable file exists | PASS — 627 B |
| Mode | PASS — `600` |
| Byte-for-byte vs backup | PASS — identical |
| Newest sibling (`0.6.2`) cleaned | PASS — gone |
| New install (`0.7.1`) holds no config of its own | PASS — right source chosen |
| `initialize` output | PASS — names the durable path, never mentions migration (33-03's rule) |
| Status read afterwards | PASS — real balances (lusha 3930, zoominfo 9301); migrated credentials work |

`0.1.0` and `0.6.1` still hold credential copies. Expected — the scan takes only the newest sibling
— but one migration does not finish the credential-hygiene job. Follow-up, not a criteria failure.

## DEFECT FOUND — STATUS-05 still broken for a first-time pointer

Step 5 created a dashboard (`.../artifact/c2ee823e-…`). The pointer landed at
**`0.7.1/state/dashboard_artifact.json`, inside the versioned install directory** — the exact
location this phase exists to stop using. The durable home held only `operator.local.json`.

**Cause.** Both resolvers end with `return legacy` when the file exists nowhere:

    explicit -> env -> durable (if exists) -> legacy (if exists) -> migrate-from-sibling -> return legacy

The **config** had a sibling copy, so it migrated — the path that passed above. The **pointer** did
not exist in any install (Step 0 confirmed no `state/` anywhere), so resolution fell through and
returned the legacy path *as the write target*. Every newly created pointer is therefore written
into the install directory and stranded by the next update.

**Wider than the pointer:** the identical fallthrough governs the config. A brand-new operator with
no config anywhere runs `initialize --create` and it is written into the versioned install
directory — stranded on their first update. Existing operators were saved only by having a sibling
to migrate from.

**Why the suite missed it — the 0.6.1/0.6.2 shape again.** Every state test seeds the durable file
before asserting:

- `test_durable_save_lands_in_the_durable_directory_not_either_version_directory` saves under
  `0.6.2`, loads under `0.7.0` to migrate that pointer up, then asserts. Its docstring says it
  covers the case "once the durable home is already established".
- `test_the_resolved_state_path_sits_outside_the_plugin_directory` and its sibling call
  `_point_at_a_fake_durable_home`, which pre-creates the pointer.

That pre-creation was 33-03's documented deviation: the bare tests failed in a dev checkout because
resolution legitimately falls through when nothing exists. **The fallthrough WAS the bug, and
seeding the fixture to get past it hid it.** The environment was blamed for a finding.

"No file anywhere, first write on a fresh install" — the state every new operator begins in — was
untested in both resolvers.

**Fixed in `0.7.2`.** Resolvers now return the durable path as the write target when nothing exists,
degrading to legacy only when the durable home cannot be created.

## Step 5's second half — NOT COMPLETED

The cross-conversation dashboard check was not walked. The skill *asserted* "Link stays the same on
refresh — even from a new conversation", but that is the skill's claim, not an observation, and
given the defect it would have held only within `0.7.1`. Re-walk after `0.7.2` with the stale
pointer cleared.
