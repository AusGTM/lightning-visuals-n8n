"""operator-claude-plugin/scripts/company_domain.py

Phase 58's domain confirm/decline lane (INPUT-03): a company row Claude (or the backend's
research node) PROPOSES a domain for is never written until the operator DECIDES. This
module owns exactly the transform between a proposal and a decided row — no I/O, no
network, no HubSpot call — mirroring `preingest.py::apply_match_decisions`'s two-pass
discipline: every entry in `resolved` is validated BEFORE any of it is applied, so a call
that raises has applied nothing at all (see `DomainDecisionError`'s docstring).

Every domain value this module ever accepts — a proposal's own value, or an operator's
correction — passes through `enrichment._clean_domain`, imported rather than
re-implemented. That import IS the point: `_clean_domain` is the one guard (mirrored in
`n8n/code/companyLink.js`) that turns a LinkedIn/profile URL into `None` rather than a
domain, closing the live 2026-08-25 defect recorded in `enrichment.py`'s own module
comment. A second copy of that host list here would drift the moment one side changed and
the other did not — this module defines no host collection of its own.

`apply_domain_decisions` -> `to_envelope_spec` -> `enrichment.build_envelope` is the only
path a domain travels to a webhook event, so `to_envelope_spec`'s refusal on an undecided
row is the code form of VOCAB-05's "ambiguity resolves to not-armed" — not just prose.
"""
import enrichment

# The decline sentinel a `resolved` entry uses to route a row to name-only. An object(),
# not a string ("decline") — a string sentinel could collide with an operator literally
# typing that word as a correction; an object() identity can never equal anything a caller
# builds from real input.
DECLINE_DOMAIN = object()


class DomainDecisionError(Exception):
    """Raised when a `resolved` decision set cannot be applied at all: a decision naming
    a row that was never proposed a domain, a confirm on a row with nothing proposed, or
    a decision (confirmed or corrected) that fails `enrichment._clean_domain`'s guard.

    Every entry in `resolved` is checked in one pass BEFORE any of it is applied — mirrors
    `preingest.MatchDecisionError`'s guarantee exactly: a call that raises here has applied
    nothing at all, and the caller's own input is unchanged."""


def _validate_decision(row_id, decision, proposal):
    """Raises if `decision` cannot be applied to `proposal`. Never mutates or builds
    anything — the validation pass is a pure guard, run once per entry before the apply
    pass below touches any list."""
    if decision is DECLINE_DOMAIN:
        return
    proposed_domain = proposal.get("domain")
    if decision == proposed_domain:
        if not proposed_domain:
            raise DomainDecisionError(
                f"Row {row_id!r} has nothing proposed to confirm — there is no domain "
                f"on this row to say yes to. Nothing was applied."
            )
        # Defence in depth: even a CONFIRM of the row's own proposed value must survive
        # the shared guard, in case the proposal itself was built from a profile page.
        if enrichment._clean_domain(decision) is None:
            raise DomainDecisionError(
                f"{decision!r} is a profile page rather than {proposal.get('name')!r}'s "
                f"own website, so it cannot be confirmed as their domain. Give the "
                f"company's own website address instead. Nothing was applied."
            )
        return
    # Anything else is an operator correction — accepted on the operator's word, with no
    # research pass, but still required to survive the shared guard.
    if enrichment._clean_domain(decision) is None:
        raise DomainDecisionError(
            f"{decision!r} is a profile page rather than {proposal.get('name')!r}'s own "
            f"website, so it cannot be recorded as their domain. Give the company's own "
            f"website address instead. Nothing was applied."
        )


def apply_domain_decisions(proposals, resolved):
    """Turn the operator's per-row domain decisions into a decided set.

    `proposals` is a list of proposal records, each carrying exactly: `row_id`, `name`
    (the company name), `domain` (the proposed domain string, or `None`/absent when
    nothing could be proposed), `source` (who proposed it), `reason` (a one-line
    explanation), and `evidence_url` (present only when something researched it).

    `resolved` maps a `row_id` from `proposals` to one of:
      - the row's own proposed `domain` value, verbatim — a CONFIRM,
      - `DECLINE_DOMAIN` — a DECLINE, moving the row to name-only,
      - any other string — an OPERATOR CORRECTION, accepted on the operator's word with
        no research pass, still required to survive `enrichment._clean_domain`.

    A row absent from `resolved` stays undecided — never defaulted either way, mirroring
    `apply_match_decisions`'s "never picks a candidate on the operator's behalf" rule.
    `apply_domain_decisions(proposals, {})` returns every row undecided.

    Pure — no I/O, no network. Returns a NEW structure; `proposals` and its own list/dict
    values are never mutated, so a raised call leaves the caller's own copy exactly as it
    was.

    Returns `{"decided_with_domain": [...], "decided_name_only": [...], "undecided": [...]}`.
    A `decided_with_domain` entry carries `domain` (confirmed or corrected, always cleaned)
    and `source` (the original source, or `"operator"` for a correction). A
    `decided_name_only` entry carries no `domain` key at all and a `reason` explaining why
    — so a report can disclose it honestly rather than as a confirmed domain.
    """
    proposed_by_id = {p["row_id"]: p for p in proposals}

    # Validation pass — every entry in `resolved` is checked against every guard BEFORE
    # anything below is built. See DomainDecisionError's docstring for why this must be a
    # separate pass: an entry validated only as it is applied lets an earlier valid entry
    # take effect before a later invalid one is even seen — exactly the half-applied set
    # this guards against.
    for row_id, decision in resolved.items():
        proposal = proposed_by_id.get(row_id)
        if proposal is None:
            raise DomainDecisionError(
                f"Row {row_id!r} was never proposed a domain — there is nothing to "
                f"decide on. Nothing was applied."
            )
        _validate_decision(row_id, decision, proposal)

    # Apply pass — reached only once every entry above has passed. Every list below is a
    # FRESH copy; nothing from `proposals` is appended to in place.
    decided_with_domain = []
    decided_name_only = []
    undecided = []

    for proposal in proposals:
        row_id = proposal["row_id"]
        if row_id not in resolved:
            undecided.append(dict(proposal))
            continue
        decision = resolved[row_id]
        if decision is DECLINE_DOMAIN:
            decided_name_only.append({
                "row_id": row_id,
                "name": proposal["name"],
                "reason": (
                    "declined by the operator — resolved by name lookup instead of the "
                    "proposed domain"
                ),
            })
            continue
        source = proposal.get("source") if decision == proposal.get("domain") else "operator"
        decided_with_domain.append({
            "row_id": row_id,
            "name": proposal["name"],
            "domain": enrichment._clean_domain(decision),
            "source": source,
        })

    return {
        "decided_with_domain": decided_with_domain,
        "decided_name_only": decided_name_only,
        "undecided": undecided,
    }


def needs_research(proposals, requested_check=None):
    """Which rows need backend domain research (D-58-08/09), and their identity.

    A row needs it when Claude proposed nothing for it (`domain` is falsy), or when the
    operator asked to have it checked regardless of what was proposed -- named in
    `requested_check`, a set of `row_id`s. A row Claude already proposed a domain for,
    and that the operator did not ask to double-check, is not in this set: the free
    in-conversation proposal is the primary path and spends nothing (D-58-01).

    Pure -- no I/O, no network, no research call. This only names the rows; pricing
    them is `cost_guard.research_line`'s job, and actually researching them is neither
    function's job. Each returned row carries `row_id` and `name` only, so a caller
    (an envelope line, a report) can name the row without reaching back into
    `proposals`.
    """
    requested_check = set(requested_check or [])
    return [
        {"row_id": p["row_id"], "name": p["name"]}
        for p in proposals
        if not p.get("domain") or p["row_id"] in requested_check
    ]


def decline_research(resolved, needs_research_rows):
    """Strike the research line: route every needs-research row not already decided to
    the SAME `DECLINE_DOMAIN` sentinel a manual decline uses, so it converges on
    `apply_domain_decisions`'s existing name-only path rather than a second one
    (D-58-10) -- one story for every no-domain row, not two that must be reconciled.

    Never overrides an entry already present in `resolved`: an explicit operator
    decision (a confirm, a correction, or an earlier decline) stands. Marks nothing
    else -- a row outside `needs_research_rows` is untouched.

    Pure -- returns a NEW dict; `resolved` is never mutated. Feed the result straight
    into `apply_domain_decisions`, unchanged.
    """
    struck = dict(resolved)
    for row in needs_research_rows:
        row_id = row["row_id"]
        if row_id not in struck:
            struck[row_id] = DECLINE_DOMAIN
    return struck


def to_envelope_spec(decided):
    """Turn a decided set (as returned by `apply_domain_decisions`) into the
    `{"companies": [...]}` spec `enrichment.build_envelope` consumes.

    RAISES when any row is still undecided, naming those rows — this is where VOCAB-05's
    "ambiguity resolves to not-armed" lives in code, not only in prose: a row without a
    yes, a correction, or a decline stops the whole batch build rather than defaulting
    either way.

    A decided-with-domain row contributes `{"name", "domain"}`. A decided-name-only row
    contributes `{"name"}` with no `domain` key at all, so the backend's exact-name search
    resolves it — the row travels, it just travels without a domain.
    """
    undecided = decided.get("undecided") or []
    if undecided:
        row_ids = ", ".join(str(row.get("row_id")) for row in undecided)
        raise DomainDecisionError(
            f"{len(undecided)} row(s) still need a decision before this batch can go — "
            f"each needs a yes, a correction, or a decline first: {row_ids}."
        )
    companies = [
        {"name": row["name"], "domain": row["domain"]}
        for row in decided.get("decided_with_domain", [])
    ] + [
        {"name": row["name"]}
        for row in decided.get("decided_name_only", [])
    ]
    return {"companies": companies}
