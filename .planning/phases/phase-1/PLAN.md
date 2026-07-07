---
phase: phase-1
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - config/icp_scoring.yaml
  - config/field_policy.yaml
  - config/source_registry.yaml
  - config/provider_priority.yaml
  - config/escalation_policy.yaml
  - requirements.txt
  - .env.example
  - src/__init__.py
  - src/schemas.py
  - tests/__init__.py
  - tests/fixtures/company_current.json
  - tests/fixtures/claude_web_research_company.json
  - tests/fixtures/provider_apollo_company.json
  - tests/fixtures/provider_zoominfo_company.json
  - tests/fixtures/provider_lusha_company.json
  - tests/test_scaffold.py
autonomous: true
requirements: [MVP-01]
must_haves:
  truths:
    - "`.venv/bin/python -m pytest tests/test_scaffold.py` exits 0 (the phase's runnable proof)"
    - "config/icp_scoring.yaml parses with version 'lv-icp-v0.1' and the four other config YAMLs (field_policy, provider_priority, source_registry, escalation_policy) parse without error"
    - "company_current.json validates as HubSpotRecord; the apollo, zoominfo, lusha, and claude_web fixtures each validate as ProviderResult"
    - "All six schema classes (HubSpotRecord, ProviderResult, CandidateValue, FieldDecision, ICPScoreResult, MergeResult) import and instantiate under pydantic v2"
  artifacts:
    - config/icp_scoring.yaml
    - config/field_policy.yaml
    - config/source_registry.yaml
    - config/provider_priority.yaml
    - config/escalation_policy.yaml
    - src/schemas.py
    - src/__init__.py
    - tests/__init__.py
    - tests/fixtures/company_current.json
    - tests/fixtures/claude_web_research_company.json
    - tests/fixtures/provider_apollo_company.json
    - tests/fixtures/provider_zoominfo_company.json
    - tests/fixtures/provider_lusha_company.json
    - tests/test_scaffold.py
    - requirements.txt
    - .env.example
  key_links:
    - "requirements.txt installs pydantic>=2.8 and PyYAML>=6.0 that schemas.py and the config loaders depend on"
    - "Provider fixtures conform to the ProviderResult contract (provider, object_type, matched, confidence, data, evidence); company_current conforms to HubSpotRecord (object_type, id, properties)"
    - "src/__init__.py makes `from src.schemas import ...` resolvable when pytest runs from the repo root"
---

<objective>
Stand up the config-driven skeleton for the local-first ICP MVP: the five config YAMLs, the pydantic v2 schema module, the test fixtures, and the project meta files (requirements.txt, .env.example). Nothing here implements scoring, enrichment, merge, or I/O — that is Phases 2–4. This phase only proves the scaffold parses and validates.

Purpose: Everything downstream (scoring engine, merge policy, dry-run PATCH) reads these configs and schemas. If the rubric, field governance, provider priority, source registry, escalation policy, and schemas do not load and validate, no later phase can run.

Output: 5 config YAMLs, src/schemas.py, empty-package __init__ files, 5 test fixtures, requirements.txt, .env.example, and tests/test_scaffold.py — the runnable proof that satisfies all three Phase 1 success criteria. Implements MVP-01.
</objective>

<execution_context>
The authoritative source is `CLAUDE.md` at the repo root — it contains the ready-to-use code and config for every file below. Do NOT design from scratch. Transcribe verbatim from the cited section, adapting only where a section note calls it out.
</execution_context>

<context>
@CLAUDE.md
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Config YAMLs + project meta files (SC1)</name>
  <files>config/icp_scoring.yaml, config/field_policy.yaml, config/source_registry.yaml, config/provider_priority.yaml, config/escalation_policy.yaml, requirements.txt, .env.example</files>
  <action>
Transcribe each file verbatim from CLAUDE.md into the paths above:
- config/icp_scoring.yaml ← CLAUDE.md §10.1 (keep version key exactly "lv-icp-v0.1").
- config/field_policy.yaml ← CLAUDE.md §9.2 (top-level `companies:` and `contacts:` maps).
- config/source_registry.yaml ← CLAUDE.md §6.3.
- config/escalation_policy.yaml ← CLAUDE.md §15.1. NOTE: the source has a corrupted entry `confidence_between:[2][3]` (markdown footnote artifact). Render it as a valid two-element range `confidence_between: [70, 85]` with a comment marking it illustrative. This file is documentation config not wired into MVP code; it only needs to be valid YAML.
- requirements.txt ← CLAUDE.md §11.3 verbatim.
- .env.example ← CLAUDE.md §11.2 verbatim.

config/provider_priority.yaml is NOT verbatim in the SPEC — derive it. Structure: two top-level keys `companies:` and `contacts:`, each a map of field name → ordered provider list. Use the ordered list `[zoominfo, apollo, lusha, claude_web]` for every field — this matches the merge_policy fallback in §12.8 so the file never contradicts the consuming code; the zoominfo-first order reflects highest firmographic trust_rank per §6.3. Add a top-of-file comment stating the order rationale. Include these company fields: industry, numberofemployees, annualrevenue, lv_revenue_band, lv_employee_band, lv_org_type, lv_produces_content, lv_content_type, lv_sponsorship_reliant, lv_is_hardware_vendor, lv_is_gambling_operator. Include these contact fields: jobtitle, phone, mobilephone, email, linkedin_url, seniority, persona_group.

Do NOT create any src/*.py module beyond what Task 2 covers. Scaffolding only.
  </action>
  <verify>
    <automated>python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt && .venv/bin/python -c "import yaml, glob; files = sorted(glob.glob('config/*.yaml')); cfg = {f: yaml.safe_load(open(f)) for f in files}; assert len(files) == 5, files; assert cfg['config/icp_scoring.yaml']['version'] == 'lv-icp-v0.1'; assert set(cfg['config/provider_priority.yaml']) >= {'companies','contacts'}; print('SC1 OK: 5 configs load; icp version lv-icp-v0.1')"</automated>
  </verify>
  <done>venv created, requirements installed, all 5 config/*.yaml parse via PyYAML, icp_scoring.yaml version is lv-icp-v0.1, provider_priority.yaml has companies+contacts keys.</done>
</task>

<task type="auto">
  <name>Task 2: Pydantic v2 schemas + package init files (SC2 definitions)</name>
  <files>src/__init__.py, tests/__init__.py, src/schemas.py</files>
  <action>
Create src/__init__.py and tests/__init__.py as empty files (package markers so `from src.schemas import ...` resolves when pytest runs from the repo root).

Transcribe src/schemas.py verbatim from CLAUDE.md §12.1. It is pydantic v2 (uses `model_dump`, `Field(default_factory=...)`, `Literal`). Define exactly: ObjectType, Decision, HubSpotRecord, ProviderEvidence, ProviderResult, CandidateValue, FieldDecision, ICPScoreResult, MergeResult. Do not add or remove fields.

Do NOT implement normalizer, providers, merge, scoring, classifier, validator, hubspot_client, or main.py — those are Phases 2–4.
  </action>
  <verify>
    <automated>.venv/bin/python -c "from src.schemas import HubSpotRecord, ProviderResult, CandidateValue, FieldDecision, ICPScoreResult, MergeResult; print('schemas import OK')"</automated>
  </verify>
  <done>All six schema classes import from src.schemas with no error under the installed pydantic v2.</done>
</task>

<task type="auto">
  <name>Task 3: Test fixtures + validation proof (SC2 + SC3)</name>
  <files>tests/fixtures/company_current.json, tests/fixtures/claude_web_research_company.json, tests/fixtures/provider_apollo_company.json, tests/fixtures/provider_zoominfo_company.json, tests/fixtures/provider_lusha_company.json, tests/test_scaffold.py</files>
  <action>
Transcribe the five fixtures from CLAUDE.md: company_current.json ← §11.4, claude_web_research_company.json ← §11.5, and provider_apollo_company.json / provider_zoominfo_company.json / provider_lusha_company.json ← §11.6 (that section has all three provider fixtures in one block — split into three files). CRITICAL: each SPEC block begins with a `// tests/fixtures/...json` header line. JSON does not allow comments — strip every `//` line so each file is pure valid JSON.

Write tests/test_scaffold.py as the phase's runnable proof (pytest, plain asserts, no fixtures framework). It must contain:
- A config test: glob config/*.yaml, assert exactly 5 files, safe_load each, assert icp_scoring.yaml version == "lv-icp-v0.1". (SC1)
- A HubSpotRecord test: load tests/fixtures/company_current.json and assert HubSpotRecord(**data) validates. (SC2/SC3)
- A ProviderResult test: parametrize over the four provider/research fixtures (apollo, zoominfo, lusha, claude_web) and assert ProviderResult(**data) validates each. (SC2/SC3)
- A remaining-schemas test proving the other schema classes validate (SC2), using these minimal constructions so nothing is guessed: build ProviderEvidence(**apollo_fixture["evidence"]); CandidateValue(canonical_field="annualrevenue", provider="apollo", value=12000000, normalized_value="5-50M", confidence=74, evidence=that_evidence); FieldDecision(field="annualrevenue", current_value="", decision="stage_only", reason="scaffold test"); ICPScoreResult(score=80, tier="A", anti_icp_flag=False, recommended_motion="work_direct", confidence=85, breakdown={}, scoring_version="lv-icp-v0.1"); MergeResult(object_type="companies", record_id="789", run_id="scaffold", field_decisions=[that_field_decision], staging_patch={}, canonical_patch={}, metadata_patch={}, status_patch={}, full_patch={}).

Resolve fixture and config paths relative to the repo root (e.g. via pathlib from __file__) so the test passes regardless of pytest invocation cwd.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_scaffold.py -q</automated>
  </verify>
  <done>pytest passes: all 5 configs load, company_current validates as HubSpotRecord, all four provider/research fixtures validate as ProviderResult, and the remaining schema classes instantiate — proving SC1, SC2, SC3.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| PyPI → local venv | requirements.txt pulls third-party packages into the dev environment |
| SPEC/fixtures → schema layer | Fixture JSON is trusted test data authored from the SPEC, not external input |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-phase-1-SC | Tampering | pip installs from requirements.txt | medium | mitigate | Packages are the canonical, most-downloaded PyPI libraries (anthropic, requests, pydantic, PyYAML, python-dotenv, phonenumbers, email-validator, pytest), transcribed verbatim from SPEC §11.3 and pinned to minimum versions. Install occurs only in a local .venv with no runtime execution of enrichment code. No `[ASSUMED]`/`[SUS]`/`[SLOP]` novel packages present, so no blocking legitimacy checkpoint is warranted; executor confirms versions resolve on pypi.org during install. |
| T-phase-1-01 | Tampering | fixture JSON parsing | low | accept | Fixtures are static, repo-local test data derived from the SPEC; no untrusted input path exists in this phase. |
| T-phase-1-02 | Information disclosure | .env.example | low | accept | .env.example carries placeholder values only (no real secrets); the real .env is git-ignored and not created here. |
</threat_model>

<verification>
Full-phase proof, run from the repo root:

```
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt && .venv/bin/python -m pytest tests/test_scaffold.py -q
```

Expected: pytest reports all tests passing. This single run exercises SC1 (5 configs load, icp version lv-icp-v0.1), SC2 (all six schemas validate), and SC3 (company + four provider/research fixtures parse into their schemas).
</verification>

<success_criteria>
1. SC1 — `config/icp_scoring.yaml` (version lv-icp-v0.1) and the four other config YAMLs load via PyYAML without error.
2. SC2 — HubSpotRecord, ProviderResult, CandidateValue, FieldDecision, ICPScoreResult, and MergeResult all import and validate under pydantic v2.
3. SC3 — company_current plus conflicting apollo/zoominfo/lusha provider fixtures and the claude_web research fixture exist and each parses into its schema.

All three are proven by `pytest tests/test_scaffold.py` passing.
</success_criteria>

<output>
Create `.planning/phases/phase-1/phase-1-01-SUMMARY.md` when done, recording: files created, the passing pytest output, and any adaptation notes (the escalation_policy `confidence_between` fix, the derived provider_priority ordering, and the stripped `//` fixture headers).
</output>
