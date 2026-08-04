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
  5. newest sibling install -> migrate to (3) — 33-02's work, not implemented here.

Step 5 is deliberately absent from this module. When it lands, it is inserted between
steps 4 and the final legacy-path return below.
"""
import os
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


def resolve_config_path(explicit: str | Path | None = None) -> Path:
    """The single config-resolution authority. See module docstring for the order."""
    if explicit is not None:
        return Path(explicit)

    env_override = os.environ.get("LV_OPERATOR_CONFIG")
    if env_override:
        return Path(env_override)

    durable = durable_dir() / CONFIG_FILENAME
    if durable.exists():
        return durable

    # step 5 (sibling scan + migrate to `durable`) is inserted here — 33-02.
    return PLUGIN_ROOT / "config" / CONFIG_FILENAME


def resolve_state_path(explicit: str | Path | None = None) -> Path:
    """Same order as `resolve_config_path`, for the dashboard-artifact pointer.

    Step 2 reads the SAME `LV_OPERATOR_CONFIG` variable, resolved as a sibling of
    whatever file it names (`Path(env_value).parent / STATE_FILENAME`) rather than
    inventing a second env var: the escape hatch means "operator state lives here", and
    an admin who redirects the config while the pointer stays put would be a surprise,
    not a feature.
    """
    if explicit is not None:
        return Path(explicit)

    env_override = os.environ.get("LV_OPERATOR_CONFIG")
    if env_override:
        return Path(env_override).parent / STATE_FILENAME

    durable = durable_dir() / STATE_FILENAME
    if durable.exists():
        return durable

    # step 5 (sibling scan + migrate to `durable`) is inserted here — 33-02.
    return PLUGIN_ROOT / "state" / STATE_FILENAME
