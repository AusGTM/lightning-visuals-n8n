---
created: 2026-09-04T22:30:00.000Z
updated: 2026-09-04
title: suggest-contacts step 8 routes partition holds into held_queue, which deliberately refuses those codes
area: operator-plugin
severity: major
resolves_phase: 69
files:

  - operator-claude-plugin/skills/suggest-contacts/SKILL.md
  - operator-claude-plugin/scripts/suggest_contacts.py
  - operator-claude-plugin/scripts/confidence.py
  - operator-claude-plugin/scripts/held_queue.py

audit_acknowledged:
  milestone: v1.1
  at: 2026-09-04
---

## The defect, hit live

Roma Turf Club round, 2026-09-04. `partition_for_dispatch` held both rows
(`no_email`, `email_domain_mismatch`). The round then followed step 8's final instruction:

> "The held half is handled exactly as `enrich-before-ingest/SKILL.md`'s own held-row path:
> `confidence.assess()`, then `held_queue.build_entry()`, then `run_manifest.save()`."

`held_queue.save` raised `HeldQueueError`. The held rows could not be persisted; the round
reported them directly to the operator instead.

## The code is RIGHT and the skill is WRONG — do not "fix" this by widening ALL_HOLD_CODES

`partition_for_dispatch`'s own docstring already states the design, in terms:

> "`confidence.ALL_HOLD_CODES` is not widened by these codes: they describe why a SUGGESTION
> round declined to send, not a held-queue class, and the held-row path downstream
> (`confidence.assess()` -> `held_queue.build_entry()`) is unchanged."

`ALL_HOLD_CODES` is the MATCH-gate vocabulary — `HOLD_UNPARSEABLE`,
`HOLD_UNADJUDICATED_CONFLICT`, `HOLD_UNKNOWN_TIER`, `HOLD_NO_MATCH`,
`HOLD_AMBIGUOUS_CANDIDATES`, `HOLD_NO_TABLE_ROW_MATCHED`. Every one answers "we could not
confidently identify this record." `no_email` and `email_domain_mismatch` answer a different
question: "we identified it fine and declined to send it anyway."

Widening the frozenset would let a suggestion-round decline enter the review queue wearing a
match-gate verdict's clothes, and the review lane adjudicates match verdicts. **The refusal is
the guard working.** The skill instruction is what has to change.

## Three candidate fixes

1. **Correct step 8 to say what actually happens** — the partition's held rows are reported to
   the operator in the round report and are not persisted to the held queue. Smallest, honest,
   and matches shipped behaviour. But it leaves the holds with no durable home: close the
   round and the two names are gone.
2. **Give suggestion-round declines their own durable store**, parallel to the held queue and
   with its own vocabulary. Preserves the separation the code is defending while making the
   holds survivable. More work.
3. **Map at the boundary** — translate a partition code into the nearest match-gate code
   before `build_entry`. **Reject this.** It is (1)'s dishonesty with extra steps: the queue
   would then claim a match-confidence verdict the round never made.

Prefer (1) if the holds do not need to survive the round; (2) if they do. The operator's Roma
round shows they may: two real committee members, correctly held, and the only record of them
is a chat message.

## Note the round's own report was complete regardless

The operator-facing output named both people, both reason codes and both reasons in words. The
defect is durability, not disclosure.

## Test shape

Offline. Assert that `partition_for_dispatch`'s reason codes are disjoint from
`confidence.ALL_HOLD_CODES` (pinning the separation as deliberate rather than accidental), and
that whichever path step 8 ends up naming actually accepts them.

## Resolution (Phase 69)

Fix **(2)** was taken — suggestion-round declines get their own durable store,
`operator-claude-plugin/scripts/suggestion_declines.py` (plan 01), keyed by
`company_id` + normalised name and accumulating across runs. `suggest-contacts/SKILL.md`
step 8 now routes every partition-declined row into it (plan 02, Task 1); step 9 reports
this run's declines beside the deferred backlog in one end-of-run batch (plan 02, Task 2).

Fix **(1)** — report-only, no durable home — was rejected: the operator's Roma Turf Club
round showed the holds may need to survive the round (two real committee members,
correctly held, with no record left once the round closed), and (1) would have left that
gap open.

Fix **(3)** — mapping a partition code onto a match-gate code at the boundary before
`held_queue.build_entry` — is implemented nowhere. It was explicitly rejected in the
plan's own prohibitions (69-02-PLAN.md): "No partition reason code is translated,
aliased, or mapped onto a member of `confidence.ALL_HOLD_CODES` at the step-8 boundary."
The two vocabularies stay disjoint by construction, pinned by test
(`test_suggestion_declines.py::test_partition_reason_codes_disjoint_from_all_hold_codes`).
