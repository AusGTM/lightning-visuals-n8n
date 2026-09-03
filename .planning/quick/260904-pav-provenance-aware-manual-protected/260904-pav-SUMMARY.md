---
quick_id: 260904-pav
type: execute
status: complete
subsystem: n8n-merge-engines
tags: [manual-protected, provenance, create-seed, non-clobber, parity, domain]

requires:
  - n8n/code/mergeCompanies.js (_gate's manual_protected branch, the domain hard guard)
  - src/merge_policy.py (deterministic_gate, has_conflict)
  - scripts/build_cloud_workflows.py (ENRICH_MERGE_CO's `conflicts`, ENRICH_DECIDE_CO_CLOUD's create branch)
  - n8n/code/reviewDecision.js (buildHumanProvenance — the additive spread order this one matches)
provides:
  - "config/field_policy.yaml `system_correctable_sources` — a per-field allowlist of provenance sources whose value the merge engines may correct despite manual_protected"
  - "mergeCompanies(existing, candidate, policy, {rowConflicted}) — the caller's row-level conflict statement, read only by the correction path, `=== false` strictly"
  - "provenance source `create_seed` + validation_status `request_echo` (CLAUDE.md §6.1)"
  - "an ADDITIVE lv_enrichment_provenance write on the enrichment lane"
affects:
  - CLAUDE.md §6.1 (vocabulary) and §17.2 / new §17.2.1 (the PROMOTE clause, now implemented)
  - tests/fixtures/companies_jscode_frozen.json (re-baselined twice, Merge Company only)

tech-stack:
  added: []          # no package installed, no dependency touched
  patterns:
    - "fail-closed conjunctive gate: four independent conjuncts, each asserted to refuse on its own"
    - "structural flag over string match: the domain hard guard tests `gate.correction`, never the reason text"
    - "no permissive default for a safety flag: `rowConflicted === false` strictly, so an un-migrated caller refuses"
    - "build the outgoing blob once, serialize once, AFTER every writer has had its turn"
    - "declared divergence: the two engines take different conflict inputs, commented in place rather than faked into a shared one"

key-files:
  created:
    - tests/n8n/decideCompanyActionCreateSeedProvenance.test.mjs
    - .planning/todos/pending/2026-09-04-company-domain-has-no-candidate-source.md
  modified:
    - n8n/code/mergeCompanies.js
    - src/merge_policy.py
    - config/field_policy.yaml
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - tests/n8n/mergeCompanies.test.mjs
    - tests/n8n/parity.test.mjs
    - tests/test_merge_policy.py
    - tests/test_field_policy_conformance.py
    - tests/fixtures/companies_jscode_frozen.json
    - CLAUDE.md
    - .planning/todos/completed/2026-09-04-provenance-aware-manual-protected.md

decisions:
  - "system_correctable_sources = [\"create_seed\"], exactly one member: every other source's `domain` provenance entry is a STAGED REFUSAL, so admitting waterfall/claude_web/hubspot_native/june_2026 would let a refused candidate authorise its own promotion next run."
  - "The confidence bar is the field's existing min_confidence (95) and no new key — the check sits inside the manual_protected branch, which the gate only reaches after its own confidence test."
  - "rowConflicted has NO permissive default in JS: `=== false` strictly. A default of false would be fail-OPEN on the franchisor guard for any caller that omits the flag, including this repo between Task 1's and Task 2's commits."
  - "The two engines take DIFFERENT conflict inputs on purpose (JS: opts.rowConflicted from the wrapper's row-level set; Python: its own has_conflict(candidates)) — commented in both, pinned by a parity table, not faked into a shared input."
  - "The create seed is `source: create_seed`, `validation_status: request_echo`, `confidence: 0` — an identity echo of the caller's own request must never read as evidence."
  - "The provenance blob write is now additive with THIS RUN winning on collision, matching reviewDecision.js's buildHumanProvenance so the two additive writers agree."

metrics:
  duration: ~75 min
  completed: 2026-09-04

actuals:
  tokens: 7800     # chars/4 over the realized diff (31,227 chars), EXCLUDING the
                   # regenerated n8n/wf_*.json and the frozen jsCode fixture — machine
                   # output, not authored work
  tasks: 3
  commits: 5
---

# Quick Task 260904-pav: Provenance-aware manual_protected Summary

`manual_protected` now asks WHO wrote the existing value before refusing, so a company
`domain` the enrichment system parked itself can be corrected by the system's own later,
better answer — while a human-curated value stays protected exactly as today.

## What shipped

**Task 1 — the correction path, both engines, one commit (`0610243`).**
CLAUDE.md §17.2's PROMOTE clause *"existing value was previously written by the enrichment
system and the new candidate has higher confidence"* had sat in the spec unimplemented.
It is now implemented in `n8n/code/mergeCompanies.js` and `src/merge_policy.py`, gated on a
new per-field policy key `system_correctable_sources` (`["create_seed"]` on
`companies.domain`, absent everywhere else — an absent key means today's behaviour).

Four conjuncts, ALL required, each asserted to refuse independently:

1. the field's policy carries a non-empty `system_correctable_sources` and the existing
   value's provenance entry names a source on it;
2. the entry's recorded `value` is STILL the record's current value;
3. no material conflict (`opts.rowConflicted === false` strictly in JS;
   `has_conflict(candidates)` in the Python oracle);
4. the field's own `min_confidence` — 95 for `domain`, the highest in the policy, reached
   with no new threshold key because the check sits inside the `manual_protected` branch.

The `domain` hard guard (a second refusal seam the source todo did not name, which would
have re-refused every correction) now tests a structural `gate.correction` flag rather than
a reason string. Every other `domain` promote still demotes.

**Task 2 — the seed and the blob (`23f5c2e`).**
`ENRICH_DECIDE_CO_CLOUD`'s create branch now stamps
`{source: "create_seed", validation_status: "request_echo", confidence: 0, value, verified_at}`
for the domain it seeds, so the correction path has something to key on. And the lane's
provenance write is now ADDITIVE — it previously REPLACED the blob with this run's
`merge.provenance`, which only ever carries this run's candidate fields, so the first
enrich after a create wiped the seed *and* every other untouched field's entry. That is a
latent loss this repairs for every field, not just `domain`. `Merge Company` passes
`rowConflicted: conflicts.length > 0` on the waterfall fold — the same array the wrapper
already computed, and the only call whose field allowlist includes `domain`.

**Task 3 — parity, vocabulary, and the open seam (`e6c3a79`).**
A seven-row genuine JS↔Python parity table; `request_echo` added to CLAUDE.md §6.1; a new
§17.2.1 recording the clause as implemented, in one place, and stating plainly that "higher
confidence" alone is not the rule.

## Value-match is load-bearing (planning finding 2, confirmed)

Both engines write a provenance entry for EVERY field before the promote branch — so a
*refused* candidate still leaves an entry whose `value` is the refused candidate. Conjunct 2
is therefore not only a guard against a human retyping the value; it is what stops a refused
candidate authorising its own promotion on the next run. Asserted in both suites.

## What did NOT land — the mechanism is INERT today

Nothing in the pipeline can propose a company `domain`. No `normalizeProviders.js` branch
pushes one; the Claude-web research fold answers only ICP fields; and the company providers
are looked up BY the record's domain (ZoomInfo `matchCompanyInput:
[{companyWebsite|companyName}]`, Lusha `?domain=`) so they structurally cannot contradict
it. The live Brisbane Lions record `285583534546` stays stuck, and its `@lions.com.au`
contacts stay held as `email_domain_mismatch`.

Recorded as `.planning/todos/pending/2026-09-04-company-domain-has-no-candidate-source.md`
rather than closed with a guessed source — adding one is new enrichment surface whose
provider payload keys cannot be confirmed without live calls this task forbade. That todo
also carries a second decision the first real candidate will force (under this-run-wins on
the now-additive blob, a REFUSED domain candidate overwrites the `create_seed` entry and
permanently closes the correction path for that record) and a precondition to check before
either (if HubSpot normalizes `domain` on write, the stored value diverges from the seeded
one and conjunct 2 refuses that record forever — fails closed, but keeps the mechanism
inert; unverifiable offline).

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 3 - Blocking] `tests/fixtures/companies_jscode_frozen.json` re-baselined, twice**
- **Found during:** Tasks 1 and 2, at the full-suite run.
- **Issue:** `tests/test_companies_factory_frozen.py` is a byte-identity guard over seven
  companies Code nodes, re-baselined "ONLY by an explicit, reviewed act". Editing
  `mergeCompanies.js` (Task 1) and `ENRICH_MERGE_CO` (Task 2) legitimately changes the
  `Merge Company` jsCode that `inline()` concatenates, so the guard failed both times. The
  plan did not name this file.
- **Fix:** re-baselined in each task's own commit, following the c671ebf precedent
  (explicit, stated on the record). Exactly two entries changed each time —
  `cloud/Merge Company` and `local_live/Merge Company`; the other six frozen nodes stayed
  byte-identical, and no assertion in the test file was added, removed or reworded.
- **Commits:** `0610243`, `23f5c2e`.

**2. [Rule 2 - Missing critical] a conformance assertion for the new policy key**
- **Found during:** Task 1, checking whether a YAML↔JS policy parity test existed.
- **Issue:** `tests/test_field_policy_conformance.py` guards `class` and `min_confidence`
  across the two hand-mirrored policy tables but would not have noticed a drift on
  `system_correctable_sources` — the key that decides whether a protected field is
  correctable at all. A silent fork there means one engine correcting a value the other
  still protects.
- **Fix:** one assertion, compared both directions (a key present on only one side is
  itself the drift).
- **Commit:** `0610243`.

**3. Test-shape adjustments (no production impact)**
- The "no `system_correctable_sources` key" JS case originally used `industry`; the enum
  guard staged it for its own unrelated reason, which would have made the test pass
  vacuously. Switched to a synthetic field name.
- The `rowConflicted` wiring is asserted on the emitted `Merge Company` source, not
  behaviourally: the waterfall fold merges at a flat confidence of 85 and `domain` demands
  95, so no input can produce a different decision today. The test says so in place.

### Out of scope, noted not chased

- **`ENRICH_DECIDE_CO_LOCAL`'s dry-run echo** reports `row.merge.provenance` rather than the
  outgoing blob, so its echo will not show the seed entry. It writes nothing to HubSpot.
- **The research lane's `existingRecord`** may be stripped by HTTP hops (memory
  `companies-research-lane-rowloss`). Where it is, the additive spread sees `{}` and
  replaces exactly as today — so the seed survives non-research enrich runs and possibly
  not research ones. Finding 6 is closed on the lanes that carry `existingRecord`, not
  provably on every path.
- **`n8n/code/mergeContacts.js`'s identical `manual_protected` branch** is unreachable (no
  contact field carries the class after 260826-20w) and was left alone, per the todo's
  grounding finding 3.

## Consumers checked before making the blob additive

- **`judge.js::isIndependentPrior`** reads `source`, and treats a MISSING entry as an
  independent legacy prior — so a surviving entry can only ever flip a prior from
  independent to NOT independent, i.e. tighten the D1 self-confirmation guard. Its
  recency/accuracy reads take the entry's own `verified_at`/`confidence`, now accurate
  where they previously fell back to null. No consumer treats mere PRESENCE as "this run
  wrote it".
- **`n8n/code/reviewDecision.js::buildHumanProvenance`** spreads existing entries first and
  its own over them — the same collision order this lane now uses, so the two additive
  writers agree.
- **The operator plugin** does not render the blob (`review_queue.py`) and only
  echo-verifies it (`review_decision.py`). Untouched by this task; `plugin.json` not bumped.

## Threat mitigations applied

| Threat ID | Mitigation as landed |
|-----------|----------------------|
| T-PAV-01 | Four conjuncts; each asserted to refuse on its own in both suites. |
| T-PAV-02 | Value-match conjunct denies a refused candidate's own leftover entry. |
| T-PAV-03 | `create_seed` + `confidence: 0` + `request_echo`; the seed can only ever authorise replacing ITSELF. |
| T-PAV-04 | `rowConflicted` reuses the existing size-conflict franchise detector; no permissive default. |
| T-PAV-05 | try/catch → `{}` in both engines and in the wrapper; asserted not to throw. |
| T-PAV-06 | Accepted: additive is strictly more audit information than a destructive replace. |
| T-PAV-SC | No package installs; none attempted. |

## Verification

Zero live HubSpot calls, zero provider credits, zero n8n executions, nothing armed. The
regenerated `n8n/*.json` is committed UNDEPLOYED — the running instance does not have it
(CLAUDE.md §13.0.2's pattern; it was already ahead of live before this task).

| Suite | Baseline | After |
|-------|----------|-------|
| root `pytest -q` | 4178 passed / 154 skipped | **4187 passed / 154 skipped** (+9) |
| `node --test tests/n8n/*.test.mjs` | 870 pass / 0 fail | **894 pass / 0 fail** (+24) |
| plugin `pytest -q` | 2430 passed / 5 skipped | **2430 passed / 5 skipped** (unchanged) |

RED was observed and recorded before each engine edit: Task 1 failed exactly one assertion
per suite (the correction case — every refusal case already passed, which is the right RED
signature for a branch that refuses unconditionally today); Task 2 failed exactly three of
eight.

## Commits

| Commit | What |
|--------|------|
| `4912aa5` | test: RED for the provenance-aware gate, both engines |
| `0610243` | feat: the correction path in both engines + policy key + conformance assertion + regenerated JSON |
| `8c10f7d` | test: RED for the create seed and the additive blob |
| `23f5c2e` | feat: the create seed, the additive blob, `rowConflicted` wiring + regenerated JSON |
| `e6c3a79` | docs: parity table, `request_echo` vocabulary, §17.2.1, the new todo, the old todo closed |

## Self-Check: PASSED

- `n8n/code/mergeCompanies.js`, `src/merge_policy.py`, `config/field_policy.yaml`,
  `scripts/build_cloud_workflows.py`, `tests/n8n/decideCompanyActionCreateSeedProvenance.test.mjs`,
  `.planning/todos/pending/2026-09-04-company-domain-has-no-candidate-source.md`,
  `.planning/todos/completed/2026-09-04-provenance-aware-manual-protected.md` — all present.
- Commits `4912aa5`, `0610243`, `8c10f7d`, `23f5c2e`, `e6c3a79` — all in `git log`.
- All three suites green at or above baseline (table above).
