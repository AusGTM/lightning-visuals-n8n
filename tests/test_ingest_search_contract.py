# tests/test_ingest_search_contract.py
#
# BUG 22 — the contact-ingest identity search was wrong at BOTH ends, found on the lane's
# first complete live run (execution 21, 2026-07-29):
#
#   22a  "HubSpot Search by Email" shipped `filterGroupsValues: []` — an empty filter (the
#        BUG 11 placeholder family) — so it returned the portal's newest 100 contacts.
#   22b  "Adapt Search Results" indexed `search[i]` and took ANY id. The native node
#        FLATTENS hits to one item per contact, so search[0] was just the first arbitrary
#        contact, and a made-up canary email produced "single email match" against a real
#        person's record. Only the disarmed write gate stopped a mis-targeted PATCH.
#
# The fix pins value-matching over index-alignment: a hit counts only when the candidate's
# own email equals the row's normalized email.
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

WF = ROOT / "n8n" / "wf_contact_ingest_cloud.json"


def _node(name):
    doc = json.loads(WF.read_text())
    return next(n for n in doc["nodes"] if n["name"] == name)


def test_search_by_email_is_a_filtered_envelope_returning_httprequest():
    """BUG 22a + execution 22. Two constraints, both live-earned the same day:
    (1) the search must actually filter on the row's email (the native node shipped with
        an EMPTY filter and returned the portal's newest 100 contacts);
    (2) the transport must return the {total, results} envelope as ONE item even on zero
        hits — the native node emits ZERO items on a no-match and n8n stops the chain
        there, killing the lane on ingest's primary case (a genuinely new contact). This
        is the BUG 10 transport, reapplied."""
    node = _node("HubSpot Search by Email")
    p = node["parameters"]
    assert node["type"] == "n8n-nodes-base.httpRequest"
    assert p["method"] == "POST"
    assert p["url"] == "https://api.hubapi.com/crm/v3/objects/contacts/search"
    assert p["authentication"] == "predefinedCredentialType"
    assert p["nodeCredentialType"] == "hubspotAppToken"
    body = p["jsonBody"]
    assert 'propertyName: "email"' in body and 'operator: "EQ"' in body
    assert "$json.email_normalized || $json.email" in body, \
        "the filter value must read the row the node executes on"
    assert '"email"' in body.split("properties:")[1], \
        "the adapter matches by candidate email — the search must request that property"


def test_search_by_email_filter_falls_back_to_an_invalid_sentinel_for_an_emailless_row():
    """Phase 36 Finding B (36-CONTEXT.md §5B). For an emailless row the filter value used
    to be `undefined`, which JSON.stringify drops from the object — HubSpot then rejected
    the filter, onError swallowed it into the item, and Adapt Search Results' batch-wide
    `lookup_failed` demoted every SIBLING row's `create` action to `review`. An RFC 2606
    `.invalid` sentinel can never be a real address, so the search now returns 200 with
    zero hits instead of a rejected filter."""
    node = _node("HubSpot Search by Email")
    body = node["parameters"]["jsonBody"]
    assert "no-email@invalid.invalid" in body
    # The pinned prefix (BUG 22a) must survive verbatim — the sentinel is APPENDED, not a
    # restructure of the existing fallback chain.
    assert "$json.email_normalized || $json.email" in body


def test_adapter_matches_hits_by_email_value_never_by_item_index():
    """BUG 22b. Value-match survives an unfiltered search (100 wrong contacts contribute
    zero hits) and is order-independent for multi-row uploads; index alignment is neither."""
    js = _node("Adapt Search Results")["parameters"]["jsCode"]
    stripped = "\n".join(l for l in js.splitlines() if not l.strip().startswith("//"))
    assert "candidateEmail(c) === rowEmail" in stripped
    assert not re.search(r"search\[\s*i\s*\]", stripped), \
        "adapter is indexing the flattened search output again — BUG 22b regressing"


def test_adapter_behavior_arbitrary_contacts_produce_zero_hits():
    """Execution 21's exact scenario, replayed offline against the compiled node: a row
    whose email matches nothing, adapted against a flattened page of OTHER contacts, must
    yield no searchResultsByKey — net_new, never a match."""
    import subprocess

    js = _node("Adapt Search Results")["parameters"]["jsCode"]
    # Phase 70 Plan 02 Task 3 (D-70-04): this node's own direct predecessor is now the
    # carry merge spliced after "HubSpot Search by Email" — one $input item per row,
    # already the row's own fields shallow-merged with the search's own `{results}`
    # envelope (the real CRM v3 shape, one item whether it matched or not).
    harness = """
const row = { email: "ingest-canary@lv-canary-delete-me.example",
              email_normalized: "ingest-canary@lv-canary-delete-me.example" };
const results = [
  { id: "341450293725", properties: { email: "someone.real@example.com" } },
  { id: "340482729442", properties: { email: "another.real@example.com" } },
];
const $input = { all: () => [{ json: { ...row, results } }] };
const out = (function () { %s })();
const srk = out[0].json.searchResultsByKey;
if (Object.keys(srk).length !== 0) { throw new Error("matched: " + JSON.stringify(srk)); }
// and the positive direction: an actual email match still resolves
results.push({ id: "777", properties: { email: "ingest-canary@lv-canary-delete-me.example" } });
const out2 = (function () { %s })();
const srk2 = out2[0].json.searchResultsByKey;
if (JSON.stringify(srk2.email) !== JSON.stringify(["777"])) { throw new Error("miss: " + JSON.stringify(srk2)); }
console.log("OK");
""" % (js, js)
    r = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0 and "OK" in r.stdout, r.stderr[:800]


def test_adapter_flags_lookup_failed_and_decide_never_creates_on_it():
    """The httpRequest transport defaults to onError:continueRegularOutput, so a FAILED
    search arrives as an item, not a node error — the Lusha/ZoomInfo masking mechanism.
    Reading that as "no hits" would mean net_new -> duplicate-create once creates are
    armed. The enrichment lanes' lookup_failed pattern applies identically here."""
    adapter = _node("Adapt Search Results")["parameters"]["jsCode"]
    assert "lookup_failed" in adapter
    decide = _node("Decide Action")["parameters"]["jsCode"]
    assert 'row.lookup_failed === true && action === "create"' in decide


def test_per_row_search_nodes_are_throttled():
    """F-A3 (uat-stress-2026-09-15, execution 12429): a 48-row batch fired one request per
    item per search node in a single burst against HubSpot's account-wide 5 req/s CRM
    Search cap and 429'd on most items (33/48, 38/48, 42/48). All three per-row search
    nodes must carry `options.batching` so n8n paces them, one item at a time."""
    for name in ("HubSpot Search by Email", "HubSpot Company Search by Domain",
                 "HubSpot Company Search by Name"):
        batching = _node(name)["parameters"]["options"]["batching"]
        assert batching["batch"]["batchSize"] == 1
        assert batching["batch"]["batchInterval"] > 0, \
            f"{name}: a zero interval throttles nothing"
        # 5 req/s is HubSpot's documented account-wide CRM Search cap; stay under it.
        assert batching["batch"]["batchInterval"] >= 200, \
            f"{name}: interval faster than 5 req/s risks the same 429"


def test_decide_action_names_lookup_failure_distinctly_from_a_genuine_miss():
    """F-A4 (uat-stress-2026-09-15, execution 12429): when the batch-wide `lookup_failed`
    flag is set, a row whose identity search legitimately found zero hits ("valid email,
    no existing match") is indistinguishable from a row whose search never ran at all —
    execution 12429 reported Colin Telfer (`1251`, an EXISTING contact) as "no existing
    match" for exactly this reason. The reason string must name the lookup failure
    instead, but ONLY for that one identity.reason (a real match/multi-match/emailless
    reason must survive unchanged — a 429 can't manufacture a positive hit, and an
    emailless row never issues this search)."""
    decide = _node("Decide Action")["parameters"]["jsCode"]
    assert "lookup failed" in decide.lower()
    assert 'identity_reason === "valid email, no existing match"' in decide
    # the override reads row.lookup_failed, and the final reason no longer takes id.reason
    # directly (it must pass through the override variable first)
    assert "identity_reason = id.reason" in decide
    assert "reason: company_hold || identity_reason" in decide

    import subprocess

    # Execution 12429's exact shape for Colin Telfer (`1251`, an EXISTING contact): a
    # valid email whose search 429'd, misread as net_new. Row 2 is the same row with a
    # healthy search (control: reason must survive unchanged). Row 3 is a genuinely
    # emailless row caught by the SAME batch-wide flag (control: unaffected, its own
    # search never ran).
    rows = [
        {"identity": {"outcome": "net_new", "contact_id": None,
                       "reason": "valid email, no existing match"},
         "lookup_failed": True, "email": "ctelfer@australianturfclub.com.au"},
        {"identity": {"outcome": "net_new", "contact_id": None,
                       "reason": "valid email, no existing match"},
         "lookup_failed": False, "email": "ctelfer@australianturfclub.com.au"},
        {"identity": {"outcome": "ambiguous", "contact_id": None,
                       "reason": "no email, insufficient identity"},
         "lookup_failed": True, "email": None},
    ]
    harness = """
const $input = { all: () => (%s).map((json) => ({ json })) };
const out = (function () { %s })();
console.log(JSON.stringify(out.map((o) => o.json.reason)));
""" % (json.dumps(rows), decide)
    r = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr[:1000]
    reasons = json.loads(r.stdout.strip().splitlines()[-1])
    assert reasons[0] == "lookup failed (HubSpot search unavailable/rate-limited) — held, not matched"
    assert reasons[1] == "valid email, no existing match"
    assert reasons[2] == "no email, insufficient identity"


def test_ingest_webhook_requires_header_auth_like_the_enrichment_webhook():
    """Security fix, activation day 2026-07-29: this webhook shipped UNAUTHENTICATED while
    the enrichment webhook has always required native Header Auth — anyone with the URL
    could submit CSVs. Same headerAuth, same shared credential (both webhook nodes are
    named "Webhook Trigger", so NODE_CREDENTIAL_MAP binds this one identically)."""
    node = _node("Webhook Trigger")
    assert node["type"] == "n8n-nodes-base.webhook"
    assert node["parameters"]["authentication"] == "headerAuth"
