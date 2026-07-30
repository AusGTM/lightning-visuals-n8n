# Quick Task 260730-din: Execution-Risk Research (deepens PLAN.md, does not re-survey)

**Researched:** 2026-07-30
**Scope:** file:line-precise mechanics for Tasks 1, 5, 6 — PLAN.md's touchpoint list is confirmed
accurate; this fills in exactly *which* test assertions break, *why*, and *how many*.

## 1. Frozen byte-identity test — `tests/test_companies_factory_frozen.py`

Only ONE byte-identity/frozen fixture exists in the repo (`tests/fixtures/companies_jscode_frozen.json`,
`{"cloud": {...7 node names}, "local_live": {...7 node names}}`). No generator script exists —
confirmed by `16.3-companies-stale-timestamp-fix/16.3-CONTEXT.md:45`: *"There is no generator
script for the fixture — re-baselining is a manual, deliberate act."*

**FROZEN_NODE_NAMES** (test file L32-40): `Research Trigger Gate`, `Build Research Request`,
`Validate Research Output`, `Judge Gate`, `Build Judge Request`, `Apply Judge Verdict`, `Merge Company`.

**Traced which of the 7 actually reference the renamed consts** (grepped `build_cloud_workflows.py`
L2054-2253, the source of each node's jsCode):

| Frozen node | References old names? | Verdict |
|---|---|---|
| Research Trigger Gate (L2073-2096) | `ALLOW_WEB_RESEARCH`/`MAX_WEB_RESEARCH_PER_RUN` only | **unchanged** |
| Build Research Request (L2104-2130) | `ANTHROPIC_SONNET_MODEL` (L2111, L2117) | **CHANGES** |
| Validate Research Output (L2135-2149) | none | **unchanged** |
| Judge Gate (L2170-2197) | `ALLOW_SONNET_ESCALATION` + `MAX_SONNET_VALIDATIONS_PER_RUN` (L2176-2178) | **CHANGES** |
| Build Judge Request (L2204-2217) | `ANTHROPIC_SONNET_MODEL` (L2209, L2213) | **CHANGES** |
| Apply Judge Verdict (L2220-2245) | none | **unchanged** |
| Merge Company (ENRICH_MERGE_CO, L2253+) | none (confirmed via grep, zero hits) | **unchanged** |

**Bound: exactly 3 of 7 node names change, × 2 variants (cloud/local_live) = 6 of 14
`{variant, node}` pairs.** This is tighter than the "budget most review attention there" framing
in PLAN.md's Risks section suggests — it is bounded and predictable, following the exact same
shape as the two prior precedent re-baselines (16.3: 2/14 pairs = `Merge Company` only; 18-03:
2/14 pairs = `Build Research Request` only).

**Documented regeneration procedure** (no script; reconstructed from `16.3-01-PLAN.md:250-302`,
the only precedent with step-by-step detail — the comment block in the test file itself only says
"re-baselined ONLY by an explicit, reviewed act"):
1. Before editing source, capture the CURRENT (pre-rename) fixture values for the 6 affected
   `{variant, node}` pairs as a baseline for the diff-proof.
2. Land the source rename (Tasks 1-4).
3. Write a **scratchpad script** (session scratchpad dir, NOT the repo — `16.3-01-PLAN.md:258`)
   that imports `build_cloud_workflows`, calls `build_enrichment_cloud()` /
   `build_enrichment_local_live()`, extracts jsCode for the 7 `FROZEN_NODE_NAMES`, and diffs
   against the OLD fixture. **Prove the diff is bounded to exactly the 3 nodes above (6/14
   pairs) before writing anything** — any other node moving is a STOP-and-report per every prior
   precedent (`16.4-CONTEXT.md:77`, `16.6-CONTEXT.md:69`).
4. Overwrite ONLY those 6 entries in `tests/fixtures/companies_jscode_frozen.json` with the
   freshly-built strings (leave the other 8 untouched — don't blind-overwrite the whole file).
5. Commit the fixture update ALONE, isolated from the source-edit commit, message stating the
   bound (e.g. "3/7 frozen nodes changed: Build Research Request, Judge Gate, Build Judge
   Request — model/flag rename, no logic change").

**No other frozen/byte-identity test exists for this rename's blast radius.** Grep for
"frozen|byte|identity" across `tests/` surfaces `test_bug10_company_search_transport.py` and
`test_create_payload_identity.py`, but those pin unrelated node bodies (search transport shape,
CREATE payload identity fields) with zero references to SONNET/MODEL/ESCALATION — confirmed via
targeted grep, no overlap.

## 2. `tests/test_deploy_flag_overlay.py` (385 lines) — near-total rewrite, not a few deletions

PLAN.md's Task 5 line ("remove/convert every ALLOW_SONNET_ESCALATION overlay case; keep
ALLOW_WEB_RESEARCH cases intact") is directionally correct but **understates scope: 10 of 13 test
functions reference `ALLOW_SONNET_ESCALATION`.** Confirmed via `scripts/deploy_n8n_workflows.py`
L294-372 (`enable_baked_flags`): it raises `ValueError` for ANY flag name not in
`_OVERLAY_FLAG_SPEC` (L313-319) **before** doing any counting/rewriting — so once Task 2 deletes
the `ALLOW_SONNET_ESCALATION` entry, every call site below that still passes the old (or even the
new `ALLOW_JUDGE_ESCALATION`) name as an *overlay* target will raise instead of running.

Per-function disposition:

| Test (line) | Current behavior | Required change |
|---|---|---|
| `hermetic` fixture (L30-37) | delenv list includes `ALLOW_SONNET_ESCALATION` | rename to `ALLOW_JUDGE_ESCALATION` |
| `test_enable_baked_flags_exactness_on_real_committed_artifact` (L72-90) | counts+asserts BOTH flags together; escalation half assumes committed literal is `false` | **DELETE the escalation half** (default is now `true`, and the flag isn't overlayable at all) — keep ALLOW_WEB_RESEARCH-only |
| `test_enable_baked_flags_independence_research_only` (L95-102) | asserts `const ALLOW_SONNET_ESCALATION = false;` survives after enabling only research | rename + flip literal: assert `const ALLOW_JUDGE_ESCALATION = true;` (now the unconditional committed default, independent of any overlay call) |
| `test_enable_baked_flags_independence_escalation_only` (L104-110) | enables escalation via overlay, asserts it flips | **DELETE entirely** — no longer overlayable, this behavior no longer exists |
| `test_enable_baked_flags_raises_on_numeric_literal_variant` (L129-139) | uses `ALLOW_SONNET_ESCALATION` as the flag under test for **drift-detection** (the fail-closed re-scan code path, L352-370 of deploy script) | **coverage regression risk**: once removed from spec, `enable_baked_flags(..., ["ALLOW_SONNET_ESCALATION"])` raises the *"not in overlayable set"* error (L314-319) instead of reaching the numeric-literal re-scan check. Swap the flag under test to `ALLOW_WEB_RESEARCH` (or a synthetic name) to keep this code path covered — do not just rename the string, or the drift-detection branch loses its only numeric-literal test case |
| `bad_flag` parametrize ×2 (L171-190) | `["MAX_WEB_RESEARCH_PER_RUN", "MAX_SONNET_VALIDATIONS_PER_RUN", "ANTHROPIC_SONNET_MODEL"]` | rename cap → `MAX_JUDGE_VALIDATIONS_PER_RUN`; split model → `ANTHROPIC_RESEARCH_MODEL`, `ANTHROPIC_JUDGE_MODEL` (2 entries); **ADD `ALLOW_JUDGE_ESCALATION`** (it just left the overlayable set — this is the correct place to pin that as a permanent invariant, mirroring how cost caps/models are pinned) |
| `test_enable_baked_flags_zero_declarations_returns_unchanged_not_a_raise` (L195-203) | calls `enable_baked_flags(wf, ["ALLOW_WEB_RESEARCH", "ALLOW_SONNET_ESCALATION"])` against a workflow with neither flag | **will now raise** (unknown flag) before it can return the zero-count tuple this test asserts. Drop the escalation arg — test with `["ALLOW_WEB_RESEARCH"]` only |
| `test_ambient_env_names_have_zero_effect_on_the_captured_put_body` (L240-269) | sets ambient env `ALLOW_SONNET_ESCALATION=true`, asserts baked output stays `const ALLOW_SONNET_ESCALATION = false;` | rename var; **flip expected literal to `true`** (new default) — and note: setting the ambient env to `true` no longer *proves* independence since `true` now coincidentally matches the default. To keep the test meaningful, set the ambient env to `"false"` instead (the non-default value) and assert the baked output still reads `true` |
| `test_default_off_through_real_path_unset_enable_baked_flags` (L274-298) | name says "default off"; asserts `const ALLOW_SONNET_ESCALATION = false;` | escalation half is now default-**on**: rename assert to `const ALLOW_JUDGE_ESCALATION = true;`. Consider renaming the test itself (only the research flag is "default off" now) |
| `test_enabled_through_real_path_and_bind_credentials_succeeds` (L302-341) | `ENABLE_BAKED_FLAGS=ALLOW_WEB_RESEARCH,ALLOW_SONNET_ESCALATION` | **will raise** once escalation leaves the spec. Rewrite to request `ALLOW_WEB_RESEARCH` only; drop all escalation-literal assertions (credential-binding proof is unaffected, it never depended on which flag was overlaid) |
| `test_dry_run_visibility_prints_rewrite_plan_and_makes_zero_http_calls` (L346-370) | same `ENABLE_BAKED_FLAGS=...,ALLOW_SONNET_ESCALATION`, asserts it appears in dry-run output | same fix: `ALLOW_WEB_RESEARCH` only, drop the `"ALLOW_SONNET_ESCALATION" in out` assert |
| `test_main_refuses_at_deploy_set_level...` (L208-236) | uses `ALLOW_WEB_RESEARCH` only | **unaffected**, no change |

Net: only 3 of 13 tests are untouched; the rest need either a literal-value flip, a flag-argument
drop, or full deletion. This is the single largest test-file diff in the whole task.

## 3. `tests/n8n/enabledResearchLaneFlow.test.mjs` (368 lines)

Builds its "enabled" fixture by **re-implementing** the Python overlay in JS (L38-49,
`enableBakedFlagsJs`): a plain string `.split(disabled).join(enabled)` over the raw committed
`wf_enrichment_cloud.json` text, for `OVERLAY_FLAGS = ["ALLOW_WEB_RESEARCH",
"ALLOW_SONNET_ESCALATION"]` (L36) — **not** the deploy module's overlay (deliberately independent,
per the file's own header comment L13-16).

**Once the rename lands, the committed workflow will already bake
`const ALLOW_JUDGE_ESCALATION = true;`** — the string `const ALLOW_SONNET_ESCALATION = false;`
this script searches for will not exist anywhere in the file. Effect: for that flag,
`enableBakedFlagsJs` finds `count = 0` and is a silent no-op (harmless, since the flag is already
enabled in the source text) — but it makes the escalation half of `OVERLAY_FLAGS` dead weight,
confirming PLAN.md's prediction that "the enabled overlay fixture may collapse into the default
build for the escalation half."

**Required change:** drop `ALLOW_SONNET_ESCALATION` from `OVERLAY_FLAGS` entirely (rename to just
`["ALLOW_WEB_RESEARCH"]`) — do not rename it in place, since it no longer needs "enabling" at all.
The `assert.ok(totalReplacements > 0, ...)` guard (L56) still passes off the `ALLOW_WEB_RESEARCH`
replacement alone.

**No downstream assertion changes needed.** Tests (2)/(3) (contacts/companies lane, L199-355)
never reference the flag names directly — they run `node.parameters.jsCode` via `new Function`
(L93-94), so the renamed consts (`ALLOW_JUDGE_ESCALATION`, `MAX_JUDGE_VALIDATIONS_PER_RUN`) are
local variable names inside that generated function body and invisible to the harness. The
`judgeGate.needs_judge === true` / `judge_reasons.includes(...)` assertions (L219-222, L338-341)
are unaffected — judge escalation fires the same way it always did, just via a baked-`true` const
instead of an overlay-flipped one. Test (4) (disabled control, L361-368) only exercises the
research trigger gate, never reaches Judge Gate, and is completely unaffected by the escalation
default flip.

**Comment-only touch:** header comment L4 ("...ALLOW_WEB_RESEARCH/ALLOW_SONNET_ESCALATION
enabled...") should be updated to reflect that judge escalation is armed by default and only
research needs the deploy-time overlay now.

## 4. `tests/test_enabled_build_invariants.py` (201 lines) — module-level `FLAGS` tuple drives most of the file

`FLAGS = ("ALLOW_WEB_RESEARCH", "ALLOW_SONNET_ESCALATION")` at **L23** is consumed by 5 of the 8
test functions. Since `ALLOW_JUDGE_ESCALATION` is (a) renamed and (b) removed from
`_OVERLAY_FLAG_SPEC` and (c) now baked `true` by default, this tuple's premise ("both flags are
overlayable and both are committed-disabled") breaks for the escalation half. Required changes:

- **L23** `FLAGS` → reduce to `("ALLOW_WEB_RESEARCH",)`. It is no longer meaningful to bundle
  `ALLOW_JUDGE_ESCALATION` with the overlayable-flags concept this tuple represents.
- **`test_committed_build_flag_declarations_are_always_disabled`** (L48-61, parametrized over
  `FLAGS` × cloud workflow paths): with `FLAGS` reduced, this test loses its escalation coverage
  entirely — but that's *correct*, since the committed build is now supposed to declare
  `ALLOW_JUDGE_ESCALATION = true`, the opposite invariant. **Add a new, inverted test**
  (`test_committed_build_judge_escalation_is_always_true` or similar) asserting every literal
  found for `ALLOW_JUDGE_ESCALATION` across the cloud workflow files is `"true"` — this is the
  actual arm-by-default guarantee this whole task exists to deliver, and it currently has zero
  test coverage in this file's proposed shape.
- **`test_enrichment_workflow_declares_both_flags_at_least_once`** (L64-71): rename/rewrite —
  "both flags" language breaks once `FLAGS` is singular; either fold the judge-escalation
  non-vacuity check into the new inverted test above, or keep this test for `ALLOW_WEB_RESEARCH`
  alone and rename.
- **`_enabled_enrichment_workflow_serialized()`** helper (L76-80): calls
  `deploy.enable_baked_flags(wf, list(FLAGS))` — fine once `FLAGS` is `("ALLOW_WEB_RESEARCH",)`,
  since escalation is no longer overlaid (it's already `true` in the committed source).
- **`test_enabled_vs_committed_diff_touches_only_the_four_flag_lines`** (L101-126): "four" =
  2 flags × 2 declaration sites each in `wf_enrichment_cloud.json` (confirmed: companies Judge
  Gate + contacts Contact Judge Gate, each declaring `ALLOW_WEB_RESEARCH`+`ALLOW_SONNET_ESCALATION`
  once). With `FLAGS` reduced to one flag, this becomes **"two" flag lines** (`ALLOW_WEB_RESEARCH`
  is baked in 2 places — Research Trigger Gate + Contact Research Trigger Gate). Rename the test
  and its `flag_decl_re` regex construction (L117) still works generically off `FLAGS`, no logic
  change needed beyond the tuple shrink + docstring/name.
- **`test_enabled_build_cost_caps_are_unchanged`** (L157-168): tuple
  `("MAX_WEB_RESEARCH_PER_RUN", "MAX_SONNET_VALIDATIONS_PER_RUN")` at **L161** → rename second
  entry to `MAX_JUDGE_VALIDATIONS_PER_RUN`. Purely a rename; the test only checks the value is
  *unchanged* across committed vs. enabled builds, not what the value is (so the `10`→`50` default
  change doesn't affect this test's correctness).
- **`test_overlayable_flags_is_a_strict_subset_of_config_flag_defaults`** (L173-201) — the
  highest-value pin in the file:
  - **L182-189**: `deploy._OVERLAYABLE_FLAGS == {"ALLOW_WEB_RESEARCH", "ALLOW_SONNET_ESCALATION",
    "ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE", "TEST_RECORD_IDS",
    "TEST_RECORD_DOMAINS"}` (6 entries) → **DROP `"ALLOW_SONNET_ESCALATION"` entirely** (5 entries
    remain; do not rename it into the set — it is no longer overlayable at all).
  - **L191-193**: `not deploy._OVERLAYABLE_FLAGS & {"MAX_WEB_RESEARCH_PER_RUN",
    "MAX_SONNET_VALIDATIONS_PER_RUN", "ANTHROPIC_SONNET_MODEL"}` (the "structurally out of reach"
    set) → rename to `{"MAX_WEB_RESEARCH_PER_RUN", "MAX_JUDGE_VALIDATIONS_PER_RUN",
    "ANTHROPIC_RESEARCH_MODEL", "ANTHROPIC_JUDGE_MODEL"}` **and ADD `"ALLOW_JUDGE_ESCALATION"`**
    to this "never overlayable" set — this is the correct permanent home for asserting the flag
    left the overlay mechanism for good.
  - **L197-201** loop over `deploy._OVERLAY_FLAG_SPEC.items()` asserting `disabled_literal ==
    "false"` for non-write-safety flags: no change needed — once the `ALLOW_SONNET_ESCALATION`
    entry is deleted from the spec dict (Task 2), this loop simply never iterates over it.

Net for this file: 6 of 8 test functions touched (rename, tuple-shrink, or new addition); this is
the second-largest test-file diff after `test_deploy_flag_overlay.py`.

## 5. Builder internals — confirmed exact call sites (scripts/build_cloud_workflows.py)

- **`CONFIG_FLAG_DEFAULTS`** (L778-785): 6 keys today. `_flag_const()` (L797-817) asserts
  `name in CONFIG_FLAG_DEFAULTS` (L805) — any call site left referencing an old key name after the
  dict is edited fails loudly at build time (not a silent bug), so the rename is naturally
  self-checking here.
- **All `_flag_const` call sites for the 3 old names** (8 raw string matches, mapped to 4 call
  sites):
  - L2111: `_flag_const("ANTHROPIC_SONNET_MODEL", cloud)` (Build Research Request, companies+contacts)
  - L2117: usage `const model = ANTHROPIC_SONNET_MODEL;` (same node)
  - L2176: `_flag_const("ALLOW_SONNET_ESCALATION", cloud) + ... + _flag_const("MAX_SONNET_VALIDATIONS_PER_RUN", cloud)` (Judge Gate, companies+contacts)
  - L2177-2178: usages `ALLOW_SONNET_ESCALATION` / `MAX_SONNET_VALIDATIONS_PER_RUN`
  - L2209: `_flag_const("ANTHROPIC_SONNET_MODEL", cloud)` (Build Judge Request, companies+contacts)
  - L2213: usage `const model = ANTHROPIC_SONNET_MODEL;`
  - Python `#` comments only (safe, don't affect frozen jsCode bytes): L2102-2103, L2165-2166, L2202-2203.
- **`tests/test_builder_flag_parity.py`**: `EXPECTED_FLAGS` (L30-37) is the 6-name pin →
  becomes 7: `{"ALLOW_WEB_RESEARCH", "MAX_WEB_RESEARCH_PER_RUN", "ANTHROPIC_RESEARCH_MODEL",
  "ANTHROPIC_JUDGE_MODEL", "WEB_RESEARCH_MAX_SEARCHES", "ALLOW_JUDGE_ESCALATION",
  "MAX_JUDGE_VALIDATIONS_PER_RUN"}`. The 4 tests that iterate `EXPECTED_FLAGS` generically
  (`test_config_flag_defaults_is_exactly_the_six_flags` L49-50,
  `test_local_live_references_all_six_flags_via_env_var_expressions` L81-88,
  `test_cloud_references_all_six_flags_as_baked_literals` L91-104) need **zero logic changes**,
  only the `EXPECTED_FLAGS` set update — their assertions are name-driven loops, not hardcoded
  literals. Consider renaming the "six" in test/function names to "seven" for accuracy (not
  load-bearing).
- **Literal occurrence counts confirmed live** in `n8n/wf_enrichment_cloud.json` (the artifact
  Task 6 rebuilds): `const ALLOW_SONNET_ESCALATION = false;` × **2** (companies Judge Gate +
  Contact Judge Gate); `ANTHROPIC_SONNET_MODEL` (bare token, decl+usage) × **8** (4 nodes ×
  2 occurrences: companies Build Research Request, companies Build Judge Request, contacts
  mirror ×2); `MAX_SONNET_VALIDATIONS_PER_RUN` × **4** (2 nodes × 2 occurrences). These match
  `.planning/STATE.md`'s recorded Phase 16.5 rewrite counts (`{'ALLOW_WEB_RESEARCH': 2,
  'ALLOW_SONNET_ESCALATION': 2}`) exactly — confidence the count-based asserts in
  `test_deploy_flag_overlay.py` (now mostly deleted, see §2) were counting real declarations, not
  an inflated/stale number.
- **`n8n/wf_scheduled_maintenance_cloud.json` has ZERO occurrences** of all 3 old names
  (confirmed via grep) — this workflow is untouched by the entire rename; no need to inspect it
  further in Task 6/7 verification.
- **No parity test exists that hardcodes a flag-count assertion tied to the literal number "6"**
  beyond the `EXPECTED_FLAGS`/`EXPECTED_SECRETS` set-equality checks already covered above — the
  6→7 shift is fully absorbed by set-membership tests, not a magic-number assert anywhere else.

## 6. Touchpoints PLAN.md's survey missed or under-scoped

- **`n8n/code/judge.js:41` and `:182`** — comment-only mentions of `ALLOW_SONNET_ESCALATION`
  (confirmed, PLAN.md's Task 8/out-of-scope note already anticipated this: "comments mentioning
  ALLOW_SONNET_ESCALATION may be renamed for greppability; zero logic edits" — just noting the
  exact 2 line numbers since PLAN.md didn't cite them).
- **`scripts/n8n_enrichment_live_replica.sh`, `scripts/n8n_replica_test.sh`,
  `scripts/provision_n8n_credentials.py`** — confirmed **zero** SONNET/MODEL/ESCALATION
  references in any of the three. PLAN.md's Task 6 focus item asking to check these can be
  closed with "checked, nothing there" — no task needed.
- **`.planning/intel/constraints.md:51`, `.planning/HANDOFF.json:36`, `.planning/STATE.md:109,
  217, 233`, `.planning/ROADMAP.md:87`, `.planning/debug/bug-23-...md:105`** — all historical
  record of PAST phases (16.5, 16.7, bug-23), correctly **out of scope** per repo convention
  (historical docs describe what was true at the time, not living config) — PLAN.md's Task 8 only
  touches the "Session Continuity" section of `STATE.md`, which is correct; do not touch the
  historical narrative lines above.
- **No other `.py`/`.js`/`.mjs`/`.json`/`.yaml`/`.md`/`.sh`/`.env.example` file outside
  `docs/reports` and `.planning/milestones` contains any of the 3 old names** beyond what
  PLAN.md's Task 1-8 already lists — full-repo grep (excluding `.venv`, `node_modules`, `.git`,
  `.planning/milestones`, `docs/reports`) confirms the survey is complete; no missed files.
- **`tests/n8n/researchRequestSponsorshipContract.test.mjs:21`** and
  **`tests/n8n/contactResearchChainRowFlow.test.mjs:68`** — both are **comment-only** mentions
  (`ANTHROPIC_SONNET_MODEL`/`ALLOW_SONNET_ESCALATION` respectively), no assertions reference the
  literal strings. Safe rename, zero logic risk — lower risk than PLAN.md's Task 5 framing
  ("baked model const name" / "comment + budget fixture") might suggest; these are pure prose
  edits.

## Net risk ranking for the planner

1. **Highest:** `tests/test_deploy_flag_overlay.py` — 10/13 functions touched, one genuine
   coverage-regression trap (§2, numeric-literal drift test loses its flag).
2. **High:** `tests/test_enabled_build_invariants.py` — 6/8 functions touched, needs one **new**
   test (judge-escalation-is-always-true) that doesn't exist in PLAN.md's task list at all.
3. **Medium, but precisely bounded:** frozen-fixture re-baseline — exactly 6/14 pairs, 3 named
   nodes, mechanical once traced (§1).
4. **Low:** builder internals (self-checking via `_flag_const`'s assert), `test_builder_flag_parity.py`
   (pure set-literal rename), the 4 env-setter test files (mechanical rename), the two `.mjs`
   comment-only files, `enabledResearchLaneFlow.test.mjs` (one-line `OVERLAY_FLAGS` shrink).
