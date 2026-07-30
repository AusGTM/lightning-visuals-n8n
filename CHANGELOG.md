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

### Fixed
- Ten-plus live-only defects across the Cloud bring-up (BUG 10–26 series), each with a red-before-green test and, where live-reachable, a canary: search transports, create patch binding, ZoomInfo 401 self-heal (`response.status` extraction), domain allowlist inertness (BUG 24/25), deployment drift (BUG 26).

### Current state
- Three workflows live and **active** on n8n Cloud, write gates **disarmed** at rest (armed only inside deliberate, audited, allowlisted windows). Offline suite: 596 pytest / 309 node. Remaining deliberate deferrals: HubSpot-side ICP formula (placeholder), `lv_org_type` text→enum one-way door, dedupe-lane native-search transport swap, armed full-enrichment (providers + research) canary.

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
