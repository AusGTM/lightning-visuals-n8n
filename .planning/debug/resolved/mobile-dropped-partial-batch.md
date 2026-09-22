---
slug: mobile-dropped-partial-batch
status: resolved
trigger: "provider_sourced_fields fix and regression test; then jobtitle lock; Apollo not master key is known - no need to investigate"
created: 2026-09-22
updated: 2026-09-22
resolution: fixed
---

# Debug session — mobilephone / linkedin dropped for EVERY row when ANY row lacks it

Found live 2026-09-22 in an operator UAT (American Football Australia board, 7-row batch).
Root cause is already established with a reproduction — this is a **fix-and-verify** session.
Do not re-derive the cause. Write the failing regression test first, then the fix, then prove.

## Current Focus

hypothesis: `operator-claude-plugin/scripts/preingest.py::provider_sourced_fields` is a set INTERSECTION over every answered row's `fields`; a row the waterfall answered WITHOUT `mobilephone` removes `mobilephone` from the round-level `source_by_field` map for ALL rows, so the ingest lane's `MERGE_CONTACTS` falls back to csv/80 and `mobilephone` (`fill_blank_only`, `min_confidence: 85`) is withheld even into a blank field. Same for `linkedin_url` (85).
test: pytest regression in `operator-claude-plugin/tests/test_preingest_merge.py` with the 7-row shape (5 rows answered with jobtitle+mobilephone+linkedin_url, 2 rows answered with jobtitle only, all 7 CSV rows BLANK for mobilephone/linkedin_url) asserting `provider_sourced_fields(result) >= {"mobilephone", "linkedin_url"}`; it must be RED on the current code first.
expecting: RED on current code (returns {"jobtitle"}); GREEN after the fix; the existing D-72-07 test (`..._omits_a_partial_one`) must be RE-SHAPED, not deleted — its row 1 must carry a CSV-supplied value for the field so the under-claim still holds where it matters.
next_action: write the RED regression test in tests/test_preingest_merge.py using the existing _rows/_response helpers, run it, confirm it fails with {"jobtitle"}; then change provider_sourced_fields per the rule below; then run the full plugin suite.
bug_class: bohrbug
reasoning_checkpoint: null
tdd_checkpoint: null

## Symptoms

expected: A contact whose mobile the waterfall returned gets `mobilephone` written on the ingest send, regardless of whether OTHER rows in the same batch got a mobile.
actual: 7-row batch: Devlin and Bennett got no mobile/linkedin from the waterfall; the other 5 (Joan Norton et al.) lost mobilephone AND lv_linkedin_url on the ingest write. A 5-row retry (all answered) landed both. The operator's Claude hand-built `source_by_field = {"mobilephone": "waterfall", "linkedin_url": "waterfall"}` to get past it — truthful there, but a workaround for this defect.
errors: none — silent field-level withholding at the merge engine; dispatch reported no failures.
reproduction: deterministic, offline —
```
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0,'operator-claude-plugin/scripts'); import preingest
class R: pass
r=R(); r.answered_fields=tuple({"row_id":i,"fields":f} for i,f in [
 (1,("jobtitle","mobilephone","linkedin_url")),(2,("jobtitle","mobilephone","linkedin_url")),
 (3,("jobtitle","mobilephone","linkedin_url")),(4,("jobtitle","mobilephone","linkedin_url")),
 (5,("jobtitle","mobilephone","linkedin_url")),(6,("jobtitle",)),(7,("jobtitle",))])
print(sorted(preingest.provider_sourced_fields(r)))   # -> ['jobtitle']
PY
```
started: Phase 72 Plan 03 (D-72-07/D-72-22, 2026-09-12) introduced the intersection rule; first hit live 2026-09-22 on the first mixed-coverage batch.

## Eliminated

- hypothesis: intermittent / provider flakiness
  evidence: same code path, same batch shape reproduces offline every time; the 5-row retry differs only in coverage
  timestamp: 2026-09-22
- hypothesis: F72-1 alias mismatch (linkedin_url vs lv_linkedin_url) recurring
  evidence: CANDIDATE_ALIASES in MERGE_CONTACTS (scripts/build_cloud_workflows.py:599) is intact; the map itself had NO linkedin_url entry to alias
  timestamp: 2026-09-22

## Evidence

- timestamp: 2026-09-22
  checked: operator-claude-plugin/scripts/preingest.py:990-1010 `provider_sourced_fields`
  found: `set.intersection(*field_sets)` over `merge_result.answered_fields`; docstring: "a field the provider answered for some rows and not others is NOT named" — deliberate under-claim per D-72-07
  implication: any row the waterfall answered partially vetoes the field for the whole batch, including rows whose only possible source for that value IS the waterfall
- timestamp: 2026-09-22
  checked: operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:1158-1170
  found: the skill builds `source_by_field = {f: "waterfall" for f in provider_sourced_fields(merge_report)}` and the comment states that with no entry MERGE_CONTACTS falls back to csv/80 "which a fill_blank_only@85 field can never clear even into a blank field"
  implication: the drop is total for mobilephone (85) and lv_linkedin_url (85); phone (80) survives — matches the observed symptom exactly
- timestamp: 2026-09-22
  checked: scripts/build_cloud_workflows.py:607-620 (MERGE_CONTACTS confidenceByField)
  found: confidence 85 assigned only for keys present in row.source_by_field with a non-csv source; aliases applied from that map
  implication: the fix belongs client-side in provider_sourced_fields; the n8n lane is correct given a truthful map
- timestamp: 2026-09-22
  checked: MergeResult (preingest.py:733-756) and merge_enriched's return (preingest.py:956-963)
  found: `rows` (merged values per row, CSV + provider) and `answered_fields` (per-row provider-answered keys) are both on the result
  implication: the truthful rule below is computable with no CSV-shape change (STRUCT-01 untouched)
- timestamp: 2026-09-22
  checked: D-72-07 rationale (docstring): "Naming a field the CSV actually supplied would let a stale spreadsheet cell win a later recency comparison it never earned"
  implication: the protected case is a row whose value for F came from the CSV. A row with F BLANK has nothing to protect and must not veto the claim

## Resolution

root_cause: `provider_sourced_fields` required the waterfall to have answered field F for EVERY answered row. Rows where F is blank (nothing from the CSV, nothing from the waterfall) vetoed the claim although they carry no CSV value the under-claim rule exists to protect. Result: a round-level map missing F, csv/80 fallback, `fill_blank_only@85` fields (mobilephone, lv_linkedin_url) withheld on every row of a mixed-coverage batch.
fix: `provider_sourced_fields` now builds `answered_by_row` from `merge_result.answered_fields`, takes the union of every row's answered fields as the candidate set, then keeps a candidate field F only if, for every row in `merge_result.rows`: `not _present(row.get(F))` OR F is in that row's own answered set. A row in `merge_result.unanswered` has no entry in `answered_by_row`, so it counts as "not answered" (its value is CSV-only) exactly as planned. Empty-set-when-nothing-answered preserved. Under-claim preserved for the stale-CSV case: a row with a present, non-waterfall value for F (nothing in its answered set) still vetoes F — reshaped `test_provider_sourced_fields_names_a_field_answered_for_every_row_and_omits_a_partial_one` proves it (row 1 now carries a CSV `jobtitle`, jobtitle still omitted). Docstring rewritten in `preingest.py`; D-72-07 prose comment in `enrich-before-ingest/SKILL.md:1158-1168` rewritten to state the refined rule — the `source_by_field = {...}` code line is byte-identical.
verification: new test `test_a_field_blank_in_every_unanswered_row_is_not_vetoed_by_partial_coverage` (7-row shape) — RED on original code (`{'jobtitle'}` only, assertion `>= {"mobilephone","linkedin_url"}` failed), GREEN after the fix. Reshaped D-72-07 guard test stayed green throughout. Full plugin suite: `.venv/bin/python -m pytest -q -p no:cacheprovider operator-claude-plugin/tests` — 3245 passed, 10 skipped. Root suite: no file references `preingest` (grep confirmed), nothing to run there.
oracle_type: specified
files_changed:
  - operator-claude-plugin/scripts/preingest.py (provider_sourced_fields: fixed + docstring)
  - operator-claude-plugin/tests/test_preingest_merge.py (new RED->GREEN regression test; reshaped D-72-07 guard test)
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md (D-72-07 comment prose only, code line unchanged)
