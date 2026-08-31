"""operator-claude-plugin/scripts/remainder_queue.py

The plugin's SIXTH persisted artifact (`artifact_store.py` first, `run_manifest.py`
second, `written_records.py` third, `held_queue.py` fourth, `run_state.py` fifth). D-57-01
needs a durable home for the rows a mid-run ceiling stop did not send, and D-57-04 needs
one for the remainder of a batch auto-split too large for the sampled allowance. Both are
answered here, by ONE store, because a ceiling-breach row and a ceiling-breach remainder
are the same fact at two granularities — splitting them across two stores would be the
second copy of one rule this codebase keeps paying for (see 57-03-PLAN.md's objective).

**Not a `held_queue.py` entry.** That module's `hold_code` is a validated, CLOSED
vocabulary (`confidence.ALL_HOLD_CODES`) built for per-row confidence holds, and its
`fingerprint()` requires a `preingest.Outcome`-shaped object carrying `.match_tier` and
`.candidate_count`. A row that was never dispatched because the budget ran out was never
assessed by `confidence.assess()` and has neither. Forcing it through would mean either
adding a hold code `assess()` never emits — breaking that module's own stated invariant —
or synthesising a fake outcome for `fingerprint()` to hash. Both are worse than a small
sibling file following the same idiom.

**This store holds WORK, never AUTHORITY (D-57-05, GRANT-06).** An entry carries a
re-sendable record specification — `chunking.failed_batch()`'s own shape — and nothing
else. No grant, arming token, allowlist, or any other authority is ever persisted here. A
resumed run against a queued remainder with no grant open refuses exactly as any other
ungranted send refuses today (`write_grant.authorize_ungranted_send`); the queue confers
nothing. `build_entry` and `save` both refuse (raise `RemainderQueueError`, nothing
written) rather than persist a spec shaped like authority.

**Per-`run_id`, glob-and-union, per D-59-09.** `written_records.py` established this
shape for the identical reason: two concurrent writers (an operator's live session and a
scheduled poller) must never share one file and race over it. `remainder_path(run_id)`
resolves fresh, one file per run, and `load()` globs `remainder_queue*.json` and unions
the matches — a reader asking "what's queued" reads every run's file, not one fixed path.

`_FORBIDDEN_NAME_MARKERS` is defined FRESH here, not imported from `held_queue.py` or
`written_records.py` — the deliberate anti-DRY convention every sibling store
(`held_queue.py`, `written_records.py`, `run_manifest.py`) already documents and follows:
a later change to one module's list must not silently weaken another's.

**SCAN KEYS, NOT FREE-TEXT VALUES (REVIEW-57-M2).** The ten markers below are matched as
plain substrings (`_looks_forbidden`, mirrored from every sibling), so `"arm"` matches
`Armstrong`, `Armidale`, and `pharmacy`. `held_queue` survives that because
`ROW_FIELD_ALLOWLIST` narrows an entry's `row` to identity keys before the scan ever
runs. This store holds COMPLETE `rows` / `people` / `companies` records — real company
and person names — and has no such allowlist to narrow with (a work spec's columns are
whatever the operator's own spreadsheet or lookup produced, and cannot be enumerated in
advance). So the scan is narrowed by POSITION instead of by allowlist:

  - every KEY, recursively, at every depth — dict keys in the spec, in nested dicts, and
    in dicts inside lists (exactly the shape a `rows` / `people` / `companies` spec has).
    A grant, a token, or an allowlist arrives as a NAMED field; this is the check that
    catches it, with no false-positive exposure to customer data.
  - the VALUE of a key is scanned only when that key itself matched a marker, or when the
    value is itself a container (a dict or list, which could hold a named credential one
    level down). A scalar string leaf under an ordinary data key (`name`, `company`,
    `domain`, `firstname`) is NEVER scanned.

An unnarrowed recursive value scan would raise on `{"people": [{"company": "Armstrong
Racing"}]}`, `{"companies": [{"name": "Armidale Jockey Club"}]}`, and `{"rows": [{"notes":
"pharmacy supplier"}]}` — refusing a legitimate batch the moment one contact works
somewhere whose name happens to contain a marker substring. That refusal would be the
worst possible one: `build_entry` raises, this module's own degrade-rather-than-halt rule
in `save()` swallows the resulting failure, and the recovery artifact whose entire job is
not losing rows would fail silently at exactly the moment recovery is needed. The
narrowing above closes that without weakening the guard: a forbidden KEY at any depth
still raises (`{"people": [{"grant": "x"}]}`), and a forbidden value nested inside an
already-suspicious container still raises (`{"rows": [{"auth": {"token": "x"}}]}`).

**One writer per `run_id`.** The per-run filename removes cross-run collision and
`durable_paths._atomic_write_0600` removes the half-written file, but `save` is a
read-append-rewrite, so two writers sharing a `run_id` can still lose one another's
update. The contract is that the dispatch owning a run is its only writer — a stated
invariant, not a lock. Adding one would be the first lock in this codebase's durable
layer, for a concurrency shape nothing currently produces (REVIEW-57-M8).

**Not a crash-recovery record.** An entry appears only on a deliberate ceiling stop or an
accepted split — never on a process that dies mid-dispatch. What such a process actually
sent is in `written_records`, and 57-05's end-of-run report names the remainder queue's
silence about a crashed run as a gap rather than reporting an empty remainder as "nothing
was left".

Writes through `durable_paths._atomic_write_0600` — a same-package use of that module's
private helper, not a second atomic-write implementation. The filename is deliberately
not a dotfile (Phase 23 D-04).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import durable_paths

# D-59-09: one artifact per run, never a shared file two writers race over. NOT
# hyphen-anchored in the glob, for the same reason `written_records.WRITTEN_RECORDS_GLOB`
# is not: a narrower glob would silently drop a legacy or hand-placed file.
REMAINDER_QUEUE_GLOB = "remainder_queue*.json"

# The whole document schema. Anything else is a rejection, not a widening.
RUN_ID_FIELD = "run_id"
STAMP_FIELD = "saved_at"
ENTRIES_FIELD = "entries"

# The two reasons an entry can carry. `REASON_CEILING_BREACH` is D-57-01's mid-run stop;
# `REASON_ALLOWANCE_SPLIT` is D-57-04's accepted-split remainder. Both are strings a
# reader can grep for in a durable file, never a bare enum only Python can compare.
REASON_CEILING_BREACH = "ceiling_breach"
REASON_ALLOWANCE_SPLIT = "allowance_split"
ALL_REASONS = frozenset({REASON_CEILING_BREACH, REASON_ALLOWANCE_SPLIT})

# Phase 23 D-11, reimplemented fresh (not imported) per this codebase's own convention —
# see module docstring. TEN markers, not nine (REVIEW-57-L4): every sibling tuple has
# ten, and an implementation that drops one most often drops "arm" first — the marker
# this module most exists to catch. Enumerated here rather than counted, so the count
# can never silently drift.
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)


class RemainderQueueError(Exception):
    """Raised when an entry cannot be persisted safely — an unrecognised `reason`, a
    non-dict `spec`, or a key/value whose name suggests an arming grant, a live-write
    permission, a secret, an API key, or a webhook (see module docstring). Nothing is
    written when this raises."""


def _looks_forbidden(value) -> bool:
    return any(marker in str(value).lower() for marker in _FORBIDDEN_NAME_MARKERS)


def _first_forbidden_key(value):
    """Recursively scans every KEY at every depth of `value`, plus the VALUE of a key
    only when that key itself matched a marker or the value is itself a container
    (dict/list) — see module docstring's "SCAN KEYS, NOT FREE-TEXT VALUES" section. A
    scalar string leaf under an ordinary data key is never inspected. Returns the
    offending name, or `None`.
    """
    if isinstance(value, dict):
        for key, sub in value.items():
            if _looks_forbidden(key):
                return key
            if isinstance(sub, (dict, list, tuple)):
                found = _first_forbidden_key(sub)
                if found is not None:
                    return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, (dict, list, tuple)):
                found = _first_forbidden_key(item)
                if found is not None:
                    return found
    return None


def remainder_path(run_id) -> Path:
    """Resolved fresh on every call — the same durable directory every sibling store
    resolves into, never a second resolution rule. D-59-09: keyed by `run_id`, so two
    runs never resolve to the same path."""
    return durable_paths.resolve_state_path().parent / f"remainder_queue-{run_id}.json"


def build_entry(spec, reason, *, note=None) -> dict:
    """One re-sendable work spec, ready to hand to `save()` inside a list.

    `spec` is whatever `chunking.failed_batch()` produced, unmodified — a well-formed
    enrichment request by construction, re-sendable through the identical armed dispatch
    path, never a second shape. Raises `RemainderQueueError` (nothing written by the
    caller) when `reason` is not one of `ALL_REASONS`, `spec` is not a dict, or `spec`
    carries a key or value shaped like authority (see module docstring).
    """
    if reason not in ALL_REASONS:
        raise RemainderQueueError(
            f"{reason!r} is not a reason this store recognises. A remainder entry is "
            f"one of: {', '.join(sorted(ALL_REASONS))}."
        )
    if not isinstance(spec, dict):
        raise RemainderQueueError(
            "A remainder entry's spec must be a dict — the shape "
            "`chunking.failed_batch()` produces."
        )

    offender = _first_forbidden_key(spec)
    if offender is not None:
        raise RemainderQueueError(
            f"refusing to persist a remainder entry — {offender!r} suggests an arming "
            "grant, a live-write permission, a secret, an API key, or a webhook. "
            "Nothing was written."
        )

    record_count = None
    for key in ("record_ids", "rows", "people", "companies"):
        members = spec.get(key)
        if isinstance(members, (list, tuple)):
            record_count = len(members)
            break

    return {
        "spec": dict(spec),
        "reason": reason,
        "record_count": record_count,
        "note": note,
    }


def _refuses_real_durable_write_under_pytest(target: Path) -> bool:
    """Defense in depth, mirrored verbatim from `written_records.py`'s own guard (see
    that module's docstring for the incident that motivated it): if `remainder_path`
    resolves into the operator's REAL durable directory while running under pytest —
    because nothing patched `durable_paths.resolve_state_path` for this test — refuse
    the write rather than decorate the operator's live state with test artifacts.
    `PYTEST_CURRENT_TEST` is set by pytest for the duration of every test; a real
    dispatch run never has it set, so this can never refuse a live write.
    """
    import os
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    try:
        return target.resolve().parent == durable_paths.durable_dir().resolve()
    except OSError:
        return False


def save(run_id, entries, path=None) -> bool:
    """Append `entries` to whatever this run's file already holds, and write through
    `durable_paths._atomic_write_0600`. Returns `True` on success.

    Validates every entry BEFORE anything is written — a `RemainderQueueError` (a
    forbidden-named value or an unrecognised `reason`, both defects in the DATA) is
    raised and PROPAGATES, never swallowed. Returns `False` (never raises) on an
    `OSError` or any other exception `_atomic_write_0600` can re-raise — deliberately
    WIDER than `written_records.append_chunk`'s `OSError`-only catch, because this is
    written from inside a live dispatch on the ceiling path, where an unexpected
    exception escaping the bookkeeping would take down the run it exists to make
    recoverable.
    """
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("reason") not in ALL_REASONS:
            raise RemainderQueueError(
                f"a remainder-queue entry must be built by build_entry() and carry a "
                f"recognised reason — got {entry!r}."
            )
        offender = _first_forbidden_key(entry.get("spec"))
        if offender is not None:
            raise RemainderQueueError(
                f"refusing to persist a remainder entry — {offender!r} suggests an "
                "arming grant, a live-write permission, a secret, an API key, or a "
                "webhook. Nothing was written."
            )

    target = Path(path) if path is not None else remainder_path(run_id)

    if _refuses_real_durable_write_under_pytest(target):
        return False

    try:
        existing = []
        try:
            document = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(document, dict) and isinstance(document.get(ENTRIES_FIELD), list):
                existing = document[ENTRIES_FIELD]
        except (OSError, ValueError):
            existing = []

        document = {
            RUN_ID_FIELD: run_id,
            STAMP_FIELD: datetime.now(timezone.utc).isoformat(),
            ENTRIES_FIELD: existing + list(entries),
        }
        durable_paths._atomic_write_0600(target, json.dumps(document))
        return True
    except Exception:  # noqa: BLE001 — see docstring: wider than OSError on purpose.
        return False


def load(path=None) -> list:
    """The remainder-queue `entries`.

    With an explicit `path=`, one file's entries, or `[]` on any usability failure. With
    no `path`, globs `remainder_queue*.json` in the durable directory, unions the
    matches in sorted filename order, and stamps each entry with its own document's
    `run_id`. A `document["entries"]` that is not a list, or that contains a non-dict,
    degrades the WHOLE file to nothing — never a partially-trusted result. One
    unreadable or malformed file among several does not suppress the readable ones.
    """
    if path is not None:
        return _entries_from_file(Path(path))

    directory = durable_paths.resolve_state_path().parent
    try:
        matches = sorted(directory.glob(REMAINDER_QUEUE_GLOB))
    except OSError:
        return []

    unioned = []
    for match in matches:
        document = _read_document(match)
        entries = _validated_entries(document)
        if entries is None:
            continue
        unioned.extend(
            {**entry, RUN_ID_FIELD: document.get(RUN_ID_FIELD)} for entry in entries
        )
    return unioned


def _read_document(target: Path):
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def _validated_entries(document):
    if document is None:
        return None
    entries = document.get(ENTRIES_FIELD)
    if not isinstance(entries, list):
        return None
    if any(not isinstance(entry, dict) for entry in entries):
        return None
    return entries


def _entries_from_file(target: Path) -> list:
    document = _read_document(target)
    entries = _validated_entries(document)
    return list(entries) if entries is not None else []
