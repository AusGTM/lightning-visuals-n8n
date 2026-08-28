"""Contract test for D-59-06's SessionStart hook.

Proves the note's content by SUBPROCESS, not by inspecting the script's source text —
`hooks/session-start.sh` is what a Claude Code host actually invokes, so this is the one
automated check that can stand in for starting a real session. What it cannot prove is
DELIVERY (does the host actually fire the hook and relay stdout) — that stays a manual,
unperformed check, recorded in 59-VALIDATION.md.
"""
import json
import os
import subprocess
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
HOOKS_JSON = PLUGIN_ROOT / "hooks" / "hooks.json"
SCRIPT = PLUGIN_ROOT / "hooks" / "session-start.sh"


def test_hooks_json_declares_a_sessionstart_entry_pointing_at_the_real_script():
    data = json.loads(HOOKS_JSON.read_text())
    entries = data["hooks"]["SessionStart"]
    assert entries, "SessionStart must be a non-empty list"

    entry = entries[0]
    assert "startup" in entry["matcher"] and "resume" in entry["matcher"], (
        "matcher must cover both startup and resume, not just one"
    )

    command = entry["hooks"][0]["command"]
    assert "${CLAUDE_PLUGIN_ROOT}" in command, (
        "command must use ${CLAUDE_PLUGIN_ROOT}, never a hardcoded/versioned path"
    )
    assert "session-start.sh" in command

    # A hooks.json pointing at a missing script would pass a JSON-only test vacuously —
    # test_plugin_manifest.py's own glob-is-not-vacuous test is the precedent for
    # guarding against exactly that shape of false positive.
    assert SCRIPT.exists(), "hooks.json references session-start.sh, but it is not on disk"


def test_script_exists_and_is_executable():
    assert SCRIPT.exists()
    assert os.access(SCRIPT, os.X_OK), "session-start.sh must be committed with the executable bit set"


def test_script_prints_all_three_d_59_06_facts():
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True)
    stdout = result.stdout
    # Normalize line-wrap whitespace so a substring spanning a wrapped line still matches —
    # the script's prose is hand-wrapped for readability, not for this test's convenience.
    flat = " ".join(stdout.split())

    assert result.returncode == 0, f"expected exit 0, got {result.returncode}. stdout={stdout!r} stderr={result.stderr!r}"
    assert "continues until it is done" in flat, f"missing run-to-completion fact. stdout={stdout!r}"
    assert "refuses the NEXT send" in flat, f"missing revoke-refuses-next-send fact. stdout={stdout!r}"
    assert "finishes its remaining chunks" in flat, f"missing already-running-dispatch-finishes fact. stdout={stdout!r}"
    assert "does not stop it" in flat, f"missing the revoke-does-not-stop-a-running-dispatch clause. stdout={stdout!r}"


def test_script_works_with_a_deliberately_minimal_environment():
    """The fresh-install case: no config, no credentials, no network — just PATH."""
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env={"PATH": os.environ["PATH"]},
    )
    stdout = result.stdout
    flat = " ".join(stdout.split())

    assert result.returncode == 0, f"expected exit 0 with a minimal env, got {result.returncode}. stderr={result.stderr!r}"
    assert "continues until it is done" in flat
    assert "refuses the NEXT send" in flat
    assert "finishes its remaining chunks" in flat


def test_script_output_has_no_question_mark():
    """The non-blocking pin, stated as a property rather than trust in the author."""
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True)
    assert "?" not in result.stdout, f"note must be a statement, never a prompt. stdout={result.stdout!r}"


def test_script_does_not_reach_into_dispatch_or_grant_internals():
    """D-59-06 explicitly does NOT make the dispatch loop grant-aware. A hook that started
    referencing dispatch_plan, write_grant, or chunking internals would be that change
    arriving by the back door.
    """
    text = SCRIPT.read_text()
    for forbidden in ("dispatch_plan", "write_grant", "chunking"):
        assert forbidden not in text, f"session-start.sh must not reference {forbidden!r}"
