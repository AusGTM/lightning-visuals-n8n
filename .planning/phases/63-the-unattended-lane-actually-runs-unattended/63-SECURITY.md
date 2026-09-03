---
phase: "63"
slug: "the-unattended-lane-actually-runs-unattended"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity
threats_open: 0
asvs_level: 1
created: "2026-09-03"
---

# Phase 63 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
>
> **Run retroactively on 2026-09-03, after the phase closed.** Phase 63 shipped without a
> SECURITY.md because the `verify:post` secure-phase hook was skipped — `workflow.security_enforcement`
> was absent from `.planning/config.json` and therefore **defaulted to enabled**. The key is now set
> explicitly. This is the **second** `*-SECURITY.md` in a repo of ~60 phases; the register below is
> the phase's own, authored at plan time in all five PLAN files
> (`register_authored_at_plan_time: true`), so this is a verification pass, not retroactive-STRIDE.

---

## Trust Boundaries

Consolidated from the five PLAN threat models.

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| scheduler → shim (63-01) | cron/launchd invokes the shim unattended, with no human present to see a prompt or a refusal; whatever the shim execs runs as the operator | an executable path chosen at run time |
| cache-root listing → `exec` target (63-01) | the shim picks an executable from a directory listing under a **user-writable** plugin cache root | a filesystem path that becomes code |
| wrapper → log file (63-01) | the wrapper appends operator-supplied path strings to a log the admin later reads | absolute install paths, version numbers |
| harness → host scheduler (63-02) | the proof harness registers a real job on the operator's machine that executes code unattended | a temporary launchd registration |
| harness → the operator's existing schedule (63-02) | the harness runs on a machine already carrying the operator's real sweep registration | none intended — see T-63-06 |
| n8n executions API → replay harness (63-03) | stored execution data crosses into a local file holding real company identity and research evidence | company names, evidence URLs, model prose |
| replay harness → Anthropic Messages API (63-03) | stored judge payloads containing real company data are sent to a third-party model endpoint | the same payloads production already sends |
| working corpus → git (63-03) | a local corpus file sits inside a repository that gets committed | real company identity |
| research candidate → judge model selection (63-04) | model-generated `reasons[]` content would have decided which adjudicator a record gets | untrusted reason strings — **surface never built, see below** |
| local workflow JSON → live n8n Cloud (63-05) | committed code crosses into a shared production orchestrator that talks to HubSpot and three paid providers | workflow definitions, baked flags |
| deploy-time overlay → baked flags (63-05) | a deploy argument can enable an arming flag inside the uploaded JSON | write-authorization state |
| proof POST → live workflow (63-05) | an inbound webhook request reaches a running production lane | one company id |

---

## Threat Register

32 threats: 27 numbered (T-63-01 … T-63-27) plus 5 per-plan supply-chain entries.

### 63-01 — the durable launcher shim

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-63-01 | Tampering | `newest_install_root` → shim `exec` | high | mitigate | Verified in `operator-claude-plugin/scripts/sweep_shim.py:106-134`: candidates must match `durable_paths._VERSION_DIR_RE` **and** carry `skills/backend-sweep/lv-sweep-run.sh`; **two** containment checks run — one on the version directory's `resolve()` and one on the wrapper's own — so neither a symlinked version dir nor a symlinked wrapper can redirect the `exec` outside the cache root. Cache root is baked at install time, never read from the environment (module docstring states this as a deliberate anti-injection choice for unattended execution). | closed |
| T-63-02 | Elevation of Privilege | installed shim file | high | mitigate | Verified `sweep_shim.py:166` — `path.chmod(0o700)` after write; `install_shim` is a plain idempotent overwrite, so a tampered shim is restored by the next `--install`. | closed |
| T-63-03 | Spoofing | resolver output consumed by the shim | medium | mitigate | Verified in `_SHIM_TEMPLATE` (`sweep_shim.py:77-81`): non-zero status, empty output, **or** a resolved root with no wrapper all take the same branch — log, banner, `exit 1`. There is no fallback to `$1`; an unresolved answer cannot become an executed one. | closed |
| T-63-04 | Denial of Service | staleness self-check in the wrapper | medium | mitigate | Verified `lv-sweep-run.sh:34-44`: the entire block contains no `exit`; a failed or hanging resolver takes the `else` branch, stamps "could not check staleness", and the sweep proceeds with its own exit status. Regression-tested by `test_stale_and_healthy_exit_codes_match_for_identical_sweep_output`. | closed |
| T-63-05 | Information Disclosure | stale stamp line in the sweep log | low | accept | Line carries absolute install paths and version numbers only — no credential, token or operator datum. The log already carries full sweep JSON. See Accepted Risks. | closed (accepted) |
| T-63-A-SC | Tampering | npm/pip/cargo installs | low | accept | No package installed by this plan; `sweep_shim.py` imports stdlib plus the plugin's own `durable_paths`. | closed (accepted) |

### 63-02 — the real-scheduler proof

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-63-06 | Denial of Service | the operator's existing sweep schedule | high | mitigate | `grep -v '^\s*#' … \| grep -c crontab` reads **0** for both `verify_sweep_shim_scheduler.sh` and the concurrency harness added 2026-09-03. Neither writes to `~/Library/LaunchAgents`; each registers a uniquely-labelled agent from a plist inside its own `mktemp -d` and removes it by label. D-63-03 holds. | closed |
| T-63-07 | Elevation of Privilege | orphaned launchd registration | high | mitigate | Both harnesses tear down from a `trap … EXIT` (plus INT/TERM), guarded against double-execution, and confirm success with an **independent** `launchctl list` grep rather than `unload`'s own status; an unconfirmed teardown exits non-zero naming the label and deliberately leaves the work dir for manual cleanup. Independently re-checked live after this audit: `launchctl list \| grep -i lightningvisuals` returns nothing. | closed |
| T-63-08 | Tampering | temporary world under `mktemp -d` | medium | mitigate | Both harnesses build and destroy their own world; neither references a path under the real plugin cache root. Confirmed live in 63-02's record: `find "$HOME/.claude/plugins/data" -iname lv-sweep-launcher.sh` finds nothing — no shim was ever installed on the real machine. | closed |
| T-63-09 | Spoofing | evidence read from the log | medium | mitigate | Both harnesses assert on marker **CONTENT**, never line count or position. The concurrency harness strengthens this: each fire's payload embeds its own pid and start/end epochs, so a leftover line from a prior fire cannot be mistaken for a later one, and overlap is decided by comparing embedded intervals. A missing marker is reported **inconclusive** and exits non-zero — never a pass. | closed |
| T-63-10 | Information Disclosure | proof records committed to `.planning/` | low | accept | Records hold temporary paths, version directory names and stub output. The stubbed entrypoint prints one synthetic marker; no backend response, credential or operator datum is produced. See Accepted Risks. | closed (accepted) |
| T-63-B-SC | Tampering | npm/pip/cargo installs | low | accept | No package installed; the harnesses are `/bin/sh` plus `launchctl` and the plugin's own scripts. | closed (accepted) |

### 63-03 — the offline judge replay

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-63-11 | Information Disclosure | committed verdict artifact | high | mitigate | Verified by reading `63-JUDGE-REPLAY-VERDICT.json`: every row's keys are exactly `body_sha256`, `classification`, `input_id`, `lane`, `model_a`, `model_b` — no body, no company name, no evidence URL, no model prose. Raw corpus is gitignored (`.gitignore:19`, `.judge-replay-corpus/`) with a comment naming why. | closed |
| T-63-12 | Information Disclosure | Anthropic request payloads | medium | accept | The replay sends the same payloads production already sends, to the same vendor under the same key — no new recipient, no new data class. Refusing it would make the D-63-06 evidence unobtainable. See Accepted Risks. | closed (accepted) |
| T-63-13 | Tampering | harness write surface | high | mitigate | Verified: `grep -cE "requests\.(post\|put\|patch\|delete)" scripts/replay_judge_models.py` → **0**; `grep -c hubapi` → **0**. `tests/test_replay_judge_models.py` reads `MODULE_SOURCE` and asserts these absences, so a later edit adding a write fails the suite rather than shipping. | closed |
| T-63-14 | Spoofing | verdict artifact consumed by 63-04 | medium | mitigate | `verdict` is a single enumerated top-level value; thresholds (`min_corpus`, the drop reasons) were fixed before the data was seen and are stored alongside it. 63-04's checkpoint read the artifact, not a human summary. | closed |
| T-63-15 | Repudiation | which models were compared | medium | mitigate | Verified `scripts/replay_judge_models.py:447-455` — `_resolve_model_ids()` reads `build_cloud_workflows.CONFIG_FLAG_DEFAULTS` (lazily, at call time) and both ids are echoed into the artifact as `model_a`/`model_b`. The evidence cannot name a model the workflow does not use. | closed |
| T-63-16 | Denial of Service | Anthropic rate limits during replay | low | accept | Two calls per input over a `--limit`-bounded corpus; only an all-raised run escalates to `HARNESS_FAILURE`. See Accepted Risks. | closed (accepted) |
| T-63-C-SC | Tampering | npm/pip/cargo installs | low | accept | No package installed; `anthropic`, `requests`, `PyYAML` already in `requirements.txt`. | closed (accepted) |

### 63-04 — the judge-model lever (DROP branch)

> **Read this before the table.** This plan's register was authored **before** its own
> `checkpoint:decision` gate, so it describes the SHIP branch's world — a shipped per-reason
> model-routing predicate. The gate resolved to **DROP** (`insufficient_corpus` +
> `material_disagreement`, `63-JUDGE-LEVER-DROP-RECORD.md`) and **nothing was built**.
> T-63-17 and T-63-20 therefore cite a mitigation artifact, `tests/test_judge_model_routing.py`,
> that does not exist on disk — it belonged to the branch never taken.

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-63-17 | Elevation of Privilege | model-selection predicate in `Build Judge Request` | high | mitigate (**substituted**) | **The planned mitigation was never built because the threatened surface was never built.** Closed instead on a stronger control: `tests/test_judge_spec.py::test_jg_drop_63_04_judge_model_is_unconditional_single_constant` asserts the node has exactly one `const model` assignment whose RHS is the bare `ANTHROPIC_JUDGE_MODEL` identifier — no ternary, no lookup, no reason-conditional expression — and that no second judge-model flag exists in the builder source. The planned test would have guarded a predicate's *correctness*; this guards that **no predicate exists**, so there is nothing to smuggle a reason past. Proved to be a real guard, not a tautology: injecting a `confidence_band`-conditional ternary to `claude-haiku-4-5` into a temporary perturbation of `n8n/wf_enrichment_local_live.json` made it fail with the intended message; file restored clean, suite 10/10. | closed (substituted evidence) |
| T-63-18 | Tampering | authorization surface (`computeEscalation`, band, fail-safe) | high | mitigate | Verified by git history rather than by claim: `n8n/code/judge.js` last touched by `d5d08ae` (58-06), `n8n/code/contactJudge.js` by `9e7644a` (16.2-02), `config/escalation_policy.yaml` by `169b35f` (58-06) — **no phase-63 commit touches any of the three**. The band survives intact at `confidence_between: [75, 85]` (`config/escalation_policy.yaml:27`). A performance change did not quietly narrow what gets adjudicated, because no performance change shipped. | closed |
| T-63-19 | Spoofing | `judge_reasons` on an inbound row | medium | mitigate | Verified `n8n/code/judge.js:397` — `escalation_reasons` is read from `row.judge_reasons`, computed in-workflow by `computeEscalation` and the Judge Gate wrapper from upstream-validated data. It is never taken from the request envelope, so a caller cannot assert a reason set. (Contrast the four legitimate request-level flags in CLAUDE.md §13.0.2 — `judge_reasons` is deliberately not one of them.) | closed |
| T-63-20 | Tampering | contacts lane inheriting unevidenced routing | high | mitigate (**substituted**) | Same substitution as T-63-17, and the reason the guard test covers **both** lanes: it asserts the single-unconditional-constant property on `Build Contact Judge Request` as well as `Build Judge Request`. The contacts lane — which had zero replay evidence — provably kept its existing adjudicator, and a future edit giving it per-reason routing fails the test. | closed (substituted evidence) |
| T-63-21 | Repudiation | which model adjudicated a given record | low | accept | The verdict path already stamps `verified_by_model` provenance; the dropped change would have altered the value written, not whether it is written. Moot under DROP. See Accepted Risks. | closed (accepted) |
| T-63-D-SC | Tampering | npm/pip/cargo installs | low | accept | No package installed; the dropped change was a constant, a dataclass field and a ternary — none of which shipped. | closed (accepted) |

### 63-05 — the disarmed deploy

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-63-22 | Elevation of Privilege | `enable_baked_flags` deploy-time overlay | high | mitigate | `63-DEPLOY-RECORD.md`: `_requested_overlay_flags()` returned `{}`, asserted **before** the write gate, so the uploaded JSON equals the committed JSON the suites ran against. The two-key gate (`DRY_RUN=false` **plus** `ALLOW_N8N_DEPLOY=true`) means the PUT cannot fire accidentally. | closed |
| T-63-23 | Tampering | live enrichment workflow content | high | mitigate | Node count **123** asserted from an independent post-bounce GET, matching the locally built JSON exactly — the Phase 62 changes edited `jsCode`/`jsonBody` strings and added no node. Content matching no commit could not have been accepted as deployed. | closed |
| T-63-24 | Elevation of Privilege | proof execution reaching a write path | high | mitigate | Execution `12070` returned `write_blocked`; 22 nodes ran, none matching any provider/write/Anthropic marker. `TEST_RECORD_IDS = ""` independently confirmed empty in the committed JSON, corroborating the empty-allowlist claim behind the block. | closed |
| T-63-25 | Repudiation | what the running instance holds | high | mitigate | A stored read-back was explicitly treated as insufficient: the running instance was proven by an execution **after** a deactivate/activate bounce, with the execution id recorded. Matches the standing repo rule that a bare PUT never reloads a running workflow. | closed |
| T-63-26 | Information Disclosure | deploy record in `.planning/` | low | accept | Holds workflow ids, node counts, an execution id and one company id. No credential or provider payload; `.n8n_credential_ids.json` is gitignored and never quoted. See Accepted Risks. | closed (accepted) |
| T-63-27 | Denial of Service | bounce leaving a workflow inactive | medium | mitigate | The bounce asserts post-activate state from an independent GET, following `scripts/prove_scale_up_runtime.py:141 _bounce_and_verify`; a workflow left inactive fails the verify rather than passing silently. | closed |
| T-63-E-SC | Tampering | npm/pip/cargo installs | low | accept | No package installed; the plan ran existing repo scripts against an existing instance. | closed (accepted) |

*Status: open · closed · closed (accepted) · closed (substituted evidence)*
*Severity: critical > high > medium > low — only open threats at or above `security_block_on` (`high`) count toward `threats_open`*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-63-01 | T-63-05 | Stale stamp line names absolute install paths and version numbers only. The log already carries full sweep JSON and is operator-local. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-63-02 | T-63-10 | Proof records hold temporary paths, version directory names and synthetic stub output. No backend response, credential or operator datum is ever produced — the stub is a `print` of one marker. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-63-03 | T-63-12 | The replay sends the payloads production already sends, to the same vendor under the same key. No new recipient, no new data class. Refusing it would make the D-63-06 adequacy evidence unobtainable — the alternative was shipping a model change on no evidence. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-63-04 | T-63-16 | Two Anthropic calls per input over a `--limit`-bounded corpus; only an all-raised run escalates to `HARNESS_FAILURE`. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-63-05 | T-63-21 | Provenance stamping is unaffected by a change that did not ship. Moot under the DROP branch. | plan-time disposition, moot under DROP | 2026-09-03 |
| AR-63-06 | T-63-26 | Deploy record holds workflow ids, node counts, an execution id and one company id; no credential or provider payload. `.n8n_credential_ids.json` is gitignored and never quoted. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-63-07 | T-63-A-SC … T-63-E-SC | No plan in this phase installs a package or adds a dependency. No package legitimacy audit is required because no package is installed. Verified: phase 63 touched no `requirements.txt` or `package.json`. | plan-time disposition, re-confirmed this audit | 2026-09-03 |

---

## Disposition Changes This Audit

Recorded separately from the register so the substitution is visible rather than buried in a cell.

**T-63-17 and T-63-20 — planned mitigation replaced by a stronger one.**

Both threats' mitigation column named `tests/test_judge_model_routing.py`. That file does not
exist. By the letter of the classification rule (*mitigation found?*) both were **OPEN**, both
`high`, and `security_block_on: high` — a blocking pair.

The substance is different from a missing control: 63-04's threat model was authored before its
own drop-gate resolved, so it describes a per-reason model-routing predicate that was **evaluated
and never built**. The threatened surface does not exist. The absent test belonged to the SHIP
branch.

They are closed on `tests/test_judge_spec.py::test_jg_drop_63_04_judge_model_is_unconditional_single_constant`,
added the same day by this phase's nyquist validation pass (`63-VALIDATION.md`, gap G1) — which
turned out to be exactly the missing evidence. It asserts, on **both** the company and contact
judge nodes, that model selection is one unconditional reference to `ANTHROPIC_JUDGE_MODEL`. That
is a stronger control than the planned one: the planned test would have verified a shipped
predicate used exact-set membership rather than containment; this one verifies **no predicate
exists at all**, and fails if one is introduced.

Independently confirmed rather than assumed: injecting a `confidence_band`-conditional ternary to
`claude-haiku-4-5` into a temporary perturbation of `n8n/wf_enrichment_local_live.json` made the
test fail with its intended message. The file was restored (`git status` clean) and the suite
returned 10/10.

**This is a substitution, not a waiver.** If the judge-model lever is ever revisited — the drop
record's "What would change the answer" section describes what that would take — both threats
return to their original form and need the exact-set-membership mitigation as written.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-03 | 32 | 32 (19 mitigation-verified, 11 accepted, 2 substituted) | 0 | orchestrator, L1 grep-depth per `asvs_level: 1` |

**Audit depth, stated honestly.** `asvs_level: 1`, so this is grep-and-read depth: each mitigation
was checked against the implementation by reading the cited file and line, and by running the
`crontab`, write-verb and git-history greps recorded in the register. It is **not** an L2
boundary-placement review or an L3 end-to-end trace. No `gsd-security-auditor` subagent was
spawned — the workflow's short-circuit permits this at `asvs_level: 1` once `threats_open` reaches
0, and the operator chose closure on substituted evidence over an independent pass. A deeper
review would be `security_asvs_level: 2` and a re-run.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-03
