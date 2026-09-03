---
phase: "51"
slug: "backfill-pipeline-credit-sizing-dry-run"
status: verified
threats_open: 0
asvs_level: 1
created: "2026-09-03"
unregistered_surface_found: 1
---

# Phase 51 — Security

> Retroactive secure-phase run, 2026-09-03, verified at HEAD `5e6f58b`. All three plans carry
> plan-time `<threat_model>` blocks — a verification pass, not retroactive-STRIDE. 18 threats.
> No `## Threat Flags` section exists in any of the three summaries.
>
> Suites re-run during the audit: pytest **3965 passed / 154 skipped**; node **862 pass / 0 fail**
> (this phase touches no n8n code — run for regression only).

---

## Finding: unregistered attack surface, added mid-plan

**This is a different failure shape from the ones the rest of this audit round found, and the more
concerning one.** Elsewhere the problem was a register that had gone *stale* — a mitigation citing
an artifact never built (63-04, 58-04, 61-06), or an acceptance whose rationale a later change
invalidated (59-01). Here the register is **incomplete**: real new outbound disclosure surface was
added after the threat model was authored, and no entry was ever created for it.

**What was added.** 51-03's `<threat_model>` (T-51-12 … T-51-15) was authored *before* checkpoint
round 1 and never revised — `git log` on `51-03-PLAN.md` shows three commits, all pre-checkpoint
plan-authoring. Checkpoint **round 3** then wired `src.validator_sonnet.validate_conflict_with_sonnet`
into `research_with_majority_vote()` (`backfill_dry_run.py:388-454`), sending real company identity
plus disagreeing candidate values to Anthropic whenever a majority-vote research conflict is
genuine.

**Why it is not alarming, and why it still matters.** The recipient is not new: the same function
is already called live by `src/merge_policy.py`, so this mirrors T-63-12's accepted position —
*the same payloads production already sends, to the same vendor, under the same key.* Real
controls exist: a pre-spend cap (`MAX_JUDGE_VALIDATIONS_DEFAULT`, asserted at `:415-417` **before**
spending) and a fail-safe-absent pattern (confidence < 80 or a missing `evidence_url` → the value
is left absent, never defaulted). But those controls exist **without a corresponding register
entry**, which means nothing would have caused them to be reviewed, and nothing would notice if a
later edit removed them.

**Second, smaller gap.** `COVERAGE.md`'s own stated scope names ZoomInfo GTM and HubSpot CRM v3 as
"External APIs integrated by this phase" and **omits Anthropic entirely** — in the document whose
purpose is to be the phase's API-integration audit trail — even though 51-03-SUMMARY.md reports
**103 live Anthropic calls**. Not a code defect; a documentation gap sitting directly on the audit
surface.

**Recorded as T-51-16 below, pending an operator disposition.** It is deliberately *not* folded
into T-51-07/T-51-08's closed status, and no acceptance is granted by this audit — the same
principle applied to 59's T-59-06. Neither item changes `threats_open`: there is no existing
register entry for them to be open against.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| ZoomInfo GTM API → Python process | Untrusted provider JSON | firmographic attributes, attacker-shaped from this process's view |
| HubSpot CRM v3 API → Python process | Read-only responses, portal asserted before trust | company records, portal id |
| Anthropic Messages API + `web_search` → Python process | Untrusted **model-authored** JSON | URLs and enum-shaped strings sourced from the open web |
| process environment → Python process | Credentials load here and must not cross back out | ZoomInfo / HubSpot credentials |
| Python process → committed artifact / stdout | The phase's information-disclosure surface | payload dicts, provider attribute values, evidence URLs |
| operator judgement → phase advance | The only non-automated control | approval/reject across 5 checkpoint rounds |
| **Python process → Anthropic Sonnet judge** | **Added at checkpoint round 3; absent from the plan-time register — see the finding above** | real company name/domain plus disagreeing candidate values |

---

## Threat Register

### 51-01 — The tracer

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-51-01 | Information Disclosure | `enrich_company`, artifact writer | high | mitigate | `zoominfo_company_client.py:125-167` builds the `Authorization: Bearer` header locally inside `enrich_company` and **never returns it**; the token is minted only in `check_provider_credits.py:145-162` via `requests`' `auth=` tuple. All five committed artifacts plus `51-SIZING.md` grepped for `bearer`/`client_secret`/`pat-na`/`api[_-]?key` — clean. | closed |
| T-51-02 | Tampering | `backfill_dry_run.main` | high | mitigate | `backfill_dry_run.py:1145` — a **single** `patch_record` call site with a literal `dry_run=True` (grep confirms one call site in the file); `src/hubspot_client.py:30-37`'s `dry_run=True` branch prints and returns before any `requests.patch`. Two independent reasons no write can occur. | closed |
| T-51-03 | Tampering | `select_never_scored_sample`, `count_never_scored_companies` | high | mitigate | `:169-222` — count via `limit=1`/`total`; the sample **raises `RuntimeError`** on a short page against a larger total; `population_total` and `sample_size` recorded as separate fields in every artifact, so a sample can never be mistaken for the population. | closed |
| T-51-04 | Denial of Service (self-inflicted spend) | credit cap path | high | mitigate | `derive_credit_cap` (`:159-166`) is integer-only and guards `balance <= 0` → 0; `build_sizing_plan` (`:811-854`) raises **before any enrich call** when `sample_size > credit_cap`; blank-domain records are skip-logged (`:994-998`) before `enrich_company` (`:999`) is reached. | closed |
| T-51-05 | Tampering | `enrich_company` response extraction | medium | mitigate | `zoominfo_company_client.py:148-167` — every extraction is `isinstance`-guarded; malformed or exception responses degrade to `matched=False` with a reason, never raise. | closed |
| T-51-06 | Repudiation | prediction derivation | medium | mitigate | `predict_tier` (`:741-754`) derives from `(score, anti_icp_flag)` only and matches the live four-branch formula. | closed |
| T-51-SC | Tampering | npm/pip/cargo installs | low | accept | No commit in this phase touches `requirements.txt`/`package.json` — all ~20 phase SHAs checked. See AR-51-01. | closed (accepted) |

### 51-02 — Gap-fill research lane, live 10-record sample

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-51-07 | Tampering | `apply_research_to_patch` | high | mitigate | `:637-694` — only `GAP_FILL_FIELDS`, only when absent (`:669-670` `continue` if already in the patch), `lv_org_type` forced through `normalize_org_type` (`:683`), booleans requiring `isinstance(value, bool)` (`:689`). **Strengthened beyond the plan-time mitigation text:** the round-2 checkpoint added `min_confidence` and `require_evidence_url(_for)` gates against `config/field_policy.yaml` (`:675-693`) that the original mitigation never claimed. | closed |
| T-51-08 | Denial of Service (self-inflicted spend) | research lane | high | mitigate | `--research` defaults **`False`** (`:1107-1108`); the cap check at `:959-975` raises before any call and — importantly — **budgets `sample_size * RESEARCH_VOTE_REPETITIONS`** (`:967`) after majority-vote (3×) was added in plan 03. The multiplier is inside the pre-spend check, not bolted on afterwards. The research lane is structurally unreachable for a skipped record (`:996-1002`'s `continue` precedes the `:1013` research call). | closed |
| T-51-09 | Repudiation | the prediction artifact | high | mitigate | The partition assertion at `:1044-1057` (`row_ids`/`skip_ids` disjoint, union equal to the sample) raises `RuntimeError` **naming the offending ids** rather than reporting a count. | closed |
| T-51-10 | Information Disclosure | artifact writers | high | mitigate | Grepped clean (see T-51-01). | closed |
| T-51-11 | Tampering | sample selection | medium | mitigate | `select_never_scored_sample` sorts by numeric id (`:188-222`, `key=lambda r: int(r["id"])`); population and sample sizes stay separate fields. | closed |
| T-51-SC | Tampering | npm/pip/cargo installs | low | accept | Same evidence as 51-01. See AR-51-01. | closed (accepted) |

### 51-03 — Before-snapshot, coverage reconciliation, operator gate

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-51-12 | Tampering | `scored_population_snapshot` | high | mitigate | `scripts/scored_population_snapshot.py:43` imports `select_scored_population` from `scripts.rescore_population`, **identity-pinned** by `test_snapshot_uses_shared_population_definition`; write-freedom proven by `test_snapshot_is_read_only` (source-inspects for `patch_record`/`batch_update_companies`/`create_record`, all absent); refuses on truncation via `test_snapshot_refuses_truncated_population`. All read and passing. | closed |
| T-51-13 | Tampering | a wrong-portal baseline | high | mitigate | `EXPECTED_PORTAL_ID = "22617666"` hard-coded at `:46` with **no env override**; `capture_snapshot()` records `portal_id_verified`, confirmed `"22617666"` in the committed `51-BEFORE-SNAPSHOT.json`. A baseline captured against the wrong portal cannot be mistaken for this one. | closed |
| T-51-14 | Elevation of Privilege | phase advance without approval | high | mitigate | `51-03-PLAN.md:13` — `autonomous: false`; `:240` — `<task type="checkpoint:human-verify" gate="blocking">`. The summary records **five** non-self-approved checkpoint rounds, final approval 2026-08-19. | closed |
| T-51-15 | Information Disclosure | the baseline artifact | medium | mitigate | Grepped clean (see T-51-01). | closed |
| **T-51-16** | **Information Disclosure** | **Sonnet judge escalation wired at checkpoint round 3** | **medium** | **proposed: accept — awaiting operator** | **Added by this audit; absent from the plan-time register.** `backfill_dry_run.py:388-454` sends real company identity plus disagreeing candidate values to `validator_sonnet.validate_conflict_with_sonnet`. Recipient is not new (the same function is already called live by `src/merge_policy.py`), and real controls exist — a pre-spend cap asserted at `:415-417` and a fail-safe-absent pattern on confidence < 80 or a missing `evidence_url`. But no register entry and no accepted-risk row was ever created, so nothing would have caused those controls to be reviewed or noticed their removal. | **unregistered — see the finding above** |
| T-51-SC | Tampering | npm/pip/cargo installs | low | accept | Same evidence as 51-01. See AR-51-01. | closed (accepted) |

*Status: closed · closed (accepted) · unregistered (no plan-time entry)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-51-01 | T-51-SC (all three plans) | No plan in this phase installs a package or adds a dependency; none of the phase's ~20 commits touches `requirements.txt` or `package.json`. | plan-time disposition, re-confirmed this audit | 2026-09-03 |

**No AR is recorded for T-51-16.** Deliberate — an acceptance for surface the register never
covered is the operator's to grant, not this audit's to assume. The proposed disposition mirrors
AR-63-03 (same vendor, same key, no new recipient, evidence otherwise unobtainable).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Unregistered | Run By |
|------------|---------------|--------|------|--------------|--------|
| 2026-09-03 | 18 registered | 18 (15 mitigation-verified, 3 accepted) | 0 | 1 (T-51-16) | `gsd-security-auditor`, `asvs_level: 1` |

Every `mitigate` threat was confirmed against code at HEAD `5e6f58b` by reading the cited file and
line and, where the plan named one, running the pinning test live. Not an L2 boundary-placement
review or an L3 end-to-end trace.

**Worth noting about this phase's own quality:** two mitigations are *stronger* than their
plan-time text claimed — T-51-07 gained confidence and evidence-URL gates at a checkpoint, and
T-51-08's spend cap correctly absorbed the 3× majority-vote multiplier **inside** the pre-spend
check rather than after it. Registers drifting toward *weaker* than claimed is the failure this
audit hunts; drifting stronger is worth recording too, because it is the same drift mechanism
producing a benign result.

---

## Sign-Off

- [x] All registered threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [ ] **T-51-16 awaiting an operator disposition — unregistered surface, non-blocking**
- [ ] `COVERAGE.md`'s scope line omits Anthropic despite 103 live calls — documentation gap, unfixed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-03, with T-51-16 outstanding and non-blocking
