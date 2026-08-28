"""Root-level pytest configuration for the tests/ suite.

D-59-04: strips ambient Anthropic/HubSpot credentials from os.environ for every test under
tests/, by construction rather than by discipline — the same rationale
operator-claude-plugin/tests/conftest.py's `no_network` fixture already states for network
access.

Why this exists: commit 89c9871 recorded a live incident where a stray load_dotenv() at test
collection time put real ANTHROPIC_API_KEY / HUBSPOT_PRIVATE_APP_TOKEN values into the
environment of a routine test run. src/web_research.py's live branch constructs Anthropic()
with no explicit key and no local `if not api_key:` guard — it relies entirely on
USE_MOCK_WEB_RESEARCH defaulting to "true", which is exactly the condition that incident
broke. Stripping the credential converts the dangerous case (a silent billable call) into a
loud one (AnthropicError at client construction).

DELIBERATE DEVIATION FROM CONTEXT.md's LETTER (D-59-04), recorded here so a future reader does
not "fix" it back: CONTEXT.md's D-59-04 describes the carve-out as "unless a test is
`@live`-marked". There is no registered pytest marker named `live` anywhere in this repo — no
pytest.ini, pyproject.toml, or setup.cfg [pytest] block exists at all. The only "live" concept
in the codebase is a locally-defined `pytest.mark.skipif(os.getenv("RUN_LIVE_PARITY") !=
"true", ...)` object, redefined per file in tests/test_scoring_parity.py and
tests/test_review_flag_eq_filter.py — the mark actually applied to those tests is `skipif`, not
`live`. A fixture that looked up a marker named "live" on the test node would therefore never
find a match. Worse: pytest runs autouse fixtures for a test whose skipif evaluates to "do not skip"
(reproduced live during research), so an unconditional strip would break both of those live
tests the moment RUN_LIVE_PARITY=true is actually used. This fixture therefore gates on the
identical `os.getenv("RUN_LIVE_PARITY") == "true"` condition those two files already use,
instead of a marker lookup. Same intent as CONTEXT.md (credentials present only for a
deliberately opted-in live run), expressed in the mechanism this repo actually has.
"""
import os

import pytest

GUARDED_CREDENTIAL_VARS = ("ANTHROPIC_API_KEY", "HUBSPOT_PRIVATE_APP_TOKEN")


def live_run_opted_in() -> bool:
    """True only when the operator deliberately opted into a live-service run.

    Mirrors the exact condition tests/test_scoring_parity.py and
    tests/test_review_flag_eq_filter.py already gate their `live` skipif on, so this fixture's
    branch never drifts from theirs.
    """
    return os.getenv("RUN_LIVE_PARITY") == "true"


@pytest.fixture(autouse=True)
def no_ambient_credentials(monkeypatch):
    """Strip ANTHROPIC_API_KEY / HUBSPOT_PRIVATE_APP_TOKEN from every test under tests/.

    Autouse so a future test author cannot opt out by forgetting to request it — the guard
    applies to every test in this suite by construction, not by discipline (the same rationale
    operator-claude-plugin/tests/conftest.py's `no_network` fixture states for network access).

    Returns immediately, leaving the environment untouched, when live_run_opted_in() is true —
    a deliberately opted-in live run needs its real credentials. Otherwise strips both guarded
    variables with monkeypatch.delenv(raising=False), since an unset variable is the common
    case, not an error. Using monkeypatch (rather than mutating os.environ directly) means the
    strip is automatically undone at test teardown and never leaks into a later process.
    """
    if live_run_opted_in():
        return

    for name in GUARDED_CREDENTIAL_VARS:
        monkeypatch.delenv(name, raising=False)
