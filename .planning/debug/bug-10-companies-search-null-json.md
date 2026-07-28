---
status: awaiting_human_verify
trigger: |
  DATA_START
  Debug and FIX BUG 10 in /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc.
  Branch: feat/company-enrichment-icp-research — stay on it, do NOT create or switch branches.

  Read this first: .planning/phases/16.6-companies-search-transport-fix/16.6-CONTEXT.md — the
  full brief: verified ground truth, the enumerated 6-node blast radius, the leading fix, the
  constraints, and the scope fence. Also .planning/phases/16.5-research-escalation-enablement/
  16.5-03-SUMMARY.md for the original live trace. Verify cited facts against the code before
  depending on them, but do NOT re-probe the live n8n workflow or re-fire webhooks — the ground
  truth below was established live this session and the deployment is currently in a deliberate
  disarmed state that must not be disturbed by investigation.

  The bug (established live, 2026-07-28): n8n's HubSpot node with resource: company,
  operation: search emits ONE item whose json is null, while the byte-identical request — same
  hs_object_id EQ filter, same 14-property list read straight out of the built node — succeeds
  against POST /crm/v3/objects/companies/search with HTTP 200, total:1 and the real record. The
  node does NOT throw: with onError cleared and the run re-fired, the execution still reported
  status: success, no failing node, no message. Its input was correct
  (object_id: '9604614548'). The resource: contact twin, structurally identical, works.

  Cascade: Adapt Company Fetch By Id -> "error: unrecognized response shape" + lookup_failed:
  true -> Company Gate overrides create to skip (the fail-closed guard working correctly) ->
  Normalize + Score Company filters on action !== "skip" -> 0 rows -> the entire companies
  research/judge lane never executes.

  Blast radius — SIX nodes, already enumerated (re-verify the list):
  wf_enrichment_cloud.json: HubSpot Company Search, HubSpot Company Fetch By Id.
  wf_scheduled_maintenance_cloud.json: SJ-1 Search (input-gap scan), SJ-2 Search (stale
  refresh), SJ-3 Search (requested poller), Review Search (approved=true).
  None has ever run live. Every contact:search node is unaffected and demonstrably works live.

  Leading fix (confirm or refute against the code): Replace the company search nodes with
  credential-bound n8n-nodes-base.httpRequest POSTs to
  https://api.hubapi.com/crm/v3/objects/companies/search. n8n/code/adaptFetchById.js already
  parses the CRM v3 search-envelope response (unit-tested for both search-envelope and
  single-object forms), so the adapters may need no change.

  Hard requirements:
  - Contacts untouched. Prove by diff that every contact:search node's type and parameters are
    byte-identical to HEAD. Contacts is the one live-proven path; regressing it would be
    strictly worse than the bug.
  - Credential-bound, registered, fail-closed. The new node must use a credential (never
    $env/$vars, never a token in a Code node), must be added to NODE_CREDENTIAL_MAP in
    scripts/deploy_n8n_workflows.py so bind_credentials() fails closed if unmapped, and must
    satisfy _node_requires_credential() rather than evade it.
    tests/test_architecture_guard.py::test_no_env_or_vars_in_cloud_workflows must stay green.
  - properties must be a LIST, not a CSV string — HubSpot rejects a string with a 400
    VALIDATION_ERROR (fixed earlier today). tests/test_hubspot_node_auth.py currently guards
    this for n8n-nodes-base.hubspot nodes only; if the transport changes node type, check
    whether that guard still covers it or must be widened. A guard that silently stops applying
    is worse than no guard.
  - Red-before-green. Add a failing test reproducing the defect at whatever level it is
    reproducible offline (node shape / emitted request / adapter contract), capture the actual
    failure, THEN fix. If the defect is genuinely only observable live, say so plainly and build
    the strongest offline guard you can instead — but do not claim red-before-green you did not
    achieve.
  - Answer explicitly: do company:create and company:update share the defect? Both have also
    never run live, and the very next piece of work is a write-path canary that exercises
    exactly those two nodes. If you leave them unfixed, say so plainly rather than implying the
    companies path is fully working.
  - If any of the 7 node bodies pinned by tests/test_companies_factory_frozen.py would change,
    STOP and report — do not re-baseline.

  Scope fence: No change to contact:search, write-safety flags, cost caps, provider fan-out,
  ICP scoring, merge/promotion policy, or the research/judge JS. No enabling of HubSpot writes.
  No activation of any workflow. No live webhook fires. No deploy — leave deployment exactly as
  found (LV Enrichment active, research/escalation disarmed).

  Environment: Tests via .venv/bin/python -m pytest -q and node --test tests/n8n/*.test.mjs
  (glob form — directory form broken on node 24; system python lacks deps). Baseline to
  protect: 459 pytest / 275 node, zero regressions. (tests/n8n/mergeContacts.test.mjs has a
  known pre-existing millisecond-boundary flake — re-run to confirm, never "fix" it.) Editing
  scripts/build_cloud_workflows.py or n8n/code/*.js regenerates n8n/wf_*.json — rebuild
  deterministically (twice -> no diff) and commit the regenerated JSON. Do NOT use
  gsd-tools query state.advance-plan / state.update-progress — known miscounting bug here.
  Hand-edit STATE.md.

  Atomic commits: red (if achievable), then fix. Return the standard debug completion report.
  DATA_END
created: 2026-07-28T00:00:00Z
updated: 2026-07-28T01:00:00Z
---

## Current Focus

reasoning_checkpoint:
  hypothesis: "UPDATED (mechanistically confirmed, not just black-box): our own
    _hs_search_node() build-script helper (scripts/build_cloud_workflows.py) sets
    `operation: 'search'` unconditionally for BOTH resource:contact and resource:company.
    n8n's n8n-nodes-base.hubspot node (typeVersion 2.1) implements a real `operation:
    'search'` for resource:contact (POSTs /crm/v3/objects/contacts/search, unwraps
    responseData.results) but has NO 'search' operation at all for resource:company — its
    schema (CompanyDescription.ts) only offers create/delete/get/getAll/
    getRecentlyCreatedUpdated/searchByDomain/update; 'searchByDomain' is a DIFFERENT,
    domain-path-only v2-API operation, not a drop-in. execute()'s resource:company branch is
    a flat if-chain with no case for 'search' and no default/throw for an unmatched
    operation, so responseData stays undefined -> serializes to null once the execution item
    round-trips through JSON -> status:success, no error node, exactly the live symptom.
    Confirmed by direct read of a fetched copy of n8n's actual node source (HubspotV2.node.ts
    /CompanyDescription.ts, typeVersion [2,2.1,2.2] matching our pin) already present in this
    session's scratchpad. Fix: replace the 6 affected company-search nodes with
    credential-bound n8n-nodes-base.httpRequest POSTs to /crm/v3/objects/companies/search
    using authentication:predefinedCredentialType, nodeCredentialType:hubspotAppToken (reuses
    the SAME provisioned 'LV HubSpot' credential — no new credential object, no $env/$vars),
    bypassing the native node's operation-dispatch entirely. adaptFetchById.js /
    ENRICH_ADAPT_CO_SEARCH already parse the search-envelope shape this returns, so the
    adapters need zero changes."
  confirming_evidence:
    - "16.6-CONTEXT.md / 16.5-03-SUMMARY.md: live trace on n8n Cloud execution 10, company
      9604614548 — HubSpot Company Fetch By Id emitted [{json:null}], status:success, no error
      node; the identical request replayed directly against POST /crm/v3/objects/companies/
      search returned HTTP 200 total:1 with the real record; resource:contact twin worked."
    - "scripts/deploy_n8n_workflows.py:186,193-197 — _node_requires_credential() and
      _CREDENTIAL_BEARING_HTTP_AUTH_MODES already treat authentication:predefinedCredentialType
      on an httpRequest node as credential-bearing, and bind_credentials() writes
      node['credentials'] = {cred_type: {id,name}} keyed by cred_type alone (node-type-
      agnostic) — so the EXISTING NODE_CREDENTIAL_MAP entries (unchanged node names, unchanged
      {cred_type:'hubspotAppToken', cred_name:'LV HubSpot'}) bind the new httpRequest nodes
      correctly with zero changes to deploy_n8n_workflows.py."
    - "scripts/provision_n8n_credentials.py:84-91 — the 'LV HubSpot' credential is type
      hubspotAppToken storing {appToken: <token>}; n8n's predefinedCredentialType feature lets
      a generic httpRequest node authenticate AS that credential type directly (the same
      mechanism the native hubspot node itself uses internally) — confirming the replacement
      transport can reuse the identical credential object, never a token literal."
    - "n8n/code/adaptFetchById.js:44-61 and ENRICH_ADAPT_CO_SEARCH (build_cloud_workflows.py
      ~1514) both already branch on Array.isArray(res.results) — the CRM v3 search-envelope
      shape httpRequest returns verbatim — before falling back to res.properties/res.id. Zero
      adapter changes needed."
    - "build_enrichment_local_live()'s company search (build_cloud_workflows.py ~2560-2565)
      ALREADY uses this exact httpRequest-to-/companies/search pattern (via _live_http +
      HS_CO_SEARCH_BODY_EXPR) instead of the native node — i.e. the raw-HTTP transport for
      this exact endpoint is a pre-existing, already-proven pattern in this codebase, only
      never ported to the Cloud (credential-bound) builder for companies."
  falsification_test: "Grepped every _hs_search_node(...) call site in
    scripts/build_cloud_workflows.py and confirmed against n8n/wf_enrichment_cloud.json /
    wf_scheduled_maintenance_cloud.json (json.load, not re-derived from memory): exactly 6
    nodes carry {type: n8n-nodes-base.hubspot, resource: company, operation: search} — HubSpot
    Company Search, HubSpot Company Fetch By Id, SJ-1/SJ-2/SJ-3 Search, Review Search — matching
    16.6-CONTEXT.md's enumerated blast radius exactly, no more no less. Dedupe Search (candidate
    contacts) is resource:contact via the same helper and is NOT in the blast radius. Wrote
    tests/test_bug10_company_search_transport.py asserting each of the 6 is NOT the
    {hubspot, company, search} shape — ran RED against the pre-fix committed JSON: 24 failed /
    6 passed (the 6 passes are the vacuity guard + the create/update-untouched pin + the
    contacts-byte-identical-to-HEAD diff, all trivially true before any change is made).
    This IS the offline-reproducible level per 16.6-CONTEXT.md ('node shape / emitted
    request') — the null-json symptom itself is live-only and this session does not re-probe
    it, per the hard constraint against re-firing the disarmed deployment."
  blind_spots: "This session must NOT re-fire the live workflow or hit the real HubSpot API to
    re-confirm the null-json symptom — ground truth is pre-established and re-probing risks
    disturbing a deliberately disarmed deployment. All verification is offline (unit tests,
    node/workflow JSON diffs, adapter contract tests, rebuild-determinism). Consequence: the
    FIX itself cannot be live-verified in this session — the write-path canary phase (deferred)
    is the first opportunity to actually fire the companies branch live end-to-end. Also
    unverified: whether n8n's search-envelope httpRequest response omits any field the native
    node would have added (e.g. archived/createdAt/updatedAt) that some downstream code might
    implicitly rely on — checked ENRICH_ADAPT_CO_SEARCH/adaptFetchById.js and neither reads
    those fields, so this is a checked-not-just-assumed blind spot, not an open one."
  candidate_causes:
    - "code (ours): _hs_search_node() in scripts/build_cloud_workflows.py assigns `operation:
      'search'` to BOTH resource:contact and resource:company call sites without checking
      whether 'search' is a valid operation value for the target resource. It is valid for
      contact (and deal); it is NOT valid for company (only 'searchByDomain' exists, a
      different domain-path v2 operation). CONFIRMED as a necessary factor by direct read of
      CompanyDescription.ts's companyOperations option list, which has no 'search' entry."
    - "environment (n8n's third-party node code, vendored copy read from a previously-fetched
      source already present in this session's scratchpad — HubspotV2.node.ts, typeVersion
      [2,2.1,2.2] matching our pin): execute()'s resource:company branch has no default/throw
      for an unrecognized `operation` value (unlike a well-behaved switch-default) — it
      silently leaves `responseData` (declared `let responseData;`, undefined) unassigned,
      which is then handed to returnJsonArray/constructExecutionMetaData with no exception
      anywhere in the path. CONFIRMED as a necessary factor by reading the full
      resource==='company' if-chain (1734-2310) and finding zero fallback/validation."
  and_gate: "Yes — genuinely two factors, in two different categories, both necessary. Factor
    A alone (our code passing an invalid operation value) would, against a node that validates
    or throws on an unrecognized operation, fail LOUDLY (activation error or an explicit
    'Unknown operation' exception) — not silently. Factor B alone (n8n's permissive, non-
    validating fallthrough) is inert unless something actually supplies an invalid operation
    value — it does no harm to any node that only ever sets valid operations (which is every
    OTHER node in this codebase). Only the conjunction — our invalid value fed into a node
    that doesn't validate it — produces the exact observed symptom (no throw, status:success,
    json:null). Recorded as `root_cause` below as a ';'-joined pair per the AND-gate
    convention. Also checked and rejected: a bad-property-name-causing-a-silent-400
    hypothesis — ruled out because the live manual replay with the SAME property list against
    the real API returned 200/total:1, so HubSpot's own API was never rejecting anything;
    the failure is entirely upstream of the HTTP call, inside the node's own operation
    dispatch, exactly as the mechanism above shows."
  fix_rationale: "Routes around the n8n-platform defect entirely by never invoking the
    implicated node code path for company search, while reusing 100% of the existing
    credential, adapter, and downstream-gate machinery — the smallest change that eliminates
    the null-json symptom's mechanism (the native node's resource:company/search handling)
    rather than attempting to catch/retry/patch its output after the fact."
next_action: "Fix implemented, guardrail accepted (504 pytest / 275 node, zero regressions;
  deterministic rebuild confirmed twice; revert-and-reconfirm proved the fix is what fixes
  it). RED commit made. Commit the fix (source + regenerated JSON + widened tests). Return
  a human-verify CHECKPOINT — genuine live confirmation is out of scope for this session
  (re-firing forbidden) and deferred to the write-path canary phase; ask the user to accept
  the offline evidence now and treat the write-path canary as the live confirmation point,
  OR hold this session open until that canary runs. Do NOT move the debug file to
  resolved/ until the user responds."

## Symptoms

expected: |
  n8n's company:search HubSpot-node operation (or its replacement transport) returns the real
  CRM v3 search response (`{results: [...], total: N}` or equivalent), which
  n8n/code/adaptFetchById.js can parse into a usable existingRecord, so Company Gate can decide
  create/update correctly instead of always falling back to lookup_failed -> skip.
actual: |
  The node emits one item whose `json` is `null`. It does not throw or report an error node;
  execution status is `success`. Downstream: Adapt Company Fetch By Id reports
  fetch_diagnostic: "error: unrecognized response shape", lookup_failed: true; Company Gate
  overrides create -> skip; Normalize + Score Company filters to 0 rows; the entire companies
  research/judge lane never executes.
errors: |
  No thrown error, no error-node output, no message anywhere in the execution trace. The only
  observable symptom is the null `json` on the HubSpot Company Fetch By Id node's output item,
  and the derived string "error: unrecognized response shape" written by our own adapter code
  (n8n/code/adaptFetchById.js) when it cannot make sense of what it received.
reproduction: |
  Established live only, on n8n Cloud, execution 10 of wf_enrichment_cloud, company
  9604614548 (Melbourne Racing Club, mrc.racing.com). Do NOT re-fire live this session. Offline
  reproduction, if any, must come from constructing/parsing the node JSON and adapter contract
  directly (see 16.6-CONTEXT.md's canonical references).
started: 2026-07-28, during the Phase 16.5 companies canary (16.5-03-SUMMARY.md), which is
  blocked on this bug.

## Eliminated

- hypothesis: "The bug is in OUR request construction (bad property name, bad filter shape)
    for the companies search, not in n8n's node itself."
  evidence: "16.6-CONTEXT.md ground truth: the exact same filter + 14-property list, replayed
    directly against POST /crm/v3/objects/companies/search, returned HTTP 200 total:1 with the
    real record. If our construction were wrong, the direct replay would have failed too."
  timestamp: 2026-07-28T00:05:00Z

## Evidence

- timestamp: 2026-07-28T00:10:00Z
  checked: scripts/build_cloud_workflows.py — every `_hs_search_node(` call site
    (grep, then read each call site in full).
  found: Exactly 6 call sites pass resource="company" — hs_co_search (inline dict, not via
    the helper, ~line 3586), hs_co_fetch_by_id (~3621), sj3_search (~4223), sj1_search
    (~4247), sj2_search (~4278), review_search (~4350). One more call site
    (dedupe_search, ~4323) passes resource="contact" and is NOT in the blast radius.
  implication: Confirms 16.6-CONTEXT.md's enumerated 6-node blast radius exactly against the
    actual source, not by re-derivation from memory.

- timestamp: 2026-07-28T00:15:00Z
  checked: n8n/code/adaptFetchById.js (full read) and ENRICH_ADAPT_CO_SEARCH
    (build_cloud_workflows.py ~1514-1537).
  found: Both already branch `Array.isArray(res.results)` (search envelope) before
    `res.properties` (single object) before `res.id` (bare object) — the exact shape
    `POST /crm/v3/objects/companies/search` returns. Neither reads any field an httpRequest
    response would omit relative to the native node's output.
  implication: Confirms 16.6-CONTEXT.md's premise — the httpRequest replacement needs ZERO
    adapter changes.

- timestamp: 2026-07-28T00:20:00Z
  checked: scripts/deploy_n8n_workflows.py — _node_requires_credential(),
    _CREDENTIAL_BEARING_HTTP_AUTH_MODES, bind_credentials(), NODE_CREDENTIAL_MAP.
  found: _CREDENTIAL_BEARING_HTTP_AUTH_MODES already includes "predefinedCredentialType".
    bind_credentials() writes `node["credentials"] = {mapping["cred_type"]: {id, name}}`
    keyed only by cred_type, never by node type. All 6 target node NAMES are already present
    in NODE_CREDENTIAL_MAP mapped to {cred_type: "hubspotAppToken", cred_name: "LV HubSpot"}.
  implication: An httpRequest replacement using authentication=predefinedCredentialType +
    nodeCredentialType=hubspotAppToken, with node NAMES kept unchanged, requires ZERO changes
    to deploy_n8n_workflows.py — it satisfies _node_requires_credential() and binds correctly
    via the existing map entries.

- timestamp: 2026-07-28T00:25:00Z
  checked: scripts/provision_n8n_credentials.py _hubspot_data() / CREDENTIAL_MANIFEST.
  found: "LV HubSpot" credential type is "hubspotAppToken", data {appToken: <token>} — the
    same credential TYPE n8n's native HubSpot node itself uses. n8n's httpRequest
    predefinedCredentialType feature lets a generic HTTP node authenticate as any existing
    app credential type, including hubspotAppToken — same mechanism, same credential object.
  implication: No new credential object needs provisioning; the replacement reuses "LV
    HubSpot" verbatim.

- timestamp: 2026-07-28T00:30:00Z
  checked: build_enrichment_local_live()'s existing "HubSpot Company Search" node
    (build_cloud_workflows.py ~2560-2565, HS_CO_SEARCH_BODY_EXPR ~1501-1510).
  found: The LOCAL-LIVE builder's companies search ALREADY uses httpRequest (_live_http) to
    POST https://api.hubapi.com/crm/v3/objects/companies/search — this transport pattern for
    this exact endpoint is pre-existing and already proven in this codebase, just never
    ported to the Cloud (credential-bound) builder or the fetch-by-id/scheduled nodes. NOTE:
    HS_CO_SEARCH_BODY_EXPR's property list (16 props, includes lv_icp_tier/lv_icp_fit_score/
    lv_anti_icp_flag, omits hs_object_id) differs from ENRICH_COMPANY_SEARCH_PROPERTIES_CSV
    (14 props, includes hs_object_id, omits the 3 ICP output fields) — the two are NOT the
    same constant, so HS_CO_SEARCH_BODY_EXPR must NOT be reused verbatim for the Cloud fix
    (would silently change which properties are requested and violate
    test_company_fetch_by_id_properties_are_identical_to_the_company_search_properties'
    pinning of ENRICH_COMPANY_SEARCH_PROPERTIES_CSV for both Cloud nodes).
  implication: Cloud fix needs its OWN generic body-expression builder parameterized by the
    same (filter_groups, properties_csv) shape _hs_search_node already takes, not a reuse of
    HS_CO_SEARCH_BODY_EXPR.

- timestamp: 2026-07-28T00:35:00Z
  checked: tests/test_companies_factory_frozen.py (FROZEN_NODE_NAMES) vs the nodes this fix
    touches.
  found: The 7 frozen node bodies (Research Trigger Gate, Build Research Request, Validate
    Research Output, Judge Gate, Build Judge Request, Apply Judge Verdict, Merge Company) are
    entirely downstream of the search/fetch/adapt nodes this fix changes. None overlaps.
  implication: No STOP-and-report condition triggered — safe to proceed without touching the
    frozen fixture.

- timestamp: 2026-07-28T00:40:00Z
  checked: Every test file referencing the 6 target node names or `type ==
    "n8n-nodes-base.hubspot"` generically (grep across tests/*.py): test_hubspot_node_auth.py,
    test_fetch_by_id_topology.py, test_cloud_write_path.py, test_cloud_companies_branch.py,
    test_builder_flag_parity.py, test_deploy_credential_binding.py.
  found: Several existing guards are TYPE-FILTERED to "n8n-nodes-base.hubspot" and would
    either (a) go hard RED once the 6 nodes become httpRequest (test_cloud_write_path.py's
    filterGroupsUi reads, test_cloud_companies_branch.py's native-node assertion for "HubSpot
    Company Search", test_fetch_by_id_topology.py's per-branch native-shape assertions,
    test_builder_flag_parity.py's _all_credential_bound_node_names() helper which only
    recognizes genericCredentialType/native-hubspot, not predefinedCredentialType) or (b)
    silently stop covering them (test_hubspot_node_auth.py's CSV/list + apptoken-auth sweeps,
    test_fetch_by_id_topology.py's enrichment-workflow credential-registration sweep).
  implication: Both classes need fixing — (a) must be updated so the suite doesn't regress,
    (b) must be widened per the explicit hard requirement ("a guard that silently stops
    applying is worse than no guard"). Full list captured for the fix step.

- timestamp: 2026-07-28T00:45:00Z
  checked: Wrote tests/test_bug10_company_search_transport.py (node-shape-level red test per
    16.6-CONTEXT.md's sanctioned offline-reproducible level) and ran
    `.venv/bin/python -m pytest -q tests/test_bug10_company_search_transport.py`.
  found: 24 failed / 6 passed. Failures are exactly the 6 nodes x 4 assertion groups (not-
    implicated-shape, httpRequest+predefinedCredentialType shape, properties-as-real-array,
    filter-token parity) — all fail because the nodes are currently the native
    {hubspot, company, search} shape. The 6 passes are the vacuity guard, the create/update-
    unchanged pin, and the contacts-byte-identical-to-HEAD diff (trivially true pre-fix).
  implication: RED confirmed at the node-shape level — the offline ceiling 16.6-CONTEXT.md
    describes ("If the defect is genuinely only observable live, say so plainly and build the
    strongest offline guard you can instead"). The null-json symptom itself remains live-only
    and unreproduced offline by design (re-firing forbidden); this is the honest substitute.

- timestamp: 2026-07-28T00:50:00Z
  checked: The scratchpad already held a fetched copy of n8n's actual `n8n-nodes-base.hubspot`
    node source (HubspotV2.node.ts, CompanyDescription.ts, ContactDescription.ts,
    GenericFunctions.ts — typeVersion `[2, 2.1, 2.2]`, matching this repo's pinned 2.1
    exactly), left over from an earlier investigation in this same working session. Read
    CompanyDescription.ts's `companyOperations` option list and HubspotV2.node.ts's
    `execute()` for `resource === 'company'` (~line 1734-2310) and `resource === 'contact'`
    (~line 1118-1731) in full.
  found: THE MECHANISM, not just the black-box symptom. CompanyDescription.ts's
    `companyOperations` options are exactly {create, delete, get, getAll,
    getRecentlyCreatedUpdated, searchByDomain, update} — there is NO `"search"` value for
    `resource: company`; the UI's own "Search" option's VALUE is `"searchByDomain"` (a
    different, domain-path-based `/companies/v2/domains/{domain}/companies` v2-API operation
    with no filterGroups support at all). Contrast: `resource: contact`'s operations DO
    include a real `operation: "search"` (line 1672) that POSTs to
    `/crm/v3/objects/contacts/search` and sets `responseData = responseData.results`. In
    execute() (line 1051-1059), `let responseData;` is declared once per item, undefined by
    default. The `resource === 'company'` block (1734 onward) is a flat `if (operation ===
    'create') {...} if (operation === 'update') {...} ... if (operation === 'delete') {...}`
    chain with NO branch for `operation === 'search'` and NO default/else throw for an
    unrecognized operation anywhere in it. Our build script's `_hs_search_node()` sets
    `"operation": "search"` UNCONDITIONALLY for both resources (reusing the contact-valid
    value for company too, without checking company's actual operation schema) — so for
    every one of the 6 company nodes, NONE of the company block's conditionals match,
    `responseData` is never assigned, and the item is built from `this.helpers.
    returnJsonArray(responseData as IDataObject[])` with `responseData` still `undefined` —
    no exception anywhere in this path, `status: success`, and `undefined` serializes to
    `null` once the execution data round-trips through JSON for the API/execution-history
    layer — reproducing "one item, json: null, no throw, status: success" exactly.
  implication: ROOT CAUSE UPGRADED from "empirically-confirmed n8n-platform black box" to a
    fully mechanistic, TWO-FACTOR finding (RCA AND-gate fires — see reasoning_checkpoint
    below): (A) code, ours — `_hs_search_node()` assigns `operation: "search"`, a value that
    is simply invalid for `resource: company` in n8n's HubSpot node schema (the valid
    "search-like" value is `"searchByDomain"`, an incompatible different operation); (B)
    third-party/environment, n8n's node — the company resource's execute() branch has no
    validation or throw for an unrecognized `operation` value, silently leaving `responseData`
    unset instead of erroring loudly. Neither factor alone reproduces the silent-null symptom:
    A alone with a validating/throwing node would have failed loudly and obviously at
    activation or first run; B alone (permissive fallthrough) is inert unless an invalid
    operation is actually supplied. The planned fix (bypass the native node's operation
    dispatch entirely via a credential-bound httpRequest POST straight to the real
    `/crm/v3/objects/companies/search` endpoint) remains exactly correct — it sidesteps BOTH
    factors by never asking the node to resolve an `operation` value in the first place — but
    is now justified by a confirmed mechanism, not a differential-test-only black box.
    `searchByDomain` cannot serve as a drop-in replacement for 5 of the 6 nodes: it is
    domain-only (URL path param, not a filter), returns the OLD v2 shape, and supports no
    arbitrary property list or hs_object_id/custom-property filterGroups — SJ-1/SJ-2/SJ-3/
    Review Search filter on lv_* custom properties and HubSpot Company Fetch By Id filters on
    hs_object_id, none of which searchByDomain can express.

## Resolution

root_cause: |
  Two-factor (AND-gate): (A) code, ours — scripts/build_cloud_workflows.py's
  _hs_search_node() helper assigns `operation: "search"` unconditionally to both
  resource:contact and resource:company call sites, but n8n's n8n-nodes-base.hubspot node
  (typeVersion 2.1) has NO `operation: "search"` for resource:company (schema only offers
  create/delete/get/getAll/getRecentlyCreatedUpdated/searchByDomain/update; "searchByDomain"
  is a different, domain-path-only v2-API operation, not a drop-in); (B) environment,
  n8n's third-party node code — execute()'s resource:company branch has no default/throw
  for an unrecognized `operation` value, so `responseData` (undefined by default) is never
  assigned and is handed to returnJsonArray/constructExecutionMetaData with no exception,
  surfacing as one item with json:null and status:success once serialized. Both factors are
  necessary: a validating node would have failed loudly on (A) alone; (B) alone is inert
  without an invalid operation value. Confirmed by direct read of a fetched copy of n8n's
  actual node source (HubspotV2.node.ts / CompanyDescription.ts) matching this repo's pinned
  typeVersion, present in this session's scratchpad from an earlier investigation.
fix: |
  Replace the 6 affected company-search nodes (HubSpot Company Search, HubSpot Company
  Fetch By Id, SJ-1/SJ-2/SJ-3 Search, Review Search) with credential-bound
  n8n-nodes-base.httpRequest POSTs directly to https://api.hubapi.com/crm/v3/objects/
  companies/search, using authentication:predefinedCredentialType +
  nodeCredentialType:hubspotAppToken to reuse the SAME provisioned "LV HubSpot" credential
  (no new credential object, no $env/$vars). This bypasses the native node's operation
  dispatch entirely, sidestepping both root-cause factors. Node names, NODE_CREDENTIAL_MAP
  entries, and downstream adapters (adaptFetchById.js / ENRICH_ADAPT_CO_SEARCH) are
  unchanged — they already parse the CRM v3 search-envelope shape this transport returns.
  contact:search, company:create, and company:update are untouched.
verification: |
  target_test: { result: pass }  # tests/test_bug10_company_search_transport.py, 30/30
  mutation_check: { result: skipped, reason: "no Stryker/package.json in this repo — Python-
    primary; the .mjs tests run via node's built-in test runner, no npm/mutation tooling
    configured" }
  no_op_deletion: { result: pass, deletion_justified_by_rca: n/a }  # scripts/build_cloud_workflows.py
    diff is 94 insertions / 22 deletions — net-positive, substantial new logic (the JSON-body-
    expression renderer + new httpRequest node constructor), not a deletion/short-circuit
  adjacent_tests: { result: pass, suites_run: [".venv/bin/python -m pytest -q (full suite)",
    "node --test tests/n8n/*.test.mjs (full suite)"] }  # 504 pytest / 275 node, zero regressions
  revert_and_reconfirm: { result: pass, bug_returned_on_revert: true, fixed_on_reapply: true }
    # git stash of the fix (source + rebuilt JSON + updated tests) -> RED reconfirmed (24
    # failed/6 passed in tests/test_bug10_company_search_transport.py, identical to the
    # original red run); git stash pop -> GREEN (504 pytest / 275 node)
  guardrail_verdict: accepted
files_changed:
  - scripts/build_cloud_workflows.py (added _hs_search_json_body_expr, _hs_http_search_node,
    _http_node's auth="hubspot" option; swapped 6 company-search call sites)
  - n8n/wf_enrichment_cloud.json (regenerated — HubSpot Company Search, HubSpot Company
    Fetch By Id)
  - n8n/wf_scheduled_maintenance_cloud.json (regenerated — SJ-1/SJ-2/SJ-3 Search, Review
    Search)
  - tests/test_bug10_company_search_transport.py (new — the red/green regression guard)
  - tests/test_hubspot_node_auth.py (widened — httpRequest-transport equivalent of the
    apptoken-auth and CSV/list guards)
  - tests/test_fetch_by_id_topology.py (split contacts/companies assertions; widened the
    credential-registration sweep)
  - tests/test_cloud_write_path.py (split contacts/companies filter assertions)
  - tests/test_cloud_companies_branch.py (narrowed the native-node pin to Create/Update;
    added the httpRequest-shape assertion for Search)
  - tests/test_builder_flag_parity.py (widened _all_credential_bound_node_names to
    recognize predefinedCredentialType)
  - tests/test_deploy_credential_binding.py (widened the unmapped-node sweep to use
    deploy._node_requires_credential() instead of a type filter)
  - tests/n8n/sjPredicates.test.mjs (jsonBody-based filterGroups() extractor)
  - tests/n8n/reviewLoop.test.mjs (jsonBody-based Review Search assertion)
