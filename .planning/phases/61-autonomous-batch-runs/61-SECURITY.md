---
phase: "61"
slug: "autonomous-batch-runs"
status: verified
threats_open: 0
asvs_level: 1
created: "2026-09-03"
---

# Phase 61 — Security

> Retroactive secure-phase run, 2026-09-03. All six plans carry plan-time `<threat_model>` blocks —
> a verification pass, not retroactive-STRIDE. 31 threats. No `## Threat Flags` section exists in
> any of the six summaries: **unregistered flags: none.**
>
> **ID disambiguation.** Five plans each declared a threat literally named `T-61-SC`. They are
> written below as `T-61-SC-02` … `T-61-SC-06` by originating plan, mirroring phase 63's
> `A-SC…E-SC` pattern. A rename for legibility, not a new finding.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| planner → executor (61-01) | A verdict document is read as **fact** by a later plan | premise claims with basis tokens; an unmarked guess would become a silent premise |
| operator machine → n8n Cloud (61-02) | `MATCH_LOOKUP_KEYS` decides which row fields leave the operator's machine | `email`, `firstname`, `lastname`, `company`, `linkedin_url` |
| n8n → HubSpot search (61-02) | A search filter value crosses into a live CRM query | LinkedIn URL variants in a `filterGroups` body |
| HubSpot response → match verdict (61-02) | An unverified server-side hit could be reported as a confident person match | candidate contact records |
| operator input → extraction gate (61-03) | An accepted row is one the system will act on and eventually write | uploaded spreadsheet row fields |
| plugin preview → deployed n8n gate (61-03) | Two independent implementations of one identity rule; drift would be silent by construction | the `required_identity.any_of` vocabulary (YAML → JS/Python) |
| confidence verdict → autonomous write (61-04) | A wrongly-confident verdict **removes the human** from a write to a CRM with no rollback | match tier, provider agreement, conflict/adjudication signals |
| held queue → disk (61-04) | A durable artifact could become a place a grant is parked | row identity fields, hold codes, reasons |
| recorded run state → completion report (61-05) | A misread state could report a half-completed batch as done | run-scoped verdict/progress counts |
| run state store → disk or n8n (61-05) | A new persistent store could become a place a grant is parked | `run_id`, row-id scope, dispatched count |
| polling → n8n execution budget (61-05) | An unbounded poll or fan-out could exhaust a hard 2,500/month allowance | requests against the executions API |
| one batch grant → many HubSpot writes (61-06) | A single consent authorises many writes to a CRM with no rollback | record ids/domains named at grant-open time |
| company resolution → contact create (61-06) | An unresolved company could produce an orphaned or duplicate record | company domain/name lookups |
| index-lag handling (61-06) | An unbounded wait or retry could stall or over-spend a run | retry counters against HubSpot search |

---

## Threat Register

### 61-01 — Spike verdict, execution arithmetic, run-state decision

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-61-01 | Spoofing | `61-SPIKE-VERDICT.md` | high | mitigate | `test_spike_verdict_61.py` 13/13, including `test_substrates_claim_lines_carry_exactly_one_basis_token` and the premises equivalent — **a claim with no basis token fails the suite.** This is the mechanism behind CLAUDE.md §13.0.3's `[documented]` vs `[observed live]` discipline. | closed |
| T-61-02 | Tampering | `61-SPIKE-VERDICT.md` | medium | mitigate | 61-05's Task 1 reads `## Premises` and halts on contradiction; `pytest test_run_state.py -k premises` 4/4. Task 1 ran, found no unresolved premise, committed `0db7bdd`. | closed |
| T-61-03 | Information Disclosure | the verdict doc | low | accept | Grep for credential patterns over `61-SPIKE-VERDICT.md` returns only false-positive matches on the word "token" inside "basis token". See AR-61-01. | closed (accepted) |

### 61-02 — LinkedIn match lane

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-61-04 | Information Disclosure | `MATCH_LOOKUP_KEYS` (`enrichment.py:79`) | medium | mitigate | Widened by **exactly one** key. `test_match_lookup_keys_stays_the_reviewed_five` is **AST-parsed rather than imported**, pins the exact tuple, and asserts `phone`/`jobtitle` are absent — so the set cannot grow without a deliberate test edit. | closed |
| T-61-05 | Spoofing | `Adapt Linkedin Search` | high | mitigate | `matchProposal.js`'s `verifiedLinkedinHits`/`linkedinAgreement` canonicalize **both** `lv_linkedin_url` and `hs_linkedin_url` and require agreement; `existingRecord` is built only on exactly **1** verified hit — 0 or >1 never auto-match. `linkedinLaneFlow.test.mjs` 16/16, including the explicit case that a different profile under the same host does **not** match. | closed |
| T-61-06 | Tampering | the `HubSpot Linkedin Search` filter | high | mitigate | The node filters on both `lv_linkedin_url` and `hs_linkedin_url`, verified against a **live portal snapshot** (`portal-schema-contacts-54-03-contacts-check.json`, GET 2026-08-27): both present, bare `linkedin_url` absent. The property name is confirmed against the portal, not guessed — the exact trap CLAUDE.md §4.0 warns about, where HubSpot silently ignores unknown property names. | closed |
| T-61-07 | Repudiation | mixed-lane routing | medium | mitigate | `linkedinLaneFlow.test.mjs` — a mixed batch of an email row, a linkedin-only row and a name-only row each produce exactly one item, and the linkedin row is never `unknown`. Passed live. | closed |
| T-61-SC-02 | Tampering | npm/pip/cargo installs | high | mitigate | `git log` on the dependency manifests shows no commit in the phase window (2026-08-28→31). | closed |

### 61-03 — Third identity group (`linkedin_url`), one YAML source

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-61-08 | Tampering | five identity-rule sites (D-61-06) | high | mitigate | `columnMapIdentityParity.test.mjs` drives `columnMap.js::requiredIdentity()` from `config/column_mapping.yaml` via a **PyYAML oracle subprocess** — no hardcoded JS copy of the groups to drift. `extraction.py:174` reads `required.get("any_of")` directly rather than restating the groups. 4/4. | closed |
| T-61-09 | Elevation of Privilege | `required_identity.any_of` | high | mitigate | `config/column_mapping.yaml:60-64` is `[[email], [firstname,lastname,company], [linkedin_url]]` — **additive** third group, byte-identical between the two config copies. `test_a_bare_name_with_no_email_and_no_linkedin_is_still_rejected` passes: a name-only row is still rejected, so the widening did not weaken the gate. | closed |
| T-61-10 | Spoofing | the `resolutions` proposal loop | medium | mitigate | `enrichment.py` and `extraction.py` both import the same shared `RESOLUTION_SOURCES` frozenset and validate every `res_source` against it (`extraction.py:652`) — one object, not two sets that could drift. | closed |
| T-61-SC-03 | Tampering | npm/pip/cargo installs | high | mitigate | Same git-log evidence. | closed |

### 61-04 — Confidence table, held queue, sixth verdict word

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-61-11 | Elevation of Privilege | `confidence.py`'s decision table | **critical** | mitigate | Read in full: exactly two verdicts (`CONFIDENT`/`HELD`); `tier == "unknown"` holds; an unresolved material-conflict group holds **regardless of tier**, checked before any tier row; and a terminal `else -> HELD` — *"a signal vocabulary that has drifted … is held, never defaulted confident."* The fail-safe direction is toward the human. | closed |
| T-61-23 | Tampering | the per-row outcome contract | high | mitigate | `preingest.py::parse_outcome` returns `UNPARSEABLE_OUTCOME` on a missing/unrecognised `outcome_contract_version`, a missing or tierless `match`, or a missing `candidate_count`. `outcomeContractFlow.test.mjs` drives the real jsCode end to end, 3/3. | closed |
| T-61-12 | Information Disclosure | `held_queue.py` | high | mitigate | `save()` runs `_looks_forbidden`/`_first_forbidden` over `row_id`, `row`, `observed_signals` and `reason` **before any write**, raising `HeldQueueError`; writes via `durable_paths._atomic_write_0600`. | closed |
| T-61-13 | Tampering | `held_queue.py`'s read path | high | mitigate | `load()` (`:245-257`) — missing, unreadable, malformed, half-written and schema-mismatched all degrade to the **same** empty `{}`, never a partial read; `_validated_entries` enforces per-entry shape. | closed |
| T-61-14 | Repudiation | resume after a confidence hold | medium | mitigate | `run_manifest.py` — `CONFIDENCE_HELD = "confidence_held"` is a documented **sixth** word, distinct from `HELD`, with its own fingerprint-comparison branch rather than reusing `held`'s no-email rule. | closed |
| T-61-SC-04 | Tampering | npm/pip/cargo installs | high | mitigate | Same git-log evidence. | closed |

### 61-05 — Async ack, run_state, poll budget

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-61-15 | Repudiation | the resume path | **critical** | mitigate | `run_state.py` reports **over** `run_manifest.load_scoped()` and never reimplements verdict loading, inheriting `run_manifest.load()`'s degrade-whole rule verbatim — *"never a partially-trusted one."* | closed |
| T-61-16 | Denial of Service | progress polling | high | mitigate | `watch.py::poll_until_settled` uses a bounded `BACKOFF_SCHEDULE_SECONDS` array, not an unbounded loop; the Task 4 checkpoint compared the observed execution count against 61-01's projection. **Evidence-tier note:** the code-side bound is `[observed in source]`, but the surrounding budget arithmetic rests partly on `[documented]` platform claims (§13.0.3's sub-workflow-not-billed line) this repo has never confirmed against billing. | closed |
| T-61-17 | Information Disclosure | `run_state.py` | high | mitigate | `:122` — carries `run_manifest.py`'s Phase 23 D-11 forbidden-name refusal in substance, with `_looks_forbidden` at `:189` applied to `row_id` before persist (`:214`). | closed |
| T-61-18 | Tampering | `n8n/wf_enrichment_cloud.json` | high | mitigate | `build_cloud_workflows.py` contains every named node's construction and wiring; both summaries state the JSON was regenerated, never hand-edited. | closed |
| T-61-SC-05 | Tampering | npm/pip/cargo installs | high | mitigate | Same git-log evidence. | closed |

### 61-06 — Pair-lane association, one grant, substrate-3 scale-up

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-61-19 | Elevation of Privilege | one grant across the lane | **critical** | mitigate | `tests/test_write_gate_coverage.py::test_every_write_node_sits_behind_a_write_safety_gate`, parametrized over **every** committed cloud workflow, graph-walks each write node and asserts no path from a trigger reaches it without crossing `_writeSafetyAllows` — covering both the spliced-gate lanes and the enrichment lane's inline gating. Ran live: 21 passed, 1 skipped (a documented read-only workflow). | closed |
| T-61-20 | Tampering | a contact create without association | high | mitigate | `pairPipelineAssociationFlow.test.mjs` — the **held** case is the load-bearing assertion: `assert.equal(held.action, "review", "an unassociated contact must never be created")`. Passed live. This is the refusal that closed CLAUDE.md §13.0.1's gap without duplicating the association rule into a second lane. | closed |
| T-61-21 | Denial of Service | index-lag handling | high | mitigate | `preingest.py` — `LAG_RETRY_LIMIT = 3`; `classify_company_resolution_hold` returns `"retry"` only while `attempt < LAG_RETRY_LIMIT`, else `"held"` naming the lag. `test_no_plugin_script_polls_sleeps_or_loops_on_execution_status` confirms no sleep or while-loop outside `watch.py`. | closed |
| T-61-24 | Elevation of Privilege | `covers()`'s created-record admission | **critical** | mitigate (**substituted**) | The register's literal mechanism — runtime "admission" of a newly created id onto the grant — **was never built**; 61-06-SUMMARY.md states plainly that no production change to `covers()`'s scope logic was needed. What closes it instead: `covers()` (pre-existing, unchanged) already requires every id/domain in a send to be a subset of the grant's **own** lists fixed at open time, and a same-run create is covered via its **domain**, confirmed by the operator *before* the grant opens — never via its not-yet-existent id. Verified by three tests: domain-covered create admits, an unnamed domain still refuses, and nothing about a grant is ever written to disk or environment (GRANT-06). 183/183 in `test_write_grant.py`. The underlying property is preserved and **arguably more simply, since no runtime mutation exists to get wrong.** | closed (substituted evidence) |
| T-61-22 | Repudiation | the end-of-run account | high | mitigate | `written_records.load(path=written_records.written_records_path(run_id))` — run-scoped, never the path-less aggregate. `test_the_end_of_run_account_after_two_runs_shows_only_the_second_runs_records` passes. The fuller Phase-57 proof is explicitly named as deferred rather than assumed. | closed |
| T-61-25 | Denial of Service | substrate-3 self-dispatch | **critical** | mitigate | **Both depth guards confirmed independently in the built JSON, not one:** (1) `IF Scale Up Route`'s condition `$json.scale_up === true && (Number($json.fan_depth) \|\| 0) < 1`; (2) `Build Scale Up Fan-Out`'s jsCode separately re-checking `scale_up === true && depth < SCALE_UP_MAX_FAN_DEPTH` and rewriting each child with `scale_up: false, fan_depth: depth + 1`. `[observed live]`: `61-SCALE-UP-VERDICT.json` — parent `12045` → children `12046`/`12047`, `depth_guard_stopped_recursion: true`, no write or provider nodes in parent or children, **no grandchildren**. The "no depth supplied still stops after one hop" test passed live (32/32). | closed |
| T-61-26 | Elevation of Privilege | Task 5 read as permission for the gated live run | high | mitigate | `61-SCALE-UP-VERDICT.json`'s `scope_boundary` states explicitly *"This is NOT D-61-08's gated live unattended run"*, and the summary says *"the armed, credit-spending, unattended batch. No such run happened in this plan."* Zero writes or provider calls in parent and both children. | closed |
| T-61-SC-06 | Tampering | npm/pip/cargo installs | high | mitigate | Same git-log evidence. | closed |

*Status: closed · closed (accepted) · closed (substituted evidence) · open*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-61-01 | T-61-03 | The verdict doc records execution counts and platform-behaviour prose. Grepped for credential/token/secret patterns — only false positives on "basis token". No credential, record id or API key present. | plan-time disposition, re-confirmed this audit | 2026-09-03 |

---

## Disposition Changes This Audit

**T-61-24 — planned mitigation replaced by an unchanged pre-existing control.** The threat
anticipated a `covers()` change admitting created-record ids at runtime. That change was never
made, so there is no admission logic to audit. The property the threat protects — *no id can gain
write authorization beyond what was named at grant-open time* — holds by the pre-existing subset
check plus domain-scoped coverage confirmed before the grant opens.

This is the **third** instance this audit round of a register describing a mitigation for a
surface that was never built (after 63-04's T-63-17/T-63-20 and 58-04's T-58-17/T-58-18). Unlike
63-04, no substitute guard was needed here; unlike 58-04, the closure rests on an unchanged
control rather than a proof of absence. Recorded so the pattern stays visible rather than being
smoothed into an ordinary close.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-03 | 31 | 31 (30 mitigation-verified, 1 accepted) | 0 | `gsd-security-auditor`, `asvs_level: 1` |

**Audit depth — performed at L1–L2.** File and line reads, a live grep against a committed portal
snapshot, the cited test files run rather than cited, and one **JSON-graph trace** of the two
independent scale-up depth guards. Suites re-run during the audit: `tests/n8n/*.test.mjs` 862/862;
`tests/test_write_gate_coverage.py` 21 passed / 1 skipped; `test_write_grant.py` 183/183. No L3
end-to-end trace.

**One evidence-tier caveat carried forward.** T-61-16's budget arithmetic rests partly on
`[documented]` n8n platform claims — notably that sub-workflow executions are neither billed nor
concurrency-capped — that this repo has never verified against billing. Per §13.0.3's own rule,
documentation is not evidence of as-built behaviour. The code-side bound (the backoff schedule) is
observed in source; the cost model around it is not.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-03
