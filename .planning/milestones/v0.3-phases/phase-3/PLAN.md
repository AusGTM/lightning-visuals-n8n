---
phase: phase-3
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/providers.py
  - src/web_research.py
  - src/normalizer.py
  - src/classifier_haiku.py
  - src/validator_sonnet.py
  - src/merge_policy.py
  - tests/test_merge_policy.py
autonomous: true
requirements: [REQ-enrichment-plan, REQ-hubspot-icp-properties, MVP-02, MVP-03]
must_haves:
  truths:
    - "`.venv/bin/python -m pytest tests/test_merge_policy.py tests/test_icp_scoring.py tests/test_scaffold.py -q` exits 0 from the repo root with NO network access (the phase's runnable proof) (REQ-enrichment-plan, MVP-02, MVP-03)"
    - "Each mock adapter (Apollo/Lusha/ZoomInfo) and mock Claude web research returns a ProviderResult carrying provider, matched, confidence, data, evidence, and model_trace (SC1, REQ-enrichment-plan)"
    - "Conflicting revenue candidates (Apollo 5-50M vs ZoomInfo 50-500M) give has_conflict True; deterministic_gate picks ZoomInfo by provider_priority and returns needs_review because lv_revenue_band allows sonnet escalation — proving the escalation trigger fires only when policy requires (SC2, MVP-02)"
    - "manual_protected (domain) and fill_blank_only-with-existing-value fields never enter canonical_patch (staged only) even when the classifier is forced to promote; system_owned (lv_org_type) and blank fill_blank_only fields promote to canonical_patch (SC3, MVP-02, REQ-hubspot-icp-properties)"
    - "For every field with candidates, metadata_patch stamps {field}_source, {field}_confidence, {field}_evidence_url, {field}_evidence_summary, {field}_verified_at, {field}_verified_by_model, and {field}_validation_status (SC4, MVP-03)"
  artifacts:
    - src/providers.py
    - src/web_research.py
    - src/normalizer.py
    - src/classifier_haiku.py
    - src/validator_sonnet.py
    - src/merge_policy.py
    - tests/test_merge_policy.py
  key_links:
    - "build_merge_result(record: HubSpotRecord, candidates: List[CandidateValue]) -> MergeResult — the surface Phase 4 main.py consumes; for companies it calls Phase 2's compute_icp_score and returns lv_icp_* in canonical_patch"
    - "merge_policy binds classify_field_with_haiku and validate_conflict_with_sonnet at import time via `from .classifier_haiku import ...` / `from .validator_sonnet import ...`, so tests monkeypatch `src.merge_policy.classify_field_with_haiku` (NOT src.classifier_haiku.*)"
    - "choose_best must return a single CandidateValue (the fixed [0] slice); deterministic_gate and build_merge_result treat gate['chosen'] as one candidate (best.confidence, chosen.normalized_value)"
    - "providers/web_research read tests/fixtures/* and merge/icp read config/* via repo-root-relative paths, so the proof runs with cwd = repo root"
---

<objective>
Build the enrichment pipeline and the non-clobber merge engine. Mock provider adapters (Apollo/Lusha/ZoomInfo) and a mock Claude web-research adapter each emit the normalized ProviderResult contract; a normalizer turns those into CandidateValue lists; a deterministic gate plus a Haiku classifier and a Sonnet validator stub resolve each field into a promote / stage_only / reject / needs_review decision under field-ownership governance; and every decision is stamped with full source attribution. Prove the whole thing offline and deterministically with tests/test_merge_policy.py.

Purpose: This is the pipeline that feeds Phase 2's scoring engine and Phase 4's dry-run PATCH. It is where CLAUDE.md's core promise lives — no clobbering of manual or higher-confidence CRM values, full source/evidence provenance, and cheap-first LLM escalation. If the merge promotes a manual_protected field or drops provenance, the whole MVP's safety guarantee fails.

Output: src/providers.py (§12.2), src/web_research.py (§12.3), src/normalizer.py (§12.4), src/classifier_haiku.py (§12.5), src/validator_sonnet.py (§12.6), src/merge_policy.py (§12.8, with one documented correctness fix), and tests/test_merge_policy.py — the runnable proof. Implements REQ-enrichment-plan, REQ-hubspot-icp-properties, MVP-02, MVP-03.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md

The authoritative source is `CLAUDE.md` at the repo root — sections §12.2, §12.3, §12.4, §12.5, §12.6, and §12.8 contain ready implementations. Transcribe them; do not redesign. Phase 2 already shipped `src/icp_scoring.py` (`compute_icp_score`) and Phase 1 shipped the schemas, config YAMLs, and fixtures — this plan consumes them unchanged. Scope boundary: ONLY the seven files listed in `files_modified`. Do NOT create or touch `src/hubspot_client.py` (§12.9) or `main.py` (§12.10) — those are Phase 4. Do NOT edit config YAMLs, schemas, icp_scoring.py, or the Phase 1/2 tests.
</execution_context>

<context>
@CLAUDE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@src/schemas.py
@src/icp_scoring.py
@config/field_policy.yaml
@config/provider_priority.yaml
@config/source_registry.yaml
@tests/fixtures/company_current.json
@tests/fixtures/provider_apollo_company.json
@tests/fixtures/provider_zoominfo_company.json
@tests/fixtures/provider_lusha_company.json
@tests/fixtures/claude_web_research_company.json
</context>

<tasks>

<task type="auto">
  <name>Task 1: Candidate production layer — providers.py, web_research.py, normalizer.py</name>
  <files>src/providers.py, src/web_research.py, src/normalizer.py</files>
  <action>
Transcribe three files from CLAUDE.md verbatim, adjusting only imports to the `src` package.

`src/providers.py` from §12.2: `ProviderAdapter` base with `enrich(record) -> ProviderResult`; `MockApolloCompanyAdapter`, `MockLushaCompanyAdapter`, `MockZoomInfoCompanyAdapter` (each reads its fixture from `FIXTURE_DIR = Path("tests/fixtures")` and returns `ProviderResult(**json.loads(...))`); and `get_mock_provider_waterfall()` returning `[MockZoomInfoCompanyAdapter(), MockApolloCompanyAdapter(), MockLushaCompanyAdapter()]`. Import `HubSpotRecord, ProviderResult` from `.schemas`. Keep the relative `tests/fixtures` path — the proof runs with cwd = repo root, matching the Phase 1 scaffold convention; do not rework path resolution.

`src/web_research.py` from §12.3: `mock_claude_web_research(record)` reading `tests/fixtures/claude_web_research_company.json` into a `ProviderResult`, and `claude_web_research(record)` which returns the mock when `USE_MOCK_WEB_RESEARCH` is unset or "true" (the default) and otherwise POSTs to `CLAUDE_WEB_RESEARCH_ENDPOINT`. Import `HubSpotRecord, ProviderResult` from `.schemas`. The live HTTP branch is transcribed but never exercised in this phase (mock path only).

`src/normalizer.py` from §12.4: `normalize_text`, `normalize_bool`, `normalize_revenue_band`, `normalize_employee_band`, `normalize_country_region`, `normalize_field`, and `provider_to_candidates(result) -> List[CandidateValue]`. Import `ProviderResult, CandidateValue` from `.schemas`. `provider_to_candidates` returns an empty list when `result.matched` is False, and skips any field whose value is None or empty string; each surviving field becomes a `CandidateValue` with `normalized_value = normalize_field(field, value)` carrying the provider's confidence, evidence, and model_trace. Transcribe the band boundaries exactly as written (they must agree with the Phase 2 rubric bands).

Do NOT add abstractions, config, or fields beyond what §12.2/§12.3/§12.4 define. These are mock/stub layers; keep them minimal.
  </action>
  <verify>
    <automated>.venv/bin/python -c "from src.schemas import HubSpotRecord; from src.providers import get_mock_provider_waterfall; from src.web_research import mock_claude_web_research; from src.normalizer import provider_to_candidates, normalize_revenue_band, normalize_country_region; r=HubSpotRecord(object_type='companies',id='789',properties={}); ws=[a.enrich(r) for a in get_mock_provider_waterfall()]+[mock_claude_web_research(r)]; assert all(w.model_trace is not None and hasattr(w,'confidence') for w in ws), ws; cands=[c for w in ws for c in provider_to_candidates(w)]; assert any(c.canonical_field=='lv_org_type' and c.normalized_value=='governing_body_league' for c in cands), 'web research org_type candidate missing'; assert normalize_revenue_band(12000000)=='5-50M' and normalize_country_region('Australia')=='AU'; print('candidate layer OK:', len(cands), 'candidates')</automated>
  </verify>
  <done>All three adapters plus mock web research return ProviderResult objects; provider_to_candidates yields CandidateValue objects with normalized_value populated (including the claude_web lv_org_type = governing_body_league candidate); revenue/country normalizers behave. Lusha (unmatched fixture) yields zero candidates. (SC1)</done>
</task>

<task type="auto">
  <name>Task 2: Cascade + non-clobber merge — classifier_haiku.py, validator_sonnet.py, merge_policy.py</name>
  <files>src/classifier_haiku.py, src/validator_sonnet.py, src/merge_policy.py</files>
  <action>
Transcribe three files from CLAUDE.md, applying exactly ONE documented correctness fix (in merge_policy).

`src/classifier_haiku.py` from §12.5: `classify_field_with_haiku(record, field, current_value, candidates, policy)`. Keep the no-API-key fallback exactly — when `ANTHROPIC_API_KEY` is unset it returns `{"decision": "stage_only", "confidence": 50, "reason": "No Anthropic API key configured; conservative fallback."}` with no network call. The live Anthropic branch is transcribed but never exercised in this phase.

`src/validator_sonnet.py` from §12.6: `validate_conflict_with_sonnet(record, field, current_value, candidates, haiku_result, policy)`. Keep the guard exactly — when `ALLOW_SONNET_ESCALATION` is not "true" OR `ANTHROPIC_API_KEY` is missing, it returns a conservative `{"decision": "needs_review", ..., "validation_status": "human_review_required"}` with no network call.

`src/merge_policy.py` from §12.8: `now_iso`, `load_yaml`, `is_blank`, `staging_property`, `source_metadata`, `group_candidates`, `choose_best`, `has_conflict`, `deterministic_gate`, and `build_merge_result`. Import the schemas from `.schemas`, `classify_field_with_haiku` from `.classifier_haiku`, `validate_conflict_with_sonnet` from `.validator_sonnet`, and `compute_icp_score` from `.icp_scoring`. Keep `load_yaml` reading the repo-root-relative `config/field_policy.yaml` and `config/provider_priority.yaml`; keep the per-field default policy `{"class": "fill_blank_only", "min_confidence": 80}` and the default priority `["zoominfo", "apollo", "lusha", "claude_web"]`. For companies, keep the block that calls `compute_icp_score(record, score_input_patch)` (built from canonical_patch + staging_patch) and writes the lv_icp_* outputs into canonical_patch. Keep the status_patch, metadata_patch, staging_patch, and full_patch assembly verbatim.

APPLY EXACTLY ONE documented correctness fix — `choose_best`. §12.8 writes `choose_best` to `return sorted(candidates, key=...) if candidates else None`, i.e. it returns the whole sorted LIST. But every caller treats the result as a single candidate: `deterministic_gate` immediately does `best.confidence`, returns it as `gate["chosen"]`, and `build_merge_result` then reads `chosen.normalized_value`, `chosen.provider`, and `chosen.evidence`. A list has no `.confidence`, so the spec as written raises AttributeError on the first field that has candidates — build_merge_result cannot run at all. Change ONLY the return to take the top element: return `sorted(candidates, key=...)[0] if candidates else None`. Leave the sort key untouched (provider_priority index ascending, then confidence descending), so the highest-priority, highest-confidence candidate is chosen. Add an inline comment naming this as the documented deviation and its reason. This mirrors the Phase 2 precedent of applying one minimal, flagged fix to a SPEC transcription defect.

Two behaviors to transcribe UNCHANGED (do NOT "fix" them — Phase 4/main handles them, and the tests assert them as-is):
- `source_metadata` sets `{field}_evidence_url` to the LIST `candidate.evidence.evidence_urls` (or None when empty), not a scalar. Leave it as the list.
- The offline classifier returns `stage_only`, and `build_merge_result` sets `final_decision = final_result.get("decision", ...)` then guards `if gate["decision"] in ["reject", "stage_only"] and final_decision == "promote": final_decision = gate["decision"]`. Net offline effect: no firmographic field promotes to canonical (only lv_icp_* outputs do). This is correct conservative behavior; the Task 3 tests use monkeypatch to exercise the promote path deterministically rather than requiring a live key.

Do NOT implement hubspot_client.py or main.py. Do NOT add retry/timeout/credit logic (that is the live-provider milestone).
  </action>
  <verify>
    <automated>.venv/bin/python -c "import json; from pathlib import Path; from src.schemas import HubSpotRecord, ProviderResult; from src.normalizer import provider_to_candidates; from src.providers import get_mock_provider_waterfall; from src.web_research import mock_claude_web_research; from src.merge_policy import build_merge_result, choose_best; rec=HubSpotRecord(**json.loads(Path('tests/fixtures/company_current.json').read_text())); ws=[a.enrich(rec) for a in get_mock_provider_waterfall()]+[mock_claude_web_research(rec)]; cands=[c for w in ws for c in provider_to_candidates(w)]; assert choose_best(cands, ['zoominfo','apollo','lusha','claude_web']).__class__.__name__=='CandidateValue', 'choose_best must return one CandidateValue'; mr=build_merge_result(rec, cands); assert mr.icp_score is not None and 'lv_icp_fit_score' in mr.canonical_patch and 'lv_icp_tier' in mr.canonical_patch, mr.canonical_patch; assert mr.status_patch.get('enrichment_status') in ('complete','needs_review'); print('merge OK: tier', mr.icp_score.tier, '| status', mr.status_patch['enrichment_status'])"</automated>
  </verify>
  <done>choose_best returns a single CandidateValue (fix present and commented); build_merge_result runs end-to-end offline on the fixture without crashing, wires in compute_icp_score so canonical_patch carries lv_icp_fit_score and lv_icp_tier, and emits an enrichment_status. The classifier/validator offline fallbacks make no network call. (SC2/SC3/SC4 mechanics in place)</done>
</task>

<task type="auto">
  <name>Task 3: Runnable proof — tests/test_merge_policy.py</name>
  <files>tests/test_merge_policy.py</files>
  <action>
Write `tests/test_merge_policy.py` as the phase's runnable proof: plain pytest, plain asserts, using the built-in `monkeypatch` fixture. It must be fully OFFLINE and DETERMINISTIC — no real Anthropic call. Import from `src.schemas`, `src.providers`, `src.web_research`, `src.normalizer`, and `src.merge_policy` (import `build_merge_result`, `deterministic_gate`, `has_conflict`, `choose_best`, `group_candidates`). Load fixtures from `tests/fixtures` via a `Path(__file__).resolve().parent / "fixtures"` helper so schema construction is cwd-independent; note that `build_merge_result` and `compute_icp_score` still read config/ relative to cwd, so the run itself must start from the repo root (document this in a header comment).

Critical monkeypatch rule: patch at the merge_policy import site, `src.merge_policy.classify_field_with_haiku` and `src.merge_policy.validate_conflict_with_sonnet` — NOT `src.classifier_haiku.*` — because merge_policy binds those names locally at import. Provide small fakes: a promote-fake returning `{"decision": "promote", "confidence": 90, "reason": "test", "requires_sonnet_validation": False}` and (where escalation is under test) a sonnet-fake returning a controlled needs_review/promote dict.

Cover these cases (one test function each, or parametrized where natural). Every case maps to a success criterion:

| # | What it proves | Assertion |
|---|----------------|-----------|
| SC1-a | Each mock adapter returns the contract | For ZoomInfo/Apollo/Lusha via get_mock_provider_waterfall: result.provider set, isinstance(result.matched, bool), isinstance(result.confidence, int), result.data is dict, result.evidence present, result.model_trace is dict |
| SC1-b | Mock web research returns the contract | mock_claude_web_research(record).provider == "claude_web", matched True, confidence > 0, evidence.evidence_urls non-empty |
| norm-a | provider_to_candidates maps a ProviderResult to CandidateValue list | apollo result yields candidates whose canonical_field/normalized_value are set; unmatched lusha yields [] |
| norm-b | revenue/employee/bool/country normalizers | normalize_revenue_band(12000000)=="5-50M"; normalize_revenue_band(65000000)=="50-500M"; normalize_employee_band(220)=="201-500"; normalize_bool("true") is True; normalize_country_region("Australia")=="AU"; normalize_country_region("Germany")=="Other" |
| SC2 | Conflict resolves via deterministic gate, escalates only when policy requires | Build two lv_revenue_band candidates (apollo "5-50M" conf 74, zoominfo "50-500M" conf 83) via provider_to_candidates or direct CandidateValue; assert has_conflict([...]) is True; call deterministic_gate with policy {"class":"system_owned","min_confidence":75,"allow_sonnet_escalation":True} and priority ["zoominfo","apollo","lusha","claude_web"] and assert gate["decision"]=="needs_review" and gate["chosen"].provider=="zoominfo". Also assert that WITHOUT allow_sonnet_escalation the same non-conflicting single-candidate case does not force needs_review. |
| SC3-gate | Governance at the gate | deterministic_gate on a manual_protected policy (domain) returns "stage_only"; on fill_blank_only with a non-blank current_value returns "stage_only"; on fill_blank_only with blank current_value returns "promote"; on system_owned above min_confidence returns "promote". (Encodes CLAUDE.md §24.1 cases 14/15/16.) |
| SC3-e2e | Governance end-to-end with promote-forced classifier | monkeypatch src.merge_policy.classify_field_with_haiku -> promote-fake; build candidates from all mock providers + web research on the fixture company; build_merge_result; assert "domain" NOT in canonical_patch (manual_protected staged despite promote-fake) but "zoominfo_domain"/"apollo_domain" ARE in staging_patch; assert "lv_org_type" IS in canonical_patch with value "governing_body_league" (system_owned promoted). |
| SC4 | Full source attribution | On the same SC3-e2e MergeResult, for field "lv_org_type" assert metadata_patch contains lv_org_type_source, lv_org_type_confidence, lv_org_type_evidence_url, lv_org_type_evidence_summary, lv_org_type_verified_at, lv_org_type_verified_by_model, lv_org_type_validation_status. Assert lv_org_type_evidence_url EQUALS the list candidate.evidence.evidence_urls (it is the list by design — do not expect a scalar). |
| integ | End-to-end wiring incl. Phase 2 scorer | build_merge_result on the fixture company (offline, no monkeypatch) returns a MergeResult whose canonical_patch includes lv_icp_fit_score and lv_icp_tier and whose status_patch has enrichment_status in {complete, needs_review}. |

For SC2 and SC3-gate, prefer calling `deterministic_gate` / `has_conflict` directly with hand-built CandidateValue objects and inline policy dicts — that isolates the governance logic with zero network and zero classifier dependency. For SC3-e2e and SC4, use build_merge_result with the monkeypatched promote-fake so the promote path is exercised deterministically. Add a short header comment explaining the monkeypatch-at-import-site rule and the cwd=repo-root requirement.

Do NOT assert on live LLM output, do NOT require ANTHROPIC_API_KEY, and do NOT re-test scoring internals already covered by tests/test_icp_scoring.py (only assert the lv_icp_* keys are wired into canonical_patch here).
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_merge_policy.py tests/test_icp_scoring.py tests/test_scaffold.py -q</automated>
  </verify>
  <done>pytest is green for all three files with no network: the mock adapters + web research satisfy the ProviderResult contract (SC1); conflicting revenue resolves through the deterministic gate and escalates to needs_review only under allow_sonnet_escalation (SC2); manual_protected/fill_blank_only stay staged while system_owned promotes even with a promote-forced classifier (SC3); and every field with candidates carries the seven source-attribution metadata keys (SC4). Proves all four Phase 3 success criteria.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| tests/fixtures/*.json -> mock adapters | Repo-local, trusted fixture data parsed with json.loads into ProviderResult (pydantic-validated); no external provider is called in this phase |
| config/*.yaml -> merge_policy / icp_scoring | Repo-local, trusted rubric/governance loaded via yaml.safe_load |
| candidates / record.properties -> build_merge_result | In-process dicts from callers (tests here; Phase 4 main later); no untrusted network input in this phase |
| ANTHROPIC_API_KEY / provider env -> classifier & validator | Live LLM/provider branches are transcribed but gated OFF (mock/fallback) this phase; no secret is logged or emitted into patches |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-phase-3-01 | Tampering | config/*.yaml + fixtures load | low | accept | Static repo-local test/config data loaded with yaml.safe_load / json.loads into pydantic models; no arbitrary object construction and no untrusted input path exists this phase. |
| T-phase-3-02 | Information disclosure | source_metadata / status_patch JSON | low | accept | Merge outputs contain only provider-derived enrichment values, evidence URLs, and decision rationale; no API keys or secrets flow through build_merge_result (classifier/validator read keys from env only inside the un-exercised live branch). |
| T-phase-3-03 | Elevation of privilege (data) | non-clobber governance in deterministic_gate | medium | mitigate | The gate + the `gate["decision"] in [reject, stage_only]` guard prevent a promoted classifier result from overwriting manual_protected / fill_blank_only-with-value fields; SC3-e2e test asserts domain never reaches canonical_patch even when the classifier is forced to promote. |

No package-manager installs occur in this phase — all dependencies (anthropic, requests, pydantic, PyYAML, pytest) were installed in Phase 1 — so no package-legitimacy checkpoint is required.
</threat_model>

<verification>
Full-phase proof, run from the repo root (no network required):

`.venv/bin/python -m pytest tests/test_merge_policy.py tests/test_icp_scoring.py tests/test_scaffold.py -q`

Expected: all green. This single run exercises SC1 (mock adapters + web research emit the ProviderResult contract), SC2 (conflicting Apollo/ZoomInfo revenue resolves via the deterministic gate and escalates to needs_review only when the field allows sonnet escalation), SC3 (manual_protected/fill_blank_only staged and never clobbered; system_owned promoted), and SC4 (full source/confidence/evidence/verified_at/verified_by_model/validation_status stamping) — while keeping the Phase 1 scaffold and Phase 2 scoring suites regression-green.
</verification>

<success_criteria>
1. SC1 — Mock Apollo/Lusha/ZoomInfo adapters and mock Claude web research each return the normalized provider contract (provider, matched, confidence, data, evidence, model_trace).
2. SC2 — Conflicting provider values (Apollo 5-50M vs ZoomInfo 50-500M revenue) normalize into candidates and resolve via the deterministic gate, escalating to the Haiku classifier / Sonnet stub only when policy requires.
3. SC3 — Field-ownership governance is enforced: manual_protected and fill_blank_only fields are staged (never clobbered); system_owned / score_output fields promote when confidence passes.
4. SC4 — Every promoted or staged field carries source, confidence, evidence URL + summary, verified_at, verified_by_model, and validation_status.

All four are proven by `pytest tests/test_merge_policy.py` passing (with the Phase 1/2 suites confirming no regression).
</success_criteria>

<output>
Create `.planning/phases/phase-3/phase-3-01-SUMMARY.md` when done, recording: the seven files created, the passing pytest output for all three suites, and the documented deviation — `choose_best` returning `[0]` (a single CandidateValue) instead of §12.8's sorted list, because every caller (`deterministic_gate`, `build_merge_result`) dereferences the result as one candidate and the list form raises AttributeError before build_merge_result can run. Also note the two transcribed-as-is behaviors relied on by the tests: `{field}_evidence_url` is the evidence_urls list (Phase 4 serializes), and the offline classifier stage_only fallback is deliberately bypassed via monkeypatch to prove the promote path.
</output>
