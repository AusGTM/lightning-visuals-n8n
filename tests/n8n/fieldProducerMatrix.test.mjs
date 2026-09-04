// tests/n8n/fieldProducerMatrix.test.mjs
//
// Phase 66 Plan 02 Task 1 (D-66-07, RICH-02, RICH-05) — the producer/consumer matrix, both
// lanes, as a derived test. Every input is READ from the source of truth at runtime (never
// a hardcoded copy):
//   - config/field_policy.yaml            -> policy key set, class, promote_to_canonical,
//                                             allow_web_research (companies' research-lane
//                                             producer signal)
//   - n8n/code/normalizeProviders.js       -> the `_push` field-key literals each provider
//                                             branch emits, split contacts vs companies
//   - scripts/build_cloud_workflows.py     -> the PN-1 `winners.X` -> `candidate.lv_X`
//                                             rename mappings (contacts only)
//   - n8n/wf_enrichment_cloud.json         -> the REGENERATED `REQUIRED` array (per lane's
//                                             gate node) and the REGENERATED search-node
//                                             property list (what the workflow will
//                                             actually request/chase)
//
// A field with a policy entry and no producer at all is reported BY NAME in the failure
// message — that is the mechanism that would have caught a second lv_linkedin_url instead
// of it being found by hand (D-66-07).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

// --- config/field_policy.yaml: hand-rolled block extractor (repo convention — no npm YAML
// dependency; same shape as tests/n8n/companyNativeFields.test.mjs and
// tests/n8n/enrichment.test.mjs's yamlContactsKeys) -----------------------------------------

function yamlSectionText(yamlText, sectionName) {
  const lines = yamlText.split("\n");
  const startIdx = lines.findIndex((l) => l === `${sectionName}:`);
  assert.ok(startIdx !== -1, `config/field_policy.yaml section ${sectionName} not found`);
  const body = [];
  for (let i = startIdx + 1; i < lines.length; i++) {
    if (/^\S/.test(lines[i])) break; // dedent to column 0 -> next top-level section
    body.push(lines[i]);
  }
  return body.join("\n");
}

function yamlKeys(sectionText) {
  const keys = [];
  for (const line of sectionText.split("\n")) {
    const m = /^  ([A-Za-z0-9_]+):\s*$/.exec(line);
    if (m) keys.push(m[1]);
  }
  return keys;
}

function yamlFieldBlock(sectionText, fieldName) {
  const lines = sectionText.split("\n");
  const fieldRe = new RegExp(`^  ${fieldName}:\\s*$`);
  const startIdx = lines.findIndex((l) => fieldRe.test(l));
  if (startIdx === -1) return null;
  const block = [];
  for (let i = startIdx + 1; i < lines.length; i++) {
    if (/^  \S/.test(lines[i])) break; // next top-level (2-space) field or comment
    block.push(lines[i]);
  }
  const text = block.join("\n");
  return {
    class: (text.match(/class:\s*(\S+)/) || [])[1] || null,
    promote_to_canonical: /promote_to_canonical:\s*true/.test(text),
    allow_web_research: /allow_web_research:\s*true/.test(text),
  };
}

function loadPolicy(lane) {
  const yamlText = fs.readFileSync(path.join(ROOT, "config/field_policy.yaml"), "utf8");
  const section = yamlSectionText(yamlText, lane);
  const keys = yamlKeys(section);
  const policy = {};
  for (const k of keys) policy[k] = yamlFieldBlock(section, k);
  return policy;
}

// --- n8n/code/normalizeProviders.js: derive pushed field-key literals per lane -------------
// Split each provider function's body on its `if (objectType === "contacts") { ... } else {
// ... }` boundary (verified identical shape across all three functions — 2-space indent
// `} else {` on its own line) and collect quoted-string literals from each half. A dynamic
// `_push(out, field, ...)` call site (Lusha/Apollo phone: `field` is "phone"/"mobilephone"
// chosen by a ternary) still surfaces here because the branch's OTHER literal strings
// ("phone"/"mobilephone") appear as quoted text in the same block — this is a broader
// "does this literal appear in this branch's source" scan, not a call-site parse, which is
// why it tolerates the ternary without special-casing it.

const NORMALIZE_PROVIDERS_SRC = fs.readFileSync(
  path.join(ROOT, "n8n/code/normalizeProviders.js"), "utf8");

function functionBody(src, fnName) {
  const marker = `\nfunction ${fnName}(`;
  const start = src.indexOf(marker);
  assert.ok(start !== -1, `function ${fnName} not found in normalizeProviders.js`);
  const rest = src.slice(start + 1);
  const nextFnMatch = /\nfunction [A-Za-z_]/.exec(rest.slice(1));
  const end = nextFnMatch ? start + 1 + 1 + nextFnMatch.index : src.length;
  return src.slice(start, end);
}

function splitContactsCompanies(body) {
  const marker = 'if (objectType === "contacts") {';
  const ifIdx = body.indexOf(marker);
  assert.ok(ifIdx !== -1, "objectType contacts branch not found in function body");
  const afterIf = ifIdx + marker.length;
  const elseMarker = "\n  } else {\n";
  const elseIdx = body.indexOf(elseMarker, afterIf);
  assert.ok(elseIdx !== -1, "objectType companies else-branch not found in function body");
  const contactsText = body.slice(afterIf, elseIdx);
  const companiesText = body.slice(elseIdx + elseMarker.length);
  return { contacts: contactsText, companies: companiesText };
}

function literalFields(text) {
  const set = new Set();
  const re = /"([a-z][a-z0-9_]*)"/g;
  let m;
  while ((m = re.exec(text))) set.add(m[1]);
  return set;
}

const PROVIDER_FNS = ["lushaCandidates", "apolloCandidates", "zoominfoCandidates"];

function pushedFieldsByLane() {
  const contacts = new Set();
  const companies = new Set();
  for (const fn of PROVIDER_FNS) {
    const body = functionBody(NORMALIZE_PROVIDERS_SRC, fn);
    const split = splitContactsCompanies(body);
    for (const f of literalFields(split.contacts)) contacts.add(f);
    for (const f of literalFields(split.companies)) companies.add(f);
  }
  return { contacts, companies };
}

const PUSHED = pushedFieldsByLane();

// --- scripts/build_cloud_workflows.py: PN-1 rename mappings (contacts only) ---------------
// Finds every `winners.X` read site in the builder and keeps it as a rename only when the
// prefixed sibling (`.lv_X` or `"lv_X"`) also appears in the source — that is the same
// evidence D-66-03 asks a human reader to find by hand (candidate.lv_linkedin_url /
// candidate.lv_persona_group), done mechanically instead.

const BUILDER_SRC = fs.readFileSync(
  path.join(ROOT, "scripts/build_cloud_workflows.py"), "utf8");

function pn1Renames(src) {
  const renames = {};
  const re = /winners\.([a-z_]+)/g;
  let m;
  while ((m = re.exec(src))) {
    const unprefixed = m[1];
    const prefixed = "lv_" + unprefixed;
    if (src.includes(`.${prefixed}`) || src.includes(`"${prefixed}"`)) {
      renames[prefixed] = unprefixed;
    }
  }
  return renames;
}

const PN1_RENAMES = pn1Renames(BUILDER_SRC); // { lv_linkedin_url: "linkedin_url", lv_persona_group: "persona_group" }

// --- n8n/wf_enrichment_cloud.json: the REGENERATED gate REQUIRED list + search property list

function loadWorkflowNodes() {
  const wf = JSON.parse(fs.readFileSync(path.join(ROOT, "n8n", "wf_enrichment_cloud.json"), "utf8"));
  const byName = {};
  for (const n of wf.nodes) byName[n.name] = n;
  return byName;
}

const GATE_NODE_NAME = { contacts: "Enrichment Gate", companies: "Company Gate" };
const SEARCH_NODE_NAME = { contacts: "HubSpot Search", companies: "HubSpot Company Search" };

function requiredListFromGate(jsCode) {
  const m = /const REQUIRED\s*=\s*\[([\s\S]*?)\]/.exec(jsCode);
  assert.ok(m, "const REQUIRED = [...] not found in gate node jsCode");
  const arr = [];
  const re = /"([A-Za-z0-9_]+)"/g;
  let mm;
  while ((mm = re.exec(m[1]))) arr.push(mm[1]);
  return arr;
}

function laneRequired(lane) {
  const nodes = loadWorkflowNodes();
  const node = nodes[GATE_NODE_NAME[lane]];
  assert.ok(node, `gate node not found for lane ${lane}: ${GATE_NODE_NAME[lane]}`);
  return requiredListFromGate(node.parameters.jsCode);
}

function laneSearchPropertiesText(lane) {
  const nodes = loadWorkflowNodes();
  const node = nodes[SEARCH_NODE_NAME[lane]];
  assert.ok(node, `search node not found for lane ${lane}: ${SEARCH_NODE_NAME[lane]}`);
  return JSON.stringify(node.parameters);
}

// --- producer predicate ---------------------------------------------------------------------
// A field has a producer when: (a) some provider branch pushes it directly under that key
// for this lane, or (b) — contacts only — a provider pushes the PN-1 unprefixed sibling and
// the builder renames it at the merge boundary, or (c) — companies only — the field policy
// marks it `allow_web_research: true`, meaning the Claude web-research lane (webResearch.js)
// is its producer (the research lane spreads `{...raw.data}` wholesale rather than pushing
// named literals, so `allow_web_research` — the merge-policy flag that gates promoting a
// research candidate for exactly this field — is the derivable signal for "research
// produces this field", not a source-text scan of webResearch.js's generic spread).

function producerFor(lane, field, policyEntry) {
  if (PUSHED[lane].has(field)) return "push";
  if (lane === "contacts" && PN1_RENAMES[field] && PUSHED.contacts.has(PN1_RENAMES[field])) {
    return `push(${PN1_RENAMES[field]})+PN-1 rename`;
  }
  if (lane === "companies" && policyEntry && policyEntry.allow_web_research) {
    return "claude_web research";
  }
  return null;
}

function recomputedOutput(policyEntry) {
  return policyEntry.class === "score_output" || policyEntry.class === "veto_output";
}

// --- Known, documented gaps (NOT assertion escape hatches — neither entry is in scope of
// any of the four assertions below; both are pinned so a future change silently closing or
// widening the gap is caught, per D-66-07's "reported BY NAME" requirement extending to
// facts about absence, not just presence). ---------------------------------------------------

const KNOWN_GAPS = [
  {
    lane: "contacts",
    field: "lv_linkedin_url",
    what: "ZoomInfo pushes no linkedin producer for lv_linkedin_url",
    reason:
      "ZOOM_OUTPUT_FIELDS is account-verified; an unprobed output field risks a batch-wide " +
      "400 (zoominfo-gtm-enrich-400-blocker memory). Not a chase-gate hole: Apollo already " +
      "produces lv_linkedin_url (66-01 Task 3). Precedent for probing before trusting a new " +
      "field: scripts/probe_zoominfo_location_fields.mjs.",
  },
  {
    lane: "companies",
    field: "domain",
    what: "companies domain has no candidate source at all",
    reason:
      "manual_protected / promote_to_canonical: false, so out of scope for all four " +
      "assertions below by construction — but genuinely producer-less: no provider branch " +
      "and no research field pushes/spreads `domain`. Open todo, reviewed by 66-CONTEXT.md's " +
      "<deferred> block and deliberately NOT folded into this phase: " +
      ".planning/todos/pending/2026-09-04-company-domain-has-no-candidate-source.md",
  },
];

test("known gap: ZoomInfo's contacts branch pushes no linkedin-shaped field", () => {
  const body = splitContactsCompanies(functionBody(NORMALIZE_PROVIDERS_SRC, "zoominfoCandidates"));
  const fields = literalFields(body.contacts);
  assert.ok(!fields.has("linkedin_url") && !fields.has("lv_linkedin_url"),
    "ZoomInfo now pushes a linkedin field — update KNOWN_GAPS and 66-COVERAGE.md, this pin should be removed/revised");
});

test("known gap: no provider branch pushes a companies `domain` candidate", () => {
  for (const fn of PROVIDER_FNS) {
    const body = splitContactsCompanies(functionBody(NORMALIZE_PROVIDERS_SRC, fn));
    const fields = literalFields(body.companies);
    assert.ok(!fields.has("domain"),
      `${fn} now pushes a companies domain candidate — update KNOWN_GAPS, 66-COVERAGE.md and the open todo`);
  }
});

// --- Assertion 1 (D-66-07 producer gate) ----------------------------------------------------

test("D-66-07 producer gate: every promotable, non-recomputed policy key has a producer", () => {
  for (const lane of ["contacts", "companies"]) {
    const policy = loadPolicy(lane);
    const failures = [];
    for (const [field, entry] of Object.entries(policy)) {
      if (!entry || !entry.promote_to_canonical) continue;
      if (recomputedOutput(entry)) continue;
      if (!producerFor(lane, field, entry)) failures.push(`${lane}.${field}`);
    }
    assert.deepEqual(failures, [], `producer-less fields (D-66-07): ${failures.join(", ")}`);
  }
});

// --- Assertion 2 (fetch gate) ----------------------------------------------------------------
// Generalises 66-01 Task 2's contacts-only fix: every member of a lane's REQUIRED list must
// be requested by that lane's search node, or the fill_blank_only/stale_refreshable
// non-clobber comparison silently reads `undefined` and turns non-clobber into clobber.

test("fetch gate: every REQUIRED member is requested by the lane's search node", () => {
  for (const lane of ["contacts", "companies"]) {
    const required = laneRequired(lane);
    const searchText = laneSearchPropertiesText(lane);
    const missing = required.filter((f) => !searchText.includes(f));
    assert.deepEqual(missing, [], `${lane}: REQUIRED but not fetched: ${missing.join(", ")}`);
  }
});

// --- Assertion 3 (D-66-01/RICH-02 chase gate) -------------------------------------------------
// Every policy key with a producer, promotable, and not a recomputed output must be chased
// (appear in REQUIRED). This is what makes the companies REQUIRED list DERIVED rather than
// chosen by intuition (RICH-02) — at the end of Task 1 (before Task 2 widens ENRICH_CO_GATE)
// this is EXPECTED to fail for the companies lane; that is the audit result Task 2 acts on.

test("chase gate: every producer-having, promotable, non-recomputed policy key is REQUIRED", () => {
  for (const lane of ["contacts", "companies"]) {
    const policy = loadPolicy(lane);
    const required = new Set(laneRequired(lane));
    const failures = [];
    for (const [field, entry] of Object.entries(policy)) {
      if (!entry || !entry.promote_to_canonical) continue;
      if (recomputedOutput(entry)) continue;
      if (!producerFor(lane, field, entry)) continue; // assertion 1's job, not this one's
      if (!required.has(field)) failures.push(`${lane}.${field}`);
    }
    assert.deepEqual(failures, [], `producer-having, promotable fields NOT chased: ${failures.join(", ")}`);
  }
});

// --- Assertion 4 (D-66-03 PN-1 seam) ----------------------------------------------------------
// A push under the PREFIXED spelling is the silent no-op D-66-03 names — scoreEnrichment.js
// groups candidates by the pushed key, so a `lv_linkedin_url` push would never reach the
// builder's `winners.linkedin_url` read at all, and no error would ever surface.

test("D-66-03 PN-1 seam: normalizeProviders.js pushes the UNPREFIXED key, never the renamed one", () => {
  for (const [prefixed, unprefixed] of Object.entries(PN1_RENAMES)) {
    assert.ok(PUSHED.contacts.has(unprefixed),
      `expected a push under the unprefixed key "${unprefixed}" for the ${prefixed} PN-1 rename`);
    assert.ok(!PUSHED.contacts.has(prefixed),
      `normalizeProviders.js pushes "${prefixed}" directly — this is the silent no-op D-66-03 warns about; the merge reads winners.${unprefixed}, not winners.${prefixed}`);
  }
  assert.ok(Object.keys(PN1_RENAMES).length >= 2,
    "expected at least the two known PN-1 renames (lv_linkedin_url, lv_persona_group) to be discovered");
});

test("D-66-03 PN-1 seam: the policy/search-property spelling is the PREFIXED key", () => {
  const policy = loadPolicy("contacts");
  for (const prefixed of Object.keys(PN1_RENAMES)) {
    assert.ok(policy[prefixed], `config/field_policy.yaml contacts.${prefixed} entry not found`);
  }
});

export { loadPolicy, PUSHED, PN1_RENAMES, KNOWN_GAPS, laneRequired, producerFor, recomputedOutput };
