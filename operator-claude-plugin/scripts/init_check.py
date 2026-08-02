"""operator-claude-plugin/scripts/init_check.py

"Am I set up?" — the whole of `/operator-claude-plugin:initialize`'s machinery.

WHY THIS EXISTS. The one-time setup was documented in the README as "copy
config/operator.local.example.json to operator.local.json". An operator who installed the
plugin through the Desktop plugin manager has never seen that directory and has no reason
to know where it landed. This prints the ABSOLUTE path and says exactly which values are
still needed.

IT NEVER READS, ACCEPTS, PRINTS OR LOGS A SECRET. It reports whether each key is filled —
present / missing / still-a-placeholder — and nothing about what any value is. There is no
flag to display one and no code path that could. A setup helper that echoed a webhook
secret into a transcript would be a worse problem than the one it solved.

Idempotent by construction: run it any number of times. When everything is configured it
says so and changes nothing. `--create` writes the example file into place ONLY when no
config exists, and never overwrites — the placeholders it writes are not secrets.

Capability rows come from `config_gate.CAPABILITY_KEYS`, never a second list: a plugin
that gains a capability must not need this file edited to keep telling the truth.
"""
import argparse
import json
import shutil
import sys

import config_gate

# The example ships angle-bracket placeholders ("https://<your-subdomain>.n8n.cloud").
# A file full of those exists but is NOT configured, and reporting it as configured is the
# one failure this check has to avoid — it would send the operator on to a step that then
# fails with an auth error nobody can trace back to here.
PLACEHOLDER_MARKERS = ("<", ">")

STATUS_READY = "ready"
STATUS_NEEDS_VALUES = "needs_values"
STATUS_NO_FILE = "no_file"
STATUS_UNREADABLE = "unreadable"


def _is_placeholder(value) -> bool:
    if not isinstance(value, str):
        return False
    return any(marker in value for marker in PLACEHOLDER_MARKERS)


def _key_state(cfg, key):
    """`filled` / `missing` / `placeholder` — never the value itself."""
    value = (cfg or {}).get(key)
    if value is None or value == "":
        return "missing"
    if _is_placeholder(value):
        return "placeholder"
    return "filled"


def inspect(config_path=None) -> dict:
    """The whole setup picture, as data. No secret ever enters the return value."""
    path = config_path or config_gate.DEFAULT_CONFIG_PATH
    example = config_gate.PLUGIN_ROOT / "config" / config_gate.EXAMPLE_CONFIG_NAME

    report = {
        "config_path": str(path),
        "example_path": str(example),
        "exists": path.exists(),
        "keys": {},
        "capabilities": {},
        "status": STATUS_NO_FILE,
    }

    if not path.exists():
        return report

    try:
        cfg = json.loads(path.read_text())
        if not isinstance(cfg, dict):
            raise ValueError("the config file is not a JSON object")
    except (ValueError, UnicodeDecodeError) as e:
        report["status"] = STATUS_UNREADABLE
        report["detail"] = f"{path} could not be read as JSON: {e}"
        return report

    every_key = sorted({key for keys in config_gate.CAPABILITY_KEYS.values()
                        for key in keys})
    report["keys"] = {key: _key_state(cfg, key) for key in every_key}

    # A placeholder counts as unset for capability purposes — same as absent.
    effective = {key: value for key, value in cfg.items()
                 if not _is_placeholder(value)}
    for capability in config_gate.CAPABILITY_KEYS:
        missing = config_gate.missing_keys(effective, capability)
        report["capabilities"][capability] = {
            "ready": not missing,
            "needs": missing,
            "does": config_gate._CAPABILITY_DESCRIPTIONS.get(capability, capability),
        }

    report["status"] = (STATUS_READY
                        if all(row["ready"] for row in report["capabilities"].values())
                        else STATUS_NEEDS_VALUES)
    return report


def create_from_example(config_path=None) -> dict:
    """Put the example file in place. Never overwrites an existing config — the operator's
    filled-in values are not this command's to destroy."""
    path = config_path or config_gate.DEFAULT_CONFIG_PATH
    example = config_gate.PLUGIN_ROOT / "config" / config_gate.EXAMPLE_CONFIG_NAME

    if path.exists():
        return {"created": False, "reason": "a config file is already there — left alone",
                "config_path": str(path)}
    if not example.exists():
        return {"created": False, "reason": f"the example file is missing at {example}",
                "config_path": str(path)}

    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example, path)
    return {"created": True, "config_path": str(path),
            "reason": "copied from the example — the values in it are placeholders, "
                      "not secrets, and still need filling in"}


def render(report: dict) -> str:
    """Plain language for the operator. Names keys and paths; never a value."""
    lines = []
    path = report["config_path"]

    if report["status"] == STATUS_READY:
        lines.append("Setup is complete — nothing to do.")
        lines.append(f"Your settings file: {path}")
        lines.append("")
        lines.append("Everything is configured:")
        for name, row in sorted(report["capabilities"].items()):
            lines.append(f"  - {row['does']}: ready")
        return "\n".join(lines)

    if report["status"] == STATUS_NO_FILE:
        lines.append("Not set up yet — there is no settings file.")
        lines.append(f"It needs to be at: {path}")
        lines.append(f"There is a template to copy at: {report['example_path']}")
        lines.append("")
        lines.append("I can put the template in place for you; you then fill in two "
                     "values from your n8n admin.")
        return "\n".join(lines)

    if report["status"] == STATUS_UNREADABLE:
        lines.append("The settings file is there but cannot be read.")
        lines.append(report.get("detail", ""))
        lines.append("")
        lines.append("Most often this is a missing comma or quote. Fix the file at the "
                     "path above, or delete it and start again from the template.")
        return "\n".join(lines)

    lines.append("Almost set up — the settings file exists but some values are still "
                 "needed.")
    lines.append(f"Your settings file: {path}")
    lines.append("")
    lines.append("Values:")
    for key, state in sorted(report["keys"].items()):
        label = {"filled": "filled in",
                 "missing": "NOT SET — needs a value",
                 "placeholder": "still the template placeholder — needs your real value"}[state]
        lines.append(f"  - {key}: {label}")

    lines.append("")
    lines.append("What that means you can and cannot do:")
    for name, row in sorted(report["capabilities"].items()):
        if row["ready"]:
            lines.append(f"  - {row['does']}: ready")
        else:
            lines.append(f"  - {row['does']}: needs {', '.join(row['needs'])}")

    lines.append("")
    lines.append("Ask your n8n admin for those values. I never see them — you type them "
                 "into the file, not into this conversation.")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Check whether this plugin is configured. Never reads or prints a "
                    "secret value.")
    parser.add_argument("--create", action="store_true",
                        help="put the template config in place if none exists "
                             "(never overwrites)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    if args.create:
        outcome = create_from_example()
        if args.json:
            print(json.dumps(outcome, indent=2))
        else:
            print(outcome["reason"])
            print(f"Settings file: {outcome['config_path']}")

    report = inspect()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render(report))

    return 0 if report["status"] == STATUS_READY else 1


if __name__ == "__main__":
    sys.exit(main())
