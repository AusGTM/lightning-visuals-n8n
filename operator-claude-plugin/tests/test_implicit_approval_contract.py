"""Phase 68 Plan 02 — the implicit-approval contract (D-68-01/03/05/06/07/08/10).

Pins the shape every batch-skill's DEFAULT (no-grant) path must take: price a grant
over exactly this batch (`write_grant.plan_grant`), state it, pause once
(`watch.pre_spend_pause`), open it (`write_grant.open_grant(proposal, "yes", config)`),
then continue on the already-correct granted branch. A `plan_grant` refusal stops the
round verbatim and never falls through to `write_grant.authorize_ungranted_send`
(D-68-06). An unsampled ceiling (`"unknown"`) is named in words, never silently
proceeded past (D-68-10). The pre-existing two-phase ask is never deleted — it survives
as the path taken when the operator interrupts the implicit open (FLOW-02).

Task 2 scopes every assertion to `enrich-before-ingest/SKILL.md` only — the source of
truth every other skill's ask either quotes (`suggest-contacts`) or independently
mirrors (`enrich-records`, `contact-upload`). Task 3 parameterises the same shape over
those three remaining skills, added to `TARGETS` below in the same commit as their own
SKILL.md edits, plus per-skill assertions for the literals each one owns.

`_normalized()` is copied from `test_enrich_before_ingest_skill_contract.py`'s own
idiom (collapse whitespace, strip `>` and `*`) rather than imported, matching that
file's own stated reason for staying separate: independent evolution, no risk of
colliding with work in flight in the file it mirrors.
"""
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"

EBI_PATH = SKILLS_DIR / "enrich-before-ingest" / "SKILL.md"
ENRICH_RECORDS_PATH = SKILLS_DIR / "enrich-records" / "SKILL.md"
CONTACT_UPLOAD_PATH = SKILLS_DIR / "contact-upload" / "SKILL.md"
SUGGEST_CONTACTS_PATH = SKILLS_DIR / "suggest-contacts" / "SKILL.md"

# Task 2 scope: enrich-before-ingest only. Task 3 adds the remaining three skills here,
# each carrying the step number its own implicit-open block lives in and the
# arming-scope literal that skill's OWN ungranted ask uses (or None where the skill
# never had its own literal to begin with -- suggest-contacts only ever cross-quoted
# enrich-before-ingest's).
TARGETS = {
    "enrich-before-ingest": {
        "path": EBI_PATH,
        "open_step": 5,
        "no_pause_steps": (7,),
        "survives": ("arms this run and nothing else", "arms this write and nothing else"),
    },
}


def _text(path):
    return path.read_text(encoding="utf-8")


def _normalized(text):
    """Markdown wraps lines and prefixes blockquotes; neither changes what the operator
    reads. Compare on collapsed whitespace with the quote markers and bold markers
    removed, so a reflow cannot fail a wording assertion (and cannot hide one either)."""
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


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_the_open_step_calls_plan_grant_then_pause_then_open_grant_in_order(name):
    target = TARGETS[name]
    step = _step(_text(target["path"]), target["open_step"])
    plan_idx = step.find("write_grant.plan_grant(")
    pause_idx = step.find("watch.pre_spend_pause()")
    open_idx = step.find("write_grant.open_grant(")
    assert plan_idx != -1, (
        f"{name} step {target['open_step']} must call write_grant.plan_grant — a "
        "find() of -1 must fail loudly rather than compare as 'earlier' than the rest"
    )
    assert pause_idx != -1, (
        f"{name} step {target['open_step']} must call watch.pre_spend_pause"
    )
    assert open_idx != -1, (
        f"{name} step {target['open_step']} must call write_grant.open_grant"
    )
    assert plan_idx < pause_idx < open_idx, (
        f"{name}: the documented order must be plan_grant -> pause -> open_grant "
        f"(found plan={plan_idx}, pause={pause_idx}, open={open_idx})"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_open_grant_is_supplied_the_literal_yes_by_the_round_itself(name):
    target = TARGETS[name]
    step = _step(_text(target["path"]), target["open_step"])
    assert 'write_grant.open_grant(proposal, "yes", config)' in step, (
        f"{name}: the round itself must supply the literal string \"yes\" to "
        "open_grant — this is what makes the open implicit rather than a second, "
        "hidden ask"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_a_plan_grant_refusal_is_relayed_verbatim_and_never_falls_through(name):
    target = TARGETS[name]
    step = _normalized(_step(_text(target["path"]), target["open_step"]))
    assert "write_grant.authorize_ungranted_send" in step, (
        f"{name}: the refusal rule must name authorize_ungranted_send as the path "
        "that is NOT taken after a plan_grant refusal"
    )
    assert "proceeding unless interrupted is never proceeding past a refusal" in step, (
        f"{name}: a plan_grant refusal must be stated as a hard stop, never softened "
        "into a disclosure (D-68-06)"
    )
    assert "STOP" in _step(_text(target["path"]), target["open_step"]), (
        f"{name}: the refusal rule must say STOP, not merely describe the refusal"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_the_unsampled_ceiling_verdict_is_named_and_disclosed(name):
    target = TARGETS[name]
    step = _normalized(_step(_text(target["path"]), target["open_step"]))
    assert '"unknown"' in step, (
        f"{name}: the open step must name the unknown ceiling verdict literally"
    )
    assert "not bounded by the monthly ceiling this run" in step, (
        f"{name}: D-68-10 requires the blind spot stated in words, not silently "
        "proceeded past"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_suggestion_companies_is_priced_and_suggestion_cap_is_left_unset(name):
    target = TARGETS[name]
    step = _normalized(_step(_text(target["path"]), target["open_step"]))
    assert "suggestion_companies" in step, (
        f"{name}: the implicit open must price suggestion_companies so a later "
        "suggest-contacts round in this sitting reuses this grant (D-68-08)"
    )
    assert "suggestion_cap` unset" in step or "suggestion_cap\" unset" in step, (
        f"{name}: suggestion_cap must be left unset so the envelope prices the "
        "suggestion round at PRICED_CAP, not a Phase-68 arithmetic invention"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_pre_spend_pause_appears_exactly_once_and_never_in_a_no_pause_step(name):
    target = TARGETS[name]
    text = _text(target["path"])
    assert text.count("pre_spend_pause") == 1, (
        f"{name}: pre_spend_pause must appear exactly once — one consent point per "
        f"batch (D-68-11), found {text.count('pre_spend_pause')}"
    )
    for excluded in target["no_pause_steps"]:
        excluded_step = _step(text, excluded)
        assert "pre_spend_pause" not in excluded_step, (
            f"{name}: step {excluded} must carry no pause of its own — the batch's "
            "one pause lives in step {target['open_step']} only"
        )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_every_pre_existing_arming_scope_literal_survives(name):
    target = TARGETS[name]
    body = _normalized(_text(target["path"]))
    for literal in target["survives"]:
        assert literal in body, (
            f"{name}: the pre-existing literal {literal!r} must survive byte-identical "
            "on the interrupted (ungranted) path — this phase never deletes the "
            "two-phase ask, only makes it non-default (FLOW-02)"
        )
