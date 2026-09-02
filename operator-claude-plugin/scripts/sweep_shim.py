"""operator-claude-plugin/scripts/sweep_shim.py

The stable launcher shim (D-63-01). A schedule (cron/launchd) that pins a versioned
plugin directory orphans or freezes on every plugin update — this module is the fix:
it installs a `/bin/sh` shim at a fixed durable path that never moves, and that shim
resolves the newest installed plugin version at every scheduled fire and `exec`s its
`lv-sweep-run.sh`. The schedule keeps pointing at the shim forever; only the shim's
OWN resolution changes what actually runs.

Version ordering is `durable_paths.py`'s, reused not reimplemented (D-63-04): this
module imports `durable_paths` and calls `durable_paths._VERSION_DIR_RE` /
`durable_paths._version_key` at call time (attribute access on the module, not a
`from ... import` copy) so a monkeypatch on `durable_paths` reaches this module too —
see `test_version_ordering_is_not_reimplemented`, the behavioural proof that this
isn't a second copy of the ordering logic.

No environment-variable override for the cache root: this script can run unattended
from a scheduler with no human present to notice an injected value, so the cache root
is always an explicit argument (`--cache-root` on the CLI, or baked into the shim
text at install time) — never read from the environment at run time.
"""
import argparse
import contextlib
from pathlib import Path

import durable_paths

SHIM_FILENAME = "lv-sweep-launcher.sh"

# `__CACHE_ROOT__` is replaced with a single-quoted shell literal in `shim_text()`.
# Structure mirrors `lv-sweep-run.sh`: `#!/bin/sh` + `set -u` (no `-e` — every command
# whose failure matters is checked explicitly so the shim can banner instead of dying
# silently), the same `banner()` helper verbatim, and the same "wrong argument count
# is loud" first check.
_SHIM_TEMPLATE = """#!/bin/sh
set -u

# LV backend sweep launcher shim — installed once at a durable path that never moves
# (D-63-01). Resolves the newest installed plugin version on every scheduled fire and
# execs its lv-sweep-run.sh, so a plugin update never orphans or freezes the schedule.
# Version ordering lives in exactly one place, durable_paths.py, reached via this
# shim's own `sweep_shim.py --newest` call below (D-63-04) — no dotted-version
# comparison lives in this file.

CACHE_ROOT=__CACHE_ROOT__

banner() {
    /usr/bin/osascript -e "display notification \\"$1\\" with title \\"LV Backend Sweep\\""
}

if [ "$#" -ne 3 ]; then
    banner "LV backend sweep launcher: cannot run - wrong number of arguments"
    exit 1
fi

# Bootstrap: find ANY install under the cache root that carries sweep_shim.py, so we
# have a python-importable copy of the real resolution logic to invoke. This pick is
# deliberately unordered (the first match wins) — ordering is `--newest`'s job below,
# not this loop's (T-63-A ordering probe).
BOOTSTRAP=""
for entry in "$CACHE_ROOT"/*; do
    if [ -f "$entry/scripts/sweep_shim.py" ]; then
        BOOTSTRAP="$entry"
        break
    fi
done

if [ -z "$BOOTSTRAP" ]; then
    banner "LV backend sweep launcher: could not resolve an install - ask the admin to check the log"
    exit 1
fi

NEWEST=$("$2" "$BOOTSTRAP/scripts/sweep_shim.py" --newest --cache-root "$CACHE_ROOT")
RC=$?

if [ "$RC" -ne 0 ] || [ -z "$NEWEST" ] || [ ! -f "$NEWEST/skills/backend-sweep/lv-sweep-run.sh" ]; then
    banner "LV backend sweep launcher: could not resolve an install - ask the admin to check the log"
    exit 1
fi

exec /bin/sh "$NEWEST/skills/backend-sweep/lv-sweep-run.sh" "$NEWEST" "$2" "$3"
"""


def newest_install_root(cache_root):
    """The newest version directory directly under `cache_root`, or `None`.

    Modeled on `durable_paths._newest_sibling_holding`'s candidate scan, with three
    differences: no current install is excluded (this answers "newest", not "newest
    OTHER"); a candidate must carry `skills/backend-sweep/lv-sweep-run.sh` (a
    version directory with no wrapper is not a usable target); and any entry whose
    resolved path escapes the resolved `cache_root` is skipped (T-63-01 — a symlink
    inside a user-writable cache root must not redirect the shim's `exec` target
    outside the plugin tree).

    An unreadable or nonexistent `cache_root` is the ordinary "nothing to resolve"
    case, not an error — the whole scan is wrapped in `contextlib.suppress(OSError)`,
    exactly like the analog.
    """
    cache_root = Path(cache_root)
    resolved_cache_root = cache_root.resolve()

    candidates = []
    with contextlib.suppress(OSError):
        for entry in cache_root.iterdir():
            if not entry.is_dir():
                continue
            if not durable_paths._VERSION_DIR_RE.match(entry.name):
                continue
            resolved_entry = entry.resolve()
            try:
                resolved_entry.relative_to(resolved_cache_root)
            except ValueError:
                continue  # symlink escapes the cache root — T-63-01
            if not (entry / "skills" / "backend-sweep" / "lv-sweep-run.sh").is_file():
                continue
            candidates.append(entry)

    # Deliberately OUTSIDE the suppress block above: a version-ordering failure (e.g.
    # a monkeypatched `_version_key` that raises) must propagate, not be swallowed
    # alongside a merely-unreadable directory.
    candidates.sort(key=lambda d: durable_paths._version_key(d.name), reverse=True)
    return candidates[0] if candidates else None


def shim_text(cache_root):
    """The `/bin/sh` shim source with `cache_root` baked in as a single-quoted shell
    literal assignment."""
    cache_root_str = str(Path(cache_root))
    quoted = "'" + cache_root_str.replace("'", "'\\''") + "'"
    return _SHIM_TEMPLATE.replace("__CACHE_ROOT__", quoted)


def shim_path(durable=None):
    """Where the shim lives: `durable_dir() / SHIM_FILENAME`, or `Path(durable) /
    SHIM_FILENAME` when `durable` is given (tests only)."""
    base = Path(durable) if durable is not None else durable_paths.durable_dir()
    return base / SHIM_FILENAME


def install_shim(cache_root=None, durable=None):
    """Write the shim to `shim_path(durable)`, creating its parent directory and
    setting mode `0o700`. `cache_root` defaults to `durable_paths.PLUGIN_ROOT.parent`
    — the installing install's own cache root, the value baked into the shim.
    Writing identical content twice leaves the file byte-identical (plain overwrite;
    no secret lives in this file, so no atomic-write dance is needed the way
    `durable_paths._atomic_write_0600` needs one for credentials).
    """
    if cache_root is None:
        cache_root = durable_paths.PLUGIN_ROOT.parent

    path = shim_path(durable)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(shim_text(cache_root), encoding="utf-8")
    path.chmod(0o700)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sweep_shim.py")
    verb = parser.add_mutually_exclusive_group(required=True)
    verb.add_argument("--newest", action="store_true", help="print the newest installed root")
    verb.add_argument("--install", action="store_true", help="write the shim to the durable home")
    parser.add_argument("--cache-root", default=None)
    parser.add_argument("--durable-dir", default=None)
    args = parser.parse_args(argv)

    if args.newest:
        if not args.cache_root:
            parser.error("--newest requires --cache-root")
        root = newest_install_root(args.cache_root)
        if root is None:
            return 1
        print(root)
        return 0

    path = install_shim(cache_root=args.cache_root, durable=args.durable_dir)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
