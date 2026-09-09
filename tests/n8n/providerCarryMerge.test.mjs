// tests/n8n/providerCarryMerge.test.mjs — Phase 70 Plan 04 Task 1 (D-70-04).
//
// Structural: every provider and HubSpot HTTP node on the enrichment lane's identity-
// search, provider-enrich, and research/judge hops must have EXACTLY ONE consumer, and
// that consumer must be an `n8n-nodes-base.merge` node — the carry-merge mechanism
// `splice_carry_merge_after` (70-02) generalises. Before this task, each of these HTTP
// nodes fed its adapter/validator DIRECTLY, and that adapter recovered the pre-hop row
// with a by-name read (Pitfall 4) instead.
//
// Behavioral (identity-contamination, Pitfall 4): a TWO-ROW research/judge chain, hand-
// walked over the committed jsCode exactly as tests/n8n/researchChainRowFlow.test.mjs
// already does for one row (simulating each real n8n Merge's combineByPosition —
// row-last, "preferLast" — rather than the old by-name recovery), proves each row's
// research/judge request body carries THAT row's own gate fields, never the other row's
// — the mix-up this repo's own by-name-recovery idiom could never even be tested against
// (there was no second row to mis-pair with; a paired-index recovery collapsing onto the
// wrong index would have looked identical to success on a batch of one).
//
// NOTE: this executes the repo's OWN committed workflow jsCode via `new Function` — the
// same mechanism n8n's Code node uses at runtime — over repo-controlled JSON. No
// external or untrusted input is ever interpolated into a function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

function loadWf() {
  return JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
}

// Every HTTP hop this task must carry the row across — contacts and companies branches,
// identity search/fetch, provider enrich, and research/judge.
const CARRIED_HTTP_HOPS = [
  "HubSpot Fetch By Id",
  "HubSpot Search",
  "HubSpot Linkedin Search",
  "HubSpot Name Search Fallback",
  "HubSpot Company Fetch By Id",
  "HubSpot Company Search",
  "HubSpot Company Name Search",
  "Lusha Enrich",
  "Apollo Match",
  "Lusha Company",
  "Apollo Org",
  "Claude Web Research",
  "Judge Call",
  "Contact Web Research",
  "Contact Judge Call",
];

function soleConsumer(wf, nodeName) {
  const spec = wf.connections[nodeName];
  const outs = (spec && spec.main) || [];
  const targets = [];
  for (const arr of outs) {
    for (const c of arr || []) targets.push(c.node);
  }
  return targets;
}

test("every carried HTTP hop's sole consumer is a Merge node (or a Wrap node feeding one)", () => {
  const wf = loadWf();
  const byName = new Map(wf.nodes.map((n) => [n.name, n]));
  const failures = [];
  for (const hop of CARRIED_HTTP_HOPS) {
    assert.ok(byName.has(hop), `fixture assumption: node ${hop} exists`);
    let targets = soleConsumer(wf, hop);
    // A provider hop whose raw response must survive further HTTP hops downstream
    // (the rest of the waterfall) is nested under a distinct key by a "Wrap * Result"
    // Code node BEFORE the carry merge — _wrap_provider_result_js's own precedent
    // (mirrors "Stash Name Primary Search" / 70-02's "Stash Domain Search"). Follow
    // that one hop before requiring a Merge.
    if (targets.length === 1 && /^Wrap .* Result$/.test(targets[0])) {
      targets = soleConsumer(wf, targets[0]);
    }
    if (targets.length !== 1 || byName.get(targets[0])?.type !== "n8n-nodes-base.merge") {
      failures.push(`${hop} -> [${targets.join(", ")}]`);
    }
  }
  assert.deepEqual(failures, [], `hops not yet carried via a Merge:\n${failures.join("\n")}`);
});

test("no by-name node lookup survives in the research/judge body builders' jsCode", () => {
  const wf = loadWf();
  const targets = [
    "Validate Research Output",
    "Validate Contact Research",
    "Apply Judge Verdict",
    "Apply Contact Judge Verdict",
    "Build Research Failure Response",
  ];
  const byName = new Map(wf.nodes.map((n) => [n.name, n]));
  const offenders = [];
  for (const name of targets) {
    const node = byName.get(name);
    assert.ok(node, `fixture assumption: node ${name} exists`);
    const js = node.parameters.jsCode || "";
    if (/\$\(\s*['"]/.test(js) || /\$\(name\)/.test(js)) offenders.push(name);
  }
  assert.deepEqual(offenders, [], `by-name reads survive in: ${offenders.join(", ")}`);
});

// --- Behavioral: 2-row hand-walked research/judge chain, Merge simulated ------------

const CHAIN = [
  { name: "Research Trigger Gate", http: false },
  { name: "Build Research Request", http: false },
  { name: "Claude Web Research", http: true },
  { name: "Validate Research Output", http: false },
  { name: "Judge Gate", http: false },
  { name: "Build Judge Request", http: false },
  { name: "Judge Call", http: true },
  { name: "Apply Judge Verdict", http: false },
];

function seedRow(domain, companyName) {
  return {
    identity_keys: { domain, companyName },
    existingRecord: { domain, name: companyName, lv_org_type: "" },
    scored: {
      best: { lv_org_type: { normalizedValue: "content_producer", source: "zoominfo", agreedBy: [] } },
      winners: { lv_org_type: "content_producer" }, sourcesByField: {},
    },
    gap_flag: true,
  };
}

function httpResponse(kind, tag) {
  if (kind === "Claude Web Research") {
    return {
      id: `msg-research-${tag}`, type: "message", role: "assistant",
      content: [{ type: "text", text: JSON.stringify({
        lv_org_type: "content_producer", confidence: 88,
        evidence_by_field: { lv_org_type: { url: `https://${tag}.example/about` } },
      }) }], model: "claude", usage: { output_tokens: 50 },
    };
  }
  return {
    id: `msg-judge-${tag}`, type: "message", role: "assistant",
    content: [{ type: "text", text: JSON.stringify({
      decision: "promote", chosen_field: "lv_org_type", confidence: 90, reason: `evidence-${tag}`,
    }) }], model: "claude", usage: {},
  };
}

// Runs the chain for a BATCH (n>1) of rows, simulating each real n8n Merge as
// `merge_node`'s own contract: combineByPosition, carried-row-last, "preferLast" wins a
// key clash — pairing item i of the HTTP response with item i of the pre-hop row.
function runChainBatch(wfPath, rows) {
  const wf = JSON.parse(fs.readFileSync(wfPath, "utf8"));
  const byName = {};
  for (const n of wf.nodes) byName[n.name] = n;

  let items = rows.map((r, i) => seedRow(r.domain, r.companyName));
  const trace = [];
  let threw = null;
  for (const step of CHAIN) {
    const node = byName[step.name];
    assert.ok(node, `node present: ${step.name}`);
    if (step.http) {
      // Real HTTP node: response REPLACES $json, but the carry Merge immediately after
      // it (this task's own deliverable) re-attaches the pre-hop row, row fields last.
      const responses = items.map((_, i) => httpResponse(step.name, rows[i].tag));
      items = items.map((row, i) => ({ ...responses[i], ...row }));
      continue;
    }
    const makeCtx = (current) => ({
      $input: {
        all: () => current.map((j) => ({ json: j })),
        get item() { return { json: current[0] }; },
      },
      $json: current[0],
    });
    const { $input, $json } = makeCtx(items);
    const $now = new Date("2026-09-10T00:00:00Z");
    const fn = new Function("$input", "$json", "$node", "$now", "$today",
      `"use strict";\n${node.parameters.jsCode}`);
    try {
      const out = fn($input, $json, {}, $now, $now) || [];
      items = out.map((it) => (it && it.json !== undefined ? it.json : it));
    } catch (e) { threw = { node: step.name, err: e.message }; break; }
    trace.push({ step: step.name, items: items.slice() });
  }
  return { trace, threw, final: items };
}

test("two-row batch: research and judge request bodies each carry their OWN row's gate fields", () => {
  const rows = [
    { domain: "aaa.example", companyName: "Aaa Co", tag: "aaa" },
    { domain: "bbb.example", companyName: "Bbb Co", tag: "bbb" },
  ];
  const { trace, threw } = runChainBatch(WF_PATH, rows);
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);

  const reqStep = trace.find((t) => t.step === "Build Research Request");
  assert.ok(reqStep, "Build Research Request ran");
  assert.equal(reqStep.items.length, 2, "both rows reached Build Research Request");
  for (let i = 0; i < rows.length; i++) {
    const body = reqStep.items[i].research_request_body;
    const parsed = JSON.parse(body.messages[0].content);
    assert.equal(parsed.company.domain, rows[i].domain,
      `row ${i}'s research request carries its OWN domain, never another row's`);
  }

  const validateStep = trace.find((t) => t.step === "Validate Research Output");
  assert.ok(validateStep, "Validate Research Output ran");
  for (let i = 0; i < rows.length; i++) {
    assert.equal(validateStep.items[i].existingRecord.domain, rows[i].domain,
      `row ${i}'s existingRecord survives its OWN HTTP hop, never swapped with the other row's`);
  }

  const judgeReqStep = trace.find((t) => t.step === "Build Judge Request");
  assert.equal(judgeReqStep.items.length, 2, "both rows reached Build Judge Request");

  const applyStep = trace.find((t) => t.step === "Apply Judge Verdict");
  assert.ok(applyStep, "Apply Judge Verdict ran");
  for (let i = 0; i < rows.length; i++) {
    assert.equal(applyStep.items[i].existingRecord.domain, rows[i].domain,
      `row ${i}'s existingRecord survives the judge HTTP hop too, never swapped`);
  }
});
