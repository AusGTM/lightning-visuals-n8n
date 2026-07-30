---
status: resolved
trigger: |
  DATA_START
  Live n8n Cloud canary run today against portal 22617666 surfaced ONE bug with TWO halves
  in the Lusha v2 person contract. Root cause already empirically confirmed against the real
  Lusha API this session (do NOT re-probe live — successful calls charge credits; discovery
  already cost ~1 credit).

  HALF 1 — REQUEST is the wrong shape (scripts/build_cloud_workflows.py, "Lusha Enrich" node):
  Current: url=https://api.lusha.com/v2/person, jsonBody=JSON.stringify(identity_keys) — POSTs
  the bare identity_keys object {email, domain, linkedin_url, firstName, lastName, companyName}.
  Live result: 400 {"name":"BadRequest","message":"property email should not exist","code":400}

  Verified real contract:
  - Body must be {"contacts": [ {...} ]} — a contacts ARRAY, max 100 elements.
  - Each element REQUIRES contactId (arbitrary caller-chosen correlation key).
  - Accepted identity properties inside an element, ONLY these:
    - email — accepted alone
    - linkedinUrl — accepted alone (camelCase; our field is linkedin_url)
    - fullName — accepted but alone errors "must have a combination of 1. linkedin url 2. full
      name + company domain". Could NOT find accepted company-domain property name
      (companyDomain/companyName/domain all rejected). Do NOT chase this — treat fullName as
      unusable, map only email and linkedinUrl.
  - REJECTED inside an element (confirmed individually): firstName, lastName, companyName,
    companyDomain, domain, phoneNumber, jobTitle.

  Request builder must map identity_keys down to {contactId, email?, linkedinUrl?}, omitting
  any key whose value is null/empty. When NEITHER email nor linkedin_url is present, do not
  send the request at all (it can only 400) — follow the existing skip-not-retry convention
  (CLAUDE.md Sec 26.1, "404/no match -> continue waterfall"). Row must keep flowing to other
  providers either way.

  HALF 2 — RESPONSE unwrapping is wrong (n8n/code/normalizeProviders.js:134 lushaCandidates()):
  Current: const raw = (rawResponse && rawResponse.contact && rawResponse.contact.data) ||
  rawResponse || {};  — looks for a SINGULAR "contact".

  Live v2 response is a keyed MAP under plural "contacts", keyed by the contactId sent:
  {"contacts": {"1": {"error": null, "isCreditCharged": true, "data": {
     "firstName":"Brendan","lastName":"Carmody","fullName":"Brendan Carmody",
     "companyId":18775823,"emails":["brendan@lightningvisuals.com"],
     "emailAddresses":[{"email":"...","emailType":"work","updateDate":"2026-01-15",
     "emailConfidence":"A+"}], "phones":["+61 493 511 289"],"phoneNumbers":[{...}] }}}}

  The rest of lushaCandidates() (emailAddresses/phoneNumbers/jobTitle handling, doNotCall
  suppression, accuracy grading) already matches this inner "data" shape and must be left
  alone. Only the unwrap line needs to learn the new envelope. Must KEEP existing fallbacks
  working (flat fixture shape + singular contact.data form — offline fixtures/tests depend on
  it). Add the contacts-map form; do not remove existing forms without checking every caller
  and fixture.

  Must also explicitly handle: a per-contact "error" field (Lusha reports per-element failures
  inside a 200 response), and a contacts map whose entry has no "data". Neither may throw —
  provider-failure convention in this repo is skip-not-retry, never crash the row.

  NOT IN SCOPE: Apollo and ZoomInfo both worked correctly in the same live run — do not touch.
  Do not touch the companies Lusha path unless the same unwrap bug provably affects it — if it
  does, say so explicitly rather than silently widening scope.
  DATA_END
created: 2026-07-28T06:10:55Z
updated: 2026-07-28T06:10:55Z
---

## Current Focus

reasoning_checkpoint:
  hypothesis: "Root cause confirmed as given: (1) request builder emitted bare identity_keys instead of {contacts:[{contactId, email?, linkedinUrl?}]}; (2) response unwrap in lushaCandidates() looked for singular rawResponse.contact.data instead of the plural keyed-map rawResponse.contacts[<id>].data. Both fixed; both verified green against the exact red tests written first."
  confirming_evidence:
    - "RED: tests/n8n/lushaRequestContract.test.mjs (4/5 tests) failed pre-fix, evaluating the REAL committed 'Lusha Enrich' jsonBody expression via new Function and showing it emits the bare identity_keys shape (Object.keys == ['email','linkedin_url','firstName',...] not ['contacts'])."
    - "RED: tests/n8n/enrichment.test.mjs 'Lusha live v2 PLURAL contacts-map' test failed pre-fix against tests/fixtures/enrichment/lusha_live_person_v2.json (the real live envelope) -- email candidate undefined, confirming the unwrap never finds .contacts."
    - "GREEN: all 267 node tests + 416 pytest tests pass after the fix; rebuild is deterministic (byte-identical across two runs)."
  falsification_test: "N/A - root cause empirically pre-confirmed against live API this session per trigger; not re-probed live (credits). Confirmed via failing-then-passing offline tests using the exact live envelope as fixture."
  blind_spots: "Resolved -- see Resolution below for the explicit fixture/scope call-outs the trigger asked for."
next_action: "DONE -- awaiting human verification that the fix is correct (cannot re-probe Lusha live this session; verification steps below are the safe, no-credit-cost checks). Once confirmed, archive to resolved/ and append knowledge-base.md entry."

## Symptoms

expected: |
  Lusha Enrich node POSTs {"contacts":[{"contactId":"1","email":"...","linkedinUrl":"..."}]}
  (omitting whichever of email/linkedinUrl is absent, and skipping the send entirely when
  neither is present) and normalizeProviders.js's lushaCandidates() correctly unwraps the
  plural contacts-map envelope {"contacts":{"<contactId>":{"error":null,"data":{...}}}},
  tolerating a per-contact error field and a missing data key without throwing, while still
  supporting the existing flat-fixture and singular contact.data offline test shapes.
actual: |
  Request: bare identity_keys object POSTed directly as jsonBody -> live 400 "property email
  should not exist".
  Response unwrap: rawResponse.contact.data (singular) does not match the live plural
  rawResponse.contacts[<id>].data map -> real Lusha responses are not correctly unwrapped by
  lushaCandidates().
errors: |
  Live: 400 {"name":"BadRequest","message":"property email should not exist","code":400}
  (Half 1, request shape). Half 2 has no captured live exception yet -- unwrap silently fails
  to find contact data because of the singular/plural mismatch (needs a red test to pin down
  exact runtime behavior, e.g. empty candidates array vs thrown error).
reproduction: |
  OFFLINE ONLY in tests -- do not re-hit live Lusha API (charges credits; already confirmed).
  Add a fixture matching the exact live response JSON in the trigger block, feed it through
  n8n/code/normalizeProviders.js lushaCandidates(), and observe it fails to extract Brendan
  Carmody's data because of the contact/contacts singular/plural mismatch. For Half 1, a unit
  test on the request-builder logic (whatever function in build_cloud_workflows.py or its
  generated n8n Code node constructs the Lusha Enrich body) should show it currently emits the
  bare identity_keys shape instead of {contacts:[{contactId,...}]}.
started: Live n8n Cloud canary run today (2026-07-28) against portal 22617666, Milestone 3 (Company Enrichment & ICP Research), post Phase 16.4.

## Eliminated

## Evidence

- timestamp: 2026-07-28T06:20:00Z
  checked: scripts/build_cloud_workflows.py for every "Lusha Enrich"/"v2/person" site
  found: "build_enrichment_cloud() (~line 3372) builds the CLOUD 'Lusha Enrich' node with
    json_body=JSON.stringify($('Enrichment Gate').item.json.identity_keys) -- exact match
    to the trigger's Half 1 description and the node the live canary exercised.
    build_enrichment_local_live() (~line 2477/1346-1369, ENRICH_BUILD_REQUESTS) builds a
    SEPARATE, GET-querystring Lusha request (firstName/lastName/companyName/companyDomain
    in the querystring -- also contract-violating, but a different failure mode, a
    different code path, and NOT what the live Cloud canary ran) -- this is the
    'build_enrichment_local_live GET path' out-of-scope call-out."
  implication: Half 1's fix target is build_enrichment_cloud()'s Lusha Enrich node only.
- timestamp: 2026-07-28T06:22:00Z
  checked: n8n/code/normalizeProviders.js for every rawResponse.contact/.contacts use
  found: "Exactly ONE call site in the whole repo (grepped *.js/*.mjs/*.py):
    lushaCandidates() line 138. No other caller re-implements the unwrap."
  implication: Root-cause fix belongs in this one shared function; no other call site to patch.
- timestamp: 2026-07-28T06:24:00Z
  checked: existing Lusha fixtures/tests (tests/fixtures/enrichment/lusha_*.json, all
    toCandidates("lusha", ...) call sites in tests/n8n/*.test.mjs)
  found: "tests/fixtures/enrichment/lusha_live_person.json is loaded in enrichment.test.mjs
    with the comment '// real v2 person: nested under contact.data' -- this is the WRONG
    shape per the live-confirmed contract (singular contact.data was never actually
    observed live; real live is the plural contacts map). Companies path
    (tests/fixtures/enrichment/lusha_company.json + the company branch of
    lushaCandidates()) uses a DIFFERENT, already-correct `raw.company || raw.data || raw`
    unwrap matching the live-confirmed /v2/company {data:{...}} envelope -- unaffected by
    the person-endpoint bug, and separately already known-broken at the REQUEST layer
    (Track B: test_track_b_lusha_company_url_method_mismatch_is_flagged_in_builder_source,
    tests/test_provider_gate_topology.py:358)."
  implication: Existing mislabeled fixture called out per instructions (comment corrected,
    not deleted, since the singular-shape offline back-compat coverage must be kept).
    Companies path confirmed unaffected and untouched.
- timestamp: 2026-07-28T06:40:00Z
  checked: "node --test tests/n8n/lushaRequestContract.test.mjs + tests/n8n/enrichment.test.mjs (new tests only), BEFORE the fix"
  found: "RED as predicted -- 4/5 fail in lushaRequestContract.test.mjs (bare identity_keys
    shape, no contactId/contacts wrapper); 1/4 new enrichment.test.mjs assertions fail
    (email/mobile extraction from the plural envelope). The 3 error/missing-data/empty-map
    tolerance tests pass even pre-fix, since the OLD code never inspects `.contacts` at all
    and therefore never throws either -- expected, not a false negative."
  implication: Both halves' primary defects are proven red before any fix code is written.
- timestamp: 2026-07-28T07:05:00Z
  checked: "node --test tests/n8n/*.test.mjs and .venv/bin/python -m pytest -q, AFTER the fix"
  found: "267/267 node passing (258 baseline + 9 new), 416/416 pytest passing (unchanged --
    no Python-side change). Rebuild via scripts/build_cloud_workflows.py run twice, diffed
    byte-identical (deterministic)."
  implication: Fix verified, zero regressions against the 416/258 baseline.

## Resolution

root_cause: |
  Two independent contract mismatches against the real live Lusha v2/person API
  (confirmed live against portal 22617666, 2026-07-28), both in the AND-gate sense
  ("root_cause" holds a set: both had to be fixed for the integration to work end to end,
  neither alone was sufficient):
  1. REQUEST (scripts/build_cloud_workflows.py, build_enrichment_cloud()'s "Lusha Enrich"
     node): jsonBody posted the bare identity_keys object directly
     (JSON.stringify($('Enrichment Gate').item.json.identity_keys)) instead of the real
     contract's {"contacts":[{contactId, email?, linkedinUrl?}]} array-of-elements shape.
  2. RESPONSE (n8n/code/normalizeProviders.js lushaCandidates(), line 138): unwrapped a
     singular rawResponse.contact.data, but the real v2/person response is a plural,
     contactId-keyed map: {"contacts":{"<contactId>":{"error","data":{...}}}}.

fix: |
  1. Request: Lusha Enrich's jsonBody expression now maps identity_keys down to
     {contactId:"1", email?, linkedinUrl?}, omitting whichever of email/linkedin_url is
     absent (mapping linkedin_url -> linkedinUrl per the confirmed camelCase contract), and
     emits an empty contacts array when neither is present (never a malformed single-field
     element that can only 400) -- skip-not-retry, CLAUDE.md Sec 26.1. Still reads identity
     BY NODE NAME from 'Enrichment Gate' (preserves the pre-existing pinned
     test_contacts_provider_request_bodies_read_identity_by_node_name_not_bare_json check).
  2. Response: lushaCandidates() now checks rawResponse.contacts (plural, object) FIRST,
     takes the single entry's .data (this pipeline sends exactly one contactId per HTTP
     call, one row per call), and treats a truthy per-contact `error` OR a missing `data`
     key as "zero candidates for this row" without throwing. The pre-existing singular
     `contact.data` and flat-fixture fallback branches are left in place, unchanged, for
     offline back-compat (per explicit instruction not to remove them without checking
     every caller/fixture -- confirmed there is exactly one caller in the whole repo).

verification: |
  RED (before fix, captured 2026-07-28):
    tests/n8n/lushaRequestContract.test.mjs -- 5 tests, 1 pass / 4 fail. Failure excerpt
    (test "Lusha Enrich body: maps identity_keys -> {contacts:[...]}"):
      AssertionError: actual ['email','linkedin_url','firstName','lastName','companyName',
      'domain'] vs expected ['contacts']
    tests/n8n/enrichment.test.mjs (new tests only) -- 4 tests, 3 pass / 1 fail. Failure:
      "toCandidates: Lusha live v2 PLURAL contacts-map (real contract) extracts email +
      mobile" -> AssertionError: email candidate present from
      contacts['1'].data.emailAddresses (actual: undefined)
    Full suite at RED: node 267 total / 262 pass / 5 fail; pytest 416/416 unaffected.

  GREEN (after fix): node 267/267 pass; pytest 416/416 pass. Zero regressions vs the
  416 pytest / 258 node baseline (9 new node tests, all passing).

  Rebuild determinism: `.venv/bin/python scripts/build_cloud_workflows.py` run twice,
  `diff -rq` on the full n8n/ output directory -> byte-identical both runs.

  Diff scope of the rebuild: n8n/wf_enrichment_cloud.json changed in exactly 2 places
  (the Lusha Enrich jsonBody -- Half 1; the inlined Normalize+Score Code node body, which
  embeds normalizeProviders.js verbatim -- Half 2). n8n/wf_enrichment_local.json and
  n8n/wf_enrichment_local_live.json changed ONLY in the inlined normalizeProviders.js
  body (Half 2 propagated automatically because it is the ONE shared module every
  workflow's Normalize+Score node inlines -- confirms the fix landed in the shared
  function, not a per-caller patch). wf_contact_ingest_*.json and
  wf_scheduled_maintenance_cloud.json are untouched (byte-identical).

  Explicit scope call-outs (as requested):
  (a) Existing fixture encoding the wrong shape: YES.
      tests/fixtures/enrichment/lusha_live_person.json is the pre-existing "singular
      contact.data" fixture, loaded in enrichment.test.mjs with a comment claiming it was
      "real v2 person" data. It was NEVER actually observed live -- the real live shape is
      the plural contacts map (tests/fixtures/enrichment/lusha_live_person_v2.json, added
      this session). Per instruction, this was NOT silently rewritten: the fixture and its
      test are kept AS-IS (they still validate the legitimate offline-fallback code path,
      which lushaCandidates() must keep supporting), and only the misleading inline
      comment was corrected to state plainly that the singular form was never confirmed
      live and is offline-fallback-only.
  (b) Companies Lusha path shares the bug: NO, not affected, not touched.
      The companies "Lusha Company" node hits a different endpoint (/v2/company) whose
      confirmed-live envelope is a flat {"data":{...}} wrap (no contact/contacts key at
      all) -- already correctly unwrapped by lushaCandidates()'s existing
      `raw.company || raw.data || raw` fallback inside the companies branch (verified by
      the pre-existing "Lusha live company unwraps `data`" test, still green, untouched).
      Separately, "Lusha Company" has its own ALREADY-TRACKED, unrelated contract bug
      (Track B, reviews LOW-5: it's a POST to a static URL with the default identity_keys
      body, but the live-verified contract is GET /v2/company?domain=... -- pinned by
      test_track_b_lusha_company_url_method_mismatch_is_flagged_in_builder_source in
      tests/test_provider_gate_topology.py, explicitly deferred there, not this session's
      scope). Cannot be proven affected by THIS bug (its request is already broken a
      different way, pre-existing and tracked) and was not touched.
  (c) build_enrichment_local_live()'s Lusha request (bonus call-out, not asked for but
      surfaced during the required "check every caller" grep): this headless
      real-provider-testing workflow builds its OWN, separately-broken GET-querystring
      Lusha request via ENRICH_BUILD_REQUESTS (firstName/lastName/companyName/
      companyDomain as querystring params -- all confirmed-rejected fields per the live
      probe). This is a DIFFERENT code path from the fixed Cloud node, was not what the
      live canary exercised, and is left untouched -- flagged here for a future session,
      not fixed.

files_changed:
  - tests/n8n/lushaRequestContract.test.mjs (new -- Half 1 red test)
  - tests/n8n/enrichment.test.mjs (Half 2 red tests + corrected fixture comment)
  - tests/fixtures/enrichment/lusha_live_person_v2.json (new -- real live envelope fixture)
  - scripts/build_cloud_workflows.py (Half 1 fix -- Lusha Enrich jsonBody)
  - n8n/code/normalizeProviders.js (Half 2 fix -- lushaCandidates() unwrap)
  - n8n/wf_enrichment_cloud.json (regenerated -- both halves)
  - n8n/wf_enrichment_local.json (regenerated -- Half 2 propagation only)
  - n8n/wf_enrichment_local_live.json (regenerated -- Half 2 propagation only)
