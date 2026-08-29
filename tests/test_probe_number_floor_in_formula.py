"""tests/test_probe_number_floor_in_formula.py

Offline pins for scripts/probe_number_floor_in_formula.py's two guards (2026-08-29
bare-assert sweep): `_patch_disposable_floor`'s payload-scope check (now
src.guards.assert_keys_equal) and `_assert_no_secrets` (now delegates to
src.guards.assert_no_secrets). No network call anywhere in this module.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*` imports resolve

import scripts.probe_number_floor_in_formula as m  # noqa: E402


def test_assert_no_secrets_wrapper_passes_clean_text():
    m._assert_no_secrets('{"name": "Example Co"}')


def test_assert_no_secrets_wrapper_raises_on_leaked_token_env_var_name():
    try:
        m._assert_no_secrets("set HUBSPOT_PRIVATE_APP_TOKEN before running")
    except ValueError as exc:
        assert "token env var name" in str(exc)
    else:
        raise AssertionError("expected ValueError for a leaked token env var name")


def test_patch_disposable_floor_guard_survives_pythonoptimize():
    import os
    import subprocess
    import textwrap

    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        from src.guards import assert_keys_equal
        try:
            assert_keys_equal(
                {{"zz_probe_floor_x": 60, "extra": 1}}, {{"zz_probe_floor_x"}},
                "payload-scope assertion failed",
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
