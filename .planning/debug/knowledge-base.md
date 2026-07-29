---
status: complete
kind: knowledge_base
---

# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## empty-evidence-by-field — closed-won smoke reported evidence_by_field empty for every company
- **Date:** 2026-07-21
- **Error patterns:** evidence_by_field, empty evidence, lv_produces_content, stop_reason, max_tokens, USE_MOCK_WEB_RESEARCH, setdefault, mock fixture, live smoke, identical verdicts, claude_web_research
- **Root cause:** PRIMARY: scripts/smoke_closed_won_research.py used `os.environ.setdefault("USE_MOCK_WEB_RESEARCH", "false")` to force live research mode, but the documented run command sources `.env` first (which sets `USE_MOCK_WEB_RESEARCH=true`), so the key was already present and `setdefault` silently no-op'd — every "live" run was actually replaying the static mock fixture (identical data for every company, no `evidence_by_field` key since the fixture predates that field). SECONDARY (real, independently confirmed): `max_tokens=2000` for the live Claude web-research call is insufficient once live calls do happen — claude-sonnet-5's extended thinking consumes ~1000-1300 tokens on this prompt, causing `stop_reason=max_tokens` truncation that drops `evidence_by_field` (emitted after the `data` block) before the JSON closes.
- **Fix:** (1) Changed `os.environ.setdefault(...)` to direct assignment `os.environ["USE_MOCK_WEB_RESEARCH"] = "false"` in scripts/smoke_closed_won_research.py. (2) Raised `max_tokens` 2000->4096 in both src/web_research.py (Python dev oracle) and scripts/build_cloud_workflows.py (n8n production prompt, parity requirement), rebuilt n8n workflows.
- **Files changed:** scripts/smoke_closed_won_research.py, src/web_research.py, scripts/build_cloud_workflows.py, n8n/wf_enrichment_local_live.json
---

## lusha-v2-person-contract — live n8n Cloud canary 400'd on Lusha Enrich, real response never unwrapped
- **Date:** 2026-07-28
- **Error patterns:** Lusha, v2/person, contacts, contactId, property email should not exist, BadRequest, identity_keys, linkedinUrl, lushaCandidates, contact.data, rawResponse.contact, 400
- **Root cause:** Two independent contract mismatches against the real live Lusha `/v2/person` API (confirmed live against portal 22617666), both required to fix end to end (AND-gate): (1) REQUEST — `scripts/build_cloud_workflows.py`'s `build_enrichment_cloud()` "Lusha Enrich" node POSTed the bare `identity_keys` object directly instead of the real `{"contacts":[{contactId, email?, linkedinUrl?}]}` array shape (only `email`/`linkedinUrl` accepted per element; `firstName`/`lastName`/`companyName`/`companyDomain`/`domain`/`phoneNumber`/`jobTitle` all rejected). (2) RESPONSE — `n8n/code/normalizeProviders.js` `lushaCandidates()` (line 138) unwrapped a singular `rawResponse.contact.data`, but the real response is a plural, contactId-keyed map `{"contacts":{"<id>":{"error","data":{...}}}}`.
- **Fix:** (1) Lusha Enrich's jsonBody expression now maps `identity_keys` down to `{contactId:"1", email?, linkedinUrl?}` (camelCase), omitting absent fields, and emits an empty `contacts` array (never a malformed element) when neither `email` nor `linkedin_url` is present — skip-not-retry, row still flows to Apollo/ZoomInfo. (2) `lushaCandidates()` now checks `rawResponse.contacts` (plural map) first, takes the single entry's `.data`, and treats a truthy per-contact `error` or missing `data` as zero candidates without throwing. Pre-existing singular `contact.data` and flat-fixture fallback branches left untouched for offline back-compat (exactly one caller in the repo, confirmed by grep).
- **Scope notes:** An existing fixture (`tests/fixtures/enrichment/lusha_live_person.json`) was mislabeled "real v2 person" using the singular shape that was never actually observed live — kept (still exercises a legitimate offline-fallback path) but its comment corrected, not silently rewritten. The companies Lusha path (`/v2/company`) uses a different, already-correct flat `{"data":{...}}` unwrap and is unaffected — untouched. `build_enrichment_local_live()`'s separate GET-querystring Lusha request (`ENRICH_BUILD_REQUESTS`) has its own, different, unrelated contract break — flagged, not fixed, deferred to a future session.
- **Files changed:** scripts/build_cloud_workflows.py, n8n/code/normalizeProviders.js, n8n/wf_enrichment_cloud.json, n8n/wf_enrichment_local.json, n8n/wf_enrichment_local_live.json, tests/n8n/lushaRequestContract.test.mjs (new), tests/n8n/enrichment.test.mjs, tests/fixtures/enrichment/lusha_live_person_v2.json (new)
---

## scheduled-lane-canary-timing — a scheduled-lane canary that "finds nothing" is usually a clock problem, not a filter problem
- **Date:** 2026-07-29
- **Error patterns:** total=0, Extract Rows items=0, scheduled tick, mode=trigger, Review Search, SJ-1, search index lag, eventual consistency, seeded canary not found, 15-minute trigger
- **Root cause:** Testing a schedule-triggered lane against a freshly-seeded HubSpot record has TWO independent race conditions, and both present identically to a broken filter (`total: 0`, downstream nodes emitting 0 items, execution status `success`): (1) HubSpot CRM search is EVENTUALLY CONSISTENT — a record created via the API is not immediately returned by `/search`; observed lag was ~6s in one case and ~3 minutes in another, so it is not a fixed bound. (2) The tick you capture may PREDATE the seed — polling "for the next scheduled execution" catches whichever tick fires first, which is frequently the one already in flight before the canary existed. This cost three separate cycles in one session: execution 45 (04:15:11Z) predated a 04:17:46Z seed; execution 49 (04:45:11Z) predated a 04:50:37Z indexing.
- **Fix:** Two guards on any scheduled-lane canary: (a) poll the REAL search filter directly until the seeded id actually comes back before trusting any tick, recording the indexed-at time; (b) filter captured executions by `startedAt >= indexed_at`, not merely "the next one seen". Independently: the same eventual consistency means a search-gated create path can double-create inside the index window (recorded in BUG 19's resolution) — a genuine production property, not only a test artifact.
- **Scope notes:** Distinguishing a timing miss from a real defect is not optional cleverness — BUG 22a was a genuinely empty filter that looked exactly like this, so "total=0 on a scheduled search" must be diagnosed, never assumed either way. The tell is the execution's `startedAt` versus the record's `createdate` / observed index time.
- **Files changed:** (none — methodology; applied in .planning/phases/16-scheduled-workflows-review-surface/16-UAT.md)
---
