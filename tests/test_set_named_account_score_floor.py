"""tests/test_set_named_account_score_floor.py

Offline pins for scripts/set_named_account_score_floor.py's payload-scope guard
(2026-08-29 bare-assert sweep: `build_payloads` used to `assert set(payload) ==
{FLOOR_PROP}` -- now src.guards.assert_keys_equal). No network call anywhere in this
module.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*` imports resolve

import scripts.set_named_account_score_floor as m  # noqa: E402


def test_build_payloads_is_exactly_one_key_per_named_account():
    payloads = m.build_payloads()
    assert set(payloads) == set(m.NAMED_ACCOUNTS)
    for payload in payloads.values():
        assert set(payload) == {m.FLOOR_PROP}
        assert payload[m.FLOOR_PROP] == m.FLOOR_VALUE


def test_build_payloads_guard_survives_pythonoptimize():
    # build_payloads() is self-consistent by construction (it checks exactly the shape
    # it just built), so exercise the guard it calls -- src.guards.assert_keys_equal,
    # imported into this module as `assert_keys_equal` -- the same way the real call
    # site would if a future edit desynced construction from expectation.
    import os
    import subprocess
    import textwrap

    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        import scripts.set_named_account_score_floor as m

        try:
            m.assert_keys_equal(
                {{m.FLOOR_PROP: 60, "extra_key": 1}}, {{m.FLOOR_PROP}}, "payload-scope assertion failed",
            )
        except ValueError:
            print("GUARD FIRED")
        else:
            print("GUARD DID NOT FIRE")
    """)

    proc = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "PYTHONOPTIMIZE": "1"},
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "GUARD FIRED" in proc.stdout, proc.stdout
