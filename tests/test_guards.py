"""tests/test_guards.py

Coverage for src/guards.py -- the shared safety-guard helpers that replaced the bare
`assert` construct across scripts/ (2026-08-29 sweep). Each guard function: passes
clean, raises ValueError with the expected message on violation. The PYTHONOPTIMIZE=1
subprocess tests pin the whole point of the change -- a bare `assert` would silently
vanish under `-O`; these prove the replacement does not.
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

from src import guards  # noqa: E402


# --- assert_disjoint -----------------------------------------------------------------

def test_assert_disjoint_passes_when_no_overlap():
    guards.assert_disjoint({"a", "b"}, {"c", "d"}, "should not raise")


def test_assert_disjoint_raises_on_overlap_with_exact_message():
    with pytest.raises(ValueError, match="^collision$"):
        guards.assert_disjoint({"a", "b"}, {"b", "c"}, "collision")


def test_assert_disjoint_accepts_dict_keys_view():
    # The real call sites pass `props` (a dict), not a pre-built set -- `.isdisjoint`
    # must work against dict_keys the same way it does against a literal set.
    guards.assert_disjoint({"a": 1, "b": 2}, {"c"}, "should not raise")
    with pytest.raises(ValueError):
        guards.assert_disjoint({"a": 1, "b": 2}, {"b"}, "collision")


# --- assert_keys_equal ----------------------------------------------------------------

def test_assert_keys_equal_passes_on_exact_match():
    guards.assert_keys_equal({"only_key": 1}, {"only_key"}, "should not raise")


def test_assert_keys_equal_raises_on_extra_key():
    with pytest.raises(ValueError, match="^extra key$"):
        guards.assert_keys_equal({"only_key": 1, "extra": 2}, {"only_key"}, "extra key")


def test_assert_keys_equal_raises_on_missing_key():
    with pytest.raises(ValueError, match="^missing key$"):
        guards.assert_keys_equal({}, {"only_key"}, "missing key")


def test_assert_keys_equal_raises_on_wrong_key():
    with pytest.raises(ValueError):
        guards.assert_keys_equal({"wrong": 1}, {"only_key"}, "wrong key")


# --- assert_keys_subset ----------------------------------------------------------------

def test_assert_keys_subset_passes_when_subset():
    guards.assert_keys_subset({"a": 1}, {"a", "b", "c"}, "should not raise")


def test_assert_keys_subset_passes_on_exact_match():
    guards.assert_keys_subset({"a": 1, "b": 2}, {"a", "b"}, "should not raise")


def test_assert_keys_subset_raises_on_extra_key():
    with pytest.raises(ValueError, match="^not permitted$"):
        guards.assert_keys_subset({"a": 1, "z": 2}, {"a", "b"}, "not permitted")


# --- assert_no_secrets -----------------------------------------------------------------

def test_assert_no_secrets_passes_on_clean_text(monkeypatch):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "pat-na1-secret-value")
    guards.assert_no_secrets(json_safe := '{"name": "Example Co", "domain": "example.org"}')
    assert json_safe  # sanity: the fixture text itself is non-empty


def test_assert_no_secrets_raises_on_authorization_header():
    with pytest.raises(ValueError, match="Authorization header"):
        guards.assert_no_secrets('{"Authorization": "Bearer pat-na1-xxx"}')


def test_assert_no_secrets_raises_on_bearer_token_value(monkeypatch):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "pat-na1-secret-value")
    with pytest.raises(ValueError, match="bearer token value"):
        guards.assert_no_secrets('{"leaked": "pat-na1-secret-value"}')


def test_assert_no_secrets_raises_on_env_var_name_leak():
    with pytest.raises(ValueError, match="token env var name"):
        guards.assert_no_secrets('{"hint": "set HUBSPOT_PRIVATE_APP_TOKEN in your shell"}')


def test_assert_no_secrets_no_token_set_still_checks_other_two(monkeypatch):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    guards.assert_no_secrets('{"clean": "no secrets here"}')
    with pytest.raises(ValueError, match="Authorization header"):
        guards.assert_no_secrets('{"Authorization": "whatever"}')


# --- PYTHONOPTIMIZE=1 proof: the whole point of the change -----------------------------
# Reuses the subprocess pattern from tests/test_enrich_coverage_companies.py's WR-02
# regression test. Runs in a REAL subprocess with PYTHONOPTIMIZE=1 (the interpreter
# reads this at startup; setting it mid-process does not apply). If any guard here
# regressed back to a bare `assert`, the subprocess would print "GUARD DID NOT FIRE"
# (or exit 0 silently) instead of raising, and the test would fail.

def _run_guard_under_dash_o(setup: str, call: str) -> subprocess.CompletedProcess:
    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        from src import guards

        {setup}
        try:
            {call}
        except ValueError as exc:
            print("GUARD FIRED:", exc)
        else:
            print("GUARD DID NOT FIRE")
    """)
    return subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "PYTHONOPTIMIZE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_assert_disjoint_survives_pythonoptimize():
    result = _run_guard_under_dash_o(
        "", 'guards.assert_disjoint({"a", "b"}, {"b"}, "collision")',
    )
    assert result.returncode == 0, result.stderr
    assert "GUARD FIRED" in result.stdout, result.stdout


def test_assert_keys_equal_survives_pythonoptimize():
    result = _run_guard_under_dash_o(
        "", 'guards.assert_keys_equal({"a": 1, "b": 2}, {"a"}, "wrong scope")',
    )
    assert result.returncode == 0, result.stderr
    assert "GUARD FIRED" in result.stdout, result.stdout


def test_assert_keys_subset_survives_pythonoptimize():
    result = _run_guard_under_dash_o(
        "", 'guards.assert_keys_subset({"a": 1, "z": 2}, {"a"}, "not permitted")',
    )
    assert result.returncode == 0, result.stderr
    assert "GUARD FIRED" in result.stdout, result.stdout


def test_assert_no_secrets_survives_pythonoptimize():
    result = _run_guard_under_dash_o(
        "", 'guards.assert_no_secrets("leaked HUBSPOT_PRIVATE_APP_TOKEN reference")',
    )
    assert result.returncode == 0, result.stderr
    assert "GUARD FIRED" in result.stdout, result.stdout
