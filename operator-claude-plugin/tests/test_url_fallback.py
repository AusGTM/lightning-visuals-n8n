"""Tests for url_fallback.py — the deterministic candidate-URL ladder (Phase 35).

The property under test is NOT "the ladder is clever". It is: the first URL the operator
is offered for the measured acceptance case is the one measured live to return the roster
(35-CONTEXT.md §2), and the operator-facing CLI layer prints exactly what the in-process
function returns — the two cannot silently drift apart. `url_fallback.py` performs no I/O
of any kind (it builds strings; `web_fetch` is a model-invoked server tool this module
cannot and does not call), so the autouse `no_network` guard in conftest.py is satisfied
by construction, not by a stub.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from url_fallback import (
    MAX_FOLLOWUP_FETCHES,
    filter_candidates,
    plan_ladder,
    same_host,
    slug_of,
)

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

ACCEPTANCE_URL = "https://gctc.com.au/board-of-directors/"
ACCEPTANCE_FIRST_CANDIDATE = "https://gctc.com.au/wp-json/wp/v2/pages?slug=board-of-directors"


def _run_url_cli(tmp_path, *args):
    """Build an ISOLATED plugin root (`scripts/` only — never `config/`, never
    `~/.claude/plugins/`, per non-negotiable 5) and run url_fallback.py against it as a
    real subprocess — the layer the operator reaches, never the in-process function, for
    any property about what the operator is actually shown."""
    root = tmp_path / "plugin"
    shutil.copytree(SCRIPTS_DIR, root / "scripts")

    argv = [sys.executable, str(root / "scripts" / "url_fallback.py"), *args]
    proc = subprocess.run(argv, capture_output=True, text=True)
    parsed = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc.returncode, parsed


# --- slug_of -----------------------------------------------------------------------------


def test_slug_of_extracts_the_last_path_segment():
    assert slug_of(ACCEPTANCE_URL) == "board-of-directors"


def test_slug_of_returns_none_when_the_path_has_no_segment():
    assert slug_of("https://gctc.com.au/") is None


# --- plan_ladder rung 1 (the acceptance case) ---------------------------------------------


def test_first_candidate_is_the_url_measured_live_to_return_9_directors():
    result = plan_ladder(ACCEPTANCE_URL)
    assert result["candidates"][0]["url"] == ACCEPTANCE_FIRST_CANDIDATE


def test_cap_is_the_named_constant():
    assert plan_ladder(ACCEPTANCE_URL)["cap"] == MAX_FOLLOWUP_FETCHES


def test_no_slug_emits_no_wp_json_candidate_and_says_why():
    result = plan_ladder("https://gctc.com.au/")
    urls = [c["url"] for c in result["candidates"]]
    assert "https://gctc.com.au/wp-json/wp/v2/pages?slug=" not in "".join(urls)
    assert any("slug" in note.lower() for note in result["notes"])


# --- plan_ladder: the full locked order (35-CONTEXT.md §3) ------------------------------


def test_full_ladder_order_for_the_acceptance_case():
    result = plan_ladder(ACCEPTANCE_URL)
    urls = [c["url"] for c in result["candidates"]]
    assert urls == [
        "https://gctc.com.au/wp-json/wp/v2/pages?slug=board-of-directors",
        "https://gctc.com.au/wp-json/wp/v2/posts?slug=board-of-directors",
        "https://gctc.com.au/sitemap.xml",
        "https://gctc.com.au/wp-sitemap.xml",
    ]


def test_a_url_with_no_slug_still_offers_the_two_sitemap_rungs():
    result = plan_ladder("https://gctc.com.au/")
    urls = [c["url"] for c in result["candidates"]]
    assert urls == [
        "https://gctc.com.au/sitemap.xml",
        "https://gctc.com.au/wp-sitemap.xml",
    ]


# --- same_host ----------------------------------------------------------------------------


def test_same_host_ignores_a_scheme_difference():
    assert same_host("https://gctc.com.au/x", "http://gctc.com.au/y") is True


def test_same_host_rejects_a_www_variant():
    assert same_host("https://gctc.com.au/x", "https://www.gctc.com.au/y") is False


def test_same_host_rejects_a_different_host():
    assert same_host("https://gctc.com.au/x", "https://evil.example/y") is False


# --- filter_candidates: the guard on page-derived candidates ------------------------------


def test_filter_candidates_refuses_an_off_host_url_naming_both_hosts():
    result = filter_candidates(ACCEPTANCE_URL, ["https://evil.example/p"], already_fetched=0)
    assert result["accepted"] == []
    reason = result["refused"][0]["reason"]
    assert "evil.example" in reason
    assert "gctc.com.au" in reason


def test_filter_candidates_accepts_up_to_the_cap_and_refuses_the_remainder():
    # Six literal same-host URLs against a cap of 5 (the <behavior> spec's own numbers,
    # not derived from MAX_FOLLOWUP_FETCHES) — deriving the URL count from the constant
    # would make this test track a raised cap instead of catching one.
    urls = [f"https://gctc.com.au/page-{i}" for i in range(6)]
    result = filter_candidates(ACCEPTANCE_URL, urls, already_fetched=0)
    assert len(result["accepted"]) == MAX_FOLLOWUP_FETCHES
    assert len(result["refused"]) == 1
    assert str(MAX_FOLLOWUP_FETCHES) in result["refused"][0]["reason"]


def test_filter_candidates_already_fetched_reduces_the_accepted_count():
    # Two literal URLs, already_fetched=4 (the <behavior> spec's own numbers) — accepts
    # exactly one of the two, because only one fetch remains in the budget of 5.
    urls = [f"https://gctc.com.au/page-{i}" for i in range(2)]
    result = filter_candidates(ACCEPTANCE_URL, urls, already_fetched=4)
    assert len(result["accepted"]) == 1


def test_filter_candidates_refuses_a_non_http_scheme_with_its_own_reason():
    result = filter_candidates(ACCEPTANCE_URL, ["ftp://gctc.com.au/p"], already_fetched=0)
    assert result["accepted"] == []
    assert "http" in result["refused"][0]["reason"].lower()


# --- the CLI layer must not disagree with the function -------------------------------------


def test_cli_prints_the_same_first_candidate_and_cap_as_the_function(tmp_path):
    returncode, parsed = _run_url_cli(tmp_path, ACCEPTANCE_URL)
    assert returncode == 0
    assert parsed["ok"] is True
    assert parsed["candidates"][0]["url"] == ACCEPTANCE_FIRST_CANDIDATE
    assert parsed["cap"] == MAX_FOLLOWUP_FETCHES


def test_cli_filter_mode_refuses_an_off_host_url(tmp_path):
    urls_file = tmp_path / "urls.json"
    urls_file.write_text(json.dumps(["https://evil.example/p"]), encoding="utf-8")

    returncode, parsed = _run_url_cli(
        tmp_path, ACCEPTANCE_URL, "--filter", str(urls_file)
    )
    assert returncode == 0
    assert parsed["ok"] is True
    assert parsed["accepted"] == []
    reason = parsed["refused"][0]["reason"]
    assert "evil.example" in reason
    assert "gctc.com.au" in reason
