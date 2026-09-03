---
phase: "48"
slug: "enrichment-coverage"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (high).
# T-48-11 and T-48-04(05) were found OPEN by this audit — both `high`, both instances of
# "the declared mitigation is not the code that ran". They were carried to the operator rather
# than re-closed by the audit, and ACCEPTED by the operator on 2026-09-03 naming D-48-01 as the
# compensating control (AR-48-03, AR-48-04). Nothing is outstanding.
threats_open: 0
threats_open_below_threshold: 0
asvs_level: 1
created: "2026-09-03"
---

# Phase 48 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
>
> **Run retroactively on 2026-09-03**, as part of the cross-phase secure-phase sweep of phases
> 46–63. Phase 48 shipped without a SECURITY.md because the `verify:post` secure-phase hook was
> skipped — `workflow.security_enforcement` was absent from `.planning/config.json` and therefore
> **defaulted to enabled**. The key is now set explicitly.
>
> All seven plans carry plan-time `<threat_model>` blocks (`register_authored_at_plan_time: true`),
> so this is a **verification pass, not retroactive-STRIDE**. 38 rows — the phase includes plan
> 48-07, inserted mid-execution (`0b7ec0f`) after the paid research misclassified Racing NSW.
>
> Phase 48 belongs to the **archived v0.9 milestone**. Mitigations were verified at current HEAD
> (`8ffe359`), not at the phase's own close.

---

## T-48-11 and T-48-04(05) — the declared mitigation was not the code that ran

**Resolved 2026-09-03 by operator decision. Closed as ACCEPTED (AR-48-03, AR-48-04) naming
D-48-01 as the compensating control, with the operator as approver.** The history is kept in full
because the *reason* the register was wrong is the useful part.

Both threats declared the mitigation as **operator-exclusive** control of the deploy and arming
keys. That is not what happened.

| Threat | Declared mitigation | What the phase's own record shows |
|---|---|---|
| T-48-11 (48-04) | *"Claude **never** sets either key; the deploy and the bounce are a blocking operator checkpoint."* | `48-DEPLOY-PROOF.md:241` — *"Task 2 — Deploy and bounce, **performed by Claude under D-48-01**."* |
| T-48-04 (48-05) | *"Both **operator-armed** in a blocking checkpoint…"* | `48-ARM-RECORD.md:111` — *"Arm (call 1, **Claude-executed under D-48-01**)."* |

This is **failure shape #3** — the declared mitigation is not the code that ran. By the letter of
the classification rule both were **OPEN**, both `high`, and `security_block_on` is `high`: a
blocking pair. Two independent audit passes agree on these facts.

**Why the audit did not close them on its own authority.** Rewriting the mitigation to describe
what actually happened would have been the audit self-authoring an acceptance on the operator's
behalf — the sweep's standing blocking anti-pattern. Both auditors declined; the second was
explicitly told the operator's approval existed and still returned *facts only*, leaving the
rationale unwritten. The acceptance below is transcribed from the operator's recorded decision,
not composed by the audit.

**The operator's rationale, as recorded** (`.planning/HANDOFF.json`, decision entry for phase 48):

> Both threats declared the mitigation as operator-exclusive key control; evidence shows Claude
> ran the deploy+bounce and armed both surfaces. D-48-01 (`48-CONTEXT.md:387-429`, verified to
> exist) is a written, phase-scoped, self-expiring waiver granted BEFORE the act, explicitly a NEW
> waiver and not a revival of the expired D-47.5-01. Its declared bounds were honoured exactly
> (1 deploy+bounce, 1 armed window, 5-record cap, per-shell-only keys, disclosed rather than
> exceeded), every mechanical safeguard verified closed independently, and it expired with the
> phase so there is no live exposure.

**Every load-bearing fact in that rationale was verified, not assumed:**

- **D-48-01 exists where claimed** — `48-CONTEXT.md:387-429`, read in full. Explicitly phase-scoped
  (`:401-403` *"Expires with Phase 48… Does not carry to Phase 49 or any later work"*) and
  explicitly **not** a revival (`:394-395` *"`D-47.5-01` is **not** being revived. This is a NEW,
  separately-granted waiver with its own expiry"*).
- **Granted before the act, with alternatives on the table** — `:389-391` records the operator was
  asked with two named alternatives (run the commands themselves, or pause the phase at 4/7).
  Confirmed by commit order, re-run independently by this record's author:
  `git merge-base --is-ancestor 375e919 f76abdf` → true, and `375e919 → 1ff80b9` → true. The
  waiver commit strictly precedes both acts it authorises.
- **Bounds honoured exactly** — 1 deploy + 1 bounce (`48-DEPLOY-PROOF.md:249,278`), 1 armed window
  opened and closed with *"no excess to disclose"* (`48-ARM-RECORD.md:208-209`), 5-record cap,
  per-shell keys only (`:211-214`).
- **No live exposure at current HEAD** — independently re-read by this record's author from the
  committed `n8n/wf_enrichment_cloud.json`: `ALLOW_HUBSPOT_RECORD_WRITES = "false"` and
  `TEST_RECORD_IDS = ""`. The waiver expired at the seal commit `44f154e`.
- **The mechanical safeguards stand on their own, independent of who typed the command** — see
  AR-48-04. Only the *who-typed-it* clause ever rode on the waiver.

**One supporting claim could NOT be confirmed — recorded rather than smoothed.** The handoff's
account of this acceptance described the two-key gate at `enrich_coverage_companies.py:489-492` as
having *"genuinely failed closed on the first attempt"*. The second audit pass found **no record of
that gate denying at runtime**. What the records actually show is (a) the *deploy script's separate*
two-key gate defaulting to a disarmed dry run (`48-DEPLOY-PROOF.md:163`), and (b)
`48-05-SUMMARY.md:184` — *"The window ran clean on the first attempt: zero timeouts, zero
retries"* — which is a clean run, not a denial. The nearby `write_blocked` fail-closed event
(`48-05-SUMMARY.md:163`) is execution `11858`, **a prior phase's**. This changes nothing about the
disposition: the gate is verified default-deny **in code** (`:489-492`, re-read by this record's
author) and its refusal branch is verified **in test**
(`test_run_coverage_window_raises_before_first_write_when_writes_not_allowed`, `:468`, suite green
43/43). It is closed on code plus test, never on the runtime-denial anecdote. The anecdote should
not be repeated.

**If the delegation is ever repeated:** D-48-01 expired at the phase seal. The `<constraints>`
table's "arming is operator-only" and "deploys are operator-only" rows resumed full force, and any
later phase needs its own separately-granted waiver. Citing D-48-01 would be the exact error
D-48-01 was itself written to prevent.

---

## Trust Boundaries

Consolidated from the seven PLAN threat models.

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| driver → HubSpot CRM v3 (48-01/03/05) | an enum-valued property is written; an out-of-vocabulary value 400s the whole batch | `lv_org_type`, `lv_org_type_verified_at`, `lv_enrichment_review_reason` |
| driver → n8n webhook → HubSpot (48-01/05) | a second, indirect write path, reached only when the n8n-side allowlist is open | one company id + `recompute: true` |
| `47-RESEARCH-RESULTS.json` → driver (48-01) | untrusted-by-provenance model free text crosses into a CRM-bound value | research prose, evidence URLs |
| operator shell env → driver (48-01/05) | two independent env keys gate every write | `DRY_RUN`, `ALLOW_ENRICH_COVERAGE` |
| Anthropic API → `Claude Web Research` node (48-02) | `on_error="continueRegularOutput"` means a 400 arrives as **data, not failure** | error-shaped JSON payloads |
| builder source → deployed workflow (48-02/04) | build output is committed; a hand edit diverges artifact from source | 8 workflow JSON files |
| local build artifact → deployed n8n instance (48-04) | a PUT changes what production runs | workflow definitions, baked flags |
| Claude → deploy/activation authority (48-04) | declared severed; **D-48-01 re-granted it, phase-scoped** | deploy + bounce + arm commands |
| n8n execution API → proof artifact (48-04) | the only trustworthy evidence of what actually runs | `workflowData.nodes`, `runData` |
| operator shell → both arming surfaces (48-05) | two independent gates; either closed silently degrades the run | driver env keys + n8n allowlist |
| captured research artifact → decision table (48-07) | model output on disk crosses into a value 48-05 writes to the CRM | `lv_org_type: "regulator"` |
| `config/taxonomy.yaml` → both research prompts (48-07) | vocabulary semantics cross into what the model is told | org-type definitions — **declared, no threat row; see WARNINGS** |
| operator judgement → `ORG_TYPE_DECISIONS` (48-07) | a human override of a machine classification enters the write path | `override_of` / `override_rationale` |

---

## Threat Register

38 rows across seven plans.

> **ID collisions — do not collapse these when merging registers.** Plans 48-06 and 48-07 both
> allocate `T-48-19` … `T-48-22` with **different meanings**; they are disambiguated below as
> `(06)` / `(07)`. `T-48-01`, `T-48-02` and `T-48-04` likewise recur across plans as distinct rows.

### 48-01 — the coverage driver

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-48-01 | Tampering | `build_coverage_patch` → HubSpot PATCH | high | mitigate | Verified `scripts/enrich_coverage_companies.py:441-445` — `if org_type not in VALID_ORG_TYPES: raise ValueError(...)`. This is a **`raise`, not an `assert`**, and the code says why at `:458-460`: *"must be a real, unstrippable check… `assert` is removed entirely under `python -O`"*. Re-read independently by this record's author. Second guard at `:461-464` (`FORBIDDEN_PROPS.isdisjoint`). Suite green 43/43. | closed |
| T-48-02 | Denial of Service (budget) | `estimate_phase48_cost` / `refuse_if_over_budget` | medium | mitigate | Verified `:931-932` — `refuse_if_over_budget(...)` / `except BudgetRefused`. `test_tracer_refuse_if_over_budget_raises_and_never_returns_a_shorter_list` (`tests/test_enrich_coverage_companies.py:174`) asserts the **no-trim** property by name — a refusal, never a silent truncation. | closed |
| T-48-04 | Elevation of Privilege | `coverage_writes_allowed` two-key gate | high | mitigate | Verified `:489-492`, re-read independently: `DRY_RUN` defaults `"true"`, `ALLOW_ENRICH_COVERAGE` defaults `"false"`; both must flip. `post_webhook_event`'s `armed` has **no default** (`scripts/remediate_veto_companies.py:627-629`, docstring: *"raises NotArmedError when falsy before any network call"*), tested at `:203`. Refusal branch tested at `:468`. **Closed on code plus test — see the caveat in the section above about the unconfirmed "failed closed at runtime" anecdote.** | closed |
| T-48-05 | Spoofing | model free text → CRM enum | medium | mitigate | Verified `:105-107` — a literal authored table, with the comment *"No regex/keyword mapper exists anywhere in this module — `decide_org_type` reads this table, it never derives the enum value from research free text."* Grep confirms no mapper exists. | closed |
| T-48-SC(01) | Tampering | npm/pip/cargo installs | high | accept | `git diff --stat f312f1d^ 44f154e -- requirements.txt package.json package-lock.json Cargo.toml pyproject.toml` → **empty**. → AR-48-02 | closed (accepted) |

### 48-02 — the research-error gate (D-04)

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-48-03 | Spoofing | `Claude Web Research` → `Validate Research Output` | high | mitigate | `IF Research Errored` present in the built JSON (3 occurrences) and in the builder at `scripts/build_cloud_workflows.py:5813`; wiring at `:6189-6194` routes true → failure terminal **before** the merge chain. `tests/n8n/researchErrorGateFlow.test.mjs:126` — *"REAL expression returns true on a degenerate shape (**fail closed**)"*. | closed |
| T-48-06 | Repudiation | failure terminal response shape | medium | mitigate | Verified builder `:5831` — `{ ...row, action: "research_failed", gate: { reason: message } }`; `research_failed` present in the committed JSON. A research failure is attributable, never indistinguishable from a no-match. | closed |
| T-48-07 | Tampering | committed `n8n/wf_*.json` | high | mitigate | **Independently re-proved this audit rather than accepted on claim.** The repo was copied to a scratchpad (`rsync`, excluding `.git`/`.venv`), the builder re-run there, and `cmp` taken against the committed files: **8/8 identical** across every `wf_*.json`. The working tree was confirmed untouched (`git status --porcelain -- n8n/` empty) before and after. | closed |
| T-48-08 | Denial of Service | `ENRICH_CO_GATE` shared across three workflows | medium | mitigate | Verified builder `:5826` — `try { return $('Build Research Request').all(); } catch (e) { return []; }` — workflow-local, fails closed. Tested at `researchErrorGateFlow.test.mjs:153`. | closed |
| T-48-SC(02) | Tampering | npm/pip/cargo installs | high | accept | As AR-48-02. | closed (accepted) |

### 48-03 — the one paid research call

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-48-01(03) | Tampering | Racing NSW output → `lv_org_type` | high | mitigate | Enum-constrained prompt `RACING_NSW_ORG_TYPE_SYSTEM` (`src/web_research.py:69`); post-hoc validation is the same `VALID_ORG_TYPES` raise at `:441`; the D-03 `unknown`-plus-reason fallback at `:242-247` and `:450-457`. | closed |
| T-48-02(03) | Denial of Service (budget) | pre-run estimate | medium | mitigate | Commit order proves the estimate was ex-ante: `85bb4cd` (estimate produced, 2026-08-12 23:15) **precedes** `d239258` (the paid call, 2026-08-13 05:56). | closed |
| T-48-09 | Information Disclosure | committed raw research artifact | low | accept | `48-RESEARCH-RACING-NSW.json` read in full: public findings only — Wikipedia, racingnsw.com.au, an NSW Parliament annual-report PDF. Credential-pattern grep (`pat-na1\|sk-ant\|token\|secret\|password\|api_key`) → **0**. No personal data. → AR-48-01 | closed (accepted) |
| T-48-10 | Repudiation | spend without a recorded decision | medium | mitigate | `48-03-SUMMARY.md:99,112` — the operator responded `approve-as-estimated` at the Task 2 checkpoint, authorising exactly one call, **before** it was made. | closed |
| T-48-SC(03) | Tampering | npm/pip/cargo installs | high | accept | As AR-48-02. | closed (accepted) |

### 48-04 — the deploy proof

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| **T-48-11** | Elevation of Privilege | `scripts/deploy_n8n_workflows.py` two-key gate | **high** | **mitigate → accept** | Declared as *"Claude never sets either key; the deploy and the bounce are a blocking operator checkpoint."* **Not what ran** — `48-DEPLOY-PROOF.md:241`. Accepted by the operator naming D-48-01 as the compensating control. → AR-48-03, and the full account above. | **closed (accepted — operator, 2026-09-03)** |
| T-48-12 | Repudiation | "deployed" claimed without a running-instance change | high | mitigate | Verified `48-DEPLOY-PROOF.md:314-327` — the proof is execution `11865`'s **own embedded `workflowData.nodes`**, count **111** against the pre-deploy baseline **109** (`:23`), captured after the bounce. A stored read-back is explicitly rejected as evidence (`:314-315`), matching the standing repo rule that a bare PUT never reloads running content. | closed |
| T-48-13 | Tampering | retry after a client timeout touching a record twice | medium | mitigate | Verified `enrich_coverage_companies.py:805-807` — `except requests.exceptions.Timeout:` sets `timed_out` and falls through to reading the execution back; **no retry**. The POST was disarmed throughout this plan regardless. | closed |
| T-48-14 | Information Disclosure | `.env` contents in logs | medium | mitigate | Module docstring `:30-35` documents the absolute-path `load_dotenv('/abs/path/to/.env')` form and why a bare call resolves relative to the calling file. `48-DEPLOY-PROOF.md:16` — auth via `config_gate.load_config()`, *"never `.env` directly"*. Secret-print grep → **0**; the only such print (`:910`) names the **variable**, not its value. | closed |
| T-48-SC(04) | Tampering | npm/pip/cargo installs | high | accept | As AR-48-02. | closed (accepted) |

### 48-05 — the armed window

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-48-01(05) | Tampering | five PATCH payloads | high | mitigate | The same verified `raise` at `:441-445`, reached before the payload is built. | closed |
| **T-48-04(05)** | Elevation of Privilege | the two arming surfaces | **high** | **mitigate → accept** | Three clauses. Clause 1 — *"Both operator-armed in a blocking checkpoint"* — is **false**: `48-ARM-RECORD.md:111`. Clauses 2 and 3 **hold and are independently verified**: `assert_allowlist_exact` at `:577-644` (fresh GET; raises unless the writes-flag is `"true"`, domains empty, ids non-empty **and** exactly equal to the intended set), closed in the same invocation and proven by an independent fetch (`:199-208`). Accepted by the operator naming D-48-01. → AR-48-04, and the full account above. | **closed (accepted — operator, 2026-09-03)** |
| T-48-15 | Tampering | duplicate write from a retried timeout | high | mitigate | The same no-retry path at `:805-807`. `48-ARM-RECORD.md:185` — exactly 5 new execution ids (`11866`–`11870`) ahead of `11865`; one PATCH and one POST per record, counted and disclosed. | closed |
| T-48-16 | Repudiation | a scoring change attributed to the wrong writer | medium | mitigate | **Precisely: zero *write* occurrences** of the four derived properties. The grep does return hits — every one is a **read** list (`POPULATION_PROPERTIES` `:320-323`, the settle-read `:819`) or the **`FORBIDDEN_PROPS` guard itself** (`:516-519`, enforced at `:461-464`). `build_coverage_patch` emits exactly three keys, none of them derived. This refines the first pass's "returned 0" into the load-bearing form. | closed |
| T-48-17 | Denial of Service | window left open after the run | high | mitigate | Verified `:838-850` (cited as `:841-850` — trivial drift, re-read independently): a `finally:` block whose comment quotes D-48-01 verbatim, calling `disarm_fn()` unconditionally, never inside the `try`, never skipped on an exception, followed by an independent `rereader`. Three independent post-window re-reads confirmed at `48-ARM-RECORD.md:194-197`, `:203-206`, `:219-222`. | closed |
| T-48-18 | Information Disclosure | `.env` contents in logs | medium | mitigate | As T-48-14. | closed |
| T-48-SC(05) | Tampering | npm/pip/cargo installs | high | accept | As AR-48-02. | closed (accepted) |

### 48-06 — the run report

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-48-19(06) | Repudiation | run report figures | high | mitigate | `48-RUN-REPORT.md` carries **13** citations to the committed artefacts named in its `read_first` (`48-ARM-RECORD`, `48-DEPLOY-PROOF`, `48-BEFORE/AFTER.json`, `48-COST-ESTIMATE`). | closed |
| T-48-20(06) | Tampering | LOCKED decision file | medium | mitigate | Hard git evidence: `6cb639a docs(48-06): amend LOCKED venue decision with dated D-02 closure block` → numstat **`32  0`** — 32 added, **0 deleted**. Additive exactly as declared. | closed |
| T-48-21(06) | Repudiation | requirement status over-claim | high | mitigate | **Drifted location, mitigation intact.** At the seal commit `44f154e`, `.planning/REQUIREMENTS.md:192-193` carried both COVER rows ending *"Joint closure not asserted here"*, with the split note at `:200-202`. v0.9 has since been archived; the same text lives at HEAD in `.planning/milestones/v0.9-REQUIREMENTS.md:255,265`. Drift, **not** a missing control. | closed (drifted) |
| T-48-22(06) | Tampering | the deliberately-red parity sweep | medium | mitigate | `scripts/run_scoring_parity.py` was last touched by `986c37f` (Phase **41**, 2026-08-08). No phase-48 commit touches it — the red sweep was not quietly made green. | closed |
| T-48-SC(06) | Tampering | npm/pip/cargo installs | high | accept | As AR-48-02. | closed (accepted) |

### 48-07 — the Racing NSW correction (plan inserted mid-phase, `0b7ec0f`)

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-48-19(07) | Repudiation | the corrected Racing NSW entry | high | mitigate | Verified `enrich_coverage_companies.py:122-123` — `override_of: "regulator"` plus a full `override_rationale`. Test: `test_racing_nsw_captured_artifact_is_unedited_and_the_override_is_recorded` (`tests/test_enrich_coverage_companies.py:346`). | closed |
| T-48-20(07) | Tampering | evidence rewritten to match the conclusion | high | mitigate | The strongest available evidence: `48-RESEARCH-RACING-NSW.json` has **exactly one commit in its entire history** — `d239258` (48-03). The artifact still reads `"lv_org_type": "regulator"`, i.e. it **contradicts the shipped decision** and was never reconciled to it. The record was left to disagree with the outcome rather than tidied. | closed |
| T-48-21(07) | Spoofing | a guard that "fixes" a classification by guessing | high | mitigate | Verified `src/taxonomy.py:145-166` — a pure function returning reason strings, docstring *"Reads only; NEVER mutates; NEVER rewrites org_type to another value."* Named test found: `test_guard_never_flips_an_incoherent_regulator_to_another_value` (`tests/test_enrich_coverage_companies.py:83`). | closed |
| T-48-22(07) | Tampering | an unintended rebuild or deploy | high | mitigate | All four 48-07 commits (`e332250`, `89c362a`, `3d8ec85`, `c38a748`) show **zero** files under `n8n/` in `git show --stat -- n8n/`. The mid-phase correction was landed offline at zero spend, as declared. | closed |
| T-48-23 | Denial of Service | shared-contract change breaking research consumers | medium | mitigate | `coherence_flags` is additive (`src/taxonomy.py:181,219`); the self-check asserts at `:256-262`; suite green 43/43 at HEAD. | closed |
| T-48-SC(07) | Tampering | npm/pip/cargo installs | high | accept | As AR-48-02. | closed (accepted) |

*Status: open · closed · closed (accepted) · closed (drifted)*
*Severity: critical > high > medium > low — only open threats at or above `security_block_on` (`high`) count toward `threats_open`*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-48-01 | T-48-09 | The committed research artifact holds only public findings — Wikipedia, racingnsw.com.au, an NSW Parliament annual-report PDF, and an evidence summary. Credential-pattern grep returns 0; no personal data. Read in full this audit. | plan-time disposition, premise re-verified this audit | 2026-09-03 |
| AR-48-02 | T-48-SC(01) … (07) | No plan in this phase installs a package or adds a dependency, so no package legitimacy audit is required. `git diff --stat f312f1d^ 44f154e` over `requirements.txt`, `package.json`, `package-lock.json`, `Cargo.toml` and `pyproject.toml` → **empty** across the full range. | plan-time disposition, premise re-verified this audit | 2026-09-03 |
| AR-48-03 | T-48-11 | **Operator's recorded rationale:** both threats declared the mitigation as operator-exclusive key control; the evidence shows Claude ran the deploy+bounce and armed both surfaces. D-48-01 (`48-CONTEXT.md:387-429`, verified to exist) is a written, phase-scoped, self-expiring waiver granted **before** the act, explicitly a new waiver and not a revival of the expired D-47.5-01. Its declared bounds were honoured exactly (1 deploy+bounce, 1 armed window, 5-record cap, per-shell-only keys, disclosed rather than exceeded), every mechanical safeguard was verified closed independently, and it expired with the phase, so there is no live exposure. *Supporting facts independently verified: waiver commit `375e919` precedes both acts `f76abdf` and `1ff80b9`; `ALLOW_HUBSPOT_RECORD_WRITES = "false"` and `TEST_RECORD_IDS = ""` at HEAD.* | **operator** | 2026-09-03 |
| AR-48-04 | T-48-04(05) | Same waiver and same operator rationale as AR-48-03, **plus** the mechanical controls that stand independently of who typed the command: the two-key default-deny gate (`enrich_coverage_companies.py:489-492`), `assert_allowlist_exact` (`:577-644`, fresh GET, five refusal branches, all unit-tested at `:433-467`), disarm-in-`finally` (`:838-850`), and three independent post-window re-reads all agreeing closed (`48-ARM-RECORD.md:194-222`). One window opened, one closed, *"no excess to disclose"*. Only the **who-typed-it** clause ever rode on the waiver. | **operator** | 2026-09-03 |

---

## WARNINGS — unregistered attack surface (failure shape #4)

No phase-48 SUMMARY contains a `## Threat Flags` section (grep for "threat" across all seven → 0
hits), so the executor declared nothing. That absence was not treated as a complete list. Two items
found; **neither blocks**, and both are recorded rather than dispositioned by the audit.

| Flag | Evidence | Why unregistered | Severity |
|---|---|---|---|
| `system_prompt` override on the shared production research function | `src/web_research.py:118` — `claude_web_research(record, system_prompt: str = None)`, added by `d239258` (48-03) | 48-03's register has no row for a caller-supplied system prompt entering a production LLM call path. **Fails safe by default** (`:129` — `system_prompt = system_prompt or RESEARCH_SYSTEM`) and is in-process only, not remotely reachable. | low |
| taxonomy content rendering into both production research prompts | `89c362a` touches `config/taxonomy.yaml` (+41) and `src/web_research.py` (+10/−2) | 48-07 **declares the boundary** (*"`config/taxonomy.yaml` → both research prompts"*) but allocates no threat row to it; T-48-23 covers only consumer breakage (DoS), not content influence. | low |

**Failure shapes #1, #2 and #5: none found in phase 48**, stated affirmatively since all five were
hunted. (#1) Every asserted control was located on the path it names. (#2) No acceptance premise
was destroyed by a later plan — 48-07 was inserted mid-phase and *strengthened* 48-03's Racing NSW
handling rather than undermining it, and AR-48-01's premise was re-verified against the file at
HEAD. (#5) No checkpoint took a DROP branch; every cited artifact exists, including the two most
easily doubted — `tests/n8n/researchErrorGateFlow.test.mjs` and the named refusal test at
`tests/test_enrich_coverage_companies.py:83`.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-03 | 38 | 38 (28 mitigation-verified, 10 accepted — 2 of those accepted by explicit operator decision this date) | 0 | `gsd-security-auditor`, VERIFY mode, L1 grep-and-read depth |

**Cross-check against the first pass.** This phase was audited twice, and the two runs **agree
entirely on the facts**: the same two threats, the same failure shape #3, the same evidence
citations. The headline verdict differs only because of disposition — the first pass returned
`OPEN_THREATS` (36/38, 2 open at high) before the operator's acceptance was applied; the second
returned `SECURED` (38/38) with those two closed as accepted. That is a bookkeeping consequence of
the operator's decision, not a disagreement about what happened. Three further divergences, all
recorded honestly:

| Item | First pass | This pass | Verdict |
|------|-----------|-----------|---------|
| Gate "failed closed on the first attempt" | asserted | **could not be confirmed as a runtime event** — see the caveat in the section above; closed on code plus test instead | diverge (material to the *evidence*, not to the disposition) |
| Phase commit count | 20 | **30** touching the phase dir, 31 in the range `f312f1d^..44f154e` | diverge (minor) — the substantive claim, zero package-manifest changes, holds across the *full* range |
| T-48-16 grep | "returned 0" | 0 **write** occurrences; the grep does return read-list and guard hits | diverge (phrasing) — same conclusion, load-bearing distinction |

**A caveat on the strength of the agreement, stated rather than implied.** The second auditor was
given the first pass's counts, the operator's approval and the distinctive findings in its prompt,
so agreement alone is weak evidence. To compensate, this record's author independently re-verified
five evidence cells against the repo before transcribing: the two-key gate at `:489-492`, the
`ValueError`-not-`assert` at `:441-445`, the disarm-in-`finally` block at `:838-850` (which quotes
D-48-01 verbatim), the waiver-precedes-act commit ancestry both ways, and the two arming flags at
HEAD. All five reproduced. The higher-signal half of this result is what the auditor reported
*against* its briefing — divergence 1 above.

**Audit depth, stated honestly.** `asvs_level: 1` — grep-and-read. Each mitigation was checked by
reading the cited file and line at current HEAD. Three checks went beyond L1 where it was cheap:
the pytest suite was run (43/43), the workflow builder was re-run in an isolated scratchpad copy
for a byte-diff against the committed JSON (8/8 identical, working tree confirmed untouched), and
git history/numstat was used as primary evidence for four threats. This is **not** an L2
boundary-placement review — the two unregistered-flag WARNINGS above are exactly what an L2 pass
would classify properly rather than merely surface.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter
- [x] T-48-11 and T-48-04(05) carried to the operator, **not** re-closed by the audit; accepted by
      operator decision on 2026-09-03 as AR-48-03 / AR-48-04
- [ ] Two unregistered low-severity surfaces (WARNINGS) await an operator disposition —
      non-blocking

**Approval:** verified 2026-09-03 at HEAD `8ffe359`
