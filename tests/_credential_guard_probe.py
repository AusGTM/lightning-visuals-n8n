"""Fixture probe, not a suite test — deliberately NOT named test_*.py.

This module is driven by SUBPROCESS from tests/test_conftest_credential_guard.py, never
collected as part of a normal `pytest tests/` run (its leading underscore keeps it out of
default collection, though it is still collectable when named explicitly on the command line,
which is exactly how the driving test uses it). Do not rename this file to test_*.py — that
would fold it into default collection and change what it proves.

Why a subprocess is required: tests/conftest.py's `no_ambient_credentials` autouse fixture has
already decided which branch to take by the time any in-process test body runs. An in-process
test cannot set RUN_LIVE_PARITY and observe the opt-in branch from inside the same pytest
session — the fixture already ran before the test body executed. Running this module as its
own pytest process, with the env set beforehand, is the only way to observe the opt-in branch.
"""
import os

from tests.conftest import GUARDED_CREDENTIAL_VARS, live_run_opted_in


def test_credential_visibility_matches_the_opt_in():
    if live_run_opted_in():
        for name in GUARDED_CREDENTIAL_VARS:
            assert name in os.environ, (
                f"opt-in branch (RUN_LIVE_PARITY=true): expected {name} to be present in "
                "os.environ, but it was stripped"
            )
    else:
        for name in GUARDED_CREDENTIAL_VARS:
            assert name not in os.environ, (
                f"default branch (no RUN_LIVE_PARITY): expected {name} to be absent from "
                "os.environ, but it was present"
            )
