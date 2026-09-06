# Phase 65: Round-empty re-entry, keyed on the cause - Research

**Researched:** 2026-09-07
**Domain:** Pure Python classification logic inside `operator-claude-plugin/scripts/suggest_contacts.py` (no HTTP, no n8n, no model call)
**Confidence:** HIGH — every claim below is grounded by `Read` on the cited file/line this session, or by running the cited test command this session. No web research was needed: this phase composes existing, already-read plugin code.

## Summary

Phase 65 has two genuinely separate deliverables that the phase's own CONTEXT.md discusses
asymmetrically. The **classifier** (`round_outcome`, D-65-01 through D-65-13) is fully
decided — CONTEXT.md's `<decisions>` section pins the cause vocabulary, the precedence
rule, the fail-closed behavior, and the three hard constraints. The **RICH-04 requirement**
(`merge_enriched`'s keep/replace rule for a CREATE row) is a "MUST address" phase
requirement per ROADMAP.md/REQUIREMENTS.md, but it was **never discussed** in this phase's
CONTEXT.md or DISCUSSION-LOG.md — grepped, zero hits for `RICH-04`, `merge_enriched`, or
"kept neither" in either file. This research grounds both halves in the actual source so
the planner can proceed on the classifier with confidence and treat RICH-04 as needing its
own design decision inside the plan (no operator ruling exists to plan against yet).

**On the classifier:** every primitive `round_outcome` needs to read already exists and is
already tested: `suggest_contacts.walk_pages`'s `ended`/`WALK_ENDINGS` (Phase 64),
`select_people`'s `dropped` reasons (`already_associated`/`role_not_selected`),
`partition_for_dispatch`'s held `reason_code`s (`no_email`/`email_domain_freemail`/
`email_domain_mismatch`/`company_domain_unknown`), and `search_fallback`'s
`SOURCE_TIER_HOLD_CODE` (`search_source_not_strong`) plus its `ELIGIBLE_DISPOSITIONS`/
`DISPOSITION_REFUSED`. `round_outcome` is a pure fold over these — no new I/O, no new
network call, and (per D-65-08) no loop of any kind: "at most one second pass" is
structurally two straight-line call sites in the SKILL.md pseudocode, not a counter.

**On RICH-04:** the actual live defect is now traced precisely (§ RICH-04 below). It is
NOT that `merge_enriched` lives in `suggest_contacts.py` (it does not — it lives in
`preingest.py` and is shared by `enrich-before-ingest` too). The real defect is a
mismatched allowlist: `merge_enriched`'s `allowed_keys = set(extraction.canonical_props())`
reads 8 CSV-ingestion-header canonical keys from `config/column_mapping.yaml`, while the
waterfall's actual promotable output (`config/field_policy.yaml`'s `contacts:` section) has
12 fields including `seniority` and `lv_linkedin_url` — neither of which is in the
CSV-header alias set, so both are silently dropped as `dropped_property_keys` regardless of
whether the target field was blank. Separately, `jobtitle`'s own field policy says
`protect_if_current_present: false` (it is `stale_refreshable`, not `manual_protected`), but
`merge_enriched`'s blanket fill-not-overwrite rule protects ANY present value regardless of
that field's own policy class — which is why the richer scraped title was logged as a
`conflicts` entry and discarded rather than replacing the stage-1 guess.

**On LADDER-05:** Phase 65's own decisions (D-65-04) keep the `no_people_found` → search
fallback trigger **condition unchanged** — still keyed on the ladder discovering literally
zero raw people, exactly today's `if not people:` check. The classifier does not create any
new occasion for the fallback to fire; it only makes the OTHER three causes (which already,
today, leave `people` non-empty and therefore already skip the fallback) legible and
reported instead of silently falling through as an unlabelled "found nothing usable". See
the dedicated LADDER-05 section below for what this means for the planner's disposition.

**Primary recommendation:** ground `round_outcome` in the three already-tested stage
outputs verbatim (walk `ended`, `select_people`'s `dropped`, `partition_for_dispatch`'s
`held`), call it twice per company (once pre-fallback to decide `reentry`, once post-fallback
for the final report/store `cause`) exactly as `search_fallback.eligible_after_ladder` is
already called today, and treat RICH-04 as a second, independent task inside the same plan
with its own `<decisions>`-style write-up since CONTEXT.md never ruled on it.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Round-empty cause classification (`round_outcome`) | Plugin script (`suggest_contacts.py`, pure Python) | — | Same tier as `walk_pages`/`select_people`/`partition_for_dispatch` — a pure fold over data those functions already produced, no new tier boundary |
| Re-entry routing (search fallback trigger) | Plugin script + SKILL.md orchestration | — | `search_fallback.py` unchanged; only the call-site decision moves from inline SKILL.md prose to a tested function |
| Cause persistence for later drain | Phase 69 (client-side decline store) | Phase 65 (names the `cause` field) | Phase 65 supplies the value; Phase 69 supplies the store. Neither phase owns both halves (CONTEXT.md, explicit) |
| RICH-04 merge/allowlist fix | Plugin script (`preingest.py::merge_enriched`) | `config/column_mapping.yaml` (data, not code) | The defect is a config/allowlist mismatch, not a network- or n8n-tier concern — confirmed no n8n file is implicated |
| n8n / HubSpot backend | Not touched by this phase | — | Confirmed: this phase's scope (`suggest_contacts.py`, `search_fallback.py`, `SKILL.md`, `preingest.py`) contains zero n8n or `scripts/build_cloud_workflows.py` files. CLAUDE.md's Phase 46 parity rule (Python/JS engine parity) and the never-hand-edit-n8n-JSON rule do not apply to this phase. |

## User Constraints (from CONTEXT.md)

<user_constraints>
### Locked Decisions

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

- **D-65-08: At most ONE second pass per company, cause-selected.** Bounded by construction —
  no counter to get wrong, trivially non-looping, satisfies the no-`while` rule structurally
  rather than by inspection. Pass 2 always ends in classify-and-report; there is no pass 3.
  Rejected: a fixed-length route list — more flexible, more state, and nothing needs the third
  route today.

- **D-65-09: NOT a blanket retry.** Explicitly refused. Neither live round would have been
  rescued by one, and a `round_empty` boolean would spend fetches and Lusha credits on exactly
  the two cases where spending cannot help.

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

### Deferred Ideas (OUT OF SCOPE)

- **A third pass, or a route list that admits new routes** — not needed today (D-65-08).
  Revisit only when a fifth cause appears with a route of its own.
- **Acting on the breakdown's secondary causes** — the classifier records them; nothing routes
  on them. If a mixed round turns out to want two routes, that is its own phase.
- **Cause-driven suppression** (never re-walk a company whose cause recurs) — related to
  D-69-07's rejected tombstone; same answer, same reason.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LADDER-03 | A round that ends with nothing usable re-enters, named by cause, not a `round_empty` boolean | § Standard Stack / Code Examples: the exact primitives `round_outcome` folds, with verbatim shapes |
| LADDER-04 | Re-entry expressed without a `while` loop (`test_report_sufficiency.py::_has_while_loop`) | § Common Pitfalls (the AST guard, verbatim) and § Architecture Patterns (two straight-line call sites, not a loop) |
| LADDER-05 | The search fallback becomes reachable in a real round (test 8, previously skipped twice) | § LADDER-05 disposition section — grounded finding that this phase's own decisions keep the trigger condition unchanged; flagged for explicit planner disposition |
| RICH-04 | `merge_enriched`'s keep/replace rule for a CREATE row audited as its own seam | § RICH-04 section — full root-cause trace with exact line numbers and quoted config; flagged as undiscussed in CONTEXT.md, needs its own decision in the plan |
</phase_requirements>

## Standard Stack

No new library, no new dependency. This phase adds one pure function to an existing module
and rewires call sites in an existing skill file. All of Python's stdlib usage stays what it
already is (nothing new needed — no `re`, no `itertools`, no `collections.Counter` even,
though `collections.Counter` is a reasonable one-liner for the `breakdown` counts if the
planner wants it: `Counter(entry["reason"] for entry in dropped)`).

### Core

| Component | Location | Purpose | Why reused, not rebuilt |
|---|---|---|---|
| `walk_pages` | `scripts/suggest_contacts.py:238-385` | Supplies `ended` ∈ `WALK_ENDINGS` and the accumulated `people`/`selected`/`dropped` | Phase 64, already tested, already the single source of ladder-walk state |
| `select_people` | `scripts/suggest_contacts.py:176-205` | Supplies `dropped` entries `{"person", "reason"}`, reason ∈ `{"already_associated", "role_not_selected"}` | Already the source `walk_pages` itself calls per page — no second implementation |
| `partition_for_dispatch` | `scripts/suggest_contacts.py:807-874` | Supplies `held` entries `{"index", "row", "reason", "reason_code"}` | Already the sole source of the four email-hold reason codes |
| `search_fallback.eligible_after_ladder` | `scripts/search_fallback.py:171-236` | Fail-closed, refusal-terminal gate `round_outcome` must route THROUGH, never around | D-65-10 forbids re-implementing this check |
| `search_fallback.hold_weak_sources` | `scripts/search_fallback.py:358-442` | Supplies `SOURCE_TIER_HOLD_CODE = "search_source_not_strong"` as a fifth held reason code the breakdown may see | Already the sole source of that code |

### Supporting

| Component | Location | When to use |
|---|---|---|
| `collections.Counter` (stdlib) | new import if used | Optional, for tallying `breakdown` counts from `dropped`/`held` lists — a one-liner, not a new abstraction |
| `dataclasses.dataclass` (stdlib) | already used in `preingest.py` (`MergeResult`) | If the planner wants `round_outcome`'s return to be a typed object rather than a dict — matches the module's existing convention (`preingest.MergeResult`), though `suggest_contacts.py` itself uses plain dicts everywhere (`walk_pages`, `partition_for_dispatch` both return dicts/tuples) — dict return is the more locally-consistent choice |

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|---|---|---|
| A pure classifier function | Stage-by-stage inference in SKILL.md prose | Explicitly rejected by D-65-01 — leaves cause logic untestable, the exact problem Phase 64 already fixed for the walk |
| Dict return shape | A `RoundOutcome` dataclass | Either works; dataclass buys attribute access and a frozen/immutable guarantee at the cost of one more import and a slight departure from this module's existing all-dict convention (`walk_pages`, `partition_for_dispatch`) |

**Installation:** none — no new package.

**Version verification:** N/A — no new dependency to verify against a registry.

## Package Legitimacy Audit

Not applicable. This phase installs no external package. Skipped per the protocol's own
scope note (only required "whenever this phase installs external packages").

## Architecture Patterns

### System Architecture Diagram

```
                         ┌─────────────────────────────────────────┐
                         │   Per-company pipeline (SKILL.md loop)   │
                         └─────────────────────────────────────────┘
 discovery_plan ──▶ walk_pages (Phase 64) ──▶ walk["ended"] ∈ WALK_ENDINGS
                          │  walk["people"] (raw union, pre-filter)
                          │  walk["selected"] / walk["dropped"]
                          ▼
                 ┌──────────────────────┐
                 │  round_outcome() #1  │   PASS 1 — decide reentry
                 │  (pre-fallback call) │   reads: ended, people, dropped so far
                 └──────────┬───────────┘
                             │ reentry == "search_fallback" only when
                             │ cause == "no_people_found" (walk["people"] empty)
                             ▼
              search_fallback.eligible_after_ladder(attempts)  ── refused? ──▶ terminal (D-65-10)
                             │ eligible
                             ▼
              search_fallback.rank_results(...) ──▶ web_fetch accepted[] ──▶ fold into walk (re-walk)
                             │
                             ▼
        synthesise_rows ──▶ mint_row_ids ──▶ stage-2 enrich (waterfall) ──▶ rejoin_enriched
                             │
                             ▼
              partition_for_dispatch(rows, company_domains) ──▶ sendable, held[{reason_code}]
                             │
              search_fallback.hold_weak_sources(...) ──▶ sendable, held (adds search_source_not_strong)
                             ▼
                 ┌──────────────────────┐
                 │  round_outcome() #2  │   PASS 2 — final cause + breakdown (terminal)
                 │ (post-partition call)│   reads: ended, dropped, held (now complete)
                 └──────────┬───────────┘
                             │
                 ┌───────────┴────────────┐
                 ▼                        ▼
        Step 9 report (per company,   Phase 69's decline store
        cause + breakdown in the      (cause is a FIELD on the
        operator's own words)         stored entry — future phase)
```

There is no loop node in this diagram. `round_outcome` is called at exactly two fixed
call sites in the per-company body of the SKILL.md pseudocode block (§9.5's Python listing) —
never inside a `for`/`while` that iterates until a condition holds. That is what satisfies
D-65-08/D-65-13 structurally: a second call site is not a loop, and there is no third call
site to add.

### Recommended Project Structure

No new files. All work lands in already-open files:

```
operator-claude-plugin/
├── scripts/
│   ├── suggest_contacts.py     # + round_outcome(), + ROUND_CAUSES vocabulary constants
│   └── preingest.py            # RICH-04: merge_enriched's allowed_keys / fill-rule (separate task)
├── config/
│   └── column_mapping.yaml     # RICH-04: candidate site for allowlist widening (needs a decision)
├── skills/suggest-contacts/
│   └── SKILL.md                # step 5/7/8/9 rewired to call round_outcome instead of inline
│                                # `if not people: eligible_after_ladder(...)` prose
└── tests/
    ├── test_suggest_contacts.py            # + round_outcome unit tests (extend existing file)
    └── test_suggest_contacts_composition.py # + composition test driving round_outcome for real
```

### Pattern 1: Fail-closed classification without raising

**What:** An absent/malformed input to a pure classifier yields a safe terminal verdict
(`cause: "unknown"`, `reentry: "none"`) rather than an exception.

**When to use:** Any function reading a stage output that could plausibly be malformed by an
LLM-orchestrated caller (the model transcribing SKILL.md's pseudocode, not a type-checked
caller) — the exact situation `eligible_after_ladder` already solved.

**Example (verbatim precedent, `search_fallback.py:192-228`):**
```python
# Source: operator-claude-plugin/scripts/search_fallback.py:192-209 (read this session)
if not isinstance(attempts, list) or not attempts:
    return {
        "eligible": False,
        "reason": (
            "no ladder attempt was recorded, so nothing establishes that the crawl "
            "completed -- refusing to open the search path on an empty record."
        ),
    }

for attempt in attempts:
    if not isinstance(attempt, dict):
        return {
            "eligible": False,
            "reason": (
                f"a ladder attempt is not an object ({attempt!r}), so its disposition "
                f"cannot be read -- treating the ladder as ineligible."
            ),
        }
```
`round_outcome` should mirror this exact idiom: `isinstance` checks first, a named reason
string on every branch, `return` never `raise`, for every one of its three stage inputs
independently.

### Pattern 2: Closed vocabulary pinned by test, not by cross-module import

**What:** `WALK_ENDINGS` mirrors `search_fallback.DISPOSITION_*` in shape but is a
module-local literal, pinned equal to the sibling module's constants by a test
(`test_walk_ending_vocabulary_pins_to_search_fallbacks_disposition_constants`), never by
importing `search_fallback` into `suggest_contacts.py`.

**When to use:** `round_outcome`'s `ROUND_CAUSES`/cause vocabulary, if it needs to restate
any string already owned by another module (e.g. `"search_source_not_strong"` from
`search_fallback.SOURCE_TIER_HOLD_CODE`) — restate the literal, pin equality by test.

**Example (verbatim, `scripts/suggest_contacts.py:208-218`):**
```python
# Source: operator-claude-plugin/scripts/suggest_contacts.py:208-218 (read this session)
WALK_GOOD_ENOUGH = "good_enough"
WALK_LADDER_EXHAUSTED = "ladder_exhausted"
WALK_CAP_EXHAUSTED = "cap_exhausted"
WALK_REFUSED = "refused"
WALK_ENDINGS = (WALK_GOOD_ENOUGH, WALK_LADDER_EXHAUSTED, WALK_CAP_EXHAUSTED, WALK_REFUSED)
```

### Pattern 3: Re-entry threads the SAME accumulator, never a fresh one

**What:** `attempts`/`company_budget(attempts)` and `search_fallback.rank_results`'s
`already_searched=N` are how the two caps (`MAX_FOLLOWUP_FETCHES=5`,
`MAX_FALLBACK_SEARCHES=3`) stay non-resettable (D-65-11/SAFE-03) — verified live:
`cost_guard.suggestion_line`'s own priced ceiling is `companies * MAX_FOLLOWUP_FETCHES`
total, not per-pass (`tests/test_cost_guard_suggestion.py:41-44`, run this session, passing).

**When to use:** Any re-entry code must pass the company's ALREADY-ACCUMULATED `attempts`
list into `eligible_after_ladder`/`next_candidates`/`company_budget` again — never
`attempts = []` for "pass 2". There is no separate accumulator to reset in the first place;
the existing functions already take the accumulator as an argument, so "not resetting" is
achieved by simply not passing a new empty list, not by any new guard code.

### Anti-Patterns to Avoid

- **A `round_empty` boolean.** Explicitly rejected (D-65-02, D-65-09) — collapses 4 distinct
  causes, 2 of which must spend nothing, into one signal that cannot express "don't spend."
- **A blanket retry / loop-back on any "nothing usable" signal.** Explicitly rejected
  (D-65-09) and would trip `test_report_sufficiency.py::_has_while_loop` the moment it is
  expressed as a `while`. Neither live round (Brisbane, Roma) would have been rescued by one
  — see § Common Pitfalls.
- **Widening `confidence.ALL_HOLD_CODES` to include `partition_for_dispatch`'s reason
  codes.** Out of scope for this phase (Phase 69's D-69-02 explicitly forbids it) — the two
  vocabularies answer different questions ("could not identify" vs "identified fine, declined
  to send") and `round_outcome` must read `partition_for_dispatch`'s codes directly, never
  through `confidence.py`.
- **Routing around `eligible_after_ladder`.** D-65-10 is explicit: re-entry goes THROUGH it.
  A `round_outcome` that computes its own refusal check duplicates a fail-closed gate that
  already exists and risks getting the refusal-is-terminal rule wrong a second time.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Deciding whether the ladder is eligible for search | A second refusal/eligibility check inside `round_outcome` | `search_fallback.eligible_after_ladder(attempts)`, called through, verbatim | D-65-10; the fail-closed refusal logic already exists and is already tested |
| Counting "found vs selected vs held" | A new tally structure | `len(walk["people"])`, `len(walk["selected"])`, `len(walk["dropped"])`, `len(held)` — all already-returned lists | Every number `round_outcome` needs is already sitting in a list it is handed; no new counter to keep in sync |
| A vocabulary for "why held" | A new enum | `partition_for_dispatch`'s `reason_code` (4 values) + `search_fallback.SOURCE_TIER_HOLD_CODE` (1 value) = the existing 5-code held vocabulary already rendered at SKILL.md step 9 | Restating this is what step 9 already does in prose; `round_outcome` should read the same 5 codes, not invent new names for them |

**Key insight:** every input `round_outcome` needs is a return value of a function that
already exists, is already tested, and is already called somewhere in the current
SKILL.md pseudocode. There is no discovery work left for this classifier — it is entirely a
composition/plumbing task, which is exactly what D-65-01's "prose rules get promoted to
code" pattern predicts.

## LADDER-05 disposition (search fallback reachability)

**Finding, tool-verified this session:** D-65-04 states the `no_people_found` → search
fallback routing rule is kept "intact" — i.e., the trigger condition stays `walk["people"]`
being empty after the whole ladder walk, byte-identical to today's SKILL.md step 7 pseudocode
(`if not people: verdict = search_fallback.eligible_after_ladder(attempts)`,
`skills/suggest-contacts/SKILL.md:415-417`, read this session). Phase 65 does not widen,
loosen, or add a second occasion for this condition to become true.

The brief itself states plainly (ROADMAP.md §Phase 65, read this session) that on AU sporting
clubs "ladder-empty is rare and round-empty is common — which is why the fallback has never
run outside its offline tests across two live attempts." Both live rounds to date
(Brisbane Roar, The Roma Turf Club) found SOME people on the ladder (`walk["people"]`
non-empty) — Brisbane's zero-sendable outcome was a matcher failure (`none_classified`), and
Roma's was an email-relatedness failure (`all_held_on_email`). Neither is `no_people_found`,
and Phase 65's own design explicitly refuses to route either of them into the search fallback
(D-65-06, D-65-07 both say "spend nothing").

**What this means for the planner:** LADDER-05 ("the search fallback becomes reachable in a
real round — test 8 can finally be exercised") is **not satisfied by anything Phase 65's
locked decisions build**. The classifier makes the OTHER three causes legible and reported —
which is real, valuable work — but it does not change when the fallback itself fires. Test 8
remains dependent on a live company whose ladder discovers **zero raw people at all** (a
club with no committee/contact page reachable through the sitemap ladder, or one that refuses
every candidate for a non-`refused`-disposition reason). Recommend the planner explicitly
disposition this in the plan rather than silently marking LADDER-05 complete:

- **Option A (recommended, cheapest):** mark LADDER-05 as "correctly wired and unit-tested,
  live-reachability remains opportunistic" — i.e., the code path is proven correct offline
  (a `round_outcome`/`eligible_after_ladder` unit test can force `walk["people"] == []` and
  assert `reentry == "search_fallback"`), and the live UAT re-run captures the outcome
  whenever it next occurs, rather than blocking phase completion on manufacturing a
  zero-people company.
- **Option B:** stage a deliberately empty-ladder company (e.g. a shell/holding-company
  HubSpot record with a domain that 404s past its homepage) into a future live UAT sitting to
  force the condition. This is a live-sitting design decision, not a code decision, and is
  out of scope for what this research can settle.

Either way, this is a call for the plan/discuss step, not something this research should
silently resolve by asserting satisfaction.

## RICH-04 (`merge_enriched`'s keep/replace rule) — full trace

**Status: undiscussed in CONTEXT.md/DISCUSSION-LOG.md.** Grepped both files this session for
`RICH-04`, `merge_enriched`, `CREATE row`, `keep neither`, `kept neither` — zero matches. This
requirement rode into Phase 65 by an operator ruling recorded only in
`.planning/REQUIREMENTS.md` (2026-09-04) and the completed todo
`.planning/todos/completed/2026-09-04-phone-is-never-chased-only-accepted.md`, not through the
phase's own discuss-phase session. The planner has no locked decision to build against here
and should treat this as needing its own mini-decision inside the plan (or a
`checkpoint:human-verify`/discretion call, per the operator's ruling style elsewhere in this
milestone).

### The routing rationale is imprecise — corrected

REQUIREMENTS.md states RICH-04 was "re-routed to Phase 65... because `merge_enriched` lives
in `suggest_contacts.py`, which 66-CONTEXT.md's `<domain>` explicitly excludes." **This is
not accurate** — `merge_enriched` is defined in `preingest.py:565` (verified this session,
`grep -n "def merge_enriched" scripts/preingest.py` → line 565), and is called from THREE
places: `preingest.py:752` (`rerequest_unanswered`'s own retry), and from BOTH
`enrich-before-ingest` (`tests/test_chunking.py:1314,1424`) and `suggest-contacts`
(`suggest_contacts.py:585` via `rejoin_enriched`, which calls
`preingest.merge_enriched(rows, merged_rows)`, and `SKILL.md` step 7's documented block).
It is a **shared** function, not a suggest-contacts-private one. The operator ruling's stated
reason for the reroute does not hold up against the source, but the underlying defect is
real and IS live-observed inside a suggest-contacts round, so keeping it in Phase 65 (rather
than reopening Phase 66, which is sealed) is still the pragmatic outcome — the planner should
just not repeat the "lives in suggest_contacts.py" claim as a design premise, since a fix here
may also change behavior for `enrich-before-ingest`.

### The actual live defect, traced to two distinct root causes

Live evidence (`.planning/todos/completed/2026-09-04-phone-is-never-chased-only-accepted.md`,
lines 143-166, read this session): on a CREATE row with every field blank, the waterfall
returned `jobtitle: "Head of Marketing and Content"` and `seniority: "Director"`; the merge
"filled the blank `email` and kept the stage-1 `jobtitle`; the richer title and the seniority
were dropped."

**Root cause 1 — `seniority` is dropped outright, unconditionally, regardless of whether the
target field was blank.** `merge_enriched`'s `allowed_keys = set(extraction.canonical_props())`
(`preingest.py:634`, read this session). `extraction.canonical_props()`
(`extraction.py:162-167`, read this session) returns "the deduplicated VALUES of
`column_mapping.yaml`'s `aliases` map." Reading `config/column_mapping.yaml`'s `aliases:`
block verbatim this session:

```yaml
# Source: operator-claude-plugin/config/column_mapping.yaml (read this session, full aliases block)
aliases:
  email: email
  "email address": email
  "e-mail": email
  "e-mail address": email
  firstname: firstname
  "first name": firstname
  fname: firstname
  "given name": firstname
  lastname: lastname
  "last name": lastname
  surname: lastname
  jobtitle: jobtitle
  "job title": jobtitle
  title: jobtitle
  position: jobtitle
  linkedin_url: linkedin_url
  linkedin: linkedin_url
  "linkedin url": linkedin_url
  li: linkedin_url
  "linkedin profile": linkedin_url
  phone: phone
  mobile: phone
  tel: phone
  company: company
  organization: company
  organisation: company
  account: company
  "org.": company
  company_id: company_id
  "company id": company_id
  "hubspot company id": company_id
  "associated company id": company_id
  "associatedcompanyid": company_id
```

The deduplicated VALUES are exactly: `{email, firstname, lastname, jobtitle, linkedin_url,
phone, company, company_id}` — **8 keys**. `seniority` is not among them. `mobilephone`,
`city`, `state`, `country`, `hs_state_code`, `hs_country_region_code`, and
`lv_persona_group` are also absent. So when the waterfall's response `properties` map
carries `seniority`, `merge_enriched`'s loop hits `if key not in allowed_keys:` and appends
it to `dropped_property_keys`, **never checking whether the row's `seniority` was blank** —
this is a total drop, not a fill-vs-conflict decision.

Compare against `config/field_policy.yaml`'s `contacts:` section — the actual promotable
enrichment-output vocabulary — read verbatim this session (`field_policy.yaml:144-227`):

```yaml
# Source: operator-claude-plugin/config/field_policy.yaml:154-227 (read this session)
contacts:
  email: {class: fill_blank_only, promote_to_canonical: true, min_confidence: 80, protect_if_current_present: true}
  city: {class: fill_blank_only, promote_to_canonical: true, min_confidence: 80, protect_if_current_present: true}
  state: {class: fill_blank_only, promote_to_canonical: true, min_confidence: 80, protect_if_current_present: true}
  country: {class: fill_blank_only, promote_to_canonical: true, min_confidence: 80, protect_if_current_present: true}
  hs_state_code: {class: fill_blank_only, promote_to_canonical: true, min_confidence: 80, protect_if_current_present: true}
  hs_country_region_code: {class: fill_blank_only, promote_to_canonical: true, min_confidence: 80, protect_if_current_present: true}
  phone: {class: fill_blank_only, promote_to_canonical: true, min_confidence: 80, protect_if_current_present: true}
  mobilephone: {class: fill_blank_only, promote_to_canonical: true, min_confidence: 85, protect_if_current_present: true}
  jobtitle: {class: stale_refreshable, promote_to_canonical: true, min_confidence: 75, stale_after_days: 180, protect_if_current_present: false, allow_sonnet_escalation: true}
  lv_linkedin_url: {class: fill_blank_only, promote_to_canonical: true, min_confidence: 85, protect_if_current_present: true}
  seniority: {class: system_owned, promote_to_canonical: true, min_confidence: 75}
  lv_persona_group: {class: system_owned, promote_to_canonical: true, min_confidence: 75}
```

This is **12 keys**, only 3 of which (`email`, `phone`, `jobtitle`) overlap with
`extraction.canonical_props()`'s 8. Note the key-naming mismatch too: the policy's
`lv_linkedin_url` (PN-1 rename, per CLAUDE.md §66) is a different literal string from
`extraction.canonical_props()`'s `linkedin_url` — even a producer emitting the field under
its correct, current property name would still be dropped by the stale alias.

**Root cause 2 — `jobtitle`'s own policy explicitly says "not protected", but
`merge_enriched` protects it anyway.** `field_policy.yaml`'s `jobtitle` entry (quoted above)
carries `protect_if_current_present: false` — the field's OWN policy says a present value
should NOT block a better one. But `merge_enriched`'s fill-not-overwrite rule
(`preingest.py:655-662`, read this session) is a single blanket rule applied to every key
uniformly, with no per-field policy read at all:

```python
# Source: operator-claude-plugin/scripts/preingest.py:655-662 (read this session)
current = merged.get(key)
if _present(current):
    if str(value).strip() != str(current).strip():
        conflicts.append({
            "row_id": row_id, "field": key,
            "kept": current, "provider_value": value,
        })
    continue
merged[key] = value
```

`_present(current)` (`preingest.py:558-560`) is true for the stage-1 scraped `jobtitle`
("Marketing" or similar), so the richer waterfall value is logged into `conflicts` and
discarded — even though `jobtitle`'s own `field_policy.yaml` entry says exactly the
opposite of what this blanket rule assumes.

### Two candidate fix shapes (planner decision needed — no operator ruling exists)

1. **Widen `allowed_keys` only.** Add the 4 missing canonical aliases
   (`seniority: seniority`, a corrected `lv_linkedin_url` alias, `mobilephone`, `city`,
   `state`, `country`, `hs_state_code`, `hs_country_region_code`, `lv_persona_group`) to
   `config/column_mapping.yaml`'s `aliases:` block, so `canonical_props()` naturally grows to
   match `field_policy.yaml`'s 12. This is the smaller, more mechanical fix — it does NOT
   touch root cause 2 (the blanket fill-not-overwrite would still wrongly protect a present
   `jobtitle`). Cheapest change; leaves the `jobtitle`-specific richness gap open.
2. **Make `merge_enriched` field-policy-aware.** Pass (or read) each field's
   `protect_if_current_present` from `field_policy.yaml` and branch on it instead of the
   blanket `_present(current)` check. This closes root cause 2 too, but widens
   `merge_enriched`'s contract for BOTH callers (`enrich-before-ingest` too), which is a
   bigger, more consequential change that the ladder (rung 1: "does this need to exist at
   all?") suggests should be scoped down first — does `enrich-before-ingest` actually want
   this too, or does it have its own reasons the blanket rule is currently safe there?

Given SAFE-01 ("richer means more fields ATTEMPTED, never more values FORCED through"), (1)
is unambiguously safe — it only widens what CAN be written, and the existing fill-vs-conflict
logic still applies per-key. (2) is a policy-semantics change that touches a second caller
and deserves its own explicit checkpoint rather than being decided by this research. Ponytail
reading: ship (1) as the phase's RICH-04 close (cheapest fix that resolves the `seniority`
half of the live defect, which is the more clear-cut and confidence-backed of the two root
causes — `seniority` is `min_confidence: 75`, `system_owned`, no ambiguity about whether it
should have been written), and record root cause 2 (`jobtitle`'s ignored
`protect_if_current_present: false`) as a named, deliberately deferred follow-up rather than
silently building (2) into the same change.

## Common Pitfalls

### Pitfall 1: Reading `people` as "selected" instead of "raw discovered"

**What goes wrong:** `no_people_found`'s trigger condition is `walk["people"]` (the raw,
pre-role-filter union) being empty — NOT `walk["selected"]` being empty. Conflating the two
would make `none_classified` (people found, all dropped by the role filter) misroute into the
search fallback, which is exactly the retry-that-cannot-help case D-65-06/D-65-09 forbid.

**Why it happens:** both are plausible names for "did the round find anyone", and the
existing SKILL.md pseudocode's `if not people:` is easy to misread if you don't trace which
variable it binds (`people = walk["people"]`, `skills/suggest-contacts/SKILL.md:413`, read
this session — NOT `walk["selected"]`).

**How to avoid:** `round_outcome` must read `walk["people"]` for the `no_people_found` check
specifically, and `walk["selected"]`/`walk["dropped"]` separately for `none_classified`.

**Warning signs:** a test where a company's role filter drops everyone (`none_classified`)
asserts `reentry == "search_fallback"` — that assertion failing is the signal this pitfall
was avoided; asserting it PASSES is the bug.

### Pitfall 2: A "second pass" that resets `attempts` to `[]`

**What goes wrong:** silently doubles the effective per-company fetch/search budget, directly
violating SAFE-03/D-65-11, and defeats the entire "no cap resets" hard constraint the phase
brief calls out by name.

**Why it happens:** the natural instinct writing a "pass 2" function is to give it a fresh
local list to accumulate into, especially if the re-entry is refactored into its own
function taking `company_row` as its only per-company argument.

**How to avoid:** thread the SAME `attempts` list (and the same running `already_searched`
count for `search_fallback.rank_results`) from pass 1 into pass 2. There is no new counter to
add — `company_budget(attempts)` already derives the spent-fetch count from `len(attempts)`,
so simply not creating a second list is sufficient.

**Warning signs:** a test asserting that a company already at `MAX_FOLLOWUP_FETCHES` before
re-entry still shows `budget_remaining == 0` after the "second pass" — if that test doesn't
exist, this pitfall may be un-caught.

### Pitfall 3: `cap_exhausted` treated as a signal to try again

**What goes wrong:** violates D-65-12 directly. `WALK_CAP_EXHAUSTED` and
`search_fallback.DISPOSITION_CAP_EXHAUSTED` are both **eligible, terminal** endings — the
existing code already treats `cap_exhausted` as "safe to hand to the search fallback because
it's absence-of-information, not a fence" (`eligible_after_ladder`'s own docstring,
`search_fallback.py:185-187`, read this session: "Nobody refused us; we stopped looking.").
That "eligible for search" status must not be confused with "eligible for a THIRD look" —
once search itself also ends in `cap_exhausted` (its own `MAX_FALLBACK_SEARCHES` budget), that
is final.

**Why it happens:** `cap_exhausted` reads like a mid-state ("didn't finish") rather than a
terminal one, inviting a "give it one more try" instinct — exactly the operator's own
question this phase exists to answer no to ("Shouldn't it loop back to the ladder... until it
exhausts the bottom rung web_search").

**How to avoid:** `round_outcome`'s `reentry` field must be `"none"` on any call made AFTER
the search fallback has already run once for that company, regardless of how the fallback
itself ended.

**Warning signs:** any code path where `round_outcome` could return
`reentry: "search_fallback"` on its SECOND call for the same company (pass 2). This is the
concrete assertion `test_report_sufficiency.py::_has_while_loop`-style structural test should
pin: grep the SKILL.md pseudocode / any refactored orchestration function's AST for a call to
whatever expresses "search fallback" appearing more than once per company body.

### Pitfall 4: Widening `confidence.ALL_HOLD_CODES`

**What goes wrong:** `held_queue.py` classifies a hold as ENRICHMENT-STAGE vs MATCH-STAGE by
checking `ALL_HOLD_CODES` membership (`confidence.py:42-46`, read this session). Adding
`partition_for_dispatch`'s reason codes (`no_email`, `email_domain_mismatch`, etc.) to that
frozenset would make a "identified fine, declined to send" hold read as a "could not
identify" hold to every downstream consumer of `held_queue.py` — this is explicitly the
mistake `.planning/todos/pending/2026-09-04-skill-step8-routes-holds-into-a-queue-that-refuses-them.md`
diagnosed and explicitly said NOT to fix this way, and Phase 69's own D-69-02 restates the
same refusal.

**Why it happens:** `round_outcome` needs to read `held`'s reason codes, and a "just add it
to the existing vocabulary" instinct is the path of least resistance if the reader doesn't
already know the two vocabularies answer different questions.

**How to avoid:** `round_outcome` reads `partition_for_dispatch`'s `reason_code` values
directly from the `held` list it is handed — it never imports or extends
`confidence.ALL_HOLD_CODES`.

**Warning signs:** a diff touching `scripts/confidence.py` at all. This phase's diff should
have zero reason to touch that file.

## Code Examples

### Exact shapes `round_outcome` must fold (all verified by `Read` this session)

```python
# walk_pages's return, scripts/suggest_contacts.py:378-385
{
    "people": [...],      # raw deduped union across every fetched page, pre-role-filter
    "selected": [...],    # accumulated select_people() selections across pages
    "dropped": [           # accumulated select_people() drops across pages
        {"person": {...}, "reason": "already_associated"},  # or "role_not_selected"
    ],
    "scores": [...],       # per-page marginal/cumulative hit counts -- internal, not for round_outcome
    "ended": None,         # one of WALK_ENDINGS, or None if the walk is not yet terminal
    "bar": int,
}
# WALK_ENDINGS = ("good_enough", "ladder_exhausted", "cap_exhausted", "refused")
```

```python
# search_fallback.eligible_after_ladder's return, scripts/search_fallback.py:171 signature,
# 192-236 body
{"eligible": bool, "reason": str}
# DISPOSITION_EMPTY = "empty"; DISPOSITION_CAP_EXHAUSTED = "cap_exhausted";
# DISPOSITION_REFUSED = "refused"; ELIGIBLE_DISPOSITIONS = (DISPOSITION_EMPTY, DISPOSITION_CAP_EXHAUSTED)
```

```python
# partition_for_dispatch's held-entry shape, scripts/suggest_contacts.py:807-874
{"index": int, "row": {...}, "reason": "<prose>", "reason_code": "no_email"}
# reason_code in {"no_email", "email_domain_freemail", "email_domain_mismatch",
#                 "company_domain_unknown"} -- from _RELATION_REASON_CODES (line 656-660)
#                 plus extraction.hold_emailless's own "no_email" stamp (line 848)
```

```python
# search_fallback.hold_weak_sources adds a fifth code onto the SAME held list,
# scripts/search_fallback.py:358-442
{"index": int, "row": {...}, "reason": "<prose>", "reason_code": "search_source_not_strong"}
# SOURCE_TIER_HOLD_CODE = "search_source_not_strong" (line 64)
```

### Sketch: `round_outcome`'s likely composition (illustrative, not prescriptive — signature is Claude's Discretion)

```python
# Illustrative only -- not verbatim from any file. Every value referenced IS verbatim
# (WALK_REFUSED, WALK_ENDINGS, reason_code strings) per the quoted shapes above.
CAUSE_NO_PEOPLE_FOUND = "no_people_found"
CAUSE_PEOPLE_THIN = "people_thin"
CAUSE_NONE_CLASSIFIED = "none_classified"
CAUSE_ALL_HELD_ON_EMAIL = "all_held_on_email"
CAUSE_UNKNOWN = "unknown"

REENTRY_SEARCH_FALLBACK = "search_fallback"
REENTRY_NONE = "none"

def round_outcome(walk, held=None, bar=None):
    """Pure. `walk` is walk_pages()'s own return dict, verbatim. `held` is
    partition_for_dispatch's (post hold_weak_sources) `held` list, or None before
    stage 2 has run at all -- the pre-fallback call. Fails closed (D-65-03): a
    malformed `walk` yields cause=unknown, reentry=none, never a raise."""
    if not isinstance(walk, dict) or "people" not in walk or "ended" not in walk:
        return {"cause": CAUSE_UNKNOWN, "reentry": REENTRY_NONE,
                "reason": f"walk output is not readable ({walk!r})", "breakdown": {}}

    if not walk["people"]:
        return {"cause": CAUSE_NO_PEOPLE_FOUND, "reentry": REENTRY_SEARCH_FALLBACK,
                "reason": "the ladder walk discovered nobody at all", "breakdown": {}}

    if held is None:
        # Pre-fallback call, people were found -- no reentry question left to ask.
        return {"cause": None, "reentry": REENTRY_NONE, "reason": None, "breakdown": {}}

    # Post-partition call: fold dropped + held into a breakdown, pick the primary
    # cause by the precedence order D-65-02 asks a test to pin.
    ...
```

## State of the Art

Not applicable — this phase is internal composition of already-current, already-tested
plugin primitives from the same repo, all landed within the last 3 days (2026-09-04 through
2026-09-05) of this session's `git log`. There is no external "old approach / new approach"
axis; the whole "state of the art" for this phase IS Phase 64's walk vocabulary plus the two
just-landed quick tasks.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `round_outcome` should be called exactly twice per company (pre-fallback to decide reentry, post-partition for the final report/store cause) rather than once at the very end | Architecture Patterns, Code Examples | If wrong, the planner may design a single-call shape that cannot decide `reentry` before stage 2 has even run — but CONTEXT.md's own "Claude's Discretion" note explicitly leaves the exact signature/call-count open, so this is offered as the most-consistent-with-existing-code reading, not asserted as decided |
| A2 | RICH-04's fix should be the allowlist-widening-only option (candidate 1), deferring the `jobtitle`-policy-awareness option (candidate 2) | RICH-04 section | If the operator actually wants candidate 2 addressed in this phase, the plan would need a second task touching `enrich-before-ingest`'s behavior too — this is a judgment call under SAFE-01's "richer, never forced" framing, not a verified fact |
| A3 | LADDER-05 cannot be satisfied by code changes alone within Phase 65's locked decisions | LADDER-05 disposition | This is a logical inference from D-65-04's "kept intact" wording plus the observed live rounds, not an operator statement — if the operator's actual intent for LADDER-05 differs (e.g., they consider "correctly wired and testable" sufficient), no plan change is needed, only a documentation framing change |

**If this table is empty:** N/A — see above.

## Open Questions

1. **Does `round_outcome` need a THIRD input parameter for `dropped` explicitly, or is
   `dropped` always read off `walk["dropped"]`?**
   - What we know: `walk_pages`'s own `dropped` list already accumulates every
     `select_people` drop across every folded page (verified: `walk_pages` calls
     `select_people` per page and does `dropped.extend(page_selection["dropped"])`,
     `suggest_contacts.py:355`).
   - What's unclear: whether a post-search-fallback re-walk's `dropped` list also needs to be
     merged in for the FINAL `round_outcome` call (since the fallback's `select_people` call
     in the SKILL.md pseudocode, line ~424-425, is a SEPARATE call outside `walk_pages`, so
     its `dropped` entries are NOT automatically folded into `walk["dropped"]`).
   - Recommendation: the planner should trace the fallback branch's `select_people` call
     (`skills/suggest-contacts/SKILL.md:428-429`) and decide whether `round_outcome`'s final
     call needs an explicit `dropped` override/merge parameter for the case where the
     fallback ran. This is a real gap in the current pseudocode's own bookkeeping, independent
     of Phase 65.

2. **Where does the `cause` value actually get attached to a record before Phase 69 exists?**
   - What we know: Phase 69 (not yet planned/built) will read `cause` as a field on a stored
     decline entry (CONTEXT.md's canonical_refs section, "the classifier's `cause` is a FIELD
     on a stored entry").
   - What's unclear: since Phase 69 doesn't exist yet, Phase 65 has nothing to write `cause`
     INTO except the round's own report (step 9's prose). Should Phase 65 stub a `cause` key
     onto each held/dropped record's dict now (so Phase 69 only has to read it, not derive
     it), or should Phase 65 confine itself to reporting and leave the data-shape work to
     Phase 69?
   - Recommendation: given D-65-01's "Reversibility: costly — ...Phase 69's stored `cause`
     field all read this one return value," the safer choice is for Phase 65 to at minimum
     attach `cause`/`breakdown` to the round's own OUTPUT structure (whatever step 9's report
     consumes) even before Phase 69 exists, so Phase 69 has a stable field to depend on rather
     than needing to re-derive it from raw stage outputs a second time.

## Environment Availability

Skipped — this phase has no external dependency (no new tool, no new service, no new
provider). Everything it touches is already-installed Python stdlib plus already-present
plugin modules, confirmed runnable this session (`.venv/bin/python -m pytest` succeeded).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (already configured; `.venv/bin/python -m pytest` confirmed working this session, no `pytest.ini` needed beyond what's already there) |
| Config file | none dedicated — plugin tests run from `operator-claude-plugin/` via the repo-root `.venv` |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py -q` (0.63s, 115 passed, confirmed this session) |
| Full suite command | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (13.03s, 2492 passed / 5 skipped, confirmed this session — this is the CURRENT baseline the plan's `<verify>` step must show growing, per the established pattern in Phase 64's summary) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LADDER-03 | `round_outcome` names one of 4 causes + breakdown, primary-cause precedence pinned | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py -k round_outcome -q` | ❌ Wave 0 (new tests) |
| LADDER-03 | `no_people_found` routes to `reentry == "search_fallback"`; the other 3 causes route to `"none"` | unit | same file, `-k round_outcome` | ❌ Wave 0 |
| LADDER-03 | Unreadable/malformed stage input fails closed to `cause: "unknown"`, does not raise | unit | same file | ❌ Wave 0 |
| SAFE-02 (D-65-10) | A `refused` disposition anywhere in `attempts` stays terminal even on a second `round_outcome` call | unit | extend `test_search_fallback.py` or `test_suggest_contacts.py`, calling `eligible_after_ladder` twice with the same refused `attempts` | ❌ Wave 0 |
| SAFE-03 (D-65-11) | Re-entry does not reset `MAX_FOLLOWUP_FETCHES`/`MAX_FALLBACK_SEARCHES` — a company already at cap before "pass 2" stays at cap | unit | same file — assert `company_budget(attempts)` / `already_searched` unchanged across the two `round_outcome` call sites | ❌ Wave 0 |
| LADDER-04 (D-65-13) | No plugin script contains a `while` loop | structural/AST | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_report_sufficiency.py::test_no_plugin_script_polls_sleeps_or_loops_on_execution_status -q` | ✅ already exists, already scans every file added |
| RICH-04 | `merge_enriched` no longer drops `seniority`/`lv_linkedin_url` etc. when the target field was blank | unit | extend `tests/test_preingest_merge.py` with a case carrying those keys in a response `properties` map | ❌ Wave 0 |
| LADDER-05 | (see disposition section — likely NOT a code-testable requirement for this phase; if the planner disagrees, an offline unit test forcing `walk["people"] == []` through to `reentry == "search_fallback"` is the closest available proxy) | unit (proxy only) | `test_suggest_contacts.py -k round_outcome` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py -q` (fast, 115+N tests, sub-second)
- **Per wave merge:** `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (full plugin suite, ~13s, must show count growing from 2492 passed / 5 skipped)
- **Phase gate:** Full suite green before `/gsd-verify-work`; also confirm `git status --porcelain -- n8n/ scripts/build_cloud_workflows.py` is empty (this phase should touch zero n8n files — mirrors Phase 64's own D5 verification, `64-01-SUMMARY.md`)

### Wave 0 Gaps

- [ ] `test_suggest_contacts.py::test_round_outcome_*` — new tests for the classifier itself (cause vocabulary, precedence, fail-closed, reentry routing per cause)
- [ ] `test_suggest_contacts_composition.py` — extend the existing composition test to drive `round_outcome` for real, mirroring how Phase 64 extended it for `walk_pages` (`64-01-SUMMARY.md`'s Deviation 1 precedent)
- [ ] `test_preingest_merge.py` — new test(s) for RICH-04's fix (whichever candidate shape the plan picks)
- [ ] Framework install: none — `.venv` and pytest already present and confirmed working

*(No test framework or fixture infrastructure gap beyond the new test cases themselves —
existing test file conventions and fixtures, e.g. `_company_row`, `FAMILY_LIST`,
`RECEPTIONIST_PAGE`/`BOARD_PAGE` in `test_suggest_contacts.py`, are directly reusable.)*

## Security Domain

`security_enforcement` is enabled in `.planning/config.json`. This phase's ASVS surface is
minimal — it is pure in-process data transformation over already-validated/already-fetched
data, with no new trust boundary crossed.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface touched |
| V3 Session Management | no | No session/grant logic touched (the open grant is read, not managed, by this phase) |
| V4 Access Control | no | No access-control decision made here |
| V5 Input Validation | yes | Fail-closed on malformed stage input (D-65-03), mirroring `eligible_after_ladder`'s existing `isinstance` guards — the same pattern, not a new one |
| V6 Cryptography | no | No crypto/secrets touched |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A malformed/adversarially-transcribed stage output (the model executing SKILL.md's pseudocode could hand `round_outcome` a corrupted `walk`/`held` structure) causing an unbounded spend | Tampering / Denial of Service (unbounded spend) | Fail-closed to `cause: "unknown"`, `reentry: "none"` (D-65-03) — never raise, never default to "eligible" |
| A refusal (`robots.txt`/access-denied) being routed around via a second classifier pass | Elevation of Privilege (bypassing a fence) | D-65-10: route THROUGH `eligible_after_ladder`, never around; `refused` is terminal on every call |

## Sources

### Primary (HIGH confidence — read this session)
- `operator-claude-plugin/scripts/suggest_contacts.py` (full file, 889 lines) — `walk_pages`, `select_people`, `partition_for_dispatch`, `synthesise_rows`, `agreed_cap`, `_ladder_source`
- `operator-claude-plugin/scripts/search_fallback.py` (full file, 490 lines) — `eligible_after_ladder`, `rank_results`, `hold_weak_sources`, the disposition/tier vocabularies
- `operator-claude-plugin/scripts/confidence.py` (full file, 169 lines) — `ALL_HOLD_CODES`, `assess()`
- `operator-claude-plugin/scripts/preingest.py:540-670` — `merge_enriched`, `_present`, `MergeResult`
- `operator-claude-plugin/scripts/extraction.py:162-176` — `canonical_props()`, `identity_groups()`
- `operator-claude-plugin/config/column_mapping.yaml` (full file) — the 8-key alias set
- `operator-claude-plugin/config/field_policy.yaml:1-227` — companies + contacts policy, verbatim
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` (full file, 488 lines) — the documented call sequence, step 5/7/8/9
- `operator-claude-plugin/tests/test_report_sufficiency.py` (full file) — the `_has_while_loop` AST guard, verbatim
- `.planning/phases/65-round-empty-re-entry-keyed-on-the-cause/65-CONTEXT.md`, `65-DISCUSSION-LOG.md`
- `.planning/phases/64-the-ladder-stops-at-the-best-page-not-the-first/64-01-SUMMARY.md`
- `.planning/todos/completed/2026-09-04-phone-is-never-chased-only-accepted.md`
- `.planning/quick/260905-rf1-role-filter-one-word-titles/260905-rf1-SUMMARY.md`, `.planning/quick/260905-ad2-company-alternate-domains/260905-ad2-SUMMARY.md`
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` (§Phase 65), `.planning/STATE.md`
- `.planning/phases/69-*/69-CONTEXT.md` (D-69-01..08, for the store shape `cause` must fit)
- Live command output this session: `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` → `2492 passed, 5 skipped in 13.03s`

### Secondary (MEDIUM confidence)
- None — no web research was performed; every claim traces to a file read or command run this session.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency, every primitive read verbatim this session
- Architecture: HIGH — the SKILL.md pseudocode and `walk_pages`/`search_fallback` call sites were read in full, not summarized from memory
- RICH-04 root cause: HIGH — traced to exact line numbers in `preingest.py`, `extraction.py`, `column_mapping.yaml`, `field_policy.yaml`, all read this session; the FIX SHAPE (candidate 1 vs 2) is a judgment call, flagged as such, not asserted as verified
- LADDER-05 disposition: HIGH confidence in the underlying finding (D-65-04 keeps the trigger unchanged); the RECOMMENDATION for how to disposition it is this researcher's judgment, flagged as such

**Research date:** 2026-09-07
**Valid until:** Until the plan for this phase is written (this research is tied to the exact commit `184ba92` state of the repo; if RICH-04 or the classifier design changes upstream before planning, re-verify the quoted line numbers)
