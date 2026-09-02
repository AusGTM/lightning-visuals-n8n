"""operator-claude-plugin/scripts/suggest_contacts.py

Phase 62's suggestion round: after a company batch, offer the operator people worth
enriching at the companies that have nobody at them. Pure orchestration -- no HTTP
client (an HTTP client is exactly what this module never becomes -- fetching a
discovered URL is `web_fetch`'s job, a model-invoked tool this module cannot and does
not call), no scraping library, no model call, no filesystem write. That is what
satisfies the autouse `no_network` guard in tests/conftest.py by construction rather
than by a mock, the same property `url_fallback.py` and `company_domain.py` already
hold.

Discovery is the existing sitemap-sourced ladder in `url_fallback.py`, called as a
library and never re-implemented (D-62-01). Rows land through `extraction.py` -- the
same validator every other ingest lane uses -- so a suggested person gets no special
treatment (D-62-09): whatever identity the round produces is what `extraction.validate()`
decides, weak or strong.

`MAX_FOLLOWUP_FETCHES` (imported from `url_fallback`) bounds ONE company's whole
discovery ladder. This is a different axis from `WEB_RESEARCH_MAX_SEARCHES` (the
backend's own `web_search` budget) -- unrelated to this module, never referenced here.
Stage 1 (discovery) runs in the plugin; stage 2 (enrich the named people) is a later
plan's concern.
"""
import json
import sys

import extraction
import role_classify
import url_fallback

# D-62-16's tri-state verdict, branching on readability BEFORE magnitude: a count that
# could not be read is `UNKNOWN`, never silently treated as `ELIGIBLE`.
ELIGIBLE = "eligible"
HAS_CONTACTS = "has_contacts"
UNKNOWN = "unknown"

# A native HubSpot company property, confirmed present in every committed portal-schema
# baseline under config/hubspot_migration/baseline/.
CONTACT_COUNT_PROPERTY = "num_associated_contacts"


def _eligibility_verdict(row):
    row_id = row["row_id"]
    if row.get("just_created"):
        return {
            "row_id": row_id,
            "verdict": ELIGIBLE,
            "reason": "created this batch -- nothing existed to associate",
        }
    count = row.get(CONTACT_COUNT_PROPERTY)
    if count is None or count == "":
        return {
            "row_id": row_id,
            "verdict": UNKNOWN,
            "reason": f"{CONTACT_COUNT_PROPERTY!r} could not be read for this company",
        }
    try:
        count_int = int(count)
    except (TypeError, ValueError):
        return {
            "row_id": row_id,
            "verdict": UNKNOWN,
            "reason": f"{CONTACT_COUNT_PROPERTY!r} is not a readable number: {count!r}",
        }
    if count_int == 0:
        return {
            "row_id": row_id,
            "verdict": ELIGIBLE,
            "reason": f"{CONTACT_COUNT_PROPERTY} is 0",
        }
    return {
        "row_id": row_id,
        "verdict": HAS_CONTACTS,
        "reason": f"{CONTACT_COUNT_PROPERTY} is {count_int}",
    }


def eligibility(company_rows):
    """One verdict per row in `company_rows` (D-62-16). Validate-then-apply, mirroring
    `company_domain.apply_domain_decisions`'s discipline: every row is checked BEFORE any
    verdict is returned, so a malformed row (missing `row_id`) raises before a partial
    verdict list is ever emitted."""
    for row in company_rows:
        if not row.get("row_id"):
            raise ValueError(
                "a company row is missing 'row_id' -- cannot report an eligibility "
                "verdict without a stable identity. Nothing was evaluated."
            )
    return [_eligibility_verdict(row) for row in company_rows]


def discovery_plan(company_row):
    """`url_fallback.plan_ladder(website)` for this company's website/domain -- called,
    never rebuilt. A company with no usable website/domain yields a plan with no
    candidates and a reason, never a constructed guess at a path."""
    website = company_row.get("website") or company_row.get("domain")
    if not website:
        return {
            "pasted_url": None,
            "host": None,
            "cap": url_fallback.MAX_FOLLOWUP_FETCHES,
            "candidates": [],
            "notes": [
                "this company has no usable website or domain -- cannot build a "
                "discovery ladder"
            ],
        }
    return url_fallback.plan_ladder(website)


def _name_key(person):
    """`(firstname, lastname)`, case-folded and whitespace-collapsed, or `None` when
    either half is missing -- an incomplete name is never a dedupe key, so a blank
    firstname on one side can never accidentally match a blank firstname on the other."""
    first = _normalize_name(person.get("firstname"))
    last = _normalize_name(person.get("lastname"))
    if not first or not last:
        return None
    return (first, last)


def _normalize_name(value):
    return " ".join(str(value or "").strip().casefold().split())


def select_people(people, family_list, chosen_families, known_contacts):
    """The role filter plus the D-62-18 dedupe pre-filter, in one pass. A discovered
    person whose name matches a contact already associated with the company (from
    `known_contacts`, `{firstname, lastname}` dicts) is dropped BEFORE the role filter
    even runs -- the saving is in what is never spent. The match is name-based and
    deliberately conservative: only a normalised (case-folded, whitespace-collapsed)
    exact first+last match drops a person; anything short of that -- an uncertain
    near-match -- is left IN and resolved by the ingest lane's own match, the backstop
    half of D-62-18. Nothing here tries to be the match lane.

    Returns `{"selected": [...], "dropped": [...]}`; a dropped entry carries `{"person",
    "reason"}` with reason `"already_associated"` or `"role_not_selected"`."""
    chosen = set(chosen_families or [])
    known_keys = {
        key for key in (_name_key(c) for c in (known_contacts or [])) if key is not None
    }

    selected = []
    dropped = []
    for person in people:
        key = _name_key(person)
        if key is not None and key in known_keys:
            dropped.append({"person": person, "reason": "already_associated"})
            continue
        family = role_classify.classify_title(person.get("jobtitle"), family_list)
        if family is None or family not in chosen:
            dropped.append({"person": person, "reason": "role_not_selected"})
            continue
        selected.append(dict(person, role_family=family))
    return {"selected": selected, "dropped": dropped}


class CapRefused(ValueError):
    """Raised when a per-company cap cannot be trusted to bound a suggestion round's
    spend to what the operator agreed to (D-62-12, SUGGEST-05: a round may spend LESS
    than the priced per-company cap; it may never spend more). This is a deliberate
    refusal -- never a clamp, never a silent fallback to some other cap -- because the
    caller (an LLM orchestrator threading a number spoken by a human) can plausibly
    hand this a `None`, a string, or a too-large value, and any of those silently
    "handled" would spend against a ceiling the operator never actually agreed to."""


def agreed_cap(chosen_cap, grant_figures):
    """The per-company cap actually chosen by the operator for THIS round, checked
    against the priced ceiling the open grant's envelope already disclosed
    (`grant_figures["suggestion_allowance"]["priced_cap"]`) -- promotes
    `skills/suggest-contacts/SKILL.md` step 3's prose rule to code (D-62-11, D-62-12).

    Pure: no I/O, and this module gains no `write_grant` import to compute it -- reads
    a plain dict, which is all `write_grant.envelope()`'s figures ever were.

    Refuses (raises `CapRefused`; never clamps, never defaults) when:
    - the grant's figures never priced a suggestion allowance at all (missing, `None`,
      or a non-positive-int `priced_cap`) -- there is no agreed ceiling to spend
      against, and defaulting to some other number would spend against a ceiling the
      operator never saw;
    - `chosen_cap` is not a plain int `>= 1` (bools excluded -- `isinstance(True, int)`
      is `True` in Python, mirroring the isinstance shape `write_grant.envelope()`
      already uses for its own `suggestion_cap` validation);
    - `chosen_cap` exceeds the priced ceiling.

    Otherwise returns `chosen_cap` unchanged -- spending AT the priced cap is
    legitimate (an inclusive boundary, mirroring `ceiling_verdict`'s strictly-exceeds
    rule); only spending ABOVE it is refused.
    """
    allowance = (grant_figures or {}).get("suggestion_allowance")
    priced_cap = allowance.get("priced_cap") if isinstance(allowance, dict) else None
    if not (isinstance(priced_cap, int) and not isinstance(priced_cap, bool)
            and priced_cap > 0):
        raise CapRefused(
            "this round was never priced into the open grant's envelope -- "
            "grant_figures['suggestion_allowance']['priced_cap'] is missing, None, "
            "or not a positive int, so there is no agreed ceiling to spend against. "
            "Refusing rather than defaulting to a cap the operator never saw."
        )
    if not (isinstance(chosen_cap, int) and not isinstance(chosen_cap, bool)
            and chosen_cap >= 1):
        raise CapRefused(
            f"chosen_cap must be a positive int, got {chosen_cap!r} -- refusing "
            f"rather than guessing what the operator meant."
        )
    if chosen_cap > priced_cap:
        raise CapRefused(
            f"the grant priced this round at a cap of {priced_cap}; a cap of "
            f"{chosen_cap} was not what was agreed to. The round may spend LESS "
            f"than the priced cap; it may never spend more."
        )
    return chosen_cap


def synthesise_rows(company, people, fetched_url, per_company_cap):
    """At most `per_company_cap` rows shaped for `extraction.validate()`: `record_type`
    "contacts", `row` carrying only canonical props (`firstname`/`lastname`/`company`/
    `jobtitle`), `provenance` naming this module as the input and `fetched_url` -- the
    URL ACTUALLY fetched, never the company's homepage -- as the locator.

    A person with no lastname produces a row with `firstname`+`company` only; that fails
    identity and routes to the standing weak-key path -- `required_identity` is never
    widened to make it fit.

    `per_company_cap` is validated HERE, at the sole site that applies it (CR-01/WR-01,
    D-62-12): a non-negative int is required, refusing rather than silently uncapping
    (`people[:None]` has no upper bound) or truncating from the wrong end
    (`people[:-1]`). The value passed in is expected to be `agreed_cap()`'s return
    value.
    """
    if not (isinstance(per_company_cap, int) and not isinstance(per_company_cap, bool)
            and per_company_cap >= 0):
        raise CapRefused(
            f"per_company_cap must be a non-negative int, got {per_company_cap!r} -- "
            f"refusing rather than silently uncapping (people[:None] has no upper "
            f"bound) or truncating from the wrong end (people[:-1]). This is the sole "
            f"site that applies the per-company cap; the value passed in is expected "
            f"to be agreed_cap()'s return value."
        )
    canonical = set(extraction.canonical_props())
    company_name = company.get("name")
    records = []
    for person in people[:per_company_cap]:
        row = {}
        if company_name:
            row["company"] = company_name
        if person.get("firstname"):
            row["firstname"] = person["firstname"]
        if person.get("lastname"):
            row["lastname"] = person["lastname"]
        if person.get("jobtitle"):
            row["jobtitle"] = person["jobtitle"]

        extra = set(row.keys()) - canonical
        assert not extra, f"synthesised row carries non-canonical key(s): {sorted(extra)}"

        records.append(
            {
                "record_type": "contacts",
                "row": row,
                "provenance": {
                    "input": "suggest_contacts_ladder",
                    "locator": fetched_url,
                },
            }
        )
    return records


def round_artifact(records):
    """Wrap synthesised `records` as the exact in-memory dict `extraction.validate()`
    takes. No file is ever written -- `validate()` operates on the dict directly."""
    return {"records": list(records)}


def company_budget(attempts):
    """The `already_fetched` integer for THIS company, derived from its own attempt
    list. The caller threads a fresh `attempts` list per company, so this always starts
    at 0 for a company that has not yet spent any of its ladder budget -- a company that
    spent 4 fetches leaves the next company with 5, not 1. `url_fallback.
    MAX_FOLLOWUP_FETCHES` bounds one company's whole ladder; this function does not
    enforce that bound itself, `url_fallback.filter_candidates` does."""
    return len(attempts or [])


def next_candidates(company_row, attempts, sitemap_urls):
    """`url_fallback.filter_candidates`, called unmodified, with this company's own
    budget threaded through `company_budget`. Returns its result verbatim -- including
    `refused` entries with their original reasons -- never re-worded, re-ordered or
    re-checked."""
    pasted_url = company_row.get("website") or company_row.get("domain")
    return url_fallback.filter_candidates(
        pasted_url, sitemap_urls, already_fetched=company_budget(attempts)
    )


def no_candidates(company_row, pasted_url, attempts):
    """The terminal state for a company the ladder could not resolve (D-62-03): record
    `url_fallback.give_up_message`'s own text as the reason and move on. There is no
    second-source branch and no search-engine fallback here."""
    return {
        "outcome": "no_candidates_found",
        "company": company_row,
        "reason": url_fallback.give_up_message(pasted_url, attempts),
    }


def partition_for_dispatch(rows):
    """A thin call to `extraction.hold_emailless(rows)`, unchanged. A suggested row still
    without an email after stage 2 is held exactly the way a CSV row is -- no branch
    anywhere in this module reads "is this a suggestion" to change that outcome
    (D-62-09, SUGGEST-04). This function exists only to give the sitting one named seam
    to call; it adds no logic, filtering, re-ordering or annotation of its own."""
    return extraction.hold_emailless(rows)


if __name__ == "__main__":
    import pathlib

    try:
        if len(sys.argv) != 2:
            raise ValueError("usage: suggest_contacts.py <round.json>")
        _data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
        _verdicts = eligibility(_data.get("companies") or [])
        _artifact = round_artifact(_data.get("records") or [])
        print(json.dumps({"ok": True, "eligibility": _verdicts, "artifact": _artifact}))
    except Exception as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)
