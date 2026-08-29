Plan phase 61: Autonomous batch runs (absorbs Phases 55 and 56)

## The phase in one line

**An operator hands over a batch and gets it back done.** The bar is not "does a record land" —
it is **300 contacts as one run plus one review pass, not 300 conversations.**

This is an **autonomy** phase. Identity resolution is its tracer slice, not its scope. Do not
plan this as an identity-key fix.

## Why it exists — FINDING F

An operator walk on 2026-08-30 concluded with *every individual refusal correct* and the
composition unusable. The operator's diagnosis, verbatim:

> "there is no self assessment of confidence, and therefore no autonomy in workflow, it requires
> an operator to walk through each step every single time, if an operator has hundreds of
> contacts to ingest, this means they will need to go through hundreds of research steps, and
> approval gates. That gets away from the point of doing this altogether."

The load-bearing argument:

> "the 3 separate backend services, which DO DO the research enrichment and ingestion ALREADY,
> but they clobber each other - if we keep the non-clobbering aspect while removing the
> autonomous research, enrichment and ingestion parts then this makes a worse system - guidance
> is speed, efficiency autonomy is MORE IMPORTANT than gating, permissions, security - this is a
> GTM function, not a core product or security function"

**The plugin's entire reason to exist is non-clobbering.** ZoomInfo, Apollo and Lusha already
perform the research, enrichment and ingestion. Keep the non-clobbering and remove the autonomy,
and the result is **worse than using the services raw** — which the walk demonstrated at n=1.
Every refusal in walk steps 3-6 was individually correct; **the composition of correct refusals
is the defect.**

**Scope**: absorbs **Phase 55** (async run: submit/poll/resume) and **Phase 56** (the unattended
pair pipeline). Autonomy that still holds a connection open ~100s per 2-record chunk is not
autonomy; async runs that still ask a question per row are not unattended.

**Closes**: INPUT-05, RUN-01, RUN-02, RUN-03, RUN-04, AFTER-02.

## Locked operator decisions — build to these, do NOT re-open

- **D-61-01 — best effort is the default, not the exception.** An exception per ingestion is the
  failure mode, not the safety net.
- **D-61-07 — low confidence HOLDS the row.** Confident rows proceed autonomously, no per-row
  gate. Unconfident rows are held — never guessed, never written, never asked about mid-run.
  **The batch always finishes**; a held row never stops the rows behind it. Held rows collect
  into ONE review queue cleared in a single pass at the end. **The phase needs a real confidence
  signal to hang this on — today there is none, and that absence IS the finding.** Deciding what
  confidence means (match-key strength, provider agreement, judge verdict, or a composite) is
  **core phase work, not a detail.**
- **D-61-08 — absorbs 55 and 56; Phase 57 stays separate and stays gating.** Phase 56's original
  gate survives: the first live unattended run is gated on Phase 57's ceiling work.
- **D-61-02 — no-invention is NOT loosened.** `extraction.md`'s verbatim no-invention sentence
  stays as-is. The distinction that had been collapsed: *inventing* = a value from nothing or a
  slug (still forbidden, STRUCT-04 unchanged); *resolving* = operator supplies a key, a licensed
  provider returns a sourced value, the operator confirms. **Provenance is the test.**
- **D-61-03 — strong keys only** (LinkedIn URL, email). Name-only rows keep routing to the
  existing `name_company` weak-key -> `needs_review` path. A wrongly matched person is worse than
  an unmatched one.
- **D-61-04 — the licensed waterfall keyed on `linkedin_url`, NOT `claude_web`.** `claude_web` is
  company-oriented (`object_type: companies` throughout `src/web_research.py`); for a person the
  waterfall is right and already paid for.
- **D-61-05 (CORRECTED) — front-end AND backend land together.** An earlier "front-end-only fix"
  claim was WRONG. Lusha enrich by `linkedinUrl` alone is real and live
  (`n8n/code/lushaRequest.js:79-98`). But **HubSpot matching by `linkedin_url` is DEAD ON THE
  LIVE PATH**: `n8n/code/resolveIdentity.js:76-90`'s branch is unreachable, the ingest lane's
  `ADAPT_SEARCH_RESULTS` builds `searchResultsByKey.email` ONLY, the match lane's
  `matchProposal.js::laneOf()` never reads the key, and
  `operator-claude-plugin/scripts/enrichment.py:71`'s frozen
  `MATCH_LOOKUP_KEYS = (email, firstname, lastname, company)` filters it out client-side.
  **A front-end-only fix reproduces the failure in a worse shape** — the row passes extraction
  then dead-ends in the `unchecked`/"could not look" bucket, failing later and more quietly than
  today's honest refusal.
- **D-61-06 — the identity rule is duplicated in FIVE sites** (two YAML configs, `extraction.py`'s
  gate plus its hardcoded reason string, `columnMap.js`'s hand-written JS reimplementation,
  `extraction.md` prose) with **no parity test between the YAML and the JS**. All five move in
  lockstep; leave a parity test behind.

## What is explicitly NOT relaxed

The operator kept non-clobbering **by name** ("in a non-clobbering way"). Being removed:
**approval friction and per-row research halts.** Staying: **the non-clobber merge policy, the
n8n write-safety gate nodes, `plan_grant`'s empty-record-set refusal, the material-conflict judge
gate, per-send armed-window narrowing, and the post-run written-records account.** HubSpot has
**no rollback** and ~700 live company records are reachable — those guards are what make autonomy
survivable, and they are the reason it can be granted at all.

## Requirements

- **INPUT-05** — a contact identified by a strong key alone resolves through match-then-enrich
  without being asked for fields the backend does not need.
- **RUN-01/03/04** (from 55) — submit returns a run id immediately, client polls rather than
  holding a request open; progress readable while running (done, held, failed, spend against
  ceiling); a run interrupted by restart resumes or fails loudly, never silently half-completes.
  **Where run state lives — n8n static data, a HubSpot object, or an external store — is an open
  design decision with a different failure mode per option when n8n restarts mid-run.**
- **RUN-02, AFTER-02** (from 56) — one grant carries ingest -> enrich -> create -> associate,
  creates included, association enforced (2026-08-25 contract: a contact that cannot resolve a
  company is **held, never landed**); held and failed rows land in a queue surviving the session,
  re-sendable as one well-formed request; the search-index lag between a company create and the
  contact ingest that must find it is handled by the run, not by an operator watching.

## Existing research

`61-RESEARCH.md` is authoritative on the identity half — cite, don't re-derive. Key points beyond
D-61-05/06 above:

- **D-59-08's `resolutions`/`provider_result` mechanism is a clean reuse fit** for "propose with
  provenance". Do NOT add a second proposal surface.
- **UNVERIFIED, check before relying**: a possible live property-name discrepancy, `linkedin_url`
  vs `lv_linkedin_url`. Research could not verify (no live calls). Re-list the live portal first
  — CLAUDE.md §4.0: its property tables are roadmap, not inventory.

**Biggest unknown, inherited from 55: n8n Cloud's execution model — not our code — decides what
submit/poll/resume can do. SPIKE IT BEFORE PLANNING TASKS AROUND IT.** Current ceiling is
`max_records_per_chunk: 2` with a ~100s synchronous window; a 40-record batch is 20 sequential
chunks each holding a connection open. There is a hard **2,500 n8n executions/month** budget, and
SJ-3 once burned 182k/month by fanning out per record — **execution count per record is a
first-class design constraint.**

## Hard constraints on execution (not on planning)

- **NO live n8n, HubSpot, Anthropic or provider calls during execution.** Zero credits, zero
  executions, zero live writes.
- **Deploying or arming n8n is an OPERATOR/ADMIN action, never the executor's.** A task needing a
  live deploy ends at a checkpoint requesting it.
- **Never hand-edit `n8n/wf_enrichment_cloud.json`** (generated, 809KB) — changes go through
  `scripts/build_cloud_workflows.py`.
- **Phase 46 parity rule**: a shared predicate lands in BOTH `src/icp_scoring.py` and
  `scripts/build_cloud_workflows.py`, in ONE commit.
- **Release hygiene**: any commit touching `operator-claude-plugin/` bumps
  `.claude-plugin/plugin.json` AND adds a `CHANGELOG.md` entry in the SAME commit. Plugin at
  **0.28.6**.
- **`operator-claude-plugin/tests/test_skill_sequence_coverage.py`** runs a set-equality census
  over documented `SKILL.md` python blocks; changing a documented block changes its call tuple and
  fails the census. **`GRANDFATHERED_UNCOVERED` is EMPTY and `MAX_GRANDFATHERED = 0`** — a new
  documented sequence needs a REAL composition test driving the join end to end, not a
  grandfather entry.
- **Test commands** (never bare `python -m pytest`): root `.venv/bin/python -m pytest -q`
  (baseline **3365 / 154**); plugin `.venv/bin/python -m pytest operator-claude-plugin/tests -q`
  (**1725 / 5**); node `node --test tests/n8n/*.test.mjs` (**glob form ONLY**).
- Do NOT weaken, delete or reword an existing assertion to make something pass.

## Acceptance

**Tracer**: `https://www.linkedin.com/in/robert-cavallucci-14698741/`, no other fields — the exact
row that failed the walk. Today the plugin stops and asks for a company. After this phase it
matches-or-enriches on the URL and proposes what it found, **with no per-row question**. LinkedIn
returns **HTTP 999** to the fetch tool (anti-bot); that stays handled as a tool-level refusal —
the fix is to stop needing the page, not to get it.

**Phase-level**: a batch of many contacts runs to completion unattended, with held rows collected
for one review pass and a post-run account of what was written.

## Output Format

Produce GSD PLAN.md file(s) with this YAML frontmatter:

---
phase: "61-autonomous-batch-runs"
plan: "61-01"
type: "feature"
wave: 1
depends_on: []
files_modified: []
autonomous: true
must_haves:
  truths: []
  artifacts: []
---

Then a ## Plan section with numbered tasks, each with a clear imperative title, files to create or
modify, and specific implementation steps.

**Structure**: **spike the n8n Cloud execution model FIRST** — it decides what the async half can
be, and planning tasks around an unknown execution model is how this phase fails. Then a
**tracer**: one production-quality end-to-end slice, the LinkedIn-URL-only row going in and coming
out matched-or-enriched with no per-row question, verified before any expansion. **Do NOT plan a
tracer that stops at the extraction gate** — a row that passes extraction and dead-ends in the
"could not look" bucket is the failure in a new shape, not progress. Then the confidence signal,
the hold-and-collect queue, the async submit/poll/resume, and the unattended pair pipeline.
**Multiple plan files are expected** given the scope — split by wave where genuinely blocked, and
say what blocks what.
