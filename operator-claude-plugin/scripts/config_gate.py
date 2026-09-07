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


def config_path(allow_migration: bool = True) -> Path:
    """Where the operator's config actually is, resolved fresh on every call (not a
    module-level constant) — 33-02's migration can create the durable file mid-run.

    `allow_migration=False` skips the sibling-scan-and-migrate step entirely — used by
    the unattended sweep (`sweep_entry._load_config_no_migration`), which must never
    perform the irreversible delete that step's migration can trigger with nobody
    watching (test_sweep_read_only.py's filesystem-write guard)."""
    return durable_paths.resolve_config_path(allow_migration=allow_migration)


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
# Match takes the same two keys enrichment takes — it POSTs to the SAME webhook path — but
# is its own row for the same reason: match spends nothing and writes nothing (37-CONTEXT
# §7), and a refusal that printed enrichment wording ("enriching records") would tell the
# operator they were about to spend money on a call that spends none.
CAPABILITY_KEYS = {
    "contact-upload": ("n8n_url", "webhook_secret"),
    "status": ("n8n_url", "n8n_api_key"),
    "control": ("n8n_url", "n8n_api_key"),
    "review": ("n8n_url", "webhook_secret"),
    "enrichment": ("n8n_url", "webhook_secret"),
    "match": ("n8n_url", "webhook_secret"),
    # The sweep runs UNATTENDED (29-03, D-15) — its own row so an admin can decline to
    # enable it without disabling the interactive status check. All three keys on
    # purpose: `status` degrades to the half it can read, but a sweep that can only read
    # half the conditions stays quiet about the other half, and quiet is a claim.
    "sweep": ("n8n_url", "n8n_api_key", "webhook_secret"),
    # WINDOWS.md #2's scheduled-arm companion (fix-40 ad-hoc, scheduled_arm.py) — its own
    # row for the same reason `sweep` has one (D-29): it runs unattended too, and needs
    # BOTH `n8n_api_key` (read SJ-3's matched batch off n8n's execution history, arm/
    # disarm the write-safety gate) AND `webhook_secret` (the same external dispatch POST
    # `enrichment`'s row already gates) — a config that may only read (`control`/`status`)
    # is not thereby one that may also arm and dispatch.
    "scheduled-arm": ("n8n_url", "n8n_api_key", "webhook_secret"),
}

_CAPABILITY_DESCRIPTIONS = {
    "contact-upload": "uploading contacts",
    "status": "the backend status check",
    "control": "turning workflows on or off",
    "review": "reading the review queue",
    "enrichment": "enriching records",
    "match": "looking up existing HubSpot matches",
    "sweep": "the unattended backend sweep",
    "scheduled-arm": "the scheduled-arm companion (SJ-3 poller write window)",
}


# --- the write-grant settings key (53-01, D-53-01) ---------------------------------------
#
# NOT a capability row, and deliberately NOT in CAPABILITY_KEYS or
# _CAPABILITY_DESCRIPTIONS above. `CAPABILITY_KEYS` means "these keys are PRESENT" — a
# missing entry there says the plugin is unconfigured for something. This key means "an
# admin AUTHORIZED live writes to be opened from a conversation", which is a different
# claim, and the refusal wording depends on the distinction. Living in the same MODULE as
# CAPABILITY_KEYS is not the same as living in the table; a later edit that folds it in is
# pinned as a failure by tests/test_write_grant.py.
#
# This is the repository's FIRST deliberate exception to "authority gates are environment
# variables compared against the exact string 'true'" (D-34). The probe, deploy and
# headless-arm gates stay environment-gated; only the interactive arm moved here, because
# an operator in Claude Desktop cannot set a shell variable (G-2, live UAT 2026-08-25).
WRITE_GRANT_SETTINGS_KEY = "allow_write_grants"


def write_grants_enabled(config: dict) -> bool:
    """True only when the admin set the key to the JSON boolean `true`.

    The ONE definition of this comparison — `n8n_arming` and `write_grant` both import it
    rather than restating it, so there are no two copies to hold in agreement.

    Identity (`is True`), not truthiness, and the reason is the same gotcha
    `n8n_cadence._read_positive_float`'s WR-03 comment documents: `bool` is an `int`
    subclass in Python, so a truthiness test would accept the string "true", the string
    "yes", the integer 1 and the float 1.0 as authority. This key REPLACES an exact-string
    comparison on the interactive path; a `1` that parsed as authority would make the new
    gate silently weaker than the one it replaced.
    """
    return (config or {}).get(WRITE_GRANT_SETTINGS_KEY) is True


# --- the autonomy levels (67-01, D-67-01/D-67-02/D-67-03) ---------------------------------
#
# NOT an authority gate. `autonomy_enabled` decides only whether an action ALREADY
# authorised by `write_grants_enabled` (interactive) or `ALLOW_N8N_ARM` (headless, an
# environment variable read only by n8n_arming.py / scheduled_arm.py — never imported
# here) proceeds without asking. Naming these three levels adds no new authority
# (D-67-02); a settings key here can never arm a live write by itself.
#
# Deliberately NOT `write_grants_enabled`'s identity-on-absence shape. That function's
# `is True` check means "absent -> False" and is reserved for AUTHORITY gates, where
# absence must never be read as permission. This key is the opposite kind of default: an
# existing install with no `autonomy` object at all must read every level as ON
# (D-67-03/D-67-10 — an update moves an install to the new defaults without anything
# being written into its file). Do NOT "fix" the absence branch below into
# `write_grants_enabled`'s shape; that would silently violate D-67-03.
#
# The near-miss rule differs from `write_grants_enabled`'s in DIRECTION, not in spirit:
# an authority gate fails toward not-authorised on a near miss; this default-setter
# fails toward ASKING on a near miss (Task 1's recorded answer, b-near-miss-asks) — only
# the JSON boolean `true`, or the level being absent from a present `autonomy` object,
# reads as ON. Every other value (`"true"`, `"false"`, `0`, `1`, `"yes"`, an explicit
# `null`) reads OFF, i.e. that round asks first rather than proceeding silently.
AUTONOMY_SETTINGS_KEY = "autonomy"
AUTONOMY_LEVELS = ("read_only", "spend_no_write", "write")  # D-67-01 — three, independent


def autonomy_enabled(config: dict, level: str) -> bool:
    """Whether `level` may proceed without asking, once already authorised elsewhere.

    Pure and repeatable (D-67-02): never touches disk or the network, and two calls on
    the same config dict return the same value without mutating it.

    - `level` not in `AUTONOMY_LEVELS` raises `ValueError` naming it.
    - No `autonomy` object in `config` at all (or `config` itself is falsy/`None`) ->
      `True` for every level (D-67-03: absence reads as ON here).
    - An `autonomy` object present but not a `dict` (e.g. `{"autonomy": true}`, a bare
      boolean where the object belongs) -> `False` for every level. A malformed config
      degrades to asking rather than raising mid-batch (b-malformed-off).
    - Otherwise: `True` only when the level is absent from the object, or explicitly the
      JSON boolean `true`. Every other value, including an explicit `null`, is `False`.
    """
    if level not in AUTONOMY_LEVELS:
        raise ValueError(f"unknown autonomy level: {level!r}. Valid levels: {AUTONOMY_LEVELS}")
    cfg = config or {}
    if AUTONOMY_SETTINGS_KEY not in cfg:
        return True
    parent = cfg[AUTONOMY_SETTINGS_KEY]
    if not isinstance(parent, dict):
        # Covers both a bare boolean (`{"autonomy": true}`) AND an explicit `null`
        # (`{"autonomy": null}`) — `.get()` alone can't tell "key absent" from
        # "key present with value null" (CR-01, 67-REVIEW), so membership is checked
        # above before this branch ever sees a null parent.
        return False
    return parent.get(level, True) is True


class ConfigError(Exception):
    """Raised when the plugin's local config is missing or invalid.

    Never carries a secret value in its message — only names of missing/invalid keys
    and where to fix them.
    """


def load_config(path: str | Path | None = None, allow_migration: bool = True) -> dict:
    """Load and validate the plugin's local config.

    Defaults to the real operator config path; tests pass an explicit ``path`` instead
    of touching the real (gitignored) file.

    Enforces only `n8n_url` — the one key every capability in `CAPABILITY_KEYS` needs.
    Anything else (`webhook_secret`, `n8n_api_key`) is capability-specific and is gated by
    `require_capability()` at the entrypoint or library function that actually needs it,
    not here: a global check on a key only some capabilities use is the over-refusal
    PLUGIN-03 forbids (a blank `webhook_secret` used to take down the whole status read).

    `allow_migration=False` resolves read-only — see `config_path()`.
    """
    cfg_path = Path(path) if path is not None else config_path(allow_migration=allow_migration)

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
