# tests/test_committed_bodies_ship_disarmed.py
#
# Phase 75, T-75-25 / D-75-17: every committed cloud body must ship every
# ALLOW_HUBSPOT_* write-safety constant "false", including the Phase 75 addition
# ALLOW_HUBSPOT_RECOMPUTE_WRITES (D-75-16). No existing test asserted this against the
# COMMITTED n8n/wf_*.json artifacts directly (tests/test_recompute_flag_isolation.py,
# tests/test_builder_flag_parity.py and tests/test_deploy_flag_overlay.py all assert the
# builder constant or a synthetic workflow, never every committed body on disk) -- this
# fails RED if a commit ever ships an armed write-safety flag.
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
N8N_DIR = ROOT / "n8n"

FLAGS = [
    "ALLOW_HUBSPOT_RECORD_WRITES",
    "ALLOW_HUBSPOT_CREATE",
    "ALLOW_HUBSPOT_REVIEW_WRITES",
    "ALLOW_HUBSPOT_RECOMPUTE_WRITES",
]

WORKFLOW_FILES = sorted(N8N_DIR.glob("wf_*.json"))


@pytest.mark.parametrize("wf_path", WORKFLOW_FILES, ids=lambda p: p.name)
@pytest.mark.parametrize("flag", FLAGS)
def test_committed_body_never_bakes_flag_true(wf_path, flag):
    text = wf_path.read_text()
    # every declared jsCode occurrence of `const <FLAG> = "true"` (or `="true"`, no space)
    armed = re.search(rf'{re.escape(flag)}\s*=\s*"true"', text)
    assert armed is None, (
        f"{wf_path.name} bakes {flag} = \"true\" -- committed cloud bodies must ship "
        "disarmed (D-75-17); flip live only via the operator's supervised overlay, never "
        "in the committed JSON."
    )


def test_workflow_files_found():
    # guards the parametrize glob itself: an empty n8n/ dir would make every test above
    # vacuously pass.
    assert WORKFLOW_FILES, "no n8n/wf_*.json files found -- check N8N_DIR"


if __name__ == "__main__":
    # ponytail: one runnable self-check without pytest, in case pytest isn't on PATH.
    ok = True
    for wf in WORKFLOW_FILES:
        text = wf.read_text()
        for flag in FLAGS:
            if re.search(rf'{re.escape(flag)}\s*=\s*"true"', text):
                print(f"FAIL: {wf.name} bakes {flag} = true")
                ok = False
    assert WORKFLOW_FILES, "no workflow files found"
    print("OK" if ok else "FAILURES ABOVE")
    assert ok
