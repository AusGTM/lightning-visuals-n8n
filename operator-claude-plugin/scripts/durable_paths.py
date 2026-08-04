"""operator-claude-plugin/scripts/durable_paths.py

Single authority for where per-operator state lives, so `config_gate.py` (the
credentials file) and `artifact_store.py` (the dashboard pointer) resolve identically
instead of each hardcoding its own path (33-CONTEXT.md's "second-source-of-truth pattern
this milestone avoids everywhere else").

Resolution order, first hit wins, identical shape for both files (33-CONTEXT.md
Contracts to Honor):
  1. explicit path argument (tests only — every existing test passes one)
  2. `LV_OPERATOR_CONFIG` env var (admin escape hatch)
  3. durable home (`${CLAUDE_PLUGIN_DATA}` or the computed equivalent)
  4. `PLUGIN_ROOT/config/operator.local.json` (legacy, same install)
  5. newest sibling install -> migrate to (3), once.

Step 5 (33-02) is the only step that performs I/O beyond an `.exists()` check: it reads
a sibling install's copy, writes it into the durable home atomically at 0600, and
deletes the sibling's copy only after a verified read-back. It is gated by
`allow_migration` (default `True`) so a caller that must never trigger it — the
unattended sweep, see `sweep_entry._load_config_no_migration` — can resolve read-only
and degrade to the legacy return instead.
"""
import contextlib
import os
import re
import tempfile
from pathlib import Path

# The harness's own plugin id with `@` -> `-`, per the documented `${CLAUDE_PLUGIN_DATA}`
# substitution rule. Verified against the official plugins reference AND against this
# machine's own install manifest (`pluginId: operator-claude-plugin@lightning-visuals-operator`)
# — 33-RESEARCH.md Finding 1. The env-override and legacy fallback below exist per D-3 in
# case the convention shifts, not because this string is a guess.
PLUGIN_ID = "operator-claude-plugin-lightning-visuals-operator"

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILENAME = "operator.local.json"
STATE_FILENAME = "dashboard_artifact.json"


_VERSION_DIR_RE = re.compile(r"^\d+(\.\d+)*$")


def _version_key(name: str) -> tuple:
    """Sorts numeric dotted-version directory names correctly (`0.10.0` above `0.9.0`,
    where plain string comparison gets it backwards). Only ever called on names that
    `_VERSION_DIR_RE` already matched — the filtering happens BEFORE the sort, in
    `_newest_sibling_holding`, not here. A mixed `int`/`str` tuple comparison raises
    `TypeError` in Python 3, which `config_gate`'s `ConfigError` wrapping does not
    catch, so a stray non-version directory name in the cache root must never reach
    this function; if the filter ahead of it is ever removed, this raises instead of
    silently misordering, which is the correct failure for that bug.
    """
    return tuple(int(part) for part in name.split("."))


def _atomic_write_0600(path: Path, content: str) -> None:
    """Write `content` to `path` so the file is never observable partially written or
    at a permissive mode — the final path is either absent, or present, complete, and
    `0600`. Pattern: tempfile in the target's OWN directory, chmod 0600, fsync,
    `os.replace` (33-RESEARCH.md Finding 3 — `O_CREAT|O_EXCL` alone leaves a
    zero-byte-but-correctly-permissioned window a crashed migration could leave
    behind).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # `dir=` must stay the target's own parent directory: os.replace is atomic only
    # within one filesystem, and moving the temp file to a system temp directory in a
    # later refactor would silently reintroduce the partial-write window this whole
    # pattern exists to close.
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".")
    try:
        os.chmod(tmp_name, 0o600)  # defensive — mkstemp already defaults to 0600 on POSIX
        with os.fdopen(fd, "w") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def _newest_sibling_holding(relative: Path) -> Path | None:
    """The newest sibling install directory under this plugin's cache root whose copy
    of `relative` (e.g. `config/operator.local.json`) actually exists and is readable
    — not merely the newest-NAMED directory. Excludes the current install
    (`PLUGIN_ROOT`) by RESOLVED-PATH equality, not by version-string comparison: a
    name-based check plus any future change to how `PLUGIN_ROOT` is computed is how the
    current install's own live credential file ends up treated as a migration source
    (33-RESEARCH.md Pitfall 3).

    A cache root that does not exist or is unreadable is the ordinary "fresh install,
    nothing to migrate" case — not an error — hence the whole scan is wrapped in
    `contextlib.suppress(OSError)`. In a repo checkout (this project's own dev
    environment), `cache_root` is the repository root, which holds no directories
    matching the version regex, so the scan is a silent no-op there too.
    """
    cache_root = PLUGIN_ROOT.parent
    here = PLUGIN_ROOT.resolve()

    candidates = []
    with contextlib.suppress(OSError):
        for entry in cache_root.iterdir():
            if not entry.is_dir():
                continue
            if not _VERSION_DIR_RE.match(entry.name):
                continue
            if entry.resolve() == here:
                continue
            candidates.append(entry)

    candidates.sort(key=lambda d: _version_key(d.name), reverse=True)

    for candidate in candidates:
        if (candidate / relative).is_file():
            return candidate

    return None


def durable_dir() -> Path:
    """Where per-operator state lives, independent of which install directory is running.

    Prefers `CLAUDE_PLUGIN_DATA` when the harness has set it (hook/MCP/LSP subprocesses
    only, per the docs — not the plain `python3 scripts/...` invocation this plugin's
    skills actually use, so the computed branch is the one normally taken). An empty
    string is treated as unset, not as the current directory.
    """
    env = os.environ.get("CLAUDE_PLUGIN_DATA")
    if env:
        return Path(env)
    return Path.home() / ".claude" / "plugins" / "data" / PLUGIN_ID


def resolve_config_path(explicit: str | Path | None = None, allow_migration: bool = True) -> Path:
    """The single config-resolution authority. See module docstring for the order.

    `allow_migration=False` skips step 5 entirely (no sibling read, no write, no
    delete) and returns the legacy path instead — the unattended sweep's read-only
    contract; see `sweep_entry._load_config_no_migration`.
    """
    if explicit is not None:
        return Path(explicit)

    env_override = os.environ.get("LV_OPERATOR_CONFIG")
    if env_override:
        return Path(env_override)

    durable = durable_dir() / CONFIG_FILENAME
    if durable.exists():
        return durable

    legacy = PLUGIN_ROOT / "config" / CONFIG_FILENAME
    if legacy.exists():
        return legacy

    if allow_migration:
        try:
            # Task 1: copy only, from the newest sibling that holds one. Task 3
            # replaces this with `_migrate_once`, which also verifies the copy and
            # deletes the sibling's source — deliberately not done here yet.
            source_dir = _newest_sibling_holding(Path("config") / CONFIG_FILENAME)
            if source_dir is not None:
                text = (source_dir / "config" / CONFIG_FILENAME).read_text(encoding="utf-8")
                _atomic_write_0600(durable, text)
                return durable
        except OSError:
            pass

    return legacy


def resolve_state_path(explicit: str | Path | None = None, allow_migration: bool = True) -> Path:
    """Same order as `resolve_config_path`, for the dashboard-artifact pointer.

    Step 2 reads the SAME `LV_OPERATOR_CONFIG` variable, resolved as a sibling of
    whatever file it names (`Path(env_value).parent / STATE_FILENAME`) rather than
    inventing a second env var: the escape hatch means "operator state lives here", and
    an admin who redirects the config while the pointer stays put would be a surprise,
    not a feature.

    `allow_migration=False` skips step 5, same contract as `resolve_config_path`.
    """
    if explicit is not None:
        return Path(explicit)

    env_override = os.environ.get("LV_OPERATOR_CONFIG")
    if env_override:
        return Path(env_override).parent / STATE_FILENAME

    durable = durable_dir() / STATE_FILENAME
    if durable.exists():
        return durable

    legacy = PLUGIN_ROOT / "state" / STATE_FILENAME
    if legacy.exists():
        return legacy

    if allow_migration:
        try:
            # Task 1: copy only — see the identical comment in resolve_config_path.
            source_dir = _newest_sibling_holding(Path("state") / STATE_FILENAME)
            if source_dir is not None:
                text = (source_dir / "state" / STATE_FILENAME).read_text(encoding="utf-8")
                _atomic_write_0600(durable, text)
                return durable
        except OSError:
            pass

    return legacy
