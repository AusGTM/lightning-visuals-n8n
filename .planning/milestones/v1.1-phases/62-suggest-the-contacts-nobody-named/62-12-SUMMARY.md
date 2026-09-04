---
phase: 62-suggest-the-contacts-nobody-named
plan: 12
subsystem: api
tags: [operator-claude-plugin, suggest-contacts, gap-closure, G-62-7, release]

requires:
  - phase: 62-suggest-the-contacts-nobody-named
    provides: "suggest_contacts.partition_for_dispatch (62-01..62-09), enrichment.NOT_A_COMPANY_DOMAIN + _clean_domain, n8n/code/companyLink.js's FREEMAIL_DOMAINS, 62-UAT.md's G-62-7 finding and the operator ruling recorded there, 62-11's shipped report.all_node_items fix"
provides:
  - "enrichment.FREEMAIL_DOMAINS — a frozenset mirroring n8n/code/companyLink.js's FREEMAIL_DOMAINS member for member, pinned equal by a parity test that survives the '// AU consumer ISPs' comment line"
  - "suggest_contacts.email_domain_relation(email, company_website) — pure classifier: no_email -> freemail -> company_domain_unknown -> related/mismatch, in that order"
  - "suggest_contacts.partition_for_dispatch(rows, company_domains) — company_domains now REQUIRED with no default; holds a row whose enriched email's domain is not the company's own domain or a label-boundary subdomain of it, with a reason_code and a prose reason naming both domains"
  - "operator-claude-plugin 0.38.3 — CHANGELOG entry names G-62-7 (this plan) and G-62-6 (62-11, which shipped a code change)"
affects: [suggest-contacts]

actuals:
  tokens: 6400
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "A second JS-authoritative/Python-mirror pair, following the precedent enrichment.NOT_A_COMPANY_DOMAIN already set: the backend (n8n/code/companyLink.js) stays the single source for a domain classification, the client gets a pinned-equal mirror, never a second independently-maintained list"
    - "A required parameter with no default as the enforcement mechanism for an operator ruling — company_domains has no None fallback, so a caller that forgets it raises rather than silently bypassing the rule"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/enrichment.py
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/tests/test_people_and_url_normalisation.py
    - operator-claude-plugin/tests/test_suggest_contacts.py
    - operator-claude-plugin/tests/test_suggest_contacts_composition.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - operator-claude-plugin/CHANGELOG.md
    - operator-claude-plugin/.claude-plugin/plugin.json

key-decisions:
  - "Followed 62-12-PLAN.md's Decision 1 exactly: related <=> ed == cd or ed.endswith('.' + cd), both sides through enrichment._clean_domain. Did not reuse url_fallback._canonical_authority (a fetch-guard comparator with port semantics that don't belong to a send decision)."
  - "Decision 3's accepted cost implemented and pinned as a fixture: kdaniel@lismoreturfclub.com against lismoreturfclub.com.au is a MISMATCH (no public-suffix logic), recorded in the classifier's own docstring and in the CHANGELOG."
  - "test_skill_sequence_coverage.py needed NO changes: the SKILL.md worked example's added company_domains = {...} line introduces no new module.function call (module names are all local/dict methods), so the registered call-sequence tuple for the suggest-contacts pipeline is unchanged and the existing COVERED entry still matches."
  - "G-62-6 named in the 0.38.3 CHANGELOG per Decision 7's condition: 62-11-SUMMARY.md confirms 62-11 shipped report.all_node_items and pointed two readers at it — a code change, not a diagnosis-only stop."

requirements-completed: [SUGGEST-01, SUGGEST-04, SUGGEST-05]

duration: ~20min
completed: 2026-09-04
status: complete
---

# Phase 62 Plan 12: Hold the stranger — email-domain relatedness + release Summary

**`partition_for_dispatch` now refuses to send a suggested row whose enriched email's domain is unrelated to the company that named the person — closing the measured defect where a US insurer's employee (`craig.smith@thehartford.com`) was one of the two rows that would have advanced from Roma Turf Club's own board page — shipped as plugin 0.38.3.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-09-04

## Observed RED (before any edit)

Per the plan's `<red_evidence_contract>`, captured before touching any source file:

```
>>> extraction.hold_emailless([{
...   "email": "craig.smith@thehartford.com", "firstname": "Craig",
...   "lastname": "Smith", "company": "The Roma Turf Club",
... }])
sendable: [{'email': 'craig.smith@thehartford.com', 'firstname': 'Craig',
            'lastname': 'Smith', 'company': 'The Roma Turf Club'}]
held: []
```

The stranger's row comes back SENDABLE — the shipped defect, not a `TypeError` from a
new parameter. This is the row the gap closure needed to hold.

## Accomplishments

### Task 1 — Mirror the freemail set into Python

`enrichment.FREEMAIL_DOMAINS` (a `frozenset`) now mirrors
`n8n/code/companyLink.js`'s `FREEMAIL_DOMAINS`, immediately beside
`NOT_A_COMPANY_DOMAIN` and in the same voice. The corrected planning premise
(`company_domain.py` holds no host collection of its own — verified by reading it)
meant there was no existing Python-side list to widen; this is a new, pinned mirror,
the same arrangement `NOT_A_COMPANY_DOMAIN` already established.

The parity test (`test_the_two_engines_agree_on_what_is_freemail`) fixes the parsing
hazard named in the plan: it strips each line's `//` tail **before** joining lines, so
the `// AU consumer ISPs` comment cannot swallow `bigpond.com` onward into a filtered
`//` piece. Asserts `bigpond.com` is present in the JS-parsed set explicitly, so a
future parser regression that silently drops entries shows up as a failed assertion
naming the real cause, not as a Python-side "fix" that deletes real entries from the
mirror.

RED for this task was structural (`AttributeError: module 'enrichment' has no
attribute 'FREEMAIL_DOMAINS'`) — explicitly correct per the plan, since a pure data
mirror has no earlier behaviour to observe; the parse-survives-the-comment property
(`bigpond.com` present) is asserted as an independent check, not treated as the red.

### Task 2 — The relatedness classifier and the changed seam

Added `suggest_contacts.email_domain_relation(email, company_website)`: a pure
classifier, evaluated in order `no_email -> freemail -> company_domain_unknown ->
related/mismatch`, exactly as specified. Freemail is tested before relatedness, so a
Gmail address is never reported as a mismatch.

Rewrote `partition_for_dispatch(rows, company_domains)`:
- `company_domains` is now a **required, positional parameter with no default**.
- Runs `extraction.hold_emailless(rows)` first, unchanged, stamping its held entries
  `reason_code: "no_email"`.
- Classifies every remaining row against its company's domain (name-normalised the
  same way `select_people`'s dedupe already normalises names); `related` stays
  sendable, everything else is held with `{index, row, reason, reason_code}`.
- Held entries are index-sorted so the two passes read as one list.

**The one replaced test**, named per the plan's Decision 6 and verification item 6:

- **Old** (`test_partition_for_dispatch_is_a_thin_call_to_hold_emailless`): asserted
  `partition_for_dispatch(rows) == extraction.hold_emailless(rows)` unconditionally —
  the exact property this plan removes.
- **New** (`test_partition_for_dispatch_agrees_with_hold_emailless_when_every_email_is_on_its_own_company_domain`):
  asserts the two agree only when every row's email is on its own company's domain,
  and a **second, separate test**
  (`test_partition_for_dispatch_holds_the_stranger_hold_emailless_alone_would_send`)
  pins that for the stranger fixture they deliberately diverge — `hold_emailless`
  alone still returns Craig Smith's row as sendable (asserted directly), while
  `partition_for_dispatch` holds it. This is the pinned proof that
  `contact-upload`/`enrich-before-ingest` (which call `hold_emailless` directly) are
  unaffected.

Nine behaviours from the plan's `<behavior>` block, all pinned as named tests in
`test_suggest_contacts.py`: the two measured strangers
(`craig.smith@thehartford.com`, `markoaten@oatens.com`), Decision 3's accepted cost
(`kdaniel@lismoreturfclub.com`), the corresponding sendable own-domain case
(`kdaniel@lismoreturfclub.com.au`), the subdomain-plus-`www` sendable case
(`staff@mail.romaturfclub.com.au` vs `www.romaturfclub.com.au`), the suffix trap
(`romaturfclub.com.au.attacker.tld`), freemail labelled distinctly, company-domain-
unknown, no-email (verbatim `hold_emailless` text), and index discipline across both
passes. Also fixed the two existing `partition_for_dispatch` call sites in
`test_suggest_contacts_composition.py` to pass a `company_domains` map built from the
fixture companies' own `name`/`website`.

### Task 3 — SKILL.md, CHANGELOG, plugin.json

SKILL.md step 8 states the rule in the operator's terms, names the 2026-09-04 ruling
and quotes the measured zero-sendable cost on the sitting that prompted it, and
updates the worked example to build `company_domains` from `eligible_companies` and
pass it. Step 9 now tells the report to group held rows by `reason_code`, naming all
four codes, so "held: 4" never appears without saying which were strangers, which were
personal mailboxes, and which had no email at all.

`test_skill_sequence_coverage.py` needed **no changes** — verified by running it
before and after: the worked example's new `company_domains = {...}` line contains no
`module.function(...)` call against a real scripts module (only dict/`.get()` calls on
a local loop variable), so the registered ordered call-sequence tuple for the
`suggest-contacts` pipeline is byte-identical and the existing `COVERED` entry still
resolves.

Bumped `.claude-plugin/plugin.json` to `0.38.3` and added a dated `## [0.38.3]`
CHANGELOG section in the same commit as the SKILL.md changes, with `## [Unreleased]`
left empty above it. The section names `G-62-7` (this plan) and `G-62-6` — read
`62-11-SUMMARY.md` first, confirmed it shipped `report.all_node_items` and pointed two
readers at it (a code change, not a diagnosis-only stop), so `G-62-6` is claimed per
Decision 7.

## Verification

- `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` — 2362 passed, 5
  skipped (was 2347 passed, 5 skipped before this plan's 15 net new tests).
- `node --test tests/n8n/*.test.mjs` — 867 passed, untouched.
- `git status --porcelain n8n/ scripts/build_cloud_workflows.py` — silent.
- Every file in `files_modified` confirmed `git ls-files`-tracked.
- No arming, no HubSpot write, no provider credit, no live sitting, no triggered
  execution — this plan touched only Python/Markdown/JSON in `operator-claude-plugin/`.

## Deviations from Plan

None — plan executed exactly as written. Decisions 1–7 implemented as specified; the
one intentionally-replaced test is named above with old and new assertions quoted.

## Known Stubs

None.

## Threat Flags

None — see the plan's own threat register (T-62-12-01 through -06, T-62-12-SC); all
dispositions (`mitigate`/`accept`) were implemented exactly as planned, no new network
endpoint, auth path, or schema change introduced.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/enrichment.py` — FOUND, `FREEMAIL_DOMAINS` present.
- `operator-claude-plugin/scripts/suggest_contacts.py` — FOUND, `email_domain_relation` and the rewritten `partition_for_dispatch` present.
- `operator-claude-plugin/tests/test_people_and_url_normalisation.py` — FOUND, freemail parity test present and passing.
- `operator-claude-plugin/tests/test_suggest_contacts.py` — FOUND, nine new fixtures present and passing.
- `operator-claude-plugin/tests/test_suggest_contacts_composition.py` — FOUND, both call sites updated.
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` — FOUND, steps 8 and 9 updated.
- `operator-claude-plugin/CHANGELOG.md` — FOUND, `## [0.38.3]` section present naming G-62-7 and G-62-6.
- `operator-claude-plugin/.claude-plugin/plugin.json` — FOUND, `"version": "0.38.3"`.
- Commit `cf4a28a` (Task 1) — FOUND in `git log --oneline`.
- Commit `fb1043a` (Task 2) — FOUND in `git log --oneline`.
- Commit `7bcf0e3` (Task 3) — FOUND in `git log --oneline`.
