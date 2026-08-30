"""operator-claude-plugin/scripts/confidence.py

D-61-07: "the phase needs a real confidence signal to hang this on — today there is
none, and that absence IS the finding." This module IS that signal: one pure function,
`assess()`, turning a row's already-computed outcome (`preingest.parse_outcome`'s
typed `Outcome` — never raw response JSON) into exactly one of two verdicts, CONFIDENT
or HELD, with a closed-vocabulary `hold_code` and a human reason on every HELD verdict.

No new scale, no numeric score, no model call. The three inputs are signals the
pipeline ALREADY produces: the match tier `n8n/code/matchProposal.js`'s
`summarizeMatch` already stamps, the provider-agreement signal
`n8n/code/scoreEnrichment.js` already computes as `agreedBy`, and the material-conflict
/ judge-adjudication pair CLAUDE.md §15.0 already routes. A confidence NUMBER invented
here would be a fourth thing to keep in step with three that already disagree — D-61-07
asks for a signal, not a metric.

`agreedBy`'s role (REVIEW-C8), stated once so no later row re-derives it:
  - Agreement is a signal about ENRICHED fields. A row that went through no enrichment
    has no agreement to read — that absence is NOT disagreement, and such a row is
    judged on its match signals alone.
  - Provider DISAGREEMENT on a veto-capable field needs no row of its own — it already
    reaches this table as a material conflict (CLAUDE.md §15.0's suppression is what
    turns the disagreement into a conflict group in the first place).
  - Agreement is corroboration, never a rescue: it never lifts a row held by an
    `unknown` tier, an unadjudicated conflict, or ambiguity. This table's first-match-
    wins ordering already guarantees this by construction; this paragraph exists so
    nobody adds an "agreed -> confident" row later.
  - A single provider's value on a non-material field is not, by itself, a hold — the
    non-clobber merge policy (downstream, untouched) already governs whether it is ever
    written. Duplicating that as a confidence rule would hold most of a normal batch
    for a risk the merge policy already carries.

The table is TOTAL (REVIEW-A5): its last row is a terminal `else -> HELD`, so a signal
vocabulary that drifts (a fifth match tier, a new conflict shape, an `unparseable`
outcome) always yields a hold, never a confident default. Read top to bottom, first
match wins — the whole policy is legible on one screen and a future change is a table
row, not a nest of conditions.

Pure: no I/O, no config read, no network, no clock, no randomness — the same inputs
always produce the same verdict, mirroring `preingest.classify_matches`' own purity.

`held_queue.py` imports the `HOLD_*` codes below to decide whether a hold is
ENRICHMENT-STAGE (its holding signal is one of the three enrichment signals: provider
agreement, conflict groups, judge adjudication) or MATCH-STAGE (every other code) —
see that module's own docstring for why the distinction governs what a resume's
fingerprint may hash.
"""
from dataclasses import dataclass

CONFIDENT = "confident"
HELD = "held"

# The closed hold-code vocabulary (REVIEW-06/HIGH-6). Exactly one of these two is set
# whenever the verdict is HELD; both are `None` when the verdict is CONFIDENT.
# `HOLD_UNADJUDICATED_CONFLICT` is the ONLY enrichment-stage code today — its holding
# signal is the conflict-group / judge-adjudication pair. Every other code holds on a
# match-stage signal (the outcome's own parseability, its match tier, or its candidate
# count) and is therefore MATCH-STAGE, per `held_queue.py`'s classifying rule.
HOLD_UNPARSEABLE = "unparseable"
HOLD_UNADJUDICATED_CONFLICT = "unadjudicated_conflict"
HOLD_UNKNOWN_TIER = "unknown_tier"
HOLD_NO_MATCH = "no_match"
HOLD_AMBIGUOUS_CANDIDATES = "ambiguous_candidates"
HOLD_NO_TABLE_ROW_MATCHED = "no_table_row_matched"

# The classifying rule `held_queue.py` inherits (REVIEW-C10/C12, stated once, here,
# where the codes themselves are defined — a code added later reads this set to know
# which stage it belongs to, rather than guessing).
ENRICHMENT_STAGE_HOLD_CODES = frozenset({HOLD_UNADJUDICATED_CONFLICT})


@dataclass(frozen=True)
class ConfidenceVerdict:
    """`verdict` is `CONFIDENT` or `HELD` — two states, no third (a middle band would
    recreate the per-row question this phase exists to remove). `hold_code` is one of
    the closed `HOLD_*` words above, and `reason` is the human sentence naming the
    signal that withheld it; both are `None` exactly when `verdict == CONFIDENT`."""

    verdict: str
    hold_code: str = None
    reason: str = None


def _unresolved_conflict_groups(outcome):
    """The material-conflict GROUP NAMES that remain unadjudicated — a group counts as
    resolved the moment ANY of its member fields appears in `judge_adjudicated_fields`
    (CLAUDE.md §15.0: "the ban is on an UNADJUDICATED conflict, not on the field").
    Tolerant of a malformed group entry (not a dict, no `fields` list) — a shape this
    parser cannot read is treated as unresolved, never silently dropped."""
    adjudicated_fields = set((outcome.judge_adjudicated_fields or {}).keys())
    unresolved = []
    for group in (outcome.material_conflicts or []):
        fields = (group.get("fields") or []) if isinstance(group, dict) else []
        if any(field in adjudicated_fields for field in fields):
            continue
        name = group.get("group") if isinstance(group, dict) else None
        unresolved.append(name or "an unnamed group")
    return unresolved


def assess(outcome) -> ConfidenceVerdict:
    """The decision table. `outcome` is `preingest.Outcome` (or anything exposing the
    same attributes: `parseable`, `match_tier`, `candidate_count`, `provider_agreement`,
    `material_conflicts`, `judge_adjudicated_fields`)."""

    # Row 0: an outcome this client could not even parse is held before anything else
    # is read — a signal this parser cannot verify must never be treated as a good one.
    if not outcome.parseable:
        return ConfidenceVerdict(
            HELD, HOLD_UNPARSEABLE,
            "the row's outcome could not be parsed — a missing or unrecognised signal "
            "is never read as a good one",
        )

    # Row 1: an unadjudicated material conflict holds the row REGARDLESS of match tier
    # — checked before the tier rows below, so a high-tier match with a live conflict
    # is never mistaken for confident.
    unresolved = _unresolved_conflict_groups(outcome)
    if unresolved:
        return ConfidenceVerdict(
            HELD, HOLD_UNADJUDICATED_CONFLICT,
            "an unadjudicated provider conflict on " + ", ".join(sorted(unresolved)),
        )

    tier = outcome.match_tier
    candidate_count = outcome.candidate_count or 0

    # Row 2: the only CONFIDENT row in the whole table.
    if tier == "high":
        return ConfidenceVerdict(CONFIDENT)

    # Row 3: "we could not look" is never a basis for acting.
    if tier == "unknown":
        return ConfidenceVerdict(
            HELD, HOLD_UNKNOWN_TIER,
            "match tier is unknown — the search could not run",
        )

    # Row 4: no record found at all.
    if tier == "none":
        return ConfidenceVerdict(
            HELD, HOLD_NO_MATCH,
            "no match found — not confident enough to act without review",
        )

    # Row 5: an ambiguous person is exactly the wrongly-matched-person risk D-61-03
    # fences off. The count comes from Task 1's named `candidate_count` signal
    # (REVIEW-C9), never re-derived from `len(candidates)` a second way.
    if tier == "medium" and candidate_count > 1:
        return ConfidenceVerdict(
            HELD, HOLD_AMBIGUOUS_CANDIDATES,
            f"medium-tier match with {candidate_count} candidates — ambiguous, never a pick",
        )

    # Row 6 (REVIEW-A5, terminal): everything else — a medium-tier match with exactly
    # one unverified candidate, or a signal vocabulary that has drifted (a fifth match
    # tier this table does not know) — is held, never defaulted confident.
    return ConfidenceVerdict(
        HELD, HOLD_NO_TABLE_ROW_MATCHED,
        "no table row matched this row's signals — held rather than guessed",
    )
