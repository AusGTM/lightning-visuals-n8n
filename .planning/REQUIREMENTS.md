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

- [x] **SAFE-01**: No `min_confidence` is lowered, no `fill_blank_only` is weakened, and none
  of the three enrichment drop paths (`doNotCall`/`dnc_status`, un-normalizable phone,
  unentitled provider field) is softened by any phase in this milestone. Richer means more
  fields ATTEMPTED, never more values FORCED through.
  *Verified 2026-09-11 (resume session, offline): `config/field_policy.yaml` byte-unchanged
  `v1.1..HEAD`, plugin copy byte-identical; `n8n/code/normalizePhone.js` unchanged; the
  `doNotCall` suppress and `normalizePhone` drop in `normalizeProviders.js` untouched — the
  file's only change since `v1.1` is Phase 66's additive `_linkedinHostOnly` producer, which
  refuses rather than admits. `test_preingest_merge.py`'s SAFE-01 pin still green (2903).*
- [x] **SAFE-02**: A refusal stays terminal (D-5sd-04). No re-entry, retry or fallback reaches
  the search path from a ladder containing a `refused` attempt, by any route.
- [x] **SAFE-03**: `MAX_FOLLOWUP_FETCHES` and `MAX_FALLBACK_SEARCHES` bound a company's WHOLE
  round. No phase resets them, and `cap_exhausted` never becomes a retry trigger.
- [x] **SAFE-04**: Ceilings remain refusals in code (`CapRefused`, the per-run ceiling), not
  prose. "Proceed unless interrupted" never becomes "proceed past a refusal". *Holds through
  Phase 67 close: `write_grant.py` is byte-identical to `238d1ab` across all four plans
  (67-01..67-04); `CEILING_OVER` and `CapRefused` remain refusals in code, D-67-09 only reverses
  the treatment of `CEILING_UNKNOWN`/an unread balance/a missing allowance key.*
- [x] **SAFE-05**: D-61-08's unattended gate stays shut unless AUTO-04 is explicitly answered
  by the operator. No phase opens it as a side effect. *Satisfied 2026-09-07: AUTO-04 was ASKED
  (67-01 Task 1, `gate="blocking-human"`) and ANSWERED — the operator reversed the gate open.
  This is a decision recorded, not an execution: no live unattended credit-spending batch has
  run and nothing is armed (see ROADMAP.md § Standing facts).*

## LADDER — the walk finds what the site actually publishes (Phases 64, 65)

- [x] **LADDER-01**: The walk continues past the first page that yields people when a better
  candidate remains, under the SAME fetch budget. *Live: Brisbane Roar stopped at
  `/about/contact-us/`; the general case is a contact page naming a receptionist while
  `/board/` lists the committee.*
- [x] **LADDER-02**: "Better" is a testable predicate, not a prose instruction to the model.
- [x] **LADDER-03**: A round that ends with nothing usable re-enters, and the re-entry names
  the CAUSE of the zero rather than reading a single `round_empty` boolean. *Live: two rounds,
  two different causes, and a blanket retry would have helped neither.*
- [x] **LADDER-04**: Re-entry is expressed without a `while` loop
  (`test_report_sufficiency.py::_has_while_loop` scans every plugin script).
- [ ] **LADDER-05**: The search fallback becomes reachable in a real round — i.e.
  `260904-QUICK-UAT.md` test 8 can finally be exercised rather than skipped a third time.
- [x] **RICH-04**: `merge_enriched`'s keep/replace rule for a CREATE row is audited as its own
  seam. *Live: on an all-blank CREATE row the round discovered `Head of Marketing and Content`
  and `seniority: Director` and kept neither.* **Routed to Phase 65 by operator ruling
  2026-09-04** — `merge_enriched` lives in `preingest.py` (shared, corrected by 65-RESEARCH.md 2026-09-07;
  the ruling said `suggest_contacts.py`), which 66-CONTEXT.md's `<domain>` excludes; 65 was not yet planned.

## RICH — the waterfall fills what it can reach (Phase 66)

*RICH-04 is listed under LADDER above: it was re-routed to Phase 65 on 2026-09-04.*

- [x] **RICH-01**: `phone` is chased, not merely accepted. *Operator target 2026-09-04: phone
  AND email, email-only as fallback.*
- [x] **RICH-02**: A producer/consumer matrix exists for all 12 promotable contact fields —
  which provider responses carry each, and which normalize branch emits it — and the gate's
  `REQUIRED` list is derived from that matrix rather than from intuition.
- [x] **RICH-03**: `lv_linkedin_url` acquires a producer. *It is `fill_blank_only` at 85 with
  NO provider branch emitting it, while Apollo and ZoomInfo both return one — verified by grep
  2026-09-04. It is also one of the three identity groups, so filling it makes those contacts
  matchable on a privileged key.*
- [x] **RICH-05**: The same audit is run for companies; this measurement covered contacts only.
- [x] **RICH-06**: Provider cost is confirmed, not assumed — Lusha's flat-per-contact billing
  is documented, ZoomInfo's fields ride an already-paid request, and Apollo is VERIFIED rather
  than generalised from the other two.

## AUTO — autonomy is a deliberate switch (Phase 67)

- [x] **AUTO-01**: Autonomy is expressed per tier (read-only / spend-no-write / write), not as
  one boolean.
- [x] **AUTO-02**: A plugin update that changes write posture states it plainly (release notes
  and a first-round notice); it never changes it silently. *Rewritten 2026-09-07 (D-67-10):
  the original "every default preserves CURRENT behaviour" text predated D-67-03, which the
  operator chose on 2026-09-05 — new defaults apply on update, an absent autonomy key reads as
  ON.* *Closed 2026-09-07: the round-level first-round notice landed in 67-02 (the off-path
  sentence naming `autonomy.<level>` and `operator.local.json`); the release-notes half landed
  in 67-04's `## [0.41.0]` CHANGELOG section, in the same commit as the `plugin.json` version
  bump.*
- [x] **AUTO-03**: On `CEILING_UNKNOWN`, an unread provider balance, or a missing allowance
  key, an autonomous round DISCLOSES the unknown state in its pre-spend line and proceeds — the
  same disclose-and-proceed as the attended path (D-68-10, D-57-02). The remaining bounds are
  `CEILING_OVER` and `CapRefused`. *Reversed 2026-09-07 by operator ruling D-67-09 from the
  original "fails closed" text; the reversal is recorded, not silent.* *The disclose-and-proceed
  prose lands at all four batch skills: `enrich-before-ingest/SKILL.md`, `enrich-records/SKILL.md`,
  `contact-upload/SKILL.md`, `suggest-contacts/SKILL.md` (67-02).*
- [x] **AUTO-04**: The phase puts the D-61-08 reversal to the operator explicitly, as a
  reversal of the 57-05 Task 4 option-a decision — and records the answer. *Answered 2026-09-07
  (67-01 Task 1, `gate="blocking-human"`); the answer is recorded in
  `operator-claude-plugin/skills/backend-control/SKILL.md`, beside the `ALLOW_N8N_ARM`
  paragraph (67-04 Task 1), pinned by `test_disclosure_audit.py`.*
- [x] **AUTO-05**: It does not replace `ALLOW_N8N_ARM` for the headless/cron path.
- [x] **AUTO-06**: The end-of-run report becomes mandatory when autonomy is on — with nobody
  watching, it is the only account of what happened.

## FLOW — stop halting on statements (Phase 68)

- [x] **FLOW-01**: A disclosure the operator cannot act on differently does not halt the round.
- [x] **FLOW-02**: The no-grant two-phase ask is NOT silently removed. Either it stays, or the
  operator explicitly chooses implicit consent for spend and writes, with that choice recorded.
- [x] **FLOW-03**: Opening a real session/batch grant is easy enough that a round does not fall
  to the per-round ask. *Live: `285507657175 - grant approved for session` yielded no machine
  grant, so the round asked anyway.*
- [x] **FLOW-04**: Every skill is swept for disclosures that halt but should not, with genuine
  decision points (roles, cap, arming, held-row adjudication) left in place.
- [x] **FLOW-05**: If FLOW-02 chooses implicit consent, D-59-06's revoke-refuses-next-send
  semantics are re-stated against it — the gap between the operator reading a line and deciding
  to interrupt is a gap in which spend may already have started.

## HELD — a held person survives the round (Phase 69)

- [x] **HELD-01**: The skill and the code agree on where partition holds go. *Live: step 8
  routes them to `held_queue`, which raises `HeldQueueError` on them.*
- [x] **HELD-02**: `confidence.ALL_HOLD_CODES` is NOT widened by the partition codes, and a
  test pins that disjointness as deliberate. *The two vocabularies answer different questions:
  "could not identify" vs "identified fine, declined to send".*
- [x] **HELD-03**: Either correctly-held people persist somewhere durable, or the skill states
  plainly that they are report-only. *Live: after Roma, the only record of two real committee
  members is a chat message.*
