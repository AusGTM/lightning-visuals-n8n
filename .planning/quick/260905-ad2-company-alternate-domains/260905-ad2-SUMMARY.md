---
quick_id: 260905-ad2
type: execute
mode: quick
status: complete
subsystem: operator-plugin
tags: [suggest-contacts, email-domain-relatedness, send-gate, operator-ruling]
requires: []
provides:
  - "suggest_contacts._company_domain_set — one company's recorded domain(s), cleaned and de-duplicated"
  - "email_domain_relation / partition_for_dispatch accept a domain string OR an iterable of them"
affects:
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md step 8
tech-stack:
  added: []
  patterns:
    - "widen the DATA a rule is applied to, never the rule — `any()` over an unchanged predicate"
key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/tests/test_suggest_contacts.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - operator-claude-plugin/CHANGELOG.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - .planning/todos/completed/2026-09-04-a-company-can-have-more-than-one-domain.md
decisions:
  - "D-ad2-01: company_domains' VALUE widens to str | iterable-of-str; its required-ness does not"
  - "D-ad2-02: the per-domain rule is byte-identical, only the number of domains changes"
  - "D-ad2-03: alternate domains are OPERATOR-SUPPLIED ONLY; mailto: harvest rejected"
  - "D-ad2-04: absent or unusable still means company_domain_unknown, never mismatch"
  - "D-ad2-05: a held reason names every domain that was compared, joined ' or '"
metrics:
  duration: ~25m
  completed: 2026-09-05
actuals:
  tokens: 4371   # chars/4 over the realized diff: 17485 chars across 246 added / 12 removed lines
  tasks: 2
  commits: 3
---

# Quick 260905-ad2: A company can carry more than one domain — Summary

Roma Turf Club's committee address `INFO@romaturfclub.org.au` now sends when the operator
names `romaturfclub.org.au` alongside the correctly-recorded `romaturfclub.com.au`, and is
still held when they do not. The widening comes entirely from what the operator supplied;
the match rule itself is byte-identical.

## What changed

`suggest_contacts._company_domain_set(company_website)` — new, ~12 lines — turns a domain
string *or* an iterable of them into an ordered, de-duplicated list of usable cleaned
domains. `email_domain_relation`'s tail became `cds = _company_domain_set(...)`; empty →
`company_domain_unknown`; then the **unchanged** expression under `any()`:

```python
if any(ed == cd or ed.endswith("." + cd) for cd in cds):
```

`_relation_reason`'s `mismatch` branch joins the same list with `" or "` — which for one
domain reproduces today's string byte for byte, which is why the join only engages at two.
`partition_for_dispatch`'s **body and signature did not change at all**; only its docstring.

The `isinstance(value, str)` branch in the normaliser is load-bearing, not tidiness
(T-ad2-03): `enrichment._clean_domain` does `str(raw)`, so a list reaching it becomes
`"['romaturfclub.com.au']"` — a string with a dot in it, which reads as a *mismatch*
against a real email instead of `company_domain_unknown`.

## RED observation (Task 1), verbatim

Ten new tests appended after
`test_partition_for_dispatch_requires_company_domains_with_no_default`, run before any edit
to `suggest_contacts.py`:

```
FAILED tests/test_suggest_contacts.py::test_email_domain_relation_relates_an_alternate_domain_the_operator_supplied
FAILED tests/test_suggest_contacts.py::test_email_domain_relation_relates_a_subdomain_of_an_alternate
FAILED tests/test_suggest_contacts.py::test_email_domain_relation_normalises_and_dedupes_the_set
FAILED tests/test_suggest_contacts.py::test_partition_for_dispatch_reason_names_every_domain_that_was_compared
FAILED tests/test_suggest_contacts.py::test_partition_for_dispatch_roma_sends_only_with_the_alternate_supplied
5 failed, 7 passed, 83 deselected in 0.13s
```

Sample failure texts:

```
E       AssertionError: assert 'mismatch' == 'related'
E       assert "email domain...club.org.au']" == 'email domain...rfclub.org.au'
E         - not match romaturfclub.com.au or romaturfclub.org.au
E         + not match ['romaturfclub.com.au', 'romaturfclub.org.au']
```

**Seven of the ten passed on RED, and that is expected — not a fail-fast trip.** They pass
*by accident* of `_clean_domain`'s `str(raw)`: `["romaturfclub.com.au", ...]` stringifies to
a dotted pseudo-domain and yields `mismatch`; `["https://www.linkedin.com/company/x", ""]`
becomes `"['https:"` after `.split("/")[0]`, which is dotless and yields
`company_domain_unknown`; `[]` is falsy and yields the same. They are regression fences
against a future loosening, not RED evidence. The five that genuinely failed are the ones
asserting `"related"` or the two-domain reason string — the behaviour this task adds.

Green after the implementation commit, with **zero removed lines** in
`test_suggest_contacts.py` (`git diff -U0 | grep -c '^-[^-]'` → `0`): the four named
regression tests, including the one pinning the single-domain reason string byte for byte,
survive untouched.

## Decisions made

**D-ad2-03 — alternates are operator-supplied only.** The `mailto:`-harvest option the todo
floated was rejected because the crawl ladder is bound to the *recorded* website host, and
whether that host is right is exactly what the companion todo
(`2026-09-04-provenance-aware-manual-protected.md`, Brisbane Lions) says is currently
unreliable and cannot self-correct. Auto-adoption composes the two open bugs: a wrong record
sends the ladder to a stranger's site and silently adopts a `mailto:` found there as this
company's second domain. Secondary, true even with a correct record: a `mailto:` on a page
is not evidence the company controls that domain's mail. A propose-and-confirm surface is
recorded as a deferred path, not built.

Everything else is the plan's D-ad2-01/02/04/05 implemented as written.

## Deviations from Plan

None — plan executed as written. Two notes, neither a deviation:

- The plan named `## [0.40.0]` as the release; the starting version was 0.39.2 (released
  minutes earlier by quick 260905-rf1), so 0.39.2 → 0.40.0 is still the correct next minor.
- The CHANGELOG date is `2026-09-05`, matching the `[0.39.2]` heading directly above it.

## Verification

| Suite | Baseline | Result |
|---|---|---|
| root `.venv/bin/python -m pytest -q` | 4206 passed / 154 skipped | **4216 passed / 154 skipped** (+10 new) |
| node `node --test tests/n8n/*.test.mjs` | 894 / 0 fail | **894 pass / 0 fail** (unchanged) |
| plugin `../.venv/bin/python -m pytest -q` | 2448 passed / 5 skipped | **2458 passed / 5 skipped** (+10 new) |

- `git diff <base> --quiet -- n8n/` → zero backend diff.
- `git diff <base> -U0 -- operator-claude-plugin/tests/test_suggest_contacts.py \| grep -c '^-[^-]'` → `0`.
- Offline throughout: no HubSpot call, no provider credit, no n8n execution, no Anthropic call.

## Commits

- `219cf1e` test(quick-260905-ad2): add failing tests for a company carrying more than one domain
- `1ab95e7` feat(quick-260905-ad2): let a company carry more than one known domain
- `900db57` docs(quick-260905-ad2): document the alternate-domain supply point, close the todo, release 0.40.0

  Amended once, before returning. The first attempt's `git add` listed the *pending* todo
  path, which no longer existed after `git mv`; `git add` is atomic on pathspec failure and
  the `2>/dev/null` on that line swallowed the error, so the commit landed carrying only the
  rename — the CHANGELOG, `plugin.json` bump, SKILL.md prose and the todo's resolution block
  were all left in the working tree. Caught by a `git status --short` check before returning
  and amended in. **Never redirect `git add`'s stderr.**

## Known Stubs

None.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/suggest_contacts.py` — FOUND (`_company_domain_set` present)
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` — FOUND (`alternates` literal present)
- `.planning/todos/completed/2026-09-04-a-company-can-have-more-than-one-domain.md` — FOUND
- commits `219cf1e`, `1ab95e7`, `900db57` — all FOUND in `git log`
- `git status --short` — clean but for the untracked SUMMARY and a pre-existing
  `.review-diagnostics/` directory from an earlier phase
- no `0.39.2` literal survives anywhere in `operator-claude-plugin/` outside the CHANGELOG's
  own history heading
