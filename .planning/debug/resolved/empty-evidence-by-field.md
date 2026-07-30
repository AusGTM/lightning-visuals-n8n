---
status: resolved
trigger: |
  DATA_START
  Live closed-won smoke (scripts/smoke_closed_won_research.py --limit 10, report at
  .planning/phases/13-web-research-retrieval-validation/13-SMOKE-CLOSED-WON.md) returned
  lv_produces_content=true for all 10 companies but evidence_by_field was EMPTY for every
  one (evidence column all "—"). Downstream impact: field policy requires evidence URL to
  promote lv_produces_content, so correct verdicts stall in staging forever.
  DATA_END
created: 2026-07-21T04:24:39Z
updated: 2026-07-21T04:24:39Z
---

## Current Focus

reasoning_checkpoint:
  hypothesis: "H4 confirmed, root cause: max_tokens=2000 (hardcoded in both src/web_research.py:99 and scripts/build_cloud_workflows.py:1385 ENRICH_BUILD_RESEARCH_REQUEST) is insufficient for claude-sonnet-5's extended-thinking + full JSON payload (data + evidence_by_field with up to 9 URLs + entity_resolution + evidence.evidence_summary). The model's thinking alone consumes ~1000-1300 tokens, leaving too little room to complete the JSON before hitting the cap. stop_reason comes back \"max_tokens\", the response is cut mid-object, and because evidence_by_field/entity_resolution are emitted AFTER the data block in the model's own JSON, they are the first casualties of truncation — _extract_json's regex fallback then either raises (full crash) or (when the cut lands past a closing brace) yields a syntactically-valid-but-incomplete dict missing the evidence_by_field key entirely, which ProviderResult silently defaults to {} (Field(default_factory=dict), no error). This is a config/budget bug, not a prompt-wording bug — the prompt already asks correctly for evidence_by_field (falsifies the 'naive prompt doesn't ask' theory, as flagged in the trigger)."
  confirming_evidence:
    - "Live call #1 (max_tokens=2000, Melbourne Racing Club): stop_reason=max_tokens, usage.output_tokens_details.thinking_tokens=1251, raw text visibly truncated mid-string inside entity_resolution.notes, _extract_json raised JSONDecodeError (both direct parse and regex-fallback parse failed)."
    - "Live call #2 (max_tokens=8192, same company): stop_reason=end_turn, complete valid JSON, evidence_by_field populated for all 9 data fields including lv_produces_content -> https://www.youtube.com/user/CaulfieldRacing/videos. Falsification test passed: raising the token budget alone (no prompt change) fixes the symptom."
  falsification_test: "If evidence_by_field remained empty even at max_tokens=8192 (full, untruncated response), the root cause would be elsewhere (prompt/H3 or taxonomy.py/H2). It did not — evidence_by_field was fully populated once truncation was removed."
  fix_rationale: "Raise max_tokens in both the dev oracle (src/web_research.py) and the n8n production prompt body (scripts/build_cloud_workflows.py ENRICH_BUILD_RESEARCH_REQUEST) to a value with real headroom above the observed successful-run usage (2829 total output tokens including 1085 thinking) — 4096. Minimal, single-value change in exactly the two places the spec's parity constraint requires; no prompt wording change, no fallback/guessed evidence mapping (which the trigger explicitly forbids)."
  blind_spots: "Only tested one company (Melbourne Racing Club) at two token budgets — did not stress-test a company likely to produce even more verbose output (e.g., a large diversified holding company/franchise where entity_resolution.notes could run longer). 4096 has ~45% headroom over the one observed complete run (2829) but is not a hard guarantee against every possible verbose response; if truncation recurs the fix would be a further budget increase or trimming the free-text fields (evidence_summary/notes) in the prompt, not a re-litigation of this hypothesis."
next_action: "DONE. Both fixes applied and verified: (1) scripts/smoke_closed_won_research.py setdefault->direct assignment for USE_MOCK_WEB_RESEARCH=false (primary, explains reported symptom), (2) max_tokens 2000->4096 in src/web_research.py + scripts/build_cloud_workflows.py (secondary, confirmed-real truncation bug that would have surfaced once (1) was fixed). Offline suite 139/51 green. Live smoke re-run shows 10/10 evidence coverage. Session archived to resolved/."

## Symptoms

expected: For every closed-won company where lv_produces_content=true (or false) is answered, evidence_by_field.lv_produces_content should contain a supporting URL (per RESEARCH_SYSTEM prompt contract in src/web_research.py and TS-3/OC-1 semantics in src/taxonomy.py).
actual: lv_produces_content=true for all 10 companies in the live smoke, but evidence_by_field.lv_produces_content was empty ("—") for all 10 — see 13-SMOKE-CLOSED-WON.md.
errors: none (no exception) — this is a silent data-quality gap, not a crash.
reproduction: |
  set -a && source .env && set +a
  .venv/bin/python scripts/smoke_closed_won_research.py --limit 10
  # live: costs HubSpot reads + up to 5 Anthropic web searches per company
started: First live run of this smoke script (Phase 13 Task 4b), 2026-07-21.

## Eliminated

## Evidence

- timestamp: 2026-07-21T04:26:00Z
  checked: src/web_research.py RESEARCH_SYSTEM prompt + claude_web_research() live path
  found: Prompt DOES ask for top-level "evidence_by_field":{"<field>":"<url>"} keyed by exact field name, and explicitly instructs "Cite a supporting URL in evidence_by_field for every field you set in data". Live path does `data = _extract_json(text); ProviderResult(**data)` — a direct unpack of the raw model JSON, no intermediate transform. If raw JSON has key "evidence_by_field", pydantic sets ProviderResult.evidence_by_field directly (field names match exactly).
  implication: "naive prompt-doesn't-ask" theory (not in original hypothesis list) is definitively wrong; confirms trigger's framing. Need to see whether model actually emits that key in live responses.

- timestamp: 2026-07-21T04:26:00Z
  checked: scripts/smoke_closed_won_research.py lines 102-127
  found: Calls `claude_web_research(record)` directly (not `to_provider_result`), builds `validate_research_output({"data": result.data, "evidence_by_field": result.evidence_by_field, "matched": result.matched, "confidence": result.confidence})`, then reads `validated["evidence_by_field"].get("lv_produces_content")`. Key names match at every hop (evidence_by_field -> evidence_by_field -> .get("lv_produces_content")). No obvious wrong-key bug in the smoke script itself (H1 looks weak on static read).
  implication: H1 (smoke script prints wrong key) is unlikely but not yet eliminated with live evidence — depends on whether result.evidence_by_field was ever populated upstream.

- timestamp: 2026-07-21T04:26:00Z
  checked: src/taxonomy.py validate_research_output() lines 109-151
  found: "evidence_by_field = dict(raw.get('evidence_by_field') or {})" is copied verbatim into the return dict unchanged (no filtering, no key remapping). This matches spec D2 (verbatim copy).
  implication: H2 (taxonomy.py drops evidence_by_field) is structurally false on read — the function is a faithful pass-through. Eliminating pending live confirmation.

- timestamp: 2026-07-21T04:35:00Z
  checked: "Live API call #1: src.web_research.claude_web_research live path replicated standalone (max_tokens=2000, real Anthropic API, company=Melbourne Racing Club/mrc.racing.com)"
  found: "msg.stop_reason == 'max_tokens'. usage.output_tokens_details.thinking_tokens=1251 (of ~2379 total). Raw text IS truncated: valid 'data' block, valid 'evidence_by_field' block (9 keys incl. lv_produces_content -> a real racingaustralia.horse URL) present in the RAW text, but the response cuts off mid-string inside entity_resolution.notes before the JSON closes. _extract_json's direct json.loads AND its regex fallback both raised JSONDecodeError."
  implication: "H4 (max_tokens truncation) has direct, unambiguous evidence: stop_reason literally says max_tokens. The model DOES write evidence_by_field with a correct lv_produces_content URL when given room — H3 (model only fills the legacy aggregate) is weakened by this single data point. Truncation lands after evidence_by_field in this instance but the exact cut point is response-dependent — in other runs (e.g. the original 10-company report) the cut could land before evidence_by_field is ever written, or land such that the regex fallback still produces a syntactically valid but incomplete dict silently missing evidence_by_field (defaults to {} via ProviderResult's Field(default_factory=dict), no exception) — consistent with the reported symptom (empty evidence, no crash, correct verdict)."

- timestamp: 2026-07-21T04:36:00Z
  checked: "Live API call #2 (falsification test): identical call, only change max_tokens 2000 -> 8192."
  found: "msg.stop_reason == 'end_turn'. Complete, valid JSON. usage.output_tokens_details.thinking_tokens=1085, total output_tokens=2829 — well under the new cap. evidence_by_field fully populated for all 9 data fields, including lv_produces_content -> https://www.youtube.com/user/CaulfieldRacing/videos (a real URL)."
  implication: "Root cause CONFIRMED: raising max_tokens alone (no prompt change) eliminates the truncation and evidence_by_field is populated correctly. This directly falsifies H2/H3 as the primary cause and confirms H4. src/web_research.py:99 and scripts/build_cloud_workflows.py:1385 both hardcode max_tokens=2000 (parity — same bug in both places, per Phase 13 D-decision that they must not drift)."

## Evidence (continued)

- timestamp: 2026-07-21T04:45:00Z
  checked: "Re-ran the live smoke AFTER applying the max_tokens 2000->4096 fix (both src/web_research.py and scripts/build_cloud_workflows.py, rebuilt, offline tests green)."
  found: "IDENTICAL symptom persisted: all 10 companies lv_produces_content=True, evidence='-' for every one. This falsifies max_tokens-truncation as the (sole) explanation of the REPORTED symptom — the fix should have changed the outcome if truncation were the active cause on this run."
  implication: "Something else must be intercepting these specific calls. Went back to first principles per debugger-philosophy: treat own code as foreign, re-read the actual call path end to end rather than trusting the earlier hypothesis."

- timestamp: 2026-07-21T04:47:00Z
  checked: "Called src.web_research.claude_web_research(record) DIRECTLY (bypassing smoke script) for the same company (Melbourne Racing Club) with the max_tokens=4096 fix in place, real ANTHROPIC_API_KEY sourced from .env."
  found: "result.evidence_by_field WAS fully populated (9 keys incl. lv_produces_content -> a real YouTube URL) via model_dump(). The function itself works correctly when called directly."
  implication: "The bug is not inside claude_web_research()/validate_research_output() — it is in how the SMOKE SCRIPT invokes claude_web_research(), or in environment state surrounding that invocation. Direct call succeeds; smoke-script-mediated call does not, on the same company, same session."

- timestamp: 2026-07-21T04:49:00Z
  checked: "scripts/smoke_closed_won_research.py line 53: `os.environ.setdefault('USE_MOCK_WEB_RESEARCH', 'false')`, cross-referenced against .env line 20 (`USE_MOCK_WEB_RESEARCH=true`) and the documented repro command (`set -a && source .env && set +a` before running the script)."
  found: "`set -a && source .env` EXPORTS USE_MOCK_WEB_RESEARCH=true into the process environment before Python even starts. `os.environ.setdefault(key, value)` only sets a key if it is ABSENT — since the key is already present (as \"true\"), the smoke script's attempt to force live mode is a silent no-op. Verified directly: `os.environ['X']='true'; os.environ.setdefault('X','false')` leaves X as 'true'. Confirmed by grep that scripts/smoke_closed_won_research.py is the ONLY call site of USE_MOCK_WEB_RESEARCH outside of src/web_research.py's own os.getenv check and a monkeypatched pytest test (tests/test_main.py, not affected)."
  implication: "ROOT CAUSE CONFIRMED. Every 'live' smoke run to date (including the one behind 13-SMOKE-CLOSED-WON.md) has silently been hitting mock_claude_web_research() -> the static tests/fixtures/claude_web_research_company.json fixture for every single company, regardless of its real HubSpot data. That fixture: (a) returns identical data (lv_produces_content=true, same content types) for every company since it never varies by input, explaining the flat 10/10 true result, and (b) predates the Phase 13 evidence_by_field field entirely (grep confirms the fixture JSON has no evidence_by_field key at all), so ProviderResult defaults it to {} for every call. Zero live Anthropic web-research calls were ever made by the reported smoke run. The Company/Domain columns in the report looked real because those come straight from the actual HubSpot record (props.get('name')/props.get('domain')) fetched before the (mocked) research call — only the research step itself was silently faked."

## Resolution

root_cause: "PRIMARY (explains the reported symptom): scripts/smoke_closed_won_research.py:53 uses `os.environ.setdefault(\"USE_MOCK_WEB_RESEARCH\", \"false\")` to force live research mode, but the documented run command sources .env first (`set -a && source .env`) which exports `USE_MOCK_WEB_RESEARCH=true` (the correct default for every OTHER offline-safe workflow) into the process environment before Python starts. `setdefault` never overrides an already-present key, so the override silently fails and every company's \"research\" call actually returns the static tests/fixtures/claude_web_research_company.json fixture — identical data every time (lv_produces_content=true for all 10, matching the report) and, because that fixture predates the Phase 13 evidence_by_field field, an empty evidence_by_field for all 10 (matching the report). No live Anthropic call was ever made by this smoke run. SECONDARY (real, confirmed, independently fixed): max_tokens=2000 (in both src/web_research.py's live path and the parity n8n prompt in scripts/build_cloud_workflows.py) is genuinely insufficient once live calls DO happen — claude-sonnet-5's extended thinking alone consumes ~1000-1300 tokens on this prompt, and two direct live probes proved stop_reason=max_tokens truncation drops evidence_by_field (emitted after the data block) at the 2000 cap, while 4096-8192 completes cleanly with evidence_by_field fully populated. This second bug was masked by the first (the smoke script was never actually reaching the live API), but would have caused intermittent evidence loss once the primary bug is fixed and live calls actually happen — so it is fixed too, not reverted."
fix: "(1) PRIMARY FIX: scripts/smoke_closed_won_research.py:53 changed from `os.environ.setdefault(\"USE_MOCK_WEB_RESEARCH\", \"false\")` to `os.environ[\"USE_MOCK_WEB_RESEARCH\"] = \"false\"` (direct assignment forces live mode regardless of what .env exported — matches the script's stated intent and its own credentials gate, which already requires the operator to explicitly provide real ANTHROPIC_API_KEY + HUBSPOT_PRIVATE_APP_TOKEN before this line is ever reached). (2) SECONDARY FIX (kept, already applied and verified before the primary bug was found): max_tokens 2000 -> 4096 in src/web_research.py (live API call) and scripts/build_cloud_workflows.py (ENRICH_BUILD_RESEARCH_REQUEST n8n prompt body), preserving Phase 13 parity; n8n workflows rebuilt, confirmed idempotent (byte-identical second rebuild), git diff shows only the intended lines."
verification: |
  (1) Offline pytest 139/139 + node 51/51 green, unchanged baseline (this script is not
  imported by any test, docstring-confirmed).
  (2) n8n rebuild idempotent (sha256 identical across two consecutive rebuilds), git diff
  limited to the two max_tokens lines + one generated JSON line.
  (3) Live smoke re-run AFTER both fixes (2026-07-21, set -a && source .env && set +a &&
  .venv/bin/python scripts/smoke_closed_won_research.py --limit 10):
  true=9 null=0 false=1 unmatched=0 (of 10). Every single company now has a DISTINCT,
  genuine evidence URL for lv_produces_content (e.g. Australian Turf Club ->
  youtube.com/user/AtcracesTV, Wyong -> bets.com.au/.../wyong-races-live-stream, Panasonic
  Studio Productions -> pspvideo.com.au) instead of uniform "-" — this is the direct fix
  confirmation for the reported bug. Script exits 2 because it flagged one evidenced FALSE
  (Queensland Racing Integrity Commission, a regulator/integrity body, not itself a content
  producer) — this is the smoke script's own by-design RED FLAG path (a real, evidenced
  research finding worth a human look), not a script failure; the prior "all true, no
  evidence" run never reached this path because it was silently querying a static mock
  fixture that always returns the same true/no-evidence answer regardless of company.
  Per the task's own success bar ("same or better verdict split AND evidence URLs populated
  for answered fields"): evidence coverage went from 0/10 to 10/10 (every answered field has
  a real citable URL) — the primary criterion this bug was about. The split changing from
  10/0/0/0 to 9/0/1/0 reflects the tool doing REAL per-company research for the first time
  (previously it was not researching anything) and surfacing one genuine, evidenced signal
  for human review, which is exactly the smoke test's stated purpose.
files_changed:
  - scripts/smoke_closed_won_research.py
  - src/web_research.py
  - scripts/build_cloud_workflows.py
  - n8n/wf_enrichment_local_live.json (regenerated artifact)
