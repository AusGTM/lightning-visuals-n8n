---
phase: "70"
slug: "one-merge-one-result-channel-n8n-runtime-truth"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-10"
---

# Phase 70 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register authored at plan time (18 plans, 70-01..70-18, one `<threat_model>` each). Verified 2026-09-10 by gsd-security-auditor at ASVS L1 (grep-depth), block_on: high.

---

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| caller → `hubspot/*` webhooks (enrichment, ingest) | Untrusted-shaped request bodies; request-level flags (`recompute`, `scale_up`, `run_id`) are normalized/refused here |
| n8n graph → HubSpot write nodes | The allowlist write-gate (`_writeSafetyAllows`) is the sole access-control layer for HubSpot writes; fail-closed on empty allowlist |
| n8n executions API → client | Row-level result channel; requires `n8n_api_key`, never embedded in ack/ledger/verdict |
| builder → generated JSON (`n8n/wf_*.json`) | Four generation-time refusals (`assert_no_by_name_reads`, `assert_merge_input_contract`, `assert_no_self_dispatch`, `assert_execution_order_v1`) are the only unbypassable structural gates |
| committed JSON → live n8n Cloud | Deploy PUT/POST payload filter + arming rewrite; both pinned to preserve `settings` |
| test harness (`walkWorkflow.mjs`) → committed jsCode | Executes repo-controlled `new Function`; a walker blind spot produces false assurance, not a live vulnerability |
| documentation/gate text → operator action | Deferred, blocking-human gates (10/11/12) are the transfer boundary for live-deploy risk |
| provider/HubSpot API → n8n graph | Untrusted response bodies now travel Merges carrying row identity; mis-pairing risk |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-70-07 | Tampering | walkWorkflow.mjs false assurance | high | mitigate | `trace.unhandledTypes` + HTTP-throw-by-name (walkWorkflow.mjs) | closed |
| T-70-08 | Elevation of Privilege | detect_by_name_reads blind spot (70-01) | high | mitigate | 3-shape unit tests; `main()`-level count | closed |
| T-70-09 | Denial of Service | `new Function` test-process eval | low | accept | Accepted Risks Log R-70-01 | closed |
| T-70-02 | Repudiation | ack mistaken for outcome (70-02) | high | mitigate | `dispatch()` ack={accepted}; rows from `watch.recover_dispatch` | closed |
| T-70-04 | Denial of Service | Merge input never fires (70-02) | high | mitigate | `set_always_output_data` + `trace.stalled=[]` (all suites green) | closed |
| T-70-05 | Repudiation | rows lost at convergence (70-02) | high | mitigate | `Build Ingest Response` reads `$input.all()` behind Merge | closed |
| T-70-03 | Information Disclosure | n8n_api_key leak (70-02) | medium | mitigate | key confined to `executions_client` header construction | closed |
| T-70-10 | Spoofing | run_id collision | low | accept | Accepted Risks Log R-70-02 | closed |
| T-70-04 | Denial of Service | Merge at 20 convergence points (70-03) | high | mitigate | same mechanism; `enrichmentBatchRefusal.test.mjs` PASS | closed |
| T-70-02 | Repudiation | refusal reason lost (70-03) | high | mitigate | `Build Refusal Row` → Merge before `Build Response`; test PASS | closed |
| T-70-11 | Tampering | scale-up depth guard weakened (70-03) | high | mitigate | superseded: fan-out node deleted at 70-13; `assert_no_self_dispatch` | closed |
| T-70-12 | Elevation of Privilege | review lane acquiring enrichment behaviour | medium | mitigate | `reviewDecisionEndpoint.test.mjs`/`reviewAllowlistRefusal.test.mjs` PASS | closed |
| T-70-13 | Tampering | combine-by-position mis-pairing | high | mitigate | `merge_node(combine_by=...)`; `providerCarryMerge.test.mjs` PASS | closed |
| T-70-08 | Elevation of Privilege | by-name read survives (70-04) | high | mitigate | `assert_no_by_name_reads` composed at all 8 write sites | closed |
| T-70-05 | Repudiation | rows lost/duplicated across hop (70-04) | high | mitigate | item-count assertion; scoring parity/judge suites green | closed |
| T-70-11 | Tampering | scale-up guard on carried row (70-04) | high | mitigate | superseded: node deleted at 70-13 | closed |
| T-70-01 | Elevation of Privilege | malformed/absent write_request | high | mitigate | `_writeSafetyAllows` fail-closed; `assert_write_request_emitters` | closed |
| T-70-14 | Denial of Service | emitter omits needed key | medium | mitigate | shared `_buildWriteRequest` helper; generation-time assert | closed |
| T-70-06 | Repudiation | refused write reported as success | high | mitigate | `splice_write_gates`: refusal rows → same Merge as success | closed |
| T-70-15 | Elevation of Privilege | review lane acquires domain allowlist | high | mitigate | review emitter sets null domain; test PASS | closed |
| T-70-02 | Repudiation | ack mistaken for outcome (70-06) | high | mitigate | sync-body branches deleted; ledger write-capable-legs only | closed |
| T-70-03 | Information Disclosure | n8n_api_key leak (70-06) | medium | mitigate | never-print-secret discipline re-asserted | closed |
| T-70-16 | Spoofing | time-proximity row misattribution | high | mitigate | D-70-10 exact-match run_id only, no time-proximity code | closed |
| T-70-17 | Repudiation | preview vs. dispatch verdict differ | high | mitigate | D-70-11 single verdict source, equality-pinned | closed |
| T-70-18 | Denial of Service | unbounded wait by migrated caller | medium | mitigate | `test_report_sufficiency.py` single-poll-site invariant PASS | closed |
| T-70-19 | Tampering | accidental live write during proof | high | mitigate | `require_disarmed()` SystemExit(2), named "(T-70-19)" in code | closed |
| T-70-03 | Information Disclosure | verdict/log leaking key (70-07) | medium | mitigate | verdict fields = execution ids/row shapes only (checked) | closed |
| T-70-04 | Denial of Service | Merge hangs on live build (70-07) | high | mitigate | 4 small sends; stuck-execution = primary pass criterion | closed |
| T-70-20 | Repudiation | walker adjusted post-hoc to match live | high | mitigate | gate text: mismatch=finding; subprocess of frozen CLI | closed |
| T-70-30 | Tampering | working-tree n8n/ left pre-70 | high | mitigate | checkout bracketed by restore; `git status --porcelain` check | closed |
| T-70-31 | Elevation of Privilege | executor invokes armed deploy | critical | mitigate | `DRY_RUN` default true; armed invocation is runbook text only | closed |
| T-70-32 | Spoofing | rollback against wrong SHA | high | mitigate | `test_phase70_rollback_bundle.py` pins SHA+node counts, PASS | closed |
| T-70-33 | Tampering | rollback bundle is armed | critical | mitigate | same test asserts disarmed-at-rest literals, PASS | closed |
| T-70-34 | Repudiation | deploy without bounce | medium | mitigate | runbook Step 5 "bounce (mandatory) and read back" | closed |
| T-70-SC | Tampering | npm/pip/cargo installs (70-08) | high | mitigate | no manifest diff since phase 70 start (verified via git diff) | closed |
| T-70-35 | Tampering | walkWorkflow.mjs adjusted until green | critical | mitigate | walker comments cite execution ids (16 matches found) | closed |
| T-70-36 | Elevation of Privilege | armed fixture escapes to deployable body | high | mitigate | arming on in-memory copy under tests/; n8n/ untouched | closed |
| T-70-37 | Information Disclosure | frozen fixture carries secret | medium | mitigate | fixtures = committed workflows (credential refs, no secrets) | closed |
| T-70-38 | Denial of Service | walker executes looping jsCode | low | accept | Accepted Risks Log R-70-03 | closed |
| T-70-39 | Repudiation | RED inventory goes stale | medium | mitigate | 70-WALKER-RED-INVENTORY.md records counts verbatim, fresh run | closed |
| T-70-SC | Tampering | npm/pip/cargo installs (70-09) | high | mitigate | no manifest diff (same check) | closed |
| T-70-40 | Elevation of Privilege | declaring node lost/added (ingest restructure) | critical | mitigate | `set_write_safety` 3-rewrite count; `assert_write_request_emitters` | closed |
| T-70-41 | Tampering | sentinel marker paired by positional Merge | high | mitigate | `assert_merge_input_contract` rule 2: no Sentinel feeds Merge input | closed |
| T-70-42 | Spoofing | marker reported as real outcome | high | mitigate | `SENTINEL_MARKER_KEY` filtered at response builders | closed |
| T-70-43 | Denial of Service | regenerated graph Merge starves | critical | mitigate | `assert_merge_input_contract` rule 4: every input has producer | closed |
| T-70-44 | Tampering | hand-edited JSON to pass suite | high | mitigate | verification regenerates via builder, requires clean tree | closed |
| T-70-45 | Repudiation | pending list outlives work | medium | mitigate | `mergeInputContract.test.mjs` PENDING=[] asserted exact | closed |
| T-70-SC | Tampering | npm/pip/cargo installs (70-10) | high | mitigate | no manifest diff (same check) | closed |
| T-70-46 | Denial of Service | staged response Merge starves | critical | mitigate | `assert_merge_input_contract` composed in generation contracts | closed |
| T-70-47 | Repudiation | response terminal renamed, client returns empty | critical | mitigate | "Build Response" node name resolves once in committed JSON | closed |
| T-70-48 | Elevation of Privilege | write gate declaration moved/duplicated | critical | mitigate | `assert_write_request_emitters` unchanged; no gate added/removed | closed |
| T-70-49 | Tampering | red suite silenced | high | mitigate | full node suite green (1078/1078); no suite deleted | closed |
| T-70-50 | Spoofing | sentinel marker into reported row | high | mitigate | `SENTINEL_MARKER_KEY` filter; mixed-batch suites PASS | closed |
| T-70-51 | Tampering | future generator re-creates shared-input defect | high | mitigate | `assert_merge_input_contract` now generation-time refusal | closed |
| T-70-SC | Tampering | npm/pip/cargo installs (70-11) | high | mitigate | no manifest diff (same check) | closed |
| T-70-52 | Repudiation | verdict shape-equal via loosened comparator | high | mitigate | 70-12 fix reads raw rows; test built from execution 12207 shape | closed |
| T-70-53 | Information Disclosure | verdict/gate leaks credential | high | mitigate | 70-RUNTIME-VERDICT.json fields: exec ids/shapes only (checked) | closed |
| T-70-54 | Elevation of Privilege | Gate 6 armed window widened | critical | mitigate | Gate 6/9/12 text: allowlist fixed to 1 contact, disarm-readback | closed |
| T-70-55 | Tampering | armed run against unproven-disarmed graph | critical | mitigate | ordering rule: disarmed proof gate precedes armed gate | closed |
| T-70-56 | Spoofing | platform claim tagged observed-live on docs alone | medium | mitigate | 70-DEFERRED-GATES.md rows cite execution ids | closed |
| T-70-57 | Denial of Service | second poll loop breaks single-poll invariant | medium | mitigate | single recovery read; `test_report_sufficiency.py` invariant PASS | closed |
| T-70-SC | Tampering | npm/pip/cargo installs (70-12) | high | mitigate | no manifest diff (same check) | closed |
| T-70-58 | Denial of Service | self-referencing Execute Workflow node | critical | mitigate | `assert_no_self_dispatch` rule 1: unconditional self-ref refusal | closed |
| T-70-59 | Elevation of Privilege | caller-supplied scale_up amplification | high | mitigate | refused whole at envelope+event level (build_cloud_workflows.py) | closed |
| T-70-60 | Tampering | removal deletes SJ-3's dispatch too | high | mitigate | 1 named exemption `_SELF_DISPATCH_EXEMPTIONS`, keyed by wf name | closed |
| T-70-61 | Repudiation | re-sourced sentinel stalls Merge silently | high | mitigate | full node suite green incl. companies/contacts/unsupported batches | closed |
| T-70-62 | Spoofing | test still asserts deleted mechanism | medium | mitigate | `scaleUpFanOutFlow.test.mjs` → `scaleUpRefused.test.mjs` | closed |
| T-70-63 | Information Disclosure | refusal reason echoes payload/creds | medium | mitigate | fixed sentence, no interpolation (build_cloud_workflows.py:5314) | closed |
| T-70-SC | Tampering | npm/pip/cargo installs (70-13) | high | mitigate | no manifest diff (same check) | closed |
| T-70-64 | Spoofing | marker item reported as real row | high | mitigate | positive identity filter; `buildResponseMarkerFilter.test.mjs` PASS | closed |
| T-70-65 | Repudiation | over-tight filter drops real terminal | high | mitigate | identity set incl. outcome+object id; full suite green | closed |
| T-70-66 | Tampering | walker taught unisolated G-70-5 mechanism | high | mitigate | `walkerEngineFidelity.test.mjs`: "does NOT reproduce" assertion | closed |
| T-70-67 | Information Disclosure | frozen execution record carries secret | high | mitigate | 0 credentials blocks in all 4 frozen fixtures (grep-verified) | closed |
| T-70-68 | Repudiation | frozen fixture regenerated, stops reproducing | medium | mitigate | fixtures/frozen/README.md never-regenerate rule, extended | closed |
| T-70-SC | Tampering | npm/pip/cargo installs (70-14) | high | mitigate | no manifest diff (same check) | closed |
| T-70-69 | Spoofing | platform fact tagged observed-live on reasoning | high | mitigate | 70-DEFERRED-GATES.md new rows cite execution ids | closed |
| T-70-70 | Repudiation | unconnected-node cause invented | high | mitigate | CLAUDE.md/gap row: "cause NOT isolated", no invented cause | closed |
| T-70-71 | Elevation of Privilege | armed gate reachable pre-disarmed-reproof | critical | mitigate | Gate ordering: "7 before 8, 8 before 9 — no exceptions" | closed |
| T-70-72 | Denial of Service | another unattended execution-budget burst | critical | mitigate | two-minute burst watch + STOP procedure at Gate 10 | closed |
| T-70-73 | Information Disclosure | gate/runbook names credential value | high | mitigate | gate text names env var NAMES only, never values (checked) | closed |
| T-70-74 | Tampering | Gate 9 duplicates superseded text, drifts | medium | mitigate | Gate 9 text: "Do not restate Gate 6's procedure" — references | closed |
| T-70-SC | Tampering | npm/pip/cargo installs (70-15) | high | mitigate | no manifest diff (same check) | closed |
| T-70-16-01 | Tampering | n8n/wf_*.json hand edit | high | mitigate | `assert_execution_order_v1` + `executionOrderV1.test.mjs` PASS | closed |
| T-70-16-02 | Repudiation | walker silently models unobserved rule | high | mitigate | D-70-30 modelled/not-modelled/unobserved tags; allowLegacy 1-suite | closed |
| T-70-16-03 | Denial of Service | regenerated body behaves differently live | critical | transfer | Gates 10/11/12 (70-18): disarmed deploy+burst watch+STOP text | closed |
| T-70-16-04 | Elevation of Privilege | armed write reaches HubSpot from this change | critical | mitigate | commit b15be01: settings-only diff, 8 files +3/-1, no flag touched | closed |
| T-70-16-SC | Tampering | npm/pip/cargo installs | high | mitigate | no manifest diff (same check) | closed |
| T-70-17-01 | Tampering | deploy PUT drops settings silently | critical | mitigate | payload filter includes `settings` key (deploy_n8n_workflows.py) | closed |
| T-70-17-02 | Tampering | arming rewrite reverts workflow to legacy | critical | mitigate | `put_body()`: settings in PUT_BODY_KEYS + change-refusal | closed |
| T-70-17-03 | Repudiation | operator believes live is v1 wrongly | high | mitigate | `bounce_n8n_workflows.py` exits 1 on non-v1 reading | closed |
| T-70-17-04 | Information Disclosure | verdict/table leaks credential | medium | mitigate | new fields = execution-order string + boolean only | closed |
| T-70-17-SC | Tampering | npm/pip/cargo installs | high | mitigate | no manifest diff (same check) | closed |
| T-70-18-01 | Repudiation | documented v1 claim read as observed fact | high | mitigate | CLAUDE.md D-70-28/29/30 rows tagged `[documented]`, cited | closed |
| T-70-18-02 | Denial of Service | Gate 10 deploy re-triggers self-dispatch burst | critical | mitigate | Gate 10: burst watch before send, names 123→287 node jump | closed |
| T-70-18-03 | Elevation of Privilege | Gate 12 armed run on unproved graph | critical | transfer | Gate 12←Gate 11←Gate 10 precondition chain, stop-and-report | closed |
| T-70-18-04 | Tampering | gap silently marked closed on offline green | high | mitigate | 70-UAT.md G-70-6 `status: failed` preserved, missing list intact | closed |
| T-70-18-SC | Tampering | npm/pip/cargo installs | high | mitigate | no manifest diff (same check) | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*
*Duplicate ids (T-70-02/03/04/05/08/11, T-70-SC) recur across plans by design — each plan re-registered the shared threat against its own component; the plan is named in the Component cell.*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-70-01 | T-70-09 | `new Function` evaluates repo-controlled jsCode inside the offline test process only; no untrusted input reaches it. Severity low. | plan 70-01 disposition (accept), confirmed by audit | 2026-09-10 |
| R-70-02 | T-70-10 | `run_id` is client-minted UUID4; collision probability negligible and a collision surfaces as a shape mismatch, not a silent write. Severity low. | plan 70-02 disposition (accept), confirmed by audit | 2026-09-10 |
| R-70-03 | T-70-38 | A looping committed jsCode would hang the offline walker only; `node --test` timeout bounds it and no live execution is affected. Severity low. | plan 70-09 disposition (accept), confirmed by audit | 2026-09-10 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-10 | 97 | 97 | 0 | gsd-security-auditor (sonnet), ASVS L1, verdict SECURED; 3 low-severity `accept` rows closed by logging R-70-01..03 |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-10 (offline audit; live gates 10/11/12 remain the operator's transfer boundary per T-70-16-03 / T-70-18-03)
