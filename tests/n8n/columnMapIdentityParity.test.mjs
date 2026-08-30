// tests/n8n/columnMapIdentityParity.test.mjs
//
// Phase 61 Plan 03 guard (D-61-06). config/column_mapping.yaml's `required_identity.any_of`
// and n8n/code/columnMap.js's hand-written requiredIdentity() restate the SAME rule in two
// independent sites with no parity test between them — the identity-rule counterpart to
// columnMapAliasParity.test.mjs's alias-table guard (same header comment explains why: the
// client tells the operator a row is understood and the backend silently rejects it).
//
// This test is driven FROM the YAML, not from three hand-written cases, so a fourth group
// added later is covered automatically without this file needing an edit.
// Run: node --test tests/n8n/columnMapIdentityParity.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const PY = path.join(ROOT, ".venv/bin/python");

const { requiredIdentity } = require(path.join(ROOT, "n8n/code/columnMap.js"));

// Python oracle: PyYAML parses the real config file, no JS-side YAML reimplementation.
function identityGroups() {
  const script =
    "import json,yaml;print(json.dumps(yaml.safe_load(open('config/column_mapping.yaml'))['required_identity']['any_of']))";
  return JSON.parse(execFileSync(PY, ["-c", script], { cwd: ROOT }).toString());
}

// Build a row satisfying exactly one group in full — every other configured field absent.
function rowFor(group) {
  const row = {};
  for (const field of group) row[field] = `${field}-value`;
  return row;
}

test("a row satisfying each configured identity group in full passes requiredIdentity()", () => {
  const groups = identityGroups();
  assert.ok(groups.length >= 1, "config/column_mapping.yaml must define at least one identity group");
  for (const group of groups) {
    const row = rowFor(group);
    assert.equal(
      requiredIdentity(row),
      true,
      `row satisfying group [${group.join(", ")}] must pass requiredIdentity() — YAML/JS drift`,
    );
  }
});

test("a row satisfying no configured group fails requiredIdentity()", () => {
  assert.equal(requiredIdentity({ jobtitle: "CEO", phone: "555-0100" }), false);
  assert.equal(requiredIdentity({}), false);
  assert.equal(requiredIdentity(null), false);
});

test("a row satisfying a multi-field group only partially still fails requiredIdentity()", () => {
  const groups = identityGroups();
  const partial = groups.find((g) => g.length > 1);
  assert.ok(partial, "expected at least one multi-field identity group to test partial satisfaction");

  // Every field but the last one present — the group is not fully satisfied.
  const row = {};
  for (const field of partial.slice(0, -1)) row[field] = `${field}-value`;

  // Guard against accidentally also satisfying a DIFFERENT configured group.
  const satisfiesAnotherGroup = groups.some(
    (g) => g !== partial && g.every((f) => Object.prototype.hasOwnProperty.call(row, f)),
  );
  assert.equal(
    satisfiesAnotherGroup,
    false,
    "test fixture accidentally satisfies a different identity group — fixture needs adjusting",
  );

  assert.equal(
    requiredIdentity(row),
    false,
    `a row missing one field of group [${partial.join(", ")}] must not pass requiredIdentity()`,
  );
});

test("requiredIdentity() has no group beyond what the YAML configures (linkedin_url alone passes, nothing wilder)", () => {
  // A linkedin-only row is D-61-06's whole point: it must pass. This also pins the group is
  // additive — the existing two groups are untouched.
  assert.equal(requiredIdentity({ linkedin_url: "https://linkedin.com/in/someone" }), true);
});
