---
phase: "54"
slug: "single-pass-armed-dispatch"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity
threats_open: 0
asvs_level: 1
created: "2026-09-03"
---

# Phase 54 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
>
> **Run retroactively on 2026-09-03.** All seven plans carry plan-time `<threat_model>` blocks —
> a verification pass, not retroactive-STRIDE. No `## Threat Flags` section exists in any of the
> seven summaries (all checked): **unregistered flags: none.**
>
> This is the phase that carried the milestone's **first real live approve** — one HubSpot write,
> on one operator-named record, inside a record-scoped armed window (54-05).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| plugin → n8n Cloud API (54-01) | Read-only measurement queries against live execution history | API key crosses; execution history can contain record identifiers |
| report artifact → git (54-01) | Whatever the measurement prints is committed | execution ids, record ids, counts |
| operator ← report text (54-02) | Everything an operator decides to spend money on is decided from this prose | outcome words, cost-disclosure sentences |
| milestone documents → future planners (54-02) | A stale requirement description causes a rebuild of something already shipped | amended G-3 / roadmap text |
| operator decision → HubSpot record (54-03) | An approve now mutates a **contact** record | untrusted intent (approve/reject) crossing into a write |
| candidate blob → property patch (54-03) | A stored candidate JSON is attacker-adjacent — hand-editable in HubSpot | field name/value pairs bound for a PATCH body |
| local built JSON → deployed n8n instance (54-04/54-06) | A PUT crosses into the system holding HubSpot credentials | workflow node content (`jsCode`, `jsonBody`) |
| deployed instance → operator's mental model (54-04) | What the skill says the endpoint does is what an operator consents to | operator-facing prose describing write behaviour |
| operator consent → live CRM write (54-05) | The one write in this phase crosses here | an operator's "yes" bound to an exact previewed patch |
| armed window → the rest of the portal (54-05) | An allowlist wider than one id is a wider blast radius | record-scoped `TEST_RECORD_IDS` |
| this repo → live n8n Cloud instance (54-06) | Deploy of the corrected contacts baseline | widened property-fetch lists, corrected `jsCode` |
| n8n review-decision endpoint → HubSpot CRM (54-06) | Deployed nodes can PATCH real records once armed | contact property values, once armed |
| grant envelope → operator's spend decision (54-07) | Rendered cost text is what an operator consents on before a write is armed | dollar figures and their basis label |

---

## Threat Register

36 threats across seven plans.

### 54-01 — Measure G-3's saving out of live execution history

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-54-01 | Elevation of Privilege | `measure_dispatch.py` | high | mitigate | `operator-claude-plugin/scripts/measure_dispatch.py:22` imports only `executions_client`; no `n8n_arming`/`arm_for_dispatch`/`armed_window` reference anywhere (grep empty). Pinned by `test_measure_dispatch.py:145::test_the_module_never_imports_arming`, which inspects `module.__dict__` for the three forbidden names — a measuring tool cannot become an arming tool. | closed |
| T-54-02 | Information Disclosure | `54-MEASUREMENT.md` | medium | mitigate | Full artifact read: execution ids, record ids, counts and a rate-table dollar figure only — no API key, credential or raw execution payload dump. | closed |
| T-54-03 | Repudiation | basis labels in `envelope()` | high | mitigate | `write_grant.py:146-147,574` — `anthropic_usd` mapped to `PROJECTED` (was `MEASURED`), with a dated comment explaining that no code path reads back real Anthropic usage. Pinned by `test_write_grant.py:1287::test_the_anthropic_figure_is_labelled_projected_never_measured`. | closed |
| T-54-04 | Tampering | `WINDOWS.md` JSON | low | mitigate | `.planning/WINDOWS.md` entry `"id": 27` present (line 358); JSON block parses; entry 26 narrowed alongside it per the summary's D4 verification. | closed |
| T-54-SC | Tampering | npm/pip/cargo installs | high | mitigate | `git show --stat` on all five commits (`e379cce`, `815edba`, `f0f1ef1`, `9990d2f`, `ace8838`) — none touches `requirements.txt`, `package.json` or `package-lock.json`. | closed |

### 54-02 — Name the two legitimate two-pass shapes, correct stale G-3 text

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-54-05 | Repudiation | `_ACTION_TO_OUTCOME` (now the `written_records` vocabulary) | high | mitigate | `report_enrichment.py` — no row ever renders `"unknown"`; `held` (needs_match_review/review) stays outside `SUCCESS_OUTCOMES` (`test_report_enrichment.py:136-144`); the per-outcome `counts` dict (line 355) never conflates a preview with `written`. **Superseded by a later deliberate decision — see the note below.** | closed |
| T-54-06 | Spoofing (of consent) | enrich-records §2 wording | medium | mitigate | `enrich-records/SKILL.md:63-64` states the cost sentence verbatim; `test_enrich_skill_contract.py:257` asserts **both** the pre-existing hold sentence and the added cost clause are present — so the addition cannot silently displace the original. | closed |
| T-54-07 | Tampering | `v1.1-ROADMAP.md` | medium | mitigate | Commit `98edcb8` — `Edit`-only, 1 file changed, 11 insertions / 3 deletions; phase-entry count unchanged. | closed |
| T-54-08 | Information Disclosure | operator-facing reason strings | low | accept | `report_enrichment.py:69-101` — all eight `_OUTCOME_REASON` strings read as record-level operational language; no credential, token or internal identifier. See AR-54-01. | closed (accepted) |
| T-54-SC | Tampering | npm/pip/cargo installs | high | mitigate | `466f026`, `1bf8f40`, `98edcb8`, `29c4fe1` touch no dependency manifest. | closed |

### 54-03 — One apply engine, two policies — contacts approve now writes

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-54-09 | Elevation of Privilege | the contacts approve branch | high | mitigate | `n8n/code/reviewDecision.js:228` — `writeAllowed === false` refuses with `not_allowlisted` **before** both the reject branch (`:237`) and the approve branch (`:258`), reusing the existing gate verdict; no new `ALLOW_*` constant was introduced. Tests at `reviewDecisionEndpoint.test.mjs:292,488,510`. | closed |
| T-54-10 | Tampering | a hand-edited candidate JSON | high | mitigate | `n8n/code/reviewApply.js:78` — `allowedFields = Object.keys(policy)`; `:84` drops any field not in that set. Compare-and-set staleness check at `:85-91` (`JSON.stringify(normalizedLive) !== JSON.stringify(storedCurrent)` → all-or-nothing refuse). | closed |
| T-54-11 | Tampering | the protected-class filter | high | mitigate | `reviewDecision.js:325-337` — the filter iterates `policy[field]` where `policy` was resolved **per object type** at `:249` (`DEFAULT_CONTACT_POLICY` for contacts, `DEFAULT_COMPANY_POLICY` for companies), not a hardcoded companies reference. That hardcoded reference **was** the bug this threat closes. | closed |
| T-54-12 | Repudiation | queue de-queueing | high | mitigate | The approve branch stamps `lv_enrichment_reviewed_at`/`P_REVIEWED_BY` (`reviewDecision.js:271,347`); the reject branch (`:237-243`) writes only `lv_enrichment_review_reason` and clears nothing (D-10/REVIEW-05 unchanged) — a reject does not silently drain the queue. | closed |
| T-54-13 | Denial of Service | queue volume | medium | accept | Applies only under the `engine-and-producer` branch. The operator's Task 2 checkpoint (2026-08-27, quoted verbatim in `54-03-SUMMARY.md`) selected `engine-only`; no contacts candidate producer was built. **Moot, not merely low-risk.** See AR-54-02. | closed (accepted) |
| T-54-SC | Tampering | npm/pip/cargo installs | high | mitigate | `90b4ef8`, `8d45a66`, `48d8f15` touch no dependency manifest. | closed |

### 54-04 — Deploy contacts-approve-writes, disarmed; correct triage wording

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-54-14 | Elevation of Privilege | the deploy | high | mitigate | `54-DEPLOY-RECORD.md` Step 4 — `scripts/verify_live_write_safety.py` disarmed run: `ALLOW_HUBSPOT_REVIEW_WRITES='false'` and both allowlists empty across all five workflows / fifteen declaring nodes, read immediately after the deploy. No arming call in any commit this plan made. | closed |
| T-54-15 | Tampering | `n8n/wf_review_decision_cloud.json` | high | mitigate | Builder-authored only; Step 1's pre-deploy diff is confined to the two Code nodes inlining the changed modules, node counts unchanged (39/26). | closed |
| T-54-16 | Repudiation | stored-versus-running content | high | mitigate | `54-DEPLOY-RECORD.md` Step 3 — an **independent second GET**, distinct from both the PUT response and `apply_mutation`'s own internal read: `jsCode` byte-identical to the committed local file, `active: true`. A stored read-back alone would not have closed this. | closed |
| T-54-17 | Spoofing (of consent) | review-triage step 6 | high | mitigate | `operator-claude-plugin/skills/review-triage/SKILL.md:196` — **"That yes is the arm."** present unchanged, verified by a deletion-grep returning 0. | closed |
| T-54-SC | Tampering | npm/pip/cargo installs | high | mitigate | `a2b5981`, `f3e3140` touch no dependency manifest. | closed |

### 54-05 — Live approve proof

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-54-18 | Elevation of Privilege | the armed window | **critical** | mitigate | `54-LIVE-PROOF.md` — gate 3 (`ALLOW_HUBSPOT_REVIEW_WRITES`) was armed **only by the administrator's own deploy** (`ENABLE_BAKED_FLAGS`), never by Claude; Claude's role was limited to submit plus a disarm-redeploy of the committed disarmed artifact. Post-disarm independent read: `verify_live_write_safety.py` → `VERDICT: disarmed PASS` across all fifteen declaring nodes. | closed |
| T-54-19 | Spoofing (of consent) | the approve submit | high | mitigate | The preview was re-confirmed three separate times (executions `11994`, `11998`, `11999`) before submit, and the submitted patch (execution `12000`) is byte-identical to what the operator approved at the checkpoint — including the reviewer label `operator (robert li)` passed through verbatim. | closed |
| T-54-20 | Repudiation | the proof artifact | high | mitigate | Both a BEFORE read (queue fetch, pre-any-preview) and an AFTER read (`verify_decision()` re-derived against execution `12000`'s own `would_write`, plus independent execution `12001` on a different webhook path) are present; the unexercised promote branch is explicitly named as unproven in three separate sections. | closed |
| T-54-21 | Tampering | blast radius | high | mitigate | Record-scoped allowlist (`TEST_RECORD_IDS='347569451461'` only, verified armed then verified empty again) plus an explicit "Nothing outside the one named record was written" section. **Honest L1 note:** this is an *inferential* statement — single-id allowlist plus exactly one submit — not a sampled read-back of other records' `lastmodifieddate`. | closed |
| T-54-SC | Tampering | npm/pip/cargo installs | high | mitigate | All five commits (`bc31ac8`, `a0d0df5`, `d2ce0a3`, `1f2cff9`, `ee09972`) touch no dependency manifest. | closed |

### 54-06 — Contacts review-decision gap closure

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-54.06-01 | Tampering | Task 3's deploy to `WBJwoZOo63wzeP69` | high | mitigate | `operator-claude-plugin/scripts/n8n_control.py:316` — `assert_only_allowlisted_change(original, modified, allowed_node_names)` runs **before** the deactivate call at `:321`, i.e. before any network mutation; `original` is always fetched fresh at `:302` and never accepted as a stale argument. | closed |
| T-54.06-02 | Elevation of Privilege | write-safety literals on deployed nodes | **critical** | mitigate | `54-06-DEPLOY-RECORD.md` Step 5 — `verify_live_write_safety.py` re-run after the PUT: `ALLOW_HUBSPOT_REVIEW_WRITES='false'`, both allowlists empty, across all fifteen declaring nodes including the two this deploy touched. `VERDICT: disarmed PASS`. | closed |
| T-54.06-03 | Tampering | the contacts non-clobber baseline | high | mitigate | `tests/test_review_contact_property_sets.py` (both tests re-run green) — the decision-lane fetch requests all twelve `config/field_policy.yaml` contacts keys while the queue node stays deliberately narrow. Live-verified in deploy record Step 4 (`mobilephone` present on decision nodes, absent on the queue node). | closed |
| T-54.06-04 | Repudiation | what reached the running instance | medium | mitigate | Step 4 — an independent second GET, distinct from the PUT response and `apply_mutation`'s internal GET, confirms byte-identical `jsCode` and the widened property sets live. | closed |
| T-54.06-05 | Denial of Service | the n8n monthly execution budget | low | accept | Deploy record confirms **0** executions consumed — administrative API calls only; the newest execution `12001` predates and is unrelated. See AR-54-03. | closed (accepted) |
| T-54.06-SC | Tampering | npm/pip/cargo installs | high | mitigate | `98afc5a`, `4f0f25f`, `e4fcfe7` touch no dependency manifest. | closed |

### 54-07 — Anthropic-spend sentence bound-word contradiction (WR-04)

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-54.07-01 | Repudiation | `write_grant.envelope()`'s cost block | medium | mitigate | `write_grant.py:641` — now reads "a projection from the dated rate table above, not a measurement"; the test is scoped to the single Anthropic-spend line and asserts `"projection"` present with `"worst case"`/`"floor"` absent (`test_write_grant.py:1287`). | closed |
| T-54.07-02 | Information Disclosure | a projection presented as a measurement | medium | mitigate | Same test re-run this audit: 183/183 in `test_write_grant.py`, including 54-01's untouched `PROJECTED` basis assertions. | closed |
| T-54.07-03 | Tampering | live HubSpot / n8n state | low | accept | This plan's sole commit (`5cafcf0`) touches only `write_grant.py` and its test — no workflow file, no deploy invocation, no live instance contact. See AR-54-04. | closed (accepted) |
| T-54.07-SC | Tampering | npm/pip/cargo installs | high | mitigate | `5cafcf0` touches no dependency manifest. | closed |

*Status: closed · closed (accepted) · open*
*Severity: critical > high > medium > low — only open threats at or above `security_block_on` (`high`) count toward `threats_open`*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-54-01 | T-54-08 | The eight operator-facing outcome-reason strings name record-level facts the operator already supplied; no credential or internal identifier appears in any of them. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-54-02 | T-54-13 | Applies only under the `engine-and-producer` branch. The operator's Task 2 checkpoint explicitly selected `engine-only`, so no contacts candidate producer was built and the queue-flood precondition never shipped. Moot rather than tolerated. | operator checkpoint 2026-08-27 | 2026-09-03 |
| AR-54-03 | T-54.06-05 | The deploy/bounce/verify sequence consumed **0** n8n executions — all administrative API calls, none appearing in execution history. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-54-04 | T-54.07-03 | This plan's sole commit touches two Python files (a sentence and its test); no workflow file modified, no deploy script invoked, no live instance touched. | plan-time disposition, re-confirmed this audit | 2026-09-03 |

---

## Judgment Calls Recorded During Verification

**T-54-05 was superseded by a later phase's deliberate decision, not silently broken.** 54-02's
mitigation text said neither `held` nor `previewed`/`proposed` joins `SUCCESS_OUTCOMES`. Commit
`0ba8130` (Phase 57-02, **D-57-03**) later reclassified `proposed` → `no_action` *into*
`SUCCESS_OUTCOMES`, on the documented reasoning that a look-only preview which saved nothing **on
purpose** is a genuine success rather than a failure — `written_records.py`'s own docstring states
this. `held` still stays excluded, exactly as the original threat required, and the concern the
threat existed to prevent (a row rendering ambiguously as `"unknown"`, letting an operator believe
a write landed) remains fully closed.

*Loose end for whoever next touches that file:* `test_report_enrichment.py:130-134` carries a
comment block still asserting **"Neither is a success,"** directly above a test at line 147 that
asserts the opposite for `proposed`. Stale documentation, not a functional gap; it does not reopen
the threat, but it will mislead the next reader.

**T-54-21's evidence is inferential, and correctly scoped to L1.** The cited artifact exists and
satisfies the plan's own mitigation text, but it reasons from configuration state — a single-id
allowlist and exactly one submit — rather than an empirical sampled read-back of other records'
`lastmodifieddate`. At `asvs_level: 1` that is a legitimate close; at L2 it would want the sample.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-03 | 36 | 36 (32 mitigation-verified, 4 accepted) | 0 | `gsd-security-auditor`, `asvs_level: 1` |

All node tests (862/862) and the relevant Python test files (268/268 spot-checked) were re-run
live during this audit and pass on current `HEAD` — confirming the mitigations are not merely
historically true but **presently** true. This is not an L2 boundary-placement review or an L3
end-to-end trace.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-03
