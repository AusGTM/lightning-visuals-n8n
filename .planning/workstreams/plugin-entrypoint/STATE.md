---
gsd_state_version: 1.0
milestone: v0.6
milestone_name: Progress
current_phase: 36
current_phase_name: Enrichment Propose Mode & Match Lane
current_plan: 5
status: blocked_on_operator
stopped_at: Phase 36 — plans 36-01 through 36-04 COMPLETE and committed; 36-05 is PAUSED at its blocking human-action checkpoint. All offline gates green (repo pytest 1960/6 from a 1933/6 baseline, plugin 1052/5 unchanged, node 609 from 553, arming grep 0, builder idempotent, zero operator-claude-plugin paths touched). DoD items 1-8 proven offline; item 9 (deploy disarmed, bounce, read back) is what the checkpoint exists to close. The deploy one-liner is denied to agents by the permission classifier and must be run by the operator via `!`; after they confirm, the agent handles the bounce (n8n_control.set_active) and the disarmed read-back. Resume by sending the deploy output to the paused 36-05 executor. ORIGINAL PLANNING NOTE — 5 plans across 5 strictly serial waves (every plan edits scripts/build_cloud_workflows.py, so files_modified overlap forces the ordering). Research verified every 36-CONTEXT.md claim against current source; plan-checker returned VERIFICATION PASSED with zero issues against 12 phase-specific hard rules. Wave order honours CONTEXT §13 — the lane stamp (Finding A) and the ingest .invalid sentinel (Finding B) land in wave 1 as independently-revertable live bug fixes, and nothing before wave 4 changes an existing caller. Phase 37 (the client half) depends on this landing first. 23-06 operator-front items (RB-3 etc.) still open, unchanged.
last_updated: "2026-08-05T05:12:10.878Z"
last_activity: 2026-08-05
last_activity_desc: Phase 36 execution started
progress:
  total_phases: 15
  completed_phases: 9
  total_plans: 65
  completed_plans: 56
  percent: 60
---

# Project State

## Current Position

Phase: 36 (Enrichment Propose Mode & Match Lane) — EXECUTING
Plan: 1 of 5
Status: Executing Phase 36. Research verified every 36-CONTEXT.md claim against current
source (zero claims failed); gsd-plan-checker returned VERIFICATION PASSED with no issues against 12
phase-specific hard rules. Wave order honours CONTEXT §13: the `lane` stamp (Finding A,
mixed-lane duplication) and the ingest `.invalid` sentinel (Finding B, manufactured
batch-wide `lookup_failed`) land in wave 1 as independently-revertable live bug fixes;
nothing before wave 4 changes an existing caller. Phase 37 (client half) waits on this.
Last activity: 2026-08-05 — Phase 36 execution started

**GATE OVERRIDE, 2026-08-05 (Phase 36 planning).** The decision-coverage gate returned
`passed: false, reason: "could-not-parse", total: 0, uncovered: []` — the documented
false-negative shape for this repo, not a real gap: `36-CONTEXT.md` states its four locked
decisions as prose under §4 rather than as `- **D-NN:**` bullets, so the parser extracts
nothing to check. Verified substantively instead — all four map to plans: propose mode →
36-04, match tiers → 36-01/36-02, Lusha widening → 36-04, oversize-`events` refusal →
36-03. Recorded here so verify-phase can re-surface it rather than inheriting a silent pass.

---

### Prior position (Phase 35, complete)

Phase: 35 (URL Structured-Representation Fallback) — COMPLETE
Plan: 2 of 3 complete (35-01, 35-02 done; 35-03 remains)
Status: `scripts/url_fallback.py` built, TDD-pinned, and now also import-set-guarded (its
"cannot reach the network" claim is proven by AST, not promised in a docstring).
extraction.md's URL adapter carries provenance/named-empty bullets, a same-host-bound
sentence, and a literal cap-quoting phrase, all pinned against the module by 7 contract
tests. No live walk yet — that is 35-03's job. No release cut yet.
Last activity: 2026-08-05 — Phase 35 plan 02 complete

**2026-08-05 — PHASE 35 PLAN 02 COMPLETE.** `extraction.md`'s URL adapter gained a
**Provenance locator** bullet (a ladder-sourced row names the URL it actually came from —
e.g. the wp-json endpoint — not the pretty page URL the operator pasted) and a **Named
empty outcome** bullet (an exhausted ladder is `url_fallback.py`'s give-up message,
relayed as a named result, per INGEST-06). All four adapters now carry the same bolded
`**Provenance locator:**` bullet shape — the screenshot adapter's was reformatted from
unbolded, line-wrapped prose. `url_fallback.py`'s "no network I/O" claim is now an AST
guard: a coarse root-import allowlist (`{json, sys, pathlib, urllib}`) plus a granular
exact-dotted-name forbidden check (catches `urllib.request` specifically, since the coarse
check alone cannot distinguish it from the allowlisted `urllib.parse`) — both layers
red-checked live. `test_extraction_contract.py` gained 7 structural pins: the script named
by path, the escalation instruction confined to the "nothing usable" region (never the
tool-error region, via a shared `_url_adapter_regions()` slicing helper), the cap the
operator is quoted imported from `MAX_FOLLOWUP_FETCHES` rather than typed in, the
same-host bound and no-same-URL-retry rule both named in prose, and the disproven
"client-rendered" verdict asserted absent from the whole file. **A genuine bug was caught
by the plan's own mandated red-check:** the first draft of the cap-parity test
(`str(cap) in text`) passed at cap=6 by coincidentally matching the unrelated
`(INGEST-06)` requirement ID a few lines below the cap sentence — fixed by pinning to the
literal phrase `"at most {cap} follow-up fetches"` and amending `extraction.md`'s prose to
actually state the number. Suites: plugin 1052/5 (1042 baseline + 10 new), repo 1933/6
(1923 baseline + 10 new), node 553 unchanged, arming grep 0. Commits `9e13890`, `e52a94d`,
`42ff387`. 35-03 (the live operator-facing walk of the acceptance URL + `0.10.0` release
cut) remains.

**2026-08-05 — PHASE 35 PLAN 01 COMPLETE.** `operator-claude-plugin/scripts/url_fallback.py`
built: `plan_ladder` (the 4-rung candidate ladder — wp-json pages-by-slug, posts-by-slug,
`/sitemap.xml`, `/wp-sitemap.xml`, locked order per 35-CONTEXT.md §3), `same_host`
(scheme-tolerant, `www.`-variant-strict netloc equality), `filter_candidates` (the guard on
sitemap-derived, attacker-influenceable candidate URLs — refuses off-host/non-http(s)/
over-cap in that order, each reason naming its own specifics), `give_up_message` (composes
the final paragraph from `{url, outcome}` pairs only — structurally cannot repeat a
rendering verdict it was never given). Zero I/O: no `requests`/`urllib.request`/
`subprocess`/scraping library, confirmed by grep and by satisfying the autouse
`no_network` test guard by construction. The acceptance URL
(`https://gctc.com.au/board-of-directors/`) produces
`https://gctc.com.au/wp-json/wp/v2/pages?slug=board-of-directors` as its first candidate —
the exact URL measured live 2026-08-05 to return all 9 directors — pinned at both the
direct-import and CLI-subprocess layers. `extraction.md`'s "Fetched but nothing usable"
branch now names `scripts/url_fallback.py`, explains the 15-minute fetch cache (why a
same-URL retry is never suggested), and walks the propose→approve→filter→give-up flow;
"Fetch failed" states in its own text that the ladder does not run on a tool error; the
"likely a client-rendered page" phrasing is gone (`grep -c 'client-rendered'` → 0). Two
deviations: a D-07 while-loop guard violation in the CLI's argv scan (rewritten as
`name_split.py`'s `for enumerate` shape), and two untracked/gitignored debug artifacts
left in `scratch/` by the live UAT 2.4 walk (removed — pre-existing, blocked full-suite
green, touched no tracked file). Suites: plugin 1042/5 (1022 baseline + 20 new), repo
1923/6 (1903 baseline + 20 new), node 553 unchanged, arming grep 0. Commits `ae45c4b`
through `b13c2bf` (7 total, RED/GREEN per task). 35-02 (provenance naming the URL actually
fetched, an AST import-set guard, contract tests tying extraction.md's cap/branch wording
to the module) and 35-03 (the live operator-facing walk + `0.10.0` release cut) remain.

**2026-08-05 — PHASE 34 COMPLETE (both halves, backend live).** Plugin `0.8.0` cut with the
version bumped in the same commit as the CHANGELOG.

Half A: `e-mail address`, `org.` and `linkedin profile` widened in all three alias tables
(`config/column_mapping.yaml`, the plugin's byte-identical shipped copy, and
`n8n/code/columnMap.js`), guarded by `tests/n8n/columnMapAliasParity.test.mjs` — written and
green BEFORE any alias moved, because the two tables agree by hand, not by construction, and
widening one alone would make the preview confidently promise a mapping the backend does not
perform. The operator ran the disarmed deploy (the classifier denies it to agents in both the
shell and python-driver forms); the four active workflows were then bounced deactivate→activate,
each verdict from an independent second read, `LV Review Decision` untouched and still inactive.
A GET of the live `LV Contact Ingest` `Map Columns` node confirms all three aliases in the
RUNNING body. `verify_live_write_safety.py --expectation disarmed` → `VERDICT: disarmed PASS`.

Half B: step 2b in `contact-upload/SKILL.md` — one confirmation per header, that column's own
`sample_values` shown beside it, a batched yes explicitly not accepted. `Full Name` refused with
its reason named. The corrected file is the one path previewed AND dispatched, proven on the
recorded multipart body rather than the path argument.

Against `22-messy-headers.csv`: 4 of 7 headers now map with nothing typed (2 before), `Ph.` is
suggested, `Full Name` refused, `Notes` honestly dropped. Suites: plugin 1002/5, repo 1883/6,
node 553, arming grep 0. **UAT 2.2 walked PASS by the operator on 2026-08-05 against `0.9.0`** — the mark was held at
`fixed-awaiting-walk` until they observed it, which is the whole method. `0.9.0` added the
reviewed per-row name split (amendment 6a) after the walk showed the flat `Full Name` refusal
was stricter than the suggest-and-confirm pattern beside it. Marketplace clone refreshed.

**2026-08-04 — Phase 34 plan 01 complete.** `operator-claude-plugin/scripts/header_suggest.py`
built: `suggest_headers()` proposes a canonical prop via `difflib` against the 7 canonical props
only (reusing `preview._normalize_header`/`preview._load_aliases`, never a second normalizer or
YAML read), carrying `sample_values` so a confirmation isn't a rubber-stamp; a dedicated
`REFUSE_NAME_SHAPES` pre-check refuses `Full Name` and its variants before `difflib` ever runs,
proven to hold at any cutoff (not by cutoff tuning — measured, `"full name"` outscores `"ph."`'s
own correct answer). `apply_confirmed_corrections()` writes a header-row-only corrected file
under `scratch/`, guarded by a canonical-target allowlist and a repeated name-shape refusal, both
checked before any file is opened for writing. Every property proven at the CLI subprocess layer
against an isolated plugin root. Plugin suite 989 passed/5 skipped (960 baseline + 29 new); repo
suite 1870 passed/6 skipped; node 553 pass; `git status --short operator-claude-plugin/scratch`
empty. Commits `bfe202d`/`579c75b`/`aa89521`. Plans 34-02 (alias widening), 34-03 (skill wiring),
34-04 (release) remain.

**2026-08-03 addendum (autonomous front):** Phase 32 (llm-free-sweep-trigger) plan 32-01 —
the LLM-free sweep wrapper (`lv-sweep-run.sh`), its two-sided contract test, the rewritten
`SWEEP-CRON-TEMPLATE.md`, and the amended `29-HOST-PROBE.md` D-01 — is built and committed.
The phase is gated on 32-02: the live RB-8 re-run against the new trigger. NOTICE-03 in
REQUIREMENTS.md stays **BLOCKED** until that live gate passes.

**2026-08-04 — PHASE 33 COMPLETE (RB-10 walked).** All four plans executed and the release gate
walked on the real machine. Config and the dashboard pointer now live in
`~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/`. RB-10 answered
Research Open Question 1 by observation — **no permission prompt fires** on writes into that
directory — and proved the migration live (0600, byte-verified, source removed). It also FOUND A
DEFECT nothing else caught: both resolvers fell back to the install folder when the file existed
nowhere, so a first-ever pointer or config was still stranded. Fixed in `0.7.2`. STATUS-05 is
proven for the first time — a first-ever pointer landed in the durable home and a brand-new
conversation resolved to the same URL. Releases: `0.7.0` (the phase), `0.7.1` (UAT 2.6 empty-input
branch), `0.7.2` (the RB-10 defect). Findings: `33-FINDINGS.md`.

**Superseded in-progress note:** Phase 33 (durable-operator-state) plan 33-01 —
the tracer: `durable_paths.py`'s shared resolver, `config_gate`/`init_check` wired through
it, resolution order pinned at the CLI subprocess against a fake `HOME` — is built,
tested (12 new tests, plugin suite 923/5), and committed.

**2026-08-04 addendum (autonomous front):** Phase 33 plan 33-02 — the sibling-scan
migration (`_migrate_once`: copy, verify byte-for-byte, delete only then, per the
operator's own checkpoint decision) — is built, tested (15 new tests, plugin suite
938/5), and committed. A blocking constraint found after planning (the sweep inheriting
a code path to the same irreversible delete) was resolved by an `allow_migration` flag
threaded through the whole resolution chain, keeping `sweep_entry` structurally
read-only; `test_sweep_read_only.py` gained a filesystem-write AST guard to close the
HTTP-verb guard's blind spot. 33-03 (dashboard-pointer wiring) and 33-04 (doc sweep +
release cut + RB-10) remain.

**2026-08-04 addendum (autonomous front):** Phase 33 plan 33-03 — `artifact_store.state_path()`
now delegates to `durable_paths.resolve_state_path()` (the pointer is no longer a second
hardcoded location), STATUS-05 is proven true again across a simulated version bump at the
CLI subprocess layer, and `/operator-claude-plugin:initialize` names the resolved settings
path's location (durable/legacy/env) without ever claiming a migration happened — is built,
tested (9 new tests, plugin suite 947/5), and committed. 33-04 (doc sweep + release cut +
RB-10) remains.

## Accepted requirement amendments (reconcile before each phase seals)

Six places (one with a later extension) where a locked decision or a verified research finding diverges from the written
requirement. Each was surfaced explicitly and chosen deliberately — none is a silent drift.

| # | Requirement | Amendment | Source |
|---|---|---|---|
| 1 | PLUGIN-02 | Operator, not admin, performs config setup from the committed example file | Phase 23 D-05 (wording reconciled in REQUIREMENTS.md by 23-05) |
| 2 | Phase 25 criterion 2 | Provider default ships as full waterfall, so silence enables providers. Mitigated: `Parse HubSpot Event` has no server-side default and fails closed, and the resolved selection is always shown in the preview | Phase 25 D-05 / D-06a |
| 3 | STATUS-04 + Phase 27 criterion 4 | "Stuck lock" redefined as a long-running execution. `enrichment_lock_until` does not exist and `lv_enrichment_status` is never set to `running` | Phase 27 D-07a–d |
| 4 | REPORT-02 | ICP-tier clause removed entirely. HubSpot owns the derived ICP outputs per Phase 15 Approach C; the backend has nothing to read back and a placeholder would imply otherwise | Phase 26 D-10a / D-10b |
| 5 | CONTROL-01 + Phase 28 criterion 1 | Off-cycle scheduled-scan execution dropped. No n8n API endpoint exists (upstream PR #20304 unmerged). Operator controls scans via enable/disable and re-timing instead | Phase 28 D-05a–c |
| 6 | REQUIREMENTS.md Out of Scope — "Re-implementing column mapping, phone/email normalization, verification, or dedupe — these live in n8n and must stay single-source-of-truth" | Header-alias **suggestion** with per-header operator confirmation is permitted in the client. **Silent client-side column mapping remains excluded.** The backend's `Map Columns` stays the single authority on what a header means; the client only helps the operator produce a file the backend can read, and never rewrites a header without an explicit yes | Phase 34 (operator decision 2026-08-04, from UAT 2.2's failure; 34-CONTEXT.md §4) |
| 6a | Extends amendment 6 — it said the client transforms header STRINGS only, never data | One **reviewed, per-row, this-file-only data transform** is permitted: splitting a full-name column into `firstname`/`lastname`. The splitter proposes per row with a confidence and a named reason, the operator resolves every row, and `apply_name_split` writes ONLY the operator's resolved values — it has no splitter of its own to fall back on and refuses a resolved list that does not match the row count. **It is never sent to the backend as a rule, never stored, never indexed**, and `Map Columns` still has no name-splitter. Rationale: refusing outright was stricter than the suggest-and-confirm pattern immediately beside it, and produced rows that failed the identity rule for want of a split the operator could have made in one turn | Phase 34 follow-up (operator decision 2026-08-05, during the UAT 2.2 re-walk; shipped in plugin `0.9.0`) |

## Backend changes v0.6 requires (not client-only)

- **Contact-lane create gate** (Phase 23 D-16a/D-16b) — `Set Config` hardcodes `allow_create: false`,
  so the contact lane cannot create a record today. Fix **reuses the existing overlayable
  `ALLOW_HUBSPOT_CREATE`** (no fifth flag — `_OVERLAYABLE_FLAGS` is pinned to four names by
  `tests/test_enabled_build_invariants.py`) and is baked into **`Decide Action`**, not `Set Config`
  — `Extract From File` emits fresh items, so anything seeded upstream is lost (BUG 12 / BUG 21
  row-loss family). Lands first in Phase 23 as plan 23-01.

- **List/view resolution** (Phase 25 D-02) — plus an unresolved feasibility question: HubSpot saved
  views have no public API, and `crm.lists.read` scope is unevidenced in this repo.

- **Credit-only status endpoint** (Phase 25), generalized to full health (Phase 27).
- **`hubspot/review/decision` webhook + `ALLOW_HUBSPOT_REVIEW_WRITES` flag** (Phase 30 D-08e).

## Progress

**Phases Complete:** 10 / 10 — Phase 30 closed 2026-08-04 (RB-9 close: REVIEW-04 demonstrated, D-31 endpoint probe recorded)
**Current Plan:** 1

```
[█░░░░░░░░░░░░░░░░░░░] 8%
```

| Phase | Requirements | Status |
|-------|--------------|--------|
| 23. Walking Skeleton | 10 | **Complete** — RB-3 armed create canary passed (contact 342770428400, run 1129) |
| 24. Non-Tabular Input Adapters | 8 | **Complete** |
| 25. Enrichment Lane & Cost Guard | 4 | **Complete** — B4 measured 37.44 s, chunk ceiling 2 CONFIRMED |
| 26. Outcome Reporting & Safe Retry | 4 | **Complete** (one open defect: thin-response reason is belief, not observation) |
| 27. Backend Status Surface | 6 | **Complete** — RB-4 approved; dashboard same-URL proven cross-session |
| 28. Control Actions | 7 | **Complete** — RB-7 armed canary passed 2026-08-03 (exec 1152, 54.37 s window, bounded to 1 record) |
| 29. Notices & Unattended Sweep | 5 | **Complete via Phase 32** — NOTICE-01/02/04/05 complete; NOTICE-03 sealed by the LLM-free trigger (RB-8 re-run passed) |
| 30. Review-Queue Triage | 5 | **Complete** — RB-9 close 2026-08-04 (armed window #2): valid-enum approve landed on `9604614548`; REVIEW-04 demonstrated (human source/timestamp/reason stamped, `superseded_source: waterfall` readable); REVIEW-02 complete via D-31 endpoint probe (`domain` withheld on preview AND submit; backstop path NOT probed — allowlists by key, `domain`/`annualrevenue` writable there); disarmed close PASS, neighbors 0 |
| 31. Enum Validation for Review Approvals | — | **Complete** — planned, executed, and proven live (BUGS 28/29/30 closed; refusal observed against the real legacy candidate) |
| 32. LLM-Free Sweep Trigger | — | **Complete** — wrapper shipped + two-sided pinned; RB-8 re-run PASSED under real cron (silence, loud-failure, zero credits) |

## Accumulated Context

### Pending Todos

- ~~`2026-08-03-sweep-cron-credentials-block-notice-03`~~ — **RESOLVED by Phase 32** (LLM-free
  trigger; RB-8 re-run passed 2026-08-03). Moved to completed.

- `2026-08-03-sweep-lookback-has-no-time-window` (major) — a fixed 100-row execution lookback with
  no time bound re-notifies an already-fixed failure until 100 newer executions displace it; plus
  the notice cannot name the failing workflow.

- `2026-08-03-fix-bugs-28-30-enum-validation-for-review-approvals` (major) — enum
  validate-and-refuse for review approvals; blocks RB-9 step 8's re-run. Decision recorded:
  no full mapping layer, exact label→value match only. **Phase 31 (out-of-band PRD Express
  Path, tracked separately from the Phase 23-30 sequence above): 31-01 (the enum spine,
  BUGS 28/29) and 31-02 (the explicit `not_allowlisted` refusal + corrected client
  messaging + runbook fix, BUG 30) are DONE, 2026-08-03. 31-03 DONE 2026-08-03 —
  contract inventory committed, checkpoint executed: disarmed redeploy + bounce, read-back
  disarmed PASS with declaring nodes 11→12 (the predicted +1, proof the deploy landed).
  **PHASE 31 COMPLETE. The live tenant now carries the fix; RB-9 step 8's re-run needs only
  a fresh needs_review fixture.**

**Decisions:**

- Phase numbering starts at 23 — v0.5 ended at phase 22; continuing avoids phase-directory
  collision with the archived `.planning/workstreams/milestone/` phases 20–22.

- The plugin is a front door, not a second pipeline. Column mapping, phone/email
  normalization, verification, identity resolution, dedupe and create/update routing stay
  in n8n. The plugin structures only *non-tabular* input; tabular input passes through.

- Walking skeleton before breadth: one input shape (spreadsheet), one lane
  (`hubspot/contact-upload`), disarmed, end to end in Phase 23 — so something demonstrable
  exists before the other adapters land.

- Dispatch ships disarmed, per the repo's established two-key write gate (phases 19–22).
  Approval at the preview is not arming; arming is a separate deliberate operator step.

- URL ingestion uses the native Anthropic `web_fetch` server tool on the existing client
  and `ANTHROPIC_API_KEY` — no new dependency. Anti-bot-detection is out of scope by
  requirement.

- Screenshot ingestion (INGEST-07) is a fifth adapter into the same Phase 24 choke point, not
  its own phase — it differs from the prose/URL adapters only in the read (vision on an
  attached image) and in needing a legibility signal, not in preview, dispatch, or gating.

- Client code lives in `operator-claude-plugin/` with its own README + CHANGELOG, versioned
  independently. It is documented as a *suggested default thin client*, not the interface: n8n is
  a standalone backend over plain HTTP, so other front ends (Slack, web app, CLI) can be built
  against the same contract, concurrently. Client never imports enrichment logic; the only
  backend edit this milestone makes is the new n8n-side status endpoint.

- **v0.6 is the control plane as well as the front door.** The operator is non-technical, works
  in Claude Desktop, and never opens n8n. Anything n8n would surface in its own UI has to arrive
  in the conversation, and "run this command" is a requirement failure, not a fallback. Phases
  27-30 add read, control, notices, and review triage.

- Control depth stops short of deploy: allowlisted mutations only (write-safety flag overlay,
  schedule cadence, workflow active state). Editing nodes, credentials, or workflow structure
  stays an admin task run from this repo.

- Arming is conversation-scoped. n8n's baked flag is persistent; the plugin's willingness to use
  it lapses with the session. Both facts must show in status — conflating them is how a silent
  live send happens.

- The plugin performs the arming write itself (the operator cannot run a command), via the
  existing `enable_baked_flags()` overlay + `PUT /api/v1/workflows/{id}`, with diff shown,
  explicit confirm, and read-back verification. Standing constraint: agent tooling here is
  blocked from arming writes, so the armed path needs a human executing even though the
  operator-facing design is a yes/no in chat.

- The plugin holds no provider or HubSpot credentials — those stay in n8n, admin-managed. So
  credit balances must come back through a new n8n-side status endpoint;
  `scripts/check_provider_credits.py` is an admin tool, not a model for the plugin. Phase 25
  builds the credit-only slice, Phase 27 grows the same endpoint into full health.

- Status presentation: conversational text by default, dashboard Artifact on request
  (re-published to the same URL, stamped with fetch time).

- Review triage happens in Claude with writeback, gated separately from dispatch and honoring
  the existing field-policy classes — a second CRM write path, not a bypass of the merge policy.

- Screenshots are operator-attached, never plugin-captured. No browser automation, no login,
  no scroll-and-shoot. A screenshot is not a bypass of the scraping exclusions: LinkedIn
  profile fields still come from the licensed provider waterfall.

- **23-01 closed D-15/D-16/D-16a/D-16b.** `Decide Action` (contact-ingest Cloud workflow) now
  derives its create decision from the existing overlayable `ALLOW_HUBSPOT_CREATE` constant
  (composed at the `build_cloud()` build site, not `Set Config`), instead of a hardcoded row
  field — an armed deploy can now actually create a net-new contact, with the same
  `TEST_RECORD_*` allowlist requirement as every other write path. No fifth overlay flag added;
  no file under `operator-claude-plugin/` touched.

- **23-02's live smoke test resolved D-14a with a positive result**, widening 23-04's build: an
  operator attachment in the Code tab resolves to a real filesystem path (not just
  conversation-content), `@mention` also resolves to a real path (workspace-scoped only),
  `python3` is available, and `openpyxl`/`requests`/`PyYAML` import with no install step. 23-04
  built the genuine two-legged file handoff (attachment + `@mention`) rather than the
  single-leg-plus-try/except degradation the plan text originally anticipated.

- **23-04 is the walking skeleton itself.** `config_gate.py` → `tabular.py` → `dispatch.py`
  wired end to end, proven against a stub transport: `armed` has no default (TypeError if
  omitted), the unarmed path leaves the stub's call log empty, and the armed path produces the
  exact `hubspot/contact-upload` multipart contract (header `X-Enrichment-Secret`, file field
  `data`, `text/csv`). Plugin manifest + `skills/contact-upload/SKILL.md` give it one loadable
  entry point (auto-triggered and slash-invocable, no `commands/` duplicate). An AST-based
  guard now makes PLUGIN-04 (no backend import) a test, not a promise. Full repo suite: 741
  passed, no regressions; no file outside `operator-claude-plugin/` touched.

- **23-05 replaced the 23-04 preview placeholder with the real adaptive preview.**
  `preview.py`'s `label_headers()`/`build_preview()` read `config/column_mapping.yaml`
  as a read-only display lookup only (mirroring `Map Columns`' case-insensitive,
  whitespace-collapsed rule exactly rather than improving on it), never transforming a
  row — a byte-identity test proves the source file is untouched. ≤20 rows renders every
  row; above that, first-10/last-3 plus per-column fill rates (including dropped
  columns). SKILL.md, README.md, and CHANGELOG.md now teach setup and usage end to end,
  and PLUGIN-02's wording was reconciled with D-05 (operator self-setup replaces the
  stale admin-provisioned text, in both REQUIREMENTS.md and two stale README passages
  that had drifted the same way). Full repo suite: 749 passed, no regressions; no file
  outside `operator-claude-plugin/` or `.planning/` touched.

- **24-01 built the extraction validator spine** — `operator-claude-plugin/scripts/extraction.py`
  validates (never extracts) a Claude-written JSON artifact: `canonical_props()` and
  `identity_groups()` derive from `config/column_mapping.yaml` rather than being retyped;
  `has_identity()` trims before checking presence, matching the deployed `Map Columns` node's
  `requiredIdentity()` rather than the untrimmed `src/file_loader.py::_has_identity`; a
  non-canonical key is stripped from the row AND reported (record index + key) before the
  identity check runs; every artifact-shape failure raises a distinct `ExtractionError` code
  (never a silent zero-row success); `write_dispatch_csv()` raises on any row key outside the
  canonical set, including a smuggled `provenance` key, so STRUCT-01 is structural, not a
  runtime filter someone can forget. `preview.py` gained `resolve_mapping_path()` (one shared
  mapping-file lookup) and `build_extracted_preview()` (provenance/rejects/dropped-keys/
  ambiguities in one structure, reusing the same adaptive-sample rule). Full repo suite: 774
  passed at completion (749 baseline + 25 new); no file outside `operator-claude-plugin/` or
  `.gitignore` touched. 24-02 (screenshot dedupe, ambiguity aggregation) and 24-03 (the four
  adapters wired into SKILL.md) build on this artifact contract next.

- **26-01 built the contact-upload report tracer** — `operator-claude-plugin/scripts/executions_client.py`
  (read-only `X-N8N-API-KEY` GETs, pure `find_execution_for_dispatch()` time-proximity
  correlator marked `best_effort`) and `report.py` (`contact_row_ledger()` reads `Decide
  Action`'s own output, never `Set Review`'s stripped `{"queue": "needs_review"}`;
  `reconcile()` downgrades a decided update/create to `not_confirmed` when the terminal
  write node produced zero items; `build_contact_report()` treats any non-settled or
  unrecognised execution status as `in_flight`, never finished). `sync_response_is_
  sufficient()` gates the synchronous webhook body, falling through to the executions
  API when it's `Set Review`-shaped. SKILL.md's step 7 renders counts first, the
  failing rows in full, the `NO_EMAIL`/`ambiguous` permanently-stuck case named
  plainly, and a run handle whose re-check is explicitly manual-only — an AST guard
  now makes D-07 (no poll loop) a property the suite enforces. Full repo suite: 869
  passed at completion; no file outside `operator-claude-plugin/` or `.planning/`
  touched. Known artifact: a concurrent-agent git-index race (24-02/24-03 sharing
  the same working tree) misattributed one commit's message to the wrong diff —
  content-correct, cosmetic only, documented in 26-01-SUMMARY.md's Issues Encountered.

- **27-01 grew `hubspot/backend-status` from Phase 25's credit-only slice into full
  health.** `n8n/code/backendStatus.js` (`extractSearchTotal`/`deriveSourceHealth`/
  `buildStatusBody`, 22 unit tests) plus four HubSpot count searches
  (requested-unresolved / awaiting-review, companies + contacts, OR'd filter groups so
  an absent `lv_enrichment_status` isn't silently under-counted by NEQ) and a
  credential-health block for the three providers plus HubSpot. Honored the
  plan-checker retarget: extended `build_backend_status_cloud()` /
  `wf_backend_status_cloud.json` (confirmed the only file serving this endpoint),
  `wf_enrichment_cloud.json` regenerated byte-identical. Full repo suite: 919 passed
  (900 baseline + 19 new), no file outside `n8n/`/`scripts/`/`tests/` touched.

- **27-03 (the phase tracer) proved the D-01/D-02 credential split end to end.**
  `n8n_read.py` (GET-only — no mutating verb exists in the module at all) reads workflow
  state, execution outcome and the write-safety literals with `X-N8N-API-KEY`;
  `backend_status.py` asks the n8n-side endpoint with `X-Enrichment-Secret` for what needs
  credentials the plugin does not hold; `status.py` composes one workflow into one mapping
  (so 27-04's widening is a loop, not a rewrite) and renders anything the backend could not
  supply as the word unknown — a genuine 0 and a False survive intact. `config_gate` gained
  per-capability refusal: a missing `n8n_api_key` disables the status check by name and says
  contact upload still works, rather than presenting as broken. Two new config keys
  (`n8n_api_key`, `stuck_execution_minutes`) documented in the committed template. Repo
  suite 992 passed / 1 skipped (+73 from this plan), node 400 unchanged, nothing under
  `n8n/` touched. **The plan's instruction to widen the network guard to `requests.get` was
  refused, not followed** — it restated the claim 27-CONTEXT D-11 refutes; a test asserting
  the existing coverage was added instead, and both D-11 and the plan now record it so it
  cannot be re-litigated. STATUS-01 deliberately left Pending: the breadth is 27-04's.

- **27-04 delivered the breadth, and STATUS-01 is now Complete.** `status.describe_all()`
  reports **every** workflow the key can see with no allowlist (D-07) — a source-scanning
  test fails if one is ever introduced — at a cost of two calls: the workflow collection
  plus one bounded executions page grouped by workflow, with a filtered top-up read for any
  workflow absent from that page (a bounded page is not history, and a failed top-up reports
  `unknown`, never never-run). **"Stuck" is an execution-age verdict** on data the client
  already holds (D-07b); no HubSpot lock state is touched, and the verdict is **tri-state** —
  `None` means in flight with an unreadable start time and must never be flattened to
  `False`, which would render an unjudgeable run as fine (folded into CONTEXT as D-07b(i)).
  `execution_errors.harvest_errors()` reads failures out of **per-node output**, so a
  provider 401 inside a run n8n reports `success` still surfaces (D-04b); identical findings
  collapse per `(node, cause)` with a count, and every one goes through 27-02's
  `error_table.translate()` — the module contains no `who_can_fix=` at all, so no caller can
  blame the operator for an unrecognised signature. `render_text.py` and
  `skills/backend-status/SKILL.md` give the plain-language answer; the skill states in its
  first paragraph that it only reads. One correction folded into CONTEXT under **D-10**:
  `describe_all()` uses a collection entry as the workflow body only when it carries a
  `nodes` list and fetches the body otherwise — deleting that fallback would make
  write-safety read `unknown` for every workflow at once. Repo suite 1065 passed / 1 skipped
  (+72), node 400 unchanged, nothing under `n8n/` touched.

- **Phase 31 Plan 02 (2026-08-03) closed BUG 30** — the review-decision endpoint's
  `Build Review Decision` node now runs the same `_writeSafetyAllows("review", ...)` check
  the spliced write gate applies and answers an explicit `outcome: "not_allowlisted"`
  refusal before the row ever reaches the gate (which is unchanged and proven, by a new
  agreement-matrix test, never to disagree with the pre-check). The plugin client
  (`review_decision.py`) now treats `not_allowlisted` as non-writing and reports it
  `not_written`; an `unparseable_response`/`no_response` now correctly means the workflow
  itself failed, pointing the operator at n8n execution history rather than
  `TEST_RECORD_IDS` — the exact wrong turn RB-9 took live. Two-sided pin:
  `operator-claude-plugin/tests/test_review_outcome_parity.py` reads
  `n8n/code/reviewDecision.js` AND the committed `wf_review_decision_cloud.json` as text
  against `review_decision.OUTCOMES`. OPERATOR-RUNBOOK RB-9 corrected to match (diagnostic
  advice, snapshot script flags, canary-record-cleared note). Nine pre-existing tests that
  encoded the old "gate-only-armed" assumption were updated, not left broken (31-02-SUMMARY
  Deviations). Full suite: node 550 pass (was 540), pytest 1697 passed/6 skipped (was 1689).

- **29-04 built the bounded in-session watch** — `operator-claude-plugin/scripts/watch.py`'s
  `poll_until_settled()` is a pure function of an injected clock/reader with exactly two
  `return` statements, each producing a full report (`build_settled_report` /
  `build_still_running_report`); "returns nothing" is not reachable. The bound defaults to
  the measured `600s` from `29-TIMING.md` (`watch_bound_seconds` in the committed config
  template), scaling per-record for a known multi-record dispatch. The settled report
  renders through the lane-matched Phase 26 renderer (never a third convention), adds a
  provider-credit delta that reports `unknown`/`"partial"` rather than a substituted zero
  when either end of the pre/post balance pair is unreadable, and inherits D-10a/D-10b's
  no-ICP rule and D-14's no-email-is-not-retryable wording for free. The still-running
  report states its run-handle correlation is by timing, not an execution id (D-12). The
  unprompted-delivery bonus (29-HOST-PROBE A2 = NO) changes only a `delivery_mode` label,
  proven identical either way. Deviation: `test_report_sufficiency.py`'s pre-existing D-07
  no-poll-loop guard needed a one-line named allowlist for `watch.py` — the module D-07
  always intended as the exception. Plugin suite 859 passed/5 skipped at completion.

- **29-05 shipped the full condition set, after a prerequisite fix that unblocks all of
  them:** the live `hubspot/backend-status` webhook answers array-wrapped (a one-element
  list), and `backend_status.fetch_backend_status` only accepted a bare dict — every real
  answer read `unrecognized_response_shape`, closing the long-standing HANDOFF §3 bug.
  Fixed and pinned both shapes before any plan task. `sweep_conditions.py` then gained
  quota-exhausted/credential-failure (D-08a's new judgment over Phase 27's credit-probe
  data — a four-way quota outcome so unknown can never become exhausted), failed-run,
  review-backlog, the maintenance workflow's swallowed-failure blind spot (D-08b, via one
  gated `get_execution` + `harvest_errors` read per D-17), and stuck-armed (D-10, both
  `status.WRITE_SAFETY_FLAGS` checked independently, a truthy `disagreement` firing
  rather than being swallowed as unknown per D-16). `sweep_notify.py` now groups more
  than one fired condition into a single delivery (most-actionable-first, capped, a
  stated remainder count) and every notice carries the full `error_table` verdict
  (`who_can_fix`, `is_interpretation`, `raw`), not just the attribution. Deviation: a
  concurrent process sharing this (non-worktree-isolated) working tree absorbed Task 3's
  commit into its own (`dfd1178`) — content verified byte-identical to what was authored
  and tested; commit-boundary only, no functional impact (29-05-SUMMARY.md Deviations).
  Plugin suite 882 passed/5 skipped, repo suite 1763 passed/6 skipped, node 550 passed —
  all unchanged in count except the plugin suite's growth.

- **33-01 built the phase's tracer: `durable_paths.py` as the single config-resolution
  authority.** `resolve_config_path()`/`resolve_state_path()` implement steps 1–4 (explicit
  path arg, `LV_OPERATOR_CONFIG`, durable home, same-install legacy) with step 5 (33-02's
  sibling-scan migration) left as a marked insertion point, not stubbed. `config_gate.py`'s
  frozen `DEFAULT_CONFIG_PATH` constant is gone, replaced by `config_path()` resolved fresh
  on every call; `init_check.py` reads the same function instead of its own copy. Every
  behaviour is pinned by driving `config_gate.py` as a subprocess against a fake `HOME`
  (`_run_cli` extended with `env=`/`durable_config=`, built from a literal dict, never
  `{**os.environ}`) — the durable home wins over the legacy path, `LV_OPERATOR_CONFIG` wins
  over the durable home, a mistyped override names its own path, and no secret leaks on any
  refusal branch. One necessary out-of-plan fix: `test_sweep_read_only.py`'s read-only
  import-closure allowlist needed `durable_paths` added (config_gate now imports it; it
  performs no I/O beyond `.exists()` checks). Plugin suite 923 passed/5 skipped (+12 from
  911 baseline), repo suite 1804 passed/6 skipped (+12), node 550 unchanged.

- **33-02 built the sibling-scan migration and closed a risk the plan's own checkpoint
  decision opened.** `durable_paths.py` gained `_atomic_write_0600` (tempfile-in-target's-
  own-dir + chmod 0600 + fsync + `os.replace`), `_newest_sibling_holding` (newest sibling
  install that actually holds the file, excluded by resolved-path equality, filtered
  before the version sort so a stray `.DS_Store` can't crash it with a `TypeError`), and
  `_migrate_once` (verify-then-delete: copy, read the durable copy back and match it
  byte-for-byte, only then unlink the sibling's copy — the operator's own checkpoint
  answer, `delete-immediately`). Both resolvers call it as resolution step 5. Because that
  delete is irreversible and lands in a module (`durable_paths.py`) `config_gate` imports —
  which puts it in `sweep_entry`'s transitive closure — a new `allow_migration` flag
  (default `True`) was threaded through `resolve_config_path`/`resolve_state_path` and
  `config_gate.config_path`/`load_config`, and `sweep_entry` gained a dedicated default
  loader (`_load_config_no_migration`) that always resolves read-only: the unattended
  sweep never scans, writes, or deletes, even when a migration is genuinely available: it
  reports the existing `sweep_not_configured` notice instead. `test_sweep_read_only.py`'s
  compensating write-verb guard was HTTP-verb-shaped (`post`/`put`/`patch`/`delete`) and
  structurally blind to `open`/`os.replace`/`Path.unlink`/`os.chmod` — extended with a
  parallel filesystem-write AST scan (narrowed so bare `.replace()` doesn't false-positive
  against `n8n_read.py`'s `datetime.replace(tzinfo=...)`), a function-level confinement
  check, and a behavioral test proving the sweep's actual run never migrates (with a
  control proving the identical layout DOES migrate when allowed, so the abstention is
  meaningful). Plugin suite 938 passed/5 skipped (+15 from 923 baseline), repo suite 1819
  passed/6 skipped (+15), node 550 unchanged.

- **33-03 gave the dashboard pointer the identical treatment the config got and closed
  the loop on `initialize`.** `artifact_store.state_path()` now returns
  `durable_paths.resolve_state_path()` instead of a hardcoded `PLUGIN_ROOT/state/`
  constant — `DEFAULT_STATE_PATH` is gone. The three "where the file lives" tests were
  retargeted, not deleted: the dotfile test narrowed to `path.name` only (D-04 was
  always about the filename, never a dot-prefixed ancestor — the plugin's own install
  root already sits under `~/.claude/plugins/cache/`), the inside-plugin test replaced
  with its exact negation, and the `git check-ignore` test replaced with an
  outside-the-repo assertion (strictly stronger — `git check-ignore` errors on a path
  outside the working tree, which is exactly where the durable home resolves to). Both
  retargeted tests isolate via `CLAUDE_PLUGIN_DATA` pointed at a `tmp_path` directory
  rather than touching real `~/.claude`, needed because a bare repo checkout has no
  version-named siblings to migrate from and would otherwise resolve to the legacy
  path regardless of the code being correct. STATUS-05 — "a brand-new conversation
  lands on the SAME dashboard URL" — is proven true again across a SIMULATED VERSION
  BUMP, driven at the CLI subprocess layer (`_run_store`, mirroring
  `test_config_gate.py::_run_cli`, copying `artifact_store.py` +`config_gate.py` +
  `durable_paths.py` for the `__main__` import chain): a pointer saved from `0.6.2` is
  read back from `0.7.0` with no `state/` of its own, via the same sibling-scan
  migration 33-02 built — not a special case for the pointer. `init_check.py` gained
  `config_location` (`env`/`durable`/`legacy`) and one reassurance line in the
  already-set-up branch naming what that location means for the operator; a code
  comment records why migration is never mentioned on any branch (criterion 4 — the
  check reads a resolved path and has no way to know whether it moved anything).
  Plugin suite 947 passed/5 skipped (+9 from 938 baseline), repo suite 1828 passed/6
  skipped (+9), node 550 unchanged.

**Todos / carried context:**

- 24-03 must write `extraction.md`'s documented artifact schema example(s) such that a
  contract test (D-13) can parse the fenced examples out of the markdown and run them
  through `extraction.py`'s real `validate()` — this pin was not yet built in 24-01 since
  `extraction.md` itself doesn't exist until 24-03.

- Phase 26 planning must first verify what `hubspot/contact-upload` actually returns:
  `responseMode: lastNode` over a branching graph may not carry every row's outcome. The
  n8n executions API (`scripts/enrichment_cost_ledger.py`) is the fallback source.

- XLSX must be converted to CSV bytes before POST — the workflow's `Extract From File`
  node runs `operation: csv`. `src/file_loader.py` already reads CSV/TSV/JSON/XLSX.

- Enrichment payloads must set `providers` explicitly; absent/unrecognized means no
  provider is enabled (the primary burn gate in `Parse HubSpot Event`).

**Blockers:**

- ~~**23-06 FINDING 1 — the armed-window read-back proves less than it appears to.**~~
  **RESOLVED 2026-07-31 by plan 23-07.** `verify_live_write_safety.py` now **discovers** rather
  than names: verified live, it scans **8 workflows / 11 declaring nodes** (was 2), a
  zero-discovery scan **fails** instead of passing quietly, and `--expect-armed FLAG,FLAG` makes
  the armed assertion symmetric — named flags must be enabled, everything else still asserted
  disabled, so Phase 22's stricter meaning survives when the flag is omitted. **Do not re-derive
  the "2 of 8" figure below; it is retired.** Original finding: the script hardcoded the workflow
  name (`LV Enrichment (Cloud template)`) and node names (`Decide Action`,
  `Decide Company Action`) with no workflow argument, covering 2 of the 8 live nodes declaring
  the write-safety constants and **none in `LV Contact Ingest (Cloud template)`** — the lane
  23-06's canary actually fires at, whose gates are `HubSpot Update Write Gate` /
  `HubSpot Create Write Gate`. Step 7's "disarmed PASS" would have been reported without ever
  inspecting the contact lane. Fix mirrored 27-04's D-07 no-allowlist reasoning: report every
  workflow/node declaring an `_OVERLAY_FLAG_SPEC` constant.

- **23-06 FINDING 2 — 23-01's create-gate fix is committed but not deployed.** Live
  `LV Contact Ingest (Cloud template)` (`updatedAt` 2026-07-30) has a `Decide Action` node that
  declares none of the four constants; the committed artifact's does. Section B Step 3 would
  therefore deploy 23-01's never-live-tested logic **in the same action that arms writes**.
  Recommended: insert a disarmed deploy + read-back between Steps 2 and 3, so "did the fix
  deploy" and "did arming work" stay separable. **Never memorise a declaration count** — it was
  9/8 on the morning of 2026-07-31 and CREATE 11 / RECORD_WRITES 10 / REVIEW_WRITES 10 across 11
  nodes by that afternoon (30-01 added a constant to 8 nodes, 30-02 added a whole workflow). Both
  runbooks now **derive** the expected rewrite count at deploy time; a stale figure makes a
  *correct* deploy look like a misfire.

- ~~**23-06 Section B cannot start: n8n instance/key ownership is unverified.**~~ **RESOLVED
  2026-07-31** — Robert confirmed the key is his; `N8N_EXPECTED_URL` appended to `.env`, pinning
  the tenant to an exact match. `N8N_API_KEY_2` remains absent, so both runbooks' claim that
  Alex's key is retained there is stale and should be corrected. Original finding: `.env`'s `N8N_URL`
  is `https://alexherman.app.n8n.cloud` (Alex's tenant), `N8N_EXPECTED_URL` is **unset**, and
  `N8N_API_KEY_2` — which both runbooks describe as where Alex's key is retained — **does not
  exist**, so the single `N8N_API_KEY` present cannot be attributed from the repo alone. The
  wrong-instance guard does **not** catch this: `deploy_n8n_workflows.py::_instance_ok()` falls
  back to "host ends with `.n8n.cloud`" when `N8N_EXPECTED_URL` is unset, which
  `alexherman.app.n8n.cloud` satisfies. Both operator runbooks warn that a wrong key silently
  deploys into the wrong project and that this has already cost one full deploy cycle. Robert
  must confirm ownership, and `N8N_EXPECTED_URL` should be set to pin it, before any armed
  deploy. This equally gates RB-5 (28-02), whose probe refuses unless the two URLs match.

Carried risks: (1) agent tooling is blocked from arming writes, so Phase 28's
armed path needs a human in the loop; (2) unattended sweep (NOTICE-03) depends on scheduling
being available in the operator's Claude Desktop environment — verify before planning Phase 29
rather than assuming; (3) the n8n-side status endpoint is new backend work landing inside a
milestone otherwise scoped as plugin-only.

## Session Continuity

**Stopped At:** Two fronts, both accurate — the Current Position block at the top now reflects the operator front rather than being left stale.

- **Operator front (active):** 23-06 Section A, walking `OPERATOR-RUNBOOK.md` §RB-3. Section B blocked, see Blockers.
- **Autonomous front: 37 of 43 plans built.** Phases 24, 25, 26, 27 COMPLETE; 30 complete bar its
  canary; 29-05 done. **Phase 28: 28-01, 28-02, 28-03, 28-04 all DONE** — RB-5's live gate ran
  2026-07-31 and `28-FINDINGS.md` exists, which released 28-03 and 28-04; both are built and
  committed (`a641119`, `c3ee663`).

- **Remaining:** 28-05 (needs 28-03/04 — now met, but serialized behind the operator committing
  `test_plugin_manifest.py`), 28-06 (armed canary), 29-01/02/03/04/05 now DONE → 29-06 remains,
  30-07 (armed canary), 23-06 §B, 25-01 Probe B4.

- **2026-08-05: Phase 35 (url-structured-fallback) plan 35-02 built.** Provenance,
  import-set guard, and contract-pin tests — see Current Position above. 35-03 (live
  walk + `0.10.0` release) remains.

- **2026-08-03: Phase 32 (llm-free-sweep-trigger) plan 32-01 built.** Replaces the cron
  trigger's `claude -p` invocation (RB-8's silent failure, `29-06-FINDINGS.md`) with
  `lv-sweep-run.sh`, a deterministic LLM-free wrapper, pinned two-sided against
  `sweep_entry.py`'s real output. Gated on 32-02 (the live RB-8 re-run) before NOTICE-03
  can seal.

- **Re-check runnability against the artifact each plan reads, never against SUMMARY presence**
  (HANDOFF §1). "Nothing is runnable" was claimed and wrong twice on 2026-07-31, and RB-5's own
  readiness row was wrong a third time — it reported the probe script MISSING when it existed
  under `operator-claude-plugin/scripts/`.

**Resume File:** `.planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-06-SUMMARY.md` (operator front) · `.../35-url-structured-fallback/35-02-SUMMARY.md` (autonomous front)

**Next Action:**
**All remaining work is operator-gated.** Highest leverage first, all in `OPERATOR-RUNBOOK.md`:

1. **RB-2 (29-01)** — no credentials, no code, pure observation. Releases 4 plans (29-03/04/05/06).
2. **RB-5 (28-02)** — probe script built, commands paste-ready. Releases 4 plans (28-03/04/05/06);
   28-05 is serialized behind the operator committing `test_plugin_manifest.py`.

3. **RB-1 Probe B4** — the only source for the expensive full-waterfall path; until it runs the
   chunk ceiling of 2 stays PROVISIONAL everywhere. Free rider: one POST naming `New Targets.xlsx`
   should return the oversize refusal (102 members vs ceiling 2) — zero writes, zero credits, and
   it exercises the one path 25-03 built but could not test live.

4. **23-06 Section B** (armed create canary; Steps 2b/2c deploy 23-01 disarmed first) and
   **30-07** (armed review-writeback canary). Both are their phase's own proof.
