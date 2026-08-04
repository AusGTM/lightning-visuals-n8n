"""operator-claude-plugin/scripts/config_gate.py

Loads and validates the plugin's local config before any network call is made. Refuses
in plain language rather than letting a raw parser/socket error reach the operator
(D-06, PLUGIN-03). Never interpolates a secret value into any message.
"""
import json
from pathlib import Path

import durable_paths

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_CONFIG_NAME = "operator.local.example.json"

WEBHOOK_PATH = "webhook/hubspot/contact-upload"

_SETUP_HINT = (
    f"The n8n_url and webhook_secret values come from your n8n admin — "
    f"{EXAMPLE_CONFIG_NAME} shows the shape, and /operator-claude-plugin:initialize "
    "prints the exact path to put them at."
)


def config_path() -> Path:
    """Where the operator's config actually is, resolved fresh on every call (not a
    module-level constant) — 33-02's migration can create the durable file mid-run."""
    return durable_paths.resolve_config_path()


# What each capability needs, rather than one global all-or-nothing gate: a plugin
# missing the read-only API key can still upload contacts, and saying "broken" when one
# capability is unconfigured is exactly the over-refusal PLUGIN-03 forbids.
#
# Note the status capability does NOT list webhook_secret. Losing that secret costs only
# the backend-supplied half of the status answer (balances, HubSpot counts), which
# reports itself unavailable — the workflow and execution half still answers.
# Control needs the same two keys status needs but is a SEPARATE capability on purpose: a
# config that may read the backend is not thereby one that may mutate it, so "read-only
# plugin" stays expressible by withholding the row rather than by convention (D-29).
# Review takes the same two keys contact-upload takes, and is a SEPARATE row for the same
# reason control is separate from status (D-29): a config that may read the review queue is
# not thereby one that may upload contacts, so a review-only config stays expressible by
# withholding a row rather than by convention (30 D-18).
# Enrichment takes the same two keys contact-upload takes and is its own row for the same
# reason: it POSTs to a different webhook path than contact-upload (SKILL.md: "different
# path from the contact-upload lane"), so reusing the contact-upload row would refuse an
# enrich request with "uploading contacts" wording, which is wrong.
CAPABILITY_KEYS = {
    "contact-upload": ("n8n_url", "webhook_secret"),
    "status": ("n8n_url", "n8n_api_key"),
    "control": ("n8n_url", "n8n_api_key"),
    "review": ("n8n_url", "webhook_secret"),
    "enrichment": ("n8n_url", "webhook_secret"),
    # The sweep runs UNATTENDED (29-03, D-15) — its own row so an admin can decline to
    # enable it without disabling the interactive status check. All three keys on
    # purpose: `status` degrades to the half it can read, but a sweep that can only read
    # half the conditions stays quiet about the other half, and quiet is a claim.
    "sweep": ("n8n_url", "n8n_api_key", "webhook_secret"),
}

_CAPABILITY_DESCRIPTIONS = {
    "contact-upload": "uploading contacts",
    "status": "the backend status check",
    "control": "turning workflows on or off",
    "review": "reading the review queue",
    "enrichment": "enriching records",
    "sweep": "the unattended backend sweep",
}


class ConfigError(Exception):
    """Raised when the plugin's local config is missing or invalid.

    Never carries a secret value in its message — only names of missing/invalid keys
    and where to fix them.
    """


def load_config(path: str | Path | None = None) -> dict:
    """Load and validate the plugin's local config.

    Defaults to the real operator config path; tests pass an explicit ``path`` instead
    of touching the real (gitignored) file.

    Enforces only `n8n_url` — the one key every capability in `CAPABILITY_KEYS` needs.
    Anything else (`webhook_secret`, `n8n_api_key`) is capability-specific and is gated by
    `require_capability()` at the entrypoint or library function that actually needs it,
    not here: a global check on a key only some capabilities use is the over-refusal
    PLUGIN-03 forbids (a blank `webhook_secret` used to take down the whole status read).
    """
    cfg_path = Path(path) if path is not None else config_path()

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

    return cfg


def missing_keys(cfg: dict, capability: str) -> list:
    """Which of a capability's required keys are absent or empty. Names only."""
    if capability not in CAPABILITY_KEYS:
        raise ValueError(f"unknown capability: {capability!r}")
    return [key for key in CAPABILITY_KEYS[capability] if not (cfg or {}).get(key)]


def usable_capabilities(cfg: dict) -> list:
    """Every capability this config can actually perform right now."""
    return [name for name in CAPABILITY_KEYS if not missing_keys(cfg, name)]


def require_capability(cfg: dict, capability: str) -> None:
    """Refuse ONE capability in plain language, before any transport is constructed.

    Names the missing key and where to fix it, states which capabilities still work, and
    never interpolates a configured value into the message (T-27-12).
    """
    missing = missing_keys(cfg, capability)
    if not missing:
        return

    still_works = [name for name in usable_capabilities(cfg) if name != capability]
    remainder = (
        f"Everything else still works: {', '.join(still_works)}."
        if still_works else
        "No other capability is configured either — start from the setup steps above."
    )
    raise ConfigError(
        f"{_CAPABILITY_DESCRIPTIONS.get(capability, capability)} needs "
        f"{', '.join(repr(key) for key in missing)}, which is not configured. Add it to "
        f"operator.local.json — {EXAMPLE_CONFIG_NAME} shows the shape, and "
        f"your n8n admin has the value. {remainder}"
    )


def describe_target(cfg: dict) -> str:
    """The full endpoint this plugin will POST to. Never includes the secret."""
    return f"{cfg['n8n_url'].rstrip('/')}/{WEBHOOK_PATH}"


if __name__ == "__main__":
    # The contact-upload lane's preflight. It reports SEND-READINESS rather than refusing:
    # previewing needs no secret and is genuinely useful without one (the same reasoning
    # review_decision.py:217 applies to its own dry run — "gating the preview would remove
    # the display the arm exists to protect"). But an operator who cannot send must be told
    # so BEFORE they read a preview and reach for the arming phrase, which is what happened
    # in the UAT 1.2 re-walk. So: `ok` stays true when the config loads, and `can_send`
    # carries the capability verdict separately.
    try:
        _cfg = load_config()
    except ConfigError as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    try:
        require_capability(_cfg, "contact-upload")
        _can_send, _blocked = True, None
    except ConfigError as _e:
        _can_send, _blocked = False, str(_e)
    print(json.dumps({"ok": True, "target": describe_target(_cfg),
                      "can_send": _can_send, "send_blocked_reason": _blocked}))
