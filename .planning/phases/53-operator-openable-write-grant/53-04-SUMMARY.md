---
phase: 53-operator-openable-write-grant
plan: 04
subsystem: operator-plugin
tags: [write-grant, skills, operator-surface, release, d-53-05, checkpoint-outstanding]

# Dependency graph
requires:
  - phase: 53-operator-openable-write-grant
    provides: write_grant.authorize_send / revoke_grant / close_grant / plan_grant / open_grant
  - phase: 53-operator-openable-write-grant
    provides: config_gate.WRITE_GRANT_SETTINGS_KEY, init_check's settings section
  - phase: 53-operator-openable-write-grant
    provides: n8n_arming.armed_window(grant=...) pass-through
provides:
  - "enrich-records / contact-upload / enrich-before-ingest: the grant conditional inside each lane's OWN numbered arming step, with the concrete authorize_send -> armed_window -> dispatch sequence"
  - "The D-53-05 decision record, in test_enrich_before_ingest_skill_contract.py, where a future reader looking at the traded pin will find it"
  - "The at-the-yes disclosure (the HubSpot write is authorized before the enriched preview exists), in skill prose AND pinned by an assertion"
  - "backend-control: open / revoke / close a grant inside the existing one-action-one-confirmation framing"
  - "README: the admin's key and the ALLOW_N8N_ARM-was-narrowed-not-replaced clause, plus a Write grants section for the operator"
  - "operator-claude-plugin 0.15.0 -- version bumped and CHANGELOG cut in one commit"
affects: [54-single-pass-dispatch, 57-ceiling-enforcement]

actuals:
  tokens: 34000
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "A traded protection is recorded IN the pin that used to hold it: docstring replaced with the decision, its date and its author, the old literal kept where it is still true of the ungranted path, and the disclosure that replaced it asserted in the same function -- so the removal and its price cannot be separated by a later sweep."
    - "The distinction a surviving literal no longer implies is written into the prose and pinned there: 'arming one lane does not arm any other lane' stays true under a grant only because the collapse is at the GRANT, not the ARM, and a reader has no way to know that unless the skill says it."
    - "Each lane skill's grant branch shows that lane's REAL dispatch (dispatch_plan for enrichment, dispatch.dispatch for contacts) -- same concreteness as the ungranted branch, not the same calls."

key-files:
  created: []
  modified:
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/skills/contact-upload/SKILL.md
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/skills/backend-control/SKILL.md
    - operator-claude-plugin/README.md
    - operator-claude-plugin/CHANGELOG.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/tests/test_enrich_skill_contract.py
    - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py

key-decisions:
  - "The recorded D-53-05 edit touches THREE things and no more: the module docstring (which claimed the two pins stop the collapse -- false the moment the collapse was taken deliberately), the combined-phrase pin, and the ordering pin. Both pins keep their names and their original assertions, because both are still literally true of the UNGRANTED path that D-53-04 leaves unchanged; what changed is the docstring (now the decision record), the failure message (now says it binds the ungranted path), and one added assertion per pin naming the new truth."
  - "The third pin (test_the_skill_states_the_grant_never_outlives_its_turn_and_arms_no_other_lane) is untouched, as directed. The skill satisfies its OR by keeping 'never written to disk' (GRANT-06, still exactly true) and the step-7 tail was rewritten so 'never outlives the turn' now applies only to the two per-send phrases, with the session grant described separately."
  - "backend-control's choke-point rule ('never call n8n_arming directly') was amended rather than contradicted: write_grant.py is named as the grant path's own choke point with the same plan/show/confirm rule. Without that the skill would forbid the very path it now offers."
  - "Version bumped 0.14.0 -> 0.15.0 (minor): added operator-facing capability, nothing removed, semver against this client's surface not the backend's milestone number."

patterns-established:
  - "Honest limits as its own CHANGELOG heading: the two trades (write authorized before the enriched preview; revoke refuses the next send only) sit next to the two standing limits (env var narrowed not replaced; the ceiling discloses not prevents) where an operator reading only the changelog will hit them."

requirements-completed: []
requirements-partial:
  - "GRANT-01: the exchange is now reachable from the operator's chair in prose -- every lane skill carries the grant branch, backend-control lists open/revoke/close, and the README tells an admin the key and an operator what a grant is. NOT ticked: the phase's own success criterion for GRANT-01 is the operator walk, which is the outstanding blocking checkpoint. Ticking it on the strength of tests would be exactly the claim G-2 disproved -- every component correct, the composition broken."
  - "GRANT-04: the surface that REPORTS an expiry now exists (backend-control names the close reasons and what closes a grant on its own; the README lists them). `ceiling_breach` still has no producer until Phase 57."
  - "GRANT-06: holds over 53-04's surfaces -- this plan added prose and a version string only. Nothing written, nothing defaulted, nothing remembered."

coverage:
  - id: G1
    description: "Each lane skill states that with a grant covering that lane open the per-turn arming phrase is not asked again, and that with no grant open behaviour is exactly what it is today (D-53-04)"
    requirement: "GRANT-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_skill_contract.py::test_the_skill_says_an_open_grant_replaces_the_per_turn_phrase"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py::test_the_skill_says_the_grant_branch_does_not_ask_for_the_phrase_again"
        status: pass
    human_judgment: false
  - id: G2
    description: "The D-53-05 removal is recorded in the contract test with its date and author, in prose naming what was traded -- held rows and merge conflicts authorized unseen -- and no test function is deleted"
    verification:
      - kind: command
        ref: "git diff -U0 operator-claude-plugin/tests/ | grep '^-' -- 13 lines, all docstring or failure-message prose, no `assert` and no `def test_`"
        status: pass
    human_judgment: false
  - id: G3
    description: "The disclosure bought with the traded protection -- the HubSpot write is authorized before the enriched preview exists -- is in the skill prose AND pinned, so a later edit cannot drop it"
    requirement: "GRANT-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py::test_the_ingest_arm_heading_is_strictly_after_the_enriched_preview_heading (the added assertion)"
        status: pass
    human_judgment: false
  - id: G4
    description: "The grant/arm distinction is written down and pinned: a grant may authorize both lanes, each arm still opens its own window over one lane and only that send's records"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py::test_the_skill_distinguishes_the_grant_that_spans_lanes_from_the_arm_that_does_not"
        status: pass
    human_judgment: false
  - id: G5
    description: "No skill widens a window to the grant's whole record set (T-53-18b) -- each grant branch names the send's own records as the allowlist and says so in words next to the code"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py::test_the_skill_never_widens_a_window_to_the_grants_whole_record_set"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_skill_contract.py::test_the_grant_branch_shows_the_window_scoped_to_this_sends_records"
        status: pass
    human_judgment: false
  - id: G6
    description: "Every operator-facing surface that mentions revocation says it bites at the next SEND and does not stop a dispatch already running"
    requirement: "GRANT-05"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_skill_contract.py::test_the_skill_says_revocation_bites_at_the_next_send_not_mid_dispatch"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py::test_the_skill_says_revocation_bites_at_the_next_send_not_mid_dispatch"
        status: pass
      - kind: manual
        ref: "backend-control/SKILL.md, README.md Write grants, CHANGELOG 0.15.0 Honest limits -- all carry the 40-records-is-20-chunks arithmetic"
        status: pass
    human_judgment: false
  - id: G7
    description: "The version string and the CHANGELOG's top dated section agree, with Unreleased empty above it"
    verification:
      - kind: command
        ref: "the release-consistency one-liner in 53-04-PLAN Task 2 -- prints `release consistency ok 0.15.0`"
        status: pass
    human_judgment: false
  - id: G8
    description: "An operator walks the whole path from Claude Desktop -- set key, open grant, send, revoke, close -- and records the result"
    requirement: "GRANT-01"
    verification:
      - kind: manual
        ref: "53-04-PLAN.md Task 3 (checkpoint:human-verify, gate=blocking)"
        status: OUTSTANDING
    human_judgment: true

duration: ~25min
completed: 2026-08-25
status: blocked-on-checkpoint
---

# Phase 53 Plan 04: Skills, Docs, Release Summary

**Every lane skill now tells the operator whether they need an arming phrase and what a
grant does not remove; the ordering protection D-53-05 traded is recorded in the pin that
used to hold it, with the disclosure it bought pinned beside it; and the client is cut at
0.15.0 — with the operator walk still outstanding as the phase's only evidence that G-2 is
actually closed.**

## Performance

- **Duration:** ~25min
- **Completed:** 2026-08-25 (tasks 1–2; task 3 outstanding)
- **Tasks:** 2 of 3 (task 3 is a blocking human checkpoint, deliberately not performed)
- **Files modified:** 9

## Accomplishments

- **Three lane skills carry the grant branch, each inside that lane's own numbered arming
  step** — not a new step and not a preamble. Each says: with an open grant covering this
  lane and these records the phrase is not asked again; with no grant open everything is
  exactly as it is today (D-53-04). Each then says **what a grant does not remove** —
  the preview still runs, the records are still named, every send arms and disarms its own
  window bounded to that send's records, a failed disarm is still reported loudly — because
  an operator who reads "you will not be asked again" without that line reasonably concludes
  the safety went away with the question (T-53-19).
- **Each grant branch shows the concrete call sequence in the same register as the
  ungranted one**: `write_grant.authorize_send(...)` → stop on a refusal →
  `n8n_arming.armed_window(decision["workflow_id"], <this send's records>, ...,
  grant=decision["grant"])` → the lane's real dispatch inside the window
  (`chunking.dispatch_plan` for enrichment, `dispatch.dispatch` for contacts). Next to the
  code, in words: the allowlist is **this send's records, never the grant's whole record
  set** — the narrowing that keeps every window strictly smaller than the grant, and the one
  mistake that would widen every window to the whole batch while every test still passed.
- **The D-53-05 trade is recorded where a reader will find it.** One deliberate edit in
  `test_enrich_before_ingest_skill_contract.py` touching the module docstring, the
  combined-phrase pin and the ordering pin: each now carries the decision, its date
  (2026-08-25), who took it (the operator), and in plain prose that **held rows and merge
  conflicts — which the enriched preview is the only place to see before a write — are now
  authorized unseen.** No test function deleted, no assertion deleted; both pins keep their
  original assertions, which remain true of the ungranted path, and each gains one assertion
  naming the new truth.
- **The disclosure bought with the protection is pinned.** The ordering pin now also asserts
  the skill says the HubSpot write is `authorized before the enriched preview exists`, so a
  later edit cannot quietly drop the sentence after the protection was already traded for it.
- **The grant/arm distinction is written down.** `arming one lane does not arm any other
  lane` stays in the skill and stays pinned — and the skill now explains why it stays true:
  D-53-05 collapsed the asks at the level of the **grant** (the authorization), not the
  **arm**; each arm still opens its own window over one lane's workflow and only that send's
  records. Without that paragraph the literal keeps passing while a reader draws the wrong
  conclusion from it.
- **`backend-control` lists open, revoke and close** inside its existing
  one-action-one-confirmation framing, with the envelope as arithmetic before one explicit
  yes, and `write_grant.py` named as the grant path's own choke point so the skill's
  "never call `n8n_arming` directly" rule does not contradict the path it now offers.
- **The README carries the admin's line and the operator's.** Which key, which file, set
  once, JSON boolean — and plainly that `ALLOW_N8N_ARM` is unchanged and remains the
  authority for the scheduled and cron paths, so an admin who finds both documented does not
  conclude one replaced the other.
- **Released at 0.15.0**, version bump and CHANGELOG cut in one commit per the checklist,
  `## [Unreleased]` left on top and empty. The entry has an **Honest limits** section
  carrying all four: the env var narrowed rather than replaced, the ceiling discloses rather
  than prevents, the two-lane grant authorizing the write before the enriched preview exists,
  and revocation biting at the next send only.

## Task Commits

1. **Task 1: The three lane skills — one grant, or today's phrase, never both** — `d266c91` (feat)
2. **Task 2: The control surface, the README, and the release cut** — `7ceca30` (docs)
3. **Task 3: The operator walk** — OUTSTANDING (blocking checkpoint, see below)

## Verification Output (as run, 2026-08-25)

```
$ .venv/bin/python -m pytest operator-claude-plugin/tests/test_enrich_skill_contract.py \
    operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py \
    operator-claude-plugin/tests/test_plugin_manifest.py \
    operator-claude-plugin/tests/test_status_skill.py -q
91 passed in 0.09s

$ .venv/bin/python -c "...release consistency check..."
release consistency ok 0.15.0

$ .venv/bin/python -m pytest operator-claude-plugin/tests/test_plugin_manifest.py -q
23 passed in 0.04s

$ .venv/bin/python -m pytest operator-claude-plugin/tests/ -q
1496 passed, 5 skipped in 5.02s

$ .venv/bin/python -m pytest -q
3059 passed, 154 skipped, 1 warning in 9.14s

$ node --test tests/n8n/*.test.mjs
ℹ tests 711
ℹ pass 711
ℹ fail 0

$ git diff -U0 operator-claude-plugin/tests/ | grep '^-' | grep -v '^---'
-step). Both are the mechanism that stops a later edit from silently collapsing the
-two-grant design into one.
-            f"a combined arming phrase slipped into SKILL.md: {spelling!r} -- a "
-            "combined phrase would necessarily be spoken before the enriched preview "
-            "exists, granting the HubSpot write before the operator can see what "
-            "they are approving"
-    """The ordering IS the safety property (37-CONTEXT.md sec 6.3): the enriched
-    preview must land in the operator's turn before the ingest arm can be spoken,
-    which is what makes the two `armed` arguments necessarily fall in different
-    turns. A later edit that reorders these two sections would collapse the design
-    with no other test noticing -- so the offsets are compared directly rather than
-    inferred from any other property of the document."""
-        f"{preview_offset}) -- the enriched preview must land in the operator's turn "
-        "before the ingest arm can be spoken"

$ git status --porcelain   # after both commits
(clean)
```

**Reading that diff, which is the plan's own acceptance test for Task 1:** thirteen removed
lines, every one of them docstring or failure-message prose, inside exactly the module
docstring and the two named pins. No line starting `assert`, and no line starting
`def test_`, was removed. The diff is **not** additions-only — and that is the point: an
additions-only diff here would have meant the trade went unrecorded.

## Decisions Made

- **The recorded edit keeps both pin names and both original assertions.** Unlike 53-01's
  parity pin, whose *name* had become false, both of these names remain literally true of the
  document and of the ungranted path D-53-04 leaves untouched. What changed is what the file
  *claims* they defend. Renaming would have spread the edit for nothing.
- **The module docstring was amended in the same edit.** It claimed the two pins "stop a
  later edit from silently collapsing the two-grant design into one" — false from the moment
  the collapse was taken deliberately. Left alone, the file would open with a lie about what
  its own pins do.
- **Step 1 of `enrich-before-ingest` got one conditional clause.** It told the operator
  unconditionally that the flow asks twice; under a two-lane grant it asks once. The clause
  names D-53-05 and the disclosure. This is the only edit outside a numbered arming step, and
  it exists because leaving a now-false promise in the skill's opening paragraph would be a
  worse outcome than the plan's "amend the arming step, not a preamble" instruction was
  guarding against.
- **`backend-control`'s choke-point sentence was amended, not left to contradict.** It says
  "everything runs through `control_actions.py` — never call `n8n_arming` directly". Grants
  run through `write_grant.py`. That module is now named as the grant path's own choke point
  with the same plan/show/confirm/never-arm-around-it rule.

## Deviations from Plan

- **Task 1's third-pin disposition was pre-decided by the orchestrator and followed exactly:**
  both assertions stay, and the skill was made to carry the grant-vs-arm distinction with its
  own additive pin. No deviation, recorded here because the plan text left the disposition
  ambiguous between two options and the choice is load-bearing.
- **`n8n/`, `scheduled_arm.py`, `test_scheduled_arm.py` untouched**, and no `scripts/` file
  was modified at all — `write_grant._consequence` was left alone deliberately; the at-the-yes
  disclosure lives in skill prose, which is what the contract test can pin.
- **Zero live HubSpot writes, zero n8n executions, zero provider credits** spent by this plan.

## Known Stubs

None. The one incomplete thing is the operator walk, which is a checkpoint rather than a stub.

## Outstanding: Task 3 — the blocking operator walk

**Not performed and not marked passed.** It requires an admin to set
`"allow_write_grants": true` in `operator.local.json` first, and it is the only evidence the
phase can produce for its headline claim: every component of the pre-phase path was
individually correct and the composition was broken — that is what G-2 was, and no test can
rule out the same failure mode here.

The full script is in `53-04-PLAN.md` Task 3. In short, from **Claude Desktop, not a
terminal**, except step 1:

1. **(Admin, terminal, by design)** Set `allow_write_grants` to `true` in
   `~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json`.
   Confirm your other values were already there and nothing had to be recreated.
2. Ask the plugin whether it is set up — the answer should now include a line saying write
   grants are **enabled**. Optionally re-try with the key as the *string* `"true"` and
   confirm it reports **not** enabled.
3. Ask to open a write grant over one or two records you are willing to have written. Check:
   does it name the lane, the records and whether creates are included; are the cost figures
   plausible and is the rate table's age shown; does it say the figure **discloses rather
   than prevents** and that the remaining monthly allowance is not yet checked; is there
   exactly **one** yes to give.
4. Send the batch. You should **not** be asked for an arming phrase, and the report should
   still tell you what was armed, what was sent, and whether the disarm verified. **Also
   confirm the D-53-05 disclosure landed**: when you opened a grant covering both lanes, were
   you told in plain words that the HubSpot write was being authorized before the enriched
   preview existed? That sentence is the whole of what you got for the protection you traded.
5. Revoke the grant. The next send should refuse and say the grant was revoked — and a
   dispatch already running should finish its chunks rather than stopping. That is the
   re-scoped GRANT-05 behaviour, not a bug.
6. Open a second grant covering a record **not** in the first, then attempt a send for a
   record outside it. It should be refused by name **before anything is armed**.
7. With the key unset, ask to open a grant. The refusal should name the key, the file and who
   sets it — and must **not** tell you to set a shell environment variable.

**Then answer the one open question:** is revocation at the next SEND enough? `dispatch_plan`
loops its chunks with no grant-aware hook, so at a 2-record chunk ceiling a 40-record send is
20 chunks and all 20 run after a revoke. Making `dispatch_plan` grant-aware is buildable but
changes the shared dispatch loop every lane uses, and would be its own phase.

**Finally, the two release steps deliberately left to you** (steps 3 and 4 of the CHANGELOG's
release checklist — the second touches a path outside this repository):

```
git push origin master

git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator fetch --depth=1 origin master
git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator reset --hard FETCH_HEAD
```

**Until the clone is refreshed, an installed plugin will not see 0.15.0 however correct the
version bump is** — the marketplace clone never fetches on its own, and a reinstall re-copies
from whatever it already holds.

## Self-Check: PASSED

- `operator-claude-plugin/.claude-plugin/plugin.json` — version `0.15.0` FOUND
- `operator-claude-plugin/CHANGELOG.md` — `## [0.15.0] - 2026-08-25` FOUND, `## [Unreleased]` empty above it
- Commits `d266c91`, `7ceca30` — both FOUND in `git log`
- `git status --porcelain` — no modification under `n8n/`, `scheduled_arm.py` or `test_scheduled_arm.py`
