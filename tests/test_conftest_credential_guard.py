"""Proves both branches of tests/conftest.py's `no_ambient_credentials` autouse fixture.

D-59-04 (Phase 59 Plan 02). Three tests:
  1. in-process: the default branch, subject to the fixture itself
  2. subprocess: the default branch, driven end-to-end through a real pytest invocation
  3. subprocess: the opt-in (RUN_LIVE_PARITY=true) branch — MUST be a subprocess, see below
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import GUARDED_CREDENTIAL_VARS

ROOT = Path(__file__).resolve().parents[1]

# Obviously-fake sentinel values — never a real key (T-59-08).
SENTINEL_ANTHROPIC_KEY = "not-a-real-key"
SENTINEL_HUBSPOT_TOKEN = "not-a-real-token"


def test_credentials_absent_by_default_in_process():
    """This test is itself subject to the autouse fixture, so no subprocess is needed here."""
    for name in GUARDED_CREDENTIAL_VARS:
        assert name not in os.environ, (
            f"{name} should have been stripped by the autouse no_ambient_credentials fixture"
        )


def test_credentials_absent_by_default_via_subprocess():
    """Subprocess proof of the DEFAULT branch: sentinel credentials in the parent env, no
    RUN_LIVE_PARITY, run the probe as a real pytest process and expect it to see them stripped.
    """
    env = dict(os.environ)
    env["ANTHROPIC_API_KEY"] = SENTINEL_ANTHROPIC_KEY
    env["HUBSPOT_PRIVATE_APP_TOKEN"] = SENTINEL_HUBSPOT_TOKEN
    env.pop("RUN_LIVE_PARITY", None)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/_credential_guard_probe.py", "-q"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"default-branch probe subprocess failed (exit {result.returncode}):\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def test_credentials_present_when_opted_in_via_subprocess():
    """Subprocess proof of the OPT-IN branch.

    Must be a subprocess: tests/conftest.py's autouse fixture decides which branch to take
    before any test body runs in this process, so there is no way to set RUN_LIVE_PARITY from
    inside a test here and observe the opt-in branch — the fixture already ran. Running the
    probe as its own pytest process, with RUN_LIVE_PARITY=true set beforehand, is the only way
    to exercise that branch.
    """
    env = dict(os.environ)
    env["ANTHROPIC_API_KEY"] = SENTINEL_ANTHROPIC_KEY
    env["HUBSPOT_PRIVATE_APP_TOKEN"] = SENTINEL_HUBSPOT_TOKEN
    env["RUN_LIVE_PARITY"] = "true"

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/_credential_guard_probe.py", "-q"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"opt-in-branch probe subprocess failed (exit {result.returncode}):\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
