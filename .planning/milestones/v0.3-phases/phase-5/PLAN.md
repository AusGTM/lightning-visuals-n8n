---
phase: phase-5
plan: 01
type: execute
wave: 1
depends_on: [phase-4-01]
files_modified:
  - src/normalizer.py
  - config/provider_priority.yaml
  - config/source_registry.yaml
  - tests/fixtures/contact_current.json
  - tests/fixtures/provider_apollo_contact.json
  - tests/fixtures/provider_lusha_contact.json
  - tests/fixtures/provider_zoominfo_contact.json
  - tests/test_contact_normalizer.py
autonomous: true
requirements: [P5-SC1, P5-SC2, P5-SC3]
must_haves:
  truths:
    - "normalize_phone('0412 345 678') == '+61412345678' (region-aware AU default); normalize_phone('+14155552671') == '+14155552671' (already-E.164 passthrough); normalize_phone('abc') is None with NO exception raised (P5-SC1)."
    - "normalize_email('  Bob@Example.COM ') == 'bob@example.com' (strip + validate + full-lowercase); normalize_email('not-an-email') is None with NO exception raised, using check_deliverability=False so it is fully offline (P5-SC1)."
    - "normalize_seniority('VP Sales') == 'vp'; normalize_seniority('') == 'unknown'; every output is inside {c_suite, vp, director, manager, individual, unknown} (P5-SC1)."
    - "normalize_field() routes phone/mobilephone -> normalize_phone, email -> normalize_email, seniority -> normalize_seniority, jobtitle -> existing normalize_text fallback; all EXISTING company field routing (bool/revenue/employee/country/text) is byte-for-byte unchanged (P5-SC1)."
    - "All four contact fixtures parse: contact_current.json -> HubSpotRecord; the three provider_*_contact.json -> ProviderResult (object_type='contacts'), with conflicting jobtitle/phone/seniority across providers (P5-SC2)."
    - "provider_priority.yaml contacts covers email/linkedin_url/seniority/persona_group AND ranks lusha first for phone/mobilephone/email per source_registry §6.3 specialties; source_registry.yaml gains a csv source (type: upload, trust_rank ~60, can_promote_directly: false, note that per-upload trust is declarable) (P5-SC2)."
    - "`.venv/bin/python -m pytest tests/test_contact_normalizer.py tests/ -q` is green OFFLINE with no network — the new contact tests pass AND every Milestone 1 company test still passes (no regression) (P5-SC3)."
  artifacts:
    - src/normalizer.py
    - config/provider_priority.yaml
    - config/source_registry.yaml
    - tests/fixtures/contact_current.json
    - tests/fixtures/provider_apollo_contact.json
    - tests/fixtures/provider_lusha_contact.json
    - tests/fixtures/provider_zoominfo_contact.json
    - tests/test_contact_normalizer.py
  key_links:
    - "normalize_field(field, value) -> normalize_phone / normalize_email / normalize_seniority for contact keys; company keys keep routing to the existing normalizers (no behavior change)."
    - "provider_to_candidates -> normalize_field -> CandidateValue.normalized_value; on malformed phone/email normalized_value is None (the 'null') while the raw .value is preserved for Phase 8's merge layer to flag."
    - "provider_*_contact.json -> ProviderResult (unchanged schema, object_type=contacts) -> the candidate source that Phase 8 merges through the existing field-ownership classes."
---

<objective>
Make contact records first-class inputs to the already-shipped engine: extend the normalizer with contact-field coercion (phone -> E.164, email validate + lowercase, seniority -> canonical set), register the upload/CSV path as a real merge source, and ship contact fixtures — all proven by an offline test suite with zero regression to company scoring.

Purpose: Phase 5 is the foundation for Milestone 2 (contact ingestion). Everything downstream (file loader P6, identity resolver P7, contact enrichment + net-new create P8) depends on contacts normalizing cleanly and the upload being a declared source. No new subsystem is built here — this EXTENDS `src/normalizer.py` and two config files and adds fixtures/tests.
Output: extended `src/normalizer.py`, updated `config/provider_priority.yaml` + `config/source_registry.yaml`, four contact fixtures, and `tests/test_contact_normalizer.py` (the runnable proof).

Reuse, do NOT rebuild (confirmed against the current tree):
- `src/schemas.py` already supports contacts via `object_type: Literal["contacts","companies"]` — NO schema change; contact fixtures reuse `HubSpotRecord` / `ProviderResult` verbatim.
- `config/field_policy.yaml` already has the full `contacts:` block (email manual_protected, phone/mobilephone/linkedin_url fill_blank_only, jobtitle stale_refreshable, seniority/persona_group system_owned) — do NOT touch it.
- `config/provider_priority.yaml` `contacts:` block ALREADY lists all seven keys (jobtitle, phone, mobilephone, email, linkedin_url, seniority, persona_group) — the coverage half of P5-SC2 is already satisfied. The ONLY substantive edit is the lusha-specialty reordering below; do not add duplicate keys.
- `phonenumbers` and `email-validator` are already in requirements.txt and installed in `.venv` — import them, do NOT add dependencies. NO package-install task, so no supply-chain checkpoint is required.

Scope guard (out of scope — belongs to Phases 6-8, do NOT build): file loading, column mapping, identity/dedupe resolution, `main.py` wiring, and any consumption of the malformed 'flag' downstream. Phase 5 returns None on malformed input; the explicit flag surfacing lives in Phase 8's merge. One plan file only.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@src/schemas.py
@src/normalizer.py
@config/field_policy.yaml
@config/provider_priority.yaml
@config/source_registry.yaml
@tests/fixtures/provider_apollo_company.json
@tests/test_icp_scoring.py

# CLAUDE.md sections for reference: §8.1/§8.2 (contact staging + metadata fields),
# §6.3 (source_registry + provider supported_signals), §16 (provider adapter contract).
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend src/normalizer.py with contact-field normalizers + dispatch</name>
  <files>src/normalizer.py</files>
  <behavior>
    Pure functions, deterministic, offline, never raise on bad input:
    - normalize_phone('0412 345 678') -> '+61412345678'   (region='AU' default via phonenumbers.parse; is_valid_number True; format E164)
    - normalize_phone('+14155552671') -> '+14155552671'    (leading + overrides region; passes through unchanged)
    - normalize_phone('abc') -> None                        (phonenumbers.NumberParseException caught)
    - normalize_phone('') / normalize_phone(None) -> None   (guarded before parse)
    - normalize_email('  Bob@Example.COM ') -> 'bob@example.com'  (strip, validate_email(check_deliverability=False), take .normalized, then .lower())
    - normalize_email('not-an-email') -> None               (EmailNotValidError caught)
    - normalize_email('') / normalize_email(None) -> None   (guarded)
    - normalize_seniority('VP Sales') -> 'vp'; 'Chief Revenue Officer'/'CEO' -> 'c_suite'; 'Head of Growth'/'Sales Manager' -> 'manager'; 'Director of Ops' -> 'director'; 'Account Executive'/'Analyst' -> 'individual'; '' / None / no-keyword-match -> 'unknown'. Output is always one of {c_suite, vp, director, manager, individual, unknown}.
    - normalize_field('phone', x) and ('mobilephone', x) -> normalize_phone(x); ('email', x) -> normalize_email(x); ('seniority', x) -> normalize_seniority(x). All existing company branches unchanged; company outputs identical to before.
  </behavior>
  <action>
Extend `src/normalizer.py` (do not rewrite; append the new functions and add dispatch branches). Import at top: `import phonenumbers` and `from email_validator import validate_email, EmailNotValidError`.

Add normalize_phone(value, region="AU"): if not value, return None. Wrap phonenumbers.parse(value, region) in try/except phonenumbers.NumberParseException returning None; if the parsed number fails phonenumbers.is_valid_number, return None; else return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164). The region default is AU per the ANZ ICP; a leading '+' in the value makes phonenumbers ignore region, giving international passthrough — both paths must be covered by tests.

Add normalize_email(value): if not value, return None. Strip whitespace first (email-validator does NOT tolerate surrounding spaces). Wrap `validate_email(stripped, check_deliverability=False)` in try/except EmailNotValidError returning None. IMPORTANT: pass check_deliverability=False so there is NO DNS/network call — this keeps the suite offline. Return `result.normalized.lower()` (.normalized lowercases the domain; the explicit .lower() also lowercases the local part so 'Bob@Example.COM' -> 'bob@example.com', matching the CRM dedupe convention).

Add normalize_seniority(value): lowercase the trimmed string, then keyword-map to the canonical set in priority order (check c-suite/chief markers before 'vp', 'vp'/'vice president' before director/manager, etc.). Return 'unknown' for empty/None/unmatched. Keep it a simple ordered keyword scan — no ML, no external calls.

Wire dispatch in normalize_field() by adding branches BEFORE the final `return normalize_text(value)`: phone and mobilephone -> normalize_phone; email -> normalize_email; seniority -> normalize_seniority. Do NOT add a jobtitle branch — the existing normalize_text fallback already trims and collapses whitespace, which is exactly the required jobtitle normalization; a dedicated normalize_jobtitle would be redundant (leave a one-line comment noting jobtitle is handled by the fallback so no future reader re-adds it).

Do NOT alter normalize_bool / normalize_revenue_band / normalize_employee_band / normalize_country_region / normalize_text / provider_to_candidates or any existing company branch. Contact keys (phone/email/seniority) never collide with company provider data, so the 16 scoring tests and merge tests stay green.
  </action>
  <verify>
    <automated>.venv/bin/python -c "from src.normalizer import normalize_phone, normalize_email, normalize_seniority, normalize_field; assert normalize_phone('0412 345 678')=='+61412345678'; assert normalize_phone('+14155552671')=='+14155552671'; assert normalize_phone('abc') is None; assert normalize_email('  Bob@Example.COM ')=='bob@example.com'; assert normalize_email('not-an-email') is None; assert normalize_seniority('VP Sales')=='vp'; assert normalize_seniority('') =='unknown'; assert normalize_field('phone','0412 345 678')=='+61412345678'; assert normalize_field('email','X@Y.COM')=='x@y.com'; assert normalize_field('lv_revenue_band',12000000)=='5-50M'; print('OK')"</automated>
  </verify>
  <done>All branches (valid / malformed / empty) return the expected value or None without raising; normalize_field dispatches contact keys correctly; company branch outputs unchanged (lv_revenue_band spot-check still '5-50M').</done>
</task>

<task type="auto">
  <name>Task 2: Register upload source + lusha-specialty reordering (config)</name>
  <files>config/provider_priority.yaml, config/source_registry.yaml</files>
  <action>
In `config/source_registry.yaml`, add ONE new source under `sources:` keyed `csv`: `type: upload`, `trust_rank: 60` (moderate — below providers, above nothing), `can_promote_directly: false`, a `notes:` line stating the value comes from an uploaded file (CSV/XLSX/JSON) and that per-upload trust is DECLARABLE (a trusted internal export can be raised, an unknown scrape lowered) and it always merges through field-ownership governance rather than promoting canonical directly, and a `supported_signals:` list (email, firstname, lastname, jobtitle, phone, company, linkedin_url). Do not add a second near-identical `upload` entry — one `csv` source with `type: upload` covers the requirement.

In `config/provider_priority.yaml` `contacts:` block: the four keys email/linkedin_url/seniority/persona_group are ALREADY present (coverage is already met) — do NOT add duplicates. The only edit is to reorder the three contact-identity fields so lusha (the direct-dial / mobile / email specialist per source_registry §6.3 supported_signals: phone, mobilephone, email) leads: set `phone: [lusha, zoominfo, apollo, claude_web]`, `mobilephone: [lusha, zoominfo, apollo, claude_web]`, `email: [lusha, apollo, zoominfo, claude_web]`. Leave jobtitle/linkedin_url/seniority/persona_group as `[zoominfo, apollo, lusha, claude_web]` (zoominfo is strong on title/seniority). Update the file's header comment: it currently claims every field uses `[zoominfo, apollo, lusha, claude_web]`; amend it to note the phone/mobilephone/email contact-identity exception where lusha leads, so the comment no longer contradicts the data. The merge policy reads per-field lists and only falls back to `[zoominfo, apollo, lusha, claude_web]` when a field is absent, so these explicit per-field orders are honored without any code change.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import yaml; sr=yaml.safe_load(open('config/source_registry.yaml')); csv=sr['sources']['csv']; assert csv['type']=='upload' and csv['can_promote_directly'] is False and isinstance(csv['trust_rank'],int); pp=yaml.safe_load(open('config/provider_priority.yaml'))['contacts']; assert {'email','linkedin_url','seniority','persona_group'} <= set(pp); assert pp['phone'][0]=='lusha' and pp['mobilephone'][0]=='lusha' and pp['email'][0]=='lusha'; print('OK')"</automated>
  </verify>
  <done>source_registry has a csv source (type upload, can_promote_directly false, declarable-trust note, supported_signals); provider_priority contacts covers the four keys and ranks lusha first for phone/mobilephone/email; both YAMLs still parse.</done>
</task>

<task type="auto">
  <name>Task 3: Contact fixtures (current + Apollo/Lusha/ZoomInfo)</name>
  <files>tests/fixtures/contact_current.json, tests/fixtures/provider_apollo_contact.json, tests/fixtures/provider_lusha_contact.json, tests/fixtures/provider_zoominfo_contact.json</files>
  <action>
Create four JSON fixtures mirroring the shape of the existing company fixtures (tests/fixtures/company_current.json and provider_apollo_company.json), but with object_type "contacts". Use SYNTHETIC data only — example.com / example.test domains and non-real phone numbers (no real personal data).

contact_current.json: `object_type` "contacts", `id` "123", `properties` with a REAL-ish contact: email (present, e.g. "bob.smith@example.com" — manual_protected, so later phases can prove it is never clobbered), firstname "Bob", lastname "Smith", jobtitle "Sales Manager" (present, so stale_refreshable conflict can be shown later), phone "" (blank — so fill_blank_only can be shown filling it later), plus enrichment control props enrichment_requested "true" / enrichment_status "queued" to match the company fixture convention.

The three provider fixtures each: `provider` (apollo|lusha|zoominfo), `object_type` "contacts", `matched` true, a plausible `confidence` int, an `evidence` block (last_seen, match_basis, evidence_urls) like the company provider fixtures, and a `data` block with CONFLICTING contact fields so Phase 8 can demonstrate merge/conflict:
- apollo: jobtitle "VP of Sales", seniority "vp", phone "+61 2 5550 1234", email "bob.smith@example.com", linkedin_url "https://linkedin.com/in/bobsmith"
- zoominfo: jobtitle "Director of Sales", seniority "director", phone "0412 345 678", mobilephone "0400 111 222"
- lusha: mobilephone "+61 400 999 888", phone "+61 2 5550 9999", email "b.smith@example.com" (note the jobtitle/seniority disagreement between apollo and zoominfo, and phone/mobile spread across lusha — this is the intentional conflict set)
Each MUST parse into ProviderResult (and contact_current into HubSpotRecord) with no extra/renamed keys.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import json; from src.schemas import HubSpotRecord, ProviderResult; HubSpotRecord(**json.load(open('tests/fixtures/contact_current.json'))); [ProviderResult(**json.load(open(f'tests/fixtures/provider_{p}_contact.json'))) for p in ['apollo','lusha','zoominfo']]; print('OK')"</automated>
  </verify>
  <done>contact_current.json parses into HubSpotRecord (object_type contacts, email present, phone blank); the three provider fixtures parse into ProviderResult with conflicting jobtitle/phone/seniority; all synthetic data.</done>
</task>

<task type="auto">
  <name>Task 4: tests/test_contact_normalizer.py (runnable proof)</name>
  <files>tests/test_contact_normalizer.py</files>
  <action>
Author `tests/test_contact_normalizer.py` — plain pytest, plain asserts, fully OFFLINE (no network, no API key), mirroring the style of tests/test_icp_scoring.py. Load fixtures cwd-relative (the suite runs from repo root). Cover every normalizer branch and the fixture-parse contract:

Phone: assert normalize_phone('0412 345 678') == '+61412345678' (AU local); assert normalize_phone('+14155552671') == '+14155552671' (international passthrough); assert normalize_phone('abc') is None (malformed, no raise); assert normalize_phone('') is None and normalize_phone(None) is None.
Email: assert normalize_email('  Bob@Example.COM ') == 'bob@example.com'; assert normalize_email('not-an-email') is None; assert normalize_email('') is None. (Rely on check_deliverability=False inside normalize_email so the test needs no DNS.)
Seniority: assert normalize_seniority('VP Sales') == 'vp'; assert normalize_seniority('') == 'unknown'; assert normalize_seniority('Chief Revenue Officer') == 'c_suite'; assert every returned value is in the canonical set.
Dispatch: assert normalize_field('phone', '0412 345 678') == '+61412345678'; assert normalize_field('email', 'X@Y.COM') == 'x@y.com'; assert normalize_field('seniority', 'VP Sales') == 'vp'.
No-regression spot check: assert normalize_field('lv_revenue_band', 12000000) == '5-50M' (company path still intact).
Fixture parse: a test that loads all four contact fixtures and constructs HubSpotRecord / ProviderResult (proves P5-SC2's parse claim inside the suite).

Do not import anthropic, do not read .env, do not hit the network.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_contact_normalizer.py -q</automated>
  </verify>
  <done>tests/test_contact_normalizer.py is green; every normalizer branch (valid / malformed / empty) and the four-fixture parse are asserted offline.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| provider / upload contact data -> normalizer | Untrusted, possibly malformed phone/email (PII) crosses into pure normalization functions |
| fixtures / repo -> git history | Test data (emails, phone numbers) is committed to the repo |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-phase5-01 | Denial of Service | normalize_phone / normalize_email | medium | mitigate | Both functions guard empty/None and wrap the parse in try/except (NumberParseException / EmailNotValidError), returning None instead of raising; unit tests assert 'abc' and 'not-an-email' -> None with no exception, so one malformed row can never crash a later batch run. |
| T-phase5-02 | Information Disclosure | committed contact fixtures | low | mitigate | Fixtures use only synthetic data (example.com/example.test domains, non-real numbers); no real PII enters git; normalizers do not log raw values. |
| T-phase5-03 | Information Disclosure | email deliverability check | low | mitigate | normalize_email passes check_deliverability=False — no DNS lookup, so a contact's domain is never exfiltrated to a resolver and the suite stays fully offline. |
| T-phase5-SC | Tampering | dependency supply chain | low | accept | No new packages are installed this phase — phonenumbers>=8.13.40 and email-validator>=2.2.0 are already pinned in requirements.txt and vendored in .venv; no install task, so no new supply-chain surface is opened. |
</threat_model>

<verification>
## Gate (must pass — offline, no network, no API key)

Run from repo ROOT:
```
.venv/bin/python -m pytest tests/test_contact_normalizer.py tests/ -q
```
The new contact tests AND the full Milestone 1 suite (scaffold + icp_scoring + merge_policy + main + classifier_parse) must be green with no network. Green-offline + zero company regression is the hard gate.

Per-task inline checks (`python -c ...`) in each task's <verify> are fast smoke gates; the pytest run above is the phase gate.
</verification>

<success_criteria>
- P5-SC1: normalize_phone (E.164, AU default, international passthrough, malformed -> None), normalize_email (validate + lowercase, invalid -> None), normalize_seniority (canonical set) exist and are wired into normalize_field; malformed input yields None, never a crash.
- P5-SC2: four contact fixtures parse into the existing schemas; provider_priority contacts covers email/linkedin_url/seniority/persona_group and ranks lusha first for phone/mobilephone/email; source_registry has a csv source (type upload, can_promote_directly false, declarable trust).
- P5-SC3: tests/test_contact_normalizer.py proves each branch (valid / malformed / empty) deterministically offline, and the full suite stays green (no company regression).
</success_criteria>

<output>
Create `.planning/phases/phase-5/phase-5-01-SUMMARY.md` when done. Record: the final normalize_seniority keyword map, the exact provider_priority contact ordering after the lusha reorder, and confirmation that `.venv/bin/python -m pytest tests/ -q` is green offline with the company suite unregressed.
</output>
