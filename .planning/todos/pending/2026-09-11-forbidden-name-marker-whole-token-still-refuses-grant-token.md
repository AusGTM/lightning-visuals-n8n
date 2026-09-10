---
created: 2026-09-11T00:00:00.000Z
updated: 2026-09-11
title: Whole-token forbidden-name matching still refuses a person named Grant or a company named Token
area: operator-plugin
severity: minor
files:
  - operator-claude-plugin/scripts/held_queue.py
  - operator-claude-plugin/scripts/suggestion_declines.py
  - operator-claude-plugin/scripts/run_manifest.py
  - operator-claude-plugin/scripts/run_state.py
  - operator-claude-plugin/scripts/run_report.py
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/scripts/remainder_queue.py
---

## Found during quick 260911-any (2026-09-11), while closing the Secretary/Armidale todo

Whole-token matching (quick 260911-any, all seven `_looks_forbidden` copies) fixed the
substring false positives — `"Secretary"` and `"Armidale Jockey Club"` now save — but a
value that IS one of the ten markers verbatim, as a whole word, still refuses. A person
whose firstname is literally `"Grant"`, or a company named `"Token"`, still trips the
`"grant"` / `"token"` marker and is refused rather than stored.

Not a regression: the old raw-substring matcher refused these too (and far more besides).
Same yield-leak class as the original todo, at a smaller scale — genuinely rare names
rather than a common committee title. Recorded rather than chased in 260911-any per that
plan's decisions ("Known residual, deliberately not fixed... do not widen scope to chase
it").

## Fix

The original todo's candidate (1) — match markers as whole tokens on the FIELD NAME only,
never on values — is the fix, if the tradeoff is ever worth it: a grant or secret smuggled
into a persisted entry arrives under a telling key, not as the word "Grant" in a firstname
cell or "Token" in a company name. 260911-any's own decisions record explicitly rejected
this for now because three shipped tests pin VALUE refusals as load-bearing
(`test_written_records.py` T-59-02, `test_held_queue.py:174`
`"n8n_api_key=super-secret"`, `test_run_manifest.py:112` the verdict `"armed"`) — dropping
value scanning reverses all three. A fix here has to keep those three passing while
exempting a bare marker-shaped VALUE from refusal, which is a different (and more
involved) change than 260911-any's whole-token matching pass.

Test shape: offline; a row with firstname `"Grant"` or company `"Token"` saves in all
seven stores; the three value-refusal regression tests above stay red for their existing
fixtures.
