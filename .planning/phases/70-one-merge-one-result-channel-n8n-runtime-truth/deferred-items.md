# Deferred Items — Phase 70

Out-of-scope discoveries logged during execution. Not fixed here.

## From 70-13 (2026-09-10)

- **`git.allow_default_branch_commits` is unset while every phase commits to `master`.**
  The executor's pre-commit protected-branch assertion resolves `master` as the
  default/protected branch and its literal reading is HALT. `use_worktrees: false` and
  the whole repo history lives on `master`, so the guard fires on every executor run and
  has to be reasoned past each time. **Operator action:** set
  `"git": {"allow_default_branch_commits": true}` in `.planning/config.json` — that is the
  sanctioned override. Deliberately not done by the executor (self-authorizing via a
  config edit is exactly what the protocol forbids). Recorded as 70-13 deviation 1.
- **A `Parse HubSpot Event`-level refusal cannot be correlated by `run_id`.**
  The refusal item is built before the per-event map, so it carries no `run_id`/`row_id`
  and `Build Ack` answers `{run_id: null, accepted: true, row_ids: []}`. Pre-existing for
  the oversize and empty-array refusals; the new `scale_up` refusal inherits it because
  the plan required copying the existing refusal shape exactly. A caller that recovers by
  `run_id` therefore cannot find a refused request's execution. Out of scope for 70-13
  (widening the refusal shape was explicitly not this plan's job).
