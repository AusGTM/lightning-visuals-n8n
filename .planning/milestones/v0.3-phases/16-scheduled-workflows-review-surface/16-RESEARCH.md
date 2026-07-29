# Phase 16: n8n Cloud Deployment, Scheduled Workflows & Review Surface - Research

**Researched:** 2026-07-23
**Domain:** n8n Cloud deployment (Public API), n8n secret/credential model, scheduled HubSpot polling, human-review workflow state machines
**Confidence:** HIGH on grounded code/JSON findings; MEDIUM on n8n Cloud API/credential mechanics (community-sourced, not verified live in this session); LOW flagged explicitly where noted

## Summary

This phase has two genuinely different kinds of work bolted together by the roadmap's scope expansion: **plumbing** (get real secrets and real deploy tooling working against an empty n8n Cloud instance) and **business logic** (schedules, a review loop, and a caching behavior that — this research found — is **already substantially implemented** in existing code, just never wired to a trigger or proven with a test). The grounded `$env`/`$vars` inventory from the built JSON confirms the roadmap's "6 secrets, 6 flags" claim exactly, with one important nuance: n8n **Code nodes can never access credentials, on Cloud or self-hosted, by design** — this is not a licensing gap that `$vars` might fix, it is permanent. That breaks the existing `zoominfoToken.js` cached-OAuth2 Code-node pattern outright and requires it to be restructured around a credential-bound HTTP node, not a `$env`→`$vars` swap. Separately, this research found that `enrichmentGate.js`'s `decideAction` (already wired into the company branch's staleness gate) already implements RT-5's "180-day TTL keyed on `_verified_at`" behavior — criterion 9 is mostly a scheduling + test-authoring task, not new business logic. Conversely, it found a real blocking gap the roadmap did not surface: the HubSpot control-plane properties SJ-3's predicate depends on (`lv_enrichment_requested`, `lv_enrichment_status`) **do not exist** in the Phase-15 33-property manifest at all.

**Primary recommendation:** Do not split Phase 16 into a formal Phase 16/17. Split it into **two sequential plans within one phase** — Plan A ("deployable," criteria 5–8, plus a newly-found prerequisite: add the missing SJ-3 control properties) and Plan B ("complete," criteria 1–4, 9) — executed in that order, because they share one heavily-edited file (`scripts/build_cloud_workflows.py`) and Plan B's live verification (not its authoring) is the only piece that hard-depends on Plan A.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Secret storage (6 API keys/tokens) | n8n Cloud credential store | — | Only tier capable of holding secrets given `$env` blocked + Code nodes can never read credentials |
| Build-time config constants (6 flags) | Build tooling (`scripts/build_cloud_workflows.py`, dev-time) | n8n Code node (consumes the inlined literal at runtime) | AR-4: nothing not already in the JSON exists at n8n Cloud runtime |
| Companies enrichment pipeline (provider waterfall, research, judge, merge) | n8n Cloud (workflow nodes) | Anthropic / ZoomInfo / Apollo / Lusha (external APIs) | AR-1: no deployed middleware; this project's Python is a dev oracle only |
| Schedule-triggered polling (SJ-1/2/3) | n8n Cloud (scheduleTrigger + HubSpot Search nodes) | HubSpot (source of the query) | Orchestration lives in n8n per CLAUDE.md §0/§13 |
| Freshness / re-research suppression (RT-5) | HubSpot (stores `_verified_at`, the ground truth) | n8n Code node (`enrichmentGate.decideAction` reads it) | Already-built gate reads a HubSpot-owned datetime; n8n does not maintain its own cache |
| Human review surface | HubSpot (9 review properties + a filtered view) | n8n (schedule poll for `approved=true`, applies + clears) | SYSTEM-CONTRACT: "HubSpot and its owners supply judgment" |
| Dedupe/mangled sweep | n8n Code node (`dedupeSweep.js`, pure function, already written) | HubSpot (record source + review-flag write) | Sweep is classification-only; HubSpot remains the write target |
| Deploy + credential-provisioning scripts | Local/CI Python (`scripts/*.py` hitting the n8n Public API) | n8n Cloud (receiving end) | Mirrors `sync_hubspot_properties.py`'s idiom — a dev-time script, not a runtime dependency (AR-1 applies to *workflow* nodes, not to this tooling) |

## PRIMARY DELIVERABLE 1 — Plan-Split Recommendation

### The two halves are not independent, but their dependency is narrower than the roadmap implies

The roadmap frames this as "deployable (5–8) blocks complete (1–4, 9)." Verified against the actual code, that is only true for **live execution**, not for **authoring and offline-proving**. Every phase in this project so far (11–15.5) built and offline-fixture-tested live-shaped behavior before any live run — zero live network calls, zero HubSpot writes, proven against recorded/synthetic fixtures. There is no reason criteria 1–4/9 need to break that pattern:

- SJ-1/2/3 **schedule trigger nodes** + the **HubSpot Search query they build** need only a HubSpot-credentialed search node (a pattern already proven in `wf_contact_ingest_cloud.json` / `wf_enrichment_cloud.json`'s contacts branch) — not the ZoomInfo/Anthropic credential conversion.
- The **review loop close** (criterion 3) needs only HubSpot search/update — no provider secrets at all.
- **`dedupeSweep.js` wiring** (criterion 2) needs only a HubSpot search feeding the already-written pure function — no provider secrets.
- **RT-5 acceptance tests** (criterion 9) exercise `enrichmentGate.decideAction` + `mergeCompanies`' `cacheKeys`, both pure functions already covered by the existing offline test culture (`node --test`) — no live deploy required to prove the TTL behavior (see Deliverable 5).
- **SJ-1..SJ-3 acceptance tests** (criterion 4) are, by the spec's own design (§0.7, and AT-3 in the sibling spec), fixture-driven, not live.

What genuinely **does** hard-depend on criteria 5–8: only the *operator runbook* step of actually running the scheduled workflows live and watching a real record move through review — because that requires real secrets to exist as n8n credentials and the companies branch to exist in the Cloud template at all. This is exactly the shape Phase 15 already used (tooling built + offline-proven this phase; live property creation as a separate operator runbook step) — reuse that pattern rather than inventing a new one.

### Recommendation: two sequential plans, one phase, not a formal 16/17 split

**Reasoning against a formal phase split:**
1. Both halves touch the *same* file (`scripts/build_cloud_workflows.py`) pervasively — a phase split would either force one phase to leave it mid-edit for the other to pick up (churn/merge risk) or force near-total duplication of read/planning context.
2. The "make it complete" criteria are mostly *test authoring against already-existing functions* (RT-5) or *small, independent new nodes* (schedule triggers, review loop) that do not carry deployable's risk profile (ZoomInfo credential restructuring, an untested Public API deploy path). Bundling them with deployable's risk in one wave-ordered phase, not a separate phase, keeps the "small stuff" from being blocked on the "risky stuff" finishing entirely — only its *live* wave is.
3. A phase split creates a new ROADMAP entry, renumbers nothing (16.5 or 17 would be additive) but adds coordination overhead (two STATE.md updates, two commit boundaries) for work that is really one deliverable ("the pipeline runs live") artificially bisected.

**Recommended plan structure (for the planner to turn into PLAN.md waves):**

**Plan 16-01 "Deployable"** (criteria 5, 6, 7, 8 + the newly-found SJ-3 property gap):
- Wave 1 — Credential conversion + build-time constants. Convert the existing $env-reading HTTP header expressions (HubSpot/Lusha/Apollo/Anthropic — the mechanical cases, see Deliverable 2) to credential-bound nodes using the pattern `wf_contact_ingest_cloud.json`/`wf_enrichment_cloud.json`'s contacts branch already proves works. Inline the 6 flags as build-time constants (mirrors the existing taxonomy/escalation generated-JS split, AR-4). **Spike first**: verify n8n's native OAuth2-API credential (Client Credentials grant) actually works against ZoomInfo's token endpoint on a scratch Cloud workflow before committing to it as the ZoomInfo fix — a known n8n bug report exists for this exact grant type (see Deliverable 2); the fallback (HTTP-mint-node + secret-free cache-only Code node) is more surgery and should only be built if the spike fails.
- Wave 2 — Companies-branch port (criterion 8): copy the company branch topology from `build_enrichment_local_live()` into `build_enrichment_cloud()`, built with the now-credentialed node patterns from Wave 1 (not ported-then-converted — do it once).
- Wave 3 — Credential-provisioning + deploy scripts (criteria 6, 7), mirroring `sync_hubspot_properties.py`'s two-key-gated/dry-run-by-default/idempotent idiom (Deliverable 3). **Also add the missing `lv_enrichment_requested`/`lv_enrichment_status` properties here** — they are a HubSpot property-sync task identical in kind to Phase 15's, cheap to bundle, and criterion 1 (SJ-3) cannot mean anything without them.
- Offline-tested throughout (mocked n8n API responses, no live calls in the automated suite). Live deploy is an operator-runbook step, exactly like Phase 15.

**Plan 16-02 "Complete"** (criteria 1, 2, 3, 4, 9), depends on Plan 16-01 for its *live* wave only:
- Wave 1 — scheduleTrigger nodes for SJ-1/2/3 + the HubSpot search predicates (Deliverable 5), `dedupeSweep.js` wiring into a scheduled workflow, review-loop close nodes (search `approved=true` → apply → clear). All new nodes; all offline-testable against fixtures.
- Wave 2 — SJ-1..SJ-3 acceptance tests + RT-5 acceptance test, proving the already-implemented `decideAction`/`cacheKeys` TTL behavior end to end against fixtures (this criterion turns out to need very little new production code — see Deliverable 5).
- Wave 3 (operator runbook, non-gating) — run Plan 16-01's deploy script live, activate the 3 scheduled workflows + the (now companies-inclusive) enrichment webhook, and watch one real company flow end to end into `needs_review`, get approved, and clear.

**Escalation condition for the planner:** if the ZoomInfo OAuth2 spike in Plan 16-01 Wave 1 fails and the fallback restructuring turns out to be large (e.g. it forces a broader rethink of the Judge/Research node graph's static-data caching), that is the point to reconsider a formal Phase 16/Phase 17 split — not before.

## PRIMARY DELIVERABLE 2 — Grounded `$env` Inventory

Verified directly against the built JSON (`grep -o '\$env\.[A-Z_]*' n8n/wf_enrichment_local_live.json | sort -u`), not the roadmap's prose summary. The JSON **confirms** the roadmap's "6 secrets, 6 flags" claim exactly — no discrepancy found.

| Name | $env in JSON | Classification | Where it's read | n8n Cloud target |
|---|---|---|---|---|
| `HUBSPOT_PRIVATE_APP_TOKEN` | yes (local-live only; already 0 in `wf_*_cloud.json` — see note) | Secret | `_live_http` header expression, 2 sites (contact + company HubSpot search) | Credential type `hubspotAppToken` (n8n's private-app-token credential; internal name unchanged despite a recent UI relabel to "Service Key" — [CITED: n8n docs/PR #28479]), bound on native `n8n-nodes-base.hubspot` nodes |
| `LUSHA_API_KEY` | yes | Secret | `_live_http` header `api_key` | Generic **HTTP Header Auth** credential — **already the exact pattern `wf_enrichment_cloud.json`'s contacts branch uses today** (`_http_node(..., auth="header")`) |
| `APOLLO_API_KEY` | yes | Secret | `_live_http` header `X-Api-Key` | Generic HTTP Header Auth credential — same already-proven pattern |
| `ANTHROPIC_API_KEY` | yes (2 sites: Claude Web Research, Judge Call) | Secret | HTTP header `x-api-key` | Generic HTTP Header Auth credential (same pattern; no native n8n Anthropic credential type needed) |
| `ZOOMINFO_CLIENT_ID` | yes | Secret | Inside a **Code node** (`zoominfoToken.js` + `ZOOM_PREAMBLE_JS`), used to mint an OAuth2 bearer | **Cannot be a Code-node-read credential — see below.** Candidate: n8n's built-in **OAuth2 API** generic credential, Client Credentials grant, bound to an HTTP node |
| `ZOOMINFO_CLIENT_SECRET` | yes | Secret | Same Code node | Same as above |
| `ALLOW_WEB_RESEARCH` | yes | Flag | Research Trigger Gate | Build-time inlined constant (AR-4) |
| `MAX_WEB_RESEARCH_PER_RUN` | yes | Flag | Research Trigger Gate | Build-time inlined constant |
| `ANTHROPIC_SONNET_MODEL` | yes | Flag | Build Research Request + Build Judge Request | Build-time inlined constant |
| `WEB_RESEARCH_MAX_SEARCHES` | yes | Flag | Build Research Request | Build-time inlined constant |
| `ALLOW_SONNET_ESCALATION` | yes | Flag | Judge Gate | Build-time inlined constant |
| `MAX_SONNET_VALIDATIONS_PER_RUN` | yes | Flag | Judge Gate | Build-time inlined constant |

**Note on scope:** `wf_enrichment_cloud.json` (the existing Cloud template, contacts-only) already has **zero** `$env` references for HubSpot/Lusha/Apollo — those are already credential-bound there. It has exactly 2 `$env` refs (both ZoomInfo, inside the Code-node token-mint pattern) and 2 matching `$vars` refs — confirming ZoomInfo is the **only** already-Cloud-facing secret still broken today, everywhere else the pattern to copy already exists in the repo. `wf_contact_ingest_cloud.json` has zero `$env` references of any kind.

### The ZoomInfo problem is not a `$env`→`$vars` swap

Two session findings compound:
1. **`$vars` is not licensed on this Cloud tier** (403 `feat:variables`, per the roadmap's session investigation — [CITED: ROADMAP.md session investigation 2026-07-23], not independently re-verified this session).
2. **n8n Code nodes can never access credentials — self-hosted or Cloud, permanently, by design** [CITED: n8n community — "the code node cannot access credentials, and any other way of passing sensitive data wouldn't be as secure"]. `this.getCredentials()`/`$getCredentials()` inside a Code node error out; this is not a licensing gate.

Together these mean `zoominfoToken.js`'s pattern (a Code node reading `$vars`/`$env` directly to mint its own bearer) has **no compliant secret source on Cloud at all** — it is not a matter of finding the right variable-injection mechanism, the architecture itself must change. Two options, in preference order:

- **Preferred: n8n's built-in generic "OAuth2 API" credential, Client Credentials grant.** Configure Access Token URL = `https://api.zoominfo.com/gtm/oauth/v1/token`, Client ID/Secret, Authentication = Header (Basic). Bind it to the ZoomInfo enrich HTTP node(s) directly (no Code node in the auth path at all) — n8n handles mint/cache/refresh natively. **Risk, flagged for a spike, not assumed:** a GitHub issue reports the generic OAuth2 Client Credentials grant returning a misleading 422 on some n8n versions [CITED: github.com/n8n-io/n8n/issues/16857, /issues/11957] — unverified whether the currently-provisioned Cloud instance is affected. If it works, this **deletes** `zoominfoToken.js`'s manual cache/refresh/retry-on-401 logic entirely (Don't Hand-Roll: the platform already does this).
- **Fallback: split the Code node.** A credential-bound HTTP node performs the token mint (Basic Auth credential: username=client_id, password=client_secret); a downstream Code node (no secrets, only `$getWorkflowStaticData`) decides whether to call it (cache-miss/near-expiry check) via an IF branch, and reads/writes the cached token from workflow static data exactly as `zoominfoToken.js` does today — just without ever touching the secret itself. This preserves the existing cache/401-retry behavior at the cost of 3–4 more nodes and a branch in the graph.

## PRIMARY DELIVERABLE 3 — Deploy + Credential-Provisioning Approach

### Idiom to mirror

`scripts/sync_hubspot_properties.py` is the established pattern for exactly this kind of tool in this repo (env-gated, dry-run-by-default, idempotent, per-item creates not batch, undo-manifest, post-write confirmation). `.env.example`'s diff this session already added the matching gate for n8n: `ALLOW_N8N_DEPLOY=false` alongside `N8N_URL`/`N8N_API_KEY` — the two-key gate convention (`DRY_RUN=false AND ALLOW_N8N_DEPLOY=true`) is already anticipated in the environment contract; the deploy script should use exactly that pair.

### Public API shapes (MEDIUM confidence — community-sourced, not tool-verified this session)

- **Create workflow:** `POST /api/v1/workflows`, body requires `name` + `nodes`; `connections`/`settings` optional. **New workflows are always created inactive** — a separate activate call is required [CITED: n8n community]. The body likely must **not** include a client-supplied top-level `id` (server-assigned) — verify on the first real call against the confirmed-empty instance rather than guessing further; this is a natural first operator-runbook step since the instance has 0 workflows today.
- **Update workflow:** `PUT /api/v1/workflows/{id}` — all fields optional [CITED: n8n community/docs].
- **Create credential:** `POST /api/v1/credentials`, body `{name, type, data, isResolvable?}`. `type` is the credential-type internal name (e.g. `hubspotAppToken`, `httpHeaderAuth`, `oAuth2Api`); the exact `data` shape per type can be introspected via `GET /api/v1/credentials/schema/{credentialType}` before constructing the create body [CITED: n8n community/docs] — the provisioning script should call this once per type and assert the field names it's about to send match, rather than hardcoding a guessed shape.
- **List:** `GET /api/v1/workflows`, `GET /api/v1/credentials` — already confirmed live and working this session per the roadmap.

### Idempotency / create-vs-update diff

n8n does not let a client set its own workflow ID; the deploy script's local JSON files already carry a distinct, stable top-level `name` per workflow (e.g. `"LV Enrichment (Cloud template)"`), set by `build_cloud_workflows.py` — **match on `name`, not on the JSON's internal `id` field.** Diff algorithm, mirroring `sync_hubspot_properties.py::compute_property_diff`:
1. `GET /api/v1/workflows` → build `{name: live_id}`.
2. For each local `n8n/wf_*.json`: if `name` is in the live map → `PUT` (update) that `live_id`; else → `POST` (create), then optionally `POST /activate` for the two Cloud-facing production templates only (not the `*_local*` files — see the deployable-set note below).
3. Dry-run mode prints the diff (`would create: [...]`, `would update: [...]`) without calling; live mode requires the two-key gate.
4. Credentials: same pattern against `GET /api/v1/credentials`, matched by `name`; a credential's `data` cannot be diffed back (n8n never returns secret values), so treat credential provisioning as **create-if-missing only**, never update-in-place — rotation is a manual "delete + recreate" operator action, exactly as ZoomInfo's own secret-rotation note in the existing Cloud-template sticky-note documentation already assumes ("Rotate the client secret ~quarterly").

### Respecting `test_top_level_is_exactly_the_deployable_set`

That test guards `n8n/*.json` == exactly the 5 `ACTIVE` files (`wf_contact_ingest_cloud.json`, `wf_contact_ingest_local.json`, `wf_enrichment_cloud.json`, `wf_enrichment_local.json`, `wf_enrichment_local_live.json`). Per AR-1's own comment, "import every workflow in `n8n/`" is meant to be a safe instruction — but three of the five (`*_local*.json`, `wf_enrichment_local_live.json`) use a Manual Trigger and are dev/test replicas; `wf_enrichment_local_live.json` specifically still contains the raw `$env` expressions this phase is retiring elsewhere (by design — it is the *local docker-replica* variant, not meant to run unattended on Cloud). **Recommendation:** the deploy script imports all 5 (satisfying "the top-level directory is the deploy manifest") but only **activates** the schedule/webhook triggers on the two genuinely production-shaped ones (`wf_contact_ingest_cloud.json`, `wf_enrichment_cloud.json`, plus whichever new scheduled-workflow file Plan 16-02 adds). The three Manual-Trigger workflows import inertly — n8n does not auto-run a Manual Trigger, so importing them is safe even though their Code nodes would error on `$env` if a human manually ran them on Cloud; document that as expected, not a bug.

## PRIMARY DELIVERABLE 4 — Companies-Branch Port

Confirmed directly from `scripts/build_cloud_workflows.py`: `build_enrichment_cloud()` (the webhook production template, lines ~2050–2268) is **contacts-only** — `Webhook Trigger → Build Identity → HubSpot Search (contact) → Adapt Search → Enrichment Gate → Route Action → Lusha/Apollo/ZoomInfo → Normalize+Score → Merge Winners → Decide Action → IF Create/Enrich → HubSpot Create/Update`. There is no company node anywhere in that function (`grep -in "compan"` returns zero hits inside it). `build_enrichment_local_live()` (lines ~1824–2013) **does** have the full company branch, as a sibling off the same trigger (not nested — matches the locked Phase-11 decision): `Emit Company Targets → Build Company Identity → HubSpot Company Search → Adapt Company Search → Company Gate → Build Company Requests → Lusha Company / Apollo Org / ZoomInfo Company → Normalize+Score Company → Research Trigger Gate → IF Research Needed → [Build Research Request → Claude Web Research → Validate Research Output] → Judge Gate → IF Needs Judge → [Build Judge Request → Judge Call → Apply Judge Verdict] → Merge Company → Decide Company Action`.

**Smallest correct port:** copy this exact node sequence and its `research_conns` wiring dict (already isolated in the source as a standalone `research_conns = {...}` block, lines ~1985–2005, specifically because it doesn't collide with the fan-in from the contacts chain) into `build_enrichment_cloud()`, with two changes only:
1. Every `_live_http(...)` call (raw HTTP with a `$env` Bearer header) becomes the Cloud pattern already used for contacts in the same function: native `n8n-nodes-base.hubspot` node for the two HubSpot searches, `_http_node(..., auth="header")` for Lusha/Apollo/Anthropic, and the ZoomInfo restructuring from Deliverable 2 for the two ZoomInfo Code nodes (`ENRICH_ZOOMINFO_CACHED` reused as-is for contacts already exists in the Cloud file; the company one, `ENRICH_ZOOMINFO_CO_CACHED`, needs the identical fix applied once and shared).
2. `Decide Company Action` needs a Cloud variant (`ENRICH_DECIDE_CO_CLOUD`, mirroring the existing `ENRICH_DECIDE_CLOUD` vs `ENRICH_DECIDE_LOCAL` pattern already used for contacts) that computes the property patch and lets IF nodes route to real HubSpot company Create/Update (gated), instead of `ENRICH_DECIDE_CO_LOCAL`'s dry-run echo.

No logic duplication is required beyond that — `mergeCompanies`, `judge.js`, `webResearch.js`, and the scoring engine are all already inlined via the same `inline(...)` helper used everywhere else in the file; the port is a topology copy + edge-type swap, not new business logic. This is the same "same inlined JS, different edges" pattern the file's own README already documents for the contacts Cloud/local pair.

## PRIMARY DELIVERABLE 5 — SJ Predicates + Review Loop + RT-5

### SJ predicate HubSpot search shapes

HubSpot's Search API ORs across `filterGroups` and ANDs within a group — get this backwards and the predicate silently becomes AND instead of the spec's OR (or vice versa). Grounded in the same `filterGroups` shape `HS_CO_SEARCH_BODY_EXPR` already uses in the codebase.

**SJ-1 (hourly input-gap scan, companies)** — three single-filter OR'd groups, exactly spec §0.7's "any... is unresolved":
```json
{"filterGroups": [
  {"filters": [{"propertyName": "lv_org_type", "operator": "NOT_HAS_PROPERTY"}]},
  {"filters": [{"propertyName": "lv_org_type", "operator": "EQ", "value": "unknown"}]},
  {"filters": [{"propertyName": "lv_produces_content", "operator": "NOT_HAS_PROPERTY"}]}
]}
```
Must reference only `lv_org_type`/`lv_produces_content` — never `lv_icp_tier` (Approach C).

**SJ-2 (monthly stale refresh, companies)** — two OR'd groups on the two cache-key datetimes; HubSpot's `LT` operator on a `datetime` property expects epoch **milliseconds**, computed in a Code node (`Date.now() - 180*86400000`) before the search node, not a date string:
```json
{"filterGroups": [
  {"filters": [{"propertyName": "lv_org_type_verified_at", "operator": "LT", "value": "{{epoch_ms_180d_ago}}"}]},
  {"filters": [{"propertyName": "lv_produces_content_verified_at", "operator": "LT", "value": "{{epoch_ms_180d_ago}}"}]}
]}
```

**SJ-3 (15-min requested poller)** — **blocked on a missing property, not just missing wiring.** `lv_enrichment_requested = true AND lv_enrichment_status ≠ running` requires both properties as a single AND'd filter group. **Neither `lv_enrichment_requested` nor `lv_enrichment_status` exists in `config/hubspot_properties.yaml`'s current 33-property manifest** — grepped directly, zero matches for `requested|_status|_lock|priority|run_id|last_enriched` anywhere in that file. This is not mentioned in ROADMAP.md's "9 review properties" or STATE.md's known-gaps list. SJ-3 is also SYSTEM-CONTRACT commitment 9's literal "on-demand (per-record flag, ~15 min)" trigger — without `lv_enrichment_requested` there is no way for a human to flag a record via HubSpot UI at all. **Add these two properties (minimum) to the manifest and re-run the sync** — this belongs in Plan 16-01 Wave 3 alongside the credential-provisioning script, same idiom, same risk profile (a HubSpot property sync, already-proven tooling). `lv_enrichment_lock_until`/`priority`/`last_enrichment_run_id` from CLAUDE.md §4.1 can be deferred — SJ-3's predicate as spec'd only needs the two.

### §22.2 review loop, grounded against the actual 9 properties

CLAUDE.md §22.2's flow, re-expressed against the properties that actually exist (`config/hubspot_properties.yaml`, same 9 names on both `companies` and `contacts`):

1. A merge decision hits `needs_review` (from `mergeCompanies`'s `_gate`, e.g. confidence-below-threshold or evidence-gate failure) → set `lv_enrichment_needs_review=true`, `lv_enrichment_review_reason=<gate.reason>`.
2. The full decision context — including per-field evidence, since Phase 15's provenance-blob model retired the flat `_evidence_url` properties — is written into `lv_enrichment_review_candidate_json` (the `decisions`/`provenance` output of `mergeCompanies`, stably-stringified, same serializer already used for `lv_enrichment_provenance`).
3. RevOps opens a HubSpot filtered view: `lv_enrichment_needs_review=true OR lv_icp_needs_review=true`. **Evidence URLs are inside the JSON blob in `lv_enrichment_review_candidate_json`/`lv_enrichment_provenance`, not a top-level property** — the view/report the operator runbook documents should say this explicitly, or a human will look for a flat "evidence URL" column that no longer exists post-Phase-15.
4. RevOps approves by setting `lv_enrichment_review_approved=true` and (convention, not enforced by any property) typing their name into `lv_enrichment_reviewed_by` at the same time — **there is no property or API mechanism in this manifest that captures who flipped the checkbox automatically**; HubSpot's property-history API could derive it later but that is out of this phase's scope, and treating it as a manual two-field RevOps convention costs nothing to document now.
5. A scheduled n8n workflow (can piggyback on SJ-3's 15-min cadence, or be its own poll) finds `lv_enrichment_review_approved=true`, parses `lv_enrichment_review_candidate_json`, re-applies the recorded `promote` decisions to their real canonical fields (respecting Approach C — never `lv_icp_fit_score`/`lv_icp_tier`), then **clears** `lv_enrichment_needs_review`, `lv_enrichment_review_approved`, `lv_enrichment_review_reason`, `lv_enrichment_review_candidate_json`, and stamps `lv_enrichment_reviewed_at=now()`.

### RT-5 is already mostly built — this is the phase's most consequential finding

Traced the actual call graph rather than trusting the roadmap's framing that RT-5 is unbuilt:

- `enrichmentGate.js::decideAction` (already wired as `ENRICH_CO_GATE` in `build_enrichment_local_live()`) treats a **missing** required field (`lv_org_type`/`lv_produces_content`) as `missingFields` unconditionally — always `enrich`, regardless of `_verified_at` age. A **present** field only becomes `staleFields` (triggering re-enrichment) if `now - _verified_at > 180 days`; a present field with no `_verified_at` at all is conservatively treated as stale (`unknown freshness == needs validation`, already commented in the source).
- `mergeCompanies.js` stamps `cacheKeys[lv_org_type_verified_at] = now()` **whenever `lv_org_type` appears as a candidate at all** — regardless of whether the gate decision was `promote` or `needs_review`. This means a `needs_review` outcome still records "we evaluated this on this date," but because the *value* was never promoted (stays blank), the *next* run's `decideAction` sees `missingFields`, not `staleFields`, and retries anyway — the two mechanisms do not fight each other.
- The Research Trigger Gate's `needsResearch()` reads the raw field value (`orgUnresolved`/`contentBlank`), not `_verified_at` — the actual TTL enforcement lives one level up, in the Company Gate deciding whether the row even reaches the research/provider branches at all (rows the Gate marks `skip` are filtered out before `Normalize + Score Company`).

Net effect: since `domain` is this system's per-company identity anchor (one HubSpot company record = one domain), and freshness is already keyed on that record's own `_verified_at` properties, **"cached by domain, 180-day TTL" is already the emergent behavior of code that exists today** — contingent only on the 4 cache-key datetime properties existing live (Phase 15's operator runbook, outside this phase) and on something actually invoking `Company Gate` on a schedule (SJ-2, this phase). **Criterion 9's remaining work is: wire SJ-2's schedule trigger to feed `Company Gate`, and write the acceptance test proving the above three bullets end to end against a fixture** (a company evaluated 10 days ago is skipped; the same company forced to 200 days ago is re-queued; a company with no `_verified_at` at all — present value, unknown freshness — is treated as stale) — not new merge/scoring logic.

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Python framework | pytest (no `pytest.ini`/`pyproject.toml` found at root — plain `pytest` discovery from `tests/`) |
| JS framework | Node's built-in `node:test` (no `package.json`/test runner config found — invoked directly, e.g. `node --test tests/n8n/mergeCompanies.test.mjs`) |
| Config file | none — see Wave 0 gap below |
| Quick run command | `node --test tests/n8n/<new-test-file>.test.mjs` (single file, seconds) |
| Full suite command | `pytest` (Python) + `node --test tests/n8n/*.test.mjs` (JS) — the pattern every prior phase's SUMMARY reports ("N pytest / M node passed") |

### Phase Requirements → Test Map

No REQ-IDs are mapped to Phase 16 (`phase_req_ids: null`); success is the ROADMAP's 9 criteria + SYSTEM-CONTRACT. Mapping each:

| Criterion | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| 1/4 SJ-1 predicate | Company with blank `lv_org_type` OR `lv_produces_content` is queued; a fully-resolved company is not | unit (JS, fixture HubSpot search response) | `node --test tests/n8n/sjPredicates.test.mjs` | ❌ new file |
| 1/4 SJ-2 predicate + RT-5 | `_verified_at` 10 days old → skip; 200 days old → re-queue; absent → treated as stale | unit (JS, reuses existing `decideAction`) | same file or `tests/n8n/enrichmentGate.test.mjs` extension | ❌ new (no direct `enrichmentGate.js` test file exists yet — grep confirms) |
| 1/4 SJ-3 predicate | `lv_enrichment_requested=true AND lv_enrichment_status≠running` fires; `running` does not | unit (JS) | `node --test tests/n8n/sjPredicates.test.mjs` | ❌ new file |
| 2 dedupeSweep wiring | Sweep runs against a fetched record set inside a scheduled workflow; flags never write | unit (JS, `dedupeSweep.js` already tested as a pure function — verify a wiring/graph-ancestry test, RO-2-style) | `node --test tests/n8n/dedupeSweepWiring.test.mjs` (or extend `test_architecture_guard.py`-style graph test) | Pure function tested elsewhere; wiring untested — check first |
| 3 review loop | `approved=true` → candidate JSON parsed → canonical fields patched → all 4 flag/JSON properties cleared; never touches `lv_icp_*` | unit (JS) | `node --test tests/n8n/reviewLoop.test.mjs` | ❌ new file |
| 5 credential conversion | Built Cloud JSON contains zero `$env`/`$vars` references (mirrors the existing AR-2 host guard style) | static/architecture | extend `tests/test_architecture_guard.py` with a `test_no_env_or_vars_in_cloud_workflows` | ❌ new test, existing file |
| 6/7 deploy + credential scripts | Dry-run diff computes correct create-vs-update against a mocked `GET /api/v1/workflows` response; two-key gate refuses without both `DRY_RUN=false` and `ALLOW_N8N_DEPLOY=true` | unit (Python, `requests-mock` or manual monkeypatch, no live network) | `pytest tests/test_deploy_n8n_workflows.py` | ❌ new file (mirror `tests/test_sync_hubspot_properties.py`'s existing mocking pattern) |
| 8 companies-branch port | `build_enrichment_cloud()`'s node/connection graph includes the company branch (BFS reachability from Webhook Trigger, RO-2-style graph-ancestry test already precedented in `tests/test_judge_spec.py`) | static/architecture | `pytest tests/test_cloud_companies_branch.py` | ❌ new file |
| 9 RT-5 | See SJ-2 row above — same test | unit (JS) | same as SJ-2 | — |

### Sampling Rate

- **Per task commit:** the single new/changed test file (`node --test <file>` or `pytest <file>`)
- **Per wave merge:** full offline suite (`pytest` + `node --test tests/n8n/*.test.mjs`) — matches every prior phase's "N pytest / M node passed" gate
- **Phase gate:** full suite green, **plus** the Plan 16-02 Wave 3 operator runbook (non-gating, live) actually exercised at least once before the phase is marked complete — mirrors Phase 15's precedent of separating "tooling proven" from "live-run done"

### Wave 0 Gaps

- [ ] `tests/n8n/sjPredicates.test.mjs` — covers SJ-1/2/3 predicate logic (criterion 4)
- [ ] `tests/n8n/reviewLoop.test.mjs` — covers the §22.2 apply/clear state machine (criterion 3)
- [ ] `tests/test_deploy_n8n_workflows.py` — covers the deploy script's diff/idempotency logic, mocked (criterion 7)
- [ ] `tests/test_cloud_companies_branch.py` — covers the ported graph structurally (criterion 8)
- [ ] A direct `enrichmentGate.js` unit test file does not exist yet (its logic is currently only exercised indirectly through `mergeCompanies.test.mjs`-adjacent fixtures, per Phase 15.5's Wave-0-gap precedent of adding first-ever direct tests for a previously only-indirectly-covered module) — add one, it is the load-bearing function for RT-5/SJ-2
- Framework install: none — pytest and Node's built-in `node:test` are already in use project-wide, no new dependency

## Standard Stack

No new runtime library is needed anywhere in this phase's *deliverable* (n8n workflow JSON) — AR-1 forbids middleware, and n8n's native node types (`scheduleTrigger`, `httpRequest` with `genericCredentialType`, `hubspot`) cover every criterion. The only *new code* is in Python tooling and Code-node JS, both using patterns/deps already present in the repo.

### Core (already-installed, reused)
| Library | Version | Purpose | Why Standard |
|---|---|---|---|
| `requests` | already a dependency (used throughout `src/hubspot_client.py`, `scripts/sync_hubspot_properties.py`) | HTTP calls from the deploy/credential-provisioning scripts to the n8n Public API | Same idiom as every other live-API script in the repo; no reason to add `httpx`/anything else |
| `PyYAML` | already a dependency | Reading `config/hubspot_properties.yaml`-shaped manifests if the SJ-3 property additions are modeled the same way | Same pattern already governs the 33-property manifest |
| Node `node:test` + `node:assert/strict` | Node built-in | New `.test.mjs` files | Zero-dependency, matches every existing `tests/n8n/*.test.mjs` |

### Supporting
| Library | Version | Purpose | When to Use |
|---|---|---|---|
| n8n's native `n8n-nodes-base.scheduleTrigger` | n8n platform-provided | SJ-1/2/3 trigger nodes | Built-in cron/interval trigger — do not hand-roll a polling loop |
| n8n's native generic **OAuth2 API** credential | n8n platform-provided | ZoomInfo Client Credentials grant (Deliverable 2 preferred option) | Spike first; this is the "don't hand-roll a token cache" option |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|---|---|---|
| n8n's native OAuth2 API credential for ZoomInfo | Keep the Code-node-based cached-token pattern, split around a credential-bound HTTP mint node (Deliverable 2 fallback) | More node/graph surgery, but a known-working fallback if the native OAuth2 grant hits the reported 422 bug |
| A dedicated deploy Python package (e.g. an n8n SDK) | Raw `requests` against the documented Public API | The existing repo idiom (`sync_hubspot_properties.py`) never adds an SDK for a handful of REST calls; consistent, zero new dependency |

**Installation:** none required — no `pip install`/`npm install` needed for this phase.

## Package Legitimacy Audit

**Not applicable.** This phase introduces no new external package dependency in any ecosystem — the deploy/credential-provisioning scripts reuse `requests`/`PyYAML` (already installed, already vetted by prior phases), and the workflow-side changes use only n8n's own native node types and Node's built-in `node:test`. No `package-legitimacy check` run was needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| ZoomInfo OAuth2 client-credentials token mint/cache/refresh | A second bespoke Code-node token cache (the current pattern, broken on Cloud) | n8n's native OAuth2 API generic credential (Client Credentials grant), spiked first | The platform already solves "cache a bearer token and refresh it" — hand-rolling it a second way (even correctly) is exactly the kind of complexity SYSTEM-CONTRACT commitment 6 ("right-sized compute... capability spent only where it changes the outcome") warns against |
| Scheduled polling | A Cron package, a `setInterval` loop, or an external scheduler | `n8n-nodes-base.scheduleTrigger` | Native to the platform this phase is deploying to |
| Idempotent workflow deploy diffing | A custom ID-tracking file/database | Match on the JSON's already-unique `name` field against a fresh `GET /api/v1/workflows`, mirroring `sync_hubspot_properties.py`'s "diff is always re-derived from a fresh GET, never local state" idiom | Re-deriving from source of truth every run is what makes `sync_hubspot_properties.py` idempotent after a mid-run failure; the same property should hold here |
| Per-record enrichment locking | A new distributed-lock mechanism | Nothing new needed yet — cost caps (`MAX_WEB_RESEARCH_PER_RUN`, `MAX_SONNET_VALIDATIONS_PER_RUN`) already bound the blast radius of SJ-1/2/3 firing concurrently on overlapping records; `lv_enrichment_lock_until` from CLAUDE.md §4.1 can be deferred rather than built speculatively | YAGNI — the existing cost caps make double-processing wasteful, not unsafe (merge is idempotent-ish: a re-run just re-stamps `_verified_at`) |

**Key insight:** almost everything this phase needs to *build* is either already written (RT-5's mechanics, the pure `dedupeSweep`/`mergeCompanies`/`enrichmentGate` functions) or already offered natively by n8n (schedule trigger, OAuth2 credential, header-auth credential). The actual new code surface is smaller than the roadmap's 9-criteria list suggests once the already-built pieces are subtracted.

## Common Pitfalls

### Pitfall 1: Assuming `$vars` is the fix for everything `$env` touches
**What goes wrong:** A mechanical "replace every `$env.X` with `($vars.X || $env.X)`" pass (which the codebase already half-did, defensively, in several spots) looks complete but silently does nothing on this Cloud tier, because `$vars` itself is unlicensed.
**Why it happens:** The fallback pattern (`$vars.X || $env.X`) reads as "handles both cases" when actually neither branch resolves on this instance.
**How to avoid:** Verify the actual credential-store/generic-credential route per secret (Deliverable 2's table), not a variable-injection route, for every one of the 6 secrets.
**Warning signs:** A workflow that imports cleanly but every provider call 401s at runtime with no local repro (since local Docker replicas legitimately use `$env` and will keep passing).

### Pitfall 2: Treating `n8n/*.json`'s Manual-Trigger workflows as production deploy targets
**What goes wrong:** Deploying `wf_enrichment_local_live.json` to Cloud and expecting it to run unattended — it never will (Manual Trigger, and its Code nodes reference `$env` by design as the docker-replica variant).
**Why it happens:** `test_top_level_is_exactly_the_deployable_set` groups all 5 files as one guarded set, which reads as "these are all the same kind of deployable."
**How to avoid:** Import all 5 (satisfies the existing test's intent), activate schedule/webhook triggers on only the genuinely production-shaped ones.
**Warning signs:** A "why is this workflow in the Cloud instance but never runs" question from an operator.

### Pitfall 3: HubSpot search `filterGroups` AND/OR inversion
**What goes wrong:** SJ-1's "any field unresolved" (OR) accidentally becomes "all fields unresolved" (AND) by putting the three conditions inside one `filters` array instead of three separate `filterGroups`.
**Why it happens:** HubSpot's shape is non-obvious — filters *within* a group AND, groups themselves OR — and it's easy to reach for the more familiar "one filters array" shape.
**How to avoid:** Mirror the exact `HS_CO_SEARCH_BODY_EXPR` shape already in the codebase (a single group there because it's a single-condition domain lookup); for a true OR, use N single-filter groups as shown in Deliverable 5.
**Warning signs:** SJ-1 queues near-zero companies (should queue most of them pre-enrichment) because the AND collapsed the predicate to "every field is simultaneously unresolved," a much rarer condition than "any field is."

### Pitfall 4: Building SJ-3 before checking the properties it needs exist
**What goes wrong:** Authoring the SJ-3 scheduleTrigger + search node against `lv_enrichment_requested`/`lv_enrichment_status`, only to find at live-test time that HubSpot returns them as always-blank because they were never created.
**Why it happens:** Every other property this phase touches (`lv_org_type`, the 9 review properties, the 4 cache-key datetimes) already exists from Phase 15 — it's reasonable to assume the rest of the control-plane came along too. It didn't (Deliverable 5).
**How to avoid:** Add the two missing properties in Plan 16-01 Wave 3, before Plan 16-02 authors SJ-3.
**Warning signs:** none until live-test — this is exactly why it's worth catching in research rather than discovering mid-plan.

## Code Examples

### SJ-1 filterGroups (OR across groups) — see Deliverable 5 for the full JSON.

### Idempotent create-vs-update diff, Python (pattern to follow, mirrors `compute_property_diff`)
```python
# Source: pattern established in scripts/sync_hubspot_properties.py::compute_property_diff
def compute_workflow_diff(local_workflows: list[dict], live_workflows: list[dict]) -> dict:
    live_by_name = {w["name"]: w["id"] for w in live_workflows}
    create, update = [], []
    for wf in local_workflows:
        name = wf["name"]
        if name in live_by_name:
            update.append({"id": live_by_name[name], "body": wf})
        else:
            create.append(wf)
    return {"create": create, "update": update}
```

### RT-5 / SJ-2 fixture shape for the acceptance test (Deliverable 5)
```javascript
// Source: derived from the existing decideAction contract (n8n/code/enrichmentGate.js)
// and mergeCompanies' cacheKeys contract (n8n/code/mergeCompanies.js)
const fresh = { lv_org_type: "governing_body_league", lv_org_type_verified_at: daysAgo(10) };
const stale = { lv_org_type: "governing_body_league", lv_org_type_verified_at: daysAgo(200) };
const neverVerified = { lv_org_type: "governing_body_league" }; // present, no _verified_at
// decideAction(fresh, REQUIRED, POLICY, NOW).action        === "skip"  (within 180d TTL)
// decideAction(stale, REQUIRED, POLICY, NOW).action         === "enrich" (staleFields)
// decideAction(neverVerified, REQUIRED, POLICY, NOW).action === "enrich" (unknown freshness == stale)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| ZoomInfo secrets via `$env` (docker-local pattern) | Must become a credential (Cloud blocks `$env`, Code nodes can never hold credentials) | This phase | Forces the ZoomInfo token-mint architecture change (Deliverable 2) |
| Flat per-field metadata properties (`lv_<field>_source` etc.) | One JSON provenance blob per object | Phase 15 | Review-surface UI/runbook must read evidence from inside the blob, not a flat column — carried forward as a note in Deliverable 5 |
| `lv_icp_fit_score`/`lv_icp_tier` as pipeline write targets | HubSpot-derived only (Approach C) | Phase 15 (locked 2026-07-20) | Every SJ predicate and every review-loop apply step in this phase must key on inputs only — already respected throughout this research |

**Deprecated/outdated:** CLAUDE.md §19.2/§19.5's original scheduled-job predicates (keyed on `lv_icp_tier`/`lv_icp_scored_at`) are explicitly superseded by WEB-RESEARCH-SPEC.md §0.7's SJ-1/2/3 — do not resurrect the CLAUDE.md versions.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | n8n Public API `POST /api/v1/workflows` rejects a client-supplied top-level `id` and requires a separate `/activate` call | Deliverable 3 | Deploy script's create path would need a quick shape fix; low risk since the first live call against the confirmed-empty instance will surface this immediately and non-destructively |
| A2 | n8n's generic OAuth2 API credential (Client Credentials grant) works against ZoomInfo's token endpoint on this specific Cloud instance/version | Deliverable 2 | If it hits the reported 422 bug, Plan 16-01 needs the fallback (credential-bound HTTP mint node + cache-only Code node) instead — flagged explicitly as a spike, not committed to in the plan |
| A3 | `$vars` is genuinely unlicensed on this Cloud tier (not independently re-verified this session; taken from the roadmap's session investigation) | Deliverable 2 | If actually available, the flag-constant approach could use `$vars` instead of build-time inlining for the 6 config flags — lower-priority difference, doesn't change the secret-handling conclusion |
| A4 | `POST /api/v1/credentials` accepts `type: "hubspotAppToken"` with a `data.appToken` field matching that internal name | Deliverable 2/3 | The provisioning script should call `GET /api/v1/credentials/schema/hubspotAppToken` first and assert the shape, rather than hardcoding it — mitigation already built into the recommendation |
| A5 | No lock/concurrency mechanism is needed given existing cost caps | Don't Hand-Roll | If SJ-1/2/3 firing concurrently on the same company causes a real problem (e.g. two Judge calls double-billed), `lv_enrichment_lock_until` from CLAUDE.md §4.1 would need to be added — deferred deliberately, not overlooked |

## Open Questions

1. **Does the review-loop apply step need its own n8n workflow, or can it share SJ-3's 15-minute poller?**
   - What we know: both need a HubSpot search + a conditional apply; the properties differ (`lv_enrichment_requested` vs `lv_enrichment_review_approved`).
   - What's unclear: whether combining them into one scheduled workflow (two search branches off one trigger, mirroring the companies/contacts sibling-branch pattern already used elsewhere) is cleaner than two separate scheduled workflows.
   - Recommendation: default to two search branches off one 15-minute trigger (fewer moving parts, same trigger cadence is already right for both) unless the plan's own graph gets unwieldy — leave the call to the planner/executor once the actual node count is visible.

2. **Should `lv_enrichment_reviewed_by` ever be populated programmatically?**
   - What we know: no property or n8n-accessible API captures "which HubSpot user flipped this checkbox" today; HubSpot's property-history API could derive it.
   - What's unclear: whether RevOps process discipline (type your name when you approve) is durable enough, or whether this becomes a recurring gap.
   - Recommendation: ship the manual-convention version now (documented in the operator runbook); revisit only if it proves unreliable in practice.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| n8n Public API (`N8N_URL`/`N8N_API_KEY`) | Deploy + credential-provisioning scripts | ✓ (confirmed live this session, per ROADMAP.md) | n8n Cloud, version not independently re-checked this session | — |
| n8n MCP server (`.mcp.json`, authoring-only) | Not directly needed by this phase's deliverables (import is a Public API concern, not MCP) | ✓ configured | — | Public API covers everything this phase needs; MCP is a nice-to-have for post-deploy activation/rollback, not required |
| HubSpot Private App token | All company/contact reads/writes | ✓ (portal 22617666 migrated, per STATE.md) | — | — |
| ZoomInfo/Apollo/Lusha/Anthropic live API access | Companies-branch port live verification | Assumed ✓ (used successfully in Phase 11-15.5 live smokes) | — | — |

**Missing dependencies with no fallback:** none identified — the one open risk (ZoomInfo OAuth2 credential grant) has an explicit fallback already designed (Deliverable 2).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | No | No interactive end-user auth surface introduced |
| V3 Session Management | No | — |
| V4 Access Control | Partial | HubSpot's own portal RBAC governs who can flip `lv_enrichment_review_approved`; not this phase's concern to build |
| V5 Input Validation | Yes | HubSpot search filter values built from Code-node-computed epoch millis / static property names — no raw user input reaches these queries |
| V6 Cryptography | Yes | Secrets at rest live in n8n's own encrypted credential store (platform-managed) — this phase's scripts must never log a secret value, mirroring `sync_hubspot_properties.py`'s existing practice of only logging HTTP status codes, never the token |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Secret leakage via script stdout/logs | Information Disclosure | Deploy/credential-provisioning scripts print status codes and diffs only, never `data.appToken`/API key values — same discipline as `sync_hubspot_properties.py` |
| Concurrent schedule triggers double-processing the same record | Denial of Service (cost) | Existing `MAX_WEB_RESEARCH_PER_RUN`/`MAX_SONNET_VALIDATIONS_PER_RUN` caps already bound this; `enrichment_lock_until` deferred per Assumption A5 |
| A malformed/expired ZoomInfo OAuth2 credential silently 401-looping | Tampering (data) | Whichever ZoomInfo approach ships must preserve the existing "on 401, re-mint once, then continue not retry-forever" behavior already proven in `zoominfoToken.js`'s tests |
| Review-loop apply step promoting a field Approach C forbids (`lv_icp_fit_score`/`lv_icp_tier`) | Tampering | The apply step must reuse the same `canonicalPatch`-shaped output `mergeCompanies` already produces (which never contains those keys post-Phase-15), not a hand-built patch that could reintroduce them |

## Sources

### Primary (HIGH confidence — read directly this session)
- `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `docs/SYSTEM-CONTRACT.md`, `docs/WEB-RESEARCH-SPEC.md` — full read
- `scripts/build_cloud_workflows.py` — full read (2298 lines)
- `n8n/wf_enrichment_local_live.json`, `n8n/wf_enrichment_cloud.json`, `n8n/wf_contact_ingest_cloud.json` — grepped for `$env`/`$vars` directly
- `scripts/sync_hubspot_properties.py` — full read
- `config/hubspot_properties.yaml` — full read
- `n8n/code/mergeCompanies.js`, `n8n/code/enrichmentGate.js`, `n8n/code/dedupeSweep.js` — full read
- `n8n/README.md` — full read
- `tests/test_architecture_guard.py` — full read (deployable-set + AR guards)
- `.env.example` git diff (direct read denied by sandbox; diff obtained via `git diff`)

### Secondary (MEDIUM confidence — community/docs, not tool-verified live this session)
- n8n Docs / community: HubSpot credential type `hubspotAppToken` (github.com/n8n-io/n8n-docs, PR #28479)
- n8n community: Code node cannot access credentials (community.n8n.io threads, github.com/n8n-io/n8n issues #17282/#14110)
- n8n Docs/community: Public API workflow create/update field requirements, credential create shape, `/credentials/schema/{type}` endpoint
- n8n Docs: `scheduleTrigger` interval/cron parameter shape
- n8n GitHub issues #16857/#11957/#11025: reported bugs in generic OAuth2 Client Credentials grant

### Tertiary (LOW confidence — carried from the roadmap's own session investigation, not independently re-verified)
- `$env` blocked by default on n8n Cloud (`N8N_BLOCK_ENV_ACCESS_IN_NODE`), `$vars` returning 403 `feat:variables` on this tier, n8n Public API confirmed live, instance confirmed empty — all per ROADMAP.md's "verified live" session note, tagged [CITED: ROADMAP.md session investigation 2026-07-23] throughout this document rather than [VERIFIED], since this research session did not re-run those live probes itself

## Metadata

**Confidence breakdown:**
- `$env`/`$vars` inventory, companies-branch port gap, RT-5 already-implemented finding, SJ-3 missing-property gap: HIGH — all directly grepped/read from code this session
- Plan-split structure: HIGH — grounded in an actual dependency trace of what each criterion needs, not a restatement of the roadmap's framing
- n8n Public API/credential mechanics, ZoomInfo OAuth2 fix: MEDIUM — community-sourced, explicitly flagged for a spike before commitment
- Cloud licensing facts (`$vars` 403, `$env` blocked): LOW-by-provenance (carried from an earlier session's live investigation, not re-verified here) but treated as reliable given it was a direct live probe, not training-data recall

**Research date:** 2026-07-23
**Valid until:** ~14 days for the n8n Cloud API/credential-mechanics claims (fast-moving platform, community-sourced); ~60 days for the codebase-grounded findings (stable until the next phase touches these files)
