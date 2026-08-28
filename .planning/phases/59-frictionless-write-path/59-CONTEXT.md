# Phase 59: Frictionless write path - Context

**Gathered:** 2026-08-28
**Status:** READY TO PLAN — the blocking walk has now been run (see D-59-01 addendum)
**Updated:** 2026-08-28, after the Phase 53 operator walk

<domain>
## Phase Boundary

**The walk has now been run — this phase IS ready to plan.** (The paragraph below records why
it was blocked; the block is discharged.) Scope was deferred until Phase 53's outstanding
operator walk had been performed, because the walk determines what is actually broken.
Planning before it would have planned against guesses — and the walk vindicated that: it found
a defect nobody had predicted (`53-WALK-RECORD.md` FINDING 2) and confirmed one that had been
(FINDING 1).

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

**ADDENDUM — the walk was run on 2026-08-28. Full record: `53-WALK-RECORD.md`.**

Run autonomously at the operator's instruction. Caveat recorded there: it ran from Claude Code
with terminal access, so it tests the COMPOSITION but not the operator's own constraint set.

- **GRANT-01 is still NOT ticked**, and the ROADMAP entry for Phase 53 stays corrected.
- **The grant machinery itself works**: authority check, envelope (Apollo honestly `known:
  false` with a citation rather than a number), the D-53-05 disclosure verbatim and clear,
  per-send narrowing (*"narrower than the grant, never wider"*), a live arm -> dispatch ->
  disarm cycle ending in `VERDICT: disarmed PASS`, and `close_grant` refusing a free-text
  reason and naming the seven it can report on.
- **FINDING 1 (predicted, and correct behaviour):** a create with neither a HubSpot id nor an
  email domain cannot be granted on ANY armed path — `plan_grant` and `authorize_ungranted_send`
  both refuse an empty record set, loudly and with a good reason. Resolved by scoping to the
  company's domain, found read-only in HubSpot.
- **FINDING 2 (unpredicted, and the reason this phase now has real scope):** the documented
  `merge_enriched(rows, outcome.responses)` call in `enrich-before-ingest` step 5 loses ALL
  enrichment silently. `dispatch_plan` returns per-chunk LISTS; `merge_enriched` skips non-dict
  items; every row lands in `unanswered` — the group documented as *"a row nothing is known
  about at all"*. Measured on one real record: as documented `unanswered: 1` / email `None`;
  flattened `unanswered: 0` / email `josh@seriesfutsal.com`. Paid-for provider data is
  discarded and reported as absent.
- **The walk was halted before the HubSpot write** rather than flattening around the defect —
  a hand-patched success would have misrepresented the shipped flow. **Zero HubSpot writes.**
  Cost: 1 n8n execution, ~1 Lusha + ~1.08 ZoomInfo credit, ~$0.07 Anthropic.
- **Consequence for scoping:** FINDING 2 is a live silent-data-loss defect on the operator's
  own headline flow. It has a strong claim on this phase, or on a fix that precedes it.

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

### D-59-05 — `ALLOW_REVIEW_SUBMIT` removed from settings (operator, 2026-08-28)

Decided before the walk, at the operator's request, because a persistent write-enabling switch
should not be carried into a live exercise unexamined.

- **State when decided, verified live rather than assumed** (`verify_live_write_safety.py
  --expectation disarmed`, read-only, 2026-08-28): backend `ALLOW_HUBSPOT_REVIEW_WRITES='false'`
  with both allowlists empty across every declaring node in all 5 workflows —
  `VERDICT: disarmed PASS`. The switch was therefore **inert**: it opened lock 1 of 2 while
  lock 2 was shut, and any review submit would have returned `not_allowlisted`.
- **Decision: removed.** The `env` block is gone from `.claude/settings.local.json`. Zero
  functional loss today; it restores the two-lock design on the one lane whose separation
  D-59-03 just confirmed is deliberate, and removes a setting that would have silently halved
  that protection the next time anyone armed review.
- **It never affected the walk** — the walk exercises the `enrichment` and `contacts` lanes;
  review is a separate authority.
- **Reject/undo decisions are unaffected**: `review_decision.is_undoing()` bypasses this gate by
  design, so walking a record back never needed it. Only approving did.
- **Known residual, stated so nobody misreads the file as proof:** Claude Code loads settings
  `env` at SESSION START, so the session in which this removal was made still carried
  `ALLOW_REVIEW_SUBMIT=true` in its own process environment for its remaining lifetime. The
  removal binds new sessions. It was inert throughout either way.
- **Cost of reversing, if a review approve is needed before Phase 60:** re-add the line, plus
  the backend arm-deploy that would be required regardless. About a minute.

### D-59-06 — Revocation stays at next-send; disclose the run-to-completion behaviour once, at session start (operator, 2026-08-28)

Answers the open question 53-04 left for the walk (*"is revocation at the next SEND enough?"*).

- **Yes, it is enough.** `dispatch_plan` stays grant-unaware; no per-chunk hook is added. A
  revoke refuses the NEXT send and a dispatch already running completes its remaining chunks
  (`test_a_revocation_midway_does_not_stop_a_running_dispatch` keeps pinning this, unchanged).
- **What is added instead:** a **non-blocking note at session start** telling the operator that
  once enrichment and writing start, the run continues until done. One statement, up front,
  where it informs the decision to begin — not a prompt, not a gate, not repeated per send.
- Rationale: the protection a grant-aware dispatch loop would buy is small (it stops chunks
  mid-run), and its cost is large (it changes the shared dispatch loop every lane in this
  plugin uses — `write_grant.py` already names that as why it was not done). Telling the
  operator the true behaviour once is the honest, cheap version.
- **This closes, rather than defers, the question 53-04 posed.** The walk no longer needs to
  answer it; it only needs to confirm the note appears.

### D-59-07 — Replace D-53-05's pre-emptive disclosure with a post-run record of what was written (operator, 2026-08-28)

Supersedes the approach D-53-05 settled on. The trade it made stands; what is received in
exchange changes.

- **The pre-emptive sentence is compressed to a plain statement of fact** — this grant enables
  enrichment and writes to HubSpot — and is **non-blocking**. The long "the HubSpot write is
  authorized BEFORE the enriched preview exists, so held rows and merge conflicts are
  authorized unseen" warning is retired as operator-facing text.
- **In its place: at the end of a run, list the HubSpot records actually written**, so the
  operator can review and amend them. Protection moves from *predicting* what might land to
  *showing* what did.
- **Why this is not a weakening.** 53-04 described the retired sentence as *"the whole of what
  you got for the protection you traded"* — i.e. the compensation was a warning nobody could
  act on until after the fact anyway. A concrete list of written records is actionable in a way
  the warning never was: HubSpot values can be amended after the write.
- **Load-bearing implementation constraint, recorded so it is designed rather than discovered:**
  the list must survive a **partial** run. A batch that dies at chunk 7 of 20 has already
  written records, and those must still appear. Under D-59-06 a revoked run also keeps writing
  to completion, so the list must reflect what a *revoked* run wrote too. This makes the list a
  **durable artifact written as records land**, not a summary printed at the end of a happy
  path. A design that only emits on clean completion fails exactly the cases the operator most
  needs it for.
- Open for the planner: where the list lives (run artifact, HubSpot note, or plugin-side
  record), and whether "amend" means anything more than "here are the ids, go look".

### D-59-08 — Resolve and propose, do not refuse outright (operator, 2026-08-28) — CROSS-CUTTING

Operator ruling, given during the Phase 53 walk after `extraction.py` dead-ended a row:
*"The identity rules surfaced are too strict, instead of immediate refusal, Claude operator
side should try to resolve and propose. The goal of this system is to guide and be assistive,
not just deterministic. Otherwise, why use AI?"*

**Applies to this and other flows** — it is not scoped to Phase 59's own work. Recorded here
because this is where it was taken; a planner should expect it to touch several lanes.

**What changes.** Where a row fails a gate today and the flow stops, Claude should first attempt
to RESOLVE the missing value, then PROPOSE it for the operator to confirm. Refusal becomes the
last resort, not the first response.

**What does NOT change — and this is the line that keeps it safe.** The no-invention rule's core
survives intact: **never silently fill a gap to get a row past a gate.** The change is
`refuse` -> `propose`, never `refuse` -> `guess`. A proposal the operator sees and confirms
preserves exactly the property the rule protects, because the failure mode it exists to prevent
is a fabricated value that lands *undetectably*. A value on screen awaiting a yes is not that.

**The distinction a planner must implement precisely — where a resolved value may come from:**

| Legitimate resolution sources | Illegitimate |
| --- | --- |
| HubSpot itself, read-only (the walk resolved `seriesfutsal.com` this way) | Claude's own recall about the person or company from training data |
| The operator's own statements earlier in the conversation | Inference from "companies like this usually…" |
| The enrichment waterfall's provider results | A plausible corporate email pattern (`first@company.com`) |
| Another field of the same row, by stated derivation (a slug, a domain from an email) | Anything the operator would have no way to check |

The right-hand column is still invention and stays forbidden. The left-hand column is lookup,
and lookup was never what the rule was aimed at.

**Provenance must not be laundered.** A Claude-resolved value carries provenance saying so —
never dressed as source-derived. An operator reading the row back must be able to tell which
fields came from their input and which from a resolution they approved. This is what keeps the
audit trail honest once refusals stop being the default.

**Evidence from the walk this ruling came out of (2026-08-28):**
- The refusal path was a genuine dead end: a LinkedIn URL yielded name + `linkedin_url` but no
  company, `extraction.py` rejected it for identity, and the flow simply stopped.
- The resolve path worked and cost nothing: a read-only HubSpot search found Series Futsal
  Victoria (`283816805830`, domain `seriesfutsal.com`), which was the exact handle the
  write-safety allowlist needed for a create. It was disclosed to the operator, not slipped in.
- Both halves of the ruling are therefore demonstrated, not hypothetical.

**Known text that must be amended, with the same recorded-edit discipline D-53-05 used**
(never deleted, never quietly weakened, the reason and date written into the file itself):
- `skills/contact-upload/extraction.md`'s no-invention rule currently states *"A row that gets
  rejected with a stated reason is the correct outcome"* and *"Never fill a gap to make a row
  satisfy the identity rule."* The second sentence survives verbatim. The first no longer
  describes the intended behaviour and must be rewritten to make rejection the last resort
  after a resolution attempt was made and either failed or was declined.
- Any contract test pinning that wording is re-pointed in the same commit, with the reason in
  the test body.

**Precedent already in the codebase, worth reusing rather than reinventing:** Phase 58's
propose mode (opt-in operator confirmation for ambiguous matches), `preingest`'s existing
`proposed` group and its `approve` / `deny` / `pick` / `email:` vocabulary, and the enrichment
backend's own `action: "proposed"` / `mode: "propose"` response shape. The mechanism for
"here is a candidate, confirm it" exists; this ruling widens where it is used.

**Interaction with FINDING 2 of the walk (`53-WALK-RECORD.md`).** Note for whoever plans this:
a propose flow makes silent enrichment loss worse, not better. If `merge_enriched` drops a
provider answer into `unanswered`, a resolve-and-propose flow will propose from nothing and
report "nothing known" about a row the backend answered fully. **Fix the merge defect before
widening propose behaviour**, or the assistive path inherits a silent data-loss bug.

### D-59-09 — Written-records concurrency: one artifact per `run_id` (operator, 2026-08-29)

Taken after the first execution pass shipped, when code review and goal verification both found
`written_records.append_chunk` had no protection against concurrent writers (gap 2 of 4,
`59-VERIFICATION.md`). Two shipped, independent processes can race the one shared path — an
operator's live session and `scheduled_arm.py`'s unattended cron poller — and `append_chunk`'s
replace-not-merge rule silently drops the loser's already-flushed chunk history. That understates
what actually landed in HubSpot, which is the exact failure category D-59-07 exists to prevent.

- **Decision: each run writes its own artifact keyed by `run_id`.** A reader globs and unions them.
- **Why this over a lock:** no contention and no stale-lock failure mode on a path that must never
  block a dispatch, and the replace-not-merge rule stops being a hazard by construction rather than
  by discipline — two runs never share a path, so there is nothing to merge and nothing to lose.
- **Rejected:** `flock` on the shared path (smaller reader-side change, but adds a blocking failure
  mode to the dispatch loop); per-run files plus a merged index (most robust, largest change — the
  index is a later addition if operators ask for one combined view).
- **Cost:** a reader-side change. Every consumer of the artifact must glob rather than open one path.

### D-59-10 — A records-write failure must never stop a dispatch (operator, 2026-08-29)

Taken at the same point, for gap 3. `WrittenRecordsError` is not one of the exception types
`dispatch_plan`'s loop catches, so it propagates and can abort an armed, in-progress dispatch;
`scheduled_arm.py` handles only `ArmingRefused` / `DisarmFailed`, so the unattended path would
crash with an unhandled traceback and no structured outcome. `scheduled_arm.py`'s own comment
claiming this cannot happen is stale and must be corrected in the same commit.

- **Decision: catch it in the loop as `DispatchError` already is, record the failure in the
  outcome, and keep writing chunks.** This honours D-59-06's promise, which is now shipped
  operator-facing text: once enrichment and writing start, the run continues until done.
- **The trade-off, stated so it is designed rather than discovered:** a run can now complete with
  an INCOMPLETE written-records list. That failure must be surfaced loudly in the outcome and to
  the operator — never swallowed. An artifact that is silently short is worse than one that is
  absent, because it reads as a complete account of what was written.
- **Rejected:** aborting the dispatch on an unrecordable write. Better for auditability in the
  abstract, but it contradicts D-59-06's promise and can strand a batch mid-run — trading a
  known, reportable gap in the record for an unknown, partial state in HubSpot.

### Claude's Discretion

- D-59-06's note wording and D-59-07's artifact location were the planner's to choose within the
  constraints stated above; both are now shipped.
- How the incomplete-list condition of D-59-10 is surfaced (outcome field, operator-facing line,
  or both) is the gap planner's to choose, provided it cannot be silent.

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

**53-04's open question is now CLOSED, not carried into the walk.** It asked whether revocation
at the next SEND is enough; D-59-06 answers yes, with a session-start note instead of a
grant-aware dispatch loop. The walk no longer has to decide it — step 5 just confirms the
behaviour matches what the note promises.

**Step 4's check changes under D-59-07.** Do NOT look for the long "authorized before the
enriched preview existed" sentence — that text is retired. What the walk confirms instead is
(a) the grant states plainly that it enables enrichment and writes to HubSpot, non-blocking,
and (b) whether anything today lists the records actually written at the end of a run. Expect
(b) to be ABSENT — that is the gap D-59-07 asks a plan to fill, and the walk's job is to
confirm it rather than assume it.

**A prediction the walk should test, found while scouting on 2026-08-28.** The chosen record is
a CREATE (a new contact from a LinkedIn URL), not an update to an existing record. The shared
write-safety gate is:

```js
if (!allowedDomains.length && !allowedIds.length) return false;  // empty allowlist denies everything
if (hsObjectId && allowedIds.indexOf(String(hsObjectId)) !== -1) return true;
if (domain && allowedDomains.indexOf(String(domain).toLowerCase()) !== -1) return true;
return false;
```

A record that does not exist yet **has no `hsObjectId`**, so it can only be allowlisted by
DOMAIN. For a contact sourced from a LinkedIn profile URL with no email, there may be no domain
to scope on either — in which case the gate denies the create and the grant cannot express it.
If that is what happens, it is exactly the composition break the walk exists to find: every
component correct, the composition unable to authorize the thing the operator asked for.
`ALLOW_HUBSPOT_CREATE` is a separate flag from `ALLOW_HUBSPOT_RECORD_WRITES` and must be
included in the grant (`allow_create`).

**Cost:** live HubSpot writes on the record(s) the operator names, plus a handful of n8n
executions against the 2,500/month budget.

**The record chosen for the walk (operator, 2026-08-28):**
`https://www.linkedin.com/in/joshua-fusco-481309247/` — create, enrich, and land in HubSpot.
This exercises both lanes of the D-53-05 grant in one pass, which is the composition nobody has
walked.

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

Nothing. The one open item at the end of the discussion (`ALLOW_REVIEW_SUBMIT`) was decided —
see D-59-05. The phase's own scope remains deliberately deferred pending the walk (D-59-01).
</open_question>
