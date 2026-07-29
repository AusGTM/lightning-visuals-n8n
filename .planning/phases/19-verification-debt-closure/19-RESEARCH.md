# Phase 19: Verification Debt Closure - Research

**Researched:** 2026-07-29
**Domain:** GSD process debt closure — re-running `/gsd-verify-work` against phases whose live-evidence verdicts may have drifted since v0.3 shipped
**Confidence:** MEDIUM (the ledger itself does not exist as a literal artifact — see below; the reconstruction is HIGH confidence given the evidence, the identity of "the six" is a defensible inference, not a verified fact)

<user_constraints>
## User Constraints (from CONTEXT.md)

No `CONTEXT.md` exists for Phase 19 (`.planning/phases/19-verification-debt-closure/` is empty
except this file). No `/gsd-discuss-phase` session has run. There are no locked decisions, no
discretion areas, and no deferred ideas to carry — this research is unconstrained by prior
phase-specific user input. The only binding constraints are the milestone-wide ones stated in
`ROADMAP.md`'s Milestone 4 "Constraints that apply across all of Milestone 4" block (armed-window
discipline, branch discipline, offline-suite baseline) and CLAUDE.md project-wide rules, both
reproduced in `## Project Constraints (from CLAUDE.md)` below.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VERIFY-01 | The six `/gsd-verify-work` re-runs carried from the v0.3 goal ledger are executed and their outcomes recorded. | This document's "The Six Re-Runs" section is the primary deliverable: it (a) proves the literal "goal ledger" is not an artifact that exists anywhere in the repo, (b) reconstructs the most defensible candidate set of six phases from hard evidence, (c) classifies each as OFFLINE- or LIVE-verifiable, and (d) proposes a recording format satisfying ROADMAP Phase 19 success criteria 1–3. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- All work stays on branch `feat/company-enrichment-icp-research` (ROADMAP Milestone 4 constraint — confirmed as the current branch).
- Any live HubSpot canary follows the established armed-window discipline: arm write gates only
  via the deploy-time overlay (`ENABLE_BAKED_FLAGS`) or `ALLOW_HUBSPOT_RECORD_WRITES` env,
  target allowlisted test records only (`TEST_RECORD_DOMAINS` / `TEST_CONTACT_IDS`), restore the
  disarmed build afterwards, and read the deployment back to confirm disarmed state.
- HubSpot search has eventual consistency (~6s–3min propagation); scheduled-lane canaries need
  tick-timing awareness.
- The contacts match path (`HubSpot Search` returning a hit, e.g. contact 201) is the single
  most live-proven path in the system — any change to its transport requires explicit
  before/after live evidence. (Not directly at risk in Phase 19 — no code changes are planned —
  but any live re-check touching this path must not accidentally exercise a write.)
- Baseline offline suite: reported by the orchestrator as **596 pytest / 309 node** (ROADMAP.md's
  own last-measured figure is "596 pytest / 285 node, measured 2026-07-29" after Phase 18 — the
  discrepancy is unresolved; Phase 19's plan should re-measure the current count at Task 1 rather
  than trust either stale figure).
- `.env` is Bash/Read-permission-blocked in this session (per `env-file-permission-blocked`
  memory). Live HubSpot/n8n calls in prior phases (17-02) were driven through an in-process
  python-dotenv wrapper, not shell-sourced `.env` — reuse that pattern for any live read-only
  check in Phase 19's plan.
- ARMING writes is the operationally blocked line in this environment (per
  `n8n-deploy-permission-blocked` memory); disarmed deploys, activation, and read-only API calls
  pass through the python driver. Any of the six items that require an armed write canary must be
  scoped as a `checkpoint:human-verify` task for the operator, not attempted by the executor.
- Do NOT use `gsd-tools state.update-progress` / `state.advance-plan` in this repo — the ROADMAP
  has multiple concatenated milestones and the tool has previously miscounted and corrupted
  `STATE.md` (`gsd-state-update-progress-unsafe` memory). Hand-edit `STATE.md`.

## Summary

Phase 19's job is to close `VERIFY-01`: "the six `/gsd-verify-work` re-runs carried from the v0.3
goal ledger are executed and their outcomes recorded." The research task's central finding is
blunt: **no file anywhere in this repository enumerates those six items.** The phrase "goal
ledger" was searched exhaustively — `STATE.md`, `ROADMAP.md`, `PROJECT.md`, `REQUIREMENTS.md`,
`.planning/milestones/v0.3-ROADMAP.md`, every commit message back to the v0.3 archive, and every
`*-UAT.md`/`*-VERIFICATION.md` file in `.planning/milestones/v0.3-phases/` — and the string
"goal ledger" occurs in exactly six places, all of them restating the same unitemized claim
("six `/gsd-verify-work` re-runs carried from the original goal ledger") with zero enumeration.
The phrase first appears in the `70a5fa5` "chore: archive v0.3 milestone" commit and was carried
forward verbatim into `REQUIREMENTS.md`, `PROJECT.md`, and `ROADMAP.md` without ever being
unpacked. There is no `.planning/*ledger*`, `*goal*`, or `*todo*` file of any kind.

Given that, this research reconstructs the most defensible candidate list from hard evidence
rather than treating "six" as gospel. Across the 17 phases of Milestone 3 (11, 12–16.10), exactly
**16 phases produced a `*-VERIFICATION.md`** and **exactly 5 of those 16 required a documented
`## Resolution` section** — meaning `/gsd-verify-work`'s first pass returned `human_needed` or
`gaps_found` and a second pass (a genuine re-run, in the literal sense of the word) was needed to
reach `passed`. The one phase with **no** `VERIFICATION.md`/`UAT.md` at all — Phase 11, executed
outside GSD and never run through the verify-work loop — is the natural sixth candidate. That
totals exactly six, which is strong corroborating (not conclusive) evidence this is the intended
set: **Phase 11, 15.5, 16, 16.4, 16.6, 16.9.**

The catch: all six were already resolved to `passed` on 2026-07-29, the same day v0.3 was
archived — none are sitting open today. So "re-run" in Phase 19 cannot mean "finish an incomplete
verification." It has to mean "re-confirm the passed verdict is still true of **current** code,"
because Phase 17 (contacts `HubSpot Search`/`Fetch By Id` transport swap) and Phase 18 (company
industry-normalization + sponsorship/persona copy-loop producers) both landed **after** these six
verdicts were recorded, and both touch code paths those six phases' live evidence walked through.
Phase 18's own `VERIFICATION.md` says as much explicitly: the new `lv_sponsorship_reliant` /
`persona_group` producers are "recorded as a recommended follow-up" for a live canary that has
never happened — and that follow-up canary would fire through exactly the company search/create/
update transport that Phase 16.6 and 16.9 verified live *before* those fields existed in the
payload.

**Primary recommendation:** Treat the six as (Phase 11, 15.5, 16, 16.4, 16.6, 16.9), but flag the
reconstruction explicitly as an inference for the plan/discuss step to confirm with the user
before locking — this is the single biggest `[ASSUMED]` claim in this document. For execution,
split the six into OFFLINE-verifiable (11, 15.5 — re-run existing tests + code inspection against
current state, no live call needed) and LIVE-verifiable (16, 16.4, 16.6, 16.9 — need a read-only
live check at minimum; 16.9's company-update claim needs an armed write canary that should be
scoped as `checkpoint:human-verify`, not attempted by the executor).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Re-confirm offline-only claims (Phase 11 code shape, Phase 15.5 test rigor) | Codebase / Test Suite | — | Both verdicts rested entirely on static analysis + pytest/node — no live call was ever part of their evidence |
| Re-confirm scheduled-workflow deployment/activation state (Phase 16) | n8n Cloud (Orchestration) | API/Backend (read-only GET) | `deploy_n8n_workflows.py`'s `DRY_RUN=true` (default) mode already does a fresh GET + diff with zero writes — the correct mechanism to re-confirm active/bound state |
| Re-confirm `hs_object_id` filterability (Phase 16.4) | Database/Storage (HubSpot CRM) | — | A HubSpot platform capability, not this codebase's code — lowest-risk item, effectively already re-exercised in spirit by Phase 17's live contacts canary |
| Re-confirm company `search`/`fetch-by-id` transport still returns real records (Phase 16.6) | n8n Cloud (Orchestration) | Database/Storage (HubSpot CRM, read-only) | Downstream of Phase 18's company merge-call changes — the read path most likely to have silently drifted |
| Re-confirm company `create`/`update` writes correctly with the new Phase 18 fields (Phase 16.9) | n8n Cloud (Orchestration) | Database/Storage (HubSpot CRM, write) | Highest-risk item — requires an ARMED write canary against an allowlisted test record; out of this session's permission envelope, must be a `checkpoint:human-verify` task |
| Record six outcomes durably | Codebase (`.planning/`) | — | GSD's own convention — `*-VERIFICATION.md`/`*-UAT.md`/`STATE.md` — is the existing recording surface; no new artifact type is needed |

## Standard Stack

No new libraries, frameworks, or packages are introduced by this phase. It reuses:

- The existing `scripts/deploy_n8n_workflows.py` DRY_RUN=true (default) mode for read-only n8n
  Cloud state checks.
- The existing in-process python-dotenv pattern (established Phase 17-02) for any read-only
  HubSpot API call, since `.env` is Bash/Read-blocked in this session.
- The GSD `gsd-verify-work` skill itself for any item where a genuine conversational UAT re-run
  is warranted (see "What `/gsd-verify-work` Actually Does" below) — this is a human-in-the-loop
  process, not a library dependency.

### Package Legitimacy Audit

Not applicable — this phase installs no packages. No `npm view` / `pip index versions` /
`cargo search` check is required.

## The Six Re-Runs — Ledger Reconstruction

### What is actually on record (verbatim, exhaustive)

The phrase occurs in exactly these places, none of which enumerate the six:

```
.planning/REQUIREMENTS.md:121: "The six `/gsd-verify-work` re-runs carried from the v0.3 goal
  ledger are executed and their outcomes recorded." (VERIFY-01 statement)
.planning/PROJECT.md:59:       "Verification debt — six `/gsd-verify-work` re-runs carried from
  the v0.3 goal ledger."
.planning/PROJECT.md:92:       "[ ] Six `/gsd-verify-work` re-runs from the v0.3 goal ledger closed"
.planning/STATE.md:164:        "Six `/gsd-verify-work` re-runs carried from the original goal
  ledger | Deferred to v0.4 | 2026-07-29" (Deferred Items table row, no itemization)
.planning/ROADMAP.md:254/279/379/384: four restatements of the same unitemized claim
.planning/milestones/v0.3-ROADMAP.md:604: "Six `/gsd-verify-work` re-runs carried from the
  original goal ledger." (the ORIGIN of the phrase, under "Issues deferred to v0.4" — also
  unitemized)
```

`git log -S"goal ledger" --all --oneline` shows the phrase entered the repository in the
`70a5fa5` "chore: archive v0.3 milestone" commit (2026-07-29 15:49) — the same session that wrote
`v0.3-ROADMAP.md`'s "Issues deferred to v0.4" list. The commit body itself never itemizes the six
either; it separately notes "`query init.manager` projects 16.6/16.8/16.9/16.10 incomplete for
bookkeeping reasons only" — a **different, already-resolved** bookkeeping concern (missing
`SUMMARY.md`/`PLAN.md` files, not missing verification), not to be confused with the six.

**Conclusion: the "goal ledger" is not a file. It is, at best, a mental model the archiving
session held and never wrote down.** `[VERIFIED: repo grep + git log -S, exhaustive]`

### Reconstruction method

Since the literal ledger doesn't exist, the defensible move is to find the six v0.3 phases whose
`/gsd-verify-work` history actually shows a *re-run* in the technical sense: an initial verdict
that was not `passed`, requiring a second look before the milestone could close. `gsd-verify-work`
produces `*-UAT.md` (only created when a human conversational check runs) and the verifier that
feeds it writes `*-VERIFICATION.md` with a `Status:` field; a phase that needed a second pass
carries a `## Resolution — <date> (status X -> passed)` section in its `VERIFICATION.md`.

```
find .planning/milestones/v0.3-phases -iname "*UAT*" -o -iname "*VERIFICATION*"
```

Inventory (Milestone 3 = phases 11, 12, 13, 14, 15, 15.5, 16, 16.1–16.10 = 17 phase dirs):

| Phase | VERIFICATION.md? | Initial status | Resolution section? | UAT.md? |
|-------|------------------|-----------------|----------------------|---------|
| 11 | **none** | — (never verified; executed outside GSD, recorded retroactively) | — | **none** |
| 12 | yes | passed | no | no |
| 13 | yes | passed | no | no |
| 14 | yes | PASSED | no | no |
| 15 | yes | PASSED | no | no |
| **15.5** | yes | human_needed | **yes** | **yes** |
| **16** | yes | human_needed | **yes** | **yes** |
| 16.1 | yes | passed | no | no |
| **16.4** | yes | human_needed | **yes** | **yes** |
| 16.2 | yes | passed — ACHIEVED | no | no |
| 16.3 | yes | passed | no | no |
| 16.5 | yes | passed | no | no |
| **16.6** | yes | gaps_found | **yes** | **yes** |
| 16.7 | yes | passed | no | no |
| 16.8 | yes | passed | no | no |
| **16.9** | yes | gaps_found | **yes** | **yes** |
| 16.10 | yes | passed | no | no |

Exactly **5** phases required a Resolution (15.5, 16, 16.4, 16.6, 16.9) — every one of them also
has a `*-UAT.md`, confirming the resolution came via a genuine `/gsd-verify-work` conversational
re-run, not a silent edit. Adding Phase 11 (zero verify-work history at all — the one phase that
never got a *first* run, closest analogue to a "re-run debt") produces exactly six.
`[VERIFIED: file inventory + grep against every v0.3-phases VERIFICATION.md/UAT.md, this session]`

**This is a strong, not certain, reconstruction.** It is corroborated by:
- The count matching exactly (6, not 5 or 7 — no other v0.3 phase has a Resolution section or a
  missing VERIFICATION.md).
- All five Resolution phases closing on **2026-07-29**, the exact archive date, meaning they were
  the last items resolved before ship — the kind of thing a closing session would mentally file as
  "handled, but the passing verdict rested on live evidence gathered under time pressure, worth a
  fresh look later."
- Phase 18's own `VERIFICATION.md` independently flagging that the new company-payload fields
  (from Phase 18) have "never [been] proven against a real n8n Cloud execution or HubSpot write" —
  which is precisely the risk a re-run of 16.6/16.9 would close.

It is **not** proven — no artifact says "these are the six." `[ASSUMED — see Assumptions Log A1]`

### The six, individually

#### 1. Phase 11 — Company Branch & Provider Contract Hardening
**What it verifies:** the companies enrichment n8n branch (sibling, not nested), `mergeCompanies.js`
non-clobber field-ownership merge, the ZoomInfo GTM `companies/enrich`/`companies/search` contract
(probed live 2026-07-08–2026-07-20), three provider unit/shape bugs (ZoomInfo revenue in
thousands, Lusha `/v2/company` `data` wrapper, ZoomInfo `naicsCodes` object-not-string), and the
cross-provider size-conflict detector (`harveynorman.com.au` — three providers, three different
entities, 40-point ICP swing withheld from promotion).
**Never run through `/gsd-verify-work` at all** — it predates the convention (executed outside
GSD between 2026-07-08 and 2026-07-20, `phase-11-01-SUMMARY.md` written retroactively).
**Offline or live:** predominantly OFFLINE. All five original success criteria (sibling branch
structure, ZoomInfo contract confirmed, unit/shape bugs fixed+regression-tested, conflict
detector withholds promotion, numbered spec exists) are checkable against current source + the
existing test suite (`tests/n8n/mergeCompanies.test.mjs`, the conflict-detector tests, taxonomy
tests). The one originally-live claim (ZoomInfo GTM contract) is an external platform fact that
hasn't needed re-probing in any subsequent phase — low priority for a fresh live call.
**Current-state risk:** MEDIUM. `mergeCompanies.js` has been touched by Phase 16.3 (stale-
timestamp fix), Phase 18 (via `build_cloud_workflows.py`'s `ENRICH_MERGE_CO` wrapper gaining the
sponsorship copy-loop), and the taxonomy generation Phase 11 itself flagged as carried-forward
debt (TX-4, closed Phase 12). A verify-work re-run here is really "confirm the five original
guarantees still hold given every phase that has touched this file since" — a code-and-test audit,
not new live evidence.

#### 2. Phase 15.5 — Tiered Candidate Adjudication
**What it verifies:** conflicting enrichment candidates stay parallel with A/R/G/T scoring
components through to the judge rather than collapsing to a premature argmax; the composite score
never feeds `mergeCompanies`' promotion gate directly; a self-confirmation guard prevents a
research candidate from agreeing with its own unprovenanced prior.
**Resolution:** the one `human_needed` item was a **test-rigor decision**, not a live gap — the
TA-4/TS-1 "recency proof" test originally called `mergeCompanies` with literally identical
arguments twice (tautological). Resolved same-day by two commits (`8c7432f`, unrecorded at the
time, plus a same-day addition) that made the test genuinely vary `page_age` through the real
`scoreResearchCandidates` → `judge_confidence_by_field` production path.
**Offline or live:** entirely OFFLINE — no live call was ever part of this phase's evidence chain.
**Current-state risk:** LOW. `judge.js`/`mergeCompanies.js`'s confidence-wiring logic has not been
touched since (Phase 16.3's stale-timestamp fix and Phase 18's copy-loop wiring are both additive,
not structural, to this code path). Re-running here means confirming the two rigor-fixing tests
are still present, unreverted, and passing in the current 596/309 suite — a fast, low-risk check.

#### 3. Phase 16 — Scheduled Workflows & Review Surface
**What it verifies:** SJ-1/SJ-2/SJ-3 schedule-triggered n8n workflows fire on their predicates,
the dedupe sweep wiring runs, and the §22.2 human review loop (flag → decision JSON → approve →
apply → clear) closes on a real record.
**Resolution:** closed live same-day via five distinct execution ids (23, 24, 29, 33, 56) proving
all three schedules fired and the review loop applied a real PATCH (`lv_org_type` None →
'broadcaster', both review flags flipped, throwaway record deleted, build restored disarmed).
**Offline or live:** LIVE — the phase goal's literal clause ("runs live on n8n Cloud") cannot be
satisfied by code inspection.
**Current-state risk:** MEDIUM-HIGH. Since 2026-07-29 the deployment has been redeployed and
armed/disarmed repeatedly (Phase 16.7 write-path canary, Phase 16.9 create-path canary, Phase 17-02's
dual live canary, and presumably a Phase 18 rebuild+redeploy to pick up the industry/sponsorship/
persona changes — **the research questions note Phase 18 rebuilt the workflow JSON; whether it
was actually redeployed to n8n Cloud is not confirmed by anything read in this session** — see
Open Questions). A re-run needs, at minimum, a read-only GET (via `deploy_n8n_workflows.py`'s
default DRY_RUN mode) confirming all three workflows are still active, still credential-bound, and
the deployed JSON matches the current committed build (no drift from an un-redeployed Phase 18
change sitting only in git).

#### 4. Phase 16.4 — Fetch by ObjectId
**What it verifies:** `hs_object_id EQ <id>` is filterable on the HubSpot CRM v3 Search API for
both `contacts` and `companies`, and a systemic filterability failure (400) is distinguishable
from a legitimate zero-result response (200, `total:0`).
**Resolution:** closed same-day by a direct read-only probe against portal `22617666` for both
object types.
**Offline or live:** LIVE, but the underlying fact is a **HubSpot platform capability**, not
something this codebase's code changes. Lowest risk of the four live items.
**Current-state risk:** LOW. Phase 17's dual live canary (`17-CANARY-EVIDENCE.md`) exercised the
CONTACTS `Fetch By Id` path live again (executions in the "AFTER (post-swap)" section), implicitly
re-confirming `hs_object_id` filterability for contacts as a side effect — though it never touched
companies, and the platform behavior is external to this repo regardless. This item is the most
likely to be **trivially satisfiable** by citing Phase 17's already-gathered evidence for
contacts, plus one cheap read-only company-side probe.

#### 5. Phase 16.6 — Companies Search Transport Fix (BUG 10)
**What it verifies:** all six `company:search`-shaped nodes (Fetch By Id, Company Search, SJ-1/
SJ-2/SJ-3 Search, Review Search) return real records live via the credential-bound `httpRequest`
transport (n8n's native HubSpot node has no `search` operation for `resource: company` at all —
root cause, not just symptom).
**Resolution:** closed same-day with live execution evidence for all six nodes (executions 12,
19, 23, 24, 29, 33) plus a verbatim replay of each node's committed `jsonBody` against the live
search API.
**Offline or live:** LIVE — this is exactly the transport BUG 10 fixed; only a live call proves it
still returns real records rather than `json: null`.
**Current-state risk:** HIGH — the highest of the six. Phase 18 changed what flows **through**
this exact transport: `NORM-01` changed how industry text is derived before it ever reaches a
search/merge call, and `COPY-01` added `lv_sponsorship_reliant` to the company research request
and its downstream merge fold. Phase 18's own `VERIFICATION.md` explicitly defers proving these
new fields live to "a future live-canary step" — which is precisely a re-run of 16.6's live check,
now carrying the new payload shape. This is the strongest candidate for genuinely needing a fresh
(read-only) live company-search canary in Phase 19.

#### 6. Phase 16.9 — Create Path Fix and Company Writes
**What it verifies:** `company:create` and `company:update` — neither of which had ever run live
before this phase — write correctly to HubSpot, or their blockers are on record.
**Resolution:** SC-2 (schema coverage oracle) and SC-4 (`company:create`, execution 34: create →
fresh-read confirm → DELETE → 404 re-read → disarmed restore) both closed with live evidence.
**SC-3 (`company:update`) was explicitly NOT independently re-confirmed** — the Resolution section
says its evidence "is unrecoverable by design," corroborated only by execution 17 plus the
byte-identical transport's later live 201 on create. This is the one item in the entire six-item
set that the ORIGINAL verifier itself flagged as residual, not fully closed.
**Offline or live:** LIVE + WRITE. This is the only one of the six that requires an **armed**
write canary (create or update against an allowlisted test record), not merely a read.
**Current-state risk:** HIGH, same reasoning as 16.6 — the create/update payload now carries
Phase 18's new fields. Combined with SC-3's already-flagged residual, this is the single most
load-bearing item to close, and the one most constrained by this session's permission envelope
(ARMING writes is blocked here — see Project Constraints). **This item should be scoped as a
`checkpoint:human-verify` task in the plan**, following the same armed-window discipline Phase
16.9/17-02 already established (allowlist a single test company, arm, fire once, read back, prove
zero other writes, restore disarmed).

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────────────────────────┐
                    │  .planning/milestones/v0.3-phases/*/     │
                    │  *-VERIFICATION.md, *-UAT.md (evidence)  │
                    └──────────────────┬────────────────────────┘
                                       │ read (grep/inspect, this research)
                                       ▼
              ┌───────────────────────────────────────────┐
              │  Six-item candidate list (Phase 11, 15.5,  │
              │  16, 16.4, 16.6, 16.9) — reconstructed,    │
              │  not enumerated anywhere pre-existing      │
              └───────┬───────────────────────┬────────────┘
                      │                        │
        OFFLINE path  │                        │  LIVE path
                      ▼                        ▼
        ┌─────────────────────────┐  ┌──────────────────────────────┐
        │ Phase 11, 15.5:          │  │ Phase 16, 16.4: READ-ONLY     │
        │ re-run pytest/node        │  │  GET via deploy_n8n_workflows │
        │ subset + code inspection  │  │  DRY_RUN=true / curl HubSpot  │
        │ against CURRENT source    │  │  search — no write gate armed │
        └───────────┬──────────────┘  └───────────┬───────────────────┘
                    │                              │
                    │              ┌───────────────┴────────────────┐
                    │              │ Phase 16.6: READ-ONLY company    │
                    │              │  search/fetch live re-canary     │
                    │              │  (post-Phase-18 payload shape)   │
                    │              └───────────────┬────────────────┘
                    │                              │
                    │              ┌───────────────┴────────────────┐
                    │              │ Phase 16.9: ARMED WRITE canary   │
                    │              │  (checkpoint:human-verify —      │
                    │              │  operator-only, out of this      │
                    │              │  session's permission envelope)  │
                    │              └───────────────┬────────────────┘
                    ▼                              ▼
        ┌─────────────────────────────────────────────────────────┐
        │  Recording: per-item outcome (passed/human_needed/failed) │
        │  written to STATE.md + a new 19-LEDGER.md, any surfaced   │
        │  defect captured as a debug brief / backlog item          │
        └─────────────────────────────────────────────────────────┘
```

### Recommended Recording Structure

Reuse the existing GSD verification vocabulary rather than inventing a new artifact type:

```
.planning/phases/19-verification-debt-closure/
├── 19-01-PLAN.md              # (planner output — not this research's job)
├── 19-LEDGER.md                # NEW — the itemized reconstruction + six outcomes
│                                # (the artifact that should have existed at v0.3 archive time)
└── 19-01-SUMMARY.md            # execution summary, one row per item, linking evidence
```

`19-LEDGER.md` should contain, per item: phase id/name, original VERIFICATION.md/UAT.md link,
what was re-checked, method (offline test re-run / live read-only GET / live write canary /
human_needed), outcome, and — critically — a note if the item surfaces a NEW defect (which must
become its own `.planning/debug/` brief or backlog row per Phase 19 success criterion 3, not be
silently folded into "passed").

### Pattern: Re-verification via read-only replay, not re-invocation of the full skill

For items 11 and 15.5 (offline), a full `/gsd-verify-work` conversational session is unnecessary —
these phases' `SUMMARY.md`/tests are already the evidence; a targeted pytest/node re-run plus a
diff against current source suffices and can be done non-interactively.

For items 16 and 16.4 (live, read-only), reuse `scripts/deploy_n8n_workflows.py` in its default
`DRY_RUN=true` mode (a fresh GET + diff, zero writes) and a read-only HubSpot search curl (the
exact pattern already used in `17-CANARY-EVIDENCE.md`'s "GET only" steps and the historical
`hs_object_id` checkpoint curl documented in `STATE.md`).

For item 16.6 (live, read-only but higher stakes since Phase 18 changed the payload), the same
read-only company-search pattern applies — no write gate needs to be armed to prove the transport
still returns real records; the payload SHAPE (does the search response still parse correctly
through `adaptFetchById.js` with the new fields present downstream) is what needs re-confirming.

For item 16.9 (live, write), only this one item genuinely needs the full armed-window ceremony:
arm `ALLOW_HUBSPOT_RECORD_WRITES` with a single allowlisted test company, fire an update (not
create — SC-3 is the update gap; SC-4/create was already independently re-confirmed), read back,
restore disarmed. This is the one item that should NOT be attempted by an unattended executor —
scope it as `checkpoint:human-verify` in the plan, consistent with the milestone's own stated
armed-window discipline.

### Anti-Patterns to Avoid
- **Silently marking all six "passed" without fresh evidence:** the whole point of Phase 19 is
  that "passed on 2026-07-29" and "passed against current code" are different claims. Re-stating
  the old VERIFICATION.md verdict without a new check is exactly what ROADMAP criterion 3
  ("nothing is silently dropped") forbids.
- **Building a new bespoke verification harness:** every mechanism needed already exists
  (`deploy_n8n_workflows.py` DRY_RUN, the python-dotenv live-call pattern, `/gsd-verify-work`
  itself). Phase 19 is a debt-discharge phase — it should not add new code.
- **Treating item 16.9 (armed write) the same as the other five (read-only):** conflating these
  risks either an unauthorized write in an unattended session, or under-verifying the one item
  the original verifier itself flagged as residual (SC-3).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Re-confirming n8n Cloud deployment state | A new n8n API polling script | `scripts/deploy_n8n_workflows.py` (DRY_RUN=true default) | Already does a fresh GET + diff with zero writes; adding a second script duplicates a proven mechanism |
| Re-confirming HubSpot search behavior | A new HubSpot client wrapper | The existing python-dotenv in-process pattern (Phase 17-02 precedent) + direct curl (as used throughout `STATE.md`'s live checkpoints) | `.env` is Bash/Read-blocked in this session; the established workaround already exists and is documented |
| Recording six verification outcomes | A new bespoke tracking format | GSD's own `*-VERIFICATION.md`/`*-UAT.md` conventions, extended with one new `19-LEDGER.md` that itemizes what STATE.md's Deferred Items row never did | Reinventing a tracking scheme when the project already has one (and the gap is precisely that this convention wasn't applied to the original "six" claim) compounds the debt instead of closing it |

**Key insight:** this phase's entire risk is in *scope creep toward rebuilding things*, not in
missing tooling. Every mechanism needed to close VERIFY-01 already exists in this repository;
the work is applying it six times and writing down what happened.

## Common Pitfalls

### Pitfall 1: Treating "the six" as a settled fact rather than a reconstruction
**What goes wrong:** the plan locks in (Phase 11, 15.5, 16, 16.4, 16.6, 16.9) as if it were read
from a ledger, and if it's wrong, VERIFY-01 closes against the wrong six items while the real
(unknown) intent goes unaddressed.
**Why it happens:** the phrase "six `/gsd-verify-work` re-runs" reads as an authoritative claim
even though no artifact backs it.
**How to avoid:** the plan (or `/gsd-discuss-phase` before it) should surface this reconstruction
to the user explicitly and get a one-line confirmation or correction before executing — this is
exactly what `## Open Questions` below recommends.
**Warning signs:** if the user has a different mental model of "the six" (e.g., they were tracking
something outside `.planning/` entirely, like a private note or Slack thread), the reconstruction
will be plausible-looking but wrong.

### Pitfall 2: Conflating "offline suite is green" with "live path still works"
**What goes wrong:** Phase 17 and 18 both report zero regressions against the growing offline
suite (422→459→504→584→596 pytest across the relevant history) — but BUG 10 itself is the
canonical proof in this exact repo that offline-green says nothing about the transport layer
(HANDOFF.json: "an offline-green suite says nothing about the transport layer... judge every live
run by node-by-node execution-API inspection, never by the webhook's HTTP 200"). A Phase 19 that
re-confirms only via `pytest`/`node --test` for items 16.6/16.9 has not actually closed the debt.
**Why it happens:** offline tests are cheap and always available; live checks require credentials,
armed-window discipline, and (for 16.9) an operator.
**How to avoid:** items classified LIVE in this research must get an actual live call (read-only
at minimum), not a test-suite citation, before being recorded `passed`.
**Warning signs:** a `19-LEDGER.md` entry for 16, 16.4, 16.6, or 16.9 whose only evidence is a
pytest/node command.

### Pitfall 3: HubSpot search eventual consistency masking a false pass
**What goes wrong:** a read-only company-search re-canary (item 16.6) fires immediately after any
recent write elsewhere in the portal and reads stale/absent data, producing a false "gap" or false
"pass."
**Why it happens:** documented in this project's own knowledge base — HubSpot search has ~6s–3min
propagation lag.
**How to avoid:** target a record known-stable for hours/days (e.g. the standing test fixtures
contact 201 / company 9604614548, both untouched per the last-known STATE.md note), not a record
just written by an adjacent step in the same session.

## Runtime State Inventory

Not applicable — Phase 19 is a verification/recording phase, not a rename/refactor/migration.
No production code paths, database keys, or OS-registered state are touched by this phase's own
work (only *read* for confirmation). Skipped per instructions.

## Code Examples

### Read-only n8n Cloud deployment state check (no writes)
```bash
# Source: scripts/deploy_n8n_workflows.py's own documented default behavior (line ~536-537)
# DRY RUN (default) — no writes will be made. Set DRY_RUN=false AND ALLOW_N8N_DEPLOY=true to deploy.
DRY_RUN=true python scripts/deploy_n8n_workflows.py
# Confirms: which workflows exist, active/inactive state, credential binding, and diffs the
# live JSON against the current committed build — all via a fresh GET, zero writes.
```

### Read-only HubSpot company search re-canary (item 16.6 pattern)
```bash
# Source: pattern established in STATE.md's historical Track-B live checkpoint curl, and
# 17-CANARY-EVIDENCE.md's "GET only" steps.
curl -s -X POST "https://api.hubapi.com/crm/v3/objects/companies/search" \
  -H "Authorization: Bearer $HUBSPOT_PRIVATE_APP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filterGroups":[{"filters":[{"propertyName":"hs_object_id","operator":"EQ","value":"9604614548"}]}],"properties":["hs_object_id","name","domain","lv_org_type","lv_sponsorship_reliant"],"limit":1}'
# Pass: 200 with the Melbourne Racing Club record, including the new lv_sponsorship_reliant
# property in the response schema (confirms Phase 15's property migration + Phase 18's new
# field are both visible through the same transport 16.6 fixed).
```

### In-process python-dotenv pattern for live calls (this session's .env-block workaround)
```python
# Source: established Phase 17-02 precedent (STATE.md decision log, Phase 17-02 entry).
# .env is Bash/Read-permission-blocked in this session; drive live calls in-process instead
# of shell-sourcing .env.
from dotenv import load_dotenv
import os
load_dotenv()
token = os.environ["HUBSPOT_PRIVATE_APP_TOKEN"]
# ... proceed with a read-only requests.post(...) call as above, never printed/logged.
```

## State of the Art

Not meaningfully applicable — this is an internal process/debt-closure phase, not a technology
choice. The one relevant "state of the art" fact is repo-internal: `gsd-verify-work` itself
gained a `## Resolution` convention and a coverage-classification mode (`uat.classify-coverage`,
auto-passed deliverables) since Milestone 3 began — the six original verifications predate some
of that tooling, but nothing about closing VERIFY-01 depends on those newer verify-work features.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The six items are (Phase 11, 15.5, 16, 16.4, 16.6, 16.9) | "The Six Re-Runs — Ledger Reconstruction" | If wrong, Phase 19 closes VERIFY-01 against the wrong scope while the actually-intended six (if a different set was meant) remains open, silently re-deferring real debt. This is the single highest-impact assumption in the whole phase and should be confirmed with the user (or accepted as the working definition) before the plan locks task scope. |
| A2 | Phase 18's company workflow rebuild (industry normalization + sponsorship/persona producers) was also **redeployed** to n8n Cloud, not just rebuilt in git | Phase 16 item, "Current-state risk" | If Phase 18's `n8n/*.json` changes were never redeployed, the live n8n Cloud instance is running STALE code relative to git — Phase 19's live checks would then be verifying an outdated deployment, and the finding itself ("deployment is behind git") becomes the actual defect to record, not a false pass. Confirm via the read-only DRY_RUN diff in the Code Examples section above before drawing conclusions from any live 16.6/16.9 re-check. |
| A3 | The offline suite baseline is 596 pytest / 309 node (per orchestrator) vs. 596/285 (per ROADMAP.md's last self-report) | Project Constraints | Minor — either way the plan should re-measure at Task 1 rather than assume either number; using a stale baseline could mask a real regression introduced between Phase 18 and Phase 19 planning. |

**If this table is empty:** N/A — see A1–A3 above.

## Open Questions

1. **Is (Phase 11, 15.5, 16, 16.4, 16.6, 16.9) actually "the six"?**
   - What we know: no enumeration exists anywhere; this set is the only group of exactly six v0.3
     phases whose `/gsd-verify-work` history shows a genuine re-run (5 Resolution sections) or a
     complete absence of any verify-work run (Phase 11).
   - What's unclear: whether the archiving session had a different, unwritten mental model (e.g.
     a subset of these plus something entirely outside `.planning/`).
   - Recommendation: surface this reconstruction explicitly at plan/discuss time; either get a
     one-line user confirmation, or proceed on this evidence-based set with the assumption logged
     (A1) and flagged non-blocking (the phase's own success criteria are about *executing and
     recording* six re-runs, which this set satisfies regardless of whether it's the exact
     original intent).

2. **Was Phase 18's rebuilt company workflow JSON actually redeployed to n8n Cloud?**
   - What we know: Phase 18's plans (`18-01`, `18-02`, `18-03`) rebuilt `n8n/wf_enrichment_*.json`
     deterministically and proved the offline suite green; nothing read in this session's phase-18
     artifacts (`18-VERIFICATION.md`, `18-03-SUMMARY.md`) mentions a `deploy_n8n_workflows.py`
     invocation against n8n Cloud.
   - What's unclear: whether the live n8n Cloud instance is running Phase-18-current code or
     Phase-17-vintage code.
   - Recommendation: the FIRST live check in Phase 19's plan should be the read-only DRY_RUN diff
     (Code Examples above) — its output settles this question before any of the six items are
     individually re-checked, and if it shows drift, that drift itself is likely worth its own
     `.planning/debug/` brief.

3. **Does Phase 16.9's item require a create canary, an update canary, or both?**
   - What we know: `16.9-VERIFICATION.md`'s Resolution explicitly says SC-4 (create) WAS
     independently re-confirmed (execution 34) but SC-3 (update) was NOT — "its evidence is
     unrecoverable by design."
   - What's unclear: whether a fresh update canary is achievable within this session's permission
     envelope (armed writes are blocked) or must wait for an operator session.
   - Recommendation: scope the update-canary specifically (not create — that's already solid) as
     a `checkpoint:human-verify` task, following the exact armed-window pattern already proven in
     16.9/17-02 (single allowlisted test company, arm, fire once, read back, restore disarmed).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Offline test suite (pytest, node --test) | Items 11, 15.5 (and baseline re-measurement for all six) | ✓ (per orchestrator: 596 pytest / 309 node) | — | — |
| n8n Cloud API (read-only GET) | Item 16 deployment-state check | Likely ✓ — `N8N_API_KEY`/`N8N_URL` established in prior phases (`.n8n_credential_ids.json` gitignored cache exists per STATE.md); `.env` itself is Bash/Read-blocked this session | — | Drive via in-process python-dotenv wrapper (Phase 17-02 pattern) rather than shell-sourcing `.env` |
| HubSpot CRM v3 API (read-only search) | Items 16.4, 16.6 | Likely ✓ — `HUBSPOT_PRIVATE_APP_TOKEN` established, portal `22617666` is the working portal throughout Milestone 3-4 | — | Same in-process wrapper pattern |
| HubSpot CRM v3 API (armed write) | Item 16.9 (update canary) | ✗ in this session — ARMING writes is the operationally blocked line (per `n8n-deploy-permission-blocked` memory) | — | Scope as `checkpoint:human-verify`; the operator runs the same armed-window ceremony already proven in 16.9/17-02 |
| `.env` direct read | All live items | ✗ — Bash/Read-permission-blocked | — | In-process python-dotenv load (established pattern, no fallback needed beyond this) |

**Missing dependencies with no fallback:** none — every live-check dependency has an established
in-repo fallback pattern.

**Missing dependencies with fallback:** armed HubSpot writes (item 16.9's update canary) has no
in-session fallback other than deferring to a human operator, which is itself an acceptable
recorded outcome per Phase 19 success criterion 2 (`human_needed` is a valid final state).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python) + `node --test` (JS, n8n Code-node bodies) |
| Config file | none dedicated — repo convention (`pyproject.toml`/no config; `tests/n8n/*.test.mjs` run directly) |
| Quick run command | `.venv/bin/python -m pytest -k <relevant module>` / `node --test tests/n8n/mergeCompanies.test.mjs` |
| Full suite command | `.venv/bin/python -m pytest` && `node --test tests/n8n/*.test.mjs` (directory form is broken on this Node version — see `test-suite-run-commands` knowledge-base entry) |

### Phase Requirements → Test/Check Map

Phase 19 is a verification-recording phase, not a code-building phase — its "tests" are the six
re-verification checks themselves, each of which produces an on-record outcome rather than a
pass/fail assertion in a new automated test file.

| Item | Behavior | Verification Type | Command / Method | Artifact Exists? |
|------|----------|--------------------|--------------------|-------------------|
| Phase 11 re-check | mergeCompanies non-clobber + conflict detector still hold against current source | offline (pytest/node re-run + code diff read) | `node --test tests/n8n/mergeCompanies.test.mjs`; read `n8n/code/mergeCompanies.js` against Phase 11's 5 success criteria | ✓ (existing tests) |
| Phase 15.5 re-check | TA-4/TS-1 recency tests still present, non-tautological, passing | offline (targeted node test) | `node --test tests/n8n/mergeCompanies.test.mjs -- --grep "TA-4\|TS-1"` (or equivalent grep-by-name) | ✓ (existing tests) |
| Phase 16 re-check | scheduled workflows still active + credential-bound; deployed JSON matches committed | live, read-only | `DRY_RUN=true python scripts/deploy_n8n_workflows.py` | ✓ (existing script) |
| Phase 16.4 re-check | `hs_object_id` still filterable on both object types | live, read-only | curl pattern in Code Examples above | ✓ (documented pattern, no dedicated script) |
| Phase 16.6 re-check | company search/fetch transport still returns real records with the new Phase-18 fields present | live, read-only | curl pattern in Code Examples above, against company 9604614548 | ✓ (documented pattern) |
| Phase 16.9 re-check (create) | already independently confirmed (execution 34) — cite, do not re-arm | none needed (already closed) | cite `16.9-VERIFICATION.md` Resolution | ✓ |
| Phase 16.9 re-check (update) | company update writes correctly with new fields | live, ARMED write | operator-run armed-window canary (checkpoint:human-verify) | requires new operator session — Wave 0 gap |

### Sampling Rate
- **Per item:** the specific check listed above, run once, evidence recorded in `19-LEDGER.md`.
- **Phase gate:** offline suite green (re-measure current count, don't trust either stale figure)
  before considering the phase closeable; live items each need their own evidence, not a suite run.

### Wave 0 Gaps
- [ ] `19-LEDGER.md` — does not exist yet; this is the phase's primary new artifact.
- [ ] Operator session for the Phase 16.9 update-canary (`checkpoint:human-verify`) — cannot be
      closed by an unattended executor in this environment.
- Framework install: none — pytest/node already fully set up in this repo.

## Security Domain

Phase 19 introduces no new attack surface — it performs read-only (and, for one item, an
already-armed-window-disciplined write) verification against existing infrastructure. No new
input validation, authentication, or cryptography surface is added.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | no | No new auth surface; reuses existing `HUBSPOT_PRIVATE_APP_TOKEN`/`N8N_API_KEY` credentials |
| V3 Session Management | no | N/A |
| V4 Access Control | yes (indirectly) | The armed-window discipline itself IS the access control for item 16.9 — write gate off by default, allowlisted test record only, restored disarmed after |
| V5 Input Validation | no | No new input surface — read-only checks against existing endpoints with existing, already-validated request shapes |
| V6 Cryptography | no | N/A — no secret handling changes; existing rule (never print/log token values) continues to apply |

### Known Threat Patterns for this phase's scope

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Accidental armed write during a "read-only" re-check | Tampering | Explicit `DRY_RUN=true`/no `ALLOW_HUBSPOT_RECORD_WRITES` in every command used for items 11, 15.5, 16, 16.4, 16.6; item 16.9's write is the ONLY exception and must be scoped as an operator checkpoint, never auto-executed |
| Credential value leaking into a recorded evidence file | Information Disclosure | Follow the existing repo convention (never f-string-interpolate token values into printed/logged output — already guarded by `tests/test_hubspot_node_auth.py`'s secret-printing sweep for the n8n side; apply the same discipline manually for any curl output pasted into `19-LEDGER.md`) |

## Sources

### Primary (HIGH confidence)
- Direct repository inspection this session: `.planning/STATE.md`, `.planning/ROADMAP.md`,
  `.planning/REQUIREMENTS.md`, `.planning/PROJECT.md`, `.planning/milestones/v0.3-ROADMAP.md`,
  `.planning/HANDOFF.json`, every `.planning/milestones/v0.3-phases/*/*-VERIFICATION.md` and
  `*-UAT.md`, `.planning/phases/17-*/17-VERIFICATION.md`, `17-CANARY-EVIDENCE.md`,
  `.planning/phases/18-*/18-VERIFICATION.md`, `phase-11-01-SUMMARY.md`.
- `git log -S"goal ledger" --all --oneline` and `git show 70a5fa5` — confirms the phrase's origin
  and that it was never itemized at introduction.
- `$HOME/.claude/gsd-core/workflows/verify-work.md` — read in full; confirms `/gsd-verify-work` is
  conversational, human-in-the-loop, produces `*-UAT.md`, and its `Resolution`/re-verification
  convention (`gsd_run query verification.status`) is exactly the mechanism this research's
  reconstruction relies on.

### Secondary (MEDIUM confidence)
- `scripts/deploy_n8n_workflows.py` (read for its documented DRY_RUN default behavior, not
  executed this session).

### Tertiary (LOW confidence)
- None — every claim in this document traces to a file read or command run in this session; the
  one genuinely unverified claim (the identity of "the six") is logged in the Assumptions Log,
  not presented as fact.

## Metadata

**Confidence breakdown:**
- Ledger non-existence: HIGH — exhaustive grep + git log -S across the entire repo and history.
- Six-item reconstruction: MEDIUM — strong circumstantial evidence (exact count match, all-same-
  archive-date resolution, Phase 18's own follow-up flag corroborating 16.6/16.9's risk) but no
  document confirms it was the intended set.
- Per-item offline/live classification: HIGH — each classification traces directly to that
  phase's own VERIFICATION.md "Human Verification Required" section or Resolution evidence type.
- Recording format proposal: HIGH — reuses existing, already-proven GSD conventions rather than
  proposing anything novel.

**Research date:** 2026-07-29
**Valid until:** short — this research is a point-in-time reconstruction; if Phase 18's workflow
was redeployed or any of the six items are independently re-verified before Phase 19 executes,
re-check the "Current-state risk" notes above before trusting them unchanged. Recommend treating
this as valid for at most the current planning session (do not let it sit stale across multiple
future milestones without a fresh grep).

## RESEARCH COMPLETE

**Phase:** 19 - Verification Debt Closure
**Confidence:** MEDIUM (ledger non-existence is HIGH confidence; the six-item reconstruction is a defensible but unproven inference)

### Key Findings
- The "v0.3 goal ledger" referenced by `VERIFY-01`/`STATE.md`/`ROADMAP.md` is not a file anywhere in this repo — the phrase "six `/gsd-verify-work` re-runs" is asserted six times, never itemized, and originates unexplained in the `70a5fa5` v0.3-archive commit.
- The most defensible reconstruction (exact count match, all evidence-backed): **Phase 11, 15.5, 16, 16.4, 16.6, 16.9** — the one v0.3 phase with zero verify-work history, plus the exactly five phases whose `VERIFICATION.md` required a documented `## Resolution` section (i.e., a genuine `/gsd-verify-work` re-run) to reach `passed`.
- All six were already `passed` by 2026-07-29 (ship date) — "re-run" in Phase 19 means re-confirming those verdicts against CURRENT code, not finishing incomplete work, because Phase 17 (contacts transport swap) and Phase 18 (company payload changes) both landed on code paths downstream of these verdicts afterward.
- Two items are OFFLINE-only (11, 15.5); three are LIVE-read-only (16, 16.4, 16.6); one (16.9, specifically the `company:update` half) needs an ARMED write canary that this session cannot execute and should be scoped `checkpoint:human-verify`.
- No new packages, no new code, no new test framework — this phase reuses `scripts/deploy_n8n_workflows.py`'s read-only DRY_RUN mode and the established in-process python-dotenv live-call pattern; its only new artifact should be a `19-LEDGER.md` itemizing what the original "goal ledger" never wrote down.

### File Created
`.planning/phases/19-verification-debt-closure/19-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Ledger non-existence | HIGH | Exhaustive repo-wide grep + git log -S, zero enumeration found anywhere |
| Six-item reconstruction | MEDIUM | Exact count match + corroborating same-date/Phase-18-flag evidence, but unproven — flagged as Assumption A1 |
| Offline/live classification per item | HIGH | Each traces directly to that phase's own VERIFICATION.md evidence type |

### Open Questions
1. Is the reconstructed six the actually-intended six? (recommend a one-line user confirmation before locking scope)
2. Was Phase 18's rebuilt workflow JSON ever redeployed to n8n Cloud? (settle FIRST via the read-only DRY_RUN diff — it affects how items 16/16.6/16.9 should be interpreted)
3. Is a `company:update` armed canary achievable this milestone, or does item 16.9 close as `human_needed` pending an operator session?

### Ready for Planning
Research complete. Planner can now create PLAN.md files — recommend structuring Phase 19 as: (0) re-measure the offline baseline + settle the Phase-18-redeploy question, (1) close the two OFFLINE items (11, 15.5), (2) close the three LIVE READ-ONLY items (16, 16.4, 16.6), (3) scope the one LIVE WRITE item (16.9 update) as `checkpoint:human-verify`, (4) write `19-LEDGER.md` recording all six outcomes and file a debug brief for anything that comes back non-`passed`.
