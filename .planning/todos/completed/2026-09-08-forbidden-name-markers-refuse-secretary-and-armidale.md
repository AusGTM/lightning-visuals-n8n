---
created: 2026-09-08T09:00:00.000Z
updated: 2026-09-11
title: The inherited forbidden-name markers refuse real club data — "Secretary" trips "secret", "Armidale" trips "arm"
area: operator-plugin
severity: major
files:
  - operator-claude-plugin/scripts/suggestion_declines.py
  - operator-claude-plugin/scripts/held_queue.py
  - operator-claude-plugin/scripts/run_manifest.py
---

## Found during Phase 69 execution (2026-09-08)

`_looks_forbidden` / `_FORBIDDEN_NAME_MARKERS` (reimplemented verbatim in `suggestion_declines.py`
per D-69-01 and the held_queue.py:68-70 precedent) matches a marker anywhere inside a value or
field name, not as a whole token. Two hits seen in this phase:

- plan 69-02's fixtures: jobtitle `"Secretary"` refused by the `"secret"` marker — changed to
  `"Treasurer"` to get RED to land. Club **Secretary** is one of the most common committee titles
  in this portal's racing and sports-club population, and a suggestion round that finds one is
  exactly the row the decline store exists to keep.
- plan 69 planning: `"Armidale Jockey Club"` (a real NSW racing body) would be refused by `"arm"`.

Plan 69-02's `unstorable` report path means one odd name costs one decline, never the batch — so
this is a yield leak, not a crash. But every Secretary in every round is lost from the store.

## Not fixed in Phase 69, deliberately

The marker list is shared, by copy, across three durable stores (`held_queue`, `run_manifest`,
`suggestion_declines`). Narrowing it in one store alone would let the three drift, and widening
the exemption is the kind of change the refusal exists to make deliberate. Out of 69's scope.

## Candidate fixes

1. Match markers as whole tokens on the FIELD NAME only (`grant`, `secret`, `token`, `arm`, …),
   never on values — a grant or secret smuggled into a persisted entry arrives under a telling
   key, not as the word "secretary" in a jobtitle cell. Apply to all three copies in one commit
   (Phase 46-style parity), with a parity test that the three tuples stay equal.
2. Keep value scanning but require word boundaries (`\bsecret\b`, `\barm\b`).

Prefer (1). Test shape: offline; a row with jobtitle "Secretary" and company "Armidale Jockey
Club" saves in all three stores; a row carrying a field named `webhook_secret` or a value that
looks like a `pat-na1-` token still refuses.

## Fixed 2026-09-11 (quick 260911-any)

Shipped candidate **(2)**, not this todo's preferred (1). (1) matches markers on the FIELD
NAME only, never on values — but three shipped tests pin VALUE refusals as load-bearing:
`test_written_records.py` T-59-02 (`"bad webhook_secret configured"`), `test_held_queue.py:174`
(`"n8n_api_key=super-secret"`), and `test_run_manifest.py:112` (the bare verdict `"armed"`).
Dropping value scanning would have reversed all three. Whole-token matching (camel-break,
lowercase, split into tokens, pad, match on `" marker "`/`" markers "`/`" markered "`/
`" markering "` runs) fixes both reported false positives while keeping every one of those
refusals — a company literally named `"Armidale Jockey Club"` or a jobtitle of `"Secretary"`
now saves; `"arm"`, `"armed"`, `"arming"`, `"webhook_secret"`, `"N8N_API_KEY"`, `"webhookSecret"`,
`"credentials"`, `"permissions"`, `"api_tokens"`, and every marker verbatim still refuse.

**All SEVEN copies changed**, not the three this todo's frontmatter lists. The literal marker
list also lives in `run_state.py`, `run_report.py`, `written_records.py`, and
`remainder_queue.py` — all seven changed in one commit (Phase 46-style parity), each keeping
its `_FORBIDDEN_NAME_MARKERS` tuple byte-identical and reimplementing its own matcher (no
shared helper — D-69-01's anti-DRY discipline stays; `test_run_report.py:116-118`'s `is not`
distinct-object assertions are untouched).

New `operator-claude-plugin/tests/test_forbidden_marker_parity.py` is the drift guard this
todo's candidate (1) also called for: it drives one corpus (`Secretary`, `Armidale Jockey
Club`, `Armstrong Racing`, `pharmacy supplier`, `farm`, `disarmed`, `The Roma Turf Club` as
must-pass; every marker plus compounds/cases/inflections as must-refuse) through all seven
modules' matchers by name — tuple equality alone cannot catch a copy left on the old
substring rule.

**Known residual, not fixed here:** a person whose firstname is literally `Grant`, or a
company named `Token`, still refuses — same yield-leak class, not a regression (substring
matching refused it too). Recorded as a new pending todo
(`2026-09-11-forbidden-name-marker-whole-token-still-refuses-grant-token.md`); this todo's
own candidate (1) is that follow-up's fix if the value-refusal tradeoff is ever worth
dropping.
