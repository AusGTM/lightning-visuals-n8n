---
phase: phase-4
plan: 01
type: execute
wave: 1
depends_on: [phase-3-01]
files_modified:
  - src/hubspot_client.py
  - main.py
  - tests/test_main.py
autonomous: true
requirements: [MVP-04]
must_haves:
  truths:
    - "Running `python main.py` from repo root prints four sections: provider results, field decisions, ICP score, and the exact HubSpot PATCH payload (SC1)."
    - "In dry-run mode NO HubSpot HTTP write occurs; patch_record returns {\"dry_run\": True, ...} without calling requests.patch (SC2/SC3)."
    - "The emitted PATCH promotes only lv_icp_* outputs to canonical and stages firmographic provider fields (zoominfo_*, apollo_*); it never contains a bare domain/annualrevenue/manual canonical key (SC2)."
    - "Flipping ALLOW_STAGING_WRITES removes staging+metadata keys; ALLOW_CANONICAL_WRITES=false withholds firmographic canonical keys while keeping lv_icp_*; DRY_RUN=true short-circuits the write (SC3)."
    - "The full offline suite `.venv/bin/python -m pytest tests/ -q` passes green with no network and no ANTHROPIC_API_KEY."
  artifacts:
    - src/hubspot_client.py
    - main.py
    - tests/test_main.py
  key_links:
    - "main.run_local_mvp -> build_merge_result (Phase 3) -> patch_record(dry_run=True) (no HTTP)"
    - "safety-gate env flags (DRY_RUN/ALLOW_CANONICAL_WRITES/ALLOW_ICP_SCORE_WRITES/ALLOW_STAGING_WRITES) -> patch-assembly branches in run_local_mvp"
---

<objective>
Wire the Phase 1–3 pieces into an end-to-end local run that prints the exact HubSpot PATCH it would send and, under env-flag safety gates, promotes only `lv_icp_*` outputs to canonical while staging firmographics — with zero live HubSpot writes.

Purpose: This is the MVP acceptance gate (MVP-04, CLAUDE.md §29 scope cut). It proves the safe-writeback contract end-to-end before any production wiring.
Output: `src/hubspot_client.py` (§12.9), `main.py` (§12.10, two flagged deviations), and `tests/test_main.py` (offline deterministic proof of SC1/SC2/SC3). Plus a one-time, non-gating live smoke run recorded in the SUMMARY.

Two proofs, one gate:
- **Proof A (the gate — must always pass, no network):** `tests/test_main.py` runs the pipeline with `ANTHROPIC_API_KEY` stripped and the classifier monkeypatched, asserting SC1/SC2/SC3 on the returned patch dict and captured stdout, and that `requests.patch` is never called.
- **Proof B (documented, run once, NOT a gate):** `python main.py` under the real `.env` (real Anthropic key, mock providers, `DRY_RUN=true`, `ALLOW_CANONICAL_WRITES=false`) — real Haiku classification runs, a real tier + dry-run PATCH print, zero HubSpot writes. Errors here (rate limit, model name) are captured, not fatal.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@CLAUDE.md
@src/schemas.py
@src/merge_policy.py
@tests/test_merge_policy.py
@.planning/phases/phase-3/phase-3-01-SUMMARY.md

# CLAUDE.md sections to transcribe/adapt: §12.9 (hubspot_client), §12.10 (main.py),
# §11.2 (.env flags), §21 (safety gates), §29 (MVP scope cut).
</context>

<tasks>

<task type="auto">
  <name>Task 1: HubSpot client with dry-run PATCH (src/hubspot_client.py)</name>
  <files>src/hubspot_client.py</files>
  <action>
Transcribe CLAUDE.md §12.9 verbatim: BASE_URL, hs_headers (reads HUBSPOT_PRIVATE_APP_TOKEN via os.getenv), get_record, patch_record, search_records. The load-bearing behavior for MVP-04 (SC2/SC3): patch_record, when dry_run is True, prints the payload as JSON (json.dumps(..., default=str)) and RETURNS {"dry_run": True, "payload": {"properties": ...}} WITHOUT calling requests.patch. Only when dry_run is False does it POST/PATCH to the API. Per CLAUDE.md §21, Phase 4 performs NO live write — dry_run stays True everywhere; live writeback / ALLOW_TEST_RECORD_WRITES is a future milestone, out of scope here. Do NOT print secret values: patch_record prints only the payload dict, never hs_headers or the token.
  </action>
  <verify>
    <automated>.venv/bin/python -c "from src.hubspot_client import patch_record, get_record, search_records, hs_headers; r=patch_record('companies','789',{'x':'y'},dry_run=True); assert r=={'dry_run':True,'payload':{'properties':{'x':'y'}}}, r; print('OK')"</automated>
  </verify>
  <done>src/hubspot_client.py imports cleanly; patch_record(dry_run=True) returns the sentinel dict and makes no HTTP call.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: End-to-end MVP runner (main.py)</name>
  <files>main.py</files>
  <behavior>
    - run_local_mvp() loads the fixture company, runs the mock provider waterfall + claude_web_research, builds candidates, calls build_merge_result, assembles the emitted patch honoring the flags, prints the four sections, and calls patch_record(dry_run=DRY_RUN).
    - Patch assembly honors flags EXACTLY as §12.10: ALLOW_STAGING_WRITES gates staging_patch+metadata_patch; status_patch always included; ALLOW_CANONICAL_WRITES=true adds full canonical_patch; otherwise ALLOW_ICP_SCORE_WRITES copies only the lv_icp_* output keys from canonical_patch.
    - run_local_mvp() RETURNS the assembled patch dict (deviation, see action) so tests assert on the dict, not stdout.
    - Importing main has NO side effects (no .env load, no run) — run only under the __main__ guard.
  </behavior>
  <action>
Transcribe CLAUDE.md §12.10 run_local_mvp with these imports already satisfied by Phases 1–3: get_mock_provider_waterfall (src.providers), claude_web_research (src.web_research), provider_to_candidates (src.normalizer), build_merge_result (src.merge_policy), patch_record (src.hubspot_client). Keep the four print sections (Provider + Research Results, Field Decisions, ICP Score, HubSpot Patch Payload) and the flag-gated patch assembly verbatim from §12.10.

TWO flagged deviations from §12.10 (both minimal, both required for the offline gate):
1. Move `load_dotenv()` OUT of module scope and INTO the `if __name__ == "__main__":` block (before calling run_local_mvp). Rationale: §12.10 calls load_dotenv() at import; because a real .env with ANTHROPIC_API_KEY exists (per §11.2 environment reality), a module-level load would leak the key into the test session on `import main`, making classify_field_with_haiku fire live network calls inside the existing hermetic suite (e.g. test_merge_policy.test_integ_wires_icp_scorer, which runs the classifier unmonkeypatched). Loading .env only under __main__ keeps `import main` side-effect-free; the CLI live smoke (Proof B) still loads the real .env. Do NOT call load_dotenv() inside run_local_mvp() (it would re-add the key and defeat the test's delenv).
2. Have run_local_mvp() `return patch` after printing and calling patch_record — the assembled emitted patch dict — so Proof A asserts on the dict deterministically. Add a one-line comment on each deviation.

Keep the guard: `if __name__ == "__main__": load_dotenv(); run_local_mvp()`. main.py lives at repo ROOT and reads tests/fixtures + config/*.yaml relative to cwd, so it (and the tests) must run from repo root.

Note (do not "fix"): metadata_patch carries `{field}_evidence_url` as a LIST (Phase 3 deviation). §12.10 does not serialize it; that is fine for dry-run print/return. Serialization for a real write is handled by the n8n build-patch node (§18.5) in a future milestone — no live write happens here, so leave it.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import main; assert hasattr(main,'run_local_mvp'); print('import-clean OK')"</automated>
  </verify>
  <done>Importing main has no side effects; `python main.py` from repo root prints the four sections and a dry-run PATCH; run_local_mvp() returns the emitted patch dict.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Offline deterministic phase-proof suite (tests/test_main.py)</name>
  <files>tests/test_main.py</files>
  <behavior>
    Fully OFFLINE, deterministic, no network, no key. Mirror the Phase 3 pattern: monkeypatch at the merge_policy import site (`src.merge_policy.classify_field_with_haiku`) with a promote_fake returning {"decision":"promote","confidence":90,"reason":"test","requires_sonnet_validation":False}. In EVERY test: monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False); monkeypatch.setenv the flags the test depends on (DRY_RUN, USE_MOCK_WEB_RESEARCH=true, ALLOW_SONNET_ESCALATION=false, plus the ALLOW_* under test); monkeypatch `src.hubspot_client.requests.patch` to a sentinel that raises if called. Import run_local_mvp from main.

    - test_sc1_prints_four_sections (capsys): flags DRY_RUN=true, ALLOW_STAGING_WRITES=true, ALLOW_CANONICAL_WRITES=false, ALLOW_ICP_SCORE_WRITES=true. Run; assert captured stdout contains all four section headers.
    - test_sc2_promotes_only_icp_stages_firmographics: same flags. patch=run_local_mvp(); assert "lv_icp_fit_score" in patch and "lv_icp_tier" in patch; assert some key starts with "zoominfo_"; assert "domain" not in patch and "annualrevenue" not in patch; assert "lv_org_type" not in patch (firmographic canonical withheld even though promote_fake promoted it into canonical_patch).
    - test_sc3_staging_flag_toggles: ALLOW_STAGING_WRITES=false → no key starts with zoominfo_/apollo_/claude_web_ and no key ends with "_source", but "lv_icp_tier" and status keys (enrichment_status) still present. Second run with ALLOW_STAGING_WRITES=true → a zoominfo_* key present.
    - test_sc3_canonical_flag_toggles_firmographic: ALLOW_CANONICAL_WRITES=false → "lv_org_type" not in patch; ALLOW_CANONICAL_WRITES=true → patch["lv_org_type"] == "governing_body_league".
    - test_sc3_dry_run_no_http: patch_record("companies","789",{"x":"y"},dry_run=True) returns {"dry_run":True,"payload":{"properties":{"x":"y"}}} and the requests.patch sentinel is never triggered.
  </behavior>
  <action>
Author tests/test_main.py implementing the behaviors above. Load fixtures/config cwd-relative (suite runs from repo root, exactly like tests/test_merge_policy.py). Reuse the promote_fake + import-site monkeypatch convention documented in tests/test_merge_policy.py header. Do NOT rely on any .env value — set every flag the assertion depends on via monkeypatch.setenv (the on-disk .env has ALLOW_SONNET_ESCALATION=false, which the test also sets explicitly to stay hermetic). The requests.patch sentinel proves SC2/SC3 "no HubSpot write" at runtime — do not assert it via grep.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_main.py -q</automated>
  </verify>
  <done>tests/test_main.py green; SC1/SC2/SC3 all asserted offline; requests.patch never called.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| main.py → HubSpot API | The only live-write surface; must stay dry-run in Phase 4 |
| .env / os.environ → process | Real secrets (HubSpot token, Anthropic key) enter here |
| process → Anthropic API | Live LLM calls during the Proof B smoke |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-phase4-01 | Tampering | patch_record write path | high | mitigate | DRY_RUN=true enforced everywhere; patch_record returns the sentinel before requests.patch; test asserts requests.patch is never called; live writeback / ALLOW_TEST_RECORD_WRITES explicitly out of scope (§21). |
| T-phase4-02 | Information Disclosure | stdout / SUMMARY | medium | mitigate | patch_record prints only the payload dict, never hs_headers/token; SUMMARY records the PATCH + tier with secrets redacted. |
| T-phase4-03 | Denial of Service (cost) | Anthropic calls in Proof B | low | mitigate | Smoke runs once on a single fixture company; MAX_* caps in .env (§11.2); the offline gate needs no key at all. |
</threat_model>

<verification>
## Gate (Proof A — must pass, no network, no key)

Run from repo ROOT:
```
.venv/bin/python -m pytest tests/ -q
```
The FULL suite (scaffold + icp_scoring + merge_policy + main) must be green with no network. This is the hard gate for the phase.

## Proof B — Live smoke (run ONCE, NON-GATING, record in SUMMARY)

Run from repo ROOT with the real .env loaded (real Anthropic key, mock providers, dry-run):
```
DRY_RUN=true ALLOW_CANONICAL_WRITES=false .venv/bin/python main.py
```
Expected: real Haiku classification runs, the four sections print, a real `lv_icp_tier` and the dry-run PATCH payload appear, and NO HubSpot write happens. In the SUMMARY, paste (a) the emitted PATCH payload, (b) the resulting `lv_icp_tier`, and (c) a one-line confirmation that zero HTTP writes reached HubSpot. If the live call errors (rate limit, model name, etc.), capture the error text and note it — this does NOT fail the phase; Proof A is the gate. NEVER set DRY_RUN=false; NEVER paste secret values.
</verification>

<success_criteria>
- SC1: `python main.py` prints provider results, field decisions, ICP score, and the exact PATCH payload.
- SC2: dry-run performs no HubSpot write; the emitted patch promotes only `lv_icp_*` to canonical and stages firmographics; never a bare domain/annualrevenue/manual canonical key.
- SC3: DRY_RUN / ALLOW_CANONICAL_WRITES / ALLOW_ICP_SCORE_WRITES / ALLOW_STAGING_WRITES / ALLOW_SONNET_ESCALATION change the emitted payload as documented.
- Gate: `.venv/bin/python -m pytest tests/ -q` passes green offline.
</success_criteria>

<output>
Create `.planning/phases/phase-4/phase-4-01-SUMMARY.md` when done. Include the Proof B live-smoke output: the dry-run PATCH payload, the resulting `lv_icp_tier`, and confirmation of zero HubSpot HTTP writes (secrets redacted). If Proof B errored, record the error and note the phase still passes on Proof A.
</output>
