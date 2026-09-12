---
phase: 71-a-held-new-person-lands-in-hubspot-with-one-reply
reviewed: 2026-09-12T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - operator-claude-plugin/scripts/held_queue.py
  - operator-claude-plugin/scripts/suggestion_declines.py
  - operator-claude-plugin/scripts/run_manifest.py
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - operator-claude-plugin/skills/review-triage/SKILL.md
  - operator-claude-plugin/tests/test_held_queue.py
  - operator-claude-plugin/tests/test_held_queue_facets.py
  - operator-claude-plugin/tests/test_suggestion_declines.py
  - operator-claude-plugin/tests/test_skill_sequence_coverage.py
  - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
  - operator-claude-plugin/tests/test_batch_finishes_composition.py
  - operator-claude-plugin/tests/test_unattended_pair_composition.py
  - operator-claude-plugin/tests/test_run_manifest.py
  - operator-claude-plugin/tests/test_preingest_match.py
  - operator-claude-plugin/tests/test_held_facet_render_composition.py
  - operator-claude-plugin/tests/test_review_triage_facets.py
  - operator-claude-plugin/tests/test_match_state.py
  - operator-claude-plugin/CHANGELOG.md
  - docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues
---

# Phase 71: Code Review Report

**Reviewed:** 2026-09-12
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 71 does three things: (1) stamps a `company_known` provenance dict onto a held
entry at persist time so the `new_person`/`needs_company` facet reads correctly cold,
without a per-sitting lookup; (2) replaces `held_queue.json`'s positional `row-N`
entries-map key with a stable identity key (`identity_keys`/`stable_key`), so a second
run's held row can no longer silently overwrite a first run's still-open entry, and so
`run_manifest.rows_to_resume`'s `confidence_held` lookup and a settled entry's
recorded verb (`create`/`skip`/`drop`) survive a row's freshly-minted, per-run
positional `row_id` changing across runs; (3) narrows both `held_queue.py`'s and
`suggestion_declines.py`'s forbidden-marker scans so a person or company literally
named "Grant"/"Token" can be persisted, while a genuine grant/token-shaped key or value
is still refused.

I traced the diff for every module against the whole file it lives in (not just the
hunks), re-derived the claimed import-cycle rationale for `held_queue.identity_keys`'s
function-scoped `import suggest_contacts` by hand (confirmed real: `extraction ->
preview -> preview_enrichment -> chunking -> run_manifest -> held_queue ->
suggest_contacts -> extraction`, a genuine cycle if that import were module-level),
checked the "merged row is a superset of the source row's identity fields" invariant
`stable_key`'s docstring leans on against `preingest.merge_enriched`'s actual
fill-not-overwrite policy (holds, because `company`/`firstname`/`lastname`/`email`
are none of them in `refreshable_contact_props()`), and ran the full plugin suite
(3032 passed, 5 skipped, no failures) plus the touched-file subset in isolation.

The two known live-UAT findings already triaged as todos (F71-1, shared
`run_manifest.json` positional-key accumulation across runs; F71-5, the ingest lane
dropping paid-for enrichment extras / `lv_linkedin_url` vs `linkedin_url` naming) are
NOT re-raised here — I hit both surfaces during the trace and they match what the
todos already describe. No new Critical/BLOCKER-level issue surfaced. Two Warnings and
one Info below are new to this phase's diff.

## Warnings

### WR-01: `company_spec` is claimed resumable across a fresh process but has no persistence path

**File:** `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:170, 200-202, 317, 748-756`

**Issue:** Step 5's own commentary says: *"`confirmed_domains` is step 2's (or, if it
ran, step 3's) value — in a fresh process re-derive it the same way, from
`match_state.load(match_run_id)`'s current classification and `company_spec`, never
assumed still in scope from an earlier turn."* This sentence treats `company_spec`
as re-derivable the same way `classified` is, but `company_spec` — the result of
`company_domain.to_envelope_spec` over the operator's company-confirm-table answers —
is never written to `match_state`, `run_state`, or any other durable store in this
skill. Only `classified` (via `match_state.save(match_run_id, classified)`) and
`match_run_id` (printed, and explicitly covered by its own "a fresh process must have
`match_run_id`" test) survive a session boundary. `company_spec` exists only as an
in-conversation Python variable minted at step 2.

Contrast with `match_run_id`, which `tests/test_enrich_before_ingest_skill_contract.py`
explicitly pins for the fresh-process case (`"a fresh process must have match_run_id to
pass to match_state.load — never ..."`). No equivalent test exists for `company_spec`,
and grepping the skill and its test contract turns up no code path that reconstructs it
from anything durable.

In a genuinely fresh process (this architecture's whole reason for existing — crash
recovery and cross-turn resume are first-class concerns throughout this codebase), a
literal execution of step 5's code sample would raise `NameError: name 'company_spec'
is not defined`. A cautious executor who instead defaults it to `None` degrades
silently: `preingest.confirmed_company_domains(classified, None)` still returns the
`step2_match`-derived domains (since those come from persisted `classified`), but
loses every `step2_company_row`-sourced domain — a held row whose only confirming
signal was a company-row confirm-table answer would misread `needs_company` instead of
`new_person`, with nothing in the transcript flagging that the seed is incomplete.

**Fix:** Either persist `company_spec` (e.g. fold it into the `match_state` document
alongside `classified`, or a small sibling file keyed by `match_run_id`), or rewrite
step 5's guidance to say plainly that `company_spec` does NOT survive a fresh process
and that `confirmed_domains` should be re-derived with `company_spec=None` in that
case — i.e. state the degradation instead of implying full re-derivability. Add a test
mirroring `test_the_persist_fence_...match_run_id...` for the `company_spec`-absent
case so the degraded (but safe) behavior is pinned rather than assumed.

### WR-02: `held_queue.identity_keys()` hardcodes the identity groups instead of reading `config/column_mapping.yaml`, with no parity test

**File:** `operator-claude-plugin/scripts/held_queue.py:306-367`

**Issue:** `identity_keys()`'s docstring states it derives "every satisfied
`config/column_mapping.yaml` `required_identity.any_of` group... in that file's own
priority order," but the implementation never reads the YAML — it hardcodes exactly
three groups (email, `firstname+lastname+company`, `linkedin_url`) in that literal
order. This happens to match the current YAML (`config/column_mapping.yaml:60-64`)
today, but nothing enforces that it keeps matching. Contrast with `extraction.py`,
which reads `required_identity.any_of` from the YAML at call time
(`extraction.py:174`), and with `n8n/code/columnMap.js`, which is pinned to the same
YAML by `tests/n8n/columnMapIdentityParity.test.mjs` per that YAML file's own header
comment ("Do not restate the groups anywhere else... pins `n8n/code/columnMap.js`
against it"). `held_queue.identity_keys()` is a third restatement of the same
groups, and it has no equivalent parity test.

If a future change widens or reorders `required_identity.any_of` (the same kind of
change Phase 61-03 already made once, adding `linkedin_url`), `held_queue.stable_key()`
would silently keep using the stale three-group definition — diverging from what the
ingest gate itself considers "the same person" — and nothing in the test suite would
fail to signal the drift.

**Fix:** Either read `required_identity.any_of` from `config/column_mapping.yaml` at
call time (mirroring `extraction.py`'s own resolution order), or add a parity test
(mirroring `columnMapIdentityParity.test.mjs`) that asserts `held_queue.identity_keys`'s
hardcoded group shape matches the YAML's current `required_identity.any_of` list, so a
future YAML change fails loudly here instead of silently.

## Info

### IN-01: `held_queue.save()`'s per-entry loop variable is misleadingly named `row_id`

**File:** `operator-claude-plugin/scripts/held_queue.py:664-727`

**Issue:** `for row_id, entry in entries.items():` inside `save()` still calls the
entries-map key `row_id`, but since D-71-04 that key is the row's *stable identity*
string (e.g. `"email::a@b.com"`, `"name::first|last|company"`, or the
`"source-position::<row_id>"` fallback) — not necessarily anything resembling a literal
row id. The variable name is accurate only for the fallback case. This is purely a
readability nit inherited from the pre-Phase-71 shape of the function; it has no
functional effect (confirmed by the full test suite passing, and by tracing every use
of the variable in the loop body, all of which treat it as an opaque map key).

**Fix:** Rename to `key` (matching `suggestion_declines.save()`'s own loop variable
name, which already uses `key` for the identical role) the next time this function is
touched. Not worth a standalone change.

---

_Reviewed: 2026-09-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
