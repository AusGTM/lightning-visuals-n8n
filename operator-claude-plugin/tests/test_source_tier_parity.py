"""D-05a: one parity test pinning ALL FOUR tier constants against the committed
allowlist — `STRONG_TIERS`, `KNOWN_TIERS`, `LISTED_TIERS` (`search_fallback.py`) and
`SEARCH_SOURCE_TIERS` (`suggest_contacts.py`) — so a future curation edit to the
allowlist, or a change to one module's constants without the other, fails here instead
of drifting quietly (Pitfall 2, 73.1-RESEARCH.md).

Follows `tests/n8n/columnMapIdentityParity.test.mjs`'s idiom: derive one side from the
other, never restate a literal tuple on the asserted side of an assertion.
"""
import search_fallback
import suggest_contacts


def _listed_tiers_from_allowlist():
    doc = search_fallback.load_sources()
    return tuple(sorted({entry["tier"] for entry in doc["tiers"]}))


def test_listed_tiers_are_exactly_the_allowlist_tiers():
    assert search_fallback.LISTED_TIERS == _listed_tiers_from_allowlist()


def test_known_tiers_are_the_computed_ranks_plus_the_listed_ones():
    assert search_fallback.KNOWN_TIERS == (1, 2) + search_fallback.LISTED_TIERS


def test_search_source_tiers_matches_known_tiers():
    """Every stampable rank must be a rank the gate can read — a rank
    `synthesise_rows` will accept that `hold_weak_sources` cannot classify would be
    silently treated as fail-closed rather than refused up front."""
    assert suggest_contacts.SEARCH_SOURCE_TIERS == search_fallback.KNOWN_TIERS


def test_strong_tiers_are_the_two_computed_ranks():
    assert search_fallback.STRONG_TIERS == (1, 2)
    assert all(tier in search_fallback.KNOWN_TIERS for tier in search_fallback.STRONG_TIERS)


def test_rank_two_is_never_listed_as_a_host():
    """Rank 2 is STAMPED by the discovery adapter and must never be mintable from a
    matched URL — the allowlist must list no tier-2 entry at all."""
    doc = search_fallback.load_sources()
    assert 2 not in {entry["tier"] for entry in doc["tiers"]}


def test_allowlist_version_records_the_renumbering():
    doc = search_fallback.load_sources()
    assert doc["version"] == "lv-source-allowlist-v2"
