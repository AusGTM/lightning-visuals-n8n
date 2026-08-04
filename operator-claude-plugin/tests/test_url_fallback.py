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

from url_fallback import MAX_FOLLOWUP_FETCHES, plan_ladder, slug_of

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
    assert result["candidates"] == []
    assert any("slug" in note.lower() for note in result["notes"])


# --- the CLI layer must not disagree with the function -------------------------------------


def test_cli_prints_the_same_first_candidate_and_cap_as_the_function(tmp_path):
    returncode, parsed = _run_url_cli(tmp_path, ACCEPTANCE_URL)
    assert returncode == 0
    assert parsed["ok"] is True
    assert parsed["candidates"][0]["url"] == ACCEPTANCE_FIRST_CANDIDATE
    assert parsed["cap"] == MAX_FOLLOWUP_FETCHES
