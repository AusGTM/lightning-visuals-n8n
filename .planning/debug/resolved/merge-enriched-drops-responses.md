---
status: resolved
trigger: "FINDING 2"
created: 2026-08-28
updated: 2026-08-28
---

# merge-enriched-drops-responses

## Trigger (verbatim)

`FINDING 2` — the operator's shorthand for the second finding of the Phase 53 operator walk,
recorded in `.planning/phases/53-operator-openable-write-grant/53-WALK-RECORD.md`.

## Symptoms

Not gathered by questioning — **measured during the walk on 2026-08-28** against one real
record. Correct any of this if it reads wrong.

**1. Expected behavior.**
`enrich-before-ingest` step 5 runs the provider waterfall over rows not yet in HubSpot, then
merges what the waterfall returned onto those rows, so the enriched row carries the new fields
(most importantly an `email`, without which the email-keyed ingest lane holds the row). The
skill documents the call as:

```python
outcome = chunking.dispatch_plan(plan, providers, True, cfg)
merge_report = preingest.merge_enriched(unmatched_rows, outcome.responses)
```

**2. Actual behavior.**
Every row lands in `merge_enriched`'s `unanswered` group and gains nothing. The provider data
is discarded silently. No exception, no warning, no non-zero exit.

**3. Error messages.**
None — and that is the defect's most dangerous property. It fails into `unanswered`, whose own
docstring defines it as *"a row nothing is known about at all"*, a group that exists
specifically to distinguish "we could not look" from "we found nothing" (T-38-01). A complete,
correct, paid-for provider answer is filed under the label meaning its opposite. The operator
reads "nothing known", concludes the providers found nothing, and never learns otherwise.

**4. Timeline.**
Unknown — first observed 2026-08-28, on the first end-to-end run of this flow ever performed.
Phase 53's operator walk was an outstanding blocking checkpoint until that day, so nobody had
run enrich-before-ingest through to a merge before. Whether this ever worked is an open
question for the investigation, not an assumption.

**5. Reproduction — measured, both ways, same input data.**

| Call | `unanswered` | merged `email` |
|---|---|---|
| As the skill documents it (`outcome.responses`) | **1** | **`None`** |
| Flattened `[i for chunk in raw for i in chunk]` | 0 | `josh@seriesfutsal.com` |

Concrete case: contact row `row-1` (Joshua Fusco / Series Futsal Victoria, one chunk).
The backend answered correctly — `action: "proposed"`, `mode: "propose"`, and a `properties`
map carrying `email josh@seriesfutsal.com` (confidence 85, `human_review_required`),
`jobtitle League Commissioner`, `seniority`, `city South Morang`, `state Victoria`,
`country Australia`, `hs_country_region_code AU`, `lusha_contact_id`.

## Suspected mechanism (hypothesis to test, NOT a conclusion)

`chunking.dispatch_plan` appears to return a list of PER-CHUNK LISTS. `preingest.merge_enriched`
builds its `row_id` index with:

```python
row_id = item.get("row_id") if isinstance(item, dict) else None
if row_id is None:
    continue
```

so a list item yields `row_id = None` and is skipped. The index ends empty, and the
walk-the-rows loop then files every row as `unanswered`.

If that is right, the interesting question is not the mechanism but the CONTRACT: which side is
wrong — `dispatch_plan` returning nested, `merge_enriched` expecting flat, or the SKILL
documenting a call that matches neither? Answer that before fixing, because the fix differs.

## Investigation constraints

- **Read-only where possible.** The defect reproduces with a canned response fixture; it needs
  no live provider call, no n8n execution, and no HubSpot write. Do NOT spend credits to
  re-observe something already measured.
- **Do not "fix" it by flattening at the call site** without first establishing which side owns
  the contract. A caller-side flatten in one skill leaves every other caller broken.
- **Check every caller of both functions** before choosing. `enrich-before-ingest` is the flow
  that surfaced it; it is very unlikely to be the only one.
- **The silent-failure behaviour is arguably a second, separable defect.** Even with the
  contract fixed, `merge_enriched` filing an unparseable response shape as `unanswered` rather
  than raising is what made this invisible. Consider whether a shape it cannot index should be
  a `MergeError` — it already raises one for a duplicate `row_id`, so there is precedent.
- Test commands: `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` (glob form).
- Plugin tests live under `operator-claude-plugin/tests/` and have an autouse `no_network`
  fixture; the repo suite is `tests/`.

## Why this matters (sequencing)

Recorded in `59-CONTEXT.md` D-59-08: the operator's resolve-and-propose ruling must NOT ship
before this is fixed. A propose flow built on a merge that drops provider answers will propose
from nothing and confidently report "nothing known" about a fully-answered row — the assistive
path would inherit the data loss and make it more persuasive.

## Current Focus

reasoning_checkpoint:
  hypothesis: "`chunking.dispatch_plan().responses` is, by design, a tuple of ONE RAW BODY PER CHUNK (each may itself be an n8n array-wrap — a list — or a bare dict). `preingest.merge_enriched` is, by design, a flat-list-of-per-row-dicts consumer. Both are correctly implemented and match every other caller in the repo. The SKILL.md-documented call in `enrich-before-ingest` step 5 is the ONLY caller that skips the flatten normalization every other caller performs, and that omission — not a contract mismatch between the two functions — is the root cause."
  confirming_evidence:
    - "`preingest.rerequest_unanswered` (same module, same endpoint, calls the SAME `dispatch_plan`) already flattens before calling `merge_enriched`: `new_items.extend(body if isinstance(body, list) else [body])` for `body in outcome.responses`, with a docstring citing `fetch_matches` as prior art for the same normalization (preingest.py:624-628)."
    - "`preingest.fetch_matches` (the match-lane sibling endpoint) performs the identical array-wrap normalization at its own layer: 'the deployed webhook answers array-wrapped, a one-element list — n8n's normal firstIncomingItem behaviour... Accept both shapes' (preingest.py:152-158), and `match_batch` then `.extend()`s (not `.append()`s) each chunk's normalized items into one flat `responses` tuple before `classify_matches` walks it (preingest.py:226)."
    - "`report_enrichment.build_sync_report(body)` docstring states explicitly: '`body` is whatever `enrichment.dispatch_enrichment` returned for that chunk: normally a JSON array... ONE item per row in the chunk... a bare object for a caller that still hands one row un-wrapped' (report_enrichment.py:245-256) — confirms `DispatchOutcome.responses` elements are per-chunk raw bodies, list-or-dict, by design."
    - "The same list-or-dict normalization idiom (`body if isinstance(body, list) else [body]`) already appears independently in 5 places in this codebase (backend_status.py:68, report_enrichment.py:267, report.py:214, preingest.py:156, preingest.py:628) — an established, repeated convention, never centralized into a shared helper, so a 6th inline occurrence (in the SKILL.md) is consistent with repo style, not a new abstraction."
    - "Enumerated every real caller of `dispatch_plan` (chunking.py, grep-confirmed): `preingest.rerequest_unanswered` (flattens correctly), `scheduled_arm.py` (uses `.responses` only for raw per-chunk audit JSON, never indexes by row_id, unaffected), and the two SKILL.md-documented call sites (`enrich-records` — feeds `outcome.responses` into `report_enrichment.build_sync_report` per-chunk, which itself normalizes internally, correct; `enrich-before-ingest` — feeds `outcome.responses` STRAIGHT into `merge_enriched`, the one broken site)."
  falsification_test: "If `dispatch_plan` were changed to return a genuinely flat `responses` tuple (one dict per row, not per chunk), `scheduled_arm.py`'s `dispatch_result=list(dispatch_outcome.responses)` audit output and `report_enrichment.build_sync_report`'s per-chunk docstring contract would both become wrong simultaneously — proving `dispatch_plan`'s current shape is the one every other consumer is built against, not an accident."
  fix_rationale: "Add the exact flatten step already used in `rerequest_unanswered` to the `enrich-before-ingest` SKILL.md's documented call, so the ONE broken caller matches the pattern the other three already follow. Separately, harden `merge_enriched` to raise `MergeError` on a response item that isn't a dict (today it silently treats it as `row_id=None` and skips) — precedent: it already raises `MergeError` for a duplicate `row_id`, and a nested-list item is exactly as unsafe to skip silently as a duplicate is to pick arbitrarily. This targets the root cause (missing normalization at one call site) AND the amplifying defect (silent misclassification as `unanswered` instead of a loud failure) without touching the two correctly-matched contracts."
  blind_spots: "Have not run the flow against a live n8n instance post-fix (orchestrator constraint: reproduces offline, no live re-observation needed/wanted). Have not exhaustively grepped every markdown file that might paraphrase this call outside the two SKILL.md files and the historical WALK-RECORD/RESEARCH docs (those are point-in-time narrative records, not live contract docs, and are intentionally left unedited)."
  candidate_causes:
    - "code: enrich-before-ingest SKILL.md's documented step-5 call omits the flatten normalization every other caller of dispatch_plan().responses performs before indexing by row_id"
    - "code (secondary/amplifying): merge_enriched's index-build loop treats 'item is not a dict' identically to 'item is a dict with no row_id', silently discarding the former instead of raising — this is what turned a caller bug into total, silent data loss instead of a loud, immediate failure"
  and_gate: "no — the two candidate causes are not jointly required to reproduce the reported symptom (the SKILL.md omission alone fully reproduces FINDING 2), but both are being fixed: the first is the actual root cause, the second is a real, separable defect per orchestrator constraint 4 that would let a FUTURE caller reproduce this same silent-data-loss failure mode even after the first fix lands"
test: applied both fixes; ran full existing test_preingest_merge.py suite plus new regression tests reproducing the exact nested-response shape from the walk; ran the fix-acceptance guardrail (5 signals) including revert-and-reconfirm via `git stash`
expecting: existing tests stay green (they already pass merge_enriched flat lists directly); new tests confirming MergeError now raises on a non-dict item, and confirming the SKILL.md documents the flatten step, both pass; guardrail accepts
next_action: DONE (self-verified). Awaiting operator confirmation per request_human_verification checkpoint below — no further debugger action until the operator responds.

## Evidence

- timestamp: 2026-08-28 — measured live during the Phase 53 walk. Same input, two call shapes: as documented `unanswered: 1` / email `None`; flattened `unanswered: 0` / email `josh@seriesfutsal.com`. Full detail and the raw backend response in `53-WALK-RECORD.md` FINDING 2.
- timestamp: 2026-08-28 — with the flatten applied, the rest of `merge_enriched` behaved correctly: the operator's longer `jobtitle` was kept over the provider's shorter one and recorded in `conflicts` (fill-not-overwrite working), and 11 non-canonical keys were dropped and reported in `dropped_property_keys` rather than silently widened. So the defect is isolated to the index-build step, not the merge logic.
- timestamp: 2026-08-28 — active plugin is 0.18.0; `grep -c proposed` is 17 in both 0.18.0's and the repo's `preingest.py`, so this is NOT version skew between the installed plugin and the repo.
- timestamp: 2026-08-28 — enumerated every caller of `chunking.dispatch_plan` repo-wide (grep for `dispatch_plan(`, excluding tests): `preingest.rerequest_unanswered` (preingest.py:621), `scheduled_arm.py:226`, and two SKILL.md-documented calls (`enrich-records/SKILL.md:265`, `enrich-before-ingest/SKILL.md:295`). Only `enrich-before-ingest`'s documented call feeds `outcome.responses` straight into `merge_enriched` without flattening; `rerequest_unanswered` flattens first (preingest.py:624-630, `body if isinstance(body, list) else [body]`), `scheduled_arm.py` only uses `.responses` for raw per-chunk audit JSON (never indexes by row_id), and `enrich-records/SKILL.md` feeds each per-chunk response into `report_enrichment.build_sync_report`, which normalizes list-or-dict internally (report_enrichment.py:265-267). Confirms exactly one broken caller, not a two-sided contract mismatch.
- timestamp: 2026-08-28 — `report_enrichment.build_sync_report`'s docstring (report_enrichment.py:245-256) states explicitly that `DispatchOutcome.responses` elements are raw per-chunk bodies — "normally a JSON array... a bare object for a caller that still hands one row un-wrapped" — confirming `dispatch_plan`'s per-chunk-list return shape is intentional, documented (there, not in `chunking.py`'s own dataclass docstring), and matches n8n's own `respondWith: allIncomingItems` behavior, not a bug.
- timestamp: 2026-08-28 — the same list-or-dict flatten idiom (`body if isinstance(body, list) else [body]`) already appears independently 5 times in this codebase (backend_status.py:68, report_enrichment.py:267, report.py:214, preingest.py:156 `fetch_matches`, preingest.py:628 `rerequest_unanswered`) — an established, repeated, never-centralized convention. Root cause narrows to: the SKILL.md's documented call is the one place this convention was omitted.
- timestamp: 2026-08-28 — checked the currently ACTIVE installed plugin version before writing the checkpoint: it is now `0.19.0` (not `0.18.0` as the orchestrator constraints stated — that was true earlier in this task's lineage but the install has since moved; `~/.claude/plugins/installed_plugins.json` shows `installPath` at `.../0.19.0`, `lastUpdated: 2026-08-26`, and the repo's own `.claude-plugin/plugin.json` already reads `0.19.0`). The installed 0.19.0 cache's `skills/enrich-before-ingest/SKILL.md` line 296 still carries the UNFLATTENED `merge_enriched(unmatched_rows, outcome.responses)` call — this fix exists only in the repo working tree (uncommitted) and has not reached the installed/active plugin surface. An operator re-running `enrich-before-ingest` through their normal installed plugin right now would still hit FINDING 2, even though the repo fix is correct and verified. Per project memory (`plugin-install-traps`, `plugin-release-requires-version-bump`), reinstalling does not refresh the marketplace clone — this needs a version bump + CHANGELOG cut + republish before the operator's live surface picks it up. That release step is OUT OF SCOPE for this debug task and is called out separately in the checkpoint rather than performed here.
- timestamp: 2026-08-28 — offline replay reconstructing the exact measured FINDING 2 case (row-1 / Joshua Fusco / Series Futsal Victoria — action `proposed`, mode `propose`, properties carrying `email josh@seriesfutsal.com`, `jobtitle`, `seniority`, `city`, `state`, `country`, `hs_country_region_code`, `lusha_contact_id`, source row's own longer `jobtitle "League Commissioner"`), run through the corrected SKILL.md step-5 code (flatten, then `merge_enriched`): `unanswered: 0`, `email: josh@seriesfutsal.com` — reproduces the walk's own "Flattened" table row exactly (`unanswered 0` / `josh@seriesfutsal.com`). Also confirmed `jobtitle` stayed "League Commissioner" (kept, recorded in `conflicts` against the provider's shorter "Commissioner") and the 6 non-canonical keys were dropped and reported — matches the walk's "11 non-canonical keys dropped and reported" / "fill-not-overwrite working" observations. The pre-fix shape, run through the now-hardened `merge_enriched`, raises `MergeError` immediately instead of the old silent `unanswered:1`/`email:None` — the two fixes together replace the silent-loss path with either "flattened and correct" or "loudly refused," never silent loss.

## Eliminated

- hypothesis: version skew between installed plugin 0.18.0 and the repo — eliminated 2026-08-28, `proposed` handling is identical in both (17 references each), and the repo's only `write_grant.py` delta is Phase 54's MEASURED→PROJECTED label change.
- hypothesis: the backend failed to enrich — eliminated 2026-08-28, the raw response carries a full `properties` map including the email. The loss is entirely client-side.

## Resolution

root_cause: |
  enrich-before-ingest/SKILL.md step 5 was the ONLY caller of chunking.dispatch_plan that
  skipped the flatten-normalization every other caller of the same endpoint performs.
  dispatch_plan(...).responses is one raw body PER CHUNK (each possibly array-wrapped by n8n);
  merge_enriched consumes a FLAT list of per-row dicts. Both functions were correct; the
  documented call site was not. A second, separable defect made it invisible: merge_enriched
  skipped non-dict items rather than raising, so the mismatch filed every row as `unanswered`
  -- the group meaning "nothing is known about this row" -- with no error at all.
  Present in every shipped version, 0.11.1 through 0.19.0; survived because Phase 53's
  operator walk on 2026-08-28 was the first end-to-end run of this flow ever performed.
fix: |
  1. SKILL.md step 5 flattens outcome.responses before merging, using preingest.
     rerequest_unanswered's existing idiom for the same endpoint.
  2. merge_enriched raises MergeError on a non-dict response item (precedent: it already
     raised for a duplicated row_id). Nothing is merged when it raises.
  3. chunking.DispatchOutcome.responses documents its per-chunk-raw-body contract.
  Released as plugin 0.20.0 -- the fix is inert until the installed plugin carries it.
verification: |
  1626 plugin tests, 3230 repo tests, 776 node tests green, verified independently by the
  orchestrator as well as the debug session. Revert-and-reconfirm reproduced FINDING 2 exactly
  before the fix, green after. Offline replay of the measured case (row-1 / Joshua Fusco /
  Series Futsal Victoria, the exact backend response from 53-WALK-RECORD.md) yields
  unanswered: 0, email: josh@seriesfutsal.com -- matching the walk's own flattened row.
  Mutation testing skipped: no Python mutation tool configured in this repo (logged, not
  silently skipped).
files_changed: |
  operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  operator-claude-plugin/scripts/preingest.py
  operator-claude-plugin/scripts/chunking.py
  operator-claude-plugin/tests/test_preingest_merge.py
  operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
  operator-claude-plugin/.claude-plugin/plugin.json (0.19.0 -> 0.20.0)
  operator-claude-plugin/CHANGELOG.md (0.20.0 entry + retroactive, incomplete 0.19.0 entry)
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/scripts/chunking.py
  - operator-claude-plugin/tests/test_preingest_merge.py
  - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
