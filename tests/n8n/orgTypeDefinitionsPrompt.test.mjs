// Regression guard for the folded todo
// .planning/todos/pending/2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md
// (Phase 49 Plan 03): the production n8n research prompt used to enumerate the nine
// lv_org_type keys with no definitions, reproducing the statutory-origin misclassification
// Phase 48-07 fixed on the Python side (src/web_research.py's RESEARCH_SYSTEM /
// RACING_NSW_ORG_TYPE_SYSTEM render org_type_definitions_block()). Mirrors
// tests/test_taxonomy_conformance.py's
// test_tx10_every_org_type_has_a_definition_and_both_prompts_render_them on the n8n side.
//
// IMPORTANT (why this test RUNS the node instead of grepping its jsCode text): as of Task
// 49-03-01, n8n/code/taxonomy.generated.js carries an ORG_TYPE_DEFINITIONS const that is
// inlined into "Build Research Request"'s jsCode regardless of whether
// researchSystemPrompt() actually USES it -- the module is already inlined there for
// ORG_TYPES/CONTENT_TYPES. A substring check over the raw jsCode text would therefore
// still pass even if researchSystemPrompt() were reverted to a bare key list, because the
// (then-unused) const would still be sitting in the inlined module text. This test instead
// executes the node's own jsCode (the researchChainRowFlow.test.mjs idiom -- `new
// Function` over the actual emitted code, the same thing n8n's Code node does at runtime)
// and asserts against the model-facing prompt string it actually RETURNS
// (research_request_body.system), so a revert of researchSystemPrompt() fails this test
// even though the inlined const would still be present.
//
// NOTE: this executes the repo's OWN committed workflow jsCode via `new Function` -- the
// same thing n8n's Code node does at runtime -- over a fixed, in-repo node name. No
// external or untrusted input is ever interpolated into the function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const require = createRequire(import.meta.url);

const { ORG_TYPES, ORG_TYPE_DEFINITIONS } = require(
  path.join(ROOT, "n8n/code/taxonomy.generated.js")
);

function buildResearchSystemPrompt(wfFile) {
  const wf = JSON.parse(fs.readFileSync(path.join(ROOT, "n8n", wfFile), "utf8"));
  const node = wf.nodes.find((n) => n.name === "Build Research Request");
  assert.ok(node, `${wfFile}: "Build Research Request" node not found`);

  const row = {
    research_needed: true,
    identity_keys: { domain: "exampleco.example" },
    existingRecord: { domain: "exampleco.example" },
  };
  const $input = { all: () => [{ json: row }] };
  const $now = new Date("2026-08-13T00:00:00Z");
  // $vars/$env stubbed for the local-live variant's runtime flag reads (cloud bakes
  // literals and never touches either).
  const fn = new Function(
    "$input", "$vars", "$env", "$node", "$now", "$today",
    `"use strict";\n${node.parameters.jsCode}`
  );
  const out = fn($input, undefined, {}, {}, $now, $now) || [];
  assert.equal(out.length, 1, `${wfFile}: Build Research Request emitted one row`);
  const body = out[0].json.research_request_body;
  assert.ok(body && typeof body.system === "string", `${wfFile}: research_request_body.system is a string`);
  return body.system;
}

// The predicate under test, run against the node's ACTUAL returned prompt string --
// never against raw jsCode text (see header note above).
function everyOrgTypeKeyAndDefinitionPresent(promptText) {
  return ORG_TYPES.every(
    (k) => promptText.includes(k) && promptText.includes(ORG_TYPE_DEFINITIONS[k])
  );
}

for (const wf of ["wf_enrichment_cloud.json", "wf_enrichment_local_live.json"]) {
  test(`${wf}: Build Research Request's returned system prompt carries every org type's key and definition`, () => {
    const prompt = buildResearchSystemPrompt(wf);
    assert.equal(everyOrgTypeKeyAndDefinitionPresent(prompt), true);
    // Anchor cases from the Racing NSW misclassification fix (Phase 48-07) -- must reach
    // the n8n prompt too, not just the Python ones.
    assert.ok(prompt.includes("QRIC"), "regulator definition names QRIC");
    assert.ok(prompt.includes("Racing NSW"), "governing_body_league definition names Racing NSW");
    // The enum constraint is unweakened -- the prompt still names all nine keys as the
    // allowed value set via the original bare JSON.stringify(ORG_TYPES) line.
    assert.ok(prompt.includes(JSON.stringify(ORG_TYPES)), "allowed_org_types enum list unchanged");
  });
}

test("negative control: a bare key-only prompt fails the same predicate", () => {
  // Proves everyOrgTypeKeyAndDefinitionPresent has teeth -- it must return false when
  // definitions are absent from the string under test, not trivially true just because
  // every org-type key happens to appear (e.g. in the enum list alone). This is exactly
  // the shape of the prompt BEFORE this plan's fix.
  const keyOnlyPrompt = "allowed_org_types: " + JSON.stringify(ORG_TYPES) + ".";
  assert.equal(everyOrgTypeKeyAndDefinitionPresent(keyOnlyPrompt), false);
});
