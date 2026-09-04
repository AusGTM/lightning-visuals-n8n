---
phase: "57"
slug: "ceilings-refusal-before-start-and-post-run-proof"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity
threats_open: 0
asvs_level: 1
created: "2026-09-03"
---

# Phase 57 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
>
> **Run retroactively on 2026-09-03.** All five plans carry plan-time `<threat_model>` blocks
> (`register_authored_at_plan_time: true`) — a verification pass, not retroactive-STRIDE.
>
> 41 threats, the largest register in the milestone. Phase 57 is the phase that turned a disclosed
> ceiling into a **binding preflight refusal and a pre-send mid-run stop** (D-57-00, superseding
> D-53-02), so most of its register is about guards that must refuse rather than reassure.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| operator conversation → grant object (57-01) | The only place write authority is created; in-memory, never persisted (GRANT-06) | write authorization state |
| plugin → n8n Cloud REST API (57-01) | The executions list this plan's ceiling arithmetic is built on — untrusted, laggy, cross-workflow, and **not the billing quota** | execution counts, timestamps |
| `dispatch_plan` loop → deployed backend (57-01) | The only place this plan can cause spend | enrichment envelopes |
| backend response body → durable artifact (57-02) | Untrusted JSON crossing into a `0600` file on the operator's disk | outcome words, ids, `row_id`/`association` |
| plugin → n8n Cloud REST API (57-02) | **Not crossed** — deploy moved to 57-05's phase gate; this plan made no live call | none |
| pre-write decision action → operator-facing outcome word (57-02) | What the backend **decided** is not proof of what HubSpot **did** | outcome vocabulary word |
| in-memory grant → durable disk (57-03) | The boundary GRANT-06 forbids authority from crossing; a new work-only store sits immediately beside it | re-sendable work specs, never authority |
| dispatch loop → durable disk (57-03) | A bookkeeping write that must never halt a live run | unsent chunk remainder |
| plugin → deployed n8n status endpoint (57-04) | The probe's only network call; read-only w.r.t. CRM effect, though still a POST | provider balance figures |
| deployed backend → provider credit APIs (57-04) | Where the balance is actually read; unchanged by this plan | credit balances |
| durable artifacts → operator-facing report (57-05) | Five independently written stores of varying trust, joined and rendered as one account of a run | write outcomes, held/remainder rows, spend figures |
| ephemeral runtime facts → disk (57-05) | GRANT-06 forbids **authority** crossing; observations may cross | ceiling verdict, balances, disarm result |
| repo → deployed n8n instance (57-05) | Task 4's deploy, behind a blocking checkpoint; disarmed and read back | regenerated workflow JSON (`row_id` field) |
| report text → operator decision (57-05) | What the operator does next is decided entirely by this text | rendered report block |

---

## Threat Register

### 57-01 — Ceilings, refusal-before-start, dispatch-path wiring

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-57-01 | Denial of Service (monthly allowance) | `ceiling_verdict` false negative | high | mitigate | `write_grant.py:285-286` — `sampled = (not truncated) and bool(covers_full_window or listing_exhausted)`; `remaining` is computed **only** when `sampled`, else `None` — never a partial-count number masquerading as a total. Page budget raised to `ceil(allowance/EXECUTIONS_WINDOW_PAGE_LIMIT)+2` at `:264`. | closed |
| T-57-02 | Repudiation | a ceiling stop reported as a chunk failure | high | mitigate | `chunking.py:428-484` — `ceiling_stop` is set, then `break`; the loop never appends to `results` or `failed_chunks` on this path. `CeilingStop`'s docstring (`:113-127`) states it must never flip `ChunkResult.ok` or enter `failed_batch`. A refusal is not a failure. | closed |
| T-57-03 | Elevation of Privilege | a ceiling parameter widening write scope | **critical** | mitigate | `chunking.py:352-353,371,440-443` — `execution_ceiling` is a plain optional `int` used only in `would_be > execution_ceiling`; no reference to `covers()` or `armed_window` anywhere near it. A budget knob cannot become an authority knob. | closed |
| T-57-04 | Information Disclosure | refusal text echoing a secret or config value | medium | mitigate | `chunking.py:90-103` and `:120-127` — both docstrings state, and the code confirms, that refusal text is composed only from the `index`, `would_be` and `execution_ceiling` integers: a "config-value-free sentence". | closed |
| T-57-05 | Tampering | package-manager installs | low | accept | `git log --oneline -- requirements.txt package.json` shows no phase-57 commit. | closed (accepted) |
| T-57-05a | Repudiation | a guard reporting active while structurally unreachable | **critical** | mitigate | `write_grant.py:209-316` (`allowance_headroom`) — `listing_exhausted` detection and the allowance-sized page budget land **before** the live Task-2 measurement (`sampled: true`, 2500/134/2366, recorded in `57-01-SUMMARY.md`), matching the ordering the mitigation requires. A guard that reports active but cannot fire is the failure mode this closes. | closed |
| T-57-05d | Denial of Service (allowance) | `CEILING_UNKNOWN` switching off both guards | **critical** | mitigate | `write_grant.py:1094-1117` — sampled once per grant, and unknown **never refuses**; `contact-upload/SKILL.md:319-325` — the unknown branch self-bounds to `ceiling["projected_executions"]`, never `None`. Pinned by `test_the_unknown_ceiling_branch_self_bounds_rather_than_going_unbounded`. Unknown degrades to bounded, not to unbounded. | closed |
| T-57-05e | Repudiation | a dispatch path outside the tally spending unaccounted | high | mitigate | `contact-upload/SKILL.md:314-328` — pre-call `would_be = 1 + send_row_count`, guarded by `if … > execution_ceiling`. An **AST** test walks both single-shot runbooks asserting `dispatch.dispatch(` is enclosed by an `If` followed by `single_dispatch_outcome` in the same branch (`test_write_grant.py` ~2580-2616) — structure, not string matching. | closed |
| T-57-05b | Elevation of Privilege | `override=True` bypassing the sampled remainder unrecorded | high | mitigate | `write_grant.py:1024-1029` — `override` with a blank `override_reason` raises `ValueError`. `grep -c "override=True"` over all three SKILL.md files returns **0**, pinned by `test_override_never_appears_literally_in_a_runbook`. | closed |
| T-57-05c | Denial of Service (allowance) | instance-wide concurrent consumption / retention pruning | medium | accept | `RETENTION_CAVEAT` (`write_grant.py:199-206`) and `_SAMPLING_CAVEAT`/`_CONCURRENCY_CAVEAT` (`run_report.py:311-320`, rendered in the end-of-run block) both disclose the point-in-time, lower-bound nature explicitly. See AR-57-02. | closed (accepted) |

### 57-02 — Outcome vocabulary + ingest `row_id`

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-57-06 | Information Disclosure | a secret reaching disk via the widened entry | high | mitigate | `written_records.py:311-322` — `row_id` and `association` are added to the `entry` dict **before** `for key, value in entry.items(): if _looks_forbidden(…)` sweeps the whole dict, so the new fields are covered by the existing sweep rather than bypassing it. | closed |
| T-57-07 | Repudiation | a gated row reported as completed | **critical** | mitigate | `written_records.py:143,168` — `GATED = "gated"` in `ACTION_TO_OUTCOME`; `test_report_enrichment.py:487-491::test_the_two_client_readers_agree_on_every_action`, parametrized over all ten real actions. | closed |
| T-57-08 | Tampering | hand-edited workflow JSON diverging from the builder | high | mitigate | `git show d78c15f -- n8n/wf_contact_ingest_cloud.json` — the diff is exactly **one** line, inside `Build Ingest Response`'s `jsCode` only; the commit message states regeneration via `scripts/build_cloud_workflows.py`. | closed |
| T-57-09 | Elevation of Privilege | a redeploy silently leaving live writes enabled | **critical** | mitigate | `git show 6187173 0ba8130 d78c15f` — no `deploy_n8n_workflows`, `requests.put` or `ALLOW_N8N_DEPLOY` reference in any of plan 02's three commits. The plan made no live call at all. | closed |
| T-57-09a | Repudiation | a row reported written on a pre-known id alone | **critical** | mitigate | `written_records.py:305-309` — `hs_object_id = item.get("hs_object_id") or None`, read only from the response item and never fabricated; `write_attempted` is the word used when the id was known before the write. Knowing the id is not evidence the write landed. | closed |
| T-57-09b | Repudiation | the AFTER-01 join claimed complete despite a `row_id: null` leg | high | mitigate | `run_report.py:704-709` — `gaps.append(…)` names `extraction.strip_row_id` (confirmed present at `extraction.py:876`) explicitly and marks those rows **UNJOINABLE** rather than silently joining them. A disclosed residual, not a phantom fix. | closed |
| T-57-10 | Tampering | package-manager installs | low | accept | No `requirements.txt`/`package.json` change in plan 02's commits. | closed (accepted) |

### 57-03 — Remainder queue and split offer

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-57-11 | Elevation of Privilege | a remainder entry carrying write authority across runs | **critical** | mitigate | `remainder_queue.py:130-151` — `_first_forbidden_key`, recursive over keys. `test_remainder_queue.py:140-158` proves "Armstrong Racing", "Armidale Jockey Club" and "pharmacy supplier" survive unmodified: **no false positive on the `arm` substring**. A filter that mangles legitimate data gets switched off, so this test is what keeps the filter alive. | closed |
| T-57-12 | Information Disclosure | an API key or webhook secret reaching the new `0600` file | high | mitigate | `remainder_queue.py:113-116` — exactly **ten** markers, with a comment stating "not nine"; `_atomic_write_0600` used at `:268`. | closed |
| T-57-13 | Denial of Service | a remainder-queue write failure halting live dispatch | high | mitigate | `chunking.py:457-483` — `remainder_queue.save` is wrapped in `try/except RemainderQueueError`; a failure degrades to a sentence appended to `ceiling_stop.reason` and never raises into the run. | closed |
| T-57-14 | Repudiation | auto-split presented as one-time authorization | high | mitigate | `write_grant.py:1137-1156` — the refusal text states verbatim that "each subsequent run opens its OWN grant… never a schedule that runs itself." | closed |
| T-57-14a | Repudiation | a ceiling-stopped batch losing records after the first chunk | **critical** | mitigate | `chunking.py:674-698` — `failed_batch` walks `LIST_BEARING_KEYS` and reconstructs all five `plan_chunks` shapes. `test_chunking.py:825-863` — dedicated people/companies/round-trip-per-shape tests. | closed |
| T-57-14b | Tampering | durable state mutated on an unaccepted offer | medium | mitigate | `write_grant.py:871-877` — `split_for_allowance` is pure: no transport, no write. `test_write_grant.py:1852-1867::test_a_ceiling_over_refusal_writes_nothing_to_the_remainder_queue` asserts `list(tmp_path.glob("remainder_queue*.json")) == []`. | closed |
| T-57-15 | Tampering | package-manager installs | low | accept | No dependency-manifest change in plan 03's commits. | closed (accepted) |

### 57-04 — ZoomInfo balance probe

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-57-16 | Spoofing | a probe run against an unrecognised n8n instance | high | mitigate | `scripts/prove_zoominfo_balance.py:113-119` — `_instance_ok` is logic-identical to `deploy_n8n_workflows.py::_instance_ok()`: env-var host-suffix check, fail-closed. | closed |
| T-57-17 | Repudiation | an unreadable balance presented as headroom | **critical** | mitigate | `prove_zoominfo_balance.py:145-156` — `_classify_zoominfo` returns four distinct answers (`readable`, `provider_error`, `unrecognized_response_shape`, `inconclusive`) with **no default-to-zero path**. Consistent with the standing repo rule that an unreadable balance never reads as headroom. | closed |
| T-57-18 | Information Disclosure | a credential or token echoed into the verdict file | medium | mitigate | `prove_zoominfo_balance.py:170-207` — `_build_verdict`'s fields are label, credits, HTTP status, timestamp and instance host only: no header, token or raw body. | closed |
| T-57-19 | Elevation of Privilege | a probe that could arm a write | **critical** | mitigate | `grep -cE "^\s*(import\|from)\s+(n8n_arming\|enrichment\|chunking\|write_grant)" scripts/prove_zoominfo_balance.py` → **0**, re-run live, matching the acceptance criterion's exact command. | closed |
| T-57-19a | Denial of Service / cost | a gate that reads but does not stop the request | high | mitigate | `test_prove_zoominfo_balance.py:59-135` — three tests assert `transport.calls == []` (gate absent, non-exact-truthy, wrong instance) and one asserts `len(transport.calls) == 2` with `hosts == {"fake-tenant.n8n.cloud"}`. All four green. Presence of a gate is not evidence it stops anything; these tests are that evidence. | closed |
| T-57-19b | Repudiation | claiming zero provider-credit spend without evidence | medium | mitigate | `57-ZOOMINFO-BALANCE-VERDICT.json` — `lusha_before: 3894`, `lusha_after: 3894`, `lusha_delta: 0`, with `lusha_after_cost_unmeasured` **disclosed** rather than implied zero. | closed |
| T-57-20 | Tampering | package-manager installs | low | accept | No dependency-manifest change in plan 04's commits. | closed (accepted) |

### 57-05 — End-of-run report and the phase gate

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-57-21 | Repudiation | a gated row reported as completed | **critical** | mitigate | `run_report.py:279-302` — `_OUTCOME_TEXT[GATED]` reads "this row would have been written; open a grant and re-send it… recoverable, never a failure", textually distinct from `WRITTEN`. `test_run_report.py:436` pins the distinct strings. | closed |
| T-57-22 | Repudiation | an incomplete report reading as complete | high | mitigate | `run_report.py:418-433` — `_add_gap` turns ABSENT / ANOMALOUS / ANOTHER_RUN into a named `gaps` entry per store; `:359-379` — unjoinable rows are kept and marked, never dropped. | closed |
| T-57-23 | Spoofing | another run's rows presented as this run's | high | mitigate | `run_report.py:701-745` — every store load is filtered `if e.get(RUN_ID_FIELD) == run_id`; `held_queue`'s global backlog is rendered explicitly as `"backlog"` and never merged into `this_run`. | closed |
| T-57-24 | Information Disclosure | PII accumulating in a second place | medium | mitigate | `run_report.py:668-694` — `build_run_report` returns a dict and calls no write function; `grep -in "email\b"` over the module is empty. The report renders; it does not persist. | closed |
| T-57-25 | Repudiation | projected spend presented as an invoice | medium | mitigate | `run_report.py:777-778,615-617` — `SPEND_BASIS`/`EXECUTIONS_BASIS` plus `_SAMPLING_CAVEAT`/`_CONCURRENCY_CAVEAT` rendered in the block; `test_spend_carries_projection_ceiling_and_the_over_statement_caveat`. | closed |
| T-57-26 | Tampering | package-manager installs | low | accept | No dependency-manifest change in plan 05's commits. | closed (accepted) |
| T-57-27 | Repudiation | five stores disagreeing, silently resolved | **critical** | mitigate | `run_report.py:437-531` — `_find_contradictions` names five kinds, **shows both disagreeing values and prefers neither**, and `_render_block` prepends `**REPORT INCOMPLETE**`. Five dedicated contradiction tests plus a banner test at `test_run_report.py:319-406`. | closed |
| T-57-28 | Repudiation | a missing store and a corrupt store reading identically | high | mitigate | `written_records.py:213-216,521-544` and `run_manifest.py:129-199` — both implement the same ABSENT / PARSEABLE / ANOMALOUS / ANOTHER_RUN four-word contract. | closed |
| T-57-29 | Elevation of Privilege | the per-run audit record becoming a place a grant is persisted | **critical** | mitigate | `run_report.py:169-198` — `record_audit` raises `RunReportError` and writes nothing on any forbidden-shaped value. `test_run_report.py:117-118` asserts `run_report._FORBIDDEN_NAME_MARKERS is not written_records._FORBIDDEN_NAME_MARKERS` (distinct object identity) — three independent marker lists, not one shared reference that a single edit could weaken everywhere. | closed |
| T-57-30 | Elevation of Privilege | the first live batch treated as an automatic consequence of a green suite | **critical** | mitigate | `57-05-PLAN.md:627` — `<task type="checkpoint:decision" gate="blocking">`; `57-DISCUSSION-LOG.md` records the operator selecting option-a (a small, supervised batch, with D-61-08's unattended gate staying shut). A real decision was recorded, not inferred from the phase landing. | closed |

*Status: closed · closed (accepted) · open*
*Severity: critical > high > medium > low — only open threats at or above `security_block_on` (`high`) count toward `threats_open`*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-57-01 | T-57-05 | No package installed by 57-01. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-57-02 | T-57-05c | Instance-wide concurrent consumption and retention pruning have **no available mitigation** — there is no usage endpoint and no n8n reservation mechanism. Disclosed via `RETENTION_CAVEAT` and the report's sampling/concurrency caveats rather than silently accepted. Consistent with the standing residual that the executions API list is not the billing quota. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-57-03 | T-57-10 | No package installed by 57-02. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-57-04 | T-57-15 | No package installed by 57-03. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-57-05 | T-57-20 | No package installed by 57-04. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-57-06 | T-57-26 | No package installed by 57-05. | plan-time disposition, re-confirmed this audit | 2026-09-03 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-03 | 41 | 41 (35 mitigation-verified, 6 accepted) | 0 | `gsd-security-auditor`, `asvs_level: 1` |

**Audit depth — this pass exceeded the L1 floor in most cases.** The majority of mitigations were
checked by reading the implementing code and **running the cited tests live**, not by confirming a
pattern's presence: the full plugin suite (2276 passed / 5 skipped) and
`node --test tests/n8n/ingestResponseRowId.test.mjs` (4/4) were both re-run during the audit rather
than cited from the SUMMARY files. No L2 boundary-placement review or L3 end-to-end trace was
performed.

**No mitigation cited an artifact absent from disk.** The one place a plan discloses an
intentionally-unclosed gap — T-57-09b's pair-pipeline `row_id: null` leg — is a genuine, named
residual in `run_report.py`'s `gaps`, not a phantom fix. That distinction is the specific failure
shape this audit round was told to hunt for, and phase 57 does not exhibit it.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-03
