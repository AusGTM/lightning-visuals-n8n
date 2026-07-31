// tests/n8n/listEnvelopeContract.test.mjs
//
// The BACKEND half of the list-envelope contract (D-19).
//
// Why this file exists. 25-04 built the client envelope and 25-03 built the backend that
// reads it, and they disagreed: the client sent a flat
//   {"providers": [...], "list": "<name>", "objectType": "contacts"}
// while `listExpansion.js` reads `isPlainObject(body.list)` and then `body.list.name` /
// `body.list.objectType`. A string is non-null, so a flat envelope PASSES the
// `IF List Input` gate and is then refused by every single request with "the enrichment
// request named no list" — the whole list lane dead, while both plans' own suites stayed
// green because each tested only its own side of the webhook.
//
// One literal, pinned from both sides. The Python twin is
// `operator-claude-plugin/tests/test_list_envelope_contract.py` and it asserts
// `enrichment.build_envelope(...)` PRODUCES exactly this. This file asserts
// `expandListToEvents` ACCEPTS exactly this. Change the shape on either side and one of
// the two fails — which is the property that was missing, not more coverage of either half.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const here = path.dirname(fileURLToPath(import.meta.url));
const { expandListToEvents } = require(path.join(here, "..", "..", "n8n", "code", "listExpansion.js"));

// EXACTLY what operator-claude-plugin/scripts/enrichment.py::build_envelope emits for
// {"list": "New Targets.xlsx", "object_type": "contacts"} with providers ["lusha"].
// Keep byte-identical with the Python twin.
const CLIENT_ENVELOPE = {
  providers: ["lusha"],
  list: { name: "New Targets.xlsx", objectType: "contacts" },
};

const listResult = { list: { listId: 15 } };
const membershipsResult = { results: [{ recordId: "101" }, { recordId: "102" }], total: 2 };

test("the backend ACCEPTS the exact envelope the client emits", () => {
  const out = expandListToEvents({
    body: CLIENT_ENVELOPE,
    listResult,
    membershipsResult,
    maxRecords: 2,
  });

  assert.equal(out.refused, false, `backend refused the client's own envelope: ${out.reason}`);
  assert.deepEqual(out.events, [
    { objectId: "101", objectType: "contacts" },
    { objectId: "102", objectType: "contacts" },
  ]);
  assert.deepEqual(out.providers, ["lusha"], "the approved provider selection must survive");
});

test("the FLAT shape that shipped briefly is refused — this is the regression", () => {
  // The exact bug: a string `list` is non-null so it passes IF List Input, then dies here.
  const flat = { providers: ["lusha"], list: "New Targets.xlsx", objectType: "contacts" };
  const out = expandListToEvents({ body: flat, listResult, membershipsResult, maxRecords: 2 });

  assert.equal(out.refused, true);
  assert.match(out.reason, /named no list/i);
  assert.deepEqual(out.events, [], "a refusal must never carry events");
});

test("the contract literal is nested, not flat — pinned so a silent reshape fails here", () => {
  assert.equal(typeof CLIENT_ENVELOPE.list, "object");
  assert.equal(CLIENT_ENVELOPE.list.name, "New Targets.xlsx");
  assert.equal(CLIENT_ENVELOPE.list.objectType, "contacts");
  assert.ok(
    !Object.prototype.hasOwnProperty.call(CLIENT_ENVELOPE, "objectType"),
    "objectType belongs inside `list`; a sibling key is the flat shape returning",
  );
});
