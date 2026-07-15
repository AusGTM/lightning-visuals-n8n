---
phase: phase-6
plan: 01
type: execute
wave: 1
depends_on: [phase-5-01]
files_modified:
  - requirements.txt
  - src/file_loader.py
  - src/column_mapper.py
  - src/schemas.py
  - config/column_mapping.yaml
  - tests/fixtures/uploads/contacts.csv
  - tests/fixtures/uploads/contacts.json
  - tests/test_file_loader.py
autonomous: false
requirements: [P6-SC1, P6-SC2, P6-SC3]
user_setup: []
must_haves:
  truths:
    - "load_rows(path) auto-detects format by file extension: .csv/.tsv -> csv.DictReader (utf-8-sig), .json -> stdlib json (top-level list OR {'contacts':[...]} OR {'rows':[...]}), .xlsx/.xls -> openpyxl; all return list[dict]; an unsupported extension raises ValueError (P6-SC1)."
    - "A CSV exported with a UTF-8 BOM parses via utf-8-sig so the first header maps correctly (e.g. maps to 'email', NOT a stray '\\ufeffEmail Address' key) (P6-SC1)."
    - "map_row(raw_row, mapping) maps arbitrary source headers (case-insensitive, whitespace-trimmed) to canonical HubSpot contact props (email, firstname, lastname, phone, jobtitle, company, linkedin_url) via config/column_mapping.yaml aliases; unmapped columns are dropped; non-string headers (csv restkey None / xlsx blank header) are skipped without crashing (P6-SC2)."
    - "ingest_file(path) -> IngestBatch returns BOTH accepted canonical rows and a structured rejects list; a row yielding neither email NOR (firstname+lastname+company) lands in rejects with row_index + reason 'no identity key' and is NEVER silently dropped (P6-SC2, P6-SC3)."
    - "The three fixtures (contacts.csv, contacts.json, contacts.xlsx generated in-test) each ingest to the SAME two accepted canonical rows and the SAME one reject, proving one interface behind three formats; Phase 6 does NOT normalize values (phone stays the raw '0412 345 678', not E.164) (P6-SC1, P6-SC3)."
    - "`.venv/bin/python -m pytest tests/test_file_loader.py tests/ -q` is green OFFLINE with no network; openpyxl is pinned in requirements.txt and installed in .venv; the full Milestone 1 + Milestone 2 suite has no regression (P6-SC3)."
  artifacts:
    - src/file_loader.py
    - src/column_mapper.py
    - config/column_mapping.yaml
    - src/schemas.py
    - tests/fixtures/uploads/contacts.csv
    - tests/fixtures/uploads/contacts.json
    - tests/test_file_loader.py
  key_links:
    - "load_rows dispatches on Path(path).suffix.lower() to private _load_csv / _load_json / _load_xlsx; the extension is the only format signal (no content sniffing)."
    - "ingest_file: load_rows(path) -> per-row map_row(row, mapping) -> _has_identity(mapped) -> IngestBatch.rows (accepted) | IngestBatch.rejects (RejectedRow with row_index+reason); every per-row step is wrapped so one bad row can never crash the batch."
    - "RejectedRow + IngestBatch live in src/schemas.py (the codebase's pydantic home); Phase 7 consumes IngestBatch.rows for identity resolution and Phase 8 turns rows into CandidateValue(s) — Phase 6 stops at parse+map+reject and does not resolve identity or normalize field values."
    - "config/column_mapping.yaml holds BOTH the alias table (aliases:) and the required-identity rule (required_identity: any_of) so there is one source of truth; ingest_file reads required_identity, map_row reads aliases."
---

<objective>
Turn any CSV / XLSX / JSON upload into normalized candidate rows mapped to canonical HubSpot contact properties, behind one interface, with malformed rows collected into a structured per-row reject report. This is the ingestion front-door for Milestone 2: Phase 7 (identity resolution) and Phase 8 (contact enrichment + net-new create) both consume the accepted rows this phase produces.

Purpose: A file/upload is "just another source" in the already-shipped merge engine. Before a row can become a CandidateValue (Phase 8) or be matched to a HubSpot contact (Phase 7), it must be parsed from three file shapes into a common row shape and have arbitrary spreadsheet headers mapped onto the fixed HubSpot property names. Phase 6 delivers exactly that — parse, map, reject-malformed — and nothing more.

Output: new src/file_loader.py (load_rows dispatch + ingest_file entrypoint), new src/column_mapper.py (map_row + config-driven alias table), new config/column_mapping.yaml, two small typed models appended to src/schemas.py (RejectedRow, IngestBatch), committed CSV + JSON fixtures, and tests/test_file_loader.py (the runnable, offline proof; the .xlsx fixture is generated in-test for determinism).

Reuse, do NOT rebuild (confirmed against the current tree):
- stdlib does csv/tsv (csv.DictReader) and json (json.load) — do NOT add pandas. openpyxl is the ONLY new dependency and only because .xlsx has no stdlib reader.
- src/schemas.py is pydantic and is the home for typed models — APPEND RejectedRow + IngestBatch there; do NOT invent a parallel models file.
- src/normalizer.py already normalizes field VALUES — do NOT call it here. Phase 6 is parse + map + reject only; value normalization (phone -> E.164, email lowercase) happens later when rows become candidates in Phase 8. The fixtures deliberately keep raw values (e.g. phone "0412 345 678") to prove Phase 6 does not normalize.
- config/source_registry.yaml already registers the csv/upload source (Phase 5) and config/field_policy.yaml already governs the contact fields — do NOT touch either.

Scope guard (out of scope — belongs to Phases 7-8, do NOT build): identity/dedupe resolution, HubSpot search, value normalization, main.py wiring, CandidateValue construction, net-new create. Phase 6 hands Phase 7 a clean list of mapped rows plus a reject report. Single plan file.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@src/schemas.py
@config/field_policy.yaml

# Reference (do not re-read wholesale): src/normalizer.py shows the Phase 8 boundary
# (value normalization lives THERE, not here). CLAUDE.md §8.1 lists canonical contact
# props; §11 shows the local MVP layout; §29 is the MVP scope cut.
</context>

<tasks>

<task type="checkpoint:human-verify" gate="blocking-human">
  <name>Task 1: Supply-chain gate — verify openpyxl before install</name>
  <what-built>Phase 6 adds exactly one new dependency: openpyxl, the only reader for .xlsx/.xls uploads (stdlib already covers csv/tsv/json; pandas is deliberately avoided as overkill). Nothing is installed and requirements.txt is not touched until this gate is approved.</what-built>
  <how-to-verify>
    1. Open https://pypi.org/project/openpyxl/ and confirm it is the maintained, widely-used spreadsheet library (millions of monthly downloads, recent releases) — not a typosquat or abandoned fork.
    2. Confirm the intended pin is `openpyxl>=3.1.2` (current stable 3.1.x line).
    3. Confirm the only runtime transitive dependency is `et-xmlfile` (long-established) — no surprising extra packages.
  </how-to-verify>
  <resume-signal>Type "approved" to allow `openpyxl>=3.1.2` into requirements.txt and .venv, or name a different pin/alternative.</resume-signal>
</task>

<task type="auto">
  <name>Task 2: src/file_loader.py load_rows() — three readers behind one extension-dispatched interface</name>
  <files>requirements.txt, src/file_loader.py</files>
  <action>
First add `openpyxl>=3.1.2` to requirements.txt and install it into the venv (`.venv/bin/pip install "openpyxl>=3.1.2"`) — approved in Task 1.

Create src/file_loader.py with ONE public dispatcher `load_rows(path: str) -> list[dict]` plus three thin private readers. Dispatch on `Path(path).suffix.lower()` only (extension is the format signal; no content sniffing): `.csv`/`.tsv` -> `_load_csv`, `.json` -> `_load_json`, `.xlsx`/`.xls` -> `_load_xlsx`, anything else -> raise ValueError naming the unsupported extension.

_load_csv(path): open with `newline=""` and `encoding="utf-8-sig"` (utf-8-sig transparently strips an Excel-exported BOM so the first header is clean). Use `csv.DictReader`, delimiter `"\t"` when the extension is `.tsv` else `","`. Return `[dict(row) for row in reader]`. Do NOT drop or rename columns here — the mapper decides that later. A row with extra columns (DictReader restkey None) or blank trailing columns must not crash; leave the raw dict as-is (the mapper guards the None key).

_load_json(path): `json.load` the file. If the top level is a list, return it. If it is a dict, return the first present list among keys "contacts" then "rows"; if neither is a list, raise ValueError describing the unrecognized shape. (Elements are returned as-is; ingest_file handles any non-dict element defensively.)

_load_xlsx(path): `from openpyxl import load_workbook`; open with `read_only=True, data_only=True` (data_only reads cached values not formulas; read_only bounds memory). Take `wb.active`, iterate `ws.iter_rows(values_only=True)`. The first row is the header — stringify each header cell (None header -> ""). Skip any subsequent row where every cell is None (fully blank). For each data row build a dict zipping headers to values, coercing a None cell value to "" so a blank xlsx cell matches a blank csv/json field (keeps the three formats byte-equal for the same logical input). Close the workbook. Return the list.

Keep the readers thin; no normalization, no mapping, no validation of values.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import tempfile,os,json; from src.file_loader import load_rows; d=tempfile.mkdtemp(); cp=os.path.join(d,'a.csv'); open(cp,'w',encoding='utf-8-sig').write('Email,First Name\nx@y.com,Al\n'); jp=os.path.join(d,'a.json'); json.dump([{'email':'x@y.com'}], open(jp,'w')); wp=os.path.join(d,'w.json'); json.dump({'contacts':[{'email':'z@y.com'}]}, open(wp,'w')); assert load_rows(cp)==[{'Email':'x@y.com','First Name':'Al'}], load_rows(cp); assert load_rows(jp)==[{'email':'x@y.com'}]; assert load_rows(wp)==[{'email':'z@y.com'}]; 
try:
    load_rows(os.path.join(d,'a.txt')); raise SystemExit('no ValueError')
except ValueError: pass
print('OK')"</automated>
  </verify>
  <done>load_rows dispatches csv (utf-8-sig strips the BOM so the first header is a clean 'Email' with no leading BOM codepoint), json list, and wrapped json {'contacts':[...]} to list[dict]; unknown extension raises ValueError; openpyxl pinned in requirements.txt and importable in .venv.</done>
</task>

<task type="auto">
  <name>Task 3: config/column_mapping.yaml + src/column_mapper.py — alias table and map_row()</name>
  <files>config/column_mapping.yaml, src/column_mapper.py</files>
  <action>
Create config/column_mapping.yaml with two top-level keys:
- `aliases:` — a flat map of lowercased, trimmed source header -> canonical HubSpot contact property. Cover all seven canonical props with sensible default aliases INCLUDING the identity self-mapping (so already-canonical headers map to themselves): email <- email, "email address", "e-mail"; firstname <- firstname, "first name", fname, "given name"; lastname <- lastname, "last name", surname; jobtitle <- jobtitle, "job title", title, position; linkedin_url <- linkedin_url, linkedin, "linkedin url", li; phone <- phone, mobile, tel; company <- company, organization, organisation, account.
- `required_identity:` with a single sub-key `any_of:` listing the acceptable identity key groups: `[[email], [firstname, lastname, company]]`. This is the one source of truth for the reject rule (matches Phase 7's identity keys: email OR name+company).

Create src/column_mapper.py with `map_row(raw_row: dict, mapping: dict) -> dict`. Accept either the whole loaded yaml or just its aliases sub-map (`aliases = mapping.get("aliases", mapping)`). Iterate raw_row items; SKIP any key that is not a str (csv DictReader restkey None, or an xlsx blank header) so a malformed header never raises. Normalize each source header the same way the yaml keys are stored — trim, collapse internal whitespace, lowercase — and look it up in aliases; if found, set `out[canonical] = value`; if not found, drop the column. Return the canonical-keyed dict. No value normalization, no required-key logic here (that is ingest_file's job) — map_row is a pure header remap.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import yaml; from src.column_mapper import map_row; m=yaml.safe_load(open('config/column_mapping.yaml')); out=map_row({'Email Address':'x@y.com','  First Name ':'Al','Notes':'drop','LinkedIn':'https://li/x', None:['extra']}, m); assert out=={'email':'x@y.com','firstname':'Al','linkedin_url':'https://li/x'}, out; assert 'Notes' not in out and 'notes' not in out; assert m['required_identity']['any_of']==[['email'],['firstname','lastname','company']]; print('OK')"</automated>
  </verify>
  <done>map_row maps case-insensitive/trimmed headers to canonical props, drops unmapped columns, skips the None restkey without crashing; column_mapping.yaml carries both aliases and the required_identity any_of rule; yaml parses.</done>
</task>

<task type="auto">
  <name>Task 4: IngestBatch/RejectedRow models + ingest_file() load->map->split entrypoint</name>
  <files>src/schemas.py, src/file_loader.py</files>
  <action>
Append two small pydantic models to src/schemas.py (do not disturb existing models): `RejectedRow` with fields `row_index: int`, `reason: str`, `raw: Dict[str, Any]` (default empty); and `IngestBatch` with `rows: List[Dict[str, Any]]` (accepted canonical rows) and `rejects: List[RejectedRow]`, both defaulting empty.

Add the combined entrypoint `ingest_file(path: str) -> IngestBatch` to src/file_loader.py. Load config/column_mapping.yaml from the repo-root-relative path "config/column_mapping.yaml" (matches the existing convention used by icp_scoring.py / merge_policy.py). Read `required_identity` from it. Call `load_rows(path)`; enumerate the raw rows with a 0-based index (over data rows returned by load_rows — the csv/xlsx header is already excluded). For each raw row, inside a try/except so one bad row can never crash the batch:
- if the raw row is not a dict, append a RejectedRow(row_index=i, reason="row is not an object", raw={"value": <repr-safe>}) and continue;
- map it via map_row(raw_row, mapping);
- test identity with a small helper `_has_identity(mapped, required)` that returns True when, for some group in required["any_of"], every key in that group is present and non-empty (value not in (None, "")); if identity fails, append RejectedRow(row_index=i, reason="no identity key", raw=raw_row) and continue;
- otherwise append the mapped dict to accepted rows.
On an unexpected exception, append RejectedRow(row_index=i, reason=f"parse error: {e}", raw=<the raw row if a dict else {"value": ...}>). Return IngestBatch(rows=accepted, rejects=rejects). Import map_row and the two models at the top of file_loader.py.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import tempfile,os; from src.file_loader import ingest_file; d=tempfile.mkdtemp(); p=os.path.join(d,'c.csv'); open(p,'w',encoding='utf-8-sig').write('Email Address,First Name,Last Name,Company,Phone,Notes\na@ex.com,Al,An,Acme,0412 345 678,n1\n,Bo,Ba,Beta,0400 111 222,n2\n,,,,0400 222 333,n3\n'); b=ingest_file(p); assert len(b.rows)==2, b.rows; assert b.rows[0]=={'email':'a@ex.com','firstname':'Al','lastname':'An','company':'Acme','phone':'0412 345 678'}, b.rows[0]; assert len(b.rejects)==1 and b.rejects[0].reason=='no identity key' and b.rejects[0].row_index==2, b.rejects; print('OK')"</automated>
  </verify>
  <done>ingest_file returns a typed IngestBatch: two accepted rows (one via email, one via firstname+lastname+company), one reject with reason 'no identity key' and row_index 2; unmapped 'Notes' dropped; phone value left raw (unnormalized); no exception on the empty row.</done>
</task>

<task type="auto">
  <name>Task 5: Fixtures (csv + json, xlsx generated in-test) + tests/test_file_loader.py</name>
  <files>tests/fixtures/uploads/contacts.csv, tests/fixtures/uploads/contacts.json, tests/test_file_loader.py</files>
  <action>
Create tests/fixtures/uploads/ with two committed fixtures carrying the SAME three logical rows (2 accepted + 1 reject), using only SYNTHETIC data (example.com domains, non-real phone numbers):
- Row A (accepted via email): email "alice@example.com", firstname "Alice", lastname "Anderson", jobtitle "Sales Manager", phone "0412 345 678", company "Example Racing League", linkedin_url "https://linkedin.com/in/alice".
- Row B (accepted via name+company, blank email): email "", firstname "Bob", lastname "Baker", jobtitle "Analyst", phone "0400 111 222", company "Example Media Co", linkedin_url "https://linkedin.com/in/bob".
- Row C (reject, no identity): email "", firstname "", lastname "", company "", jobtitle "Coordinator", phone "0400 222 333", linkedin_url "".

contacts.csv: write it WITH a UTF-8 BOM and MESSY/aliased headers to exercise mapping — e.g. "Email Address,First Name,Last Name,Job Title,Phone,Company,LinkedIn,Notes" — where "Notes" is an extra UNMAPPED column (proves unmapped columns are dropped). Keep phone values as the raw strings above.

contacts.json: a top-level list of the same three rows using canonical (or lightly-aliased) keys; keep email "" present on Row B and Row C so the mapped rows match the csv exactly.

Do NOT commit a .xlsx binary (openpyxl embeds a nondeterministic created-timestamp). Instead, in tests/test_file_loader.py add a pytest fixture that WRITES contacts.xlsx into tmp_path via openpyxl from the same header row + three data rows (all string cells, blank cell = empty string), and yields its path. This keeps the xlsx deterministic and out of git.

Author tests/test_file_loader.py — plain pytest, plain asserts, fully OFFLINE (no network, no API key), fixtures loaded cwd-relative from repo root, mirroring the style of tests/test_contact_normalizer.py:
- same_rows_across_formats: ingest contacts.csv, contacts.json, and the generated contacts.xlsx; assert each yields exactly the two accepted canonical rows AND they are equal across all three formats (one interface, three formats). Assert Row A's mapped dict has no 'Notes'/'notes' key (unmapped dropped) and phone is still "0412 345 678" (Phase 6 does not normalize).
- required_key_missing_rejected: for each format, assert Row C is in rejects with reason "no identity key" and the correct row_index, and is NOT in accepted rows (never silently dropped).
- bom_parsed: assert the BOM csv's first canonical key is 'email' (BOM stripped; otherwise the header would not alias-match).
- unsupported_extension: assert load_rows on a ".txt" path raises ValueError.
Do not import anthropic, read .env, or hit the network.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_file_loader.py tests/ -q</automated>
  </verify>
  <done>tests/test_file_loader.py is green offline; all three formats ingest to the same two accepted rows and the same one reject (row_index + reason); unmapped columns dropped; BOM csv parses; unsupported extension raises; the full Milestone 1 + 2 suite is unregressed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| uploaded file -> load_rows/ingest_file | Untrusted file content: arbitrary/messy headers, blank/extra columns, non-object rows, possibly PII, crosses into the parser |
| new dependency openpyxl -> runtime | Third-party package added to the supply chain to read .xlsx |
| committed upload fixtures -> git history | Test contact data (emails, phone numbers) is stored in the repo |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-phase6-SC | Tampering | openpyxl dependency (supply chain) | high | mitigate | Blocking-human supply-chain checkpoint (Task 1) verifies openpyxl on pypi.org before any install; pin `openpyxl>=3.1.2` in requirements.txt; no pandas (stdlib covers csv/tsv/json); only transitive dep is the established et-xmlfile. |
| T-phase6-01 | Denial of Service | ingest_file per-row loop | medium | mitigate | Each row is mapped/validated inside try/except; a non-dict row or a malformed header (skipped by map_row's non-str-key guard) becomes a RejectedRow instead of an exception, so one bad row can never crash a multi-row batch. Test drives an empty/no-identity row and asserts it lands in rejects. |
| T-phase6-02 | Information Disclosure | committed contacts.csv / contacts.json fixtures | low | mitigate | Fixtures use only synthetic data (example.com domains, non-real numbers); no real PII enters git; the loader does not log raw row values. |
| T-phase6-03 | Denial of Service | _load_xlsx parsing an untrusted workbook | low | accept | openpyxl opened `read_only=True` (bounds memory) and `data_only=True` (no formula evaluation); it does not resolve external XML entities by default. POC uploads are operator-supplied/trusted; a hardened untrusted-upload path is deferred to production intake. |
</threat_model>

<verification>
## Gate (must pass — offline, no network, no API key)

Run from repo ROOT:
```
.venv/bin/python -m pytest tests/test_file_loader.py tests/ -q
```
The new file-loader tests AND the full Milestone 1 + Milestone 2 suite (scaffold, icp_scoring, merge_policy, main, classifier_parse, contact_normalizer) must be green with no network. Green-offline + zero regression is the hard gate.

Per-task inline `python -c ...` checks are fast smoke gates that use tempfiles (self-contained); the pytest run above, driving the committed + generated fixtures, is the phase gate.
</verification>

<success_criteria>
- P6-SC1: load_rows reads CSV, TSV, XLSX, and JSON into a common list[dict] behind one interface, format auto-detected by extension; BOM CSV parses; unsupported extension raises; all three fixtures ingest to the same accepted rows.
- P6-SC2: config/column_mapping.yaml maps arbitrary source headers -> canonical HubSpot props (email, firstname, lastname, phone, jobtitle, company, linkedin_url); map_row drops unmapped columns; ingest_file rejects rows missing the required identity key (email OR firstname+lastname+company).
- P6-SC3: malformed/rejected rows are collected into a structured per-row report (RejectedRow: row_index + reason) inside a typed IngestBatch and are never silently dropped; the whole suite stays green offline with no regression.
</success_criteria>

<output>
Create `.planning/phases/phase-6/phase-6-01-SUMMARY.md` when done. Record: the openpyxl pin that was approved and installed, the final column_mapping.yaml alias table + required_identity rule, the ingest_file row_index convention (0-based over data rows), the decision to generate contacts.xlsx in-test (no committed binary), and confirmation that `.venv/bin/python -m pytest tests/ -q` is green offline with no Milestone 1/2 regression.
</output>
