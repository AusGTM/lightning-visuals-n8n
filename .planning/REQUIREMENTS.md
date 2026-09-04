# Requirements — Milestone v1.2: Yield and Friction

**Defined:** 2026-09-05. **Status:** DEFINED, NOT STARTED (phases 64–69 unplanned).
**Roadmap:** `.planning/milestones/v1.2-ROADMAP.md`
**Prior milestone:** v1.1 Unattended Session Runs — **still IN FLIGHT** (Phases 60, 62, 63
open). This milestone is defined ahead of that close on purpose; the milestone switch has not
been run. Nothing here is tracked in `.planning/milestones/v1.1-REQUIREMENTS.md`.

**Evidence base.** Seven of the eight items come from the first two live `suggest-contacts`
rounds, 2026-09-04: Brisbane Roar FC (2 contacts created and associated) and The Roma Turf Club
(0 sendable, 2 correctly held). Both rounds are recorded in
`.planning/quick/260904-QUICK-UAT.md`. Each requirement below names the live observation it
comes from — none is speculative.

**Scope note.** Items 1–2 of the operator's priority list (the role-filter matcher, the
alternate-domain set) are quick tasks, not phases in this milestone.

---

## Binding constraints — every requirement below inherits these

- [ ] **SAFE-01**: No `min_confidence` is lowered, no `fill_blank_only` is weakened, and none
  of the three enrichment drop paths (`doNotCall`/`dnc_status`, un-normalizable phone,
  unentitled provider field) is softened by any phase in this milestone. Richer means more
  fields ATTEMPTED, never more values FORCED through.
- [ ] **SAFE-02**: A refusal stays terminal (D-5sd-04). No re-entry, retry or fallback reaches
  the search path from a ladder containing a `refused` attempt, by any route.
- [ ] **SAFE-03**: `MAX_FOLLOWUP_FETCHES` and `MAX_FALLBACK_SEARCHES` bound a company's WHOLE
  round. No phase resets them, and `cap_exhausted` never becomes a retry trigger.
- [ ] **SAFE-04**: Ceilings remain refusals in code (`CapRefused`, the per-run ceiling), not
  prose. "Proceed unless interrupted" never becomes "proceed past a refusal".
- [ ] **SAFE-05**: D-61-08's unattended gate stays shut unless AUTO-04 is explicitly answered
  by the operator. No phase opens it as a side effect.

## LADDER — the walk finds what the site actually publishes (Phases 64, 65)

- [ ] **LADDER-01**: The walk continues past the first page that yields people when a better
  candidate remains, under the SAME fetch budget. *Live: Brisbane Roar stopped at
  `/about/contact-us/`; the general case is a contact page naming a receptionist while
  `/board/` lists the committee.*
- [ ] **LADDER-02**: "Better" is a testable predicate, not a prose instruction to the model.
- [ ] **LADDER-03**: A round that ends with nothing usable re-enters, and the re-entry names
  the CAUSE of the zero rather than reading a single `round_empty` boolean. *Live: two rounds,
  two different causes, and a blanket retry would have helped neither.*
- [ ] **LADDER-04**: Re-entry is expressed without a `while` loop
  (`test_report_sufficiency.py::_has_while_loop` scans every plugin script).
- [ ] **LADDER-05**: The search fallback becomes reachable in a real round — i.e.
  `260904-QUICK-UAT.md` test 8 can finally be exercised rather than skipped a third time.

## RICH — the waterfall fills what it can reach (Phase 66)

- [ ] **RICH-01**: `phone` is chased, not merely accepted. *Operator target 2026-09-04: phone
  AND email, email-only as fallback.*
- [ ] **RICH-02**: A producer/consumer matrix exists for all 12 promotable contact fields —
  which provider responses carry each, and which normalize branch emits it — and the gate's
  `REQUIRED` list is derived from that matrix rather than from intuition.
- [ ] **RICH-03**: `lv_linkedin_url` acquires a producer. *It is `fill_blank_only` at 85 with
  NO provider branch emitting it, while Apollo and ZoomInfo both return one — verified by grep
  2026-09-04. It is also one of the three identity groups, so filling it makes those contacts
  matchable on a privileged key.*
- [ ] **RICH-04**: `merge_enriched`'s keep/replace rule for a CREATE row is audited as its own
  seam. *Live: on an all-blank CREATE row the round discovered `Head of Marketing and Content`
  and `seniority: Director` and kept neither.*
- [ ] **RICH-05**: The same audit is run for companies; this measurement covered contacts only.
- [ ] **RICH-06**: Provider cost is confirmed, not assumed — Lusha's flat-per-contact billing
  is documented, ZoomInfo's fields ride an already-paid request, and Apollo is VERIFIED rather
  than generalised from the other two.

## AUTO — autonomy is a deliberate switch (Phase 67)

- [ ] **AUTO-01**: Autonomy is expressed per tier (read-only / spend-no-write / write), not as
  one boolean.
- [ ] **AUTO-02**: Every default preserves CURRENT behaviour, so a plugin update never turns
  autonomy on for an existing install.
- [ ] **AUTO-03**: It fails closed on `CEILING_UNKNOWN`, on an unread provider balance
  (D-57-02: unreadable is `unknown`, never headroom), and on a missing allowance key.
- [ ] **AUTO-04**: The phase puts the D-61-08 reversal to the operator explicitly, as a
  reversal of the 57-05 Task 4 option-a decision — and records the answer.
- [ ] **AUTO-05**: It does not replace `ALLOW_N8N_ARM` for the headless/cron path.
- [ ] **AUTO-06**: The end-of-run report becomes mandatory when autonomy is on — with nobody
  watching, it is the only account of what happened.

## FLOW — stop halting on statements (Phase 68)

- [ ] **FLOW-01**: A disclosure the operator cannot act on differently does not halt the round.
- [ ] **FLOW-02**: The no-grant two-phase ask is NOT silently removed. Either it stays, or the
  operator explicitly chooses implicit consent for spend and writes, with that choice recorded.
- [ ] **FLOW-03**: Opening a real session/batch grant is easy enough that a round does not fall
  to the per-round ask. *Live: `285507657175 - grant approved for session` yielded no machine
  grant, so the round asked anyway.*
- [ ] **FLOW-04**: Every skill is swept for disclosures that halt but should not, with genuine
  decision points (roles, cap, arming, held-row adjudication) left in place.
- [ ] **FLOW-05**: If FLOW-02 chooses implicit consent, D-59-06's revoke-refuses-next-send
  semantics are re-stated against it — the gap between the operator reading a line and deciding
  to interrupt is a gap in which spend may already have started.

## HELD — a held person survives the round (Phase 69)

- [ ] **HELD-01**: The skill and the code agree on where partition holds go. *Live: step 8
  routes them to `held_queue`, which raises `HeldQueueError` on them.*
- [ ] **HELD-02**: `confidence.ALL_HOLD_CODES` is NOT widened by the partition codes, and a
  test pins that disjointness as deliberate. *The two vocabularies answer different questions:
  "could not identify" vs "identified fine, declined to send".*
- [ ] **HELD-03**: Either correctly-held people persist somewhere durable, or the skill states
  plainly that they are report-only. *Live: after Roma, the only record of two real committee
  members is a chat message.*
