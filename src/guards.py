"""src/guards.py

Shared, unstrippable safety-guard helpers.

Every guard below used to be a bare `assert` -- one copy-pasted verbatim across six
files for the secrets check, and one ad hoc `assert ...isdisjoint(...)` /
`assert set(...) == {...}` per call site for the payload-scope checks. CPython removes
`assert` ENTIRELY under `python -O` / `PYTHONOPTIMIZE=1`: under either flag the guard
does not weaken, it ceases to exist (WR-02, commit ac64353). What several of these guard
is a live PATCH to a HubSpot portal with no rollback, or a bearer token leaking into a
committed artifact -- both need to fail loudly regardless of how the interpreter is
invoked. Every function here raises ValueError unconditionally instead (matching the
precedent ac64353 set, and the two independent `assert_payload_scope` helpers already
living in scripts/backfill_anti_icp_flag_num.py and scripts/rescore_population.py).

Three payload-scope shapes are kept as three functions because they express different
predicates over the same "a dict of properties about to be PATCHed to HubSpot" shape --
a self-documenting name at each call site is worth more than one generic `require()`:

  - `assert_disjoint`: the payload must NOT contain any of a small, explicit forbidden
    set (e.g. FORBIDDEN_PROPS, the derived scoring fields an enrichment script must
    never write). The payload is otherwise free to carry any other keys. Also fits any
    two sets that must never overlap (e.g. a pinned-id set and an excluded-id set).
  - `assert_keys_equal`: the payload's key set must be EXACTLY a given set -- a tighter
    bound, used where a single write is meant to touch one fixed key (or a small fixed
    set) and nothing else.
  - `assert_keys_subset`: the payload's key set must be a SUBSET of a permitted set --
    looser than equality, used where a payload legitimately varies in which of a
    known-safe set of keys it carries.

`assert_no_secrets` is the separate secret-leak guard, previously copy-pasted verbatim
across six scripts (check_schema_drift.py, check_tier_null_propagation.py,
probe_enum_in_formula.py, probe_number_floor_in_formula.py, snapshot_hubspot_schema.py,
sweep_tier_dependents.py); now a single implementation those six files' own
`_assert_no_secrets` wrappers delegate to, so every existing call site is unchanged.
"""
import json
import os
from pathlib import Path


def assert_disjoint(keys, forbidden, message: str) -> None:
    """Raise ValueError(message) unless `keys` and `forbidden` share no elements."""
    if not set(keys).isdisjoint(forbidden):
        raise ValueError(message)


def assert_keys_equal(keys, expected, message: str) -> None:
    """Raise ValueError(message) unless `keys` is EXACTLY `expected`."""
    if set(keys) != set(expected):
        raise ValueError(message)


def assert_keys_subset(keys, permitted, message: str) -> None:
    """Raise ValueError(message) unless `keys` is a subset of `permitted`."""
    if not set(keys) <= set(permitted):
        raise ValueError(message)


def assert_no_secrets(text: str) -> None:
    """Raise ValueError naming what leaked if `text` (a serialized artifact about to be
    written to disk or printed) carries a live bearer token, an Authorization header, or
    the token's own env var name."""
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN") or ""
    if "Authorization" in text:
        raise ValueError("serializer leaked the Authorization header")
    if token and token in text:
        raise ValueError("serializer leaked the bearer token value")
    if "HUBSPOT_PRIVATE_APP_TOKEN" in text:
        raise ValueError("serializer leaked the token env var name")


# --- guarded emit paths (Phase 50 security audit, 2026-09-03) ---------------------
# `assert_no_secrets` above is only a guard if something CALLS it. The 2026-09-03
# retroactive secure-phase run found five scripts whose threat registers asserted the
# check was applied to their committed artifacts, and which had never imported it:
# check_tier_derived_parity, apply_fit_score_formula, rollback_property_migration,
# put_hubspot_flow, backfill_anti_icp_flag_num (T-50-11 / T-50-27 / T-50-36). It was
# never-present rather than drift, so nothing would ever have caught it.
#
# These two wrappers make the guarded path the SHORTEST path: one call instead of a
# serialize-check-emit trio at every site. `tests/test_guarded_emit_coverage.py` pins
# that every script writing a committed artifact routes through one of them, so a sixth
# script cannot be added without the guard the way these five were.


def emit_json(obj, **dumps_kwargs) -> None:
    """`json.dumps` -> `assert_no_secrets` -> `print`. The guarded stdout path.

    stdout matters as much as a file here: these scripts' output is routinely captured
    into a committed run record, so a token reaching stdout reaches git.
    """
    text = json.dumps(obj, **dumps_kwargs)
    assert_no_secrets(text)
    print(text)


def write_guarded(path, text: str) -> None:
    """`assert_no_secrets` -> `write_text`. The guarded file path.

    Checks BEFORE writing, so a leak raises with nothing on disk rather than leaving a
    poisoned file behind for the caller to clean up.
    """
    assert_no_secrets(text)
    Path(path).write_text(text)
