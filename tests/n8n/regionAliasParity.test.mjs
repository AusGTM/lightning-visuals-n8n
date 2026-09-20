// tests/n8n/regionAliasParity.test.mjs
//
// Phase 75 Plan 02 (D-75-08). config/icp_scoring.yaml's regions.aliases is now the SINGLE
// country-name/ISO2 -> region-code table in the system; n8n/code/normalizeProviders.js's
// hand-typed _COUNTRY_ISO2 map was deleted in the same plan. This test pins two things
// that must never regress independently of each other:
//
//   (a) the generated n8n/code/icpScoring.generated.js REGION_ALIASES equals the yaml's
//       regions.aliases exactly (the currency test in tests/test_icp_scoring_generated_
//       currency.py already pins the WHOLE generated file; this is scoped to just the
//       alias table, mirroring the tests/n8n/columnMapIdentityParity.test.mjs idiom);
//   (b) REGION_ALIASES is a superset of a HARD-CODED, frozen historical key list -- the
//       eleven deleted _COUNTRY_ISO2 keys plus the three extra literals
//       (au/aus/nz) the JS/Python/ZoomInfo normalisers each carried independently. This
//       list is deliberately NOT derived from the yaml it guards -- it is the frozen
//       record of what the deleted maps guaranteed, so a future yaml edit that drops one
//       of these keys is caught here rather than silently regressing phone normalisation
//       to the AU heuristic;
//   (c) every value in REGION_ALIASES is either a member of REGIONS_HOME or the literal
//       "Other" -- an alias pointing at an unknown region code would silently create a
//       third, unhandled region class.
//
// Run: node --test tests/n8n/regionAliasParity.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const PY = path.join(ROOT, ".venv/bin/python");

const { REGION_ALIASES, REGIONS_HOME } = require(path.join(ROOT, "n8n/code/icpScoring.generated.js"));

// Python oracle: PyYAML parses the real config file, no JS-side YAML reimplementation.
function yamlRegionAliases() {
  const script =
    "import json,yaml;print(json.dumps(yaml.safe_load(open('config/icp_scoring.yaml'))['regions']['aliases']))";
  return JSON.parse(execFileSync(PY, ["-c", script], { cwd: ROOT }).toString());
}

// Frozen historical key list -- the eleven n8n/code/normalizeProviders.js _COUNTRY_ISO2
// keys (deleted in this plan) plus the three extra literals (au/aus/nz) the JS/Python/
// ZoomInfo normalisers each carried in their own hand-typed lists. NOT derived from the
// yaml under test -- hard-coded on purpose (D-75-08's own instruction).
const HISTORICAL_ALIASES = {
  australia: "AU",
  "new zealand": "NZ",
  "united states": "US",
  "united states of america": "US",
  canada: "CA",
  "united kingdom": "GB",
  "great britain": "GB",
  england: "GB",
  ireland: "IE",
  india: "IN",
  singapore: "SG",
  au: "AU",
  aus: "AU",
  nz: "NZ",
};

test("REGION_ALIASES equals config/icp_scoring.yaml regions.aliases exactly", () => {
  assert.deepEqual(REGION_ALIASES, yamlRegionAliases());
});

test("REGION_ALIASES is a superset of the frozen historical _COUNTRY_ISO2 + normaliser literal list", () => {
  for (const [key, expected] of Object.entries(HISTORICAL_ALIASES)) {
    assert.equal(
      REGION_ALIASES[key],
      expected,
      `REGION_ALIASES["${key}"] must be "${expected}" (historical alias, deleted _COUNTRY_ISO2/normaliser literal) — got ${REGION_ALIASES[key]}`,
    );
  }
});

test("every REGION_ALIASES value is a member of REGIONS_HOME or the literal 'Other'", () => {
  const homeSet = new Set(REGIONS_HOME);
  for (const [key, value] of Object.entries(REGION_ALIASES)) {
    assert.ok(
      homeSet.has(value) || value === "Other",
      `REGION_ALIASES["${key}"] = "${value}" is neither a REGIONS_HOME member nor "Other" — typo'd region code`,
    );
  }
});
