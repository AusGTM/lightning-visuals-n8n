// tests/n8n/widenedKeyParity.test.mjs
//
// Phase 72 Plan 02 Task 3 (D-72-02). The third dimension of the columnMap*Parity family
// (columnMapAliasParity.test.mjs pins the alias table; columnMapIdentityParity.test.mjs
// pins required_identity) — this one pins the relationship BETWEEN
// config/field_policy.yaml's `contacts:` promotable keys, config/column_mapping.yaml's
// canonical alias targets, and the ingest lane's actual candidate loop, so a future edit
// that widens one without the others fails here instead of silently reopening RICH-04's
// original bug (a key the policy promotes that the CSV boundary can never carry, or a
// lane candidate no policy governs at all).
//
// Reuses columnMapIdentityParity.test.mjs's idiom verbatim: a `.venv/bin/python -c`
// oracle parses the real YAML files with PyYAML and prints JSON; this file never
// restates a key list of its own — every assertion is a set operation over what the
// oracle returns, plus one regex extraction of the COMMITTED workflow JSON (never
// scripts/build_cloud_workflows.py, which is the generator, not the deployed artifact).
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const PY = path.join(ROOT, ".venv/bin/python");

const { ALIASES } = require(path.join(ROOT, "n8n/code/columnMap.js"));

// Python oracle: PyYAML parses the real config files, no JS-side YAML reimplementation.
function policyContactsKeys() {
  const script =
    "import json,yaml;" +
    "print(json.dumps(sorted(yaml.safe_load(open('config/field_policy.yaml'))['contacts'])))";
  return JSON.parse(execFileSync(PY, ["-c", script], { cwd: ROOT }).toString());
}

function columnMappingCanonicalTargets() {
  const script =
    "import json,yaml;" +
    "print(json.dumps(sorted(set(yaml.safe_load(open('config/column_mapping.yaml'))['aliases'].values()))))";
  return JSON.parse(execFileSync(PY, ["-c", script], { cwd: ROOT }).toString());
}

function yamlAliasValues() {
  const script =
    "import json,yaml;" +
    "print(json.dumps(sorted(yaml.safe_load(open('config/column_mapping.yaml'))['aliases'].values())))";
  return JSON.parse(execFileSync(PY, ["-c", script], { cwd: ROOT }).toString());
}

// The lane-side-only exemption: a promotable contacts: key with NO canonical alias
// target, because the CSV vocabulary for that fact deliberately uses a different name
// (lv_linkedin_url -- D-72-19, the naming fork closed inside merge_enriched, not the
// column map) or exists only as a native-property write mirror with no CSV header of
// its own (hs_linkedin_url -- D-72-04, always populated from the linkedin_url header
// alongside lv_linkedin_url, never dispatched under its own name). lv_phone_2 /
// lv_mobilephone_2 (Phase 72 Plan 05, D-72-11/D-72-12) join the same exemption for a
// third reason: they are WRITE-ONLY overflow slots the merge engine's own
// opts.rankedByField routing populates from a live waterfall disagreement -- no CSV
// column has ever named a "second phone", and none ever will (D-72-11 forbids a `_3`
// the same way it forbids a CSV route for these two).
const LANE_SIDE_ONLY_EXEMPTION = new Set([
  "lv_linkedin_url", "hs_linkedin_url", "lv_phone_2", "lv_mobilephone_2",
]);

test("every field_policy.yaml contacts key reachable from a CSV column has a canonical alias target, except the named lane-side-only exemption", () => {
  const policyKeys = new Set(policyContactsKeys());
  const canonicalTargets = new Set(columnMappingCanonicalTargets());

  const uncovered = [...policyKeys].filter((k) => !canonicalTargets.has(k)).sort();

  assert.deepEqual(
    uncovered,
    [...LANE_SIDE_ONLY_EXEMPTION].sort(),
    "config/field_policy.yaml's contacts: block promotes a key with no route from a CSV " +
    "header — widen config/column_mapping.yaml's aliases (and n8n/code/columnMap.js's " +
    "ALIASES) to cover it, never a second key list. If the new key is genuinely " +
    "lane-side-only like lv_linkedin_url/hs_linkedin_url, add it to this test's own " +
    "LANE_SIDE_ONLY_EXEMPTION set with a comment naming the decision that makes it so."
  );
});

// --- The committed ingest lane's actual candidate loop -----------------------------------

function ingestCandidateLoopFields() {
  const wf = JSON.parse(
    fs.readFileSync(path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json"), "utf8")
  );
  const node = wf.nodes.find((n) => n.name === "Merge Contacts");
  assert.ok(node, "Merge Contacts node not found in n8n/wf_contact_ingest_cloud.json");
  const js = node.parameters.jsCode;
  const m = /for\s*\(const f of \[([\s\S]*?)\]\)/.exec(js);
  assert.ok(m, "for (const f of [...]) candidate loop not found in Merge Contacts jsCode");
  const fields = [];
  const re = /"([A-Za-z0-9_]+)"/g;
  let mm;
  while ((mm = re.exec(m[1]))) fields.push(mm[1]);
  assert.ok(fields.length > 0, "extracted an empty candidate-loop field list — regex drifted");
  return fields;
}

test("the committed ingest lane's candidate loop reaches no key that neither the policy nor the column map governs", () => {
  const governed = new Set([...policyContactsKeys(), ...columnMappingCanonicalTargets()]);
  const loopFields = ingestCandidateLoopFields();

  const ungoverned = loopFields.filter((f) => !governed.has(f));

  assert.deepEqual(
    ungoverned,
    [],
    "n8n/wf_contact_ingest_cloud.json's Merge Contacts candidate loop reads a field " +
    "neither config/field_policy.yaml's contacts: block nor config/column_mapping.yaml's " +
    "canonical targets govern — widen the YAML the field actually belongs to (policy for " +
    "a merge-gated property, column_mapping for a CSV-only identity field like company), " +
    "never add a second, ungoverned key list to the candidate loop."
  );
});

// --- columnMap.js ALIASES vs config/column_mapping.yaml aliases: canonical-target SET ----
// columnMapAliasParity.test.mjs already pins the whole alias MAP (deepEqual, every header
// -> canonical pair). This assertion is narrower and explicit: the deduplicated SET of
// canonical targets alone, which is exactly what extraction.canonical_props() derives.

test("columnMap.js ALIASES and config/column_mapping.yaml aliases resolve to the same canonical-target set", () => {
  const jsTargets = [...new Set(Object.values(ALIASES))].sort();
  const yamlTargets = [...new Set(yamlAliasValues())].sort();

  assert.deepEqual(
    jsTargets,
    yamlTargets,
    "n8n/code/columnMap.js's ALIASES and config/column_mapping.yaml's aliases resolve to " +
    "different canonical-target sets — widen config/column_mapping.yaml AND mirror the " +
    "same addition into n8n/code/columnMap.js's ALIASES in the same commit, never one " +
    "file alone."
  );
});
