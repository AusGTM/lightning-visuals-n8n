"""Pins `extraction.md`'s documented artifact schema to `extraction.py`'s real validator
(D-13 — the drift pin). `extraction.md` is instructions for Claude, not documentation about
the plugin, and its fenced JSON examples are executable documentation: this suite parses them
out of the file and runs them through the real validator, so the two halves of the contract
(the prompt half in `extraction.md`, the validation half in `extraction.py`) cannot silently
stop matching each other. This is the only automated defence available, since the extraction
step itself — Claude reading a source in-session — cannot be tested.
"""
import json
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import extraction  # noqa: E402
import url_fallback  # noqa: E402

EXTRACTION_MD = PLUGIN_ROOT / "skills" / "contact-upload" / "extraction.md"

# The literal bullet headings the URL adapter's two outcomes split on. Structural, not a
# grep over keywords — a heading rename fails the one helper below rather than breaking
# every placement assertion separately and silently.
URL_ADAPTER_HEADING = "## Adapter: a public URL (INGEST-05)"
NEXT_ADAPTER_HEADING = "## Adapter: operator-supplied screenshots (INGEST-07)"
FETCH_FAILED_HEADING = "**Fetch failed (a tool-level error).**"
NOTHING_USABLE_HEADING = "**Fetched but nothing usable.**"


def _extraction_md_text() -> str:
    return EXTRACTION_MD.read_text(encoding="utf-8")


def _fenced_json_blocks(text: str) -> list[dict]:
    """Every ```json ... ``` fenced block in `text`, parsed, in document order. This is the
    "pin": it reads the *rendered* markdown, not a copy kept in the test, so an edit to
    extraction.md's example is exactly what this test re-checks against the real validator."""
    blocks = re.findall(r"```json\s*\n(.*?)```", text, re.DOTALL)
    return [json.loads(block) for block in blocks]


def _url_adapter_regions():
    """The URL adapter's full text, and its two outcome-bullet regions ("Fetch failed" vs
    "Fetched but nothing usable"), sliced structurally at the literal bullet headings.
    The single shared slice every placement assertion below reads off — if a heading is
    ever renamed, this helper is the one place the suite fails, rather than each
    assertion re-deriving the split and breaking in a different, quieter way."""
    text = _extraction_md_text()
    start = text.index(URL_ADAPTER_HEADING)
    end = text.index(NEXT_ADAPTER_HEADING, start)
    adapter_text = text[start:end]

    fetch_failed_start = adapter_text.index(FETCH_FAILED_HEADING)
    nothing_usable_start = adapter_text.index(NOTHING_USABLE_HEADING, fetch_failed_start)

    tool_error_region = adapter_text[fetch_failed_start:nothing_usable_start]
    nothing_usable_region = adapter_text[nothing_usable_start:]

    return adapter_text, tool_error_region, nothing_usable_region


def test_extraction_md_exists_and_is_addressed_to_claude_as_instructions():
    text = _extraction_md_text()
    assert text.strip(), "extraction.md must not be empty"
    assert "you" in text.lower(), "the file must address Claude directly, in the imperative"


def test_first_fenced_example_artifact_is_accepted_by_the_real_validator_with_no_rejects():
    blocks = _fenced_json_blocks(_extraction_md_text())
    assert blocks, "extraction.md must contain at least one fenced JSON example artifact"

    artifact = blocks[0]
    result = extraction.validate(artifact)

    assert len(result.accepted) == 3
    assert result.rejected == []
    assert result.dropped_keys == []
    for record in result.accepted:
        assert record["provenance"]["input"]
        assert record["provenance"]["locator"]


def test_first_fenced_example_carries_the_documented_ambiguity():
    blocks = _fenced_json_blocks(_extraction_md_text())
    artifact = blocks[0]
    result = extraction.validate(artifact)

    assert len(result.ambiguities) == 1
    ambiguity = result.ambiguities[0]
    assert ambiguity["field"] == "jobtitle"


def test_every_canonical_prop_is_named_in_extraction_md():
    text = _extraction_md_text()
    for prop in extraction.canonical_props():
        assert prop in text, f"canonical prop {prop!r} is not named anywhere in extraction.md"


def test_extraction_md_references_extraction_py_as_the_validator_to_run():
    text = _extraction_md_text()
    assert "extraction.py" in text


def test_every_script_path_named_in_extraction_md_exists_on_disk():
    text = _extraction_md_text()
    referenced = set(re.findall(r"scripts/(\w+\.py)", text))
    assert referenced, "expected extraction.md to name at least one script by path"
    for script in referenced:
        assert (SCRIPTS_DIR / script).exists(), (
            f"extraction.md references scripts/{script}, which does not exist on disk"
        )


def test_screenshot_example_artifact_collapses_to_one_row_with_one_carried_ambiguity():
    """The second fenced example: two screenshot-sourced records naming the same person
    (email matches once trimmed/case-folded) but disagreeing on `jobtitle` — one image's
    clipped view reads one character short. Per D-08/D-09, dedupe on the identity rule is
    the validator's job, not something extraction.md instructs Claude to pre-decide; this
    runs the documented example through the real validator (including its dedupe pass) and
    asserts the two records collapse to exactly one accepted row, with the job-title
    disagreement carried through as exactly one ambiguity."""
    blocks = _fenced_json_blocks(_extraction_md_text())
    assert len(blocks) >= 2, "expected a second fenced example artifact for the screenshot case"

    artifact = blocks[1]
    assert artifact["source"]["kind"] == "screenshot"
    assert len(artifact["records"]) == 2, "the documented example starts as two records"

    result = extraction.validate(artifact)

    assert len(result.accepted) == 1, (
        "the two records name the same person and must collapse to one accepted row"
    )
    assert len(result.ambiguities) == 1, (
        "the jobtitle disagreement must be carried through as exactly one ambiguity"
    )
    assert result.ambiguities[0]["field"] == "jobtitle"


def test_extraction_md_states_the_fetch_failed_and_nothing_usable_outcomes_separately():
    text = _extraction_md_text()
    assert "url_not_allowed" in text
    assert "Fetch failed" in text or "fetch failed" in text.lower()
    assert "nothing usable" in text.lower() or "Nothing usable" in text


def test_extraction_md_states_the_no_automated_screenshot_capture_fence():
    text = _extraction_md_text()
    assert "capture" in text.lower()
    assert "web_fetch" in text


# --- Phase 35 Plan 02 Task 3: the URL adapter and url_fallback.py are two hand-maintained
# sides of one contract with no compiler between them. Each test below pins one bound
# that a later edit could silently drift past.


def test_url_adapter_names_the_url_fallback_script_by_path():
    adapter_text, _tool_error, _nothing_usable = _url_adapter_regions()
    assert "scripts/url_fallback.py" in adapter_text


def test_url_fallback_py_is_named_only_in_the_nothing_usable_region_never_in_tool_error():
    """T-35-08: the escalation instruction drifting onto the tool-error branch in a
    later edit. 35-CONTEXT.md's decision is explicit that the ladder runs on the
    fetched-but-empty branch ONLY, never on a tool error — escalating past a refusal
    turns a fence into a suggestion. This fails the moment url_fallback.py is named
    before the 'Fetched but nothing usable' bullet starts."""
    _adapter_text, tool_error_region, nothing_usable_region = _url_adapter_regions()
    assert "url_fallback.py" not in tool_error_region, (
        "url_fallback.py must not be named in the tool-error region — the ladder does "
        "not run on a tool error"
    )
    assert "url_fallback.py" in nothing_usable_region


def test_tool_error_region_states_that_branch_ends_there():
    _adapter_text, tool_error_region, _nothing_usable = _url_adapter_regions()
    assert "ladder" in tool_error_region.lower()
    assert "does not run" in tool_error_region.lower()


def test_url_adapter_quotes_the_same_cap_url_fallback_enforces():
    """T-35-09: the operator is quoted a cap that does not match the enforced cap. The
    number extraction.md shows the operator is imported from url_fallback.py here, never
    typed into this test — the same drift class Phase 34's columnMapAliasParity.test.mjs
    guards one layer down, where two alias tables agree by hand instead of by
    construction.

    Pinned to the actual cap-quoting phrase, not a bare `str(cap) in text` substring
    check: this section also contains `(INGEST-06)`, so a bare digit search on cap=6
    passes by coincidence on an unrelated requirement ID rather than on genuine
    cap-quoting text — caught by this plan's own mandated red-check. Whitespace is
    normalized before matching because markdown line-wraps the phrase across lines."""
    adapter_text, _tool_error, _nothing_usable = _url_adapter_regions()
    normalized = " ".join(adapter_text.split())
    expected = f"at most {url_fallback.MAX_FOLLOWUP_FETCHES} follow-up fetches"
    assert expected in normalized


def test_url_adapter_states_the_same_host_bound():
    adapter_text, _tool_error, _nothing_usable = _url_adapter_regions()
    assert "same-host" in adapter_text.lower() or "same host" in adapter_text.lower()


def test_url_adapter_states_the_no_same_url_retry_rule():
    adapter_text, _tool_error, _nothing_usable = _url_adapter_regions()
    assert "do not re-fetch the same url" in adapter_text.lower()


def test_a_record_with_no_record_type_key_still_routes_to_the_contact_rules():
    """Phase 58 added a per-record `record_type` discriminator (`"contacts"` or
    `"companies"`) to `validate()`. This is the backwards-compatibility property
    every other test in this file depends on without saying so: an artifact with no
    `record_type` key anywhere — every artifact this file's fenced examples and every
    pre-Phase-58 test builds — must be judged by the contact identity rule exactly as
    it always has been, byte-for-byte the same rejection sentence."""
    artifact = {
        "batch_id": "batch-58-pin",
        "source": {"kind": "prose", "detail": "pasted text"},
        "records": [
            {"row": {}, "provenance": {"input": "pasted_text", "locator": "line 1"}},
        ],
        "ambiguities": [],
    }

    result = extraction.validate(artifact)

    assert result.accepted == []
    assert result.rejected == [
        {
            "index": 0,
            "reason": (
                "no identity present: needs a non-blank 'email', or all three of "
                "'firstname'/'lastname'/'company' non-blank, or a non-blank "
                "'linkedin_url'"
            ),
        }
    ]


# D-61-02 (do-not-simplify), REVIEW-A10: the no-invention sentence (rules 1-2 of "The
# no-invention rule" section) is a different, independently-editable sentence from the
# identity-group list this plan's Task 1/2 changed (rule 3's parenthetical). Pinned here
# VERBATIM so a future edit to this file fails THIS suite rather than only a one-time
# summary byte-check that runs on the day of this plan and never again.
NO_INVENTION_SENTENCE = (
    "1. **A field the source does not supply is left out of the row entirely.** Never fill it from\n"
    "   what you already know about the person or the company — a blank cell is honest; a plausible\n"
    "   guess is not.\n"
    "2. **A value the source renders unclearly goes in the ambiguity list, and the field is left out\n"
    "   of the row it belongs to.** Do not put your best reading in the row and hope it is right."
)


def test_no_invention_sentence_is_byte_identical_to_its_pre_plan_61_03_text():
    """REVIEW-A10 / D-61-02: rules 1-2 govern every adapter and must never be loosened
    just because the identity-group list (rule 3's parenthetical, a few lines below)
    gained a third group in this same plan. An edit to this sentence must fail this
    test, not slip through unnoticed."""
    assert NO_INVENTION_SENTENCE in _extraction_md_text()


def test_client_rendered_verdict_is_nowhere_in_extraction_md():
    """T-35-10: the unevidenced 'likely a client-rendered page' verdict returning and
    being repeated to an operator as fact. Live evidence (35-CONTEXT.md Section 2): the
    contract handed the model that conclusion, the Desktop run repeated it verbatim to
    the operator, and the wp-json probe proved it wrong — the content was server-side
    available the whole time, at a URL url_fallback.py itself can build. The fix is not
    a better guess; it is no guess, checked against the whole file, not just the section
    the verdict used to live in."""
    text = _extraction_md_text()
    assert "client-rendered" not in text.lower()
