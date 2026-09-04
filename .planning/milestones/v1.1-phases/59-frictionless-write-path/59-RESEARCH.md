# Phase 59: Frictionless write path - Research

**Researched:** 2026-08-28
**Domain:** Python test-fixture safety, Claude Code plugin lifecycle hooks, n8n dispatch/response
plumbing, operator-facing refusal-gate inventory (Claude-plugin skills)
**Confidence:** HIGH for D-59-04 and D-59-07 (all claims read directly from source and pytest
behaviour reproduced live in-sandbox); MEDIUM for D-59-06 (mechanism confirmed via a real
installed-plugin precedent, but never exercised inside *this* plugin); MEDIUM for D-59-08 (gate
inventory is representative, not exhaustive — the ruling is explicitly cross-cutting and a full
sweep is plan-sized work, not research-sized)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

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

> **Research note — this finding is FIXED as of this session.** Commit `9e603d6`, plugin
> release 0.20.0, 2026-08-28. Verified live in this research pass (see § FINDING 2 status
> below). Do not re-scope a fix for it; the phase's remaining work is what D-59-08 explicitly
> calls out — a resolve-and-propose flow built on top of the now-fixed merge must not itself
> reintroduce a silent-loss shape.

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

### Claude's Discretion

- Nothing yet. This phase has no implementation scope until the walk lands. D-59-06's note
  wording and D-59-07's artifact location are the planner's to choose within the constraints
  stated above.

### Deferred Ideas (OUT OF SCOPE)

- **Review-lane authority** — D-59-03, its own phase after the walk.
- **`dispatch_plan` grant-awareness** (chunk-granular revocation) — 53-04 already names it as
  its own phase; the walk decides whether it is needed.
- **Todo `2026-08-04-sweep-crontab-pins-a-versioned-plugin-path`** — surfaced by todo matching
  at 0.4; not folded. Unrelated to this phase's subject (the unattended sweep's crontab pins a
  versioned plugin path). Left in the backlog.

**Also explicitly out of scope per the orchestrator's task framing** (not from CONTEXT.md, but
binding for this research pass):
- `max_records_per_chunk` and the ~100s synchronous response window → Phase 55.
- Unifying ingest → enrich → create → associate into one flow → Phase 56.
- Refuse-before-start against the remaining monthly allowance → Phase 57.
- The review lane / `ALLOW_REVIEW_SUBMIT` replacement → Phase 60 (D-59-03). D-59-05 already
  removed `ALLOW_REVIEW_SUBMIT` from `.claude/settings.local.json` — done, not scope.
- The n8n write-safety gate nodes, the material-conflict judge gate, and the non-clobber merge
  policy — operator-confirmed load-bearing, deliberately untouched.
</user_constraints>

## Summary

This phase has four independent-but-related pieces of scope (D-59-04, D-59-06, D-59-07,
D-59-08) plus one candidate slice (finishing the halted GRANT-01 walk). None of them touches
n8n workflow JSON, none installs a new package, and none is UI/frontend work — this is entirely
Python test infrastructure, a Claude Code plugin lifecycle mechanism, and operator-facing
skill/script text in `operator-claude-plugin/`. The research below front-loads three things a
planner would otherwise discover mid-execution and have to re-plan around:

1. **D-59-04's own framing is imprecise and, taken literally, breaks a working test.** There is
   no registered pytest marker named `live` anywhere in this repo — no `pytest.ini`,
   `pyproject.toml`, or `[pytest]` marker block exists at all. The only "live" concept in the
   codebase is a locally-defined `pytest.mark.skipif(os.getenv("RUN_LIVE_PARITY") != "true", ...)`
   object, redefined per file, in exactly two files
   (`tests/test_scoring_parity.py:51-54`, `tests/test_review_flag_eq_filter.py:28-31`). A
   conftest fixture that tries to detect "a test is `@live`-marked" via
   `request.node.get_closest_marker("live")` will never find one — the applied mark's real name
   is `skipif`, not `live`. Worse: **pytest runs autouse fixtures for a test that is NOT
   skipped, before the test body — including a `RUN_LIVE_PARITY=true` live test** (reproduced
   live in this session, see § D-59-04 below). An unconditional strip breaks the two existing
   live tests the moment anyone actually runs them with `RUN_LIVE_PARITY=true`. The fixture must
   gate on the SAME env var the existing tests already use (`RUN_LIVE_PARITY`), not on a marker
   that doesn't exist.
2. **FINDING 2 is verified fixed in this session, at the exact call site the walk found broken.**
   `preingest.merge_enriched` (`operator-claude-plugin/scripts/preingest.py:528-537`) now raises
   `MergeError` on a non-dict response item instead of silently indexing it as `row_id: None`.
   Do not re-diagnose or re-fix it.
3. **D-59-07's artifact needs to survive a crash of the calling process, not just a caught chunk
   failure.** `chunking.dispatch_plan` already accumulates results and raw per-chunk response
   bodies inside its loop as it goes (`operator-claude-plugin/scripts/chunking.py:265-313`), and
   `DispatchOutcome.responses` is documented as one raw body per chunk sent — but that
   accumulation lives in a plain Python list held in memory, returned once at the end of the
   function. A chunk failure the loop itself catches (timeout, non-2xx, unreadable body) already
   continues past and is captured in `results`; what does NOT survive is the calling *process*
   being interrupted mid-loop (a killed session, an uncaught exception). To satisfy D-59-07's
   "die at chunk 7 of 20" requirement, the write-record list must be flushed to a durable file
   **after each chunk**, not assembled and written once at the end.

**Primary recommendation:** treat D-59-04, D-59-06, D-59-07 as three small, independent,
mechanically well-scoped changes (conftest fixture; a new `hooks/hooks.json` + script;
an atomic-append durable-artifact writer threaded into `dispatch_plan`'s loop). Treat D-59-08 as
a scoping/inventory task first (which gates get touched, in what order) and an actual rewrite of
`extraction.md`'s two no-invention passages second — do not let it expand into every refusal gate
in the plugin in one plan; the ruling itself says other lanes are expected to pick this up later.
Decide explicitly, as a first planning step, whether this phase's plan set also completes the
halted GRANT-01 walk (cheap now that FINDING 2 is fixed) or leaves that for a dedicated
walk-only plan.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Ambient-credential test guard (D-59-04) | Test infrastructure (pytest conftest) | — | Pure Python fixture; no runtime tier |
| Session-start disclosure note (D-59-06) | Claude Code plugin lifecycle (hook) | Operator-facing text (skill/script) | Hook script emits context; the *text* is a skill-adjacent concern |
| Post-run written-records artifact (D-59-07) | Plugin-side orchestration (`chunking.dispatch_plan`) | Local durable file (plugin's existing `durable_paths` home) | The data becomes known exactly where `dispatch_plan` already receives each chunk's response body; n8n is not involved |
| Resolve-and-propose widening (D-59-08) | Operator-facing skill contract (`extraction.md`, `preingest.py`) | Plugin script layer (`extraction.py`, `company_domain.py`) | The gate lives client-side (Claude-as-extractor + validator scripts); the backend/n8n gates are untouched |
| Completing the GRANT-01 walk | Operator conversation (manual/scripted walk) | Plugin scripts (unchanged) | Verification activity, not new capability |

No capability in this phase touches the n8n workflow tier, the HubSpot write-safety gate nodes,
or the ICP scoring engines — consistent with the CONTEXT's explicit "deliberately untouched"
list.

## Project Constraints (from CLAUDE.md)

- **§0/§13 orchestration boundary:** all complex orchestration lives in n8n or the plugin, never
  in HubSpot workflow automation. Not directly implicated here — nothing in this phase adds
  HubSpot-side automation.
- **§4.0 `lv_`-prefix as-built delta:** any code this phase writes that reads or writes HubSpot
  company/contact control properties must use the live `lv_`-prefixed names, never the bare
  names documented in the original §4 tables. D-59-07's artifact reads `hs_object_id` off
  n8n response bodies (verified below), not a `lv_*` property, so this constraint is not
  triggered by this phase's likely implementation — flag it only if a plan ends up reading a
  scoring/control property directly.
- **Phase 46 parity rule** (a shared predicate lands in BOTH `src/icp_scoring.py` and
  `scripts/build_cloud_workflows.py` in one commit; never hand-edit `n8n/wf_enrichment_cloud.json`):
  not triggered — none of D-59-04/06/07/08 touches scoring logic or n8n workflow JSON. Restated
  here only as a guardrail in case a plan drafts touching `Build Ingest Response` or
  `Decide Company Action` (both generated by `scripts/build_cloud_workflows.py`, confirmed in
  this research — see § D-59-07 below): if a plan does touch either, it must go through the
  generator script and both engines, never a hand-edit of the deployed JSON.
- **Test commands of record** (verified live in this session):
  `.venv/bin/python -m pytest` (pytest 9.1.1, Python 3.14.5) and
  `node --test tests/n8n/*.test.mjs` (node v24.10.0; directory form of the glob is broken on
  node 24, per project memory, confirmed still node 24 in this environment).

## Standard Stack

No new external package is introduced by this phase. All four decision areas are implemented
with what is already a project dependency:

| Library | Version (installed, verified) | Purpose | Why no alternative needed |
|---------|------|---------|----------------------------|
| `pytest` | 9.1.1 [VERIFIED: `.venv/bin/python -m pytest --version`] | D-59-04's conftest fixture, `RUN_LIVE_PARITY` skipif convention | Already the test framework; no marker plugin needed — a bare `autouse` fixture plus an env-var check is stdlib-pytest, no `pytest-env`/`pytest-dotenv` |
| Claude Code plugin hooks (`hooks/hooks.json`, `SessionStart`) | N/A (host feature, not a package) [VERIFIED: live precedent, `~/.claude/plugins/marketplaces/stz-marketplace/hooks/hooks.json`, and this very session's own injected "PONYTAIL MODE ACTIVE" context] | D-59-06's session-start note | Native platform feature — no library needed |
| Python stdlib `json` / `pathlib` + the plugin's own `durable_paths.py` (`_atomic_write_0600`) | n/a | D-59-07's durable written-records artifact | Reuse the plugin's existing atomic-write primitive (`operator-claude-plugin/scripts/durable_paths.py`) rather than adding a file-locking library |

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| Env-var-gated `RUN_LIVE_PARITY` skip check in the new conftest fixture | Register a real `@pytest.mark.live` marker in a new `pyproject.toml`/`pytest.ini` and rewrite the two existing `live = pytest.mark.skipif(...)` sites to use it | More "correct" pytest idiom, but a bigger diff (touches 2 existing files + adds a repo-wide pytest config that has never existed) for no behavioural gain — the existing env-var convention already works and is already documented as a deliberate choice (D-11 / 40-RESEARCH.md A3, see `tests/test_scoring_parity.py:48-50`) |
| A `SessionStart` plugin hook for D-59-06 | A line added to every skill's own `SKILL.md` telling Claude to mention run-to-completion behaviour "when relevant" | Hook is reliable and shown once per session; the SKILL.md-instruction approach is what the plugin already avoids elsewhere (relies on Claude remembering, not on structural guarantee) — matches this codebase's stated preference for "by construction rather than by discipline" (`operator-claude-plugin/tests/conftest.py:8-11`) |
| A single durable JSON file for D-59-07, updated in place | A HubSpot Note (engagement) written per record | No existing precedent in this codebase for the HubSpot-Note route (`grep` for `engagements`/`hs_note_body` returns nothing); a local durable file reuses `durable_paths.py`'s existing atomic-write machinery and needs no new HubSpot scope. Trade-off: a HubSpot Note attaches to the record the operator is already looking at, a local file needs the operator to ask for it — planner's call, not decided here (per D-59-07's own "open for the planner") |

**Installation:** none — no new dependency to add to `requirements.txt` or
`operator-claude-plugin/requirements.txt`.

## Package Legitimacy Audit

Not applicable — this phase installs no external packages.

## Architecture Patterns

### System Architecture Diagram — where D-59-07's data already flows

```
operator: "send this batch"
        │
        ▼
enrich-records / contact-upload / enrich-before-ingest  SKILL.md
        │  (builds a ChunkPlan via chunking.plan_chunks)
        ▼
chunking.dispatch_plan(plan, providers, armed, config)
        │
        │  for each chunk, IN ORDER:
        ├─► enrichment.build_envelope(chunk, providers)
        ├─► enrichment.dispatch_enrichment(envelope, armed, config, transport)
        │        │
        │        ▼
        │   n8n webhook  →  {contact,company} ingest/enrich workflow
        │        │            (per-row node: "Build Ingest Response" for
        │        │             contacts — action/contact_id/hs_object_id/
        │        │             email/company_id/association/reason)
        │        ▼
        │   body  (one raw JSON blob for the whole chunk —
        │          array of per-row items, or a bare dict for one row)
        │
        ├─► results.append(ChunkResult(index, rows, ok, reason))   [in-memory]
        ├─► responses.append(body)                                 [in-memory]
        │        ▲
        │        └── D-59-07's artifact must intercept HERE, per chunk,
        │            flushed to disk before the loop moves to the next
        │            chunk — not read back out of the returned
        │            DispatchOutcome after the whole loop finishes.
        │
        └─► (loop continues even on a chunk failure — D-12)
        │
        ▼
DispatchOutcome(results=tuple(...), responses=tuple(...), failed_batch=...)
        │
        ▼
caller flattens responses, joins by row_id → preingest.merge_enriched (fixed, see below)
```

### Recommended structure for D-59-07 (no new files needed by default)

```
operator-claude-plugin/scripts/
├── chunking.py         # dispatch_plan's loop — add an optional per-chunk
│                        # "on_chunk_written" callback OR inline artifact-append
│                        # call here (smallest diff: no new module)
├── durable_paths.py     # already provides resolve_state_path() + _atomic_write_0600
└── written_records.py   # ONLY if the artifact's read/format logic grows past a
                          # few lines — otherwise fold into chunking.py or a
                          # thin wrapper module the planner names
```

### Pattern: the `no_network` / ambient-credential-guard idiom (precedent for D-59-04)

**What:** an `autouse=True` pytest fixture that removes ambient capability (network access, or
here, credentials) "by construction rather than by discipline" — the plugin's own stated
rationale.
**When to use:** exactly D-59-04's case — a whole test-suite-wide safety net that must not
depend on every future test author remembering to opt in.
**Example — the existing precedent, read directly from source:**
```python
# operator-claude-plugin/tests/conftest.py:575-592 — VERIFIED, read this session
@pytest.fixture(autouse=True)
def no_network(monkeypatch, request):
    """Any requests.post/request/Session.request call inside a test raises immediately.

    Autouse so a later plan's test cannot opt out by forgetting to request a fixture — the
    guard applies to every test in this suite by construction, not by discipline.
    """
    test_name = request.node.name

    def _blocked(*args, **kwargs):
        raise RuntimeError(
            f"Network access blocked in test '{test_name}': plugin tests must use "
            "stub_transport instead of a real requests call."
        )

    monkeypatch.setattr(requests, "post", _blocked)
    monkeypatch.setattr(requests, "request", _blocked)
    monkeypatch.setattr(requests.Session, "request", _blocked)
```
**Difference the planner must design around:** this plugin fixture is UNCONDITIONAL — the
plugin suite has no live tests to carve out. The root `tests/` suite DOES have two live tests
(`RUN_LIVE_PARITY=true`), so D-59-04's fixture cannot be a straight copy; it needs the
`RUN_LIVE_PARITY` carve-out described below.

### Pattern: Claude Code plugin `SessionStart` hook (precedent for D-59-06)

**What:** a plugin ships `hooks/hooks.json` naming a `SessionStart` matcher; the host runs the
named script at session start (and session resume) and injects its stdout as additional context
for Claude to read and relay.
**When to use:** exactly D-59-06's case — informing the operator of a standing behaviour once,
without a per-action prompt.
**Example — a real, installed, working precedent, read this session:**
```json
// ~/.claude/plugins/marketplaces/stz-marketplace/hooks/hooks.json — VERIFIED, installed and
// live in this very environment (this session's own transcript carries a SubagentStart
// hook's injected text, "PONYTAIL MODE ACTIVE", from an equivalent mechanism)
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh\""
          }
        ]
      }
    ]
  }
}
```
`operator-claude-plugin/` currently has **no `hooks/` directory at all**
[VERIFIED: `find operator-claude-plugin -maxdepth 1 -type d` this session lists
`.pytest_cache config tests scratch scripts .claude-plugin skills` — no `hooks`]. This is new
infrastructure for the plugin, not an extension of an existing mechanism.

**How the hook's output actually reaches the human operator — inferred, not directly observed
in this plugin.** A `SessionStart` hook's stdout becomes context available to Claude, not text
guaranteed to be echoed verbatim to the user. The existing convention THIS plugin already uses
for comparable machine-to-Claude-to-operator relay is explicit: `initialize/SKILL.md` step 1
says *"Read its output back to the operator in your own words"* — i.e. the established pattern
in this codebase is Claude paraphrasing structured tool output for the human, not verbatim
echo. A session-start hook script for D-59-06 should therefore likely emit an instruction
("tell the operator: ...") rather than assume the raw text is shown, mirroring that
convention — **this is a design choice for the planner, flagged here as inferred rather than
independently confirmed**, since no existing hook in this specific plugin has been observed
firing end-to-end.

### Pattern: resolve-then-propose (precedent for D-59-08)

**What:** where a client-side gate would otherwise refuse outright, a resolution step attempts
a read-only lookup first, and on success routes the row into an existing "confirm before
committing" group instead of straight rejection.
**When to use:** D-59-08's cases — the identity gate in `contact-upload/extraction.md`, and any
other operator-facing gate the planner's inventory turns up.
**Existing, working precedent in this exact codebase — company-domain resolve/confirm/decline,
Phase 58:**
```python
# operator-claude-plugin/scripts/company_domain.py — VERIFIED, read this session
# Phase 58's domain confirm/decline lane (INPUT-03): a company row Claude (or the backend's
# research) resolved a candidate domain for is not silently written — it is proposed, and
# the operator must confirm, correct, or decline before it becomes part of the envelope.
#
# apply_domain_decisions(proposals, resolved) -- never mutates input; DomainDecisionError raised
# for: no decision recorded, an unrecognized decision value, or a decision naming a row that was
# never proposed. Vocabulary: confirm / correct / DECLINE_DOMAIN sentinel.
```
Also present and reusable: `preingest.py`'s `proposed` / `auto_matched` / `unmatched` /
`unchecked` grouping (`classify_matches`, `resolve_proposed`), and the enrichment backend's own
`action: "proposed"` / `mode: "propose"` response shape (confirmed live in the walk record,
`53-WALK-RECORD.md` Step 7: `action: proposed / mode: propose / needs_review: true`). D-59-08
does not need a new mechanism — it needs `extraction.py`'s identity gate wired to reach one of
these instead of terminating in `rejected`.

### Anti-Patterns to Avoid

- **Checking `get_closest_marker("live")` in the D-59-04 fixture.** No such marker is ever
  applied. Every `@live`-decorated test in this repo carries a `skipif` mark, not a `live`
  mark — `live` is a Python variable name, not a pytest marker name. A fixture written against
  the marker name will silently never find a match and will (depending on the fixture's default
  branch) either always strip or never strip, neither of which is the intended behaviour.
- **Writing D-59-07's artifact only from the value `dispatch_plan` returns.** `DispatchOutcome`
  is constructed and returned in one statement after the `for` loop completes
  (`chunking.py:309-313`). A crash of the calling process between chunk 7's completion and
  chunk 8's start loses everything accumulated in `results`/`responses` if the artifact write
  happens only at that final point. The per-chunk write must happen inside the loop, immediately
  after `responses.append(body)`.
- **Assuming `Decide Company Action`'s output IS the write confirmation.** The company-side
  fixture read this session (`execution_enrichment.json`) shows `hs_object_id: null` for a row
  whose `action` is `"create"` — that is the pre-write DECISION, not proof a company was
  created. For companies, the actual created id is not knowable from that node alone; the
  contact-ingest lane's `Build Ingest Response` node (below) is the one place this research
  found an actual post-write `hs_object_id` being resolved and returned synchronously. A planner
  building D-59-07 must check, per object type and per lane, whether the response body it reads
  reflects a decision or a confirmed write — do not assume parity between the contacts and
  companies lanes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Detecting whether a test intends to hit live services | A new `@pytest.mark.live` marker + `pyproject.toml` marker registration | The existing `RUN_LIVE_PARITY` env-var convention (`os.getenv("RUN_LIVE_PARITY") != "true"`) | Already used, already documented as a deliberate choice (D-11), zero new config surface |
| Emitting a message at session start | A skill instruction telling Claude to "remember to mention" the note | A `hooks/hooks.json` `SessionStart` hook | Structural guarantee vs. relying on Claude's own memory — matches this codebase's stated "by construction, not discipline" principle |
| Atomic durable-file writes for D-59-07 | A new file-locking / write-then-rename helper | `operator-claude-plugin/scripts/durable_paths.py`'s existing `_atomic_write_0600` and `resolve_state_path()` | Already the plugin's one precedent for durable local state (`artifact_store.py`); reuse rather than duplicate the atomic-write logic |
| Joining enrichment responses back onto rows | A new indexing/merge function for D-59-08's resolve-and-propose flow | `preingest.merge_enriched`'s existing `row_id`-keyed join (now fixed) and its `proposed`/`unanswered`/`conflicts` vocabulary | The join-by-id discipline (never positional) is exactly what FINDING 2 exists to protect; a parallel ad hoc join would reopen the same class of bug |

**Key insight:** every one of this phase's four decision areas already has a working precedent
somewhere in this exact codebase or this exact host environment (RUN_LIVE_PARITY skipif,
`no_network` fixture, `hooks/hooks.json`, `durable_paths.py`, `company_domain.py`,
`preingest.py`'s propose vocabulary). None of this phase's scope requires inventing a new
mechanism — the work is composing existing mechanisms in new places.

## Runtime State Inventory

Not applicable — this is not a rename/refactor/migration phase. No stored data, live service
config, OS-registered state, secrets, or build artifacts are renamed or relocated by any of
D-59-04/06/07/08.

## Common Pitfalls

### Pitfall 1: autouse fixtures run for tests that pass their skip check — proven live this session

**What goes wrong:** a conftest fixture assumed to run "unless a test is live-marked" is
actually invoked for a `RUN_LIVE_PARITY=true` test too, since that test is NOT skipped.
**Why it happens:** pytest evaluates `skipif` conditions before fixture setup ONLY for the
skip decision itself; if the condition evaluates to "do not skip," fixture setup — including
every applicable `autouse` fixture — proceeds normally before the test body runs.
**How to avoid:** gate the strip on the identical condition the existing live tests use
(`os.getenv("RUN_LIVE_PARITY") != "true"`), so the fixture's own branch mirrors the skip
condition rather than trying to read a marker that isn't there.
**Warning signs:** `RUN_LIVE_PARITY=true .venv/bin/python -m pytest tests/test_scoring_parity.py`
starts failing with `AnthropicError`/`HubSpot 401`-shaped errors that were not there before
D-59-04 landed — that is this exact pitfall, not a new bug in the test itself.
**Reproduced empirically this session** (isolated probe, not this repo's real fixtures):
an autouse fixture prints nothing for a skipped test, and DOES run (and would strip
credentials) for the same test invoked with its opt-in env var set.

### Pitfall 2: D-59-07's data source differs by object type and by lane

**What goes wrong:** building the written-records artifact against `Decide Company Action`'s
output (or its equivalent) for BOTH contacts and companies, and reporting a company as written
before the actual create/update HTTP call has run.
**Why it happens:** the fixture available for companies in this repo's test data
(`execution_enrichment.json`) is a snapshot of the DECISION node, not the write-confirmation —
its `create` row carries `hs_object_id: null` by construction, because the create hasn't
happened yet at that point in the graph.
**How to avoid:** for the contacts/ingest lane, read `hs_object_id` off `Build Ingest Response`'s
output (`scripts/build_cloud_workflows.py:471-520`, confirmed to compute a real post-association
`contact_id`/`hs_object_id` per row). For the companies lane, the planner needs to locate (or
add, if it does not already exist) an equivalent post-write node before treating any id as
confirmed-written — this research did not find one; flagged as an open question below.
**Warning signs:** the artifact lists a company id that a subsequent HubSpot read shows was
never actually created.

### Pitfall 3: `merge_enriched` requires flattening `dispatch_plan(...).responses` before use

**What goes wrong (now fixed, but the shape is still easy to misuse in new code):**
`chunking.dispatch_plan(...).responses` is a tuple of ONE RAW BODY PER CHUNK — each element may
itself be a list. Passing it directly into any function expecting a flat, per-row list (as
`merge_enriched` used to accept silently) either raises now (`MergeError`, since the 0.20.0 fix)
or, in any NEW code written for D-59-07/D-59-08, could reintroduce the same silent-loss shape if
it does its own ad hoc indexing instead of reusing the fix.
**Why it happens:** `dispatch_enrichment`'s return value is n8n's raw `respondWith:
allIncomingItems` body for a chunk, not a per-row envelope — the two shapes (list-of-chunks vs.
flat list-of-rows) look similar enough at a glance to pass code review.
**How to avoid:** always flatten with the documented idiom before touching row-level data:
`[item for body in outcome.responses for item in (body if isinstance(body, list) else [body])]`
(quoted verbatim from `chunking.py:93-96`, itself already followed by
`preingest.rerequest_unanswered`).
**Warning signs:** a merge/report function that receives `outcome.responses` as a parameter name
literally called `responses` (plural, chunk-shaped) and iterates it as if each element were one
row.

## Code Examples

### D-59-04 — verified failure mode of a naive fixture, and the fix's shape

```python
# What this session reproduced, isolated from the real repo (do not copy verbatim — this is
# the minimal repro, not the actual fixture to ship):
#
#   conftest.py:
#     @pytest.fixture(autouse=True)
#     def marker(request):
#         print(f"FIXTURE RAN for {request.node.name}")
#
#   test_probe.py:
#     live = pytest.mark.skipif(os.getenv("RUN_IT") != "true", reason="opt-in")
#     @live
#     def test_skipped(): ...
#
# WITHOUT RUN_IT=true:  fixture does NOT run for test_skipped (test is skipped before setup)
# WITH    RUN_IT=true:  fixture DOES run for test_skipped, before the test body executes
#
# Conclusion for D-59-04's real fixture: it must check the SAME env var
# (RUN_LIVE_PARITY) the two real live tests use, and skip stripping when it is "true" —
# not attempt to detect a "live" marker, which does not exist in this repo's pytest config.
```

### D-59-04 — the two client-construction sites the guard protects, confirmed with exact lines

```python
# src/classifier_haiku.py:47,50-57 — VERIFIED, read this session
api_key = os.getenv("ANTHROPIC_API_KEY")
...
if not api_key:
    return {"decision": "stage_only", "confidence": 50,
            "reason": "No Anthropic API key configured; conservative fallback."}
client = Anthropic(api_key=api_key)   # line 57 — only reached if api_key is truthy

# src/validator_sonnet.py:23,26-36 — VERIFIED, read this session
api_key = os.getenv("ANTHROPIC_API_KEY")
...
if not allow or not api_key:
    return {"decision": "needs_review", ..., "validation_status": "human_review_required"}
client = Anthropic(api_key=api_key)   # line 36 — only reached if api_key is truthy

# src/web_research.py:119,124-126 — VERIFIED, read this session
if os.getenv("USE_MOCK_WEB_RESEARCH", "true").lower() == "true":
    return mock_claude_web_research(record)          # default path in any test that
                                                       # never sets USE_MOCK_WEB_RESEARCH
from anthropic import Anthropic
client = Anthropic()   # line 126 — reads ANTHROPIC_API_KEY from the environment directly,
                        # no explicit api_key kwarg, no local guard against a missing key
```
The first two sites are already self-guarding (no key → no client, no network) as long as
`ANTHROPIC_API_KEY` is genuinely absent from `os.environ` at call time — exactly what stripping
it accomplishes. `web_research.py`'s live branch has NO local guard at all; it relies entirely
on `USE_MOCK_WEB_RESEARCH` defaulting to `"true"` when unset, which is also exactly the
condition the prior credential-leak bug (`89c9871`, a stray `load_dotenv()` at test-collection
time) broke — confirming the ROADMAP's stated rationale is accurate, not speculative.

### D-59-04 — confirmed: no pytest marker config exists anywhere in this repo

```
$ grep -rln '\[pytest\]' . )                 # 0 hits (excluding .venv and node_modules)
$ find . -iname pytest.ini -o -iname pyproject.toml -o -iname setup.cfg   # only .venv/pyvenv.cfg
$ grep -rn 'RUN_LIVE\b' tests/*.py            # exactly 2 files, both "RUN_LIVE_PARITY"
```

### D-59-06 — the exact hooks.json shape a real, installed plugin uses

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {"type": "command",
           "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh\""}
        ]
      }
    ]
  }
}
```
Source: `~/.claude/plugins/marketplaces/stz-marketplace/hooks/hooks.json`, installed and active
in this exact environment. `${CLAUDE_PLUGIN_ROOT}` resolves at the plugin's install location —
the same versioned-path caveat this project's own memory already flags for cron
(`sweep-crontab-pins-a-versioned-plugin-path`) does NOT apply here, since Claude Code resolves
this variable itself at hook-invocation time rather than the plugin hard-coding a path.

### D-59-07 — the write-confirmation shape that already exists for contacts

```javascript
// scripts/build_cloud_workflows.py:471-520 (BUILD_INGEST_RESPONSE) — VERIFIED, read this
// session. This is the source the generator writes into the deployed n8n "Build Ingest
// Response" code node — the per-row synchronous response body for the contact-ingest lane.
return decided.map((row) => {
  ...
  return { json: {
    action: row.action,
    outcome: row.outcome || null,
    contact_id: contactId,
    hs_object_id: contactId,
    email: email || null,
    company_id: row.company_id || null,
    company_match: row.company_match || null,
    association,
    reason: row.reason || null,
    email_status: row.email_status || null,
  }};
});
```
Every row Decide Action produced appears here — including held/gated rows — per its own
comment: *"A row that never reached the association subgraph still appears here — the
alternative is a response that silently omits held and gated rows."* This is the body
`enrichment.dispatch_enrichment` receives and `chunking.dispatch_plan` appends to `responses`
for a contacts-lane chunk.

### D-59-07 — `dispatch_plan`'s loop, the exact point an artifact write must hook in

```python
# operator-claude-plugin/scripts/chunking.py:279-313 — VERIFIED, read this session
for index, chunk in enumerate(plan.chunks):
    ...
    body = enrichment.dispatch_enrichment(envelope, armed, config, transport=watcher)
    ...
    responses.append(body)          # <-- durable write must happen right here, per chunk,
                                     #     not after the loop via the returned DispatchOutcome
    if reason is not None:
        failed_chunks.append(chunk)

return DispatchOutcome(
    results=tuple(results),
    failed_batch=failed_batch(failed_chunks),
    responses=tuple(responses),
)
```

### D-59-08 — the exact two passages that must be amended, verbatim, with line numbers

```
# operator-claude-plugin/skills/contact-upload/extraction.md:27-30 — VERIFIED, read this session
3. **Never fill a gap to make a row satisfy the identity rule** (a non-blank `email`, or all
   three of `firstname`/`lastname`/`company`). A row that gets rejected with a stated reason is
   the correct outcome. A row you completed just to get it past that check is not — it is
   invention with extra steps.

# operator-claude-plugin/skills/contact-upload/extraction.md:364-368 — VERIFIED, read this session
The rule at the top of this file governs company rows exactly as it governs contact rows: a
field the source does not show is left out of the row entirely, a value the source renders
unclearly goes in the ambiguity list rather than the row, and a company name is never invented
to make a nameless row pass the identity check. A company row rejected with a stated reason is
the correct outcome here too — never fill a gap just to get it past the check.
```
Per D-59-08: the "Never fill a gap..." sentence in both passages survives verbatim. The
"rejected with a stated reason is the correct outcome" sentence in both passages is the one that
needs rewriting to make rejection the last resort after an attempted resolve-and-propose.

**Contract-test search result — no test found pinning either sentence.**
`grep -rln "rejected with a stated reason" tests/*.py operator-claude-plugin/tests/*.py
scripts/*.py operator-claude-plugin/scripts/*.py` returns nothing in either test directory
[VERIFIED this session]. The CONTEXT's instruction to "re-point [any pinning test] in the same
commit" therefore likely has zero tests to re-point for THIS specific wording — do not spend
planning effort hunting for one; verify at implementation time rather than assuming one exists.

### D-59-08 — existing resolve/propose precedent to extend, not reinvent

```python
# operator-claude-plugin/scripts/company_domain.py — module docstring, VERIFIED read this
# session: "Phase 58's domain confirm/decline lane (INPUT-03): a company row Claude (or the
# backend's research) proposed a domain for is not silently written — it is proposed, and the
# operator must confirm, correct, or decline before it becomes part of the envelope."
# Functions: apply_domain_decisions(proposals, resolved), needs_research(...),
# decline_research(...), to_envelope_spec(...). DomainDecisionError raised on: no decision
# recorded for a row, an unrecognized decision, a decision naming a row never proposed.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `merge_enriched` silently filed correct provider answers as `unanswered` when handed a nested per-chunk response shape | `merge_enriched` raises `MergeError` immediately on a non-dict response item, naming the exact flattening idiom to use | Commit `9e603d6`, plugin release 0.20.0, 2026-08-28 [VERIFIED: `preingest.py:528-537` read this session] | The `enrich-before-ingest` flow's step 5 now fails loudly instead of silently discarding paid-for enrichment; this phase's D-59-08 work can build on a merge that is now trustworthy |
| D-53-05's pre-emptive "authorized before the enriched preview exists" disclosure | Superseded by D-59-07 — a plain non-blocking statement plus a post-run written-records list | Operator ruling, 2026-08-28 | Changes what the operator sees at grant-open time; the walk's step 4 check (`53-04-PLAN.md`) must be re-read against the NEW text, not the retired sentence — already noted in `59-CONTEXT.md` § specifics |

**Deprecated/outdated:**
- The long D-53-05 warning sentence quoted in `53-WALK-RECORD.md` Step 6 ("This grant covers
  both lanes at once...") is explicitly retired operator-facing text per D-59-07 — a planner
  reading the walk record for wording to preserve must not carry that specific sentence forward.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `SessionStart` hook's stdout reaches the human operator only via Claude relaying it in its own words (matching `initialize/SKILL.md`'s established convention), not by verbatim display | Architecture Patterns — session-start hook | If Claude Code actually echoes hook stdout verbatim to the transcript, the hook script's text can be written for a human reader directly instead of as an instruction to Claude; a plan built on the wrong assumption may produce a note that reads oddly either way (too instructional if verbatim, too terse if relayed) — low severity, easily corrected once the hook is actually exercised |
| A2 | No equivalent of `Build Ingest Response`'s post-write `hs_object_id` resolution exists yet for the **companies** lane (this research did not find one; `execution_enrichment.json`'s `Decide Company Action` fixture shows only a pre-write decision) | Common Pitfalls — Pitfall 2; Architecture Patterns | If such a node/response DOES exist under a name this research didn't grep for, D-59-07's planner may spend time building something redundant — or, if it truly doesn't exist, the artifact's company coverage needs either a new n8n node (Phase 46 parity implications) or a companies-specific follow-up HubSpot read to confirm what was actually written |
| A3 | D-59-07's artifact is best implemented plugin-side (a local durable file), not as a HubSpot Note — inferred from the total absence of any HubSpot-Note/engagement code in this codebase, not from an explicit operator ruling | Standard Stack — Alternatives Considered | If the operator actually wants the record visible IN HubSpot (their primary working surface), a plugin-side-only file may under-deliver on D-59-07's "operator can review and amend" framing; this is explicitly left open for the planner in D-59-07 itself, so the risk is bounded |

**If this table is empty:** N/A — see above.

## Open Questions

1. **Does a company-create write-confirmation node exist anywhere in the deployed n8n
   workflows, equivalent to the contacts lane's `Build Ingest Response`?**
   - What we know: the contacts/ingest lane resolves and returns a confirmed `hs_object_id`
     post-write, per row, synchronously (`scripts/build_cloud_workflows.py:471-520`, verified).
     The companies fixture available in this repo's test data shows only pre-write decisions.
   - What's unclear: whether CLAUDE.md §13.0/§13.0.1's "companies branch resolves the same two
     keys" text implies a parallel confirmed-write response exists for companies too, or whether
     company creation genuinely has no equivalent synchronous confirmation today.
   - Recommendation: the planner should grep `scripts/build_cloud_workflows.py` for the
     companies-branch equivalent of `BUILD_INGEST_RESPONSE` before committing to a design that
     assumes symmetry between the two lanes; if none exists, D-59-07's companies coverage may
     need its own small addition (through the generator script, per the Phase 46 parity rule)
     rather than reuse.

2. **Should the D-59-04 fixture ALSO guard `USE_MOCK_WEB_RESEARCH` / `DRY_RUN` /
   `USE_MOCK_PROVIDERS`, given `web_research.py`'s live branch has no local key-guard of its
   own?**
   - What we know: `web_research.py:126`'s `Anthropic()` call has no explicit `api_key=`
     argument and no `if not api_key:` guard before it — it relies entirely on
     `USE_MOCK_WEB_RESEARCH` defaulting to `"true"` when unset. Stripping `ANTHROPIC_API_KEY`
     alone still protects this site (the SDK raises `AnthropicError` at construction with no
     key found), so the CONTEXT's stated scope (strip the two credential vars only) is
     sufficient on its own.
   - What's unclear: whether the operator/planner wants defense-in-depth against a
     `USE_MOCK_WEB_RESEARCH=false` leak too (the exact prior-bug shape), even though the
     credential strip already makes that leak fail loudly rather than silently succeed.
   - Recommendation: ship the credential-strip only, as CONTEXT specifies — it already converts
     the dangerous case (silent billable call) into a loud one (`AnthropicError` at construction).
     Flag this as a possible but non-blocking hardening follow-up, not phase scope.

3. **Does this phase's plan set also complete the halted GRANT-01 walk (re-run past the point
   FINDING 2 halted it, now that it's fixed), or does that stay a separate, later verification
   activity?**
   - What we know: the CONTEXT explicitly names this as "a live candidate for this phase's
     first end-to-end slice," names the cost (live HubSpot writes on the walk's chosen record,
     `joshua-fusco-481309247`), and notes the installed plugin cache is still pre-0.20.0 — the
     operator must update the plugin before any re-run would exercise the fix.
   - What's unclear: whether the planner should sequence "operator updates plugin, then Claude
     completes the walk" as an executable task inside this phase's plan, or leave it as a
     post-phase verification step outside the plan's own task list.
   - Recommendation: the planner should decide this explicitly as a first step (it changes
     whether the phase has a live-write task at all), not leave it implicit.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pytest | D-59-04 (conftest fixture) | ✓ [VERIFIED] | 9.1.1 | — |
| Python | all four decision areas | ✓ [VERIFIED] | 3.14.5 (`.venv`) | — |
| node | regression gate (`node --test tests/n8n/*.test.mjs`) — only if a plan touches n8n code (none of D-59-04/06/07/08 currently require this) | ✓ [VERIFIED] | v24.10.0 | — |
| Claude Code plugin `hooks/hooks.json` support | D-59-06 | ✓ [VERIFIED: live precedent from another installed plugin in this same environment] | host feature, no version to pin | none needed |
| Installed operator-claude-plugin version (marketplace cache) | Completing the GRANT-01 walk (open question 3) | ✗ pre-0.20.0 confirmed stale in the walk record; not re-verified live in this research pass | unknown until operator updates | Operator must run the plugin update before any re-walk exercises the FINDING-2 fix |

**Missing dependencies with no fallback:** none blocking for D-59-04/06/07/08 themselves.

**Missing dependencies with fallback:** the installed plugin cache being stale only blocks
open question 3 (completing the walk); the operator-side update is the fallback, not a phase
blocker for the rest of the scope.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 [VERIFIED] |
| Config file | none — no `pytest.ini`/`pyproject.toml`/`setup.cfg` `[pytest]` block exists anywhere in this repo [VERIFIED this session] |
| Quick run command | `.venv/bin/python -m pytest tests/<new_or_touched_test>.py -x` |
| Full suite command | `.venv/bin/python -m pytest` (root) and, separately, `operator-claude-plugin/tests` (plugin suite has its own `conftest.py`); `node --test tests/n8n/*.test.mjs` only if n8n code is touched (not expected this phase) |

### Phase Requirements → Test Map

No `phase_req_ids` were supplied for this phase (traceability table intentionally omitted per
output contract). The natural test surface per decision area:

| Decision | Behavior | Test Type | Automated Command | File Exists? |
|----------|----------|-----------|-------------------|-------------|
| D-59-04 | credentials absent by default; present when `RUN_LIVE_PARITY=true` | unit (new) | `.venv/bin/python -m pytest tests/test_conftest_credential_guard.py -x` (name illustrative — planner's choice) | ❌ Wave 0 — new `tests/conftest.py` and its own test both need writing |
| D-59-04 | existing live tests still pass with real credentials when opted in | regression | `RUN_LIVE_PARITY=true .venv/bin/python -m pytest tests/test_scoring_parity.py -k live -x` (live, costs real HubSpot calls — run deliberately, not per-commit) | ✅ exists (`tests/test_scoring_parity.py`) |
| D-59-06 | session-start note text/mechanism | manual (hook output cannot be asserted by pytest without invoking the Claude Code host) | operator/Claude walk, one session start | ❌ Wave 0 — no automated harness for hook stdout in this repo |
| D-59-07 | artifact survives a chunk-7-of-20 interruption | unit (new) | a test that drives `dispatch_plan` with a stub transport, raises/kills after N chunks, and asserts the durable file already has N chunks' worth of ids | ❌ Wave 0 |
| D-59-07 | artifact reflects a revoked-but-completing run | integration | reuses the existing `test_a_revocation_midway_does_not_stop_a_running_dispatch` fixture shape, extended to also assert the artifact's contents | ❌ Wave 0 (extends an existing test file — locate it and confirm exact name before planning) |
| D-59-08 | extraction.md wording rewritten; behaviour still refuses on illegitimate resolution sources | contract (existing pattern in this codebase, `test_no_invention_structural.py`) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_no_invention_structural.py -x` | ✅ exists — planner should read this file before touching `extraction.md`'s wording, since it may already assert on adjacent text |

### Sampling Rate
- **Per task commit:** the quick command for the file(s) touched.
- **Per wave merge:** full root + plugin suites; live tests (`RUN_LIVE_PARITY=true`) run
  deliberately, not on every merge — they cost real HubSpot/Anthropic calls.
- **Phase gate:** full suite green (both root and plugin) before `/gsd-verify-work`; if the
  walk-completion candidate (open question 3) is in scope, that is a separate, explicitly
  armed, disarmed-and-verified live exercise per this project's established discipline (Phase
  47-50, restated in the walk record).

### Wave 0 Gaps
- [ ] `tests/conftest.py` — does not exist yet; D-59-04's entire deliverable
- [ ] A test asserting the D-59-04 fixture does NOT strip credentials when
      `RUN_LIVE_PARITY=true` (the exact failure mode this research proved live) — without this,
      a regression here is silent until someone runs the live suite and gets a confusing auth
      error
- [ ] A test harness for D-59-07's crash-survival requirement — no existing test in this repo
      simulates a mid-loop process interruption; the closest existing pattern
      (`test_a_revocation_midway_does_not_stop_a_running_dispatch`, referenced in CONTEXT) tests
      revocation, not artifact durability, and needs to be located and read before assuming it
      covers this
- [ ] `operator-claude-plugin/tests/test_no_invention_structural.py` should be read in full
      before D-59-08's `extraction.md` rewrite — it likely already has assertions this phase's
      wording change must keep passing

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | This phase does not touch how the operator or the plugin authenticates to HubSpot/n8n/Anthropic — those tokens/keys are pre-existing, config-file-based |
| V3 Session Management | partial — D-59-06 only | The "grant" concept (session-scoped, revocable) is Phase 53's, unchanged here; D-59-06 only adds a disclosure, it does not alter grant lifetime semantics |
| V4 Access Control | no | The write-safety allowlist gates (`_writeSafetyAllows()`, `plan_grant`'s empty-allowlist refusal) are explicitly out of scope and untouched |
| V5 Input Validation | **yes — central to D-59-08** | `extraction.py`'s identity gate and `company_domain.py`'s decision validation are exactly V5 input-validation controls; the resolve-and-propose widening must preserve their existing refuse-on-invalid-input behaviour for the illegitimate-source column, changing only the FLOW (refuse → attempt-resolve → propose → refuse-if-declined-or-failed), never the acceptance criteria itself |
| V6 Cryptography | no | Not implicated |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Ambient test credentials causing an unintended billable/live call during a routine test run | Information Disclosure / unintended Elevation of capability (a test gains network-write capability it shouldn't have) | D-59-04's guard itself — strip the ambient credential by construction; already the exact mitigation this phase implements, informed by the actual prior incident (`89c9871`) |
| A resolve-and-propose flow silently laundering a Claude-guessed value as if it were source-derived | Repudiation (the audit trail can no longer distinguish operator-supplied from Claude-resolved data) | D-59-08's explicit provenance requirement: "A Claude-resolved value carries provenance saying so — never dressed as source-derived." This is a design requirement already stated in CONTEXT.md, not a gap this research found — restated here because it is the single most safety-critical line in this phase's cross-cutting decision |
| A durable written-records artifact accumulating without bound or ever being read | Denial of Service (disk growth) / stale-data confusion | Not addressed in CONTEXT.md — flag for the planner: does the artifact need a retention/rotation policy, or is it scoped to "this run" and cleaned up like the walk's own "scratch artifacts deleted" convention (`53-WALK-RECORD.md`, post-walk state)? |

## Sources

### Primary (HIGH confidence — read directly this session)
- `operator-claude-plugin/scripts/chunking.py` (full file) — `dispatch_plan`, `DispatchOutcome`, `ChunkResult`
- `operator-claude-plugin/scripts/preingest.py:483-620` — `merge_enriched` (confirmed FINDING-2 fix), `rerequest_unanswered`
- `operator-claude-plugin/scripts/company_domain.py` (header + function list) — resolve/propose precedent
- `operator-claude-plugin/scripts/durable_paths.py:44-234` — atomic-write and state-path resolution primitives
- `operator-claude-plugin/scripts/artifact_store.py:1-80` — the plugin's one existing durable-state precedent, and its explicit rationale for NOT growing into a general store
- `operator-claude-plugin/tests/conftest.py:1-36,573-592` — `no_network` autouse-fixture precedent
- `src/classifier_haiku.py:1-65`, `src/validator_sonnet.py:1-45`, `src/web_research.py:95-135` — the three Anthropic-client construction sites
- `tests/test_scoring_parity.py:40-58`, `tests/test_review_flag_eq_filter.py:1-31` — the two real `live`/`RUN_LIVE_PARITY` skipif sites
- `scripts/build_cloud_workflows.py:471-520` — `BUILD_INGEST_RESPONSE`, the contacts-lane write-confirmation shape
- `operator-claude-plugin/skills/contact-upload/extraction.md:1-40,345-375` — the two no-invention passages, verbatim
- `operator-claude-plugin/scripts/write_grant.py:60-73,377-430` — review-lane exclusion comment, `plan_grant`'s empty-allowlist refusal text
- `operator-claude-plugin/.claude-plugin/plugin.json` — confirms plugin version 0.20.0, no `hooks` directory present
- `~/.claude/plugins/marketplaces/stz-marketplace/hooks/hooks.json` — real, installed `SessionStart` hook precedent
- `.planning/phases/53-operator-openable-write-grant/53-WALK-RECORD.md` (full file) — the walk itself
- `.planning/phases/59-frictionless-write-path/59-CONTEXT.md` (full file)
- `.planning/ROADMAP.md:40-196`
- `.planning/STATE.md:1-375` (partial — sufficient for milestone/phase framing)
- `.planning/REQUIREMENTS.md` (confirmed stale/v1.0, not applicable to this v1.1 phase)
- Live shell commands this session: pytest/python/node version checks, `find`/`grep` sweeps for
  pytest config, conftest.py locations, `Anthropic(` construction sites, HubSpot-note/engagement
  references, `hooks.json` precedent, and a live isolated pytest repro of the autouse-fixture
  skip-ordering behaviour (see Code Examples § D-59-04)

### Secondary (MEDIUM confidence)
- CLAUDE.md §13.0.1's description of a "companies branch resolves the same two keys" — cited but
  not independently re-verified against `scripts/build_cloud_workflows.py`'s companies branch in
  this session (see Open Question 1)
- Inference about how `SessionStart` hook stdout reaches the human operator (Assumption A1) —
  grounded in this plugin's own stated convention (`initialize/SKILL.md`) but not observed
  firing end-to-end for a hook in THIS plugin specifically

### Tertiary (LOW confidence)
- None — every claim in this document is either read directly from source this session, cited to
  an already-committed CONTEXT/ROADMAP/WALK-RECORD document, or explicitly flagged as an
  assumption in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- D-59-04 (ambient-credential guard): HIGH — mechanism traced end-to-end, failure mode
  reproduced live in this session
- D-59-06 (session-start note): MEDIUM — mechanism confirmed via a real precedent in this
  environment, but never exercised inside this specific plugin; the relay-to-operator step is
  inferred from an adjacent convention, not observed
- D-59-07 (post-run artifact): HIGH for the data source and durability requirement (read
  directly from `chunking.py`/`build_cloud_workflows.py`); MEDIUM for companies-lane coverage
  (Open Question 1 unresolved)
- D-59-08 (resolve-and-propose): HIGH for the exact text to amend and the existing
  precedent to reuse; MEDIUM for completeness of the "every gate" inventory the CONTEXT asks
  for, since a full sweep of every operator-facing refusal gate is planning-sized work, not
  research-sized — `extraction.py`'s identity gate and `company_domain.py`'s decision gate are
  the two concretely inventoried here; other lanes (e.g. `chunking.py`'s own `ChunkPlanError`
  paths, `preingest.py`'s `RowSpecError`/`ClassifyError`) exist and were located but not
  individually assessed for whether D-59-08 should reach them in THIS phase or a later one

**Research date:** 2026-08-28
**Valid until:** short shelf life — 7 days recommended. This phase's research is tightly coupled
to the exact state of a fast-moving repo (FINDING 2's fix landed the same day this research was
done); re-verify the FINDING-2 fix and the installed-plugin-version residual are still accurate
before planning executes if more than a few days elapse.
