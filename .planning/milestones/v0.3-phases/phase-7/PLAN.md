---
phase: phase-7
plan: 01
type: execute
wave: 1
depends_on: [phase-6-01]
files_modified:
  - src/schemas.py
  - src/identity.py
  - tests/test_identity.py
autonomous: true
requirements: [P7-SC1, P7-SC2, P7-SC3]
user_setup: []
must_haves:
  truths:
    - "resolve_identity tries match keys STRICTLY IN ORDER: email -> linkedin_url -> phone+lastname -> firstname+lastname+company; a SINGLE hit on email OR linkedin_url returns outcome='match' with the existing HubSpot contact_id and match_key set to the matched key; weak keys (phone+lastname, name+company) ALONE never return 'match' (P7-SC1)."
    - "A row with NO valid email is NEVER classified net_new: normalize_email returning None routes to linkedin/weak/ambiguous; outcome='net_new' is returned ONLY when a valid email is present AND the email search returns 0 hits (reason 'valid email, no existing match') (P7-SC2)."
    - ">1 hit on the searched key -> ambiguous (needs_review) with all seen ids in candidate_ids; a weak-key search returning >=1 candidate -> ambiguous (reason 'weak-key match requires review'); no valid email AND no weak-key hits -> ambiguous (reason 'no email, insufficient identity'), NOT net_new (P7-SC1, P7-SC3)."
    - "hs_search is INJECTED (default = hubspot_client.search_records); tests pass a stub returning canned {'results':[...],'total':N} dicts; resolve_identity is pure/deterministic given injected results; import of src.identity and the whole test run are OFFLINE with no HUBSPOT token and no network (P7-SC2, P7-SC3)."
    - "resolve_batch(rows, hs_search=...) maps each accepted Phase-6 IngestBatch.rows dict to one IdentityResult, in order (P7-SC3)."
  artifacts:
    - src/schemas.py
    - src/identity.py
    - tests/test_identity.py
  key_links:
    - "resolve_identity normalizes identity keys via EXISTING normalizer fns before searching: email via normalize_email (validate+lowercase, offline), phone via normalize_phone (E.164, AU region), names trimmed, linkedin via a new small canonicalize_linkedin (strip trailing slash, lowercase host) - no normalization is re-implemented."
    - "HubSpot search JSON shape {'results':[{'id':...,'properties':{...}}],'total':N} is parsed to a list of string ids via a small _search_ids helper; filters are [{'propertyName':k,'operator':'EQ','value':v}] AND-ed inside one filterGroup, so phone+lastname and firstname+lastname+company each require ALL keys to match."
    - "resolve_identity(row, hs_search=search_records): the hs_search default is hubspot_client.search_records; Phase 8 wires the real search when it builds the create path - Phase 7 only CLASSIFIES and MUST NOT create or PATCH anything."
---

<objective>
Classify each accepted upload row (from Phase 6 IngestBatch.rows) as an existing HubSpot contact (match), net-new, or ambiguous (needs_review) BEFORE any write. This is the new safety core of Milestone 2: a conservative identity resolver that auto-matches only on strong keys (email / LinkedIn), never auto-creates a no-email row, and routes everything uncertain to review.

Purpose: Matching is the real risk in contact ingestion - a wrong match clobbers the wrong record, a wrong net-new explodes duplicates in HubSpot. Per PROJECT.md Key Decision (M2) "auto only on email/LinkedIn; no-email never auto-creates; ambiguous -> review", Phase 7 encodes that policy as a pure, deterministic function with an injected (mockable, offline) HubSpot search. Phase 7 CLASSIFIES only; the create/PATCH paths are Phase 8.

Output: a new typed IdentityResult appended to src/schemas.py; a new src/identity.py holding resolve_identity (the ordered matching algorithm) + resolve_batch + a LinkedIn canonicalizer + a search-parsing helper; and tests/test_identity.py proving EVERY outcome offline against a mocked search.

Reuse, do NOT rebuild (confirmed against the current tree):
- src/normalizer.py already has normalize_email (validate+lowercase, check_deliverability=False so offline) and normalize_phone (E.164, region="AU"). CALL them for identity-key normalization. Do NOT re-implement email/phone parsing.
- src/hubspot_client.py already has search_records(object_type, filters, properties, limit=100) returning HubSpot search JSON. INJECT it as the default hs_search so tests substitute a stub. Do NOT add a new HTTP client.
- src/schemas.py is the pydantic home - APPEND IdentityResult there, matching the existing model style (Literal outcomes, Optional fields, Field(default_factory=list)). Do NOT invent a parallel models file.
- Phase 6 already parsed + mapped rows into IngestBatch.rows (canonical-keyed dicts: email, firstname, lastname, phone, jobtitle, company, linkedin_url). resolve_batch consumes those rows as-is.

Scope guard (out of scope - belongs to Phase 8, do NOT build): creating or PATCHing HubSpot records, turning rows into CandidateValue(s), main.py wiring, the ALLOW_CONTACT_CREATE gate, and the re-check-by-email create guard. Phase 7 stops at classification. Single plan file.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@src/schemas.py
@src/normalizer.py
@src/hubspot_client.py

# Reference (do not re-read wholesale): src/file_loader.py shows the row shape Phase 7
# consumes (IngestBatch.rows are canonical-keyed dicts). CLAUDE.md Key Decisions (M2) and
# §13.4 (dedupe) are the policy source: auto-match only on email/LinkedIn, no-email never
# net-new, ambiguous -> review.
</context>

<tasks>

<task type="auto">
  <name>Task 1: schemas.py - add the typed IdentityResult model</name>
  <files>src/schemas.py</files>
  <action>
Append ONE pydantic model, IdentityResult, to src/schemas.py (do not disturb existing models; match the existing style already in the file). Fields:
- `outcome: Literal["match", "net_new", "ambiguous"]` - the classification.
- `contact_id: Optional[str] = None` - the existing HubSpot contact id, set ONLY on a confident single match.
- `match_key: Optional[str] = None` - which key surfaced the result: one of "email", "linkedin_url", "phone_lastname", "name_company", or None when no key applied (the terminal no-identity case).
- `candidate_ids: List[str] = Field(default_factory=list)` - ALL HubSpot ids seen for this row (>=2 on an ambiguous multi-hit; the single id also appears here on a match; empty on net_new and on the no-identity ambiguous).
- `reason: str` - short human-readable explanation of the outcome.

Reuse the module's existing imports (Literal, Optional, List, Field are already imported at the top of schemas.py); do not add new imports. Keep it minimal and typed - no methods, no validators.
  </action>
  <verify>
    <automated>.venv/bin/python -c "from src.schemas import IdentityResult; r=IdentityResult(outcome='match', contact_id='501', match_key='email', candidate_ids=['501'], reason='single email match'); assert r.outcome=='match' and r.contact_id=='501' and r.candidate_ids==['501']; d=IdentityResult(outcome='ambiguous', reason='x'); assert d.contact_id is None and d.match_key is None and d.candidate_ids==[]; print('OK')"</automated>
  </verify>
  <done>IdentityResult imports and validates: outcome is a Literal of the three classes; contact_id/match_key default None; candidate_ids defaults to an empty list; reason is required. No existing schema is disturbed.</done>
</task>

<task type="auto">
  <name>Task 2: src/identity.py - resolve_identity (ordered algorithm, injected search) + resolve_batch + helpers</name>
  <files>src/identity.py</files>
  <action>
Create src/identity.py. Import IdentityResult from src.schemas; normalize_email and normalize_phone from src.normalizer; search_records from src.hubspot_client (used ONLY as the default value of the injected hs_search parameter); and urllib.parse (urlsplit, urlunsplit) from stdlib for the LinkedIn canonicalizer.

Provide `canonicalize_linkedin(url) -> Optional[str]`: return None for falsy/blank input; otherwise trim, ensure a scheme (prefix "https://" if the string has no "//"), lowercase the host (netloc) and scheme, strip a single trailing slash from the path, and reassemble with no query/fragment. This yields a deterministic key so exact-match search is stable. Keep it small.

Provide a private `_search_ids(hs_search, filters) -> list[str]`: call `hs_search(object_type="contacts", filters=filters, properties=["email", "linkedin_url", "phone", "firstname", "lastname", "company"])`; from the returned dict read `results` (default empty list) and return `[str(r["id"]) for r in results if isinstance(r, dict) and "id" in r]`. Filters are the HubSpot shape: a list of `{"propertyName": key, "operator": "EQ", "value": value}`, AND-ed inside the single filterGroup that search_records builds.

Provide `resolve_identity(row: dict, hs_search=search_records) -> IdentityResult`. It must be PURE and DETERMINISTIC given the injected hs_search (no time, no randomness, no global state). Algorithm, in this exact order:

1. Normalize identity keys first: `email = normalize_email(row.get("email"))` (None when absent OR invalid - an invalid email string therefore takes the no-email path); `linkedin = canonicalize_linkedin(row.get("linkedin_url"))`; `phone = normalize_phone(row.get("phone"))`; `firstname/lastname/company = str(row.get(k) or "").strip()`.

2. Email (CONFIDENT). If email is truthy: `ids = _search_ids(hs_search, [{"propertyName":"email","operator":"EQ","value":email}])`. If exactly 1 id -> return match: outcome="match", contact_id=that id, match_key="email", candidate_ids=[id], reason "single email match". If >1 -> return ambiguous: outcome="ambiguous", match_key="email", candidate_ids=ids, reason "multiple email matches". If 0 -> return net_new: outcome="net_new", candidate_ids=[], match_key=None, reason "valid email, no existing match". (Email present is the ONLY route to net_new; do NOT fall through to weaker keys once a valid email is in hand.)

3. Reaching here means NO valid email. LinkedIn (CONFIDENT). If linkedin is truthy: `ids = _search_ids(hs_search, [{"propertyName":"linkedin_url","operator":"EQ","value":linkedin}])`. 1 id -> match(match_key="linkedin_url", contact_id, candidate_ids=[id], reason "single linkedin match"); >1 -> ambiguous(match_key="linkedin_url", candidate_ids=ids, reason "multiple linkedin matches"); 0 -> fall through to weak keys.

4. Weak keys (a hit here is NEVER confident). First, if phone AND lastname: `ids = _search_ids(hs_search, [{"propertyName":"phone","operator":"EQ","value":phone},{"propertyName":"lastname","operator":"EQ","value":lastname}])`; if `ids` non-empty -> return ambiguous(match_key="phone_lastname", candidate_ids=ids, reason "weak-key match requires review"). Otherwise, if firstname AND lastname AND company: `ids = _search_ids(hs_search, [{"propertyName":"firstname","operator":"EQ","value":firstname},{"propertyName":"lastname","operator":"EQ","value":lastname},{"propertyName":"company","operator":"EQ","value":company}])`; if `ids` non-empty -> return ambiguous(match_key="name_company", candidate_ids=ids, reason "weak-key match requires review").

5. THE HARD SAFETY RULE (give it an explicit inline comment): no valid email AND no confident match AND no weak-key candidate -> return ambiguous, outcome="ambiguous", contact_id=None, match_key=None, candidate_ids=[], reason "no email, insufficient identity". This branch is the single most important safety property of Milestone 2 - a no-email row NEVER becomes net_new (which is what would let Phase 8 auto-create it). Never return net_new from this branch.

Provide `resolve_batch(rows: list[dict], hs_search=search_records) -> list[IdentityResult]`: return `[resolve_identity(r, hs_search=hs_search) for r in rows]`, preserving order. This is the Phase-6 -> Phase-7 seam (consumes IngestBatch.rows).

Do NOT import requests, read env, create, or PATCH. The only HubSpot touchpoint is the injected hs_search.
  </action>
  <verify>
    <automated>.venv/bin/python -c "
from src.identity import resolve_identity, canonicalize_linkedin
def only(prop):
    def s(object_type, filters, properties, limit=100):
        return {'results':[{'id':'501'}],'total':1} if filters[0]['propertyName']==prop else {'results':[],'total':0}
    return s
def none(object_type, filters, properties, limit=100):
    return {'results':[],'total':0}
r=resolve_identity({'email':'a@ex.com'}, hs_search=only('email')); assert r.outcome=='match' and r.contact_id=='501' and r.match_key=='email', r
r=resolve_identity({'email':'a@ex.com'}, hs_search=none); assert r.outcome=='net_new', r
r=resolve_identity({'linkedin_url':'https://LinkedIn.com/in/x/'}, hs_search=only('linkedin_url')); assert r.outcome=='match' and r.match_key=='linkedin_url', r
r=resolve_identity({'phone':'0412 345 678','lastname':'Baker'}, hs_search=only('phone')); assert r.outcome=='ambiguous' and r.contact_id is None and r.match_key=='phone_lastname', r
r=resolve_identity({'phone':'0412 345 678','lastname':'Baker'}, hs_search=none); assert r.outcome=='ambiguous' and r.reason=='no email, insufficient identity', r
r=resolve_identity({'email':'not-an-email'}, hs_search=none); assert r.outcome=='ambiguous', r
assert canonicalize_linkedin('https://LinkedIn.com/in/Alice/').endswith('/in/Alice') and 'linkedin.com' in canonicalize_linkedin('https://LinkedIn.com/in/Alice/')
print('OK')
"</automated>
  </verify>
  <done>resolve_identity classifies in strict key order with an injected search: email 1-hit -> match(email,id); email 0-hit -> net_new; linkedin 1-hit -> match; phone+lastname hit -> ambiguous (not match, not net_new); no-email + no hits -> ambiguous "no email, insufficient identity"; invalid email -> no-email path. Host is lowercased and trailing slash stripped by canonicalize_linkedin. No network, no create/PATCH.</done>
</task>

<task type="auto">
  <name>Task 3: tests/test_identity.py - offline proof of every outcome with a mocked HubSpot search</name>
  <files>tests/test_identity.py</files>
  <action>
Author tests/test_identity.py - plain pytest, plain asserts, fully OFFLINE (no network, no API key, no HUBSPOT token), mirroring the style of tests/test_file_loader.py and tests/test_contact_normalizer.py.

Build a small mock-search factory: a function that, given a per-propertyName map of canned responses, returns a stub `hs_search(object_type, filters, properties, limit=100)` which reads `filters[0]["propertyName"]` and returns the mapped `{"results":[...],"total":N}` (default `{"results":[],"total":0}`). Have the stub RECORD each call (e.g. append to a list) so a test can assert the resolver actually called the injected search (proving injection is wired and the real search_records is never used). The stub must NOT import requests or touch the network - being a pure canned-dict function is the offline guarantee.

Cover EVERY outcome, each mapping precisely to a success criterion:
- email 1 hit -> outcome "match", contact_id equals the canned id, match_key "email" (P7-SC1, P7-SC2).
- email >1 hits -> outcome "ambiguous", candidate_ids has both ids, contact_id None (P7-SC3).
- email 0 hits (valid email) -> outcome "net_new", contact_id None (P7-SC3).
- no email + linkedin 1 hit -> outcome "match", match_key "linkedin_url" (P7-SC1).
- no email + linkedin >1 hits -> outcome "ambiguous" (P7-SC3).
- no email + no linkedin + phone+lastname hit -> outcome "ambiguous", match_key "phone_lastname", contact_id None - assert it is NEITHER "match" NOR "net_new" (P7-SC1).
- no email + no linkedin + no weak-key hits -> outcome "ambiguous", reason "no email, insufficient identity" - assert NOT "net_new". Give this THE HARD RULE its own dedicated test with a comment naming it the core safety property (P7-SC2).
- invalid email string (e.g. "not-an-email") with no other keys -> treated as the no-email path -> outcome "ambiguous" (not net_new) (P7-SC2).
- an offline/injection assertion: after a resolve, assert the mock stub recorded >=1 call (the resolver used the injected search, no network).
- resolve_batch over a small list of rows (one email-match row + one no-identity row) returns a list of IdentityResults in order with the expected outcomes (P7-SC3).

Do not import anthropic, read .env, or hit the network. Do not construct the real search_records.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_identity.py tests/ -q</automated>
  </verify>
  <done>tests/test_identity.py is green offline; every classification outcome (match via email, match via linkedin, ambiguous via multi-hit, ambiguous via weak key, ambiguous via no-identity hard rule, net_new via valid-email-zero-hits, invalid-email no-email path) is asserted against a mocked search; the injection/no-network assertion passes; resolve_batch order is proven; the full Milestone 1 + 2 suite (was 52 tests) has no regression.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| uploaded row -> resolve_identity | Untrusted, possibly crafted/mangled contact fields (bad email, spoofed name/company) cross into the classifier that decides match vs create |
| HubSpot search JSON -> _search_ids | External search response parsed into contact ids that drive the classification outcome |
| injected hs_search default -> hubspot_client.search_records | The real search reads HUBSPOT_PRIVATE_APP_TOKEN and hits the network when called; tests must never reach it |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-phase7-01 | Spoofing / Elevation | resolve_identity net_new vs ambiguous decision | high | mitigate | The HARD RULE (Task 2 step 5, Task 3 dedicated test): a row with no valid email can NEVER return net_new; only a validated email with 0 existing hits does. A mangled/no-email row that would otherwise trigger a Phase-8 auto-create is forced to ambiguous->review. Weak keys (phone+lastname, name+company) can never yield a confident match either - they only route to review. |
| T-phase7-02 | Tampering | wrong-record match (clobber risk) | medium | mitigate | Confident match requires exactly ONE hit on a STRONG key (email/linkedin_url); >1 hit -> ambiguous, never a silent pick. Identity keys are normalized (email lowercased/validated, phone E.164, linkedin host-lowercased/trailing-slash-stripped) before EQ search so trivial format variants do not mis-match or duplicate. |
| T-phase7-03 | Information Disclosure | test suite reaching real HubSpot | low | mitigate | hs_search is injected; every test passes a canned-dict stub, so no HUBSPOT token or network is used. The real search_records is only the default parameter value and is never constructed in tests; a call-recording stub asserts the injected search was used. |
| T-phase7-04 | Repudiation | opaque classification decisions | low | accept | Each IdentityResult carries match_key + candidate_ids + a reason string, giving downstream review a traceable record of why a row was matched/net_new/ambiguous. Full audit-note persistence is a later (writeback/n8n) milestone. |
</threat_model>

<verification>
## Gate (must pass - offline, no network, no API key, no HUBSPOT token)

Run from repo ROOT:
```
.venv/bin/python -m pytest tests/test_identity.py tests/ -q
```
The new identity tests AND the full Milestone 1 + Milestone 2 suite (scaffold, icp_scoring, merge_policy, main, classifier_parse, contact_normalizer, file_loader) must be green with no network. Green-offline + zero regression against the 52-test baseline is the hard gate.

Per-task inline `python -c ...` checks are fast self-contained smoke gates (inline stub searches); the pytest run above, driving the full mocked-search matrix, is the phase gate.
</verification>

<success_criteria>
- P7-SC1: resolve_identity tries email -> linkedin_url -> phone+lastname -> firstname+lastname+company IN ORDER; a single hit on email OR linkedin_url is a confident match returning the existing contact_id; weak keys alone are only ever ambiguous (never match).
- P7-SC2: a row with no valid email is NEVER net_new (routes to ambiguous/review); net_new is returned ONLY for a valid email with zero existing matches; the confident-match id is returned via the injected, mockable, offline search_records.
- P7-SC3: multiple candidate matches -> ambiguous (needs_review); zero matches + valid email -> net_new; EVERY outcome is unit-tested with a mocked HubSpot search, fully offline, with no regression to the existing suite.
</success_criteria>

<output>
Create `.planning/phases/phase-7/phase-7-01-SUMMARY.md` when done. Record: the final IdentityResult field set, the resolve_identity key order + the exact net_new condition (valid email + 0 email hits), the LinkedIn canonicalization rule chosen, the mock-search stub shape used in tests, confirmation that the HARD RULE (no-email-never-net_new) has its own dedicated test, and that `.venv/bin/python -m pytest tests/ -q` is green offline with no Milestone 1/2 regression.
</output>
