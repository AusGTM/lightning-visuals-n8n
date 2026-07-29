# tests/test_create_payload_identity.py
#
# BUG 19 — a `create` must write enough identity to be findable again.
#
# The create payload is {...merge.canonicalPatch, ...cacheKeys}, and the non-clobber policy
# classes `domain` (companies) and `email` (contacts) as manual_protected, so neither is
# ever promoted into canonicalPatch. That is correct for an UPDATE — never overwrite a
# human's identity value — and incoherent for a CREATE, where no record exists yet and the
# identity field is the one thing that must be written.
#
# Confirmed live 2026-07-29 against a throwaway company (created and deleted, re-read 404):
# POST returned 201 with name=None, domain=None, and a subsequent
# `domain EQ <domain>` search returned total=0 — meaning the record is invisible to the very
# search whose zero-result answer decided to create it. Every later run creates another.
#
# These tests are xfail(strict=True): they FAIL today, on purpose. When a lane is fixed they
# XPASS, which strict mode turns into an error — forcing whoever fixes it to promote the
# test to a real assertion rather than leaving a stale expectation behind.
# See .planning/debug/bug-19-create-omits-identity-fields.md.
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_cloud_workflows as B  # noqa: E402

# (constant name, lane description, the identity property a create MUST carry)
CREATE_LANES = [
    ("DECIDE_LOCAL", "contacts / local replica", "email"),
    ("DECIDE_CLOUD", "contacts / contact-ingest cloud", "email"),
    ("ENRICH_DECIDE_LOCAL", "contacts / enrichment local", "email"),
    ("ENRICH_DECIDE_CLOUD", "contacts / enrichment cloud", "email"),
    ("ENRICH_DECIDE_CO_CLOUD", "companies / enrichment cloud", "domain"),
]


#: The variables each decide node builds its outgoing HubSpot payload in. Scoping to these
#: matters: DECIDE_LOCAL echoes `email: row.email || null` at the TOP LEVEL of its row for
#: the dry-run display, which is NOT part of the patch sent to HubSpot. A predicate that
#: merely greps the source for "email:" reads that echo as a fix and reports the lane clean
#: — it did, on the first run of this test, and the lane is not clean.
PAYLOAD_VARS = ("patch", "properties")


def _assigns_identity_on_create(src: str, prop: str) -> bool:
    """Does this decide node ever put `prop` into the object it SENDS to HubSpot?

    Assignment onto the payload variable only — `patch.domain = ...` /
    `properties["email"] = ...`. Generous about form, strict about target."""
    for var in PAYLOAD_VARS:
        patterns = [
            rf"{var}\.{re.escape(prop)}\s*=",
            rf"{var}\[[\"']{re.escape(prop)}[\"']\]\s*=",
            rf"{var}\s*=\s*\{{[^}}]*\b{re.escape(prop)}\s*:",
        ]
        if any(re.search(p, src) for p in patterns):
            return True
    return False


@pytest.mark.parametrize("const,lane,prop", CREATE_LANES, ids=[c for c, _, _ in CREATE_LANES])
@pytest.mark.xfail(strict=True, reason="BUG 19: create omits the identity field; see .planning/debug/bug-19-create-omits-identity-fields.md")
def test_create_payload_carries_the_identity_field_that_makes_the_record_findable(const, lane, prop):
    src = getattr(B, const)
    assert "create" in src, f"{const} has no create branch — re-anchor this test"
    assert _assigns_identity_on_create(src, prop), (
        f"{const} ({lane}) builds its create payload from canonicalPatch only, which never "
        f"contains `{prop}` (manual_protected). A record created without `{prop}` cannot be "
        f"found by the search that gates creation, so every subsequent run creates another."
    )


def test_the_policy_classes_that_cause_bug_19_are_still_what_this_test_claims():
    """Anchor the diagnosis, not just the symptom. If someone reclassifies `domain`/`email`
    away from manual_protected, BUG 19 changes shape and the xfails above become misleading."""
    companies = (ROOT / "n8n" / "code" / "mergeCompanies.js").read_text()
    contacts = (ROOT / "n8n" / "code" / "mergeContacts.js").read_text()
    assert re.search(r"domain:\s*\{\s*class:\s*\"manual_protected\"", companies), \
        "company `domain` is no longer manual_protected — re-read BUG 19's root cause"
    assert re.search(r"email:\s*\{\s*class:\s*\"manual_protected\"", contacts), \
        "contact `email` is no longer manual_protected — re-read BUG 19's root cause"
    assert 'field === "email" && decision === "promote"' in contacts, \
        "the explicit email->stage_only hard-force is gone — re-read BUG 19's root cause"
