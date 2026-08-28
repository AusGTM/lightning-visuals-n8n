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

Schema: `run_id`, `saved_at` (UTC isoformat), `entries` — a list, in chunk order, of
`{chunk_index, object_type, action, hs_object_id, outcome, reason}`.

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
from datetime import datetime, timezone
from pathlib import Path

import durable_paths

WRITTEN_RECORDS_FILENAME = "written_records.json"

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


def written_records_path() -> Path:
    """Where the artifact lives — resolved fresh on every call, never a module-level
    constant (33-02's migration can create the durable file mid-run; the same reason
    `run_manifest.manifest_path()` and `artifact_store.state_path()` both resolve fresh).

    The same durable directory those two files resolve into — never a second resolution
    rule and never a second env var.
    """
    return durable_paths.resolve_state_path().parent / WRITTEN_RECORDS_FILENAME


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
    `append_chunk` to decide whether to extend the existing entries or start fresh.
    Never raises; a failure to read the existing artifact must not stop a live dispatch
    (T-59-04)."""
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def append_chunk(run_id, chunk_index, body, path=None):
    """Classify every item in one chunk's raw response `body` and flush the WHOLE
    written-records document — this chunk's entries appended to whatever the file
    already held for `run_id` — through `durable_paths._atomic_write_0600`.

    Called from INSIDE `chunking.dispatch_plan`'s per-chunk loop, immediately after
    `responses.append(body)` — see the call site there for why moving this call out of
    the loop breaks D-59-07's partial-run guarantee.

    A document on disk carrying a DIFFERENT `run_id` is replaced, not merged into — a
    written-records file is scoped to the one run that is currently writing it.

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

    target = Path(path) if path is not None else written_records_path()

    try:
        existing = _load_document(target)
        if (
            isinstance(existing, dict)
            and existing.get(RUN_ID_FIELD) == run_id
            and isinstance(existing.get(ENTRIES_FIELD), list)
        ):
            entries = existing[ENTRIES_FIELD] + new_entries
        else:
            entries = new_entries

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
    """The document's `entries`, or `[]` when there is nothing usable — missing,
    unreadable, malformed, half-written, and schema-mismatched all degrade to the SAME
    empty result, never a partially-trusted one (`run_manifest.load()`'s reasoning
    verbatim: a truncated list read as complete would understate what was actually
    written, the exact failure this artifact exists to prevent)."""
    target = Path(path) if path is not None else written_records_path()
    document = _load_document(target)
    if document is None:
        return []

    entries = document.get(ENTRIES_FIELD)
    if not isinstance(entries, list):
        return []
    if any(not isinstance(entry, dict) for entry in entries):
        return []
    return entries
