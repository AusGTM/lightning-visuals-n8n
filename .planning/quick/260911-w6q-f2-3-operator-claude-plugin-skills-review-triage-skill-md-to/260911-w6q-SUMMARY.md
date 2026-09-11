---
phase: quick-260911-w6q
plan: 01
subsystem: operator-plugin
tags: [review-triage, held-queue, facets, ingest-lane, F2-3]

requires: ["260911-w6o", "260911-w6p"]
provides:
  - "review-triage/SKILL.md reads held_queue.json alongside the HubSpot review queue and renders one continuously-numbered table over four facets (new_person, needs_company, nothing_found, parked)"
  - "a held new_person row's documented, tested route to HubSpot: widened review+contacts grant -> CSV of exactly the chosen rows -> contact-upload's own dispatch (delegated by heading) -> independent re-read joined on email -> held_queue.record_verb mark"
affects: [260911-w6r]

actuals:
  tokens: 5600
  tasks: 3
  commits: 2
  plan_head_before: 66de79b8

tech-stack:
  added: []
  patterns:
    - "A caller-resolved, per-sitting known_company_domains set (RESOLUTION_SOURCES vocabulary only, never a live lookup added to the read path) rather than widening the authorization boundary with a HubSpot search of its own"
    - "A held-row create delegated by heading to another skill's own dispatch steps, never a second copy of the dispatch ritual"

key-files:
  created:
    - operator-claude-plugin/tests/test_review_triage_facets.py
  modified:
    - operator-claude-plugin/skills/review-triage/SKILL.md
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py

key-decisions:
  - "held_queue.classify_facet(entry, known_company_domains) used as shipped -- discriminates on whether the entry's OWN email domain is already known to exist as a HubSpot company, never on whether entry[\"row\"][\"company\"] is filled in. KATIE_ENTRY carries a company name and still reads needs_company, because the classifier never reads that column at all."
  - "known_company_domains is per-sitting conversation knowledge, seeded empty, grown only from the plugin's existing RESOLUTION_SOURCES vocabulary (hubspot_lookup/operator_statement/provider_result/same_row_derivation) or 4c's own company-verb handoff landing -- review-triage performs no HubSpot search of its own to populate it, which would be the exact widening write_grant.py's own docstring already refuses to give plan_grant."
  - "held_queue.record_verb(row_id, verb, run_id) used as shipped (loads and saves itself) -- collapses the plan's assumed load()/mark()/save() triple into one call."
  - "The open/undecided split uses the shipped held_queue.open_entries() (drops create/skip/drop) plus entry_verb() is None (also drops retry) rather than a hand-rolled `not entry.get(\"status\")` filter -- retry lands in the parked count, never silently dropped."
  - "Two commits, not three task-shaped ones: the SKILL.md prose for Tasks 1-2 is genuinely interleaved (one table, one set of facets) and slicing it into artificial hunks risked a broken intermediate state for no benefit. Commit 1 is the product change (SKILL.md + its composition test); commit 2 is the mechanical coverage-ratchet registration Task 3(c) asked for."

requirements-completed: ["F2-3"]

coverage:
  - id: T1
    description: "One held new person, end to end: read -> bucket -> render -> CSV -> dispatch delegation -> confirm re-read joined on email -> mark, only for a row the re-read found"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_triage_facets.py::test_one_held_new_person_end_to_end_read_render_create_confirm_mark"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_triage_facets.py::test_a_row_absent_from_the_confirm_re_read_is_not_marked_created"
        status: pass
    human_judgment: false
  - id: T2
    description: "needs_company/nothing_found/parked facets, and the parked total accounts for every open entry the table did not list (nothing-found, non-no_match hold codes, retry-marked)"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_triage_facets.py::test_needs_company_nothing_found_and_parked_totals_account_for_every_unlisted_open_entry"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_triage_facets.py::test_a_needs_company_row_re_facets_to_new_person_once_its_domain_is_confirmed"
        status: pass
    human_judgment: false
  - id: T3
    description: "Answer vocabulary ported by heading, step 5's opening claim narrowed correctly, and all three new fences registered in the sequence-coverage ratchet"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_skill_sequence_coverage.py::test_no_new_or_orphaned_sequence_exists_in_the_live_corpus"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests -q (whole plugin suite, 2991 passed, 5 skipped)"
        status: pass
    human_judgment: false

duration: ~90min
completed: 2026-09-12
status: complete
---

# Quick 260911-w6q: review-triage reads both queues, creates a held new-person row (F2-3) Summary

**`review-triage/SKILL.md` now reads `held_queue.json` alongside the HubSpot `lv_enrichment_needs_review` queue, renders one continuously-numbered table over four facets, and gives a held `new_person` row a tested route to HubSpot through the contact-ingest lane -- closing the review-triage half of the operator's 2026-09-11 F2 ruling.**

## API reconciliation against 260911-w6p's shipped surface (load-bearing — read this before 260911-w6r touches the same area)

This plan was written against an assumed `held_queue.facet(entry)` / `held_queue.mark(entries, row_id, verb, run_id=...)` API. The item's own `<upstream_api_contract>` anticipated drift and authorized adaptation; the drift here was semantic, not just a rename, so it is recorded explicitly:

- **`facet(entry)` → `classify_facet(entry, known_company_domains=frozenset())`.** The plan assumed the facet derived from whether the held row's own `company` column was populated. The shipped function never reads that column at all — it discriminates on whether the entry's own email **domain** is already known, via the caller-supplied `known_company_domains` set, to exist as a HubSpot company. `KATIE_ENTRY` (company="Atherton Turf Club", populated) still reads `needs_company` because her own domain isn't in the supplied set — proven directly in `test_a_needs_company_row_re_facets_to_new_person_once_its_domain_is_confirmed`.
- **`known_company_domains` is per-sitting conversation knowledge, never a lookup this skill performs.** With nothing confirmed yet, `classify_facet(entry)`'s own default (empty set) reads `needs_company` for every usable-email entry — the function's documented safe default. A domain is added only from the plugin's existing `RESOLUTION_SOURCES` vocabulary (`hubspot_lookup`, `operator_statement`, `provider_result`, `same_row_derivation`) or from 4c's own company-verb handoff landing. Adding a live HubSpot search here would be exactly the widening `write_grant.py`'s own docstring already refuses to take on for `plan_grant`'s resolution.
- **`mark(entries, row_id, verb, run_id=)` → `record_verb(row_id, verb, run_id, path=None)`.** Loads and saves itself; the plan's assumed `load()`/`mark()`/`save()` triple collapses to one call.
- **`not entry.get("status")` → `held_queue.open_entries()` + `held_queue.entry_verb(entry) is None`.** `open_entries()` (shipped) drops only settled verbs (`create`/`skip`/`drop`); a `retry`-marked entry is still "open" per that function but is excluded from the table's own `undecided` set by the second check — landing in the parked count instead, never silently dropped.
- **Plan Task 2(b)'s "the facet does not flip... it reads the held entry's own `row["company"]`" text was false about the shipped function** — replaced in the SKILL with the accurate mechanism: `classify_facet` is pure over the entry plus the caller's own domain set; 4c re-facets one row after its company lands.

Two facts verified on disk rather than assumed (per the plan's own instruction):
- `send_domains` for a create **is** the domain of the row's own enriched email — confirmed against `suggestion_declines.py`'s own shipped precedent (`row["email"].rpartition("@")[2]`), not against `write_grant._classify_scope_member`'s docstring (a different function, classifying `split_for_allowance` spec members — its "a domain has no meaning for a contact" line does not apply here).
- `write_grant.preflight_before_send` is workflow-scoped (`{lane: granted[lane]}`), and D-60-06/MEDIUM-1 already carves the review flag out of dispatch-liveness reads on the review lane specifically — so the review window and an ingest send's own window never collide; no sequencing constraint was needed.

Two smaller corrections made along the way: `"unknown_tier"` (one of the five non-`no_match` hold codes) is spelled as "an unrecognized match signal" in the parked-line prose — `test_report_enrichment.py`'s substring ban on `"tier"` anywhere in a skill file is documented as deliberately non-discriminating (D-10b), not a defect to route around. And the plan's `preingest.LAG_RETRY_LIMIT` citation for HubSpot search-index lag was removed — that constant is the ingest lane's own bounded retry for a **company** dependency created earlier in the same run, not a contact search-index-lag concept; the confirm-fence prose now states the lag plainly without a misapplied citation.

## Performance

- **Tasks:** 3/3 completed
- **Files modified:** 3 (1 created, 2 modified)
- **Commits:** 2 (`7e6af271`, `2101b747`)

## What now exists (for 260911-w6r to close the todo against)

`.planning/todos/pending/2026-09-11-no-plugin-path-turns-an-approved-held-row-into-a-sent-row.md` is **not edited by this item** (260911-w6r owns closing it), but the fact it names is now resolved on the review-triage side:

- `review-triage/SKILL.md` step 2b reads `held_queue.json`; step 2c renders one numbered table over both queues, four facets, and a parked line that never drops an entry silently.
- Step 3 documents the answer vocabulary (ported by heading from `enrich-before-ingest/SKILL.md` step 3) and narrows step 5's own "approve/reject are the only decision words" claim to HubSpot-flagged conflicts specifically.
- Steps 4/4a/4b/4c: the grant widens to `lanes=["review","contacts"]`/`allow_create=True` only when a create is chosen; the CSV-build fence writes exactly the chosen rows; the send is delegated **by heading** to `contact-upload/SKILL.md`'s own dispatch/report/re-check/retry/clean-up steps (never a second dispatch implementation); the confirm fence re-reads by email and marks only a landed row via `held_queue.record_verb`.
- A `needs_company` row's `company` verb hands off by heading to `enrich-records/SKILL.md`'s company-creation form; once that company lands, 4c re-facets the one row with its now-confirmed domain and offers its create in the same sitting.
- `held_queue.py` is untouched, as required.

## Task Commits

1. **Tasks 1-2: review-triage reads the held queue, renders four facets, creates a held new-person row through the ingest lane** - `7e6af271` (feat)
2. **Task 3(c): register the three new held-queue sequences in the skill-sequence coverage ratchet** - `2101b747` (test)

No separate plan-metadata commit -- per the orchestrator constraints for this quick-batch leaf, STATE.md/ROADMAP.md updates and this SUMMARY's own commit belong to the orchestrator, not this execution.

### Why two commits, not three task-shaped ones

Tasks 1 and 2's SKILL.md prose is genuinely interleaved — one continuously-numbered table, one `by_facet` dict, one parked-line paragraph covering all four facets at once. Slicing that into two artificial hunks would have risked a broken intermediate state (a table description naming facets a not-yet-committed fence hadn't added) for no real benefit, since both tasks share the identical `<verify>` commands and neither is independently shippable. Commit 1 covers the product change (SKILL.md plus its composition test, `test_review_triage_facets.py`, which exercises Task 1's and Task 2's behaviors together); commit 2 is the separate, mechanical coverage-ratchet registration Task 3(c) specifically asked for, and is naturally its own unit (Task 3(a)/(b)'s vocabulary and step-5 amendment landed inside commit 1 alongside the fences they describe, since they are prose edits to the same file with no independent test surface).

## TDD Gate Compliance

Both tasks carried `tdd="true"`. This item added **no new source-code behavior** to `scripts/` — every function the new SKILL.md fences call (`held_queue.classify_facet`, `open_entries`, `entry_verb`, `record_verb`; `preingest.strip_enrichment_extras`/`build_rows_spec`/`match_batch`/`classify_matches`; `extraction.strip_row_id`/`write_dispatch_csv`; `chunking.plan_chunks`/`chunk_ceiling`) was already shipped by 260911-w6p or earlier, before this item started. So RED here was **not** a failing Python assertion against not-yet-written source — it took two honest forms instead:

1. **The coverage-ratchet failure, observed before the registry edit.** Running `test_skill_sequence_coverage.py` after committing the SKILL.md prose (before touching the registry) failed `test_no_new_or_orphaned_sequence_exists_in_the_live_corpus`, naming exactly the three new sequences by skill, line, and call tuple:
   ```
   AssertionError: new, unregistered SKILL.md sequence(s): [
     'review-triage/SKILL.md line 89 ... [held_queue.classify_read -> load -> open_entries -> entry_verb -> classify_facet]',
     'review-triage/SKILL.md line 317 ... [config_gate.load_config -> build_rows_spec -> plan_chunks -> chunk_ceiling -> match_batch -> classify_matches]',
     'review-triage/SKILL.md line 281 ... [strip_enrichment_extras -> strip_row_id -> write_dispatch_csv]']
   ```
   This is a real RED, caused by real prose that did not exist before this item's first commit.
2. **`grep -c 'held_queue' skills/review-triage/SKILL.md`: 0 before this item, 24 after.** The plan's own `<verify>` command for Task 1 is itself a RED/GREEN pin on the documentation surface.

Each behaviour in `test_review_triage_facets.py` was then verified by driving the fence's exact call sequence as real Python against a held-queue map built inline (mirroring `test_held_queue_facets.py`'s own recorded `a254d1eda71246a2a964922cdf5c2bd2` fixture shapes), with a fake transport for `match_batch` (no network) and every held-queue write scoped to `tmp_path` via an explicit `path=` argument. Final full-suite runs: `operator-claude-plugin/tests` 2991 passed, 5 skipped; root suite 4852 passed, 154 skipped; `node --test tests/n8n/*.test.mjs` 1101 passed, 0 failed (`n8n/` diff empty throughout — no n8n change in this item).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, caught pre-commit by advisor review] `created_by_row_id` dict could in principle carry `None` for an emailless chosen row**
- **Found during:** final review before committing, while reconciling the confirm fence against `held_queue.classify_facet`'s actual guarantees.
- **Issue:** `4c`'s `[{"email": email} for email in created_by_row_id.values() if email]` silently drops a `None`-email entry from the confirm pass, which — read in isolation — looks like it could leave a chosen row sent-but-never-confirmed with nothing said.
- **Fix:** Not a guard (it cannot actually happen): `chosen_row_ids` only ever names rows 2c offered `create` for, and `classify_facet` only ever returns `FACET_NEW_PERSON` for an entry whose own decision table (step 1 of its own docstring) has already proven a usable email. Added one sentence to 4a's prose naming this guarantee explicitly, so a future reader does not mistake the `if email` filter for a silent drop of a row the operator actually chose.
- **Files modified:** `operator-claude-plugin/skills/review-triage/SKILL.md`
- **Commit:** `7e6af271`

**2. [Rule 3 - Blocking issue] `test_report_enrichment.py`'s substring ban on "tier" tripped on `unknown_tier`**
- **Found during:** first full-suite run after Task 2's edits.
- **Issue:** The parked-line prose named all five non-`no_match` hold codes, including `unknown_tier`, tripping `test_no_operator_facing_skill_body_mentions_icp_or_tier_not_even_a_placeholder` (a pre-existing, unrelated D-10b guard that bans the literal substring `"tier"` anywhere in any skill file, by design "does not discriminate").
- **Fix:** Reworded to "an unrecognized match signal" — no change in meaning, no new vocabulary invented.
- **Files modified:** `operator-claude-plugin/skills/review-triage/SKILL.md`
- **Commit:** `7e6af271`

Or, in full: everything else executed per the (adapted) plan. The only genuine scope difference from the plan-as-written is the classify_facet API reconciliation recorded above, which the plan's own `<upstream_api_contract>` explicitly authorized and asked to be recorded here.

## Known Stubs

None.

## Threat Flags

None -- the plan's own `<threat_model>` (T-w6q-01 through T-w6q-06, T-w6q-SC) already covers this execution's surface: the CSV-build fence writes exactly the chosen rows (T-w6q-01, proven by `test_one_held_new_person_end_to_end...`'s CSV-content assertions), the table's answer vocabulary refuses a bare blanket affirmative and requires a restated count for a bulk one (T-w6q-02, documented in step 3, ported by heading from an existing, tested vocabulary), the confirm fence's verdict comes only from an independent re-read joined on email (T-w6q-03, proven directly), `held_queue.py` is untouched so its allowlist/forbidden-name refusal is unchanged (T-w6q-04), and the two-window non-collision is documented with an on-disk citation rather than merely assumed (T-w6q-05). No package was installed (T-w6q-SC).

## Self-Check: PASSED

- `git log --oneline --all | grep -q 7e6af271` -> FOUND
- `git log --oneline --all | grep -q 2101b747` -> FOUND
- `operator-claude-plugin/skills/review-triage/SKILL.md` -> FOUND
- `operator-claude-plugin/tests/test_review_triage_facets.py` -> FOUND
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` -> FOUND
