---
phase: 62-suggest-the-contacts-nobody-named
verified: 2026-09-02T00:20:00Z
status: passed
reconciled: 2026-09-04T17:30:00Z
score: 13/13 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 12/13
  gaps_closed:
    - "A suggestion round may spend LESS than the priced per-company cap; it may never spend more (D-62-12, SUGGEST-05)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "A real company's sitemap yields a usable people page on a live racing-club-shaped site"
    expected: "The sitemap-ladder rung resolves a people/board/team page and names at least one person, mirroring UAT 2.4's precedent (9/9 directors on gctc.com.au)"
    why_human: "url_fallback.py is pure string-building with no I/O by construction (62-VALIDATION.md manual-verification row 1) — the unit suite proves the ladder logic and the host-bound guard, never whether a given site's sitemap actually lists a people page. Requires a live plugin sitting with a real web_fetch."
  - test: "Stage 1 → stage 2 handoff on a real discovered person (name+company → Lusha search-and-enrich → proposal)"
    expected: "A person named by the ladder with no email resolves through identity group 2, the waterfall fills email/phone, and the row lands as a proposal (or HELD if still emailless) — never a silent write"
    why_human: "Requires a real page fetch (plugin-side web_fetch) followed by a real Lusha credit spend; neither runs in the stub-transport test suite (62-VALIDATION.md manual-verification row 2)."
  - test: "The priced ceiling is not exceeded in a real sitting"
    expected: "Actual page fetches and provider credits spent land at or under the quoted worst-case ceiling shown at grant-open; a bad or omitted per-company cap does not silently blow the ceiling"
    why_human: "The ceiling arithmetic and the cap-refusal guard (agreed_cap / synthesise_rows) are both now unit- and live-probe-tested outside the test suite, but 'the operator saw a number and the round stayed under it in a real sitting' is an end-to-end property only a live sitting can demonstrate (62-VALIDATION.md manual-verification row 3)."
human_verification_discharged:
  by: 62-UAT.md
  on: 2026-09-04
  how: |
    All three human_verification items above are the three UAT tests, one-to-one and in the
    same order. All three now read `result: pass` in 62-UAT.md — test 1 on its second run,
    2026-09-03, after the G-62-1 fix shipped. Status moved human_needed -> passed on that
    basis, not on any new automated evidence: the point of these items was that only a live
    sitting could settle them, and the live sittings happened.
    All 7 UAT gaps are also resolved as of 2026-09-04; G-62-5 was the last one open and was
    closed on the live operator --dry-run it itself specified. Both verify:post gates were
    re-run in the same session and refreshed to cover plans 62-11 and 62-12, which they had
    not previously reached: nyquist found 5/5 already covered, security returned SECURED with
    13/13 threats closed and 0 open.
---

# Phase 62: Suggest the Contacts Nobody Named — Verification Report

**Phase Goal:** Suggest the contacts nobody named — An enriched company with nobody at it is
not a lead. After a company batch, the operator is offered contacts worth enriching, chosen by
role and priced once. Closes SUGGEST-01, -02, -04, -05, and AMENDS SUGGEST-03 per D-62-07 (a
disclosed un-evidenced fallback is now permitted).

**Verified:** 2026-09-02T00:20:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (62-06)

## Goal Achievement

### Gap Closure Verification (the one item this run exists to check)

The prior run (`status: gaps_found`, 12/13) found exactly one failed truth: `synthesise_rows()`
applied the per-company cap with a bare, unvalidated `people[:per_company_cap]` slice, so
`per_company_cap=None` uncapped the round entirely (5/5 rows on a 5-person fixture) and
`per_company_cap=-1` truncated from the wrong end (4/5 rows) — a direct violation of the
phase's own stated invariant ("a round may spend LESS than the priced cap; it may never spend
more," D-62-12). Plan 62-06 closed it. This run re-derives the result **live, independently of
the SUMMARY and the code-review narrative**, per the re-verification instructions.

**Live probe against the current code** (run directly by this verifier, not copied from
`62-REVIEW-GAP.md` or the SUMMARY):

```
synthesise_rows(..., cap=None)  -> REFUSED: CapRefused "must be a non-negative int, got None"
synthesise_rows(..., cap=-1)    -> REFUSED: CapRefused "must be a non-negative int, got -1"
synthesise_rows(..., cap="2")   -> REFUSED: CapRefused (string)
synthesise_rows(..., cap=True)  -> REFUSED: CapRefused (bool excluded)
synthesise_rows(..., cap=False) -> REFUSED: CapRefused (bool excluded)
synthesise_rows(..., cap=1.5)   -> REFUSED: CapRefused (float excluded)
synthesise_rows(..., cap=0)     -> ACCEPTED, 0 rows   (spending less stays legal)
synthesise_rows(..., cap=2)     -> ACCEPTED, 2 rows
synthesise_rows(..., cap=5)     -> ACCEPTED, 5 rows

agreed_cap(2, {"suggestion_allowance": {"priced_cap": 3}})   -> ACCEPTED 2
agreed_cap(3, {..priced_cap 3})                              -> ACCEPTED 3 (at-cap is legal)
agreed_cap(5, {..priced_cap 3})                              -> REFUSED, names both "3" and "5"
agreed_cap(2, {"suggestion_allowance": None})                -> REFUSED (never priced)
agreed_cap(2, {})                                             -> REFUSED (never priced)
agreed_cap(None/0/-1/True, {..priced_cap 3})                  -> REFUSED (each case)
```

Both original defects are gone: `None` now refuses instead of uncapping; `-1` now refuses
instead of truncating from the wrong end. `agreed_cap()` is a real function — not SKILL.md
prose — that compares the operator's chosen cap against
`grant_figures["suggestion_allowance"]["priced_cap"]` and refuses when exceeded, naming both
numbers.

**Wiring, confirmed live (not inferred from the plan):**
- `skills/suggest-contacts/SKILL.md`'s single documented python block binds
  `per_company_cap = suggest_contacts.agreed_cap(chosen_cap, figures)` immediately before
  `synthesise_rows(eligible_company, selection["selected"], fetched_url, per_company_cap)` —
  the variable that flows into the cap argument is `agreed_cap()`'s return value, not
  `chosen_cap` and not a literal (grepped directly, line-numbered above the code block).
- `test_skill_sequence_coverage.py`'s `suggest-contacts` COVERED key now contains
  `"suggest_contacts.agreed_cap"` immediately before `"suggest_contacts.synthesise_rows"` — one
  entry, not a second registered sequence (grepped directly).
- `operator-claude-plugin/.claude-plugin/plugin.json` reads `"0.37.0"`; `CHANGELOG.md` carries
  a `[0.37.0]` entry — both confirmed on disk, not just claimed by the SUMMARY.

**Regression check (12 previously-passed truths, no full re-litigation):**
- `.venv/bin/python -m pytest -q` → **3929 passed, 154 skipped, 0 failed** (independently
  re-run by this verifier; matches the SUMMARY's claimed count and exceeds the 3912 baseline —
  17 new tests, all for the gap closure).
- `node --test tests/n8n/*.test.mjs` → **862 pass, 0 fail** (independently re-run; this plan
  touched no `n8n/` code, so this is a no-drift confirmation, not new evidence).
- `v1.1-REQUIREMENTS.md` SUGGEST-01/02/04/05 remain `[x]`, SUGGEST-03 remains `[ ]` with the
  D-62-07 amendment text — unchanged from the prior verification, confirmed by direct read.
- `write_grant.py`'s `envelope()`/`suggestion_allowance`/`priced_cap` wiring (truths 10-12 of
  the prior run) spot-checked by grep and is unchanged in shape; the new end-to-end test
  (`test_a_real_envelope_priced_cap_feeds_agreed_cap_and_bounds_synthesise_rows`) additionally
  proves a REAL `envelope()` figures dict feeds `agreed_cap()` correctly, which is strictly new
  evidence strengthening truth 10-12, not a regression risk to them.

**One residual, correctly scoped as non-blocking (not re-opening the gap):** the code review
(`62-REVIEW-GAP.md`, IN-01) notes `synthesise_rows()` still accepts any non-negative int
directly — nothing at the Python call boundary *forces* a caller to route through
`agreed_cap()` first; the priced-ceiling comparison lives only in `agreed_cap()`, by the
module's own deliberate purity decision (`suggest_contacts.py` carries no `write_grant`
import). This verifier independently confirmed the same behavior
(`synthesise_rows(..., cap=1_000_000_000)` would accept). This is not a reopening of CR-01 —
both of CR-01's concrete, live-reproduced failure modes (`None`, `-1`) are closed — it is a
structural note that the ceiling is enforced by the documented SKILL.md dataflow plus a
composition test, not by a runtime invariant inside `synthesise_rows` itself. The
sequence-coverage ratchet checks call ORDER, not that the same variable flows between the two
calls, so a future SKILL.md edit that kept call order but rewired the argument would not be
caught by the ratchet. This is exactly the kind of gap that a live sitting (human verification
item 3, below) is positioned to catch in practice, and does not block this phase's goal —
flagged for awareness, not as a gap.

### Observable Truths (full table, carried forward with truth 13 updated)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A company with zero associated contacts is named eligible; one with contacts is skipped; one whose count could not be read is unknown and never silently eligible (D-62-16) | ✓ VERIFIED | Unchanged from prior verification; `suggest_contacts._eligibility_verdict` branches readability before magnitude |
| 2 | A person named by reading a company's own page becomes a row extraction.validate() accepts on identity group 2 without changing the identity contract (D-62-09) | ✓ VERIFIED | Unchanged; `synthesise_rows()` still emits only canonical props |
| 3 | When the ladder finds nobody, the round records the ladder's own give-up text and moves on — never a second search on another host (D-62-03) | ✓ VERIFIED | Unchanged |
| 4 | A person already associated with the company is filtered out before any spend (D-62-18) | ✓ VERIFIED | Unchanged |
| 5 | A suggested person still without an email after stage 2 is HELD by the existing `hold_emailless` path, not written and not special-cased (D-62-09, SUGGEST-04) | ✓ VERIFIED | Unchanged |
| 6 | The role list is derived from the portal's own `jobtitle` values, clustered once and cached — not re-clustered per round (D-62-05) | ✓ VERIFIED | Unchanged |
| 7 | Offers top N families by recurrence, N fixed and scannable (D-62-06) | ✓ VERIFIED | Unchanged |
| 8 | Sparse-portal fallback served AND visibly marked un-evidenced (D-62-07) | ✓ VERIFIED | Unchanged |
| 9 | SUGGEST-03's text and the ROADMAP's Closes line both record AMENDS, not closed (D-62-07) | ✓ VERIFIED | Re-confirmed live this run — `v1.1-REQUIREMENTS.md` SUGGEST-03 still `[ ]` with amendment text |
| 10 | Suggestion cost disclosed in the SAME opening envelope as enrichment cost, one number, one yes (D-62-11) | ✓ VERIFIED | Unchanged, and strengthened by the new real-envelope end-to-end test |
| 11 | Quoted figure is a worst-case ceiling with both stage-1 fetch and stage-2 credit components visible; stage-1 dollar cost disclosed as unmeasured, never $0 (D-62-14) | ✓ VERIFIED | Unchanged |
| 12 | A batch whose suggestion weight pushes it over the sampled monthly ceiling is refused before it starts (D-62-13) | ✓ VERIFIED | Unchanged |
| 13 | The round may spend LESS than the priced per-company cap; it may never spend more (D-62-12, SUGGEST-05) | ✓ VERIFIED | Gap closed — live-reproduced this run: `CapRefused` fires for `None`/`-1`/`"2"`/`True`/float; `agreed_cap()` code-enforces the chosen-vs-priced comparison; both wired into the documented SKILL.md sequence and pinned by the sequence-coverage ratchet |

**Score:** 13/13 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `operator-claude-plugin/scripts/suggest_contacts.py` | Suggestion round engine | ✓ VERIFIED | 331 lines; `CapRefused` and `agreed_cap()` added, `synthesise_rows` guarded at the sole application site — confirmed by direct read and live execution |
| `operator-claude-plugin/scripts/role_classify.py` | Online role matcher + offline cache loader | ✓ VERIFIED | Unchanged from prior verification |
| `operator-claude-plugin/tests/test_suggest_contacts.py` | Unit tests | ✓ VERIFIED | Extended with `CapRefused`/`agreed_cap` regression tests; existing `test_synthesise_rows_honors_per_company_cap` unmodified and still passes |
| `scripts/role_vocabulary.py` | Repo-root, credentialled, read-only inventory | ✓ VERIFIED (untested, WR-02, out of this plan's scope) | Unchanged; deliberately deferred per 62-06's scope fence |
| `operator-claude-plugin/config/role_vocabulary.yaml` | Committed cache | ✓ VERIFIED | Unchanged |
| `operator-claude-plugin/tests/test_role_vocabulary.py` | Tests | ✓ VERIFIED | Unchanged |
| `operator-claude-plugin/scripts/cost_guard.py` | Suggestion pricing | ✓ VERIFIED | Unchanged |
| `operator-claude-plugin/scripts/write_grant.py` | Envelope integration | ✓ VERIFIED | Unchanged; confirmed still the sole source of `suggestion_allowance["priced_cap"]` |
| `operator-claude-plugin/tests/test_cost_guard_suggestion.py` | Tests | ✓ VERIFIED | Unchanged |
| `operator-claude-plugin/tests/test_write_grant_suggestion.py` | Tests | ✓ VERIFIED | Extended with the real-envelope → `agreed_cap` → `synthesise_rows` end-to-end join |
| `n8n/code/mergeContacts.js` | Per-field provenance (sourceByField) | ✓ VERIFIED | Unchanged; this plan touched no `n8n/` code |
| `scripts/build_cloud_workflows.py` | MERGE_CONTACTS wrapper + num_associated_contacts wiring | ✓ VERIFIED | Unchanged |
| `tests/n8n/suggestionProvenanceFlow.test.mjs` | Node tests | ✓ VERIFIED | Unchanged; 862/0 fail full node suite re-run confirms no drift |
| `operator-claude-plugin/skills/suggest-contacts/SKILL.md` | The sitting itself | ✓ VERIFIED | Step 3 now names the enforcing code (`agreed_cap`); documented python block binds its return value before calling `synthesise_rows` — the prior "prose only" gap is closed |
| `operator-claude-plugin/tests/test_suggest_contacts_composition.py` | Composition test | ✓ VERIFIED | Now drives the result-consuming `agreed_cap` → `synthesise_rows` join plus a refusal-direction test, per plan Task 2(d) |
| `operator-claude-plugin/tests/test_skill_sequence_coverage.py` | Census ratchet | ✓ VERIFIED | `suggest-contacts` COVERED key updated in place, one entry (not a second registered sequence) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `suggest_contacts.py` | `url_fallback.plan_ladder`/`filter_candidates`/`give_up_message` | library call, never re-implemented | ✓ WIRED | Unchanged |
| `suggest_contacts.py` | `extraction.validate`/`canonical_props`/`hold_emailless` | library call, contract unchanged | ✓ WIRED | Unchanged |
| `suggest_contacts.py` | `role_classify.classify_title` | family list passed as parameter | ✓ WIRED | Unchanged |
| `scripts/role_vocabulary.py` | `config/role_vocabulary.yaml` | committed cache write | ✓ WIRED | Unchanged |
| `config/role_vocabulary.yaml` | `role_classify.load_families()` | plugin read, no credential | ✓ WIRED | Unchanged |
| `cost_guard.suggestion_line()` | `write_grant.envelope()` `figures["suggestion_allowance"]` | projected execution count, `ceiling_verdict` | ✓ WIRED | Unchanged |
| ingest webhook envelope source map | `MERGE_CONTACTS` → `mergeContacts(opts.sourceByField)` → `lv_contact_enrichment_provenance` | request-level per-field source | ✓ WIRED | Unchanged |
| `HS_CO_SEARCH_BODY_EXPR num_associated_contacts` | `Adapt Company Search` row key | `Build Response` → plugin eligibility tri-state | ✓ WIRED | Unchanged |
| batch completion in `enrich-records/SKILL.md` | unprompted offer | `suggest-contacts/SKILL.md` | ✓ WIRED | Unchanged |
| operator-chosen `per_company_cap` | grant's priced `suggestion_allowance["priced_cap"]` | code-enforced refusal | ✓ WIRED | **Now wired** — `suggest_contacts.agreed_cap()` performs this comparison in code, confirmed live this run; the composition test and sequence-coverage ratchet pin the join into the documented sequence |

### Requirements Coverage

| Requirement | Source Plan(s) | Status | Evidence |
|-------------|----------------|--------|----------|
| SUGGEST-01 | 62-01, 62-04, 62-05 | ✓ SATISFIED | Unchanged from prior verification |
| SUGGEST-02 | 62-02, 62-05 | ✓ SATISFIED | Unchanged |
| SUGGEST-03 (amended, not closed) | 62-02 | ✓ CORRECTLY LEFT UNCHECKED | Unchanged; re-confirmed live |
| SUGGEST-04 | 62-01, 62-04, 62-05 | ✓ SATISFIED | Unchanged |
| SUGGEST-05 | 62-03, 62-05, **62-06** | ✓ SATISFIED (no longer partially undermined) | Pricing disclosure was already fully wired; the round's own stated guarantee that actuals can never exceed the priced cap is now ALSO code-enforced at the sole function that applies the cap (`synthesise_rows`) and at the operator-choice seam (`agreed_cap`) — closing the enforcement half the prior run flagged as a gap. Checked `[x]` in `v1.1-REQUIREMENTS.md`, now fully justified. |

No orphaned requirements — unchanged from prior verification.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `operator-claude-plugin/scripts/suggest_contacts.py` | 232-240 (was 171) | ~~Unvalidated slice bound~~ **RESOLVED** — `synthesise_rows` now guards `per_company_cap` before any slicing | — | Prior 🛑 Blocker closed; live-reproduced fix confirmed independently this run |
| `operator-claude-plugin/scripts/suggest_contacts.py` | 216-240 | `synthesise_rows()` accepts any non-negative int directly — nothing at the Python call boundary forces routing through `agreed_cap()` first (IN-01, `62-REVIEW-GAP.md`) | ℹ️ Info | Deliberate consequence of the module-purity decision (no `write_grant` import); the ceiling holds in the documented SKILL.md dataflow (tested) but not as a runtime invariant inside `synthesise_rows` itself. Not a reopening of the closed gap — flagged for awareness, matches human-verification item 3's real-sitting test. |
| `scripts/role_vocabulary.py` | 114-130 (`cluster_titles`) | No retry/repair on invalid JSON from Haiku, contra CLAUDE.md §26.3's stated policy | ⚠️ Warning | Unchanged; explicitly out of 62-06's scope by the plan's own scope fence (WR-03) |
| `scripts/role_vocabulary.py` | whole file | No test coverage of pure logic functions | ⚠️ Warning | Unchanged; explicitly out of 62-06's scope (WR-02) |

No `TBD`/`FIXME`/`XXX` markers found in phase-modified files.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full Python suite stays green (independently re-run) | `.venv/bin/python -m pytest -q` | 3929 passed, 154 skipped, 0 failed | ✓ PASS |
| Full Node suite stays green (independently re-run) | `node --test tests/n8n/*.test.mjs` | 862 pass, 0 fail | ✓ PASS |
| Targeted gap-closure tests (independently re-run) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py operator-claude-plugin/tests/test_write_grant_suggestion.py operator-claude-plugin/tests/test_suggest_contacts_composition.py operator-claude-plugin/tests/test_skill_sequence_coverage.py -q` | 66 passed | ✓ PASS |
| `synthesise_rows(cap=None)` now refuses instead of uncapping | live one-off script against a 5-person fixture, run by this verifier | `CapRefused` raised, 0 rows | ✓ PASS (gap closed) |
| `synthesise_rows(cap=-1)` now refuses instead of truncating from the wrong end | live one-off script, run by this verifier | `CapRefused` raised, 0 rows | ✓ PASS (gap closed) |
| `agreed_cap(5, {priced_cap:3})` refuses, naming both numbers | live one-off script, run by this verifier | `CapRefused: "...cap of 3...cap of 5..."` | ✓ PASS |
| `agreed_cap(3, {priced_cap:3})` accepts (at-cap boundary) | live one-off script, run by this verifier | returns `3` | ✓ PASS |
| SKILL.md's cap argument is `agreed_cap()`'s return value, not a literal | `grep -n "agreed_cap\|per_company_cap" skills/suggest-contacts/SKILL.md` | line 170 binds it, line 172 passes it | ✓ PASS |
| Sequence-coverage ratchet pins the new join, one entry | `grep -n "suggest_contacts.agreed_cap" tests/test_skill_sequence_coverage.py` | present between `select_people` and `synthesise_rows` | ✓ PASS |
| Plugin version bumped | `grep version .claude-plugin/plugin.json` | `0.37.0` | ✓ PASS |
| Module purity preserved (no `write_grant` import in `suggest_contacts.py`) | `grep -c "^import write_grant\|^from write_grant" suggest_contacts.py` | `0` | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` conventions apply to this phase; none declared in any plan or SUMMARY. Skipped.

### Human Verification Required

Three items — all irreducibly manual, all carried forward unresolved from `62-VALIDATION.md`'s
Manual-Only Verifications table and from the prior VERIFICATION.md. None were claimed done by
any SUMMARY, including 62-06's:

1. **A real company's sitemap yields a usable people page on a live racing-club-shaped site.**
   Expected: the sitemap-ladder rung resolves a people/board/team page and names at least one
   person. Why human: `url_fallback.py` is pure string-building with no I/O by construction —
   the unit suite proves the ladder logic, never whether a real site's sitemap lists a people
   page.

2. **Stage 1 → stage 2 handoff on a real discovered person.** Expected: a person named by the
   ladder with no email resolves through identity group 2, the waterfall fills email/phone, and
   the row lands as a proposal (or HELD if still emailless) — never a silent write. Why human:
   requires a real page fetch followed by a real Lusha credit spend; neither runs in the
   stub-transport test suite.

3. **The priced ceiling is not exceeded in a real sitting.** Expected: actual page fetches and
   provider credits spent land at or under the quoted worst-case ceiling shown at grant-open.
   This item is now ALSO the acceptance test for the just-closed cap-enforcement gap: a real
   sitting should demonstrate that a bad or omitted per-company cap cannot silently blow the
   ceiling. Why human: the arithmetic and the refusal guard are both unit- and live-probe-tested
   outside the suite, but "the operator saw a number and the round stayed under it" is an
   end-to-end property only a live sitting demonstrates.

### Gaps Summary

None remaining. The single gap from the prior verification (`gaps_found`, 12/13 — the
per-company cap applied by an unvalidated slice) is closed, verified independently and live by
this run rather than by trusting `62-06-SUMMARY.md`'s narrative or `62-REVIEW-GAP.md`'s
conclusion: `CapRefused` now fires for `None`, negative, string, bool, and float caps at the
sole site that applies the cap (`synthesise_rows`), and `agreed_cap()` code-enforces the
chosen-cap-vs-priced-cap comparison that previously existed only as SKILL.md prose. Both are
wired into the documented round sequence and pinned against decay by the sequence-coverage
ratchet and a composition test. No regression was found in any of the 12 previously-verified
truths; both full baseline suites were independently re-run and stayed green (3929p/154s/0f
Python, 862p/0f Node).

The phase goal is code-achieved. What remains is exactly the three items that were always
outside what static analysis or a stub-transport test suite can prove — a real sitemap yielding
a real people page, a real stage-1→stage-2 handoff spending a real credit, and the priced
ceiling holding (including against a bad/omitted cap) in a real operator sitting. These route
to `human_needed` per the phase's own validation strategy, not to `passed`.

---

_Verified: 2026-09-02T00:20:00Z_
_Verifier: Claude (gsd-verifier)_
