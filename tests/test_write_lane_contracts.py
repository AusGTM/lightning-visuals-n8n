# tests/test_write_lane_contracts.py
#
# BUG 16 — and the generic guard for the whole BUG 11 / 13 / 16 family.
#
# Every one of those bugs is the same shape: a node reads a field its own input never
# carries, or ignores the field the input does carry.
#
#   BUG 11  write nodes shipped `updateFields: {}` — the patch on $json.properties was
#           referenced nowhere.
#   BUG 13  create nodes read $json.name / $json.identity_keys.* / $json.properties.email,
#           none of which the Decide output emits.
#   BUG 16  the contact-ingest write GATES read $json.hs_object_id, but that lane emits
#           `contact_id` — so _writeSafetyAllows(action, null, null) returned false
#           unconditionally and the gates could never pass, whatever the allowlist said.
#
# Three lanes had drifted to three different row contracts:
#
#   enrichment      hs_object_id + properties
#   contact ingest  contact_id   + properties
#   review          hs_object_id + canonicalPatch/clearPatch (no `properties` at all)
#
# The fix converges them, and this file pins the convergence: for every gated write node
# in every cloud workflow, the id and patch fields the node and its gate READ must be
# fields the upstream lane actually EMITS. A one-off pin per node would not have caught
# BUG 16, because that gate was written after the pins existed.
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLOUD_WORKFLOWS = sorted((ROOT / "n8n").glob("wf_*_cloud.json"))


def _load(path):
    return json.loads(path.read_text())


def _node(wf, name):
    return next((n for n in wf["nodes"] if n["name"] == name), None)


def _feeders(wf, name):
    return [src for src, spec in wf["connections"].items()
            if any(c["node"] == name
                   for outputs in spec.get("main", []) for c in (outputs or []))]


def _is_write_node(node):
    params = node.get("parameters", {})
    if node.get("type") == "n8n-nodes-base.hubspot":
        return params.get("operation") in ("create", "update")
    if node.get("type") == "n8n-nodes-base.httpRequest":
        url = str(params.get("url", ""))
        method = str(params.get("method", "")).upper()
        return ("hubapi.com" in url and "/search" not in url
                and method in ("POST", "PATCH", "PUT"))
    return False


def _emitted_fields(wf, name, depth=0):
    """Field names a node emits on $json. Code nodes: the keys their return object
    literal assigns, plus anything spread in from upstream. Walks back through pure
    pass-through nodes (IF, gates) to the nearest node that actually shapes the row."""
    node = _node(wf, name)
    if node is None or depth > 6:
        return set()
    js = node.get("parameters", {}).get("jsCode")
    if not isinstance(js, str):
        # IF / Set / trigger — inherits from upstream.
        fields = set()
        for f in _feeders(wf, name):
            fields |= _emitted_fields(wf, f, depth + 1)
        return fields
    tail = js[js.rfind("return $input"):] if "return $input" in js else js
    # A node that only filters or sorts rows constructs no `{ json: ... }` object — it is a
    # pass-through and emits exactly what its upstream emits. The write-safety gates are
    # this shape; treating them as emitting nothing was what made an earlier draft of this
    # guard report every gated write node as broken.
    constructs_row = "json:" in tail.replace(" ", "")
    if not constructs_row:
        fields = set()
        for f in _feeders(wf, name):
            fields |= _emitted_fields(wf, f, depth + 1)
        return fields
    tail = re.sub(r"//[^\n]*", "", tail)  # comments are not row fields
    # `key: value` plus ES6 shorthand (`properties` on its own, no colon) — the shorthand
    # case is how `properties` is emitted on two of the three lanes.
    fields = set(re.findall(r"(\w+)\s*:", tail))
    fields |= set(re.findall(r"(?:^|[{,])\s*(\w+)\s*(?=[,}])", tail, re.M))
    if re.search(r"\.\.\.\s*(?:it\.json|row)\b", tail):
        for f in _feeders(wf, name):
            fields |= _emitted_fields(wf, f, depth + 1)
    return fields


def _reads(text):
    """Field names an expression or jsCode reads off $json / it.json."""
    return set(re.findall(r"(?:\$json|it\.json)\.(\w+)", text or ""))


def _gated_writes(wf):
    out = []
    for node in wf["nodes"]:
        if not _is_write_node(node):
            continue
        for gate_name in _feeders(wf, node["name"]):
            gate = _node(wf, gate_name)
            gate_js = (gate or {}).get("parameters", {}).get("jsCode", "") or ""
            if "_writeSafetyAllows" in gate_js:
                out.append((node, gate_name, gate_js))
    return out


@pytest.mark.parametrize("path", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_write_nodes_read_only_fields_their_lane_emits(path):
    """BUG 13's generalisation. A write node's URL and body may only reference fields the
    upstream lane actually produces."""
    wf = _load(path)
    offenders = []
    for node, gate_name, _ in _gated_writes(wf):
        params = node.get("parameters", {})
        read = _reads(str(params.get("url", ""))) | _reads(str(params.get("jsonBody", "")))
        read |= _reads(str(params.get("contactId", ""))) | _reads(str(params.get("companyId", "")))
        read |= _reads(str(params.get("email", "")))
        emitted = _emitted_fields(wf, gate_name)
        missing = {f for f in read if f not in emitted}
        if missing:
            offenders.append((node["name"], sorted(missing), sorted(emitted)[:12]))
    assert not offenders, (
        f"{path.name}: write node(s) reference fields their lane never emits — the BUG 13 "
        f"shape: {offenders}"
    )


@pytest.mark.parametrize("path", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_write_gates_read_only_fields_their_lane_emits(path):
    """BUG 16 proper. A gate that reads an absent id field denies unconditionally — safe,
    but it is a wall rather than a gate, and the reason is invisible at runtime."""
    wf = _load(path)
    offenders = []
    for _node_obj, gate_name, gate_js in _gated_writes(wf):
        upstream = set()
        for f in _feeders(wf, gate_name):
            upstream |= _emitted_fields(wf, f)
        # The gate's id expression must be satisfiable by SOMETHING the lane emits.
        id_candidates = {"hs_object_id", "existingRecord"}
        if not (id_candidates & upstream):
            offenders.append((gate_name, sorted(upstream)[:12]))
    assert not offenders, (
        f"{path.name}: write gate(s) read an id field their lane never emits, so "
        f"_writeSafetyAllows always denies: {offenders}"
    )


@pytest.mark.parametrize("path", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_no_write_node_ships_an_empty_field_map(path):
    """BUG 11's generalisation, across every workflow rather than just enrichment. A
    native HubSpot write with an empty updateFields/additionalFields sends nothing."""
    wf = _load(path)
    offenders = []
    for node in wf["nodes"]:
        if not _is_write_node(node):
            continue
        params = node.get("parameters", {})
        for key in ("updateFields", "additionalFields"):
            if key in params and not params[key]:
                offenders.append((node["name"], key))
    assert not offenders, (
        f"{path.name}: write node(s) ship an empty field map and would write nothing "
        f"(BUG 11 shape): {offenders}"
    )
