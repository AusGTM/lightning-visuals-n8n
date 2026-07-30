---
phase: 27-backend-status-surface
plan: 05
subsystem: operator-claude-plugin
tags: [plugin, dashboard, artifact, persisted-state, ttl, parity, skill]

requires:
  - phase: 27
    plan: 04
    provides: "status.full_report()'s assembled mapping and render_text's helpers — the same data and the same wording the dashboard renders, plus the SKILL.md marker this plan fills in"
  - phase: 27
    plan: 03
    provides: "status.render() — the unknown discipline every dashboard value still routes through"
provides:
  - "artifact_store.load()/save()/collect()/state_path() — the plugin's only persisted state: one dashboard Artifact identifier and its timestamp, expiring on a configurable TTL (D-09a/D-09b)"
  - "render_dashboard.dashboard_payload()/render_dashboard() — the dashboard's data and its self-contained HTML, built from the same mapping the text answer is built from (D-09, STATUS-05)"
  - "config key dashboard_artifact_ttl_days (default 30)"
  - "skills/backend-status/SKILL.md — collection on open, dashboard on request, republish against the remembered identifier"
affects: [28 (adds steps to the same SKILL.md; see D-09c(3) for where start-time housekeeping goes)]

tech-stack:
  added: []
  patterns:
    - "A bounded store proves its bound by test: save(**extra) raises, and a fourth public verb fails the surface test"
    - "The stamp is read from the data, not from the clock — a republished cached view says when it was gathered"
    - "Two renderers compared against each other from one fixture, not each against its own expectations"
    - "n8n-supplied strings are escaped into markup; a workflow name is not trusted HTML"

key-files:
  created:
    - operator-claude-plugin/scripts/artifact_store.py
    - operator-claude-plugin/scripts/render_dashboard.py
    - operator-claude-plugin/tests/test_artifact_store.py
    - operator-claude-plugin/tests/test_dashboard_parity.py
  modified:
    - operator-claude-plugin/skills/backend-status/SKILL.md
    - operator-claude-plugin/config/operator.local.example.json
    - operator-claude-plugin/README.md
    - operator-claude-plugin/CHANGELOG.md
    - .gitignore
    - .planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-CONTEXT.md

key-decisions:
  - "The gitignore entry names the FILE, not the directory. A wildcard on operator-claude-plugin/state/ would swallow a second state file silently; naming the one file means anything else that appears there shows up in `git status` and gets argued about — which is D-09b's bound enforced by version control as well as by test."
  - "`_ttl()` falls back to 30 days when the config value is unreadable (a string, a null, a list) rather than raising or coercing. A typo in the operator's config must not silently shorten the expiry to nothing — and 0 is a legitimate, deliberate value meaning 'stop reusing the link', so it cannot double as the error case."
  - "The dashboard reuses `render_text`'s own sentence helpers (`_right_now`, `_last_run`, `_armed`) and its `COUNT_LABELS` rather than restating them. Parity is then structural: the two surfaces cannot word the same fact differently, and a rename in render_text fails the dashboard's tests loudly instead of silently forking the wording."
  - "`render_dashboard.py` keeps a `__main__` block that fetches, even though the rendering functions are pure. The skill needs one command; purity is a property of what the renderers can reach (no transport, no file, no store), not of the file. Folded into 27-CONTEXT.md as D-09c(2)."
  - "Collection goes in a new `## On start` section above step 1 rather than inside an existing step — 27-04 owns steps 1–3 and 5, and renumbering them to insert housekeeping would churn a file two phases now edit."

requirements-completed: []

duration: 48min
completed: 2026-07-31
status: awaiting-checkpoint
---

# Phase 27 Plan 05: The dashboard, and the one thing this plugin remembers Summary

**The same status reading the text answer carries, published as a bookmarkable Artifact stamped
with when the data was fetched — backed by the plugin's first and only piece of persisted state, a
store bounded to exactly an identifier and a timestamp by a test rather than by intention.**

## Status: Tasks 1 and 2 complete, Task 3 awaiting the operator

**Task 3 is a `checkpoint:human-verify` and was deliberately not performed.** It requires
publishing an Artifact in Claude Desktop and observing cross-session URL behaviour — a platform
tool call this repository's test suite cannot invoke, and the only step that actually proves
D-09a. Nothing about it was simulated, stubbed or asserted from a stand-in. See
**"What the operator must do"** below.

## Performance

- **Duration:** ~48 min
- **Completed (Tasks 1–2):** 2026-07-31
- **Tasks:** 2 of 3 (both TDD with genuine RED); Task 3 blocked on a human
- **Files modified:** 10 (4 created, 6 modified — 1 of them a planning doc)

## Accomplishments

- **`artifact_store.py` — the plugin's only persisted state, and bounded by proof.** Exactly
  `artifact_id` and `saved_at`. `save()` takes `**extra` purely in order to **refuse** it: the
  plausible next commit is `save(id, url=...)`, and silently persisting that is how a two-field
  store becomes a general one (D-09b, T-27-22). A test asserts the rejected save writes *nothing
  at all*, and a second test pins the module's public surface to exactly
  `load/save/collect/state_path` so a fourth verb cannot appear quietly. The arming grant stays
  where Phase 23 D-11 put it — nowhere on disk.
- **Every unusable pointer is silently nothing.** Missing file, unparseable JSON, a top-level
  list, a missing field, an unparseable timestamp, or an entry past its expiry all return `None`
  rather than raising. A stale or broken pointer is indistinguishable in effect from no pointer,
  and neither is worth an error message an operator has to read.
- **Expiry is real and operator-owned.** `dashboard_artifact_ttl_days` in the committed example
  config, default 30, `0` meaning "expire immediately" — the operator's off switch for link
  reuse, and the thing Task 3 step 6 exercises. `collect()` deletes an expired *or unreadable*
  pointer and leaves a live one byte-identical; on a missing file it is a no-op.
- **The state file cannot be committed.** `.gitignore` names the file itself rather than the
  directory, so a second state file would surface in `git status` instead of being swallowed by a
  wildcard. `git check-ignore` proves it from inside the test suite (T-27-24).
- **`render_dashboard.py` — the same data, or it would be a second source of truth.** The payload
  is built from `status.full_report()`'s mapping, the one `render_text.render_report()` consumes,
  reusing render_text's own sentence helpers and count labels. `test_dashboard_parity.py` drives
  both renderers from `test_status_skill.py`'s fixture and compares them **against each other** —
  every workflow, every count value, on/off, last run, right-now, each live-write flag, provider
  balances, and a failed run's sentence and attribution.
- **The stamp says when the data was fetched, not when the page was drawn.** It is read out of
  the mapping (`backend.checked_at`), so two renders of one mapping carry one stamp — asserted
  directly. A dashboard republished from a cached reading cannot present itself as current
  (T-27-23), and the skill tells the operator so in words.
- **Unknown survives onto the visual surface.** Every value goes through `status.render()`; a null
  count renders the word `unknown`, italicised so the eye separates it from a real reading, and
  the counts block is asserted to contain **no bare zero and no empty cell** when the backend did
  not answer. A genuine `0` still reads `0`.
- **n8n-supplied strings are escaped.** Workflow names and raw error text are attacker-adjacent
  input to a page; a test feeds `<script>` and an `onerror` payload through both and asserts they
  come out inert.
- **The skill wiring.** Collection on open (its own `## On start` section), text as the default
  with the dashboard published only on request, load-then-publish-or-republish against the
  remembered identifier, save back when one is newly minted, and an explicit instruction to
  publish the generated HTML verbatim rather than improvising a page from the text answer.

## Task Commits

1. **Task 1 — RED:** `32f372a` (test) · **GREEN:** `23bb787` (feat)
2. **Task 2 — RED:** `d082c9a` (test) · **GREEN:** `f1db7a1` (feat)
3. **Task 3 —** not started; blocking human checkpoint.

RED was genuine both times: Task 1's RED failed at collection (`No module named
'artifact_store'`), Task 2's likewise (`No module named 'render_dashboard'`).

## Test Counts

| Suite | Before | After | Delta |
|---|---|---|---|
| pytest (repo, `.venv/bin/python -m pytest -q`) | 1065 passed, 1 skipped | **1117 passed, 1 skipped** | **+52** |
| pytest (plugin only) | 302 passed | **354 passed** | **+52** |
| node (`node --test tests/n8n/<file>.test.mjs`) | 400 passed, 0 fail | **400 passed, 0 fail** | 0 |

The +52 is exactly this plan's two new test files (27 + 25). No existing test was weakened,
skipped or deleted; no regression anywhere. `test_status_skill.py`'s marker assertion still passes
— the `27-05 DASHBOARD STEP` comment was edited in place, not removed.

## Decisions Made

See `key-decisions` in the frontmatter. The two a later plan could undo without noticing:

- **Do not add a fourth writing verb to `artifact_store`.** The public-surface test is the bound,
  and the bound is the whole reason the store is allowed to exist (D-09b).
- **Do not delete `render_dashboard.py`'s `__main__` block in the name of purity.** It is the
  skill's only command. Purity is a property of the rendering functions, not of the file — folded
  into `27-CONTEXT.md` as **D-09c(2)**.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] The plan's behaviour list did not mention escaping**
- **Found during:** Task 2, writing the markup.
- **Issue:** Workflow names and raw error text come from n8n and land in an HTML document. The
  plan's behaviour list covers parity, unknowns and credentials but says nothing about markup
  safety; interpolating those values raw would put attacker-adjacent input into a page the
  operator opens.
- **Fix:** Every value goes through `html.escape()` via one `_e()` helper, with
  `test_values_are_escaped_into_the_html_rather_than_interpolated_raw` feeding a `<script>` tag
  and an `onerror` payload through both fields.
- **Commit:** `f1db7a1`

**2. [Rule 3 - Blocking] `state_path()` had to be public, against the plan's "exactly three entry
points"**
- **Found during:** Task 1.
- **Issue:** The plan's own acceptance criteria call `artifact_store.state_path()`, and both the
  gitignore proof and the not-a-dotfile proof need the resolved path. Keeping it private would
  have meant duplicating the resolution logic in the tests, which is how a path check drifts away
  from the path actually used.
- **Fix:** Made it public and pinned the whole public surface to exactly four names by test, which
  preserves the plan's actual intent (the store cannot grow another verb) rather than its literal
  count. Folded into `27-CONTEXT.md` as **D-09c(1)**.
- **Commit:** `23bb787`

**Total deviations:** 2. Neither changed what the plan asked for.

## Plan/reality mismatches

Three, all folded into `27-CONTEXT.md` as **D-09c** rather than left here (the planner reads
CONTEXT): the store's four-name public surface, the scope of "rendering is pure" versus the
module's operator-facing CLI, and where start-time housekeeping goes in a SKILL.md that two
phases now edit.

## Known Stubs

None. No placeholder value reaches a rendering surface, and the skill's previous "not built yet"
paragraph has been replaced by the working step.

## Threat Flags

None. No new network endpoint, no auth path, no schema change. The one new file-access pattern —
the state file — is the plan's declared artifact, is gitignored, and holds neither a secret, a URL
nor a record identifier (asserted by test).

## Safety invariants

- **No write flag armed, no deploy, no activation, no live HubSpot or n8n call.** No automated
  verification made a network request; the autouse `no_network` guard was left untouched (D-11).
- `grep -o 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json | wc -l` → **0**. This plan touched no
  `n8n/` file.
- **Phase 27 reads only.** Nothing added here can turn a workflow on or off, start a run, or
  change a record. The dashboard's footer and the skill's opening both say so.
- The only send-shaped functions in the plugin remain `dispatch.py::dispatch` and the allowlisted
  bodyless `backend_status.py::fetch_backend_status`; `test_retry_reuses_dispatch.py`'s three
  guards stayed green with no allowlist edit. Neither new module constructs a request.
- Every commit staged explicit paths in the same shell invocation as the commit, with
  `git diff --cached --name-only` printed immediately beforehand. No `git add -A`, no `git add .`,
  no `git commit -a`.

## Concurrent-operator hygiene

Another operator was mid-way through the 23-06 checkpoint in this working tree throughout. Their
four paths — `.planning/workstreams/plugin-entrypoint/STATE.md`,
`operator-claude-plugin/.claude-plugin/plugin.json`,
`operator-claude-plugin/tests/test_plugin_manifest.py`, and the untracked `23-06-SUMMARY.md` —
were never read-modified, staged or committed, and remain exactly as they were.

**STATE.md was deliberately not updated this run.** Leaving it stale is correct: it carries the
operator's live checkpoint notes, and advancing the plan counter would have swept them into this
plan's commit. The next agent to touch STATE.md should hand-edit it (per HANDOFF §6, the
`state.*` tools mangle this workstream's file) to record 27-05 as built-pending-checkpoint.

**ROADMAP.md and REQUIREMENTS.md were also left alone**, on purpose: **STATUS-05 is not complete
until Task 3 passes.** The store, the parity and the expiry are proven by test, but "a refresh in
a new session lands on the same URL" is proven only by the human checkpoint. Marking the
requirement complete now would assert something nothing has verified.

## What the operator must do (Task 3)

In a Claude Desktop **Code**-tab session with the plugin installed and
`config/operator.local.json` filled in:

1. Ask for backend status. **Expect conversational text and no dashboard** — text is the default.
2. Ask for the dashboard. Confirm it publishes, and that its workflows, counts and provider
   states match the text answer, with a fetch-time stamp on the page.
3. In the *same* conversation, ask for a refresh. **Confirm the URL is unchanged** and the stamp
   has moved forward.
4. Start a **brand-new conversation** and ask for the dashboard again. **Confirm it lands on the
   same URL as step 2**, not a second one. This is the only step that proves D-09a — everything
   else about the store is covered by tests, but nothing automated can reach the publish
   mechanism.
5. Confirm a provider whose balance the backend could not read shows as **unknown**, not as a
   zero balance and not as healthy.
6. Set `dashboard_artifact_ttl_days` to `0` in `config/operator.local.json`, open the skill again,
   and confirm `operator-claude-plugin/state/dashboard_artifact.json` has been removed and the
   next dashboard request mints a fresh identifier. **Restore the value to 30 afterwards.**
7. Confirm none of the above turned a workflow on or off, started a run, or changed a record.

Reply **"approved"**, or describe which step's behaviour differed.

If step 4 fails — a new conversation minting a second URL — the likely causes, in order: the
`## On start` collection ran with a TTL of 0 left over from step 6; the identifier was never
saved back after step 2 (check the file exists and holds `artifact_id`); or the platform does not
allow updating an Artifact created in another session, which would be a genuine platform finding
and an amendment to D-09a rather than a bug in this plan.

## Next Phase Readiness

- **Phase 27 is code-complete.** Its remaining work is this checkpoint.
- **Phase 28** adds steps to the same `skills/backend-status/SKILL.md`; read **D-09c(3)** in
  `27-CONTEXT.md` before inserting anything, and note that 27-04 owns steps 1–3 and 5 while this
  plan owns `## On start` and step 4.
- No blocker for Phase 28's own planning or checker run.

---
*Phase: 27-backend-status-surface*
*Tasks 1–2 completed: 2026-07-31 · Task 3 awaiting the operator*

## Self-Check: PASSED

All four created files exist on disk (`scripts/artifact_store.py`,
`scripts/render_dashboard.py`, `tests/test_artifact_store.py`, `tests/test_dashboard_parity.py`);
all four task commit hashes (`32f372a`, `23bb787`, `d082c9a`, `f1db7a1`) verified present in
`git log`.
