---
phase: 69-held-rows-survive-the-round
reviewed: 2026-09-07T22:04:16Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - operator-claude-plugin/scripts/suggestion_declines.py
  - operator-claude-plugin/scripts/suggest_contacts.py
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md
  - operator-claude-plugin/skills/suggestion-declines/SKILL.md
  - operator-claude-plugin/tests/test_disclosure_audit.py
  - operator-claude-plugin/tests/test_skill_sequence_coverage.py
  - operator-claude-plugin/tests/test_suggest_contacts_composition.py
  - operator-claude-plugin/tests/test_suggestion_declines.py
  - operator-claude-plugin/tests/test_suggestion_declines_skill.py
findings:
  critical: 2
  warning: 1
  info: 3
  total: 6
status: issues_found
---

# Phase 69: Code Review Report

**Reviewed:** 2026-09-07T22:04:16Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 69 builds a new durable store (`suggestion_declines.py`), routes
`suggest-contacts/SKILL.md` step 8's held rows into it instead of `held_queue`, and adds a
standalone drain skill (`suggestion-declines/SKILL.md`) offering `send`/`defer`/`delete`/
`export`. The vocabulary-boundary work (D-69-02) is sound: `PARTITION_REASON_CODES` is
disjoint from `confidence.ALL_HOLD_CODES` by test and by construction, `held_queue.py` and
`confidence.py` are byte-identical to `6b16634` (confirmed by `git diff`), and no code path
maps a partition code onto a match-gate code. `apply_action`'s `defer`/`delete`/`export`
semantics, `save()`'s validate-before-write ordering, and `_atomic_write_0600` usage are all
correct and covered by real tests (no gate function is mocked; transports are stubbed, not
the grant/dispatch functions themselves; the pre-spend pause always takes an injected
`sleep=` recorder; nothing sleeps, loops, or reaches the network).

Two problems undercut the phase's central promise ("held rows survive the round") badly
enough to block: (1) the store's own `load()`/`save()` pairing can silently destroy the
entire accumulated backlog the moment the file becomes unreadable even once — the exact
scenario D-69-03's reversibility note calls "one-way" and "discards every deferred entry" —
and it is reachable through the very fence this phase adds at `suggest-contacts/SKILL.md`
step 8; (2) the drain's own `send` fence can crash with an unhandled `KeyError` on the
single most common decline shape (`no_email`) instead of the graceful backstop its own prose
promises. Both are provable from the code as written, not hypothetical.

The known, already-filed forbidden-name-marker false positive (`"arm"`/`"secret"` matching
inside ordinary words such as "Armidale" or "Secretary") is unchanged by this phase — the
markers are copied verbatim, `first_refusal`/`_first_forbidden` refuse loudly rather than
silently drop (confirmed by
`test_a_real_company_name_containing_a_forbidden_marker_is_refused_not_dropped`), and
nothing here makes it worse. Not re-reported as a new finding per the review brief.

## Critical Issues

### CR-01: A single unreadable store file silently discards the entire accumulated backlog on the very next round

**File:** `operator-claude-plugin/scripts/suggestion_declines.py:245-255` (`load()`), `:201-223`
(`save()`) — reached from `operator-claude-plugin/skills/suggest-contacts/SKILL.md:660,681`
(step 8's held-routing fence) and `operator-claude-plugin/skills/suggestion-declines/SKILL.md:52,171`
(the drain's step 1 load / step 7 save)

**Issue:** `load()` degrades *every* unusable-file case — missing, unreadable, malformed
JSON, or a single entry that fails `_validated_entries`'s schema check (e.g. an unknown
`reason_code`, one bad `run_id`) — to the same empty `{}`, exactly mirroring
`held_queue.load()`'s reasoning and pinned by
`test_load_still_degrades_whole_for_every_case_classify_read_calls_anomalous`. That
degrade-to-`{}` is *correct* for `held_queue`, whose document is single-run and gets
overwritten by the very next run regardless. It is **wrong** for `suggestion_declines`,
whose entire design point (D-69-03) is that the document accumulates and a save "merges
into what `load()` returned... it never overwrites it."

Trace step 8's held-routing fence with an anomalous file on disk (any cause — a partial
write from a crash between the `os.replace` and a later read, a future rename of a
`PARTITION_REASON_CODES` member that makes every pre-existing entry fail its own schema
check, or simple bit rot):

```python
declines = suggestion_declines.load()   # file unreadable -> {} (backlog silently vanishes here)
for entry in held:
    ...
    declines[key] = candidate           # only THIS round's entries ever land in declines
    added += 1
if added:
    suggestion_declines.save(declines)  # overwrites the file with ONLY this round's entries
```

`save()` performs no read-before-write check of its own — it validates the entries it was
*given*, not whether it is about to clobber something it never got a chance to read. The
previously-accumulated backlog — potentially many runs' worth of correctly-held people, the
exact Roma-Turf-Club-shaped loss this whole phase exists to prevent — is gone, with no
error, no warning, and no chance for the operator to intervene, the moment `added` happens
to be truthy on a round after the file went bad. Worse: after this save, the file is
perfectly well-formed again, so `suggest-contacts/SKILL.md` step 9's own
`suggestion_declines.classify_read()` call — which runs *after* step 8's save, not before —
reports `parseable`, never `anomalous`. The operator is never told anything was lost.

The standalone drain (`suggestion-declines/SKILL.md`) is theoretically better protected —
its step 1 calls `classify_read()` before `load()` and its prose says to "say so plainly...
rather than reporting an empty backlog" on `anomalous` — but that protection lives entirely
in prose the interpreting agent must choose to honor; nothing in the module itself refuses
the save. `suggest-contacts/SKILL.md` step 8's fence has no `classify_read()` call in it at
all before the save, so for that path the loss is not just theoretically possible but
structurally unguarded.

**Fix:** Root-cause it once, in `save()`, so both callers (`suggest-contacts` step 8 and the
drain's step 7) are covered by the same change without either SKILL.md needing to remember
to call `classify_read()` first:

```python
def save(entries, path=None) -> None:
    target = Path(path) if path is not None else queue_path()
    if target.exists() and classify_read(target) == ANOMALOUS:
        raise SuggestionDeclineError(
            f"{target} exists but could not be read cleanly -- refusing to overwrite it "
            "and destroy whatever it currently holds. Report this to the operator instead "
            "of saving; nothing was written."
        )
    for key, entry in entries.items():
        refusal = first_refusal(key, entry)
        if refusal is not None:
            raise SuggestionDeclineError(refusal)
    ...
```

This preserves every existing passing test (`test_a_refused_save_leaves_the_previous_file_
byte_identical` still holds; every `tmp_path` test that never writes an anomalous file first
is unaffected) and turns a silent, unrecoverable data-loss path into the same
`SuggestionDeclineError` refusal the rest of the module already uses for "cannot persist
safely."

---

### CR-02: A drained `send` on a `no_email` entry can crash with an unhandled `KeyError` instead of the "backstop" the same step promises

**File:** `operator-claude-plugin/skills/suggestion-declines/SKILL.md:97-109` (step 4(a))

**Issue:** `no_email` is one of the five `PARTITION_REASON_CODES` and, per
`suggest_contacts.synthesise_rows`, a row held for that reason never carried an `"email"`
key in the first place (only `firstname`/`lastname`/`jobtitle`/`company` are ever set before
the waterfall runs, and a `no_email` decline is precisely the case where the waterfall never
filled one in). `build_entry`'s `ROW_FIELD_ALLOWLIST` filter (`{key: row[key] for key in
ROW_FIELD_ALLOWLIST if key in row}`) then never adds an `"email"` key to the stored entry
either, since the key was never present to copy.

Step 4(a)'s fence:

```python
records = [
    {"record_type": "contacts",
     "row": {**entry["row"], **supplied.get(key, {}), "company_id": entry["company_id"]},
     "provenance": entry["provenance"]}
    for key, entry in chosen.items()
]
extraction.validate(suggest_contacts.round_artifact(records))
rows = [record["row"] for record in records]

send_ids = sorted({entry["company_id"] for entry in chosen.values()})
send_domains = [record["row"]["email"].rpartition("@")[2] for record in records]
```

Two independent problems in this one block:

1. `extraction.validate(...)`'s return value is never bound or inspected. `has_identity`
   accepts a `firstname`+`lastname`+`company` row without any email at all (identity group
   2 of `required_identity.any_of`), so `validate()` will not reject a still-emailless row —
   it cannot be relied on as "the gate" the prose claims it is, for this specific field.
2. `send_domains` unconditionally indexes `record["row"]["email"]`. If the operator picks
   `send` for a `no_email` entry and `supplied.get(key, {})` does not happen to include an
   `"email"` key (nothing in step 3 or step 4 *requires* the operator supply it before
   `send` is chosen — the prose only says the field gets "merged onto the stored row" if
   supplied), this line raises `KeyError: 'email'` and the whole drain aborts.

This directly contradicts the step's own claim two lines later: *"step 7's own
`extraction.hold_emailless` is the backstop if the field is still missing after this fence,
so a still-emailless row is held there rather than written blank."* That backstop is never
reached — the crash happens in *this* fence, before step 7 is even entered. Compare
`enrich-before-ingest/SKILL.md`'s own step 7 (line ~774), which calls
`extraction.hold_emailless(merge_report.rows)` and computes everything downstream — CSV,
domains — from the `sendable_rows` half only, *before* any domain-based figure is built. The
drain's step 4(a) skips that ordering entirely.

Untested: every test that exercises step 4's send fence
(`test_a_drained_send_clears_the_same_gates_a_normal_send_clears`,
`test_a_drained_send_runs_step_5s_gates_before_step_7`,
`test_a_drained_send_is_removed_only_after_the_outcome_is_recorded`) supplies a full email
via `supplied`; none drives the still-missing-email path this step's own prose describes as
handled.

**Fix:** Reorder to match the pattern this same document cites (`enrich-before-ingest` step
7): call `extraction.hold_emailless(rows)` before building `send_domains`, hold what it
holds (report it to the operator the same way a still-emailless spreadsheet row is held —
not silently dropped, not crashed on), and build `send_ids`/`send_domains`/the dispatch CSV
from the sendable half only:

```python
extraction.validate(suggest_contacts.round_artifact(records))
rows = [record["row"] for record in records]
sendable_rows, held_rows = extraction.hold_emailless(rows)
# report held_rows to the operator; they stay in suggestion_declines, unremoved,
# for the next drain -- exactly like any other held row

send_ids = sorted({entry["company_id"] for entry in chosen.values()})
send_domains = [row["email"].rpartition("@")[2] for row in sendable_rows]
```

## Warnings

### WR-01: A batch mixing `send` with `defer`/`delete`/`export` in one sitting can silently lose the non-send picks if the send fails

**File:** `operator-claude-plugin/skills/suggestion-declines/SKILL.md:162-171` (step 7)

**Issue:** Step 7's apply-and-save fence is one flat, uncontrolled loop:

```python
for key, action in picks.items():
    declines = suggestion_declines.apply_action(declines, key, action)
suggestion_declines.save(declines)
```

D-69-05/D-69-08 describe the drain as one sitting where the operator answers per entry and
"every entry gets its own answer" — implying a realistic sitting picks `send` for some
entries and `defer`/`delete`/`export` for others in the same pass. Step 4's own send fence
(4(b)/(c)) runs the real `armed_window`/`dispatch.dispatch` call *before* step 7 is reached,
inside a `try/finally` that re-raises on a transport failure (proven by
`test_a_drained_send_is_removed_only_after_the_outcome_is_recorded`). If that exception
propagates — the documented, tested, and correct behavior for a failed send — step 7's loop
is never reached at all, for *any* key, not just the failed send's. An operator who also
chose `delete` for an unrelated person in the same sitting loses that decision too; nothing
in the SKILL.md or the test suite drives a mixed-action batch (`picks` with more than one
action) to check this. No test in `test_suggestion_declines_skill.py` references `picks`
directly.

Consequence is bounded (delete/defer/export are re-askable next time, nothing is written to
HubSpot incorrectly), but it is a real, untested loss of already-made operator decisions on
every send failure in a mixed batch, worth fixing rather than shipping silently.

**Fix:** Apply and save the non-send picks first, independently of whether any send
succeeds:

```python
non_send = {k: a for k, a in picks.items() if a != "send"}
for key, action in non_send.items():
    declines = suggestion_declines.apply_action(declines, key, action)
if non_send:
    suggestion_declines.save(declines)
# ... then run step 4's send fence; on success, apply "send" removals and save again
```

## Info

### IN-01: The composite entry key can collide for two different people at the same company if either name contains the key's own separator

**File:** `operator-claude-plugin/scripts/suggestion_declines.py:120-136` (`entry_key`)

**Issue:** `entry_key` builds `f"{company_id}{KEY_SEPARATOR}{first}{NAME_SEPARATOR}{last}"`.
The docstring already discloses that `NAME_SEPARATOR` ("|") inside a normalised name is "NOT
defended." Concretely: `first="A", last="B|C"` and `first="A|B", last="C"` both produce the
same key suffix `"A|B|C"` — two different real people at the same company could silently
overwrite one another's stored entry with no warning. `_normalize_name` only casefolds and
collapses whitespace; it does not strip or escape `|`. In practice a scraped human name
containing a literal pipe character is very unlikely, and this is a documented, accepted
limitation, not an oversight — recorded here per the review brief's explicit request to
validate the "cannot collide" claim in D-69-04, which does not fully hold in the strict
sense.

**Fix (low priority, only if this is ever observed in practice):** Encode the key
unambiguously, e.g. `json.dumps([str(company_id), first, last])`, instead of raw
concatenation with a reusable separator character.

### IN-02: `export_rows` raises a bare `KeyError` on an unknown key, unlike every other function in this module

**File:** `operator-claude-plugin/scripts/suggestion_declines.py:328-366` (`export_rows`)

**Issue:** `apply_action` explicitly checks `if key not in entries: raise
SuggestionDeclineError(...)` with a clear message. `export_rows` does the equivalent lookup
(`entry = entries[key]`) with no such check — a key not present in `entries` (e.g. a stale
`chosen_keys` list built against an earlier snapshot of the store) raises a bare `KeyError`
instead of the module's own domain error. Low practical risk since `chosen_keys` is derived
by the interpreting agent from the same `declines` map it is exporting from, but worth
aligning for consistency.

**Fix:**

```python
for key in keys:
    if key not in entries:
        raise SuggestionDeclineError(f"key {key!r} is not in the entries map. Nothing was written.")
    entry = entries[key]
    ...
```

### IN-03: Docstring typo — duplicated `classify_read()` mention

**File:** `operator-claude-plugin/scripts/suggestion_declines.py:228`

**Issue:** `` shared by `load()` and `classify_read()``classify_read()` so both agree...`` —
a stray duplicated, mis-backticked mention. Cosmetic only.

**Fix:** `` shared by `load()` and `classify_read()` so both agree...``

---

_Reviewed: 2026-09-07T22:04:16Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
