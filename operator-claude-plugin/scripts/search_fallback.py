"""operator-claude-plugin/scripts/search_fallback.py

The web-search fallback for a suggestion round whose sitemap ladder finished without
finding a person (quick task 260904-5sd). Three pure decisions, in the order the round
makes them:

  1. `eligible_after_ladder(attempts)` -- may the round look anywhere else at all?
  2. `rank_results(results, company_url)` -- which of the search's URLs may be fetched,
     and how much is each source's claim worth?
  3. `hold_weak_sources(records, sendable, held)` -- may a person found that way be SENT,
     or only shown?

PURITY, stated precisely and honestly. This module builds and checks strings. Its only
filesystem reads are the shipped allowlist (inside `load_sources`) and the model's own
scratch JSON (inside the `__main__` guard). It holds NO HTTP client: the search and every
fetch are model-invoked tools this module cannot call. It therefore CANNOT claim
`url_fallback.py`'s "no I/O of any kind" -- it loads a shipped config -- and the AST guard
in `tests/test_search_fallback.py` is scoped accordingly, permitting `open()` in exactly
those two places and `yaml` in the import allowlist. The autouse `no_network` guard in
tests/conftest.py is still satisfied by construction rather than by a mock: nothing here
can reach the network, so there is nothing to stub.

WHY THIS IS A SEPARATE MODULE FROM `url_fallback.py`. That module's entire safety property
is `same_host`: every candidate it hands back is on the pasted URL's own host. A search
result is off-host BY DEFINITION, so putting this behind that guard would destroy the
property rather than extend it. Different boundary, different module.

The three decisions above are independent gates and every one of them must hold. A tier-3
person the waterfall confirmed perfectly is still held (D-5sd-05); a refusal anywhere in
the ladder closes the whole path however promising the search would have been (D-5sd-04).
"""
import json
import sys
from urllib.parse import urlsplit
from pathlib import Path

import url_fallback

# Bounds this company's WHOLE search fallback: at most this many searches (SKILL.md prose,
# the same class of bound the fetch ordering already is) and at most this many accepted
# URLs handed back, enforced here and threaded across calls via `already_searched`.
# Mirrors `url_fallback.MAX_FOLLOWUP_FETCHES`'s register.
#
# Per D-5sd-03 the searches themselves spend no provider credit and no separately-billed
# tokens -- they run in the operator's own Claude Code session -- so they sit OUTSIDE the
# SUGGEST-05 priced ceiling. The Lusha credit that a promoted person later triggers is NOT
# free and stays inside it; do not let the "free" ruling leak onto the enrichment call.
#
# Deliberately NOT named `WEB_RESEARCH_MAX_SEARCHES`: `suggest_contacts.py:25-29` reserves
# that name for the backend's own, unrelated company-ICP research axis.
MAX_FALLBACK_SEARCHES = 3

# `provenance.input` values. A record's provenance is what declares where a person came
# from; the row itself never can (see `hold_weak_sources`).
SEARCH_INPUT = "suggest_contacts_web_search"
LADDER_INPUT = "suggest_contacts_ladder"

# D-5sd-05: "strong source" stops at tier 2. Tier 1 is the company's own host and tier 2
# is LinkedIn -- both self-attested and current in a way a third-party mention is not.
STRONG_TIERS = (1, 2)
KNOWN_TIERS = (1, 2, 3)
LISTED_TIERS = (2, 3)

SOURCE_TIER_HOLD_CODE = "search_source_not_strong"

# The closed disposition vocabulary, recorded by the model on each `attempts` entry
# alongside the existing free-prose `outcome` (which stays untyped and is still rendered
# verbatim by `url_fallback.give_up_message`). `refused` is ONE disposition covering every
# cause: `web_fetch` cannot report `robots.txt` as a distinct cause and
# `contact-upload/extraction.md:233-236` forbids claiming it.
DISPOSITION_EMPTY = "empty"
DISPOSITION_CAP_EXHAUSTED = "cap_exhausted"
DISPOSITION_REFUSED = "refused"
ELIGIBLE_DISPOSITIONS = (DISPOSITION_EMPTY, DISPOSITION_CAP_EXHAUSTED)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ALLOWLIST_PATH = PLUGIN_ROOT / "config" / "source_allowlist.yaml"


class SourceAllowlistError(Exception):
    """Raised when the shipped source allowlist is missing, unparseable, or describes
    something this ranker does not implement. Names the file -- mirrors
    `role_classify.RoleVocabularyError`'s register: a missing shipped config file is an
    incomplete install, never a silent empty list, which here would render as "no source
    qualified" and read as a finding rather than a broken install."""


def load_sources(path=None):
    """The committed source allowlist, validated whole before any of it is returned.

    Mirrors `role_classify.load_families` in all four of its properties: a `path`
    parameter for tests, defaulting to the shipped file; `import yaml` INSIDE the
    function; refusing a missing or unparseable file BY NAME; and validating the document
    rather than returning something half-formed.

    The document is `{"version", "tiers": [{"tier", "label", "hosts"}, ...]}`. Only tiers
    2 and 3 may be listed: tier 1 is COMPUTED from the company's own host and differs per
    company, and tier 4 is the ABSENCE of a match. A host in two tiers is refused rather
    than silently resolved in file order, because file order is not a ranking decision
    anyone made.
    """
    import yaml

    allowlist_path = Path(path) if path is not None else DEFAULT_ALLOWLIST_PATH
    if not allowlist_path.exists():
        raise SourceAllowlistError(
            f"Source allowlist not found at {allowlist_path}. It ships with the plugin -- "
            "if it is missing, the install is incomplete; reinstall rather than ranking "
            "every source as unlisted."
        )
    try:
        document = yaml.safe_load(allowlist_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        raise SourceAllowlistError(
            f"Source allowlist at {allowlist_path} could not be parsed as YAML."
        ) from None

    tiers = document.get("tiers") if isinstance(document, dict) else None
    if not isinstance(tiers, list) or not tiers:
        raise SourceAllowlistError(
            f"Source allowlist at {allowlist_path} is missing its 'tiers' list."
        )

    seen_hosts = {}
    for entry in tiers:
        if not isinstance(entry, dict):
            raise SourceAllowlistError(
                f"Source allowlist at {allowlist_path} has a tier entry that is not an "
                f"object: {entry!r}"
            )
        tier = entry.get("tier")
        if isinstance(tier, bool) or tier not in LISTED_TIERS:
            raise SourceAllowlistError(
                f"Source allowlist at {allowlist_path} lists tier {tier!r}; only "
                f"{list(LISTED_TIERS)} may be listed. Tier 1 is computed from the "
                f"company's own host and tier 4 is the absence of a match."
            )
        if not isinstance(entry.get("label"), str) or not entry["label"].strip():
            raise SourceAllowlistError(
                f"Source allowlist at {allowlist_path}: tier {tier} has no label, so a "
                f"rejected or held row could not say what the source was."
            )
        hosts = entry.get("hosts")
        if not isinstance(hosts, list) or not hosts:
            raise SourceAllowlistError(
                f"Source allowlist at {allowlist_path}: tier {tier} has no hosts."
            )
        for host in hosts:
            if (
                not isinstance(host, str)
                or host != host.strip().lower()
                or "." not in host
                or "/" in host
                or ":" in host
            ):
                raise SourceAllowlistError(
                    f"Source allowlist at {allowlist_path}: {host!r} is not a bare "
                    f"lowercase dotted host (no scheme, no path, no port)."
                )
            if host in seen_hosts:
                raise SourceAllowlistError(
                    f"Source allowlist at {allowlist_path}: {host!r} appears in tier "
                    f"{seen_hosts[host]} and tier {tier}. A host has one rank; file "
                    f"order is not a ranking decision anyone made."
                )
            seen_hosts[host] = tier

    return document


def eligible_after_ladder(attempts):
    """`{"eligible": bool, "reason": str}` -- may the round look past the ladder at all?

    FAIL-CLOSED, and deliberately so (D-5sd-06): an `attempts` entry whose disposition is
    unknown, absent or unreadable makes the whole ladder INELIGIBLE. It does NOT raise.
    Raising would surface a transcription gap as a crash mid-round; the fail-closed
    reading simply declines to open the search path, and the round reports and moves on
    exactly as it does today. The ONLY way through here is an affirmative `empty` or
    `cap_exhausted` on every recorded attempt.

    `refused` anywhere -- first position or last -- closes the path (D-5sd-04). Phase 53's
    principle survives intact: escalating past a refusal turns a fence into a suggestion,
    and this predicate is what keeps a fence a fence.

    `cap_exhausted` is ELIGIBLE because a budget we imposed on ourselves is not a fence
    the site put up. Nobody refused us; we stopped looking. That is materially closer to
    "found nothing" than to "told no".

    An EMPTY list is ineligible: with no attempt on record, nothing establishes that the
    crawl completed rather than never running.
    """
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
        url = attempt.get("url")
        disposition = attempt.get("disposition")
        if disposition == DISPOSITION_REFUSED:
            return {
                "eligible": False,
                "reason": (
                    f"{url} was refused. A refusal is terminal -- escalating past it "
                    f"turns a fence into a suggestion (D-5sd-04)."
                ),
            }
        if disposition not in ELIGIBLE_DISPOSITIONS:
            return {
                "eligible": False,
                "reason": (
                    f"{url} carries no readable disposition ({disposition!r}); the only "
                    f"values that open the search path are "
                    f"{list(ELIGIBLE_DISPOSITIONS)} (D-5sd-06, fail-closed)."
                ),
            }

    return {
        "eligible": True,
        "reason": (
            f"every one of the {len(attempts)} ladder attempt(s) completed without being "
            f"refused -- this is absence of information, not a fence."
        ),
    }


def _host_matches(host, listed):
    """The ONE matching rule, for all three tiers: `host == listed` or `host` is a
    label-boundary SUBDOMAIN of `listed`. Never a bare substring or `endswith(listed)`
    test, which would accept `linkedin.com.attacker.tld` as LinkedIn.

    Deliberately NOT `url_fallback.same_host`: that is a FETCH guard on
    attacker-influenceable sitemap content and refuses subdomains outright, so a search
    hit on the company's own `board.example.com` would fall to tier 4 and be thrown away.
    This is a SOURCE-RANKING question -- whose claim to trust -- and a company's own
    subdomain is the company. Same direction and same suffix trap as
    `suggest_contacts.email_domain_relation`.
    """
    return bool(listed) and (host == listed or host.endswith("." + listed))


def _tier_of(host, company_host, sources):
    """`(tier, label)` for `host`, or `(None, None)` when it is on no tier.

    The company's own host is checked FIRST, so a company that also appears on the
    tier-3 allowlist (a racing authority searching for its own people) ranks its own site
    tier 1 rather than demoting it to a third-party mention of itself.
    """
    if _host_matches(host, company_host):
        return 1, "the company's own host"
    for entry in sorted(sources.get("tiers") or [], key=lambda e: e["tier"]):
        for listed in entry["hosts"]:
            if _host_matches(host, listed):
                return entry["tier"], entry["label"]
    return None, None


def rank_results(results, company_url, sources=None, already_searched=0):
    """Rank the model's transcribed search results against the committed allowlist.

    Returns `{"accepted", "rejected", "cap", "budget_remaining"}`, mirroring
    `url_fallback.filter_candidates`'s shape. `accepted` entries are `{"url", "tier",
    "why"}`, ordered by tier lowest-first; `rejected` entries are `{"url", "reason"}`.

    Checks run in this order -- shape, then scheme, then tier, then budget -- so an
    unlisted host is rejected FOR BEING UNLISTED rather than for exhausting a budget it
    was never entitled to spend in the first place.

    TITLE AND SNIPPET ARE NEVER READ. The accept/reject decision is made on the URL host
    alone. That is not an oversight, it is the mitigation: the scratch file is a model
    TRANSCRIPTION and its fidelity cannot be verified offline, so no search snippet is
    ever allowed to become a row field. A person comes from a real `web_fetch` of an
    accepted URL; a fabricated URL simply fails to fetch or yields nobody.
    """
    if sources is None:
        sources = load_sources()

    company_host = url_fallback._canonical_authority(company_url) if company_url else ""
    budget_remaining = max(MAX_FALLBACK_SEARCHES - already_searched, 0)

    accepted = []
    rejected = []
    for result in results or []:
        url = result.get("url") if isinstance(result, dict) else None
        if not isinstance(url, str) or not url.strip():
            rejected.append({
                "url": None,
                "reason": (
                    f"{result!r} is not a search result carrying a 'url' -- refusing to "
                    f"guess at what was meant."
                ),
            })
            continue

        scheme = urlsplit(url).scheme
        if scheme not in ("http", "https"):
            rejected.append({
                "url": url,
                "reason": f"{scheme or '(no scheme)'!r} is not an http or https URL — refusing to fetch it.",
            })
            continue

        host = url_fallback._canonical_authority(url)
        tier, label = _tier_of(host, company_host, sources)
        if tier is None:
            rejected.append({
                "url": url,
                "reason": (
                    f"{host} is on no tier of the committed source allowlist — an "
                    f"unlisted source is rejected outright, never ranked last "
                    f"(D-5sd-02)."
                ),
            })
            continue

        if len(accepted) >= budget_remaining:
            rejected.append({
                "url": url,
                "reason": (
                    f"the search fallback cap (MAX_FALLBACK_SEARCHES = "
                    f"{MAX_FALLBACK_SEARCHES}) is exhausted "
                    f"({already_searched} already spent for this company)."
                ),
            })
            continue

        accepted.append({
            "url": url,
            "tier": tier,
            "why": (
                f"{host} is {label}."
                if tier == 1
                else f"{host} is on the committed source allowlist as {label} (tier {tier})."
            ),
        })

    accepted.sort(key=lambda entry: entry["tier"])
    return {
        "accepted": accepted,
        "rejected": rejected,
        "cap": MAX_FALLBACK_SEARCHES,
        "budget_remaining": budget_remaining,
    }


def hold_weak_sources(records, sendable, held):
    """`(sendable, held)` -- the D-5sd-01/D-5sd-05 source-tier gate, applied AFTER
    `suggest_contacts.partition_for_dispatch` has already had its say.

    This is a SECOND, RECORDS-level pass and it leaves `partition_for_dispatch` untouched:
    D-5sd-01 forbids weakening that function's required `company_domains` argument or its
    suffix-trap refusal, and an optional keyword there would be a one-keyword bypass of
    the operator's ruling. The two gates are INDEPENDENT and BOTH must hold -- a tier-3
    person stays held however confidently the waterfall validated them, and a tier-2
    person with no related email is still held by the pass before this one.

    Nothing here is written into a match verdict, so `match.tier` stays what
    `n8n/code/matchProposal.js::summarizeMatch` produces and
    `confidence.ALL_HOLD_CODES` is not widened. The source tier is a plugin-side,
    records-level concept and stays one.

    Joined on `row_id`, never on position: rows are dicts (unhashable) and `row_id` is the
    join key the whole round already uses. A held entry carries the record's ORIGINAL
    index and the merged `held` is re-sorted by it, so the two passes read as one list in
    the uniform `{"index", "row", "reason", "reason_code"}` shape.

    A record that does not declare itself search-sourced is PASSED THROUGH UNTOUCHED.
    That is why a mis-stamped record fails OPEN rather than holding the whole existing
    round -- a limit of the same transcription class as the disposition, stated here
    rather than hidden. Failing the other way would hold every ladder row in every round.
    """
    sendable_ids = {row.get("row_id") for row in sendable}
    merged_held = list(held)
    weak_ids = set()

    for index, record in enumerate(records):
        provenance = record.get("provenance") or {}
        if provenance.get("input") != SEARCH_INPUT:
            continue

        row = record.get("row") or {}
        row_id = row.get("row_id")
        if row_id is None:
            raise ValueError(
                f"the search-sourced record at index {index} carries no 'row_id', so this "
                f"gate has nothing to join it to -- `mint_row_ids` runs once at the batch "
                f"level, before stage 2, and every record must have been through it. "
                f"Refusing rather than silently matching nothing and reporting the row "
                f"as sent."
            )

        tier = provenance.get("source_tier")
        if not isinstance(tier, bool) and isinstance(tier, int) and tier in STRONG_TIERS:
            continue

        if row_id not in sendable_ids:
            continue  # already held by the pass before this one; its entry stands

        weak_ids.add(row_id)
        locator = provenance.get("locator")
        if not isinstance(tier, bool) and isinstance(tier, int) and tier in KNOWN_TIERS:
            reason = (
                f"named by {locator} — a third-party source (tier {tier}), not this "
                f"company's own site or LinkedIn, so this person is held for you to "
                f"judge rather than sent. An industry site can name someone "
                f"historically: the person can be real and the enrichment confirmation "
                f"genuine, and the role still stale (D-5sd-05)."
            )
        else:
            reason = (
                f"this record declares itself search-sourced (locator {locator}) but "
                f"carries no readable source tier ({tier!r}) — held rather than sent, "
                f"fail-closed."
            )
        merged_held.append({
            "index": index,
            "row": row,
            "reason": reason,
            "reason_code": SOURCE_TIER_HOLD_CODE,
        })

    kept = [row for row in sendable if row.get("row_id") not in weak_ids]
    merged_held.sort(key=lambda entry: entry["index"])
    return kept, merged_held


if __name__ == "__main__":
    import pathlib

    _args = sys.argv[1:]
    try:
        if not _args:
            raise ValueError(
                "usage: search_fallback.py --eligible <attempts.json> | "
                "search_fallback.py --rank <results.json> --company-url <url> "
                "[--already-searched N]"
            )

        # A `for enumerate` scan, not a `while` loop — required by this suite's own guard
        # (tests/test_report_sufficiency.py D-07): no plugin script may contain a `while`
        # loop, full stop, so that the one bounded watch loop in watch.py stays the only
        # one in the plugin. A four-flag argv scan has no need for one anyway.
        _eligible_path = None
        _rank_path = None
        _company_url = None
        _already_searched = 0
        for _i, _a in enumerate(_args):
            if _a == "--eligible" and _i + 1 < len(_args):
                _eligible_path = _args[_i + 1]
            elif _a == "--rank" and _i + 1 < len(_args):
                _rank_path = _args[_i + 1]
            elif _a == "--company-url" and _i + 1 < len(_args):
                _company_url = _args[_i + 1]
            elif _a == "--already-searched" and _i + 1 < len(_args):
                _already_searched = int(_args[_i + 1])

        if _eligible_path:
            _attempts = json.loads(pathlib.Path(_eligible_path).read_text(encoding="utf-8"))
            print(json.dumps({"ok": True, **eligible_after_ladder(_attempts)}))
        elif _rank_path:
            if not _company_url:
                raise ValueError("--rank needs --company-url (tier 1 is computed from it)")
            _results = json.loads(pathlib.Path(_rank_path).read_text(encoding="utf-8"))
            print(json.dumps({
                "ok": True,
                **rank_results(_results, _company_url, already_searched=_already_searched),
            }))
        else:
            raise ValueError("nothing to do: pass --eligible or --rank")
    except Exception as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)
