"""operator-claude-plugin/scripts/match_handoff.py

Quick task 260911-ss5 (F9, `.planning/UAT-autonomous-batch-2026-09-09.md`). The
plugin's EIGHTH persisted artifact family (`artifact_store.py` first, `run_manifest.py`
second, `written_records.py` third, `held_queue.py` fourth, `run_state.py` fifth,
`remainder_queue.py` sixth, `run_report.py` seventh, `match_state.py` eighth by quick
task 260911-ss4 -- this module is the ninth). Holds exactly the one fact no existing
store could: the matched-id handoff `enrich-before-ingest` step 7 hands to
`enrich-records` as `confirmed_ids`. Those rows never call `run_state.start_run` --
they are not in this run's enrichment scope -- so before this module existed they had
no durable record anywhere; "every row came back exactly once" was demonstrable only
from the chat transcript (F9's own finding).

**Schema.** A run id, `saved_at` (UTC isoformat), and `entries` -- a list, in input
order, of exactly three keys: `row_id`, `hs_object_id`, `confirmed`.

Two decisions, each load-bearing:

1. **`record_handoff` PROJECTS, it does not store what it is given.** A full
   `auto_matched` entry (`preingest.classify_matches`'s own shape) carries the
   operator's whole spreadsheet `row` -- names, emails, phone numbers -- and this file
   OUTLIVES the run. The projection is this store's own information-disclosure control,
   the same discipline `preingest.py`'s six-key `CANDIDATE_KEYS` projection already
   applies on the way in. A second reason worth one line: with names never stored, the
   known open defect in
   `.planning/todos/pending/2026-09-11-forbidden-name-marker-whole-token-still-refuses-grant-token.md`
   (a contact literally named Grant is refused by every store's matcher) cannot reach
   this store's payload at all -- not fixed here, just structurally out of reach.
   `confirmed` is the truthiness of the entry's own `confirmed` flag (defaulting to
   `False` when absent) -- an email auto-match and an operator's step-3 confirmation
   are both in the handoff, and which was which is the one distinction worth keeping.
2. **Every read degrades rather than raises** -- unlike `match_state.py`'s
   raise-on-anything-but-parseable contract, this store's only consumer is a REPORT
   (`run_report.py`), and a report that cannot read a file must say so in `gaps`, never
   halt (the same reasoning `run_manifest.py`'s docstring gives). `classify_read`
   distinguishes all FOUR states -- `absent`, `parseable`, `anomalous`, `another_run`
   -- mirroring `written_records.classify_read` exactly, so `run_report._add_gap`'s
   existing four-word contract applies unchanged.

`record_handoff([])` (an all-unmatched batch hands nothing onward) still WRITES a file
-- an empty list is a different, legitimate fact from "step 7 never ran", and
`classify_read` answers `parseable` for it, never `absent`.

Carries, freshly reimplemented and never imported (D-69-01, the deliberate anti-DRY
convention every sibling store documents): the ten forbidden-name markers, the
whole-token matcher, and a recursive scan over keys and scalar values that raises
BEFORE writing -- a refused call leaves any previous document on disk untouched. The
scan is over NAMES only (top-level document keys, `row_id`, `hs_object_id`'s own key
name, and the `run_id`), never a string VALUE -- a person named Grant must persist,
mirroring `match_state.py`'s decision 1 verbatim.

Writes through `durable_paths._atomic_write_0600`, the same durable directory every
sibling artifact resolves into, filename deliberately not a dotfile (Phase 23 D-04).
ONE FILE PER RUN (`match_handoff-<run_id>.json`), mirroring `run_state.run_state_path`'s
exact naming shape. Overwrite-whole on every call, never a merge -- a second, shorter
call (a declined step-3 proposal) must be able to leave the handoff, not accumulate
onto the first.

Registered in `run_report._PRUNE_LONG_TTL_GLOBS` (a per-run artifact the operator may
want to keep around as long as `written_records-*.json`, not a within-round working
file like `run_state-*.json`/`match_state-*.json`) and in
`test_forbidden_marker_parity._KEY_MATCHER_MODULES` (a ninth matcher, behaviourally
identical to the other eight).

Mirrors `written_records.py`'s `_refuses_real_durable_write_under_pytest` guard
verbatim in substance: a test that forgets to pass `path=` must not decorate the
operator's real durable directory.
"""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import durable_paths

# --- schema ------------------------------------------------------------------------

RUN_ID_FIELD = "run_id"
STAMP_FIELD = "saved_at"
ENTRIES_FIELD = "entries"

# The three keys `record_handoff` projects every entry down to -- see module docstring
# decision 1. No fourth key: `row` and `candidates` never reach this store.
ENTRY_KEYS = ("row_id", "hs_object_id", "confirmed")

# classify_read()'s four answers -- the same contract as
# written_records.classify_read / run_manifest.classify_read / run_report's own.
ABSENT = "absent"
PARSEABLE = "parseable"
ANOMALOUS = "anomalous"
ANOTHER_RUN = "another_run"

# Phase 23 D-11, reimplemented (not imported) per this module's own anti-DRY
# discipline -- a future change to one list must not silently weaken another.
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)

_CAMEL_BREAK = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_TOKEN = re.compile(r"[^a-z0-9]+")
_INFLECTION_SUFFIXES = ("", "s", "ed", "ing")


def _tokenised(value) -> str:
    """`value`, camel-broken, lowercased, and split into a padded, space-joined run
    of tokens (e.g. `" armed row "`) -- the shape a marker is matched against."""
    broken = _CAMEL_BREAK.sub(" ", str(value)).lower()
    tokens = [token for token in _NON_TOKEN.split(broken) if token]
    return f" {' '.join(tokens)} "


_FORBIDDEN_TOKEN_RUNS = tuple(
    _tokenised(marker).rstrip() + suffix + " "
    for marker in _FORBIDDEN_NAME_MARKERS
    for suffix in _INFLECTION_SUFFIXES
)


def _looks_forbidden(value) -> bool:
    tokenised = _tokenised(value)
    return any(run in tokenised for run in _FORBIDDEN_TOKEN_RUNS)


class MatchHandoffError(Exception):
    """Raised when a matched-id handoff cannot be persisted safely -- the run id, an
    entry's `row_id`, or an entry's `hs_object_id` whose name suggests an arming
    grant, a live-write permission, a secret, or an API key. Nothing is written when
    this raises."""


def handoff_path(run_id) -> Path:
    """Where ONE run's matched-id handoff lives -- resolved fresh on every call, the
    same durable directory every sibling store resolves into."""
    return durable_paths.resolve_state_path().parent / f"match_handoff-{run_id}.json"


def _project_entry(entry):
    """One `auto_matched`-shaped entry -> exactly `{row_id, hs_object_id, confirmed}`.
    `confirmed` defaults to the entry's own truthiness (absent -> False, see module
    docstring decision 1)."""
    return {
        "row_id": entry.get("row_id"),
        "hs_object_id": entry.get("hs_object_id"),
        "confirmed": bool(entry.get("confirmed")),
    }


def _first_forbidden_name(run_id, entries):
    """Scans NAMES ONLY, over the RAW entries -- before projection strips a `row` dict
    away -- so a caller-supplied payload is checked as given, not just what would have
    survived to disk. Mirrors `match_state.py`'s decision 1 exactly: the run id; every
    entry's own top-level KEYS (catches an extraneous forbidden-shaped field even
    though projection would have dropped it); `row_id`/`hs_object_id` as VALUES (they
    are identifiers, not free text); and every KEY inside a `row` dict, never a `row`
    VALUE (a person's first name is not a name in the Phase 23 D-11 sense). Returns the
    offending name, or `None`."""
    if _looks_forbidden(run_id):
        return run_id
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for key in entry:
            if _looks_forbidden(key):
                return key
        for id_key in ("row_id", "hs_object_id"):
            value = entry.get(id_key)
            if value is not None and _looks_forbidden(value):
                return value
        row = entry.get("row")
        if isinstance(row, dict):
            for key in row:
                if _looks_forbidden(key):
                    return key
    return None


def _refuses_real_durable_write_under_pytest(target: Path) -> bool:
    """Mirrored verbatim (in substance) from `written_records.py`: if `handoff_path`
    resolves into the operator's REAL durable directory while running under pytest --
    because nothing patched it for this test -- refuse the write rather than decorate
    the operator's live state with test artifacts."""
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    try:
        return target.resolve().parent == durable_paths.durable_dir().resolve()
    except OSError:
        return False


def record_handoff(run_id, entries, path=None) -> bool:
    """Persist the WHOLE matched-id handoff for one run -- overwrite, never a merge
    (decision: a second, shorter call, e.g. after a declined step-3 proposal, must be
    able to leave the handoff). `entries` carries a full `auto_matched` shape (or
    already-projected dicts); only `row_id`/`hs_object_id`/`confirmed` survive to disk.

    `record_handoff(run_id, [])` still writes a file -- an all-unmatched batch hands
    nothing onward, and that is a different, legitimate fact from "step 7 never ran".

    Raises `MatchHandoffError` (nothing written) on a forbidden-shaped run id or
    entry name. Returns `True` on a successful write, `False` (never raises) on an
    I/O failure or when running under pytest against the operator's real durable
    directory unpatched (D-59-10's same degrade-not-halt posture)."""
    offender = _first_forbidden_name(run_id, entries)
    if offender is not None:
        raise MatchHandoffError(
            f"refusing to persist a matched-id handoff for run {run_id!r} -- "
            f"{offender!r} suggests an arming grant, a live-write permission, a "
            "secret, or an API key. Nothing was written."
        )

    target = Path(path) if path is not None else handoff_path(run_id)

    if _refuses_real_durable_write_under_pytest(target):
        return False

    projected = [_project_entry(entry) for entry in entries]
    document = {
        RUN_ID_FIELD: run_id,
        STAMP_FIELD: datetime.now(timezone.utc).isoformat(),
        ENTRIES_FIELD: projected,
    }
    try:
        durable_paths._atomic_write_0600(target, json.dumps(document))
        return True
    except OSError:
        return False


def _load_document(run_id, path=None):
    """The raw document, or `None` if it cannot be read or is malformed. Shared by
    `classify_read()` and `load()` so both agree on what "usable" means."""
    target = Path(path) if path is not None else handoff_path(run_id)
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(document, dict):
        return None
    entries = document.get(ENTRIES_FIELD)
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        return None
    return document


def classify_read(run_id, path=None) -> str:
    """What this run's own matched-id handoff file looks like, from a fresh probe --
    never raises. `ABSENT` (never saved -- a legitimate zero), `PARSEABLE` (a real,
    readable document belonging to this run, including one whose `entries` is an
    empty list), `ANOMALOUS` (present but unreadable, malformed, or schema-
    mismatched), or `ANOTHER_RUN` (a readable document recorded under a different
    run's id)."""
    try:
        target = Path(path) if path is not None else handoff_path(run_id)
        if not target.exists():
            return ABSENT
        document = _load_document(run_id, path)
        if document is None:
            return ANOMALOUS
        if document.get(RUN_ID_FIELD) != run_id:
            return ANOTHER_RUN
        return PARSEABLE
    except (TypeError, ValueError, OSError):
        return ABSENT


def load(run_id, path=None) -> list:
    """This run's own handoff entries, or `[]` on ANY usability failure -- absent,
    unreadable, malformed, or another run's file. Never a partial list, never raises
    (module docstring decision 2: this store's only consumer is a report, which must
    degrade to a named gap rather than halt)."""
    document = _load_document(run_id, path)
    if document is None or document.get(RUN_ID_FIELD) != run_id:
        return []
    return document[ENTRIES_FIELD]
