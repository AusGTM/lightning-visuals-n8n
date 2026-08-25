---
status: fixing
trigger: "Fix F3 first then F1, and choose to allow ungranted send for F2, wrap the grant in the ability to set a standing session grant."
created: 2026-08-25T10:40:00Z
updated: 2026-08-25T10:40:00Z
---

# Debug: operator walk write-path defects (F3, F1, F2)

## Symptoms

Operator walk 2026-08-25 in Claude Desktop, plugin 0.17.0, against n8n workflow
`LV Enrichment (Cloud template)` (`950HPb7a1GgSAIyZ`). Operator said "Update John
Tsatsimas from Football NSW", answered a plain "yes" (VOCAB-05 **passed** — no phrase
demanded), the send dispatched (execution `11948`), the client reported "Sent. Backend
accepted 1 chunk, 1 row. No failures, nothing to re-send" — and HubSpot contact
`347569451461` was **not updated**.

## Root causes — ALREADY ESTABLISHED, do not re-investigate

All three verified live by reading n8n executions and the deployed workflow via the API.
Evidence quoted below is from actual API reads, not inference.

### F3 — client reports success over a received failure (fix FIRST, client-only)

The synchronous webhook response body of execution `11948` — which the client held in
hand — said:

```json
{"action": "write_blocked", "hs_object_id": null,
 "match": {"tier": "none", "auto": false, "reason": "searched, no hit"}}
```

The client suppressed both facts and reported "No failures, nothing to re-send".
Why: `skills/enrich-records/SKILL.md` step 8 ("Report what was sent, and no more than
that") tells the model this lane reports at chunk granularity and must not claim
per-record outcomes. That rule was written to stop the client INVENTING outcomes; here it
suppressed a RECEIVED one. `scripts/report_enrichment.py` already maps `write_blocked` →
"blocked" (line ~39) — the machinery exists and is not reached on the synchronous path.

Fix direction: step 8 (and the equivalent reporting steps in `contact-upload` and
`enrich-before-ingest` if they share the defect) must relay `action` values present in
the synchronous body — `write_blocked`, and a no-hit `match.reason` — as what they are.
"Do not claim per-record outcomes" must be narrowed to "do not INVENT what the body does
not carry". Contract-test the skill wording (the existing SKILL contract test files are
the pattern; pins rewritten in place with reason, never deleted).

### F1 — name lane cannot find contacts this system itself creates (backend, n8n)

Deployed `HubSpot Name Search` node (workflow `950HPb7a1GgSAIyZ`) filters:

```
lastname EQ <lastName>  AND  company CONTAINS_TOKEN <companyName>
```

against the contact's `company` TEXT PROPERTY. Contacts created by the ingest lane are
associated to a company object and leave `company` (text) null. Live proof: contact
`347569451461` has `company: null` while associated to Football NSW; the search returned
`total: 0` (execution `11948`, node output read via API). Secondary suspect: multi-word
`CONTAINS_TOKEN` values.

Fix direction (user-approved): make the name lane resilient — e.g. when the
lastname+company search returns 0, fall back to a lastname-only (or firstname+lastname)
search and route multiple hits through the EXISTING match-proposal machinery
(`n8n/code/matchProposal.js`, `Adapt Name Search`) as candidates/ambiguity, never an
auto-match on a weaker key. Exact design is the fixer's call; the constraint is that a
weaker search key must not silently auto-match.

**HARD CONSTRAINTS:** the workflow JSON is BUILT by `scripts/build_cloud_workflows.py` —
NEVER hand-edit `n8n/wf_enrichment_cloud.json`. Change the builder (and any
`n8n/code/*.js` module it inlines), rebuild, diff, deploy via the existing python-driver
deploy path (disarmed deploys are permitted from this environment; ARMING writes is the
blocked line — see memory `n8n-deploy-permission-blocked`). After any PUT, bounce the
workflow (deactivate/reactivate) — a bare PUT never reloads a running workflow (memory
`n8n-stored-vs-running-content`). Node tests: `node --test tests/n8n/*.test.mjs` (glob
form; dir form broken on node 24).

### F2 — no interactive ungranted send can ever write (design decision TAKEN)

The deployed `Decide Action` node carries compiled-in:

```js
const ALLOW_HUBSPOT_RECORD_WRITES = "false";
const TEST_RECORD_IDS = "";
```

so every send returns `action: "write_blocked"` unless an armed window flips those
constants. Only the GRANT path calls `n8n_arming.armed_window`; the ungranted path's
`armed=True` authorizes the client POST only. Proof: executions `11934/11935/11937`
matched contact `347569451461` correctly by id and still returned `write_blocked`. This
is G-2 (client UAT gap): every write to date was landed by an admin from a terminal.

**Operator's decision (this session, verbatim in trigger):** allow ungranted send —
the per-send "yes" (VOCAB-05 consent, already implemented at plugin 0.17.0) opens a
PER-SEND armed window scoped to that send's records, using the SAME machinery the grant
path uses (`n8n_arming.armed_window` with the send's record ids/domains) — and the
standing session grant REMAINS as the wrap-around option that removes the per-send ask.
So: consent hierarchy = per-send yes → one armed window for that send; session grant →
standing authority, no per-send ask (D-53-06 unchanged).

Consequences the fix must handle:
- `n8n_arming.arm_for_dispatch` currently REFUSES with no grant and no `ALLOW_N8N_ARM`
  env var. Tests pinning that:
  `operator-claude-plugin/tests/test_write_grant.py::test_with_no_grant_and_no_environment_variable_the_arm_refuses_at_zero_http_cost`
  and `::test_the_no_grant_refusal_names_both_routes`. These pins are REWRITTEN IN PLACE
  with the reason recorded (the project's established discipline), never deleted.
- Admin gating: the per-send window should be gated on the same
  `allow_write_grants: true` settings key (`config_gate.WRITE_GRANT_SETTINGS_KEY`) — the
  admin enables interactive writes once; the operator's attached yes authorizes each
  send. No new env var, no new key unless a test forces one.
- Record scoping: the window's allowlist is THIS send's records, never wider — same
  narrowing rule the grant path already documents in every lane SKILL.
- Guardrails A/B (dirty-backend refusal, failed-disarm loud report) apply to the
  per-send window exactly as they do under a grant — they live in `n8n_arming`/
  `write_grant` already.
- Headless/cron paths keep `ALLOW_N8N_ARM` as their authority (D-1.1-01) — untouched.
  `scripts/scheduled_arm.py` and `tests/test_scheduled_arm.py` remain byte-identical.
- SKILL wording: the four lane skills currently say the ungranted path dispatches
  without arming the backend implicitly; after F2 the per-send yes arms a window.
  Update the lane skills' dispatch blocks (the granted/ungranted split collapses into
  "yes → window for this send; grant → skip the ask") and rewrite affected contract-test
  pins in place with reasons.

## Fix order (user-directed)

1. **F3** — client reporting (small, client-only, no backend)
2. **F1** — name-lane fallback (builder change + rebuild + disarmed deploy + bounce)
3. **F2** — per-send armed window for ungranted sends (client scripts + skills + pins)

## Project invariants — check after EVERY fix

```
.venv/bin/python -m pytest -q            # from repo root; was 3084 passed / 154 skipped
node --test tests/n8n/*.test.mjs         # was 711 passed
```

- `operator-claude-plugin/scripts/scheduled_arm.py` + its test: byte-identical.
- Plugin release procedure: bump `.claude-plugin/plugin.json` version + CHANGELOG entry
  in the SAME commit (current version 0.17.0; F3 alone is a patch bump, F2 lands a minor
  bump). Marketplace clone refresh + Desktop Update are the operator's steps — say so,
  do not attempt them.
- `.env` unreadable in this environment. n8n API access: durable config at
  `~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json`
  (NOT the repo's stale `operator-claude-plugin/config/operator.local.json`), key
  `n8n_api_key`, header `X-N8N-API-KEY`, base `https://alexherman.app.n8n.cloud`.
  `executions_client.py`'s own transport fails from this session; plain urllib works.
- Commit style: conventional prefixes, reasons in body, one concern per commit.

## Evidence

- timestamp: 2026-08-25T10:05 — execution 11948 (the walk send): name-lane path, Parse
  event shows firstname/lastname/company from request; HubSpot Name Search total:0;
  Decide Action action:write_blocked, hs_object_id:null, match.reason "searched, no hit";
  enriched properties present in body (jobtitle CEO, mobile, persona) — derived, unwritten.
- timestamp: 2026-08-25T02:05 — execution 11937 (earlier id-lane send): object_id
  347569451461, lane fetch_by_id, match tier high "matched by fetch_by_id", action STILL
  write_blocked — proves F2 independent of F1.
- timestamp: 2026-08-25 — deployed Decide Action node source read via API: compiled
  ALLOW_HUBSPOT_RECORD_WRITES="false", TEST_RECORD_IDS="" — the gate F2 must open per send.
- timestamp: 2026-08-25 — HubSpot Fetch By Id output in 11937: contact 347569451461 has
  company:null, jobtitle:null, email:null, lastmodified 2026-08-25T00:39 — record truly
  unwritten, and the company TEXT property truly blank (F1's mechanism).
- timestamp: 2026-08-25 — client transcript: "Sent. Backend accepted 1 chunk, 1 row. No
  failures, nothing to re-send" — over a body carrying write_blocked (F3's mechanism).
- timestamp: 2026-08-25T11:00 — F3 RESOLVED. Confirmed via advisor: "Respond to Webhook"
  uses `respondWith: allIncomingItems`, so the real sync body is a JSON ARRAY of per-row
  objects (the debug evidence quote above showed one element unwrapped). Added
  `report_enrichment.build_sync_report(body)` reusing `_ACTION_TO_OUTCOME`/
  `_OUTCOME_REASON`/`_build_row_report` (extended with `match_level`/`match_reason` —
  named to avoid the literal substring "tier", which `test_built_report_object_carries_
  no_icp_trace_anywhere` and the skill-wide ICP/tier ban scan for in every serialized
  key). Rewrote `enrich-records/SKILL.md` step 8 to call it per `outcome.responses` entry
  and relay outcome/reason/match_level/match_reason honestly; narrowed (never silently
  kept) the old blanket "do not claim per-record outcomes" rule to "never invent what the
  body does not carry; always relay what it does". Rewrote the one affected contract-test
  pin (`test_the_skill_refuses_to_claim_per_record_outcomes` ->
  `test_the_skill_relays_what_the_sync_body_says_never_inventing_beyond_it`) in place with
  a RECORDED EDIT docstring. `contact-upload`/`enrich-before-ingest` read and confirmed to
  NOT share the defect (no equivalent suppression clause) — F3 is enrich-records-only.
  Suite: 3094 passed/154 skipped (+10 new tests), node 711/711 unchanged. Plugin bumped
  0.17.0 -> 0.17.1, CHANGELOG entry same commit.

## Eliminated

- hypothesis: network/dispatch failure — eliminated: execution 11948 exists with status
  success; the POST landed.
- hypothesis: VOCAB-05 consent failed to arm the POST — eliminated: dispatch happened;
  the defect is downstream of consent.
- hypothesis: enrichment itself failed — eliminated: providers returned; jobtitle/phone/
  persona all present in the response body. Derivation works; the write and the match are
  what fail.

## Current Focus

hypothesis: "Root causes established for all three defects; work is fixes, not investigation."
test: "After F3: a synchronous body carrying write_blocked/no-hit is relayed as blocked/no-match, pinned by contract test. After F1: rebuilt workflow searches fall back on 0 hits and route multi-hits as candidates, node tests pass. After F2: an ungranted send under allow_write_grants:true opens a record-scoped armed window and the walk send writes contact 347569451461."
expecting: "All existing suites stay green except pins rewritten in place with recorded reasons."
next_action: "F3 DONE (not yet committed). Fix F1 next: builder change in scripts/build_cloud_workflows.py — add 'HubSpot Name Search Fallback' (_hs_http_search_node, lastname EQ only, filter value read by node name $('Build Identity').item.json.identity_keys.lastName per the bd682a2 idiom, NEVER $json since its input is the primary search's own response) wired SEQUENTIALLY after 'HubSpot Name Search' (not a parallel fan-out — $() on an unexecuted node throws) and before 'Adapt Name Search'; extend matchProposal.js's mediumCandidates(hits, identityKeys, opts) with an optional requireCompanyToken (default true, byte-stable for existing 2-arg callers) plus a firstname-equality filter on the fallback path when identityKeys.firstName is present (bounds candidate count on a common surname); Adapt Name Search tries primary candidates first, falls back to the weaker search's candidates only when primary is empty, tier stays medium/auto:false either way (never auto-match on the weaker key). Register 'HubSpot Name Search Fallback' in scripts/deploy_n8n_workflows.py NODE_CREDENTIAL_MAP (LV HubSpot / hubspotAppToken) or test_every_hubspot_node_in_the_enrichment_workflow_is_registered_and_bound_to_lv_hubspot goes red. Rebuild via build_cloud_workflows.py, diff against committed n8n/wf_enrichment_cloud.json, run node --test tests/n8n/*.test.mjs (glob form), then deploy via the existing python-driver DISARMED path + bounce (deactivate/reactivate — a bare PUT never reloads). Free live verification: re-POST the John Tsatsimas people spec (writes still off) and confirm match.tier medium with candidate 347569451461, action needs_match_review instead of write_blocked/'searched, no hit'.">

