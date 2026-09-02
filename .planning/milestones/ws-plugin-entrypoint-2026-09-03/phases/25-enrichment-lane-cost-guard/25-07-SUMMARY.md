---
phase: 25-enrichment-lane-cost-guard
plan: 07
subsystem: operator-claude-plugin (enrichment preview, the shared cost block, the enrichment skill)
tags: [preview, cost-guard, chunk-plan, unknown-never-zero, enrich-records-skill, amendment-7]
status: complete

requires:
  - operator-claude-plugin/scripts/preview.py (Phase 23 — the tabular lane's preview this plan adds a cost block to)
  - operator-claude-plugin/scripts/cost_guard.py (25-05 — estimate_batch, fetch_balances, compare, rate_table_age_days)
  - operator-claude-plugin/scripts/chunking.py (25-06 — ChunkPlan.chunk_count / row_counts / record_count, chunk_ceiling)
  - operator-claude-plugin/scripts/enrichment.py (25-04 — resolve_providers, FULL_WATERFALL, VIEW_REFUSAL)
  - 25-BLOCKERS.md §"View resolution" (amendment #7 wording and the live lists-scope verdict)
provides:
  - preview_enrichment.records_block / providers_block / cost_block / chunks_block / assemble_preview
  - preview_enrichment.zero_cost_estimate + TABULAR_COST_REASON (the tabular lane's real zero)
  - preview.tabular_cost_block(row_count) — the same helper, not a second one
  - operator-claude-plugin/skills/enrich-records/SKILL.md (auto-triggered and slash-invocable)
affects:
  - 26 (a retry preview renders through the same four blocks)
  - the milestone's requirement record — INGEST-04, DISPATCH-02, PREVIEW-02, PREVIEW-03 now complete

tech-stack:
  added: []
  patterns:
    - "the whole preview is PURE: balances arrive as an argument, so it renders in full when
       the status endpoint is unreachable — a guard that vanishes when the backend is down is
       not a guard"
    - "the reference date is a parameter (rate_age_days), never a wall-clock read at render
       time, so no rendered string can flake on a clock read twice"
    - "one cost_block() renderer imported by both lanes rather than two that can drift (D-16)"

key-files:
  created:
    - operator-claude-plugin/scripts/preview_enrichment.py
    - operator-claude-plugin/tests/test_preview_enrichment.py
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/tests/test_enrich_skill_contract.py
  modified:
    - operator-claude-plugin/scripts/preview.py
    - operator-claude-plugin/README.md
    - operator-claude-plugin/CHANGELOG.md
    - .planning/workstreams/plugin-entrypoint/ROADMAP.md
    - .planning/workstreams/plugin-entrypoint/REQUIREMENTS.md
    - .planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-CONTEXT.md

decisions:
  - "The shared cost block lives in preview_enrichment.py and preview.py imports it, not the
     reverse — the reverse would drag column_mapping.yaml and tabular.read_table into a lane
     that reads no file (D-23)."
  - "A list's record count renders as the word `unknown` with NO numeral anywhere in that
     block, asserted by a regex for any digit — not merely by the presence of the word."
  - "An unreadable balance's row is asserted to contain no cell equal to `0`; a readable zero
     and an unreadable balance are asserted to render as DIFFERENT text (D-17's banned
     'unreadable is falsy' shape avoided)."
  - "The new skill's manifest assertions live in their own test file because
     test_plugin_manifest.py is operator-held and uncommitted (D-24)."

requirements-completed: [INGEST-04, DISPATCH-02, PREVIEW-02, PREVIEW-03]

metrics:
  duration: ~55 min
  completed: 2026-07-31
  tasks: 3
  files: 10
  tests_added: 35
---

# Phase 25 Plan 07: Enrichment Preview & Cost Guard Surface Summary

**The block that makes a batch impossible to launch blind: four sections an operator reads
before approving — what is being enriched, which providers, what it will cost at most, and how
it will be split — where a list's count is the word `unknown` rather than a fabricated zero, an
unreadable balance says headroom could not be *confirmed* rather than that there is enough, and
the tabular lane's zero is a stated fact with its reason rather than an omitted block.**

## Commits

| Commit | Type | What |
|---|---|---|
| `79ca8d9` | feat | `preview_enrichment.py`, the shared cost block wired into `preview.py`, `test_preview_enrichment.py` (26 tests) |
| `3153591` | feat | `skills/enrich-records/SKILL.md`, README enrichment-lane section, plugin CHANGELOG entry, `test_enrich_skill_contract.py` (9 tests) |
| `0b69b2c` | docs | ROADMAP criteria 1 and 2, REQUIREMENTS INGEST-04, four requirement statuses, Phase 25 plan checkboxes |

No sibling executor was running. Every commit staged explicit paths, with
`git diff --cached --name-only` printed in the **same shell invocation** as the commit. No
`git add -A`, no `git add .`, no `git commit -a`. The operator's four in-flight 23-06 files
(`STATE.md`, `plugin.json`, `test_plugin_manifest.py`, `23-06-SUMMARY.md`) were not read-modified,
staged or committed, and **`STATE.md` was not touched**.

## Task 1 — the cost block, on both lanes

`preview_enrichment.py` renders four blocks and returns both the joined markdown and the
structured form, so the skill can print one and branch on the other.

| Block | What it renders | The failure it refuses |
|---|---|---|
| Records | the exact count for named IDs; the list name plus the word `unknown` for a list | a fabricated count for something the client never resolved (D-02, D-21) |
| Providers | the resolved selection, **every time**, including the full waterfall and none | a permissive default taking effect unseen (D-06) |
| Cost | per-provider credits vs credits remaining, the Anthropic dollar figure, the rate table's date **and its age** | a stale table reading as fact (D-08); an unreadable balance reading as zero or as healthy (D-10) |
| Chunks | chunk count and rows per chunk, always — including the one-chunk case | an omitted line being indistinguishable from no plan at all (PREVIEW-03) |

**Every function is pure.** Balances arrive as an argument and the reference date arrives as
`rate_age_days`, so nothing here reads a clock or a socket. That is what makes the
unreachable-backend case a rendering path rather than an error path: with every balance
unreadable the preview still shows the count, the selection, the estimate and the plan, and every
headroom cell reads **could not be confirmed**.

### The three assertions that carry the weight

- `test_a_list_input_preview_contains_no_numeric_record_count` — asserts `re.search(r"\d", block)
  is None` on the records block. Asserting merely that the word `unknown` is present would pass
  against a block that said "unknown (0 records)".
- `test_a_readable_zero_balance_and_an_unreadable_balance_render_as_different_text` — the two
  cost blocks are asserted **unequal**, and then each cell checked: `0` for the readable zero,
  `unknown — could not be read` for the unreadable one. D-17 bans "unreadable is falsy" because
  it passes against the defect.
- `test_the_tabular_lanes_preview_carries_a_cost_block` — `build_preview()`'s result must carry
  `cost_block` at all, and `test_the_tabular_cost_block_states_a_zero_with_its_reason` asserts
  `preview_enrichment.UNKNOWN` is **absent** from it. A real zero and an unread balance must not
  converge from either direction.

Plus `test_an_unreadable_balance_row_carries_no_zero_figure_for_that_provider`, which splits the
rendered row on `|` and asserts no cell equals `"0"`.

### Copy decisions the plan called out, honoured

- **"at most", never "will cost"** — asserted by a test, because 25-05's estimator deliberately
  prices Lusha at its first-time rate rather than its measured-zero re-enrich rate.
- **Apollo's `unknown` is the normal answer** (D-10a) — the block appends, only when Apollo is
  among the unknowns, that it exposes per-endpoint rate limits rather than a depleting credit
  pool and that this is "not a fault to fix". Copy presenting it as an exception state would be a
  standing false alarm on every run of the default waterfall.
- **The ceiling stays labelled PROVISIONAL** — the chunk block says so verbatim, with the reason
  (single-record, company-lane timings; the full-waterfall probe **B4** has not run). Asserted by
  `test_the_chunk_ceiling_is_labelled_provisional`.

The plan is **rendered, not recomputed**: `chunks_block` reads `plan.chunk_count` and
`plan.row_counts` off the very `ChunkPlan` `dispatch_plan` iterates, and a test builds a
`ChunkPlan` by hand to prove the renderer has no planning path of its own.

## Task 2 — the skill and the documentation

`skills/enrich-records/SKILL.md`: frontmatter fires on natural phrasing ("enrich these
companies", "run the waterfall on this list") and names the slash form, so it is one entry point
reachable two ways — **no `commands/` directory** (asserted).

The body is the conversation contract in order: endpoint and disarmed state **before any other
work** → config gate, refusal relayed as-is and stop → record IDs / list / **view refused with
`enrichment.VIEW_REFUSAL` verbatim** → provider override over the config default → chunk plan →
balances and estimate → preview → approval (declining sends nothing) → arming, `"arm the
enrichment"`, conversation-scoped and written nowhere → dispatch the approved plan → report **at
chunk granularity only**, naming the failed batch as the thing to hand a retry.

The refusal wording is asserted equal to the module constant under whitespace/markdown
normalization, so the sentence cannot drift into a fourth phrasing.

README gains an enrichment-lane section covering what can be named, why a list's count is
`unknown` and that this is not zero, how provider selection defaults and how to override it for
one batch, what each cost verdict means and **who can fix which unknown** (nobody, for Apollo; an
admin, for Lusha/ZoomInfo), and how chunking appears with the provisional ceiling stated. The
endpoint table now names `hubspot/backend-status` as the only source of balances, and the layout
lists the four new scripts and the second skill.

Two accuracy fixes made while there (Rule 1, documentation bugs): the cost-posture paragraph
claimed rates were "derived from the measured rates in this repo (`scripts/enrichment_cost_ledger.py`,
`docs/`)", which reads as a runtime read of a repo doc and is exactly what **D-09** forbids — it
now names the dated plugin-local `config/cost_rates.json`; and the status banner still said "one
lane implemented".

## Task 3 — the two requirement amendments

**ROADMAP criterion 2, amendment #2 (D-05).** Reworded to state what shipped: the POST carries an
explicit selection resolved from a per-batch override over an **admin default that ships as the
full waterfall**, that selection is stated in the preview before approval every time, and the
backend enables no provider when a request carries no recognizable selection. The italic note
records that the original sentence folded the backend's fail-closed behaviour and the client's own
default together, and that the default-on behaviour was chosen deliberately with the preview
display as its mitigation. **The old phrase is gone** — `grep -c 'no provider is enabled and no
credits burn'` → **0**, and the note paraphrases rather than quoting it, so the grep stays honest.

**ROADMAP criterion 1 + REQUIREMENTS INGEST-04, amendment #7.** `25-BLOCKERS.md` records views
scoping out, so both were reworded to **lists + record IDs**, with the view refused. The wording
applied:

> **ROADMAP criterion 1:** "Naming existing HubSpot records — record IDs or a HubSpot list —
> produces an enrichment request with no row structuring involved, previewed and approved through
> the same gate as any other batch." Note: *a saved view is refused with a redirect to saving it
> as a list, because HubSpot exposes no public API for views. Lists themselves are supported and
> were probed live on 2026-07-31 — `crm.lists.read` granted, HTTP 200, 102 members read — so this
> is the small amendment (views only), not the large one. Seventh accepted requirement amendment
> in this milestone; INGEST-04 is reworded to match.*

> **INGEST-04:** "Operator can name existing HubSpot records (a HubSpot **list** or **record
> IDs**) to enrich, with no row structuring involved." Note carries `enrichment.VIEW_REFUSAL`
> **verbatim**, the reason (no public view API; a view name colliding with a list name would
> enrich the wrong record set with no error), the live lists-scope evidence, and the pointer to
> `25-BLOCKERS.md` §"View resolution".

Recorded in the same shape as amendments #3 and #4 already are in this file (an italic note on the
criterion/requirement itself, naming its ordinal and where the decision lives) — consistent with
HANDOFF §3.

**Requirement statuses.** INGEST-04, DISPATCH-02, PREVIEW-02 and PREVIEW-03 are marked complete
in both the checklist and the traceability table, each confirmed against a landed implementing
plan: INGEST-04 (25-03 backend + 25-04 client + this plan's skill), DISPATCH-02 (25-04's envelope
and dispatch), PREVIEW-02 (25-05's arithmetic + this plan's rendering), PREVIEW-03 (25-06's plan +
this plan's chunk block). The Phase 25 plan checkboxes and the plan count (**7/7**) were updated
to match the six summaries on disk plus this one.

Edits were scoped, not wholesale: 7 `### Phase 2[3-9]` sections before and after, Phase 25 still
carries its Goal / Depends on / Requirements lines and **exactly four** criteria, and the
`| INGEST-04 | Phase 25 |` traceability row survives.

## Deviations from Plan

### 1. [Rule 3 — blocked] Task 2's manifest-test criterion could not be satisfied as written

- **Found during:** Task 2. The criterion says to extend "the same manifest test Phase 23
  established" to cover the new skill. `operator-claude-plugin/tests/test_plugin_manifest.py` is
  **operator-held and uncommitted** mid-23-06 and hardcodes a single `contact-upload` SKILL_PATH.
- **Fix:** the identical assertions live in a new file,
  `operator-claude-plugin/tests/test_enrich_skill_contract.py` — frontmatter parses and carries
  name + description, every `scripts/<name>.py` the body names exists on disk, no `commands/`
  directory — scoped to `skills/enrich-records/`. No glob was widened onto the held file and the
  held file was not read-modified. Folded into `25-CONTEXT.md` as **D-24**.

### 2. [Rule 1 — bug] The first skill draft violated amendment #4's ICP/tier ban

- **Found during:** Task 2 verification. `test_report_enrichment.py::test_no_operator_facing_
  skill_body_mentions_icp_or_tier_not_even_a_placeholder` rglobs `skills/` and fired on the
  sentence "merge policy and ICP scoring all live in n8n" — a true statement about the backend,
  and still a violation: the client must name neither a tier nor a placeholder for one.
- **Fix:** "merge policy and scoring"; the frontmatter's "score these accounts" phrasing changed
  to "research these accounts" for the same reason. Folded into `25-CONTEXT.md` as **D-25**.

### 3. [Rule 1 — documentation bug] README claimed a runtime read of repo cost docs

Described above under Task 2. `config/cost_rates.json` is plugin-local and dated; naming
`scripts/enrichment_cost_ledger.py` and `docs/` as the runtime source is the coupling D-09 exists
to prevent, and a reader following that sentence would have re-introduced it.

### TDD gate compliance

Task 1 carries `tdd="true"`. **There is no separate `test(...)` RED commit.** The implementation
and its tests were written in one editing pass and landed in `79ca8d9`. Recorded rather than
manufactured — re-staging already-passing tests as a retroactive RED commit is theatre, and a
fabricated gate is worse than a missing one (the same call, and the same reasoning, as 25-04 and
25-06). Every behaviour the RED phase would have pinned is present as a test, including all four
the plan names explicitly: unreadable-vs-readable-zero rendering differently, the preview rendering
in full when the balance fetch failed, a list preview carrying no numeric count, and the tabular
lane carrying a cost block. Two assertions did fail on first run and were **corrected as tests**,
not by weakening them: one asserted a phrase absent from a block whose own explanatory sentence
legitimately contains it, and one compared un-normalized markdown that a line wrap had reflowed.

## Test counts

Baselines were re-verified by me before writing anything, and matched the brief exactly.

| Suite | Baseline (verified) | Final | Delta | Attribution |
|---|---|---|---|---|
| plugin (`operator-claude-plugin/tests`) | **619** | **654** | +35 | all mine — 26 in `test_preview_enrichment.py`, 9 in `test_enrich_skill_contract.py` |
| repo (`.venv/bin/python -m pytest -q`) | **1494 passed, 1 skipped** | **1529 passed, 1 skipped** | +35 | all mine |
| node (`node --test tests/n8n/<file>.test.mjs`, file form, summed) | **506 pass / 0 fail** | **506 pass / 0 fail** | 0 | this plan touches no n8n artifact |

Measured directly: `pytest operator-claude-plugin/tests/test_preview_enrichment.py -q` → **26
passed**; `test_enrich_skill_contract.py` → **9 passed**. `node --test
tests/n8n/enrichment.test.mjs` → **44 pass / 0 fail**. Zero failures in any final run. The known
1 ms `mergeContacts.test.mjs` timestamp flake did not fire, **no test was re-run to obtain a
green**, and nothing added here reads a wall clock at all — the rate-table age is a parameter
precisely so a rendered string cannot depend on one.

## Guard status

- **`_EXPECTED_SEND_SHAPED` is byte-identical — the allowlist was not appended to.**
  `shasum -a 256 operator-claude-plugin/tests/test_retry_reuses_dispatch.py` =
  `26bba4f2a7f71401e095846a81abc39119a5e87e48f254cb4f71721d2e2f97ad`, matching the brief.
  **`preview_enrichment.py` makes no network call and takes no `transport` parameter at all** —
  the preview is pure and balances are injected; the only status read happens in the module's
  `__main__` block, through `cost_guard.fetch_balances()`, which already delegates to the one
  allowlisted `backend_status` client.
- **No live network call** from any verification. The autouse `no_network` guard (which blocks
  `requests.get` too) was neither widened nor bypassed.
- **All 8 `n8n/*.json` disarmed** — `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → **0**.
  This plan touched **no file under `n8n/`**.
- **Nothing armed, deployed or activated. No package installed** (T-25-SC holds trivially).
- **D-18's broken `vars()`/`inspect.signature` walk was not copied** anywhere. `preview_enrichment.py`
  defines no `armed` parameter — it cannot send.
- Branch `feat/v0.6-plugin-entrypoint` throughout; no switch, merge or rebase.

## Known Stubs

None. No placeholder, no hardcoded empty value flowing to a rendered surface, no skipped test, no
unrun `<verify>`.

## Threat Flags

None. No new network egress (the preview adds none; its `__main__` reuses the existing status
read), no new credential surface, no package installed. The plan's own register is mitigated as
designed: T-25-05 by the per-cell no-zero assertion plus the different-output assertion; T-25-26
by the always-rendered selection with a test across all three selection shapes; T-25-27 by the
digit-free list block; T-25-22 by the pure renderer proven against an all-unreadable balance map;
T-25-17 by the skill relaying the config gate's refusal as-is and never surfacing a raw error;
T-25-01 by the arming step being stated as off, conversation-scoped, and written nowhere.

## Phase 25 success criteria — where they stand

| # | Criterion (as amended) | Met? |
|---|---|---|
| 1 | Record IDs or a list produce an enrichment request, previewed and approved through the same gate; a view is refused | **Yes** — backend 25-03, client 25-04, operator surface here |
| 2 | The POST carries an explicit selection resolved from an override over the full-waterfall default, always stated in the preview; the backend enables nothing on an unrecognized selection | **Yes** — 25-04 + this plan's providers block |
| 3 | Every preview on both lanes shows an estimated provider-credit and Anthropic cost from measured rates, warns against remaining credits, and reads `unknown` rather than assuming headroom | **Yes** — 25-05's arithmetic, this plan's rendering, both lanes |
| 4 | A batch above the size limit is shown already split before approval, and dispatch sends exactly that plan | **Yes** — 25-06's plan object, rendered here, iterated with no splitting path of its own |

**All four criteria are met in code, and the phase's plans are all executed.** Two things remain
open and neither is a criterion:

1. **The live proof 25-06 also flagged (still owed, needs no write):** one armed-window POST
   naming `New Targets.xlsx` (contacts, list id 15, 102 members) should return the **oversize
   refusal**, not a 200 and not a hang. It exercises the nested list envelope end to end and burns
   zero provider credits. Agent tooling here is classifier-blocked from arming, so this is an
   operator gate.
2. **The chunk ceiling is PROVISIONAL.** Probe **B4** — the full-waterfall timing fire — has not
   run, so `max_records_per_chunk: 2` is a derivation from single-record, company-lane runs. Every
   artifact carrying it says so, including the rendered chunk block, and nothing in this phase
   presents it as measured. It is not a criterion, but it is the number the criterion-4 mechanism
   is calibrated against.

**`STATE.md` was deliberately not updated** — the operator holds it uncommitted mid-23-06, and
this workstream's `state.update-progress` is known to mangle it. It owes a Phase 25 position and
plan-count update once the operator commits.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/preview_enrichment.py` — FOUND
- `operator-claude-plugin/tests/test_preview_enrichment.py` — FOUND
- `operator-claude-plugin/skills/enrich-records/SKILL.md` — FOUND
- `operator-claude-plugin/tests/test_enrich_skill_contract.py` — FOUND
- `operator-claude-plugin/scripts/preview.py` — FOUND (modified)
- `operator-claude-plugin/README.md`, `CHANGELOG.md` — FOUND (modified)
- `.planning/workstreams/plugin-entrypoint/ROADMAP.md`, `REQUIREMENTS.md` — FOUND (modified)
- commit `79ca8d9` — FOUND · commit `3153591` — FOUND · commit `0b69b2c` — FOUND

---
*Phase: 25-enrichment-lane-cost-guard*
*Completed: 2026-07-31*
