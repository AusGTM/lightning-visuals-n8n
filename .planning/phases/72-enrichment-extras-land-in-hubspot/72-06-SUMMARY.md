---
phase: 72-enrichment-extras-land-in-hubspot
plan: 06
subsystem: enrichment-merge-engine
tags: [n8n, hubspot, merge-policy, normalizeProviders, field-policy, geo]

requires:
  - phase: 72-enrichment-extras-land-in-hubspot
    provides: "plan 05's closed overflow-slot map (_overflowSlot()/opts.rankedByField) and 72-PORTAL-PROBE.json's live verdicts for hs_additional_domains/hs_country_region_code"
provides:
  - "Company state/hs_state_code/phone producers on the Lusha and Apollo company branches of normalizeProviders.js, each backed by named live evidence"
  - "Explicit fill_blank_only@80 field_policy.yaml/DEFAULT_COMPANY_POLICY entries for companies.state/hs_state_code/phone"
  - "Merge Company's candidate loop admits state/hs_state_code (raw-value loop) and phone (opts.rankedByField, routing the runner-up to lv_phone_2)"
  - "A permanent regression guard proving contact-shaped geo can never reach the company's lv_country_region_normalized (D-72-16)"
affects: ["72-08 (deploy/bounce scope for this phase's ingest lane; these companies-lane changes ship in wf_enrichment_cloud.json alongside it)"]

actuals:
  tokens: 554914
  tasks: 3
  commits: 6
  # measured as chars/4 over `git diff 9091f706..HEAD` (9091f706 = last commit before this
  # plan's Task 1). Same measurement-artifact caveat plan 05's SUMMARY recorded: n8n stores
  # each Code node's jsCode as one JSON string with escaped \n, so a single-character change
  # inside Merge Company's large embedded script makes git diff print the whole multi-KB
  # line as removed+added. The line-level diff (`git diff --stat`: 468 insertions / 26
  # deletions across 15 files) reflects the actual size of the change; this plan's own
  # estimate (120,000 tokens, confidence: low) anticipated exactly this kind of miss.
  plan_head_before: 9091f7065ae9f0705242dc86cc39276d8c30ca48

tech-stack:
  added: []
  patterns:
    - "Per-field evidence gate before writing a producer: a nine-cell (3 providers x state/code/phone) table, each cell either cited evidence (documented contract + live-captured JSON) or 'no producer', checked by an automated verify that the code and the table agree."
    - "NEVER_CHASE exemption set (tests/n8n/fieldProducerMatrix.test.mjs) as the mechanism for a producer-having, promotable field that must stay off the REQUIRED chase list -- write-map admission and REQUIRED-list chasing are deliberately different questions."

key-files:
  created: []
  modified:
    - n8n/code/normalizeProviders.js
    - n8n/code/mergeCompanies.js
    - config/field_policy.yaml
    - operator-claude-plugin/config/field_policy.yaml
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - tests/fixtures/companies_jscode_frozen.json
    - tests/n8n/normalizeProviders.test.mjs
    - tests/n8n/mergeCompanies.test.mjs
    - tests/n8n/enrichment.test.mjs
    - tests/n8n/fieldProducerMatrix.test.mjs

key-decisions:
  - "Per-cell evidence table (see below) decided the shape: Lusha and Apollo both get state (raw name) + a guarded, code-shaped-only hs_state_code (never observed to fire, structurally identical to the contacts branches' existing rule); Apollo alone gets phone; ZoomInfo gets none of the three (ZOOM_CO_OUTPUT_FIELDS requests neither field, mirroring 58-05's `city` precedent)."
  - "hs_country_region_code is out of scope entirely for companies -- 72-PORTAL-PROBE.json confirmed the property does not exist (404). Pre-authorized by the plan text itself (\"if the probe says absent... scope the company half of D-72-15 to state/hs_state_code\"), so this needed no operator ruling."
  - "hs_additional_domains stays an accepted no-producer gap: no provider branch of normalizeProviders.js pushes a company `domain` candidate at all (pre-existing, documented gap, CLAUDE.md §17.2.1 / the open todo), so an overflow slot for a second domain has nothing to route -- the property's existence/writability (confirmed by plan 05's probe) is necessary but not sufficient."
  - "Corrected a false plan-time assumption: Task 2's text says \"companies.phone already exists\" as a field_policy.yaml entry. Verified it does not (checked config/field_policy.yaml, operator-claude-plugin's copy, and DEFAULT_COMPANY_POLICY -- none had a `phone` key under `companies:`). `phone` IS a genuine, existing, writable native HubSpot company property (confirmed by 72-RESEARCH.md's live property-export citation and 72-CONTEXT.md's live portal read) -- the plan's confusion was between the HubSpot schema property and a merge-policy entry for it. Added fresh with the same shape as the other two new entries; a Rule 1 correction, not an architectural change, so no checkpoint was raised."
  - "phone is admitted to Merge Company's write map via opts.rankedByField ONLY, not the raw-value loop -- the engine's own `candidateRow[field] == null` fallback assigns the trust-rank winner from the ranked list, and the same pass routes the runner-up to lv_phone_2 (Phase 72 Plan 05's overflow map). Adding phone to the raw-value loop too would be redundant, not wrong, so it was left out to keep each field's admission path singular."
  - "state/hs_state_code/phone were added to tests/n8n/fieldProducerMatrix.test.mjs's pre-existing NEVER_CHASE exemption set rather than to ENRICH_CO_GATE's REQUIRED list -- that test's own \"chase gate\" assertion (every producer-having, promotable, non-recomputed policy key must be REQUIRED) would otherwise have failed, since these three now have real producers. The plan explicitly forbids widening REQUIRED (T-72-09); NEVER_CHASE is the pre-built mechanism for exactly this situation (already used for contacts.hs_linkedin_url)."
  - "Task 3's guard test cannot naturally go RED under the current engine (mergeCompanies() never derives lv_country_region_normalized from anything -- it only writes whichever candidateRow key it is handed). RED evidence was captured by temporarily injecting a fake derivation, observing the test fail with the D-72-16 message, then reverting byte-for-byte (confirmed via `git diff --stat` showing no change before the real commit)."

requirements-completed: [D-72-14, D-72-15, D-72-16]

coverage:
  - id: D1
    description: "Company state/hs_state_code/phone producers exist for exactly the fields a real provider response carries (Lusha: state; Apollo: state+phone; both guarded for hs_state_code; ZoomInfo: none), with every absence documented in-file and the two pre-existing lv_country_region_normalized pushes unchanged."
    requirement: "D-72-15"
    verification:
      - kind: unit
        ref: "tests/n8n/normalizeProviders.test.mjs (20 tests: 5 new-behavior, RED-then-GREEN; 15 absence/negative)"
        status: pass
      - kind: unit
        ref: "tests/n8n/enrichment.test.mjs (2 pre-existing field-set pins updated to include `state`, expected consequence)"
        status: pass
      - kind: other
        ref: "REGION_PUSHES==2 regex check (n8n/code/normalizeProviders.js); hs_state_code grep agreement check"
        status: pass
    human_judgment: false
  - id: D2
    description: "Companies gain explicit fill_blank_only@80 policy for state/hs_state_code/phone (both field_policy.yaml copies + DEFAULT_COMPANY_POLICY, byte-identical), Merge Company's write map admits all three (state/hs_state_code via the raw-value loop, phone via opts.rankedByField with lv_phone_2 overflow), and ENRICH_CO_GATE's 13-key REQUIRED list is untouched."
    requirement: "D-72-14"
    verification:
      - kind: unit
        ref: "tests/test_field_policy_conformance.py (4/4, RED-then-GREEN on key-set parity)"
        status: pass
      - kind: unit
        ref: "tests/n8n/mergeCompanies.test.mjs (7 new tests: fill_blank_only behavior, overflow routing, explicit-policy pin)"
        status: pass
      - kind: unit
        ref: "tests/n8n/fieldProducerMatrix.test.mjs (8/8, NEVER_CHASE extended)"
        status: pass
      - kind: other
        ref: "CO_REQUIRED_LEN==13; NO_EXPLICIT_POLICY==[]; diff -q byte-identity between both field_policy.yaml copies; second build_cloud_workflows.py run produces no diff; Merge Company's regenerated jsCode confirmed to contain state/hs_state_code/phone/lv_phone_2"
        status: pass
    human_judgment: false
  - id: D3
    description: "A person's location can never reach the company's lv_country_region_normalized -- enforced by a guard test whose failure message names D-72-16 and 58-06, plus a pin that the escalation policy's material-conflict group pairing (region/country) is unweakened."
    requirement: "D-72-16"
    verification:
      - kind: unit
        ref: "tests/n8n/mergeCompanies.test.mjs::mergeCompanies: a contact-shaped geo candidate set ... (D-72-16) -- RED evidence captured via temporary injection, reverted"
        status: pass
      - kind: unit
        ref: "tests/n8n/mergeCompanies.test.mjs::config/escalation_policy.yaml: lv_country_region_normalized and country stay in ONE material_conflict_field_groups entry"
        status: pass
      - kind: other
        ref: "tests/test_judge_spec.py::test_ro2_judge_gate_cannot_see_size_conflicts (unmodified, still 10/10 pass)"
        status: pass
    human_judgment: false

duration: 95min
completed: 2026-09-12
status: complete
---

# Phase 72 Plan 06: Company Geo and Phone Producers Summary

**Companies gain the geo/phone shape contacts already had — but only where a real Lusha or Apollo response actually carries it — with `hs_country_region_code`'s scope-down and `hs_additional_domains`'s accepted no-producer gap both settled by the live probe rather than guessed.**

## Performance

- **Duration:** 95 min
- **Started:** 2026-09-12T12:22:00Z (approx)
- **Completed:** 2026-09-12T13:57:00Z (approx)
- **Tasks:** 3 of 3 complete
- **Files modified:** 15 (across 5 commits: 2 RED/GREEN pairs + 1 test-only commit)

## Accomplishments

- **Nine-cell evidence table (3 providers × state / hs_state_code / hs_country_region_code+phone), resolved before any code was written:**

  | Provider | `state` | `hs_state_code` | `phone` |
  | --- | --- | --- | --- |
  | Lusha | **producer** — `co.location.state`, full name, documented live (LUSHA-V3-CONTRACT.md §5, confirmed-live companies/search-and-enrich example) | **producer, guarded** — code-shaped-only push off the same `state` value; never observed code-shaped in that documented shape, mirrors the identical "structural guard" rule the contacts branches already carry | **no producer** — Lusha's dedicated companies-lane response (LUSHA-V3-CONTRACT.md §5) has no phone field at all |
  | Apollo | **producer** — `org.state`, full name, live evidence `docs/reports/2026-07-17-dryrun-batch.md` (FanDuel org: `state: "New York"`) | **producer, guarded** — same discipline; Apollo's org.state has never been observed code-shaped, matching the existing "these two never fire from Apollo today" comment on its contacts branch | **producer** — `org.primary_phone.sanitized_number` (preferred) or `org.phone` through `normalizePhone`; live evidence `docs/reports/2026-07-15-dry-run-gillon-mclachlan.md` (Tabcorp: `phone: "+61 3 9246 6010"`, `primary_phone.sanitized_number: "+61392466010"`) |
  | ZoomInfo | **no producer** — `ZOOM_CO_OUTPUT_FIELDS` requests neither field for companies today; both are valid, individually-probed GTM outputFields per the `zoominfo-gtm-companies-contract` memory note, so this is a documented scoping choice (mirrors 58-05's `city` precedent), not an API limitation | **no producer** (moot — no state value to guard) | **no producer** — same reasoning as `state` |

  `hs_country_region_code` (a separate, distinct property from `hs_state_code`) has **no producer for any provider** — `72-PORTAL-PROBE.json` confirmed live that the property does not exist on companies (404). This scopes the company half of D-72-15's ISO-code requirement to `hs_state_code` only, exactly as the plan's own fallback instruction anticipated.

- **Task 1 (`n8n/code/normalizeProviders.js`):** added the four real producers above (Lusha state+guarded-code, Apollo state+guarded-code+phone) plus an in-file comment on the ZoomInfo company branch documenting the accepted absence — mirroring the file's existing "ZoomInfo GTM company enrich requests no `city` outputField" precedent so a future reader finds the reason in the code, not only in a planning file. Extended `tests/n8n/normalizeProviders.test.mjs` with 20 tests (5 genuinely RED before the producers existed) and updated two pre-existing pinned field-set assertions in `tests/n8n/enrichment.test.mjs` to include the new `state` candidate (an expected, invited consequence — the fixture used already carried a `state` key).

- **Task 2 (policy + write map):** added explicit `fill_blank_only@80` `field_policy.yaml`/`DEFAULT_COMPANY_POLICY` entries for `state`/`hs_state_code`/`phone` (mirrored byte-for-byte between the repo and plugin copies); widened `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` so the existing-value fetch actually returns these three (the same non-clobber correctness fix 58-05/plan 05 already made for `country`/`city`/`numberofemployees`/`lv_phone_2`); threaded `scoreCandidates().ranked` through `ENRICH_NORMALIZE_SCORE_CO` into `row.scored`; and widened `Merge Company`'s candidate loop — `state`/`hs_state_code` join the existing raw-value loop, `phone` is admitted via `opts.rankedByField` (which both assigns the trust-rank winner and routes the runner-up to `lv_phone_2` in one pass). Regenerated all five affected workflow JSONs and re-baselined `tests/fixtures/companies_jscode_frozen.json` (an explicit, reviewed act per that fixture's own docstring — only the `Merge Company` node's jsCode changed).

- **Task 3 (D-72-16 guard):** added a permanent regression test proving `mergeCompanies()` never derives `lv_country_region_normalized` from contact-shaped `city`/`state`/`country` candidates, plus a pin that `config/escalation_policy.yaml`'s `material_conflict_field_groups` still pairs `lv_country_region_normalized` with `country` in exactly one group. Since the engine has no derivation code path at all, this test cannot naturally go RED — RED evidence was captured by temporarily injecting a fake derivation, observing the failure (with the D-72-16 message), then reverting before the real commit.

## Task Commits

Each task was committed as a RED/GREEN pair (or, for Task 3, a single test-only commit since no production code changed):

1. **Task 1 RED:** failing tests for company state/hs_state_code/phone producers — `2b704280` (test)
2. **Task 1 GREEN:** company state/hs_state_code/phone producers (D-72-14, D-72-15) — `fb6188c1` (feat)
3. **Task 2 RED:** explicit companies policy for state/hs_state_code/phone — `9293ccf7` (test)
4. **Task 2 GREEN:** wire state/hs_state_code/phone through the Merge Company write map — `514c4ec6` (feat)
5. **Task 3:** guard test that contact geo can never reach company region (D-72-16) — `f8030371` (test)

**Plan metadata:** (this commit)

## Files Created/Modified

- `n8n/code/normalizeProviders.js` — Lusha/Apollo company state+guarded-code+phone producers, ZoomInfo no-producer comment
- `n8n/code/mergeCompanies.js` — `DEFAULT_COMPANY_POLICY` entries for state/hs_state_code/phone
- `config/field_policy.yaml` / `operator-claude-plugin/config/field_policy.yaml` — the same three new `companies:` policy entries, byte-identical
- `scripts/build_cloud_workflows.py` — search-CSV widened, `ranked` threaded through `ENRICH_NORMALIZE_SCORE_CO`, `Merge Company`'s candidate loop widened (raw-value loop + `rankedByField`) with a write-map-vs-chase-list comment
- `n8n/wf_enrichment_cloud.json`, `wf_enrichment_local.json`, `wf_enrichment_local_live.json`, `wf_review_decision_cloud.json`, `wf_scheduled_maintenance_cloud.json` — regenerated, never hand-edited
- `tests/fixtures/companies_jscode_frozen.json` — re-baselined (`Merge Company` node only)
- `tests/n8n/normalizeProviders.test.mjs` — 20 new tests
- `tests/n8n/mergeCompanies.test.mjs` — 9 new tests (7 behavior/policy + 2 D-72-16 guards)
- `tests/n8n/enrichment.test.mjs` — 2 pre-existing pins updated
- `tests/n8n/fieldProducerMatrix.test.mjs` — `NEVER_CHASE` extended with the three new write-only company keys

## Decisions Made

See `key-decisions` in the frontmatter for the full list. Highlights: the nine-cell evidence table drove every producer decision; `hs_country_region_code` and `hs_additional_domains` both stay accepted gaps for independent, pre-existing reasons (property absence and no-domain-producer, respectively); the plan's "companies.phone already exists" assumption was corrected in place (Rule 1, no checkpoint needed); `phone`'s overflow routes exclusively through `opts.rankedByField`; and the `NEVER_CHASE` exemption set (not `ENRICH_CO_GATE`'s `REQUIRED`) is the mechanism keeping these three fields write-map-only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the plan's "companies.phone already exists" assumption**
- **Found during:** Task 2, before writing any policy YAML
- **Issue:** The plan instructs "check its current class... leave it alone." No `phone` key exists under `companies:` in `config/field_policy.yaml`, its plugin copy, or `DEFAULT_COMPANY_POLICY`. `phone` IS a genuine, existing, writable native HubSpot company property (confirmed by 72-RESEARCH.md's live property-export citation) — the plan conflated the portal-schema property with a merge-policy entry for it.
- **Fix:** Added the policy entry fresh, using the exact shape (`fill_blank_only`, `min_confidence: 80`, `protect_if_current_present: true`) the plan specifies for its other two new entries.
- **Files modified:** `config/field_policy.yaml`, `operator-claude-plugin/config/field_policy.yaml`, `n8n/code/mergeCompanies.js`
- **Verification:** `tests/test_field_policy_conformance.py` (4/4 pass), `NO_EXPLICIT_POLICY==[]` check
- **Committed in:** `9293ccf7` / `514c4ec6`

**2. [Rule 1 - Bug] `tests/n8n/fieldProducerMatrix.test.mjs`'s "chase gate" required an exemption**
- **Found during:** Task 2 GREEN, after widening the write map and rebuilding
- **Issue:** This pre-existing test asserts every producer-having, promotable, non-recomputed policy key must be in `ENRICH_CO_GATE`'s `REQUIRED` list. Adding real producers for `state`/`hs_state_code`/`phone` (while the plan explicitly forbids widening `REQUIRED` — T-72-09) made the test fail: `producer-having, promotable fields NOT chased: companies.state, companies.hs_state_code, companies.phone`.
- **Fix:** Added all three to the test's pre-existing `NEVER_CHASE` exemption set (the same mechanism already used for `contacts.hs_linkedin_url`), with a comment naming the T-72-09 economics.
- **Files modified:** `tests/n8n/fieldProducerMatrix.test.mjs`
- **Verification:** `node --test tests/n8n/fieldProducerMatrix.test.mjs` (8/8 pass)
- **Committed in:** `514c4ec6`

**3. [Rule 1 - Bug] Re-baselined the frozen companies-jsCode fixture**
- **Found during:** Task 2 GREEN full-suite verification
- **Issue:** `tests/test_companies_factory_frozen.py`'s byte-identity guards failed because `Merge Company`'s jsCode legitimately changed (new policy entries inlined via `mergeCompanies.js`, plus the widened candidate loop and `rankedByField` wiring). The fixture's own docstring calls re-baselining "an explicit, reviewed act" for exactly this situation.
- **Fix:** Regenerated `tests/fixtures/companies_jscode_frozen.json` by calling `build_enrichment_cloud()`/`build_enrichment_local_live()` directly and confirming only the `Merge Company` node's jsCode differed.
- **Files modified:** `tests/fixtures/companies_jscode_frozen.json`
- **Verification:** `tests/test_companies_factory_frozen.py` (4/4 pass)
- **Committed in:** `514c4ec6`

**4. [Rule 1 - Minor] Task 1's Apollo phone test assertion used the wrong raw value**
- **Found during:** Task 1 GREEN, first test run
- **Issue:** The producer prefers `org.primary_phone.sanitized_number` (already E.164-shaped) over `org.phone` when both are present. My own new test asserted the RAW `phone` string, not the sanitized value actually used.
- **Fix:** Corrected the test assertion to the sanitized value.
- **Files modified:** `tests/n8n/normalizeProviders.test.mjs`
- **Verification:** `node --test tests/n8n/normalizeProviders.test.mjs` (20/20 pass)
- **Committed in:** `fb6188c1`

---

**Total deviations:** 4 auto-fixed (1 plan-assumption correction, 1 pre-existing-gate exemption, 1 fixture re-baseline, 1 self-authored test-assertion fix)
**Impact on plan:** All four are mechanical consequences of Task 1/2's legitimate, in-scope changes. No scope creep — no unrelated fixture, test, or field was touched.

## TDD Gate Compliance

- **Task 1:** RED (`2b704280`, 5/20 tests genuinely failing for the right reason) → GREEN (`fb6188c1`, 20/20 pass). No REFACTOR commit — the initial implementation needed no cleanup.
- **Task 2:** RED (`9293ccf7`) → GREEN (`514c4ec6`). The RED signal was `tests/test_field_policy_conformance.py`'s key-set parity check (genuinely red: YAML had the three new keys, `DEFAULT_COMPANY_POLICY` did not). Four of the seven new `mergeCompanies.test.mjs` behavior tests were **already GREEN at RED-commit time** — investigated per tdd.md's "unexpected GREEN" guidance and understood: `mergeCompanies()`'s own undeclared-field fallback (`policy[field] || { class: "fill_blank_only", min_confidence: 80 }`) already gave `state`/`hs_state_code`/`phone` this exact runtime behavior before any policy key existed. This task made the policy **explicit** (SAFE-01), not new at the engine level; the genuinely-red assertion (the SAFE-01 declaration-presence test, plus the conformance test) is what actually drove GREEN. Documented, not a wrong test.
- **Task 3:** a single test-only commit (`f8030371`), no separate RED/GREEN split since no production code changed. **No natural RED exists** — `mergeCompanies()` has no code path deriving `lv_country_region_normalized` from anything, so the guard test is a permanent invariant pin, not a driver of new behaviour. Per the project's own memory note ("a guard test must be seen RED first"), RED evidence was captured by temporarily injecting a fake derivation directly into `n8n/code/mergeCompanies.js` (`if (candidateRow.city && candidateRow.country && candidateRow.lv_country_region_normalized == null) candidateRow.lv_country_region_normalized = "AU";`), running `node --test tests/n8n/mergeCompanies.test.mjs`, observing the guard test fail with its D-72-16 failure message, then reverting the file byte-for-byte (`cp` from a pre-edit backup, confirmed via `git diff --stat n8n/code/mergeCompanies.js` showing no output) before making the real, test-only commit.

## Issues Encountered

- The plan's own Task 3 verify snippet for the escalation-groups check (`.venv/bin/python -c "... hit=[x for x in g if 'lv_country_region_normalized' in x and 'country' in x] ..."`) has a bug: `x` is a group **dict** (`{"name": ..., "fields": [...]}`), so `'lv_country_region_normalized' in x` tests dict **keys**, never the nested `fields` list — the check always exits 1 regardless of actual state. Ran the corrected form (`'lv_country_region_normalized' in x['fields']`) to confirm the invariant genuinely holds (it does — one `country_region` group, `["lv_country_region_normalized", "country"]`). Not a permanent test file, so no source fix was needed; documented here in case a future plan reuses this exact snippet verbatim.

## User Setup Required

None — no external service configuration required. Nothing armed, deployed, or bounced; no live HubSpot or n8n call was made.

## Next Phase Readiness

- All three of this plan's `must_haves.truths` are satisfied: D-72-15's company geo lands as names/codes only where a provider actually supplies them; D-72-14's company phone (+ its single `lv_phone_2` overflow) is reachable from a real producer, and `hs_additional_domains` correctly stays an accepted no-producer gap; D-72-16's boundary is enforced by a permanent guard test; every new policy entry has an explicit class/threshold; and the companies `REQUIRED` chase list is still exactly thirteen keys.
- The pre-existing open todo about company `domain` having no producer at all (and therefore no second-domain overflow into `hs_additional_domains`) remains open and unaffected by this plan — it was out of scope here (Task 1's producers cover state/code/phone only).
- No blockers. Nothing in this plan deploys, bounces, or arms anything — plan 08's deploy/bounce/gate work is unaffected in scope.

## Self-Check: PASSED
- `n8n/code/normalizeProviders.js` — FOUND, contains the new Lusha/Apollo company producers
- `n8n/code/mergeCompanies.js` — FOUND, contains `state`/`hs_state_code`/`phone` in `DEFAULT_COMPANY_POLICY`
- `config/field_policy.yaml` / `operator-claude-plugin/config/field_policy.yaml` — byte-identical (confirmed via `diff -q`)
- Commits `2b704280`, `fb6188c1`, `9293ccf7`, `514c4ec6`, `f8030371` — all present in `git log --oneline --all`
- `node --test tests/n8n/*.test.mjs` — 1167/1167 pass
- `.venv/bin/python -m pytest -q --tb=short tests/ operator-claude-plugin/tests/` — 4947 passed, 154 skipped, 0 failed
- A second `.venv/bin/python scripts/build_cloud_workflows.py` run produces no diff (idempotent regeneration confirmed)

---
*Phase: 72-enrichment-extras-land-in-hubspot*
*Completed: 2026-09-12*
