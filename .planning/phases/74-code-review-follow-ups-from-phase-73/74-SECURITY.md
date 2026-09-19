---
phase: "74"
slug: "code-review-follow-ups-from-phase-73"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-19"
---

# Phase 74 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| n8n execution runData → git | `scripts/freeze_execution_rundata.py` freezes live executions into `tests/n8n/fixtures/frozen/` | webhook shared secret, caller IP, ZoomInfo OAuth JWTs, HubSpot error objects (may carry `Authorization`) — all must be scrubbed before commit |
| session scratchpad → repo | the raw, unredacted `12522` capture lived only in the session scratchpad; the widened freezer is the sole path into git | raw runData with live headers |
| `.env` → process environment | deploy / bounce / proof-send / freeze credentials loaded in-process by python-dotenv only | `N8N_URL`, `N8N_API_KEY`, HubSpot private-app token |
| local repo → n8n Cloud | two scoped `--only` disarmed deploys + one bounce of the changed generated bodies | workflow bodies whose every `ALLOW_HUBSPOT_*` literal must read `"false"` |
| n8n Cloud → HubSpot | two disarmed proof sends (ingest update batch, enrichment recompute) | contact emails (read-only search), company id — no write permitted |
| operator CSV → plugin tooling | `csv_dedupe.py` reads an operator file and writes dedupe artifacts | contact PII in the input and in the generated outputs (see T-74-07-01) |
| plugin → planning docs / git | UAT, SUMMARY, REVIEW, VERIFICATION committed | execution ids, node names, counts; no tokens, no raw items |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-74-01-01 | Information Disclosure | `scripts/freeze_execution_rundata.py` narrow scrub | high | mitigate | D-74-07: non-enumerating `_scrub` over the whole node run, five key names at any depth (Task 1) | closed — `scripts/freeze_execution_rundata.py:91-98,117-142` `_scrub`/`_SENSITIVE_KEYS` recursive whole-node-run walk (7 keys) |
| T-74-01-02 | Information Disclosure | committed ZoomInfo OAuth JWT bodies in `exec_12434`/`exec_12449` | high | mitigate | D-74-08: re-redact in place through the widened freezer and commit the rewritten bytes (Tasks 1-2). Git history is not rewritten — accepted per D-74-08, tokens have a 24h lifetime | closed — `exec_12434`/`exec_12449` working tree: `/usr/bin/grep -c eyJ` = 0; history residual accepted (R-74-01) |
| T-74-01-03 | Information Disclosure | a future freeze reintroducing the gap | medium | mitigate | D-74-09 guard test over the whole frozen directory, refusing four value shapes (Tasks 1-2) | closed — `tests/n8n/frozenFixtureSecrets.test.mjs` directory-wide, 4 value shapes; 2/2 pass |
| T-74-01-04 | Information Disclosure | the raw unscrubbed `12522` runData in the session scratchpad | high | mitigate | Task 3 forbids copying it into the repo; the only path into git is the widened freezer | closed — `git log --all --name-only | grep -i 12522` hits only the committed frozen fixture; no raw capture ever in git |
| T-74-01-05 | Information Disclosure | credentials echoed to the transcript while freezing | medium | mitigate | in-process dotenv driver, never `source .env`, never printing env values (Task 3) | closed — `freeze_execution_rundata.py:74-76` `load_dotenv()` in-process; scratchpad driver only |
| T-74-01-06 | Tampering | over-broad scrub blanking a field a consumer test asserts on | medium | mitigate | Pitfall 4 check: run `test_run_report_enrich_account.py` immediately after re-redaction; no path exemptions permitted (Task 2) | closed — `operator-claude-plugin/tests/test_run_report_enrich_account.py` 3/3 pass on re-redacted fixtures |
| T-74-01-SC (typo `T-74-74-SC` in 74-01-PLAN.md) | Tampering | npm/pip/cargo installs | low | accept | No package install of any kind is in this plan's scope; no dependency is added | closed (accepted — R-74-SC) — no dependency added (R-74-SC) |
| T-74-02-01 | Repudiation | `write_grant.py` grant preview omitting the execution count on a config gap | medium | mitigate | WR-01: hoist the lane-invariant assignment out of the raising `try` (Task 1) | closed — `write_grant.py:593-594` `executions = 1` hoisted above the raising `try` |
| T-74-02-02 | Spoofing (of provenance) | `write_grant.py` reporting another lane's basis/providers | medium | mitigate | WR-02: per-lane basis and providers from the estimate (Task 1) | closed — `write_grant.py:190,610-614,671` per-lane `CONTACT_UPLOAD_BASIS`, basis/providers from the estimate |
| T-74-02-03 | Tampering | `report_enrichment.py` last-lane-wins ledger overwrite | high | mitigate | WR-05: key by (lane, id); skip ambiguous ids rather than merging (Task 2) | closed — `report_enrichment.py:219-267` ledger keyed `(lane, id)`, ambiguous ids skipped |
| T-74-02-04 | Repudiation | a silently dropped excluded-marker count hiding rows from the audit | medium | mitigate | WR-06: return and conditionally report the count (Task 3) | closed — `chunking.py:691-722` `excluded_marker_count` returned, reported when non-zero |
| T-74-02-05 | Denial of Service (of the report channel) | a match chunk that does not settle inside a fixed bound, leaving rows unchecked | medium | mitigate | D-74-13: expose the bound as an operator-facing override and surface the unchecked count (Task 3) | closed — `chunking.py:653` `resolve_bound_seconds`; `test_chunking.py` override + floor tests |
| T-74-02-SC | Tampering | npm/pip/cargo installs | low | accept | No package install is in this plan's scope; no dependency is added | closed (accepted — R-74-SC) — no dependency added (R-74-SC) |
| T-74-03-01 | Tampering | `csv_dedupe.py` row canonicalisation truncating a short row | high | mitigate | WR-11: index walk over the header with empty-string padding (Task 1) | closed — `csv_dedupe.py:44-63` index-walk `_canonical_rows`, no `zip()` |
| T-74-03-02 | Tampering | `csv_dedupe.py` writing outputs beside a same-stem path it does not own | medium | mitigate | WR-12: derive both paths from the input's full resolved path (Task 1) | closed — `csv_dedupe.py:131` `out_dir = path.parent` (full resolved input path); see T-74-07-01 for the new surface this opens |
| T-74-03-03 | Spoofing (of configuration) | a second, drifting column-mapping resolver in the dedupe CLI | medium | mitigate | WR-03: reuse the one canonical config-gate reader (Task 2) | closed — `csv_dedupe.py:153-163,180` `_resolve_configured_mapping_path` via `config_gate.load_config()` |
| T-74-03-04 | Repudiation | `preview.py` swallowing a collapsed-block parse failure into an absent block | medium | mitigate | WR-04: narrow the exception; name the offending path (Task 2) | closed — `preview.py:155-180` `CollapsedBlockError` / `read_collapsed_block` names the path |
| T-74-03-05 | Elevation of Privilege (of an unintended write) | `review_decision.py` treating an absent key as agreeing, letting an unintended field through | high | mitigate | WR-09: presence tested before value equality; reason names which case fired (Task 3) | closed — `review_decision.py:501-524` presence tested before `_as_hubspot_text` equality |
| T-74-03-SC | Tampering | npm/pip/cargo installs | low | accept | No package install is in this plan's scope; no dependency is added | closed (accepted — R-74-SC) — no dependency added (R-74-SC) |
| T-74-04-01 | Denial of Service (silent row loss) | `walkWorkflow.mjs` padding whichever branch is empty | high | mitigate | D-74-03: gate padding on output index 0; pin against `exec_12522` (Tasks 1, 3) | closed — `tests/n8n/lib/walkWorkflow.mjs:534` `outputIndex === 0` gate, no per-node exemption |
| T-74-04-02 | Denial of Service (silent row loss) | enrichment research-error branch leaving `Build Response Merge` undrained | high | mitigate | D-74-14: one gated sentinel with walker-derived Merge targets; regenerate once (Task 2) | closed — `build_cloud_workflows.py:9065-9104` `Companies Research Errored Sentinel`; 7 occurrences in `wf_enrichment_cloud.json` |
| T-74-04-03 | Tampering | a second producer on an existing input double-firing under v1 | high | mitigate | targets restricted to Merge inputs; mutual-exclusion argument written into the builder comment; a per-input producer check in the acceptance criteria (Task 2) | closed — sentinel targets Merge inputs only, derived index; `mergeInputContract.test.mjs` green |
| T-74-04-04 | Repudiation | a documented-only claim read later as observed | medium | mitigate | two-tag convention enforced in the section 13.0.3 rows; research-error branch explicitly left documented-only (Task 3) | closed — `CLAUDE.md` §13.0.3 two-tag row citing execution `12522` |
| T-74-04-05 | Repudiation | closing an open engine question on a phase-id match rather than evidence | medium | mitigate | D-74-12: verdict from frozen runData only; todo left open with its trigger otherwise (Task 3) | closed — `.planning/todos/pending/2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md` still open, trigger unchanged |
| T-74-04-06 | Information Disclosure | runData printed raw into a transcript | medium | mitigate | node names, run counts and item counts only; never raw items (Tasks 1-3) | closed — SUMMARY/UAT report node names and counts only; no raw item quoted |
| T-74-04-SC | Tampering | npm/pip/cargo installs | low | accept | No package install is in this plan's scope; no dependency is added | closed (accepted — R-74-SC) — no dependency added (R-74-SC) |
| T-74-05-01 | Spoofing | classification of an error item resting on a guessed shape | high | mitigate | D-74-04: explicit stamp applied on the error edge, tested first (Task 1) | closed — `n8n/code/pairCreateOutcome.js:92-93,118` `_isStampedError` checked first; `pairCreateOutcome.test.mjs` 48/48 |
| T-74-05-02 | Repudiation | a create with no joined response reported to the operator still carrying its pre-write action | high | mitigate | D-74-06: unconfirmed-create action, reason passed through verbatim, mapped to failed (Task 2) | closed — `build_cloud_workflows.py:926-927,1039-1040`, `written_records.py:216` `create_unconfirmed` → FAILED |
| T-74-05-03 | Information Disclosure | serializing a raw HubSpot error object (which can carry the outbound request's auth header) into a row or fixture | high | mitigate | keep the existing read-at-most-a-few-named-scalars rule in the create-failure row constant; the new stamp node adds one boolean and copies nothing else (Tasks 1-2) | closed — `build_cloud_workflows.py:880-895` `_createFailureReason` reads only message/description/statusCode |
| T-74-05-04 | Denial of Service (report channel) | the create-failure input starving on an all-update batch | medium | mitigate | D-74-02: gated sentinel with a derived target index (Task 3) | closed — `Create Failure Row Sentinel` + gate present in `wf_contact_ingest_cloud.json`; fired live on execution 12676 |
| T-74-05-05 | Tampering | a sentinel composed with the write-safety gate that the arming setter does not rewrite, dropping rows on a real armed batch | high | mitigate | Task 3 requires confirming the setter is scan-driven before relying on the composition, with a named fallback otherwise | closed — `operator-claude-plugin/scripts/n8n_arming.py:125` scan-driven `for node in wf.get("nodes", [])` |
| T-74-05-06 | Repudiation | a documented-only lane claim read later as observed | medium | mitigate | the create-error lane stays documented-only per D-73-19; the UNOBSERVED tag names the open question (Task 1) | closed — `tests/n8n/ingestCreateErrorLane.test.mjs:100` `KNOWN-UNOBSERVED` tag |
| T-74-05-SC | Tampering | npm/pip/cargo installs | low | accept | No package install is in this plan's scope; no dependency is added | closed (accepted — R-74-SC) — no dependency added (R-74-SC) |
| T-74-06-01 | Elevation of Privilege | deploying a body whose write-safety constants read true | critical | mitigate | committed-body check in Task 1's automated verify; post-deploy read-back of every flag; no arming variable set, no arming setter called | closed — committed bodies: zero non-`"false"` write-safety declarations across 101+289 nodes; live read-back in `74-UAT.md` Task 1 and post-send; orchestrator re-read live |
| T-74-06-02 | Tampering | deploying more than the two changed workflows | high | mitigate | scoped single-file deploy argument, twice; the deploy output is recorded and checked for absence of the other four (Task 1) | closed — `74-UAT.md` deploy table names only the two changed workflows; `updatedAt` of the other four unchanged since 2026-09-18 |
| T-74-06-03 | Denial of Service (budget) | a self-dispatch or retry burst consuming the monthly execution budget | high | mitigate | hard ceiling of 2 executions stated in the objective; two-minute burst watch after each bounce; the named stop is deactivating the workflow, the 2026-09-10 precedent | closed — `74-UAT.md` burst watch: baseline 12663/12662 → only 12676/12677; instance-wide list confirms |
| T-74-06-04 | Information Disclosure | the webhook shared secret and caller IP in runData reaching git or the transcript | high | mitigate | freeze through the D-74-07-widened scrubber only; D-74-09 guard re-run over the directory; print node names and counts only, never raw items | closed — `exec_12676`/`exec_12677` pass `frozenFixtureSecrets.test.mjs` in directory scope |
| T-74-06-05 | Information Disclosure | credentials echoed while deploying or sending | medium | mitigate | in-process dotenv driver; never `source .env`; never printing env values | closed — in-process dotenv driver (scratchpad `plan74_06_driver.py`, never committed); no `source .env` |
| T-74-06-06 | Repudiation | claiming a live property the sends never exercised | medium | mitigate | D-74-14's research-error branch is explicitly NOT exercised and stays documented-only; stated in the SUMMARY and the UAT addendum | closed — `exec_12677.runData.json` has no `IF Research Errored` / `Companies Research Errored Sentinel` key |
| T-74-06-07 | Denial of Service (cost) | an enrichment send that silently spends provider credits or Anthropic calls | medium | mitigate | the zero-cost request shape is named; the acceptance criterion requires proving from runData that no provider or Anthropic node ran | closed — `exec_12677.runData.json` (71 keys) has no provider/judge/research node; no `HubSpot *Update`/`Create` node in either fixture |
| T-74-06-SC | Tampering | npm/pip/cargo installs | low | accept | No package install is in this plan's scope; no dependency is added | closed (accepted — R-74-SC) — no dependency added (R-74-SC) |
| T-74-07-01 | Information Disclosure (data hygiene) | `csv_dedupe.py` WR-12 fix writes `deduped-<stem>.csv` / `dedupe-report-<stem>.json` (PII-bearing) beside the operator's input file, outside repo control, with no cleanup step in `contact-upload/SKILL.md` | medium | mitigate | `74-REVIEW.md` WR-13: add the two artifacts to the skill's cleanup step, or return the write location to a gitignored scratch dir with disambiguated names | open — below high threshold (non-blocking); surfaced by the Phase 74 code review, not by any plan register |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (`high`) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

Register origin: 41 threats authored at plan time (six `<threat_model>` blocks, 74-01..74-06;
74-01's supply-chain row is mis-numbered `T-74-74-SC` in the plan and is recorded here as
`T-74-01-SC`); one threat (T-74-07-01) added at audit time from the phase's own code review
(WR-13). No SUMMARY carried a `## Threat Flags` block.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-74-01 | T-74-01-02 | Git history before commits `e7caad29` / `bc83d181` still contains the two fixtures' pre-redaction bytes (ZoomInfo OAuth JWT bodies). History is not rewritten per D-74-08: the tokens carry a 24-hour lifetime and were minted 2026-09-18; the working tree and every later commit are clean and guarded by `frozenFixtureSecrets.test.mjs`. | operator (D-74-08 ruling, 74-CONTEXT.md) | 2026-09-19 |
| R-74-SC | T-74-0[1-6]-SC | No package install of any kind in the phase; no dependency added (`requirements.txt` / `package.json` unchanged since `dd7d8110`). | planner (per-plan threat model) | 2026-09-19 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-19 | 42 | 41 | 1 (medium, non-blocking: T-74-07-01) | gsd-security-auditor (sonnet) — `## SECURED`, 41/41 plan-time threats verified at file:line with suites re-run live (node 1321/0, pytest 5170/160); orchestrator added T-74-07-01 from `74-REVIEW.md` WR-13 |

Auditor notes carried forward, non-blocking: `74-REVIEW.md` IN-01 (a hypothetical third
`WRITE_SAFETY_GATE_JS` sentinel could drift hand-rolled test arm-lists; the production setter
`n8n_arming.set_write_safety` is scan-driven, so T-74-05-05 stays closed) and IN-02 (a
placeholder-exclusion lookahead in `frozenFixtureSecrets.test.mjs` is dead code today and fails
closed, not open).

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed (one medium threat open, below the `high` block threshold)
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-19
