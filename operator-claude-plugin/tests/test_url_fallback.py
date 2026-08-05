"""Tests for url_fallback.py — the deterministic candidate-URL ladder (Phase 35).

The property under test is NOT "the ladder is clever". It is: the first URL the operator
is offered for the measured acceptance case is the one measured live to return the roster
(35-CONTEXT.md §2), and the operator-facing CLI layer prints exactly what the in-process
function returns — the two cannot silently drift apart. `url_fallback.py` performs no I/O
of any kind (it builds strings; `web_fetch` is a model-invoked server tool this module
cannot and does not call), so the autouse `no_network` guard in conftest.py is satisfied
by construction, not by a stub.
"""
import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

from url_fallback import (
    MAX_FOLLOWUP_FETCHES,
    filter_candidates,
    give_up_message,
    plan_ladder,
    same_host,
    slug_of,
)

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
URL_FALLBACK_PATH = SCRIPTS_DIR / "url_fallback.py"

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


# --- give_up_message: what was tried, in order, and no verdict about why -----------------


def test_give_up_message_names_attempts_in_the_order_supplied():
    first = {"url": "https://gctc.com.au/wp-json/wp/v2/pages?slug=board-of-directors",
             "outcome": "empty result set"}
    second = {"url": "https://gctc.com.au/sitemap.xml", "outcome": "404"}
    message = give_up_message(ACCEPTANCE_URL, [first, second])
    assert message.index(first["url"]) < message.index(second["url"])
    assert first["outcome"] in message
    assert second["outcome"] in message


def test_give_up_message_draws_no_rendering_verdict():
    message = give_up_message(ACCEPTANCE_URL, [])
    assert "javascript" not in message.lower()
    assert "client-rendered" not in message.lower()
    assert "cannot execute" not in message.lower()


def test_give_up_message_with_no_attempts_still_names_the_pasted_url():
    message = give_up_message(ACCEPTANCE_URL, [])
    assert ACCEPTANCE_URL in message
    assert "no follow-up" in message.lower()


# --- the CLI layer must not disagree with the function -------------------------------------


def test_cli_prints_the_same_first_candidate_and_cap_as_the_function(tmp_path):
    returncode, parsed = _run_url_cli(tmp_path, ACCEPTANCE_URL)
    assert returncode == 0
    assert parsed["ok"] is True
    assert parsed["candidates"][0]["url"] == ACCEPTANCE_FIRST_CANDIDATE
    assert parsed["cap"] == MAX_FOLLOWUP_FETCHES


def test_cli_attempted_mode_matches_the_function(tmp_path):
    attempted_file = tmp_path / "attempted.json"
    attempted_file.write_text(
        json.dumps([{"url": ACCEPTANCE_FIRST_CANDIDATE, "outcome": "empty result set"}]),
        encoding="utf-8",
    )
    returncode, parsed = _run_url_cli(
        tmp_path, ACCEPTANCE_URL, "--attempted", str(attempted_file)
    )
    assert returncode == 0
    assert parsed["ok"] is True
    assert parsed["message"] == give_up_message(
        ACCEPTANCE_URL,
        [{"url": ACCEPTANCE_FIRST_CANDIDATE, "outcome": "empty result set"}],
    )


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


# --- the import-set guard: the exclusions are proven, not promised (T-35-06) --------------
#
# REQUIREMENTS.md's Out of Scope list excludes user-agent obfuscation, viewport emulation,
# any anti-bot-detection technique, authenticated/paywalled scraping, and driving a browser
# — and this phase does not amend that list. That exclusion is only real if it is checked:
# a module that grows an HTTP client, a scraper, or a browser driver one phase later crosses
# the line silently, because the prose fence lives in a different file from the code. Parsed
# with `ast`, never grepped — the module's own docstring and comments legitimately discuss
# what it does not do (see the module docstring above `MAX_FOLLOWUP_FETCHES`), and a text
# grep over the source would make those comments self-invalidating.

# The pure-stdlib import surface url_fallback.py is allowed to have, by ROOT module name.
# A subset check against this explicit allowlist means a new import fails by default rather
# than passing by omission — widening it is a deliberate act with a human attached.
ALLOWED_ROOT_IMPORTS = {"json", "sys", "pathlib", "urllib"}

# Exact dotted import names that must never appear, checked independently of the root
# allowlist above — this is what stops `urllib` (needed for `urllib.parse`) from being a
# back door for `urllib.request`, which is the one urllib submodule that opens a real
# network connection. Also covers non-stdlib scraping/browser/shell capabilities by name.
FORBIDDEN_DOTTED_IMPORTS = {
    "requests", "httpx", "selenium", "playwright", "puppeteer", "bs4",
    "subprocess", "socket", "http.client", "urllib.request",
}


def _import_names(path):
    """Every import in `path`: `(roots, dotted)` — `roots` is the top-level module name
    for every `Import`/`ImportFrom` (what a coarse allowlist check sees), `dotted` is the
    full dotted module named by an `ImportFrom` (what a granular per-submodule check
    needs, since `from urllib.request import urlopen` and `from urllib.parse import
    urlsplit` share a root but not a dotted name)."""
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


def _main_guard_descendants(tree):
    """Every AST node inside an `if __name__ == "__main__":` block (recursively) — the
    one place url_fallback.py may legitimately touch the filesystem, because it reads a
    local JSON file the model itself already wrote to scratch. That is not a fetch."""
    descendants = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ):
            for inner in ast.walk(node):
                descendants.add(inner)
    return descendants


def _open_calls_outside_main(path):
    """`Call` nodes naming the builtin `open`, excluding any inside the `__main__`
    guard (see `_main_guard_descendants`)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    guarded = _main_guard_descendants(tree)
    return [
        node
        for node in ast.walk(tree)
        if node not in guarded
        and isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "open"
    ]


def test_url_fallback_import_set_is_a_subset_of_the_pure_stdlib_allowlist():
    """The exclusion is only real if it is checked: a later phase adding an HTTP client,
    scraper, or browser driver to url_fallback.py must fail this test by default, not
    pass by omission. This is also why the autouse `no_network` guard in conftest.py
    needs no seam here — nothing in this module's import set can reach the network."""
    roots, _dotted = _import_names(URL_FALLBACK_PATH)
    assert roots <= ALLOWED_ROOT_IMPORTS, (
        f"url_fallback.py imports {sorted(roots - ALLOWED_ROOT_IMPORTS)}, outside the "
        f"pure-stdlib allowlist {sorted(ALLOWED_ROOT_IMPORTS)} — before widening this "
        f"allowlist, confirm the new import performs no network I/O and does not "
        f"reintroduce a scraping/browser capability REQUIREMENTS.md excludes"
    )


def test_url_fallback_never_imports_a_named_forbidden_capability():
    """The granular check `ALLOWED_ROOT_IMPORTS` alone cannot make: `urllib` is allowed
    (for `urllib.parse`), but `urllib.request` specifically — the one urllib submodule
    that can open a real network connection — must fail here by exact dotted name,
    never slip through because its root happens to be on the allowlist above."""
    _roots, dotted = _import_names(URL_FALLBACK_PATH)
    offending = dotted & FORBIDDEN_DOTTED_IMPORTS
    assert not offending, (
        f"url_fallback.py imports {sorted(offending)} — each of these would let this "
        f"module fetch, scrape, drive a browser, or shell out, which REQUIREMENTS.md's "
        f"Out of Scope list forbids"
    )


def test_url_fallback_calls_open_only_inside_the_main_guard():
    """The one legitimate filesystem touch is inside `if __name__ == "__main__":`,
    reading a local file the model already wrote — never anywhere else in the module."""
    offenders = _open_calls_outside_main(URL_FALLBACK_PATH)
    assert not offenders, (
        "url_fallback.py calls open() outside the __main__ guard — this module must "
        "perform no I/O beyond reading a local file the model itself wrote, and only "
        "from its CLI entrypoint"
    )
