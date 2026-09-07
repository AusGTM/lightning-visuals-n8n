---
created: 2026-09-08T09:00:00.000Z
updated: 2026-09-08
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
