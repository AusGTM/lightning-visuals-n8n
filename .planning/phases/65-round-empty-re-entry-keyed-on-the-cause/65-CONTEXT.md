# Phase 65: Round-empty re-entry, keyed on the cause - Context

**Gathered:** 2026-09-05
**Status:** Ready for planning

<domain>
## Phase Boundary

A round that ends with nothing usable does not stop because an intermediate stage reported
success. The search fallback fires on **ladder**-empty (`eligible_after_ladder`); the
operator's intent is **round**-empty. This phase names the CAUSE of a round-empty in code and
routes on it — including routing to "spend nothing", which is the right answer for two of the
four causes.

**In scope:** a pure cause classifier over what the round already produced, the at-most-one
cause-selected re-entry, and what the report and the decline store record about the cause.

**Out of scope:** `eligible_after_ladder` itself (unchanged), the walk's stop rule (Phase 64),
the role matcher (quick 260905-rf1, landed), the alternate-domain set (quick 260905-ad2,
landed), and the decline store's own shape (Phase 69).

</domain>

<decisions>
## The classifier

- **D-65-01: One pure classifier function.** `round_outcome(...)` in `suggest_contacts.py`
  reads what the round already has — Phase 64's walk `ended` reason, `select_people`'s
  `dropped` reasons, and `partition_for_dispatch`'s holds — and returns one named cause with
  its routing decision. Single testable place. `SKILL.md` consults it; it does not reason
  about cause in prose. Rejected: each stage reporting its own cause and the skill inferring
  — that leaves cause logic in prose, which is exactly what Phase 64 just moved out of prose.
  — **Reversibility:** costly — the report, the re-entry route and Phase 69's stored `cause`
  field all read this one return value.

- **D-65-02: Returns one primary `cause` plus a full `breakdown`.** Real rounds mix causes
  (4 found, 2 dropped by the matcher, 2 held on email, 0 sendable). The primary cause is
  chosen by a fixed precedence a test pins, so routing is unambiguous; the `breakdown` names
  every contributing cause with its count, so the report and the decline entries carry the
  whole truth rather than the headline. Rejected: a bare list with no primary — it pushes the
  routing decision back into skill prose.

- **D-65-03: Unreadable cause fails closed, and does NOT raise.** An absent or malformed stage
  output yields `cause: "unknown"`, `reentry: "none"`, and a plain reason. This copies
  `search_fallback.eligible_after_ladder`'s D-5sd-06 precedent exactly — that function
  deliberately declines rather than raising, because raising surfaces a transcription gap as a
  crash mid-round. The round reports and moves on. No spend on a cause nobody can name.

## The four causes and what each does

- **D-65-04: `no_people_found` → the search fallback.** Today's rule, kept intact. The
  classifier routes to it instead of the skill deciding. `eligible_after_ladder` is unchanged,
  still fail-closed, and a `refused` disposition still closes the path (D-5sd-04).

- **D-65-05: `people_thin` → classify only; Phase 64 already acted.** Phase 64's cumulative
  bar (D-64-05/-06) already continues the walk on exactly this condition. Phase 65 names it in
  the report and re-fetches nothing. Deliberate: two phases must not both spend on the same
  case.

- **D-65-06: `none_classified` → report the matcher cause, spend nothing.** Search re-finds
  the same people with the same titles and the same matcher drops them again — the brief's own
  Brisbane Roar row. Fixed by quick 260905-rf1; named here so a recurrence is visible rather
  than silent.

- **D-65-07: `all_held_on_email` → report, and the held people go to Phase 69's decline
  store.** Search cannot produce a club-domain email; the waterfall supplies emails, not the
  ladder — the brief's Roma Turf Club row. Fixed by quick 260905-ad2. The people survive the
  run because of Phase 69, not because of a retry.

## The shape of a re-entry

- **D-65-08: At most ONE second pass per company, cause-selected.** Bounded by construction —
  no counter to get wrong, trivially non-looping, satisfies the no-`while` rule structurally
  rather than by inspection. Pass 2 always ends in classify-and-report; there is no pass 3.
  Rejected: a fixed-length route list — more flexible, more state, and nothing needs the third
  route today.

- **D-65-09: NOT a blanket retry.** Explicitly refused. Neither live round would have been
  rescued by one, and a `round_empty` boolean would spend fetches and Lusha credits on exactly
  the two cases where spending cannot help.

## Constraints that bind regardless

- **D-65-10: A refusal stays terminal, by every route.** Re-entry re-checks dispositions; a
  ladder containing a `refused` attempt must never reach the search path by a second route.
  Re-entry goes THROUGH `eligible_after_ladder`, never around it — bypassing it would bypass
  the order-free refusal check that test already pins.
- **D-65-11: No cap resets.** `MAX_FOLLOWUP_FETCHES` (5) and `MAX_FALLBACK_SEARCHES` (3) bound
  the WHOLE round for a company, not one pass. A second pass spends from the same remaining
  budget or is refused by the existing guards.
- **D-65-12: `cap_exhausted` stays a terminal, eligible ending — never a retry trigger.**
- **D-65-13: No `while` loop in any plugin script**
  (`tests/test_report_sufficiency.py::_has_while_loop`).

### Claude's Discretion

- The cause vocabulary's exact spellings and the precedence order for D-65-02's primary cause
  (pinned by test either way).
- `round_outcome`'s exact signature and whether it takes the three stage outputs or one
  assembled round record.
- Whether `reentry` is a route name or a callable reference.
- How the breakdown is rendered in the operator's report.

### Folded Todos

- **`2026-09-05-fallback-is-keyed-on-ladder-empty-not-round-empty.md` (first half).** Its
  second half — the ladder stopping at the first page rather than the best — was Phase 64.
  This phase closes the remainder, including the four-cause table, which is the phase brief
  proper. The todo can close when this phase does.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The brief
- `.planning/todos/pending/2026-09-05-fallback-is-keyed-on-ladder-empty-not-round-empty.md` —
  read "So the fix is re-entry keyed on the CAUSE", the "Where a loop-back would NOT have
  helped" table (both live rounds, with the reason each), and the three hard constraints.
- `.planning/ROADMAP.md` § "Phase 65" and § "Binding on all six" (SAFE-01..05).
- `.planning/milestones/v1.2-REQUIREMENTS.md`

### The fence this phase must not weaken
- `operator-claude-plugin/scripts/search_fallback.py` — `eligible_after_ladder` (fail-closed,
  refusal-terminal, `ELIGIBLE_DISPOSITIONS = (empty, cap_exhausted)`), `MAX_FALLBACK_SEARCHES
  = 3`, `rank_results`, `hold_weak_sources`. **Not modified by this phase.**
- `.planning/quick/260904-5sd-sitemap-crawl-fallback-to-client-side-cl/` — D-5sd-04 (a
  refusal is terminal) and D-5sd-06 (fail-closed on an unreadable disposition, without
  raising). D-65-03 copies D-5sd-06 exactly.

### The stages the classifier reads
- `.planning/phases/64-.../64-CONTEXT.md` — D-64-08's `ended` reason
  (`good_enough`/`ladder_exhausted`/`cap_exhausted`/`refused`) is one of the classifier's
  three inputs. **Phase 65 depends on Phase 64 shipping that field.**
- `operator-claude-plugin/scripts/suggest_contacts.py` — `select_people` (its `dropped`
  entries carry `already_associated` / `role_not_selected`), `partition_for_dispatch` (its
  hold codes), `no_candidates`, `round_artifact`.
- `operator-claude-plugin/scripts/confidence.py` — `assess`, the hold-code vocabulary.

### Where the cause lands
- `.planning/phases/69-.../69-CONTEXT.md` — D-69-01/-03: the client-side decline store. The
  classifier's `cause` is a FIELD on a stored entry. 65 names the cause; 69 makes it survive
  the run. **Neither phase owns both halves.**

### The causes already fixed upstream
- `.planning/quick/260905-rf1-role-filter-one-word-titles/` — `none_classified`'s live cause
  (Brisbane Roar). Landed.
- `.planning/quick/260905-ad2-company-alternate-domains/` — `all_held_on_email`'s live cause
  (Roma Turf Club). Landed.

### Test constraint
- `operator-claude-plugin/tests/test_report_sufficiency.py::_has_while_loop`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `search_fallback.eligible_after_ladder(attempts)` — already returns
  `{"eligible", "reason"}` and is already the fail-closed, refusal-terminal gate. D-65-04
  routes INTO it; D-65-10 forbids routing around it.
- `search_fallback.DISPOSITION_EMPTY` / `DISPOSITION_CAP_EXHAUSTED` / `DISPOSITION_REFUSED`
  and `ELIGIBLE_DISPOSITIONS` — the existing disposition vocabulary the classifier should
  read rather than restate.
- `select_people`'s `{"selected", "dropped"}` with per-drop reasons — supplies
  `none_classified` directly, no new instrumentation.
- `partition_for_dispatch`'s hold codes — supply `all_held_on_email` directly.

### Established Patterns
- **Fail closed without raising.** `eligible_after_ladder`'s docstring states the rule and the
  reason; D-65-03 is the same rule in a new function.
- **Refusal text is never re-worded.** `next_candidates` returns `filter_candidates`'s result
  verbatim; `no_candidates` returns `give_up_message`'s text verbatim. A classifier that
  summarises a refusal must quote, not paraphrase.
- **Prose rules get promoted to code.** `agreed_cap` (D-62-11/-12), Phase 64's walk predicate,
  and now the cause routing.
- **Plugin scripts are pure** — no HTTP, no model call, no filesystem write in
  `suggest_contacts.py`. `round_outcome` must stay pure.
- **Bounded iteration only** — no `while`.

### Integration Points
- `SKILL.md`'s post-round step consults `round_outcome` and acts on `reentry`.
- Phase 64 supplies `ended`; Phase 69 stores `cause`. This phase is the join between them.
- The operator-facing report gains the breakdown — Phase 68's rule applies: a report reports,
  it does not halt.

</code_context>

<specifics>
## Specific Ideas

- Why the fallback has never run outside its offline tests: on AU sporting clubs, which
  reliably publish a committee or contact page, ladder-empty is rare and round-empty is
  common. The code path was keyed on the rarer event.
- `260904-QUICK-UAT.md` test 8 is skipped after two live attempts for exactly this reason.
- The operator's own words: "Shouldn't it loop back to the ladder if the ultimate result is
  nothing? Until it exhausts the bottom rung web_search and then it can return nothing."
  Answered by cause-keyed routing rather than by a loop — two of four causes route to
  "spend nothing", and that is the correct answer for both.

</specifics>

<deferred>
## Deferred Ideas

- **A third pass, or a route list that admits new routes** — not needed today (D-65-08).
  Revisit only when a fifth cause appears with a route of its own.
- **Acting on the breakdown's secondary causes** — the classifier records them; nothing routes
  on them. If a mixed round turns out to want two routes, that is its own phase.
- **Cause-driven suppression** (never re-walk a company whose cause recurs) — related to
  D-69-07's rejected tombstone; same answer, same reason.

### Reviewed Todos (not folded)
- `2026-09-04-phone-is-never-chased-only-accepted.md` — Phase 66.
- `2026-09-04-autonomy-flag-with-sensible-defaults.md` — Phase 67.
- `2026-09-04-state-the-price-and-keep-moving.md` — Phase 68.

</deferred>

---

*Phase: 65-round-empty-re-entry-keyed-on-the-cause*
*Context gathered: 2026-09-05*
