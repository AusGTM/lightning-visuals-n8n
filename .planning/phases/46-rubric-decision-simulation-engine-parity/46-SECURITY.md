---
phase: "46"
slug: "rubric-decision-simulation-engine-parity"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (high).
# No threat was found OPEN by this audit. Three register-ACCURACY findings were raised
# (FINDING-1, FINDING-2, WARNING-2); none removes a control, and each carries a proposed
# disposition for the operator rather than a correction applied by the audit.
threats_open: 0
threats_open_below_threshold: 0
asvs_level: 1
created: "2026-09-03"
---

# Phase 46 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
>
> **Run retroactively on 2026-09-03**, as part of the cross-phase secure-phase sweep of phases
> 46–63. Phase 46 shipped without a SECURITY.md because the `verify:post` secure-phase hook was
> skipped — `workflow.security_enforcement` was absent from `.planning/config.json` and therefore
> **defaulted to enabled**. The key is now set explicitly.
>
> All five plans carry plan-time `<threat_model>` blocks (`register_authored_at_plan_time: true`),
> so this is a **verification pass, not retroactive-STRIDE**.
>
> Phase 46 belongs to the **archived v0.9 milestone**. Mitigations were verified at current HEAD
> (`8ffe359`), not at the phase's own close, and later phases have extended some of the cited
> code — drifted citations are recorded as drift, not as missing mitigations. See *Drift notes*.

---

## Trust Boundaries

Consolidated from the five PLAN threat models.

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| local process → HubSpot CRM v3 (46-01) | the simulation reads live company records; a coding error could reach a write endpoint or the wrong portal | company ids, scoring properties |
| repo config → scoring engines (46-01) | `config/icp_scoring.yaml` is the rubric of record; an unguarded divergence in any other engine is the split-brain class v0.7 already paid for | org-type weight table |
| local process → HubSpot CRM v3, full population (46-02) | live reads across the whole scored population — the largest live surface this phase touches | 66 company records |
| report artefact → operator decision (46-02) | the report drives a decision re-tiering more than half the scored list | three score columns per company, flags |
| decision record → future recalibration (46-03) | the only durable account of why these weights exist; a record editing its own evidence misleads with no detection path | evidence citations, override statements |
| operator sign-off → engine writes (46-03) | **the authorisation boundary** for every write in plans 04 and 05 | a signed acceptance of three weights |
| repo → HubSpot Automation v4 (46-04) | a PUT replaces a live flow definition wholesale; a malformed body silently drops actions from a flow scoring every company | full flow JSON, `isEnabled`, `revisionId` |
| config → derived engines (46-04) | any engine carrying a different value is the split-brain class | the same weight table, three mirrors |
| test suite → correctness claims (46-04) | a weakened assertion converts a real regression into a green build | assertion expected values |
| documentation → human decision-making (46-05) | other agents read `.planning/intel/*` and `CLAUDE.md` §10 as machine-readable rubric mirrors | weight values as prose |
| business evidence → future recalibration (46-05) | `docs/business/icp-scoring.md` is the closed-deal record the next revision reads; evidence edited to agree with a later decision is unrecoverable | win rate, sample size |
| scoped edit → planning ledger (46-05) | a wholesale rewrite of `ROADMAP.md` destroys phase entries outside the change window | roadmap phase entries |

---

## Threat Register

25 register rows across five plans — 20 numbered rows (16 **distinct** threats; see FINDING-1 on
the ID collision, and the continuation count below) plus 5 per-plan supply-chain entries.

### 46-01 — rubric decision foundations

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-46-01 | Tampering | `scripts/simulate_rubric_weights.py` | high | mitigate | Verified three ways at HEAD. `tests/test_simulate_rubric_weights.py:431` static source scan, `:448` import-namespace scan (catches the wildcard/alias case the text scan misses), `:461` behavioural stub asserting `calls == ids`. The write-name list is **self-updating** — `_write_capable_hubspot_client_names()` (`:413-418`) derives it by introspecting `src.hubspot_client` for functions carrying a `dry_run` parameter, pinned by `:421` to `[batch_update_companies, create_record, delete_record, patch_record]`. Suite green: 28 passed. Observed-failing-when-violated recorded at `46-01-SUMMARY.md:170-180` with the literal assertion text. | closed |
| T-46-02 | Tampering | portal targeting | medium | mitigate | `scripts/simulate_rubric_weights.py:80` `EXPECTED_PORTAL_ID = "22617666"`, no env override; `_portal_ok()` `:112`; refusal at `:498-501` **precedes** `_select_row_ids()` (`:504`, the only network call) and `build_simulation` (`:505`). | closed |
| T-46-03 | Tampering | rubric drift between engines | high | mitigate | `tests/test_n8n_org_type_absence.py:68/:81/:93` — no org-type weight table in `n8n/wf_*.json`, `scripts/build_cloud_workflows.py`, or `n8n/code/mergeCompanies.js`; the key list is derived from the rubric (`:41-44`), not hardcoded. New `defaultBranch` assertion at `tests/test_flow_rubric_conformance.py:155-178`. **Not vacuous** — a `-rs` run confirms 4 non-skipped cases against real flow archives. Register enumeration is incomplete: see WARNING-2 (third mirror). | closed |
| T-46-04 **(a)** | Information Disclosure | HubSpot private-app token | low | accept | Premise verified: `src/hubspot_client.py` dry-run branches print payload dicts only, never `hs_headers`/token (`:28-31`, `:49-53`, `:69-72`). The simulation's only credential contact is `bool(os.getenv(...))` at `:109` and a print of the **variable name** at `:495`. No new credential handling. → AR-46-01 | closed (accepted) |
| T-46-SC | Tampering | npm/pip/cargo installs | low | accept | Cited section exists: `46-RESEARCH.md:563 ## Package Legitimacy Audit`. Independently: `git log 55225e4~1..d66068e -- requirements.txt package.json` → **empty** across every phase-46 commit. → AR-46-02 | closed (accepted) |

### 46-02 — simulation expansion and live run

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-46-01 *(continuation)* | Tampering | live simulation run | high | mitigate | Same three tests, green at HEAD. "Remains green and unmodified" verified over plan 02's own window; see FINDING-3 for the later plan-04 edit, which did **not** touch the zero-write tests. No arming flag anywhere in the script. | closed |
| T-46-02 *(continuation)* | Tampering | portal targeting on the live run | medium | mitigate | Same guard, `:498-501`; halts (`return 1`, "No API call made") rather than proceeding. | closed |
| T-46-05 | Repudiation | report provenance | medium | mitigate | `46-SIMULATION-REPORT.md:3-5` — UTC `2026-08-11T07:59:01.631351+00:00`, Portal `22617666`, Rows `66`; `:11-14` carries the three literal overrides as applied. Rendered by `render_markdown`, pinned by `tests/test_simulate_rubric_weights.py:389`. | closed |
| T-46-06 | Information Disclosure | stale-snapshot substitution presented as live | medium | mitigate | **No fallback path exists.** `_select_row_ids` (`:226-248`) reads explicit ids → env → live `HAS_PROPERTY` search; it never reads `CROSS_CHECK_POPULATION_PATH`, whose only consumers are the name lookup (`:195-205`) and `_row_set_finding` (`:208-223`). The finding is **reported** at report `:6` (live=66, cross-check=66, symmetric difference=0) rather than silently reconciled. Credential/portal preconditions halt. | closed |
| T-46-SC | Tampering | npm/pip/cargo installs | low | accept | Same evidence. → AR-46-02 | closed (accepted) |

### 46-03 — decision record and blocking sign-off

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-46-04 **(b)** — **ID COLLISION**, see FINDING-1 | Repudiation | `46-DECISION.md` | high | mitigate | Structure verified: 10 `##` sections (`grep -c "^## " 39-DECISION.md` also returns 10 — the precedent matches; the register's "nine-section" label undercounts by one). Dated evidence index at `:393` with 12 artefacts and per-lever roles. Signed operator block at `:412`: decision, date 2026-08-11, an explicit "Substituted values (if override): None", what the operator was shown, and a provenance paragraph naming the relay channel. | closed |
| T-46-07 | Tampering | closed-deal evidence in `docs/business/icp-scoring.md` | high | mitigate | 19% / n=36 survives verbatim in three places: `:13` ("36 … 19%"), `:41` ("Club/Team 19% (n=36)"), `:59` ("19% win over 36 deals"). The GTM override is recorded **alongside**, not in place of: `:59` — "a deliberate GTM decision against the win-rate evidence above, not a data disagreement; the underlying finding is preserved verbatim, not softened." | closed |
| T-46-08 | Elevation of Privilege | weights reaching an engine without authorisation | high | mitigate | `46-03-PLAN.md:185` `<task type="checkpoint:human-verify" gate="blocking">`, acceptance criterion at `:204` (`git diff config/icp_scoring.yaml config/hubspot_flows/` empty at resume), `<resume-signal>` at `:244-251`. **Independently proven rather than taken on the record's word:** `git merge-base --is-ancestor c95fdf6 caae5d6` → true. Sign-off (`c95fdf6`, "record operator sign-off — accept all three rubric weights") strictly precedes the engine write (`caae5d6`, "land signed-off rubric weights"). Re-verified by this record's author, independently of the auditor. The row's `depends_on` literal is inaccurate — see FINDING-2; the control itself is intact and gates transitively. | closed |
| T-46-SC | Tampering | npm/pip/cargo installs | low | accept | Same evidence. → AR-46-02 | closed (accepted) |

### 46-04 — weight commit and live flow PUT

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-46-09 | Tampering | HubSpot flow PUT (replace-not-merge) | high | mitigate | `scripts/put_hubspot_flow.py:54` `STRIP_KEYS`; `load_flow_body` `:74-79` **refuses** a poisoned body rather than silently stripping it. `--disable`/`--enable` at `:127-128` implement the PORTAL-FACTS protocol. Pre-PUT archives exist on disk (`4626124224-org-type-score.46-04-pre-put.json`, `4634822085-gambling-score.46-04-pre-put.json`) and were committed in `5643dda`, **before** the PUT commit `4f7c395`. **Diffed independently this audit** — pre→post shows exactly `"5"→"15"`, `"5"→"-20"`, `revisionId 24→26` on the org-type flow and `"-20"→"0"`, `revisionId 2→4` on the gambling flow. Nothing else changed; no action dropped. | closed |
| T-46-10 | Spoofing | PUT targeted at the wrong portal or flow id | high | mitigate | Present in **both** flow scripts as the register claims: `put_hubspot_flow.py:49/:61/:139-142` and `fetch_hubspot_flow.py:39/:71/:118-120`, each refusing before any call. `--flow-id` is `required=True` (`put_hubspot_flow.py:125`). | closed |
| T-46-11 | Elevation of Privilege | flow write fired without deliberate arming | high | mitigate | `_writes_allowed()` `:65-68` — `DRY_RUN` defaults `"true"`, `ALLOW_HUBSPOT_FLOW_WRITE` defaults `"false"`; both keys required. Gate at `:144-147`. Default-deny on both axes. **Exercised under real arming** (`46-04-SUMMARY.md` § Issues Encountered): four armed PUTs executed cleanly; the gate held rather than being merely untested. | closed |
| T-46-03 *(continuation)* | Tampering | rubric drift between config and flows | high | mitigate | `test_org_type_flow_matches_rubric` (`tests/test_flow_rubric_conformance.py:128`) is genuinely self-updating — it reads `load_rubric()["base_score"]["org_type"]` at `:140` and compares branch-by-branch. The rewritten gambling test at `:209` asserts the key's **absence** from the rubric (`:224`) and both branches at 0. Three mirrors independently confirmed to agree: `config/icp_scoring.yaml` (club 15, regulator −20, `graduated_deductions: {}`), `config/taxonomy.yaml:86/:100` (15 / −20), and the post-PUT flow archive. | closed |
| T-46-12 | Repudiation | false green from a stored-only read-back | medium | mitigate | `46-04-SUMMARY.md:72` records the running-content GET **after** re-enable, with `revisionId 26` / `revisionId 4` and `isEnabled=true` on both flows — matching the committed archives' revisionIds exactly (verified above). The `<human-check>` rationale at `:75` explicitly refuses script-derived proof. Consistent with the standing repo rule that a bare PUT never reloads running content. | closed |
| T-46-SC | Tampering | npm/pip/cargo installs | low | accept | Same evidence. → AR-46-02 | closed (accepted) |

### 46-05 — documentation sync

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-46-07 *(continuation)* | Tampering | closed-deal evidence | high | mitigate | Same three sites verified verbatim at HEAD **after** the plan-05 doc sync (`db7440d` touched this file). | closed |
| T-46-13 | Tampering | archived milestone artefacts | high | mitigate | Stronger than the declared `git status` criterion: **no plan-05 commit touches `.planning/milestones/` at all.** File scopes — `db7440d` (5 files: intel ×2, `CLAUDE.md`, `WEB-RESEARCH-SPEC`, `icp-scoring`), `4484994` (`REQUIREMENTS`, `ROADMAP`), `53d50d1` (`SUMMARY`), `d66068e` (`ROADMAP`, `STATE`). `git status --porcelain .planning/milestones/` clean at HEAD. | closed |
| T-46-14 | Tampering | `ROADMAP.md` collateral loss from a wholesale write | medium | mitigate | `git show --stat 4484994` → `.planning/ROADMAP.md | 23 +++…` — **23 insertions, 0 deletions**, a pure append, matching `46-05-SUMMARY.md:76`. The second ROADMAP touch `d66068e` is 4 ins / 3 del, confined to the Phase 46 block (`@@ -109`, `@@ -119` "Plans: 4/5 → 5/5", `@@ -134` plan-05 checkbox) in a 73 KB file. | closed |
| T-46-15 | Repudiation | regulator deduction described as a graduated-deductions entry | medium | mitigate | The exact negative assertion exists in text: `docs/business/icp-scoring.md:81` — "Regulator carries a direct org-type weight of –20 (`46-DECISION.md` D-02) — **not a graduated deduction**." Corroborated by `.planning/intel/constraints.md:46` (`regulator:-20` under `base_score org_type`; `graduated_deductions {} (empty)`), `.planning/intel/requirements.md:13`, `CLAUDE.md:802`. A repo-wide grep for regulator-within-graduated returns no conflation. | closed |
| T-46-SC | Tampering | npm/pip/cargo installs | low | accept | Same evidence. → AR-46-02 | closed (accepted) |

*Status: open · closed · closed (accepted)*
*Severity: critical > high > medium > low — only open threats at or above `security_block_on` (`high`) count toward `threats_open`*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-46-01 | T-46-04 (a) | The simulation introduces no new credential handling: it tests only `bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))` and prints the variable **name**, never the value. The reused `src/hubspot_client.py` dry-run branches print payload dicts only, never `hs_headers`/token. | plan-time disposition, premise re-verified this audit | 2026-09-03 |
| AR-46-02 | T-46-SC ×5 (one per plan) | No plan in this phase installs a package or adds a dependency, so no package legitimacy audit is required. The cited section `46-RESEARCH.md:563 § Package Legitimacy Audit` exists; independently, no phase-46 commit (`55225e4~1..d66068e`) touches `requirements.txt` or `package.json`. | plan-time disposition, premise re-verified this audit | 2026-09-03 |

---

## Findings — register accuracy

Surfaced rather than smoothed. **None of these removes a control and none changes a status.** Each
carries a *proposed* disposition; per the sweep's standing rule, neither the auditor nor this
record's author may self-author a corrected rationale — the operator grants it.

**FINDING-1 — `T-46-04` is a genuine ID collision, not a continuation.** Plan 01's row is
*Information Disclosure / low / accept* (HubSpot token). Plan 03's row is *Repudiation / high /
mitigate* (`46-DECISION.md`). Two unrelated threats share one ID across a phase whose register is
meant to read as a whole. Both are independently closed. **Proposed disposition:** re-key plan
03's row (e.g. `T-46-16`) in this register, with a note that the PLAN text retains the original
ID. *Confirms the first pass.*

**FINDING-2 — `T-46-08`'s literal claim is false as written.** The row states "Plans 04 and 05
declare `depends_on: [46-03]`". Actual frontmatter, re-read independently by this record's author:
`46-04-PLAN.md:6` → `depends_on: [46-03]` ✓; `46-05-PLAN.md:6` → **`depends_on: [46-04]`**, not
`[46-03]`. The authorisation ordering still holds transitively (05 → 04 → 03) and is independently
proven by `c95fdf6` being an ancestor of `caae5d6`, so the control is intact — but the register
asserts a declaration that does not exist on the path it names. This is **failure shape #1 in its
mildest form**: a *claim* about a path, not a control, that never existed. **Proposed
disposition:** correct the row text to "46-04 declares `depends_on: [46-03]`; 46-05 declares
`[46-04]`, gating transitively", closed on the ancestry proof. *New — not reported by the first
pass.*

**FINDING-3 — plan 02's "remains green and unmodified" was later falsified at file level, but not
at control level.** `tests/test_simulate_rubric_weights.py` **was** rewritten in plan 04's
`caae5d6` (`46-04-SUMMARY.md` § Deviations, item 2): `CURRENT_CFG` loads
`config/icp_scoring.yaml` at import time, so landing the weights collapsed roughly a dozen
before/after assertions, fixed by adding `PRE_PHASE_46_CFG`. **Verified this audit that the
zero-write tests themselves survived untouched** — `git diff caae5d6~1 caae5d6 --
tests/test_simulate_rubric_weights.py` shows no line matching `zero_write` or `write_capable`; the
only assertion change is `individual_club_team == 5` → `== 15`. Plan 02's claim was therefore true
in its own window and the T-46-01 control is unweakened. Recorded because *"the declared mitigation
is not the code that ran"* (**failure shape #3**) is exactly the shape a later same-phase rewrite
can produce, and here it came close.

**WARNING-2 — `config/taxonomy.yaml` is a third mirror of the org-type score table that no
phase-46 planning document enumerates.** This is **failure shape #4** — surface inside T-46-03's
own declared trust boundary ("config → derived engines"), never registered. Per `46-04-SUMMARY.md`
Deviation 1, neither `46-RESEARCH.md` nor `46-ENGINE-INVENTORY.md` names this file; editing
`icp_scoring.yaml` and the flow left `taxonomy.yaml` stale at 5/5, and the drift was caught by
**`tests/test_taxonomy_conformance.py:49 test_tx1_scores_match`** — a pre-existing guard that
appears in **no** T-46-03 mitigation cell. Verified at HEAD, independently re-read by this record's
author: `config/taxonomy.yaml:86` `score: 15`, `:100` `score: -20`; `test_tx1_scores_match` passes.
Confirmed via `scripts/gen_taxonomy_js.py` (`46-04-SUMMARY.md`) that `score:` never reaches
generated n8n JS, so `46-ENGINE-INVENTORY.md`'s "two engines" finding survives — this is a third
*mirror*, not a third computing engine. The threat is guarded; the register's *enumeration* was
incomplete. **Proposed disposition:** amend T-46-03's mitigation to name `test_tx1_scores_match`
as the third-mirror guard and state the mirror count as three. Does **not** warrant OPEN — every
mirror is guarded and green. *New — not reported by the first pass.*

**Failure shapes verified NOT present.**

- **#2 (an acceptance whose premise a later plan in the same phase destroyed):** both accept
  premises were re-tested at HEAD across the full phase range and are intact — no dependency
  commit, no new credential handling.
- **#5 (a mitigation citing an artifact never built because a checkpoint took its DROP branch):**
  46-03's blocking checkpoint took the **ACCEPT** branch ("Accepted — Accept all three
  (Recommended)", `46-DECISION.md:414`). Every artifact cited downstream exists on disk:
  `46-DECISION.md`, `46-SIMULATION-REPORT.md`, both pre-PUT archives, both `.after.json`
  re-archives.

**Threat-flag coverage.** No `46-0*-SUMMARY.md` carries a `## Threat Flags` section — that heading
exists nowhere in this phase, whose v0.9-era template predates it. The auditor substituted a read
of each summary's *Deviations from Plan* section as the equivalent surface, which is precisely
where `taxonomy.yaml` (WARNING-2) surfaced. **Unregistered flags: 1** (`config/taxonomy.yaml`),
non-blocking.

---

## Drift notes — cited line moved, control intact

These are **not** missing mitigations.

- The 46-05 amendment greps return **0 / 0** against root `.planning/REQUIREMENTS.md` and
  `.planning/ROADMAP.md` because v0.9 was archived (`48c037b chore: archive v0.9 milestone`).
  Reproducing `46-05-SUMMARY.md:73`'s exact recorded command against the archive —
  `grep -c '46-ENGINE-INVENTORY.md' .planning/milestones/v0.9-REQUIREMENTS.md
  .planning/milestones/v0.9-ROADMAP.md` → **2 and 3**, byte-matching the recorded counts.
  Independently re-run by this record's author.
- `scripts/put_hubspot_flow.py` gained a Phase-50 `--delete` path (`:105`, `:129-131`, `:149-152`)
  **after** the audit window. It sits behind the same two-key gate and portal guard; T-46-09/10/11
  are unaffected.
- `docs/OPERATOR-RESCORE.md:185` states "`regulator` 0→−20"; the pre-value was **5** (proven by the
  pre-PUT archive diff). A later-phase document outside this register — flagged, not scored.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-03 | 25 | 25 (19 mitigation-verified, 6 accepted) | 0 | `gsd-security-auditor`, VERIFY mode, L1 grep-and-read depth |

**Cross-check against the first pass.** This phase was audited twice. The two runs agree on the
verdict, the row count and the split (25/25, 19 + 6), on the `T-46-04` ID collision, on the drifted
amendment-note locations, and on `c95fdf6` preceding `caae5d6`. Two divergences are recorded
honestly:

| Item | First pass | This pass | Verdict |
|------|-----------|-----------|---------|
| "Five rows are continuations" | 5 | **4** — plan 02's T-46-01 and T-46-02, plan 04's T-46-03, plan 05's T-46-07. Arithmetic: 20 non-SC rows − 16 distinct threats = 4 repeats; the fifth repeated row is the `T-46-04` **collision**, a different threat rather than a continuation. | diverge (minor, arithmetic) |
| `config/taxonomy.yaml` third mirror | not reported | WARNING-2 | new |
| `T-46-08` `depends_on` claim | not reported | FINDING-2 | new |

**A caveat on the strength of that agreement, stated rather than implied.** The second auditor was
given the first pass's expected counts and distinctive findings in its prompt, so count-agreement
alone is weak evidence. To compensate, this record's author independently re-verified four evidence
cells against the repo before transcribing: the `c95fdf6`→`caae5d6` ancestry
(`git merge-base --is-ancestor` → true), both PLAN `depends_on` literals (FINDING-2), the
`taxonomy.yaml` score values (WARNING-2), and both grep-count pairs for the drifted amendment
notes. All four reproduced exactly. The two *new* findings, raised despite the auditor knowing the
first pass's target, are the higher-signal half of this result.

**Audit depth, stated honestly.** `asvs_level: 1` — grep-and-read. Each mitigation was located at
its cited file and line at HEAD and, where the control is a test, executed:
`tests/test_simulate_rubric_weights.py` + `tests/test_n8n_org_type_absence.py` (28 passed),
`tests/test_flow_rubric_conformance.py` (24 passed, 112 skipped — with `-rs` used to confirm the
org-type and gambling assertions are non-vacuous), `test_tx1_scores_match` (1 passed). Four claims
were verified **independently of the phase's own summaries** rather than at L1 depth: the
pre/post-PUT archive diff, the commit ancestry, the plan-05 commit file scopes, and the `caae5d6`
diff of the zero-write tests. This is **not** an L2 boundary-placement review — for example,
`build_simulation`/`main()` remain callable as a library, bypassing `cli_main`'s portal guard (the
guard sits on the operator entry point, which is what the register declares). Confirming that
closes would need `security_asvs_level: 2` and a re-run.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter
- [ ] FINDING-1, FINDING-2 and WARNING-2 carry **proposed** register corrections awaiting operator
      disposition — non-blocking, no control is absent

**Approval:** verified 2026-09-03 at HEAD `8ffe359`
