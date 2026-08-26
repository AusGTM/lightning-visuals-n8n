# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.19.0] - 2026-08-26

### Added
- **Company-lane extraction (Phase 58, plans 01–03).** A company can now be named by
  anything the operator holds — a bare name list, pasted text, foreign JSON, a public URL,
  a LinkedIn company page, a screenshot (including a search-results page). Company rows ride
  the same Claude-as-extractor machinery as contacts (`company_column_mapping.yaml`,
  record-type-aware `extraction.py`, single identity group: name alone), with mixed
  people+companies input read in one pass, companies first.
- **Domain propose/confirm/decline/correct lane (`company_domain.py`).** When a row has no
  usable domain, Claude proposes one (marked unverified, source + one-line reason). The
  operator answers a batch confirm table — approve wholesale, type the correct website over
  a row, or reject a row. A rejected/declined row is never dropped: it proceeds looked up by
  name, and the report says so. The envelope refuses undecided rows; nothing is sent until
  the table is answered. Operator-typed domains pass the NOT_A_COMPANY_DOMAIN/freemail
  guards only. A profile URL is never recorded as a website.
- **Propose-mode spike proven live (execution 11972).** A request-level `mode: "propose"`
  on a company event survives `Parse HubSpot Event` and reaches `Decide Company Action`,
  producing the non-writing `action: "proposed"` — 0 provider credits, 0 Anthropic calls,
  no write. Backend research-node domain extension deferred by operator ruling 2026-08-26
  (`58-SPIKE-VERDICT.md`); rows Claude cannot propose fall back to name-only.

- **Contact -> company association in the ingest lane (2026-08-25).** A contact is never
  created in HubSpot unassociated any more, and an existing company is never recreated to
  achieve that. `wf_contact_ingest_cloud` gained a resolve-then-associate subgraph
  (`Build Company Link` -> two credential-bound company searches -> `Adapt Company Link`,
  then `Build Association Request` -> a gated `HubSpot Associate Company` PUT ->
  `Build Ingest Response`): each row resolves a company by **manual `company_id` column
  first, then exact email-domain match, then exact company-name match**, and the v4
  `associations/default` endpoint links the contact after the write. Resolution only — the
  lane creates no company, because a junk company shell is worse than a held row. A create
  that resolves no company is downgraded to `review` at `Decide Action` with the reason
  kept; an update is not held (it may already carry an association this lane cannot see)
  and simply has nothing to associate. New `company_id` column alias
  (`company id` / `hubspot company id` / `associatedcompanyid`) carries the operator's
  manual override for a held row. The association PUT is spliced through
  `splice_write_gates` like every other write, so it needs the same arming as the write
  that preceded it. `Build Ingest Response` now returns one row-identifying item per
  decided row (`action`, `contact_id`, `company_id`, `association`, `reason`), which
  `report.py::sync_response_is_sufficient` accepts — previously the response was whichever
  branch happened to run last.
- **Company-lane name fallback (2026-08-25), found live.** The companies branch of
  `wf_enrichment_cloud` resolved on `domain` alone, so a company already in the portal
  under a *different* domain read as absent and the gate said "create". Proven live by the
  ingest lane's own rehearsal (n8n execution `11922`): Harness Racing NSW is company
  `18756544347` under `www.harnessmediacentre.com.au`, and a `hrnsw.com.au` request would
  have duplicated it. Two nodes added on the search branch only (`HubSpot Company Name
  Search` -> `Adapt Company Name Search`): an EXACT single-hit name match, applied only
  where the domain search found nothing, never overriding a domain hit and never firing on
  a failed lookup (an unknown is not an absence). The fetch-by-id branch is untouched.

- **Companies spec form in the plugin (2026-08-25).** `enrichment.build_envelope` accepts
  `{"companies": [{"name", "domain"}]}` and emits a write-mode `companies` events array,
  making the backend's existing `HubSpot Company Create` lane reachable from Claude for
  the first time. `domain` is mandatory and a company without one is refused by name:
  domain is the identity anchor the company lane searches on, so a domainless company
  could only be created, never matched. The form carries **no** `mode`, deliberately — a
  `propose` mode would report success having written nothing. `chunking.plan_chunks` and
  `preview_enrichment.records_block` handle the form; the preview states plainly that an
  existing company is enriched in place and never duplicated, and one with no match is
  created if creation is armed.

- **Quick task 260823-ono — Metro peak-body named-account score floor (live 2026-08-23).**
  Five AU metro racing peak bodies — Australian Turf Club, Melbourne Racing Club, Southside
  Racing, Brisbane Racing Club, Perth Racing — now tier at a floored `lv_icp_fit_score` >= 60
  / `lv_icp_tier_derived` "B", correcting an under-weighting of their governing/owning role
  over smaller clubs that the `individual_club_team` org type alone did not capture. The
  mechanism is a new operator-editable `number` company property,
  `lv_named_account_score_floor`: `60` on a record floors that record's score at 60 (`max`,
  no cap — an earned base above 60 passes through unchanged) via a change to the
  `lv_icp_fit_score` calculation formula; blank/0 means no override. The first design tried
  — reading an enumeration property (`lv_named_account_priority`) from the formula — was
  proven live to be dead on arrival before any production write: a CP1 probe (5 formula
  variants, all armed and live) showed `string(<enum>)` parses in a `calculation_equation`
  on this portal but silently computes null once the enum has a value (`halt-b`, evidence
  in `260823-ono-PROBE-VERDICT.json`; D-20 reconfirmed). The operator selected a plain
  number instead. Before the production formula push, a second live probe (CP1b, two
  disposable properties, three records written and cleared) proved five specific
  behaviours the operator required: a null floor computes the record's true existing score
  (not blank, not altered); a null floor on a never-enriched record stays blank; a set
  floor computes 60 on all-blank inputs; a set floor does not cap an already-higher base;
  and a set floor overrides a lower base (`all_pass: true`,
  `260823-ono-FLOOR-PROBE-VERDICT.json`). Only after that all-pass did the property get
  created and the formula pushed to all ~712 companies, then the floor value written to the
  5 named records. Post-write: `check_tier_derived_parity.py` `defect=0`
  (`population=67 match=60 expected_mismatch=7`, MRC and Perth Racing pre-registered as
  permanent expected mismatches against the archived, now-unwritable `lv_icp_tier` —
  `.planning/WINDOWS.md` ids 20-22); `check_schema_drift.py` exit 0; both suites green.
  Disclosed non-change: the n8n `Decide Company Action` node computes no score and no tier
  at all (Approach C, Phase 15), so nothing on that lane needed a matching change — zero n8n
  changes, zero n8n executions, zero provider credits, zero Anthropic calls across the whole
  task. Zero properties leaked across both probes (10 disposables created and archived
  across CP1 + CP1b).
- **v0.8 Phase 45 — Burn-Rate Alarm, Cadence Budget Floor & Windowed Lookback (sealed
  2026-08-10).** Phase 44 stopped the runaway; this phase reports one before a human reads the
  billing page. A new `burn_rate_alarm` sweep condition samples the execution rate over a bounded
  recent window (`n8n_read.executions_in_window`) and fires when that rate, projected over a
  30-day month, would exhaust the allowance read from `config/execution_budget.yaml`. It never
  states a monthly total: n8n prunes execution history (2,500 rows / ~10 hours observed) and
  exposes no usage endpoint to an API key, so a total is unknowable by construction and reporting
  one would be a fabrication. The projection is deliberately anchor-free (rate × 30 days) because
  n8n exposes no billing-cycle day. A missing allowance produces a notice naming the missing key —
  never silence, never a guessed default — and an alarm that cannot read execution history says
  so, inheriting the sweep's rule that a check which failed to run must never look like a check
  that found nothing wrong. The sweep's lookback is now bounded by time rather than a fixed
  100-row page, so a failure whose cause was fixed ages out while an in-flight run is never aged
  out. Separately, a runtime cadence change is refused when the **whole** schedule's monthly
  execution floor would bust its configured share of the allowance — stating the arithmetic before
  the refusal, with a single-shot override. `tests/test_execution_budget_drift.py` pins the
  plugin's allowance and floor share to `config/execution_budget.yaml` so the two cannot drift.
  Post-execution code review caught a false-positive class and it was fixed before sealing: an
  unanchored sub-hour sample (retained history holding nothing older than the window — first day
  after deploy, a history rotation, a fresh instance) was extrapolated into a false alarm whose
  notice also blamed n8n pruning that never happened; such a sample is now silent, while a
  page-cap-truncated read still fires so a genuinely fast runaway is not silenced. **Ships
  inert** — no cron/launchd schedule is installed (an admin action, an accepted limit), so the
  alarm is proven by unit tests against synthetic execution history rather than an observed
  scheduled fire. Plugin 0.13.0. 6/6 requirements closed (ALARM-01..04, LOOK-01, FLOOR-01);
  26/26 must-haves verified; suites 2487 pytest / 656 node / 1332 plugin.
- **v0.8 Phase 44 — SJ-3 Dispatch Gate, Drain & Cap (live-proven 2026-08-10).** After the
  2026-08-09 execution runaway (61 stuck `lv_enrichment_requested` flags × a 15-min poller =
  253 executions/hour, ~73x the 2,500/month n8n plan, spent on dispatches that could never
  complete), the SJ-3 lane is now structurally budget-safe: a per-record write-safety gate
  (reusing `WRITE_SAFETY_GATE_JS`) dispatches only what an armed window would actually permit;
  declined rows are **drained** (`lv_enrichment_requested="false"` + `lv_enrichment_status="skipped"`,
  a two-key allowlisted patch under a new `ALLOW_SJ3_DRAIN_WRITES` authority that defaults true,
  is never armable, and can only remove queued work); and dispatch is **capped** at a bound
  derived from `config/execution_budget.yaml` (allowance × share / cadence — 40/tick at daily),
  with overflow deferred, never drained, and found-vs-dispatched always logged. A
  `SJ-3 Tick Outcome` node runs even on a fully gate-closed tick (`gate_closed`/`capped_partial`/
  `dispatched` + counts). `tests/test_execution_budget.py` fails the build if the shipped
  schedule's idle floor exceeds its configured share of the plan — the check the old
  2.6x-over-budget schedule would have failed. Live evidence (execution 11820): gate-closed tick
  cost exactly 1 execution with 0 sub-executions; drain landed with a 272-property diff showing
  nothing outside the allowlist changed. All five schedule triggers also moved to daily/weekly/
  monthly cadence (idle floor ~95/month). 9/9 requirements closed; suites 2438 pytest / 656 node.
- **Milestone v0.7 — HubSpot Scoring Engine Remediation, sealed 2026-08-08.** 5 phases (39–43),
  23 plans, 16/16 requirements. The ICP rubric had been implemented twice — correctly in
  `src/icp_scoring.py` (oracle only, no production callers) and incorrectly as four live HubSpot
  workflows created 2026-08-04 that surfaced only when the `automation` scope was granted. All
  ten validated defects (F1–F10) are fixed in place:
  - **Engine (Phase 40):** `lv_produces_content` contributes +20; scoring reads the canonical
    `lv_country_region_normalized`/`lv_revenue_band` the pipeline actually writes instead of
    native `country`/never-written `annualrevenue`; revenue decay lands −5/−15/−30/−50 in the
    rubric-correct band at 500M/750M/1B/1.2B; the gambling deduction is driven by
    `lv_is_gambling_operator` independent of org type and never sets the veto flag; regulator
    scores 5; sub-15 without a veto no longer grades D. All three hard vetoes write flag **and**
    reason, vetoes clear on correction (no one-way latch), and a flag change alone moves the
    tier. New flow fetch/PUT tooling and `PORTAL-FACTS.md`.
  - **Parity (Phase 40):** `scripts/run_scoring_parity.py` recomputes via the oracle and asserts
    against live HubSpot, with a false-green guard that FAILS when zero assertions execute.
    Every F-defect had been invisible in the HubSpot UI. F4/F7/F9/F10 encoded as named
    regression cases.
  - **Data (Phase 41):** the 66 web-researched validation companies landed with `lv_*` inputs and
    provenance at **zero provider spend**, and scored automatically on the real write path —
    A:7 B:18 C:17 D:24, parity PASS over all 66.
  - **Cleanup (Phase 42):** `config/hubspot_properties.yaml` expanded to a full 32-property live
    mirror at zero drift; standing `scripts/check_schema_drift.py` with a machine-checked
    do-not-archive invariant and a dedicated exit code when the live engine itself is damaged.
    Live orphan derivation found zero uncontested and zero ambiguous candidates — nothing to
    archive.
  - **Pipeline hygiene (Phase 43):** six boolean write sites coerced to strings at two shared
    choke points; the dormant `mergeCompanies.js` veto site hardened; `--write-breakdown` gives
    `lv_icp_score_breakdown` a producer (rubric-versioned, shed-detail-first serializer);
    closed-lost reasons aggregated into a report plus an operator-plugin skill.
- **Null-safe `lv_icp_fit_score` formula + blank-score detector (2026-08-08).** Phase 41 exposed
  that HubSpot blanks a `calculation_equation` entirely when any referenced term is null, and
  research legitimately answers null for `gambling_score` on ~95% of companies — so **63 of 66
  records carried no score at all** while the parity sweep still reported PASS. A live spike
  mapped the formula grammar (the API's 400 body enumerates every valid token) and verified
  three null guards; the live formula is now
  `org_type_score + coalesce(geography_score, 0) + coalesce(annual_revenue_score, 0) + coalesce(produces_content_score, 0) + coalesce(gambling_score, 0)`.
  `org_type_score` is deliberately left unguarded as the "has been through the pipeline"
  sentinel — guarding all five would score the 646 never-enriched companies as 0 and enroll every
  one of them in the tier flow. The parity harness gained a detector for the complement of its
  own sample (`org_type_score` present, `lv_icp_fit_score` absent) — the set it structurally
  could not see, which is exactly how 63 records shipped as apparent success. New
  `scripts/apply_fit_score_formula.py` (archive is the source of truth, `ALLOW_FORMULA_WRITE`
  gated, dry-run by default); regression tests proven to fail on revert.
- **Phase 39 (v0.7) — scoring-remediation path decision, sealed 2026-08-06.** Company fit-score
  availability on Sales Hub Pro verified **in-portal** (Lead Scoring app renders; company + fit
  score offered; Contacts locked behind Marketing Hub) with evidence on disk — 2 read-only API
  probe JSONs, 4 portal screenshots, and a re-checkable attestation
  (`.planning/phases/39-path-decision-fit-score-verification/evidence/`). **Path decided:
  fix-the-four-workflow-chain-in-place** (`39-DECISION.md`): operator hard requirement that the
  score keep landing in `lv_icp_fit_score`/`lv_icp_tier` and reuse the existing architecture —
  the lead-scoring tool's auto-generated `hubspotDefined` score property cannot write there, so
  the tool was not adopted despite availability. New assets: `delete_record()` in
  `src/hubspot_client.py`; `scripts/probe_scoring_tool_availability.py` (disarmed-by-default,
  read-only, portal-guarded); `scripts/probe_scoring_recalc_latency.py` (two-key-gated
  disposable-company harness, built but never armed — moot for the decision, kept for Phase 40);
  25 unit tests. Post-execution code review fixed 1 Critical (sample-loop no-op writes would
  have faked a "recalc never fires" verdict) + 3 Warnings. Branch: `feat/v0.6-plugin-entrypoint`
  fast-forwarded into `master`; v0.7 work continues on `feat/v0.7-scoring-remediation`.
- Repository structure: README, CHANGELOG, proprietary LICENSE; docs reorganised into `docs/{business,architecture,reviews}`.
- **`operator-claude-plugin/`** — directory for the operator-facing client (planned, milestone v0.6),
  with its own README and independently-versioned CHANGELOG. Documented as a *suggested default thin
  client*: n8n is a standalone backend reached over plain HTTP, so other front ends (Slack, web app,
  CLI) can be built against the same contract. Client changes are recorded there, not here.
- **Milestone 3 (company enrichment & ICP research)** — company enrichment branch, web research (native `web_search`), Haiku/Sonnet judge wiring, tiered candidate adjudication; **HubSpot `lv_*` property migration live** (33 + review/SJ-3 control props) via idempotent `scripts/sync_hubspot_properties.py`; **n8n Cloud deploy** over the Public API (`scripts/deploy_n8n_workflows.py` + `scripts/provision_n8n_credentials.py`, credential-bound, two-key gated); **scheduled maintenance** (`wf_scheduled_maintenance_cloud.json`: SJ-1/2/3 + weekly dedupe + §22.2 review loop); ZoomInfo converted to credential-bound **split-code-node** for n8n Cloud.
- Live-provider **dry run** executed (Lusha/Apollo/ZoomInfo → scored winners → HubSpot read → printed payload, no write) — see `docs/reports/`.
- **Phase 16.1 — per-request provider selection + credit reporting + schedule safety.** The enrichment webhook payload accepts a `providers` field (`all` / list / `none` / blank / absent→`none`); each provider runs behind an `IF <provider> Enabled` bypass gate so a disabled provider's HTTP node never fires (per-request cost gate, no global kill-switch). The webhook response carries `remaining_credits` per provider (single-item credit branch → `Respond to Webhook` with `responseMode: responseNode`); live-validated usage endpoints + `scripts/check_provider_credits.py` (read-only balance CLI). Scheduled-maintenance workflow ships `active: false`.
- **Phase 16.2 — contacts research → judge mirror.** The contacts branch gained the companies web-research → judge → verdict chain (jobtitle + seniority, off by default, PII-scoped), built via parameterized `EnrichTarget` factories (`COMPANIES_TARGET`/`CONTACTS_TARGET`) that keep companies byte-identical; new `n8n/code/contactResearch.js` + `contactJudge.js`; `mergeContacts.foldContactResearch` write-safety fold; `chosen_field` allowlist. Fixed a latent companies research-lane row-loss bug (HTTP nodes replace `$json`) via node-name row recovery, with an item-flow regression test.
- **Phases 16.3–16.9 — hardening + live bring-up.** Stale-timestamp fix mirrored onto `mergeCompanies.js` (cache-key `verified_at` only stamps on promote); fetch-by-objectId lane for bare webhook events (`hs_object_id EQ` search, live-confirmed filterable); deploy-time baked-flags overlay (`ENABLE_BAKED_FLAGS`, fails closed, write flags refuse without an allowlist); companies search transport swapped to credential-bound `httpRequest` (BUG 10 — n8n's native HubSpot node has no company `search` operation and falls through silently); create nodes rebuilt to POST the computed patch (BUG 13); `bind_credentials()` fails closed on any unmapped credential-requiring node.
- **Live n8n Cloud deploy + activation (was Pending — DONE).** All three workflows deployed to n8n Cloud via the Public API, credential-bound, read-back-verified, and **activated**. Non-clobber proven live (a threshold-clearing candidate refused on ownership class; un-allowlisted company refused `write_blocked`); `company:create` proven live (create → confirm → delete canary); `company:update` proven live in an audited armed window (2026-07-29, execution 108: write to the allowlisted test record only, neighbor untouched, deployment restored disarmed and read back).
- **Phase 17 — BUG 23 (enrichment `contact:create` structurally unreachable) fixed.** Contacts-lane `HubSpot Search`/`HubSpot Fetch By Id` swapped to the credential-bound `httpRequest` envelope (the native node emits zero items on zero hits, silently ending the chain); dual live canary proved both the match path and create-path reachability (write-gated).
- **Phase 18 — normalization + copy-loop fixes.** A numeric provider industry code (ZoomInfo NAICS `"71"`) can no longer survive normalization or win the waterfall over provider text (`_industryText` prefers the provider's own name); `lv_sponsorship_reliant` and `lv_persona_group` wired into their merge calls AND given live producers (research contract requests sponsorship; `_personaGroup()` maps Apollo/Lusha `departments`). All red-before-green against the real execution-19 conflict shape.
- **Phase 19 — verification debt discharged.** The six deferred verify-work re-runs reconstructed (the referenced "goal ledger" never existed as a file), re-executed, and recorded in `19-LEDGER.md`: **6/6 passed**. The sweep surfaced and same-day-resolved BUG 26 (live deployment had drifted behind git — content-marker probe, redeploy, read-back).
- **Phase 25 Plan 02 — `hubspot/backend-status` (credit-only slice).** New n8n Cloud workflow (`wf_backend_status_cloud.json`) so the operator-facing plugin, which holds no provider credentials, can read remaining provider credits without a client ever touching a provider key. Reads Lusha/Apollo/ZoomInfo usage endpoints only — never a data endpoint, never a HubSpot endpoint, and performs zero writes. A balance that cannot be read (e.g. this account's non-master Apollo key, which 403s by design) comes back as an explicit unreadable marker, never as zero. Full backend health is deferred to Phase 27; this is the credit slice only.
- **Phase 25 Plan 03 — the enrichment webhook can resolve a HubSpot list.** `hubspot/enrichment/event` now accepts, in addition to the existing `{providers, events:[...]}` record-ID envelope, a **list envelope** `{providers, list:{name, objectType}}` where `objectType` is `contacts` or `companies`. n8n resolves the name to its members with the HubSpot credential it already holds (two credential-bound Lists API GETs, `crm.lists.read`, granted 2026-07-31) and expands them into exactly the events envelope the existing parser consumes — **the client never holds a HubSpot token, and never needs one to name a list**. The record-ID path is untouched: the branch is the true lane of a new IF whose false lane is the edge the webhook trigger already had.
  - **A list of more than 2 records per request is REFUSED, not truncated.** That number is measured, not chosen: n8n Cloud caps a webhook response at roughly 100 seconds (Cloudflare 524 past it), this workflow has no `Split In Batches` node, so every record in a request runs the full provider + Haiku + Sonnet chain before the response fires — live executions measured ~36 s/record, giving `floor(100/45) = 2`. The reason a *backend* limit exists at all is that a list resolved on the backend cannot be split by the client: the client cannot count a list it cannot read, so the backend has to enforce the same bound client-side chunking enforces. Truncating instead would enrich an arbitrary subset and report success. The refusal names the limit and redirects to record IDs. **This number is expected to move** — the measurement is single-record and company-lane, and the full-waterfall timing probe has not yet been run.
  - The same refusal fires when HubSpot returns a **paging cursor**, even if that page is within the limit: a cursor means the response is a page, not the list, and a page enriched as if it were the whole list is a partial result impersonating a complete one. A list that does not resolve, one with no members, and an unreadable membership response each refuse in their own words rather than quietly enriching nothing.
  - **Saved views are refused, not resolved.** HubSpot exposes no API for views, so a view name is never looked up against the *list* endpoint — a view name colliding with an unrelated list name would enrich the wrong records with no error. Naming a view returns: *"I can't resolve a HubSpot view — HubSpot doesn't expose views through its API. Save that view as a list in HubSpot and give me the list name, or paste the record IDs directly."*
  - The provider selection on a list envelope is carried onto the expanded events unchanged, including an explicitly empty one, so a list batch burns exactly the providers that were approved and no more. Only record IDs cross this branch; no HubSpot property value is read or emitted by it.

- **Milestone v0.5 (Lusha v3 & Armed Enrichment, phases 20–22, 2026-07-30).** Lusha **v2→v3 migration** on both lanes (v2 sunset; flat measured pricing 1cr/contact, 2cr/company, 0-credit stored-id re-enrich via `lusha_contact_id`/`lusha_company_id`; contract of record `docs/LUSHA-V3-CONTRACT.md`); Phase 21 transport/schema hygiene incl. the `lv_org_type` **text→enum one-way-door migration** (`docs/ORG-TYPE-ENUM-MIGRATION.md`); Phase 22 **armed E2E enrichment canary PASSED** (execution 332: full chain live — providers + Haiku research + Sonnet judge — neighbors untouched, closed disarmed, $0.0686 Anthropic/record, 0 provider credits; BUG 27 array→semicolon PATCH fix found+fixed live).
- **Milestone v0.6 backend-side additions (phases 27, 30, 31 — client changes live in `operator-claude-plugin/CHANGELOG.md`).**
  - `wf_backend_status_cloud.json` grown from the credit slice to **full backend health** (workflows, executions, queue counts, provider balances — read-only, unknown never rendered as zero).
  - **`wf_review_decision_cloud.json`** (Phase 30): synchronous `hubspot/review/decision` endpoint (`n8n/code/reviewDecision.js`, calling the existing `reviewApply` engine) plus a read-only `hubspot/review/queue` endpoint. Approve promotes the held candidate, clears the flags, and writes a **human provenance entry** (`source: human`, `human_approved`, timestamp, operator reason, `superseded_source` preserving the machine attribution); reject records the reason and leaves the record queued; `manual_protected`/`review_required` fields are withheld by class on this endpoint. Ships inactive; activated only inside review windows. Proven live 2026-08-04 (RB-9 close: one-record armed window, `neighbors_changed: 0`).
  - **HubSpot enum validate-and-refuse** (Phase 31, BUGS 28/29/30): generated option module (`n8n/code/hubspotEnums.generated.js` from the schema snapshot) + validator (`hubspotEnums.js`) consumed at enrichment staging AND both review paths. Exact case-insensitive label→value match only — no mapping layer. Preview and real submit return the identical explicit refusal naming property/value/closest labels; an un-allowlisted decision answers `not_allowlisted` instead of an empty body.

### Fixed
- Ten-plus live-only defects across the Cloud bring-up (BUG 10–26 series), each with a red-before-green test and, where live-reachable, a canary: search transports, create patch binding, ZoomInfo 401 self-heal (`response.status` extraction), domain allowlist inertness (BUG 24/25), deployment drift (BUG 26).
- **Stored-vs-running reload gap (found live 2026-08-03, RB-3).** n8n serves a running workflow's pre-PUT content until a deactivate→activate bounce; `deploy_n8n_workflows.py` PUTs but never activates, and the write-safety read-back reads STORED content. Every arm AND disarm deploy now bounces all active workflows before any verdict is trusted.
- **BUG 28/29/30 family (found live by RB-9, fixed Phase 31).** An enum-invalid review candidate 400'd inside the workflow on real submit while the preview claimed `applied`; an allowlist drop returned an empty body indistinguishable from a broken endpoint. Both now refuse explicitly and identically on preview and submit.
- **Phase 23 backend gate fix (D-15) — contact-upload lane could never create a contact.** `Decide Action` in `wf_contact_ingest_cloud.json` read a `Set Config`-seeded row field that hardcoded `allow_create: false` unconditionally, forcing every net-new contact row to `needs_review` regardless of arming. `Decide Action` now derives its create decision from the existing deploy-time-overlayable `ALLOW_HUBSPOT_CREATE` constant — the same one the lane's own `HubSpot Create Write Gate` already reads — instead of a fifth flag, so arming contact creation requires the identical `ALLOW_HUBSPOT_RECORD_WRITES` + `ALLOW_HUBSPOT_CREATE` + `TEST_RECORD_*` allowlist combination as every other write path in this repo. This is a backend gate fix made for Phase 23 (walking-skeleton plugin), not a client change; the plugin's own changelog lives in `operator-claude-plugin/CHANGELOG.md`.

### Current state
- **Five** workflows deployed on n8n Cloud (contact ingest, enrichment, scheduled maintenance, backend status active; `LV Review Decision` inactive at rest), write gates **disarmed** at rest (armed only inside deliberate, audited, single-record-allowlisted windows with symmetric read-backs and post-deploy bounces). Offline suite: **1784 pytest / 550 node**; committed workflow JSON carries zero armed literals (gated by `operator-claude-plugin/tests/test_control_disarmed_artifacts.py`). v0.6 sealed 2026-08-04 (`.planning/MILESTONES.md`). Remaining deliberate deferrals: HubSpot-side ICP formula (placeholder), dedupe-lane native-search transport swap, per-provider disagreement persistence for the review queue, sweep lookback time-window + workflow-name resolution.

### Known debt
- The **enrichment** lane's own contact create (`wf_enrichment_cloud`) does not associate:
  the 2026-08-25 rule is implemented in the ingest lane only. That lane's create requires
  `ALLOW_HUBSPOT_CREATE` plus an allowlist match, so it cannot fire unattended, but a
  contact created through it lands unassociated.

## [0.4.0] - 2026-07-15

### Added
- **Enrichment workflow** (n8n Cloud): idempotency gate — check HubSpot first, then **create / enrich (stale) / skip (current)**.
- **Quality-scored waterfall** replacing FIFO stop-on-first-match: field-level best-of-breed scoring across all three providers `value_score = wA·accuracy + wR·recency + wG·agreement + wT·trust`, with cross-source consensus and provenance.
- **ZoomInfo autonomous OAuth2** (Okta client-credentials): token minted from `client_id`/`client_secret`, cached in workflow static data, re-minted on near-expiry and **refresh-on-401**. No static token stored.
- Provider response normalizer + accuracy/recency signal mapping for Lusha, Apollo, ZoomInfo; tested JS modules (`n8n/code/{scoreEnrichment,enrichmentGate,normalizeProviders,zoominfoToken}.js`).

### Verified
- Live authentication for **Lusha, Apollo, ZoomInfo**; ZoomInfo client-credentials mint confirmed against `gtm/oauth/v1/token` (no `scope`).

### Fixed
- ZoomInfo auth corrected from single-key/PKI assumptions to Okta client-credentials (DevPortal `client_id` + `client_secret`).

## [0.3.0] - 2026-07-08

### Added
- **n8n Cloud-native port**: contact-ingestion pipeline runs entirely in n8n Code nodes (no npm) + HTTP/HubSpot nodes; AU-phone normalization in inline JS; email validation via the external verifier API.
- Cloud + locally-executable workflow templates; scripted local-n8n replica proof.

### Removed
- FastAPI decision service (superseded by inline Code nodes).

## [0.2.0] - 2026-07-08

### Added
- **Contact ingestion**: file loader (CSV/XLSX/JSON), column mapper, contact normalizer (phone→E.164, email validate).
- **Identity/dedupe resolver** (email→linkedin→phone+name→name+company; no-email never auto-creates).
- Gated net-new create with pre-create re-check; dedupe/mangled sweep.
- n8n local-server replica (FastAPI decision service) for contact ingestion + weekly sweep.

## [0.1.0] - 2026-07-07

### Added
- **Local-first ICP scoring MVP** (Milestone 1): config-driven scoring engine (score / tier / anti-ICP vetoes / graduated deductions), non-clobber merge with field-ownership classes, per-field source attribution, dry-run HubSpot PATCH output under env-flag safety gates.
- Mock provider waterfall + Claude web research; Haiku→Sonnet LLM cascade.
- Bootstrapped from ingested specification and ICP validation docs.

[Unreleased]: https://github.com/AusGTM/lightning-visuals-n8n/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/AusGTM/lightning-visuals-n8n/releases/tag/v0.4.0
[0.3.0]: https://github.com/AusGTM/lightning-visuals-n8n/releases/tag/v0.3.0
[0.2.0]: https://github.com/AusGTM/lightning-visuals-n8n/releases/tag/v0.2.0
[0.1.0]: https://github.com/AusGTM/lightning-visuals-n8n/releases/tag/v0.1.0
