"""The disclosure audit (FLOW-04 / D-68-09) -- a per-skill verdict table, ratcheted.

D-68-09's test, applied per line: a statement of fact the operator cannot act on
differently is not a decision point, and each one costs a round trip. This module is
the TRACKED artifact recording that audit's outcome -- not a second copy of
68-RESEARCH.md's "Skill-by-Skill Audit" table (a doc copy would be a second place for
the two to drift). Every reclassification recorded below names the operator action the
halt was asking for, so a future reclassification made without one is visibly
incomplete against this file's own pattern.

**Honest scope (68-REVIEW.md WR-03):** this file pins what is already known -- it does
NOT detect new halts. Every assertion below is one of: the AUDIT dict's keys match the
skills on disk (an added/removed *skill*, not added/removed *prose*), a specific
pre-recorded literal is still present (deletion of an already-known-good sentence, not
addition of a new one), or a specific symbol is absent from the read-only skills. None
of these fail if a converted skill's already-converted step grows a brand-new
"Confirm before proceeding? (yes/no)"-style block -- there is no scan here for
newly-added question-like text on any converted skill's disclosure surface, and a
scanner precise enough to add one without drowning in the pervasive, legitimate
"confirm"/"?" language the PRESERVED decision points already use throughout these same
files (held-row review, per-header confirmation, company-domain confirmation) is not
built. A human reviewer re-reading a converted skill's disclosure prose after an edit
is still how a new halt gets caught, same as before this file existed.

Row order is `sorted()` over the skill directory name, matching
`test_skill_sequence_coverage.py`'s own `SKILL_PATHS = sorted(glob(...))` idiom, so two
skills sharing a verdict keep a stable, reproducible order run to run.

| Skill               | Verdict                                  | Reason |
|----------------------|-------------------------------------------|--------|
| backend-control      | decision-point-preserved                  | Every structural mutation (workflow on/off, schedule change, live-write enable, grant open, grant revoke) still gates on step 3's explicit-yes confirm-and-wait rule; D-68-01's implicit-approval posture is scoped to batch spend, never to this skill's own mutations. The FLOW-05 interrupt/revoke restatement (68-03 Task 2) sits beside "Revoking a grant", never replacing the confirm rule. |
| backend-status       | swept-no-findings                         | Read-only, no write/spend path. Already states the posture Phase 68 wants elsewhere ("Re-check only when the operator asks... does not watch the backend; it answers a question when asked"). |
| backend-sweep        | swept-no-findings                         | Read-only sweep report; no write/spend path. |
| contact-upload       | converted (decision-point-preserved: per-header confirmation, step 2b) | Step 4/5's no-grant ask converted to state-pause-open (Plan 68-02); FLOW-05's interrupt/revoke half added (68-03 Task 2). The one-confirmation-per-header rule -- a header like `Ph.` could be phone or photo -- stays a genuine, un-batchable ask. |
| enrich-before-ingest | converted (decision-point-preserved: held-row review vocabulary, end-of-run) | The two-phase ask at steps 5 and 7 converted (Plan 68-02); FLOW-05's interrupt/revoke half added (68-03 Task 2). A row the table cannot confirm is still HELD and still routed through the end-of-run `approve`/`deny`/`pick`/`email:` vocabulary -- an ambiguous or low-confidence case the system cannot resolve for the operator. |
| enrich-records       | converted (decision-point-preserved: company-domain confirmation, step 2) | Steps 5-6's ask converted (Plan 68-02); FLOW-05's interrupt/revoke half added (68-03 Task 2). The company-domain confirmation table stays a genuine ask -- an undecided row stops the whole batch rather than defaulting either way. |
| initialize           | swept-no-findings                         | Read-only setup/check skill; its own explicit "never guess a value" refusal is a config-gate STOP, not a question awaiting an answer. |
| loss-reason-report   | swept-no-findings                         | Read-only report; no write/spend path. |
| review-triage        | decision-point-preserved (verified non-change) | Unmodified by this phase -- its own prose already states the exemption: "This per-record ritual is unchanged by the grant... what changed underneath it is only the authority, never the act." Recorded here as a VERIFIED non-change, not an oversight. |
| suggest-contacts     | converted + decision-point-preserved (split, step 3) | Step 3 is SPLIT, never collapsed into one verdict: role selection stays a genuine ask ("no default to state instead of asking it", D-68-02); the per-company cap default of 2 is a converted statement (D-68-02, D-62-12). `CapRefused` fences anything above the grant's priced cap either way (D-68-06). |
| suggestion-declines  | decision-point-preserved                  | Phase 69 Plan 03: step 3's per-entry `send`/`defer`/`delete`/`export` choice is a genuine decision the system cannot make for the operator -- there is no default to state instead of asking it, and every entry gets its own answer. |

Read-only skills (`backend-status`, `backend-sweep`, `initialize`,
`loss-reason-report`) are pinned by SYMBOL absence, not prose-phrase absence -- a
benign rewording of their text must never fail this suite for the wrong reason.
`pre_spend_pause` and `open_grant` are the two symbols a write/spend path would need;
neither name appears in any of the four.

`review-triage/SKILL.md` is pinned POSITIVELY, never by content hash and never by
prose absence: its per-record ritual sentence is present; its `open_grant` fence
(`skills/review-triage/SKILL.md:120` at last read) passes the `confirmation` variable,
and the round-supplied `"yes"` literal never appears as that call's argument; the
symbol `pre_spend_pause` does not appear anywhere in the file. A content hash would rot
the moment Phase 67 touches any *other* skill in the same commit as an unrelated
refactor of this test file's own imports -- these three facts are what actually matter
and are what stay checked.
"""
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATHS = sorted(PLUGIN_ROOT.glob("skills/*/SKILL.md"))

# The single source of truth for the classification below -- the markdown table in
# this module's own docstring above is ITS rendering, kept in sync by hand the same
# way `test_enrich_before_ingest_skill_contract.py`'s pinned-literal dicts are (that
# file's own precedent for "a Python constant IS the checked artifact; the prose
# around it documents, it does not re-derive"). Deliberately not sourced from
# 68-RESEARCH.md -- RESEARCH.md is a planning document, and a second copy of the same
# table there would be a second place for the two to drift.
AUDIT = {
    "backend-control": "decision-point-preserved",
    "backend-status": "swept-no-findings",
    "backend-sweep": "swept-no-findings",
    "contact-upload": "converted",
    "enrich-before-ingest": "converted",
    "enrich-records": "converted",
    "initialize": "swept-no-findings",
    "loss-reason-report": "swept-no-findings",
    "review-triage": "decision-point-preserved",
    "suggest-contacts": "converted",
    "suggestion-declines": "decision-point-preserved",
}

READ_ONLY_SKILLS = ("backend-status", "backend-sweep", "initialize", "loss-reason-report")

# Each preserved decision point, pinned by its own literal (normalized substring).
PRESERVED_LITERALS = {
    "review-triage": "this per-record ritual is unchanged by the grant",
    "backend-control": "confirm. ask, and wait. only an explicit yes proceeds.",
    "suggest-contacts": "relay a caprefused to the operator exactly as it reads",
    "enrich-records": "an undecided row stops the whole batch rather than defaulting either way",
    "contact-upload": "one confirmation per header, each answered before the next is asked",
    # backticks are stripped by _normalized() too, so this reads as plain words.
    "enrich-before-ingest": "approve / deny / pick <sub-label> / email: <address>",
    # Phase 69 Plan 03: the drain skill's own preserved-decision-point sentence, step 3.
    "suggestion-declines": (
        "this per-entry choice is genuine, and there is no default to state instead "
        "of asking it"
    ),
}

# suggest-contacts step 3 is split -- both halves pinned separately (never collapsed).
SUGGEST_CONTACTS_ROLE_ASK = (
    "this choice is genuine; there is no default to state instead of asking it"
)
SUGGEST_CONTACTS_CAP_STATED = "state the per-company cap default of 2"

# 67-04 (D-67-04, AUTO-04): the D-61-08 reversal, recorded beside the ALLOW_N8N_ARM
# paragraph in backend-control/SKILL.md. Pinned as its own constant rather than added
# to PRESERVED_LITERALS -- 67-04-PLAN.md's own instruction is "do not change
# PRESERVED_LITERALS' existing entries", and a new key would still be a change to that
# dict's shape even though no existing entry moves.
BACKEND_CONTROL_REVERSAL_LITERAL = (
    "allow_write_grants and allow_n8n_arm remain the only authorities"
)

# The retired forward reference (67-02-SUMMARY.md's known exclusion of
# backend-control/SKILL.md from test_autonomy_switch_prose.py's equivalent check --
# that exclusion is a by-name skip, not a requirement that the phrase be present, so it
# stays harmless and does not need tightening once this string is gone here too).
RETIRED_FORWARD_REFERENCE = "is Phase 67's to open"


def _text(skill_dir):
    return (PLUGIN_ROOT / "skills" / skill_dir / "SKILL.md").read_text(encoding="utf-8")


def _normalized(text):
    """Same idiom as `test_interrupt_semantics.py`'s `_normalized()`: collapse
    whitespace, strip blockquote markers, and strip both `*` and `` ` `` markers so a
    reflow or a bold/code-span tweak cannot fail a wording assertion (and cannot hide
    one either). Every assertion below is a SYMBOL check or a semantic-phrase check --
    never a check for the absence of ordinary prose."""
    stripped = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    stripped = stripped.replace("*", "").replace("`", "")
    return re.sub(r"\s+", " ", stripped).strip().lower()


def test_audit_table_covers_every_skill_on_disk():
    on_disk = {p.parent.name for p in SKILL_PATHS}
    in_table = set(AUDIT)
    assert in_table == on_disk, (
        f"AUDIT table and on-disk skills/*/SKILL.md diverge -- "
        f"missing from table: {on_disk - in_table}; "
        f"stale in table: {in_table - on_disk}"
    )


def test_audit_rows_are_sorted_by_skill_directory_name():
    assert list(AUDIT) == sorted(AUDIT)


def test_at_least_four_skills_are_swept_no_findings():
    assert sum(1 for v in AUDIT.values() if v == "swept-no-findings") >= 4


@pytest.mark.parametrize("skill", READ_ONLY_SKILLS)
def test_read_only_skill_is_classified_swept_no_findings(skill):
    assert AUDIT[skill] == "swept-no-findings"


@pytest.mark.parametrize("skill", READ_ONLY_SKILLS)
def test_read_only_skill_has_no_pre_spend_pause_or_open_grant_symbol(skill):
    text = _text(skill)
    assert "pre_spend_pause" not in text, f"{skill} names pre_spend_pause"
    assert "open_grant" not in text, f"{skill} names open_grant"


@pytest.mark.parametrize("skill", sorted(PRESERVED_LITERALS))
def test_preserved_decision_point_literal_is_present(skill):
    normalized = _normalized(_text(skill))
    assert PRESERVED_LITERALS[skill] in normalized, f"{skill} is missing its preserved-decision-point literal"


def test_suggest_contacts_step_3_is_split_not_collapsed():
    normalized = _normalized(_text("suggest-contacts"))
    assert SUGGEST_CONTACTS_ROLE_ASK in normalized, "role selection ask literal missing"
    assert SUGGEST_CONTACTS_CAP_STATED in normalized, "cap-default-stated literal missing"


def test_review_triage_per_record_ritual_sentence_is_present():
    normalized = _normalized(_text("review-triage"))
    assert PRESERVED_LITERALS["review-triage"] in normalized


def test_review_triage_open_grant_fence_passes_confirmation_not_a_yes_literal():
    text = _text("review-triage")
    open_grant_lines = [line for line in text.splitlines() if "open_grant(" in line]
    assert open_grant_lines, "review-triage has no open_grant( call to pin"
    for line in open_grant_lines:
        assert '"yes"' not in line, f"open_grant call passes a literal yes: {line!r}"
        assert "confirmation" in line, f"open_grant call does not pass confirmation: {line!r}"


def test_review_triage_never_names_pre_spend_pause():
    assert "pre_spend_pause" not in _text("review-triage")


def test_backend_control_reversal_record_is_present():
    """67-04 (D-67-04, AUTO-04): the operator's verbatim reversal answer, quoted into
    backend-control/SKILL.md beside the ALLOW_N8N_ARM paragraph."""
    normalized = _normalized(_text("backend-control"))
    assert BACKEND_CONTROL_REVERSAL_LITERAL in normalized, (
        "backend-control/SKILL.md is missing the D-61-08 reversal record"
    )


def test_retired_forward_reference_appears_in_no_skill_body():
    """67-04 retires the stale "is Phase 67's to open" forward reference at
    backend-control/SKILL.md -- the one skill `test_autonomy_switch_prose.py` (67-02)
    was prohibited from editing and therefore excluded by name from its own equivalent
    check. That exclusion permits either presence or absence; this test asserts the
    string is now gone everywhere, unconditionally, over every skill on disk."""
    offenders = [
        path.parent.name
        for path in SKILL_PATHS
        if RETIRED_FORWARD_REFERENCE in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"the retired forward reference \"{RETIRED_FORWARD_REFERENCE}\" is still "
        f"present in: {offenders}"
    )
