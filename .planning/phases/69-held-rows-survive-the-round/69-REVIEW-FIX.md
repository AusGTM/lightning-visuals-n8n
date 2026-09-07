---
phase: 69-held-rows-survive-the-round
fixed_at: 2026-09-08T00:00:00Z
review_path: .planning/phases/69-held-rows-survive-the-round/69-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 1
status: partial
---

# Phase 69: Code Review Fix Report

**Fixed at:** 2026-09-08
**Source review:** .planning/phases/69-held-rows-survive-the-round/69-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (CR-01, CR-02, WR-01, IN-02, IN-03) — fix_scope was
  `critical+warning`, with IN-02/IN-03 pulled in per the config's explicit
  one-liner carve-out. IN-01 was explicitly out of scope (skip-with-note).
- Fixed: 5
- Skipped: 1 (IN-01, per the config's own instruction — not attempted)

## Fixed Issues

### CR-01: A single unreadable store file silently discards the entire accumulated backlog

**Files modified:** `operator-claude-plugin/scripts/suggestion_declines.py`,
`operator-claude-plugin/skills/suggest-contacts/SKILL.md`,
`operator-claude-plugin/tests/test_suggestion_declines.py`,
`operator-claude-plugin/tests/test_suggest_contacts_composition.py`
**Commit:** `a5bd494`

**Applied fix:** `save()` now resolves its target path first and, if a file already
exists there and `classify_read()` reports it `ANOMALOUS`, raises
`SuggestionDeclineError` naming the path before validating a single entry or writing
anything — matching the reviewer's suggested fix exactly (root-caused once, in
`save()`, so every caller — both `suggest-contacts` step 8 and the drain's step 7 —
is covered without either SKILL.md needing to remember to call `classify_read()`
first). `suggest-contacts/SKILL.md` step 8's held-routing fence now wraps its
`save()` call in `try/except SuggestionDeclineError`, capturing the message into
`save_refused` instead of letting it crash the round; step 9's report prose was
extended to name `save_refused` individually, in the same style as the existing
`unstorable` list, and to say plainly that this round's newly-held people are shown
but were not persisted — never a halt (Phase 68's standing rule).

RED-then-GREEN: added `test_save_refuses_to_overwrite_a_preexisting_anomalous_file`
(confirmed failing with "DID NOT RAISE SuggestionDeclineError" against the
pre-fix code), then the fix, then confirmed green. Also added a composition test,
`test_a_save_refused_by_an_anomalous_preexisting_file_is_caught_not_raised`,
driving the fixed step-8 try/except shape end to end under `tmp_path`.

### CR-02: A drained send on a no_email entry can crash with an unhandled KeyError

**Files modified:** `operator-claude-plugin/skills/suggestion-declines/SKILL.md`,
`operator-claude-plugin/tests/test_suggestion_declines_skill.py`,
`operator-claude-plugin/tests/test_skill_sequence_coverage.py`
**Commit:** `8fcacdc`

**Applied fix:** Step 4(a)'s fence now calls `extraction.hold_emailless(rows)`
immediately after building `rows`, before `send_domains` is ever computed —
mirroring `enrich-before-ingest/SKILL.md` step 7's own ordering, per the reviewer's
cited precedent. `send_domains` is now built over `sendable_rows` only
(`[row["email"].rpartition("@")[2] for row in sendable_rows]`), never by indexing
`record["row"]["email"]` directly. Prose was updated to explain that step 7's own
re-entered `hold_emailless` call becomes a redundant no-op once every row here is
already sendable, and that a still-emailless row is held (not dropped, not crashed
on).

RED-then-GREEN: added a text-level test,
`test_the_drain_send_fence_holds_emailless_rows_before_computing_send_domains`,
confirmed `ValueError: substring not found` (no `hold_emailless` call existed yet)
against pre-fix SKILL.md text, then the fix, then confirmed green. Also added
`test_a_drained_send_on_a_still_emailless_no_email_entry_holds_it_instead_of_crashing`
driving the fixed logic directly (no `KeyError`, zero transport calls, entry stays
in the store) — this one exercises the already-correct `extraction.hold_emailless`
primitive directly and was green from the start; the text-level test is what
actually proves the SKILL.md fence itself was fixed.

The fence's new three-call sequence
(`extraction.validate -> suggest_contacts.round_artifact -> extraction.hold_emailless`)
was re-registered in `test_skill_sequence_coverage.py`'s `COVERED` in the same
commit, replacing the now-nonexistent two-call tuple, and the covering test
(`test_a_drained_send_clears_the_same_gates_a_normal_send_clears`) was extended to
actually call `extraction.hold_emailless` in the fixed position rather than merely
being named as the covering test without driving the new call.

### WR-01: A mixed send/defer/delete/export batch can lose non-send picks if the send fails

**Files modified:** `operator-claude-plugin/skills/suggestion-declines/SKILL.md`,
`operator-claude-plugin/tests/test_suggestion_declines_skill.py`
**Commit:** `512b16e`

**Applied fix:** Step 3 (where the operator states per-entry picks) now ends with a
fence that applies and saves every non-`"send"` pick immediately — `non_send =
{key: action for key, action in picks.items() if action != "send"}`, applied via
`apply_action` and saved once — before step 4's send is ever attempted, matching the
reviewer's suggested fix. Step 7's apply-and-save fence was narrowed to touch only
`action == "send"` picks (still gated on `write_grant.record_dispatch_outcome` having
already been called, unchanged from before); its prose now states plainly that
non-send picks were already applied and saved at step 3, so a failed send below
never touches them.

Deviation from the reviewer's literal snippet placement: rather than inlining the
non-send apply/save inside step 4 itself (which would have broken
`test_the_drain_send_fence_binds_step_5s_inputs` — that test asserts step 4's FIRST
python fence binds `send_ids`/`send_domains`/`allow_create` by name), the same logic
was placed at the end of step 3, the step immediately preceding step 4 in the
document's read order. Functionally identical: it still runs unconditionally before
send is ever attempted, and it reuses the existing `("suggestion_declines.apply_action",
"suggestion_declines.save")` `COVERED` identity (same two-call tuple, no new
sequence-coverage registration needed).

RED-then-GREEN: added a text-level test,
`test_non_send_picks_apply_and_save_before_the_send_fence_is_ever_reached`,
confirmed it failed (step 3 had no `apply_action`/`save` fence yet) against pre-fix
SKILL.md text, then the fix, then confirmed green. Also added
`test_a_mixed_batch_keeps_non_send_decisions_when_the_send_fails`, driving a real
mixed batch (`send`/`defer`/`delete`) through the store end to end under `tmp_path`
and asserting the delete is applied, the defer is present, and the (unreachable-send)
entry stays in the store. One pre-existing test,
`test_a_drained_send_is_removed_only_after_the_outcome_is_recorded`, needed a
one-line adjustment: it located the send's `apply_action(` call via
`text.index("suggestion_declines.apply_action(")`, which now matches step 3's
*earlier* non-send call first; changed to search from `rdo_index` onward so it still
locates step 7's send-only call specifically — the invariant it checks
(`record_dispatch_outcome` before the send's own `apply_action`) is unchanged and
still verified.

### IN-02: export_rows raised a bare KeyError on an unknown key

**Files modified:** `operator-claude-plugin/scripts/suggestion_declines.py`,
`operator-claude-plugin/tests/test_suggestion_declines.py`
**Commit:** `67fcf08`

**Applied fix:** `export_rows` now checks `if key not in entries` and raises
`SuggestionDeclineError(f"key {key!r} is not in the entries map. Nothing was
written.")` before the lookup, matching `apply_action`'s own convention exactly
(same message shape, reused verbatim from the reviewer's suggested fix).

RED-then-GREEN: added `test_export_rows_raises_suggestion_decline_error_on_an_unknown_key`,
confirmed it failed with a bare `KeyError` against pre-fix code, then the fix, then
confirmed green.

### IN-03: Docstring typo — duplicated classify_read() mention

**Files modified:** `operator-claude-plugin/scripts/suggestion_declines.py`
**Commit:** `67fcf08`

**Applied fix:** One-line docstring correction in `_validated_entries`, exactly as
the reviewer specified: `` shared by `load()` and `classify_read()``classify_read()`
so both agree...`` → `` shared by `load()` and `classify_read()` so both agree...``.
No test needed (cosmetic-only, no behavior).

## Skipped Issues

### IN-01: The composite entry key can collide if either name contains the key's own separator

**File:** `operator-claude-plugin/scripts/suggestion_declines.py:120-136` (`entry_key`)
**Reason:** Explicitly out of scope per this fix pass's `fix_scope` instruction
("skip the separator-collision one with a note"). The review itself classifies this
as "a documented, accepted limitation, not an oversight" and gives the fix a
"low priority, only if this is ever observed in practice" qualifier. Not attempted.
No code or test changes made for this finding.

## Constraints Honored

- No `while` loop, `import time`, or `sleep()` introduced in any plugin script.
- Plugin scripts remain pure (no HTTP client, no model call added).
- No SKILL.md body gained the substring "tier" or "icp" (unaffected by these fixes).
- `held_queue.py` and `confidence.py` untouched.
- Nothing under `n8n/` touched.
- Nothing armed; no network; no durable writes outside `tmp_path` in any new/changed
  test (`no_network` / `no_durable_writes` conftest fixtures apply as before).
- Fixture jobtitles introduced in new tests use "Treasurer", never "Secretary".
- Every commit message carries both required trailer lines via `git commit -F`.

## Final Verification

```
.venv/bin/python -m pytest operator-claude-plugin/tests/ -q
2816 passed, 5 skipped in 14.09s
```

(2816 ≥ the required 2809 baseline; 0 failed; 5 skipped, unchanged from baseline.)

```
.venv/bin/python -m pytest operator-claude-plugin/tests/test_skill_sequence_coverage.py operator-claude-plugin/tests/test_disclosure_audit.py -q
35 passed in 0.08s
```

---

_Fixed: 2026-09-08_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
