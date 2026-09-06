# Phase 65: Round-empty re-entry, keyed on the cause - Pattern Map

**Mapped:** 2026-09-07
**Files analyzed:** 6 (2 new-function targets, 1 config, 4 test files to extend — no wholly new files)
**Analogs found:** 6 / 6 (all in-repo, no external analog needed — this phase composes existing tested primitives)

All target "files" are existing, git-tracked files being extended, not new files. Verified via
`git ls-files` — every path below is tracked.

## File Classification

| File to modify | Role | Data Flow | Closest Analog (same file, sibling function) | Match Quality |
|---|---|---|---|---|
| `operator-claude-plugin/scripts/suggest_contacts.py` (+`round_outcome`, +`ROUND_CAUSES`/`REENTRY_*` constants) | utility (pure classifier) | transform (fold over already-computed stage outputs) | `search_fallback.eligible_after_ladder` (fail-closed gate) + `suggest_contacts.WALK_ENDINGS` (closed vocabulary) | exact — same module, same fail-closed idiom, same vocabulary-pinned-by-test pattern |
| `operator-claude-plugin/scripts/preingest.py` (`merge_enriched`, RICH-04 fix) | utility (merge/CRUD-style field promotion) | transform (fill-vs-conflict decision per field) | `merge_enriched` itself, existing (widen `allowed_keys`, no new function) | exact — self-analog, one-line-shaped config fix |
| `operator-claude-plugin/config/column_mapping.yaml` (`aliases:` block widened) | config | data | itself — existing `aliases:` entries (e.g. `jobtitle: jobtitle`) | exact |
| `operator-claude-plugin/skills/suggest-contacts/SKILL.md` (step 5/7/8/9 rewired) | orchestration doc (pseudocode) | request-response (per-company loop body) | existing step 7's `if not people: verdict = search_fallback.eligible_after_ladder(attempts)` block | exact — replace inline prose-cause-reasoning with a call to `round_outcome` |
| `operator-claude-plugin/tests/test_suggest_contacts.py` (+`round_outcome` unit tests) | test | transform | existing `test_walk_ending_vocabulary_pins_to_search_fallbacks_disposition_constants` + `select_people`/`partition_for_dispatch` tests in same file | exact — same file, same fixtures (`FAMILY_LIST`, `_company_row`) |
| `operator-claude-plugin/tests/test_suggest_contacts_composition.py` (+composition test) | test | transform | Phase 64's extension of this same file for `walk_pages` (see `64-01-SUMMARY.md` Deviation 1) | exact |
| `operator-claude-plugin/tests/test_preingest_merge.py` (+RICH-04 test) | test | transform | existing `merge_enriched` fill/conflict test cases in same file | exact |
| `operator-claude-plugin/tests/test_search_fallback.py` (extend, if D-65-10 refusal-terminal-on-second-call needs a dedicated test) | test | transform | existing `eligible_after_ladder` refusal tests in same file | exact |
| `operator-claude-plugin/tests/test_report_sufficiency.py` | test (guard, no change expected) | structural/AST | `_has_while_loop` — already scans every plugin script; no new file needed, phase must stay green against it | n/a (pre-existing guard, verify only) |

## Pattern Assignments

### `round_outcome` (new function in `scripts/suggest_contacts.py`)

**Analog 1 — fail-closed without raising:** `search_fallback.eligible_after_ladder`
(`scripts/search_fallback.py:192-209`)

```python
# Source: operator-claude-plugin/scripts/search_fallback.py:192-209
if not isinstance(attempts, list) or not attempts:
    return {
        "eligible": False,
        "reason": (
            "no ladder attempt was recorded, so nothing establishes that the crawl "
            "completed -- refusing to open the search path on an empty record."
        ),
    }

for attempt in attempts:
    if not isinstance(attempt, dict):
        return {
            "eligible": False,
            "reason": (
                f"a ladder attempt is not an object ({attempt!r}), so its disposition "
                f"cannot be read -- treating the ladder as ineligible."
            ),
        }
```

Copy this idiom exactly for `round_outcome`: `isinstance` checks first on every stage input it
reads (`walk`, `held`), `return` a named-reason dict on any malformed shape, never `raise`.
D-65-03 requires the same terminal shape: `cause: "unknown"`, `reentry: "none"`, plain reason
string.

**Analog 2 — closed vocabulary pinned by test, not cross-module import:**
`scripts/suggest_contacts.py:208-218` (`WALK_ENDINGS`)

```python
# Source: operator-claude-plugin/scripts/suggest_contacts.py:208-218
WALK_GOOD_ENOUGH = "good_enough"
WALK_LADDER_EXHAUSTED = "ladder_exhausted"
WALK_CAP_EXHAUSTED = "cap_exhausted"
WALK_REFUSED = "refused"
WALK_ENDINGS = (WALK_GOOD_ENOUGH, WALK_LADDER_EXHAUSTED, WALK_CAP_EXHAUSTED, WALK_REFUSED)
```

`round_outcome`'s `CAUSE_*`/`REENTRY_*` constants should follow this exact naming/tuple
convention. If a cause literal restates a string owned by another module (e.g.
`search_fallback.SOURCE_TIER_HOLD_CODE = "search_source_not_strong"`), restate the literal and
pin equality with a test — do not import `search_fallback` into `suggest_contacts.py` (mirrors
the existing `test_walk_ending_vocabulary_pins_to_search_fallbacks_disposition_constants` test
in `test_suggest_contacts.py`, which the planner should use as the template for a
`test_round_outcome_cause_vocabulary_pins_to_...` test).

**Analog 3 — the exact shapes `round_outcome` folds (verbatim source shapes, no restatement
needed, only reading):**

`walk_pages`'s return (`scripts/suggest_contacts.py:378-385`):
```python
{
    "people": [...],      # raw deduped union, pre-role-filter
    "selected": [...],
    "dropped": [{"person": {...}, "reason": "already_associated"}],  # or "role_not_selected"
    "ended": None,          # one of WALK_ENDINGS, or None if not yet terminal
    "bar": int,
}
```

`partition_for_dispatch`'s `held` entries (`scripts/suggest_contacts.py:807-874`):
```python
{"index": int, "row": {...}, "reason": "<prose>", "reason_code": "no_email"}
# reason_code in {"no_email", "email_domain_freemail", "email_domain_mismatch", "company_domain_unknown"}
```

`search_fallback.hold_weak_sources` adds a fifth code onto the same `held` list
(`scripts/search_fallback.py:358-442`):
```python
{"index": int, "row": {...}, "reason": "<prose>", "reason_code": "search_source_not_strong"}
```

**Do not widen `confidence.ALL_HOLD_CODES`** to include these `reason_code`s —
`confidence.py:42-46`'s frozenset answers a different question ("could not identify" vs
"identified fine, declined to send"); `round_outcome` reads `partition_for_dispatch`'s
`reason_code` directly off the list it's handed. A diff touching `scripts/confidence.py` at all
is a warning sign per RESEARCH.md's Pitfall 4.

**Threading the accumulator (no cap resets), analog: existing `attempts`/`company_budget`
call convention already used at the SKILL.md step-7 call site.** Any re-entry call must pass the
SAME `attempts` list forward — never `attempts = []` for "pass 2". `company_budget(attempts)`
already derives spent-fetch count from `len(attempts)`, so "not resetting" is achieved simply by
not constructing a second list.

---

### `merge_enriched` RICH-04 fix (`scripts/preingest.py:565` / `preingest.py:655-662`)

**Analog:** the function's own existing fill-vs-conflict branch — no new function, widen the
allowlist config it reads.

```python
# Source: operator-claude-plugin/scripts/preingest.py:655-662 (existing, unchanged by fix)
current = merged.get(key)
if _present(current):
    if str(value).strip() != str(current).strip():
        conflicts.append({
            "row_id": row_id, "field": key,
            "kept": current, "provider_value": value,
        })
    continue
merged[key] = value
```

`allowed_keys = set(extraction.canonical_props())` (`preingest.py:634`) currently reads only 8
keys from `config/column_mapping.yaml`'s `aliases:` block. Recommended fix shape (RESEARCH.md's
candidate 1, the SAFE-01-compliant one): widen the `aliases:` block to add the missing
`field_policy.yaml` `contacts:` keys (`seniority`, corrected `lv_linkedin_url`, `mobilephone`,
`city`, `state`, `country`, `hs_state_code`, `hs_country_region_code`, `lv_persona_group`) —
mirroring existing alias entries:

```yaml
# Source: operator-claude-plugin/config/column_mapping.yaml aliases: block (existing pattern to extend)
jobtitle: jobtitle
"job title": jobtitle
title: jobtitle
position: jobtitle
```

Add `seniority: seniority` etc. following this identical one-key-per-alias-line shape. This
does NOT touch `merge_enriched`'s fill/conflict logic itself (root cause 2, `jobtitle`'s ignored
`protect_if_current_present: false`) — that is a larger, field-policy-aware rewrite flagged in
RESEARCH.md as a separate, deferred judgment call, not bundled into this fix.

---

### `skills/suggest-contacts/SKILL.md` (step 5/7/8/9 rewiring)

**Analog:** existing step 7 inline prose block being replaced.

```
# Existing pattern (skills/suggest-contacts/SKILL.md:413-417), to be replaced by a call to round_outcome:
people = walk["people"]
if not people:
    verdict = search_fallback.eligible_after_ladder(attempts)
    ...
```

Replace the inline `if not people:` reasoning with `verdict = round_outcome(walk, ...)`, then
route on `verdict["reentry"]`. Per D-65-08/D-65-13, this must appear at exactly two straight-line
call sites in the per-company body (pre-fallback, post-partition) — never inside a `for`/`while`
that iterates until a condition holds. No new call site beyond these two.

---

## Shared Patterns

### Fail-closed classification (applies to `round_outcome` and any RICH-04 helper touching malformed provider output)
**Source:** `operator-claude-plugin/scripts/search_fallback.py:192-236` (`eligible_after_ladder`)
**Apply to:** `round_outcome`'s handling of `walk`/`held`; extend to any new guard in
`merge_enriched` if the RICH-04 fix touches control flow (it should not, per the recommended
allowlist-only fix — pure config change, no new control flow).

### Closed vocabulary pinned by test
**Source:** `operator-claude-plugin/scripts/suggest_contacts.py:208-218` (`WALK_ENDINGS`) +
its pinning test in `test_suggest_contacts.py`
**Apply to:** `round_outcome`'s `CAUSE_*` / `REENTRY_*` constants.

### No cap resets / thread the same accumulator
**Source:** existing `attempts` / `company_budget(attempts)` / `search_fallback.rank_results`
`already_searched=N` convention (`scripts/search_fallback.py`, `scripts/suggest_contacts.py`)
**Apply to:** whatever orchestration function ends up calling `round_outcome` twice per
company — must pass the SAME `attempts` list both times.

### No `while` loop
**Source:** `operator-claude-plugin/tests/test_report_sufficiency.py::_has_while_loop` (AST guard,
already scans every plugin script file — no test change needed, only compliance)
**Apply to:** every new function in this phase.

## No Analog Found

None — this phase is entirely in-repo composition of already-tested primitives (per
RESEARCH.md's own "Standard Stack": no new dependency, no new file, no new tier). Every target
file already exists and is git-tracked.

## Metadata

**Analog search scope:** `operator-claude-plugin/scripts/`, `operator-claude-plugin/config/`,
`operator-claude-plugin/skills/suggest-contacts/`, `operator-claude-plugin/tests/`
**Files scanned:** 6 source/config/doc files + 4 test files (all read in full or by targeted
grep during RESEARCH.md's authoring session, reused here rather than re-read)
**Pattern extraction date:** 2026-09-07
