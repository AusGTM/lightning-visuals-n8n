"""Pure-function checks for scripts/uat_reset.py (no network): domain normalisation, the
`uat.` / `uat-` contact marker, and the createdate >= --since window."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import uat_reset  # noqa: E402


def test_self_test_assertions_hold():
    assert uat_reset.self_test() == 0


def test_linkedin_and_freemail_never_become_company_domains():
    assert uat_reset.normalize_domain("https://www.linkedin.com/company/x/") == ""
    assert uat_reset.normalize_domain("https://facebook.com/x") == ""
    assert uat_reset.normalize_domain("outlook.com") == ""
