"""Phase 67 Plan 02 — the autonomy switch prose contract (AUTO-01, AUTO-03, D-67-09).

Pins the shape every batch skill's ask-or-proceed switch site must take, at the ONE
site Phase 68 already left in each: read `config_gate.autonomy_enabled(config,
"<level>")` in its own single-call fence, before `write_grant.plan_grant(`; name
`autonomy.<level>` and `operator.local.json` on the off-path; retire the stale
"Phase 67's to add" forward reference; state the D-67-09 disclosure (Phase 67 adds no
fence either — an autonomous round discloses an unknown state and proceeds); name all
three unknown-bound causes; and state the pre-start `"over"`-refusal's missing report
as a named limitation (D-67-13, RUN-05).

`_normalized` / `_numbered_step_spans` / `_step` are copied from
`test_implicit_approval_contract.py`, not imported — matching that file's own stated
reason for staying separate (independent evolution, no risk of colliding with work in
flight in the file it mirrors).

Task 2 lands `enrich-before-ingest` alone (`TARGETS` holds one entry). Task 3 widens
`TARGETS` to all four batch skills and adds structural assertions (exact `TARGETS`
size, every path exists, `review-triage`/`backend-control` name no autonomy read) in
the same commit as the prose edits.
"""
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"

TARGETS = {
    "enrich-before-ingest": {
        "path": SKILLS_DIR / "enrich-before-ingest" / "SKILL.md",
        "level": "write",
        "open_steps": (5,),
    },
}


def _text(path):
    return path.read_text(encoding="utf-8")


def _normalized(text):
    """Same idiom as `test_implicit_approval_contract.py`'s `_normalized()`: collapse
    whitespace, strip blockquote markers and bold markers, so a reflow cannot fail a
    wording assertion (and cannot hide one either)."""
    stripped = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", stripped.replace("*", "")).strip()


def _numbered_step_spans(text):
    """Every top-level numbered step (`N. **...`) as `(step_number, span_text)`, a span
    running from its own heading to the next top-level heading or end of file."""
    matches = list(re.finditer(r"^(\d+)\. \*\*", text, flags=re.MULTILINE))
    assert matches, "expected at least one top-level numbered step in SKILL.md"
    spans = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        spans.append((match.group(1), text[start:end]))
    return spans


def _step(text, number):
    for n, span in _numbered_step_spans(text):
        if n == str(number):
            return span
    raise AssertionError(f"no top-level numbered step {number} found in SKILL.md")


def _open_span(target):
    """The concatenation, in order, of every step this skill's ask-or-proceed switch
    is documented across — a single string so every span-scoped assertion below reads
    as one logical block regardless of how many numbered steps it physically spans."""
    text = _text(target["path"])
    return "".join(_step(text, n) for n in target["open_steps"])


_FENCE_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _fence_containing(text, marker):
    """The body of the first ```python fence in `text` that contains `marker`, or
    None. Used to prove the autonomy read sits in its OWN fence — a second
    scripts-module call sharing that fence would give `test_skill_sequence_coverage.py`
    a new >=2-call sequence identity to register, which this plan must not create."""
    for match in _FENCE_RE.finditer(text):
        body = match.group(1)
        if marker in body:
            return body
    return None


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_autonomy_read_calls_config_gate_once_with_the_skills_own_level(name):
    target = TARGETS[name]
    span = _open_span(target)
    call = f'config_gate.autonomy_enabled(config, "{target["level"]}")'
    assert span.count(call) == 1, (
        f"{name}: expected exactly one {call!r} in the open span, found "
        f"{span.count(call)}"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_autonomy_read_sits_in_its_own_single_call_fence(name):
    target = TARGETS[name]
    text = _text(target["path"])
    body = _fence_containing(text, "config_gate.autonomy_enabled(")
    assert body is not None, f"{name}: no python fence found containing the autonomy read"
    non_blank = [ln for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    assert len(non_blank) == 1, (
        f"{name}: the autonomy read's fence must contain exactly one statement (a "
        f"second scripts-module call in the same fence creates a new sequence "
        f"identity), found {len(non_blank)}: {non_blank}"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_autonomy_read_precedes_plan_grant(name):
    target = TARGETS[name]
    span = _open_span(target)
    read_idx = span.find("config_gate.autonomy_enabled(")
    plan_idx = span.find("write_grant.plan_grant(")
    assert read_idx != -1, f"{name}: no autonomy read found in the open span"
    assert plan_idx != -1, f"{name}: no write_grant.plan_grant( found in the open span"
    assert read_idx < plan_idx, (
        f"{name}: the autonomy read must appear before write_grant.plan_grant( in the "
        f"same span (read={read_idx}, plan_grant={plan_idx})"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_off_path_names_the_settings_key_and_the_config_file(name):
    target = TARGETS[name]
    span = _open_span(target)
    assert f'autonomy.{target["level"]}' in span, (
        f"{name}: the off-path sentence must name autonomy.{target['level']}"
    )
    assert "operator.local.json" in span, (
        f"{name}: the off-path sentence must name operator.local.json"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_phase_67s_to_is_retired_from_this_skill(name):
    target = TARGETS[name]
    assert "Phase 67's to" not in _text(target["path"]), (
        f"{name}: the stale \"Phase 67's to add\" forward reference must be retired"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_the_unsampled_ceiling_verdict_is_still_named_and_disclosed(name):
    target = TARGETS[name]
    normalized = _normalized(_open_span(target))
    assert '"unknown"' in normalized, (
        f"{name}: the open span must still name the unknown ceiling verdict literally"
    )
    assert "not bounded by the monthly ceiling this run" in normalized, (
        f"{name}: D-68-10's blind-spot sentence must survive"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_pre_spend_pause_appears_exactly_once(name):
    target = TARGETS[name]
    text = _text(target["path"])
    assert text.count("pre_spend_pause") == 1, (
        f"{name}: pre_spend_pause must appear exactly once, found "
        f"{text.count('pre_spend_pause')}"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_no_icp_or_tier_substring_anywhere_in_the_file(name):
    target = TARGETS[name]
    lowered = _text(target["path"]).lower()
    assert "icp" not in lowered, f"{name}: forbidden substring 'icp' found (D-10b)"
    assert "tier" not in lowered, f"{name}: forbidden substring 'tier' found (D-10b)"


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_the_d_67_09_disclosure_is_present(name):
    target = TARGETS[name]
    text = _text(target["path"])
    assert "D-67-09" in text, f"{name}: the D-67-09 disclosure sentence must be present"


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_all_three_unknown_causes_are_named(name):
    target = TARGETS[name]
    normalized = _normalized(_open_span(target))
    assert "unsampled or unreadable monthly ceiling" in normalized, (
        f"{name}: the unsampled/unreadable ceiling cause must be named"
    )
    assert "provider balance the backend could not read" in normalized, (
        f"{name}: the unreadable provider balance cause must be named"
    )
    assert "n8n_monthly_execution_allowance" in normalized, (
        f"{name}: the unconfigured allowance key cause must be named by its own key"
    )
    assert "never read as headroom" in normalized, (
        f"{name}: the unreadable balance must be tied to the envelope's own "
        f"`unconfirmed` rendering, per the plan's own action text"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_the_pre_start_refusal_limitation_is_stated(name):
    target = TARGETS[name]
    normalized = _normalized(_open_span(target))
    assert "no run and no end-of-run report" in normalized, (
        f"{name}: the pre-start over-ceiling refusal's missing report must be named"
    )
    assert "D-67-13" in normalized, f"{name}: D-67-13 must be cited"
    assert "RUN-05" in normalized, f"{name}: RUN-05 must be cited as the unbuilt split"

