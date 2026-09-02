---
phase: 62-suggest-the-contacts-nobody-named
verified: 2026-09-02T00:04:28Z
status: gaps_found
score: 12/13 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "A suggestion round may spend LESS than the priced per-company cap; it may never spend more (D-62-12, SUGGEST-05) — the round's own stated design rule, and the one place the cap is applied enforces it"
    status: failed
    reason: >
      Live-reproduced (not inferred): `suggest_contacts.synthesise_rows(company, people,
      fetched_url, per_company_cap)` is the SOLE function that applies the per-company cap
      (62-01-PLAN.md line 84's own contract: "emits at most `per_company_cap` records").
      It slices with a bare `people[:per_company_cap]` and performs no validation.
      `per_company_cap=None` returns ALL discovered people (no cap at all — confirmed 5/5
      rows against a 5-person fixture); `per_company_cap=-1` truncates from the wrong end
      (4/5 rows) instead of refusing. `skills/suggest-contacts/SKILL.md` step 3 states the
      refusal rule in prose only ("A cap above the grant's priced cap is refused, naming the
      number... it may never spend more") — no function anywhere (`write_grant.py`,
      `cost_guard.py`, `suggest_contacts.py`) compares the operator's chosen cap against
      `figures["suggestion_allowance"]["priced_cap"]`, and nothing validates the type/range
      of the cap before it reaches the slice. The production path here is an LLM
      orchestrator following SKILL.md prose at runtime, so "the cap silently arrives as
      None or a bad value" is a plausible failure of the actual mechanism, not a contrived
      edge case. This is a direct violation of the phase's own stated cost-safety
      invariant, first surfaced as Critical (CR-01) plus Warning (WR-01) in
      `62-REVIEW.md` and reproduced independently here.
    artifacts:
      - path: "operator-claude-plugin/scripts/suggest_contacts.py:158-195"
        issue: "synthesise_rows() has no type/range guard on per_company_cap; None uncaps entirely, negative truncates from the wrong end — contrast write_grant.envelope()'s own suggestion_cap handling a few lines away, which validates and falls back to PRICED_CAP on anything else"
      - path: "operator-claude-plugin/scripts/write_grant.py"
        issue: "envelope() validates and prices a fallback-safe suggestion_cap at grant-open time, but nothing threads that priced ceiling forward to a runtime comparison against the operator's chosen per_company_cap at synthesise_rows() call time"
    missing:
      - "A validation guard in synthesise_rows (or a wrapper called immediately before it) that raises on a non-int or negative per_company_cap rather than silently uncapping or mis-truncating — mirrors the CR-01 fix suggestion in 62-REVIEW.md"
      - "A small pure function (suggest_contacts.py or write_grant.py) that compares the operator's chosen cap against the grant's figures['suggestion_allowance']['priced_cap'] and returns a code-enforced refusal when the chosen cap exceeds it — today this rule exists only as SKILL.md prose for the LLM orchestrator to follow"
      - "Regression tests for per_company_cap=None (must raise, never uncap) and a negative value (must raise, never truncate from the wrong end) — test_synthesise_rows_honors_per_company_cap only proves the happy path"
human_verification:
  - test: "A real company's sitemap yields a usable people page on a live racing-club-shaped site"
    expected: "The sitemap-ladder rung resolves a people/board/team page and names at least one person, mirroring UAT 2.4's precedent (9/9 directors on gctc.com.au)"
    why_human: "url_fallback.py is pure string-building with no I/O by construction (VALIDATION.md manual-verification row 1) — the unit suite proves the ladder logic and the host-bound guard, never whether a given site's sitemap actually lists a people page. Requires a live plugin sitting with a real web_fetch."
  - test: "Stage 1 → stage 2 handoff on a real discovered person (name+company → Lusha search-and-enrich → proposal)"
    expected: "A person named by the ladder with no email resolves through identity group 2, the waterfall fills email/phone, and the row lands as a proposal (or HELD if still emailless) — never a silent write"
    why_human: "Requires a real page fetch (plugin-side web_fetch) followed by a real Lusha credit spend; neither runs in the stub-transport test suite (VALIDATION.md manual-verification row 2)."
  - test: "The priced ceiling is not exceeded in a real sitting"
    expected: "Actual page fetches and provider credits spent land at or under the quoted worst-case ceiling shown at grant-open"
    why_human: "The ceiling arithmetic is unit-tested, but 'the operator saw a number and the round stayed under it' is an end-to-end property of a live sitting (VALIDATION.md manual-verification row 3). This item is now also the acceptance test for the CR-01 fix once landed — a real sitting after the fix should demonstrate a bad/omitted cap cannot silently blow the ceiling."
---

# Phase 62: Suggest the Contacts Nobody Named — Verification Report

**Phase Goal:** Suggest the contacts nobody named — An enriched company with nobody at it is
not a lead. After a company batch, the operator is offered contacts worth enriching, chosen by
role and priced once. Closes SUGGEST-01, -02, -04, -05, and AMENDS SUGGEST-03 per D-62-07 (a
disclosed un-evidenced fallback is now permitted).

**Verified:** 2026-09-02T00:04:28Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A company with zero associated contacts is named eligible; one with contacts is skipped; one whose count could not be read is unknown and never silently eligible (D-62-16) | ✓ VERIFIED | `suggest_contacts._eligibility_verdict` branches readability BEFORE magnitude (`suggest_contacts.py:41-72`); `mergeContacts.js`/`Adapt Company Search` stamps `num_associated_contacts` as explicit `null` on any unreadable case, never a missing key or a false zero — confirmed by `tests/n8n/suggestionProvenanceFlow.test.mjs` (5 assertions, all green) |
| 2 | A person named by reading a company's own page becomes a row extraction.validate() accepts on identity group 2 without changing the identity contract (D-62-09) | ✓ VERIFIED | `synthesise_rows()` emits only canonical props (`firstname`/`lastname`/`company`/`jobtitle`), asserted a subset of `extraction.canonical_props()`; `test_suggest_contacts.py` exercises the tracer end-to-end into `extraction.validate()` |
| 3 | When the ladder finds nobody, the round records the ladder's own give-up text and moves on — never a second search on another host (D-62-03) | ✓ VERIFIED | `no_candidates()` returns `url_fallback.give_up_message(...)` verbatim, no second-source branch anywhere in `suggest_contacts.py` |
| 4 | A person already associated with the company is filtered out before any spend (D-62-18) | ✓ VERIFIED | `select_people()` drops on `known_keys` match before the role filter runs; tested (`test_suggest_contacts.py`) |
| 5 | A suggested person still without an email after stage 2 is HELD by the existing `hold_emailless` path, not written and not special-cased (D-62-09, SUGGEST-04) | ✓ VERIFIED | `partition_for_dispatch()` is a thin, unmodified call to `extraction.hold_emailless` |
| 6 | The role list is derived from the portal's own `jobtitle` values, clustered once and cached — not re-clustered per round (D-62-05) | ✓ VERIFIED | `scripts/role_vocabulary.py` (repo root, credentialled) is the sole producer of `operator-claude-plugin/config/role_vocabulary.yaml`; `role_classify.load_families()` reads the cache only, no re-derivation |
| 7 | Offers top N families by recurrence, N fixed and scannable (D-62-06) | ✓ VERIFIED | `TOP_N_FAMILIES` truncation in `role_vocabulary.py`; `offer_block()` renders recurrence counts for an evidenced vocabulary |
| 8 | Sparse-portal fallback served AND visibly marked un-evidenced (D-62-07) | ✓ VERIFIED | Shipped `config/role_vocabulary.yaml` ships `evidenced: false`, `source: generic_fallback`; `offer_block()`'s `DISCLOSURE_SENTENCE` renders whenever `evidenced` is false — proven by `test_offer_block_un_evidenced_contains_disclosure_sentence` |
| 9 | SUGGEST-03's text and the ROADMAP's Closes line both record AMENDS, not closed (D-62-07) | ✓ VERIFIED | `.planning/milestones/v1.1-REQUIREMENTS.md` SUGGEST-03 is `[ ]` unchecked with the disclosed-fallback exception text and an explicit "AMENDS" annotation; `.planning/ROADMAP.md` and `.planning/milestones/v1.1-ROADMAP.md` both read "Closes SUGGEST-01,-02,-04,-05, and AMENDS SUGGEST-03 per D-62-07" |
| 10 | Suggestion cost disclosed in the SAME opening envelope as enrichment cost, one number, one yes (D-62-11) | ✓ VERIFIED | `write_grant.envelope(..., suggestion_companies=, suggestion_cap=)` folds `cost_guard.suggestion_line()` into the same `figures` dict under a third key (`suggestion_allowance`) that cannot collide with `chunk_ceiling`/`ceiling` (explicit CR-01-from-Phase-60 anti-regression comment); omitting the args reproduces the pre-Phase-62 envelope byte-for-byte (tested) |
| 11 | Quoted figure is a worst-case ceiling with both stage-1 fetch and stage-2 credit components visible; stage-1 dollar cost disclosed as unmeasured, never $0 (D-62-14) | ✓ VERIFIED | `cost_guard.suggestion_line()` renders one sentence naming both components; `stage1_cost_usd=None`/`stage1_state="unmeasured"` when `SUGGESTION_RATE_KEY` is null, never coerced to 0 |
| 12 | A batch whose suggestion weight pushes it over the sampled monthly ceiling is refused before it starts (D-62-13) | ✓ VERIFIED | `envelope()` adds the suggestion round's projected chunk weight to `executions` BEFORE `ceiling_verdict()` runs; `test_plan_grant_refuses_over_ceiling_when_only_the_suggestion_weight_pushes_it_over` passes |
| 13 | The round may spend LESS than the priced per-company cap; it may never spend more (D-62-12, SUGGEST-05) | ✗ FAILED | See Gaps below — live-reproduced `cap=None` uncaps the round entirely at the one function that applies it |

**Score:** 12/13 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `operator-claude-plugin/scripts/suggest_contacts.py` | Suggestion round engine | ✓ VERIFIED (with gap) | 257 lines, all documented functions present and wired; `synthesise_rows` has the CR-01 validation gap (see Gaps) |
| `operator-claude-plugin/scripts/role_classify.py` | Online role matcher + offline cache loader | ✓ VERIFIED | 123 lines, `load_families`/`offer_block`/`chosen_families`/`classify_title` all present and tested |
| `operator-claude-plugin/tests/test_suggest_contacts.py` | Unit tests | ✓ VERIFIED | 315 lines, exercises tracer through `extraction.validate()` |
| `scripts/role_vocabulary.py` | Repo-root, credentialled, read-only inventory | ✓ VERIFIED (untested, WR-02) | 228 lines; at repo root (not under `operator-claude-plugin/`, confirmed by `find`); no plugin credential (`grep -rl HUBSPOT_PRIVATE_APP_TOKEN operator-claude-plugin/scripts/` empty); has zero test coverage of its own pure functions (`rank_top_families`, `build_generic_fallback`, `build_portal_vocabulary`) — flagged WR-02 in code review, matches repo convention (`inventory_org_type_values.py` also untested) |
| `operator-claude-plugin/config/role_vocabulary.yaml` | Committed cache | ✓ VERIFIED | Ships the disclosed generic fallback (`evidenced: false`), consistent with the live portal sweep never having been run in this session — expected, not a defect |
| `operator-claude-plugin/tests/test_role_vocabulary.py` | Tests | ✓ VERIFIED (misleadingly named, see note) | Actually tests `role_classify.py`'s loader/offer/select, NOT `scripts/role_vocabulary.py` (confirmed by import statement and docstring) — the WR-02 gap stands despite this file's existence |
| `operator-claude-plugin/scripts/cost_guard.py` | Suggestion pricing | ✓ VERIFIED | `suggestion_line()` present, tested |
| `operator-claude-plugin/scripts/write_grant.py` | Envelope integration | ✓ VERIFIED | `envelope()`/`plan_grant()` thread `suggestion_companies`/`suggestion_cap` through to `ceiling_verdict` |
| `operator-claude-plugin/tests/test_cost_guard_suggestion.py` | Tests | ✓ VERIFIED | 93 lines, all green |
| `operator-claude-plugin/tests/test_write_grant_suggestion.py` | Tests | ✓ VERIFIED | 220 lines, 11 test functions including the over-ceiling refusal case, all green |
| `n8n/code/mergeContacts.js` | Per-field provenance (sourceByField) | ✓ VERIFIED | `mergeContacts(existing, candidate, source, opts)` accepts `sourceByField`, resolves per-field before falling back to `source` |
| `scripts/build_cloud_workflows.py` | MERGE_CONTACTS wrapper + num_associated_contacts wiring | ✓ VERIFIED | `_sourceByFieldFromEnvelope()` reads `Set Config`, falls through to `{}` (byte-identical `csv` default) for every existing caller; `HS_CO_SEARCH_BODY_EXPR` requests `num_associated_contacts`, `Adapt Company Search` coerces/stamps null |
| `tests/n8n/suggestionProvenanceFlow.test.mjs` | Node tests | ✓ VERIFIED | 175 lines, 12 assertions, all green |
| `operator-claude-plugin/skills/suggest-contacts/SKILL.md` | The sitting itself | ✓ VERIFIED | 180 lines; documents the full 9-step round, the priced-cap refusal rule (prose only — see gap), the report step |
| `operator-claude-plugin/tests/test_suggest_contacts_composition.py` | Composition test | ✓ VERIFIED | 160 lines, registered in `test_skill_sequence_coverage.COVERED` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `suggest_contacts.py` | `url_fallback.plan_ladder`/`filter_candidates`/`give_up_message` | library call, never re-implemented | ✓ WIRED | direct imports and calls confirmed |
| `suggest_contacts.py` | `extraction.validate`/`canonical_props`/`hold_emailless` | library call, contract unchanged | ✓ WIRED | direct imports; `synthesise_rows` asserts subset of `canonical_props()` |
| `suggest_contacts.py` | `role_classify.classify_title` | family list passed as parameter | ✓ WIRED | `select_people()` calls `role_classify.classify_title(person.get("jobtitle"), family_list)` |
| `scripts/role_vocabulary.py` | `config/role_vocabulary.yaml` | committed cache write | ✓ WIRED | `role_vocabulary.py`'s `main()` writes the cache; the committed file exists and matches the generic-fallback shape |
| `config/role_vocabulary.yaml` | `role_classify.load_families()` | plugin read, no credential | ✓ WIRED | `DEFAULT_VOCABULARY_PATH` points at the committed file |
| `cost_guard.suggestion_line()` | `write_grant.envelope()` `figures["suggestion_allowance"]` | projected execution count, `ceiling_verdict` | ✓ WIRED | confirmed by reading `envelope()`'s body and the passing over-ceiling test |
| ingest webhook envelope source map | `MERGE_CONTACTS` → `mergeContacts(opts.sourceByField)` → `lv_contact_enrichment_provenance` | request-level per-field source | ✓ WIRED | traced through `build_cloud_workflows.py` and confirmed by `suggestionProvenanceFlow.test.mjs` |
| `HS_CO_SEARCH_BODY_EXPR num_associated_contacts` | `Adapt Company Search` row key | `Build Response` → plugin eligibility tri-state | ✓ WIRED | confirmed live in `wf_enrichment_cloud.json` and by node test |
| batch completion in `enrich-records/SKILL.md` | unprompted offer | `suggest-contacts/SKILL.md` | ✓ WIRED | grepped: `enrich-records/SKILL.md:557-564` names D-62-15 and unconditionally offers the round when object_type is companies and the manifest reached a terminal verdict |
| operator-chosen `per_company_cap` | grant's priced `suggestion_allowance["priced_cap"]` | code-enforced refusal | ✗ NOT WIRED | exists only as `SKILL.md` step 3 prose; no function anywhere performs this comparison (WR-01, folded into the CR-01 gap below) |

### Requirements Coverage

| Requirement | Source Plan(s) | Status | Evidence |
|-------------|----------------|--------|----------|
| SUGGEST-01 | 62-01, 62-04, 62-05 | ✓ SATISFIED | Eligibility tri-state, `num_associated_contacts` wiring, unprompted offer hook in `enrich-records/SKILL.md` all confirmed live; checked `[x]` in `v1.1-REQUIREMENTS.md` |
| SUGGEST-02 | 62-02, 62-05 | ✓ SATISFIED | Roles + cap chosen once per batch, applied across it (`chosen_families()`, SKILL.md step 3); checked `[x]` |
| SUGGEST-03 (amended, not closed) | 62-02 | ✓ CORRECTLY LEFT UNCHECKED | `[ ]` in `v1.1-REQUIREMENTS.md` with amendment text and D-62-07 annotation; ROADMAP.md and v1.1-ROADMAP.md both say AMENDS, not Closes — confirmed on disk, not just in commit messages |
| SUGGEST-04 | 62-01, 62-04, 62-05 | ✓ SATISFIED | `hold_emailless` reuse, `extraction.validate()` gate, held/needs_review routing unchanged; checked `[x]` |
| SUGGEST-05 | 62-03, 62-05 | ⚠️ PARTIALLY UNDERMINED | Pricing disclosure (envelope, ceiling, split-offer refusal) is fully wired and tested — but the round's own stated guarantee that actuals can never exceed the priced cap is NOT code-enforced at the one function that applies the cap (CR-01/WR-01). Checked `[x]` in the requirements file, which is arguably premature given the gap below — flagged for the operator's attention rather than unchecking it myself, since the pricing/disclosure half genuinely is closed and the failure is in enforcement, not disclosure. |

No orphaned requirements — all SUGGEST-01..05 IDs are declared across the five plans' `requirements` frontmatter and none appear in `v1.1-REQUIREMENTS.md`'s SUGGEST section without a corresponding plan claim.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `operator-claude-plugin/scripts/suggest_contacts.py` | 171 | Unvalidated slice bound (`people[:per_company_cap]`) | 🛑 Blocker | Silently defeats the round's cost-control invariant on a plausible bad input (see Gaps) |
| `scripts/role_vocabulary.py` | 114-130 (`cluster_titles`) | No retry/repair on invalid JSON from Haiku, contra CLAUDE.md §26.3's stated policy | ⚠️ Warning | Offline admin script; crashes with a traceback instead of falling back to the disclosed generic vocabulary one function away (WR-03 in code review) |
| `scripts/role_vocabulary.py` | whole file | No test coverage of pure logic functions | ⚠️ Warning | Matches repo convention (`inventory_org_type_values.py` also untested); not a phase-specific regression |

No `TBD`/`FIXME`/`XXX` markers found in phase-modified files.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full Python suite stays green | `.venv/bin/python -m pytest -q` | 3912 passed, 154 skipped, 0 failed | ✓ PASS |
| Full Node suite stays green | `node --test tests/n8n/*.test.mjs` | 862 pass, 0 fail | ✓ PASS |
| `synthesise_rows(cap=None)` uncaps the round | live one-off script against a 5-person fixture | 5/5 rows synthesised, no cap applied | ✓ PASS (confirms the gap, not the goal) |
| `synthesise_rows(cap=-1)` truncates from the wrong end | live one-off script | 4/5 rows synthesised | ✓ PASS (confirms the gap, not the goal) |
| No plugin script holds a HubSpot credential | `grep -rl "HUBSPOT_PRIVATE_APP_TOKEN\|api.hubapi.com" operator-claude-plugin/scripts/` | empty | ✓ PASS |
| No vendor people-search calls in the new surface | `grep -rn "search-and-enrich\|mixed_people/search\|Prospecting" suggest_contacts.py role_classify.py role_vocabulary.py` | empty | ✓ PASS |
| No backend `web_fetch` | `grep -rn "web_fetch" n8n/code/*.js` | empty | ✓ PASS |
| Plugin version bumped | `grep version operator-claude-plugin/.claude-plugin/plugin.json` | `0.36.0` | ✓ PASS |
| `scripts/role_vocabulary.py` lives at repo root, not under the plugin | `find . -name role_vocabulary.py` | `./scripts/role_vocabulary.py` only | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` conventions apply to this phase; none declared in any plan or SUMMARY. Skipped.

### Human Verification Required

See frontmatter `human_verification` — three items carried forward unresolved from `62-VALIDATION.md`'s Manual-Only Verifications table (a real sitemap yielding a usable people page, a real stage-1→stage-2 handoff, and the priced ceiling holding in a live sitting). These are irreducibly manual by the phase's own validation strategy and were never claimed as done by any SUMMARY — correctly deferred to a live operator sitting.

### Gaps Summary

One gap blocks the phase goal: the per-company cap — the mechanism the whole round relies on to
keep stage-2 provider spend inside what the operator agreed to pay — is applied by a single,
unvalidated Python slice. A `None` cap (a plausible failure of the LLM-orchestrator-driven
production path, not a contrived input) silently removes the cap entirely rather than refusing,
directly contradicting the phase's own stated design rule ("a cap above the grant's priced cap
is refused... it may never spend more"). This was raised as a Critical finding in the
just-completed code review (`62-REVIEW.md` CR-01) and independently reproduced live in this
verification. The fix is small (a validation guard plus a chosen-cap-vs-priced-cap refusal
function, both suggested in the review) and does not require re-architecting anything the phase
already built — everything else in the round (eligibility, discovery, role filtering, dedupe,
pricing disclosure, ceiling refusal, provenance, the unprompted offer) is verified live against
the codebase and matches its documented design.

`/gsd-plan-phase --gaps` should target this one truth. After it closes, re-verification is
expected to land `human_needed` rather than `passed` — the three manual-only items above are
irreducible and were never meant to close automatically.

---

_Verified: 2026-09-02T00:04:28Z_
_Verifier: Claude (gsd-verifier)_
