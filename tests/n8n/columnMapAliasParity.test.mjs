// tests/n8n/columnMapAliasParity.test.mjs
//
// Phase 34 guard. config/column_mapping.yaml (what the plugin's preview reads, via the
// byte-identical shipped copy pinned by test_column_mapping_shipped.py) and
// n8n/code/columnMap.js's embedded ALIASES agree today BY HAND — build_cloud_workflows.py
// does not generate one from the other. Widening one side alone makes the preview predict a
// mapping the backend will not perform: the client tells the operator a header is understood
// and the backend silently drops it. That is worse than today's honest mismatch.
//
// This test pins the two alias tables equal so any future widening has to move both.
// Run: node --test tests/n8n/columnMapAliasParity.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const PY = path.join(ROOT, ".venv/bin/python");

const { ALIASES, mapRow } = require(path.join(ROOT, "n8n/code/columnMap.js"));

// Python oracle: PyYAML parses the real config file, no JS-side YAML reimplementation.
function yamlAliases() {
  const script =
    "import json,yaml;print(json.dumps(yaml.safe_load(open('config/column_mapping.yaml'))['aliases']))";
  return JSON.parse(execFileSync(PY, ["-c", script], { cwd: ROOT }).toString());
}

test("columnMap.js ALIASES equals config/column_mapping.yaml aliases", () => {
  const yaml = yamlAliases();
  assert.deepEqual(
    ALIASES,
    yaml,
    "alias tables drifted — edit config/column_mapping.yaml AND n8n/code/columnMap.js together",
  );
});

test("every YAML alias key is already normalized (lowercase, whitespace-collapsed)", () => {
  // mapRow normalizes the INCOMING header, never the table key. A key like "E-Mail Address"
  // would sit in the table unreachable, so the preview and the backend would both miss it.
  for (const key of Object.keys(yamlAliases())) {
    assert.equal(key, key.trim().replace(/\s+/g, " ").toLowerCase(), `alias key not normalized: ${key}`);
  }
});

test("each YAML alias actually maps through mapRow to its canonical prop", () => {
  // Equality alone would pass if both sides shared the same broken key. This walks the real
  // lookup path the backend uses.
  for (const [alias, canonical] of Object.entries(yamlAliases())) {
    assert.deepEqual(mapRow({ [alias]: "v" }), { [canonical]: "v" }, `alias failed to map: ${alias}`);
  }
});
