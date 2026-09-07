"""Pins FLOW-05's sharpened interrupt/revoke statement at the four sites that carry
D-59-06's revoke semantics (68-RESEARCH.md "D-59-06 / FLOW-05 -- Where the Revoke
Semantics Are Stated Today").

Implicit approval (D-68-01, Plan 68-02) means a round now opens a grant and proceeds
by default. D-68-05's pre-spend pause is what makes an interrupt during that default
path real: the window between the operator reading the stated line and reacting is a
window in which spend could already have started, and the pause makes that window
exist. FLOW-05 asks each of the four sites that already told the truth about a
REVOKE (refuses the next send, does not stop a dispatch already running) to tell the
same truth about the INTERRUPT: free inside the pause, a revoke once it has elapsed.

`SITES` is deliberately a declared list, not a glob -- adding a fifth site later
without adding it here is a visible gap, not a silent one. This file ships with
`SITES` holding only `contact-upload` (Task 1, "the honest interrupt, end to end at
one site") -- Task 2 widens it to all four and adds the two structural assertions
that a fifth-site drift would trip.
"""
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

SITES = (
    "skills/contact-upload/SKILL.md",
)


def _text(relative_path):
    return (PLUGIN_ROOT / relative_path).read_text(encoding="utf-8")


def _normalized(text):
    """Markdown wraps lines; that never changes what the operator reads. Compare on
    collapsed whitespace with bold markers removed, mirroring
    `test_enrich_before_ingest_skill_contract.py`'s `_normalized()` idiom, so a line
    reflow cannot fail a wording assertion (and cannot hide one either)."""
    stripped = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", stripped.replace("*", "")).strip().lower()


@pytest.mark.parametrize("site", SITES)
def test_an_interrupt_inside_the_pause_stops_the_round_before_anything_is_spent(site):
    normalized = _normalized(_text(site))
    assert "stops the round here, before anything is spent" in normalized


@pytest.mark.parametrize("site", SITES)
def test_once_the_pause_has_elapsed_an_interrupt_is_a_revoke(site):
    normalized = _normalized(_text(site))
    assert "once that pause has elapsed" in normalized
    assert "is a revoke" in normalized


@pytest.mark.parametrize("site", SITES)
def test_the_existing_revoke_refuses_next_send_and_does_not_stop_a_running_dispatch(site):
    normalized = _normalized(_text(site))
    assert "refuses the next send" in normalized
    assert "does not stop a dispatch already running" in normalized


@pytest.mark.parametrize("site", SITES)
def test_never_claims_an_interrupt_can_stop_an_in_flight_dispatch(site):
    normalized = _normalized(_text(site))
    banned = (
        "interrupt stops a dispatch already running",
        "interrupt stops the dispatch",
        "interrupt can stop a dispatch already running",
        "interrupt can stop the dispatch",
        "interrupt halts a dispatch already running",
        "interrupt halts the dispatch",
    )
    for phrase in banned:
        assert phrase not in normalized, f"{site} overstates the interrupt: {phrase!r}"
