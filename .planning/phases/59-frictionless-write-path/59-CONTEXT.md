# Phase 59: Frictionless write path - Context

**Gathered:** 2026-08-28
**Status:** SCOPE DELIBERATELY DEFERRED — do not plan this phase yet

<domain>
## Phase Boundary

**This phase is not ready to plan, by operator decision (2026-08-28).** Its scope is deferred
until Phase 53's outstanding operator walk has been performed, because the walk determines
what is actually broken. Planning it now would plan against guesses.

The roadmap entry for Phase 59 (three scoped items plus a credential guard) was written on
2026-08-27 from a code-review reading, before the scouting below. That scouting found two of
those items were mis-scoped. The entry is retained as history but is NOT the phase boundary.

</domain>

<decisions>
## Implementation Decisions

### D-59-01 — Walk Phase 53's grant BEFORE scoping this phase (operator, 2026-08-28)

The operator asked the right question — *"how do we make it so that an operator can approve
once per session, and then ingest, enrich and write to HubSpot unattended?"* — and the answer
turned out to be: **that is already built, and has never been run once.**

- Phase 53 shipped the once-per-session grant: one grant spans BOTH the `contacts` (ingest)
  and `enrichment` lanes (D-53-05), arms `ALLOW_HUBSPOT_RECORD_WRITES` + `ALLOW_HUBSPOT_CREATE`
  + the record allowlist (`n8n_arming.DISPATCH_FLAGS`), and no per-send ask survives it
  (D-53-06, implemented — `enrich-records/SKILL.md:182-222`).
- **Authorization is therefore NOT the blocker for the operator's stated goal.**
- But `53-04-SUMMARY.md` records its own headline claim as unproven: *"NOT ticked: the phase's
  own success criterion for GRANT-01 is the operator walk, which is the outstanding blocking
  checkpoint. Ticking it on the strength of tests would be exactly the claim G-2 disproved —
  every component correct, the composition broken."*
- **Phase 53 was nonetheless sealed `Complete (verified)` in the ROADMAP ledger on 2026-08-26
  with that blocking checkpoint still open.** Corrected in the ledger on 2026-08-28.
- The 2026-08-27 phase-54 session is direct evidence for taking this seriously: five executor
  agents, every component passing its tests, and the composition broke twice on authorization
  locks nobody had walked end to end.
- **Decision:** perform the walk (script: `53-04-PLAN.md` Task 3, summarized in
  `53-04-SUMMARY.md` § Outstanding), then scope Phase 59 from what it finds.
- **Step 1 of that walk is already satisfied** — verified 2026-08-28:
  `allow_write_grants` is present and `true` (a real boolean, not the string `"true"` that
  step 2's negative check probes for) in
  `~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json`.
  No admin/terminal step remains; the walk runs from the operator's chair.

### D-59-02 — "Unattended" is not an authorization problem (scouted 2026-08-28)

Stated so the next planner does not look for it in the wrong place. What stops the grant path
from being genuinely unattended is not consent, it is throughput and safety-net work that other
phases already own:

| Blocker | Owner |
| --- | --- |
| `max_records_per_chunk: 2` + the synchronous ~100s response window — a 40-record batch is 20 sequential chunks each holding a connection open. Supervised, not unattended. | **Phase 55** |
| ingest → enrich → create → associate as ONE flow; today ingest and enrich are separate dispatches | **Phase 56** |
| refuse-before-start against the remaining monthly allowance — D-53-02 states plainly that the grant's computed ceiling is **disclosure, not constraint**, and that the protective load falls entirely here | **Phase 57** |

Phase 59 must not absorb any of these.

### D-59-03 — The review lane gets its own small phase, after the walk (operator, 2026-08-28)

- Approving a flagged record is **human triage, not unattended running**. It is not on the
  ingest → enrich → write path and does not belong in a phase about that path.
- The 2026-08-27 pain was real but was misdiagnosed in the 2026-08-27 roadmap entry as
  "redundant ceremony". It is not redundancy — `write_grant.py:66-69` excludes the review lane
  from grants **deliberately** (30-01 D-02/D-08e): *"arming a dispatch grants nothing on the
  review path, and `ALLOW_REVIEW_SUBMIT` is its own gate. Folding review into a dispatch grant
  would revoke that separation silently."*
- So review is the ONE lane grants do not reach, which is why approving one contact fell back
  to a kill switch plus an admin-only arm-deploy — G-2's shape, still live on that lane.
- **Deleting `ALLOW_REVIEW_SUBMIT` with nothing behind it makes that lane HARDER, not easier**
  (its only remaining authority would open via a deploy an operator cannot run). The
  2026-08-27 roadmap entry's item 1 is wrong as written and must not be executed literally.
- Deferred to its own phase. The live options identified, for that phase to choose between:
  (a) an admin-set settings key mirroring D-53-01's `allow_write_grants` pattern — keeps the
  separation, removes the shell dependency; (b) make the review lane grantable — most friction
  removed, but deliberately reverses 30-01's separation and needs D-53-05's recorded-edit
  discipline; (c) accept the admin deploy as correct for occasional triage.

### D-59-04 — The ambient-credential guard survives, unchanged (operator, 2026-08-27)

Folded into 59 on 2026-08-27 and NOT affected by the re-scope — it is independent of the walk.
Add a root `tests/conftest.py` autouse fixture stripping `ANTHROPIC_API_KEY` /
`HUBSPOT_PRIVATE_APP_TOKEN` from `os.environ` unless a test is `@live`-marked. Full rationale
and evidence in the ROADMAP Phase 59 entry. Carry it into whatever 59 becomes.

### Claude's Discretion

- Nothing yet. This phase has no implementation scope until the walk lands.

</decisions>

<specifics>
## The walk, as it stands today

From `53-04-PLAN.md` Task 3. Step 1 is already done (see D-59-01). Steps 2-7 run from Claude
Desktop, not a terminal:

2. Ask the plugin whether it is set up — the answer should now say write grants are **enabled**.
3. Open a write grant over 1-2 records you are willing to have written. Check: does it name the
   lane, the records, and whether creates are included; are the cost figures plausible and is
   the rate table's age shown; does it say the figure **discloses rather than prevents** and
   that the remaining monthly allowance is not yet checked; is there exactly **one** yes.
4. Send the batch. You should **not** be asked for an arming phrase. Confirm the D-53-05
   disclosure landed: were you told in plain words that the HubSpot write was authorized
   BEFORE the enriched preview existed?
5. Revoke. The next send should refuse by name — and a dispatch already running should finish
   its chunks rather than stopping (re-scoped GRANT-05 behaviour, not a bug).
6. Open a second grant covering a record NOT in the first, then attempt a send for a record
   outside it. It should be refused by name **before anything is armed**.
7. With the key unset, opening a grant should name the key, the file and who sets it — and
   must NOT tell you to set a shell environment variable.

**The open question the walk must also answer** (from 53-04): is revocation at the next SEND
enough? `dispatch_plan` loops chunks with no grant-aware hook, so at chunk ceiling 2 a
40-record send is 20 chunks and all 20 run after a revoke
(`test_a_revocation_midway_does_not_stop_a_running_dispatch` pins this). Making `dispatch_plan`
grant-aware is buildable but changes the shared dispatch loop every lane uses.

**Cost:** live HubSpot writes on the 1-2 records the operator names, plus a handful of n8n
executions against the 2,500/month budget.

</specifics>

<deferred>
## Deferred Ideas

- **Review-lane authority** — D-59-03, its own phase after the walk.
- **`dispatch_plan` grant-awareness** (chunk-granular revocation) — 53-04 already names it as
  its own phase; the walk decides whether it is needed.
- **Todo `2026-08-04-sweep-crontab-pins-a-versioned-plugin-path`** — surfaced by todo matching
  at 0.4; not folded. Unrelated to this phase's subject (the unattended sweep's crontab pins a
  versioned plugin path). Left in the backlog.

</deferred>

<open_question>
## Still outstanding after this discussion

`ALLOW_REVIEW_SUBMIT=true` remains live in `.claude/settings.local.json`, set on 2026-08-27 to
unblock one review write. It is a persistent switch, and under D-59-03 it is no longer slated
for near-term removal. Either remove the line now (the backend allowlist is the binding
constraint regardless) or record deliberately that it stays.
</open_question>
