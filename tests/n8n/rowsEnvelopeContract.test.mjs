// tests/n8n/rowsEnvelopeContract.test.mjs
//
// The BACKEND half of the rows-envelope contract (D-19 class).
//
// Why this file exists. The list-envelope contract pinned one wire shape after a
// field-name mismatch shipped once and killed the whole list lane while both suites
// stayed green. Phase 37's rows form is the same risk: a rows envelope whose event keys
// the backend does not read routes every row to lane "none", where the enrichment gate
// skips it silently and returns a clean 200 having matched nothing — the exact class of
// bug this pin exists to catch.
//
// One literal, pinned from both sides. The Python twin is
// `operator-claude-plugin/tests/test_rows_envelope_contract.py` and it asserts
// `enrichment.build_envelope(...)` PRODUCES exactly this. This file asserts the
// backend's own `parseWebhookBody` + (a local mirror of `ENRICH_BUILD_IDENTITY`'s
// wrapper) + `laneOf` route this exact envelope to the MEDIUM match lane ("name").
// Change the shape on either side and one of the two fails — which is the property that
// was missing, not more coverage of either half.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const here = path.dirname(fileURLToPath(import.meta.url));
const { parseWebhookBody } = require(path.join(here, "..", "..", "n8n", "code", "providerSelection.js"));
const { laneOf } = require(path.join(here, "..", "..", "n8n", "code", "matchProposal.js"));

// EXACTLY what operator-claude-plugin/scripts/enrichment.py::build_envelope emits for
// {"rows": [{"row_id": "r1", "firstname": "Jane", "lastname": "Doe", "company": "GCTC"}],
// "object_type": "contacts"} with providers []. Keep byte-identical with the Python twin.
// Phase 61 Plan 02 Task 3 (deviation — D-19 discipline: this literal must stay
// byte-identical with the Python twin's CLIENT_ENVELOPE or the two suites silently drift
// apart, the exact class of bug this pin exists to catch): `linkedin_url` widened into
// MATCH_LOOKUP_KEYS on the Python side, so every event now carries it (null when the row
// didn't supply one).
const CLIENT_ENVELOPE = {
  providers: [],
  mode: "propose",
  events: [
    {
      row_id: "r1",
      objectType: "contacts",
      email: null,
      firstname: "Jane",
      lastname: "Doe",
      company: "GCTC",
      linkedin_url: null,
    },
  ],
};

// Mirrors build_cloud_workflows.py's ENRICH_BUILD_IDENTITY wrapper: derive
// identity_keys from a parsed event exactly as the deployed workflow does, so this test
// proves the contract through the SAME derivation the live workflow runs, not a
// reimplementation of its own.
function deriveIdentityKeys(row) {
  return {
    email: row.email || null,
    linkedin_url: row.linkedin_url || null,
    firstName: row.firstname || row.first_name || null,
    lastName: row.lastname || row.last_name || null,
    companyName: row.company || row.companyName || null,
  };
}

test("the backend ACCEPTS the exact rows envelope the client emits", () => {
  const parsed = parseWebhookBody(CLIENT_ENVELOPE);
  assert.equal(parsed.mode, "propose");
  assert.deepEqual(parsed.providers, []);
  assert.equal(parsed.events.length, 1);
});

test("the client's exact rows envelope reaches the MEDIUM match lane, never none", () => {
  const parsed = parseWebhookBody(CLIENT_ENVELOPE);
  const event = parsed.events[0];
  const identityKeys = deriveIdentityKeys(event);
  const lane = laneOf({ object_id: event.object_id, identity_keys: identityKeys });

  assert.equal(
    lane,
    "name",
    `expected the MEDIUM match lane "name", got "${lane}" — a row in lane "none" is ` +
      "skipped by the enrichment gate and returns a clean 200",
  );
});

test("the camelCase regression — wrong field spellings route to lane none", () => {
  // The exact bug this pin exists to catch: a rows event carrying camelCase spellings
  // (firstName/lastName/companyName) instead of the flat HubSpot-property spellings
  // (firstname/lastname/company) is invisible to ENRICH_BUILD_IDENTITY, which reads
  // ONLY the flat spellings. A row in lane "none" is skipped by the enrichment gate and
  // returns a clean 200, which is why this cannot be left to either side's own suite.
  const wrong = {
    providers: [],
    mode: "propose",
    events: [
      {
        row_id: "r1",
        objectType: "contacts",
        email: null,
        firstName: "Jane",
        lastName: "Doe",
        companyName: "GCTC",
      },
    ],
  };
  const parsed = parseWebhookBody(wrong);
  const event = parsed.events[0];
  const identityKeys = deriveIdentityKeys(event);
  const lane = laneOf({ object_id: event.object_id, identity_keys: identityKeys });

  assert.equal(lane, "none");
});

test("the contract literal carries mode: propose structurally", () => {
  assert.equal(CLIENT_ENVELOPE.mode, "propose");
  assert.deepEqual(CLIENT_ENVELOPE.providers, []);
});
