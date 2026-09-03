"""Tests for search_fallback.py — the web-search fallback's three pure decisions
(quick task 260904-5sd).

The properties under test are the three the operator locked, and each is a REFUSAL
property rather than a capability one:

  1. `eligible_after_ladder` — a refusal anywhere in the ladder's own record closes the
     search path, and an unreadable record closes it too (D-5sd-04, D-5sd-06). The
     predicate is fail-closed: only an affirmative `empty`/`cap_exhausted` opens it.
  2. `rank_results` — only the company's own host, LinkedIn, and the committed tier-3
     allowlist survive; everything else is REJECTED rather than ranked last (D-5sd-02),
     and the host match is label-boundary in both directions so
     `linkedin.com.attacker.tld` cannot pass as LinkedIn.
  3. `hold_weak_sources` — a tier-3 person is always held, however confidently the
     waterfall validated them (D-5sd-05), and a record that does not declare itself
     search-sourced is untouched.

`search_fallback.py` holds no HTTP client — the search and every fetch are model-invoked
tools it cannot call — so the autouse `no_network` guard in conftest.py is satisfied by
construction, not by a stub. Its ONE filesystem read outside the `__main__` guard is the
shipped allowlist, which is why the AST guard below is scoped to permit `open()` inside
`load_sources` as well as the CLI entrypoint.
"""
import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import search_fallback
from search_fallback import (
    MAX_FALLBACK_SEARCHES,
    SEARCH_INPUT,
    SOURCE_TIER_HOLD_CODE,
    SourceAllowlistError,
    eligible_after_ladder,
    hold_weak_sources,
    load_sources,
    rank_results,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
CONFIG_DIR = PLUGIN_ROOT / "config"
SEARCH_FALLBACK_PATH = SCRIPTS_DIR / "search_fallback.py"
SHIPPED_ALLOWLIST = CONFIG_DIR / "source_allowlist.yaml"

COMPANY_URL = "https://example-club.example/board"

# A synthetic allowlist for the ranker's unit tests, so a curation edit to the shipped
# file cannot turn a ranking assertion red. The shipped file gets its own contract test
# further down.
FIXTURE_SOURCES = {
    "version": "test-allowlist",
    "tiers": [
        {"tier": 2, "label": "LinkedIn", "hosts": ["linkedin.com"]},
        {
            "tier": 3,
            "label": "Racing/sport industry bodies and industry media",
            "hosts": ["racingvictoria.example", "racenet.example"],
        },
    ],
}


def _run_search_cli(tmp_path, *args):
    """Build an ISOLATED plugin root and run search_fallback.py against it as a real
    subprocess — the layer the operator reaches, never the in-process function.

    The one real difference from `test_url_fallback.py::_run_url_cli`, which copies
    `scripts/` only: this module SHIPS a config file, so the isolated root must carry
    `config/source_allowlist.yaml` too, or `load_sources` refuses inside the subprocess
    for a reason that has nothing to do with the property under test.
    """
    root = tmp_path / "plugin"
    shutil.copytree(SCRIPTS_DIR, root / "scripts")
    (root / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SHIPPED_ALLOWLIST, root / "config" / "source_allowlist.yaml")

    argv = [sys.executable, str(root / "scripts" / "search_fallback.py"), *args]
    proc = subprocess.run(argv, capture_output=True, text=True)
    parsed = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc.returncode, parsed


def _attempt(url, disposition=None, outcome="nothing usable on the page"):
    entry = {"url": url, "outcome": outcome}
    if disposition is not None:
        entry["disposition"] = disposition
    return entry


# --- eligible_after_ladder: the D-5sd-04 / D-5sd-06 branch --------------------------------


def test_a_single_empty_attempt_is_eligible():
    """The crawl COMPLETED and found nobody. Absence of information is not a fence."""
    verdict = eligible_after_ladder([_attempt("https://a.example/x", "empty")])
    assert verdict["eligible"] is True


def test_a_single_cap_exhausted_attempt_is_eligible():
    """D-5sd-06's third ending: a budget WE imposed on ourselves is not a fence the site
    put up. Nobody refused us; we stopped looking."""
    verdict = eligible_after_ladder([_attempt("https://a.example/x", "cap_exhausted")])
    assert verdict["eligible"] is True


def test_empty_rungs_ending_in_cap_exhaustion_are_eligible():
    attempts = [
        _attempt("https://a.example/1", "empty"),
        _attempt("https://a.example/2", "empty"),
        _attempt("https://a.example/3", "cap_exhausted"),
    ]
    assert eligible_after_ladder(attempts)["eligible"] is True


def test_a_refusal_after_an_empty_rung_closes_the_search_path_naming_the_url():
    """THE D-5sd-04 test: a simulated 403/robots-disallow does not reach the search path.
    One fence anywhere in the ladder is a fence."""
    attempts = [
        _attempt("https://a.example/ok", "empty"),
        _attempt("https://a.example/sitemap.xml", "refused"),
    ]
    verdict = eligible_after_ladder(attempts)
    assert verdict["eligible"] is False
    assert "https://a.example/sitemap.xml" in verdict["reason"]


def test_a_refusal_before_an_empty_rung_closes_the_search_path_too():
    """Order-free: the refusal is checked wherever it sits, first position or last."""
    attempts = [
        _attempt("https://a.example/sitemap.xml", "refused"),
        _attempt("https://a.example/ok", "empty"),
    ]
    verdict = eligible_after_ladder(attempts)
    assert verdict["eligible"] is False
    assert "https://a.example/sitemap.xml" in verdict["reason"]


def test_an_unknown_disposition_value_is_ineligible():
    """Fail-closed on a value outside the closed vocabulary — never read as `empty`."""
    verdict = eligible_after_ladder([_attempt("https://a.example/x", "wat")])
    assert verdict["eligible"] is False
    assert "wat" in verdict["reason"]


def test_an_attempt_with_no_disposition_key_is_ineligible_and_does_not_raise():
    """D-5sd-06 overrides RESEARCH.md §1b here: a transcription gap makes the ladder
    INELIGIBLE, never an exception. Raising would surface a missing key as a crash in the
    middle of a round; the fail-closed reading simply declines to open the search path."""
    verdict = eligible_after_ladder([_attempt("https://a.example/x")])
    assert verdict["eligible"] is False
    assert "https://a.example/x" in verdict["reason"]


def test_an_empty_attempt_list_is_ineligible_because_nothing_establishes_the_crawl_ran():
    verdict = eligible_after_ladder([])
    assert verdict["eligible"] is False
    assert "attempt was recorded" in verdict["reason"].lower()


def test_none_attempts_is_ineligible():
    verdict = eligible_after_ladder(None)
    assert verdict["eligible"] is False
    assert "attempt was recorded" in verdict["reason"].lower()


def test_a_non_list_attempts_value_is_ineligible():
    verdict = eligible_after_ladder({"url": "https://a.example/x", "disposition": "empty"})
    assert verdict["eligible"] is False


def test_an_attempt_entry_that_is_not_a_dict_is_ineligible():
    verdict = eligible_after_ladder(["https://a.example/x"])
    assert verdict["eligible"] is False


# --- rank_results: the D-5sd-02 tier ranking ----------------------------------------------


def _rank(urls, company_url=COMPANY_URL, already_searched=0):
    results = [{"url": u, "title": "ignored", "snippet": "ignored"} for u in urls]
    return rank_results(
        results, company_url, sources=FIXTURE_SOURCES, already_searched=already_searched
    )


def _tier_of(outcome, url):
    for entry in outcome["accepted"]:
        if entry["url"] == url:
            return entry["tier"]
    return None


def test_the_companys_own_host_is_tier_one():
    outcome = _rank(["https://example-club.example/about/our-people"])
    assert _tier_of(outcome, "https://example-club.example/about/our-people") == 1


def test_apex_and_www_are_the_same_host_in_both_directions():
    """Mirrors G-62-2's apex/`www` ruling on the fetch side: the ranker reuses
    `url_fallback._canonical_authority` rather than re-deriving canonicalisation."""
    from_apex = rank_results(
        [{"url": "https://www.example-club.example/people"}],
        "https://example-club.example/board",
        sources=FIXTURE_SOURCES,
    )
    assert _tier_of(from_apex, "https://www.example-club.example/people") == 1

    from_www = rank_results(
        [{"url": "https://example-club.example/people"}],
        "https://www.example-club.example/board",
        sources=FIXTURE_SOURCES,
    )
    assert _tier_of(from_www, "https://example-club.example/people") == 1


def test_a_real_subdomain_of_the_companys_host_is_tier_one():
    """Deliberately NOT `url_fallback.same_host`, which refuses subdomains: that is a
    FETCH guard on attacker-influenceable sitemap content. This is a SOURCE-ranking
    question — whose claim to trust — and a company's own subdomain is the company."""
    outcome = _rank(["https://board.example-club.example/committee"])
    assert _tier_of(outcome, "https://board.example-club.example/committee") == 1


def test_linkedin_and_its_subdomains_are_tier_two():
    urls = [
        "https://linkedin.com/in/someone",
        "https://www.linkedin.com/in/someone-else",
        "https://au.linkedin.com/in/a-third",
    ]
    outcome = _rank(urls)
    assert [_tier_of(outcome, u) for u in urls] == [2, 2, 2]


def test_a_linkedin_suffix_trap_host_is_rejected():
    """`linkedin.com.attacker.tld` does not END WITH `.linkedin.com` — the label-boundary
    rule, never a bare substring or `endswith(listed)` test."""
    outcome = _rank(["https://linkedin.com.attacker.tld/in/someone"])
    assert outcome["accepted"] == []
    assert "linkedin.com.attacker.tld" in outcome["rejected"][0]["reason"]


def test_a_company_host_suffix_trap_is_rejected_too():
    """The same trap in the other direction: a host that merely starts with the company's
    own domain is a different registrant entirely."""
    outcome = _rank(["https://example-club.example.attacker.tld/people"])
    assert outcome["accepted"] == []
    assert "example-club.example.attacker.tld" in outcome["rejected"][0]["reason"]


def test_a_listed_tier_three_host_and_a_real_subdomain_of_one_are_tier_three():
    urls = [
        "https://racingvictoria.example/about/board",
        "https://news.racenet.example/appointments",
    ]
    outcome = _rank(urls)
    assert [_tier_of(outcome, u) for u in urls] == [3, 3]


def test_a_host_on_no_tier_is_rejected_with_a_reason_naming_it():
    """D-5sd-02's tier 4 is REJECTION, not last place. An unknown domain contributes
    nothing at all — this is a positive assertion, not an omission."""
    outcome = _rank(["https://random-blog.example/who-works-where"])
    assert outcome["accepted"] == []
    assert len(outcome["rejected"]) == 1
    assert "random-blog.example" in outcome["rejected"][0]["reason"]


def test_a_non_http_scheme_is_rejected_with_its_own_reason():
    outcome = _rank(["ftp://example-club.example/people"])
    assert outcome["accepted"] == []
    assert "ftp" in outcome["rejected"][0]["reason"]


def test_a_result_that_is_not_a_dict_carrying_a_url_is_rejected_never_guessed_at():
    outcome = rank_results(
        ["https://example-club.example/people", {"title": "no url here"}, None],
        COMPANY_URL,
        sources=FIXTURE_SOURCES,
    )
    assert outcome["accepted"] == []
    assert len(outcome["rejected"]) == 3


def test_accepted_entries_carry_url_tier_and_why_ordered_by_tier_lowest_first():
    outcome = _rank([
        "https://racingvictoria.example/about/board",
        "https://linkedin.com/in/someone",
        "https://example-club.example/people",
    ])
    assert [entry["tier"] for entry in outcome["accepted"]] == [1, 2, 3]
    for entry in outcome["accepted"]:
        assert set(entry) == {"url", "tier", "why"}
        assert entry["why"]


def test_a_company_host_that_is_also_on_the_tier_three_list_still_ranks_tier_one():
    """Racing Victoria searching for Racing Victoria's own people: the company's own host
    is checked BEFORE the allowlist, so its own site is never demoted to a third-party
    mention of itself."""
    outcome = rank_results(
        [{"url": "https://racingvictoria.example/about/board"}],
        "https://racingvictoria.example/",
        sources=FIXTURE_SOURCES,
    )
    assert outcome["accepted"][0]["tier"] == 1


def test_the_search_cap_refuses_the_remainder_naming_the_constant():
    urls = [f"https://example-club.example/person-{i}" for i in range(MAX_FALLBACK_SEARCHES + 2)]
    outcome = _rank(urls)
    assert len(outcome["accepted"]) == MAX_FALLBACK_SEARCHES
    assert outcome["cap"] == MAX_FALLBACK_SEARCHES
    assert len(outcome["rejected"]) == 2
    assert str(MAX_FALLBACK_SEARCHES) in outcome["rejected"][0]["reason"]


def test_already_searched_shrinks_the_budget():
    urls = [f"https://example-club.example/person-{i}" for i in range(MAX_FALLBACK_SEARCHES)]
    outcome = _rank(urls, already_searched=MAX_FALLBACK_SEARCHES - 1)
    assert outcome["budget_remaining"] == 1
    assert len(outcome["accepted"]) == 1


def test_an_unlisted_host_is_rejected_for_being_unlisted_not_for_a_budget_it_never_had():
    """Check ORDER, mirroring `filter_candidates`: shape, then scheme, then tier, then
    budget. An unlisted host must never be reported as a cap casualty."""
    outcome = _rank(["https://random-blog.example/x"], already_searched=MAX_FALLBACK_SEARCHES)
    assert "random-blog.example" in outcome["rejected"][0]["reason"]
    assert str(MAX_FALLBACK_SEARCHES) not in outcome["rejected"][0]["reason"]


# --- load_sources: the shipped config contract --------------------------------------------


def test_the_shipped_allowlist_parses_through_load_sources():
    sources = load_sources()
    assert sources["tiers"]
    tiers = {entry["tier"] for entry in sources["tiers"]}
    assert tiers == {2, 3}


def test_the_shipped_allowlist_ships_inside_the_plugin_package():
    assert SHIPPED_ALLOWLIST.exists(), (
        f"{SHIPPED_ALLOWLIST} must ship with the plugin — without it every search "
        "fallback refuses at load_sources()"
    )


def test_every_shipped_host_is_a_bare_lowercase_dotted_host_appearing_in_one_tier_only():
    sources = load_sources()
    seen = {}
    for entry in sources["tiers"]:
        for host in entry["hosts"]:
            assert host == host.lower(), f"{host!r} is not lowercase"
            assert "." in host, f"{host!r} has no dot"
            assert "/" not in host and ":" not in host, f"{host!r} is not a bare host"
            assert host not in seen, f"{host!r} appears in tiers {seen[host]} and {entry['tier']}"
            seen[host] = entry["tier"]


def test_linkedin_is_the_whole_of_tier_two():
    sources = load_sources()
    [tier_two] = [entry for entry in sources["tiers"] if entry["tier"] == 2]
    assert tier_two["hosts"] == ["linkedin.com"]


def test_a_missing_allowlist_raises_a_named_error_rather_than_an_empty_list(tmp_path):
    """`RoleVocabularyError`'s register: a missing shipped config is an incomplete
    install, never a silent empty list — which would read as "no source qualified"."""
    missing = tmp_path / "not-there.yaml"
    with pytest.raises(SourceAllowlistError) as excinfo:
        load_sources(missing)
    assert str(missing) in str(excinfo.value)


def test_an_unparseable_allowlist_raises_a_named_error(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("tiers: [\n  - tier: 2\n", encoding="utf-8")
    with pytest.raises(SourceAllowlistError) as excinfo:
        load_sources(path)
    assert str(path) in str(excinfo.value)


def test_a_host_listed_in_two_tiers_is_refused(tmp_path):
    path = tmp_path / "dupe.yaml"
    path.write_text(
        "version: x\n"
        "tiers:\n"
        "  - tier: 2\n    label: LinkedIn\n    hosts: [linkedin.com]\n"
        "  - tier: 3\n    label: Media\n    hosts: [linkedin.com]\n",
        encoding="utf-8",
    )
    with pytest.raises(SourceAllowlistError) as excinfo:
        load_sources(path)
    assert "linkedin.com" in str(excinfo.value)


def test_a_tier_outside_two_and_three_is_refused(tmp_path):
    """Tier 1 is COMPUTED from the company's own host and is never listed; tier 4 is the
    ABSENCE of a match. A file that lists either is describing something this ranker does
    not implement."""
    path = tmp_path / "tier1.yaml"
    path.write_text(
        "version: x\ntiers:\n  - tier: 1\n    label: Own host\n    hosts: [example.com]\n",
        encoding="utf-8",
    )
    with pytest.raises(SourceAllowlistError):
        load_sources(path)


def test_a_host_carrying_a_scheme_is_refused(tmp_path):
    path = tmp_path / "scheme.yaml"
    path.write_text(
        "version: x\ntiers:\n  - tier: 2\n    label: LinkedIn\n"
        "    hosts: ['https://linkedin.com']\n",
        encoding="utf-8",
    )
    with pytest.raises(SourceAllowlistError):
        load_sources(path)


# --- hold_weak_sources: the D-5sd-01 + D-5sd-05 gate --------------------------------------


def _record(row_id, provenance):
    return {
        "record_type": "contacts",
        "row": {
            "row_id": row_id,
            "firstname": "Jamie",
            "lastname": "Fox",
            "company": "Example Club",
            "email": f"{row_id}@example-club.example",
        },
        "provenance": provenance,
    }


def _ladder_record(row_id):
    return _record(row_id, {"input": "suggest_contacts_ladder", "locator": COMPANY_URL})


def _search_record(row_id, tier, locator="https://racingvictoria.example/about/board"):
    provenance = {"input": SEARCH_INPUT, "locator": locator}
    if tier is not None:
        provenance["source_tier"] = tier
    return _record(row_id, provenance)


def test_a_ladder_sourced_record_is_passed_through_untouched():
    """Truth: a ladder-sourced record's send-vs-hold behaviour is byte-identical to
    today. The new gate is a no-op for any record that does not declare itself
    search-sourced."""
    records = [_ladder_record("row-1")]
    sendable = [records[0]["row"]]
    sendable_out, held_out = hold_weak_sources(records, sendable, [])
    assert sendable_out == sendable
    assert held_out == []


def test_a_tier_one_or_tier_two_search_record_stays_sendable():
    records = [_search_record("row-1", 1), _search_record("row-2", 2)]
    sendable = [record["row"] for record in records]
    sendable_out, held_out = hold_weak_sources(records, sendable, [])
    assert [row["row_id"] for row in sendable_out] == ["row-1", "row-2"]
    assert held_out == []


def test_a_tier_three_search_record_is_held_with_its_source_url_in_the_reason():
    """D-5sd-05: an industry site can name a person historically — a 2019 committee list,
    an archived media release. The person can be real and the waterfall's confirmation
    genuine, and the claim can still be stale. The operator judges it, with the URL in
    hand."""
    locator = "https://racenet.example/2019/committee"
    records = [_search_record("row-1", 3, locator=locator)]
    sendable = [records[0]["row"]]
    sendable_out, held_out = hold_weak_sources(records, sendable, [])
    assert sendable_out == []
    assert len(held_out) == 1
    assert held_out[0]["reason_code"] == SOURCE_TIER_HOLD_CODE
    assert locator in held_out[0]["reason"]
    assert held_out[0]["index"] == 0
    assert held_out[0]["row"]["row_id"] == "row-1"


def test_a_search_record_with_an_unreadable_tier_is_held_fail_closed():
    for tier in (None, "2", True, 9):
        records = [_search_record("row-1", tier)]
        sendable = [records[0]["row"]]
        sendable_out, held_out = hold_weak_sources(records, sendable, [])
        assert sendable_out == [], f"tier {tier!r} must not promote"
        assert held_out[0]["reason_code"] == SOURCE_TIER_HOLD_CODE


def test_a_row_already_held_stays_held_and_held_stays_sorted_by_index():
    """The two passes read as one list: a new hold carries the record's ORIGINAL index,
    and the merged list is re-sorted so it never reads as two appended halves."""
    records = [
        _search_record("row-1", 3),
        _ladder_record("row-2"),
        _search_record("row-3", 3),
    ]
    already_held = [
        {
            "index": 1,
            "row": records[1]["row"],
            "reason": "no usable email",
            "reason_code": "no_email",
        }
    ]
    sendable = [records[0]["row"], records[2]["row"]]
    sendable_out, held_out = hold_weak_sources(records, sendable, already_held)
    assert sendable_out == []
    assert [entry["index"] for entry in held_out] == [0, 1, 2]
    assert [entry["reason_code"] for entry in held_out] == [
        SOURCE_TIER_HOLD_CODE, "no_email", SOURCE_TIER_HOLD_CODE
    ]


def test_a_weak_record_that_was_already_held_is_not_held_twice():
    records = [_search_record("row-1", 3)]
    already_held = [
        {"index": 0, "row": records[0]["row"], "reason": "no usable email",
         "reason_code": "no_email"}
    ]
    sendable_out, held_out = hold_weak_sources(records, [], already_held)
    assert sendable_out == []
    assert len(held_out) == 1
    assert held_out[0]["reason_code"] == "no_email"


def test_a_search_sourced_record_with_no_row_id_refuses_rather_than_joining_nothing():
    """`rejoin_enriched`'s register: the join key is `row_id`, minted once at the batch
    level. A search-sourced record that reaches this gate unminted would silently match
    nothing in `sendable` and be reported as sent."""
    record = _search_record("row-1", 3)
    del record["row"]["row_id"]
    with pytest.raises(ValueError):
        hold_weak_sources([record], [], [])


# --- the CLI layer ------------------------------------------------------------------------


def test_the_cli_reports_an_eligible_ladder(tmp_path):
    attempts_path = tmp_path / "attempts.json"
    attempts_path.write_text(
        json.dumps([_attempt("https://a.example/x", "empty")]), encoding="utf-8"
    )
    returncode, parsed = _run_search_cli(tmp_path, "--eligible", str(attempts_path))
    assert returncode == 0
    assert parsed["ok"] is True
    assert parsed["eligible"] is True


def test_the_cli_reports_a_refused_ladder_as_ineligible(tmp_path):
    attempts_path = tmp_path / "attempts.json"
    attempts_path.write_text(
        json.dumps([_attempt("https://a.example/sitemap.xml", "refused")]), encoding="utf-8"
    )
    returncode, parsed = _run_search_cli(tmp_path, "--eligible", str(attempts_path))
    assert returncode == 0
    assert parsed["ok"] is True
    assert parsed["eligible"] is False
    assert "https://a.example/sitemap.xml" in parsed["reason"]


def test_the_cli_ranks_results_against_the_shipped_allowlist(tmp_path):
    results_path = tmp_path / "results.json"
    results_path.write_text(
        json.dumps([
            {"url": "https://www.linkedin.com/in/someone"},
            {"url": "https://example-club.example/people"},
            {"url": "https://random-blog.example/who"},
        ]),
        encoding="utf-8",
    )
    returncode, parsed = _run_search_cli(
        tmp_path, "--rank", str(results_path), "--company-url", COMPANY_URL
    )
    assert returncode == 0
    assert parsed["ok"] is True
    assert [entry["tier"] for entry in parsed["accepted"]] == [1, 2]
    assert len(parsed["rejected"]) == 1
    assert "random-blog.example" in parsed["rejected"][0]["reason"]


def test_the_cli_threads_already_searched(tmp_path):
    results_path = tmp_path / "results.json"
    results_path.write_text(
        json.dumps([{"url": f"https://example-club.example/p{i}"} for i in range(3)]),
        encoding="utf-8",
    )
    returncode, parsed = _run_search_cli(
        tmp_path, "--rank", str(results_path), "--company-url", COMPANY_URL,
        "--already-searched", str(MAX_FALLBACK_SEARCHES - 1),
    )
    assert returncode == 0
    assert parsed["budget_remaining"] == 1
    assert len(parsed["accepted"]) == 1


def test_the_cli_reports_a_failure_the_same_way_as_any_other(tmp_path):
    returncode, parsed = _run_search_cli(tmp_path)
    assert returncode == 1
    assert parsed["ok"] is False
    assert parsed["error"]


def test_the_cli_agrees_with_the_in_process_function(tmp_path):
    """The operator-facing layer cannot silently drift from the function under test."""
    attempts = [_attempt("https://a.example/x", "cap_exhausted")]
    attempts_path = tmp_path / "attempts.json"
    attempts_path.write_text(json.dumps(attempts), encoding="utf-8")
    _returncode, parsed = _run_search_cli(tmp_path, "--eligible", str(attempts_path))
    in_process = eligible_after_ladder(attempts)
    assert parsed["eligible"] == in_process["eligible"]
    assert parsed["reason"] == in_process["reason"]


# --- AST purity guards --------------------------------------------------------------------
#
# Structurally copied from test_url_fallback.py:330-414, SCOPED for this module. The
# difference is deliberate and stated: url_fallback.py can claim "no I/O of any kind";
# search_fallback.py cannot, because it loads a shipped config. So `yaml` joins the root
# allowlist, and `open()` is permitted in `load_sources` as well as the `__main__` guard.
# Neither of those two reads is a fetch: one is a file that shipped inside the plugin, the
# other is a local JSON the model itself already wrote to scratch.

ALLOWED_ROOT_IMPORTS = {"json", "sys", "pathlib", "urllib", "yaml", "url_fallback"}

FORBIDDEN_DOTTED_IMPORTS = {
    "requests", "httpx", "selenium", "playwright", "puppeteer", "bs4",
    "subprocess", "socket", "http.client", "urllib.request",
}


def _import_names(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots, dotted = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
                dotted.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
            dotted.add(node.module)
    return roots, dotted


def _permitted_open_scopes(tree):
    """Every AST node inside either (a) the `__main__` guard or (b) `load_sources` — the
    only two places this module may touch the filesystem, and each for a stated reason:
    the CLI reads a local JSON the model itself already wrote to scratch, and
    `load_sources` reads the config file that ships inside the plugin. Neither is a
    fetch."""
    permitted = set()
    for node in ast.walk(tree):
        is_main_guard = (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        )
        is_loader = isinstance(node, ast.FunctionDef) and node.name == "load_sources"
        if is_main_guard or is_loader:
            for inner in ast.walk(node):
                permitted.add(inner)
    return permitted


def test_search_fallback_import_set_is_a_subset_of_the_allowlist():
    roots, _dotted = _import_names(SEARCH_FALLBACK_PATH)
    assert roots <= ALLOWED_ROOT_IMPORTS, (
        f"search_fallback.py imports {sorted(roots - ALLOWED_ROOT_IMPORTS)}, outside its "
        f"allowlist {sorted(ALLOWED_ROOT_IMPORTS)} — before widening this allowlist, "
        f"confirm the new import performs no network I/O. This module ranks off-host "
        f"URLs; it must never be the thing that fetches one."
    )


def test_search_fallback_never_imports_a_named_forbidden_capability():
    _roots, dotted = _import_names(SEARCH_FALLBACK_PATH)
    offending = dotted & FORBIDDEN_DOTTED_IMPORTS
    assert not offending, (
        f"search_fallback.py imports {sorted(offending)} — each of these would let this "
        f"module fetch, scrape, drive a browser, or shell out"
    )


def test_search_fallback_calls_open_only_where_a_read_is_legitimate():
    tree = ast.parse(SEARCH_FALLBACK_PATH.read_text(encoding="utf-8"))
    permitted = _permitted_open_scopes(tree)
    offenders = [
        node
        for node in ast.walk(tree)
        if node not in permitted
        and isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "open"
    ]
    assert not offenders, (
        "search_fallback.py calls open() outside load_sources and the __main__ guard — "
        "those two reads (a shipped config; a local JSON the model itself wrote) are the "
        "only filesystem touches this module is allowed"
    )


def test_search_fallback_contains_no_while_loop():
    """`tests/test_report_sufficiency.py`'s D-07 guard scans every plugin script,
    including this new one. Pinned here too so the failure names this module."""
    tree = ast.parse(SEARCH_FALLBACK_PATH.read_text(encoding="utf-8"))
    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))


def test_the_cap_is_not_named_after_the_backends_unrelated_axis():
    """`suggest_contacts.py:25-29` reserves `WEB_RESEARCH_MAX_SEARCHES` for the backend's
    own company-ICP research budget. Two different axes must not share a name."""
    assert not hasattr(search_fallback, "WEB_RESEARCH_MAX_SEARCHES")
    assert isinstance(MAX_FALLBACK_SEARCHES, int) and MAX_FALLBACK_SEARCHES > 0
