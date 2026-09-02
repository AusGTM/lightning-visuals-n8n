"""operator-claude-plugin/tests/test_sweep_trigger_contract.py

32-01 Task 1 — the wrapper's contract with `sweep_entry.py`'s real printed output,
pinned from both ends. Follows `test_control_flag_parity.py`'s two-sided idiom: the
OTHER side is read as TEXT (`lv-sweep-run.sh`, the shell wrapper) and THIS side is
EXECUTED — the wrapper's own embedded `-c` python programs, extracted from the shell
text and `exec()`'d in-process with a stubbed `sys.argv`. Never shelled out: the
suite's autouse `no_network` fixture forbids that anyway (conftest.py), and this test
never runs `osascript` either — running the shell script for real is out of scope for
an automated test (see the phase's hard invariant against executing it).

Imports `ALLOWED_MODULES` and `_skill_capabilities` from `test_sweep_read_only` rather
than re-declaring either — that file's own docstring names a second copy as the copy
that drifts wider.
"""
import json
import re
import sys
from pathlib import Path

import config_gate
import sweep_entry
import test_sweep_read_only as read_only

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
WRAPPER_PATH = PLUGIN_ROOT / "skills" / "backend-sweep" / "lv-sweep-run.sh"
WRAPPER_TEXT = WRAPPER_PATH.read_text()

# The wrapper's own embedded python, extracted as TEXT rather than restated. Neither
# program contains a literal single quote, so a non-greedy match up to the shell's own
# closing quote is exact — no hand-written approximation of what the shell runs.
_DASH_C_RE = re.compile(r"-c\s*'(.*?)'", re.S)
_COUNT_PROGRAM, _HEADLINE_PROGRAM = 0, 1


def _programs():
    programs = _DASH_C_RE.findall(WRAPPER_TEXT)
    assert len(programs) == 2, (
        f"expected exactly 2 embedded -c programs (count, headline) in "
        f"lv-sweep-run.sh, found {len(programs)}"
    )
    return programs


def _run_embedded(index, arg_value, capsys):
    """`exec()` the wrapper's OWN program text in-process, with `sys.argv` stubbed the
    way `"$2" -c '<program>' "$OUT"` supplies it at runtime: `sys.argv[1]` is the JSON
    string. capsys captures the program's own `print()` calls."""
    program = _programs()[index]
    old_argv = sys.argv
    sys.argv = ["-c", arg_value]
    try:
        exec(compile(program, f"<lv-sweep-run.sh -c program {index}>", "exec"), {})
    finally:
        sys.argv = old_argv
    return capsys.readouterr().out.strip()


def _count(arg_value, capsys):
    return _run_embedded(_COUNT_PROGRAM, arg_value, capsys)


def _headline(arg_value, capsys):
    return _run_embedded(_HEADLINE_PROGRAM, arg_value, capsys)


def _config_error_notices_json():
    """The one-notice, real-headline case, from a REAL `_cli_main` call rather than a
    hand-written fixture — the plan's own requirement for these two behavior cases."""
    def _raise():
        raise config_gate.ConfigError("boom: no config at all")
    return json.dumps(sweep_entry._cli_main(load_config=_raise))


def _branch(pattern):
    match = re.search(pattern, WRAPPER_TEXT, re.S)
    assert match, f"could not locate a wrapper branch matching {pattern!r}"
    return match.group(0)


# --- static shape --------------------------------------------------------------------


def test_wrapper_exists_with_shebang_and_set_dash_u():
    assert WRAPPER_TEXT.startswith("#!/bin/sh\n")
    assert re.search(r"^set -u\s*$", WRAPPER_TEXT, re.M)


def test_wrapper_names_only_the_sweep_entrypoint_and_the_launcher_resolver():
    """A shipped shell file is a capability surface the import-graph guard cannot
    see (T-29-20's hole, closed here for shell as it was for skill prose).

    D-63-02 added a second named script: the wrapper now shells out to
    `sweep_shim.py` (`--newest`) to resolve the newest installed root for its
    staleness self-check. `sweep_shim` is deliberately NOT folded into
    `read_only.ALLOWED_MODULES` — that set doubles as the exact reachable set of
    `sweep_entry`'s PYTHON IMPORT closure (`test_the_sweep_import_closure_is_
    exactly_the_allowlist` requires equality, not just a subset), and `sweep_shim`
    is never imported by `sweep_entry.py` — it is invoked as an independent
    subprocess, the same relationship the wrapper already has with `sweep_entry`
    itself. Its write-capable verb (`--install`) is checked separately, below:
    the unattended wrapper must never reach it."""
    named = read_only._skill_capabilities(WRAPPER_TEXT)
    assert named == {"sweep_entry", "sweep_shim"}
    assert named <= read_only.ALLOWED_MODULES | {"sweep_shim"}


def test_wrapper_never_invokes_the_shims_write_capable_install_verb():
    """sweep_shim.py's `--install` verb writes and chmods the launcher shim file —
    legitimate for the admin's one-time SWEEP-CRON-TEMPLATE.md step, but the
    unattended wrapper must never reach it. Only `--newest` (a directory listing,
    no writes) may appear in lv-sweep-run.sh, closing the gap the module-import
    guard cannot see for a subprocess-invoked script (T-29-20's hole, again)."""
    assert "--newest" in WRAPPER_TEXT
    assert "--install" not in WRAPPER_TEXT


# <!-- planner-discipline-allow: claude -p -->
# <!-- planner-discipline-allow: --allowedTools -->
# <!-- planner-discipline-allow: ANTHROPIC_API_KEY -->
def test_wrapper_contains_no_llm_invocation_or_credential():
    for forbidden in ("claude -p", "--allowedTools", "ANTHROPIC_API_KEY", "anthropic"):
        assert forbidden not in WRAPPER_TEXT, (
            f"{forbidden!r} must not appear in the wrapper — the LLM-free property is "
            f"asserted, not merely intended"
        )


def test_osascript_appears_exactly_once():
    assert WRAPPER_TEXT.count("osascript") == 1


def test_the_json_parsing_programs_are_invoked_with_the_handed_interpreter():
    assert WRAPPER_TEXT.count('"$2" -c') == 2, (
        'both JSON-parsing programs must run through "$2" -- the interpreter handed '
        "in, never a second one and never a bare interpreter name"
    )


def test_escape_program_escapes_backslash_before_double_quote():
    sed_match = re.search(r"sed\s+'([^']*)'", WRAPPER_TEXT)
    assert sed_match, "no sed escaping program found before osascript interpolation"
    program = sed_match.group(1)
    backslash_target = f"s/{chr(92) * 2}/"
    quote_target = f"s/{chr(34)}/"
    b_idx, q_idx = program.find(backslash_target), program.find(quote_target)
    assert b_idx != -1 and q_idx != -1, "expected both substitutions in the sed program"
    assert b_idx < q_idx, "backslash must be escaped before the double quote (T-32-01)"


# --- the five <behavior> cases, driven through the wrapper's own extracted programs --


def test_behavior_one_notice_counts_as_one(capsys):
    assert _count(_config_error_notices_json(), capsys) == "1"


def test_behavior_config_error_headline_prints_verbatim(capsys):
    assert _headline(_config_error_notices_json(), capsys) == (
        "LV backend sweep: not configured — it is NOT watching"
    )


def test_behavior_empty_list_counts_as_zero(capsys):
    assert _count("[]", capsys) == "0"


def test_behavior_non_json_counts_as_unreadable(capsys):
    traceback_fragment = "Traceback (most recent call last):\n  ...\nValueError: boom"
    assert _count(traceback_fragment, capsys) == "-1"


def test_behavior_json_object_rather_than_list_counts_as_unreadable(capsys):
    assert _count("{}", capsys) == "-1"


# --- structural pins on the healthy / failure / unreadable branches ------------------


def test_the_healthy_branch_stamps_once_with_no_banner_and_no_out_append():
    branch = _branch(r'if \[ "\$COUNT" = "0" \].*?\nfi')
    assert branch.count("stamp ") == 1
    assert "banner " not in branch
    assert "$OUT" not in branch


def test_the_failure_branch_banners_and_exits_the_captured_code():
    branch = _branch(r'if \[ "\$RC" -ne 0 \].*?\nfi')
    assert "banner " in branch
    assert 'exit "$RC"' in branch


def test_the_unreadable_branch_banners_and_exits_one():
    branch = _branch(r'if \[ "\$COUNT" = "-1" \].*?\nfi')
    assert "banner " in branch
    assert "exit 1" in branch
