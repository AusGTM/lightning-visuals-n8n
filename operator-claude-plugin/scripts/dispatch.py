"""operator-claude-plugin/scripts/dispatch.py

The only network call this plugin makes: a multipart POST to the deployed
`hubspot/contact-upload` webhook. `armed` has NO default — a caller that forgets it gets
a TypeError, never a silent send (D-11, D-13, T-23-01). Nothing about the grant is
persisted anywhere; it exists only as this call's argument.
"""
import json

import requests

import config_gate
import tabular


class NotArmedError(Exception):
    """Raised when dispatch is attempted without the operator's arming phrase spoken
    this turn."""


class DispatchError(Exception):
    """Raised when the transport itself fails. Never echoes the raw transport
    exception's text, which can carry request headers (T-23-09)."""


def dispatch(file_path, armed, config, transport=requests.post):
    if not armed:
        raise NotArmedError(
            "Live writes are off for this conversation — nothing was sent. Say the "
            "arming phrase to turn sending on for this conversation only."
        )

    csv_bytes = tabular.to_csv_bytes(file_path)
    url = config_gate.describe_target(config)
    headers = {"X-Enrichment-Secret": config["webhook_secret"]}
    files = {"data": ("contacts.csv", csv_bytes, "text/csv")}

    try:
        response = transport(url, headers=headers, files=files, timeout=30)
    except Exception:
        raise DispatchError(
            "Could not reach the n8n webhook. Check the connection and try again, or "
            "ask an admin to check the n8n Cloud instance if this persists."
        ) from None

    try:
        return response.json()
    except Exception:
        return {
            "status_code": getattr(response, "status_code", None),
            "text": getattr(response, "text", None),
        }


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3 or sys.argv[2] not in ("armed", "disarmed"):
        print(json.dumps({"ok": False, "error": "usage: dispatch.py <path> armed|disarmed"}))
        raise SystemExit(1)

    _file_path, _armed = sys.argv[1], sys.argv[2] == "armed"

    try:
        _cfg = config_gate.load_config()
    except config_gate.ConfigError as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    try:
        _result = dispatch(_file_path, _armed, _cfg)
    except (NotArmedError, DispatchError, tabular.UnsupportedFileError, OSError) as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    print(json.dumps({"ok": True, "response": _result}))
