---
phase: 09-functional-e2e-tests-dedupe-sweep
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/sweep.py
  - src/schemas.py
  - tests/test_sweep.py
  - tests/fixtures/uploads/contacts_e2e.csv
  - tests/test_e2e_ingest.py
  - tests/live_smoke_contact.py
autonomous: true
requirements: [P9-SC1, P9-SC2, P9-SC3]

must_haves:
  truths:
    - "A single multi-row upload file drives every ingestion path (match+enrich, net-new create, ambiguous weak-key, no-email→never-create, rejected-at-load) with asserted per-row outcomes+actions AND field-level invariants, fully offline."
    - "dedupe_sweep flags duplicate email/phone/linkedin groups and mangled (invalid email / unparseable phone) contacts as needs_review, returning a typed SweepReport; the phone-dup proof catches a '0412...' vs '+61412...' pair via normalize-before-compare (P9-SC2)."
    - "The full offline suite (69 baseline + new) is green with zero network; a non-gating live smoke enriches one matched contact through the REAL Haiku classifier with zero HubSpot writes (P9-SC3)."
  artifacts:
    - src/sweep.py
    - "SweepReport model in src/schemas.py"
    - tests/test_sweep.py
    - tests/fixtures/uploads/contacts_e2e.csv
    - tests/test_e2e_ingest.py
    - tests/live_smoke_contact.py
  key_links:
    - "sweep reuses normalize_email / normalize_phone (normalizer.py) + canonicalize_linkedin (identity.py) so keys are compared AFTER normalization"
    - "test_e2e_ingest drives run_contact_ingest with a value-routed hs_search + injected hs_get; classify_field_with_haiku is monkeypatched offline"
    - "live_smoke_contact runs run_contact_ingest with injected HubSpot stubs (no network) but a LIVE classify_field_with_haiku (real ANTHROPIC key)"
---

<objective>
Prove the whole Milestone-2 contact-ingestion behavior end to end on a realistic
multi-row file, add the weekly dedupe/mangled maintenance sweep (CLAUDE.md §13.4
Workflow D), and confirm the full suite stays green offline plus one live-Haiku smoke.

Purpose: Phases 5–8 built the loader, resolver, merge wiring, and gated create in
isolation. Phase 9 is the integration proof the developer explicitly asked for — one
file exercising every path at once — plus the operational sweep that keeps the CRM clean.
Output: src/sweep.py + SweepReport schema + tests/test_sweep.py (SC2); a multi-row
contacts_e2e fixture + tests/test_e2e_ingest.py (SC1); a documented non-gating live
smoke script + a full-suite green run (SC3). No new dependencies, no production wiring
(the n8n workflow is Phase 10).
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

# The ingestion pipeline this phase proves end to end
@src/ingest.py
@src/identity.py
@src/file_loader.py
@src/normalizer.py
@src/merge_policy.py
@src/hubspot_client.py
@src/schemas.py

# The Phase-8 functional test whose offline-hermetic conventions the new tests copy
# (injected hs_search/hs_get stubs, monkeypatched src.merge_policy.classify_field_with_haiku,
#  requests.* sentinels that raise on any leaked live call)
@tests/test_contact_ingest.py

# Existing single upload fixture (BOM + "Email Address"/"First Name"… headers, column_mapping aliases)
@tests/fixtures/uploads/contacts.csv
@config/field_policy.yaml
@config/column_mapping.yaml
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Dedupe/mangled sweep (src/sweep.py + SweepReport) with offline proof (P9-SC2)</name>
  <files>src/sweep.py, src/schemas.py, tests/test_sweep.py</files>
  <behavior>
    - Duplicate email: two records whose raw emails normalize equal → one finding {key_type:"email", key_value, ids:[both]}.
    - Duplicate phone (THE load-bearing case): one record raw "+61412345678" and one raw "0412 345 678" → both normalize to "+61412345678" → a single {key_type:"phone", ...} finding with both ids. Proves normalize-BEFORE-compare; a naive raw-string compare would miss it.
    - Duplicate linkedin: two records whose linkedin_url differ only by trailing slash / host case → one {key_type:"linkedin_url", ...} finding (canonicalize_linkedin).
    - Mangled email: a record with a non-empty but invalid raw email (normalize_email → None) → {id, field:"email", raw, reason}.
    - Mangled phone: a record with a non-empty but unparseable raw phone (normalize_phone → None) → {id, field:"phone", raw, reason}.
    - Clean records (unique + valid) appear in NO finding.
    - to_review_ids == the sorted-unique union of every id in duplicates + mangled.
    - Deterministic ordering across repeated runs.
  </behavior>
  <action>
    Add a small SweepReport pydantic model to src/schemas.py (Phase 9 section, after IdentityResult), with the imports already present in that file. Fields: duplicates: List[Dict[str, Any]] (default_factory list), mangled: List[Dict[str, Any]] (default_factory list), duplicate_count: int = 0, mangled_count: int = 0, to_review_ids: List[str] (default_factory list). Keep findings as plain dicts (matches the run_contact_ingest report style already shipped in ingest.py — JSON-serializable for the Phase 10 decision service); do NOT introduce per-finding sub-models. Note in a comment that to_review_ids is a sorted-unique LIST representing set semantics (a real set is neither ordered nor JSON-serializable), chosen for determinism + Phase-10 transport.

    Create src/sweep.py exposing dedupe_sweep(records: list[dict]) -> SweepReport. records are HubSpot-contact-like dicts shaped {id, properties:{email, phone, mobilephone, linkedin_url, ...}}; the sweep is INJECTED this in-memory list so it is pure and offline (a thin HubSpot-search adapter can feed it in Phase 10 — do NOT build that here, YAGNI). Reuse the existing normalizers — import normalize_email and normalize_phone from src.normalizer and canonicalize_linkedin from src.identity — so comparison happens on normalized keys, never raw strings. Read each record's fields via rec.get("properties", {}) and coerce ids with str(rec["id"]).

    Duplicate detection: for each (key_type, normalizer, prop) in the fixed order [("email", normalize_email, "email"), ("phone", normalize_phone, "phone"), ("linkedin_url", canonicalize_linkedin, "linkedin_url")], build a dict mapping normalized-key → list of ids (skip records whose normalized key is falsy). For every key with ≥2 ids, emit {key_type, key_value, ids: sorted(ids)}. Iterate keys in sorted order for determinism. Phone dedup keys on the "phone" property only (mobilephone is out of scope for the group key this phase — a one-line note).

    Mangled detection: iterate records sorted by str(id); for field in ("email", "phone") with normalizer normalize_email / normalize_phone, if the raw value is non-empty (not in None/"") AND the normalizer returns None, emit {id, field, raw, reason:"invalid email"/"unparseable phone"}. A blank field is NOT mangled.

    Compute duplicate_count/mangled_count as the list lengths, and to_review_ids as sorted(set(...)) over every id appearing in any duplicate group plus every mangled id. Return the SweepReport. No prints, no I/O, no HubSpot calls — this is a pure classify-only function per CLAUDE.md §13.4 (flags to needs_review; never writes).

    Write tests/test_sweep.py as an OFFLINE test using an inline list literal of records (no fixture file, no monkeypatching needed — the function is pure). Include: two records sharing an email; two records sharing a phone written as "+61412345678" and "0412 345 678"; two sharing a linkedin differing by trailing-slash/case; one garbage-email record; one unparseable-phone record; and at least one fully clean unique record. Assert the exact duplicate groups (key_type, key_value, and the id sets), the exact mangled findings, the counts, and that to_review_ids equals the expected sorted-unique union AND is itself sorted. Add an EXPLICIT standalone assertion that the phone group's key_value == "+61412345678" and its ids == both raw-format records' ids — the comment on that assertion names it as the normalize-before-compare proof. Assert the clean record's id is absent from to_review_ids.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_sweep.py -q</automated>
  </verify>
  <done>tests/test_sweep.py passes offline; the phone-dup assertion proves "0412…" and "+61412…" collapse to one group; SweepReport validates and to_review_ids is the sorted-unique union.</done>
</task>

<task type="auto">
  <name>Task 2: Multi-row E2E fixture + tests/test_e2e_ingest.py — full ingestion matrix (P9-SC1)</name>
  <files>tests/fixtures/uploads/contacts_e2e.csv, tests/test_e2e_ingest.py</files>
  <action>
    Create tests/fixtures/uploads/contacts_e2e.csv reusing the existing header/alias shape (column_mapping.yaml maps "Email Address","First Name","Last Name","Job Title","Phone","Company","LinkedIn"). Header row: Email Address,First Name,Last Name,Job Title,Phone,Company,LinkedIn. Five data rows, one per path:
      Row A — confident match+enrich: bob.smith@example.com,Bob,Smith,New Title From Upload,0412 345 678,Example Co,https://linkedin.com/in/bob-upload
      Row B — net-new create: alice@example.com,Alice,Anderson,Analyst,0400 111 222,Example Media,(empty LinkedIn)
      Row C — ambiguous weak-key (phone+lastname): (empty email),Carol,Jones,Coordinator,0400 222 333,Some Company,(empty LinkedIn)
      Row D — no-email → never create: (empty email),Dave,Nguyen,Manager,(empty phone),Another Company,(empty LinkedIn)
      Row E — rejected at load: (empty email),(empty first),(empty last),Just A Title,0400 999 888,(empty company),(empty LinkedIn)
    Rationale (encode as a header comment via a leading note in the test, not in the CSV): required_identity is email OR firstname+lastname+company, so Row E (only jobtitle+phone) has no identity key and is rejected at LOAD before resolution; Rows C and D carry firstname+lastname+company so they pass load and reach the resolver; Row C additionally carries a phone so it hits the phone+lastname weak-key branch, Row D has no phone so it falls through to the name+company branch then the hard no-email rule.

    Write tests/test_e2e_ingest.py copying the hermetic conventions from tests/test_contact_ingest.py verbatim: an autouse fixture that deletes HUBSPOT_PRIVATE_APP_TOKEN and ANTHROPIC_API_KEY, sets ALLOW_SONNET_ESCALATION=false, monkeypatches src.merge_policy.classify_field_with_haiku to a promote-style stub, and installs raise-on-call sentinels on src.hubspot_client.requests.get/post/patch so any leaked live call fails the test.

    Build ONE value-routed hs_search(object_type, filters, properties=None, limit=100) that routes on (filters[0]["propertyName"], filters[0]["value"]) against a lookup, defaulting to {"results": []}. Populate the lookup with NORMALIZED values (resolve_identity normalizes before searching): ("email","bob.smith@example.com") → [{"id":"123"}] (single match); ("email","alice@example.com") → [] (0 hits → net_new, and because routing is by value the pre-create recheck for the SAME email also returns [] so the create proceeds — this is the recheck-stays-empty requirement, satisfied by value-consistent routing rather than a call counter); ("phone","+61400222333") → [{"id":"777"}] (Row C weak-key hit → ambiguous). Everything else (Row D firstname EQ, linkedin, etc.) → []. Add a one-line note that value routing is inherently call-count-safe for the net_new recheck because the same email value yields the same empty result on both the resolve and recheck calls.

    Provide an injected hs_get(object_type, record_id, properties) returning the Row-A existing contact used for the enrich invariants: properties {email:"bob.smith@example.com", firstname:"Bob", lastname:"Smith", jobtitle:"Sales Manager" (PRESENT and DIFFERENT from the upload's "New Title From Upload" → stale_refreshable conflict → needs_review), phone:"" (BLANK → fill_blank_only promotes the upload phone), linkedin_url:"https://linkedin.com/in/bob-existing" (PRESENT → fill_blank_only staged, never clobbered)}.

    Drive report = run_contact_ingest(contacts_e2e.csv, hs_search=<value-routed>, hs_get=<injected>, allow_create=True, dry_run=True, upload_confidence=85) once. Assert the PER-ROW outcomes+actions: exactly one {outcome:"match", action:"patch"}; exactly one {outcome:"net_new", action:"create"}; exactly two {action:"review"} — one {outcome:"ambiguous"} whose reason names the weak-key match and one {outcome:"ambiguous"} whose reason is the no-email/insufficient-identity hard rule; exactly one {outcome:"rejected", action:"skip"}; and assert exactly ONE create total (Row D must NOT create).

    Assert the FIELD-LEVEL invariants on the match entry (m = the patch entry): "csv_email" in m["payload"] (staged) but "email" not in m["canonical_patch"] and "email" not in m["payload"] (manual_protected → never a bare canonical email); "phone" in m["canonical_patch"] (blank filled); "jobtitle" not in m["canonical_patch"] (present+conflicting → needs_review, withheld); "csv_linkedin_url" in m["payload"] but "linkedin_url" not in m["canonical_patch"] (present fill_blank_only → never clobbered). Assert the create entry's payload.payload.properties["email"] == "alice@example.com" (email IS written as the new record's identity on create). Add a final assertion that no requests.* sentinel fired (reaching the end proves zero network for both the dry-run PATCH and dry-run POST paths).
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_e2e_ingest.py -q</automated>
  </verify>
  <done>One multi-row file drives all five paths with exact per-row outcomes/actions and the enrich field-invariants (email never canonical, blank phone filled, conflicting jobtitle withheld, present linkedin not clobbered); exactly one create; zero network.</done>
</task>

<task type="auto">
  <name>Task 3: Non-gating live-Haiku smoke script + full offline suite run (P9-SC3)</name>
  <files>tests/live_smoke_contact.py</files>
  <action>
    Create tests/live_smoke_contact.py as a standalone runnable (guarded by if __name__ == "__main__"). It is NOT collected by pytest (no test_ prefix) so it never runs in the offline suite — it is the documented one-shot the executor runs by hand. It calls run_contact_ingest on tests/fixtures/uploads/contacts_e2e.csv with an injected hs_search that returns a single email match for the Row-A email (so exactly one matched contact enriches) and an injected hs_get returning the Row-A existing record; allow_create=False, dry_run=True. Do NOT monkeypatch classify_field_with_haiku — the point is the REAL Haiku classifier drives a contact field decision (ANTHROPIC_API_KEY + ANTHROPIC_HAIKU_MODEL=claude-haiku-4-5 are already in .env). HubSpot stays fully mocked via the injected stubs + dry_run, so no real HubSpot call occurs; the only live component is the Anthropic call (the anthropic SDK uses httpx, not the requests client, so the pipeline's requests-based HubSpot client is untouched).

    Wrap the whole run in try/except: on success print a "LIVE SMOKE PASS" line summarizing that a matched contact enriched and that the emitted action was a dry-run patch (assert at least one report entry has action=="patch" and its canonical_patch/payload is non-empty, evidencing the live classifier ran); on ANY exception (rate limit, model id, auth) print "LIVE SMOKE SKIPPED/ERROR: <exception>" and exit 0. This step is NON-GATING — it must never fail the phase. Add a short docstring documenting the exact command and the safety posture (real Haiku, mock providers/HubSpot, DRY_RUN=true, ALLOW_CONTACT_CREATE=false, zero writes).

    After the script exists, run the FULL offline suite to confirm Milestone-1 + Milestone-2 green with the new tests and zero network (69 baseline + the new test_sweep.py and test_e2e_ingest.py cases), then run the live smoke once and capture its single PASS/SKIP line into the SUMMARY (do not gate on it).
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/ -q</automated>
    <human-check>Run `.venv/bin/python tests/live_smoke_contact.py` once with the real ANTHROPIC key present; confirm it prints a single LIVE SMOKE PASS (or SKIPPED/ERROR) line, performs zero HubSpot writes, and exits 0. Non-gating — capture the line in the SUMMARY regardless.</human-check>
  </verify>
  <done>`pytest tests/ -q` is fully green offline with no network (baseline + new tests); the live smoke runs as a documented, non-gating one-shot that enriches one matched contact via real Haiku with zero HubSpot writes and never fails the phase.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| uploaded file → sweep/ingest | Untrusted CSV/XLSX/JSON rows (arbitrary emails, phones, LinkedIn URLs) cross into the pipeline |
| CRM record list → dedupe_sweep | Untrusted/dirty HubSpot-shaped dicts (malformed emails, unparseable phones) are classified |
| local process → Anthropic API (live smoke only) | The one-shot smoke sends contact fields to the real Haiku endpoint |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-9-01 | Tampering | dedupe_sweep raw keys | medium | mitigate | Compare only NORMALIZED keys (normalize_email/normalize_phone/canonicalize_linkedin); mangled inputs return None and are surfaced as mangled findings, never silently grouped |
| T-9-02 | Denial of Service | malformed upload row in E2E | low | mitigate | ingest_file's per-row try/except already routes bad rows to rejects; Row E asserts a load-time reject never reaches resolution — no crash path |
| T-9-03 | Information Disclosure | live smoke / dry-run output | medium | mitigate | dry_run=True short-circuits before any requests.* call; HubSpot fns injected; tokens never printed (hubspot_client prints only the payload); requests.* sentinels raise on any leaked live call in the offline tests |
| T-9-04 | Elevation of Privilege | net-new create in E2E | high | mitigate | allow_create honored + pre-create email recheck; Row D (no email) asserted to NEVER create; exactly-one-create assertion bounds writes; dry_run keeps every write a no-op |
| T-9-05 | Repudiation | sweep findings | low | accept | Sweep is classify-only (needs_review flags), returns a deterministic typed report; audit trail is Phase 10's decision-service concern, not this phase |
</threat_model>

<verification>
- `.venv/bin/python -m pytest tests/ -q` — full suite green offline, no network (69 baseline + new test_sweep.py + test_e2e_ingest.py).
- `.venv/bin/python -m pytest tests/test_sweep.py tests/test_e2e_ingest.py -q` — the two new proofs pass in isolation.
- The phone-dup assertion in test_sweep.py fails if normalization is removed (normalize-before-compare is load-bearing, not incidental).
- The E2E requests.* sentinels raise if any live HubSpot call leaks — reaching the asserts proves zero network for both PATCH and POST paths.
- `.venv/bin/python tests/live_smoke_contact.py` — one-shot, non-gating; prints a single PASS/SKIP line, zero HubSpot writes, exit 0.
</verification>

<success_criteria>
- SC1: tests/test_e2e_ingest.py drives one multi-row file through match+enrich, net-new create, ambiguous weak-key, no-email→never-create, and rejected-at-load, asserting exact per-row outcomes/actions AND field-level invariants (email never canonical, blank phone filled, conflicting jobtitle → needs_review, present fill_blank_only never clobbered), fully offline.
- SC2: src/sweep.py dedupe_sweep flags duplicate email/phone/linkedin and mangled (invalid email/unparseable phone) contacts as needs_review in a typed SweepReport; the phone-dup proof shows normalize-before-compare collapsing "0412…" and "+61412…".
- SC3: `pytest tests/ -q` is green offline with no network; the documented non-gating live smoke enriches at least one matched contact via the real Haiku classifier with zero HubSpot writes.
</success_criteria>

<output>
Create `.planning/phases/phase-9/09-01-SUMMARY.md` when done. Capture: the new test/module paths, the final `pytest tests/ -q` count (baseline 69 + added), and the single live-smoke PASS/SKIP line (non-gating).
</output>
