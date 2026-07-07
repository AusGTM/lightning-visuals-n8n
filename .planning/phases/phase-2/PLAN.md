---
phase: phase-2
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/icp_scoring.py
  - tests/test_icp_scoring.py
autonomous: true
requirements: [REQ-icp-scoring-model, REQ-anti-icp-vetoes, REQ-graduated-deductions, REQ-tiering, REQ-org-type-targeting]
must_haves:
  truths:
    - "`.venv/bin/python -m pytest tests/test_icp_scoring.py -q` exits 0 (the phase's runnable proof), run from the repo root"
    - "AU governing-body/league + produces_content + $5-500M revenue scores Tier A; AU content_producer scores Tier B; AU individual_club_team scores Tier C (REQ-icp-scoring-model, REQ-org-type-targeting, REQ-tiering)"
    - "Non-ANZ geography, produces_content False, and hardware_vendor each force Tier D with lv_anti_icp_flag True and a populated anti_icp_reason (REQ-anti-icp-vetoes)"
    - "Gambling operator (-20) and the >$500M revenue decay (-5/-15/-30/-50) reduce the score and never set the anti-ICP flag (REQ-graduated-deductions)"
    - "Unknown org_type or None produces_content yields Needs Review / Unscored at confidence 55 (not a false A/B/C/D score); every result stamps breakdown['version'] and scoring_version = lv-icp-v0.1 (REQ-tiering)"
  artifacts:
    - src/icp_scoring.py
    - tests/test_icp_scoring.py
  key_links:
    - "compute_icp_score(record: HubSpotRecord, candidate_patch: dict) -> ICPScoreResult — the signature Phase 3 (merge_policy) and Phase 4 (main) call"
    - "src/icp_scoring.py reads config/icp_scoring.yaml (version lv-icp-v0.1) via a repo-root-relative load_yaml, so the proof must run with cwd = repo root"
    - "src/icp_scoring.py imports HubSpotRecord and ICPScoreResult from src.schemas (Phase 1 provides)"
---

<objective>
Build the ICP scoring engine — the crown jewel. Given firmographic + enrichment signals on a HubSpotRecord (plus an optional candidate_patch that overrides record properties), compute an ICP fit score, an A/B/C/D/Needs Review/Unscored tier, the anti-ICP hard-veto flag, a recommended motion, a confidence, and a breakdown JSON stamped with the rubric version. Cover the behavior with a comprehensive, deterministic unit-test suite that is the phase's runnable proof.

Purpose: This is the single most valuable output of the whole MVP (ROADMAP: "the crown jewel"). Phase 3's non-clobber merge and Phase 4's dry-run PATCH both call compute_icp_score to produce the lv_icp_* canonical outputs. If the engine mis-scores the ideal customer or fires a veto incorrectly, every downstream A/B/C/D decision is wrong.

Output: src/icp_scoring.py (compute_icp_score, load_yaml, boolish, get_signal) transcribed from CLAUDE.md §12.7 with one documented correctness fix, and tests/test_icp_scoring.py with 16 scoring assertions. Implements REQ-icp-scoring-model, REQ-anti-icp-vetoes, REQ-graduated-deductions, REQ-tiering, REQ-org-type-targeting.
</objective>

<execution_context>
The authoritative source is `CLAUDE.md` at the repo root — §12.7 contains a ready implementation of `src/icp_scoring.py`. Transcribe it; do not design from scratch. The rubric it reads, `config/icp_scoring.yaml` (version `lv-icp-v0.1`), was created in Phase 1 and is frozen — this phase does NOT change it. Scope boundary: ONLY `src/icp_scoring.py` and `tests/test_icp_scoring.py`. Do NOT create or touch normalizer, providers, web_research, merge_policy, classifier, validator, hubspot_client, or main.py — those are Phases 3-4.
</execution_context>

<context>
@CLAUDE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@src/schemas.py
@config/icp_scoring.yaml
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Transcribe the ICP scoring engine (src/icp_scoring.py)</name>
  <files>src/icp_scoring.py</files>
  <behavior>
Anchor input -> output pairs the engine must satisfy (candidate_patch keys shown; record.properties may be empty). All verified against config/icp_scoring.yaml (lv-icp-v0.1):
    - governing_body_league + produces_content True + region AU + revenue 5-50M  -> score 80, tier A, anti_icp_flag False
    - content_producer + produces_content True + AU + 5-50M                       -> score 60, tier B, anti_icp_flag False
    - individual_club_team + produces_content True + AU + revenue 1-5M (0-band)   -> score 35, tier C, anti_icp_flag False
    - region Other (non-ANZ)                                                      -> tier D, anti_icp_flag True, reason "Non-ANZ geography"
    - produces_content False                                                      -> tier D, anti_icp_flag True, reason "No broadcast or streaming content"
    - lv_is_hardware_vendor True                                                  -> tier D, anti_icp_flag True, reason "Hardware/AV/LED vendor, not sports-media buyer"
    - lv_is_gambling_operator True (else gov+content+AU+5-50M)                     -> score 60 (80 minus 20), anti_icp_flag False (deduction, not veto)
    - revenue 500-750M / 750M-1B / 1B-1.2B / 1.2B+ (else gov+content+AU)          -> revenue points -5 / -15 / -30 / -50, anti_icp_flag False
    - lv_org_type absent (unknown) + produces_content True, score >= 15           -> tier "Needs Review", confidence 55
    - produces_content absent (None), org known, score >= 15                      -> tier "Needs Review", confidence 55
    - lv_org_type absent + score < 15, no veto                                    -> tier "Unscored", confidence 55
    - every result: breakdown["version"] == "lv-icp-v0.1" and scoring_version == "lv-icp-v0.1"
  </behavior>
  <action>
Transcribe `src/icp_scoring.py` from CLAUDE.md §12.7 verbatim — `load_yaml`, `boolish`, `get_signal`, and `compute_icp_score` — importing `HubSpotRecord` and `ICPScoreResult` from `src.schemas`. Keep the hard-coded tier cutoffs as-is (>= 70 A, >= 40 B, >= 15 C, else Unscored); CONFIRM in a short header comment that they agree with `config/icp_scoring.yaml` `tier_rules` (A min 70, B 40-69, C 15-39) — they do, so config and code are consistent for the MVP. Keep the Needs Review / Unscored branch exactly as written: when `org_type == "unknown"` OR `produces_content is None`, set confidence 55, then tier "Needs Review" if score >= 15 else "Unscored", motion "research_more". Keep `load_yaml` reading the repo-root-relative path `config/icp_scoring.yaml`; the phase proof runs with cwd = repo root, so do not rework path resolution.

APPLY EXACTLY ONE documented correctness fix — the `produces_content` points lookup. §12.7 writes `cfg["base_score"]["produces_content"].get(str(produces_content).lower(), 0)`. That is wrong against the Phase-1 config: PyYAML parses the YAML keys `true:` / `false:` as Python booleans, so the loaded dict is `{True: 20, False: 0, "unknown": 0}`, and looking it up with the strings `"true"`/`"false"` never matches — it silently returns 0, zeroing out the +20 "produces content" rule required by REQ-icp-scoring-model and dropping the flagship AU-governing-body case from Tier A (80) to Tier B (60), which fails phase success criterion 1. Change ONLY that one line to look up the boolean/None value directly: `cfg["base_score"]["produces_content"].get(produces_content, 0)` so True -> 20, False -> 0, None -> 0 (fallback). Add an inline comment naming this as the documented deviation and its reason. This mirrors the Phase-1 precedent of applying minimal, flagged fixes to SPEC transcription defects. Leave org_type, geography, and revenue_band lookups untouched (their string keys already match the YAML).

Do NOT read the tier_rules / recommended_motion mapping differently than §12.7 does; motion still comes from `cfg["recommended_motion"].get(tier, "research_more")` before the Needs Review / Unscored override. Do NOT add config for values that never change, and do NOT implement anything beyond these four names.
  </action>
  <verify>
    <automated>.venv/bin/python -c "from src.schemas import HubSpotRecord; from src.icp_scoring import compute_icp_score; r=compute_icp_score(HubSpotRecord(object_type='companies',id='789',properties={}), {'lv_org_type':'governing_body_league','lv_produces_content':True,'lv_country_region_normalized':'AU','lv_revenue_band':'5-50M'}); assert (r.tier,r.score,r.anti_icp_flag)==('A',80,False), r; assert r.scoring_version=='lv-icp-v0.1'; print('engine OK: gov+content+AU+midrev -> A/80')"</automated>
  </verify>
  <done>src/icp_scoring.py imports cleanly; compute_icp_score returns an ICPScoreResult; the AU governing-body + content + $5-500M case scores 80 / Tier A / anti_icp_flag False with scoring_version lv-icp-v0.1; the produces_content fix is present and commented.</done>
</task>

<task type="auto">
  <name>Task 2: Scoring unit-test suite (tests/test_icp_scoring.py) — the runnable proof</name>
  <files>tests/test_icp_scoring.py</files>
  <action>
Write `tests/test_icp_scoring.py` as the phase's runnable proof: plain pytest, plain asserts, no fixture framework. Import `HubSpotRecord` from `src.schemas` and `compute_icp_score` from `src.icp_scoring`. Provide a tiny helper that builds a companies HubSpotRecord with empty `properties` and calls `compute_icp_score(record, candidate_patch)` — every case drives the engine purely through `candidate_patch`. Always set `lv_country_region_normalized` explicitly (AU / NZ / Other) so geography is deterministic and never falls back to the `country` property.

Implement these 16 cases (one test function each, or parametrized where natural). Assert `tier` and `anti_icp_flag` on every case; assert `score` and the noted extras where called out. All expected values below are verified against the fixed engine + config/icp_scoring.yaml — assert them as written:

| # | candidate_patch (all companies) | assert |
|---|---|---|
| 1 | org governing_body_league, produces_content True, region AU, revenue 5-50M | tier A, anti False, score 80 |
| 2 | org content_producer, produces_content True, region AU, revenue 5-50M | tier B, anti False, score 60 |
| 3 | org individual_club_team, produces_content True, region AU, revenue 1-5M | tier C, anti False, score 35 |
| 4 | org governing_body_league, produces_content True, region Other, revenue 5-50M | tier D, anti True, anti_icp_reason contains "Non-ANZ" |
| 5 | org governing_body_league, produces_content False, region AU, revenue 5-50M | tier D, anti True, anti_icp_reason contains "No broadcast or streaming content" |
| 6 | org hardware_vendor, produces_content True, lv_is_hardware_vendor True, region AU, revenue 5-50M | tier D, anti True, anti_icp_reason contains "Hardware/AV/LED vendor" |
| 7 | org governing_body_league, produces_content True, lv_is_gambling_operator True, region AU, revenue 5-50M | anti False, score 60, breakdown graduated_deductions includes gambling_operator -20 |
| 8 | org governing_body_league, produces_content True, region AU, revenue 500-750M | anti False, score 65 (revenue component -5) |
| 9 | org governing_body_league, produces_content True, region AU, revenue 750M-1B | anti False, score 55 (revenue component -15) |
| 10 | org governing_body_league, produces_content True, region AU, revenue 1B-1.2B | anti False, score 40 (revenue component -30) |
| 11 | org governing_body_league, produces_content True, region AU, revenue 1.2B+ | anti False, score 20 (revenue component -50) |
| 12 | org ABSENT, produces_content True, region AU, revenue 5-50M | tier "Needs Review", confidence 55, anti False |
| 13 | org governing_body_league, produces_content ABSENT, region AU, revenue 5-50M | tier "Needs Review", confidence 55, anti False |
| 14 | org ABSENT, produces_content True, region AU, revenue 1B-1.2B | tier "Unscored", confidence 55, score 0 |
| 15 | org governing_body_league, produces_content True, region NZ, revenue 5-50M | tier A, anti False, score 80 |
| 16 | org governing_body_league, produces_content True, region AU, revenue 5-50M | scoring_version == "lv-icp-v0.1" AND breakdown["version"] == "lv-icp-v0.1" |

"ABSENT" means omit the key from candidate_patch (record.properties is empty), so `get_signal` returns the "unknown"/None default — this exercises the Needs Review / Unscored branch. For cases 8-11, read the revenue component points out of `breakdown["components"]` (the entry with signal "revenue_band") to assert the exact decay, so the test pins REQ-graduated-deductions precisely.

Two deliberate, documented test-design choices to encode as short comments:
- Case 3 (individual club) uses revenue 1-5M (a 0-point band), NOT mid-market. CLAUDE.md §24.1 case 3 does not specify a revenue band for the club (unlike case 1, which pins $5-500M). Under correct produces_content scoring, club (5) + content (20) + AU (10) + mid-market revenue (10) = 45 = Tier B; choosing a 0-point revenue band gives 5 + 20 + 10 + 0 = 35 = Tier C, which is the outcome REQ-org-type-targeting and success criterion 1 require. This is a rubric-weight sensitivity (the individual-club base weight is generous relative to content+geo) that belongs to the frozen Phase-1 rubric and the v2 sign-off gate, not this phase.
- CLAUDE.md §24.1 cases 11-16 (provider org-type conflict -> Sonnet, content conflict -> Sonnet, missing evidence URL -> human review, manual domain -> stage only, existing phone -> stage only, blank phone + agreement -> promote) are NOT scoring behaviors — compute_icp_score has no provider-conflict, evidence, phone, or promote/stage logic. They belong to Phase 3's merge/escalation layer (REQ-enrichment-plan, MVP-02, MVP-03) and will be covered by tests/test_merge_policy.py then. Do NOT fabricate them here against a function that cannot express them; the 16 cases above are the real scoring coverage (full veto set, full revenue-decay sweep, NZ geography, unknown-content, Unscored) instead.

Resolve no external paths in the test itself; compute_icp_score handles config loading. The proof runs from the repo root.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_icp_scoring.py -q</automated>
  </verify>
  <done>pytest passes: all 16 scoring cases green — Tier A/B/C for AU gov/producer/club, Tier D + anti_icp_flag + reason for the three vetoes, gambling and the four revenue-decay bands as deductions with no flag, unknown org / None content as Needs Review / Unscored at confidence 55, and the version stamp present. Proves all four Phase 2 success criteria.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| config/icp_scoring.yaml -> scoring engine | Repo-local, trusted rubric authored in Phase 1; loaded via PyYAML safe_load |
| candidate_patch / record.properties -> compute_icp_score | In-process dicts from callers (tests here; Phase 3 merge later); no external/untrusted input in this phase |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-phase-2-01 | Tampering | config/icp_scoring.yaml load | low | accept | Rubric is static repo-local test/config data loaded with yaml.safe_load (no arbitrary object construction); no untrusted input path exists in this phase. |
| T-phase-2-02 | Information disclosure | breakdown JSON / anti_icp_reason | low | accept | Outputs contain only rubric-derived scoring rationale (points, tier, veto reasons); no secrets or PII flow through compute_icp_score. |

No package-manager installs occur in this phase (all dependencies were installed in Phase 1), so no package-legitimacy checkpoint is required.
</threat_model>

<verification>
Full-phase proof, run from the repo root:

```
.venv/bin/python -m pytest tests/test_icp_scoring.py -q
```

Expected: all 16 scoring assertions pass. This single run exercises SC1 (AU gov -> A, producer -> B, club -> C), SC2 (non-ANZ / no-content / hardware -> D + anti_icp_flag + reason), SC3 (gambling -20 and revenue -5/-15/-30/-50 as deductions with no flag), and SC4 (unknown org / None content -> Needs Review / Unscored, plus breakdown + scoring_version stamped lv-icp-v0.1).
</verification>

<success_criteria>
1. SC1 — AU governing-body/league + produces_content + $5-500M revenue -> Tier A; AU content_producer -> Tier B; AU individual_club_team -> Tier C.
2. SC2 — Non-ANZ, produces_content False, or hardware_vendor -> Tier D with lv_anti_icp_flag True and a populated anti_icp_reason.
3. SC3 — Gambling operator (-20) and >$500M revenue decay (-5/-15/-30/-50) reduce the score without ever setting the anti-ICP flag.
4. SC4 — Missing org_type or produces_content -> Needs Review / Unscored (confidence 55, not a false A/B/C/D score); every result emits a breakdown JSON stamped with scoring_version lv-icp-v0.1.

All four are proven by `pytest tests/test_icp_scoring.py` passing.
</success_criteria>

<output>
Create `.planning/phases/phase-2/phase-2-01-SUMMARY.md` when done, recording: the two files created, the passing pytest output, and the two documented deviations — (1) the produces_content boolean-key fix on the §12.7 lookup (why it was needed: PyYAML boolean keys vs string lookup silently zeroed the +20 content rule and dropped the flagship case from Tier A to Tier B), and (2) the case-3 revenue choice plus the §24.1 cases 11-16 out-of-scope note (merge/escalation, Phase 3).
</output>
