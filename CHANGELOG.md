# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
