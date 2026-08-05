# tests/test_create_payload_identity.py
#
# BUG 19 (FIXED) — a `create` must write enough identity to be findable again.
#
# The create payload is {...merge.canonicalPatch, ...cacheKeys}, and the non-clobber policy
# classes `domain` (companies) and `email` (contacts) as manual_protected, so neither is
# ever promoted into canonicalPatch. Correct for an UPDATE — never overwrite a human's
# identity value — and incoherent for a CREATE, where no record exists yet and identity is
# the one thing that must be written.
#
# Confirmed live 2026-07-29 against a throwaway company (created and deleted, re-read 404):
# POST returned 201 with name=None/domain=None, and the `domain EQ` search whose zero-result
# answer had just decided "create" returned total=0 against the new record — so every later
# run re-creates it. Unbounded duplicates.
#
# Fix: each decide node seeds identity from its lane's own row onto the payload, on the
# create branch ONLY — seeding on enrich/update would be exactly the clobber the
# manual_protected class exists to prevent. These were xfail(strict=True) pins while the
# bug was open; strict XPASS forced this promotion when the lanes were fixed.
# History: .planning/debug/bug-19-create-omits-identity-fields.md.
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
#: merely greps the source for "email:" reads that echo as a fix — it did, on this test's
#: first run while the bug was open, and would have halved the reported blast radius.
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
def test_create_payload_carries_the_identity_field_that_makes_the_record_findable(const, lane, prop):
    src = getattr(B, const)
    assert "create" in src, f"{const} has no create branch — re-anchor this test"
    assert _assigns_identity_on_create(src, prop), (
        f"{const} ({lane}) builds its create payload from canonicalPatch only, which never "
        f"contains `{prop}` (manual_protected). A record created without `{prop}` cannot be "
        f"found by the search that gates creation, so every subsequent run creates another. "
        f"This is BUG 19 regressing — see .planning/debug/bug-19-create-omits-identity-fields.md."
    )


@pytest.mark.parametrize("const,lane,prop", CREATE_LANES, ids=[c for c, _, _ in CREATE_LANES])
def test_the_identity_seed_is_guarded_by_the_create_branch(const, lane, prop):
    """The other edge of the same blade: an UNCONDITIONAL seed would patch identity onto
    existing records during enrich/update — the precise clobber `manual_protected` exists
    to prevent. Every seeding assignment must sit under a create check."""
    src = getattr(B, const)
    for var in PAYLOAD_VARS:
        for m in re.finditer(rf"{var}\.{re.escape(prop)}\s*=", src):
            window = src[max(0, m.start() - 700):m.start()]
            assert re.search(r'(action\s*===\s*"create"|allow_create)', window), (
                f"{const} ({lane}): `{var}.{prop} =` at offset {m.start()} has no create "
                f"guard within its preceding context — an unguarded identity seed clobbers "
                f"on enrich/update."
            )


# =====================================================================================
# 37-CONTEXT.md §13(b) — the enrichment handoff stamp (NOT the BUG 19 identity rule).
#
# A create-outcome contact must be stamped `lv_enrichment_requested = "true"` so the
# already-deployed 15-minute scheduled poller sweeps it. This is a work-queue flag the
# poller searches for, not a write gate — see 36-07-PLAN.md <not_arming>.
# =====================================================================================

_QUEUE_FLAG_PROP = "lv_enrichment_requested"


def test_the_create_body_carries_the_enrichment_handoff_flag():
    """DECIDE_CLOUD's create branch must assign the queue flag onto the payload it sends
    to HubSpot — reusing `_assigns_identity_on_create`'s assignment-target discipline so a
    mention in a comment or a top-level display echo cannot satisfy this."""
    src = B.DECIDE_CLOUD
    assert _assigns_identity_on_create(src, _QUEUE_FLAG_PROP), (
        "DECIDE_CLOUD never assigns the queue flag onto `properties`/`patch` — a created "
        "contact will never be swept by the scheduled poller (37-CONTEXT.md §13(b))."
    )


def test_the_handoff_flag_assignment_sits_inside_the_create_block():
    """Character-index pin (the source-order-by-index idiom 36-04 established): the
    assignment must fall strictly between the create block's `if` and the `return
    { json: {` that follows it. Outside the block, an update payload would carry the
    flag and re-queue records the operator already curated."""
    src = B.DECIDE_CLOUD
    i = src.index('if (action === "create")')
    j = src.index("return { json: {", i)
    k = src.index(f"properties.{_QUEUE_FLAG_PROP}")
    assert i < k < j, (
        f"`properties.{_QUEUE_FLAG_PROP} =` (offset {k}) must sit inside the create-only "
        f"block (if at {i}, return at {j})."
    )


def test_the_handoff_flag_is_stamped_exactly_once():
    """The update path must stay clean. A second occurrence is the shape this failure
    takes: someone "helpfully" hoists the stamp above the create branch so it applies to
    every action, and every matched record on every future upload gets re-queued —
    silently spending provider credits on records that were already enriched. One
    occurrence, inside the create block, is the whole guarantee."""
    src = B.DECIDE_CLOUD
    assert src.count(f'properties.{_QUEUE_FLAG_PROP} = "true";') == 1, (
        f"`properties.{_QUEUE_FLAG_PROP} = \"true\";` must appear exactly once in "
        f"DECIDE_CLOUD — a second occurrence outside the create block would re-queue "
        f"already-enriched records on every update."
    )


def test_the_unprefixed_spelling_is_never_assigned():
    """The deployed property is `lv_enrichment_requested`; the repo-root design doc uses
    the unprefixed `enrichment_requested` for the same concept, and the two are not
    interchangeable — the poller searches for the prefixed one only.

    This must be an assignment-target assertion (`properties.enrichment_requested =`),
    not a bare substring search: the prefixed name CONTAINS the unprefixed one as a
    substring (`lv_enrichment_requested` ends in `enrichment_requested`), so a naive
    `"enrichment_requested" not in src` check would fail against CORRECT code, and
    someone would "fix" it by deleting the test. The assignment form is naturally
    anchored: `properties.lv_enrichment_requested =` does not contain
    `properties.enrichment_requested =` as a substring. This trap already cost this repo
    once on the client side (37-07-SUMMARY.md D3 hit the same ambiguity)."""
    src = B.DECIDE_CLOUD
    assert "properties.enrichment_requested =" not in src, (
        "DECIDE_CLOUD assigns the unprefixed spelling onto the payload — the poller's "
        "EQ filter reads `lv_enrichment_requested` and will never match this record."
    )


def test_the_policy_classes_that_motivated_bug_19_are_unchanged():
    """Anchor the design, not just the fix. The seed is only coherent while `domain`/`email`
    stay manual_protected (never promoted by candidates). If someone reclassifies them, the
    seed and the policy start competing for the same field and this file needs re-thinking."""
    companies = (ROOT / "n8n" / "code" / "mergeCompanies.js").read_text()
    contacts = (ROOT / "n8n" / "code" / "mergeContacts.js").read_text()
    assert re.search(r"domain:\s*\{\s*class:\s*\"manual_protected\"", companies), \
        "company `domain` is no longer manual_protected — re-read BUG 19's root cause"
    assert re.search(r"email:\s*\{\s*class:\s*\"manual_protected\"", contacts), \
        "contact `email` is no longer manual_protected — re-read BUG 19's root cause"
    assert 'field === "email" && decision === "promote"' in contacts, \
        "the explicit email->stage_only hard-force is gone — re-read BUG 19's root cause"
