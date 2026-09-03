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

A company's `website`/`domain` is a bare CRM property, not a pasted URL, so it is
normalised at THIS seam (`_ladder_source`, below) before either call site hands it to
`url_fallback.py` -- one helper, used by both `discovery_plan` and `next_candidates`
(62-07-PLAN.md Decision 1). The host rule and its non-goals (scheme prefixed only when
absent; `www.`, case, path and query preserved exactly as recorded; no redirect
following, no host-variant retry) are 62-07-PLAN.md Decision 2.

`MAX_FOLLOWUP_FETCHES` (imported from `url_fallback`) bounds ONE company's whole
discovery ladder. This is a different axis from `WEB_RESEARCH_MAX_SEARCHES` (the
backend's own `web_search` budget) -- unrelated to this module, never referenced here.
Stage 1 (discovery) runs in the plugin; stage 2 (enrich the named people) is a later
plan's concern.
"""
import json
import sys

import enrichment
import extraction
import preingest
import role_classify
import url_fallback

_NO_USABLE_WEBSITE_REASON = (
    "this company has no usable website or domain -- cannot build a discovery ladder"
)


def _ladder_source(company_row):
    """`(url, reason)`, exactly one set. `website` wins over `domain` -- the existing
    first-non-empty precedence, UNCHANGED, with no fall-through from a failing `website`
    to `domain` (62-07-PLAN.md Decision 2 sub-decision): a value that fails the guard
    below is reported by name, never silently retried against the other property.

    The guard is `enrichment._clean_domain`, called as a BOOLEAN test only -- its return
    value (scheme and `www.` stripped) is never the host that gets built, because
    Decision 2 forbids rewriting either. A `None` return, or a return with no dot in it
    (e.g. "unknown"), means the recorded value cannot be a company's own site.

    A value that already carries a scheme (http/https, case-insensitive) is returned
    unchanged. Otherwise `https://` is prefixed and nothing else is touched -- no path
    drop, no query drop, no case change, no `www` edit -- so this is a byte-identical
    no-op for every value that already works today.
    """
    recorded = company_row.get("website") or company_row.get("domain")
    if not recorded:
        return None, _NO_USABLE_WEBSITE_REASON

    cleaned = enrichment._clean_domain(recorded)
    if cleaned is None or "." not in cleaned:
        return None, (
            f"{recorded!r} does not look like this company's own website -- cannot "
            f"build a discovery ladder"
        )

    if recorded.lower().startswith(("http://", "https://")):
        return recorded, None
    return f"https://{recorded}", None

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
    """`url_fallback.plan_ladder(...)` for this company's website/domain -- called, never
    rebuilt. The CRM value is normalised at the seam first (`_ladder_source`); a company
    with no usable website/domain, or a recorded value that cannot be its own site,
    yields a plan with no candidates and a reason naming the recorded value, never a
    constructed guess at a path."""
    recorded = company_row.get("website") or company_row.get("domain")
    url, reason = _ladder_source(company_row)
    if reason:
        return {
            "pasted_url": None,
            "host": None,
            "cap": url_fallback.MAX_FOLLOWUP_FETCHES,
            "candidates": [],
            "notes": [reason],
        }
    plan = url_fallback.plan_ladder(url)
    if url != recorded:
        plan["notes"] = list(plan["notes"]) + [
            f"{recorded!r} had no scheme; every candidate below is bound to {url!r}."
        ]
    return plan


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


def mint_row_ids(records):
    """Mint the whole batch's `row_id` join keys ONCE, over every eligible company's
    accumulated `records`, by calling `preingest.build_rows_spec` -- never per company,
    since that function mints `row-1`, `row-2`, ... by POSITION and a per-company call
    would mint `row-1` at every company, joining two different people onto one id with
    no error (Decision 1, 62-08-PLAN.md).

    Returns `{"spec": <build_rows_spec's own spec>, "records": [...]}`: `spec` is the
    exact dict `chunking.plan_chunks` takes, and `records` is a fresh list pairing each
    input record with the spec row minted at its own index, so a person's `provenance`
    stays attached to the row that now carries their `row_id`. `preingest.RowSpecError`
    (an empty batch, or a row that already carries a `row_id`) propagates untouched --
    never caught, re-worded or worked around; a duplicate mint site is exactly the
    ambiguity this function exists to prevent.
    """
    spec = preingest.build_rows_spec([record["row"] for record in records])
    minted_records = [
        {**record, "row": spec_row}
        for record, spec_row in zip(records, spec["rows"])
    ]
    return {"spec": spec, "records": minted_records}


def rejoin_enriched(records, merged_rows):
    """Give each of `records` its own stage-2 MERGED row back, joined on `row_id` --
    never on position.

    `preingest.merge_enriched` returns FRESH rows and never mutates the ones it was
    given (its own docstring), so without this join the round's own `records` would
    still hold pre-merge rows: `partition_for_dispatch` would then HOLD every row the
    waterfall had just filled, reporting an enriched person as though nothing had been
    found (Decision 2, 62-08-PLAN.md).

    Indexes `merged_rows` by `row_id` first, then walks `records`; a record whose id is
    absent from that index raises `ValueError` naming it -- `merge_enriched` walks the
    rows it was given and returns exactly one row per input row, so a missing id means
    a different row set was passed in and every downstream verdict would be about the
    wrong person. Returns a fresh records list; mutates nothing.
    """
    merged_by_id = {row["row_id"]: row for row in merged_rows}
    rejoined = []
    for record in records:
        row_id = record["row"]["row_id"]
        if row_id not in merged_by_id:
            raise ValueError(
                f"row {row_id!r} has no merged row to rejoin against -- merge_enriched "
                f"returns exactly one row per input row, so a missing id means a "
                f"different row set was passed in and every downstream verdict would "
                f"be about the wrong person."
            )
        rejoined.append({**record, "row": merged_by_id[row_id]})
    return rejoined


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
    budget threaded through `company_budget`. The pasted URL comes from the SAME seam
    helper `discovery_plan` uses (`_ladder_source`) -- the second broken call site
    (62-07-PLAN.md Decision 1) -- so a bare-domain company's sitemap candidates are
    checked against the same host they were actually built for, rather than an empty
    authority. A recorded value the helper cannot turn into a URL raises `ValueError`
    naming it, rather than handing `filter_candidates` something unusable. Otherwise
    returns `url_fallback.filter_candidates`'s result verbatim -- including `refused`
    entries with their original reasons -- never re-worded, re-ordered or re-checked."""
    pasted_url, reason = _ladder_source(company_row)
    if reason:
        raise ValueError(reason)
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


_RELATION_REASON_CODES = {
    "freemail": "email_domain_freemail",
    "mismatch": "email_domain_mismatch",
    "company_domain_unknown": "company_domain_unknown",
}


def email_domain_relation(email, company_website):
    """One of `"no_email"`, `"freemail"`, `"company_domain_unknown"`, `"related"`,
    `"mismatch"` -- evaluated in that order (62-12, G-62-7, operator ruling
    2026-09-04: "the email domain should be related to the company").

    "related" <=> ed == cd or ed.endswith("." + cd) -- equal, or a label-boundary
    SUBDOMAIN of the company's own domain. Both sides go through
    `enrichment._clean_domain` (lowercase, scheme and `www.` stripped, host only), the
    one domain-normalisation guard the client, the ingest lane, and this check all
    already agree on -- so `www.romaturfclub.com.au` and `romaturfclub.com.au` are the
    same string with no extra helper, and `staff@mail.romaturfclub.com.au` is that
    club's own domain.

    The subdomain direction is deliberate and single-directional:
    `ed.endswith("." + cd)` accepts a host UNDER the company's own domain (which the
    company's own DNS controls), and refuses `romaturfclub.com.au.attacker.tld` --
    that string does not end with `.romaturfclub.com.au`. This is the send-direction
    sibling of `url_fallback`'s fetch-guard suffix trap. The reverse (company recorded
    at a subdomain, email at the apex) is NOT related -- fail-closed; a company
    recorded at a subdomain is a rarity and holding it is cheap.

    Freemail is tested BEFORE relatedness, so a personal-mailbox address is never
    reported as a mismatch -- that is what lets the held pile separate strangers from
    people with Gmail at a glance.

    Accepted, measured cost (Decision 3, 62-12-PLAN.md): `kdaniel@lismoreturfclub.com`
    against a company recorded at `lismoreturfclub.com.au` is a MISMATCH under this
    rule -- `.com` is not `.com.au` and is not a subdomain of it. Relating the two
    would need registrable-domain (public-suffix) logic this repo does not carry, or a
    heuristic that could relate a domain the company never registered. The operator
    accepted this cost, with the round's own zero-sendable consequence in view, rather
    than widen the rule. Widening path, if ever asked for: one small
    registrable-domain-equivalence helper plus its own fixture set -- not a change to
    this function's ordering.

    Deliberately NOT `url_fallback._canonical_authority` (62-10) -- that comparator is
    built for a security guard on what the agent will FETCH (parses a netloc, carries
    the port, refuses a dotless remainder). This question has no URLs and no ports; it
    compares an email's domain to a CRM property to decide what to SEND. Importing a
    fetch-guard's port semantics here would borrow the wrong invariant.

    No public-suffix / registrable-domain dependency is used or considered.
    """
    stripped = str(email or "").strip().lower()
    if "@" not in stripped:
        return "no_email"
    raw = stripped.rsplit("@", 1)[-1]
    if not raw:
        return "no_email"
    if raw in enrichment.FREEMAIL_DOMAINS:
        return "freemail"
    cd = enrichment._clean_domain(company_website)
    if cd is None or "." not in cd:
        return "company_domain_unknown"
    ed = enrichment._clean_domain(raw)
    if ed is None:
        return "mismatch"
    if ed == cd or ed.endswith("." + cd):
        return "related"
    return "mismatch"


def _relation_reason(relation, email, company_website):
    """The prose text for a held entry, per 62-12-PLAN.md Decision 5's table. Every
    branch names what was compared -- no bare flag ever reaches the operator."""
    stripped = str(email or "").strip().lower()
    domain = stripped.rsplit("@", 1)[-1] if "@" in stripped else stripped

    if relation == "freemail":
        return (
            f"{domain} is a personal mailbox, not this company's own domain -- held "
            f"and labelled separately from a stranger's domain so the held pile stays "
            f"legible"
        )
    if relation == "mismatch":
        cd = enrichment._clean_domain(company_website)
        if cd is None:
            return f"email domain {domain} does not match this company's recorded domain"
        return f"email domain {domain} does not match {cd}"
    if relation == "company_domain_unknown":
        if not company_website:
            return (
                f"this company has no recorded website or domain -- nothing to "
                f"compare {domain} against"
            )
        return (
            f"{company_website!r} does not look like this company's own domain -- "
            f"nothing to compare {domain} against"
        )
    return f"{email!r} does not look like a usable email address"


def partition_for_dispatch(rows, company_domains):
    """Split `rows` into `(sendable, held)`, holding a row whose enriched email is not
    related to the company that named the person (62-12, G-62-7, operator ruling
    2026-09-04: "the email domain should be related to the company").

    This is scoped to THIS suggestion round only: `extraction.hold_emailless` -- shared
    by `contact-upload` and `enrich-before-ingest`, where the operator supplied the
    email themselves -- is called unchanged and untouched. A suggested row's email came
    from a provider resolving a weak identity-group-2 key (firstname+lastname+company);
    an operator-typed address carries no such risk, and the ruling was made about the
    former, not the latter.

    `company_domains` maps a company NAME (normalised the same way `select_people`'s
    dedupe already normalises names -- case-folded, whitespace-collapsed) to that
    company's recorded `website`/`domain` string. It is REQUIRED, with no default: an
    optional argument here would be a one-keyword bypass of the operator's ruling. A
    row whose company is absent from the map, or whose recorded value cannot be turned
    into a domain, is held with `reason_code: "company_domain_unknown"` -- never sent.

    Runs `extraction.hold_emailless(rows)` first, stamping its held entries with
    `reason_code: "no_email"` and keeping their reasons verbatim. Every remaining row
    is then classified by `email_domain_relation`; `"related"` stays sendable, and
    every other verdict becomes a held entry naming the ORIGINAL index in `rows` (never
    a position in the sendable sublist, which would renumber this pass's holds).
    Returns `(sendable, held)` with `held` ordered by original index, so the two passes
    read as one list.

    Every held entry carries `{"index", "row", "reason", "reason_code"}` -- a uniform
    shape across both passes. `confidence.ALL_HOLD_CODES` is not widened by these
    codes: they describe why a SUGGESTION round declined to send, not a held-queue
    class, and the held-row path downstream (`confidence.assess()` ->
    `held_queue.build_entry()`) is unchanged.
    """
    _, no_email_held = extraction.hold_emailless(rows)
    held_indices = {entry["index"] for entry in no_email_held}
    for entry in no_email_held:
        entry["reason_code"] = "no_email"

    domains_by_name = {
        _normalize_name(name): website for name, website in (company_domains or {}).items()
    }

    sendable = []
    held = list(no_email_held)
    for i, row in enumerate(rows):
        if i in held_indices:
            continue
        company_website = domains_by_name.get(_normalize_name(row.get("company")))
        relation = email_domain_relation(row.get("email"), company_website)
        if relation == "related":
            sendable.append(row)
            continue
        held.append(
            {
                "index": i,
                "row": row,
                "reason": _relation_reason(relation, row.get("email"), company_website),
                "reason_code": _RELATION_REASON_CODES.get(relation, relation),
            }
        )

    held.sort(key=lambda entry: entry["index"])
    return sendable, held


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
