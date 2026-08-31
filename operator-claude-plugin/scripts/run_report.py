"""operator-claude-plugin/scripts/run_report.py

The plugin's SEVENTH persisted artifact family (`artifact_store.py` first,
`run_manifest.py` second, `written_records.py` third, `held_queue.py` fourth,
`run_state.py` fifth, `remainder_queue.py` sixth). Phase 57 Plan 05 (AFTER-01, AFTER-03's
operator-facing half, G-4's disclosure half): one end-of-run report joining every
durable store a run touches, plus a small per-run record of the facts that would
otherwise die with the process.

**Two halves, added in two tasks.**

Task 1 (this half): `record_audit` / `load_audit` / `classify_audit_read` — a per-run
`run_audit-<run_id>.json` file holding OBSERVATIONS ONLY: the ceiling verdict from grant
time, which provider balances were readable, the disarm result, and any ceiling-stop
metadata. A crashed run loses all four today; this persists them at the moment each is
OBSERVED so a report can be reconstructed after a crash. `record_audit` MERGES into
whatever the file already holds (REVIEW-57-M11) — the ceiling verdict is written at
grant time, the disarm result at the end of the run, and a second call must never erase
the first.

**What must never go in it, said once, here.** These are OBSERVATIONS: a verdict word,
a readability state, a disarm-result word, a chunk index, a count. The GRANT is never
among them — GRANT-06 forbids a grant being persisted or rehydrated, and D-57-05 is
rated one-way. A FRESH, per-module copy of the forbidden-name markers (never imported —
the same deliberate anti-DRY convention `held_queue.py`/`written_records.py`/
`run_manifest.py`/`remainder_queue.py` all document) scans every value passed to
`record_audit` and raises rather than persisting anything grant-shaped.

**The scan is narrowed exactly like `remainder_queue.py`'s (REVIEW-57-M2), with one more
twist this module needs that no sibling does.** A plain leaf-scan against all ten
markers would refuse the module's OWN vocabulary: `disarm`/`disarmed`/`disarm_failed`
all contain the substring `"arm"`, and `write_grant.EXECUTIONS_BASIS` — a real, load-
bearing observation string this module is asked to persist verbatim — contains
`"webhook"`. Both are real facts this record exists to hold, not authority smuggled in
under a data field. So: every KEY, at every depth, is scanned against ALL TEN markers
(a grant, token, or allowlist arrives as a NAMED field, and nothing about "arm" or
"webhook" is a legitimate KEY name inside an audit record). A scalar string VALUE is
scanned against the eight markers that exclude `"arm"` and `"webhook"` — the two
markers whose value-position false positives are this module's own everyday
vocabulary — so a value shaped like a real grant, secret, token, or credential still
raises, while "disarmed" and the executions-basis sentence do not. The four top-level
call arguments (`ceiling`, `balances`, `disarm`, `ceiling_stop`) are treated as SCHEMA,
never scanned as data themselves — `record_audit(run_id, disarm=...)` must not refuse
on its own parameter name containing "arm".

**The audit record is itself a durable input** (REVIEW-57-M4): `run_audit-<run_id>.json`
can be absent, malformed, or another run's exactly as the five primary stores can.
`classify_audit_read` mirrors `written_records.classify_read`/`run_manifest.classify_read`
exactly — same four words, same never-raise contract — so an unreadable audit record
degrades to a named `gaps` entry rather than silently reading as "no ceiling verdict was
observed".

Writes through `durable_paths._atomic_write_0600`, mirrors the pytest-safety guard
`written_records.py`/`remainder_queue.py` both carry (`_refuses_real_durable_write_under_pytest`):
a test that forgets to patch `run_audit_path` must never decorate the operator's real
durable directory.

Task 2 adds `build_run_report` — the join over the five primary stores plus this record.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import durable_paths

# The whole document schema. Anything else is a rejection, not a widening.
RUN_ID_FIELD = "run_id"
STAMP_FIELD = "saved_at"
FACTS_FIELD = "facts"

# classify_audit_read()'s four answers — the same contract as
# written_records.classify_read / run_manifest.classify_read / held_queue.classify_read.
ABSENT = "absent"
PARSEABLE = "parseable"
ANOMALOUS = "anomalous"
ANOTHER_RUN = "another_run"

# Phase 23 D-11, reimplemented fresh (not imported) — see module docstring. Scanning
# KEYS at every depth uses all ten; scanning scalar VALUES excludes "arm" and "webhook"
# (this module's own vocabulary: "disarm"/"disarmed" and EXECUTIONS_BASIS's "webhook
# execution" are real observations, never authority).
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)
_VALUE_MARKERS = tuple(m for m in _FORBIDDEN_NAME_MARKERS if m not in ("arm", "webhook"))

# The four observation fields `record_audit` accepts. Schema, not data — never fed
# through the forbidden-name scan under their OWN names ("disarm" contains "arm").
_AUDIT_FIELDS = ("ceiling", "balances", "disarm", "ceiling_stop")


class RunReportError(Exception):
    """Raised when an audit observation cannot be persisted safely — a key or value
    anywhere in it whose name suggests an arming grant, a live-write permission, a
    secret, an API key, a webhook, or a credential (Phase 23 D-11 / GRANT-06 /
    D-57-05). Nothing is written when this raises."""


def _looks_forbidden_key(name) -> bool:
    lowered = str(name).lower()
    return any(marker in lowered for marker in _FORBIDDEN_NAME_MARKERS)


def _looks_forbidden_value(value) -> bool:
    lowered = str(value).lower()
    return any(marker in lowered for marker in _VALUE_MARKERS)


def _first_forbidden(value):
    """Recursively scans keys (all ten markers) and scalar string leaves (the eight
    value markers) at every depth of an already-built observation payload. Returns the
    offending name, or `None`. See module docstring for why keys and values use
    different marker sets."""
    if isinstance(value, dict):
        for key, sub in value.items():
            if _looks_forbidden_key(key):
                return key
            found = _first_forbidden(sub)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _first_forbidden(item)
            if found is not None:
                return found
    elif isinstance(value, str) and _looks_forbidden_value(value):
        return value
    return None


def run_audit_path(run_id) -> Path:
    """Where ONE run's audit record lives — resolved fresh on every call, the same
    durable directory every sibling store resolves into, never a second resolution
    rule. Keyed by `run_id`, one file per run, mirroring every other per-run artifact
    in this family."""
    return durable_paths.resolve_state_path().parent / f"run_audit-{run_id}.json"


def _refuses_real_durable_write_under_pytest(target: Path) -> bool:
    """Mirrored verbatim from `written_records.py`/`remainder_queue.py`'s own guard: if
    `run_audit_path` resolves into the operator's REAL durable directory while running
    under pytest — because nothing patched it for this test — refuse the write rather
    than decorate the operator's live state with test artifacts."""
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    try:
        return target.resolve().parent == durable_paths.durable_dir().resolve()
    except OSError:
        return False


def _read_document(target: Path):
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def record_audit(run_id, *, ceiling=None, balances=None, disarm=None,
                  ceiling_stop=None, path=None) -> bool:
    """Persist whichever of the four ephemeral observations this call is carrying,
    MERGED into whatever `run_id`'s audit record already holds — never a replace
    (REVIEW-57-M11). Only the keyword arguments actually supplied (non-`None`) are
    merged in; a caller that observes the ceiling at grant time and the disarm result
    at the end of the run makes two calls, and both survive.

    Raises `RunReportError` (nothing written) on any forbidden-shaped key or value
    anywhere in `ceiling`/`balances`/`disarm`/`ceiling_stop` — see module docstring for
    exactly which markers apply to a key and which to a value.

    Returns `True` on a successful write, `False` (never raises) on an I/O failure —
    this is called from the same live dispatch paths the other bookkeeping writes are,
    and must never halt a run over a bookkeeping miss (D-59-10's same discipline).
    """
    updates = {}
    for field, value in (("ceiling", ceiling), ("balances", balances),
                         ("disarm", disarm), ("ceiling_stop", ceiling_stop)):
        if value is None:
            continue
        offender = _first_forbidden(value)
        if offender is not None:
            raise RunReportError(
                f"refusing to persist a run-audit observation for {field!r} — "
                f"{offender!r} suggests an arming grant, a live-write permission, a "
                "secret, an API key, a webhook, or a credential (GRANT-06/D-57-05). "
                "Nothing was written."
            )
        updates[field] = value

    if not updates:
        return True

    target = Path(path) if path is not None else run_audit_path(run_id)

    if _refuses_real_durable_write_under_pytest(target):
        return False

    try:
        existing_document = _read_document(target)
        existing_facts = existing_document.get(FACTS_FIELD) if isinstance(existing_document, dict) else None
        facts = dict(existing_facts) if isinstance(existing_facts, dict) else {}
        facts.update(updates)

        document = {
            RUN_ID_FIELD: run_id,
            STAMP_FIELD: datetime.now(timezone.utc).isoformat(),
            FACTS_FIELD: facts,
        }
        durable_paths._atomic_write_0600(target, json.dumps(document))
        return True
    except OSError:
        return False


def load_audit(run_id, path=None) -> dict:
    """This run's persisted observations, or `{}` when there is nothing usable —
    missing, unreadable, or malformed all degrade to the same empty result, never
    raising. A caller wanting to know WHY it is empty uses `classify_audit_read`."""
    target = Path(path) if path is not None else run_audit_path(run_id)
    document = _read_document(target)
    if document is None:
        return {}
    facts = document.get(FACTS_FIELD)
    return dict(facts) if isinstance(facts, dict) else {}


def classify_audit_read(run_id, path=None) -> str:
    """What this run's own audit record looks like, from a fresh probe — never raises
    (REVIEW-57-M4). `ABSENT` (no file), `PARSEABLE` (a real, readable document,
    including one holding no facts yet), `ANOMALOUS` (present but unparseable, or not a
    mapping, or `facts` is not a mapping), or `ANOTHER_RUN` (a readable document whose
    own stored `run_id` does not match). Same contract every sibling classifier in this
    family carries.
    """
    try:
        target = Path(path) if path is not None else run_audit_path(run_id)
        if not target.exists():
            return ABSENT
        document = _read_document(target)
        if document is None:
            return ANOMALOUS
        facts = document.get(FACTS_FIELD)
        if not isinstance(facts, dict):
            return ANOMALOUS
        if document.get(RUN_ID_FIELD) != run_id:
            return ANOTHER_RUN
        return PARSEABLE
    except (TypeError, ValueError, OSError):
        return ABSENT
