---
phase: 58-take-what-the-operator-actually-has
reviewed: 2026-08-26T00:00:00Z
depth: standard
files_reviewed: 30
files_reviewed_list:
  - operator-claude-plugin/config/company_column_mapping.yaml
  - operator-claude-plugin/scripts/extraction.py
  - operator-claude-plugin/scripts/company_domain.py
  - operator-claude-plugin/scripts/enrichment.py
  - operator-claude-plugin/scripts/cost_guard.py
  - operator-claude-plugin/config/cost_rates.json
  - operator-claude-plugin/skills/contact-upload/extraction.md
  - operator-claude-plugin/skills/contact-upload/SKILL.md
  - operator-claude-plugin/skills/enrich-records/SKILL.md
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - scripts/probe_company_propose_mode.py
  - scripts/fix_sfv_region.py
  - scripts/remediate_veto_companies.py
  - n8n/code/normalizeProviders.js
  - n8n/code/mergeCompanies.js
  - n8n/code/providerConflict.js
  - n8n/code/judge.js
  - n8n/code/escalation.generated.js
  - scripts/gen_escalation_js.py
  - scripts/build_cloud_workflows.py
  - config/escalation_policy.yaml
  - config/field_policy.yaml
  - src/judge.py
  - operator-claude-plugin/tests/test_company_extraction.py
  - operator-claude-plugin/tests/test_company_domain_confirm.py
  - operator-claude-plugin/tests/test_enrichment_envelope.py
  - operator-claude-plugin/tests/test_company_research_envelope.py
  - operator-claude-plugin/tests/test_cost_guard.py
  - operator-claude-plugin/tests/test_extraction_contract.py
  - tests/n8n/providerConflict.test.mjs
  - tests/n8n/materialConflictNoVetoFlip.test.mjs
  - tests/n8n/companyNativeFields.test.mjs
  - tests/n8n/judge.test.mjs
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: issues_found
---

# Phase 58: Code Review Report

**Reviewed:** 2026-08-26
**Depth:** standard
**Files Reviewed:** 30 (scoped via `git diff 5e79b670..123051f`, the phase's own commit range, excluding `.planning/`, generated `n8n/wf_*.json`, and the re-baselined frozen fixture)
**Status:** issues_found

## Summary

Reviewed the full Phase 58 diff: the new company-extraction lane (58-01), the propose-mode
spike (58-02), the domain confirm/decline module (58-03), the priced/declinable research
line (58-04), native `country`/`city`/`numberofemployees` wiring (58-05), and the
material-conflict suppression guard (58-06). The Python↔JS parity checks (field_policy.yaml
vs. `mergeCompanies.js`'s `DEFAULT_COMPANY_POLICY`, and `escalation_policy.yaml` →
`src/judge.py` → `escalation.generated.js`) hold exactly — both `country`/`city`/
`numberofemployees` classification and the five `MATERIAL_CONFLICT_GROUPS` are declared
once and mechanically propagated with no hand-typed second copy. The 58-06
suppress-unless-adjudicated guard, the domain confirm/decline atomicity module, and the
`fill_blank_only` non-clobber gate in `mergeCompanies.js` were traced end to end and hold up
under adversarial reasoning; I reproduced the claimed behaviors locally (`pytest`, `node
--test`) and all pass as reported.

One genuine correctness defect was found and reproduced live against the real code: the new
per-record-type "companies-first" reassembly in `extraction.py::validate()` can silently
defeat the D-07 no-invention guard for a mixed contact+company artifact — exactly the new
capability this phase ships. Two further items are quality/robustness gaps worth fixing
before this ships further: a non-JSON-serializable `set` returned from a cost-reporting
function, and a silent, untested type-coercion fallback for a malformed `record_type` value.

## Critical Issues

### CR-01: Mixed-batch companies-first reassembly defeats the D-07 no-invention guard

**Status: fixed** — commit `5e22393`. `validate()` now tags every pre-flight `accepted`
entry with its raw `records` index (`_raw_index`, carried through a merge as
`_raw_indices`), builds a raw-index -> final-position lookup from the reassembled
companies-first list, and translates every artifact-supplied ambiguity's `record_index`
through that lookup before the D-07 contradiction pass runs — the same treatment
dedupe-generated ambiguities already got. An ambiguity whose raw index does not resolve
to a surviving row is dropped rather than guessed at. Internal `_raw_index`/`_raw_indices`
keys never reach `ExtractionResult.accepted`. Regression tests added reproducing this
finding's exact repro (contact ambiguity, company record ordered first) and the inverse
ordering — both now correctly reject the contradicting row.

**File:** `operator-claude-plugin/scripts/extraction.py:519-586` (the type-split/reassemble
block added in `validate()`, Phase 58 Plan 01)

**Issue:** `validate()` now splits the pre-flight-accepted list into `company_accepted` /
`contact_accepted`, runs `dedupe()` once per type, and reassembles the result
companies-first: `deduped_accepted = company_deduped + contact_deduped`. Every index
`dedupe()` itself produces (`record_index`/`other_record_index`/`merged_from`) is correctly
remapped onto the reassembled list's final positions via `_remap_collapse`/
`_remap_ambiguity`.

But `all_ambiguities = list(artifact.get("ambiguities") or []) + dedupe_ambiguities` folds in
the **artifact-supplied** ambiguities verbatim, with no remapping at all. The D-07
contradiction pass then does `for i, entry in enumerate(deduped_accepted): ... if
amb.get("record_index") != i: continue`, i.e. it compares an unmapped, caller-supplied index
directly against a position in the now-reordered list. Whenever at least one company record
precedes, in the final list, a contact record an ambiguity was written against, the
ambiguity's `record_index` silently lands on the wrong row. The D-07 check then evaluates a
field that doesn't exist on that (wrong) row, finds nothing to reject, and the real target
row — carrying a value for a field the extraction step explicitly flagged as unconfirmed —
passes through to `accepted` untouched. This is precisely the "said it was unsure, then
filled it anyway" invention case D-07 exists to catch (per the function's own docstring and
`extraction.md`'s "no-invention rule", the single most-cited rule in that file).

Reproduced directly against the shipped code:

```python
artifact = {
    "batch_id": "b1",
    "source": {"kind": "prose", "detail": "x"},
    "records": [
        {"row": {"email": "a@x.com", "jobtitle": "Snr Producer"},
         "provenance": {"input": "pasted_text", "locator": "l1"}},
        {"row": {"name": "Acme"},
         "provenance": {"input": "pasted_text", "locator": "l2"}, "record_type": "companies"},
    ],
    "ambiguities": [
        {"record_index": 0, "field": "jobtitle", "reason": "title looked uncertain"}
    ],
}
result = extraction.validate(artifact)
# result.rejected == []
# result.accepted includes the contact row WITH jobtitle="Snr Producer" still on it —
# the exact value the ambiguity said was unconfirmed.
```

This is not a contrived ordering: `extraction.md`'s own Phase 58 instruction ("Read it
**once** and write both kinds of row into the same artifact, companies first") is precisely
what produces this shape whenever the extraction agent (Claude, in-session, per the file's
own "you are the extractor" contract) happens to encounter a person before a company in a
source it reads top-to-bottom — a routine reading order, not an edge case. The convention is
prose-only; nothing in `extraction.py` enforces it, warns when it's violated, or protects
against it when it's followed. I also confirmed the inverse (company-first submission, with
the ambiguity's index written against the already-reassembled position) correctly rejects —
so the guard *can* work, but only when the artifact producer perfectly predicts the
post-reassembly index space by hand, for every ambiguity, in every batch. No test in
`test_company_extraction.py` or `test_extraction_contract.py` exercises a mixed-type artifact
carrying an artifact-supplied (non-dedupe-generated) ambiguity — the one D-07 test added for
this phase (`test_company_record_flagging_domain_ambiguous_with_a_value_is_rejected`) uses a
single-record, single-type artifact, which cannot exercise the reassembly/index-drift
interaction at all.

**Fix:** Give artifact-supplied ambiguities the same remapping treatment
`_remap_ambiguity`/`_remap_collapse` already apply to dedupe-generated ones. Concretely: tag
each pre-flight `accepted` entry with its original raw `records` index (e.g.
`accepted.append({"row": clean_row, "provenance": provenance, "record_type": record_type,
"_raw_index": i})`), carry that tag through the per-type split, and build a `raw_index ->
final_position` lookup from `deduped_accepted` once it's assembled (via `merged_from`/each
entry's own `_raw_index` for records that never got merged). Translate every
`artifact.get("ambiguities")` entry's `record_index` through that lookup — refusing to run
D-07 for any ambiguity whose named raw index can't be resolved — before the contradiction
loop runs, rather than trusting the caller to have hand-computed the final position:

```python
raw_to_final = {}
for i, entry in enumerate(deduped_accepted):
    for raw_i in entry.get("_raw_indices", [entry.get("_raw_index")]):
        if raw_i is not None:
            raw_to_final[raw_i] = i

remapped_artifact_ambiguities = []
for amb in artifact.get("ambiguities") or []:
    ri = amb.get("record_index")
    if isinstance(ri, int) and ri in raw_to_final:
        remapped_artifact_ambiguities.append({**amb, "record_index": raw_to_final[ri]})
    # else: index does not resolve to any surviving record — drop or flag, never guess.

all_ambiguities = remapped_artifact_ambiguities + dedupe_ambiguities
```

Add a test with the exact shape reproduced above (contact ambiguity, company record ordered
first in the final list) asserting the contact row is rejected, not silently accepted.

## Warnings

### WR-01: `cost_guard.research_line()` returns a non-JSON-serializable `set`

**Status: fixed** — commit `d9b7510`. `row_ids` is now `sorted((row.get("row_id") for row
in rows), key=lambda v: (v is None, v))` — a deterministic, JSON-serializable list, `None`
sorted safely to the end rather than raising on a mixed `str`/`None` comparison. The two
pre-existing tests in `test_company_research_envelope.py` that asserted set equality were
updated to list equality; new tests in `test_cost_guard.py` assert `json.dumps` succeeds on
the full result and that a missing `row_id` doesn't raise.

**File:** `operator-claude-plugin/scripts/cost_guard.py:166-217` (`research_line`, new in
Phase 58 Plan 04)

**Issue:** `research_line()`'s return dict includes `"row_ids": {row.get("row_id") for row in
rows}` — a Python `set`. Every other cost/report structure in this module
(`estimate_batch`, `compare`, `_verdict`) is a plain dict/list tree, and this module's own
`__main__` block dumps its output via `json.dumps(...)`. Verified live:

```python
>>> json.dumps(cost_guard.research_line([{"row_id": "r1", "name": "A"}], rates))
TypeError: Object of type set is not JSON serializable
```

Nothing in this phase's own code currently calls `json.dumps` on `research_line`'s result —
today it is only read in-session per `enrich-records/SKILL.md`'s prose instructions — so this
is not (yet) a live crash. But it is a landmine for the next caller that logs, persists, or
otherwise serializes this line the way the rest of the cost-reporting family already is, and
it is inconsistent with the module's own established convention.

**Fix:** Use a sorted list instead of a set — deterministic output is also generally
preferable for anything that might end up in a test assertion or a log line:

```python
"row_ids": sorted(row.get("row_id") for row in rows),
```

### WR-02: Malformed `record_type` is silently coerced to `"contacts"` with a misleading rejection reason

**Status: fixed** — commit `5e22393` (landed alongside CR-01: both edits touched adjacent
lines of `validate()`'s per-record pre-flight in the same pass before the first commit was
made, so they were not split into two separate commits as the atomic-per-finding rule
otherwise calls for — noted here rather than silently deviating). A `record_type` that is
present but not exactly `"contacts"` or `"companies"` is now rejected by name (`"unrecognized
record_type {value!r}: expected 'companies' or 'contacts' (or omit the key for a contact)"`)
rather than silently defaulting to the contact lane, following the `normalizeObjectType`
precedent WR-02 cites. New test asserts a near-miss spelling (`"Companies"`) is rejected with
this reason and never the contact-oriented identity message.

**File:** `operator-claude-plugin/scripts/extraction.py:471` (`validate()`, Phase 58 Plan 01)

**Issue:** `record_type = "companies" if record.get("record_type") == "companies" else
"contacts"` treats every value other than the exact literal string `"companies"` — including
plausible near-misses like `"Companies"`, `"company"`, or `"COMPANIES"` — as `"contacts"`,
silently, with no diagnostic recorded anywhere in the result (`rejected`, `dropped_keys`,
etc. carry no trace that a `record_type` value was seen and ignored). A company row
mis-tagged this way gets its company-only fields (`name`, `domain`, `industry`, `website`)
stripped as "non-canonical" against the *contact* prop set, then rejected with the
contact-oriented reason ("no identity present: needs a non-blank 'email', or all three of
'firstname'/'lastname'/'company' non-blank") — a message that gives no hint the actual
problem was an unrecognized `record_type` spelling. This is inconsistent with this
codebase's own established precedent for exactly this class of input
(`n8n/code`'s `normalizeObjectType` throws `Unsupported object type: ${input}` rather than
silently defaulting). No test in `test_company_extraction.py` covers a non-`"companies"`,
non-absent `record_type` value.

**Fix:** Treat an unrecognized non-absent `record_type` value as a rejection naming the
problem, rather than a silent contact-lane default:

```python
raw_type = record.get("row_type") if False else record.get("record_type")
if raw_type is not None and raw_type not in ("contacts", "companies"):
    rejected.append({"index": i, "reason": f"unrecognized record_type {raw_type!r}: expected 'companies' or omitted for a contact"})
    continue
record_type = "companies" if raw_type == "companies" else "contacts"
```

## Info

### IN-01: `company_domain.apply_domain_decisions` silently drops an earlier duplicate `row_id`

**File:** `operator-claude-plugin/scripts/company_domain.py:101` (`proposed_by_id = {p["row_id"]:
p for p in proposals}`)

**Issue:** If `proposals` ever contains two entries with the same `row_id` (a caller bug
upstream, not something this module can currently receive from the documented confirm-table
flow), the dict comprehension silently keeps only the last one — no error, no warning. This
is a minor inconsistency with the module's own stated design philosophy ("no silent
default", "a call that raises has applied nothing at all") applied everywhere else in the
same file. Low likelihood given the documented `row_id` minting contract elsewhere in the
plugin (`SKILL.md`: "Mint one `row_id` per row, once, for the whole batch"), but worth a
defensive check given how deliberately this module guards every other input shape.

**Fix:** Raise `DomainDecisionError` on a duplicate `row_id` in `proposals`, or note in the
docstring that `proposals` is assumed pre-deduplicated by the caller and a duplicate silently
takes the last entry.

---

_Reviewed: 2026-08-26_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
