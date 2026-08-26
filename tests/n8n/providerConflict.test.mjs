// tests/n8n/providerConflict.test.mjs
//
// Gap-closure 58-06 Task 1: the shared cross-provider conflict predicate in isolation.
// n8n/code/providerConflict.js is a plain CommonJS module (never inlined-and-stripped
// here, unlike the wrapper tests) -- require() it directly.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const require = createRequire(import.meta.url);
const { detectConflicts, groupConflicts } = require(path.join(ROOT, "n8n/code/providerConflict.js"));

function scoredBundle(fieldEntries) {
  // fieldEntries: { [field]: [{source, value}, ...] } -- raw per-source normalized
  // values, scored the same way scoreEnrichment.js's scoreCandidates would (agreedBy =
  // other distinct sources whose normalizedValue matches; best = first entry, arbitrary
  // for these tests since ties are not under test here).
  const best = {};
  const sourcesByField = {};
  for (const [field, entries] of Object.entries(fieldEntries)) {
    sourcesByField[field] = entries.map((e) => ({ source: e.source, value: e.value }));
    const top = entries[0];
    const agreedBy = entries
      .filter((e) => e.source !== top.source && e.value === top.value)
      .map((e) => e.source);
    best[field] = { field, value: top.value, normalizedValue: top.value, source: top.source,
                     agreedBy };
  }
  return { best, sourcesByField };
}

test("two sources disagreeing on a watched field is a conflict", () => {
  const scored = scoredBundle({
    lv_country_region_normalized: [
      { source: "zoominfo", value: "Other" },
      { source: "lusha", value: "AU" },
    ],
  });
  const conflicts = detectConflicts(scored, ["lv_country_region_normalized"]);
  assert.equal(conflicts.length, 1);
  assert.equal(conflicts[0].field, "lv_country_region_normalized");
  assert.equal(conflicts[0].chosen, "Other");
  assert.equal(conflicts[0].chosen_source, "zoominfo");
  assert.deepEqual(conflicts[0].candidates,
    [{ source: "zoominfo", value: "Other" }, { source: "lusha", value: "AU" }]);
});

test("two sources agreeing on a watched field is not a conflict", () => {
  const scored = scoredBundle({
    country: [
      { source: "lusha", value: "australia" },
      { source: "apollo", value: "australia" },
    ],
  });
  const conflicts = detectConflicts(scored, ["country"]);
  assert.equal(conflicts.length, 0);
});

test("a single source on a watched field is never a conflict", () => {
  const scored = scoredBundle({
    lv_country_region_normalized: [{ source: "zoominfo", value: "Other" }],
  });
  const conflicts = detectConflicts(scored, ["lv_country_region_normalized"]);
  assert.equal(conflicts.length, 0);
});

test("a field not in the watched list is ignored even when it conflicts", () => {
  const scored = scoredBundle({
    lv_revenue_band: [
      { source: "zoominfo", value: "1-5M" },
      { source: "lusha", value: "5-50M" },
    ],
  });
  const conflicts = detectConflicts(scored, ["lv_country_region_normalized"]);
  assert.equal(conflicts.length, 0);
});

test("the same predicate called with two different watch lists returns different results " +
     "(the watched list is a real parameter, not a closed-over constant)", () => {
  const scored = scoredBundle({
    lv_revenue_band: [
      { source: "zoominfo", value: "1-5M" },
      { source: "lusha", value: "5-50M" },
    ],
    lv_country_region_normalized: [
      { source: "zoominfo", value: "Other" },
      { source: "lusha", value: "AU" },
    ],
  });
  const sizeOnly = detectConflicts(scored, ["lv_revenue_band", "lv_employee_band"]);
  const materialOnly = detectConflicts(scored, ["lv_country_region_normalized"]);
  assert.deepEqual(sizeOnly.map((c) => c.field), ["lv_revenue_band"]);
  assert.deepEqual(materialOnly.map((c) => c.field), ["lv_country_region_normalized"]);
});

test("no scored bundle at all yields no conflicts (never throws)", () => {
  assert.deepEqual(detectConflicts(undefined, ["lv_country_region_normalized"]), []);
  assert.deepEqual(detectConflicts({}, ["lv_country_region_normalized"]), []);
});

// --- groupConflicts: group membership -----------------------------------------------

const COUNTRY_REGION_GROUP = { name: "country_region", fields: ["lv_country_region_normalized", "country"] };
const ORG_TYPE_GROUP = { name: "org_type", fields: ["lv_org_type"] };

test("a conflict on ONE group member surfaces the WHOLE group, naming only the " +
     "actually-conflicted member", () => {
  const conflicts = detectConflicts(
    scoredBundle({
      lv_country_region_normalized: [
        { source: "zoominfo", value: "Other" },
        { source: "lusha", value: "AU" },
      ],
    }),
    COUNTRY_REGION_GROUP.fields,
  );
  const grouped = groupConflicts(conflicts, [COUNTRY_REGION_GROUP, ORG_TYPE_GROUP]);
  assert.equal(grouped.length, 1);
  assert.equal(grouped[0].group, "country_region");
  assert.deepEqual(grouped[0].fields, ["lv_country_region_normalized", "country"]);
  assert.equal(grouped[0].conflicts.length, 1);
  assert.equal(grouped[0].conflicts[0].field, "lv_country_region_normalized");
});

test("a group with no conflicted member is omitted entirely", () => {
  const conflicts = detectConflicts(
    scoredBundle({
      country: [
        { source: "lusha", value: "australia" },
        { source: "apollo", value: "australia" },
      ],
    }),
    COUNTRY_REGION_GROUP.fields,
  );
  const grouped = groupConflicts(conflicts, [COUNTRY_REGION_GROUP]);
  assert.equal(grouped.length, 0);
});

test("groupConflicts never throws on empty inputs", () => {
  assert.deepEqual(groupConflicts([], []), []);
  assert.deepEqual(groupConflicts(undefined, undefined), []);
});
