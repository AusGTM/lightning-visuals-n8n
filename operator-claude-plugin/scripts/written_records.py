"""operator-claude-plugin/scripts/written_records.py

The plugin's THIRD persisted artifact (`artifact_store.py` is the first,
`run_manifest.py` the second). D-59-07: the pre-emptive "this write was authorized
before you could see the preview" warning is retired; what replaces it is a durable,
readable list of the HubSpot records a dispatch run ACTUALLY wrote, so an operator can
review and amend them after the fact instead of trusting a prediction beforehand.

This is a SEPARATE file with its OWN schema and its OWN refusal, mirroring
`run_manifest.py`'s reasoning verbatim: a store that accepts arbitrary keys becomes a
general-purpose store one commit later, and the first thing parked in one would be the
arming grant Phase 23 D-11 deliberately keeps off disk.

**D-59-09 (operator, 2026-08-29): ONE ARTIFACT PER `run_id`, not one shared file.**
Code review and goal verification both found the original one-shared-file design had no
protection against two real, shipped, concurrent writers — an operator's live session
and `scheduled_arm.py`'s unattended cron poller — and the old replace-not-merge rule
(now removed, see `append_chunk`) silently dropped the loser's already-flushed chunk
history on a race. Two runs never share a path any more, so there is nothing to race
over and nothing to merge. An OS-level advisory file lock was considered here and
rejected: it would add contention and a stale-lock failure mode to a path that must
never block a dispatch — the same reasoning `append_chunk`'s own docstring gives for why
a bookkeeping failure must degrade rather than raise. A merged index across every run's
file was also considered and rejected as a later addition, only if operators ask for one
combined view. The cost of this decision is paid on the READER side: every consumer of
this artifact globs `written_records*.json` and unions the matches (`load()`, below)
rather than opening one fixed path.

Schema: `run_id`, `saved_at` (UTC isoformat), `entries` — a list, in chunk order, of
`{chunk_index, object_type, action, hs_object_id, outcome, reason}`. The filename is
`written_records-<run_id>.json`, resolved fresh on every call by `written_records_path`.

`email` and every other contact PII field is DELIBERATELY EXCLUDED from an entry. An
operator opens the record by id; this artifact does not need to become a second place
personal data accumulates. A later widening to include more fields is a decision, not a
drift — this comment is what makes that visible.

`outcome` is one of three words:
  - `written`           — a write action (`update`/`enrich`/`create`) carried a real
                           HubSpot object id.
  - `created_id_unknown` — a `create` whose response carried no id. NEVER a fabricated
                           id: the companies branch's `Build Response`
                           (`scripts/build_cloud_workflows.py`) reads `hs_object_id` off
                           `row.existingRecord`, which is null for a create by
                           construction, and there is no post-write companies
                           confirmation node in this codebase (59-01-PLAN.md's
                           planner_assumptions #5 — that node is explicitly SCOPED OUT,
                           not silently omitted).
  - `not_written`        — the backend's own `action` says the row was refused, held, or
                           never reached a write gate (`write_blocked`, `proposed`,
                           `needs_match_review`, `skip`, `review`, `held`, or anything
                           this module does not recognise).

Reuses `run_manifest.py`'s `_FORBIDDEN_NAME_MARKERS` discipline (defined fresh in THIS
module, not imported from `run_manifest`'s private name, so a later change to one cannot
silently weaken the other): a value whose name suggests an arming grant, a live-write
permission, a secret, an API key, or a webhook raises `WrittenRecordsError` rather than
being persisted. Phase 23 D-11 holds here for the same reason it holds in
`run_manifest.py` — a grant read back off disk on a later run is a live send nobody
authorised in that conversation.

Writes through `durable_paths._atomic_write_0600` — a same-package use of that module's
private helper, not a second atomic-write implementation (see `run_manifest.py`'s own
docstring for why: it already carries the exact guarantee this file needs).

The filename is deliberately NOT a dotfile — Phase 23 D-04, dotfiles are unreadable to
this environment's tooling.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import durable_paths

# NOT hyphen-anchored on purpose (D-59-09): an artifact written under the pre-change
# shared filename (`written_records.json`, no run-id suffix) must still be found by
# `load()` — a narrower, hyphen-anchored glob would silently drop an operator's
# existing file, which is the same understate-what-was-written failure this artifact
# exists to prevent.
WRITTEN_RECORDS_GLOB = "written_records*.json"

# The whole document schema. Anything else is a rejection, not a widening.
RUN_ID_FIELD = "run_id"
STAMP_FIELD = "saved_at"
ENTRIES_FIELD = "entries"

# The three outcomes a classified entry may carry. See module docstring.
WRITTEN = "written"
CREATED_ID_UNKNOWN = "created_id_unknown"
NOT_WRITTEN = "not_written"

# An `action` in this set means the backend passed the row through its write gate.
# Anything else — `write_blocked`, `proposed`, `needs_match_review`, `skip`, `review`,
# `held`, or an unrecognised value — means no write happened.
WRITE_ACTIONS = frozenset({"update", "enrich", "create"})

# Phase 23 D-11, reimplemented (not imported) per `run_manifest.py`'s own precedent —
# see module docstring.
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)


class WrittenRecordsError(Exception):
    """Raised when an entry cannot be persisted safely — a non-dict response item (the
    FINDING 2 discipline, `9e603d6`: fail loud on a shape mismatch rather than silently
    filing it as absent), or a value whose name suggests the one thing this module must
    never hold on disk (see module docstring, Phase 23 D-11)."""


def _looks_forbidden(value) -> bool:
    lowered = str(value).lower()
    return any(marker in lowered for marker in _FORBIDDEN_NAME_MARKERS)


def written_records_path(run_id) -> Path:
    """Where ONE run's artifact lives — resolved fresh on every call, never a
    module-level constant (33-02's migration can create the durable file mid-run; the
    same reason `run_manifest.manifest_path()` and `artifact_store.state_path()` both
    resolve fresh).

    D-59-09: keyed by `run_id`, so two runs never resolve to the same path. The same
    durable directory `run_manifest.py` and `artifact_store.py` both resolve into —
    never a second resolution rule and never a second env var.
    """
    return durable_paths.resolve_state_path().parent / f"written_records-{run_id}.json"


def classify_item(item) -> dict:
    """One per-row n8n response item -> `{object_type, action, hs_object_id, outcome,
    reason}`. Pure, no I/O.

    Raises `WrittenRecordsError` on a non-dict item — the flattening idiom documented at
    `chunking.py:93-96` must run first; a caller that indexes a raw, unflattened body is
    the exact defect FINDING 2 (53-WALK-RECORD.md) recorded (commit `9e603d6`): silently
    filing every row as unanswered with no error. This module never repeats that — it
    fails loud on a shape it cannot classify instead.

    `object_type` defaults to `"contacts"` when the item carries none — contacts-lane
    bodies from `Build Ingest Response` never carry the key at all, and the companies
    branch's own terminal markers (a `Company Gate` skip that reaches `Build Response`
    without passing through `Decide Company Action`) apply exactly this same default, so
    matching it keeps one convention rather than inventing a second.

    `email` and every other PII field on the item is read by nothing here — see module
    docstring.
    """
    if not isinstance(item, dict):
        raise WrittenRecordsError(
            f"a written-records entry must be a dict, got {type(item).__name__} — "
            "flatten the dispatch response first (the idiom `chunking.py`'s own "
            "`DispatchOutcome` docstring gives: `[item for body in outcome.responses "
            "for item in (body if isinstance(body, list) else [body])]`). Silently "
            "skipping a shape it cannot classify is the exact defect FINDING 2 "
            "(53-WALK-RECORD.md, commit 9e603d6) recorded — this module fails loud "
            "instead."
        )

    action = item.get("action")
    hs_object_id = item.get("hs_object_id") or None
    object_type = item.get("object_type") or "contacts"
    reason = item.get("reason")

    if action in WRITE_ACTIONS:
        if hs_object_id:
            outcome = WRITTEN
        elif action == "create":
            outcome = CREATED_ID_UNKNOWN
        else:
            outcome = NOT_WRITTEN
    else:
        outcome = NOT_WRITTEN

    entry = {
        "object_type": object_type,
        "action": action,
        "hs_object_id": hs_object_id,
        "outcome": outcome,
        "reason": reason,
    }

    for key, value in entry.items():
        if _looks_forbidden(key) or (value is not None and _looks_forbidden(value)):
            raise WrittenRecordsError(
                f"refusing to persist a written-records entry — {key}={value!r} looks "
                "like an arming grant, a live-write permission, a secret, an API key, "
                "or a webhook (Phase 23 D-11). Nothing was written."
            )

    return entry


def _load_document(target: Path):
    """The document dict, or `None` on any read/parse failure — used internally by
    `append_chunk` to decide whether to extend the existing entries or start fresh, and
    by `load()` to classify one file. Never raises; a failure to read the existing
    artifact must not stop a live dispatch (T-59-04)."""
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def _entries_from_document(document):
    """`entries`, or `None` when `document` fails the usability check — shared by both
    branches of `load()` so a single-file read and a globbed union degrade identically
    (missing, unreadable, malformed, half-written, schema-mismatched all -> `None`, never
    a partially-trusted list; `run_manifest.load()`'s reasoning verbatim)."""
    if document is None:
        return None
    entries = document.get(ENTRIES_FIELD)
    if not isinstance(entries, list):
        return None
    if any(not isinstance(entry, dict) for entry in entries):
        return None
    return entries


def _refuses_real_durable_write_under_pytest(target: Path) -> bool:
    """Defense in depth for bug_001 (2026-08-29 ultrareview), behind
    `conftest.py`'s `no_durable_writes` autouse fixture: if that fixture is ever
    bypassed or forgotten by a future test, a write from inside pytest that still
    resolves to the operator's REAL durable directory (`durable_dir()`, computed
    independently of whatever `written_records_path` was mocked to) must not land —
    degrade instead of decorating the operator's live state with test artifacts.

    `PYTEST_CURRENT_TEST` is set by pytest itself for the duration of every test; a
    real dispatch run never has it set, so this can never refuse a live write.
    """
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    try:
        return target.resolve().parent == durable_paths.durable_dir().resolve()
    except OSError:
        return False


def append_chunk(run_id, chunk_index, body, path=None):
    """Classify every item in one chunk's raw response `body` and flush the WHOLE
    written-records document — this chunk's entries appended to whatever `run_id`'s file
    already held — through `durable_paths._atomic_write_0600`.

    Two call sites, both at the write itself, never in a caller (written-records-misses-write,
    debug session 2026-08-29 — the gap this docstring used to name only one of them left open):
    `chunking.dispatch_plan`'s per-chunk loop, INSIDE it immediately after
    `responses.append(body)` (`chunk_index` is the loop index; see the call site there for why
    moving this call out of the loop breaks D-59-07's partial-run guarantee), and
    `dispatch.dispatch` (`chunk_index` is always `0` — that function sends exactly one request).

    D-59-09 (operator, 2026-08-29): a document already on disk at this path is now
    ALWAYS this run's own earlier chunks — `written_records_path(run_id)` gives every
    run its own file, so two runs never share one — and is appended to unconditionally.
    The old run-id-mismatch check-and-replace branch is gone: there is no foreign
    document left to replace it against.

    MUST NOT raise on an I/O failure (`OSError`): returns a falsey result instead. This
    is load-bearing — a bookkeeping failure that halted a live HubSpot run would convert
    a missing log line into a mid-run stop, exactly the opposite of D-59-06's
    run-to-completion contract. A `WrittenRecordsError` (a shape or forbidden-name
    problem) DOES propagate — that is a defect in the data, not an environment
    condition, and this function does not decide whether the caller should continue.
    """
    items = body if isinstance(body, list) else [body]
    new_entries = [
        {"chunk_index": chunk_index, **classify_item(item)} for item in items
    ]

    target = Path(path) if path is not None else written_records_path(run_id)

    if _refuses_real_durable_write_under_pytest(target):
        return False

    try:
        existing_entries = _entries_from_document(_load_document(target))
        entries = (existing_entries or []) + new_entries

        document = {
            RUN_ID_FIELD: run_id,
            STAMP_FIELD: datetime.now(timezone.utc).isoformat(),
            ENTRIES_FIELD: entries,
        }
        durable_paths._atomic_write_0600(target, json.dumps(document))
        return True
    except OSError:
        return False


def load(path=None) -> list:
    """The written-records `entries`.

    With an explicit `path=`, this is a single-file read — the document's `entries`, or
    `[]` on any usability failure — unchanged from before D-59-09.

    With no `path`, globs every `written_records*.json` file in the durable directory
    (D-59-09: each run writes its own artifact, so reading "the" list means reading all
    of them) and unions their entries. Matches are read in sorted filename order for
    determinism. One unreadable or malformed file among several does not suppress the
    readable ones — same whole-document degradation `_entries_from_document` gives the
    single-file path, applied per file. Each returned entry is stamped with its own
    document's `run_id` so a unioned `chunk_index` from two different runs stays
    distinguishable.
    """
    if path is not None:
        entries = _entries_from_document(_load_document(Path(path)))
        return entries if entries is not None else []

    directory = durable_paths.resolve_state_path().parent
    try:
        matches = sorted(directory.glob(WRITTEN_RECORDS_GLOB))
    except OSError:
        return []

    unioned = []
    for match in matches:
        document = _load_document(match)
        entries = _entries_from_document(document)
        if entries is None:
            continue
        unioned.extend({**entry, RUN_ID_FIELD: document.get(RUN_ID_FIELD)} for entry in entries)
    return unioned
