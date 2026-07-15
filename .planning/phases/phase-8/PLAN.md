---
phase: phase-8
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - src/hubspot_client.py
  - src/ingest.py
  - main.py
  - tests/test_contact_ingest.py
  - .env.example
autonomous: true
requirements: [P8-SC1, P8-SC2, P8-SC3]

must_haves:
  truths:
    - "python main.py --ingest <csv> resolves each accepted row and, in dry-run, prints a PATCH for a matched contact and a create payload for a net-new row with ZERO live writes (P8-SC3)."
    - "A matched contact's emitted PATCH never contains a canonical `email` write (email is manual_protected) but fills a blank `phone` (fill_blank_only) and holds a present `jobtitle` for needs_review (stale_refreshable) (P8-SC1)."
    - "A net-new row creates ONLY when ALLOW_CONTACT_CREATE is true AND a pre-create email recheck finds no existing contact; DRY_RUN prints only; flag off => review, no create (P8-SC2)."
    - "python main.py (no args) still runs the company demo (run_local_mvp) unchanged (P8-SC3)."
  artifacts:
    - src/hubspot_client.py   # gains create_record (gated dry-run, no requests.post in dry-run)
    - src/ingest.py           # row_to_provider_result, precreate_email_recheck, run_contact_ingest
    - main.py                 # --ingest <path> entrypoint alongside the company demo
    - tests/test_contact_ingest.py  # offline functional proof, all HubSpot fns mocked
    - .env.example            # ALLOW_CONTACT_CREATE=false
  key_links:
    - "row_to_provider_result -> provider_to_candidates -> build_merge_result: the match path REUSES the existing merge engine (contacts skip ICP at merge_policy line 296)."
    - "run_contact_ingest injects hs_search / hs_get / create_record so the whole path runs offline with canned-dict stubs (no token, no network)."
    - "precreate_email_recheck sits BETWEEN net_new resolution and create_record; a hit there downgrades net_new to review."
---

<objective>
Wire object_type=contacts through the existing pipeline end to end in dry-run: resolve
identity -> non-clobber merge (PATCH existing) OR gated net-new create. An uploaded file
row becomes just another enrichment SOURCE (`csv`) that flows through the SAME
build_merge_result engine already shipped in Milestone 1. The one genuinely new mechanism
is a gated, dry-run-first `create_record` with a re-check-by-email guard.

Purpose: Complete the contact pipeline (SC of Phase 8) so Phase 9 can prove the full
ingestion matrix on multi-row files and add the dedupe sweep.

Output: create_record on the HubSpot client, src/ingest.py (row->candidate helper +
recheck guard + batch runner), a `--ingest` entrypoint on main.py, and an offline
functional test that drives tests/fixtures/uploads/contacts.csv to a matched-contact PATCH
and a net-new create payload with zero live writes.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@src/schemas.py
@src/merge_policy.py
@src/identity.py
@src/normalizer.py
@src/file_loader.py
@src/hubspot_client.py
@main.py
@config/field_policy.yaml
@config/source_registry.yaml
@tests/test_identity.py
@tests/test_main.py
@tests/fixtures/contact_current.json
@tests/fixtures/uploads/contacts.csv
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Gated dry-run create_record on the HubSpot client (P8-SC2)</name>
  <files>src/hubspot_client.py, .env.example</files>
  <behavior>
    - create_record("contacts", {"email": "x@y.com"}, dry_run=True) prints a POST preview and returns the sentinel {"dry_run": True, "payload": {"properties": {...}}} WITHOUT calling requests.post (monkeypatch requests.post to raise -> must not fire).
    - The dry_run print never includes hs_headers/token (payload dict only), mirroring patch_record.
    - Live branch (dry_run=False) POSTs to /crm/v3/objects/{type} with the properties body — exercised only structurally (not called in tests; no token).
  </behavior>
  <action>
    Add `create_record(object_type: str, properties: dict, dry_run=True)` to src/hubspot_client.py, mirroring the existing patch_record exactly. Wrap properties as {"properties": properties}. When dry_run is True: print a json.dumps of {dry_run: True, method: "POST", url: f"{BASE_URL}/crm/v3/objects/{object_type}", payload} (indent=2, default=str) and return {"dry_run": True, "payload": payload} WITHOUT touching requests — dry-run must short-circuit before any network call, same as patch_record. Only in the live branch (dry_run False) call requests.post(url, headers=hs_headers(), json=payload, timeout=30), raise_for_status, return r.json(). Do NOT read or check ALLOW_CONTACT_CREATE inside the client — that gate is the CALLER's job (per §21 safety-gate pattern). Add the env flag `ALLOW_CONTACT_CREATE=false` to .env.example near the other ALLOW_* gates so the default is off.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import src.hubspot_client as h; h.requests.post=lambda *a,**k:(_ for _ in ()).throw(AssertionError('network in dry-run')); r=h.create_record('contacts',{'email':'x@y.com'},dry_run=True); assert r=={'dry_run':True,'payload':{'properties':{'email':'x@y.com'}}}, r; print('OK')"</automated>
    <automated>grep -q '^ALLOW_CONTACT_CREATE=false' .env.example && echo ENV_OK</automated>
  </verify>
  <done>create_record exists and mirrors patch_record; in dry_run it returns the sentinel with no requests.post call; ALLOW_CONTACT_CREATE=false is in .env.example.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: src/ingest.py — row->candidate helper, recheck guard, batch runner (P8-SC1, P8-SC2)</name>
  <files>src/ingest.py</files>
  <behavior>
    - row_to_provider_result({"phone":"0412 345 678","jobtitle":"Sales Manager","email":"a@b.com"}) returns ProviderResult(provider="csv", object_type="contacts", matched=True, data={mapped contact fields present in the row}); provider_to_candidates(...) then yields CandidateValue(provider="csv") with phone normalized to E.164 (+61412345678).
    - precreate_email_recheck("a@b.com", hs_search=<stub returning 1 hit>) returns a non-empty id list (dup found); with a 0-hit stub returns [] (clear to create).
    - run_contact_ingest on a CSV with a matched row (email hit) emits action="patch" whose payload has NO canonical `email` key but DOES fill a blank `phone`; a net_new row (email 0 hits) with allow_create=True and a clear recheck emits action="create" with the email in the payload; allow_create=False OR a recheck hit emits action="review" with NO create payload; an ambiguous row and an ingest-reject emit action="review"/"skip" with no write.
  </behavior>
  <action>
    Create src/ingest.py. Import ProviderResult, ProviderEvidence, HubSpotRecord from src.schemas; provider_to_candidates from src.normalizer; resolve_identity from src.identity; build_merge_result from src.merge_policy; ingest_file from src.file_loader; get_record, search_records, create_record from src.hubspot_client.

    (a) `row_to_provider_result(row: dict, confidence: int = 80) -> ProviderResult`: build data = {k: row[k] for the mapped contact fields present and non-empty in row} over the keys email, firstname, lastname, jobtitle, phone, mobilephone, linkedin_url, company. Set provider="csv", object_type="contacts", matched=True, confidence, evidence=ProviderEvidence(match_basis=["upload"], evidence_summary="user-uploaded file row"). DOCUMENTED DEVIATION from the CLAUDE.md brief's example default of 60: every contacts field threshold in field_policy is >=75 (phone 80, jobtitle 75, linkedin 85, email 95), so a 60-confidence upload could NEVER fill a blank — 80 reflects a declarable trusted internal export (source_registry csv "trust is DECLARABLE") and lets fill_blank_only/stale_refreshable actually exercise their promote/needs_review branches. Keep confidence a parameter so a caller/test can lower it to hit the needs_review branch. Add a `# ponytail:` line naming this ceiling.

    (b) `precreate_email_recheck(email: str, hs_search=search_records) -> list`: re-run the email EQ search (same shape as identity._search_ids: filters=[{propertyName:"email",operator:"EQ",value:email}], object_type="contacts") and return the list of string ids found. Empty list == clear to create; non-empty == a dup appeared since resolution. Do NOT create here — classification only.

    (c) `run_contact_ingest(path, hs_search=search_records, hs_get=get_record, allow_create=False, dry_run=True, upload_confidence=80) -> list[dict]`: call ingest_file(path). Seed the report with one entry per reject: {row_index, outcome:"rejected", action:"skip", reason}. For each accepted row (keep its index), resolve_identity(row, hs_search):
      - outcome "match": fetch the existing contact via hs_get("contacts", result.contact_id, <a contacts property list>) -> build HubSpotRecord(object_type="contacts", id=result.contact_id, properties=fetched["properties"]); candidates = provider_to_candidates(row_to_provider_result(row, confidence=upload_confidence)); merge = build_merge_result(record, candidates); assemble the emitted patch from merge.full_patch (staging+metadata+canonical+status — for contacts there is no ICP) and call create/patch via patch_record(object_type, id, patch, dry_run=dry_run); append {row_index, outcome:"match", action:"patch", contact_id, payload: patch, canonical_patch: merge.canonical_patch}.
      - outcome "net_new": ids = precreate_email_recheck(row's normalized email, hs_search). If ids -> append {outcome:"net_new", action:"review", reason:"dup found on pre-create recheck", candidate_ids: ids} (NO create). Elif not allow_create -> append {outcome:"net_new", action:"review", reason:"ALLOW_CONTACT_CREATE is off; staged for review"} (NO create). Else -> build the create properties by NORMALIZING the row: create_props = {c.canonical_field: c.normalized_value for c in provider_to_candidates(row_to_provider_result(row, confidence=upload_confidence)) if c.normalized_value not in (None, "")} — this reuses the same normalize path and INCLUDES email as the new record's identity (nothing to protect on create). Call create_record("contacts", create_props, dry_run=dry_run); append {outcome:"net_new", action:"create", payload: create_record's returned/sent payload with email present}.
      - outcome "ambiguous": append {outcome:"ambiguous", action:"review", reason: result.reason} (NO write).
    Return the ordered report list (plain dicts — JSON-serializable for the Phase 10 decision service; no new schema needed). `# ponytail:` note that the report is plain dicts, add a pydantic model only if a consumer needs validation.

    Reuse build_merge_result for the match path — do NOT write a second merge engine. Do NOT let create run when allow_create is False or when the recheck returns ids.
  </action>
  <verify>
    <automated>.venv/bin/python -c "from src.ingest import row_to_provider_result, precreate_email_recheck; from src.normalizer import provider_to_candidates; cs=provider_to_candidates(row_to_provider_result({'phone':'0412 345 678','email':'a@b.com'})); assert all(c.provider=='csv' for c in cs); assert any(c.canonical_field=='phone' and c.normalized_value=='+61412345678' for c in cs), cs; hit=lambda object_type,filters,properties,limit=100:{'results':[{'id':'9'}]}; clr=lambda object_type,filters,properties,limit=100:{'results':[]}; assert precreate_email_recheck('a@b.com',hit)==['9']; assert precreate_email_recheck('a@b.com',clr)==[]; print('OK')"</automated>
  </verify>
  <done>row_to_provider_result emits csv-sourced normalized candidates; precreate_email_recheck returns ids on a hit and [] when clear; run_contact_ingest routes match->patch, net_new->create/review, ambiguous->review, reject->skip with the create gates honored.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: main.py --ingest entrypoint + offline functional test (P8-SC1, P8-SC2, P8-SC3)</name>
  <files>main.py, tests/test_contact_ingest.py</files>
  <behavior>
    - `python main.py --ingest tests/fixtures/uploads/contacts.csv` runs run_contact_ingest (reading DRY_RUN + ALLOW_CONTACT_CREATE from env) and prints the per-row report; `python main.py` with no args still runs run_local_mvp (company demo) unchanged.
    - Functional test (all HubSpot fns mocked, no token, no network):
      1. matched row (email hit stub) -> report action "patch"; payload has `csv_email` staged but NO canonical `email`; blank `phone` filled in canonical_patch (`phone` present); present `jobtitle` NOT in canonical_patch (needs_review).
      2. net_new row (email 0 hits at resolve) with ALLOW_CONTACT_CREATE=true and a clear recheck -> action "create"; payload properties contain the email.
      3. same net_new row but the recheck stub now returns a hit -> action "review", reason mentions dup, NO create payload.
      4. ALLOW_CONTACT_CREATE=false -> net_new -> action "review", NO create payload.
      5. no requests.post / requests.patch / requests.get ever fires (sentinels raise if called).
  </behavior>
  <action>
    main.py: keep run_local_mvp and its __main__ behavior intact. Under the __main__ guard, after load_dotenv(), parse sys.argv: if "--ingest" is present, read the path that follows, read allow_create = os.getenv("ALLOW_CONTACT_CREATE","false").lower()=="true" and dry_run = os.getenv("DRY_RUN","true").lower()=="true", call run_contact_ingest(path, allow_create=allow_create, dry_run=dry_run), print the returned report (json.dumps, default=str) and a one-line summary of action counts; else call run_local_mvp() as today. Import run_contact_ingest lazily inside the guard (or at top — no side effects). Do NOT call load_dotenv at module import (preserve main.py DEVIATION 1: import main stays side-effect-free for the hermetic suite).

    tests/test_contact_ingest.py: fully offline, following tests/test_identity.py and tests/test_main.py conventions. Build a call-count-aware email search stub (returns configured results for the FIRST email-EQ call at resolve time and a different result for the SECOND email-EQ call at recheck time) so scenario 3 can flip 0-hits->hit for the same row; a get stub returning a contact_current-shaped dict {"id":"123","properties":{...}} with phone="" (blank) and jobtitle="Sales Manager" (present) and a present email; and sentinels for requests.get/post/patch that raise AssertionError if called (delenv HUBSPOT_PRIVATE_APP_TOKEN and ANTHROPIC_API_KEY). Monkeypatch src.merge_policy.classify_field_with_haiku with a promote-style fake (as in test_main.py) so no live classifier fires. Drive run_contact_ingest(path=tests/fixtures/uploads/contacts.csv, hs_search=<stub>, hs_get=<stub>, allow_create=<per scenario>, dry_run=True, upload_confidence=85). Assert the 5 behaviors above. For scenario 1 focus assertions on the alice row (has an email); confirm the no-email row -> action "review"/ambiguous and the empty row -> "skip"/rejected (via ingest_file) so the whole batch is covered. Note explicitly in a comment that email is manual_protected on the ENRICH path (never canonical) but written as identity on the CREATE path — assert BOTH directions.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_contact_ingest.py -q</automated>
    <automated>.venv/bin/python -m pytest tests/ -q</automated>
  </verify>
  <done>main.py --ingest drives run_contact_ingest and the default demo still runs; tests/test_contact_ingest.py proves patch(no-canonical-email)+create(email-present)+recheck-downgrade+flag-off-review with zero network; full suite green with no regression against the 64-test baseline.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| uploaded file -> ingest | untrusted CSV/XLSX/JSON rows enter the pipeline |
| ingest/merge -> HubSpot | proposed writes (PATCH existing, POST net-new) cross into the CRM |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-8-01 | Tampering/Elevation | create_record / run_contact_ingest net-new path | high | mitigate | dry_run defaults True (prints only, no requests.post); ALLOW_CONTACT_CREATE defaults false and is checked by the caller so create never runs unless explicitly enabled; test asserts flag-off => review, no create |
| T-8-02 | Tampering | net-new create between resolution and create | medium | mitigate | precreate_email_recheck re-runs the email EQ search immediately before create; any hit downgrades net_new to review (no duplicate created) — test flips 0-hits->hit to prove it |
| T-8-03 | Integrity/Info-Disclosure | email on the enrich path | high | mitigate | email is manual_protected in field_policy contacts, so build_merge_result never promotes it to canonical from a csv source; test asserts no canonical `email` in the matched-row PATCH |
| T-8-04 | Denial of Service | one malformed upload row | low | accept | ingest_file already wraps each row in try/except and routes failures to rejects; run_contact_ingest surfaces them as action="skip" |
| T-8-SC | Tampering | package installs | low | accept | no new dependencies added this phase — reuses existing pydantic/requests/phonenumbers/email-validator; no package-legitimacy checkpoint required |
</threat_model>

<verification>
- `.venv/bin/python -m pytest tests/test_contact_ingest.py tests/ -q` — all green offline, no network, no token.
- Full suite shows no regression against the 64-test baseline (new file adds tests; prior 64 still pass).
- `python main.py` (no args) still prints the company demo's four sections (run_local_mvp unchanged).
- Manual grep proof: create_record has no requests.post reachable in the dry_run branch; run_contact_ingest never calls create_record when allow_create is False.
</verification>

<success_criteria>
1. object_type=contacts flows through build_merge_result; an upload row becomes CandidateValue(s) as source `csv` and merges under the existing field-ownership classes (email manual_protected -> never canonical from CSV on enrich; fill_blank_only phone fills a blank; jobtitle stale_refreshable -> needs_review on a present value). [P8-SC1]
2. hubspot_client gains a gated create_record (dry_run + caller-checked ALLOW_CONTACT_CREATE); net-new create re-checks HubSpot by email immediately before create and is a no-op (route to review) when the flag is off or a dup reappears. [P8-SC2]
3. main.py exposes a `--ingest <path>` entrypoint; the functional test drives tests/fixtures/uploads/contacts.csv to an emitted dry-run PATCH (matched) AND a create payload (net-new) with ZERO live writes; the default company demo is intact. [P8-SC3]
</success_criteria>

<output>
Create `.planning/phases/phase-8/phase-8-01-SUMMARY.md` when done.
</output>
