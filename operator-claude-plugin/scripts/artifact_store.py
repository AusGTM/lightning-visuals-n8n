"""operator-claude-plugin/scripts/artifact_store.py

The plugin's ONLY persisted state: which dashboard Artifact to republish into, so a
refresh in a *new* session lands on the same URL the operator bookmarked (D-09a).
Same-conversation republishing is already automatic; cross-session sameness is the one
part that needs a memory, and this file is the whole of it.

D-09b bounds it on purpose — exactly an identifier and a timestamp, an
operator-configurable expiry defaulting to thirty days, collected on the next plugin
open. `save()` refuses any additional field rather than persisting it, because a store
that accepts arbitrary keys is a general-purpose store one commit later, and the first
thing parked in one would be the arming grant Phase 23 D-11 deliberately keeps off disk.

Every failure mode returns nothing rather than raising: a stale, missing, malformed or
half-written pointer all have the same effect — there is nothing to republish into — and
none of them is worth an error the operator has to read.

The filename is deliberately NOT a dotfile: dotfiles are unreadable to this
environment's tooling (Phase 23 D-04), so a dotfile store would be dead at runtime.

Reads and writes one local file. No network, no credential, no record identifier.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_PATH = PLUGIN_ROOT / "state" / "dashboard_artifact.json"

TTL_CONFIG_KEY = "dashboard_artifact_ttl_days"
DEFAULT_TTL_DAYS = 30

# The whole schema. Anything else is a rejection, not a widening.
ID_FIELD = "artifact_id"
STAMP_FIELD = "saved_at"


def state_path() -> Path:
    """Where the pointer lives. Gitignored, non-dotfile, inside the plugin."""
    return DEFAULT_STATE_PATH


def _resolve(path) -> Path:
    return Path(path) if path is not None else state_path()


def _ttl(config) -> timedelta:
    """Days from configuration, falling back to thirty. An unreadable setting falls back
    too — a typo in the config must not silently shorten the expiry to nothing."""
    raw = (config or {}).get(TTL_CONFIG_KEY, DEFAULT_TTL_DAYS)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return timedelta(days=DEFAULT_TTL_DAYS)
    return timedelta(days=max(float(raw), 0))


def _read(path) -> dict | None:
    """The two fields, or None. Extras on disk are dropped here and never propagate."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(document, dict):
        return None

    artifact_id = document.get(ID_FIELD)
    stamp = document.get(STAMP_FIELD)
    if not isinstance(artifact_id, str) or not artifact_id:
        return None
    if not isinstance(stamp, str):
        return None
    try:
        saved_at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if saved_at.tzinfo is None:
        saved_at = saved_at.replace(tzinfo=timezone.utc)

    return {ID_FIELD: artifact_id, STAMP_FIELD: saved_at}


def _expired(entry, config) -> bool:
    return datetime.now(timezone.utc) - entry[STAMP_FIELD] >= _ttl(config)


def load(config: dict | None = None, path=None) -> str | None:
    """The remembered identifier, or None when there is nothing usable to republish
    into — missing, malformed, half-written or past its expiry."""
    entry = _read(_resolve(path))
    if entry is None or _expired(entry, config):
        return None
    return entry[ID_FIELD]


def save(artifact_id: str, config: dict | None = None, path=None, **extra) -> None:
    """Remember one identifier and when it was remembered. Nothing else.

    `**extra` exists only to refuse: the plausible next commit is `save(id, url=...)`,
    and silently persisting it is how a two-field store becomes a general one (D-09b,
    T-27-22).
    """
    if extra:
        raise ValueError(
            f"artifact_store holds exactly {ID_FIELD} and {STAMP_FIELD}; refusing "
            f"{sorted(extra)}. Widening it needs a decision, not a keyword argument — "
            "see D-09b. The arming grant in particular stays off disk entirely."
        )
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        raise ValueError("artifact_id must be a non-empty string")

    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({
        ID_FIELD: artifact_id,
        STAMP_FIELD: datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")


def collect(config: dict | None = None, path=None) -> bool:
    """Delete an expired (or unusable) pointer; leave a live one alone. True if deleted.

    Runs when the skill opens rather than on a schedule — this client has no daemon and
    D-09b asks for collection on the next open.
    """
    target = _resolve(path)
    if not target.exists():
        return False

    entry = _read(target)
    if entry is not None and not _expired(entry, config):
        return False

    try:
        target.unlink()
    except OSError:
        return False
    return True


if __name__ == "__main__":
    import sys

    import config_gate

    _usage = {"ok": False, "error": "usage: artifact_store.py load|save <id>|collect"}
    _args = sys.argv[1:]
    if not _args or _args[0] not in ("load", "save", "collect"):
        print(json.dumps(_usage))
        raise SystemExit(1)

    try:
        _cfg = config_gate.load_config()
    except config_gate.ConfigError:
        # The pointer is local state; a missing config must not stop collection. The
        # status skill's own step 1 is what refuses in plain language.
        _cfg = {}

    if _args[0] == "load":
        print(json.dumps({"ok": True, "artifact_id": load(_cfg)}))
    elif _args[0] == "collect":
        print(json.dumps({"ok": True, "collected": collect(_cfg)}))
    elif len(_args) == 2:
        save(_args[1], _cfg)
        print(json.dumps({"ok": True, "artifact_id": _args[1]}))
    else:
        print(json.dumps(_usage))
        raise SystemExit(1)
