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


def select_people(people, family_list, chosen_families, known_contacts):
    """The role filter: keep only people whose `jobtitle` classifies (via
    `role_classify.classify_title`) into one of `chosen_families`. Returns
    `{"selected": [...], "dropped": [...]}`; a dropped entry carries `{"person",
    "reason"}`. `known_contacts` is accepted here for interface stability across this
    plan's tasks -- the D-62-18 dedupe pre-filter it drives is added on top of this
    function later in this same plan."""
    chosen = set(chosen_families or [])
    selected = []
    dropped = []
    for person in people:
        family = role_classify.classify_title(person.get("jobtitle"), family_list)
        if family is None or family not in chosen:
            dropped.append({"person": person, "reason": "role_not_selected"})
            continue
        selected.append(dict(person, role_family=family))
    return {"selected": selected, "dropped": dropped}


def synthesise_rows(company, people, fetched_url, per_company_cap):
    """At most `per_company_cap` rows shaped for `extraction.validate()`: `record_type`
    "contacts", `row` carrying only canonical props (`firstname`/`lastname`/`company`/
    `jobtitle`), `provenance` naming this module as the input and `fetched_url` -- the
    URL ACTUALLY fetched, never the company's homepage -- as the locator.

    A person with no lastname produces a row with `firstname`+`company` only; that fails
    identity and routes to the standing weak-key path -- `required_identity` is never
    widened to make it fit.
    """
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
