"""operator-claude-plugin/scripts/config_gate.py

Loads and validates the plugin's local config before any network call is made. Refuses
in plain language rather than letting a raw parser/socket error reach the operator
(D-06, PLUGIN-03). Never interpolates a secret value into any message.
"""
import json
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PLUGIN_ROOT / "config" / "operator.local.json"
EXAMPLE_CONFIG_NAME = "operator.local.example.json"

WEBHOOK_PATH = "webhook/hubspot/contact-upload"

_SETUP_HINT = (
    f"Copy config/{EXAMPLE_CONFIG_NAME} to config/operator.local.json and fill it in "
    "once — the n8n_url and webhook_secret values come from your n8n admin."
)


class ConfigError(Exception):
    """Raised when the plugin's local config is missing or invalid.

    Never carries a secret value in its message — only names of missing/invalid keys
    and where to fix them.
    """


def load_config(path: str | Path | None = None) -> dict:
    """Load and validate the plugin's local config.

    Defaults to the real operator config path; tests pass an explicit ``path`` instead
    of touching the real (gitignored) file.
    """
    cfg_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH

    if not cfg_path.exists():
        raise ConfigError(f"Configuration file not found at {cfg_path}. {_SETUP_HINT}")

    try:
        with cfg_path.open(encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError:
        raise ConfigError(
            f"Configuration file at {cfg_path} could not be parsed as JSON. {_SETUP_HINT}"
        ) from None

    n8n_url = cfg.get("n8n_url")
    if not n8n_url:
        raise ConfigError(f"'n8n_url' is not configured. {_SETUP_HINT}")
    if not str(n8n_url).startswith("https://"):
        raise ConfigError(f"'n8n_url' must be an https:// URL. {_SETUP_HINT}")

    if not cfg.get("webhook_secret"):
        raise ConfigError(f"'webhook_secret' is not configured. {_SETUP_HINT}")

    return cfg


def describe_target(cfg: dict) -> str:
    """The full endpoint this plugin will POST to. Never includes the secret."""
    return f"{cfg['n8n_url'].rstrip('/')}/{WEBHOOK_PATH}"


if __name__ == "__main__":
    try:
        _cfg = load_config()
    except ConfigError as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)
    print(json.dumps({"ok": True, "target": describe_target(_cfg)}))
