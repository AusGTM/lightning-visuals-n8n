"""operator-claude-plugin/scripts/role_classify.py

Phase 62's ONLINE half of the role vocabulary: matches one already-extracted job title
string against a supplied list of role families and returns the matching family label,
or `None`. Pure -- no I/O, no network, no model call -- mirroring
`company_domain.needs_research()`'s discipline: this module DECIDES a match, it never
derives or refreshes the family list itself. The list is always a parameter; where it
comes from (Haiku clustering of live `jobtitle` values, cached) is `role_vocabulary.py`'s
job, a different module for a different (offline, build-time) problem.

Each family entry is `{"label": <str>, "members": [<title>, ...]}`. Matching is
case-folded and whitespace-normalised over the member titles, exact match only -- no
fuzzy matching, no partial/substring matching. A title this module cannot place is `None`,
never a guess.
"""


def _normalize(value) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def classify_title(title, family_list):
    """One already-extracted job title string, and a list of role families, in; the
    matching family's `label`, or `None`, out. Never fetches, never calls a model, never
    derives or refreshes `family_list` -- that list is always supplied by the caller."""
    normalized_title = _normalize(title)
    if not normalized_title:
        return None
    for family in family_list or []:
        members = family.get("members") or []
        for member in members:
            if _normalize(member) == normalized_title:
                return family.get("label")
    return None
