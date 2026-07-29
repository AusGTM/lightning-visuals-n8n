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
    harness = """
const rows = [{ json: { email: "ingest-canary@lv-canary-delete-me.example",
                        email_normalized: "ingest-canary@lv-canary-delete-me.example" } }];
const search = [
  { json: { id: "341450293725", properties: { email: "someone.real@example.com" } } },
  { json: { id: "340482729442", properties: { email: "another.real@example.com" } } },
];
const $ = (name) => ({ all: () => (name === 'Normalize Phone' ? rows : search) });
const out = (function () { %s })();
const srk = out[0].json.searchResultsByKey;
if (Object.keys(srk).length !== 0) { throw new Error("matched: " + JSON.stringify(srk)); }
// and the positive direction: an actual email match still resolves
search.push({ json: { id: "777", properties: { email: "ingest-canary@lv-canary-delete-me.example" } } });
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
