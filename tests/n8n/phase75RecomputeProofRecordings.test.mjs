// tests/n8n/phase75RecomputeProofRecordings.test.mjs
//
// Phase 75 (2026-09-20): the two live proof recordings for the config-driven region
// whitelist and scoring-version write (`exec_12682`, `exec_12683`) are the `[observed
// live]` evidence for D-75-01/02/03/05/06/12/17/19 and prohibition 22 in 75-VERIFICATION.md.
// Nothing previously read them. These are READER assertions over the frozen runData, in
// the style of v1RuntimeRecordings.test.mjs — no graph is walked here.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const FROZEN = path.join(ROOT, "tests", "n8n", "fixtures", "frozen");
const load = (id) => JSON.parse(fs.readFileSync(path.join(FROZEN, `exec_${id}.runData.json`), "utf8"));
const firstItem = (run) => run[0].data.main[0][0].json;

const EXPECTED_VERSION = (() => {
  const raw = fs.readFileSync(path.join(ROOT, "config", "icp_scoring.yaml"), "utf8");
  const m = raw.match(/^version:\s*"([^"]+)"/m);
  assert.ok(m, "config/icp_scoring.yaml must declare a top-level version: \"...\"");
  return m[1];
})();

const EXPECTED_OUTSIDE_REGIONS_REASON = (() => {
  const raw = fs.readFileSync(path.join(ROOT, "config", "icp_scoring.yaml"), "utf8");
  const section = raw.split("outside_home_regions:")[1];
  assert.ok(section, "config/icp_scoring.yaml must declare hard_vetoes.outside_home_regions");
  const m = section.match(/reason:\s*"([^"]+)"/);
  assert.ok(m, "outside_home_regions must declare a reason string");
  return m[1];
})();

const CASES = [
  {
    id: 12682,
    companyId: "9604614548",
    region: "AU",
    flag: "false",
    flagNum: "0",
    reason: "",
  },
  {
    id: 12683,
    companyId: "17317850381",
    region: "Other",
    flag: "true",
    flagNum: "1",
    reason: EXPECTED_OUTSIDE_REGIONS_REASON,
  },
];

for (const c of CASES) {
  test(`exec_${c.id}: settled success on v1 with exactly 71 runData nodes`, () => {
    const e = load(c.id);
    assert.equal(e.execution_id, String(c.id));
    assert.equal(e.status, "success");
    assert.equal(e.settings.executionOrder, "v1");
    assert.equal(Object.keys(e.runData).length, 71);
  });

  test(`exec_${c.id}: Decide Company Action ran exactly once with exactly one item`, () => {
    const rd = load(c.id).runData;
    const decide = rd["Decide Company Action"];
    assert.equal(decide.length, 1, "Decide Company Action must run exactly once");
    assert.equal(decide[0].data.main[0].length, 1, "must carry exactly one item");
  });

  test(`exec_${c.id}: recompute was an explicit request, not a gate-derived version-stale reroute`, () => {
    const rd = load(c.id).runData;
    const parsed = firstItem(rd["Parse HubSpot Event"]);
    assert.equal(parsed.recompute, true, "Parse HubSpot Event must carry the explicit recompute request flag");

    const gated = firstItem(rd["Company Gate"]);
    assert.equal(gated.recompute, true);
    assert.equal(gated.recompute_reason, "requested", "must be the explicit request, never version_stale");
    const stampedVersion = gated.existingRecord?.lv_icp_scoring_version;
    assert.ok(
      stampedVersion === null || stampedVersion === undefined,
      "no record in these fixtures carried lv_icp_scoring_version yet — the version-stale reroute stays [documented] only until one does"
    );
  });

  test(`exec_${c.id}: Company Gate read the expected geography input`, () => {
    const rd = load(c.id).runData;
    const gated = firstItem(rd["Company Gate"]);
    assert.equal(gated.existingRecord?.lv_country_region_normalized, c.region);
  });

  test(`exec_${c.id}: Decide's derived patch is exactly the four-property recompute PATCH (D-75-16)`, () => {
    const rd = load(c.id).runData;
    const br = firstItem(rd["Build Response"]);
    assert.deepEqual(
      Object.keys(br.properties).sort(),
      ["lv_anti_icp_flag", "lv_anti_icp_flag_num", "lv_anti_icp_reason", "lv_icp_scoring_version"]
    );
    assert.equal(
      br.properties.lv_icp_scoring_version,
      EXPECTED_VERSION,
      `stamped version must equal config/icp_scoring.yaml's version: — RED here means the fixtures need re-proving against a version bump`
    );
    assert.equal(br.properties.lv_anti_icp_flag, c.flag);
    assert.equal(br.properties.lv_anti_icp_flag_num, c.flagNum);
    assert.equal(br.properties.lv_anti_icp_reason, c.reason);
  });

  test(`exec_${c.id}: Build Response emitted exactly one write_blocked row, nothing armed`, () => {
    const rd = load(c.id).runData;
    const runs = rd["Build Response"];
    assert.equal(runs.length, 1, "Build Response must run exactly once");
    const items = runs[0].data.main[0];
    assert.equal(items.length, 1, "exactly one row");
    const row = items[0].json;
    assert.equal(row.action, "write_blocked");
    assert.equal(row.hs_object_id, c.companyId);
    assert.equal(row.write_allowed, false);
  });

  test(`exec_${c.id}: no HubSpot write and no provider/research/judge HTTP call ran`, () => {
    const rd = load(c.id).runData;
    const names = Object.keys(rd);
    assert.ok(!names.includes("HubSpot Company Update"), "no write node may have run disarmed");
    // The only real HubSpot data-fetch node this lane runs is the by-id fetch (a search
    // node); no Apollo/Lusha/ZoomInfo HTTP request node, and no Anthropic/research/
    // judge/haiku/sonnet call, may appear among the nodes that actually ran.
    const forbiddenSubstrings = [
      "Apollo HTTP", "Lusha HTTP", "ZoomInfo HTTP",
      "Claude Web", "Anthropic", "Research HTTP", "Judge", "Haiku", "Sonnet",
    ];
    for (const name of names) {
      for (const bad of forbiddenSubstrings) {
        assert.ok(!name.includes(bad), `node "${name}" looks like a live provider/research/judge call — must not have run`);
      }
    }
    assert.ok(names.includes("HubSpot Company Fetch By Id"), "the one legitimate HubSpot fetch node must have run");
  });

  test(`exec_${c.id}: Webhook Trigger headers stay redacted, never a live object`, () => {
    const rd = load(c.id).runData;
    const wt = firstItem(rd["Webhook Trigger"]);
    assert.equal(typeof wt.headers, "string", "headers must be replaced wholesale by the redaction placeholder, not a live object");
    assert.ok(wt.headers.startsWith("<redacted"), `headers must start with the redaction placeholder, got: ${wt.headers}`);
  });
}
