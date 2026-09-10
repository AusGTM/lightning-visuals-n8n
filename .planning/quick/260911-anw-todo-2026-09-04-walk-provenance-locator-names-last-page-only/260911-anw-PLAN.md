---
phase: quick-260911-anw
plan: 01
type: execute
wave: 1
depends_on: []           # see <objective> § "Why no dependency on 260911-ao2"
files_modified:
  - operator-claude-plugin/scripts/suggest_contacts.py
  - operator-claude-plugin/tests/test_suggest_contacts.py
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md
  - .planning/todos/pending/2026-09-04-walk-provenance-locator-names-last-page-only.md   # moved to completed/
files_deleted:
  - .planning/todos/pending/2026-09-04-walk-provenance-locator-names-last-page-only.md
autonomous: true
requirements: [PROV-01, PROV-02]   # quick-task-local handles, NOT ROADMAP requirement IDs.
                                   # PROV-01 -> Task A (per-person source_url through the fold,
                                   #            per-person locator in synthesise_rows).
                                   # PROV-02 -> Task B (SKILL.md's two stale lines, todo closed).
                                   # Both trace to
                                   # .planning/todos/pending/2026-09-04-walk-provenance-locator-names-last-page-only.md
                                   # (64-REVIEW.md § WR-01).

estimate:
  tokens: 45000
  raw_tokens: 45000      # factor 1.0, applied: false, sample_count 0 (estimate-calibration)
  tasks: 2
  confidence: low        # derived from sample_count 0, not self-rated

must_haves:
  truths:
    - "In a two-page walk, a person folded from page 1 carries page 1's URL as their provenance locator even though page 2 was fetched afterwards."
    - "A person whose name appears on both pages is attributed to the page they were FIRST seen on, matching the fold's first-wins dedupe."
    - "A person carrying no source_url (the search-fallback path, whose people never go through the fold) still gets `fetched_url` as their locator — byte-identical to today."
    - "A walk that ends on a refused final page still attributes every selected person to the page that actually yielded them; a refused page can never be a locator."
    - "`walk_pages` still returns exactly six top-level keys — the new value rides each admitted person, never a seventh key."
    - "The full plugin suite passes and no plugin script gains a `while` loop."
  artifacts:
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/tests/test_suggest_contacts.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - .planning/todos/completed/2026-09-04-walk-provenance-locator-names-last-page-only.md
  key_links:
    - "`walk_pages`' admit site is the ONLY moment the page a person came from is known; stamping there is what makes the rest per-person."
    - "`select_people` returns `dict(person, role_family=family)` — a COPY that carries every key through, which is what delivers `source_url` into `walk['selected']` with no change to `select_people` itself."
    - "`synthesise_rows`' per-record provenance dict is the only writer of `provenance.locator` for a ladder person; `extraction.validate` checks presence only, so the value may vary per record."
---

<objective>
Attribute a synthesised contact row to the page the person was actually found on, instead of to
whatever page the company's walk happened to fetch last.

Purpose: `64-REVIEW.md` § WR-01. Phase 64 made a company's walk span several pages and union their
people, but `synthesise_rows` still takes ONE `fetched_url` and stamps it on every row in the call,
and the documented caller sets that one value from the final entry of `pages`. Every person not
found on the final page — the receptionist-plus-board case the phase exists to serve — is
provenanced to a page they were never on. Phase 64's own threat model (T-64-05) asserts the
opposite, so the record and the code disagree.

Output: a `source_url` stamped on each person at the one moment it is known (the fold's admit
site), a `synthesise_rows` that reads it per person and keeps `fetched_url` as the fallback for
callers whose people never went through the fold, the two SKILL.md lines that still describe the
old semantics, and the todo closed.

**Why no dependency on 260911-ao2.** That item edits `discovery_plan`'s empty-candidates branch in
the same script and the search-fallback prose in the same SKILL.md. This plan's hunks are
`walk_pages`' fold (≈ lines 367-386), `synthesise_rows` (≈ lines 475-568), and SKILL.md lines ~325
and ~549 — all ≥ 10 lines from `discovery_plan` (much earlier in the file), from step 5's ladder
prose (~300-315), and from the fallback branch inside the step-7 block (≥ 561). Three-way merge
context is 3 lines, so the hunks cannot collide, and this item precedes ao2 in catalog order
anyway. Declared `[]` rather than serialising two independent edits.

**Deliberately NOT fixed here (record it, do not chase it):** the same last-page shape exists in
the search-fallback branch when more than one accepted URL is fetched for one company — that
branch sets a single `fetched_url` "from the page ACTUALLY fetched", singular. Out of this todo's
scope (the todo names the ladder walk). Name it in the SUMMARY; do not widen the diff.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/todos/pending/2026-09-04-walk-provenance-locator-names-last-page-only.md
@operator-claude-plugin/scripts/suggest_contacts.py
@operator-claude-plugin/skills/suggest-contacts/SKILL.md
</context>

<tasks>

<task type="tracer" tdd="true">
  <name>Task A: carry the page each person came from through the fold and into their provenance</name>
  <files>operator-claude-plugin/scripts/suggest_contacts.py, operator-claude-plugin/tests/test_suggest_contacts.py</files>
  <read_first>
    `operator-claude-plugin/scripts/suggest_contacts.py` — `select_people` (≈180-209), `walk_pages`
    (≈264-411), `synthesise_rows` (≈475-569).
    `operator-claude-plugin/tests/test_suggest_contacts.py` — the Phase 64 walk block (≈987-1240),
    including the six-key assertion at ≈1236 and the existing locator assertion at ≈189.
  </read_first>
  <behavior>
    - Two-page walk (`/contact` then `/board`), both people in a chosen family, bar high enough
      that the walk folds both pages: through `synthesise_rows`, the `/contact` person's
      `provenance.locator` is the `/contact` URL and the `/board` person's is the `/board` URL.
    - One name present on BOTH pages: the single surviving record's locator is page 1's URL
      (first-wins, matching the fold's existing dedupe).
    - Walk whose LAST page carries `disposition: WALK_REFUSED`: the person folded from the earlier
      page still gets that earlier page's URL, and no record carries the refused page's URL.
    - A person dict with no `source_url` (hand-built, as the search-fallback branch produces) still
      gets `fetched_url` as its locator — the existing assertion at ≈189 must stay green unmodified.
    - `set(walk_pages(...).keys())` is still the six documented keys — the assertion at ≈1236 stays
      green unmodified.
  </behavior>
  <action>
    Write the failing tests FIRST and observe RED. The first THREE behaviours fail against today's
    code when each test passes the walk's FINAL page URL as `fetched_url` — which is exactly what
    the documented caller did, and what makes the RED meaningful rather than manufactured. The last
    two must be GREEN from the start: they are regression guards on properties this plan must not
    disturb, not new work.

    In `walk_pages`' fold, at the admit site inside the per-page loop, append a COPY of the person
    carrying the page's own URL rather than the caller's dict:
    `new_people.append(dict(person, source_url=page.get("url")))`. A copy, never a mutation — the
    `pages` list belongs to the caller and is re-walked on every subsequent call as the ladder
    grows, so mutating it in place would rewrite history each pass. Stamp at the ADMIT site (after
    the `seen_keys` dedupe `continue`), which is what makes a duplicate keep its first sighting's
    page. The refusal check already breaks BEFORE a refused page's people are touched, so a refused
    URL can never reach this line. Add no top-level return key: the six documented keys stay
    exactly six (D-64-11 still holds — nothing added here invites another fetch), and no
    `select_people` change is needed because it already returns `dict(person, role_family=family)`,
    a copy that carries every key through.

    In `synthesise_rows`, keep `source_tier` validation and the two provenance SHAPES exactly as
    they are, but resolve the locator per person inside the record loop:
    `{**provenance, "locator": person.get("source_url") or fetched_url}`. `fetched_url` stays a
    required positional and remains the locator for any person that carries no `source_url` — that
    is the search-fallback branch and every existing test call site. The row itself is untouched:
    `source_url` rides the PERSON, never a row key, so the canonical-key assertion and
    `write_dispatch_csv`'s own refusal are unaffected.

    Update both docstrings, which are now false as written. `walk_pages`' returns paragraph must say
    every admitted person carries the URL of the page it was folded from while the return keys stay
    six. `synthesise_rows`' opening paragraph and its `source_tier` paragraph must say the locator is
    the person's own recorded page when they carry one and `fetched_url` otherwise — the 260904-5sd
    "no extra key" property still holds, since only the locator VALUE varies, never the provenance
    key set. Cite `64-REVIEW.md` § WR-01 in a one-line comment at the admit site so the next reader
    finds the finding, not just the mechanism.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py operator-claude-plugin/tests/test_suggest_contacts_composition.py -q</automated>
  </verify>
  <done>
    The three new attribution tests pass (RED observed first for the two-page and duplicate cases);
    the six-key assertion (test_suggest_contacts.py ≈1236) and the existing single-locator assertion
    (≈189) pass UNMODIFIED; `walk_pages` returns exactly six keys; no caller of `select_people`
    changed.
  </done>
</task>

<task type="auto">
  <name>Task B: align SKILL.md with the per-person locator and close the todo</name>
  <files>operator-claude-plugin/skills/suggest-contacts/SKILL.md, .planning/todos/pending/2026-09-04-walk-provenance-locator-names-last-page-only.md, .planning/todos/completed/2026-09-04-walk-provenance-locator-names-last-page-only.md</files>
  <read_first>
    `operator-claude-plugin/skills/suggest-contacts/SKILL.md` — step 6's synthesise paragraph
    (≈320-330) and step 7's code block, specifically the `fetched_url = ...` assignment (≈549) and
    the fallback-branch comment at ≈570.
    `.planning/todos/completed/2026-09-11-walker-rule-c-zero-item-output-not-a-delivery-under-v1.md`
    — one recent completed todo, for the front-matter and resolution-note shape to mirror.
  </read_first>
  <action>
    In step 7's code block, replace the `fetched_url` assignment's right-hand side with
    `plan.get("pasted_url")` and a one-line comment saying it is now only the FALLBACK locator, for
    a person the walk never folded (the search-fallback branch below sets it to the page it actually
    fetched); a ladder person's locator comes from their own recorded page. This removes the
    last-page expression the finding names — the ladder path no longer reads it at all, and the
    pasted URL is at worst a page the walk genuinely started from rather than one the person was
    never on.

    In step 6's synthesise paragraph, replace the clause promising the locator is "the URL actually
    fetched ... never the page the operator originally pasted if the ladder had to escalate past it"
    with the per-person truth: each row carries the page THAT person was found on — which is the
    pasted page for a person found there, and a later ladder page for a person found there.

    Touch NOTHING else in the file. In particular leave the fallback-branch comment at ≈570 exactly
    as it is: it stays accurate (fallback people carry no recorded page, so `fetched_url` is their
    locator) and it sits in sibling item 260911-ao2's edit zone.

    Then close the todo: `git mv` it from `.planning/todos/pending/` to `.planning/todos/completed/`
    and append a short resolution note naming quick task 260911-anw, the seam used (a per-person
    key on each admitted person, the six return keys untouched), and the test that pins it. Leave
    `resolves_phase: null` as the todo's own body instructs — a quick task is not a phase.
  </action>
  <verify>
    <automated>/usr/bin/grep -q 'fetched_url = plan.get("pasted_url")' operator-claude-plugin/skills/suggest-contacts/SKILL.md && ! /usr/bin/grep -q 'pages\[-1\]' operator-claude-plugin/skills/suggest-contacts/SKILL.md && test ! -f .planning/todos/pending/2026-09-04-walk-provenance-locator-names-last-page-only.md && test -f .planning/todos/completed/2026-09-04-walk-provenance-locator-names-last-page-only.md && .venv/bin/python -m pytest operator-claude-plugin/tests -q</automated>
  </verify>
  <done>
    SKILL.md's step-7 assignment reads from the pasted URL as a fallback only, the last-page
    expression is gone from that file, step 6's promise matches per-person semantics, the
    fallback-branch comment is byte-identical to before, the todo lives in `completed/` with a
    resolution note, and the FULL plugin suite passes (which also covers the no-`while`-loop guard
    in `test_report_sufficiency.py` and the SKILL call-sequence coverage test).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| fetched web page → row provenance | Attacker-controlled page content becomes a `locator` string that a human later trusts when judging a suggested contact. |
| suggested row → HubSpot write | A row's provenance is what `search_fallback.hold_weak_sources` and the operator read before a person is created. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-anw-01 | Repudiation | `synthesise_rows` provenance `locator` | medium | mitigate | The locator now names the page that actually yielded the person, so an operator auditing a row reaches the evidence rather than an unrelated page. This IS the fix. |
| T-anw-02 | Spoofing | a person dict carrying its own `source_url` | low | mitigate | The value is written by `walk_pages` from the FETCHED page's `url`, never read from page content or from a caller-supplied person key — the fold overwrites whatever a person dict arrived with. |
| T-anw-03 | Tampering | mutation of the caller's `pages` list | low | mitigate | The fold appends `dict(person, ...)` copies; the caller's page dicts are never written to, so re-walking the growing `pages` list stays idempotent. |
| T-anw-04 | Information disclosure | row keys | low | accept | `source_url` rides the person, never the row; the canonical-key assertion in `synthesise_rows` and `write_dispatch_csv`'s own refusal both still hold, so it cannot reach HubSpot as a property. |
| T-anw-SC | Tampering | npm/pip/cargo installs | high | accept | No package is installed by this plan — no dependency changes, no install task. |
</threat_model>

<verification>
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — full plugin suite green.
- No `n8n/` diff and no workflow regeneration: `git status --porcelain n8n/ scripts/` is empty.
- `walk_pages` still returns exactly six keys (pinned by the pre-existing assertion, unmodified).
- Residual to record in the SUMMARY, NOT to fix: the search-fallback branch still carries one
  `fetched_url` per company when it fetches more than one accepted URL.
</verification>

<success_criteria>
A person folded from an earlier page of a multi-page walk is provenanced to that page; a person
carrying no recorded page is provenanced exactly as today; the plugin suite passes; the todo is in
`completed/`.
</success_criteria>

<output>
Create `.planning/quick/260911-anw-todo-2026-09-04-walk-provenance-locator-names-last-page-only/260911-anw-SUMMARY.md` when done
</output>
