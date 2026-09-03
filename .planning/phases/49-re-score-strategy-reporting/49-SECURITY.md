---
phase: "49"
slug: "re-score-strategy-reporting"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (high).
# No registered threat was found OPEN. Two items are surfaced for operator disposition and
# deliberately NOT dispositioned by the audit: an unregistered direct-library-bypass threat class
# (Divergence 1) and a missing .planning/WINDOWS.md ledger row (Divergence 2). Neither changes a
# register status — see "Divergences" for why.
threats_open: 0
threats_open_below_threshold: 0
asvs_level: 1
created: "2026-09-03"
---

# Phase 49 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
>
> **Run retroactively on 2026-09-03**, as part of the cross-phase secure-phase sweep of phases
> 46–63. Phase 49 shipped without a SECURITY.md because the `verify:post` secure-phase hook was
> skipped — `workflow.security_enforcement` was absent from `.planning/config.json` and therefore
> **defaulted to enabled**. The key is now set explicitly.
>
> All seven plans carry plan-time `<threat_model>` blocks (`register_authored_at_plan_time: true`),
> so this is a **verification pass, not retroactive-STRIDE**. 42 threats — the phase spans a dry
> re-score lane, an operator runbook, a prompt change, a deploy, two armed write windows and a
> published report.
>
> Phase 49 belongs to the **archived v0.9 milestone**. Mitigations were verified at current HEAD
> (`8ffe359`), not at the phase's own close.

---

## Trust Boundaries

Consolidated from the seven PLAN threat models.

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| driver → HubSpot CRM v3 (49-01/05) | a bearer token authorises writes to 66 production company records; the driver decides both scope and payload | five `*_score` component properties |
| operator shell → driver (49-01/05) | two env vars are the entire write authorisation; a leaked or persisted value silently arms the next run | `DRY_RUN`, `ALLOW_SCORE_BACKFILL` |
| oracle config → payload (49-01) | `config/icp_scoring.yaml` values flow untransformed into production property values | rubric weights |
| runbook → operator action (49-02) | the document is the operator's only pre-decision surface; a wrong number causes a wrong arming decision | cost figures, population count |
| config file → production scoring (49-02) | a rubric edit propagates to every scored record's tier with no other approval step | weight table |
| build script → deployed workflow JSON (49-03) | generated code becomes the prompt an LLM executes against real company data | org-type definition strings |
| taxonomy config → model prompt (49-03) | a definition string flows untransformed into a system prompt | `config/taxonomy.yaml` text |
| frozen fixture → change detection (49-03) | the only mechanism detecting an unintended change to emitted node code | `jsCode` bytes |
| operator shell → n8n Cloud API (49-04) | two env vars grant authority to overwrite production workflow definitions | `DRY_RUN`, `ALLOW_N8N_DEPLOY` |
| stored workflow body → running workflow (49-04) | a PUT changes storage; only a bounce changes what executes — the gap is where a false proof lives | workflow JSON |
| deploy → arming state (49-04) | a deploy PUT can close or reopen an arming window as a side effect | baked write-safety flags |
| armed shell → subsequent shells (49-05) | an arming variable that outlives the window silently arms the next invocation | env |
| model output → production veto state (49-06) | research output can clear a hard veto and return an excluded company to the target list | `lv_produces_content`, `lv_country_region_normalized` |
| n8n allowlist → write scope (49-06) | an empty or wrong allowlist changes what the lane will touch while still reporting armed | `TEST_RECORD_IDS` / `TEST_RECORD_DOMAINS` |
| committed snapshots → report claims (49-07) | every number the operator acts on originates in a committed JSON file | tiers, scores, ids |
| report → published Artifact (49-07) | internal company names, tiers and scores leave the repository into a shareable surface | company identity |

---

## Threat Register

42 threats, `T-49-01` … `T-49-42`.

### 49-01 — the dry re-score plan lane

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-49-01 | Elevation of Privilege | `_writes_allowed()` | high | mitigate | `scripts/rescore_population.py:84-87` — `(not dry_run) and allow`, both keys required. The disarmed path builds and prints, never reaching `batch_update_companies` (`:319-323`, `:357-367`). Refusal tested: `tests/test_rescore_population.py:267` `test_execute_disarmed_no_arm_vars_builds_prints_no_write` and `:276` `test_execute_dry_run_false_but_allow_unset_zero_writes` — 57/57 green at HEAD. | closed |
| T-49-02 | Tampering | payload builder | high | mitigate | `assert_payload_scope` at `:191-204` — positive equality (`keys != expected` against `set(COMPONENT_PROPS)`), so an over-broad **and** a *partial* write both raise. Called on every payload: `:315` (canary), `:359` (each chunk). Tests `:176`, `:189`, `:331`. | closed |
| T-49-03 | Tampering | population selection | high | mitigate | `enforce_exact_population` imported at `:61` from `scripts/backfill_seed_company_scores.py`, called in `_derive_and_confirm_population` `:223` against a **second** live derivation `:222`. No id literal anywhere in the file. Test `:287` `test_execute_armed_population_drift_refuses_and_makes_no_write`. | closed |
| T-49-04 | Information Disclosure | `hs_headers()` | medium | mitigate | The driver contains no `hs_headers` reference and no header print; the four `json.dumps` sites (`:317`, `:329`, `:360`, `:475`) emit plan / components / chunk-ids / snapshot only. Refusal messages print `EXPECTED_PORTAL_ID`, a committed constant already plaintext throughout the repo's evidence — not a new disclosure. | closed |
| T-49-05 | Spoofing | portal targeting | medium | mitigate | `_portal_ok()` `:80-81` against `EXPECTED_PORTAL_ID = "22617666"` (`scripts/backfill_seed_company_scores.py:67`), asserted before any network call at **all four** entry points: `:301`, `:338`, `:434`, `:461`. Test `:236`. | closed |
| T-49-06 | Denial of Service | HubSpot batch endpoint | low | accept | `src/hubspot_client.py:95-100` raises `ValueError` on >100 rather than sending or truncating; 66 records is a single call. → AR-49-01 | closed (accepted) |

### 49-02 — the operator runbook and the D-09 rubric guard

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-49-07 | Tampering | `config/icp_scoring.yaml` | high | mitigate | `tests/test_rubric_change_guard.py:32-58` pins base_score's four tables **and** `PINNED_GRADUATED_DEDUCTIONS = {}`; `:94` diffs the empty map so a re-introduced key fails; four mutation cases at `:121-136`, including `graduated_deduction_reintroduced`, prove the test has teeth; the failure message names the runbook (`:104`) and that is asserted (`:160`). Green at HEAD. **Scope, stated rather than implied:** "full scoring surface" means the four `base_score` tables plus `graduated_deductions`, per the test's own definition — `hard_vetoes` and `tier_rules` are **not** pinned. | closed |
| T-49-08 | Repudiation | runbook cost figures | high | mitigate | `docs/OPERATOR-RESCORE.md:143-146` names the capture; the plan's verify one-liner (`49-02-PLAN.md:88`) parses `49-PLAN-OUTPUT.json` and asserts `population_count` / `chunk_size` / `chunks` / `max_records` appear verbatim in the doc. **Re-run this audit: `missing: []`, exit 0** — still holds after the two post-seal runbook amendments (see Drift notes). | closed |
| T-49-09 | Information Disclosure | captured `--plan` JSON | low | accept | `49-PLAN-OUTPUT.json` read in full (100 lines): 66 company ids, counts, timestamps, arm-key *names*, integer cost fields. No token, no personal data. → AR-49-02 | closed (accepted) |
| T-49-10 | Elevation of Privilege | runbook invocation lines | medium | mitigate | `docs/OPERATOR-RESCORE.md:300-302` — arm vars "set **per-shell only** — never written into `.env`, never exported into a profile, never left set in a shell that outlives the [window]". All four mode invocations (`:307`, `:314`, `:320`, `:327`) use the prefixed per-invocation form. | closed |

### 49-03 — org-type definitions in the research prompt

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-49-11 | Tampering | emitted research `jsCode` | high | mitigate | `tests/n8n/orgTypeDefinitionsPrompt.test.mjs:69,76` pins every key **and its definition text** in the prompt the node actually *returns*; negative control at `:93`. The re-baseline was an explicit act — commit `c671ebf`, reason recorded at `49-03-SUMMARY.md:87`, with `git diff HEAD -- tests/test_companies_factory_frozen.py \| grep -cE '^[-+][[:space:]]*assert '` = 0 (`:94`), i.e. no assertion was weakened. 3/3 green at HEAD. | closed |
| T-49-12 | Tampering | `n8n/wf_*.json` | high | mitigate | `49-03-SUMMARY.md:79` and `:167` — both files byte-reproducible from `scripts/build_cloud_workflows.py`, `git diff --stat` identical across two consecutive full builds. Not re-run in this pass: rebuilding writes `n8n/*.json` and this audit was read-only. (The equivalent claim **was** independently re-proved for phase 48 in an isolated scratchpad — see `48-SECURITY.md` T-48-07.) | closed |
| T-49-13 | Spoofing | prompt-injected definition text | medium | mitigate | The source is repo-controlled: `src/taxonomy.py:20` loads `config/taxonomy.yaml`, `:48` derives `ORG_TYPE_DEFINITIONS`; a single escape path at `scripts/gen_taxonomy_js.py:75` — `json.dumps(ORG_TYPE_DEFINITIONS, indent=2)`, with the reason stated in a comment at `:16`. | closed |
| T-49-14 | Repudiation | undisclosed prompt change | medium | mitigate | `docs/WEB-RESEARCH-SPEC.md:217` — a dated `**Update (2026-08-13, Phase 49 Plan 03).**` added *beneath* the original `Known divergence` at `:208`, which is left intact. Recorded, not rewritten. | closed |
| T-49-15 | Elevation of Privilege | none introduced | low | accept | All five 49-03 commits (`dac9a8d`, `41064de`, `986e58f`, `5356528`, `c671ebf`) touch only taxonomy source, generated JS, committed workflow JSON, the spec doc and tests — no deploy invocation, no credential, no arming surface. → AR-49-03 | closed (accepted) |

### 49-04 — deploy and prove

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-49-16 | Elevation of Privilege | deploy arming | high | mitigate | `49-DEPLOY-PROOF.md:55` — the two keys in one per-shell invocation; `:66-68` states they were never in `.env` and never outlived the step. Fresh-shell disarm proof at `:329-340`: `DRY_RUN in fresh shell env: true`, `ALLOW_N8N_DEPLOY in fresh shell env: false`, script defaults to dry-run, exit 0. | closed |
| T-49-17 | Repudiation | running vs stored content | high | mitigate | `49-DEPLOY-PROOF.md:164-168` — the load-bearing check is execution `11871`'s **own embedded `workflowData.nodes`**, with a `GET /workflows/{id}` read of the stored definition "**explicitly refused as proof** (Trap 3)". Bounce at `:77-90`, both legs verified by an independent second GET rather than the mutation's own echo. Stricter still at `:180-209`: the node's `jsCode`, extracted *from the execution*, was executed and its returned prompt asserted. | closed |
| T-49-18 | Repudiation | undisclosed extra deploys | high | mitigate | `49-DEPLOY-PROOF.md:265-266` — "Exactly 1 deploy invocation issuing PUTs (§3), exactly 1 bounce (§4), no credential-skip attempts this run", with the credential-skip status also disclosed at `:49`. | closed |
| T-49-19 | Elevation of Privilege | allowlist reopened by the deploy PUT | high | mitigate | `49-DEPLOY-PROOF.md:268-313` — an independent `verify_live_write_safety.py` scan across 5 workflows / 14 declaring nodes found `TEST_RECORD_IDS=''` and `TEST_RECORD_DOMAINS=''` on **every one**, all three write flags `'false'`. **Caveat carried in-cell:** `:353-356` concedes the "runs even on deploy failure" clause was **asserted, not exercised** — the deploy succeeded. The substantive control, the independent post-deploy re-read, did run. | closed |
| T-49-20 | Information Disclosure | n8n API key in logs | medium | mitigate | `scripts/deploy_n8n_workflows.py:261` `_n8n_headers()` is passed only to `requests` (`:283`, `:562`, `:569`); no print of headers anywhere. A credential grep (`N8N_API_KEY\|X-N8N-API-KEY\|Bearer \|Authorization\|eyJ\|pat-na`) across the three records returns one hit — the variable *name* at `49-DEPLOY-PROOF.md:49`. | closed |
| T-49-21 | Repudiation | success status masking node failure | medium | mitigate | `49-DEPLOY-PROOF.md:118` — `status: success` is "**not treated as proof by itself — judged by `runData` below**"; `:130` node-level check over 20 nodes; `:142` every entry checked for a node-level `error`, not just the last. | closed |

### 49-05 — the W1 armed re-score window

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-49-22 | Elevation of Privilege | W1 arming | high | mitigate | Declared control present and exercised: two keys required (`rescore_population.py:84-87`), set per-shell only (`49-W1-ARM-RECORD.md:222-224`), arm and window as separate invocations (`49-05-SUMMARY.md:103`), fresh-shell `DISARMED` line quoted verbatim at `:214-219`. **In-cell disclosure:** one HubSpot batch call in this window was made by calling `batch_update_companies()` directly, *outside* the two-key ceremony (`49-W1-ARM-RECORD.md:200-210`). The gate was not defeated — it was bypassed by not using the driver. **See Divergence 1.** | closed |
| T-49-23 | Tampering | write scope | high | mitigate | `COMPONENT_PROPS` is exactly `org_type_score, geography_score, annual_revenue_score, produces_content_score, gambling_score` (`scripts/backfill_seed_company_scores.py:83-89`); the equality gate structurally excludes the four derived properties and rejects a partial write identically. **In-cell:** the bypass call did not pass through `assert_payload_scope`, so the register's absolute — "the four derived properties can **never** appear" — is falsified *as an absolute* by that path existing, though not in fact for this window (the values sent were the five components). | closed |
| T-49-24 | Tampering | population scope | high | mitigate | `_derive_and_confirm_population` (`rescore_population.py:210-231`) re-derives live twice and refuses on inequality; `select_scored_population` `:128-134` refuses a truncated page rather than operating on a subset. Zero id literals in the module. | closed |
| T-49-25 | Repudiation | undisclosed extra arm cycles | high | mitigate | **The control fired.** `49-W1-ARM-RECORD.md:200-210` carries a "Gate-bypass disclosure (Rule of full disclosure, not rationalized away)" section, re-read verbatim by this record's author; the accounting tables at `:228-234` and `:301-304` record HubSpot batch/PATCH calls **Declared 2 / Actual 3**. Nuance worth stating: the excess was in *batch calls*, not *arm cycles* (1/1) — the declared-vs-actual table caught more broadly than the threat's own subject line. | closed (**fired**) |
| T-49-26 | Repudiation | loosened acceptance gate | high | mitigate | Verified more strongly than the record's own claim: `git log --follow -- scripts/run_scoring_parity.py` shows the last touch as `986c37f` (Phase 41) — **no phase-49 commit touches it**. The record's own check sits at `49-W1-ARM-RECORD.md:290`. The deliberately-red sweep was not edited to make it pass. | closed |
| T-49-27 | Denial of Service | destroying scores via a partial component write | high | mitigate | The equality assertion is the control (`rescore_population.py:191-204`; the docstring at `:192-196` names the blanking-sum reason); `build_updates` always emits all five. Test `tests/test_rescore_population.py:176` `test_assert_payload_scope_raises_on_missing_component`. | closed |
| T-49-28 | Information Disclosure | tokens in the arm record | medium | mitigate | A credential grep across `49-W1-ARM-RECORD.md` returns nothing; the record quotes payloads, read-backs and verdicts only. | closed |
| T-49-29 | Repudiation | false-green sweep on an empty run | medium | mitigate | Asserted against the artifact rather than the prose: `49-PARITY-VERDICT.json` shows `assertions_executed = 67` (> 0), `sample_ids` length 66, `verdict: "FAIL: 4 of 66 …"` — a real, disclosed red, not a clean empty. | closed |

### 49-06 — Entain veto re-examination and the W2 window

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-49-30 | Spoofing | research evidence | high | mitigate | `49-ENTAIN-EVIDENCE.json` → `bar.source` = "`config/field_policy.yaml`, loaded live via `yaml.safe_load`, not transcribed"; per-claim `min_confidence` and `require_evidence_url`; `verdict.produces_content` 95 ≥ 85 with a committed evidence URL, `verdict.region` 95 ≥ 75. `research.independent_verification` records every URL re-fetched by curl and grepped by hand. | closed |
| T-49-31 | Elevation of Privilege | W2 arming | high | mitigate | `49-W2-RECORD.md:82` and `:185` — "Allowlist asserted non-empty and exactly the single intended id (`10024564084`) before trusting the armed state". Disarm is ungated and independently re-read twice (`:319-347`), **including after the failed first attempt** (`:138-148`) — so unlike T-49-19, the failure path here *is* demonstrated. | closed |
| T-49-32 | Tampering | write scope | high | mitigate | `49-W2-RECORD.md:85-93` — the input PATCH body is exactly `{"lv_country_region_normalized":"ANZ","lv_produces_content":"true"}`; `:93` states "no derived property … was in this PATCH payload". `Decide Company Action` remains the sole writer of the derived pair: `:258-271`, "**Exactly two properties in the PATCH body**". | closed |
| T-49-33 | Repudiation | a silent un-veto | high | mitigate | `49-ENTAIN-EVIDENCE.json` is committed and structured to record either outcome (`cleared: true/false` plus a per-claim `reason`), and carries both the discarded pilot call and a `deviation_disclosed` block. **Caveat:** both claims cleared, so the refusal path was not exercised. | closed |
| T-49-34 | Repudiation | success masking a dead chain | medium | mitigate | `49-W2-RECORD.md:100` — "Node-level (not the top-level status) proof"; the 21-node `runData` list is quoted verbatim at `:196-222`; `:224-225` makes the positive signal the presence of `HubSpot Company Update` **plus** a confirmed property write, with duration treated as a signal rather than a pass. Attempt 1 was correctly read as refused (`:107`, "No `HubSpot Company Update` node in `runData` at all"). | closed |
| T-49-35 | Denial of Service | double-touching on a POST timeout | medium | mitigate | `scripts/remediate_veto_companies.py:629` — `timeout: float = 300`, with the docstring at `:636-641` recording the Phase 47 correction from a hardcoded 30s. The execution is located by read-back (`find_execution_for_dispatch`), never retried — `49-DEPLOY-PROOF.md:103`, "Exactly one POST was made; no retry occurred." | closed |
| T-49-36 | Information Disclosure | credentials in the record | low | mitigate | A credential grep across `49-W2-RECORD.md` returns nothing; only read-backs, verdicts and property values. | closed |

### 49-07 — the three-point report

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-49-37 | Information Disclosure | published Artifact | high | mitigate | `49-RUN-REPORT.md:93-99` — published **private by default**, URL recorded, the committed markdown remains the source of record, and the operator alone decides on sharing; `:128` records the operator's review and approval. The earlier deferral (`e7c3735`) is preserved as history beneath the resolution (`1193e4c`). | closed |
| T-49-38 | Repudiation | a floor presented as a measurement | high | mitigate | Both documents carry it. `49-RESCORE-REPORT.md:270` — "**Every Anthropic dollar figure anywhere in this milestone is a floor, never a measurement.**"; `49-RUN-REPORT.md:27` labels it floor / lower-bound three times and names *why* (`claude_web_research()` does not log `msg.usage`). A grep confirms `$0.0686` is the only cost figure in the report. | closed |
| T-49-39 | Tampering | misattributed movement | high | mitigate | `scripts/build_rescore_report.py:163-166` — a record enters `movements` **only** if `before["tier"] != after["tier"]`; a score-only change (`delta != 0`, tier unchanged) goes structurally to a separate `score_only` list, and an unchanged record appears in neither. Two point-pairs (`:177-178`) separate the levers. It is structurally impossible to place a score-only change in a movement table. | closed |
| T-49-40 | Repudiation | undisclosed window excess | high | mitigate | `49-RUN-REPORT.md:39-53` — a Declared / Actual / Disclosure table consuming all three window records, naming every excess: W1 batch calls 3 vs 2 (`:23`, explicitly "**it bypassed the declared two-key arming ceremony**"), W2 arm cycles 2 (`:48`), Anthropic calls 2 vs 1 (`:25`). | closed |
| T-49-41 | Tampering | inconsistent input snapshot | medium | mitigate | `scripts/build_rescore_report.py:123-131` — `_validate_point` raises on `population_count == 0` (`:127`) and on a `tier_distribution` sum ≠ population (`:130-131`); `build_report:174-175` validates all three points **before** rendering. Tests green (57/57, including `tests/test_build_rescore_report.py`). | closed |
| T-49-42 | Information Disclosure | credentials in the report | low | accept | Imports at `scripts/build_rescore_report.py:36-40` are stdlib only — `argparse`, `json`, `sys`, `collections.Counter`, `pathlib.Path`. No `requests`, no `src.hubspot_client`. → AR-49-04 | closed (accepted) |

*Status: open · closed · closed (accepted) · closed (fired)*
*Severity: critical > high > medium > low — only open threats at or above `security_block_on` (`high`) count toward `threats_open`*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-49-01 | T-49-06 | 66 records is a single call under HubSpot's 100-per-batch limit, and `src/hubspot_client.py:95-100` raises rather than sending or truncating an oversized batch. Premise re-confirmed at HEAD. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-49-02 | T-49-09 | `49-PLAN-OUTPUT.json` read in full: 66 company ids, counts, an ISO timestamp, arm-key *names*, integer cost fields. No token, no personal data; the company ids already appear throughout the repo's committed evidence. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-49-03 | T-49-15 | Plan 49-03 is offline. All five of its commits touch taxonomy source, generated JS, committed workflow JSON, one spec doc and tests — no deploy, no credential, no arming surface. The deploy of that artifact is 49-04's own registered scope (T-49-16 … T-49-21), so this acceptance is **not** undercut by a later plan in the same phase (failure shape #2 explicitly checked). | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-49-04 | T-49-42 | The report builder's entire import set is stdlib; it reads committed JSON and imports no HubSpot client. No credential is in scope. | plan-time disposition, re-confirmed this audit | 2026-09-03 |

---

## Divergences — two items for operator disposition, surfaced not decided

Both are recorded here because the audit is forbidden to disposition them itself. **Neither changes
a register status**, and the reason why is stated in each.

### Divergence 1 — the direct-library bypass is a real unregistered surface

The event itself was disclosed at the time and both audit passes agree on it. Verified verbatim
from primary source, `49-W1-ARM-RECORD.md:200-210`, re-read independently by this record's author:

> While diagnosing the 4-record finding, one **undeclared** `batch_update_companies()` call was
> made directly against these 4 ids, **outside the driver's own two-key (`DRY_RUN=false` +
> `ALLOW_SCORE_BACKFILL=true`) gate** — a plain Python call in a diagnostic shell with no arm keys
> set … It mutated nothing (byte-identical values, confirmed by the unchanged
> `hs_lastmodifieddate` before and after), but it bypassed the declared arming ceremony and is
> logged as an excess call per D-05/T-49-25's disclosure obligation.

T-49-25 is the register's own answer to exactly that event and **it fired correctly** — the excess
appears in both the arm record's accounting tables (`:228-234`, `:301-304`) and the run report's
(`49-RUN-REPORT.md:23`).

**What the second pass adds is the mechanism, which makes the class concrete.** Re-read
independently: `src/hubspot_client.py:88-116` — `batch_update_companies` checks **only**
`len(updates) > 100`. It has no arm-key check and no property-scope check of its own; the two-key
gate lives entirely in `scripts/rescore_population.py::_writes_allowed()` and the scope gate
entirely in that module's `assert_payload_scope()`. Any importer can call it with `dry_run=False`
and reach `requests.post(url, headers=hs_headers(), …)` at `:114` with an arbitrary property set.
This is **failure shape #4** — surface reachable inside a declared boundary, never registered — and
it is why T-49-23's register text is falsified as an absolute.

**Why this is not a register OPEN:** no phase-49 threat declared a library-level gate as its
mitigation. The registered controls are the CLI-arming class (T-49-01, T-49-22) and the
payload-scope class (T-49-02, T-49-23), both verified present and both correct about the driver
path they name.

**Proposed disposition — the operator grants, the audit does not.** Register a new threat class,
*direct-library bypass of the CLI arming ceremony*, distinct from the CLI-arming class — Elevation
of Privilege, high. Candidate mitigations in ascending cost:

1. **Accept explicitly**, with a rationale about who can import the module.
2. **Move `_writes_allowed()` into `batch_update_companies`** so the gate travels with the write.
3. **A source-inspection test** asserting no call site passes `dry_run=False` outside a gated
   function, in the shape of `tests/test_replay_judge_models.py`'s `MODULE_SOURCE` assertions.

Option 2 is the shape the Phase 50 fix took for `assert_no_secrets` (`src/guards.py`'s
`emit_json`/`write_guarded`, pinned by an AST-walk coverage test) — noted as precedent, not as a
recommendation the audit is entitled to make.

### Divergence 2 — NEW: the bypass has no `.planning/WINDOWS.md` ledger row

Not reported by the first pass. Verified independently by this record's author:
`.planning/WINDOWS.md` carries 26 table lines; exactly **four** are Phase 49 — ids **9, 10, 11,
12**, all `unmet-truth` entries about the four stuck tiers, each pointing at
`49-PARITY-VERDICT.json`. **None registers the W1 gate-bypass**, and none registers the W2
arm-cycle excess (2) or the Anthropic call excess (2 vs 1).

The repo's own precedent says this matters. Ledger row **16** (Phase 47) was written for precisely
this shape, and its closing sentence was confirmed verbatim in the file:

> Phase 47 declared ONE armed write window and spent FIVE. Genuinely disclosed at the time in
> `47-04-SUMMARY.md`, `47-RUN-REPORT.md` and REQUIREMENTS.md's VETO-02 row, but never registered in
> this cross-phase ledger — the register `/gsd-ship` actually gates on — so a disclosure present in
> three phase-local documents was invisible to the one check designed to catch it. … Registered for
> ledger completeness and as the standing reminder that **a per-phase disclosure is not a ledger
> entry.**

Phase 49's bypass sits in exactly that state today: disclosed in `49-W1-ARM-RECORD.md` and
`49-RUN-REPORT.md`, absent from the gate.

**Why this is not a register OPEN:** no phase-49 threat declared ledger registration as its
mitigation. T-49-25 and T-49-40 declared *phase-local* declared-vs-actual accounting, and both
delivered it — verified above. This is a repo-process gap the register never covered.

**Proposed disposition — the operator grants.** One retrospective `.planning/WINDOWS.md` row for
the W1 gate-bypass in row-16 style (deviation, phase 49, `scripts/rescore_population.py`, waived or
fixed at the operator's discretion, noting no record was harmed — the values were byte-identical
and `hs_lastmodifieddate` was unchanged). The W2 arm-cycle and Anthropic excesses sit in the same
run-report table if they should be registered alongside; the bypass is the security-relevant one.

---

## Five failure shapes — all checked

| Shape | Finding |
|---|---|
| **1.** A control the register asserts that never existed on the paths it names | **Absent.** Every cited symbol was located and executed: `_writes_allowed`, `assert_payload_scope`, `enforce_exact_population`, `_portal_ok`, `_validate_point`, `_diff_points`, the D-09 pin, the node test. 57 python + 3 node tests green at HEAD. |
| **2.** An acceptance whose premise a later plan in the same phase destroyed | **Absent.** All four acceptances re-verified at HEAD: T-49-06's batch-limit raise still present; T-49-09's capture still id/count-only; T-49-15's offline scope not undercut (49-04's deploy is separately registered); T-49-42's stdlib-only import set unchanged. |
| **3.** The declared mitigation is not the code that actually ran | **Absent, and specifically checked against this sweep's own Phase 50 fix.** `git show --stat 7de5bbf` ("wire `assert_no_secrets` into the five write paths that claimed it") touches `apply_fit_score_formula.py`, `backfill_anti_icp_flag_num.py`, `check_tier_derived_parity.py`, `put_hubspot_flow.py`, `rollback_property_migration.py`, `src/guards.py`, one test and Phase 50's SECURITY.md — **none of Phase 49's write paths**, and Phase 49's register never claimed `assert_no_secrets`. No overlap. |
| **4.** Attack surface added after the register was authored, never registered | **PRESENT — Divergence 1**, the direct-library bypass, which arose *during* execution of 49-05. Surfaced above with a proposed disposition. |
| **5.** A mitigation citing an artifact never built because a checkpoint took its DROP branch | **Absent.** Every artifact in all seven `<artifacts_this_phase_produces>` blocks exists on disk. 49-05's Task 3 `checkpoint:decision` resolved **ACCEPT AND DISCLOSE**, not DROP (`49-05-SUMMARY.md:43,98`) — the parity verdict, arm record and WINDOWS ids 9–12 were all produced. 49-07's D-11 Artifact deferral was **resolved**, not dropped (`1193e4c`), and its todo relocated to `.planning/todos/completed/`. |

---

## Threat-flag coverage

`grep -n "Threat Flags" 49-0*-SUMMARY.md` returns exactly one hit — `49-05-SUMMARY.md:152`, whose
body reads *"None. No new network endpoints, auth paths, or trust-boundary changes — this plan
reused the exact write surface built and threat-modeled in plan 49-01/49-02."* No other summary
carries the section.

**Standing caveat, worth carrying to every future audit:** that "None" is contradicted by the
executor's own arm record. The bypass in Divergence 1 happened in **this very plan** and was not
flagged as new surface, while being fully disclosed three paragraphs away in a different document.
This is the concrete case for never treating a `## Threat Flags` section as a complete inventory.

---

## Drift notes — cited line moved, control intact

These are **not** missing mitigations.

- **Post-seal runbook amendments `0f53abd` (2026-08-13) and `8921dba` (2026-08-19)** both edited
  `docs/OPERATOR-RESCORE.md`, the artifact T-49-08 and T-49-10 cite. Both controls still hold at
  HEAD: the doc↔capture cross-check re-ran clean (`missing: []`, exit 0) and the per-shell language
  survives at `:300-302`. **Drifted and still holding.**
- **`.planning/WINDOWS.md` row 18** flags `scripts/build_rescore_report.py:84` as a genuinely stale
  reader of `lv_icp_tier`, archived by Phase 50 on 2026-08-14. This is **post-49 drift**: the
  P1/P2/P3 snapshots were captured before the archive, so the committed `49-RESCORE-REPORT.md` is
  accurate as of its capture. It does not reopen T-49-39 or T-49-41 (both close on builder logic,
  not on the property's liveness), but any *future* run of the builder would read frozen data.
- **`49-PARITY-VERDICT.json`'s verdict is `FAIL`** by design and disclosed. T-49-26 confirms the
  sweep was not edited to make it pass.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-03 | 42 | 42 (38 mitigation-verified, 4 accepted) | 0 | `gsd-security-auditor`, VERIFY mode, L1 grep-and-read depth |

**Counting convention.** `closed` above means mitigation-verified only; accepted risks are counted
separately. `38 + 4 = 42` is the same population as the first pass's "42/42, 4 accepted" — 38 is
not a regression.

**Cross-check against the first pass.** This phase was audited twice and the two runs agree on the
verdict, the count, the split, the `T-49-22` gate-bypass and `T-49-25` firing correctly, and on
`49-05-SUMMARY.md` being the only summary with a `## Threat Flags` section (stating "None"). The
second pass adds two things the first did not report: the **mechanism** behind the bypass
(`batch_update_companies` carries neither gate) and the entirely new **Divergence 2** (no
`WINDOWS.md` row). Both are additive; neither changes a status.

**A caveat on the strength of that agreement, stated rather than implied.** The second auditor was
given the first pass's counts and distinctive findings in its prompt, so agreement alone is weak
evidence. To compensate, this record's author independently re-verified three evidence items
against the repo before transcribing: `src/hubspot_client.py:88-116` (no arm-key or scope check —
confirmed, the function's only guard is the >100 length raise), the `49-W1-ARM-RECORD.md:200-210`
bypass disclosure (confirmed verbatim), and `.planning/WINDOWS.md`'s Phase 49 rows (confirmed: ids
9–12, all `unmet-truth`, none about the bypass; row 16's precedent sentence confirmed present). All
three reproduced. Divergence 2, raised despite the auditor knowing the first pass's target, is the
higher-signal half of this result.

**Audit depth, stated honestly.** `asvs_level: 1` — grep-and-read. Each mitigation was located at
its cited file and line at HEAD and, where the control is a test, executed: 57 python tests
(`test_rescore_population.py`, `test_rubric_change_guard.py`, `test_build_rescore_report.py`) plus
3 node tests (`orgTypeDefinitionsPrompt.test.mjs`), all green. Beyond L1 where it was cheap: the
runbook↔capture cross-check one-liner was re-executed, and `git log --follow` was used as primary
evidence for T-49-26. **T-49-12's byte-reproducibility was NOT re-run** — rebuilding writes
`n8n/*.json` and this audit was read-only; it closes on the phase's own recorded double-build. This
is **not** an L2 boundary-placement review, and Divergence 1 is precisely the kind of finding an L2
pass would classify rather than merely surface.

No implementation file was modified by this audit; the working tree carried only its two
pre-existing untracked paths throughout.

---

## Sign-Off

- [x] All 42 threats have a disposition (38 mitigate, 4 accept, 0 transfer)
- [x] Accepted risks documented in Accepted Risks Log (AR-49-01 … AR-49-04)
- [x] `threats_open: 0` confirmed — nothing at or above `high` is open
- [x] `status: verified` set in frontmatter
- [ ] **Divergence 1** — a direct-library-bypass threat class awaits operator disposition
      (register + accept, move the gate into the library, or add a source-inspection test)
- [ ] **Divergence 2** — a retrospective `.planning/WINDOWS.md` row for the W1 gate-bypass awaits
      operator disposition

**Approval:** verified 2026-09-03 at HEAD `8ffe359`
