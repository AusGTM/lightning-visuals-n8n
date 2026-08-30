"""operator-claude-plugin/scripts/held_queue.py

The plugin's FOURTH persisted artifact (`artifact_store.py` first, `run_manifest.py`
second, `written_records.py` third). AFTER-02 needs held and confidence-held rows to
survive the session, and neither existing store can carry them: `run_manifest.py`
holds verdict WORDS and refuses widening its schema by design, and a never-landed row
has no HubSpot record to flag (`written_records.py` is write-outcome only). So this is
a THIRD durable artifact, written the way `run_manifest.py` was written, for the same
reasons its own docstring gives — a store that accepts arbitrary keys becomes a
general-purpose store one commit later.

**Schema.** A run id, a timestamp, and `entries`: a map of `row_id -> entry`, where an
entry carries:
  - `hold_code` — one of `confidence.ALL_HOLD_CODES`, the closed vocabulary.
  - `reason` — the human sentence `confidence.assess()` produced.
  - `observed_signals` — REVIEW-FACING context (which field disagreed, which providers
    disagreed about it) — what the end-of-run review pass shows the operator.
  - `resume_fingerprint` — the RESUME-FACING comparison key (see `fingerprint()`).
  - `row` — an ALLOWLISTED snapshot of the row (see `ROW_FIELD_ALLOWLIST`), enough to
    re-send it.

`observed_signals` and `resume_fingerprint` are two DIFFERENT fields for two DIFFERENT
consumers — the review pass reads the first, `run_manifest.rows_to_resume` reads the
second — because collapsing them into one field is exactly what cycle-3 review found
broken: hashing the enrichment signals the review pass needs to SHOW made the resume
comparison always-unequal, re-spending provider credit on every resume to reach an
identical hold.

**The fingerprint is PER-`hold_code`.** `fingerprint()` hashes the `hold_code` plus
ONLY the two of the outcome contract's five signals a resume's FREE MATCH PASS (zero
provider credit, `preingest.fetch_matches` with an empty provider list) can itself
re-derive: `match_tier` and `candidate_count`. Every other signal (per-field provider
agreement, conflict group names, adjudicated field names) is excluded because the free
match pass cannot observe it AT ALL — hashing it would make the comparison
always-unequal, which is the exact money bug this module exists to prevent for every
enrichment-stage hold. `confidence.ENRICHMENT_STAGE_HOLD_CODES` names the one hold code
this consequence actually applies to; every other code holds on a match-stage signal
that a resume CAN observe changing, so re-inclusion there is a real, working comparison.

**The read path classifies before it degrades** (REVIEW-C11). `classify_read()` is a
PROBE over the raw file, returning `"absent"`, `"parseable"`, `"anomalous"`, or
`"another_run"` — four states `load()`'s own return value cannot carry by design (it
degrades every anomaly to the SAME empty result, mirroring `run_manifest.load()`'s own
reasoning: a partially-trusted queue is worse than an empty one, because presenting an
empty review pass over an unreadable file tells the operator the batch had nothing to
look at, when held rows may in fact exist and are not shown). The two consumers get two
different sentences from the SAME read: the resume path (`load()`) keeps degrade-whole
unchanged; the review pass (`classify_read()`) can say WHICH of the four it saw.

**Write order relative to `run_manifest.py`** (REVIEW-07's other half): the QUEUE entry
is written FIRST, the MANIFEST verdict (`run_manifest.CONFIDENCE_HELD`) SECOND. A crash
between them leaves a queue entry for a row the manifest does not mention — an
unmentioned row is simply re-run on the next resume, the safe direction (a duplicate
provider call, never a dropped contact). The reverse order would mark a row held with
nothing recorded to review, which is the silent-drop this whole plan exists to prevent.
This module does not enforce the order itself (there is no single call that does both
writes) — the two `save()` calls are made by the caller, in this order, and
`test_held_queue.py` asserts the outcome of that ordering directly.

**Row content and the allowlist** (REVIEW-A7). A re-send needs the row's original
specification — a bare `row_id` cannot rebuild a request — but only the identity keys
and the columns the envelope projects, never whatever else happened to be in the
operator's spreadsheet. `ROW_FIELD_ALLOWLIST` mirrors `enrichment.MATCH_LOOKUP_KEYS`
exactly, plus the `row_id` join key itself. The forbidden-name scan below is a SECOND
line, not the first — it targets grants, secrets, and tokens; the allowlist is what
actually keeps an arbitrary spreadsheet column off disk.

Carries `run_manifest.py`'s Phase 23 D-11 forbidden-name refusal verbatim in substance
(reimplemented, not imported — the same discipline `written_records.py` already
applies to this same list, so a future change to one cannot silently weaken another):
the arming grant exists as a call argument for one turn and must never be readable off
disk on a later run.

Writes through `durable_paths._atomic_write_0600`; the filename is deliberately not a
dotfile (Phase 23 D-04). ONE GLOBAL FILE, never one per run (unlike
`written_records.py`) — "held rows collect into ONE review queue, cleared in a single
pass" (D-61-07) is a promise about a single durable backlog, not a per-run artifact; an
entry from an earlier run stays in the queue until an operator's review clears it,
across however many later runs happen in between.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import confidence
import durable_paths
import enrichment

QUEUE_FILENAME = "held_queue.json"

# The whole document schema. Anything else is a rejection, not a widening.
RUN_ID_FIELD = "run_id"
STAMP_FIELD = "saved_at"
ENTRIES_FIELD = "entries"

# REVIEW-A7: identity keys + the columns the envelope projects, and nothing else.
ROW_FIELD_ALLOWLIST = ("row_id",) + enrichment.MATCH_LOOKUP_KEYS

# Phase 23 D-11, reimplemented (not imported) per `run_manifest.py`'s own precedent.
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)

# classify_read()'s four answers (REVIEW-C11).
ABSENT = "absent"
PARSEABLE = "parseable"
ANOMALOUS = "anomalous"
ANOTHER_RUN = "another_run"


class HeldQueueError(Exception):
    """Raised when an entry cannot be persisted safely — a `hold_code` outside
    `confidence.ALL_HOLD_CODES`, or a key/value whose name suggests an arming grant, a
    live-write permission, a secret, or an API key (Phase 23 D-11, see module
    docstring). Nothing is written when this raises."""


def _looks_forbidden(value) -> bool:
    lowered = str(value).lower()
    return any(marker in lowered for marker in _FORBIDDEN_NAME_MARKERS)


def _first_forbidden(value):
    """Recursively scans keys and string leaves of an already-built entry's `row` /
    `observed_signals` payload for a forbidden-shaped name — returns the offending
    string, or `None`. The allowlist (`ROW_FIELD_ALLOWLIST`) is the first line; this is
    the second, belt-and-braces check `run_manifest.py`'s own docstring describes."""
    if isinstance(value, dict):
        for key, sub in value.items():
            if _looks_forbidden(key):
                return key
            found = _first_forbidden(sub)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _first_forbidden(item)
            if found is not None:
                return found
    elif isinstance(value, str) and _looks_forbidden(value):
        return value
    return None


def queue_path() -> Path:
    """Resolved fresh on every call — the same durable directory
    `run_manifest.manifest_path()` and `artifact_store.state_path()` both resolve into,
    never a second resolution rule."""
    return durable_paths.resolve_state_path().parent / QUEUE_FILENAME


def fingerprint(hold_code, outcome) -> str:
    """The resume-time comparison key. Hashes EXACTLY `hold_code`, `outcome.match_tier`,
    and `outcome.candidate_count` — see module docstring for why every other signal is
    deliberately excluded. `outcome` is `preingest.Outcome` or anything exposing those
    two attributes; an `UNPARSEABLE_OUTCOME` (both attributes `None`) is inside this
    function's normal domain, not a special case — it simply hashes to a value that
    stays identical across resumes for as long as the row stays unparseable.
    """
    payload = json.dumps(
        {"hold_code": hold_code, "match_tier": outcome.match_tier,
         "candidate_count": outcome.candidate_count},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _allowlisted_row(row) -> dict:
    return {key: row[key] for key in ROW_FIELD_ALLOWLIST if key in row}


def build_entry(row, hold_code, reason, outcome, observed_signals=None) -> dict:
    """One held row's queue entry, ready to hand to `save()` (merged into the map
    `save()` expects: `{row_id: entry, ...}`)."""
    return {
        "hold_code": hold_code,
        "reason": reason,
        "observed_signals": dict(observed_signals or {}),
        "resume_fingerprint": fingerprint(hold_code, outcome),
        "row": _allowlisted_row(row),
    }


def save(run_id, entries, path=None) -> None:
    """Persist the WHOLE current set of held entries — mirrors `run_manifest.save`'s
    contract exactly: the caller assembles the full `{row_id: entry}` map (typically
    `load()`'s own return, with this run's new/updated entries merged in) and this
    function overwrites the file atomically. Validates every entry BEFORE anything is
    written, so a save that raises leaves the previous queue untouched.
    """
    for row_id, entry in entries.items():
        if _looks_forbidden(row_id):
            raise HeldQueueError(
                f"refusing to persist a held-queue entry keyed {row_id!r} — its name "
                "suggests an arming grant, a live-write permission, a secret, or an "
                "API key. Nothing was written."
            )
        hold_code = entry.get("hold_code") if isinstance(entry, dict) else None
        if hold_code not in confidence.ALL_HOLD_CODES:
            raise HeldQueueError(
                f"row {row_id!r} carries hold_code {hold_code!r}, which is not one of "
                f"confidence.ALL_HOLD_CODES. Nothing was written."
            )
        offender = _first_forbidden(entry.get("row"))
        if offender is None:
            offender = _first_forbidden(entry.get("observed_signals"))
        if offender is None and _looks_forbidden(entry.get("reason") or ""):
            offender = entry.get("reason")
        if offender is not None:
            raise HeldQueueError(
                f"refusing to persist a held-queue entry for row {row_id!r} — "
                f"{offender!r} suggests an arming grant, a live-write permission, a "
                "secret, or an API key. Nothing was written."
            )

    target = Path(path) if path is not None else queue_path()
    document = {
        RUN_ID_FIELD: run_id,
        STAMP_FIELD: datetime.now(timezone.utc).isoformat(),
        ENTRIES_FIELD: dict(entries),
    }
    durable_paths._atomic_write_0600(target, json.dumps(document))


def _validated_entries(document):
    """`entries`, or `None` when `document` fails the usability check — shared by
    `load()` and `classify_read()` so both agree on what "usable" means."""
    if not isinstance(document, dict):
        return None
    entries = document.get(ENTRIES_FIELD)
    if not isinstance(entries, dict):
        return None
    for row_id, entry in entries.items():
        if not isinstance(row_id, str) or not isinstance(entry, dict):
            return None
        if entry.get("hold_code") not in confidence.ALL_HOLD_CODES:
            return None
        if not isinstance(entry.get("resume_fingerprint"), str):
            return None
    return entries


def load(path=None) -> dict:
    """The `{row_id: entry}` map, or `{}` when there is nothing usable — missing,
    unreadable, malformed, half-written, or schema-mismatched all degrade to the SAME
    empty result, never a partially-trusted one (mirrors `run_manifest.load()`'s own
    reasoning verbatim: a queue that silently drops one bad row is worse than an empty
    one — see `classify_read()` for the review pass's own, more honest answer)."""
    target = Path(path) if path is not None else queue_path()
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entries = _validated_entries(document)
    return dict(entries) if entries is not None else {}


def classify_read(path=None, expected_run_id=None) -> str:
    """REVIEW-C11: what the review pass says it saw, from a fresh probe over the file —
    `load()`'s return value cannot carry this by design. One of `ABSENT`, `PARSEABLE`,
    `ANOMALOUS`, or `ANOTHER_RUN`. Never raises. Does not change `load()`'s own
    degrade-whole behaviour — a caller still calls `load()` for the actual entries and
    `classify_read()` for the sentence to say about them.
    """
    target = Path(path) if path is not None else queue_path()
    if not target.exists():
        return ABSENT
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ANOMALOUS
    entries = _validated_entries(document)
    if entries is None:
        return ANOMALOUS
    if expected_run_id is not None and document.get(RUN_ID_FIELD) != expected_run_id:
        return ANOTHER_RUN
    return PARSEABLE
