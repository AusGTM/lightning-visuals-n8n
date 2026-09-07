"""Phase 68 Plan 02 — the implicit-approval contract (D-68-01/03/05/06/07/08/10).

Pins the shape every batch-skill's DEFAULT (no-grant) path must take: price a grant
over exactly this batch (`write_grant.plan_grant`), state it, pause once
(`watch.pre_spend_pause`), open it (`write_grant.open_grant(proposal, "yes", config)`),
then continue on the already-correct granted branch. A `plan_grant` refusal stops the
round verbatim and never falls through to `write_grant.authorize_ungranted_send`
(D-68-06). An unsampled ceiling (`"unknown"`) is named in words, never silently
proceeded past (D-68-10). The pre-existing two-phase ask is never deleted — it survives
as the path taken when the operator interrupts the implicit open (FLOW-02).

Task 2 landed `enrich-before-ingest/SKILL.md` alone — the source of truth every other
skill's ask either quotes (`suggest-contacts`, before this task) or independently
mirrors (`enrich-records`, `contact-upload`). Task 3 (this commit) parameterises the
same shape over those three remaining skills.

Two skills split the three fences across TWO numbered steps rather than one:
`enrich-records` (`plan_grant` in step 5, `pause`+`open_grant` at the end of step 6,
immediately before step 8's dispatch fence) and `contact-upload` (`plan_grant` in step
4, `pause`+`open_grant` at the end of step 5, before step 6's dispatch) —
`suggest-contacts` splits the same way (`plan_grant`/`agreed_cap` in step 3, `pause`
[already landed by Plan 01] + `open_grant` in step 4). `open_steps` is therefore always
a tuple, concatenated in order for every span-scoped assertion below, so a two-step
split is not read as "the call is missing".

`suggestion_companies` is priced only when the batch's own `object_type` can be
`"companies"` (`enrich-before-ingest`, `enrich-records`, `suggest-contacts`) — never for
`contact-upload`, which is contacts-only end to end; `envelope()` defaults the argument
to `None` and skips the whole suggestion-allowance branch when omitted, so omitting it
for a contacts-only skill is correct, not an oversight (`has_suggestion=False`).

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

TARGETS = {
    "enrich-before-ingest": {
        "path": EBI_PATH,
        "open_steps": (5,),
        "no_pause_steps": (7,),
        "has_suggestion": True,
        "survives": ("arms this run and nothing else", "arms this write and nothing else"),
    },
    "enrich-records": {
        "path": ENRICH_RECORDS_PATH,
        "open_steps": (5, 6),
        "no_pause_steps": (7, 8),
        "has_suggestion": True,
        "survives": ("arms this send and nothing else",),
    },
    "contact-upload": {
        "path": CONTACT_UPLOAD_PATH,
        "open_steps": (4, 5),
        "no_pause_steps": (6,),
        "has_suggestion": False,
        "survives": ("arms this send and nothing else",),
    },
    "suggest-contacts": {
        "path": SUGGEST_CONTACTS_PATH,
        "open_steps": (3, 4),
        "no_pause_steps": (5,),
        "has_suggestion": True,
        "survives": (),
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


def _open_span(target):
    """The concatenation, in order, of every step this skill's implicit-open sequence
    is split across — a single string so every span-scoped assertion below reads as
    one logical block regardless of how many numbered steps it physically spans."""
    text = _text(target["path"])
    return "".join(_step(text, n) for n in target["open_steps"])


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_the_open_span_calls_plan_grant_then_pause_then_open_grant_in_order(name):
    target = TARGETS[name]
    span = _open_span(target)
    plan_idx = span.find("write_grant.plan_grant(")
    pause_idx = span.find("watch.pre_spend_pause()")
    open_idx = span.find("write_grant.open_grant(")
    assert plan_idx != -1, (
        f"{name} step(s) {target['open_steps']} must call write_grant.plan_grant — a "
        "find() of -1 must fail loudly rather than compare as 'earlier' than the rest"
    )
    assert pause_idx != -1, (
        f"{name} step(s) {target['open_steps']} must call watch.pre_spend_pause"
    )
    assert open_idx != -1, (
        f"{name} step(s) {target['open_steps']} must call write_grant.open_grant"
    )
    assert plan_idx < pause_idx < open_idx, (
        f"{name}: the documented order must be plan_grant -> pause -> open_grant "
        f"(found plan={plan_idx}, pause={pause_idx}, open={open_idx})"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_open_grant_is_supplied_the_literal_yes_by_the_round_itself(name):
    target = TARGETS[name]
    span = _open_span(target)
    assert 'write_grant.open_grant(proposal, "yes", config)' in span, (
        f"{name}: the round itself must supply the literal string \"yes\" to "
        "open_grant — this is what makes the open implicit rather than a second, "
        "hidden ask"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_a_plan_grant_refusal_is_relayed_verbatim_and_never_falls_through(name):
    target = TARGETS[name]
    span = _open_span(target)
    normalized = _normalized(span)
    assert "write_grant.authorize_ungranted_send" in normalized, (
        f"{name}: the refusal rule must name authorize_ungranted_send as the path "
        "that is NOT taken after a plan_grant refusal"
    )
    assert "proceeding unless interrupted is never proceeding past a refusal" in normalized, (
        f"{name}: a plan_grant refusal must be stated as a hard stop, never softened "
        "into a disclosure (D-68-06)"
    )
    assert "STOP" in span, (
        f"{name}: the refusal rule must say STOP, not merely describe the refusal"
    )


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_the_unsampled_ceiling_verdict_is_named_and_disclosed(name):
    target = TARGETS[name]
    normalized = _normalized(_open_span(target))
    assert '"unknown"' in normalized, (
        f"{name}: the open span must name the unknown ceiling verdict literally"
    )
    assert "not bounded by the monthly ceiling this run" in normalized, (
        f"{name}: D-68-10 requires the blind spot stated in words, not silently "
        "proceeded past"
    )


@pytest.mark.parametrize("name", [n for n in TARGETS if TARGETS[n]["has_suggestion"]])
def test_suggestion_companies_is_priced_and_suggestion_cap_is_left_unset(name):
    target = TARGETS[name]
    normalized = _normalized(_open_span(target))
    assert "suggestion_companies" in normalized, (
        f"{name}: the implicit open must price suggestion_companies so a later "
        "suggest-contacts round in this sitting reuses this grant (D-68-08)"
    )
    assert "suggestion_cap` unset" in normalized or 'suggestion_cap" unset' in normalized, (
        f"{name}: suggestion_cap must be left unset so the envelope prices the "
        "suggestion round at PRICED_CAP, not a Phase-68 arithmetic invention"
    )


@pytest.mark.parametrize("name", ["contact-upload"])
def test_contact_upload_never_prices_a_suggestion_allowance(name):
    """Rule 2 (Task 3 action): a contacts-only batch omits suggestion_companies rather
    than passing zero — `envelope()`'s documented skip for `None` (D-62-11). Checks the
    keyword-argument FORM, not bare substring presence, since the implicit-open prose
    is free to explain the omission by name without passing it."""
    target = TARGETS[name]
    span = _open_span(target)
    assert "suggestion_companies=" not in span, (
        f"{name} is contacts-only end to end — it must never pass suggestion_companies "
        "as a keyword argument, pricing a suggestion round it will never run"
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
            f"one pause lives in step(s) {target['open_steps']} only"
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


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_the_skill_names_backend_controls_direct_grant_route_inline(name):
    """D-68-07: every batch skill offers the direct route to a grant spanning more
    than this batch, and states that a phrase inside this invocation's own argument
    string is not a machine grant — the live Brisbane Roar friction this phase
    fixes."""
    target = TARGETS[name]
    body = _normalized(_text(target["path"]))
    assert "Opening a write grant" in body, (
        f"{name}: must name backend-control's existing 'Opening a write grant' action "
        "as the direct route to a grant spanning more than this batch"
    )
    assert "not a machine grant" in body, (
        f"{name}: must state plainly that a phrase inside an invocation argument "
        "string is not a machine grant"
    )


def test_suggest_contacts_binds_send_domains_as_a_named_variable_reused_at_dispatch():
    """WR-01 (68-REVIEW.md): unlike the other three skills, `suggest-contacts`'s
    implicit open used to price `record_domains` from an inline list-comprehension
    expression rather than a variable named `send_domains` the way the other three
    skills do (`enrich-before-ingest/SKILL.md:287`,
    `enrich-records/SKILL.md:194`, `contact-upload/SKILL.md:240`). Because
    `write_grant.covers()` does exact-membership checking, only a single named
    `send_domains` binding reused verbatim at dispatch time can guarantee the grant
    opened at step 3 actually covers step 7's dispatch. Pins both halves: the bind
    at step 3, and the prose naming that SAME variable at step 7's reused dispatch
    block."""
    text = _text(SUGGEST_CONTACTS_PATH)
    open_span = _open_span(TARGETS["suggest-contacts"])
    assert "send_domains = [" in open_span, (
        "suggest-contacts step 3 must bind the domain list to a named `send_domains` "
        "variable, mirroring the other three converted skills, rather than inlining "
        "the expression directly into plan_grant's record_domains= kwarg"
    )
    assert "record_domains=send_domains" in open_span, (
        "suggest-contacts step 3's plan_grant call must pass the bound `send_domains` "
        "variable, not a fresh expression"
    )
    step_7 = _step(text, 7)
    assert "send_domains" in step_7, (
        "suggest-contacts step 7 must name `send_domains` explicitly when describing "
        "the reused dispatch block's authorize_send/covers() call, so the value is "
        "provably the same variable bound at step 3, not merely likely to be"
    )


def test_suggest_contacts_names_the_caprefused_cause_on_the_reuse_branch():
    """WR-02 (68-REVIEW.md): a grant opened via `backend-control/SKILL.md`'s "Opening
    a write grant" action -- the direct route D-68-07 tells every skill to advertise --
    never prices `suggestion_companies` unless the opener passed it explicitly, so a
    following `suggest-contacts` round's reuse branch raises `CapRefused` on the
    operator's own recommended path. Step 3's reuse branch must name this specific
    cause and the specific next step, not just relay `agreed_cap`'s generic message."""
    step_3 = _step(_text(SUGGEST_CONTACTS_PATH), 3)
    normalized = _normalized(step_3)
    assert "CapRefused" in step_3 and "specific" in normalized, (
        "suggest-contacts step 3's reuse branch must name CapRefused's specific, "
        "foreseeable cause (a grant opened without suggestion_companies priced) "
        "rather than only relaying the generic agreed_cap message"
    )
    assert "suggestion_companies=<count of this batch" in normalized, (
        "suggest-contacts step 3's reuse branch must tell the operator exactly which "
        "kwarg to pass when re-opening a grant via backend-control's 'Opening a "
        "write grant' action so this round can reuse it"
    )
    assert "cannot be reused for one" in normalized, (
        "suggest-contacts step 3's reuse branch must state plainly that the "
        "unpriced grant cannot be reused for a suggestion round"
    )
