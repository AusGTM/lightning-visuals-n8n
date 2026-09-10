---
phase: quick-260911-anx
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/tests/test_preingest_merge.py
  - operator-claude-plugin/tests/test_preingest_preview.py
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - .planning/todos/completed/2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md   # moved from pending/
files_deleted:
  - .planning/todos/pending/2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md
autonomous: true

must_haves:
  truths:
    - "A row whose `jobtitle` is already non-empty and whose waterfall response carries a DIFFERING `jobtitle` ends the merge holding the waterfall value, for BOTH `enrich-before-ingest` and `suggest-contacts` (they call the same `preingest.merge_enriched`)."
    - "A row whose `email` (or any of the five location fields, `phone`, `mobilephone`, `lv_linkedin_url`) is already non-empty is NEVER replaced by a differing waterfall value — unchanged from today."
    - "A key whose `contacts:` policy entry omits `protect_if_current_present` (`seniority`, `lv_persona_group`), or which has no `contacts:` entry at all (`firstname`, `lastname`), keeps today's fill-only behaviour."
    - "Every differing value is recorded in `MergeResult.conflicts` — both the ones kept and the ones replaced — and each entry says which happened."
    - "An unresolvable or malformed `field_policy.yaml` degrades to protect-everything (today's behaviour), never to replace-everything."
    - "`render_enriched_preview` shows a replaced value under the row's `enriched_values`, so the operator's one pre-arm look never shows only the superseded value."
  artifacts:
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/tests/test_preingest_merge.py
    - operator-claude-plugin/tests/test_preingest_preview.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  key_links:
    - "`merge_enriched`'s fill-versus-conflict branch reads the per-field rule through `resolve_policy_path` — the SAME seam `promotable_contact_props` already uses (RICH-04, Phase 65 Plan 02), never a second YAML resolution rule."
    - "`config/field_policy.yaml` `contacts.jobtitle.protect_if_current_present: false` is the ONE source of the new behaviour; no key is hardcoded in Python."
    - "`render_enriched_preview` -> `_row_view` -> `enriched_values` is the operator-facing consequence of a replaced value; `SKILL.md` step 6's conflict sentence is its prose."
---

<objective>
Close todo `2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present`
under its **Operator ruling 2026-09-11 (per-field, both callers)**.

`preingest.merge_enriched` applies ONE blanket fill-not-overwrite rule to every key,
silently overriding `config/field_policy.yaml`'s own, more permissive per-field rule for
`jobtitle` (`protect_if_current_present: false`). A richer waterfall title is recorded in
`conflicts` and discarded.

Purpose: the policy file becomes the single source for per-field protection, for both
`enrich-before-ingest` and `suggest-contacts` (one shared `merge_enriched`, one rule).
Output: a per-field read on the existing policy seam, a fill-versus-conflict branch that
honours it, a conflicts entry that says which of the two happened, a preview that shows a
replaced value, and the SKILL prose that no longer claims the source value is always kept.

Explicitly OUT of scope, per the ruling: per-field `min_confidence` in the merge.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/todos/pending/2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md
@operator-claude-plugin/scripts/preingest.py
@operator-claude-plugin/config/field_policy.yaml
</context>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: per-field protect_if_current_present in merge_enriched</name>
  <files>operator-claude-plugin/scripts/preingest.py, operator-claude-plugin/tests/test_preingest_merge.py</files>
  <read_first>
    - `operator-claude-plugin/scripts/preingest.py` lines 32-96 (`PLUGIN_POLICY_PATH`,
      `REPO_POLICY_PATH`, `resolve_policy_path`, `promotable_contact_props`) — the RICH-04
      seam this task extends.
    - `operator-claude-plugin/scripts/preingest.py` lines 679-800 (`merge_enriched` and its
      docstring's "Fill-not-overwrite" paragraph).
    - `operator-claude-plugin/config/field_policy.yaml` `contacts:` — `jobtitle` is the ONLY
      entry carrying `protect_if_current_present: false`; `seniority` and `lv_persona_group`
      carry no such key at all.
    - `operator-claude-plugin/tests/test_preingest_merge.py` around lines 228-244, 545-590 and
      660-685 — the three existing tests that assert on a `conflicts` entry.
  </read_first>
  <behavior>
    RED FIRST — write these before touching `merge_enriched`, run them, observe the failures,
    and record the RED output in the SUMMARY. A guard test that was never seen red is not a
    guard.

    - `jobtitle` present ("Head of Marketing") + differing response value
      ("Head of Marketing and Content") -> merged row holds the RESPONSE value, and
      `conflicts` carries one entry for it marked as replaced. (RED today: the row keeps
      "Head of Marketing".)
    - `email` present + differing response value -> merged row holds the SOURCE value,
      one conflict entry marked NOT replaced. (This is the ruling's "operator-typed email
      never replaced" test — repoint the existing
      `test_a_non_empty_source_value_is_never_overwritten_and_is_reported_as_conflict`
      from `jobtitle` to `email` rather than adding a fourth near-identical test.)
    - `test_the_allowlist_is_a_union_and_a_shared_key_behaves_as_before` (around line 571)
      ALSO sets `rows[0]["jobtitle"] = "Director"` and asserts it survives — its ROW
      assertion goes red under this change, not just its conflict-entry keys. Repoint it to
      `email` too (still in the shared set, so its union property is unchanged) and rewrite
      its "behave byte-identically to today" comment: `jobtitle` deliberately no longer does.
    - A key with a `contacts:` entry that OMITS `protect_if_current_present` (`seniority`)
      present + differing -> kept, entry NOT replaced. The existing
      `test_a_present_widened_key_is_never_overwritten_and_records_a_conflict` already
      asserts this; update only its conflict-entry keys.
    - A key with NO `contacts:` entry at all but in `extraction.canonical_props()`
      (`firstname` or `lastname`) present + differing -> kept, entry NOT replaced. New test —
      this is the ruling's "a field absent from policy keeps today's fill-only behaviour".
    - `jobtitle` present + BYTE-EQUAL response value -> no conflict entry, nothing written
      (the existing byte-equal test's property, asserted for `jobtitle` too).
    - Fail-safe: with BOTH `PLUGIN_POLICY_PATH` and `REPO_POLICY_PATH` monkeypatched to
      nonexistent paths, a present, differing `jobtitle` is NOT replaced. Add this as one
      assertion inside the existing unresolvable-policy test (around line 545), not a new
      test file section.
  </behavior>
  <action>
    Extend the EXISTING RICH-04 policy seam; do not add a second YAML reader or a second
    resolution rule.

    (1) Factor the defensive YAML load `promotable_contact_props` already performs into one
    private module-level helper that takes the same optional `policy_path`, calls
    `resolve_policy_path`, and returns the `contacts:` mapping — or an empty mapping on any
    failure (unresolvable, unreadable, not a mapping, `contacts:` missing or not a mapping).
    Rewrite `promotable_contact_props` to read from it so exactly one load path exists. Keep
    the no-module-level-cache property its docstring states: re-read fresh on every call.

    (2) Add a sibling public function returning the `contacts:` keys whose entry carries
    `protect_if_current_present` set to the literal boolean `false` — an `is False` identity
    test, never a truthiness test, so a missing key, a `null`, or a string never opts a field
    in. Its degradation direction is the OPPOSITE of `promotable_contact_props`': an empty
    result means "nothing is refreshable", which collapses to today's protect-everything
    behaviour. Say that in its docstring and say why: a widening read may degrade to a
    smaller set, and this read must degrade to the SAFER one.

    (3) In `merge_enriched`, build that set once beside `allowed_keys` (same place, same
    single call per merge — never per row, never per key). In the `_present(current)` branch,
    when the values differ: append the conflict entry as today, then write the response value
    onto the merged row only when the key is in that set. Byte-equal values still record no
    conflict and write nothing.

    (4) Conflict entry shape: replace `kept` with `source_value` and add `replaced` (a bool).
    `kept` names a value that was NOT kept in the new case, and the operator reads these — do
    not keep a key whose name is false half the time. Update the three existing tests'
    entries. Grep first to confirm nothing outside `preingest.py` and
    `tests/test_preingest_merge.py` reads the `kept` key: `write_grant.py`'s comments and the
    CHANGELOG describe conflicts in prose only and are NOT to be edited.

    (5) Update `merge_enriched`'s own "Fill-not-overwrite" docstring paragraph to state the
    per-field rule, name `field_policy.yaml` as its one source, name the ruling
    (operator, 2026-09-11), state that BOTH callers get the same rule, and state that
    per-field `min_confidence` is deliberately NOT read here.

    Do NOT edit either `field_policy.yaml` — `jobtitle` already carries
    `protect_if_current_present: false` in both copies, and the byte-identical parity test
    must stay green untouched. Do NOT add a `policy_path` parameter to `merge_enriched`;
    tests inject by monkeypatching the two path constants, as the existing ones do.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py -q</automated>
  </verify>
  <done>
    `jobtitle` refreshes, `email` and the location/phone/linkedin fields do not, a policy-less
    key and a policy-key-less field both keep today's behaviour, an unresolvable policy
    protects everything, and every differing value is still recorded in `conflicts` with
    `replaced` saying which happened. The RED run of the new jobtitle test is recorded in the
    SUMMARY.
  </done>
</task>

<task type="auto">
  <name>Task 2: show a replaced value in the pre-arm preview and fix the SKILL prose</name>
  <files>operator-claude-plugin/scripts/preingest.py, operator-claude-plugin/tests/test_preingest_preview.py, operator-claude-plugin/skills/enrich-before-ingest/SKILL.md</files>
  <read_first>
    - `operator-claude-plugin/scripts/preingest.py` `render_enriched_preview` -> `_row_view`
      (around lines 1115-1140) — `source_values` is built from the ORIGINAL row,
      `enriched_values` from "present in merged AND absent from original".
    - `operator-claude-plugin/tests/test_preingest_preview.py` lines 43-80 — the three tests
      that pin `enriched_values`.
    - `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` lines 776-786 (step 6's
      conflict sentence).
  </read_first>
  <action>
    Task 1 makes `_row_view`'s `enriched_values` predicate wrong: a replaced `jobtitle` is
    present in the original, so it is excluded, and `source_values` shows the SUPERSEDED
    value. The operator's one look before arming would show only the value that is not going
    to be written.

    Change the `enriched_values` predicate from "absent from the original" to "differs from
    the original", comparing against the `source_values` dict already built one line above
    (it holds only present originals, so an absent or blank original compares as empty and a
    filled key still lands in `enriched_values` exactly as today). Do not change
    `source_values` — showing the operator their own original beside the new value is the
    point. Add one test asserting a replaced key appears in `enriched_values` while
    `source_values` still shows the original; the three existing `enriched_values` tests must
    stay green unmodified.

    Then fix `SKILL.md` step 6. Its current sentence — "a case where the source's own value
    and a provider's differing value both exist, and the source's value was kept" — is now
    false for a `protect_if_current_present: false` field. Rewrite it to tell the operator
    that a conflict is a source value and a differing provider value, that the report says
    for each one which value the row now carries, and that most fields keep the source value
    while a field the policy marks refreshable takes the provider's. Keep it to prose in the
    operator's terms; do not name the YAML key or paste policy in the skill.

    CONSTRAINT on that sentence: `operator-claude-plugin/tests/test_autonomy_switch_prose.py`
    reads this whole SKILL and forbids the lowercased substrings `icp` and `tier` anywhere in
    it (D-10b). Neither word — nor any word containing them — may appear in the new prose.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests -q</automated>
  </verify>
  <done>
    A replaced value is visible in the enriched preview beside the operator's original, the
    SKILL no longer claims the source value is always kept, and the FULL plugin suite is
    green (including `test_enrich_before_ingest_skill_contract.py` and every other test that
    parses that SKILL).
  </done>
</task>

</tasks>

<verification>
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — full plugin suite green.
- `/usr/bin/grep -rn '"kept"' operator-claude-plugin/scripts operator-claude-plugin/tests | /usr/bin/grep -v __pycache__` returns nothing — the renamed conflict key has no stragglers.
- `git diff --stat -- config/ operator-claude-plugin/config/` is EMPTY — no policy YAML was edited, so the byte-identical parity test is untouched.
- `git diff --stat -- n8n/ src/ scripts/` is EMPTY — this is a plugin-side merge rule; neither n8n engine nor the Python oracle is in scope.
- No plugin version bump, no CHANGELOG entry: eight batch siblings share those two files and one bump at batch close avoids serializing every wave.
- Batch ordering note: sibling `260911-anz` declares `depends_on: ["260911-anx"]` and edits
  `render_enriched_preview`'s docstring, `test_preingest_preview.py` and the same SKILL AFTER
  this item lands. Leave its ground clear — this plan changes `_row_view`'s `enriched_values`
  predicate and step 6's conflict sentence only, and touches no line of the
  `partition_for_ingest` -> `confidence.assess` verdict chain anz owns.
</verification>

<success_criteria>
- The todo's ruling is implemented per-field from `field_policy.yaml`, for both callers, through the one existing policy seam.
- `jobtitle` accepts a differing waterfall value; `email` and the `protect_if_current_present: true` fields never do.
- A field absent from the policy — or present without the key — keeps today's fill-only behaviour, and so does an unresolvable policy.
- Every replaced value is recorded in `conflicts` and visible in the pre-arm preview.
- Full plugin suite green; zero diff in `config/`, `n8n/`, `src/`, `scripts/`.
</success_criteria>

<output>
Create `.planning/quick/260911-anx-todo-2026-09-07-merge-enriched-ignores-jobtitles-own-protect/260911-anx-SUMMARY.md` when done.
Move `.planning/todos/pending/2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md` to `.planning/todos/completed/` as part of the final commit.
</output>
