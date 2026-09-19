// tests/n8n/frozenFixtureSecrets.test.mjs
//
// D-74-09 (Phase 74 Plan 01): a guard test over tests/n8n/fixtures/frozen/ refusing VALUE
// shapes, never key NAMES — the key name `x-enrichment-secret` legitimately appears inside
// the frozen workflow-body fixtures' jsCode/notes strings (and as the placeholder string
// itself on the 5 Phase-70 runData fixtures) and must never trip this guard; only a live
// secret/token/JWT VALUE does.
//
// Assertions never print the matched substring: `assert.equal(re.test(raw), false, msg)`,
// never `assert.doesNotMatch(raw, re, msg)` — the latter's failure output is
// `Input: '<entire file>'`, which would print the very secret the guard exists to catch,
// straight into the test transcript and (via #3770 RED-evidence capture) the commit body.
//
// Task 1 scope (this commit): exec_12434.runData.json only — the one fixture Task 1's
// `_scrub` widening re-redacts. Task 2 widens IN_SCOPE_FILES to every JSON file under
// fixtures/frozen/ and reports the in-scope count so the workflow-body fixtures are
// provably covered too.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const FROZEN = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures", "frozen");

const IN_SCOPE_FILES = ["exec_12434.runData.json"];

// Value shapes only (D-74-09) — never a bare key-name match.
const VALUE_PATTERNS = [
  { name: "HubSpot private-app token", re: /pat-na\d-[A-Za-z0-9-]+/ },
  // A real bearer VALUE is a token-shaped run of characters immediately after
  // "Bearer ". Deliberately does NOT match the workflow-body jsCode literals this
  // guard must pass through, e.g. `Authorization: \"Bearer \" + token,` — the
  // escaped quote/plus-operator right after the space is not a token character —
  // or a bare `"token_type": "Bearer"` label with no attached value.
  { name: "bearer scheme with a token value", re: /Bearer\s+[A-Za-z0-9._-]{10,}/ },
  { name: "x-enrichment-secret with a non-placeholder value", re: /"x-enrichment-secret":\s*"(?!<redacted>)[^"]+"/ },
  { name: "JWT body", re: /eyJ[A-Za-z0-9_-]{20,}/ },
];

test("frozen fixtures carry no live secret value shape", () => {
  for (const file of IN_SCOPE_FILES) {
    const raw = fs.readFileSync(path.join(FROZEN, file), "utf8");
    for (const { name, re } of VALUE_PATTERNS) {
      assert.equal(re.test(raw), false, `${file}: must not carry a ${name}`);
    }
  }
});

test("guard reports its own in-scope file count", () => {
  assert.equal(IN_SCOPE_FILES.length, 1, "Task 1 scopes the guard to exec_12434.runData.json only");
});
